#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Simulated pen tablet, driven by the mouse, for developing and testing
experiments without a tablet.
"""

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2025 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

__all__ = [
    'SimulatedPenDevice',
]

import numpy as np

from psychopy import clock as psyclock
from psychopy.hardware.pen.base import BasePenDevice


class SimulatedPenDevice(BasePenDevice, aliases=["simulatedPen"]):
    """Pen tablet which uses the mouse in place of a pen: holding the left
    button down counts as touching the tablet (with a pressure of 1).

    Responses can also be made directly with `makeResponse`, or by passing
    samples to `addSample`.

    Parameters
    ----------
    win : psychopy.visual.Window, optional
        Window which the pen is used on, leave as None to use the first window
        which is opened.
    deviceIndex : int, optional
        Not used, only here so this class can be made from the same profile as
        a real tablet.
    pressureThreshold : float, optional
        Pressure (from 0 to 1) above which the pen counts as touching the
        tablet.
    units : str, optional
        Units for the positions of responses, leave as None to use the units
        of the window.
    useMouse : bool, optional
        If True (default), make samples from the mouse.
    """

    def __init__(
            self, win=None, deviceIndex=0, pressureThreshold=0, units=None, useMouse=True
    ):
        BasePenDevice.__init__(
            self, win=win, deviceIndex=deviceIndex, pressureThreshold=pressureThreshold,
            units=units
        )
        self.useMouse = useMouse
        # samples added by addSample, waiting to be dispatched
        self._queue = []
        # last mouse state, to only make samples when it changes
        self._lastMouse = None

    @staticmethod
    def getAvailableDevices():
        return [{
            'deviceName': "Simulated pen (mouse)",
            'deviceIndex': 0,
        }]

    def isSameDevice(self, other):
        # there's only ever one simulated pen
        if isinstance(other, dict):
            return other.get('deviceName') == "Simulated pen (mouse)"

        return isinstance(other, SimulatedPenDevice)

    def addSample(self, **kwargs):
        """Add a sample, as if it had come from a tablet. Takes the same keys as
        samples from `BasePenDevice._poll`.
        """
        kwargs.setdefault("type", "sample")
        kwargs.setdefault("t", psyclock.getTime())
        self._queue.append(kwargs)

    def _poll(self):
        samples = self._queue
        self._queue = []
        if self.useMouse and self.win is not None:
            samples += self._pollMouse()

        return samples

    def _pollMouse(self):
        from psychopy import event

        self._pumpEvents()
        win = self.win
        try:
            # framebuffer pixels from the center of the window
            buffPos = np.asarray(win.backend.getMousePos(), dtype=float)
        except Exception:
            return []
        pix = buffPos / win.pixScaleFactor
        pressed = bool(event.mouseButtons[0])
        current = (tuple(pix), pressed)
        if current == self._lastMouse:
            return []
        samples = []
        if self._lastMouse is None:
            samples.append({'type': "enter", 't': psyclock.getTime(), 'pix': pix})
        self._lastMouse = current
        samples.append({
            'type': "sample",
            't': psyclock.getTime(),
            'pix': pix,
            'pressure': 1.0 if pressed else 0.0,
            'buttons': 1 if pressed else 0,
            'cursor': "pen",
        })

        return samples
