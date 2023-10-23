#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Audio playback using a speaker.
"""

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2022 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

__all__ = ['Speaker']

import sys
import atexit
import psychopy.logging as logging
from psychopy.constants import NOT_STARTED
from psychopy.hardware.base import BaseDevice
from psychopy.preferences import prefs
from .audioclip import *
from .audiodevice import *
from .exceptions import *
import numpy as np


# Get the default backend for creating speakers. This is fixed after the first
# speaker is created. You must close all devices first before changing the 
# backend within a session.
_sessionBackend = prefs.general['audioLib'][0]

# Speaker objects register here when they are created, this is used to resolve
# conflicts when multiple speakers are created with the same device.
_openSpeakerDevices = set()


class SpeakerDevice(BaseDevice):
    """Device class for playing audio through a speaker.

    Parameters
    ----------
    device : int
        The device index to use for audio playback.
    sampleRateHz : int
        The sample rate to use for audio playback.
    channels : int
        The number of channels to use for audio playback.
    backend : str or None, optional
        The backend to use for audio playback. Cannot be changed after the
        first speaker is created. After the first speaker is created, the
        backend is fixed for the session. Default is `None` which uses the
        default backend specified in preferences.

    """
    def __init__(self,
                 device=None,
                 sampleRateHz=None,
                 channels=None,
                 streamBufferSecs=2.0,
                 audioLatencyMode=None,
                 audioRunMode=0,
                 backend='ptb'):
        super().__init__()

        self._device = device
        self._sampleRateHz = sampleRateHz
        self._channels = channels
        self._streamBufferSecs = streamBufferSecs
        self._audioLatencyMode = audioLatencyMode
        self._audioRunMode = audioRunMode
        self._backend = backend

        # handle to the sound interface
        self._stream = None

    def __hash__(self):
        return hash((self._device))  # has only on the device

    @staticmethod
    def getDevices():
        """Get a list of available audio devices usable for audio playback.

        Returns
        -------
        list
            A list of available audio devices.

        """
        return []

    @property
    def device(self):
        """int: The device index to use for audio playback."""
        return self._device

    @device.setter
    def device(self, value):
        self._device = value

    @property
    def sampleRateHz(self):
        """int: The sample rate to use for audio playback."""
        return self._sampleRateHz   

    @sampleRateHz.setter
    def sampleRateHz(self, value):
        self._sampleRateHz = value  

    @property
    def channels(self):
        """int: The number of channels to use for audio playback."""
        return self._channels

    @channels.setter
    def channels(self, value):
        self._channels = value  

    @property
    def streamBufferSecs(self):
        """float: The buffer size to use for audio playback."""
        return self._streamBufferSecs

    @streamBufferSecs.setter
    def streamBufferSecs(self, value):
        self._streamBufferSecs = value

    @property
    def audioLatencyMode(self):
        """int: The audio latency mode to use for audio playback."""
        return self._audioLatencyMode   

    @audioLatencyMode.setter
    def audioLatencyMode(self, value):
        self._audioLatencyMode = value

    @property
    def audioRunMode(self):
        """int: The audio run mode to use for audio playback."""
        return self._audioRunMode

    @audioRunMode.setter
    def audioRunMode(self, value):
        self._audioRunMode = value

    @property
    def backend(self):
        """str: The backend to use for audio playback."""
        return self._backend

    @backend.setter
    def backend(self, value):
        self._backend = value

    def open(self):
        """Open the speaker device.

        """
        pass

    def close(self):
        """Close the speaker device.

        """
        pass


def closeAllSpeakerDevices():
    """Close all speaker devices.

    """
    pass


atexit.register(closeAllSpeakerDevices)

    
if __name__ == "__main__":
    pass