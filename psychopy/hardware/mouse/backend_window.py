#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Mouse backend which gets events from the backends of PsychoPy windows.

"""

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2025 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

__all__ = ['WindowMouseBackend']

from ._base import BaseMouseBackend


class WindowMouseBackend(BaseMouseBackend):
    """Get mouse events from the backends of PsychoPy windows (pyglet or GLFW).

    Window backends pass their mouse events to
    `psychopy.hardware.mouse._onWindowMouseEvent`, which pushes them to the
    device while this backend is running. Events are only received while the
    cursor is over a PsychoPy window, or dragging from one.

    Notes
    -----
    * Events are timestamped when the window dispatches them, which is usually
      once per frame when it is flipped, rather than when they happened. Use a
      system backend (``backend='system'``) for more precise timing.
    * Windows using the pygame backend don't report mouse events.

    """
    name = "window"
    usesScreenCoords = False


if __name__ == "__main__":
    pass
