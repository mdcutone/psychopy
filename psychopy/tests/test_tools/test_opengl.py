"""Tests for PsychoPy's OpenGL loader, `psychopy.tools.opengl`.
"""
import ctypes
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

import psychopy
import psychopy.tools.opengl as GL
from psychopy.tests import skip_under_vm
from psychopy.tools.opengl import _lib

# the generator is only in the repository, not installed packages
_GENERATOR = Path(psychopy.__file__).parents[1] / 'building' / \
    'generateGLBindings.py'
needsGenerator = pytest.mark.skipif(
    not _GENERATOR.is_file(), reason="needs the PsychoPy repository")


@pytest.fixture(scope='module')
def generator():
    return runpy.run_path(str(_GENERATOR))


def _ctypeName(ctype):
    """Comparable description of a `ctypes` type, since equivalent types from
    different modules are different objects."""
    if ctype is None:
        return 'void'
    if issubclass(ctype, ctypes._Pointer):
        return f'POINTER({_ctypeName(ctype._type_)})'
    if issubclass(ctype, ctypes._CFuncPtr):
        argtypes = ', '.join(_ctypeName(t) for t in ctype._argtypes_)
        return f'FUNCTYPE({_ctypeName(ctype._restype_)}, {argtypes})'
    if issubclass(ctype, ctypes.Structure):
        return 'Structure'

    return ctype.__name__


@needsGenerator
def test_usedNamesBound(generator):
    """Every OpenGL name PsychoPy uses is bound."""
    used = generator['findUsedNames'](Path(psychopy.__file__).parent)
    assert used  # the search works
    assert not {name for name in used if not hasattr(GL, name)}


@needsGenerator
def test_bindingsUpToDate(generator):
    """The bindings are what the generator creates from the registry."""
    commit = generator['COMMIT'].read_text().strip()
    source, _ = generator['generate'](generator['REGISTRY'], commit)
    bindings = Path(GL.__file__).parent / '_bindings.py'
    assert source == bindings.read_text(encoding='utf-8')


def test_pygletParity():
    """Everything in `pyglet.gl` is bound, with the same types and values, so
    either can be used with the other's values."""
    pytest.importorskip('pyglet', minversion='2.0')
    import psychopy.tools.pygletgl  # creates pyglet's (legacy) shadow window
    from pyglet.gl import gl as pygletGL, gl_compat as pygletCompat

    missing, different = [], []
    for module in (pygletGL, pygletCompat):
        for name, pygletValue in vars(module).items():
            if not name.startswith(('gl', 'GL_')):
                continue
            if not hasattr(GL, name):
                missing.append(name)
                continue
            value = getattr(GL, name)
            if name.startswith('GL_'):
                if value != pygletValue:
                    different.append(name)
            elif hasattr(pygletValue, 'argtypes'):
                # (`argtypes` are a tuple once functions are linked)
                ours = [_ctypeName(t) for t in
                        [value.restype, *value.argtypes]]
                theirs = [_ctypeName(t) for t in
                          [pygletValue.restype, *pygletValue.argtypes]]
                if ours != theirs:
                    different.append(name)

    assert not missing
    assert not different


def test_noContext():
    """Without a context, `gl_info` reports nothing (in a new process, since
    other tests leave pyglet's shadow window current)."""
    script = (
        "import psychopy.tools.opengl as GL\n"
        "assert not GL.gl_info.have_context()\n"
        "assert GL.gl_info.get_version() == (0, 0)\n"
        "assert GL.gl_info.get_extensions() == set()\n")
    subprocess.run([sys.executable, '-c', script], check=True)


