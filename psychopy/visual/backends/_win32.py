#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2025 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

"""Windows specific functionality shared by window backends (e.g., Pyglet and
GLFW). This includes timing when buffer swaps are presented on screen, using
the timing information of the Desktop Window Manager (DWM).

This module can be imported on any platform, so that its calculations can be
tested, but :meth:`DwmSwapTimer.create` only gives a timer on Windows.
"""

__all__ = [
    'DwmSwapTimer'
]

import ctypes
import sys
import time

from psychopy import logging
from psychopy.clock import measureClockOffset

_SM_CMONITORS = 80  # `GetSystemMetrics` index of the number of displays


class _UnsignedRatio(ctypes.Structure):
    _layout_ = 'ms'
    _pack_ = 1
    _fields_ = [
        ('uiNumerator', ctypes.c_uint32),
        ('uiDenominator', ctypes.c_uint32),
    ]


class DwmTimingInfo(ctypes.Structure):
    """`DWM_TIMING_INFO` from `dwmapi.h`, which is byte packed. Counts
    prefixed `cDX` are 32-bit and wrap around, the others are 64-bit."""
    _layout_ = 'ms'
    _pack_ = 1
    _fields_ = [
        ('cbSize', ctypes.c_uint32),
        ('rateRefresh', _UnsignedRatio),
        ('qpcRefreshPeriod', ctypes.c_uint64),
        ('rateCompose', _UnsignedRatio),
        ('qpcVBlank', ctypes.c_uint64),
        ('cRefresh', ctypes.c_uint64),
        ('cDXRefresh', ctypes.c_uint32),
        ('qpcCompose', ctypes.c_uint64),
        ('cFrame', ctypes.c_uint64),
        ('cDXPresent', ctypes.c_uint32),
        ('cRefreshFrame', ctypes.c_uint64),
        ('cFrameSubmitted', ctypes.c_uint64),
        ('cDXPresentSubmitted', ctypes.c_uint32),
        ('cFrameConfirmed', ctypes.c_uint64),
        ('cDXPresentConfirmed', ctypes.c_uint32),
        ('cRefreshConfirmed', ctypes.c_uint64),
        ('cDXRefreshConfirmed', ctypes.c_uint32),
        ('cFramesLate', ctypes.c_uint64),
        ('cFramesOutstanding', ctypes.c_uint32),
        ('cFrameDisplayed', ctypes.c_uint64),
        ('qpcFrameDisplayed', ctypes.c_uint64),
        ('cRefreshFrameDisplayed', ctypes.c_uint64),
        ('cFrameComplete', ctypes.c_uint64),
        ('qpcFrameComplete', ctypes.c_uint64),
        ('cFramePending', ctypes.c_uint64),
        ('qpcFramePending', ctypes.c_uint64),
        ('cFramesDisplayed', ctypes.c_uint64),
        ('cFramesComplete', ctypes.c_uint64),
        ('cFramesPending', ctypes.c_uint64),
        ('cFramesAvailable', ctypes.c_uint64),
        ('cFramesDropped', ctypes.c_uint64),
        ('cFramesMissed', ctypes.c_uint64),
        ('cRefreshNextDisplayed', ctypes.c_uint64),
        ('cRefreshNextPresented', ctypes.c_uint64),
        ('cRefreshesDisplayed', ctypes.c_uint64),
        ('cRefreshesPresented', ctypes.c_uint64),
        ('cRefreshStarted', ctypes.c_uint64),
        ('cPixelsReceived', ctypes.c_uint64),
        ('cPixelsDrawn', ctypes.c_uint64),
        ('cBuffersEmpty', ctypes.c_uint64),
    ]


