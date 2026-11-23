"""Tests for eye tracker calibration drawn in the experiment window.

The experiment process draws the targets (`ClientCalibrationProcedure`) and
the ioHub server drives the tracker through a window-less ("headless")
calibration procedure (`EyeTrackerDevice.startClientCalibration` etc.).
"""
from types import SimpleNamespace

import pytest

import psychopy.iohub.client.eyetracker.calibration as clientcal
from psychopy.iohub.client.eyetracker import EyeTracker as EyeTrackerView
from psychopy.iohub.devices.eyetracker import EyeTrackerDevice
from psychopy.iohub.devices.eyetracker.calibration import (
    BaseCalibrationProcedure, headlessCalibration)
from psychopy.iohub.devices.eyetracker.calibration import procedure as serverproc


# --- fakes for the experiment-process side -----------------------------------

class FakeWin:
    units = 'norm'
    color = (0, 0, 0)
    colorSpace = 'rgb'
    size = (800, 600)

    def __init__(self):
        self.mouseVisible = True
        self.flips = 0

    def flip(self, *args, **kwargs):
        self.flips += 1


class FakeTarget:
    units = 'norm'

    def __init__(self):
        self.pos = (0.25, 0.25)
        self.size = (0.1, 0.1)
        self.minSize = (0.02, 0.02)
        self.drawnAt = []

    def draw(self):
        self.drawnAt.append(tuple(self.pos))


class FakeText:
    text = ''

    def draw(self):
        pass


class Key:
    def __init__(self, name):
        self.name = name


class FakeKeyboard:
    """Returns `keys(pollNumber)` on each poll."""

    def __init__(self, keys):
        self.keys = keys
        self.polls = 0

    def getKeys(self, keyList=None, waitRelease=True, clear=True):
        self.polls += 1
        return [Key(k) for k in self.keys(self.polls)]

    def clearEvents(self, eventType=None):
        pass


class FakeTracker:
    """Experiment-side tracker view recording the calibration RPCs."""

    def __init__(self, config=None, allowEscape=True, failOnPoint=None):
        self.config = config or {}
        self.allowEscape = allowEscape
        self.failOnPoint = failOnPoint
        self.calls = []

    def getConfiguration(self):
        return {'calibration': dict(self.config)}

    def startClientCalibration(self, calibration_args, points):
        self.calls.append(('start', calibration_args, points))
        return {'allow_escape': self.allowEscape, 'points': points}

    def registerClientCalibrationPoint(self, point):
        self.calls.append(('point', point))
        if self.failOnPoint is not None and len(self.points()) == self.failOnPoint:
            raise RuntimeError('tracker error')
        return True

    def finishClientCalibration(self, aborted=False):
        self.calls.append(('finish', aborted))
        return {'RESULT': 'ABORTED' if aborted else 'OK', 'fromTracker': True}

    def points(self):
        return [c[1] for c in self.calls if c[0] == 'point']


FAST = {'target_delay': 0.001, 'target_duration': 0.002, 'type': 'FIVE_POINTS',
        'randomize': False}


@pytest.fixture
def makeProcedure(monkeypatch):
    # no real window: keep normalised positions and use a dummy text stim
    monkeypatch.setattr(clientcal, 'normToWindowUnits',
                        lambda win, point, units: tuple(point))
    monkeypatch.setattr(clientcal.ClientCalibrationProcedure, '_createText',
                        lambda self: FakeText())

    def makeProcedure(keys, tracker=None, args=None):
        tracker = tracker or FakeTracker()
        procedure = clientcal.ClientCalibrationProcedure(
            FakeWin(), tracker, dict(FAST, **(args or {})),
            target=FakeTarget(), keyboard=FakeKeyboard(keys))
        return procedure, tracker

    return makeProcedure


def always(*names):
    return lambda poll: list(names)


# --- ClientCalibrationProcedure ----------------------------------------------

def test_hooks_called_in_order(makeProcedure):
    procedure, tracker = makeProcedure(always('space'))
    result = procedure.run()

    expected = [list(p) for p in serverproc.target_positions[5]]
    assert tracker.calls[0][0] == 'start'
    assert tracker.calls[0][2] == expected
    assert tracker.points() == expected
    assert tracker.calls[-1] == ('finish', False)
    # the tracker's own result is passed through
    assert result == {'RESULT': 'OK', 'fromTracker': True}


