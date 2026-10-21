#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Pen tablets (e.g. Wacom tablets), giving the position, pressure and tilt of
a pen.

`PenDevice` is the tablet backend for the current platform: Wintab on Windows
and native events on macOS. `SimulatedPenDevice` uses the mouse in place of a
pen, for developing experiments without a tablet.

Examples
--------
Draw with a pen tablet::

    from psychopy import visual
    from psychopy.hardware.pen import PenDevice

    win = visual.Window(units="pix")
    pen = PenDevice()
    while True:
        for resp in pen.getResponses():
            if resp.value in ("down", "move"):
                print(resp.x, resp.y, resp.pressure)
        win.flip()
"""

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2025 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

__all__ = [
    'PenResponse',
    'BasePenDevice',
    'PenDevice',
    'SimulatedPenDevice',
    'Pen',
    'orientationToTilt',
    'tiltToOrientation',
]

import sys

import numpy as np

from psychopy import constants
from psychopy.hardware import DeviceManager
from psychopy.hardware.exceptions import DeviceNotConnectedError
from psychopy.hardware.pen.base import (
    PenResponse, BasePenDevice, orientationToTilt, tiltToOrientation
)
from psychopy.hardware.pen._sim import SimulatedPenDevice
from psychopy.localization import _translate


class UnsupportedPenDevice(BasePenDevice):
    """Stands in for `PenDevice` on platforms without a pen tablet backend.
    """
    # why there's no backend
    reason = "Pen tablets are not supported on this platform."

    def __init__(self, win=None, deviceIndex=0, pressureThreshold=0, units=None):
        raise DeviceNotConnectedError(self.reason, deviceClass=UnsupportedPenDevice)

    @staticmethod
    def getAvailableDevices():
        return []

    def isSameDevice(self, other):
        return False


if sys.platform == "win32":
    from psychopy.hardware.pen._wintab import WintabPenDevice as PenDevice
elif sys.platform == "darwin":
    try:
        from psychopy.hardware.pen._cocoa import CocoaPenDevice as PenDevice
    except ImportError as _err:
        UnsupportedPenDevice.reason = (
            f"Could not load macOS pen tablet support, is pyobjc installed? ({_err})"
        )
        PenDevice = UnsupportedPenDevice
else:
    PenDevice = UnsupportedPenDevice


class Pen:
    """Builder-friendly wrapper around a pen tablet device, which stores the
    samples from each Routine.

    Parameters
    ----------
    device : BasePenDevice, str or None
        Pen device, or the name of one in DeviceManager. Leave as None to use
        the first pen device in DeviceManager, or to make one for this platform.
    win : psychopy.visual.Window, optional
        Window which the pen is used on.
    units : str, optional
        Units for positions, leave as None to use the units of the window.
    pressureThreshold : float, optional
        Pressure (from 0 to 1) above which the pen counts as touching the
        tablet, leave as None to keep the device's setting.
    """
    # attributes storing each sample's values (Builder)
    dataFields = (
        "x", "y", "pressure", "time", "state", "tiltX", "tiltY", "azimuth", "altitude",
        "twist", "buttons", "cursor"
    )

    def __init__(self, device=None, win=None, units=None, pressureThreshold=None):
        self.device = self._resolveDevice(device)
        # the device's window is the first one opened unless it's been given one
        if win is not None and self.device._win is None:
            self.device.win = win
        # start reading from the tablet now, rather than on the first poll
        self.device._open()
        self.win = win if win is not None else self.device.win
        self._units = units
        if pressureThreshold is not None:
            self.device.pressureThreshold = pressureThreshold
        # starting value for status (Builder)
        self.status = constants.NOT_STARTED
        # arrays to store info (Builder)
        self.clearData()

    @staticmethod
    def _resolveDevice(device):
        if isinstance(device, BasePenDevice):
            return device
        if device in (None, ""):
            # use the first pen device we find in DeviceManager, or make one
            for dev in DeviceManager.getInitialisedDevices(BasePenDevice).values():
                return dev
            return PenDevice()
        if isinstance(device, str):
            dev = DeviceManager.getDevice(device)
            if isinstance(dev, BasePenDevice):
                return dev
            # don't use formatted string literals in _translate()
            raise ValueError(_translate(
                "Could not find a pen device named '{}', make sure it has been set up in "
                "DeviceManager."
            ).format(device))
        raise TypeError(f"Could not get a pen device from {device!r}")

    @property
    def units(self):
        """Units which positions are given in.
        """
        if self._units is not None:
            return self._units
        if self.win is not None:
            return self.win.units
        return self.device.getUnits()

    @units.setter
    def units(self, value):
        self._units = value

    def clearData(self):
        """Clear the samples stored on this object (by `record`).
        """
        for field in self.dataFields:
            setattr(self, field, [])

    def record(self, resp):
        """Store a response's values in this object's data lists (`x`, `y`,
        `pressure`, `time`, etc.).

        Parameters
        ----------
        resp : PenResponse or None
            Response to store, does nothing if None.
        """
        if resp is None:
            return
        x, y = self.getResponsePos(resp)
        self.x.append(float(x))
        self.y.append(float(y))
        self.time.append(resp.t)
        self.state.append(resp.value)
        for field in (
                "pressure", "tiltX", "tiltY", "azimuth", "altitude", "twist", "buttons",
                "cursor"
        ):
            getattr(self, field).append(getattr(resp, field))

    def getResponsePos(self, resp):
        """Get the position of a response in this object's units.

        Parameters
        ----------
        resp : PenResponse
            Response to get the position of.

        Returns
        -------
        numpy.ndarray
            Position `(x, y)`.
        """
        if resp.pix is None:
            return np.array((resp.x, resp.y))

        return self.device.pixToUnits(resp.pix, self.units)

    def getResponses(self, value=None, clear=True):
        return self.device.getResponses(value=value, clear=clear)

    def getState(self):
        return self.device.getState()

    def getPos(self):
        return self.device.getPos(units=self.units)

    def getPressure(self):
        return self.device.getPressure()

    def isDown(self):
        return self.device.isDown()

    def inProximity(self):
        return self.device.inProximity()

    def resetTimer(self, clock=None):
        return self.device.resetTimer(clock=clock)

    def clearResponses(self):
        return self.device.clearResponses()
