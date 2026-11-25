import json
from psychopy import constants, core, sound, logging
from psychopy.hardware import base, DeviceManager
from psychopy.localization import _translate
from psychopy.hardware import keyboard
from psychopy.tools.arraytools import ExpandingList


class SoundSensorResponse(base.BaseResponse):
    # list of fields known to be a part of this response type
    fields = ["t", "value", "channel", "threshold"]

    def __init__(self, t, value, channel, device=None, threshold=None):
        # initialise base response class
        base.BaseResponse.__init__(self, t=t, value=value, device=device)
        # store channel and threshold
        self.channel = channel
        self.threshold = threshold


class BaseSoundSensorGroup(base.BaseResponseDevice):

    def __init__(self, channels=1, threshold=None):
        base.BaseResponseDevice.__init__(self)
        # store number of channels
        self.channels = channels
        # attribute in which to store current state
        self.state = ExpandingList([False] * channels)
        # set initial threshold
        self.threshold = ExpandingList([None] * channels)
        self.setThreshold(threshold, channel=list(range(channels)))
    
    def findThreshold(self, speaker, channel=None, samplingWindow=0.5):
        """
        Find the best threshold for this device with a given speaker, and set it.

        The threshold is searched for twice: once in silence, to find the level of background
        noise, and once while a test sound plays on the speaker, to find the level of that sound.
        The threshold chosen is halfway between the two.

        Parameters
        ----------
        speaker : psychopy.hardware.speaker.SpeakerDevice
            Speaker to find best threshold for.
        channel : int or list[int]
            Channel to look for responses in, or a list of channels
        samplingWindow : float
            How long (s) to listen for a response at each threshold tried

        Returns
        -------
        float, None or list
            The threshold chosen (from 0 to 1), or None if the test sound couldn't be heard over
            background noise (in which case the threshold is left as it was). If given several
            channels, a list with one of these per channel.
        """
        # if not given any channels, use all
        if channel is None:
            channel = list(range(self.channels))
        # is given many channels, find for each
        if isinstance(channel, (list, tuple)):
            thresholds = []
            # iterate through channels
            for thisChannel in channel:
                thresholds.append(
                    self.findThreshold(
                        speaker, channel=thisChannel, samplingWindow=samplingWindow
                    )
                )

            return thresholds

        # sound to play
        snd = sound.Sound("voicekeyThresholdStim.wav", speaker=speaker, secs=5, loops=-1)
        # keyboard to check for escape/continue
        kb = keyboard.Keyboard(deviceName="defaultKeyboard")
        # threshold to go back to if no good threshold is found
        originalThreshold = self.getThreshold(channel)

        def _bisectThreshold():
            """
            Narrow down the threshold at which the current sound level stops being detected.
            """
            # a higher threshold needs a louder sound to trigger it, so the sound level is
            # somewhere between the highest threshold detected and the lowest not detected
            low, high = 0, 1
            while high - low >= 0.01:
                current = (low + high) / 2
                # forget the current state, so that it's reported afresh at the new threshold
                self.state[channel] = None
                self.clearResponses()
                self.setThreshold(current, channel=channel)
                # listen for sound at any point in the sampling window
                countdown = core.CountdownTimer(samplingWindow)
                detected = False
                while countdown.getTime() > 0:
                    detected = detected or bool(self.getState(channel=channel))
                logging.debug(
                    f"Trying threshold range: {[low, high]}, threshold {current} detected "
                    f"sound: {detected}"
                )
                # narrow the range
                if detected:
                    low = current
                else:
                    high = current
                # stop early if escape is pressed
                if kb.getKeys(['escape']):
                    break

            return (low + high) / 2

        # reset state
        self.dispatchMessages()
        self.clearResponses()
        try:
            # get level of background noise, with no sound playing
            snd.stop()
            offThreshold = _bisectThreshold()
            # get level of the test sound
            snd.play()
            onThreshold = _bisectThreshold()
        finally:
            # stop sound once done
            snd.stop()
        logging.debug(
            f"Channel {channel} detected background noise below threshold {offThreshold} and "
            f"the test sound below threshold {onThreshold}"
        )
        # if the test sound is no louder than background noise, no threshold can tell them apart
        if onThreshold <= offThreshold:
            logging.warning(
                f"Could not find a threshold for sound sensor channel {channel} which detects "
                f"the test sound but not background noise; leaving threshold as "
                f"{originalThreshold}."
            )
            threshold = None
            self.setThreshold(originalThreshold, channel=channel)
        else:
            # pick a threshold between background noise and the test sound
            threshold = (offThreshold + onThreshold) / 2
            self.setThreshold(threshold, channel=channel)
        # clear all the events created by this process
        self.state[channel] = False
        self.dispatchMessages()
        self.clearResponses()

        return threshold

    def getThreshold(self, channel):
        return self.threshold[channel]
    
    def setThreshold(self, threshold, channel=None):
        # if not given a channel, set for all channels
        if channel is None:
            channel = list(range(self.channels))
        # if given multiple channels, set for each
        if isinstance(channel, (list, tuple)):
            state = []
            for thisChannel in channel:
                state.append(
                    self.setThreshold(threshold, channel=thisChannel)
                )
            return state

        # store threshold value
        self.threshold[channel] = threshold
        # do device-specific threshold setting
        state = self._setThreshold(threshold, channel=channel)

        return state

    def _setThreshold(self, threshold, channel=None):
        """
        Device-specific threshold setting method. This will be called by `setThreshold` and should 
        be overloaded by child classes of BaseSoundSensor.

        Parameters
        ----------
        threshold : float
            Threshold at which to register a SoundSensor response, from 0 to 1. A higher threshold
            needs a louder sound to trigger it.
        channel : int
            Channel to set the threshold for (if applicable to device)

        Returns
        ------
        bool
            True if current decibel level is above the threshold.
        """
        raise NotImplementedError()
    
    def getResponses(self, state=None, channel=None, clear=True):
        """
        Get responses which match a given on/off state.

        Parameters
        ----------
        state : bool or None
            True to get voicekey "on" responses, False to get voicekey "off" responses, None to 
            get all responses.
        channel : int
            Which voicekey to get responses from?
        clear : bool
            Whether or not to remove responses matching `state` after retrieval.

        Returns
        -------
        list[SoundSensorResponse]
            List of matching responses.
        """
        # make sure parent dispatches messages
        self.dispatchMessages()
        # array to store matching responses
        matches = []
        # check messages in chronological order
        for resp in self.responses.copy():
            # does this message meet the criterion?
            if (state is None or resp.value == state) and (channel is None or resp.channel == channel):
                # if clear, remove the response
                if clear:
                    i = self.responses.index(resp)
                    resp = self.responses.pop(i)
                # append the response to responses array
                matches.append(resp)

        return matches
    
    def receiveMessage(self, message):
        # do base receiving
        base.BaseResponseDevice.receiveMessage(self, message)
        # update state
        self.state[message.channel] = message.value

    def resetTimer(self, clock=logging.defaultClock):
        raise NotImplementedError()

    def getState(self, channel):
        # dispatch messages from parent
        self.dispatchMessages()
        # return state after update
        return self.state[channel]
    
    def findSpeakers(self, channel, allowedSpeakers=None, beepDur=1):
        """
        Play a sound on different speakers and return a list of all those which this SoundSensor was 
        able to detect.

        Parameters
        ----------
        channel : int
            Channel to listen for responses on.
        allowedSpeakers : list[SpeakerDevice or dict] or None
            List of speakers to test, or leave as None to test all speakers. If speakers are given 
            as a dict, SpeakerDevice objects will be created via DeviceManager. 
        beepDur : float
            How long (s) to play a beep for on each speaker?
        """
        # if no allowed speakers given, use all
        if allowedSpeakers is None:
            allowedSpeakers = DeviceManager.getAvailableDevices(
                "psychopy.hardware.speaker.SpeakerDevice"
            )
        # list of found speakers
        foundSpeakers = []
        # iterate through allowed speakers
        for speaker in allowedSpeakers:
            # if given a dict, actualise it
            if isinstance(speaker, dict):
                speakerProfile = speaker
                speaker = DeviceManager.getDevice(speakerProfile['deviceName'])
                if speaker is None:
                    speaker = DeviceManager.addDevice(**speakerProfile)
            # generate a sound for this speaker
            try:
                snd = sound.Sound("A", speaker=speaker)
            except Exception as err:
                # silently skip on error
                logging.warn(f"Failed to play audio on speaker {speaker}, reason: {err}")
                continue
            # reset current state and clear responses
            self.state[channel] = False
            self.responses = []
            # start a countdown for beep duration
            countdown = core.CountdownTimer(beepDur)
            # start playing sound
            snd.play()
            # wait for a response
            while countdown.getTime() > 0:
                self.dispatchMessages()
            # stop playing sound
            snd.stop()
            # wait again for the off message, to a max of the beep duration
            countdown.reset(beepDur)
            while countdown.getTime() > 0 and len(self.responses) <= 1:
                self.dispatchMessages()
            # if we got messages, the speaker is good
            if len(self.responses) == 2:
                foundSpeakers.append(speaker)
        
        return foundSpeakers



