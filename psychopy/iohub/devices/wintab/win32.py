# -*- coding: utf-8 -*-
# Part of the PsychoPy library
# Copyright (C) 2012-2020 iSolver Software Solutions (C) 2021 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

# Initial file based on pyglet.libs.win32
# Tablet related class definitions
import pyglet
from pyglet.event import EventDispatcher
import ctypes
from ...errors import print2err
from ...constants import EventConstants

lib = ctypes.windll.wintab32

# Wintab types, structures and constants are shared with psychopy.hardware.pen
from psychopy.tools.wintab import *  # noqa: F401,F403


def print_struct(s, pretxt=''):
    print2err('{}{}:'.format(pretxt, s))
    for field_name, field_type in s._fields_:
        print2err('\t{}:\t{}'.format(field_name, getattr(s, field_name)))
    print2err('<<<<<<<<')


def struct2dict(s):
    csdict = {}
    for field_name, field_type in s._fields_:
        ufield_name = field_name
        if field_name.startswith('ax'):
            ufield_name = field_name[2:].lower()
        csdict[ufield_name] = getattr(s, field_name)
    return csdict


DEFAULT_PACKET_DATA_FIELDS = (
    PK_STATUS | PK_TIME | PK_CHANGED |
    PK_SERIAL_NUMBER | PK_CURSOR | PK_BUTTONS |
    PK_X | PK_Y | PK_Z |
    PK_NORMAL_PRESSURE |
    PK_ORIENTATION)


class PACKET(ctypes.Structure):
    _fields_ = (
        ('pkStatus', UINT),
        ('pkTime', LONG),
        ('pkChanged', WTPKT),
        ('pkSerialNumber', UINT),
        ('pkCursor', UINT),
        ('pkButtons', DWORD),
        ('pkX', LONG),
        ('pkY', LONG),
        ('pkZ', LONG),
        ('pkNormalPressure', UINT),
        ('pkOrientation', ORIENTATION)
    )


def wtinfo(category, index, buffer):
    size = lib.WTInfoW(category, index, None)
    assert size <= ctypes.sizeof(buffer)
    lib.WTInfoW(category, index, ctypes.byref(buffer))
    return buffer


def wtinfo_string(category, index):
    size = lib.WTInfoW(category, index, None)
    buffer = ctypes.create_unicode_buffer(size)
    lib.WTInfoW(category, index, buffer)
    return buffer.value


def wtinfo_uint(category, index):
    buffer = UINT()
    lib.WTInfoW(category, index, ctypes.byref(buffer))
    return buffer.value


def wtinfo_word(category, index):
    buffer = WORD()
    lib.WTInfoW(category, index, ctypes.byref(buffer))
    return buffer.value


def wtinfo_dword(category, index):
    buffer = DWORD()
    lib.WTInfoW(category, index, ctypes.byref(buffer))
    return buffer.value


def wtinfo_wtpkt(category, index):
    buffer = WTPKT()
    lib.WTInfoW(category, index, ctypes.byref(buffer))
    return buffer.value


def wtinfo_bool(category, index):
    buffer = BOOL()
    lib.WTInfoW(category, index, ctypes.byref(buffer))
    return bool(buffer.value)


