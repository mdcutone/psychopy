import sys
from types import SimpleNamespace

import numpy as np
import pytest

from psychopy import clock as psyclock
from psychopy.hardware import DeviceManager
from psychopy.hardware.pen import (
    BasePenDevice, Pen, PenResponse, SimulatedPenDevice, orientationToTilt, tiltToOrientation
)
from psychopy.tools import wintab as wt


def makeWin(size=(800, 600), units="pix", pixScaleFactor=1.0):
    """
    Make an object with the window attributes pen devices use, so tests don't need a real window.
    """
    return SimpleNamespace(
        size=np.array(size), units=units, pixScaleFactor=pixScaleFactor, monitor=None
    )


def makeSimPen(**kwargs):
    kwargs.setdefault("win", makeWin())
    kwargs.setdefault("useMouse", False)
    pen = SimulatedPenDevice(**kwargs)
    pen.resetTimer()
    return pen


class TestPenDevice:
    def test_states(self):
        """
        Check that samples are labelled with what the pen is doing.
        """
        pen = makeSimPen()
        pen.addSample(type="enter")
        for pressure in (0, 0, 0.4, 0.5, 0, 0):
            pen.addSample(pix=(1, 1), pressure=pressure)
        pen.addSample(type="leave")
        values = [resp.value for resp in pen.getResponses()]
        assert values == ["enter", "hover", "hover", "down", "move", "up", "hover", "leave"]

    def test_leave_while_down(self):
        """
        Check that the pen stops counting as down if it goes out of range.
        """
        pen = makeSimPen()
        pen.addSample(pix=(0, 0), pressure=1)
        assert pen.isDown()
        pen.addSample(type="leave")
        assert not pen.isDown()
        assert not pen.inProximity()
        # next sample in range is a new press
        pen.addSample(pix=(0, 0), pressure=1)
        assert pen.getResponses()[-1].value == "down"

    def test_pressure_threshold(self):
        pen = makeSimPen(pressureThreshold=0.5)
        for pressure in (0.2, 0.6, 0.4):
            pen.addSample(pix=(0, 0), pressure=pressure)
        assert [resp.value for resp in pen.getResponses()] == ["hover", "down", "up"]

    def test_timing(self):
        """
        Check that response times are relative to when the timer was reset.
        """
        pen = makeSimPen()
        t0 = pen.clock.getLastResetTime()
        pen.addSample(t=t0 + 0.5, pix=(0, 0))
        resp, = pen.getResponses()
        assert resp.t == pytest.approx(0.5)
        # reset to another clock
        other = psyclock.Clock()
        pen.resetTimer(other)
        pen.addSample(t=other.getLastResetTime() + 1.25, pix=(0, 0))
        resp, = pen.getResponses()
        assert resp.t == pytest.approx(1.25)

    def test_get_responses(self):
        pen = makeSimPen()
        for pressure in (0, 1, 1, 0):
            pen.addSample(pix=(0, 0), pressure=pressure)
        # filter by value without clearing others
        downs = pen.getResponses(value="down")
        assert [resp.value for resp in downs] == ["down"]
        assert [resp.value for resp in pen.getResponses(value=["move", "up"], clear=False)] == [
            "move", "up"
        ]
        assert [resp.value for resp in pen.getResponses()] == ["hover", "move", "up"]
        assert pen.getResponses() == []

    def test_state_and_pos(self):
        pen = makeSimPen()
        assert pen.getState() is None
        assert list(pen.getPos()) == [0, 0]
        pen.addSample(pix=(30, -20), pressure=0.25)
        assert pen.getState().value == "down"
        assert list(pen.getPos()) == [30, -20]
        assert pen.getPressure() == 0.25
        # leaving keeps the last position, but has no pressure
        pen.addSample(type="leave")
        assert pen.getState().value == "leave"
        assert list(pen.getPos()) == [30, -20]
        assert pen.getPressure() == 0

    @pytest.mark.parametrize("units, pix, expected", [
        ("pix", (200, -100), (200, -100)),
        ("norm", (200, -150), (0.5, -0.5)),
        ("height", (300, -150), (0.5, -0.25)),
    ])
    def test_units(self, units, pix, expected):
        pen = makeSimPen(win=makeWin(units=units))
        pen.addSample(pix=pix)
        resp, = pen.getResponses()
        assert resp.units == units
        assert (resp.x, resp.y) == pytest.approx(expected)
        # device units override window units
        pen.units = "pix"
        assert tuple(pen.getPos()) == pytest.approx(pix)

    def test_units_retina(self):
        """
        Check that 'pix' positions convert correctly when the framebuffer has 2 pixels per point.
        """
        win = makeWin(size=(1600, 1200), units="norm", pixScaleFactor=2.0)
        pen = makeSimPen(win=win)
        # 'pix' units are points, so the window is 800x600 'pix'
        pen.addSample(pix=(400, 300))
        resp, = pen.getResponses()
        assert (resp.x, resp.y) == pytest.approx((1, 1))

    def test_cursor_kept(self):
        """
        Check that the cursor from entering is kept for later samples.
        """
        pen = makeSimPen()
        pen.addSample(type="enter", cursor="eraser")
        pen.addSample(pix=(0, 0))
        assert [resp.cursor for resp in pen.getResponses()] == ["eraser", "eraser"]

    def test_callback(self):
        pen = makeSimPen()
        calls = []
        pen.registerCallback("down", calls.append, args=("pressed",))
        pen.addSample(pix=(0, 0), pressure=0)
        pen.addSample(pix=(0, 0), pressure=1)
        pen.addSample(pix=(0, 0), pressure=1)
        pen.dispatchMessages()
        assert calls == ["pressed"]

    def test_response_eq(self):
        resp = PenResponse(t=0, value="down", x=1, y=2)
        assert resp == "down"
        assert resp != "up"
        assert resp == PenResponse(t=0, value="down", x=1, y=2)
        assert resp != PenResponse(t=0, value="down", x=1, y=3)

    def test_device_manager(self):
        """
        Check that pen devices can be set up via DeviceManager, as Builder does.
        """
        profiles = DeviceManager.getAvailableDevices("psychopy.hardware.pen.SimulatedPenDevice")
        assert len(profiles) == 1
        profile = profiles[0]
        try:
            dev = DeviceManager.addDevice(
                deviceName="testPenDevice",
                **{key: val for key, val in profile.items() if key != "deviceName"}
            )
            assert isinstance(dev, SimulatedPenDevice)
            assert dev.getDeviceProfile()['deviceName'] == profile['deviceName']
            assert DeviceManager.getInitialisedDevices(BasePenDevice) == {"testPenDevice": dev}
            # get it from Pen by name
            pen = Pen(device="testPenDevice", win=makeWin())
            assert pen.device is dev
            # or as the default device
            assert Pen(win=makeWin()).device is dev
        finally:
            DeviceManager.removeDevice("testPenDevice")

    def test_pen_unknown_device(self):
        with pytest.raises(ValueError):
            Pen(device="noSuchPenDevice")


