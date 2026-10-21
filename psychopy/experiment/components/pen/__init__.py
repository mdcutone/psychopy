#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2025 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

import re
from pathlib import Path
from psychopy.experiment.components import BaseComponent, BaseDeviceComponent, Param, getInitVals
from psychopy.experiment.devices import DeviceBackend
from psychopy.localization import _translate


class PenComponent(BaseDeviceComponent):
    """
    Component for getting the position, pressure and tilt of a pen on a pen tablet (e.g. a
    Wacom tablet).
    """
    categories = ['Responses']  # which section(s) in the components panel
    targets = ['PsychoPy']
    iconFile = Path(__file__).parent / 'pen.png'
    iconSVG = Path(__file__).parent / 'PenComponent.svg'
    tooltip = _translate('Pen: get position, pressure and tilt from a pen tablet')
    beta = True

    def __init__(
            self, exp, parentName,
            # basic
            name='pen',
            startType='time (s)', startVal=0.0,
            stopType='duration (s)', stopVal=1.0,
            startEstim='', durationEstim='',
            forceEndRoutine='never',
            clickable='',
            pressureThreshold=0,
            # layout
            units='from exp settings',
            # device
            deviceLabel="",
            # data
            saveState='every sample',
            saveTilt=False,
            saveParamsClickable='name,',
            discardPrevious=True,
            # testing
            disabled=False,
    ):
        # initialise base class
        BaseDeviceComponent.__init__(
            self, exp, parentName,
            name=name,
            startType=startType, startVal=startVal,
            stopType=stopType, stopVal=stopVal,
            startEstim=startEstim, durationEstim=durationEstim,
            deviceLabel=deviceLabel,
            disabled=disabled
        )
        self.type = "Pen"

        self.exp.requireImport(
            importName="Pen",
            importFrom="psychopy.hardware.pen"
        )

        # --- Basic params ---
        self.order += [
            "forceEndRoutine",
            "clickable",
            "pressureThreshold",
        ]
        self.params['forceEndRoutine'] = Param(
            forceEndRoutine, valType='str', inputType="choice", categ='Basic',
            allowedVals=['never', 'pen down', 'pen up', 'valid pen down'],
            allowedLabels=[
                _translate("Never"), _translate("Pen down"), _translate("Pen up"),
                _translate("Pen down on a clickable stimulus")
            ],
            updates='constant', direct=False,
            hint=_translate(
                "Should touching the tablet with the pen (or lifting it off again) end the "
                "Routine?"
            ),
            label=_translate("End Routine on..."))
        self.params['clickable'] = Param(
            clickable, valType='list', inputType="single", categ='Basic',
            updates='constant', direct=False,
            hint=_translate(
                "A comma-separated list of your stimulus names that can be \"clicked\" by putting "
                "the pen down on them, e.g. target, foil"
            ),
            label=_translate("Clickable stimuli"))
        self.params['pressureThreshold'] = Param(
            pressureThreshold, valType='num', inputType="single", categ='Basic',
            updates='constant',
            hint=_translate(
                "Pressure (from 0 to 1) above which the pen counts as touching the tablet."
            ),
            label=_translate("Pressure threshold"))

        # --- Layout params ---
        self.order += [
            "units",
        ]
        self.params['units'] = Param(
            units, valType='str', inputType="choice", categ='Layout',
            allowedVals=['from exp settings', 'deg', 'cm', 'pix', 'norm', 'height', 'degFlatPos',
                         'degFlat'],
            hint=_translate("Units to record the position of the pen in"),
            label=_translate("Spatial units"))

        # --- Data params ---
        self.order += [
            "saveState",
            "saveTilt",
            "saveParamsClickable",
            "discardPrevious",
        ]
        self.params['saveState'] = Param(
            saveState, valType='str', inputType="choice", categ='Data',
            allowedVals=['every sample', 'every frame', 'on pen down', 'final', 'never'],
            allowedLabels=[
                _translate("Every sample"), _translate("Every frame"), _translate("On pen down"),
                _translate("Final"), _translate("Never")
            ],
            updates='constant', direct=False,
            hint=_translate(
                "Which samples to save: every sample from the tablet (usually 100-200 a second), "
                "the latest sample each frame, the samples where the pen touches the tablet, or "
                "just the last sample of the Routine?"
            ),
            label=_translate("Save pen state"))
        self.params['saveTilt'] = Param(
            saveTilt, valType='bool', inputType="bool", categ='Data',
            updates='constant', direct=False,
            hint=_translate(
                "Save the tilt and orientation of the pen, as well as its position and pressure?"
            ),
            label=_translate("Save tilt"))
        self.params['saveParamsClickable'] = Param(
            saveParamsClickable, valType='list', inputType="single", categ='Data',
            updates='constant', direct=False,
            hint=_translate(
                "The params (e.g. name, text) to store for each stimulus that was \"clicked\" by "
                "the pen. Make sure that all the clickable objects have all these params."
            ),
            label=_translate("Store params for clicked"))
        self.params['discardPrevious'] = Param(
            discardPrevious, valType='bool', inputType="bool", categ="Data",
            updates="constant",
            hint=_translate(
                "Do you want to discard all samples from before the onset of this Component?"
            ),
            label=_translate("Discard previous")
        )

    @property
    def _clickableParamsList(self):
        # convert clickableParams (str) to a list
        params = self.params['saveParamsClickable'].val
        paramsList = re.findall(r"[\w']+", str(params))
        return paramsList or ['name']

    def writeInitCode(self, buff):
        inits = getInitVals(self.params)
        code = (
            "%(name)s = Pen(\n"
            "    device=%(deviceLabel)s,\n"
            "    win=win,\n"
            "    units=%(units)s,\n"
            "    pressureThreshold=%(pressureThreshold)s,\n"
            ")\n"
        )
        buff.writeIndentedLines(code % inits)

    def writeRoutineStartCode(self, buff):
        code = (
            "# clear %(name)s data from the last repeat\n"
            "%(name)s.clearData()\n"
        )
        if self.params['clickable'].val:
            for paramName in self._clickableParamsList:
                code += f"%(name)s.clicked_{paramName} = []\n"
        buff.writeIndentedLines(code % self.params)

    def writeFrameCode(self, buff):
        params = self.params
        saveState = params['saveState'].val
        forceEnd = params['forceEndRoutine'].val
        code = (
            "\n"
            "# *%(name)s* updates\n"
        )
        buff.writeIndentedLines(code % params)
        # writes an if statement to determine whether to draw etc
        indented = self.writeStartTestCode(buff)
        if indented:
            # time samples from when the Component starts
            if params['syncScreenRefresh']:
                code = "win.callOnFlip(%(name)s.resetTimer)\n"
            else:
                code = "%(name)s.resetTimer()\n"
            if params['discardPrevious']:
                code += (
                    "# clear any samples from before starting\n"
                    "%(name)s.clearResponses()\n"
                )
            buff.writeIndentedLines(code % params)
            # to get out of the if statement
            buff.setIndentLevel(-indented, relative=True)

        # test for started (will update parameters each frame as needed)
        indented = self.writeActiveTestCode(buff)
        if indented:
            code = (
                "# get samples from %(name)s since the last frame\n"
                "for _thisResp in %(name)s.getResponses():\n"
            )
            buff.writeIndentedLines(code % params)
            buff.setIndentLevel(1, relative=True)
            # code within the loop
            code = ""
            if saveState == "every sample":
                code += "%(name)s.record(_thisResp)\n"
            elif saveState == "on pen down":
                code += (
                    "if _thisResp.value == 'down':\n"
                    "    %(name)s.record(_thisResp)\n"
                )
            if params['clickable'].val:
                code += (
                    "if _thisResp.value == 'down':\n"
                    "    # was the pen put down on one of the clickable stimuli?\n"
                    "    _clicked = None\n"
                    "    for _thisObj in environmenttools.getFromNames(%(clickable)s, namespace=locals()):\n"
                    "        if _thisObj.contains(%(name)s.getResponsePos(_thisResp), units=%(name)s.units):\n"
                    "            _clicked = _thisObj\n"
                    "            break\n"
                )
                for paramName in self._clickableParamsList:
                    code += (
                    f"    %(name)s.clicked_{paramName}.append(getattr(_clicked, '{paramName}', None))\n"
                    )
                if forceEnd == "valid pen down":
                    code += (
                    "    if _clicked is not None:\n"
                    "        continueRoutine = False\n"
                    )
            if forceEnd == "pen down":
                code += (
                    "if _thisResp.value == 'down':\n"
                    "    continueRoutine = False\n"
                )
            elif forceEnd == "pen up":
                code += (
                    "if _thisResp.value == 'up':\n"
                    "    continueRoutine = False\n"
                )
            if not code:
                code = "pass\n"
            buff.writeIndentedLines(code % params)
            buff.setIndentLevel(-1, relative=True)
            if saveState == "every frame":
                code = (
                    "# store the latest sample from %(name)s\n"
                    "%(name)s.record(%(name)s.getState())\n"
                )
                buff.writeIndentedLines(code % params)
            # to get out of the if statement
            buff.setIndentLevel(-indented, relative=True)

        # test for stop (only if there was some setting for duration or stop)
        indented = self.writeStopTestCode(buff)
        if indented:
            # to get out of the if statement
            buff.setIndentLevel(-indented, relative=True)

    def writeRoutineEndCode(self, buff):
        BaseComponent.writeRoutineEndCode(self, buff)
        params = self.params
        saveState = params['saveState'].val
        if saveState == "never":
            return
        code = (
            "# store data from %(name)s\n"
        )
        if saveState == "final":
            code += (
                "%(name)s.record(%(name)s.getState())\n"
            )
        fields = ["x", "y", "pressure", "time", "state"]
        if params['saveTilt']:
            fields += ["tiltX", "tiltY", "azimuth", "altitude", "twist"]
        if params['clickable'].val:
            fields += [f"clicked_{paramName}" for paramName in self._clickableParamsList]
        for field in fields:
            if saveState == "final" and not field.startswith("clicked_"):
                # only one sample, so save it as a value rather than a list
                code += (
                    f"thisExp.addData('%(name)s.{field}', %(name)s.{field}[-1] if %(name)s.{field} else None)\n"
                )
            else:
                code += (
                    f"thisExp.addData('%(name)s.{field}', %(name)s.{field})\n"
                )
        buff.writeIndentedLines(code % params)


class PenDeviceBackend(DeviceBackend):
    backendLabel = "Pen Tablet"
    deviceClass = "psychopy.hardware.pen.PenDevice"
    icon = "light/pen.png"

    def writeDeviceCode(self, buff):
        """
        Code to setup a device with this backend.

        Parameters
        ----------
        buff : io.StringIO
            Text buffer to write code to.
        """
        self.writeBaseDeviceCode(buff, close=True)


class SimulatedPenDeviceBackend(DeviceBackend):
    backendLabel = "Simulated Pen (Mouse)"
    deviceClass = "psychopy.hardware.pen.SimulatedPenDevice"
    icon = "light/pen.png"

    def writeDeviceCode(self, buff):
        """
        Code to setup a device with this backend.

        Parameters
        ----------
        buff : io.StringIO
            Text buffer to write code to.
        """
        self.writeBaseDeviceCode(buff, close=True)


# register backends with Component
PenComponent.registerBackend(PenDeviceBackend)
PenComponent.registerBackend(SimulatedPenDeviceBackend)
