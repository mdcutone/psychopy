#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Mouse backend which gets events system-wide from the RECORD extension of X11
(Linux).

"""

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2025 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

__all__ = ['XlibMouseBackend']

import os
import threading

from Xlib import X, display
from Xlib.ext import record
from Xlib.protocol import rq

from psychopy.clock import getTime
from psychopy.hardware.mouse import (
    MOUSE_BUTTON_LEFT, MOUSE_BUTTON_MIDDLE, MOUSE_BUTTON_RIGHT,
    MOUSE_BUTTON_X1, MOUSE_BUTTON_X2)
from ._base import BaseMouseBackend

# X button numbers for each button
_BUTTONS = {
    1: MOUSE_BUTTON_LEFT,
    2: MOUSE_BUTTON_MIDDLE,
    3: MOUSE_BUTTON_RIGHT,
    8: MOUSE_BUTTON_X1,
    9: MOUSE_BUTTON_X2
}
# X reports scrolling as presses of these buttons, with the offset of each
_SCROLL_BUTTONS = {
    4: (0.0, 1.0),
    5: (0.0, -1.0),
    6: (-1.0, 0.0),
    7: (1.0, 0.0)
}


class XlibMouseBackend(BaseMouseBackend):
    """Get mouse events system-wide from the RECORD extension of X11 (Linux),
    running on its own thread.

    Events are timestamped when they are received, with
    `psychopy.clock.getTime()`, as X gives times in milliseconds on its own
    clock. Positions are in coordinates of the root window (pixels), with the
    origin at its top-left.

    Notes
    -----
    * Wayland doesn't let apps receive input events from the whole system, so
      this only works in X11 sessions.

    """
    name = "xlib"
    usesScreenCoords = True

    def __init__(self, device):
        BaseMouseBackend.__init__(self, device)
        # connection for queries and to control recording, and the connection
        # recording is done on (which is blocked while it runs)
        self._local = None
        self._record = None
        self._context = None
        self._thread = None
        # connections can't be used from more than one thread at once
        self._lock = threading.Lock()

    def start(self):
        if self._running:
            return
        if os.environ.get('XDG_SESSION_TYPE', '').lower() == 'wayland' or \
                not os.environ.get('DISPLAY'):
            raise RuntimeError(
                "Getting mouse events from the whole system needs an X11 "
                "session, which this isn't (e.g. it's Wayland).")
        self._local = display.Display()
        self._record = display.Display()
        if not self._record.has_extension('RECORD'):
            self._local.close()
            self._record.close()
            raise RuntimeError(
                "The X server doesn't support the RECORD extension, which is "
                "needed to get mouse events from the whole system.")
        self._context = self._record.record_create_context(
            0,
            [record.AllClients],
            [{
                'core_requests': (0, 0),
                'core_replies': (0, 0),
                'ext_requests': (0, 0, 0, 0),
                'ext_replies': (0, 0, 0, 0),
                'delivered_events': (0, 0),
                'device_events': (X.ButtonPress, X.MotionNotify),
                'errors': (0, 0),
                'client_started': False,
                'client_died': False
            }])
        self._running = True
        self._thread = threading.Thread(
            target=self._run, name="XlibMouseBackend", daemon=True)
        self._thread.start()

    def _run(self):
        """Record events until stopped, on the backend's thread."""
        # blocks until `stop` disables the context
        self._record.record_enable_context(self._context, self._onReply)
        self._record.record_free_context(self._context)
        self._record.close()

    def stop(self):
        if not self._running:
            return
        self._running = False
        with self._lock:
            self._local.record_disable_context(self._context)
            self._local.flush()
        if self._thread is not None:
            self._thread.join(1.0)
        with self._lock:
            self._local.close()
        self._thread = None
        self._context = None
        self._local = None
        self._record = None

    def _onReply(self, reply):
        """Called with each batch of recorded events, on the backend's
        thread."""
        t = getTime()
        if reply.category != record.FromServer or reply.client_swapped:
            return
        if not len(reply.data) or reply.data[0] < 2:
            # not an event
            return
        data = reply.data
        while len(data):
            event, data = rq.EventField(None).parse_binary_value(
                data, self._record.display, None, None)
            screenPos = (event.root_x, event.root_y)
            if event.type == X.MotionNotify:
                self.push("move", t, screenPos=screenPos, osTime=event.time)
            elif event.detail in _SCROLL_BUTTONS:
                # scrolling is a press and release, so only count presses
                if event.type == X.ButtonPress:
                    self.push(
                        "scroll", t, screenPos=screenPos,
                        scroll=_SCROLL_BUTTONS[event.detail],
                        osTime=event.time)
            elif event.detail in _BUTTONS:
                kind = "press" if event.type == X.ButtonPress else "release"
                self.push(
                    kind, t, button=_BUTTONS[event.detail],
                    screenPos=screenPos, osTime=event.time)

    def getWindowRect(self, win):
        windowId = getattr(win, '_hw_handle', None)
        if not windowId or self._local is None:
            return None
        with self._lock:
            window = self._local.create_resource_object('window', int(windowId))
            geometry = window.get_geometry()
            # position of the window's top-left corner on the root window
            origin = self._local.screen().root.translate_coords(window, 0, 0)

        return origin.x, origin.y, geometry.width, geometry.height

    def getCursorPos(self):
        if self._local is None:
            return None
        with self._lock:
            pointer = self._local.screen().root.query_pointer()

        return pointer.root_x, pointer.root_y

    def setCursorPos(self, pos):
        if self._local is None:
            return False
        with self._lock:
            self._local.screen().root.warp_pointer(
                int(round(pos[0])), int(round(pos[1])))
            self._local.sync()

        return True


if __name__ == "__main__":
    pass
