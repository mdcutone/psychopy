"""Keyboard and mouse events from the ioHub server's Windows input hooks
(`psychopy/iohub/devices/win32hooks.py`), checked end to end by injecting
input with `keybd_event` / `mouse_event`, which low-level hooks see just like
real input.

Injected keys go to whichever window is in the foreground, so keys are only
injected while the PsychoPy window is in the foreground; the tests skip if it
can't be brought there, and fail if it loses the foreground part way through.
Don't use the keyboard or mouse while these tests run: real input lands in the
same event stream.
"""
import ctypes
import sys
import time
from ctypes import wintypes

import pytest

from psychopy.iohub.constants import EventConstants as EC, MouseConstants as MC
from psychopy.tests import skip_under_vm

pytestmark = [
    pytest.mark.skipif(sys.platform != 'win32',
                       reason='tests the Windows keyboard / mouse hooks'),
    skip_under_vm,
]

KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP = 0x0008, 0x0010
MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP = 0x0020, 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000

VK_BACK, VK_RETURN, VK_SPACE, VK_LEFT = 0x08, 0x0D, 0x20, 0x25
VK_CAPITAL, VK_NUMLOCK, VK_SCROLL = 0x14, 0x90, 0x91
VK_1, VK_A, VK_F5 = 0x31, 0x41, 0x74
VK_LSHIFT, VK_LCONTROL, VK_LMENU = 0xA0, 0xA2, 0xA4
VK_OEM_2, VK_OEM_4 = 0xBF, 0xDB  # '/' and '[' on a US layout
VK_NUMPAD0, VK_DECIMAL = 0x60, 0x6E

US_ENGLISH = 0x0409


