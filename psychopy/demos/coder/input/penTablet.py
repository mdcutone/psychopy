#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Demo of drawing with a pen tablet (e.g. a Wacom tablet).

Strokes are drawn while the pen touches the tablet. The circle shows where the
pen is, getting bigger with pressure, and the line from it shows which way the
pen is tilted.

If no tablet is attached, the mouse is used instead (hold the left
button to draw).

Press C to clear the drawing, or Escape to quit.
"""

from psychopy import visual, core, event
from psychopy.hardware.pen import PenDevice, SimulatedPenDevice

# Create a window to draw in
win = visual.Window((800, 600), units="height", color="white", allowGUI=True)

# Get the first tablet attached, or use the mouse if there isn't one
tablets = PenDevice.getAvailableDevices()
print(tablets)
if tablets:
    profile = tablets[0]
    deviceName = profile['deviceName']
    pen = PenDevice(win=win, **{key: val for key, val in profile.items() if key != "deviceName"})
else:
    print("No pen tablet found, using the mouse instead.")
    pen = SimulatedPenDevice(win=win)
    deviceName = "mouse"

# Initialize some stimuli
cursor = visual.Circle(win, size=0.01, lineColor="red", fillColor=None, autoLog=False)
tiltLine = visual.Line(win, start=(0, 0), end=(0, 0), lineColor="red", autoLog=False)
message = visual.TextStim(
    win, pos=(-0.65, -0.48), height=0.025, color="black", alignText="left",
    anchorHoriz="left", anchorVert="bottom", autoLog=False
)
# finished strokes, and the stroke being drawn
strokes = []
points = []
currentStroke = visual.ShapeStim(
    win, vertices=[(0, 0), (0, 0)], closeShape=False, lineColor="black", lineWidth=2,
    fillColor=None, autoLog=False
)

nSamples = 0
clock = core.Clock()
while True:
    keys = event.getKeys()
    if "escape" in keys:
        break
    if "c" in keys:
        strokes = []
    # get samples since the last frame
    for resp in pen.getResponses():
        nSamples += 1
        if resp.value in ("down", "move"):
            points.append((resp.x, resp.y))
        elif resp.value in ("up", "leave") and len(points) > 1:
            # stroke finished, so keep it
            strokes.append(visual.ShapeStim(
                win, vertices=points, closeShape=False, lineColor="black", lineWidth=2,
                fillColor=None, autoLog=False
            ))
        if resp.value in ("up", "leave"):
            points = []
    # draw finished strokes, and the current stroke
    for stroke in strokes:
        stroke.draw()
    if len(points) > 1:
        currentStroke.vertices = points
        currentStroke.draw()
    # show the pen, if it's in range
    state = pen.state
    if state is not None and state.value != "leave":
        cursor.pos = (state.x, state.y)
        cursor.size = 0.01 + 0.04 * state.pressure
        cursor.draw()
        tiltLine.start = (state.x, state.y)
        tiltLine.end = (state.x + state.tiltX / 600, state.y + state.tiltY / 600)
        tiltLine.draw()
        message.text = (
            f"{deviceName}: {state.value} ({state.cursor}), pressure {state.pressure:.2f}, "
            f"tilt ({state.tiltX:.0f}, {state.tiltY:.0f}), "
            f"{nSamples / max(clock.getTime(), 1e-6):.0f} samples/s\n"
            "C to clear, Escape to quit"
        )
    message.draw()
    win.flip()

pen.close()
win.close()
core.quit()

# The contents of this file are in the public domain.
