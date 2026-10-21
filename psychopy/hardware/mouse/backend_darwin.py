#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Mouse backend which gets events system-wide from a Quartz event tap
(macOS).

"""

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2025 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

__all__ = ['QuartzMouseBackend']

import threading

# import everything up front, as pyobjc looks names up lazily, which isn't
# thread safe and the tap runs on its own thread
from Quartz import (
    CFMachPortCreateRunLoopSource,
    CFRunLoopAddSource,
    CFRunLoopGetCurrent,
    CFRunLoopRemoveSource,
    CFRunLoopRunInMode,
    CFRunLoopStop,
    CGAssociateMouseAndMouseCursorPosition,
    CGEventCreate,
    CGEventGetDoubleValueField,
    CGEventGetIntegerValueField,
    CGEventGetLocation,
    CGEventGetTimestamp,
    CGEventMaskBit,
    CGEventTapCreate,
    CGEventTapEnable,
    CGWarpMouseCursorPosition,
    CGWindowListCopyWindowInfo,
    kCFRunLoopCommonModes,
    kCFRunLoopDefaultMode,
    kCGEventLeftMouseDown,
    kCGEventLeftMouseDragged,
    kCGEventLeftMouseUp,
    kCGEventMouseMoved,
    kCGEventOtherMouseDown,
    kCGEventOtherMouseDragged,
    kCGEventOtherMouseUp,
    kCGEventRightMouseDown,
    kCGEventRightMouseDragged,
    kCGEventRightMouseUp,
    kCGEventScrollWheel,
    kCGEventTapDisabledByTimeout,
    kCGEventTapDisabledByUserInput,
    kCGEventTapOptionListenOnly,
    kCGHeadInsertEventTap,
    kCGMouseEventButtonNumber,
    kCGScrollWheelEventFixedPtDeltaAxis1,
    kCGScrollWheelEventFixedPtDeltaAxis2,
    kCGSessionEventTap,
    kCGWindowBounds,
    kCGWindowListOptionIncludingWindow,
)

from psychopy.clock import getTime
from psychopy.hardware.mouse import (
    MOUSE_BUTTON_LEFT, MOUSE_BUTTON_MIDDLE, MOUSE_BUTTON_RIGHT,
    MOUSE_BUTTON_X1, MOUSE_BUTTON_X2)
from ._base import BaseMouseBackend

# event types the tap listens for, with the kind of event and the button
_EVENT_TYPES = {
    kCGEventLeftMouseDown: ("press", MOUSE_BUTTON_LEFT),
    kCGEventLeftMouseUp: ("release", MOUSE_BUTTON_LEFT),
    kCGEventRightMouseDown: ("press", MOUSE_BUTTON_RIGHT),
    kCGEventRightMouseUp: ("release", MOUSE_BUTTON_RIGHT),
    kCGEventOtherMouseDown: ("press", None),
    kCGEventOtherMouseUp: ("release", None),
    kCGEventMouseMoved: ("move", None),
    kCGEventLeftMouseDragged: ("move", None),
    kCGEventRightMouseDragged: ("move", None),
    kCGEventOtherMouseDragged: ("move", None),
    kCGEventScrollWheel: ("scroll", None)
}
# buttons for 'other' mouse events, by `kCGMouseEventButtonNumber`
_OTHER_BUTTONS = {
    2: MOUSE_BUTTON_MIDDLE,
    3: MOUSE_BUTTON_X1,
    4: MOUSE_BUTTON_X2
}
# events which mean the system has disabled the tap
_TAP_DISABLED = (
    kCGEventTapDisabledByTimeout,
    kCGEventTapDisabledByUserInput
)
# event timestamps further than this (in seconds) before the callback runs
# can't be on the same clock as `getTime()`
_MAX_EVENT_AGE = 1.0


class QuartzMouseBackend(BaseMouseBackend):
    """Get mouse events system-wide from a listen-only Quartz event tap
    (macOS), running on its own thread.

    Events are timestamped by the system when they happen, on the same clock as
    `psychopy.clock.getTime()`. Positions are in global display coordinates
    (points), with the origin at the top-left of the main display.

    Notes
    -----
    * The tap can't be made unless the app running Python is allowed to monitor
      input, in System Settings > Privacy & Security.

    """
    name = "darwin"
    usesScreenCoords = True

    def __init__(self, device):
        BaseMouseBackend.__init__(self, device)
        self._tap = None
        self._runLoop = None
        self._thread = None
        self._ready = threading.Event()

    def start(self):
        if self._running:
            return
        mask = 0
        for eventType in _EVENT_TYPES:
            mask |= CGEventMaskBit(eventType)
        self._tap = CGEventTapCreate(
            kCGSessionEventTap,
            kCGHeadInsertEventTap,
            kCGEventTapOptionListenOnly,
            mask,
            self._onEvent,
            None)
        if self._tap is None:
            raise RuntimeError(
                "Could not create a Quartz event tap for the mouse, check that "
                "the app running Python is allowed to monitor input in System "
                "Settings > Privacy & Security.")
        self._running = True
        self._ready.clear()
        self._thread = threading.Thread(
            target=self._run, name="QuartzMouseBackend", daemon=True)
        self._thread.start()
        self._ready.wait(1.0)

    def _run(self):
        """Run the tap until stopped, on the backend's thread."""
        self._runLoop = CFRunLoopGetCurrent()
        source = CFMachPortCreateRunLoopSource(None, self._tap, 0)
        CFRunLoopAddSource(
            self._runLoop, source, kCFRunLoopCommonModes)
        CGEventTapEnable(self._tap, True)
        self._ready.set()
        # run in short slices, in case `stop` is called before the loop runs
        while self._running:
            CFRunLoopRunInMode(kCFRunLoopDefaultMode, 0.25, False)
        CGEventTapEnable(self._tap, False)
        CFRunLoopRemoveSource(
            self._runLoop, source, kCFRunLoopCommonModes)

    def stop(self):
        if not self._running:
            return
        self._running = False
        if self._runLoop is not None:
            CFRunLoopStop(self._runLoop)
        if self._thread is not None:
            self._thread.join(1.0)
        self._thread = None
        self._runLoop = None
        self._tap = None

    def _onEvent(self, proxy, eventType, event, refcon):
        """Called by the tap for each event, on the backend's thread."""
        now = getTime()
        if eventType in _TAP_DISABLED:
            # the system disables taps it thinks are slow, so turn it back on
            if self._tap is not None:
                CGEventTapEnable(self._tap, True)
            return event
        kind, button = _EVENT_TYPES.get(eventType, (None, None))
        if kind is None:
            return event
        if eventType in (kCGEventOtherMouseDown,
                         kCGEventOtherMouseUp):
            button = _OTHER_BUTTONS.get(CGEventGetIntegerValueField(
                event, kCGMouseEventButtonNumber))
            if button is None:
                return event
        scroll = None
        if kind == "scroll":
            scroll = (
                CGEventGetDoubleValueField(
                    event, kCGScrollWheelEventFixedPtDeltaAxis2),
                CGEventGetDoubleValueField(
                    event, kCGScrollWheelEventFixedPtDeltaAxis1))
        location = CGEventGetLocation(event)
        # timestamps are nanoseconds on the same clock as `getTime()`, but
        # check in case they aren't
        osTime = CGEventGetTimestamp(event)
        t = osTime * 1e-9
        if not 0.0 <= now - t < _MAX_EVENT_AGE:
            t = now
        self.push(kind, t, button=button, screenPos=(location.x, location.y),
                  scroll=scroll, osTime=osTime)

        return event

    def getWindowRect(self, win):
        windowNumber = getattr(win, '_hw_handle', None)
        if windowNumber is None:
            return None
        info = CGWindowListCopyWindowInfo(
            kCGWindowListOptionIncludingWindow, int(windowNumber))
        if not info:
            return None
        bounds = info[0].get(kCGWindowBounds)
        if bounds is None:
            return None
        left, top = bounds['X'], bounds['Y']
        width, height = bounds['Width'], bounds['Height']
        # the bounds include the title bar, which is above the content area, so
        # get the height of the content from the shape of the framebuffer
        fbWidth, fbHeight = win.frameBufferSize
        contentHeight = min(height, width * fbHeight / float(fbWidth))

        return left, top + height - contentHeight, width, contentHeight

    def getCursorPos(self):
        location = CGEventGetLocation(CGEventCreate(None))

        return location.x, location.y

    def setCursorPos(self, pos):
        CGWarpMouseCursorPosition((float(pos[0]), float(pos[1])))
        # warping stops the cursor following the mouse for a moment, so
        # reconnect them straight away
        CGAssociateMouseAndMouseCursorPosition(True)

        return True


if __name__ == "__main__":
    pass