class InputInjector:
    """A PsychoPy window with ioHub running, and methods to inject input into
    it and collect the resulting ioHub events."""

    def __init__(self, win, io):
        self.user32 = ctypes.windll.user32
        self.win = win
        self.io = io
        # the top level window, which GetForegroundWindow returns
        self.hwnd = win.winHandle._hwnd
        self.held = set()
        self.startToggles = {}
        self.startCursor = None

    def bringToFront(self):
        for _ in range(30):
            # Windows only lets a process take the foreground in some cases,
            # one being that it sent the last input; a mouse move of 0 pixels
            # is input that does nothing, whichever window has the focus
            self.user32.mouse_event(MOUSEEVENTF_MOVE, 0, 0, 0, 0)
            self.win.winHandle.activate()
            self.win.flip()
            if self.user32.GetForegroundWindow() == self.hwnd:
                return True
            time.sleep(0.05)
        return False

    def toggleState(self, vk):
        return self.user32.GetKeyState(vk) & 0x01

    def setToggle(self, vk, on):
        if self.toggleState(vk) != on:
            self.tap(vk)

    def prepare(self):
        """Save the lock key states and cursor position, then set the locks to
        a known state: Num Lock on, Caps Lock and Scroll Lock off."""
        self.startToggles = {
            vk: self.toggleState(vk) for vk in (VK_CAPITAL, VK_NUMLOCK, VK_SCROLL)}
        pt = wintypes.POINT()
        self.user32.GetCursorPos(ctypes.byref(pt))
        self.startCursor = (pt.x, pt.y)
        self.setToggle(VK_NUMLOCK, 1)
        self.setToggle(VK_CAPITAL, 0)
        self.setToggle(VK_SCROLL, 0)

    def restore(self):
        # key ups and lock key taps only, so harmless in whatever window has
        # the focus by now
        for vk in list(self.held):
            self._send(vk, up=True)
        for vk, state in self.startToggles.items():
            if self.toggleState(vk) != state:
                self._send(vk)
                self._send(vk, up=True)
        if self.startCursor:
            self.user32.SetCursorPos(*self.startCursor)

    def _send(self, vk, up=False):
        self.user32.keybd_event(vk, self.user32.MapVirtualKeyW(vk, 0),
                                KEYEVENTF_KEYUP if up else 0, 0)
        (self.held.discard if up else self.held.add)(vk)
        for _ in range(3):
            self.win.flip()

    def key(self, vk, up=False):
        if self.user32.GetForegroundWindow() != self.hwnd:
            pytest.fail('The PsychoPy window lost the foreground; stopped '
                        'injecting keys.')
        self._send(vk, up)

    def tap(self, vk):
        self.key(vk)
        self.key(vk, up=True)

    def chord(self, modVK, vk):
        self.key(modVK)
        self.tap(vk)
        self.key(modVK, up=True)

    def clientCenter(self):
        """Centre of the window's client area, in screen pixels."""
        view = self.win._hw_handle
        rect = wintypes.RECT()
        self.user32.GetClientRect(view, ctypes.byref(rect))
        pt = wintypes.POINT(rect.right // 2, rect.bottom // 2)
        self.user32.ClientToScreen(view, ctypes.byref(pt))
        return pt.x, pt.y

    def windowRect(self):
        rect = wintypes.RECT()
        self.user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
        return rect

    def mouse(self, flags, data=0):
        self.user32.mouse_event(flags, 0, 0,
                                ctypes.c_uint32(data & 0xFFFFFFFF).value, 0)
        for _ in range(3):
            self.win.flip()

    def moveTo(self, x, y):
        sw = self.user32.GetSystemMetrics(0)
        sh = self.user32.GetSystemMetrics(1)
        self.user32.mouse_event(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
                                round(x * 65535 / (sw - 1)),
                                round(y * 65535 / (sh - 1)), 0, 0)
        for _ in range(3):
            self.win.flip()

    def clearEvents(self):
        for _ in range(3):
            self.win.flip()
        self.io.clearEvents('all')

    def collect(self, device, count, timeout=2.0, settle=0.2):
        """Events from `device` until there are `count` of them (or
        `timeout`), then any more that arrive within `settle` seconds."""
        # the device's own getEvents: ioHubConnection.getEvents(device, ...)
        # converts the events twice, which fails for keyboard events
        getEvents = getattr(self.io.devices, device).getEvents
        events = []
        deadline = time.perf_counter() + timeout
        while len(events) < count and time.perf_counter() < deadline:
            self.win.flip()
            events += getEvents(asType='dict')
        deadline = time.perf_counter() + settle
        while time.perf_counter() < deadline:
            self.win.flip()
            events += getEvents(asType='dict')
        return [{k: v.decode() if isinstance(v, bytes) else v
                 for k, v in e.items()} for e in events]


def _launch(**deviceConfig):
    from psychopy import visual
    from psychopy.iohub import launchHubServer

    win = visual.Window((800, 600), units='pix', winType='pyglet',
                        allowGUI=True)
    io = injector = None
    try:
        io = launchHubServer(window=win, **deviceConfig)
        injector = InputInjector(win, io)
        if not injector.bringToFront():
            pytest.skip('Could not bring the PsychoPy window to the '
                        'foreground, so no input was injected.')
        injector.prepare()
        yield injector
    finally:
        if injector:
            injector.restore()
        if io:
            io.quit()
        win.close()


@pytest.fixture(scope='class')
def inputs():
    yield from _launch()


@pytest.fixture(scope='class')
def windowOnlyInputs():
    yield from _launch(Keyboard=dict(report_system_wide_events=False),
                       Mouse=dict(report_system_wide_events=False))


def keyRows(events):
    """(type, key, char, modifiers) of keyboard events, with Num Lock (on
    throughout, see InputInjector.prepare) left out of the modifiers."""
    return [(e['type'], e['key'], e['char'],
             set(e['modifiers']) - {'numlock'}) for e in events]


def tapped(key, char, mods=()):
    return [(EC.KEYBOARD_PRESS, key, char, set(mods)),
            (EC.KEYBOARD_RELEASE, key, char, set(mods))]


def chorded(modKey, key, char, mods=()):
    return ([(EC.KEYBOARD_PRESS, modKey, '', {modKey, *mods})]
            + tapped(key, char, {modKey, *mods})
            + [(EC.KEYBOARD_RELEASE, modKey, '', set(mods))])


class TestSystemWide:
    """Default configuration: events are reported wherever they happen."""

    def test_key_codes_and_window(self, inputs):
        inputs.clearEvents()
        inputs.tap(VK_F5)
        events = inputs.collect('keyboard', 2)
        assert keyRows(events) == tapped('f5', '')
        scanCode = inputs.user32.MapVirtualKeyW(VK_F5, 0)
        for e in events:
            assert e['key_id'] == VK_F5
            assert e['scan_code'] == scanCode
            # keyboard events report the foreground (top level) window,
            # mouse events the window under the cursor (pyglet's child view)
            assert e['window_id'] == inputs.hwnd

    def test_ctrl_letter_named_from_key_code(self, inputs):
        # ToUnicode gives a control character for ctrl + letter, so the key
        # name comes from the virtual key code instead
        inputs.clearEvents()
        inputs.chord(VK_LCONTROL, VK_A)
        events = inputs.collect('keyboard', 4)
        assert keyRows(events) == chorded('lctrl', 'a', '\x01')

    def test_lock_key_modifiers(self, inputs):
        inputs.clearEvents()
        for lockVK in (VK_CAPITAL, VK_SCROLL, VK_NUMLOCK):
            inputs.tap(lockVK)
            inputs.tap(VK_F5)
            inputs.tap(lockVK)
            inputs.tap(VK_F5)
        events = inputs.collect('keyboard', 24)
        assert len(events) == 24
        f5Mods = [set(e['modifiers']) for e in events
                  if e['key'] == 'f5' and e['type'] == EC.KEYBOARD_PRESS]
        assert f5Mods == [
            {'numlock', 'capslock'}, {'numlock'},
            {'numlock', 'scrolllock'}, {'numlock'},
            set(), {'numlock'},
        ]

    def test_auto_repeat_dropped(self, inputs):
        # report_auto_repeat_press_events is False by default
        inputs.clearEvents()
        inputs.key(VK_F5)
        inputs.key(VK_F5)
        inputs.key(VK_F5)
        inputs.key(VK_F5, up=True)
        events = inputs.collect('keyboard', 2)
        assert keyRows(events) == tapped('f5', '')

    def test_numpad_keys(self, inputs):
        inputs.clearEvents()
        vks = [VK_NUMPAD0 + i for i in range(10)] + [VK_DECIMAL]
        for vk in vks:
            inputs.tap(vk)
        events = inputs.collect('keyboard', 2 * len(vks))
        keys = [e['key'] for e in events if e['type'] == EC.KEYBOARD_PRESS]
        assert keys == ['insert', 'end', 'down', 'pagedown', 'left', ' ',
                        'right', 'home', 'up', 'pageup', 'delete']

    def test_us_layout_translation(self, inputs):
        # an HKL's low word is the input language, its high word the layout
        layout = (inputs.user32.GetKeyboardLayout(0) >> 16) & 0xFFFF
        if layout != US_ENGLISH:
            pytest.skip('Expected key / char values are for a US English '
                        'keyboard layout; this one is %#06x.' % layout)
        steps = [
            ((VK_A,), tapped('a', 'a')),
            ((VK_1,), tapped('1', '1')),
            ((VK_SPACE,), tapped(' ', ' ')),
            ((VK_RETURN,), tapped('return', '\n')),
            ((VK_BACK,), tapped('backspace', '')),
            ((VK_LEFT,), tapped('left', '')),
            ((VK_OEM_4,), tapped('[', '[')),
            ((VK_OEM_2,), tapped('/', '/')),
            ((VK_LSHIFT, VK_A), chorded('lshift', 'a', 'A')),
            ((VK_LSHIFT, VK_1), chorded('lshift', '1', '!')),
            ((VK_LCONTROL, VK_OEM_4), chorded('lctrl', 'oem_4', '\x1b')),
            ((VK_LMENU, VK_A), chorded('lalt', 'a', 'a')),
            # Caps Lock state is tracked by the hook, and changes the char
            ((VK_CAPITAL,), tapped('capslock', '', ['capslock'])),
            ((VK_A,), tapped('a', 'A', ['capslock'])),
            ((VK_LSHIFT, VK_A), chorded('lshift', 'a', 'a', ['capslock'])),
            ((VK_CAPITAL,), tapped('capslock', '')),
            ((VK_A,), tapped('a', 'a')),
        ]
        inputs.clearEvents()
        expected = []
        for vks, rows in steps:
            if len(vks) == 1:
                inputs.tap(vks[0])
            else:
                inputs.chord(*vks)
            expected += rows
        events = inputs.collect('keyboard', len(expected))
        assert keyRows(events) == expected

    def test_mouse_events(self, inputs):
        cx, cy = inputs.clientCenter()
        inputs.moveTo(cx, cy)
        inputs.clearEvents()
        inputs.moveTo(cx + 50, cy + 20)
        inputs.mouse(MOUSEEVENTF_LEFTDOWN)
        inputs.moveTo(cx + 60, cy + 30)
        inputs.mouse(MOUSEEVENTF_LEFTUP)
        inputs.mouse(MOUSEEVENTF_RIGHTDOWN)
        inputs.mouse(MOUSEEVENTF_RIGHTUP)
        inputs.mouse(MOUSEEVENTF_MIDDLEDOWN)
        inputs.mouse(MOUSEEVENTF_MIDDLEUP)
        inputs.mouse(MOUSEEVENTF_WHEEL, -120)
        inputs.mouse(MOUSEEVENTF_WHEEL, 120)
        inputs.mouse(MOUSEEVENTF_WHEEL, 240)
        events = inputs.collect('mouse', 11)

        assert [e['type'] for e in events] == [
            EC.MOUSE_MOVE, EC.MOUSE_BUTTON_PRESS, EC.MOUSE_DRAG,
            EC.MOUSE_BUTTON_RELEASE,
            EC.MOUSE_BUTTON_PRESS, EC.MOUSE_BUTTON_RELEASE,
            EC.MOUSE_BUTTON_PRESS, EC.MOUSE_BUTTON_RELEASE,
            EC.MOUSE_SCROLL, EC.MOUSE_SCROLL, EC.MOUSE_SCROLL]
        for e in events:
            assert e['window_id'] == inputs.win._hw_handle

        # 'pix' units, so the drag is 10 right and 10 down (y is up)
        move, drag = events[0], events[2]
        dx = drag['x_position'] - move['x_position']
        dy = drag['y_position'] - move['y_position']
        assert abs(dx - 10) <= 1 and abs(dy + 10) <= 1

        left, right, middle = (MC.MOUSE_BUTTON_LEFT, MC.MOUSE_BUTTON_RIGHT,
                               MC.MOUSE_BUTTON_MIDDLE)
        assert [(e['button_id'], e['pressed_buttons'])
                for e in events[1:8]] == [
            (left, left), (0, left), (left, 0),
            (right, right), (right, 0), (middle, middle), (middle, 0)]

        scrolls = events[8:]
        # each wheel event counts as one step, whatever its size
        assert [e['scroll_dy'] for e in scrolls] == [-1, 1, 1]
        assert [e['scroll_y'] - scrolls[0]['scroll_y']
                for e in scrolls] == [0, 1, 2]


class TestWindowOnly:
    """report_system_wide_events False: only events in a PsychoPy window."""

    def test_mouse_outside_window_not_reported(self, windowOnlyInputs):
        inputs = windowOnlyInputs
        cx, cy = inputs.clientCenter()
        outsideX = inputs.windowRect().right + 20
        if outsideX >= inputs.user32.GetSystemMetrics(0):
            pytest.skip('No room on screen to the right of the window.')
        inputs.moveTo(cx, cy)
        inputs.clearEvents()
        inputs.moveTo(cx + 10, cy)
        inputs.moveTo(outsideX, cy)   # a move only; nothing is clicked
        inputs.moveTo(cx, cy)
        events = inputs.collect('mouse', 2)
        assert [e['type'] for e in events] == [EC.MOUSE_MOVE, EC.MOUSE_MOVE]
        for e in events:
            assert e['window_id'] == inputs.win._hw_handle

    @pytest.mark.xfail(strict=True, reason=(
        'Known bug, also with pyWinhook: keyboard events report the '
        'foreground (top level) window, but ioHub registers the PsychoPy '
        "window by pyglet's child view window (win._hw_handle), so with "
        'report_system_wide_events False every keyboard event is dropped.'))
    def test_keyboard_reported_in_window(self, windowOnlyInputs):
        inputs = windowOnlyInputs
        inputs.clearEvents()
        inputs.tap(VK_F5)
        events = inputs.collect('keyboard', 2)
        assert keyRows(events) == tapped('f5', '')
