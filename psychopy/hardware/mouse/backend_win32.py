#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Mouse backend which gets events system-wide from a low-level mouse hook
(Windows).

"""

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2025 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

__all__ = ['Win32MouseBackend']

import ctypes
import threading
from ctypes import wintypes

from psychopy.clock import getTime
from psychopy.hardware.mouse import (
    MOUSE_BUTTON_LEFT, MOUSE_BUTTON_MIDDLE, MOUSE_BUTTON_RIGHT,
    MOUSE_BUTTON_X1, MOUSE_BUTTON_X2)
from ._base import BaseMouseBackend

_user32 = ctypes.WinDLL('user32', use_last_error=True)
_kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

WH_MOUSE_LL = 14
HC_ACTION = 0
PM_NOREMOVE = 0x0000
WM_QUIT = 0x0012
WM_USER = 0x0400
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEWHEEL = 0x020A
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
WM_MOUSEHWHEEL = 0x020E
WHEEL_DELTA = 120
# positions in physical pixels, which is what the hook reports
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)

# messages the hook handles, with the kind of event and the button
_MESSAGES = {
    WM_MOUSEMOVE: ("move", None),
    WM_LBUTTONDOWN: ("press", MOUSE_BUTTON_LEFT),
    WM_LBUTTONUP: ("release", MOUSE_BUTTON_LEFT),
    WM_RBUTTONDOWN: ("press", MOUSE_BUTTON_RIGHT),
    WM_RBUTTONUP: ("release", MOUSE_BUTTON_RIGHT),
    WM_MBUTTONDOWN: ("press", MOUSE_BUTTON_MIDDLE),
    WM_MBUTTONUP: ("release", MOUSE_BUTTON_MIDDLE),
    WM_XBUTTONDOWN: ("press", None),
    WM_XBUTTONUP: ("release", None),
    WM_MOUSEWHEEL: ("scroll", None),
    WM_MOUSEHWHEEL: ("scroll", None)
}
# buttons for X button messages, by the high word of `mouseData`
_XBUTTONS = {
    1: MOUSE_BUTTON_X1,
    2: MOUSE_BUTTON_X2
}

LRESULT = ctypes.c_ssize_t
ULONG_PTR = ctypes.c_size_t


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ('pt', wintypes.POINT),
        ('mouseData', wintypes.DWORD),
        ('flags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', ULONG_PTR)
    ]


LowLevelMouseProc = ctypes.WINFUNCTYPE(
    LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

_user32.SetWindowsHookExW.argtypes = (
    ctypes.c_int, LowLevelMouseProc, wintypes.HINSTANCE, wintypes.DWORD)
_user32.SetWindowsHookExW.restype = wintypes.HHOOK
_user32.CallNextHookEx.argtypes = (
    wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
_user32.CallNextHookEx.restype = LRESULT
_user32.UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)
_user32.UnhookWindowsHookEx.restype = wintypes.BOOL
_user32.GetMessageW.argtypes = (
    ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT)
_user32.GetMessageW.restype = wintypes.BOOL
_user32.PeekMessageW.argtypes = (
    ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT,
    wintypes.UINT)
_user32.PeekMessageW.restype = wintypes.BOOL
_user32.PostThreadMessageW.argtypes = (
    wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
_user32.PostThreadMessageW.restype = wintypes.BOOL
_user32.GetClientRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
_user32.GetClientRect.restype = wintypes.BOOL
_user32.ClientToScreen.argtypes = (
    wintypes.HWND, ctypes.POINTER(wintypes.POINT))
_user32.ClientToScreen.restype = wintypes.BOOL
_user32.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)
_user32.GetCursorPos.restype = wintypes.BOOL
_user32.SetCursorPos.argtypes = (ctypes.c_int, ctypes.c_int)
_user32.SetCursorPos.restype = wintypes.BOOL
_kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
_kernel32.GetModuleHandleW.restype = wintypes.HMODULE
_kernel32.GetCurrentThreadId.restype = wintypes.DWORD

# only on Windows 10 (1607) and later
_setThreadDpiAwarenessContext = getattr(
    _user32, 'SetThreadDpiAwarenessContext', None)
if _setThreadDpiAwarenessContext is not None:
    _setThreadDpiAwarenessContext.argtypes = (ctypes.c_void_p,)
    _setThreadDpiAwarenessContext.restype = ctypes.c_void_p


class _PhysicalPixels:
    """Context manager making Windows give positions to this thread in physical
    pixels, like the hook does, whatever the DPI awareness of the process."""

    def __enter__(self):
        self._previous = None
        if _setThreadDpiAwarenessContext is not None:
            self._previous = _setThreadDpiAwarenessContext(
                DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)

    def __exit__(self, *args):
        if self._previous:
            _setThreadDpiAwarenessContext(self._previous)


class Win32MouseBackend(BaseMouseBackend):
    """Get mouse events system-wide from a low-level mouse hook (Windows),
    running on its own thread.

    Events are timestamped when the hook receives them, with
    `psychopy.clock.getTime()`, as the timestamps given by Windows are only in
    milliseconds. Positions are in screen coordinates (physical pixels), with
    the origin at the top-left of the main display.

    Notes
    -----
    * Windows waits for the hook before passing on each mouse event, so it only
      adds events to a buffer. Python can't run the hook while another thread
      holds the GIL though, so long calls which hold it may delay the cursor.

    """
    name = "win32"
    usesScreenCoords = True

    def __init__(self, device):
        BaseMouseBackend.__init__(self, device)
        # keep a reference to the callback, so it isn't garbage collected
        self._proc = LowLevelMouseProc(self._onEvent)
        self._hook = None
        self._threadId = None
        self._thread = None
        self._error = None
        self._ready = threading.Event()

    def start(self):
        if self._running:
            return
        self._error = None
        self._running = True
        self._ready.clear()
        self._thread = threading.Thread(
            target=self._run, name="Win32MouseBackend", daemon=True)
        self._thread.start()
        self._ready.wait(1.0)
        if self._hook is None:
            self._running = False
            raise RuntimeError(
                f"Could not install a low-level mouse hook: {self._error}")

    def _run(self):
        """Install the hook and receive events until stopped, on the backend's
        thread."""
        msg = wintypes.MSG()
        # make sure the thread has a message queue, so `stop` can post to it
        _user32.PeekMessageW(
            ctypes.byref(msg), None, WM_USER, WM_USER, PM_NOREMOVE)
        self._threadId = _kernel32.GetCurrentThreadId()
        hook = _user32.SetWindowsHookExW(
            WH_MOUSE_LL, self._proc, _kernel32.GetModuleHandleW(None), 0)
        if not hook:
            self._error = ctypes.WinError(ctypes.get_last_error())
            self._ready.set()
            return
        self._hook = hook
        self._ready.set()
        # the hook is called while the thread waits for messages
        while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            pass
        _user32.UnhookWindowsHookEx(hook)
        self._hook = None

    def stop(self):
        if not self._running:
            return
        self._running = False
        if self._threadId is not None:
            _user32.PostThreadMessageW(self._threadId, WM_QUIT, 0, 0)
        if self._thread is not None:
            self._thread.join(1.0)
        self._thread = None
        self._threadId = None

    def _onEvent(self, nCode, wParam, lParam):
        """Called by Windows for each mouse event, on the backend's thread.
        Windows waits for this before moving on, so it must be quick."""
        try:
            if nCode == HC_ACTION and wParam in _MESSAGES:
                t = getTime()
                info = ctypes.cast(
                    lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                kind, button = _MESSAGES[wParam]
                highWord = (info.mouseData >> 16) & 0xFFFF
                scroll = None
                if wParam in (WM_XBUTTONDOWN, WM_XBUTTONUP):
                    button = _XBUTTONS.get(highWord)
                elif wParam == WM_MOUSEWHEEL:
                    scroll = (0.0, ctypes.c_short(highWord).value / WHEEL_DELTA)
                elif wParam == WM_MOUSEHWHEEL:
                    scroll = (ctypes.c_short(highWord).value / WHEEL_DELTA, 0.0)
                if kind not in ("press", "release") or button is not None:
                    self.push(
                        kind, t, button=button,
                        screenPos=(info.pt.x, info.pt.y), scroll=scroll,
                        osTime=info.time)
        except Exception:
            # whatever happens, the event must still reach other apps
            pass

        return _user32.CallNextHookEx(None, nCode, wParam, lParam)

    def getWindowRect(self, win):
        hwnd = getattr(win, '_hw_handle', None)
        if not hwnd:
            return None
        rect = wintypes.RECT()
        origin = wintypes.POINT(0, 0)
        with _PhysicalPixels():
            if not _user32.GetClientRect(hwnd, ctypes.byref(rect)):
                return None
            if not _user32.ClientToScreen(hwnd, ctypes.byref(origin)):
                return None

        return origin.x, origin.y, rect.right - rect.left, rect.bottom - rect.top

    def getCursorPos(self):
        point = wintypes.POINT()
        with _PhysicalPixels():
            if not _user32.GetCursorPos(ctypes.byref(point)):
                return None

        return point.x, point.y

    def setCursorPos(self, pos):
        with _PhysicalPixels():
            return bool(_user32.SetCursorPos(
                int(round(pos[0])), int(round(pos[1]))))


if __name__ == "__main__":
    pass
