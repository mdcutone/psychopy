#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Classes and functions for interfacing with pointing devices (i.e. mice).

"""

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2025 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

__all__ = [
    'Mouse',
    'MouseDevice',
    'MouseResponse',
    'MOUSE_BUTTON_LEFT',
    'MOUSE_BUTTON_MIDDLE',
    'MOUSE_BUTTON_RIGHT',
    'MOUSE_BUTTON_X1',
    'MOUSE_BUTTON_X2'
]

import importlib.metadata
import sys
import threading
import weakref
from collections import deque

import numpy as np

from psychopy import core, logging
from psychopy.clock import getTime
from psychopy.hardware.base import BaseResponseDevice, BaseResponse
from psychopy.hardware.manager import DeviceManager
from psychopy.tools.attributetools import AttributeGetSetMixin
from psychopy.tools.monitorunittools import convertToPix, pix2cm, pix2deg


# mouse button indices
MOUSE_BUTTON_LEFT = 0
MOUSE_BUTTON_MIDDLE = 1
MOUSE_BUTTON_RIGHT = 2
MOUSE_BUTTON_X1 = 3  # usually 'back'
MOUSE_BUTTON_X2 = 4  # usually 'forward'
MOUSE_BUTTON_COUNT = 5

buttonNames = {
    'left': MOUSE_BUTTON_LEFT,
    'middle': MOUSE_BUTTON_MIDDLE,
    'right': MOUSE_BUTTON_RIGHT,
    'x1': MOUSE_BUTTON_X1,
    'x2': MOUSE_BUTTON_X2
}
# button names by index
_buttonLabels = {index: name for name, index in buttonNames.items()}

# the cursor counts as moving for this long after it last moved, in seconds
MOTION_TIMEOUT = 0.05
# how often system backends check where windows are on screen, in seconds
_RECT_REFRESH_INTERVAL = 0.5

# backend used on each platform for `backend='system'`
_systemBackends = {
    'darwin': "darwin",
    'win32': "win32",
    'linux': "xlib"
}


def _buttonIndex(button):
    """Get the index of a button from its name or index."""
    if isinstance(button, str):
        return buttonNames[button]

    return int(button)


def _openWindows():
    """Get the windows which are open, from `psychopy.core.openWindows`."""
    wins = []
    for ref in core.openWindows:
        win = ref() if callable(ref) else ref
        if win is not None and not getattr(win, '_closed', False):
            wins.append(win)

    return wins


def _cmToDegFlat(cm, dist):
    """Convert positions in cm to degrees, correcting for a flat screen. This is
    the inverse of `deg2cm(..., correctFlat=True)`, which `cm2deg` isn't.
    """
    xy = np.asarray(cm, dtype=float) / dist
    x, y = xy[..., 0], xy[..., 1]
    # `deg2cm` gives x = u * sqrt(1 + v ** 2) and y = v * sqrt(1 + u ** 2) for
    # u = tan(degX) and v = tan(degY), solve for u ** 2 and v ** 2
    diff = x ** 2 - y ** 2
    vSq = (-(1.0 + diff) + np.sqrt((1.0 + diff) ** 2 + 4.0 * y ** 2)) / 2.0
    uSq = vSq + diff
    degs = np.empty_like(xy)
    degs[..., 0] = np.degrees(np.arctan(np.sign(x) * np.sqrt(np.abs(uSq))))
    degs[..., 1] = np.degrees(np.arctan(np.sign(y) * np.sqrt(np.abs(vSq))))

    return degs


def _pixToUnits(pos, win):
    """Convert positions in 'pix' coordinates of a window (framebuffer pixels
    from its centre) to the units of the window. This is the inverse of
    `_unitsToPix`.

    Parameters
    ----------
    pos : ArrayLike
        Position `(x, y)`, or array of positions, in 'pix' coordinates.
    win : :class:`~psychopy.visual.Window` or None
        Window to convert to the units of. If `None`, `pos` is returned as is.

    Returns
    -------
    ndarray
        Position(s) in the units of `win`.

    """
    pos = np.asarray(pos, dtype=float)
    if win is None:
        return pos

    # with `useRetina`, stimuli treat 'pix' as points rather than framebuffer
    # pixels, so convert to the same 'pix' they use
    pix = pos / win.pixScaleFactor
    units = win.units
    if units in ('pix', 'pixels'):
        return pix
    elif units == 'norm':
        return pos * 2.0 / win.size
    elif units == 'height':
        return pos / float(win.size[1])
    elif units == 'cm':
        return pix2cm(pix, win.monitor)
    elif units in ('deg', 'degs'):
        return pix2deg(pix, win.monitor)
    elif units in ('degFlat', 'degFlatPos'):
        return _cmToDegFlat(pix2cm(pix, win.monitor), win.monitor.getDistance())

    raise ValueError(
        f"Can't convert mouse positions to units '{units}' of window "
        f"{win.name}.")


def _unitsToPix(pos, win):
    """Convert positions in the units of a window to its 'pix' coordinates
    (framebuffer pixels from its centre). This is the inverse of `_pixToUnits`.

    Parameters
    ----------
    pos : ArrayLike
        Position `(x, y)`, or array of positions, in the units of `win`.
    win : :class:`~psychopy.visual.Window` or None
        Window whose units to convert from. If `None`, `pos` is returned as is.

    Returns
    -------
    ndarray
        Position(s) in 'pix' coordinates.

    """
    pos = np.asarray(pos, dtype=float)
    if win is None:
        return pos

    pix = convertToPix(np.zeros_like(pos), pos, win.units, win)

    return np.asarray(pix, dtype=float) * win.pixScaleFactor


def _screenToPix(screenPos, win, rect):
    """Convert a position in screen coordinates to the 'pix' coordinates of a
    window, given where the window is on screen (see
    `BaseMouseBackend.getWindowRect`).
    """
    left, top, width, height = rect
    scale = np.asarray(win.frameBufferSize, dtype=float) / (width, height)
    # screen coordinates have y increasing downwards, unlike 'pix'
    bufferPos = np.array(
        (screenPos[0] - left, top + height - screenPos[1]), dtype=float) * scale

    return bufferPos - np.asarray(win.size, dtype=float) / 2.0


def _pixToScreen(pos, win, rect):
    """Convert a position in the 'pix' coordinates of a window to screen
    coordinates. This is the inverse of `_screenToPix`.
    """
    left, top, width, height = rect
    scale = (width, height) / np.asarray(win.frameBufferSize, dtype=float)
    bufferPos = np.asarray(pos, dtype=float) + \
        np.asarray(win.size, dtype=float) / 2.0
    x, y = bufferPos * scale

    return left + x, top + height - y


def _rectContains(rect, screenPos):
    """Check whether a position in screen coordinates is inside a window."""
    left, top, width, height = rect

    return left <= screenPos[0] < left + width and \
        top <= screenPos[1] < top + height


class MouseResponse(BaseResponse):
    """A press of a mouse button, completed when the button is released.

    Parameters
    ----------
    t : float
        Time the button was pressed, on the clock of the device.
    value : str
        Name of the button, one of 'left', 'middle', 'right', 'x1' or 'x2'.
    pos : ArrayLike or None
        Position of the cursor when the button was pressed, in the units of
        the window the device gives positions in.
    screenPos : ArrayLike or None
        Position of the cursor in screen coordinates. Only given by system
        backends.
    device : MouseDevice or None
        Device the response came from.

    Attributes
    ----------
    duration : float or None
        How long the button was held down for in seconds, `None` until it is
        released.
    releasePos : ndarray or None
        Position of the cursor when the button was released, `None` until it is
        released.

    """
    fields = ["t", "value", "pos", "duration"]

    def __init__(self, t, value, pos=None, screenPos=None, device=None):
        BaseResponse.__init__(self, t=t, value=value, device=device)
        self.pos = pos
        self.screenPos = screenPos
        # start off pressed (not released)
        self.duration = None
        self.releasePos = None

    @property
    def button(self):
        """Name of the button which was pressed (`str`)."""
        return self.value

    def __eq__(self, other):
        if isinstance(other, MouseResponse):
            return self.value == other.value
        else:
            return self.value == other

    def __ne__(self, other):
        return not self.__eq__(other)


class MouseDevice(BaseResponseDevice, aliases=["mouse"]):
    """A mouse (or other pointing device) as a response device.

    There is only one system pointer, so `MouseDevice` is a singleton; creating
    it again gives the same object, with any settings given applied to it.
    Positions are given in the units of a window (see `win`), which can be any
    window that is open.

    Events come from a backend, either:

    * ``'window'``: the backends of PsychoPy windows (pyglet or GLFW). Events
      are only received over PsychoPy windows, and are timestamped when the
      windows dispatch them, usually once per frame.
    * ``'system'``: a hook into the input events of the operating system,
      running on its own thread (a Quartz event tap on macOS, a low-level mouse
      hook on Windows or the RECORD extension of X11 on Linux). Events are
      received wherever the cursor is, with or without a window, and are
      timestamped when they happen. If the hook can't be started (e.g. under
      Wayland, or without permission to monitor input on macOS) the 'window'
      backend is used instead.

    Button presses are stored as `MouseResponse` objects (see `getClicks`),
    with their duration filled in when the button is released. Motion and
    scrolling update the state of the device (see `getPos` and `getWheelRel`)
    and are kept in a history (see `getMotion` and `getScrolls`), rather than
    being responses, as there are far too many of them.

    Parameters
    ----------
    backend : str or None
        Backend to get events from, ``'window'`` or ``'system'``, or the name of
        a backend in `MouseDevice.backends`. If `None`, ``'window'``.
    clock : :class:`~psychopy.clock.Clock` or None
        Clock to give times on. If `None`, a new clock is made.
    bufferSize : int or None
        Maximum number of events to hold until they are dispatched. If `None`,
        10000.
    waitForStart : bool
        If `True`, no events are received until `start()` is called.
    muteOutsidePsychopy : bool or None
        If `True`, presses and scrolling while the cursor isn't over a PsychoPy
        window are ignored (the position and button states are still updated).
        Only system backends receive these events. If `None`, `True`.
    historySize : int or None
        Maximum number of motion and scroll events to keep. If `None`, 10000.

    Settings given as `None` when the device already exists are left as they
    are.

    """
    responseClass = MouseResponse
    # there is only one system pointer, so this is a singleton
    _instance = None
    # known backends
    backends = {
        'window': importlib.metadata.EntryPoint(
            name="window",
            value="psychopy.hardware.mouse.backend_window:WindowMouseBackend",
            group="psychopy.hardware.mouse.backends"
        ),
        'darwin': importlib.metadata.EntryPoint(
            name="darwin",
            value="psychopy.hardware.mouse.backend_darwin:QuartzMouseBackend",
            group="psychopy.hardware.mouse.backends"
        ),
        'win32': importlib.metadata.EntryPoint(
            name="win32",
            value="psychopy.hardware.mouse.backend_win32:Win32MouseBackend",
            group="psychopy.hardware.mouse.backends"
        ),
        'xlib': importlib.metadata.EntryPoint(
            name="xlib",
            value="psychopy.hardware.mouse.backend_xlib:XlibMouseBackend",
            group="psychopy.hardware.mouse.backends"
        )
    }

    def __new__(cls, *args, **kwargs):
        # instantiate, if not already
        if cls._instance is None:
            cls._instance = super(MouseDevice, cls).__new__(cls)

        return cls._instance

    def __init__(self, backend=None, clock=None, bufferSize=None,
                 waitForStart=False, muteOutsidePsychopy=None,
                 historySize=None):
        # already initialised, so just apply settings given to the device
        if getattr(self, '_initialized', False):
            self.configure(
                backend=backend, clock=clock, bufferSize=bufferSize,
                muteOutsidePsychopy=muteOutsidePsychopy,
                historySize=historySize)
            if not waitForStart:
                self.start()
            return
        # defaults for settings not given
        if backend is None:
            backend = "window"
        if bufferSize is None:
            bufferSize = 10000
        if muteOutsidePsychopy is None:
            muteOutsidePsychopy = True
        if historySize is None:
            historySize = 10000

        BaseResponseDevice.__init__(self)
        # events can be dispatched from both the main and listener threads
        self._lock = threading.RLock()
        self.clock = clock if clock is not None else core.Clock()
        self.buffer = deque(maxlen=bufferSize)
        self._bufferSize = bufferSize
        # history of motion as (t, pos, window), and scrolling as (t, dx, dy)
        self.motion = deque(maxlen=historySize)
        self.scrolls = deque(maxlen=historySize)
        self.muteOutsidePsychopy = muteOutsidePsychopy
        self.autoFocus = True
        # windows positions are given relative to
        self._windows = []
        self._winRef = None
        self._windowRects = {}
        self._rectsUpdated = -np.inf
        # cursor state, positions are in 'pix' of the window they were in
        self._pos = None
        self._posWinRef = None
        self._prevPos = None
        self._prevPosWinRef = None
        self._screenPos = None
        self._hovering = False
        self._lastMotion = None
        self._prevMotion = None
        self._initTime = getTime()
        # button state, with times on the `getTime()` time base
        self.buttons = np.zeros((MOUSE_BUTTON_COUNT,), dtype=bool)
        self._pressedTimes = np.full((MOUSE_BUTTON_COUNT,), np.nan)
        self._releasedTimes = np.full((MOUSE_BUTTON_COUNT,), np.nan)
        self._pressedPos = np.full((MOUSE_BUTTON_COUNT, 2), np.nan)
        self._releasedPos = np.full((MOUSE_BUTTON_COUNT, 2), np.nan)
        self._clickResetTimes = np.full((MOUSE_BUTTON_COUNT,), self._initTime)
        # presses awaiting release, by button
        self._openPresses = {}
        # scroll wheel travel since `getWheelRel` was last called
        self._wheel = np.zeros((2,), dtype=float)
        # cursor appearance
        self._visible = True
        self._exclusive = False
        # get backend
        self.backend = None
        self._requestedBackend = None
        self.started = False
        self._initialized = True
        self.setBackend(backend)
        # start listening for events (unless told not to)
        if not waitForStart:
            self.start()

    def configure(self, backend=None, clock=None, bufferSize=None,
                  muteOutsidePsychopy=None, historySize=None):
        """Change the settings of the device. Settings given as `None` are left
        as they are, see `MouseDevice` for the rest.
        """
        if clock is not None:
            self.clock = clock
        if bufferSize is not None:
            self.bufferSize = bufferSize
        if historySize is not None:
            self.historySize = historySize
        if muteOutsidePsychopy is not None:
            self.muteOutsidePsychopy = muteOutsidePsychopy
        if backend is not None and backend != self._requestedBackend:
            self.setBackend(backend)

    @property
    def bufferSize(self):
        """Maximum number of events to hold until they are dispatched
        (`int`)."""
        return self._bufferSize

    @bufferSize.setter
    def bufferSize(self, value):
        if value == self._bufferSize:
            return
        self._bufferSize = value
        # new buffer, keeping events not yet dispatched
        self.buffer = deque(self.buffer, maxlen=value)

    @property
    def historySize(self):
        """Maximum number of motion and scroll events to keep (`int`)."""
        return self.motion.maxlen

    @historySize.setter
    def historySize(self, value):
        if value == self.motion.maxlen:
            return
        self.motion = deque(self.motion, maxlen=value)
        self.scrolls = deque(self.scrolls, maxlen=value)

    # --------------------------------------------------------------------------
    # Backends
    #

    @classmethod
    def _resolveBackendName(cls, backend):
        """Get the name of the backend in `backends` to use for a requested
        backend, which may be 'system'."""
        if backend == "system":
            platform = "linux" if sys.platform.startswith("linux") \
                else sys.platform
            if platform not in _systemBackends:
                raise ValueError(
                    f"No system mouse backend is available on {sys.platform}.")
            backend = _systemBackends[platform]
        if backend not in cls.backends:
            raise ValueError(
                f"Unknown mouse backend '{backend}', known backends are: "
                f"{['system'] + list(cls.backends)}")

        return backend

    @classmethod
    def getBackends(cls):
        """Get all known mouse backends (by name).

        Returns
        -------
        dict[str:importlib.metadata.EntryPoint]
            Dict mapping backend names to entry points, call `.load()` on an
            entry point to import its class.

        """
        return cls.backends

    def getBackend(self):
        """Get the name of the backend in use.

        Returns
        -------
        str or None
            Name of the backend, e.g. 'window' or 'darwin'.

        """
        if self.backend is None:
            return None

        return self.backend.name

    def setBackend(self, backend):
        """Change the backend events come from. If the device has been started,
        it is restarted with the new backend.

        Parameters
        ----------
        backend : str
            Backend to use, ``'window'`` or ``'system'``, or the name of a
            backend in `MouseDevice.backends`.

        """
        wasStarted = self.started
        if wasStarted:
            self.stop()
        self._requestedBackend = backend
        name = self._resolveBackendName(backend)
        try:
            backendClass = self.backends[name].load()
        except ImportError as err:
            if name == "window":
                raise
            logging.warning(
                f"Could not load the '{name}' mouse backend, so using 'window' "
                f"instead: {err}")
            backendClass = self.backends['window'].load()
        self.backend = backendClass(self)
        # screen coordinates from the last backend may not mean anything now
        self._screenPos = None
        self._windowRects = {}
        if wasStarted:
            self.start()

    def start(self):
        """Start listening for mouse events."""
        if self.started:
            return
        # report positions relative to windows which are already open
        for win in _openWindows():
            self.attachWindow(win)
        try:
            self.backend.start()
        except Exception as err:
            if self.backend.name == "window":
                raise
            logging.warning(
                f"Could not start the '{self.backend.name}' mouse backend, so "
                f"using 'window' instead: {err}")
            self.backend = self.backends['window'].load()(self)
            self.backend.start()
        self._updateWindowRects(force=True)
        self.started = True

    def stop(self):
        """Stop listening for mouse events."""
        if self.backend is not None:
            self.backend.stop()
        self.started = False

    def close(self):
        """Stop listening for mouse events. Creating `MouseDevice` again starts
        it again."""
        self.stop()

    # --------------------------------------------------------------------------
    # DeviceManager
    #

    def isSameDevice(self, other):
        """There is only one system pointer, so any `MouseDevice` is the same
        device. A profile is for this device if it's for the same backend, or
        doesn't give one.

        Parameters
        ----------
        other : MouseDevice or dict
            Device or profile to compare against.

        Returns
        -------
        bool
            `True` if `other` represents this device.

        """
        if isinstance(other, MouseDevice):
            return True
        if not isinstance(other, dict):
            return False
        backend = other.get('backend')
        if backend is None:
            return True
        try:
            return self._resolveBackendName(backend) == self.getBackend()
        except ValueError:
            return False

    @staticmethod
    def getAvailableDevices():
        # the system pointer is available with each kind of backend
        profiles = [{
            'deviceName': "Mouse",
            'deviceClass': "psychopy.hardware.mouse.MouseDevice",
            'backend': "window"
        }]
        try:
            MouseDevice._resolveBackendName("system")
        except ValueError:
            pass
        else:
            profiles.append({
                'deviceName': "Mouse (system)",
                'deviceClass': "psychopy.hardware.mouse.MouseDevice",
                'backend': "system"
            })

        return profiles

    # --------------------------------------------------------------------------
    # Windows
    #

    @property
    def windows(self):
        """Open windows the device reports positions in (`list`). Windows are
        added as they are opened."""
        wins = []
        for ref in self._windows:
            win = ref()
            if win is not None and not getattr(win, '_closed', False):
                wins.append(win)

        return wins

    def attachWindow(self, win):
        """Report positions in a window. Windows are attached automatically
        when they are opened.

        Parameters
        ----------
        win : :class:`~psychopy.visual.Window`
            Window to attach.

        """
        with self._lock:
            if any(ref() is win for ref in self._windows):
                return
            self._windows.append(weakref.ref(win))
            self._updateWindowRects(force=True)

    def detachWindow(self, win):
        """Stop reporting positions in a window. Windows are detached
        automatically when they are closed.

        Parameters
        ----------
        win : :class:`~psychopy.visual.Window`
            Window to detach.

        """
        with self._lock:
            self._windows = [
                ref for ref in self._windows
                if ref() is not None and ref() is not win]
            self._windowRects.pop(id(win), None)
            if self._winRef is not None and self._winRef() is win:
                self._winRef = None

    @property
    def win(self):
        """Window positions are given in the units of
        (:class:`~psychopy.visual.Window` or `None`). With `autoFocus`, this is
        the window the cursor was last over. If not set, the first window which
        is open is used.
        """
        win = self._winRef() if self._winRef is not None else None
        if win is None or getattr(win, '_closed', False):
            wins = self.windows
            win = wins[0] if wins else None

        return win

    @win.setter
    def win(self, value):
        if value is None:
            self._winRef = None
            return
        self.attachWindow(value)
        self._winRef = weakref.ref(value)

    def _updateWindowRects(self, force=False):
        """Find where windows are on screen, which system backends need to map
        the cursor to windows. Unless `force` is `True`, this is only done if it
        hasn't been in the last `_RECT_REFRESH_INTERVAL` seconds."""
        if self.backend is None or not self.backend.usesScreenCoords:
            return
        now = getTime()
        if not force and now - self._rectsUpdated < _RECT_REFRESH_INTERVAL:
            return
        with self._lock:
            self._rectsUpdated = now
            rects = {}
            for win in self.windows:
                try:
                    rect = self.backend.getWindowRect(win)
                except Exception as err:
                    logging.debug(f"Could not find window {win.name}: {err}")
                    rect = None
                if rect is not None:
                    rects[id(win)] = rect
            self._windowRects = rects

    def _locate(self, screenPos):
        """Find the window a position in screen coordinates is over.

        Returns
        -------
        tuple
            The window the position is over (`None` if it isn't over one), the
            window to give the position in, and the position in 'pix'
            coordinates of that window (`None` if unknown).

        """
        self._updateWindowRects()
        hit = None
        for win in self.windows:
            rect = self._windowRects.get(id(win))
            if rect is not None and _rectContains(rect, screenPos):
                hit = win
                break
        target = hit if hit is not None and self.autoFocus else self.win
        pos = None
        if target is not None:
            rect = self._windowRects.get(id(target))
            if rect is not None:
                pos = _screenToPix(screenPos, target, rect)

        return hit, target, pos

    def _pumpWindowEvents(self):
        """Have windows dispatch their pending events, so the 'window' backend
        receives mouse events without waiting for the windows to flip. Only
        done from the main thread, which owns the windows."""
        if self.backend is None or self.backend.usesScreenCoords:
            return
        if threading.current_thread() is not threading.main_thread():
            return
        pumped = set()
        for win in self.windows:
            # backends dispatch events for all of their windows at once
            backendType = type(win.backend)
            if backendType in pumped:
                continue
            pumped.add(backendType)
            try:
                win.backend.dispatchEvents()
            except Exception:
                pass

    # --------------------------------------------------------------------------
    # Event handling
    #

    def dispatchMessages(self):
        """Process events received from the backend, storing button presses as
        responses and updating the state of the mouse."""
        with self._lock:
            while self.buffer:
                self._handleEvent(self.buffer.popleft())

    def parseMessage(self, message):
        """Make a response from a raw 'press' event, which must have a
        position in 'pix' coordinates of its window."""
        pos = message['pos']
        if pos is not None:
            pos = _pixToUnits(pos, message['win'])

        return MouseResponse(
            t=message['t'] - self.clock.getLastResetTime(),
            value=_buttonLabels[message['button']],
            pos=pos,
            screenPos=message['screenPos'],
            device=self
        )

    def _update(self):
        """Receive any pending events, before querying the state."""
        self._pumpWindowEvents()
        self.dispatchMessages()

    def _handleEvent(self, evt):
        """Update the state of the mouse from a raw event."""
        kind, t = evt['type'], evt['t']
        # find which window the event is in and where
        if evt['screenPos'] is not None:
            screenPos = np.asarray(evt['screenPos'], dtype=float)
            hit, win, pos = self._locate(screenPos)
            inside = hit is not None
            # system backends get events from everywhere, so ignore presses and
            # scrolling outside of PsychoPy if requested
            muted = self.muteOutsidePsychopy and not inside
        else:
            screenPos = None
            win, pos = evt['win'], evt['pos']
            if pos is not None:
                pos = np.asarray(pos, dtype=float)
            # without auto focus, positions are only known in the chosen window
            if not self.autoFocus and win is not self.win:
                pos = None
            inside = kind != "leave"
            if inside and pos is not None and win is not None:
                inside = bool(np.all(np.abs(pos) <= np.asarray(win.size) / 2.0))
            hit = win if inside else None
            # windows only get events meant for them, even with the cursor
            # outside (e.g. while dragging)
            muted = False
        self._hovering = inside
        if self.autoFocus and hit is not None:
            self._winRef = weakref.ref(hit)
        # update position
        self._move(t, pos, win, screenPos)

        if kind == "press":
            button = evt['button']
            self.buttons[button] = True
            self._pressedTimes[button] = t
            self._pressedPos[button] = pos if pos is not None else np.nan
            if not muted:
                resp = self.parseMessage(dict(evt, pos=pos, win=win))
                self._openPresses[button] = resp
                # already muted as needed, so don't check which app is in focus
                self.receiveMessage(resp, muteOutsidePsychopy=False)
        elif kind == "release":
            button = evt['button']
            self.buttons[button] = False
            self._releasedTimes[button] = t
            self._releasedPos[button] = pos if pos is not None else np.nan
            # complete the press this releases, even if it was muted
            resp = self._openPresses.pop(button, None)
            if resp is not None:
                resp.duration = t - self._pressedTimes[button]
                if pos is not None:
                    resp.releasePos = _pixToUnits(pos, win)
        elif kind == "scroll" and not muted:
            dx, dy = evt['scroll']
            self._wheel += (dx, dy)
            self.scrolls.append((t, dx, dy))

    def _move(self, t, pos, win, screenPos):
        """Record the cursor being at a position, if it has moved."""
        moved = False
        if screenPos is not None:
            moved = self._screenPos is None or \
                not np.array_equal(screenPos, self._screenPos)
            self._screenPos = screenPos
        if pos is not None:
            posWin = self._posWinRef() if self._posWinRef is not None else None
            if self._pos is None or posWin is not win or \
                    not np.array_equal(pos, self._pos):
                moved = True
                self._prevPos, self._prevPosWinRef = \
                    self._pos, self._posWinRef
                self._pos = pos
                self._posWinRef = weakref.ref(win) if win is not None else None
                self.motion.append((t, pos, self._posWinRef))
        if moved:
            self._prevMotion, self._lastMotion = self._lastMotion, t

    def _getPix(self, win):
        """Get the position of the cursor in 'pix' coordinates of a window."""
        # system backends know where the cursor is relative to any window
        if self._screenPos is not None and win is not None:
            rect = self._windowRects.get(id(win))
            if rect is not None:
                return _screenToPix(self._screenPos, win, rect)
        posWin = self._posWinRef() if self._posWinRef is not None else None
        if self._pos is not None and posWin is win:
            return self._pos
        # nothing received yet, so ask where the cursor is
        if self.backend.usesScreenCoords:
            screenPos = self.backend.getCursorPos()
            if screenPos is not None and win is not None:
                self._updateWindowRects()
                rect = self._windowRects.get(id(win))
                if rect is not None:
                    return _screenToPix(screenPos, win, rect)
        elif win is not None:
            try:
                return np.asarray(win.backend.getMousePos(), dtype=float)
            except Exception:
                pass

        return np.zeros((2,), dtype=float)

    # --------------------------------------------------------------------------
    # Position
    #

    def getPos(self):
        """Get the position of the cursor.

        Returns
        -------
        ndarray
            Position `(x, y)` in the units of `win`.

        """
        self._update()
        win = self.win

        return _pixToUnits(self._getPix(win), win)

    def getPrevPos(self):
        """Get the position of the cursor before it last moved.

        Returns
        -------
        ndarray
            Position `(x, y)` in the units of `win`.

        """
        self._update()
        win = self.win
        prevWin = self._prevPosWinRef() \
            if self._prevPosWinRef is not None else None
        if self._prevPos is None or prevWin is not win:
            return _pixToUnits(self._getPix(win), win)

        return _pixToUnits(self._prevPos, win)

    def getScreenPos(self):
        """Get the position of the cursor in screen coordinates. Only system
        backends know this.

        Returns
        -------
        ndarray or None
            Position `(x, y)` in screen coordinates, or `None` if unknown.

        """
        self._update()
        if self._screenPos is not None:
            return self._screenPos.copy()
        screenPos = self.backend.getCursorPos()
        if screenPos is None:
            return None

        return np.asarray(screenPos, dtype=float)

    def setPos(self, pos):
        """Move the cursor.

        The cursor is moved to the nearest position the operating system
        supports, so `getPos()` may differ slightly from `pos`.

        Parameters
        ----------
        pos : ArrayLike
            Position `(x, y)` in the units of `win`. If there is no window,
            system backends take a position in screen coordinates.

        """
        win = self.win
        if self.backend.usesScreenCoords:
            if win is None:
                screenPos = tuple(pos)
            else:
                self._updateWindowRects(force=True)
                rect = self._windowRects.get(id(win))
                screenPos = None if rect is None else \
                    _pixToScreen(_unitsToPix(pos, win), win, rect)
            if screenPos is not None and self.backend.setCursorPos(screenPos):
                # moving the cursor doesn't always make an event, so add one
                self.backend.push("move", getTime(), screenPos=screenPos)
                return
        if win is None:
            logging.error("Could not set the mouse position, no window is open.")
            return
        win.backend.setMousePos(_unitsToPix(pos, win))
        self.backend.push(
            "move", getTime(), pos=win.backend.getMousePos(), win=win)

    def getVelocity(self):
        """Get the velocity of the cursor between the last two positions it
        moved to.

        Returns
        -------
        ndarray
            Velocity `(vx, vy)` in units of `win` per second, which is zero if
            the cursor isn't moving.

        """
        self._update()
        win = self.win
        posWin = self._posWinRef() if self._posWinRef is not None else None
        prevWin = self._prevPosWinRef() \
            if self._prevPosWinRef is not None else None
        if not self.isMoving or self._prevPos is None or \
                posWin is not win or prevWin is not win or \
                self._prevMotion is None:
            return np.zeros((2,), dtype=float)
        dt = self._lastMotion - self._prevMotion
        if dt <= 0:
            return np.zeros((2,), dtype=float)

        return (_pixToUnits(self._pos, win) -
                _pixToUnits(self._prevPos, win)) / dt

    @property
    def isMoving(self):
        """`True` if the cursor has moved in the last `MOTION_TIMEOUT` seconds
        (`bool`)."""
        self._update()
        return self._lastMotion is not None and \
            getTime() - self._lastMotion < MOTION_TIMEOUT

    @property
    def isHovering(self):
        """`True` if the cursor is over a PsychoPy window (`bool`)."""
        self._update()
        return self._hovering

    def getMoveTime(self):
        """Get the time since the cursor last moved.

        Returns
        -------
        float
            Time in seconds since the cursor last moved, or since the device was
            created if it hasn't moved.

        """
        self._update()
        last = self._lastMotion if self._lastMotion is not None \
            else self._initTime

        return getTime() - last

    def getMotion(self, clear=True):
        """Get the positions the cursor has moved through.

        Parameters
        ----------
        clear : bool
            If `True`, the positions returned aren't returned again.

        Returns
        -------
        ndarray
            Array with a row `(t, x, y)` for each position, where `t` is the
            time on `clock` and `(x, y)` are in the units of the window the
            cursor was in.

        """
        self._update()
        tReset = self.clock.getLastResetTime()
        rows = []
        for t, pos, winRef in self.motion:
            win = winRef() if winRef is not None else None
            x, y = _pixToUnits(pos, win)
            rows.append((t - tReset, x, y))
        if clear:
            self.motion.clear()

        return np.array(rows, dtype=float).reshape((-1, 3))

    # --------------------------------------------------------------------------
    # Buttons
    #

    def isPressed(self, button):
        """Check whether a button is pressed.

        Parameters
        ----------
        button : str or int
            Name of the button (e.g. 'left') or its index (`MOUSE_BUTTON_*`).

        Returns
        -------
        bool
            `True` if the button is pressed.

        """
        self._update()
        return bool(self.buttons[_buttonIndex(button)])

    def getPressed(self, getTime=False):
        """Get whether the left, middle and right buttons are pressed, like
        `psychopy.event.Mouse.getPressed`.

        Parameters
        ----------
        getTime : bool
            If `True`, also give the time each button was last pressed since
            `clickReset` was last called for it.

        Returns
        -------
        list or tuple
            List of three `bool` for whether the left, middle and right buttons
            are pressed. With `getTime`, a tuple of this and a list of three
            times in seconds, which are 0 for buttons which haven't been pressed
            since `clickReset`.

        """
        self._update()
        pressed = [bool(state) for state in self.buttons[:3]]
        if not getTime:
            return pressed
        times = []
        for tPressed, tReset in zip(self._pressedTimes[:3],
                                    self._clickResetTimes[:3]):
            if np.isnan(tPressed) or tPressed < tReset:
                times.append(0.0)
            else:
                times.append(float(tPressed - tReset))

        return pressed, times

    def clickReset(self, buttons=(0, 1, 2)):
        """Reset the times `getPressed(getTime=True)` gives for buttons, so they
        are relative to now.

        Parameters
        ----------
        buttons : list
            Buttons to reset, as names or indices.

        """
        now = getTime()
        for button in buttons:
            self._clickResetTimes[_buttonIndex(button)] = now

    def getClicks(self, buttons=None, waitRelease=False, clear=True):
        """Get button presses.

        Parameters
        ----------
        buttons : str, int, list or None
            Only get presses of these buttons, as names or indices. If `None`,
            get presses of all buttons.
        waitRelease : bool
            If `True`, only get presses whose button has been released.
        clear : bool
            If `True`, the presses returned aren't returned again.

        Returns
        -------
        list[MouseResponse]
            Presses, in the order they happened.

        """
        self._update()
        if buttons is not None:
            if isinstance(buttons, (str, int)):
                buttons = [buttons]
            buttons = [_buttonLabels[_buttonIndex(b)] for b in buttons]
        clicks = []
        for resp in self.responses:
            if buttons is not None and resp.value not in buttons:
                continue
            if waitRelease and resp.duration is None:
                continue
            clicks.append(resp)
        if clear:
            returned = {id(resp) for resp in clicks}
            self.responses = [
                resp for resp in self.responses if id(resp) not in returned]

        return clicks

    # --------------------------------------------------------------------------
    # Scroll wheel
    #

    def getWheelRel(self):
        """Get the travel of the scroll wheel since this was last called.

        Returns
        -------
        ndarray
            Horizontal and vertical travel `(x, y)`.

        """
        self._update()
        rel = self._wheel.copy()
        self._wheel[:] = 0.0

        return rel

    def getScrolls(self, clear=True):
        """Get scroll events.

        Parameters
        ----------
        clear : bool
            If `True`, the events returned aren't returned again.

        Returns
        -------
        ndarray
            Array with a row `(t, dx, dy)` for each event, where `t` is the
            time on `clock`.

        """
        self._update()
        tReset = self.clock.getLastResetTime()
        rows = [(t - tReset, dx, dy) for t, dx, dy in self.scrolls]
        if clear:
            self.scrolls.clear()

        return np.array(rows, dtype=float).reshape((-1, 3))

    def clearEvents(self):
        """Discard button presses, motion, scrolling and wheel travel received
        so far. The state of the buttons and position are kept."""
        self._update()
        self.responses = []
        self.motion.clear()
        self.scrolls.clear()
        self._wheel[:] = 0.0

    # --------------------------------------------------------------------------
    # Cursor appearance
    #

    def getVisible(self):
        """Get whether the cursor is shown over PsychoPy windows.

        Returns
        -------
        bool
            `True` if the cursor is shown.

        """
        return self._visible

    def setVisible(self, visible=True):
        """Show or hide the cursor over all PsychoPy windows. The position of
        the cursor is still tracked while it is hidden.

        Parameters
        ----------
        visible : bool
            `True` to show the cursor.

        """
        self._visible = bool(visible)
        for win in self.windows:
            win.setMouseVisible(self._visible)

    def getExclusive(self):
        """Get whether `win` has exclusive control of the cursor.

        Returns
        -------
        bool
            `True` if exclusive.

        """
        return self._exclusive

    def setExclusive(self, exclusive):
        """Give `win` exclusive control of the cursor, which hides it and keeps
        it within the window. This should be used for fullscreen windows which
        need mouse input but don't show the cursor.

        Parameters
        ----------
        exclusive : bool
            `True` to make `win` exclusive.

        """
        win = self.win
        if win is None:
            logging.error(
                "Could not make the mouse exclusive, no window is open.")
            return
        self._exclusive = bool(exclusive)
        win.backend.setMouseExclusive(self._exclusive)

    def setCursorStyle(self, cursorType='default'):
        """Change the appearance of the cursor over all PsychoPy windows.

        Cursors give hints about how to interact with things on screen, using
        the standard cursors of the operating system, so their appearance varies
        between platforms. These are valid on most platforms and backends:

        * ``'arrow'`` or ``'default'``: Default system pointer.
        * ``'ibeam'`` or ``'text'``: Indicates text can be edited.
        * ``'crosshair'``: Crosshair with hot-spot at center.
        * ``'hand'``: A pointing hand.
        * ``'hresize'``: Double arrows pointing horizontally.
        * ``'vresize'``: Double arrows pointing vertically.

        Pyglet windows (``winType='pyglet'``) support more, see
        :meth:`~psychopy.visual.Window.setMouseType`. Where a cursor isn't
        supported, the default for the system is used.

        Parameters
        ----------
        cursorType : str
            Type of cursor to use.

        """
        for win in self.windows:
            if hasattr(win.backend, 'setMouseCursor'):
                win.backend.setMouseCursor(cursorType)


