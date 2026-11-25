#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Demo of using the Cedrus Riponda response pad.

The Riponda has three kinds of input, and this demo reads all of them at once:

    * buttons: the response keys on the pad
    * voice key: the sound sensor, triggered by speaking into the microphone
    * light sensor: the TTL light sensor, which you attach to the screen to
      detect when a stimulus appears

Each input is a separate PsychoPy device (a button group, a sound sensor group
and a light sensor group), which all share the same physical Riponda. The
window shows the live state of each input and a log of recent events. A
patch in the bottom-left corner of the window flashes on and off: attach the
light sensor over it to see light sensor events, along with how long after
the screen flip each onset was detected.

Press Escape to quit.

Requirements:

    * the `psychopy-cedrus` plugin, which you can install from the Plugin
      Manager or with `pip install psychopy-cedrus`
    * the FTDI driver for the Riponda's USB connection, available from
      https://ftdichip.com/drivers/vcp-drivers/
"""

from psychopy import core, visual
from psychopy.hardware import deviceManager, keyboard

try:
    from psychopy_cedrus.riponda import RipondaDevice
except ImportError:
    raise ImportError(
        "This demo needs the psychopy-cedrus plugin. Install it from the Plugin "
        "Manager or with `pip install psychopy-cedrus`."
    )

# --- Settings ---
DEVICE_INDEX = 0  # which Riponda to use, if more than one is connected
N_BUTTONS = 7  # number of response keys on the pad
LIGHT_THRESHOLD = 0.5  # light sensor sensitivity, from 0 to 1
VOICEKEY_THRESHOLD = None  # voice key sensitivity, from 0 to 1 (None keeps the device's setting)
FLASH_INTERVAL = 0.5  # seconds the light sensor patch spends on, then off
LOG_LENGTH = 10  # number of recent events to show

# --- Find the Riponda --- 
available = RipondaDevice.getAvailableDevices()
if not available:
    raise ConnectionError(
        "No Cedrus Riponda found. Check that it is plugged in and that the FTDI "
        "driver is installed."
    )
print("Riponda devices found:")
for profile in available:
    print("    %(index)s: %(deviceName)s" % profile)

# --- Set up one device for each kind of input ---
# These all refer to the same Riponda (pad=DEVICE_INDEX), so they share one
# connection to it.
buttons = deviceManager.addDevice(
    deviceClass="psychopy_cedrus.riponda.RipondaButtonGroup",
    deviceName="ripondaButtons",
    pad=DEVICE_INDEX,
    channels=N_BUTTONS,
)
voicekey = deviceManager.addDevice(
    deviceClass="psychopy_cedrus.riponda.RipondaSoundSensorGroup",
    deviceName="ripondaVoicekey",
    pad=DEVICE_INDEX,
    channels=1,
    threshold=VOICEKEY_THRESHOLD,
)
lightSensor = deviceManager.addDevice(
    deviceClass="psychopy_cedrus.riponda.RipondaLightSensorGroup",
    deviceName="ripondaLightSensor",
    pad=DEVICE_INDEX,
    channels=1,
)
lightSensor.setThreshold(LIGHT_THRESHOLD, channel=0)

# --- Window and stimuli ---
win = visual.Window(
    size=(1024, 768), units="height", color="black", fullscr=False,
    title="Cedrus Riponda demo"
)
aspect = win.size[0] / win.size[1]

title = visual.TextStim(
    win, text="Cedrus Riponda: press buttons, speak, or flash the light sensor.\n"
               "Press Escape to quit.",
    pos=(0, 0.42), height=0.03, wrapWidth=1.2
)

# one row per input: a label, an indicator light, and a description of the state
rowNames = ("Buttons", "Voice key", "Light sensor")
rows = {}
for i, name in enumerate(rowNames):
    y = 0.28 - i * 0.09
    rows[name] = {
        'label': visual.TextStim(
            win, text=name, pos=(-0.42, y), height=0.035, anchorHoriz="left"
        ),
        'indicator': visual.Circle(
            win, radius=0.025, pos=(-0.12, y), fillColor="dimgrey",
            lineColor="white"
        ),
        'state': visual.TextStim(
            win, text="", pos=(-0.07, y), height=0.035, anchorHoriz="left"
        ),
    }

logText = visual.TextStim(
    win, text="", pos=(-0.42, 0.0), height=0.025, anchorHoriz="left",
    anchorVert="top", wrapWidth=1.0, color="lightgrey"
)

# patch for the light sensor, in the bottom-left corner of the window
patchSize = 0.15
patch = visual.Rect(
    win, width=patchSize, height=patchSize,
    pos=(-aspect / 2 + patchSize / 2, -0.5 + patchSize / 2),
    fillColor="white", lineColor=None
)
patchLabel = visual.TextStim(
    win, text="light sensor here", height=0.02,
    pos=(-aspect / 2 + patchSize + 0.01, -0.5 + patchSize / 2),
    anchorHoriz="left", color="grey"
)

# --- Run ---
kb = keyboard.Keyboard()
clock = core.Clock()
# report all response times on the same clock as the screen flips
for device in (buttons, voicekey, lightSensor):
    device.resetTimer(clock)
    device.getResponses(clear=True)  # discard anything received during setup

heldButtons = set()
voicekeyOn = False
lightOn = False
log = []
lastFlipOn = None  # time of the most recent flip that showed the patch


def addToLog(t, message):
    log.append("%8.3f s   %s" % (t, message))
    del log[:-LOG_LENGTH]
    print(log[-1])


def recordFlip():
    global lastFlipOn
    lastFlipOn = clock.getTime()


patchVisible = False
nextToggle = 0
while not kb.getKeys(["escape"]):
    # toggle the light sensor patch, noting when the flip that shows it happens
    if clock.getTime() >= nextToggle:
        patchVisible = not patchVisible
        nextToggle += FLASH_INTERVAL
        if patchVisible:
            win.callOnFlip(recordFlip)

    # buttons: each response is one key going down (value=True) or up (False)
    for resp in buttons.getResponses(clear=True):
        if resp.value:
            heldButtons.add(resp.channel)
        else:
            heldButtons.discard(resp.channel)
        addToLog(resp.t, "button %s %s" % (resp.channel, "pressed" if resp.value else "released"))

    # voice key: on when sound goes above threshold, off when it falls below
    for resp in voicekey.getResponses(clear=True):
        voicekeyOn = resp.value
        addToLog(resp.t, "voice key %s" % ("on" if resp.value else "off"))

    # light sensor: on when light goes above threshold, off when it falls below
    for resp in lightSensor.getResponses(clear=True):
        lightOn = resp.value
        message = "light sensor %s" % ("on" if resp.value else "off")
        if resp.value and lastFlipOn is not None:
            message += " (%.1f ms after flip)" % ((resp.t - lastFlipOn) * 1000)
        addToLog(resp.t, message)

    # show the current state of each input
    states = {
        "Buttons": (
            bool(heldButtons),
            "held: " + ", ".join(str(b) for b in sorted(heldButtons))
            if heldButtons else "none held"
        ),
        "Voice key": (voicekeyOn, "sound detected" if voicekeyOn else "quiet"),
        "Light sensor": (lightOn, "light detected" if lightOn else "dark"),
    }
    for name, (active, description) in states.items():
        rows[name]['indicator'].fillColor = "limegreen" if active else "dimgrey"
        rows[name]['state'].text = description
        for stim in rows[name].values():
            stim.draw()
    logText.text = "Recent events:\n" + "\n".join(log)

    title.draw()
    logText.draw()
    patchLabel.draw()
    if patchVisible:
        patch.draw()
    win.flip()

win.close()
core.quit()

# The contents of this file are in the public domain.
