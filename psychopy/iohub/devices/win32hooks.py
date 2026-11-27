# -*- coding: utf-8 -*-
# Part of the PsychoPy library
# Copyright 2026 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).
"""Low-level Windows keyboard and mouse hooks for the ioHub server.

Replaces pyWinhook. The hooks are installed by pynput listeners, each of which
runs its own thread and message loop, so events are delivered as soon as they
happen rather than when the ioHub server next pumps its message queue.

Only pynput's hook plumbing is used: the raw ``KBDLLHOOKSTRUCT`` /
``MSLLHOOKSTRUCT`` data is read in ``win32_event_filter``, which returns False
so pynput does no translation of its own. Events are never suppressed.

Callbacks run on the listener threads. They receive record objects with the
same attribute names pyWinhook's events had (``Message``, ``KeyID``,
``ScanCode``, ``flags``, ``Time``, ``Window``, ``Position``, ``Wheel``) and
should do no more than timestamp the record and queue it for the server's main
thread.
"""

import ctypes
from ctypes import wintypes

from ..errors import print2err, printExceptionDetailsToStdErr

# A private user32 instance, so setting argtypes here does not affect
# ctypes.windll.user32 as used by pynput or other code.
_user32 = ctypes.WinDLL('user32', use_last_error=True)

_GetForegroundWindow = _user32.GetForegroundWindow
_GetForegroundWindow.argtypes = ()
_GetForegroundWindow.restype = wintypes.HWND

_WindowFromPoint = _user32.WindowFromPoint
_WindowFromPoint.argtypes = (wintypes.POINT,)
_WindowFromPoint.restype = wintypes.HWND

_GetKeyState = _user32.GetKeyState
_GetKeyState.argtypes = (ctypes.c_int,)
_GetKeyState.restype = wintypes.SHORT

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
KEY_DOWN_MESSAGES = (WM_KEYDOWN, WM_SYSKEYDOWN)
KEY_MESSAGES = (WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP)

WM_MOUSEMOVE = 0x0200
WM_MOUSEWHEEL = 0x020A
# The mouse messages pyWinhook passed on to ioHub: move, wheel, and left /
# right / middle button down, up and double click (low-level hooks never
# actually deliver the double click messages). X buttons and the horizontal
# wheel were dropped, and still are.
MOUSE_MESSAGES = frozenset(range(WM_MOUSEMOVE, WM_MOUSEWHEEL + 1))

VK_CAPITAL = 0x14
VK_NUMLOCK = 0x90
VK_SCROLL = 0x91
TOGGLE_KEYS = (VK_CAPITAL, VK_NUMLOCK, VK_SCROLL)


class KeyboardHookEvent:
    """A keyboard event read from the low-level keyboard hook.

    ``Window`` is the foreground window when the event happened.
    ``cap_state``, ``num_state`` and ``scroll_state`` are 1 if that lock is on
    after this event, else 0.
    """

    def __init__(self, msg, data, window, toggles):
        self.Message = msg
        self.KeyID = data.vkCode
        self.ScanCode = data.scanCode
        self.flags = data.flags
        self.Time = data.time
        self.Window = window or 0
        self.cap_state = toggles[VK_CAPITAL]
        self.num_state = toggles[VK_NUMLOCK]
        self.scroll_state = toggles[VK_SCROLL]

    @property
    def isPress(self):
        return self.Message in KEY_DOWN_MESSAGES


class MouseHookEvent:
    """A mouse event read from the low-level mouse hook.

    ``Position`` is in virtual-screen pixels, ``Window`` is the window under
    the cursor, and ``Wheel`` is +1 / -1 for a wheel event, else 0.
    """

    def __init__(self, msg, data, window):
        self.Message = msg
        self.Position = (data.pt.x, data.pt.y)
        self.Time = data.time
        self.flags = data.flags
        self.Window = window or 0
        wheel = 0
        if msg == WM_MOUSEWHEEL:
            # mouseData's high word holds the signed wheel delta
            delta = ctypes.c_short((data.mouseData >> 16) & 0xFFFF).value
            wheel = (delta > 0) - (delta < 0)
        self.Wheel = wheel