class TestPenWrapper:
    def test_record(self):
        dev = makeSimPen(win=makeWin(units="pix"))
        pen = Pen(device=dev, units="norm")
        dev.addSample(pix=(400, 300), pressure=0.5, tiltX=10, tiltY=-5)
        for resp in pen.getResponses():
            pen.record(resp)
        pen.record(None)
        assert pen.x == [pytest.approx(1)]
        assert pen.y == [pytest.approx(1)]
        assert pen.pressure == [0.5]
        assert pen.state == ["down"]
        assert pen.tiltX == [10]
        assert pen.tiltY == [-5]
        assert len(pen.time) == 1
        # positions in the wrapper's units
        assert tuple(pen.getPos()) == pytest.approx((1, 1))
        pen.clearData()
        assert pen.x == [] and pen.state == []

    def test_units_follow_window(self):
        win = makeWin(units="height")
        pen = Pen(device=makeSimPen(win=win), win=win)
        assert pen.units == "height"
        win.units = "pix"
        assert pen.units == "pix"


class TestOrientation:
    @pytest.mark.parametrize("azimuth, altitude, expected", [
        (0, 90, (0, 0)),
        (0, 45, (0, 45)),
        (90, 45, (45, 0)),
        (180, 60, (0, -30)),
        (270, 30, (-60, 0)),
    ])
    def test_orientation_to_tilt(self, azimuth, altitude, expected):
        assert orientationToTilt(azimuth, altitude) == pytest.approx(expected, abs=1e-9)

    @pytest.mark.parametrize("azimuth, altitude", [
        (0, 90), (45, 50), (135, 70), (225, 30), (300, 80),
    ])
    def test_round_trip(self, azimuth, altitude):
        tilt = orientationToTilt(azimuth, altitude)
        az, alt = tiltToOrientation(*tilt)
        assert alt == pytest.approx(altitude)
        if altitude < 90:
            assert az == pytest.approx(azimuth)


