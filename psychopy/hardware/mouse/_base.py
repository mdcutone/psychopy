#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Base class for the backends a `MouseDevice` gets its events from.

"""

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2025 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

__all__ = ['BaseMouseBackend']


class BaseMouseBackend:
    """Base class for mouse backends.

    A backend produces raw mouse events and pushes them to the buffer of the
    `MouseDevice` which owns it. The device turns them into responses and state
    in `MouseDevice.dispatchMessages()`. Backends may push events from any
    thread, so they must not do anything else with the device.

    Parameters
    ----------
    device : MouseDevice
        Device to push events to.

    """
    # name of the backend in `MouseDevice.backends`
    name = None
    # `True` if events give the cursor in screen coordinates, which the device
    # maps to windows itself, rather than in the 'pix' coordinates of a window
    usesScreenCoords = False

    def __init__(self, device):
        self.device = device
        self._running = False

    @property
    def isRunning(self):
        """`True` if the backend is producing events (`bool`)."""
        return self._running

    def start(self):
        """Start producing events.

        Raises
        ------
        RuntimeError
            If mouse events can't be captured this way on this system.

        """
        self._running = True

    def stop(self):
        """Stop producing events."""
        self._running = False

    def push(self, kind, t, button=None, pos=None, screenPos=None, win=None,
             scroll=None, osTime=None):
        """Add a raw event to the buffer of the device.

        Parameters
        ----------
        kind : str
            Type of event, one of 'press', 'release', 'move', 'scroll', 'enter'
            or 'leave'.
        t : float
            Time of the event, on the time base of `psychopy.clock.getTime()`.
        button : int or None
            Index of the button (`MOUSE_BUTTON_*`) for 'press' and 'release'
            events.
        pos : ArrayLike or None
            Position `(x, y)` of the cursor in the 'pix' coordinates of `win`,
            i.e. framebuffer pixels from the centre of the window.
        screenPos : ArrayLike or None
            Position `(x, y)` of the cursor in screen coordinates, for backends
            which use them (see `usesScreenCoords`).
        win : :class:`~psychopy.visual.Window` or None
            Window the event came from.
        scroll : ArrayLike or None
            Horizontal and vertical scroll offsets `(dx, dy)` for 'scroll'
            events.
        osTime : float or None
            Timestamp given by the operating system, in its own units. Only
            kept to help diagnose timing.

        """
        if not self._running:
            return

        self.device.buffer.append({
            'type': kind,
            't': t,
            'button': button,
            'pos': pos,
            'screenPos': screenPos,
            'win': win,
            'scroll': scroll,
            'osTime': osTime
        })

    # the following are only used by backends which use screen coordinates

    def getWindowRect(self, win):
        """Get where the content area of a window is on screen.

        Parameters
        ----------
        win : :class:`~psychopy.visual.Window`
            Window to locate.

        Returns
        -------
        tuple or None
            Position of the top-left corner and size of the content area
            `(left, top, width, height)` in screen coordinates, or `None` if
            unknown.

        """
        return None

    def getCursorPos(self):
        """Get the position of the cursor.

        Returns
        -------
        tuple or None
            Position `(x, y)` in screen coordinates, or `None` if unknown.

        """
        return None

    def setCursorPos(self, pos):
        """Move the cursor.

        Parameters
        ----------
        pos : ArrayLike
            Position `(x, y)` in screen coordinates.

        Returns
        -------
        bool
            `True` if the cursor was moved.

        """
        return False


if __name__ == "__main__":
    pass