class HookManager:
    """Owns the low-level keyboard and mouse hooks of the ioHub server.

    ``hookKeyboard(callback)`` and ``hookMouse(callback)`` each start a pynput
    listener thread, which calls ``callback`` with a
    :class:`KeyboardHookEvent` or :class:`MouseHookEvent` for each event.
    ``stop()`` removes both hooks.
    """

    def __init__(self):
        self._keyboardListener = None
        self._mouseListener = None
        self._keyboardCallback = None
        self._mouseCallback = None
        # Lock key states, tracked here because GetKeyState only reflects the
        # state of the calling thread's input queue, which a hook thread does
        # not receive. Seeded when the keyboard hook is started, then only
        # changed on the keyboard listener thread.
        self._toggles = {vk: 0 for vk in TOGGLE_KEYS}
        self._togglesHeld = set()

    @property
    def keyboardHooked(self):
        return self._keyboardListener is not None

    @property
    def mouseHooked(self):
        return self._mouseListener is not None

    def hookKeyboard(self, callback):
        """Start reporting keyboard events to ``callback``."""
        if self._keyboardListener is not None:
            raise RuntimeError('The keyboard hook is already installed.')
        from pynput import keyboard

        for vk in TOGGLE_KEYS:
            self._toggles[vk] = _GetKeyState(vk) & 0x01
        self._togglesHeld.clear()
        self._keyboardCallback = callback
        listener = keyboard.Listener(
            win32_event_filter=self._keyboardFilter)
        listener.start()
        listener.wait()
        self._keyboardListener = listener

    def hookMouse(self, callback):
        """Start reporting mouse events to ``callback``."""
        if self._mouseListener is not None:
            raise RuntimeError('The mouse hook is already installed.')
        from pynput import mouse

        self._mouseCallback = callback
        listener = mouse.Listener(win32_event_filter=self._mouseFilter)
        listener.start()
        listener.wait()
        self._mouseListener = listener

    def stop(self, timeout=1.0):
        """Remove both hooks and wait for the listener threads to finish."""
        listeners = (self._keyboardListener, self._mouseListener)
        self._keyboardListener = self._mouseListener = None
        for listener in listeners:
            if listener is None:
                continue
            try:
                listener.stop()
                listener.join(timeout)
            except Exception:
                print2err('Error stopping ioHub input hook listener:')
                printExceptionDetailsToStdErr()

    def _updateToggles(self, msg, vk):
        # Windows flips a lock on key down; auto-repeat key downs do not flip
        # it again.
        if vk not in self._toggles:
            return
        if msg in KEY_DOWN_MESSAGES:
            if vk not in self._togglesHeld:
                self._togglesHeld.add(vk)
                self._toggles[vk] ^= 0x01
        else:
            self._togglesHeld.discard(vk)

    def _keyboardFilter(self, msg, data):
        # Runs on the keyboard listener thread, inside the hook procedure. An
        # exception escaping it would stop the pynput listener.
        try:
            if msg in KEY_MESSAGES:
                self._updateToggles(msg, data.vkCode)
                event = KeyboardHookEvent(
                    msg, data, _GetForegroundWindow(), self._toggles)
                self._keyboardCallback(event)
        except Exception:
            printExceptionDetailsToStdErr()
        # False: skip pynput's own processing; the event is still passed on.
        return False

    def _mouseFilter(self, msg, data):
        # Runs on the mouse listener thread; see _keyboardFilter.
        try:
            if msg in MOUSE_MESSAGES:
                event = MouseHookEvent(msg, data, _WindowFromPoint(data.pt))
                self._mouseCallback(event)
        except Exception:
            printExceptionDetailsToStdErr()
        return False