class TestWintab:
    """
    Tests for the parts of the Wintab backend which don't need a tablet (or Windows).
    """
    pktData = wt.PK_STATUS | wt.PK_TIME | wt.PK_CURSOR | wt.PK_BUTTONS | wt.PK_X | wt.PK_Y \
        | wt.PK_NORMAL_PRESSURE | wt.PK_ORIENTATION

    def makeDevice(self):
        from psychopy.hardware.pen._wintab import WintabPenDevice, _AxisScale
        # skip __init__, which needs the driver
        dev = object.__new__(WintabPenDevice)
        BasePenDevice.__init__(dev, win=makeWin())
        dev.resetTimer()
        dev.name = "Test tablet"
        dev._context = None
        dev._sync = None
        dev._wtInProximity = False
        dev._firstCursor = 0
        circle = 3600 << 16  # 3600 units per circle, as 16.16 fixed point
        dev._axes = {
            wt.PK_NORMAL_PRESSURE: [_AxisScale(wt.AXIS(0, 1023, 0, 0))],
            wt.PK_ORIENTATION: [
                _AxisScale(wt.AXIS(0, 3599, wt.TU_CIRCLE, circle)),
                _AxisScale(wt.AXIS(-900, 900, wt.TU_CIRCLE, circle)),
                _AxisScale(wt.AXIS(0, 3599, wt.TU_CIRCLE, circle)),
            ],
        }
        dev._packetClass = wt.makePacketClass(self.pktData)
        return dev

    def makePacket(self, dev, status=0, x=500, y=350, pressure=0, azimuth=0, altitude=900,
                   twist=0, cursor=1, buttons=0):
        pkt = dev._packetClass()
        pkt.pkStatus = status
        pkt.pkTime = 0
        pkt.pkCursor = cursor
        pkt.pkButtons = buttons
        pkt.pkX = x
        pkt.pkY = y
        pkt.pkNormalPressure = pressure
        pkt.pkOrientation.orAzimuth = azimuth
        pkt.pkOrientation.orAltitude = altitude
        pkt.pkOrientation.orTwist = twist
        return pkt

    def test_packet_layout(self):
        fields = [name for name, _ in wt.makePacketClass(self.pktData)._fields_]
        assert fields == [
            "pkStatus", "pkTime", "pkCursor", "pkButtons", "pkX", "pkY", "pkNormalPressure",
            "pkOrientation"
        ]

    def test_screen_to_pix(self):
        dev = self.makeDevice()
        # window's client area is 800x600 at (100, 50) on the screen
        rect = (100, 50, 800, 600)
        assert tuple(dev.screenToPix(500, 350, rect)) == pytest.approx((0, 0))
        assert tuple(dev.screenToPix(100, 50, rect)) == pytest.approx((-400, 300))
        assert tuple(dev.screenToPix(900, 650, rect)) == pytest.approx((400, -300))
        # client area smaller than the framebuffer (e.g. high DPI scaling)
        assert tuple(dev.screenToPix(500, 50, (100, 50, 400, 300))) == pytest.approx((400, 300))

    def test_packets(self):
        dev = self.makeDevice()
        rect = (100, 50, 800, 600)
        samples = dev.packetToSamples(
            self.makePacket(dev, pressure=1023, azimuth=900, altitude=450, twist=100, buttons=1),
            clientRect=rect
        )
        # first packet in range also enters
        assert [s['type'] for s in samples] == ["enter", "sample"]
        sample = samples[1]
        assert tuple(sample['pix']) == pytest.approx((0, 0))
        assert sample['pressure'] == pytest.approx(1)
        assert sample['azimuth'] == pytest.approx(90)
        assert sample['altitude'] == pytest.approx(45)
        assert sample['twist'] == pytest.approx(10)
        assert (sample['tiltX'], sample['tiltY']) == pytest.approx((45, 0), abs=1e-9)
        assert sample['cursor'] == "pen"
        assert sample['buttons'] == 1
        # next packet doesn't enter again
        samples = dev.packetToSamples(self.makePacket(dev), clientRect=rect)
        assert [s['type'] for s in samples] == ["sample"]
        # out of range
        samples = dev.packetToSamples(
            self.makePacket(dev, status=wt.TPS_PROXIMITY), clientRect=rect
        )
        assert [s['type'] for s in samples] == ["leave"]
        assert dev.packetToSamples(
            self.makePacket(dev, status=wt.TPS_PROXIMITY), clientRect=rect
        ) == []

    def test_eraser(self):
        dev = self.makeDevice()
        rect = (100, 50, 800, 600)
        # inverted pen
        samples = dev.packetToSamples(
            self.makePacket(dev, status=wt.TPS_INVERT, altitude=-450), clientRect=rect
        )
        assert samples[-1]['cursor'] == "eraser"
        assert samples[-1]['altitude'] == pytest.approx(45)
        # eraser cursor index
        samples = dev.packetToSamples(self.makePacket(dev, cursor=5), clientRect=rect)
        assert samples[-1]['cursor'] == "eraser"
        samples = dev.packetToSamples(self.makePacket(dev, cursor=3), clientRect=rect)
        assert samples[-1]['cursor'] == "puck"

    def test_parse(self):
        """
        Check that samples from packets are parsed into responses.
        """
        dev = self.makeDevice()
        rect = (100, 50, 800, 600)
        for pressure in (0, 600, 0):
            for sample in dev.packetToSamples(
                    self.makePacket(dev, x=900, y=50, pressure=pressure), clientRect=rect
            ):
                dev.receiveMessage(dev.parseMessage(sample))
        resps = dev.getResponses()
        assert [resp.value for resp in resps] == ["enter", "hover", "down", "up"]
        assert (resps[2].x, resps[2].y) == pytest.approx((400, 300))
        assert resps[2].pressure == pytest.approx(600 / 1023)

    def test_tick_sync(self):
        from psychopy.hardware.pen._wintab import _TickSync
        ticks = [1000]
        sync = _TickSync(lambda: ticks[0])
        t0 = psyclock.getTime()
        # times are mapped onto the PsychoPy clock
        assert sync.toTime(1000) == pytest.approx(t0, abs=0.05)
        assert sync.toTime(1500) - sync.toTime(1000) == pytest.approx(0.5)
        # times from before the reference tick
        assert sync.toTime(900) - sync.toTime(1000) == pytest.approx(-0.1)

    def test_tick_sync_wrap(self):
        """
        Check that tick times are mapped correctly when the 32-bit counter wraps around.
        """
        from psychopy.hardware.pen._wintab import _TickSync
        sync = _TickSync(lambda: 2 ** 32 - 100)
        assert sync.toTime(50) - sync.toTime(2 ** 32 - 100) == pytest.approx(0.15)

    def test_tick_sync_offset(self):
        """
        Check that the offset estimate takes the smallest offset, as the tick counter lags
        behind the true time.
        """
        from psychopy.hardware.pen._wintab import _TickSync
        ticks = [0]
        sync = _TickSync(lambda: ticks[0])
        first = sync.getOffset()
        # counter lagging further behind gives a larger offset, which shouldn't be used
        sync._offsets.append(first + 0.01)
        assert sync.getOffset() == first
        sync._offsets.append(first - 0.002)
        assert sync.getOffset() == first - 0.002


