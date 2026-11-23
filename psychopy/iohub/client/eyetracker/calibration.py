# -*- coding: utf-8 -*-
# Part of the PsychoPy library
# Copyright (C) 2012-2020 iSolver Software Solutions (C) 2021 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

"""Eye tracker calibration drawn in the experiment's own window.

The experiment process draws the intro screen, the targets and the finished
screen in the experiment window, and reads SPACE / ESCAPE with a
`psychopy.hardware.keyboard.Keyboard`. The ioHub server only talks to the
tracker, through the RPC methods `startClientCalibration`,
`registerClientCalibrationPoint` and `finishClientCalibration` of
`psychopy.iohub.devices.eyetracker.EyeTrackerDevice`.
"""

import copy
import random

from psychopy import core, layout, logging
from psychopy.constants import PLAYING
# same point layouts (normalised, origin top-left) as the server-side procedure
from psychopy.iohub.devices.eyetracker.calibration.procedure import (
    target_positions, target_position_count, legacyTargetStim)

INTRO_TEXT = 'Press SPACE to Start Calibration; ESCAPE to Exit.'
FINISHED_TEXT = "Calibration Complete. Press 'SPACE' key to continue."

_ABORTED = {"RESULT": "CALIBRATION_ABORTED"}


def minimumJerk(t):
    """Minimum-jerk interpolation factor for t in [0, 1]."""
    return 60.0 * ((1.0 / 10.0) * t ** 5 - (1.0 / 4.0) * t ** 4 +
                   (1.0 / 6.0) * t ** 3)


def normToWindowUnits(win, point, units):
    """Convert a normalised calibration point to window coordinates.

    Parameters
    ----------
    win : psychopy.visual.Window
    point : (x, y)
        Position as a fraction of the window, origin top-left, y down.
    units : str
        Units to return the position in.

    Returns
    -------
    tuple of float
    """
    x = point[0] * 2.0 - 1.0
    y = 1.0 - point[1] * 2.0
    pos = getattr(layout.Position((x, y), 'norm', win), units)
    return float(pos[0]), float(pos[1])


def calibrationPoints(calType, randomize, rng=None):
    """Calibration points for a layout, optionally shuffled.

    The first point is never moved when randomising, matching the ioHub
    server's calibration.

    Parameters
    ----------
    calType : str
        One of THREE_POINTS, FIVE_POINTS, NINE_POINTS or THIRTEEN_POINTS.
        Anything else gives NINE_POINTS.
    randomize : bool
    rng : random.Random or None

    Returns
    -------
    list of (x, y)
    """
    points = list(target_positions[target_position_count.get(calType, 9)])
    if randomize:
        rest = points[1:]
        (rng or random).shuffle(rest)
        points = points[:1] + rest
    return points