class Mouse(AttributeGetSetMixin):
    """Mouse input, through a :class:`MouseDevice` managed by
    :class:`~psychopy.hardware.manager.DeviceManager`.

    This has the same methods as :class:`psychopy.event.Mouse`, so can be used
    in its place, along with timestamped button presses (`getClicks`), the
    path of the cursor (`getMotion`) and scrolling (`getScrolls`). Positions
    are in the units of the window the cursor is in (see `win`).

    Parameters
    ----------
    visible : bool or None
        Show the cursor. If `None`, leave it as it is.
    newPos : ArrayLike or None
        Move the cursor to this position `(x, y)` in window units. If `None`,
        leave it where it is.
    win : :class:`~psychopy.visual.Window` or None
        Window to give positions in. If `None`, use the window the cursor is
        over (see `autoFocus`), or the first window which is open.
    backend : str or None
        Backend for the device to get events from, ``'window'`` or
        ``'system'`` (see :class:`MouseDevice`). If `None`, the device keeps the
        backend it has, or uses ``'window'`` if one needs making.
    clock : :class:`~psychopy.clock.Clock` or None
        Clock to give times on. If `None`, the clock of the device is used.
    muteOutsidePsychopy : bool or None
        Ignore presses and scrolling while the cursor isn't over a PsychoPy
        window, see :class:`MouseDevice`. If `None`, keep the setting the device
        has, or use `True` if one needs making.
    autoFocus : bool
        Give positions in the window the cursor is over, rather than always in
        `win`.
    deviceName : str
        Name of the device in DeviceManager, which is made if it doesn't exist.

    Examples
    --------
    Get the position of the cursor, and whether the left button is pressed::

        from psychopy.hardware.mouse import Mouse
        mouse = Mouse(win=win)
        x, y = mouse.getPos()
        pressed = mouse.isPressed('left')

    Get timestamped presses of the left button, once released::

        for click in mouse.getClicks('left', waitRelease=True):
            print(click.t, click.pos, click.duration)

    Get events wherever the cursor is, timestamped when they happen::

        mouse = Mouse(win=win, backend='system')

    """

    def __init__(self, visible=None, newPos=None, win=None, backend=None,
                 clock=None, muteOutsidePsychopy=None, autoFocus=True,
                 deviceName="defaultMouse"):
        # create a MouseDevice if one doesn't already exist, otherwise apply any
        # settings given to it
        if deviceName not in DeviceManager.devices:
            DeviceManager.addDevice(
                deviceClass="psychopy.hardware.mouse.MouseDevice",
                deviceName=deviceName,
                backend=backend,
                clock=clock,
                muteOutsidePsychopy=muteOutsidePsychopy
            )
        self.device = DeviceManager.getDevice(deviceName)
        self.device.configure(
            backend=backend,
            clock=clock,
            muteOutsidePsychopy=muteOutsidePsychopy)
        self.device.autoFocus = autoFocus
        if win is not None:
            self.device.win = win
        # for Builder: set status to STARTED, NOT_STARTED etc
        self.status = None
        self.mouseClock = core.Clock()
        # position at the last call to `getPos` or `getRel`
        self.lastPos = None
        # position `mouseMoved` measures movement from
        self._movedFrom = None
        if visible is not None:
            self.setVisible(visible)
        if newPos is not None:
            self.setPos(newPos)

    @staticmethod
    def _pixToWindowUnits(pos, win):
        """Convert positions in 'pix' coordinates of a window (framebuffer
        pixels from its centre) to the units of the window."""
        return _pixToUnits(pos, win)

    @staticmethod
    def _windowUnitsToPix(pos, win):
        """Convert positions in the units of a window to its 'pix' coordinates
        (framebuffer pixels from its centre)."""
        return _unitsToPix(pos, win)

    @property
    def win(self):
        """Window positions are given in the units of
        (:class:`~psychopy.visual.Window` or `None`), see `MouseDevice.win`.
        """
        return self.device.win

    @win.setter
    def win(self, value):
        self.device.win = value

    @property
    def units(self):
        """Units positions are given in, which are those of `win` (`str`). To
        change them, change the units of the window."""
        win = self.win
        if win is None:
            return None

        return win.units

    @property
    def clock(self):
        """Clock times are given on (:class:`~psychopy.clock.Clock`)."""
        return self.device.clock

    @clock.setter
    def clock(self, value):
        self.device.clock = value

    @property
    def autoFocus(self):
        """Give positions in the window the cursor is over, rather than always
        in `win` (`bool`)."""
        return self.device.autoFocus

    @autoFocus.setter
    def autoFocus(self, value):
        self.device.autoFocus = bool(value)

    @property
    def visible(self):
        """Whether the cursor is shown over PsychoPy windows (`bool`)."""
        return self.getVisible()

    @visible.setter
    def visible(self, value):
        self.setVisible(value)

    def getVisible(self):
        """Get whether the cursor is shown over PsychoPy windows.

        Returns
        -------
        bool
            `True` if the cursor is shown.

        """
        return self.device.getVisible()

    def setVisible(self, visible=True):
        """Show or hide the cursor over all PsychoPy windows.

        Parameters
        ----------
        visible : bool
            `True` to show the cursor.

        """
        self.device.setVisible(visible)

    @property
    def exclusive(self):
        """Whether `win` has exclusive control of the cursor (`bool`)."""
        return self.getExclusive()

    @exclusive.setter
    def exclusive(self, value):
        self.setExclusive(value)

    def getExclusive(self):
        """Get whether `win` has exclusive control of the cursor.

        Returns
        -------
        bool
            `True` if exclusive.

        """
        return self.device.getExclusive()

    def setExclusive(self, exclusivity):
        """Give `win` exclusive control of the cursor, see
        `MouseDevice.setExclusive`.

        Parameters
        ----------
        exclusivity : bool
            `True` to make `win` exclusive.

        """
        self.device.setExclusive(exclusivity)

    def setCursorStyle(self, cursorType='default'):
        """Change the appearance of the cursor over all PsychoPy windows, see
        `MouseDevice.setCursorStyle`.

        Parameters
        ----------
        cursorType : str
            Type of cursor to use.

        """
        self.device.setCursorStyle(cursorType)

    @property
    def pos(self):
        """Position of the cursor `(x, y)` in the units of `win`
        (`ndarray`)."""
        return self.getPos()

    @pos.setter
    def pos(self, value):
        self.setPos(value)

    def getPos(self):
        """Get the position of the cursor.

        Returns
        -------
        ndarray
            Position `(x, y)` in the units of `win`.

        """
        self.lastPos = self.device.getPos()

        return self.lastPos

    def setPos(self, newPos=(0, 0)):
        """Move the cursor. The cursor is moved to the nearest position the
        operating system supports, so `getPos()` may differ slightly from
        `newPos`.

        Parameters
        ----------
        newPos : ArrayLike
            Position `(x, y)` in the units of `win`.

        """
        self.device.setPos(newPos)

    @property
    def prevPos(self):
        """Position of the cursor before it last moved, in the units of `win`
        (`ndarray`)."""
        return self.device.getPrevPos()

    @property
    def relPos(self):
        """Change in position of the cursor when it last moved, in the units of
        `win` (`ndarray`)."""
        return self.device.getPos() - self.device.getPrevPos()

    @property
    def velocity(self):
        """Velocity of the cursor `(vx, vy)` in units of `win` per second
        (`ndarray`), see `MouseDevice.getVelocity`."""
        return self.device.getVelocity()

    @property
    def isMoving(self):
        """`True` if the cursor has moved in the last `MOTION_TIMEOUT` seconds
        (`bool`)."""
        return self.device.isMoving

    @property
    def isDragging(self):
        """`True` if the cursor is moving with a button pressed (`bool`)."""
        return self.device.isMoving and bool(np.any(self.device.buttons))

    @property
    def isHovering(self):
        """`True` if the cursor is over a PsychoPy window (`bool`)."""
        return self.device.isHovering

    @property
    def buttons(self):
        """Whether each button is pressed (`ndarray`), indexed by
        `MOUSE_BUTTON_*`."""
        self.device._update()
        return self.device.buttons.copy()

    @property
    def pressedTimes(self):
        """Time on `clock` each button was last pressed (`ndarray`), indexed by
        `MOUSE_BUTTON_*`. `nan` for buttons which haven't been pressed."""
        self.device._update()
        return self.device._pressedTimes - self.clock.getLastResetTime()

    @property
    def releasedTimes(self):
        """Time on `clock` each button was last released (`ndarray`), indexed by
        `MOUSE_BUTTON_*`. `nan` for buttons which haven't been released."""
        self.device._update()
        return self.device._releasedTimes - self.clock.getLastResetTime()

    @property
    def pressedPos(self):
        """Position each button was last pressed at, in 'pix' coordinates of the
        window it was pressed in (`ndarray`), indexed by `MOUSE_BUTTON_*`."""
        self.device._update()
        return self.device._pressedPos.copy()

    @property
    def releasedPos(self):
        """Position each button was last released at, in 'pix' coordinates of
        the window it was released in (`ndarray`), indexed by
        `MOUSE_BUTTON_*`."""
        self.device._update()
        return self.device._releasedPos.copy()

    def getRel(self):
        """Get how far the cursor has moved since the last call to `getRel` or
        `getPos`.

        Returns
        -------
        ndarray
            Change in position `(dx, dy)` in the units of `win`.

        """
        lastPos = self.lastPos
        pos = self.getPos()
        if lastPos is None:
            return pos

        return pos - lastPos

    def getWheelRel(self):
        """Get the travel of the scroll wheel since this was last called.

        Returns
        -------
        ndarray
            Horizontal and vertical travel `(x, y)`.

        """
        return self.device.getWheelRel()

    def mouseMoved(self, distance=None, reset=False):
        """Determine whether, or how far, the cursor has moved since this was
        last called.

        Parameters
        ----------
        distance : float, ArrayLike or None
            If `None`, check whether the cursor has moved at all. If a number,
            check whether it has moved further than this in a straight line. If
            `(x, y)`, check whether it has moved further than either of these
            along that axis.
        reset : bool, str or ArrayLike
            If `True` or 'here', measure movement from where the cursor is now
            on later calls, returning `False`. If a position `(x, y)`, measure
            movement from there, checking `distance` if given.

        Returns
        -------
        bool
            `True` if the cursor has moved.

        """
        movedFrom = self._movedFrom
        pos = self.getPos()
        if reset is True or (isinstance(reset, str) and reset == 'here'):
            self._movedFrom = pos
            return False
        if reset is not False and hasattr(reset, '__len__'):
            movedFrom = self._movedFrom = np.asarray(reset, dtype=float)
            if not distance:
                return False
        else:
            self._movedFrom = pos
        if movedFrom is None:
            return False
        if distance is None:
            return bool(np.any(pos != movedFrom))
        if isinstance(distance, (int, float)):
            return bool(np.hypot(*(pos - movedFrom)) > distance)

        return bool(np.any(np.abs(pos - movedFrom) > np.asarray(distance)))

    def mouseMoveTime(self):
        """Get the time since the cursor last moved.

        Returns
        -------
        float
            Time in seconds.

        """
        return self.device.getMoveTime()

    def isPressed(self, button):
        """Check whether a button is pressed.

        Parameters
        ----------
        button : str or int
            Name of the button (e.g. 'left') or its index (`MOUSE_BUTTON_*`).

        Returns
        -------
        bool
            `True` if the button is pressed.

        """
        return self.device.isPressed(button)

    def getPressed(self, getTime=False):
        """Get whether the left, middle and right buttons are pressed, see
        `MouseDevice.getPressed`.

        Parameters
        ----------
        getTime : bool
            If `True`, also give the time each button was last pressed since
            `clickReset` was last called for it.

        Returns
        -------
        list or tuple
            List of three `bool`, or with `getTime` a tuple of this and a list
            of three times.

        """
        return self.device.getPressed(getTime=getTime)

    def clickReset(self, buttons=(0, 1, 2)):
        """Reset the times `getPressed(getTime=True)` gives for buttons, so they
        are relative to now.

        Parameters
        ----------
        buttons : list
            Buttons to reset, as names or indices.

        """
        self.device.clickReset(buttons=buttons)

    def isPressedIn(self, shape, buttons=(0, 1, 2)):
        """Check whether a button is pressed while the cursor is inside a shape.

        Parameters
        ----------
        shape : object
            Anything with a `contains` method, such as a
            :class:`~psychopy.visual.ShapeStim`.
        buttons : list
            Buttons to check, as names or indices.

        Returns
        -------
        bool
            `True` if any of `buttons` is pressed with the cursor in `shape`.

        """
        pressed = self.getPressed()
        if not any(pressed[_buttonIndex(button)] for button in buttons):
            return False

        return bool(shape.contains(self))

    def getClicks(self, buttons=None, waitRelease=False, clear=True):
        """Get button presses, see `MouseDevice.getClicks`.

        Parameters
        ----------
        buttons : str, int, list or None
            Only get presses of these buttons, as names or indices. If `None`,
            get presses of all buttons.
        waitRelease : bool
            If `True`, only get presses whose button has been released.
        clear : bool
            If `True`, the presses returned aren't returned again.

        Returns
        -------
        list[MouseResponse]
            Presses, in the order they happened.

        """
        return self.device.getClicks(
            buttons=buttons, waitRelease=waitRelease, clear=clear)

    def getMotion(self, clear=True):
        """Get the positions the cursor has moved through, see
        `MouseDevice.getMotion`.

        Parameters
        ----------
        clear : bool
            If `True`, the positions returned aren't returned again.

        Returns
        -------
        ndarray
            Array with a row `(t, x, y)` for each position.

        """
        return self.device.getMotion(clear=clear)

    def getScrolls(self, clear=True):
        """Get scroll events, see `MouseDevice.getScrolls`.

        Parameters
        ----------
        clear : bool
            If `True`, the events returned aren't returned again.

        Returns
        -------
        ndarray
            Array with a row `(t, dx, dy)` for each event.

        """
        return self.device.getScrolls(clear=clear)

    def clearEvents(self):
        """Discard button presses, motion, scrolling and wheel travel received
        so far."""
        self.device.clearEvents()

    def start(self):
        """Start listening for mouse events."""
        self.device.start()

    def stop(self):
        """Stop listening for mouse events."""
        self.device.stop()


