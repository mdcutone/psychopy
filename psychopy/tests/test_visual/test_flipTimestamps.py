"""Tests for using presentation times reported by the operating system as flip
times (`Window(flipTimestamps='auto')`), without a window: the backend and its
platform's timing are stood in for.
"""
import ctypes
import types
from collections import deque

import pytest

from psychopy import logging
from psychopy.visual.window import Window
from psychopy.visual.backends import _linux, _win32


# --------------------------------------------------------------------------
# Window: checking a reported presentation time is for the frame just flipped
#

class _FakeBackend:
    flipTimestampSource = 'fake'

    def __init__(self, tRaw):
        self.tRaw = tRaw

    def getLastFlipTimestamp(self):
        return self.tRaw


def _fakeWin(tReportedRaw, previous=None, waitBlanking=True):
    """Just enough of a Window for `_getPresentationTime`."""
    win = types.SimpleNamespace(
        backend=_FakeBackend(tReportedRaw),
        waitBlanking=waitBlanking,
        _frameTimes=deque([] if previous is None else [previous]),
        _warnedFlipTimestamp=False)
    return win


def _raw(t):
    """Raw time of time `t` on the logging clock."""
    return t + logging.defaultClock.getLastResetTime()


@pytest.fixture
def warnings(monkeypatch):
    logged = []
    monkeypatch.setattr(logging, "warning", lambda msg, *a, **k: logged.append(msg))
    return logged


def test_presentation_time_used(warnings):
    win = _fakeWin(_raw(10.005), previous=9.99)
    t = Window._getPresentationTime(win, tSubmit=10.0, tReturned=10.008)
    assert float(t) == pytest.approx(10.005)
    assert not warnings


@pytest.mark.parametrize("tReported, previous", [
    (9.99, None),     # before the frame was submitted
    (10.02, None),    # after the flip returned
    (10.005, 10.006),  # not after the previous flip
])
def test_presentation_time_not_for_this_frame_rejected(tReported, previous, warnings):
    win = _fakeWin(_raw(tReported), previous=previous)
    assert Window._getPresentationTime(win, tSubmit=10.0, tReturned=10.008) is None
    # warned the first time, not again
    Window._getPresentationTime(win, tSubmit=10.0, tReturned=10.008)
    assert len(warnings) == 1


def test_no_presentation_time_without_vsync_or_source():
    assert Window._getPresentationTime(
        _fakeWin(_raw(10.005), waitBlanking=False), 10.0, 10.008) is None
    assert Window._getPresentationTime(_fakeWin(None), 10.0, 10.008) is None


# --------------------------------------------------------------------------
# Windows: DWM timing information
#

def test_dwm_timing_info_is_packed():
    """`DWM_TIMING_INFO` is byte packed, so its size (which must be given in
    `cbSize`) is that of its fields with no padding."""
    fieldSizes = sum(
        ctypes.sizeof(fieldType) for _, fieldType in _win32.DwmTimingInfo._fields_)
    assert ctypes.sizeof(_win32.DwmTimingInfo) == fieldSizes


@pytest.mark.parametrize("cDXRefresh, cDXRefreshConfirmed, refreshesBefore", [
    (1000, 1000, 0),  # confirmed at the last refresh
    (1002, 1000, 2),  # two refreshes before it
    (1, 0xFFFFFFFF, 2),  # across the 32-bit count wrapping around
])
def test_dwm_presentation_ticks(cDXRefresh, cDXRefreshConfirmed, refreshesBefore):
    info = _win32.DwmTimingInfo(
        qpcVBlank=10_000_000, qpcRefreshPeriod=166_667,
        cDXRefresh=cDXRefresh, cDXRefreshConfirmed=cDXRefreshConfirmed)
    assert _win32.presentationTicks(info) == 10_000_000 - refreshesBefore * 166_667


def test_dwm_swap_timer_only_on_windows(monkeypatch):
    monkeypatch.setattr(_win32.sys, "platform", "darwin")
    assert _win32.DwmSwapTimer.create() is None


# --------------------------------------------------------------------------
# Linux: GLX_OML_sync_control
#

def _omlTimer(results):
    """An OML swap timer whose `glXWaitForSbcOML` gives `results`, a list of
    (ok, ust, sbc), one per swap."""
    results = iter(results)

    def waitForSbc(display, drawable, targetSbc, ust, msc, sbc):
        ok, ust._obj.value, sbc._obj.value = next(results)
        return ok

    return _linux.OMLSwapTimer(1, 2, waitForSbc)


@pytest.mark.skipif(not hasattr(_linux.time, "CLOCK_MONOTONIC"),
                    reason="no CLOCK_MONOTONIC")
def test_oml_swap_times_on_raw_clock():
    """The UST is on CLOCK_MONOTONIC, in microseconds, and is put on the raw
    clock."""
    from psychopy.clock import getTime
    ust = int(_linux._getMonotonicTime() * 1e6)
    timer = _omlTimer([(1, ust, 5)])
    timer.afterSwap()
    assert timer.lastTimestamp == pytest.approx(getTime(), abs=0.01)


@pytest.mark.skipif(not hasattr(_linux.time, "CLOCK_MONOTONIC"),
                    reason="no CLOCK_MONOTONIC")
def test_oml_swap_count_must_follow_on():
    """A swap count other than one more than the last means the time is for
    another swap, which isn't used, but it doesn't stop the next being."""
    timer = _omlTimer([(1, 1_000_000, 5), (1, 1_016_000, 7), (1, 1_032_000, 8)])
    timer.afterSwap()
    assert timer.lastTimestamp is not None
    timer.afterSwap()
    assert timer.lastTimestamp is None
    timer.afterSwap()
    assert timer.lastTimestamp is not None


@pytest.mark.parametrize("ok, ust", [(0, 1_000_000), (1, 0)])
def test_oml_driver_without_times_not_used_again(ok, ust):
    timer = _omlTimer([(ok, ust, 5)])
    timer.afterSwap()
    assert timer.lastTimestamp is None
    timer.afterSwap()  # isn't asked again, which would run out of results
    assert timer.lastTimestamp is None


def test_oml_swap_timer_needs_glx(monkeypatch):
    monkeypatch.setattr(_linux.sys, "platform", "linux")
    assert _linux.OMLSwapTimer.create(None, 3) is None  # e.g. Wayland
    assert _linux.OMLSwapTimer.create(1234, 0) is None  # e.g. EGL context
    monkeypatch.setattr(_linux.sys, "platform", "darwin")
    assert _linux.OMLSwapTimer.create(1234, 3) is None