def test_target_drawn_at_each_point_and_restored(makeProcedure):
    procedure, tracker = makeProcedure(always('space'))
    target = procedure.target
    procedure.run()
    for point in serverproc.target_positions[5]:
        assert tuple(point) in target.drawnAt
    assert target.pos == (0.25, 0.25)
    assert target.size == (0.1, 0.1)
    assert procedure.win.mouseVisible is True


def test_escape_at_intro_does_not_start_tracker(makeProcedure):
    procedure, tracker = makeProcedure(always('escape'))
    result = procedure.run()
    assert result == {'RESULT': 'CALIBRATION_ABORTED'}
    assert tracker.calls == []


def test_escape_during_targets_aborts(makeProcedure):
    # SPACE on the intro screen, then ESCAPE
    procedure, tracker = makeProcedure(
        lambda poll: ['space'] if poll == 1 else ['escape'])
    result = procedure.run()
    assert tracker.calls[-1] == ('finish', True)
    assert len(tracker.points()) < 5
    assert result['RESULT'] == 'ABORTED'


def test_escape_ignored_when_tracker_disallows_it(makeProcedure):
    procedure, tracker = makeProcedure(
        lambda poll: ['space'] if poll == 1 else ['escape'],
        tracker=FakeTracker(allowEscape=False))
    procedure.run()
    assert len(tracker.points()) == 5
    assert tracker.calls[-1] == ('finish', False)


def test_manual_pacing_waits_for_space(makeProcedure):
    procedure, tracker = makeProcedure(always('space'), args={'auto_pace': False})
    procedure.run()
    assert len(tracker.points()) == 5
    # one extra poll per point while waiting for SPACE
    assert procedure.keyboard.polls >= 5 + 2


def test_error_still_finishes_tracker(makeProcedure):
    procedure, tracker = makeProcedure(
        always('space'), tracker=FakeTracker(failOnPoint=2))
    with pytest.raises(RuntimeError):
        procedure.run()
    assert tracker.calls[-1] == ('finish', True)


def test_target_attributes_not_sent_to_server(makeProcedure):
    procedure, tracker = makeProcedure(
        always('space'), args={'target_attributes': {'animate': {'enable': True}}})
    procedure.run()
    sentArgs = tracker.calls[0][1]
    assert 'target_attributes' not in sentArgs
    assert sentArgs['type'] == 'FIVE_POINTS'
    # animation settings are still used for drawing
    assert procedure.animateMovement is True


def test_settings_merged_over_tracker_config(makeProcedure):
    tracker = FakeTracker(config={'target_delay': 5.0, 'auto_pace': False,
                                  'type': 'THREE_POINTS'})
    procedure, _ = makeProcedure(always('space'), tracker=tracker,
                                 args={'type': 'NINE_POINTS'})
    assert procedure.settings['type'] == 'NINE_POINTS'
    assert procedure.autoPace is False
    # call args override config
    assert procedure.targetDelay == FAST['target_delay']


def test_calibration_points_keep_first_point_when_randomised():
    import random
    rng = random.Random(1)
    for calType, n in (('THREE_POINTS', 3), ('NINE_POINTS', 9)):
        points = clientcal.calibrationPoints(calType, True, rng=rng)
        assert points[0] == serverproc.target_positions[n][0]
        assert sorted(points) == sorted(serverproc.target_positions[n])
    assert clientcal.calibrationPoints('UNKNOWN', False) == \
        serverproc.target_positions[9]


def test_norm_to_window_units():
    from psychopy import visual
    win = visual.Window(size=(200, 100), units='pix', allowGUI=False,
                        autoLog=False)
    try:
        assert clientcal.normToWindowUnits(win, (0.5, 0.5), 'norm') == (0, 0)
        # origin top-left, y down -> norm origin centre, y up
        assert clientcal.normToWindowUnits(win, (0, 0), 'norm') == (-1, 1)
        assert clientcal.normToWindowUnits(win, (1, 1), 'norm') == (1, -1)
        x, y = clientcal.normToWindowUnits(win, (1, 0.5), 'height')
        assert x == pytest.approx(0.5 * win.size[0] / win.size[1])
        assert y == pytest.approx(0)
        topLeft = clientcal.normToWindowUnits(win, (0, 0), 'pix')
        bottomRight = clientcal.normToWindowUnits(win, (1, 1), 'pix')
        assert topLeft[0] < 0 < topLeft[1]
        assert bottomRight == pytest.approx((-topLeft[0], -topLeft[1]))
    finally:
        win.close()


