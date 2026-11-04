"""Machine-speed calibration for timing-sensitive tests.

Tests which assert on wall-clock durations can fail randomly on slow or
overloaded machines (e.g. CI runners), so rather than hard-coding thresholds
they should be loosened according to how the machine is performing. This
module measures that once per session and provides a `TimingTolerance` object
to scale thresholds with. In tests, request it via the `timing` fixture (see
`conftest.py`) and mark the test with `@pytest.mark.timing`::

    @pytest.mark.timing
    def test_something(timing):
        start = time.perf_counter()
        time.sleep(0.05)
        elapsed = time.perf_counter() - start
        assert timing.lower(0.05) <= elapsed <= timing.upper(0.06)

Two kinds of slowness are corrected for separately:

* CPU throughput: compute-bound durations (imports, call overhead) take longer
  on a slow or contended CPU, so are scaled multiplicatively (`scaled`).
* Scheduler/timer jitter: a sleep or wait overshoots by a roughly fixed amount
  regardless of how long it was, so upper bounds on durations which include
  sleeps get an additive slack per sleep (`upper`).

Lower bounds are never loosened (`lower` returns its input unchanged), as a
sleep never returns early, so a test failing a lower bound is a real bug.

Calibration can be overridden with environment variables, e.g. to pin
generous values on CI or to force strict thresholds locally:

* ``PSYCHOPY_TEST_TIME_SCALE``: CPU scale factor (``1`` for no scaling)
* ``PSYCHOPY_TEST_SLEEP_SLACK``: slack per sleep in seconds (``0`` for none)

This module deliberately only imports from the standard library, so that
using it doesn't affect tests of PsychoPy's import speed.
"""

import os
import time
from dataclasses import dataclass

__all__ = [
    "TimingTolerance",
    "getTimingTolerance",
    "isTimingCalibrated",
]

# iterations of the busy loop used to measure CPU speed
CPU_LOOP_ITERATIONS = 1000000
# number of times to run the busy loop, taking the fastest (rejects one-off
# stalls, so we measure the machine's speed rather than a hiccup)
CPU_LOOP_REPEATS = 3
# time the busy loop takes on a mid-range PC, a machine taking this long gets
# a scale of 1
REF_CPU_SECONDS = 0.1
# limit on how much thresholds can be loosened, so that a very slow machine
# can't make them meaningless
MAX_CPU_SCALE = 10.0

# duration of each sleep used to measure overshoot, and how many to take
SLEEP_PROBE_SECONDS = 0.005
SLEEP_PROBE_REPEATS = 20
# percentile of measured overshoots to use as slack
SLEEP_PERCENTILE = 90
# minimum and maximum slack per sleep (s)
MIN_SLEEP_SLACK = 0.005
MAX_SLEEP_SLACK = 0.05

ENV_TIME_SCALE = "PSYCHOPY_TEST_TIME_SCALE"
ENV_SLEEP_SLACK = "PSYCHOPY_TEST_SLEEP_SLACK"