class MicrophoneSoundSensor(BaseSoundSensorGroup):
    """
    Use a MicrophoneDevice to emulate a SoundSensor, by continuously querying its volume.

    Parameters
    ----------
    device : psychopy.hardware.MicrophoneDevice
        Microphone to sample from
    threshold : int, optional
        Threshold (0-1) at which to register a response, by default 0.5
    dbRange : tuple, optional
        Range of possible decibels to expect mic responses to be in, by default (0, 1)
    samplingWindow : float
        How long (s) to average samples from the microphone across? Larger sampling windows reduce 
        the chance of random spikes, but also reduce sensitivity.
    """
    def __init__(self, device, threshold=0.5, dbRange=(0, 1), samplingWindow=0.03):
        # if device is given by name, get it from DeviceManager
        if isinstance(device, str):
            deviceName = device
            device = DeviceManager.getDevice(deviceName)
            # if none by that name, try by that index
            if device is None:
                device = DeviceManager.getDeviceBy("index", deviceName)
            # if none by that index, do any profiles match?
            if device is None:
                for profile in DeviceManager.getAvailableDevices(
                    "psychopy.hardware.microphone.MicrophoneDevice"
                ):
                    # if any match the index, make a device from that profile
                    if deviceName in (profile['index'], profile['deviceName']):
                        device = DeviceManager.addDevice(**profile)
            # if none found, fallback to default and print warning
            if device is None:
                logging.warn(
                    f"No Microphonen named {deviceName}, falling back to default device."
                )
        # if no device given, get default
        if device is None:
            device = DeviceManager.getDeviceBy("index", None)
        # store device
        self.device = device
        # store decibel range
        self.dbRange = dbRange
        # store sampling window
        self.samplingWindow = samplingWindow
        # make clock
        from psychopy.core import Clock
        self.clock = Clock()
        # initialise base class
        BaseSoundSensorGroup.__init__(
            self, channels=1, threshold=threshold
        )
    
    def getThreshold(self, channel=None):
        return BaseSoundSensorGroup.getThreshold(self, channel=channel or 0)
    
    def getThresholdDb(self, channel=None):
        """
        Get the volume threshold in dB rather than arbitrary units.
        """
        return (
            min(self.dbRange) + 
            self.getThreshold(channel=channel) * (max(self.dbRange) - min(self.dbRange))
        )
    
    def getCurrentVolume(self):
        return self.device.getCurrentVolume()
    
    def _setThreshold(self, threshold, channel=None):
        """
        No additional setup is needed for emulator as thresholding is emulated outside of the 
        device.
        """
        return self.getState(channel=channel)

    def dispatchMessages(self):
        """
        Check the Microphone volume and deliver appropriate response.
        """
        # make sure mic is recording
        if not self.device.isStarted:
            self.device.start()
        # get current volume
        vol = self.device.getCurrentVolume(timeframe=self.samplingWindow)
        # if device is multi-channel, take max
        if not isinstance(vol, (int, float)):
            vol = max(vol)
        # transform volume to arbitrary units
        adjVol = int(
            (vol - min(self.dbRange)) / (max(self.dbRange) - min(self.dbRange))
        )
        # iterate through channels
        for channel in range(self.channels):
            # work out state from adjusted volume
            state = adjVol > self.getThreshold(channel=channel)
            # if state has changed, make an event
            if state != self.state[channel]:
                resp = SoundSensorResponse(
                    t=self.clock.getTime(),
                    value=state,
                    channel=channel,
                    threshold=self.getThreshold(channel=channel),
                    device=self
                )
                self.receiveMessage(resp)

    def parseMessage(self, message):
        """
        Events are created as SoundSensorResponse, so parseMessage is not needed. Will return message 
        unchanged.
        """
        return message

    def isSameDevice(self, other):
        if isinstance(other, type(self)):
            # if both objects are this class, then compare mics
            return other.device is self.device
        else:
            # if types don't match up, it's not the same device
            return False

    @staticmethod
    def getAvailableDevices():
        profiles = []
        # iterate through available microphones
        for micProfile in DeviceManager.getAvailableDevices("psychopy.hardware.microphone.MicrophoneDevice"):
            profiles.append({
                'deviceName': "SoundSensor Emulator (%(deviceName)s)" % micProfile,
                'deviceClass': "psychopy.hardware.soundsensor.MicrophoneSoundSensor",
                'device': micProfile['index'],

            })
        
        return profiles
    
    def resetTimer(self, clock=logging.defaultClock):
        self.clock._timeAtLastReset = clock._timeAtLastReset
        self.clock._epochTimeAtLastReset = clock._epochTimeAtLastReset


