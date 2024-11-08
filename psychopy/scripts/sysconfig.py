#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Script for querying the system configuration and genreating a JSON file with 
the results.
"""

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2024 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).


import os
import sys
import platform
import subprocess
import argparse
import json
import contextlib
from pathlib import Path
from io import StringIO 

import psychtoolbox.audio as ptbaudio

import psychopy.tools.systemtools as sysTools
import itertools


# additional modes to check for
AUDIO_SAMPLE_RATES = [
    8000, 11025, 16000, 22050, 32000, 44100, 48000, 88200, 96000, 192000]
AUDIO_CHANNELS = [1, 2, 4, 6, 8]
AUDIO_LATENCY_CLASSES = [0, 1, 2, 3, 4]


def getDeviceMap():
    """Get a map of devices on the current system and their properties.
    
    Returns
    -------
    dict
        A dictionary with the devices on the system and their properties.

    """
    hwmap = {}

    # get audio devices
    audioDevices = {}
    audioDevices['input'] = {}
    audioDevices['output'] = {}
    
    allAudioDevices = sysTools.getAudioDevices()

    # get audio input devices
    idxOutput = idxInput = 0
    for dev in allAudioDevices.values():
        if dev['outputChannels'] > 0:
            audioDevices['output'][idxOutput] = dev
            idxOutput += 1
        elif dev['inputChannels'] > 0:
            audioDevices['input'][idxInput] = dev
            idxInput += 1

    # now test the devices for additional modes

    audioSettingToTest = itertools.product(
        AUDIO_SAMPLE_RATES, AUDIO_CHANNELS, AUDIO_LATENCY_CLASSES
    )

    for devType in ['input', 'output']:
        for dev in audioDevices[devType].values():
            availableModes = {}
            for setting in audioSettingToTest:
                devIndex = dev['index']
                if devType == 'input':
                    deviceMode = 2
                else:
                    deviceMode = 1
                sampleRate, channels, latencyClass = setting
                # try:

                outBuff = StringIO()
                errBuff = StringIO()
                with contextlib.redirect_stdout(outBuff):
                    with contextlib.redirect_stderr(errBuff):
                        try:
                            print(errBuff.getvalue())
                            _ = ptbaudio.Stream(
                                mode=deviceMode,
                                device_id=devIndex,
                                freq=sampleRate,
                                channels=channels,
                                latency_class=[latencyClass],
                            ).close()
                        except Exception as e:
                            continue


                print(errBuff.getvalue())

    hwmap['audio'] = audioDevices

    return hwmap


if __name__ == "__main__":
    devMap = getDeviceMap()
    #print(json.dumps(devMap, indent=4))

