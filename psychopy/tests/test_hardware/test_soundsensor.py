import pytest
from psychopy.hardware import soundsensor
from psychopy.hardware.soundsensor import BaseSoundSensorGroup, SoundSensor, SoundSensorResponse


class FakeSoundSensor(BaseSoundSensorGroup):
    """
    Sound sensor which hears a fixed level of background noise, or a louder level while a test
    sound is playing. Like a real sensor, it responds when the level is above its threshold.
    """
    def __init__(self, background, testSound, threshold=0.5):
        self.levels = {False: background, True: testSound}
        self.playing = False
        BaseSoundSensorGroup.__init__(self, channels=1, threshold=threshold)

    def _setThreshold(self, threshold, channel=None):
        return self.getState(channel)

    def dispatchMessages(self):
        for channel in range(self.channels):
            state = self.levels[self.playing] > self.getThreshold(channel)
            if state != self.state[channel]:
                self.receiveMessage(
                    SoundSensorResponse(t=0, value=state, channel=channel, device=self)
                )

    def resetTimer(self, clock=None):
        pass


class FakeSound:
    """
    Stands in for sound.Sound, telling the fake sensor when it's playing.
    """
    def __init__(self, sensor):
        self.sensor = sensor

    def play(self):
        self.sensor.playing = True

    def stop(self):
        self.sensor.playing = False


class FakeKeyboard:
    def __init__(self, *args, **kwargs):
        pass

    def getKeys(self, *args, **kwargs):
        return []


@pytest.fixture
def makeSensor(monkeypatch):
    """
    Make a fake sound sensor, with sound and keyboard swapped for fakes so that findThreshold
    needs no audio or keyboard devices.
    """
    def _makeSensor(background, testSound, threshold=0.5):
        sensor = FakeSoundSensor(background, testSound, threshold=threshold)
        monkeypatch.setattr(
            soundsensor.sound, "Sound", lambda *args, **kwargs: FakeSound(sensor)
        )
        monkeypatch.setattr(soundsensor.keyboard, "Keyboard", FakeKeyboard)
        return sensor

    return _makeSensor


@pytest.mark.parametrize("background, testSound", [
    (0.2, 0.8),
    (0.1, 0.4),
    (0.6, 0.9),
])
def test_findThreshold(makeSensor, background, testSound):
    """
    findThreshold should set and return a threshold between the background noise and the test
    sound, so that the sensor detects the test sound but not the background noise.
    """
    sensor = makeSensor(background, testSound)
    threshold = sensor.findThreshold(speaker=None, channel=0, samplingWindow=0.001)

    assert threshold == pytest.approx((background + testSound) / 2, abs=0.01)
    assert sensor.getThreshold(0) == threshold
    # sensor should be left silent, with no responses from the search
    assert sensor.getState(0) is False
    assert sensor.getResponses() == []
    # sensor should now detect the test sound but not background noise
    sensor.playing = True
    assert sensor.getState(0) is True
    sensor.playing = False
    assert sensor.getState(0) is False


def test_findThreshold_allChannels(makeSensor):
    """
    Given no channel, findThreshold should return a threshold for each channel.
    """
    sensor = makeSensor(0.2, 0.8)
    thresholds = sensor.findThreshold(speaker=None, samplingWindow=0.001)

    assert thresholds == [pytest.approx(0.5, abs=0.01)]


def test_findThreshold_inaudible(makeSensor):
    """
    If the test sound is no louder than background noise, findThreshold should return None and
    leave the threshold as it was.
    """
    sensor = makeSensor(0.6, 0.6, threshold=0.3)
    threshold = sensor.findThreshold(speaker=None, channel=0, samplingWindow=0.001)

    assert threshold is None
    assert sensor.getThreshold(0) == 0.3


def test_findThreshold_wrapper(makeSensor):
    """
    SoundSensor should pass on the values returned by its device.
    """
    sensor = makeSensor(0.2, 0.8)
    wrapper = SoundSensor(sensor)

    threshold = wrapper.findThreshold(speaker=None, channel=0, samplingWindow=0.001)
    assert threshold == pytest.approx(0.5, abs=0.01)
    assert wrapper.getThreshold(0) == threshold
    wrapper.setThreshold(0.7, channel=0)
    assert wrapper.getThreshold(0) == 0.7
