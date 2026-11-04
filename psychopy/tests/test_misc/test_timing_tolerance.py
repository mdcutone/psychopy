"""Tests for the machine-speed calibration used to scale timing thresholds in
tests (`psychopy/tests/timing.py`).
"""

import pytest

from psychopy.tests import timing as timingModule
from psychopy.tests.timing import TimingTolerance


@pytest.fixture
def fresh(monkeypatch):
    """Clear the cached calibration and any env overrides, so each test
    calibrates from scratch (the cache is restored afterwards by
    monkeypatch, so other tests are unaffected).
    """
    monkeypatch.setattr(timingModule, "_tolerance", None)
    monkeypatch.delenv(timingModule.ENV_TIME_SCALE, raising=False)
    monkeypatch.delenv(timingModule.ENV_SLEEP_SLACK, raising=False)

    return monkeypatch


class TestTimingTolerance:

    def test_scaled(self):
        tol = TimingTolerance(cpuRatio=0.5, cpuScale=1.0, sleepSlack=0.01)
        # clamped, so never tightened on a fast machine...
        assert tol.scaled(2) == 2
        # ...unless asked
        assert tol.scaled(2, clamp=False) == 1

        tol = TimingTolerance(cpuRatio=3, cpuScale=3, sleepSlack=0.01)
        assert tol.scaled(2) == 6
        assert tol.scaled(2, clamp=False) == 6

    def test_upper(self):
        tol = TimingTolerance(cpuRatio=1, cpuScale=1, sleepSlack=0.01)
        assert tol.upper(0.1) == pytest.approx(0.11)
        assert tol.upper(0.1, nSleeps=3) == pytest.approx(0.13)
        assert tol.upper(0.1, nSleeps=0) == pytest.approx(0.1)

        tol = TimingTolerance(cpuRatio=2, cpuScale=2, sleepSlack=0.01)
        assert tol.upper(0.1, nSleeps=2) == pytest.approx(0.22)

    def test_lower_unchanged(self):
        tol = TimingTolerance(cpuRatio=5, cpuScale=5, sleepSlack=0.05)
        assert tol.lower(0.04) == 0.04

    def test_str(self):
        tol = TimingTolerance(cpuRatio=0.5, cpuScale=1, sleepSlack=0.0123)
        assert "sleepSlack=12.30ms" in str(tol)
        assert "source: measured" in str(tol)


class TestCalibration:

    def test_measured_within_limits(self, fresh):
        tol = timingModule.getTimingTolerance()
        assert tol.source == "measured"
        assert tol.cpuRatio > 0
        assert 1 <= tol.cpuScale <= timingModule.MAX_CPU_SCALE
        assert (
            timingModule.MIN_SLEEP_SLACK
            <= tol.sleepSlack
            <= timingModule.MAX_SLEEP_SLACK)

    def test_cached(self, fresh):
        assert not timingModule.isTimingCalibrated()
        first = timingModule.getTimingTolerance()
        assert timingModule.isTimingCalibrated()
        assert timingModule.getTimingTolerance() is first

    def test_env_overrides(self, fresh):
        fresh.setenv(timingModule.ENV_TIME_SCALE, "0.5")
        fresh.setenv(timingModule.ENV_SLEEP_SLACK, "0")
        tol = timingModule.getTimingTolerance()
        assert tol.source == "env"
        # explicit values are used as-is, so they can force strict thresholds
        assert tol.cpuRatio == tol.cpuScale == 0.5
        assert tol.sleepSlack == 0
        assert tol.upper(0.15) == pytest.approx(0.075)

    def test_partial_env_override(self, fresh):
        fresh.setenv(timingModule.ENV_SLEEP_SLACK, "0.02")
        tol = timingModule.getTimingTolerance()
        assert tol.source == "measured+env"
        assert tol.sleepSlack == 0.02
        assert tol.cpuScale >= 1

    def test_bad_env_value(self, fresh):
        fresh.setenv(timingModule.ENV_TIME_SCALE, "fast")
        with pytest.raises(ValueError, match=timingModule.ENV_TIME_SCALE):
            timingModule.getTimingTolerance()

    def test_sleep_slack_clamped(self, fresh):
        # a machine where sleeps overshoot hugely is capped...
        fresh.setattr(timingModule.time, "sleep", lambda s: None)
        clock = iter(range(0, 1000))
        fresh.setattr(timingModule.time, "perf_counter", lambda: next(clock))
        assert timingModule._measureSleepSlack() == timingModule.MAX_SLEEP_SLACK


@pytest.mark.timing
def test_fixture(timing):
    """The conftest fixture should give the shared, cached calibration."""
    assert isinstance(timing, TimingTolerance)
    assert timing is timingModule.getTimingTolerance()