class SoundSensor:
    """
    Object to represent a SoundSensor in Builder experiments. Largely exists as a wrapper around 
    BaseSoundSensorGroup, with the ability to inherit a device defined by a backend.
    """
    def __init__(self, device):
        if isinstance(device, BaseSoundSensorGroup):
            # if given a button group, use it
            self.device = device
        # if given a string, get via DeviceManager
        if isinstance(device, str):
            if device in DeviceManager.devices:
                self.device = DeviceManager.getDevice(device)
            else:
                # don't use formatted string literals in _translate()
                raise ValueError(_translate(
                    "Could not find device named '{device}', make sure it has been set up "
                    "in DeviceManager."
                ).format(device))

        # starting value for status (Builder)
        self.status = constants.NOT_STARTED
        # arrays to store info (Builder)
        self.buttons = []
        self.times = []
        self.corr = []

    def getAvailableDevices(self):
        return self.device.getAvailableDevices()

    def getResponses(self, state=None, channel=None, clear=True):
        return self.device.getResponses(state=state, channel=channel, clear=clear)

    def resetTimer(self, clock=logging.defaultClock):
        return self.device.resetTimer(clock=clock)

    def getState(self, channel):
        return self.device.getState(channel=channel)

    def clearResponses(self):
        return self.device.clearResponses()
    
    def findSpeakers(self, channel, allowedSpeakers=None, beepDur=1):
        return self.device.findSpeakers(channel, allowedSpeakers=allowedSpeakers, beepDur=beepDur)
    
    def findThreshold(self, speaker, channel=None, samplingWindow=0.5):
        return self.device.findThreshold(speaker, channel=channel, samplingWindow=samplingWindow)

    def getThreshold(self, channel):
        return self.device.getThreshold(channel=channel)

    def setThreshold(self, threshold, channel=None):
        return self.device.setThreshold(threshold=threshold, channel=channel)
