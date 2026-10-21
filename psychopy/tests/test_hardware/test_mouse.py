"""Tests for `psychopy.hardware.mouse`.
"""
import numpy as np
import pytest

from psychopy import event, monitors, visual
from psychopy.clock import getTime
from psychopy.hardware import DeviceManager, mouse
from psychopy.hardware.mouse import MouseDevice, Mouse, MouseResponse
from psychopy.hardware.mouse._base import BaseMouseBackend
from psychopy.tests import skip_under_vm


# rect of a fake window on screen, (left, top, width, height)
_FAKE_RECT = (100, 50, 200, 100)


class FakeScreenBackend(BaseMouseBackend):
    """Backend giving events in screen coordinates, as system backends do, with
    every window at `_FAKE_RECT` on screen."""
    name = "fake"
    usesScreenCoords = True

    def getWindowRect(self, win):
        return _FAKE_RECT


@pytest.fixture
def device():
    """A new `MouseDevice` using the 'window' backend."""
    if MouseDevice._instance is not None:
        MouseDevice._instance.stop()
    MouseDevice._instance = None
    dev = MouseDevice(backend="window")
    yield dev
    dev.stop()
    MouseDevice._instance = None


@pytest.fixture
def legacyMouse():
    """Restore the state of the mouse in `psychopy.event` after tests which send
    events through window backends, as other tests expect it untouched."""
    saved = (list(event.mouseButtons), list(event.mouseTimes),
             np.array(event.mouseWheelRel))
    yield
    event.mouseButtons[:] = saved[0]
    event.mouseTimes[:] = saved[1]
    event.mouseWheelRel = saved[2]


@pytest.fixture
def win():
    # not shared between tests, as windows of other types can't be opened
    # while it's open
    monitor = monitors.Monitor("mouseTestMonitor", width=40.0, distance=57.0)
    monitor.setSizePix((1920, 1080))
    win = visual.Window(
        (200, 100), units='pix', allowGUI=False, autoLog=False,
        monitor=monitor, winType='pyglet')
    yield win
    win.close()


def _screenDevice(device, win):
    """Swap the backend of a device for `FakeScreenBackend`."""
    device.stop()
    device.backend = FakeScreenBackend(device)
    device.attachWindow(win)
    device.win = win
    device.start()

    return device.backend


def test_click_between_dispatches(device):
    """A press and release which both happen before events are dispatched
    still give a click with its duration."""
    t = getTime()
    device.backend.push('press', t, button=mouse.MOUSE_BUTTON_LEFT, pos=(1, 2))
    device.backend.push(
        'release', t + 0.1, button=mouse.MOUSE_BUTTON_LEFT, pos=(3, 4))
    clicks = device.getClicks()
    assert len(clicks) == 1
    assert clicks[0] == 'left'
    assert clicks[0].duration == pytest.approx(0.1)
    assert np.allclose(clicks[0].pos, (1, 2))
    assert np.allclose(clicks[0].releasePos, (3, 4))
    assert device.getPressed() == [False, False, False]
    # cleared, so not returned again
    assert device.getClicks() == []


def test_click_filters(device):
    t = getTime()
    for button in (mouse.MOUSE_BUTTON_LEFT, mouse.MOUSE_BUTTON_RIGHT,
                   mouse.MOUSE_BUTTON_X1):
        device.backend.push('press', t, button=button, pos=(0, 0))
    assert [c.value for c in device.getClicks('right', clear=False)] == \
        ['right']
    assert [c.value for c in device.getClicks(0, clear=False)] == ['left']
    assert [c.value for c in device.getClicks(['x1', 'left'], clear=False)] \
        == ['left', 'x1']
    # none released yet
    assert device.getClicks(waitRelease=True) == []
    assert device.isPressed('x1')
    assert device.getPressed() == [True, False, True]


def test_release_after_clear(device):
    """A press returned and cleared before its release still gets a
    duration."""
    t = getTime()
    device.backend.push('press', t, button=mouse.MOUSE_BUTTON_LEFT, pos=(0, 0))
    click, = device.getClicks()
    assert click.duration is None
    device.backend.push(
        'release', t + 0.25, button=mouse.MOUSE_BUTTON_LEFT, pos=(0, 0))
    device.dispatchMessages()
    assert click.duration == pytest.approx(0.25)


def test_getPressed_times(device):
    device.clickReset()
    tReset = getTime()
    device.backend.push(
        'press', tReset + 0.5, button=mouse.MOUSE_BUTTON_MIDDLE, pos=(0, 0))
    pressed, times = device.getPressed(getTime=True)
    assert pressed == [False, True, False]
    assert times[0] == 0.0
    assert times[1] == pytest.approx(0.5, abs=0.01)


