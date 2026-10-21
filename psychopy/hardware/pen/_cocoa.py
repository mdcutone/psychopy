#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Pen tablet backend for macOS, reading tablet data from the events which the
tablet driver sends to the application.
"""

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2025 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

__all__ = [
    'CocoaPenDevice',
    'getAttachedTablets',
]

import ctypes
import ctypes.util

import numpy as np

import AppKit
import Foundation
import objc

from psychopy import clock as psyclock
from psychopy import logging
from psychopy.hardware.exceptions import DeviceNotConnectedError
from psychopy.hardware.pen.base import BasePenDevice, tiltToOrientation

# NSEvent reports tilt from -1 to 1, with 1 being the tablet's maximum tilt
MAX_TILT = 60
# mouse events, which carry tablet data when they come from a pen
MOUSE_EVENT_TYPES = {
    AppKit.NSEventTypeLeftMouseDown,
    AppKit.NSEventTypeLeftMouseUp,
    AppKit.NSEventTypeLeftMouseDragged,
    AppKit.NSEventTypeRightMouseDown,
    AppKit.NSEventTypeRightMouseUp,
    AppKit.NSEventTypeRightMouseDragged,
    AppKit.NSEventTypeOtherMouseDown,
    AppKit.NSEventTypeOtherMouseUp,
    AppKit.NSEventTypeOtherMouseDragged,
    AppKit.NSEventTypeMouseMoved,
}
EVENT_MASK = (
    AppKit.NSEventMaskTabletPoint
    | AppKit.NSEventMaskTabletProximity
    | AppKit.NSEventMaskLeftMouseDown
    | AppKit.NSEventMaskLeftMouseUp
    | AppKit.NSEventMaskLeftMouseDragged
    | AppKit.NSEventMaskRightMouseDown
    | AppKit.NSEventMaskRightMouseUp
    | AppKit.NSEventMaskRightMouseDragged
    | AppKit.NSEventMaskOtherMouseDown
    | AppKit.NSEventMaskOtherMouseUp
    | AppKit.NSEventMaskOtherMouseDragged
    | AppKit.NSEventMaskMouseMoved
)
CURSOR_TYPES = {
    AppKit.NSPointingDeviceTypePen: "pen",
    AppKit.NSPointingDeviceTypeEraser: "eraser",
    AppKit.NSPointingDeviceTypeCursor: "puck",
}
# HID usage page for digitizers, and the usages on it which are pens (rather than touch
# screens or trackpads, which are also digitizers)
HID_DIGITIZER_PAGE = 0x0D
HID_PEN_USAGES = {
    0x01,  # digitizer (e.g. a graphics tablet)
    0x02,  # pen
    0x03,  # light pen
}
# USB vendor IDs of pen tablet makers, whose tablets don't always describe themselves as pens
TABLET_VENDORS = {
    0x056A: "Wacom",
    0x256C: "Huion",
    0x28BD: "XP-Pen",
    0x5543: "UC-Logic",
    0x2FEB: "Veikk",
}


def _iterHIDDevices():
    """Get the properties of each HID device (or interface of a device) in the IORegistry.

    Reading the registry doesn't open the devices, so doesn't need the Input
    Monitoring permission.

    Yields
    ------
    dict
        Properties of a HID device, e.g. "Product", "VendorID", "ProductID",
        "SerialNumber", "LocationID", "PrimaryUsagePage", "PrimaryUsage",
        "DeviceUsagePairs".
    """
    iokit = ctypes.cdll.LoadLibrary(ctypes.util.find_library("IOKit"))
    cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))
    iokit.IOServiceMatching.argtypes = (ctypes.c_char_p,)
    iokit.IOServiceMatching.restype = ctypes.c_void_p
    iokit.IOServiceGetMatchingServices.argtypes = (
        ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)
    )
    iokit.IOServiceGetMatchingServices.restype = ctypes.c_int
    iokit.IOIteratorNext.argtypes = (ctypes.c_uint32,)
    iokit.IOIteratorNext.restype = ctypes.c_uint32
    iokit.IORegistryEntryCreateCFProperties.argtypes = (
        ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.c_uint32
    )
    iokit.IORegistryEntryCreateCFProperties.restype = ctypes.c_int
    iokit.IOObjectRelease.argtypes = (ctypes.c_uint32,)
    iokit.IOObjectRelease.restype = ctypes.c_int
    cf.CFRelease.argtypes = (ctypes.c_void_p,)

    iterator = ctypes.c_uint32()
    # the matching dict is consumed by IOServiceGetMatchingServices, 0 is the default main port
    matching = iokit.IOServiceMatching(b"IOHIDDevice")
    if iokit.IOServiceGetMatchingServices(0, matching, ctypes.byref(iterator)) != 0:
        return
    try:
        while True:
            entry = iokit.IOIteratorNext(iterator)
            if not entry:
                break
            try:
                props = ctypes.c_void_p()
                if iokit.IORegistryEntryCreateCFProperties(
                        entry, ctypes.byref(props), None, 0
                ) != 0 or not props.value:
                    continue
                # wrap as an NSDictionary (which keeps its own reference), then release ours
                nsProps = objc.objc_object(c_void_p=props.value)
                cf.CFRelease(props)
                yield {
                    key: _fromObjC(nsProps.get(key))
                    for key in (
                        "Product", "Manufacturer", "VendorID", "ProductID", "SerialNumber",
                        "LocationID", "Transport", "PrimaryUsagePage", "PrimaryUsage",
                        "DeviceUsagePairs",
                    )
                }
            finally:
                iokit.IOObjectRelease(entry)
    finally:
        iokit.IOObjectRelease(iterator.value)


def _fromObjC(value):
    """Convert a property list value from Objective-C to plain Python types."""
    if value is None:
        return None
    if isinstance(value, (AppKit.NSArray, list, tuple)):
        return [_fromObjC(item) for item in value]
    if isinstance(value, (AppKit.NSDictionary, dict)):
        return {str(key): _fromObjC(val) for key, val in value.items()}
    if isinstance(value, str):
        return str(value)
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return float(value)
    return value


def isTabletInterface(props):
    """Is a HID device (or interface) a pen tablet?

    Parameters
    ----------
    props : dict
        Properties of the device, from the IORegistry.

    Returns
    -------
    bool
        True if the device reports itself as a pen (not a touch screen or
        trackpad), or comes from a pen tablet maker.
    """
    usages = [(props.get("PrimaryUsagePage"), props.get("PrimaryUsage"))]
    for pair in props.get("DeviceUsagePairs") or []:
        usages.append((pair.get("DeviceUsagePage"), pair.get("DeviceUsage")))
    for page, usage in usages:
        if page == HID_DIGITIZER_PAGE and usage in HID_PEN_USAGES:
            return True

    return props.get("VendorID") in TABLET_VENDORS


def getAttachedTablets(devices=None):
    """Get the pen tablets attached to the system.

    Parameters
    ----------
    devices : list[dict], optional
        Properties of HID devices to look through, leave as None to read them
        from the system.

    Returns
    -------
    list[dict]
        Profile for each tablet, with keys "deviceName", "vendorID",
        "productID" and "serialNumber".
    """
    if devices is None:
        try:
            devices = list(_iterHIDDevices())
        except Exception as err:
            logging.error(f"Could not list HID devices to find pen tablets: {err}")
            return []
    tablets = {}
    for props in devices:
        if not isTabletInterface(props):
            continue
        vendorID = props.get("VendorID") or 0
        productID = props.get("ProductID") or 0
        serialNumber = props.get("SerialNumber") or ""
        # tablets have several interfaces (pen, touch, buttons...), so group them by the
        # physical device they're part of
        key = (vendorID, productID, serialNumber or props.get("LocationID"))
        if key in tablets:
            continue
        name = (props.get("Product") or "").strip()
        if not name:
            name = f"{TABLET_VENDORS.get(vendorID, 'Pen')} tablet ({vendorID:04x}:{productID:04x})"
        tablets[key] = {
            'deviceName': name,
            'vendorID': vendorID,
            'productID': productID,
            'serialNumber': serialNumber,
        }
    # give tablets which share a name a number, so they can be told apart
    profiles = list(tablets.values())
    names = [profile['deviceName'] for profile in profiles]
    for profile in profiles:
        if names.count(profile['deviceName']) > 1:
            profile['deviceName'] += f" ({profile['serialNumber'] or profiles.index(profile) + 1})"

    return profiles


def eventToRaw(event):
    """Get the tablet data from an NSEvent.

    Parameters
    ----------
    event : AppKit.NSEvent
        Event to read.

    Returns
    -------
    tuple or None
        Either `("proximity", timestamp, entering, deviceType)` or
        `("point", timestamp, screenX, screenY, pressure, tangentialPressure,
        tiltX, tiltY, rotation, z, buttons)`, or None if the event has no
        tablet data. Times are seconds since the system started and screen
        positions are in points, origin at the bottom left.
    """
    kind = event.type()
    subtype = None
    if kind in MOUSE_EVENT_TYPES:
        subtype = event.subtype()
    if kind == AppKit.NSEventTypeTabletProximity or subtype == AppKit.NSEventSubtypeTabletProximity:
        return (
            "proximity", event.timestamp(), bool(event.isEnteringProximity()),
            event.pointingDeviceType()
        )
    if kind == AppKit.NSEventTypeTabletPoint or subtype == AppKit.NSEventSubtypeTabletPoint:
        loc = event.locationInWindow()
        # events not tied to a window are already in screen coordinates
        nsWindow = event.window()
        if nsWindow is not None:
            loc = nsWindow.convertPointToScreen_(loc)
        tilt = event.tilt()
        return (
            "point", event.timestamp(), loc.x, loc.y, event.pressure(),
            event.tangentialPressure(), tilt.x, tilt.y, event.rotation(), event.absoluteZ(),
            event.buttonMask()
        )

    return None


class CocoaPenDevice(BasePenDevice, aliases=["cocoaPen"]):
    """Pen tablet on macOS.

    The tablet driver sends tablet data along with mouse events, so samples
    are only received while the window is processing events (e.g. on
    `win.flip()`, or when this device is polled). Each event keeps the time it
    was recorded, so the times of samples are accurate even if they're read
    late.

    Attached tablets are found from the USB/Bluetooth devices which describe
    themselves as pens, or come from pen tablet makers. macOS sends events from
    all tablets the same way, so samples from every attached tablet are read
    whichever tablet this device is made for.

    Parameters
    ----------
    win : psychopy.visual.Window, optional
        Window which the pen is used on, leave as None to use the first window
        which is opened.
    deviceIndex : int, optional
        Not used, tablets on macOS are identified by `vendorID`, `productID` and
        `serialNumber`.
    pressureThreshold : float, optional
        Pressure (from 0 to 1) above which the pen counts as touching the
        tablet.
    units : str, optional
        Units for the positions of responses, leave as None to use the units
        of the window.
    vendorID, productID : int, optional
        USB vendor and product IDs of the tablet, leave as None to use the
        first attached tablet.
    serialNumber : str, optional
        Serial number of the tablet, to tell apart several of the same model.
    """

    def __init__(
            self, win=None, deviceIndex=0, pressureThreshold=0, units=None, vendorID=None,
            productID=None, serialNumber=""
    ):
        BasePenDevice.__init__(
            self, win=win, deviceIndex=deviceIndex, pressureThreshold=pressureThreshold,
            units=units
        )
        self.vendorID = vendorID
        self.productID = productID
        self.serialNumber = serialNumber or ""
        # find the tablet
        attached = self.getAvailableDevices()
        if vendorID is None and productID is None:
            if attached:
                # use the first tablet
                self.vendorID = attached[0]['vendorID']
                self.productID = attached[0]['productID']
                self.serialNumber = attached[0]['serialNumber']
            else:
                # samples from a tablet which wasn't detected still come through, so carry on
                logging.warning(
                    "No pen tablets were found attached to this computer, but samples from any "
                    "pen tablet will still be read."
                )
        elif not any(self.isSameDevice(profile) for profile in attached):
            raise DeviceNotConnectedError(
                f"Could not find pen tablet with vendor ID {vendorID}, product ID {productID}"
                + (f" and serial number {serialNumber}" if serialNumber else "")
                + ", make sure it's connected.",
                deviceClass=CocoaPenDevice
            )
        # tablet data from events, waiting to be dispatched
        self._queue = []
        self._monitor = None
        self._nsWindow = None
        self._lastRaw = None
        self._coalescing = None
        # start listening now if there's a window
        self._open()

    @staticmethod
    def getAvailableDevices():
        return getAttachedTablets()

    def isSameDevice(self, other):
        if isinstance(other, CocoaPenDevice):
            other = {
                'vendorID': other.vendorID,
                'productID': other.productID,
                'serialNumber': other.serialNumber,
            }
        if not isinstance(other, dict):
            return False
        if (other.get('vendorID'), other.get('productID')) != (self.vendorID, self.productID):
            return False
        # only compare serial numbers if both have one
        otherSerial = other.get('serialNumber')
        if self.serialNumber and otherSerial and otherSerial != self.serialNumber:
            return False

        return True

    def _open(self):
        """Start listening for tablet events, if there's a window.

        Returns
        -------
        bool
            True if listening.
        """
        if self._monitor is not None:
            return True
        win = self.win
        windowNumber = getattr(win, "_hw_handle", None)
        if not windowNumber:
            return False
        app = AppKit.NSApplication.sharedApplication()
        self._nsWindow = app.windowWithWindowNumber_(windowNumber)
        if self._nsWindow is None:
            logging.error(f"Could not find window {windowNumber} to read pen tablet events on.")
            return False
        # without this, macOS merges consecutive mouse (and so pen) events
        self._coalescing = AppKit.NSEvent.isMouseCoalescingEnabled()
        AppKit.NSEvent.setMouseCoalescingEnabled_(False)
        self._monitor = AppKit.NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            EVENT_MASK, self._handleEvent
        )

        return True

    def _handleEvent(self, event):
        try:
            raw = eventToRaw(event)
        except Exception as err:
            logging.debug(f"Failed to read pen tablet event: {err}")
            raw = None
        if raw is not None:
            self._queue.append(raw)
        # pass the event on, so the window still gets it
        return event

    def screenToPix(self, sx, sy):
        """Convert a position on the screen to PsychoPy 'pix' units relative to
        the window.

        Parameters
        ----------
        sx, sy : float
            Position on the screen in points, origin at the bottom left.

        Returns
        -------
        numpy.ndarray
            Position `(x, y)` in 'pix' units, origin at the center of the window.
        """
        win = self.win
        view = self._nsWindow.contentView()
        pt = self._nsWindow.convertPointFromScreen_(Foundation.NSMakePoint(sx, sy))
        pt = view.convertPoint_fromView_(pt, None)
        bounds = view.bounds()
        width = max(bounds.size.width, 1)
        height = max(bounds.size.height, 1)
        x = pt.x - bounds.origin.x
        y = pt.y - bounds.origin.y
        if view.isFlipped():
            y = height - y

        return self.viewToPix(x, y, width, height, win)

    @staticmethod
    def viewToPix(x, y, width, height, win):
        """Convert a position within the window's view (in points, origin at
        the bottom left) to PsychoPy 'pix' units.
        """
        size = np.asarray(win.size, dtype=float)
        # the view is in points, which may differ in size from framebuffer pixels
        buff = np.array((x * size[0] / width, y * size[1] / height))

        return (buff - size / 2) / win.pixScaleFactor

    def rawToSample(self, raw, offset):
        """Convert tablet data from `eventToRaw` into a sample for
        `BasePenDevice.parseMessage`.

        Parameters
        ----------
        raw : tuple
            Output of `eventToRaw`.
        offset : float
            Seconds to add to event times to get the PsychoPy clock.

        Returns
        -------
        dict
            The sample.
        """
        if raw[0] == "proximity":
            _, timestamp, entering, deviceType = raw
            sample = {'type': "enter" if entering else "leave", 't': timestamp + offset}
            if entering:
                sample['cursor'] = CURSOR_TYPES.get(deviceType, "pen")
            return sample
        (
            _, timestamp, sx, sy, pressure, tangentialPressure, tiltX, tiltY, rotation, z,
            buttons
        ) = raw
        # flip y, so that positive tilt is towards the top of the tablet
        tiltX = tiltX * MAX_TILT + 0.0
        tiltY = -tiltY * MAX_TILT + 0.0  # + 0.0 avoids -0.0
        azimuth, altitude = tiltToOrientation(tiltX, tiltY)

        return {
            'type': "sample",
            't': timestamp + offset,
            'pix': self.screenToPix(sx, sy),
            'pressure': pressure,
            'tangentialPressure': tangentialPressure,
            'tiltX': tiltX,
            'tiltY': tiltY,
            'azimuth': azimuth,
            'altitude': altitude,
            'twist': rotation,
            'z': z,
            'buttons': buttons,
        }

    def _poll(self):
        if not self._open():
            return []
        # process events so the monitor sees any new ones
        self._pumpEvents()
        raws = self._queue
        self._queue = []
        # event times are seconds since the system started
        offset = psyclock.getTime() - Foundation.NSProcessInfo.processInfo().systemUptime()
        samples = []
        for raw in raws:
            # skip duplicates (the same sample can arrive as both a mouse and a tablet event)
            if raw == self._lastRaw:
                continue
            self._lastRaw = raw
            samples.append(self.rawToSample(raw, offset))

        return samples

    def close(self):
        if self._monitor is not None:
            AppKit.NSEvent.removeMonitor_(self._monitor)
            self._monitor = None
        if self._coalescing is not None:
            AppKit.NSEvent.setMouseCoalescingEnabled_(self._coalescing)
            self._coalescing = None