@pytest.mark.skipif(sys.platform != "darwin", reason="Needs pyobjc, on macOS")
class TestCocoa:
    """
    Tests for the parts of the macOS backend which don't need a tablet.
    """
    # HID properties of some devices, as read from the IORegistry
    hidDevices = {
        'trackpad': {
            "Product": "Apple Internal Keyboard / Trackpad", "PrimaryUsagePage": 1,
            "PrimaryUsage": 2, "DeviceUsagePairs": [
                {"DeviceUsagePage": 1, "DeviceUsage": 2},
                {"DeviceUsagePage": 13, "DeviceUsage": 5},
            ],
        },
        'touchscreen': {
            "Product": "Touch screen", "VendorID": 0x1234, "ProductID": 1,
            "PrimaryUsagePage": 13, "PrimaryUsage": 4,
        },
        'keyboard': {
            "Product": "Keyboard", "VendorID": 0x05AC, "ProductID": 2, "PrimaryUsagePage": 1,
            "PrimaryUsage": 6,
        },
        # Wacom tablets use their own usage page, and have several interfaces
        'wacomPen': {
            "Product": "Intuos S", "VendorID": 0x056A, "ProductID": 0x0374,
            "SerialNumber": "ABC123", "LocationID": 1, "PrimaryUsagePage": 0xFF0D,
            "PrimaryUsage": 1,
        },
        'wacomTouch': {
            "Product": "Intuos S", "VendorID": 0x056A, "ProductID": 0x0374,
            "SerialNumber": "ABC123", "LocationID": 1, "PrimaryUsagePage": 13,
            "PrimaryUsage": 5,
        },
        'wacomPen2': {
            "Product": "Intuos S", "VendorID": 0x056A, "ProductID": 0x0374,
            "SerialNumber": "XYZ789", "LocationID": 2, "PrimaryUsagePage": 0xFF0D,
            "PrimaryUsage": 1,
        },
        # a tablet from another maker which describes itself as a pen, but has no name
        'genericPen': {
            "VendorID": 0x1111, "ProductID": 0x2222, "LocationID": 3, "PrimaryUsagePage": 1,
            "PrimaryUsage": 2, "DeviceUsagePairs": [{"DeviceUsagePage": 13, "DeviceUsage": 2}],
        },
    }

    def makeDevice(self, **kwargs):
        from psychopy.hardware.pen._cocoa import CocoaPenDevice
        dev = CocoaPenDevice(win=makeWin(**kwargs))
        dev.resetTimer()
        # treat screen coordinates as being in the window's view, which is 800x600 points
        dev.screenToPix = lambda sx, sy: dev.viewToPix(sx, sy, 800, 600, dev.win)
        return dev

    def test_tablet_interfaces(self):
        from psychopy.hardware.pen._cocoa import isTabletInterface
        found = {name for name, props in self.hidDevices.items() if isTabletInterface(props)}
        # trackpads and touch screens are digitizers too, but not pens
        assert found == {"wacomPen", "wacomTouch", "wacomPen2", "genericPen"}

    def test_attached_tablets(self):
        from psychopy.hardware.pen._cocoa import getAttachedTablets
        devices = [self.hidDevices[name] for name in (
            "trackpad", "keyboard", "wacomPen", "wacomTouch", "touchscreen", "genericPen"
        )]
        assert getAttachedTablets(devices) == [
            # interfaces of the same tablet are combined
            {
                'deviceName': "Intuos S", 'vendorID': 0x056A, 'productID': 0x0374,
                'serialNumber': "ABC123",
            },
            {
                'deviceName': "Pen tablet (1111:2222)", 'vendorID': 0x1111, 'productID': 0x2222,
                'serialNumber': "",
            },
        ]
        assert getAttachedTablets([self.hidDevices['trackpad']]) == []

    def test_same_model_tablets(self):
        """
        Check that two tablets of the same model are listed separately, with different names.
        """
        from psychopy.hardware.pen._cocoa import getAttachedTablets
        tablets = getAttachedTablets([self.hidDevices['wacomPen'], self.hidDevices['wacomPen2']])
        assert [tablet['deviceName'] for tablet in tablets] == [
            "Intuos S (ABC123)", "Intuos S (XYZ789)"
        ]

    def test_system_tablets(self):
        """
        Check that tablets can be listed from the system (whether or not there are any).
        """
        from psychopy.hardware.pen._cocoa import CocoaPenDevice
        profiles = CocoaPenDevice.getAvailableDevices()
        assert isinstance(profiles, list)
        for profile in profiles:
            assert set(profile) == {'deviceName', 'vendorID', 'productID', 'serialNumber'}

    def test_init_from_profile(self, monkeypatch):
        from psychopy.hardware.pen import _cocoa
        from psychopy.hardware.exceptions import DeviceNotConnectedError
        tablets = _cocoa.getAttachedTablets(
            [self.hidDevices['wacomPen'], self.hidDevices['wacomPen2']]
        )
        monkeypatch.setattr(_cocoa, "getAttachedTablets", lambda: tablets)
        # with no details, the first tablet is used
        dev = _cocoa.CocoaPenDevice(win=makeWin())
        assert dev.getDeviceProfile()['deviceName'] == "Intuos S (ABC123)"
        # with details, the matching tablet is used
        kwargs = {key: val for key, val in tablets[1].items() if key != "deviceName"}
        dev2 = _cocoa.CocoaPenDevice(win=makeWin(), **kwargs)
        assert dev2.getDeviceProfile()['deviceName'] == "Intuos S (XYZ789)"
        assert not dev.isSameDevice(dev2)
        # serial numbers are only compared if both have one
        assert dev.isSameDevice({'vendorID': 0x056A, 'productID': 0x0374})
        assert not dev.isSameDevice({'vendorID': 0x056A, 'productID': 0x0375})
        # a tablet which isn't attached
        with pytest.raises(DeviceNotConnectedError):
            _cocoa.CocoaPenDevice(win=makeWin(), vendorID=0x056A, productID=0x0999)

    def test_init_no_tablets(self, monkeypatch):
        """
        Check that, with no tablets found, a device is still made (as events from tablets which
        weren't detected still come through).
        """
        from psychopy.hardware.pen import _cocoa
        monkeypatch.setattr(_cocoa, "getAttachedTablets", lambda: [])
        dev = _cocoa.CocoaPenDevice(win=makeWin())
        assert dev.vendorID is None
        assert dev.getDeviceProfile() is None

    def test_view_to_pix(self):
        from psychopy.hardware.pen._cocoa import CocoaPenDevice
        win = makeWin(size=(1600, 1200), pixScaleFactor=2.0)
        # center of an 800x600 point view
        assert tuple(CocoaPenDevice.viewToPix(400, 300, 800, 600, win)) == pytest.approx((0, 0))
        # top right
        assert tuple(CocoaPenDevice.viewToPix(800, 600, 800, 600, win)) == pytest.approx(
            (400, 300)
        )

    def test_raw_to_sample(self):
        import AppKit
        dev = self.makeDevice()
        offset = dev.clock.getLastResetTime()
        raws = [
            ("proximity", 1.0, True, AppKit.NSPointingDeviceTypeEraser),
            ("point", 1.5, 400, 300, 0.75, 0.0, 0.5, -0.5, 12.0, 3, 1),
            ("point", 1.5, 400, 300, 0.75, 0.0, 0.5, -0.5, 12.0, 3, 1),
            ("proximity", 2.0, False, 0),
        ]
        for raw in raws:
            dev.receiveMessage(dev.parseMessage(dev.rawToSample(raw, offset)))
        resps = dev.getResponses()
        assert [resp.value for resp in resps] == ["enter", "down", "move", "leave"]
        assert [resp.t for resp in resps] == pytest.approx([1.0, 1.5, 1.5, 2.0])
        down = resps[1]
        assert down.cursor == "eraser"
        assert (down.x, down.y) == pytest.approx((0, 0))
        assert down.pressure == 0.75
        # tilt of +/-1 is the maximum tilt, and positive y is towards the top
        assert (down.tiltX, down.tiltY) == pytest.approx((30, 30))
        assert down.azimuth == pytest.approx(45)
        assert down.twist == 12.0
        assert down.z == 3
        assert down.buttons == 1

    @pytest.mark.parametrize("winType", ["pyglet", "glfw"])
    def test_real_events(self, winType):
        """
        Post tablet events to the app's own event queue (as the tablet driver would) and check
        that they come out of the device.
        """
        import AppKit
        import Quartz
        from psychopy import visual, core
        from psychopy.hardware.pen._cocoa import CocoaPenDevice

        def makeEvent(kind, x, y, pressure, tiltX, tiltY, buttons,
                      subtype=Quartz.kCGEventMouseSubtypeTabletPoint):
            # Quartz has its origin at the top left of the main screen, Cocoa the bottom left
            screenH = AppKit.NSScreen.screens()[0].frame().size.height
            ev = Quartz.CGEventCreateMouseEvent(
                None, kind, (x, screenH - y), Quartz.kCGMouseButtonLeft
            )
            Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventSubtype, subtype)
            Quartz.CGEventSetDoubleValueField(ev, Quartz.kCGMouseEventPressure, pressure)
            Quartz.CGEventSetDoubleValueField(ev, Quartz.kCGTabletEventPointPressure, pressure)
            Quartz.CGEventSetDoubleValueField(ev, Quartz.kCGTabletEventTiltX, tiltX)
            Quartz.CGEventSetDoubleValueField(ev, Quartz.kCGTabletEventTiltY, tiltY)
            Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGTabletEventPointButtons, buttons)
            # event times are nanoseconds since the system started
            Quartz.CGEventSetTimestamp(
                ev, int(AppKit.NSProcessInfo.processInfo().systemUptime() * 1e9)
            )
            return AppKit.NSEvent.eventWithCGEvent_(ev)

        win = visual.Window(size=(400, 300), units="pix", winType=winType, fullscr=False)
        try:
            win.flip()
            dev = CocoaPenDevice(win=win)
            dev.resetTimer()
            # center of the window on the screen
            view = dev._nsWindow.contentView()
            frame = dev._nsWindow.convertRectToScreen_(view.convertRect_toView_(view.bounds(), None))
            cx = frame.origin.x + frame.size.width / 2
            cy = frame.origin.y + frame.size.height / 2
            app = AppKit.NSApplication.sharedApplication()
            events = [
                (Quartz.kCGEventMouseMoved, cx, cy, 0.0, 0.0, 0.0, 0),
                (Quartz.kCGEventLeftMouseDown, cx + 50, cy + 25, 0.5, 0.5, 0.0, 1),
                (Quartz.kCGEventLeftMouseDragged, cx + 100, cy - 50, 0.9, 0.0, -0.5, 1),
                (Quartz.kCGEventLeftMouseUp, cx + 100, cy - 50, 0.0, 0.0, 0.0, 0),
            ]
            for event in events:
                app.postEvent_atStart_(makeEvent(*event), False)
                core.wait(0.01)
            # mouse events which aren't from a tablet should be ignored
            app.postEvent_atStart_(makeEvent(
                Quartz.kCGEventMouseMoved, cx, cy, 0, 0, 0, 0,
                subtype=Quartz.kCGEventMouseSubtypeDefault
            ), False)
            resps = dev.getResponses()
            dev.close()
        finally:
            win.close()
        assert [resp.value for resp in resps] == ["hover", "down", "move", "up"]
        assert [(resp.x, resp.y) for resp in resps] == pytest.approx(
            [(0, 0), (50, 25), (100, -50), (100, -50)]
        )
        # macOS stores pressure and tilt to 8 bits
        assert [resp.pressure for resp in resps] == pytest.approx([0, 0.5, 0.9, 0], abs=0.01)
        assert (resps[1].tiltX, resps[2].tiltY) == pytest.approx((30, 30), abs=0.5)
        assert [resp.buttons for resp in resps] == [0, 1, 1, 0]
        # times come from the events, ~10ms apart, even though they were read later
        gaps = np.diff([resp.t for resp in resps])
        assert all(0.008 < gap < 0.05 for gap in gaps)
