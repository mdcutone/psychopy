import ast
import csv
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from psychopy.experiment import Experiment
from psychopy.experiment.components.code import CodeComponent
from psychopy.experiment.components.pen import PenComponent, SimulatedPenDeviceBackend
from psychopy.experiment.components.polygon import PolygonComponent
from psychopy.hardware.pen import Pen
from psychopy.tests import utils
from psychopy.tests.test_experiment.test_components import BaseComponentTests


class TestPenComponent(BaseComponentTests):
    comp = PenComponent
    libraryClass = Pen

    def setup_class(cls):
        """
        Setup a simulated pen for this test in prefs
        """
        from psychopy.preferences import prefs
        from psychopy.hardware import DeviceManager

        for profile in DeviceManager.getAvailableDevices(SimulatedPenDeviceBackend.deviceClass):
            device = SimulatedPenDeviceBackend(profile)
            device.params['name'].val = "testPen"
            prefs.devices['testPen'] = device
            break

    def run_experiment(self, compParams, samples, extraComps=()):
        """
        Make and run an experiment with a Pen Component, feeding it samples from a Code Component,
        and return the row of data it saved.

        Parameters
        ----------
        compParams : dict
            Values for the Pen Component's params
        samples : list[dict]
            Samples to feed to the pen (keyword arguments for `SimulatedPenDevice.addSample`)
        extraComps : list
            Functions taking (exp, routineName) and returning other Components to add to the
            Routine
        """
        exp = Experiment()
        exp.name = "testPen"
        rt = exp.addRoutine(routineName="penRoutine")
        exp.flow.addRoutine(rt, 0)
        exp.settings.params['Full-screen window'].val = False
        exp.settings.params['Show info dlg'].val = False
        exp.settings.params['Window size (pixels)'].val = "[200, 200]"
        exp.settings.params['Units'].val = "pix"
        exp.settings.params['Data filename'].val = "'data/penTest'"
        # feed samples on the third frame, so the pen has started
        code = "if frameN == 2:\n"
        for sample in samples:
            code += f"    pen.device.addSample(**{sample!r})\n"
        codeComp = CodeComponent(
            exp, parentName="penRoutine", name="feedPen",
            # don't let the mouse add samples
            beginRoutine="pen.device.useMouse = False\n",
            eachFrame=code,
        )
        rt.addComponent(codeComp)
        for makeComp in extraComps:
            rt.addComponent(makeComp(exp, "penRoutine"))
        comp = PenComponent(exp, parentName="penRoutine", name="pen", deviceLabel="testPen")
        for key, val in compParams.items():
            comp.params[key].val = val
        rt.addComponent(comp)
        # write and run the script
        tmpDir = Path(tempfile.mkdtemp())
        script = exp.writeScript(target="PsychoPy")
        tmpPy = tmpDir / "testPen.py"
        tmpPy.write_text(script, encoding="utf-8")
        try:
            subprocess.run(
                args=[sys.executable, "-u", str(tmpPy)],
                capture_output=True,
                check=True,
                cwd=str(tmpDir),
                timeout=120,
            )
        except subprocess.CalledProcessError as err:
            # save script to fails folder to help debugging
            (Path(utils.TESTS_FAILS_PATH) / tmpPy.name).write_text(script, encoding="utf-8")
            raise AssertionError(err.stderr.decode("utf-8"))
        # read the data
        with open(tmpDir / "data" / "penTest.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        return rows[0]

    @staticmethod
    def parse(value):
        return ast.literal_eval(value)

    def test_every_sample(self):
        row = self.run_experiment(
            compParams={'forceEndRoutine': "pen up", 'saveTilt': True, 'stopVal': 5},
            samples=[
                {'type': "enter"},
                {'pix': (0, 0), 'pressure': 0},
                {'pix': (10, 10), 'pressure': 0.8, 'tiltX': 20},
                {'pix': (20, 20), 'pressure': 0.9},
                {'pix': (30, 30), 'pressure': 0},
            ]
        )
        assert self.parse(row['pen.state']) == ["enter", "hover", "down", "move", "up"]
        assert self.parse(row['pen.x']) == [0, 0, 10, 20, 30]
        assert self.parse(row['pen.pressure']) == [0, 0, 0.8, 0.9, 0]
        assert self.parse(row['pen.tiltX']) == [0, 0, 20, 0, 0]
        # routine ended on pen up, rather than lasting the full 5s
        assert float(row['penRoutine.stopped']) - float(row['penRoutine.started']) < 4

    def test_on_pen_down(self):
        row = self.run_experiment(
            compParams={'saveState': "on pen down", 'forceEndRoutine': "pen down"},
            samples=[
                {'pix': (5, 5), 'pressure': 0},
                {'pix': (10, -10), 'pressure': 0.5},
                {'pix': (20, 20), 'pressure': 0.9},
            ]
        )
        assert self.parse(row['pen.state']) == ["down"]
        assert self.parse(row['pen.x']) == [10]
        assert self.parse(row['pen.y']) == [-10]
        assert 'pen.tiltX' not in row

    def test_final(self):
        row = self.run_experiment(
            compParams={'saveState': "final", 'stopVal': 0.5},
            samples=[
                {'pix': (5, 5), 'pressure': 0.5},
                {'pix': (40, 30), 'pressure': 0.25},
            ]
        )
        assert float(row['pen.x']) == 40
        assert float(row['pen.y']) == 30
        assert float(row['pen.pressure']) == 0.25
        assert row['pen.state'] == "move"

    def test_clickable(self):
        def makeTarget(exp, rtName):
            return PolygonComponent(
                exp, parentName=rtName, name="target", shape="square", units="pix",
                size="(50, 50)", pos="(0, 0)", stopVal=""
            )

        row = self.run_experiment(
            compParams={
                'clickable': "target", 'forceEndRoutine': "valid pen down", 'stopVal': 5,
                'saveState': "on pen down",
            },
            samples=[
                # down outside the target, then lift and put down inside it
                {'pix': (80, 80), 'pressure': 0.5},
                {'pix': (80, 80), 'pressure': 0},
                {'pix': (10, 10), 'pressure': 0.5},
            ],
            extraComps=[makeTarget],
        )
        assert self.parse(row['pen.clicked_name']) == [None, "target"]
        assert self.parse(row['pen.x']) == [80, 10]
        assert float(row['penRoutine.stopped']) - float(row['penRoutine.started']) < 4

    @pytest.mark.parametrize("saveState", ['every sample', 'every frame', 'on pen down', 'final', 'never'])
    @pytest.mark.parametrize("forceEndRoutine", ['never', 'pen down', 'pen up', 'valid pen down'])
    @pytest.mark.parametrize("clickable", ["", "target"])
    def test_syntax_combinations(self, saveState, forceEndRoutine, clickable):
        """
        Check that all combinations of the params which change the code produce valid code.
        """
        comp, rt, exp = self.make_minimal_experiment()
        comp.params['saveState'].val = saveState
        comp.params['forceEndRoutine'].val = forceEndRoutine
        comp.params['clickable'].val = clickable
        comp.params['saveTilt'].val = True
        script = exp.writeScript(target="PsychoPy")
        compile(script, "<test>", "exec")
