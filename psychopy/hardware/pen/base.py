#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Base classes for pen tablet devices (e.g. Wacom tablets).
"""

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2025 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

__all__ = [
    'PenResponse',
    'BasePenDevice',
    'tiltToOrientation',
    'orientationToTilt',
]

import math
import threading

import numpy as np

from psychopy import clock as psyclock
from psychopy import core, logging
from psychopy.hardware import base


# possible values of PenResponse.value
PEN_STATES = ("enter", "leave", "hover", "down", "move", "up")


def orientationToTilt(azimuth, altitude):
    """Convert pen orientation as azimuth and altitude to tilt along x and y.

    Parameters
    ----------
    azimuth : float
        Direction the pen is pointing, in degrees clockwise from the top of the
        tablet.
    altitude : float
        Angle between the pen and the tablet surface, in degrees (90 means
        upright).

    Returns
    -------
    tuple[float, float]
        Tilt `(x, y)` in degrees, positive when the top of the pen leans right
        (x) or towards the top of the tablet (y).
    """
    if altitude >= 90:
        return 0.0, 0.0
    az = math.radians(azimuth)
    alt = math.radians(altitude)
    # direction of the pen, from the tip to the top
    vx = math.cos(alt) * math.sin(az)
    vy = math.cos(alt) * math.cos(az)
    vz = math.sin(alt)

    return math.degrees(math.atan2(vx, vz)), math.degrees(math.atan2(vy, vz))


def tiltToOrientation(tiltX, tiltY):
    """Convert tilt along x and y to pen orientation as azimuth and altitude.
    This is the inverse of `orientationToTilt`.

    Parameters
    ----------
    tiltX : float
        Tilt in degrees, positive when the top of the pen leans right.
    tiltY : float
        Tilt in degrees, positive when the top of the pen leans towards the top
        of the tablet.

    Returns
    -------
    tuple[float, float]
        Azimuth and altitude, in degrees.
    """
    tx = math.tan(math.radians(tiltX))
    ty = math.tan(math.radians(tiltY))
    if tx == 0 and ty == 0:
        return 0.0, 90.0
    azimuth = math.degrees(math.atan2(tx, ty)) % 360
    altitude = math.degrees(math.atan2(1, math.hypot(tx, ty)))

    return azimuth, altitude


class PenResponse(base.BaseResponse):
    """A single sample from a pen tablet.

    Attributes
    ----------
    t : float
        Time of the sample, relative to the device's clock.
    value : str
        What the pen was doing, one of:
        - "enter": the pen came into range of the tablet
        - "leave": the pen went out of range of the tablet
        - "hover": the pen is in range but not touching the tablet
        - "down": the pen has just touched the tablet
        - "move": the pen is still touching the tablet
        - "up": the pen has just lifted off the tablet
    x, y : float
        Position of the pen, in the device's units (or the window's units if
        the device has none).
    z : int
        Height above the tablet, for devices which report it.
    pressure : float
        Tip pressure, from 0 to 1.
    tangentialPressure : float
        Barrel pressure, e.g. from the wheel on an airbrush pen.
    tiltX, tiltY : float
        Tilt of the pen in degrees, positive when the top of the pen leans
        right (x) or towards the top of the tablet (y).
    azimuth : float
        Direction the pen is pointing in degrees, clockwise from the top of
        the tablet.
    altitude : float
        Angle between the pen and the tablet in degrees, 90 means upright.
    twist : float
        Rotation of the pen around its own axis in degrees, for pens which
        report it.
    buttons : int
        Bitmask of the buttons being pressed (1 = tip, 2 = lower side button,
        4 = upper side button).
    cursor : str
        What's touching the tablet: "pen", "eraser" or "puck".
    """
    fields = [
        "t", "value", "x", "y", "z", "pressure", "tangentialPressure", "tiltX",
        "tiltY", "azimuth", "altitude", "twist", "buttons", "cursor"
    ]

    def __init__(
            self, t, value, x=0, y=0, z=0, pressure=0, tangentialPressure=0,
            tiltX=0, tiltY=0, azimuth=0, altitude=90, twist=0, buttons=0,
            cursor="pen", device=None
    ):
        base.BaseResponse.__init__(self, t=t, value=value, device=device)
        self.x = x
        self.y = y
        self.z = z
        self.pressure = pressure
        self.tangentialPressure = tangentialPressure
        self.tiltX = tiltX
        self.tiltY = tiltY
        self.azimuth = azimuth
        self.altitude = altitude
        self.twist = twist
        self.buttons = buttons
        self.cursor = cursor
        # position in PsychoPy 'pix' units, so it can be converted to other units
        self.pix = None
        # units which x and y are in
        self.units = None

    def __eq__(self, other):
        """
        PenResponse will recognise itself as equal to either:
        - A string which matches its value (e.g. "down")
        - Another PenResponse with the same value, time and position
        """
        if isinstance(other, str):
            return other == self.value
        if isinstance(other, PenResponse):
            return (
                other.value == self.value
                and other.t == self.t
                and other.x == self.x
                and other.y == self.y
            )

        return False

    @property
    def pos(self):
        return np.array((self.x, self.y))


class BasePenDevice(base.BaseResponseDevice):
    """Base class for pen tablet devices.

    Subclasses read samples from the tablet in `_poll`, as dicts with the
    following keys (any not given take the defaults of `PenResponse`):
    - "type": "sample", "enter" or "leave"
    - "t": time of the sample, in the same timebase as `psychopy.clock.getTime`
    - "pix": position `(x, y)` in PsychoPy 'pix' units, origin at the center
    of the window
    - "pressure", "tangentialPressure", "tiltX", "tiltY", "azimuth",
    "altitude", "twist", "z", "buttons", "cursor": as in `PenResponse`

    This class turns these into `PenResponse` objects, working out whether the
    pen is touching the tablet from the pressure.

    Parameters
    ----------
    win : psychopy.visual.Window, optional
        Window which the pen is used on, leave as None to use the first window
        which is opened.
    deviceIndex : int, optional
        Index of the tablet to use, if more than one is connected.
    pressureThreshold : float, optional
        Pressure (from 0 to 1) above which the pen counts as touching the
        tablet.
    units : str, optional
        Units for the positions of responses, leave as None to use the units
        of the window.
    """
    responseClass = PenResponse

    def __init__(self, win=None, deviceIndex=0, pressureThreshold=0, units=None):
        base.BaseResponseDevice.__init__(self)
        self._win = win
        self.deviceIndex = deviceIndex
        self.pressureThreshold = pressureThreshold
        self.units = units
        # clock which response times are relative to
        self.clock = core.Clock()
        # most recent response
        self.state = None
        # is the pen currently touching the tablet / in range of it?
        self._isDown = False
        self._inProximity = False
        # last cursor seen, as some platforms only report it on entering
        self._cursor = "pen"

    @property
    def win(self):
        """Window which the pen is used on (the first window opened, if none was
        given).
        """
        if self._win is None:
            from psychopy.visual.window import openWindows
            for ref in openWindows:
                if ref() is not None:
                    self._win = ref()
                    break

        return self._win

    @win.setter
    def win(self, value):
        self._win = value

    def resetTimer(self, clock=None):
        """Set the clock which response times are relative to.

        Parameters
        ----------
        clock : psychopy.core.Clock, optional
            Clock to measure times relative to, leave as None to measure times
            from now.
        """
        if clock is None:
            self.clock.reset()
        else:
            self.clock._timeAtLastReset = clock.getLastResetTime()

    def _open(self):
        """Start reading from the tablet, if possible (e.g. once there's a window).
        Subclasses which need setting up should override this.

        Returns
        -------
        bool
            True if ready to read samples.
        """
        return True

    def _poll(self):
        """Get any new samples from the tablet. Must be implemented by
        subclasses.

        Returns
        -------
        list[dict]
            Samples, in chronological order (see `BasePenDevice` for keys).
        """
        raise NotImplementedError()

    def dispatchMessages(self):
        for message in self._poll():
            resp = self.parseMessage(message)
            if resp is not None:
                self.receiveMessage(resp)

    def parseMessage(self, message):
        """Turn a sample from `_poll` into a `PenResponse`.

        Parameters
        ----------
        message : dict
            Sample to parse (see `BasePenDevice` for keys).

        Returns
        -------
        PenResponse
            Parsed response.
        """
        message = dict(message)
        kind = message.pop("type", "sample")
        t = message.pop("t", None)
        if t is None:
            t = psyclock.getTime()
        pix = message.pop("pix", None)
        if "cursor" in message:
            self._cursor = message["cursor"]
        else:
            message['cursor'] = self._cursor
        # work out what the pen is doing
        if kind == "enter":
            value = "enter"
            self._inProximity = True
        elif kind == "leave":
            value = "leave"
            self._inProximity = False
            # can't be touching the tablet if out of range
            self._isDown = False
        else:
            self._inProximity = True
            isDown = message.get("pressure", 0) > self.pressureThreshold
            if isDown and not self._isDown:
                value = "down"
            elif isDown:
                value = "move"
            elif self._isDown:
                value = "up"
            else:
                value = "hover"
            self._isDown = isDown
        # keep the last position if this message doesn't have one
        if pix is None and self.state is not None:
            pix = self.state.pix
        if pix is None:
            pix = (0, 0)
        pix = np.asarray(pix, dtype=float)
        # make response
        resp = PenResponse(
            t=t - self.clock.getLastResetTime(), value=value, device=self, **message
        )
        resp.pix = pix
        resp.units = self.getUnits()
        resp.x, resp.y = self.pixToUnits(pix, resp.units)

        return resp

    def receiveMessage(self, message, muteOutsidePsychopy=None):
        # same as BaseResponseDevice.receiveMessage, but pens send hundreds of samples a
        # second so only log the ones where something changes
        if muteOutsidePsychopy is None:
            muteOutsidePsychopy = self.muteOutsidePsychopy
        from psychopy.tools.systemtools import isRegisteredApp
        if muteOutsidePsychopy and not isRegisteredApp():
            return
        assert isinstance(message, self.responseClass), (
            f"{type(self).__name__}.receiveMessage() can only receive messages of type "
            f"{self.responseClass.__name__}, instead received {type(message).__name__}. Try "
            f"parsing the message first using {type(self).__name__}.parseMessage()"
        )
        self.responses.append(message)
        self.state = message
        self.checkCallbacks(message)
        for listener in self.listeners:
            listener.receiveMessage(message)
        if message.value not in ("hover", "move"):
            logging.exp(f"Device response: {message}")

        return True

    def getUnits(self):
        """Units which positions are given in (the device's units if set,
        otherwise the window's units).
        """
        if self.units is not None:
            return self.units
        if self.win is not None:
            return self.win.units
        return "pix"

    def pixToUnits(self, pix, units=None):
        """Convert a position in 'pix' units to other units, using the
        device's window.

        Parameters
        ----------
        pix : ArrayLike
            Position `(x, y)` in 'pix' units.
        units : str, optional
            Units to convert to, leave as None to use the device's units.

        Returns
        -------
        numpy.ndarray
            Position `(x, y)` in the requested units.
        """
        from psychopy.tools import monitorunittools as mut

        if units is None:
            units = self.getUnits()
        pix = np.asarray(pix, dtype=float)
        win = self.win
        if units in ("pix", "pixels") or win is None:
            return pix
        # framebuffer pixels per 'pix' unit
        scale = win.pixScaleFactor
        if units == "norm":
            return pix * 2.0 * scale / np.asarray(win.size)
        elif units == "height":
            return pix * scale / float(win.size[1])
        elif units in ("deg", "degs", "degFlat", "degFlatPos"):
            return mut.pix2deg(pix, win.monitor, correctFlat=units != "deg")
        elif units == "cm":
            return mut.pix2cm(pix, win.monitor)
        else:
            raise ValueError(f"Unknown units for a pen position: {units}")

    def getResponses(self, value=None, clear=True):
        """Get responses from the pen.

        Parameters
        ----------
        value : str or list[str], optional
            Only get responses with this value (or one of these values), e.g.
            "down". Leave as None to get all responses.
        clear : bool, optional
            Remove the responses which are returned, so they aren't returned
            again.

        Returns
        -------
        list[PenResponse]
            Matching responses, in chronological order.
        """
        if isinstance(value, str):
            value = [value]
        self.dispatchMessages()
        matches = []
        remaining = []
        for resp in self.responses:
            if value is None or resp.value in value:
                matches.append(resp)
            else:
                remaining.append(resp)
        if clear:
            self.responses = remaining

        return matches

    def getState(self):
        """Get the most recent response from the pen (or None if there hasn't
        been one).
        """
        self.dispatchMessages()

        return self.state

    def getPos(self, units=None):
        """Get the most recent position of the pen.

        Parameters
        ----------
        units : str, optional
            Units to get the position in, leave as None to use the device's
            units.

        Returns
        -------
        numpy.ndarray
            Position `(x, y)`.
        """
        state = self.getState()
        if state is None:
            return np.zeros(2)

        return self.pixToUnits(state.pix, units)

    def getPressure(self):
        """Get the most recent pressure of the pen tip, from 0 to 1.
        """
        state = self.getState()
        if state is None or not self._inProximity:
            return 0

        return state.pressure

    def isDown(self):
        """Is the pen currently touching the tablet?
        """
        self.dispatchMessages()

        return self._isDown

    def inProximity(self):
        """Is the pen currently in range of the tablet?
        """
        self.dispatchMessages()

        return self._inProximity

    def _pumpEvents(self):
        """Have the window process events from the operating system, needed on
        platforms where pen events arrive alongside window events.
        """
        win = self.win
        # events can only be processed on the main thread
        if win is None or threading.current_thread() is not threading.main_thread():
            return
        try:
            if win.winType == "pyglet":
                win.winHandle.dispatch_events()
            elif win.winType == "glfw":
                import glfw
                glfw.poll_events()
        except Exception as err:
            logging.debug(f"{type(self).__name__} failed to process window events: {err}")

    def close(self):
        pass

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