class Win32Wintab:
    '''High-level interface to tablet devices.

    Unlike other devices, tablets must be opened for a specific window,
    and cannot be opened exclusively.  The `open` method returns a
    `TabletCanvas` object, which supports the events provided by the tablet.

    Currently only one tablet device can be used, though it can be opened on
    multiple windows.  If more than one tablet is connected, the behaviour is
    undefined.
    '''

    def __init__(self, index):
        self._device = WTI_DEVICES + index
        self.name = wtinfo_string(self._device, DVC_NAME).strip()
        self.id = wtinfo_string(self._device, DVC_PNPID)
        self.hardware_type = wtinfo_uint(self._device, DVC_HARDWARE)

        self.hw_model_info = dict()
        self.hw_model_info['name'] = self.name
        self.hw_model_info['id'] = self.id
        self.hw_model_info['type'] = self.hardware_type
        self.hw_model_info['handle'] = self._device

        #phys_cursors = hardware & HWC_PHYSID_CURSORS

        n_cursors = wtinfo_uint(self._device, DVC_NCSRTYPES)
        first_cursor = wtinfo_uint(self._device, DVC_FIRSTCSR)

        self.hw_axis_info = dict()

        self._x_axis = wtinfo(self._device, DVC_X, AXIS())
        self._y_axis = wtinfo(self._device, DVC_Y, AXIS())
        self._z_axis = wtinfo(self._device, DVC_Z, AXIS())

        self.tip_pressure_axis = wtinfo(self._device, DVC_NPRESSURE,
                                        AXIS())
        # self.barrel_pressure_axis = wtinfo(self._device, DVC_TPRESSURE,
        #                            AXIS())

        self.orient_axis = wtinfo(self._device, DVC_ORIENTATION,
                                  (AXIS * 3)())

        # self.rotation_axis = wtinfo(self._device, DVC_ROTATION,
        #                          (AXIS*3)())

        self.hw_axis_info['x'] = struct2dict(self._x_axis)
        self.hw_axis_info['y'] = struct2dict(self._y_axis)
        self.hw_axis_info['z'] = struct2dict(self._z_axis)
        # seems that z axis min value is being reported as -1023,
        # but it is never < 0 in PACKET field, so setting z min to 0
        #print2err("z axis: ", self.hw_axis_info['z'])
        self.hw_axis_info['z']['min'] = 0

        self.hw_axis_info['pressure'] = struct2dict(self.tip_pressure_axis)
        #self.hw_axis_info['barrel_pressure_axis'] = struct2dict(self.barrel_pressure_axis)
        self.hw_axis_info['orient_azimuth'] = struct2dict(self.orient_axis[0])
        self.hw_axis_info['orient_altitude'] = struct2dict(self.orient_axis[1])
        self.hw_axis_info['orient_twist'] = struct2dict(self.orient_axis[2])
        #self.hw_axis_info['rotation_pitch_axis'] = struct2dict(self.rotation_axis[0])
        #self.hw_axis_info['rotation_roll_axis'] = struct2dict(self.rotation_axis[1])
        #self.hw_axis_info['rotation_yaw_axis'] = struct2dict(self.rotation_axis[2])

        self.cursors = []
        self._cursor_map = {}

        for i in range(n_cursors):
            cursor = Win32WintabCursor(self, i + first_cursor)
            if not cursor.bogus:
                self.cursors.append(cursor)
                self._cursor_map[i + first_cursor] = cursor

    def open(self, window, iohub_wt_device):
        """Open a tablet device for a window.

        :Parameters:
            `window` : `Window`
                The window on which the tablet will be used.

        :rtype: `Win32WintabCanvas`

        """
        Win32WintabCanvas.iohub_wt_device = iohub_wt_device
        pc = Win32WintabCanvas(self, window)
        return pc


