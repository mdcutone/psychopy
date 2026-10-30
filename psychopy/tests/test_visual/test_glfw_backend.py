# Provisional (super simple) test file which doesn't really test anything else
# besides simply opening a `pyGLFW` window. Add more complete `glfw` backend
# tests to other scripts ASAP, then remove this file.
from psychopy.tests import skip_under_vm
import numpy as np
import pytest


@skip_under_vm(reason="GLFW doesn't work on (macOS) virtual machine")
def test_open_glfw_window():
    from psychopy.visual.window import Window
    win = Window(winType='glfw', autoLog=False)
    try:
        assert win.winType == 'glfw'
        win.flip()
    finally:
        win.close()


@skip_under_vm(reason="GLFW doesn't work on (macOS) virtual machine")
def test_glfw_legacy_gl():
    """GLFW windows use the same OpenGL module as the rest of PsychoPy, so the
    fixed-function (legacy) API is available."""
    import psychopy.tools.opengl as opengl
    from psychopy.visual.backends import glfwbackend

    assert glfwbackend.GL is opengl
    assert glfwbackend.USE_LEGACY_GL == opengl.USE_LEGACY_GL
    assert hasattr(glfwbackend.GL, 'glMatrixMode')


@skip_under_vm(reason="GLFW doesn't work on (macOS) virtual machine")
def test_glfw_without_pyglet_gl():
    """GLFW windows don't use pyglet for OpenGL, or need a pyglet context to be
    current (in a new process, since other tests create pyglet windows).
    `pyglet.gl` itself may be imported, since `psychopy.event` uses
    `pyglet.window`."""
    import subprocess
    import sys

    script = (
        "import sys\n"
        "from psychopy import visual\n"
        "win = visual.Window((64, 64), winType='glfw', autoLog=False)\n"
        "visual.Rect(win, size=(.5, .5), fillColor='red').draw()\n"
        "win.flip()\n"
        "win.close()\n"
        "assert 'psychopy.tools.pygletgl' not in sys.modules\n"
        "pygletGL = sys.modules.get('pyglet.gl')\n"
        "assert pygletGL is None or pygletGL._shadow_window is None\n")
    subprocess.run([sys.executable, '-c', script], check=True)


@skip_under_vm(reason="GLFW doesn't work on (macOS) virtual machine")
@pytest.mark.parametrize('useRetina', [True, False])
def test_glfw_draw_position(useRetina):
    """Stimuli are drawn where expected, and the framebuffer size matches what
    was created. On macOS, the size of a window created without retina scaling
    is only correct after it has processed its events."""
    from psychopy import visual
    win = visual.Window(
        (200, 150), winType='glfw', units='pix', useRetina=useRetina,
        allowGUI=False, autoLog=False, color=(-1, -1, -1))
    try:
        scale = win.getContentScaleFactor()
        assert np.allclose(win.size, win.clientSize * scale)
        # 'pix' units are window coordinates with retina scaling
        pixScale = 2. if win.useRetina else 1.

        for pos in [(0, 0), (20, -10), (-30, 15)]:
            rect = visual.Rect(win, pos=pos, size=(6, 6), fillColor='white',
                               lineColor=None)
            rect.draw()
            frame = np.asarray(win.getMovieFrame(buffer='back'))[:, :, 0]
            win.movieFrames = []
            win.flip()

            rows, cols = np.nonzero(frame > 128)
            # only the rect is drawn, as a square of the expected size
            assert len(rows) == int(6 * pixScale) ** 2, pos
            center = (cols.mean() + .5 - frame.shape[1] / 2.,
                      frame.shape[0] / 2. - rows.mean() - .5)
            assert np.allclose(center, np.multiply(pos, pixScale)), pos
    finally:
        win.close()
