#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Demo showing the coordinates of the mouse, using psychopy.hardware.mouse.

The position of the cursor is shown next to it, in the units of the window
('pix', with (0, 0) at the centre and y increasing upwards), along with the
state of the buttons, the travel of the scroll wheel and the last click.

The mouse can get its events from one of two backends:
    'system' gets them from the operating system, wherever the cursor is, so
        the coordinates keep updating when the cursor leaves the window, and
        its position on screen is known too. Clicks outside of the window are
        ignored though.
    'window' gets them from the window, so the coordinates stop updating when
        the cursor leaves it.
If the 'system' backend can't start (e.g. without permission to monitor input
on macOS, or under Wayland on Linux) the 'window' backend is used instead.

Press B to switch backends, and Escape to quit.
"""

import numpy as np
from psychopy import visual, core, event
from psychopy.hardware.mouse import Mouse

# Create a window to draw in, with coordinates in pixels from its centre
win = visual.Window((800, 600), units='pix', allowGUI=True)

# Get the mouse, with events from the operating system if possible
mouse = Mouse(win=win, backend='system')

# Crosshair and dot which follow the cursor
hLine = visual.Line(win, start=(-2000, 0), end=(2000, 0),
    lineColor='white', opacity=0.25, autoLog=False)
vLine = visual.Line(win, start=(0, -2000), end=(0, 2000),
    lineColor='white', opacity=0.25, autoLog=False)
dot = visual.Circle(win, size=8, fillColor='white', lineColor=None,
    autoLog=False)
# Coordinates, shown next to the cursor
coords = visual.TextStim(win, height=16, color='white',
    autoLog=False)  # autologging not useful for dynamic stimuli
# Everything else, shown in the top-left corner
info = visual.TextStim(win, pos=(-385, 285), height=16, wrapWidth=770,
    alignText='left', anchorHoriz='left', anchorVert='top', color='white',
    autoLog=False)

wheel = np.zeros(2)  # total travel of the scroll wheel
lastClick = None

# Continue until Escape is pressed
while True:
    keys = event.getKeys(keyList=['b', 'escape'])
    if 'escape' in keys:
        break
    if 'b' in keys:
        # switch backend, if 'system' can't start the mouse uses 'window'
        if mouse.device.getBackend() == 'window':
            mouse.device.setBackend('system')
        else:
            mouse.device.setBackend('window')

    # get the state of the mouse
    x, y = mouse.getPos()
    screenPos = mouse.device.getScreenPos()
    pressed = [name for name, isPressed in
               zip(('left', 'middle', 'right'), mouse.getPressed())
               if isPressed]
    wheel += mouse.getWheelRel()
    # clicks are given as they are pressed, and their duration is filled in
    # once released
    for click in mouse.getClicks():
        lastClick = click

    # follow the cursor, keeping the coordinates on the side of it nearest the
    # centre of the window so they don't go off the edge
    hLine.pos = (0, y)
    vLine.pos = (x, 0)
    dot.pos = (x, y)
    coords.text = f"({x:.0f}, {y:.0f})"
    # align the text to the same side as the anchor, or it's centred in a box
    # as wide as the wrap width
    coords.anchorHoriz = coords.alignHoriz = 'left' if x < 0 else 'right'
    coords.anchorVert = 'bottom' if y < 0 else 'top'
    coords.pos = (x + (12 if x < 0 else -12), y + (12 if y < 0 else -12))

    # describe everything else
    backend = mouse.device.getBackend()
    if backend != 'window':
        backend = f"system ({backend})"
    lines = [
        f"Backend: {backend}  (press B to switch, Escape to quit)",
        f"Position: ({x:.0f}, {y:.0f}) {win.units}",
    ]
    if screenPos is not None:
        lines.append(
            f"Position on screen: ({screenPos[0]:.0f}, {screenPos[1]:.0f})")
    else:
        lines.append("Position on screen: only known by the 'system' backend")
    lines += [
        f"Over the window: {'yes' if mouse.isHovering else 'no'}",
        f"Buttons pressed: {', '.join(pressed) or 'none'}",
        f"Scroll wheel: ({wheel[0]:.1f}, {wheel[1]:.1f})",
    ]
    if lastClick is not None:
        clickText = f"Last click: {lastClick.value}"
        if lastClick.pos is not None:
            clickText += f" at ({lastClick.pos[0]:.0f}, {lastClick.pos[1]:.0f})"
        clickText += f", {lastClick.t:.3f} s"
        if lastClick.duration is None:
            clickText += ", still held"
        else:
            clickText += f", held for {lastClick.duration:.3f} s"
        lines.append(clickText)
    info.text = "\n".join(lines)

    # Do the drawing
    hLine.draw()
    vLine.draw()
    dot.draw()
    coords.draw()
    info.draw()
    win.flip()

win.close()
core.quit()

# The contents of this file are in the public domain.
