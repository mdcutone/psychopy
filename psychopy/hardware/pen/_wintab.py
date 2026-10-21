#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Pen tablet backend for Windows, using the Wintab API which is installed by
the drivers of Wacom (and most other) tablets.
"""

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2025 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

__all__ = [
    'WintabPenDevice',
]

import collections
import ctypes

import numpy as np

from psychopy import clock as psyclock
from psychopy import logging
from psychopy.hardware.exceptions import DeviceNotConnectedError
from psychopy.hardware.pen.base import BasePenDevice, orientationToTilt
from psychopy.tools import wintab as wt

# packet fields which are always requested
REQUIRED_PACKET_DATA = (
    wt.PK_STATUS | wt.PK_TIME | wt.PK_CHANGED | wt.PK_SERIAL_NUMBER | wt.PK_CURSOR
    | wt.PK_BUTTONS | wt.PK_X | wt.PK_Y
)
# packet fields which are requested if the tablet supports them, against the
# axis info needed to scale them
OPTIONAL_PACKET_DATA = {
    wt.PK_Z: wt.DVC_Z,
    wt.PK_NORMAL_PRESSURE: wt.DVC_NPRESSURE,
    wt.PK_TANGENT_PRESSURE: wt.DVC_TPRESSURE,
    wt.PK_ORIENTATION: wt.DVC_ORIENTATION,
}
# Wacom drivers give each tablet three cursors, in this order
CURSOR_TYPES = ("puck", "pen", "eraser")


class _POINT(ctypes.Structure):
    _fields_ = (("x", ctypes.c_long), ("y", ctypes.c_long))


class _RECT(ctypes.Structure):
    _fields_ = (
        ("left", ctypes.c_long), ("top", ctypes.c_long),
        ("right", ctypes.c_long), ("bottom", ctypes.c_long)
    )


class _TickSync:
    """Map times from a millisecond tick counter (which Wintab uses for packet
    times) to the PsychoPy clock.

    The counter only updates every tick (1-16ms depending on the system timer
    resolution) so it lags behind the true time by up to one tick. The smallest
    offset between the PsychoPy clock and the counter, over many samples, is
    therefore the closest to the true offset. Keeping only recent samples lets
    the estimate follow any drift between the two clocks.

    Parameters
    ----------
    getTicks : callable
        Function returning the current tick count, in milliseconds.
    window : int
        Number of samples to estimate the offset from.
    """

    def __init__(self, getTicks, window=600):
        self._getTicks = getTicks
        self._refTicks = getTicks()
        self._offsets = collections.deque(maxlen=window)
        # sample for long enough to see the counter change at least once
        self.sample(duration=0.02)

    def _relTicks(self, ticks):
        # milliseconds since the reference tick, allowing for the 32-bit counter wrapping
        return ((ticks - self._refTicks + 2 ** 31) % 2 ** 32) - 2 ** 31

    def sample(self, duration=0):
        """Add a sample of the offset between the clocks.

        Parameters
        ----------
        duration : float
            Keep sampling for this long (in seconds), keeping the best sample.
        """
        best = None
        tEnd = psyclock.getTime() + duration
        while True:
            t = psyclock.getTime()
            offset = t - self._relTicks(self._getTicks()) / 1000
            if best is None or offset < best:
                best = offset
            if t >= tEnd:
                break
        self._offsets.append(best)

    def getOffset(self):
        """Current estimate of the offset, in seconds, between the PsychoPy
        clock and the reference tick.
        """
        return min(self._offsets)

    def toTime(self, ticks, offset=None):
        """Convert a tick count to the PsychoPy clock.

        Parameters
        ----------
        ticks : int
            Tick count to convert, in milliseconds.
        offset : float, optional
            Offset to use (from `getOffset`), leave as None to get the latest.

        Returns
        -------
        float
            Time in the same timebase as `psychopy.clock.getTime`.
        """
        if offset is None:
            offset = self.getOffset()

        return offset + self._relTicks(ticks) / 1000


class _AxisScale:
    """Scale raw values from a Wintab axis.

    Parameters
    ----------
    axis : psychopy.tools.wintab.AXIS
        Axis info from the driver.
    """

    def __init__(self, axis):
        self.min = axis.axMin
        self.max = axis.axMax
        self.units = axis.axUnits
        # resolution is a 16.16 fixed point number
        self.resolution = axis.axResolution / 65536

    def toFraction(self, value):
        """Scale a value to between 0 and 1."""
        if self.max <= self.min:
            return 0.0
        return min(max((value - self.min) / (self.max - self.min), 0.0), 1.0)

    def toDegrees(self, value):
        """Convert an angle to degrees."""
        if self.units == wt.TU_CIRCLE and self.resolution > 0:
            return value / self.resolution * 360
        # most drivers report angles in tenths of a degree
        return value / 10


class WintabPenDevice(BasePenDevice, aliases=["wintabPen"]):
    """Pen tablet on Windows, using the Wintab API.

    Samples are read from the driver's queue, which keeps the time each one was
    recorded, so timing doesn't depend on how often the device is polled as
    long as it's polled before the queue fills up.

    Positions are in whole screen pixels, mapped to the screen by the tablet
    driver in the same way as the system cursor.

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
    queueSize : int, optional
        Number of samples the driver should hold between polls. A tablet
        sending 200 samples a second fills a queue of 256 in just over a
        second.
    """

    def __init__(
            self, win=None, deviceIndex=0, pressureThreshold=0, units=None, queueSize=256
    ):
        BasePenDevice.__init__(
            self, win=win, deviceIndex=deviceIndex, pressureThreshold=pressureThreshold,
            units=units
        )
        self.queueSize = queueSize
        # make sure the tablet exists
        try:
            wt.getLib()
        except OSError:
            raise DeviceNotConnectedError(
                "Could not load wintab32.dll, make sure the driver for your tablet is installed.",
                deviceClass=WintabPenDevice
            )
        nDevices = wt.wtinfo_uint(wt.WTI_INTERFACE, wt.IFC_NDEVICES)
        if deviceIndex >= nDevices:
            raise DeviceNotConnectedError(
                f"Could not find a tablet with index {deviceIndex}, {nDevices} tablets are "
                f"connected.",
                deviceClass=WintabPenDevice
            )
        self._device = wt.WTI_DEVICES + deviceIndex
        self.name = wt.wtinfo_string(self._device, wt.DVC_NAME).strip()
        self._firstCursor = wt.wtinfo_uint(self._device, wt.DVC_FIRSTCSR)
        # work out which packet fields to request, and how to scale them
        available = (
            wt.wtinfo_wtpkt(self._device, wt.DVC_PKTDATA)
            | wt.wtinfo_wtpkt(self._device, wt.DVC_CSRDATA)
        )
        self._pktData = REQUIRED_PACKET_DATA
        self._axes = {}
        for flag, axisIndex in OPTIONAL_PACKET_DATA.items():
            if available and not available & flag:
                continue
            nAxes = 3 if flag == wt.PK_ORIENTATION else 1
            if wt.getLib().WTInfoW(self._device, axisIndex, None) < ctypes.sizeof(wt.AXIS) * nAxes:
                # driver doesn't describe this axis, so it isn't supported
                continue
            axes = wt.wtinfo(self._device, axisIndex, (wt.AXIS * nAxes)())
            self._axes[flag] = [_AxisScale(ax) for ax in axes]
            self._pktData |= flag
        self._packetClass = wt.makePacketClass(self._pktData)
        # context is opened once there's a window to open it on
        self._context = None
        self._sync = None
        self._wtInProximity = False
        # open now if possible, so the clock sync (which takes a few ms) doesn't delay polling
        self._open()

    @staticmethod
    def getAvailableDevices():
        try:
            wt.getLib()
        except OSError:
            logging.info(
                "No Wintab tablets available as wintab32.dll could not be loaded (it's installed "
                "by tablet drivers)."
            )
            return []
        # require spec version 1.1 or greater
        if wt.wtinfo_word(wt.WTI_INTERFACE, wt.IFC_SPECVERSION) < 0x101:
            logging.warning("Wintab driver is too old (spec version < 1.1) to be used.")
            return []
        profiles = []
        for i in range(wt.wtinfo_uint(wt.WTI_INTERFACE, wt.IFC_NDEVICES)):
            name = wt.wtinfo_string(wt.WTI_DEVICES + i, wt.DVC_NAME).strip()
            profiles.append({
                'deviceName': name or f"Wintab tablet {i}",
                'deviceIndex': i,
            })

        return profiles

    def isSameDevice(self, other):
        if isinstance(other, dict):
            return other.get('deviceIndex', 0) == self.deviceIndex
        if isinstance(other, WintabPenDevice):
            return other.deviceIndex == self.deviceIndex

        return False

    def _open(self):
        """Open a Wintab context on the window, if there is one.

        Returns
        -------
        bool
            True if the context is open.
        """
        if self._context is not None:
            return True
        win = self.win
        hwnd = getattr(win, "_hw_handle", None)
        if not hwnd:
            return False
        lib = wt.getLib()
        user32 = ctypes.windll.user32
        # start from the default system context for this tablet, so the pen also moves the
        # cursor and the driver's screen mapping is used
        lc = wt.LOGCONTEXT()
        if lib.WTInfoW(wt.WTI_DSCTXS + self.deviceIndex, 0, None):
            wt.wtinfo(wt.WTI_DSCTXS + self.deviceIndex, 0, lc)
        else:
            wt.wtinfo(wt.WTI_DEFSYSCTX, 0, lc)
        lc.lcName = "PsychoPy pen"
        lc.lcOptions |= wt.CXO_SYSTEM
        # packets are read from the queue, so no need for window messages
        lc.lcOptions &= ~wt.CXO_MESSAGES
        lc.lcPktData = self._pktData
        lc.lcPktMode = 0  # all absolute
        lc.lcMoveMask = self._pktData
        lc.lcBtnUpMask = lc.lcBtnDnMask
        # output in virtual screen pixels, with the origin at the top left
        vx, vy, vw, vh = (user32.GetSystemMetrics(i) for i in (76, 77, 78, 79))
        lc.lcOutOrgX = vx
        lc.lcOutOrgY = vy
        lc.lcOutExtX = vw
        lc.lcOutExtY = -vh
        context = lib.WTOpenW(hwnd, ctypes.byref(lc), True)
        if not context:
            logging.error(f"Could not open a Wintab context for tablet '{self.name}'.")
            return False
        # put this context on top, so it gets packets
        lib.WTOverlap(context, True)
        # set the queue size, trying smaller queues if the driver refuses
        size = self.queueSize
        while size >= 8 and not lib.WTQueueSizeSet(context, size):
            size //= 2
        actualSize = lib.WTQueueSizeGet(context)
        if actualSize > 0:
            self.queueSize = actualSize
        self._context = context
        # map the counter used for packet times (the same as timeGetTime) to the PsychoPy clock
        winmm = ctypes.windll.winmm
        winmm.timeGetTime.restype = ctypes.c_uint32
        self._sync = _TickSync(winmm.timeGetTime)
        logging.info(
            f"Opened Wintab context for tablet '{self.name}' with a queue of {self.queueSize} "
            f"packets."
        )

        return True

    def _getClientRect(self):
        """Get the position and size of the window's drawable area in screen
        coordinates, as `(left, top, width, height)`.
        """
        user32 = ctypes.windll.user32
        hwnd = ctypes.c_void_p(self.win._hw_handle)
        origin = _POINT(0, 0)
        user32.ClientToScreen(hwnd, ctypes.byref(origin))
        rect = _RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rect))

        return origin.x, origin.y, rect.right - rect.left, rect.bottom - rect.top

    def screenToPix(self, sx, sy, clientRect=None):
        """Convert a position in screen pixels to PsychoPy 'pix' units relative
        to the window.

        Parameters
        ----------
        sx, sy : int
            Position on the screen, origin at the top left.
        clientRect : tuple, optional
            Position and size of the window's drawable area, as
            `(left, top, width, height)` in screen pixels. Leave as None to get
            it from the window.

        Returns
        -------
        numpy.ndarray
            Position `(x, y)` in 'pix' units, origin at the center of the window.
        """
        if clientRect is None:
            clientRect = self._getClientRect()
        left, top, width, height = clientRect
        win = self.win
        size = np.asarray(win.size, dtype=float)
        # the client area may differ in size from the framebuffer (e.g. on high DPI displays)
        buffX = (sx - left) * size[0] / max(width, 1)
        buffY = (height - (sy - top)) * size[1] / max(height, 1)

        return (np.array((buffX, buffY)) - size / 2) / win.pixScaleFactor

    def packetToSamples(self, packet, offset=None, clientRect=None):
        """Convert a Wintab packet into samples for `BasePenDevice.parseMessage`.

        Parameters
        ----------
        packet : ctypes.Structure
            Packet from the driver, made by `psychopy.tools.wintab.makePacketClass`.
        offset : float, optional
            Clock offset from `_TickSync.getOffset`.
        clientRect : tuple, optional
            Position and size of the window, see `screenToPix`.

        Returns
        -------
        list[dict]
            Samples (as few as none, if the packet is just the pen leaving).
        """
        samples = []
        t = self._sync.toTime(packet.pkTime, offset) if self._sync else psyclock.getTime()
        if packet.pkStatus & wt.TPS_QUEUE_ERR:
            logging.warning(
                f"Wintab queue for tablet '{self.name}' overflowed, some samples were lost. Poll "
                f"the pen more often or increase its queue size."
            )
        # TPS_PROXIMITY is set when the pen is *out* of range
        if packet.pkStatus & wt.TPS_PROXIMITY:
            if self._wtInProximity:
                self._wtInProximity = False
                samples.append({'type': "leave", 't': t})
            return samples
        # what's touching the tablet?
        if packet.pkStatus & wt.TPS_INVERT:
            cursor = "eraser"
        else:
            cursor = CURSOR_TYPES[(packet.pkCursor - self._firstCursor) % 3]
        if not self._wtInProximity:
            self._wtInProximity = True
            samples.append({'type': "enter", 't': t, 'cursor': cursor})
        sample = {
            'type': "sample",
            't': t,
            'pix': self.screenToPix(packet.pkX, packet.pkY, clientRect),
            'buttons': packet.pkButtons,
            'cursor': cursor,
        }
        if wt.PK_Z in self._axes:
            sample['z'] = packet.pkZ
        if wt.PK_NORMAL_PRESSURE in self._axes:
            sample['pressure'] = self._axes[wt.PK_NORMAL_PRESSURE][0].toFraction(
                packet.pkNormalPressure
            )
        if wt.PK_TANGENT_PRESSURE in self._axes:
            sample['tangentialPressure'] = self._axes[wt.PK_TANGENT_PRESSURE][0].toFraction(
                packet.pkTangentPressure
            )
        if wt.PK_ORIENTATION in self._axes:
            azAxis, altAxis, twistAxis = self._axes[wt.PK_ORIENTATION]
            azimuth = azAxis.toDegrees(packet.pkOrientation.orAzimuth) % 360
            # altitude is negative when the pen is upside down (eraser)
            altitude = abs(altAxis.toDegrees(packet.pkOrientation.orAltitude))
            sample['azimuth'] = azimuth
            sample['altitude'] = altitude
            sample['twist'] = twistAxis.toDegrees(packet.pkOrientation.orTwist)
            sample['tiltX'], sample['tiltY'] = orientationToTilt(azimuth, altitude)
        samples.append(sample)

        return samples

    def _poll(self):
        if not self._open():
            return []
        lib = wt.getLib()
        self._sync.sample()
        offset = self._sync.getOffset()
        clientRect = self._getClientRect()
        samples = []
        buffer = (self._packetClass * self.queueSize)()
        while True:
            n = lib.WTPacketsGet(self._context, self.queueSize, buffer)
            for i in range(n):
                samples += self.packetToSamples(buffer[i], offset=offset, clientRect=clientRect)
            # if the buffer was filled there may be more packets waiting
            if n < self.queueSize:
                break

        return samples

    def close(self):
        if self._context is not None:
            try:
                wt.getLib().WTClose(self._context)
            finally:
                self._context = None