def test_guess_color_space():
    guess = serverproc.guessColorSpace
    # YAML-style 0-255 values
    assert guess([[64, 64, 64], [0, 255, 0], None], 'rgb') == 'rgb255'
    # valid 'rgb' values stay as they are
    assert guess([[1, 1, 1], [-1, 0, 0.5]], 'rgb') == 'rgb'
    # anything that isn't a plain numeric triplet isn't guessed
    assert guess(['red', [64, 64, 64]], 'rgb') == 'rgb'
    assert guess([[300, 0, 0]], 'rgb') == 'rgb'
    assert guess([None], 'hsv') == 'hsv'


def test_legacy_target_stim():
    from psychopy import visual
    win = visual.Window(size=(200, 100), units='pix', colorSpace='rgb',
                        allowGUI=False, autoLog=False)
    try:
        attrs = {'outer_diameter': 40.0, 'inner_diameter': 10.0,
                 'outer_stroke_width': 2.0, 'outer_fill_color': [64, 64, 64],
                 'outer_line_color': [255, 255, 255],
                 'inner_fill_color': [0, 255, 0], 'inner_line_color': [0, 0, 0]}
        target = serverproc.legacyTargetStim(win, attrs)
        assert isinstance(target, visual.TargetStim)
        assert target.radius == pytest.approx(20)
        assert target.innerRadius == pytest.approx(5)
        # 0-255 colours read as rgb255 in an 'rgb' window, not clipped to white
        assert target.inner.colorSpace == 'rgb255'
        assert list(target.inner._fillColor.rgb) == pytest.approx([-1, 1, -1])
        # sizes are pixels, converted to the requested units
        from psychopy import layout
        heightTarget = serverproc.legacyTargetStim(win, attrs, units='height')
        assert heightTarget.units == 'height'
        assert heightTarget.radius == pytest.approx(
            layout.Size((20, 20), 'pix', win).height[0])
        assert heightTarget.radius < 1
        # missing settings use defaults
        assert serverproc.legacyTargetStim(win, {}).radius == pytest.approx(20)
    finally:
        win.close()


# --- experiment-side EyeTracker view -----------------------------------------

@pytest.fixture
def makeView(monkeypatch):
    def makeView(supported):
        view = object.__new__(EyeTrackerView)
        view.device_class_path = 'psychopy.iohub.devices.eyetracker.hw.test.EyeTracker'
        view.device_class = 'EyeTracker'
        view.rpcCalls = []

        def rpc(name, *args, **kwargs):
            view.rpcCalls.append((name, args))
            if name == 'supportsClientCalibration':
                return supported
            return {'RESULT': 'from server'}
        view._rpc = rpc
        view._methods = ['supportsClientCalibration', 'runSetupProcedure']
        return view
    return makeView


def test_view_without_window_uses_server(makeView):
    view = makeView(supported=True)
    assert view.runSetupProcedure() == {'RESULT': 'from server'}
    # None isn't sent, so the tracker's own default is used
    assert view.rpcCalls == [('runSetupProcedure', ())]
    view.runSetupProcedure({'type': 'FIVE_POINTS'})
    assert view.rpcCalls[-1] == ('runSetupProcedure', ({'type': 'FIVE_POINTS'},))


def test_view_falls_back_when_unsupported(makeView, monkeypatch):
    from psychopy import logging
    warnings = []
    monkeypatch.setattr(logging, 'warning', lambda msg, *a, **k: warnings.append(msg))
    view = makeView(supported=False)
    win = FakeWin()
    win._isFullScr = False
    assert view.runSetupProcedure({'a': 1}, win=win) == {'RESULT': 'from server'}
    assert view.rpcCalls[-1] == ('runSetupProcedure', ({'a': 1},))
    assert warnings and 'hw.test.EyeTracker' in warnings[0]
    assert win.flips == 1


def test_view_uses_client_procedure_when_supported(makeView, monkeypatch):
    ran = []

    class FakeProcedure:
        def __init__(self, win, tracker, args, target=None, keyboard=None):
            ran.append((win, tracker, args, target, keyboard))

        def run(self):
            return {'RESULT': 'client'}

    monkeypatch.setattr(clientcal, 'ClientCalibrationProcedure', FakeProcedure)
    view = makeView(supported=True)
    win = FakeWin()
    assert view.runSetupProcedure({'a': 1}, win=win, target='t') == {'RESULT': 'client'}
    assert ran == [(win, view, {'a': 1}, 't', None)]
    assert ('runSetupProcedure', ({'a': 1},)) not in view.rpcCalls