@dataclass(frozen=True)
class TimingTolerance:
    """Factors to scale timing thresholds in tests by, according to how fast
    this machine is.

    Attributes
    ----------
    cpuRatio : float
        Time the calibration busy loop took relative to a mid-range PC,
        unclamped (so less than 1 on a fast machine).
    cpuScale : float
        `cpuRatio` clamped to between 1 and `MAX_CPU_SCALE`, so thresholds
        are never tightened on fast machines.
    sleepSlack : float
        Typical worst-case overshoot (s) of a single sleep/wait.
    source : str
        Where the values came from: "measured", "env" or "measured+env".
    """
    cpuRatio: float
    cpuScale: float
    sleepSlack: float
    source: str = "measured"

    def scaled(self, threshold, clamp=True):
        """Scale an upper limit on a compute-bound duration (e.g. an import or
        function call overhead) by CPU speed.

        Parameters
        ----------
        threshold : float
            Maximum allowed duration (s) on a mid-range PC.
        clamp : bool
            If True (default), never return less than `threshold`. If False,
            the limit is tightened on machines faster than a mid-range PC,
            which is stricter but more sensitive to calibration noise.

        Returns
        -------
        float
        """
        if clamp:
            return threshold * self.cpuScale
        return threshold * self.cpuRatio

    def upper(self, threshold, nSleeps=1):
        """Loosen an upper limit on a wall-clock duration which includes
        sleeps or waits.

        Parameters
        ----------
        threshold : float
            Maximum allowed duration (s) on an idle machine.
        nSleeps : int
            Number of sleeps/waits within the measured duration, each of
            which may overshoot by up to `sleepSlack`.

        Returns
        -------
        float
        """
        return threshold * self.cpuScale + nSleeps * self.sleepSlack

    def lower(self, threshold):
        """Lower limit on a duration, returned unchanged.

        Machine slowness only ever makes things take longer, so failing a
        lower limit indicates a real bug. This exists so that tests using
        `upper` can use it for their lower bound too, making it explicit that
        the lower bound is deliberately not loosened.

        Parameters
        ----------
        threshold : float
            Minimum allowed duration (s).

        Returns
        -------
        float
        """
        return threshold

    def __str__(self):
        return (
            f"cpuRatio={self.cpuRatio:.3f}, cpuScale={self.cpuScale:.3f}, "
            f"sleepSlack={self.sleepSlack * 1000:.2f}ms (source: {self.source})"
        )


def _measureCpuRatio():
    """Time a busy loop and return how long it took relative to a mid-range
    PC (`REF_CPU_SECONDS`), taking the fastest of several runs.
    """
    durations = []
    for _ in range(CPU_LOOP_REPEATS):
        start = time.perf_counter()
        for n in range(CPU_LOOP_ITERATIONS):
            y = n + 1
        durations.append(time.perf_counter() - start)

    return min(durations) / REF_CPU_SECONDS


def _measureSleepSlack():
    """Measure how much short sleeps overshoot, returning a high percentile
    of the overshoots, clamped to between `MIN_SLEEP_SLACK` and
    `MAX_SLEEP_SLACK`.
    """
    overshoots = []
    for _ in range(SLEEP_PROBE_REPEATS):
        start = time.perf_counter()
        time.sleep(SLEEP_PROBE_SECONDS)
        overshoots.append(time.perf_counter() - start - SLEEP_PROBE_SECONDS)
    overshoots.sort()
    i = min(
        len(overshoots) - 1,
        int(len(overshoots) * SLEEP_PERCENTILE / 100))

    return min(max(overshoots[i], MIN_SLEEP_SLACK), MAX_SLEEP_SLACK)


def _getEnvFloat(name):
    """Get the value of an environment variable as a float, or None if it
    isn't set.
    """
    value = os.environ.get(name, "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        raise ValueError(
            f"Environment variable {name} must be a number, got {value!r}")


def _calibrate():
    """Make a TimingTolerance from environment overrides where given, and
    measurements otherwise.
    """
    envScale = _getEnvFloat(ENV_TIME_SCALE)
    envSlack = _getEnvFloat(ENV_SLEEP_SLACK)

    if envScale is None:
        cpuRatio = _measureCpuRatio()
        cpuScale = min(max(cpuRatio, 1.0), MAX_CPU_SCALE)
    else:
        # an explicit value is used as-is, so it can force strict thresholds
        cpuRatio = cpuScale = envScale

    if envSlack is None:
        sleepSlack = _measureSleepSlack()
    else:
        sleepSlack = envSlack

    if envScale is None and envSlack is None:
        source = "measured"
    elif envScale is not None and envSlack is not None:
        source = "env"
    else:
        source = "measured+env"

    return TimingTolerance(
        cpuRatio=cpuRatio,
        cpuScale=cpuScale,
        sleepSlack=sleepSlack,
        source=source)


_tolerance = None


def getTimingTolerance():
    """Get the timing tolerance for this machine, calibrating it the first
    time this is called.

    Returns
    -------
    TimingTolerance
    """
    global _tolerance
    if _tolerance is None:
        _tolerance = _calibrate()

    return _tolerance


def isTimingCalibrated():
    """Whether `getTimingTolerance` has been called yet this session.

    Returns
    -------
    bool
    """
    return _tolerance is not None
