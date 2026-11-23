# -*- coding: utf-8 -*-
# Part of the PsychoPy library
# Copyright (C) 2012-2020 iSolver Software Solutions (C) 2021 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

import sys

from psychopy import logging
from psychopy.iohub.client import ioHubDeviceView, DeviceRPC


class EyeTracker(ioHubDeviceView):
    """Experiment-process view of an ioHub eye tracker device.

    Behaves like a plain `ioHubDeviceView` (every public device method is
    forwarded to the ioHub server), except that `runSetupProcedure` can draw
    the calibration in the experiment's own window.
    """
    # tell ioHubConnection._addDeviceView to pass the full device class path
    _acceptsDeviceClassPath = True

    def __init__(self, ioclient, dev_cls_name, dev_config, device_class_path=None):
        # Keep the real device class path (unlike the Keyboard view);
        # EyetrackerCalibration uses getIOHubDeviceClass(full=True) to find the
        # tracker class.
        super().__init__(ioclient, device_class_path or dev_cls_name,
                         dev_cls_name, dev_config)

    def _rpc(self, methodName, *args, **kwargs):
        """Call a method of the device on the ioHub server."""
        return DeviceRPC(self.hubClient._sendToHubServer, self.device_class,
                         methodName)(*args, **kwargs)

    def supportsClientCalibration(self):
        """Whether this tracker's calibration can be drawn in the experiment
        window (see `runSetupProcedure`).

        Returns
        -------
        bool
        """
        if 'supportsClientCalibration' not in self._methods:
            return False
        return bool(self._rpc('supportsClientCalibration'))

    def runSetupProcedure(self, calibration_args=None, win=None, target=None,
                          keyboard=None):
        """Run the eye tracker calibration.

        Parameters
        ----------
        calibration_args : dict or None
            Calibration settings, merged over the tracker's calibration
            config (e.g. `dict(EyetrackerCalibration(...))`).
        win : psychopy.visual.Window or None
            If given, draw the calibration in this window from the experiment
            process. Trackers that don't support this fall back to the ioHub
            server's own calibration window (with a warning), minimising `win`
            while it runs. If None, the ioHub server's calibration window is
            used.
        target : psychopy.visual.TargetStim or None
            Target to draw when `win` is given. If None, one is created from
            the calibration settings.
        keyboard : psychopy.hardware.keyboard.Keyboard or None
            Keyboard to read SPACE / ESCAPE from when `win` is given. If None,
            a default `Keyboard` is used.

        Returns
        -------
        dict or int
            Tracker-specific calibration result.
        """
        if win is None:
            return self._runServerSetupProcedure(calibration_args)

        if self.supportsClientCalibration():
            from .calibration import ClientCalibrationProcedure
            procedure = ClientCalibrationProcedure(
                win, self, calibration_args, target=target, keyboard=keyboard)
            return procedure.run()

        logging.warning(
            "Eye tracker '{}' can't draw its calibration in the experiment "
            "window; using a separate calibration window instead.".format(
                self.getIOHubDeviceClass(full=True)))
        # The experiment process blocks (and stops drawing) during the server
        # calibration, so get the fullscreen window out of the way.
        hide = win._isFullScr and sys.platform == 'win32'
        if hide:
            win.winHandle.set_fullscreen(False)
            win.winHandle.minimize()
        try:
            return self._runServerSetupProcedure(calibration_args)
        finally:
            if hide:
                win.winHandle.set_fullscreen(True)
                win.winHandle.maximize()
                win.winHandle.activate()
            win.flip()

    def _runServerSetupProcedure(self, calibration_args=None):
        # Don't send None: some trackers' runSetupProcedure doesn't accept it
        if calibration_args is None:
            return self._rpc('runSetupProcedure')
        return self._rpc('runSetupProcedure', calibration_args)