@pytest.mark.parametrize('winType', [
    'pyglet',
    pytest.param('glfw', marks=skip_under_vm(
        reason="GLFW doesn't work on (macOS) virtual machine")),
])
def test_drawWithWindow(winType):
    """Functions work with contexts made by each backend."""
    from psychopy import visual
    win = visual.Window(
        (64, 64), winType=winType, allowGUI=False, autoLog=False)
    try:
        assert GL.gl_info.have_context()
        assert GL.gl_info.have_version(2, 1)
        assert GL.gl_info.get_renderer()

        GL.glClearColor(0., 1., 0., 1.)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        pixel = (GL.GLubyte * 4)()
        GL.glReadPixels(0, 0, 1, 1, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, pixel)
        assert list(pixel) == [0, 255, 0, 255]

        # linked functions replace their placeholders
        assert not isinstance(GL.glClearColor, _lib.GLFunction)

        # concave, so needs the GLU tessellator
        shape = visual.ShapeStim(
            win, vertices=[(-.5, -.5), (0, .5), (.5, -.5), (0, 0)],
            fillColor='red', autoLog=False)
        shape.draw()
        win.flip()
    finally:
        win.close()


@pytest.mark.skipif(
    not sys.platform.startswith('linux'), reason="EGL is only used on Linux")
def test_eglContext():
    """Functions work with EGL contexts, as GLFW creates under Wayland (in a
    new process, since a GLX context can't be current on the same thread as an
    EGL one, and other tests leave pyglet's current)."""
    pytest.importorskip('glfw')
    script = (
        "import sys\n"
        "import glfw\n"
        "import psychopy.tools.opengl as GL\n"
        "from psychopy.tools.opengl import _platform\n"
        "if not glfw.init():\n"
        "    sys.exit(77)\n"
        # also EGL under X11, so this runs without Wayland
        "glfw.window_hint(glfw.CONTEXT_CREATION_API, glfw.EGL_CONTEXT_API)\n"
        "win = glfw.create_window(16, 16, 'EGL', None, None)\n"
        "if not win:\n"
        "    sys.exit(77)\n"
        "glfw.make_context_current(win)\n"
        "assert _platform._getCurrentEGLContext()\n"
        "assert GL.gl_info.have_version(2, 1)\n"
        "GL.glClearColor(0., 1., 0., 1.)\n"
        "GL.glClear(GL.GL_COLOR_BUFFER_BIT)\n"
        "pixel = (GL.GLubyte * 4)()\n"
        "GL.glReadPixels(0, 0, 1, 1, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, pixel)\n"
        "assert list(pixel) == [0, 255, 0, 255], list(pixel)\n"
        # not exported by libOpenGL, so found with `eglGetProcAddress()`
        "program = GL.glCreateProgramObjectARB()\n"
        "assert program\n"
        "GL.glDeleteObjectARB(program)\n"
        "glfw.terminate()\n")
    result = subprocess.run([sys.executable, '-c', script])
    if result.returncode == 77:
        pytest.skip("can't create an EGL context")
    assert result.returncode == 0


@pytest.fixture
def win():
    from psychopy import visual
    win = visual.Window((64, 64), allowGUI=False, autoLog=False)
    yield win
    win.close()


def test_errorChecking(win, monkeypatch):
    """With error checking on, OpenGL errors raise `GLException`, except
    between `glBegin()` and `glEnd()` where checking is an error itself."""
    monkeypatch.setattr(_lib, 'DEBUG_GL', True)
    # new placeholders, since error checking is set up when they're linked
    glEnable = _lib.link('glEnable', None, [GL.GLenum], 'OpenGL 1.0')
    glBegin = _lib.link('glBegin', None, [GL.GLenum], 'OpenGL 1.0')
    glVertex2f = _lib.link(
        'glVertex2f', None, [GL.GLfloat, GL.GLfloat], 'OpenGL 1.0')
    glEnd = _lib.link('glEnd', None, [], 'OpenGL 1.0')

    with pytest.raises(GL.GLException, match='GL_INVALID_ENUM'):
        glEnable(0xDEAD)

    glBegin(GL.GL_TRIANGLES)
    for vertex in [(0., 0.), (1., 0.), (0., 1.)]:
        glVertex2f(*vertex)
    glEnd()


def test_missingFunction():
    """Calling a function the driver doesn't have raises `GLException`."""
    # not starting with 'gl', since on Linux `glXGetProcAddressARB()` returns
    # a dispatch stub for any name that does
    func = _lib.link('psychopyNotAFunction', None, [], 'OpenGL 9.9')
    with pytest.raises(GL.GLException, match='psychopyNotAFunction'):
        func()