def test_scrolling(device):
    t = getTime()
    device.backend.push('scroll', t, pos=(0, 0), scroll=(0, 1))
    device.backend.push('scroll', t + 0.1, pos=(0, 0), scroll=(1, -3))
    assert np.allclose(device.getWheelRel(), (1, -2))
    assert np.allclose(device.getWheelRel(), (0, 0))
    scrolls = device.getScrolls()
    assert scrolls.shape == (2, 3)
    assert np.allclose(scrolls[:, 1:], [(0, 1), (1, -3)])
    assert device.getScrolls().shape == (0, 3)
    # scrolling isn't a response
    assert device.getClicks() == []


def test_motion(device):
    t = getTime()
    for i, pos in enumerate([(0, 0), (10, 0), (10, 5)]):
        device.backend.push('move', t + i * 0.01, pos=pos)
    # repeating the position isn't motion
    device.backend.push('move', t + 0.03, pos=(10, 5))
    motion = device.getMotion()
    assert np.allclose(motion[:, 1:], [(0, 0), (10, 0), (10, 5)])
    assert np.allclose(np.diff(motion[:, 0]), 0.01)
    assert np.allclose(device.getPos(), (10, 5))
    assert np.allclose(device.getPrevPos(), (10, 0))
    assert device.getMotion().shape == (0, 3)


def test_callback(device):
    calls = []
    device.registerCallback('right', calls.append, args=['called'])
    t = getTime()
    device.backend.push('press', t, button=mouse.MOUSE_BUTTON_LEFT, pos=(0, 0))
    device.backend.push('press', t, button=mouse.MOUSE_BUTTON_RIGHT, pos=(0, 0))
    device.dispatchMessages()
    assert calls == ['called']
    device.clearCallbacks()


def test_singleton_reconfigure(device):
    device.backend.push('press', getTime(), button=0, pos=(0, 0))
    device.dispatchMessages()
    again = MouseDevice(historySize=5)
    assert again is device
    assert device.historySize == 5
    # unspecified settings and responses are kept
    assert device.getBackend() == "window"
    assert len(device.getClicks()) == 1


def test_profiles(device):
    profiles = MouseDevice.getAvailableDevices()
    assert profiles[0]['backend'] == "window"
    assert device.isSameDevice(profiles[0])
    for profile in profiles[1:]:
        assert not device.isSameDevice(profile)
    assert device.getDeviceProfile()['deviceName'] == "Mouse"


def test_device_manager(device):
    name = "testMouse"
    profile = dict(MouseDevice.getAvailableDevices()[0], deviceName=name)
    try:
        added = DeviceManager.addDevice(**profile)
        assert added is device
        assert DeviceManager.getDevice(name) is device
        assert name in DeviceManager.getInitialisedDevices("mouse")
    finally:
        DeviceManager.removeDevice(name)
    assert not device.started


def test_wrapper(device):
    m = Mouse(deviceName="testWrapperMouse")
    try:
        assert m.device is device
        m.clickReset()
        device.backend.push(
            'press', getTime(), button=mouse.MOUSE_BUTTON_LEFT, pos=(0, 0))
        buttons, times = m.getPressed(getTime=True)
        assert buttons == [True, False, False]
        assert m.getClicks('left')[0] == 'left'
        # Builder sets attributes of its own
        m.status = None
        m.tStart = 0.0
    finally:
        DeviceManager.removeDevice("testWrapperMouse")


@pytest.mark.parametrize("units", [
    'pix', 'norm', 'height', 'cm', 'deg', 'degFlat', 'degFlatPos'])
def test_units_round_trip(win, units):
    win.units = units
    pix = np.array([[37.0, -21.0], [-80.0, 45.0]])
    converted = mouse._pixToUnits(pix, win)
    assert np.allclose(mouse._unitsToPix(converted, win), pix)
    win.units = 'pix'


def test_screen_coords(device, win):
    """Positions in screen coordinates are mapped to windows, and presses
    outside of windows are muted."""
    backend = _screenDevice(device, win)
    left, top, width, height = _FAKE_RECT
    centre = (left + width / 2.0, top + height / 2.0)
    t = getTime()
    backend.push('move', t, screenPos=centre)
    assert np.allclose(device.getPos(), (0, 0))
    assert device.isHovering
    # top-right corner of the window
    backend.push('move', t, screenPos=(left + width, top))
    expected = np.asarray(win.frameBufferSize) / 2.0 / win.pixScaleFactor
    assert np.allclose(device.getPos(), expected)
    # outside of the window, muted
    backend.push('press', t, button=0, screenPos=(0, 0))
    backend.push('release', t, button=0, screenPos=(0, 0))
    assert not device.isHovering
    assert device.getClicks() == []
    # unless muting is turned off
    device.muteOutsidePsychopy = False
    backend.push('press', t, button=0, screenPos=(0, 0))
    assert len(device.getClicks()) == 1
    device.muteOutsidePsychopy = True
    backend.push('release', t, button=0, screenPos=(0, 0))
    device.dispatchMessages()
    # inside the window
    backend.push('press', t, button=2, screenPos=centre)
    click, = device.getClicks()
    assert click == 'right'
    assert np.allclose(click.pos, (0, 0))
    assert np.allclose(click.screenPos, centre)