def presentationTicks(info):
    """When the last confirmed present was presented, from DWM timing
    information, in QPC ticks.

    That's the refresh the DWM confirmed the present at, which is
    `cDXRefresh - cDXRefreshConfirmed` refreshes before the one at
    `qpcVBlank`.

    Parameters
    ----------
    info : DwmTimingInfo
        Timing information from `DwmGetCompositionTimingInfo`.

    Returns
    -------
    int
        QPC ticks.

    """
    refreshesSince = (info.cDXRefresh - info.cDXRefreshConfirmed) & 0xFFFFFFFF

    return info.qpcVBlank - refreshesSince * info.qpcRefreshPeriod


class DwmSwapTimer:
    """Times when buffer swaps are presented on screen, from the timing
    information of the Desktop Window Manager (DWM), which composites every
    window.

    After each swap, :meth:`afterSwap` waits for the DWM to confirm the
    present the swap led to, and works out the refresh that happened at.
    This relies on the most recent present being the one for our window, so
    it's only used with a single display, and works best with nothing else
    on screen changing.

    Use :meth:`create` to get an instance, which returns `None` where the
    DWM's timing information can't be used.

    """
    source = 'dwm'
    # longest to wait for a present to be confirmed, in refreshes
    _maxWaitRefreshes = 2

    def __init__(self, dwmapi, qpcFrequency, qpcSeconds):
        self._dwmapi = dwmapi
        self._qpcFrequency = qpcFrequency
        self._qpcSeconds = qpcSeconds
        # offset from QPC seconds to `psychopy.clock.getTime()`, which
        # shares the QPC counter so doesn't change
        self._clockOffset = measureClockOffset(qpcSeconds)
        self.lastTimestamp = None

    @classmethod
    def create(cls):
        """Create a DWM swap timer, if the DWM's timing information can be
        used.

        Returns
        -------
        DwmSwapTimer or None
            Timer, or `None` if not on Windows, the DWM isn't compositing, or
            there's more than one display (the DWM's timing information isn't
            for any one display).

        """
        if sys.platform != 'win32':
            return None

        try:
            user32 = ctypes.windll.user32
            if user32.GetSystemMetrics(_SM_CMONITORS) != 1:
                logging.info(
                    "Presentation times from the DWM need a single display, "
                    "so flip times will be read in software.")
                return None

            dwmapi = ctypes.windll.dwmapi
            enabled = ctypes.c_int(0)
            if dwmapi.DwmIsCompositionEnabled(ctypes.byref(enabled)) != 0 or \
                    not enabled.value:
                return None

            kernel32 = ctypes.windll.kernel32
            frequency = ctypes.c_int64()
            kernel32.QueryPerformanceFrequency(ctypes.byref(frequency))
            frequency = float(frequency.value)
            counter = ctypes.c_int64()

            def qpcSeconds():
                kernel32.QueryPerformanceCounter(ctypes.byref(counter))
                return counter.value / frequency

            return cls(dwmapi, frequency, qpcSeconds)
        except Exception as err:
            logging.debug(
                "Unable to get presentation times from the DWM: {}".format(err))

        return None

    def _getTimingInfo(self):
        info = DwmTimingInfo()
        info.cbSize = ctypes.sizeof(DwmTimingInfo)
        if self._dwmapi.DwmGetCompositionTimingInfo(
                None, ctypes.byref(info)) != 0:
            return None

        return info

    def afterSwap(self):
        """Wait for the DWM to confirm presenting the swap just made, and
        record when that was in `lastTimestamp` (`None` if it couldn't be
        told).
        """
        self.lastTimestamp = None
        # the DWM presents our swap as part of its next composition
        self._dwmapi.DwmFlush()

        info = self._getTimingInfo()
        if info is None:
            return
        target = info.cDXPresentSubmitted
        maxWait = self._maxWaitRefreshes * info.qpcRefreshPeriod / \
            self._qpcFrequency
        deadline = self._qpcSeconds() + maxWait
        while info.cDXPresentConfirmed != target:
            if self._qpcSeconds() > deadline:
                return
            time.sleep(0.0005)
            info = self._getTimingInfo()
            if info is None:
                return

        self.lastTimestamp = \
            presentationTicks(info) / self._qpcFrequency + self._clockOffset