class ClientCalibrationProcedure:
    """Run an eye tracker calibration in the experiment's window.

    Normally created by `EyeTracker.runSetupProcedure(win=win)` rather than
    directly.

    Parameters
    ----------
    win : psychopy.visual.Window
        Window to draw the calibration in.
    tracker : psychopy.iohub.client.eyetracker.EyeTracker
        Eye tracker device view.
    calibration_args : dict or None
        Calibration settings, merged over the tracker's calibration config.
    target : psychopy.visual.TargetStim or None
        Target to draw. If None, one is created from the calibration settings.
    keyboard : psychopy.hardware.keyboard.Keyboard or None
        Keyboard to read SPACE / ESCAPE from. If None, a default one is used.
    """

    def __init__(self, win, tracker, calibration_args=None, target=None,
                 keyboard=None):
        self.win = win
        self.tracker = tracker
        self.calibrationArgs = dict(calibration_args or {})

        # merge the call's settings over the tracker's calibration config, the
        # same way the server-side procedure does
        config = tracker.getConfiguration() or {}
        settings = copy.deepcopy(config.get('calibration') or {})
        settings.update(self.calibrationArgs)
        self.settings = settings

        animate = (settings.get('target_attributes') or {}).get('animate') or {}
        self.animateMovement = bool(animate.get('enable', False))
        self.expansionRatio = float(animate.get('expansion_ratio') or 1.0)
        self.contractOnly = bool(animate.get('contract_only', False))
        self.targetDelay = float(settings.get('target_delay', 0.75))
        self.targetDuration = float(settings.get('target_duration', 1.5))
        # matches the server: only an explicit False means manual pacing
        self.autoPace = settings.get('auto_pace', True) is not False

        self.target = target if target is not None else self._createTarget()
        self.keyboard = keyboard
        self.textStim = None

    # --- setup ----------------------------------------------------------

    def _createTarget(self):
        from psychopy import visual
        from psychopy.tools.stimulustools import actualize

        attrs = dict(self.settings.get('target_attributes') or {})
        attrs.pop('animate', None)
        if '__class__' in attrs:
            # serialized stimulus, e.g. from EyetrackerCalibration
            attrs['win'] = self.win
            return actualize(attrs)
        if attrs:
            # YAML-style target settings (outer_diameter etc.), e.g. the
            # tracker's defaults
            return legacyTargetStim(
                self.win, attrs, units=self.settings.get('unit_type'),
                colorSpace=self.settings.get('color_type'))
        return visual.TargetStim(self.win, name='calibrationTarget',
                                 radius=20, innerRadius=6, units='pix')

    def _createText(self):
        from psychopy import visual
        from psychopy.colors import Color

        color = self.settings.get('text_color')
        colorSpace = self.settings.get('color_type') or self.win.colorSpace
        if color is None:
            # contrast with the window background, like the server does
            from psychopy.iohub.util import complement
            bg = Color(self.win.color, self.win.colorSpace)
            color = complement(*bg.rgb255)
            colorSpace = 'rgb255'
        aspect = self.win.size[0] / float(self.win.size[1])
        return visual.TextStim(
            self.win, text='', pos=(0, 0), units='height', height=0.04,
            color=color, colorSpace=colorSpace, wrapWidth=aspect * 0.9)

    def _getKeyboard(self):
        if self.keyboard is None:
            from psychopy.hardware.keyboard import Keyboard
            self.keyboard = Keyboard()
        return self.keyboard

    # --- input / drawing helpers ------------------------------------------

    def _pollKeys(self):
        """Names of SPACE / ESCAPE keys pressed since the last poll."""
        keys = self._getKeyboard().getKeys(
            keyList=['space', 'escape'], waitRelease=False)
        return [k.name for k in keys]

    def _showText(self, text, allowEscape=True):
        """Show text until SPACE (returns True) or ESCAPE (returns False)."""
        if self.textStim is None:
            self.textStim = self._createText()
        self.textStim.text = text
        while True:
            self.textStim.draw()
            self.win.flip()
            keys = self._pollKeys()
            if 'space' in keys:
                return True
            if allowEscape and 'escape' in keys:
                return False

    def _activateWindow(self):
        """Try to give the window keyboard focus.

        Keyboard backends that read window events only get keys while the
        window has focus, and other programs (e.g. eye tracker software
        started by ioHub) can take it. The OS may refuse if another program
        is in active use.
        """
        winHandle = getattr(self.win, 'winHandle', None)
        activate = getattr(winHandle, 'activate', None)
        if callable(activate):
            try:
                activate()
            except Exception:  # noqa: BLE001
                logging.debug("Could not activate the calibration window.")

    def _targetUnits(self):
        return getattr(self.target, 'units', None) or self.win.units

    def _hasPlayPause(self):
        return hasattr(self.target, 'play') and hasattr(self.target, 'pause')

    def _drawTargetAt(self, pos):
        self.target.pos = pos
        self.target.draw()
        self.win.flip()

    # --- calibration ------------------------------------------------------

    def run(self):
        """Run the calibration.

        Returns
        -------
        dict
            Calibration result from the tracker, e.g.
            ``{"RESULT": "CALIBRATION_OK"}``.
        """
        originalPos = self.target.pos
        originalSize = self.target.size
        mouseVisible = getattr(self.win, 'mouseVisible', True)
        self.win.mouseVisible = False
        self._activateWindow()
        self._getKeyboard().clearEvents()
        started = finished = False
        try:
            if not self._showText(INTRO_TEXT):
                return dict(_ABORTED)

            points = calibrationPoints(self.settings.get('type'),
                                       self.settings.get('randomize') is True)
            session = self.tracker.startClientCalibration(
                self._serverArgs(), [list(p) for p in points])
            if not isinstance(session, dict):
                raise RuntimeError(
                    "Eye tracker could not start the calibration "
                    "(startClientCalibration returned {!r}).".format(session))
            started = True
            allowEscape = session.get('allow_escape', True)

            aborted = self._presentTargets(points, allowEscape)

            self.win.flip()  # clear the last target
            result = self.tracker.finishClientCalibration(aborted)
            finished = True
            if not aborted:
                self._showText(FINISHED_TEXT)
            return result
        finally:
            if started and not finished:
                # make sure the tracker leaves calibration mode
                try:
                    self.tracker.finishClientCalibration(True)
                except Exception:  # noqa: BLE001
                    logging.error("Could not finish the eye tracker calibration "
                                  "after an error.")
            if self._hasPlayPause():
                self.target.pause()
            self.target.size = originalSize
            self.target.pos = originalPos
            self.win.mouseVisible = mouseVisible
            self.win.flip()
            self._getKeyboard().clearEvents()

    def _serverArgs(self):
        """Calibration args for the server (the target is drawn here)."""
        args = dict(self.calibrationArgs)
        args.pop('target_attributes', None)
        return args

    def _presentTargets(self, points, allowEscape):
        """Show each target and register it with the tracker.

        Returns
        -------
        bool
            True if the calibration was aborted.
        """
        units = self._targetUnits()
        positions = [normToWindowUnits(self.win, pt, units) for pt in points]
        baseSize = self.target.size

        for i, (pt, pos) in enumerate(zip(points, positions)):
            # delay before the target, moving it from the previous point
            start = core.getTime()
            while core.getTime() - start <= self.targetDelay:
                if self.animateMovement and i > 0:
                    t = minimumJerk((core.getTime() - start) / self.targetDelay)
                    prev = positions[i - 1]
                    self._drawTargetAt((prev[0] + t * (pos[0] - prev[0]),
                                        prev[1] + t * (pos[1] - prev[1])))
                else:
                    if self._hasPlayPause() and self.target.status == PLAYING:
                        self.target.pause()
                    self.win.flip()
                if allowEscape and 'escape' in self._pollKeys():
                    return True

            # show the target, expanding / contracting it
            self.target.size = baseSize
            if self._hasPlayPause() and self.target.status != PLAYING:
                self.target.play()
            self._drawTargetAt(pos)
            self._animateTargetSize(baseSize)

            if not self.autoPace:
                # wait for SPACE before registering the point
                while True:
                    self.target.draw()
                    self.win.flip()
                    keys = self._pollKeys()
                    if 'space' in keys:
                        break
                    if allowEscape and 'escape' in keys:
                        return True
            elif allowEscape and 'escape' in self._pollKeys():
                return True

            self.tracker.registerClientCalibrationPoint(list(pt))
            self.win.flip()
        return False

    def _animateTargetSize(self, baseSize):
        """Expand / contract the target for the target duration."""
        size = float(baseSize[0])
        minSize = size / self.expansionRatio
        if hasattr(self.target, 'minSize'):
            minSize = float(self.target.minSize[0])
        maxSize = size * self.expansionRatio
        half = self.targetDuration / 2.0

        start = core.getTime()
        while core.getTime() - start <= self.targetDuration:
            elapsed = core.getTime() - start
            newSize = None
            if self.contractOnly:
                t = elapsed / self.targetDuration
                newSize = size - t * (size - minSize)
            elif self.expansionRatio != 1.0:
                if elapsed <= half:
                    newSize = size + (elapsed / half) * (maxSize - size)
                else:
                    newSize = maxSize - ((elapsed - half) / half) * (maxSize - minSize)
            if newSize:
                self.target.size = (newSize, newSize)
            self.target.draw()
            self.win.flip()