def test_view_unsupported_without_rpc_method(makeView):
    view = makeView(supported=True)
    view._methods = ['runSetupProcedure']  # older tracker interface
    assert view.supportsClientCalibration() is False


# --- server side: headless procedure and session RPCs ------------------------

class FakeDisplay:
    def getPixelResolution(self):
        return (1920, 1080)

    def getCoordinateType(self):
        return 'pix'

    def getColorSpace(self):
        return 'rgb'


class RecordingProcedure(BaseCalibrationProcedure):
    """Tracker-style subclass whose __init__ doesn't know about headless mode."""

    def __init__(self, eyetrackerInterface, calibration_args):
        BaseCalibrationProcedure.__init__(
            self, eyetrackerInterface, calibration_args,
            allow_escape_in_progress=False)
        self.hookCalls = []

    def startCalibrationHook(self):
        self.hookCalls.append(('start', list(self.cal_target_list)))

    def registerCalibrationPointHook(self, pt):
        self.hookCalls.append(('point', pt))

    def finishCalibrationHook(self, aborted=False):
        self.hookCalls.append(('finish', aborted))


class FakeEyeTracker(EyeTrackerDevice):
    """EyeTrackerDevice without hardware or ioHub server."""
    _display_device = FakeDisplay()

    def __init__(self, config):
        self._config = config

    def getConfiguration(self):
        return self._config

    def _getCalibrationProcedureClass(self):
        return RecordingProcedure


@pytest.fixture
def noRawInput(monkeypatch):
    # don't touch this process' raw keyboard registration
    monkeypatch.setattr(serverproc, '_removeRawKeyboardRegistration', lambda: None)


def test_headless_procedure_has_no_window(noRawInput):
    config = {'calibration': {'type': 'NINE_POINTS', 'target_delay': 1.0}}
    tracker = FakeEyeTracker(config)
    points = [(0.5, 0.5), (0.1, 0.1)]
    with headlessCalibration(points):
        procedure = RecordingProcedure(tracker, {'target_delay': 0.2})
    assert procedure.headless is True
    assert procedure.window is None
    assert procedure.cal_target_list == points
    assert procedure.allow_escape is False
    assert procedure.getCalibSetting('target_delay') == 0.2
    # calibration args don't change the device config
    assert config['calibration']['target_delay'] == 1.0
    # headless mode only applies inside the block
    assert BaseCalibrationProcedure._headlessRequest is None


def test_point_list_is_per_instance(noRawInput):
    tracker = FakeEyeTracker({'calibration': {'type': 'THREE_POINTS'}})
    with headlessCalibration():
        procedure = RecordingProcedure(tracker, {})
    assert procedure.cal_target_list == serverproc.target_positions[3]
    # the class default isn't overwritten any more
    assert BaseCalibrationProcedure.CALIBRATION_POINT_LIST == serverproc.target_positions[9]


def test_session_rpcs_drive_hooks(noRawInput):
    tracker = FakeEyeTracker({'calibration': {'type': 'FIVE_POINTS'}})
    points = [[0.5, 0.5], [0.9, 0.1]]
    assert tracker.supportsClientCalibration() is True

    session = tracker.startClientCalibration({'target_delay': 0.3}, points)
    assert session == {'allow_escape': False, 'points': points}
    procedure = tracker._clientCalibrationSession

    for pt in points:
        tracker.registerClientCalibrationPoint(pt)
    result = tracker.finishClientCalibration(False)

    assert procedure.hookCalls == [
        ('start', [(0.5, 0.5), (0.9, 0.1)]),
        ('point', (0.5, 0.5)), ('point', (0.9, 0.1)),
        ('finish', False)]
    assert result == {'RESULT': 'CALIBRATION_OK'}
    assert tracker._clientCalibrationSession is None


def test_session_rpcs_without_support():
    tracker = object.__new__(EyeTrackerDevice)
    assert tracker.supportsClientCalibration() is False
    from psychopy.iohub.constants import EyeTrackerConstants
    assert tracker.startClientCalibration({}, []) == \
        EyeTrackerConstants.EYETRACKER_INTERFACE_METHOD_NOT_SUPPORTED
    with pytest.raises(RuntimeError):
        tracker.registerClientCalibrationPoint((0.5, 0.5))
    assert tracker.finishClientCalibration(False) == {"RESULT": "CALIBRATION_ABORTED"}