def test_screen_pix_round_trip(win):
    pix = np.array([33.0, -12.0])
    screenPos = mouse._pixToScreen(pix, win, _FAKE_RECT)
    assert np.allclose(mouse._screenToPix(screenPos, win, _FAKE_RECT), pix)


def test_window_backend_feeds_both(device, win, legacyMouse):
    """Events from the window reach both `psychopy.event` and the device."""
    from pyglet.window import mouse as pygletMouse
    device.attachWindow(win)
    device.getClicks()
    win.backend.onMouseButtonPress(10, 20, pygletMouse.LEFT, 0)
    assert event.mouseButtons[0] == 1
    assert device.getPressed()[0]
    win.backend.onMouseButtonRelease(10, 20, pygletMouse.LEFT, 0)
    assert event.mouseButtons[0] == 0
    click, = device.getClicks()
    assert click == 'left'
    assert click.duration is not None
    assert np.allclose(
        click.pos, mouse._pixToUnits(
            win.backend._windowCoordsToPix((10, 20)), win))
    # buttons without an index don't raise
    win.backend.onMouseButtonPress(10, 20, 1 << 10, 0)
    win.backend.onMouseScroll(10, 20, 0, 2)
    assert np.allclose(device.getWheelRel(), (0, 2))
    win.backend.onMouseDrag(30, 40, 20, 20, pygletMouse.LEFT, 0)
    assert np.allclose(
        device.getPos(), mouse._pixToUnits(
            win.backend._windowCoordsToPix((30, 40)), win))


def test_glfw_window_backend_feeds_both(device, legacyMouse):
    """Events from a GLFW window reach both `psychopy.event` and the
    device."""
    glfw = pytest.importorskip("glfw")
    try:
        glfwWin = visual.Window(
            (200, 100), units='pix', allowGUI=False, autoLog=False,
            winType='glfw')
    except Exception as err:
        pytest.skip(f"Could not open a GLFW window: {err}")
    try:
        assert glfwWin in device.windows
        handle = glfwWin.backend.winHandle.handle
        glfwWin.backend.onMouseMove(handle, 10.0, 20.0)
        assert np.allclose(
            device.getPos(), mouse._pixToUnits(
                glfwWin.backend._windowCoordsToPix((10.0, 20.0)), glfwWin))
        glfwWin.backend.onMouseButton(
            handle, glfw.MOUSE_BUTTON_RIGHT, glfw.PRESS, 0)
        assert event.mouseButtons[2] == 1
        assert device.getPressed()[2]
        glfwWin.backend.onMouseButton(
            handle, glfw.MOUSE_BUTTON_RIGHT, glfw.RELEASE, 0)
        assert event.mouseButtons[2] == 0
        click, = device.getClicks()
        assert click == 'right'
        assert click.duration is not None
        glfwWin.backend.onMouseScroll(handle, 1.0, -1.0)
        assert np.allclose(device.getWheelRel(), (1, -1))
    finally:
        glfwWin.close()
    assert glfwWin not in device.windows


def test_window_events_without_device(device, win, legacyMouse):
    """Without a running device, events from the window still reach
    `psychopy.event`."""
    from pyglet.window import mouse as pygletMouse
    device.stop()
    assert not mouse._isListeningToWindows()
    win.backend.onMouseButtonPress(10, 20, pygletMouse.RIGHT, 0)
    assert event.mouseButtons[2] == 1
    win.backend.onMouseButtonRelease(10, 20, pygletMouse.RIGHT, 0)
    assert event.mouseButtons[2] == 0
    assert device.buffer == type(device.buffer)()


@skip_under_vm
def test_system_backend(device, win):
    """The system backend starts, maps the cursor to the window and moves it.
    Skipped if it can't start (e.g. without permission to monitor input)."""
    device.setBackend('system')
    device.start()
    if device.getBackend() == "window":
        pytest.skip("The system mouse backend couldn't start.")
    original = device.backend.getCursorPos()
    try:
        device.win = win
        win.units = 'pix'
        device.setPos((20, -10))
        assert np.allclose(device.getPos(), (20, -10), atol=1)
        assert device.getScreenPos() is not None
    finally:
        device.backend.setCursorPos(original)
        device.stop()
        assert not device.backend.isRunning