class Win32WintabCanvas(EventDispatcher):
    """Event dispatcher for tablets.

    Use `Tablet.open` to obtain this object for a particular tablet device and
    window.  Events may be generated even if the tablet stylus is outside of
    the window; this is operating-system dependent.

    The events each provide the `TabletCursor` that was used to generate the
    event; for example, to distinguish between a stylus and an eraser.  Only
    one cursor can be used at a time, otherwise the results are undefined.

    :Ivariables:
        `window` : Window
            The window on which this tablet was opened.

    """
    iohub_wt_device = None

    def __init__(self, device, window, msg_base=WT_DEFBASE):
        super(Win32WintabCanvas, self).__init__()
        self.window = window

        self.device = device
        self.msg_base = msg_base

        self._iohub_events = []

        # TODO: Let user determine if raw or pixel coords should be used for
        #       x,y pos fields. i.e. WTI_DEFCONTEXT == raw,
        #       WTI_DEFSYSCTX == pix
        self.context_info = context_info = LOGCONTEXT()
        #wtinfo(WTI_DEFSYSCTX, 0, context_info)
        wtinfo(WTI_DEFCONTEXT, 0, context_info)
        context_info.lcMsgBase = msg_base
        context_info.lcOptions |= CXO_MESSAGES

        # If you change this, change definition of PACKET also.
        context_info.lcPktData = DEFAULT_PACKET_DATA_FIELDS
        context_info.lcPktMode = 0   # All absolute

        # set output scaling, right now, out == in
        # TODO: determine what coord space we want to output in.
        context_info.lcOutOrgX = context_info.lcOutOrgY = 0

        # Set the entire tablet as active
        context_info.lcInOrgX = 0
        context_info.lcInOrgY = 0
        context_info.lcInOrgZ = 0
        context_info.lcInExtX = self.device._x_axis.axMax
        context_info.lcInExtY = self.device._y_axis.axMax
        context_info.lcInExtZ = self.device._z_axis.axMax

        context_info.lcOutOrgX = context_info.lcInOrgX
        context_info.lcOutOrgY = context_info.lcInOrgY
        context_info.lcOutOrgZ = context_info.lcInOrgZ
        # INT(scale[0] * context_info.lcInExtX);
        context_info.lcOutExtX = context_info.lcInExtX
        # INT(scale[1] * context_info.lcInExtY);
        context_info.lcOutExtY = context_info.lcInExtY
        # INT(scale[1] * context_info.lcInExtY);
        context_info.lcOutExtZ = context_info.lcInExtZ

        self._context = lib.WTOpenW(window._hwnd,
                                    ctypes.byref(context_info),
                                    self.iohub_wt_device.getConfiguration().
                                    get('auto_report_events', False))
        if not self._context:
            print2err("Couldn't open tablet context.")
        window._event_handlers[msg_base + WT_PACKET] = self._event_wt_packet
        window._event_handlers[msg_base + WT_PROXIMITY] = self._event_wt_proximity

        self._current_cursor = None
        #self._pressure_scale = device.tip_pressure_axis.get_scale()
        #self._pressure_bias = device.tip_pressure_axis.get_bias()

    def getContextInfo(self):
        return struct2dict(self.context_info)

    def enable(self, enable=True):
        lib.WTEnable(self._context, enable)

    def close(self):
        lib.WTClose(self._context)
        self._context = None
        del self.window._event_handlers[self.msg_base + WT_PACKET]
        del self.window._event_handlers[self.msg_base + WT_PROXIMITY]

    def _set_current_cursor(self, cursor_type):
        self._current_cursor = self.device._cursor_map.get(cursor_type, None)

        if self._current_cursor:
            self.addHubEvent(None, EventConstants.WINTAB_ENTER_REGION)

    def addHubEvent(
            self,
            packet,
            evt_type=EventConstants.WINTAB_SAMPLE):
        # TODO: Display (screen) index
        #display_id = 0
        #window_id = self.window._hwnd

        #ccursor = self._current_cursor
        #if ccursor is None:
        #    ccursor = 0
        #else:
        #    ccursor = ccursor._cursor

        if packet is None or evt_type != EventConstants.WINTAB_SAMPLE:
            cevt = [evt_type,
                    0,
                    0,
                    0,
                    0,
                    0,  # ('x',N.int32),
                    0,  # ('y',N.int32),
                    0,  # ('z',N.int32),
                    0,  # ('pressure',N.uint32),
                    0,  # ('orient_azimuth',N.int32),
                    0,  # ('orient_altitude;',N.int32),
                    0,  # ('orient_twist',N.int32),
                    0  # ('status', N.uint8)
                    ]
        else:
            cevt = [evt_type,
                    packet.pkTime / 1000.0,
                    packet.pkStatus,
                    packet.pkSerialNumber,
                    packet.pkButtons,
                    packet.pkX,  # ('x',N.int32),
                    packet.pkY,  # ('y',N.int32),
                    packet.pkZ,  # ('z',N.int32),
                    #(packet.pkNormalPressure + self._pressure_bias) * \
                    #            self._pressure_scale,
                    packet.pkNormalPressure,  # ('pressure',N.uint32),
                    # ('orient_azimuth',N.int32),
                    packet.pkOrientation.orAzimuth,
                    # ('orient_altitude;',N.int32),
                    packet.pkOrientation.orAltitude,
                    packet.pkOrientation.orTwist,  # ('orient_twist',N.int32),
                    0  # ('status', N.uint8)
                    ]
        self._iohub_events.append(cevt)

    @pyglet.window.win32.Win32EventHandler(0)
    def _event_wt_packet(self, msg, wParam, lParam):
        if lParam != self._context:
            return

        packet = PACKET()
        if lib.WTPacket(self._context, wParam, ctypes.byref(packet)) == 0:
            return

        if not packet.pkChanged:
            return

        if self._current_cursor is None:
            self._set_current_cursor(packet.pkCursor)

        self.addHubEvent(packet)

    @pyglet.window.win32.Win32EventHandler(0)
    def _event_wt_proximity(self, msg, wParam, lParam):
        if wParam != self._context:
            return

        if lParam & 0xffff:
            # Proximity Enter Event
            # If going in, proximity event will be generated by next event, which
            # can actually grab a cursor id, so evt is generated when
            # _set_current_cursor() is called with a non None cursor.
            pass
        else:
            # Proximity Leave Event
            self.addHubEvent(None, EventConstants.WINTAB_LEAVE_REGION)
            self._current_cursor = None


class Win32WintabCursor:

    def __init__(self, device, index):
        self.device = device
        self._cursor = WTI_CURSORS + index

        self.name = wtinfo_string(self._cursor, CSR_NAME).strip()
        self.active = wtinfo_bool(self._cursor, CSR_ACTIVE)
        pktdata = wtinfo_wtpkt(self._cursor, CSR_PKTDATA)

        # A whole bunch of cursors are reported by the driver, but most of
        # them are hogwash.  Make sure a cursor has at least X and Y data
        # before adding it to the device.
        self.bogus = not (pktdata & PK_X and pktdata & PK_Y)
        if self.bogus:
            return

        self.id = (wtinfo_dword(self._cursor, CSR_TYPE) << 32) | \
            wtinfo_dword(self._cursor, CSR_PHYSID)

    def __repr__(self):
        return 'WintabCursor(%r)' % self.name


def get_spec_version():
    spec_version = wtinfo_word(WTI_INTERFACE, IFC_SPECVERSION)
    return spec_version


def get_interface_name():
    interface_name = wtinfo_string(WTI_INTERFACE, IFC_WINTABID)
    return interface_name


def get_implementation_version():
    impl_version = wtinfo_word(WTI_INTERFACE, IFC_IMPLVERSION)
    return impl_version


def get_tablets():
    # Require spec version 1.1 or greater
    if get_spec_version() < 0x101:
        return []

    n_devices = wtinfo_uint(WTI_INTERFACE, IFC_NDEVICES)
    devices = [Win32Wintab(i) for i in range(n_devices)]
    return devices