# get mouse backends from plugins
for _ep in importlib.metadata.entry_points(
        group="psychopy.hardware.mouse.backends"):
    MouseDevice.backends[_ep.name] = _ep


def _isListeningToWindows():
    """Check whether a `MouseDevice` is receiving events from the backends of
    windows."""
    device = MouseDevice._instance
    if device is None or device.backend is None:
        return False

    return not device.backend.usesScreenCoords and device.backend.isRunning


def _onWindowMouseEvent(win, kind, pos=None, button=None, scroll=None):
    """Called by the backends of windows for each mouse event, passing it to
    the `MouseDevice` if it is using the 'window' backend.

    Parameters
    ----------
    win : :class:`~psychopy.visual.Window`
        Window the event came from.
    kind : str
        Type of event, one of 'press', 'release', 'move', 'scroll', 'enter' or
        'leave'.
    pos : ArrayLike or None
        Position `(x, y)` in 'pix' coordinates of `win`, `None` if unknown.
    button : int or None
        Index of the button (`MOUSE_BUTTON_*`) for 'press' and 'release'
        events. Events from buttons without an index are ignored.
    scroll : ArrayLike or None
        Horizontal and vertical scroll offsets `(dx, dy)` for 'scroll' events.

    """
    t = getTime()
    if not _isListeningToWindows():
        return
    if kind in ("press", "release") and button is None:
        return
    MouseDevice._instance.backend.push(
        kind, t, button=button, pos=pos, win=win, scroll=scroll)


def _onWindowMoved(win):
    """Called by the backends of windows when a window moves, so system
    backends keep mapping the cursor to it correctly."""
    device = MouseDevice._instance
    if device is not None:
        device._updateWindowRects(force=True)


if __name__ == "__main__":
    pass
