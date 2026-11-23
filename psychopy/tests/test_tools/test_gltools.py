"""Tests for OpenGL state set by `psychopy.tools.gltools` and the window.
"""
import ctypes

import pytest

from psychopy import visual
import psychopy.tools.gltools as gt
import psychopy.tools.pygletgl as GL


@pytest.fixture(scope='module')
def win():
    win = visual.Window((128, 128), allowGUI=False, autoLog=False)
    yield win
    win.close()


def _getInteger(name):
    value = GL.GLint()
    GL.glGetIntegerv(name, ctypes.byref(value))
    return value.value


def _boundVAO():
    # same value as `GL_VERTEX_ARRAY_BINDING_APPLE`
    return _getInteger(GL.GL_VERTEX_ARRAY_BINDING)


@pytest.fixture
def vao(win):
    vertices = gt.createVBO([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]])
    vao = gt.createVAO({GL.GL_VERTEX_ARRAY: vertices}, legacy=True)
    yield vao
    gt.deleteVAO(vao)
    gt.deleteVBO(vertices)


def test_useProgram(win):
    prog = win._shaders['stim3d_phong'][(0, False)]
    gt.useProgram(prog)
    assert _getInteger(GL.GL_CURRENT_PROGRAM) == prog
    gt.useProgram(None)
    assert _getInteger(GL.GL_CURRENT_PROGRAM) == 0


def test_drawVAO_unbind(win, vao):
    gt.drawVAO(vao, GL.GL_TRIANGLES)
    assert _boundVAO() == 0

    # left bound for drawing another VAO
    gt.drawVAO(vao, GL.GL_TRIANGLES, unbind=False)
    assert _boundVAO() == vao.name
    gt.drawVAO(vao, GL.GL_TRIANGLES)
    assert _boundVAO() == 0


@pytest.mark.parametrize('name, value', [
    ('never', GL.GL_NEVER), ('less', GL.GL_LESS), ('equal', GL.GL_EQUAL),
    ('lequal', GL.GL_LEQUAL), ('greater', GL.GL_GREATER),
    ('notequal', GL.GL_NOTEQUAL), ('gequal', GL.GL_GEQUAL),
    ('always', GL.GL_ALWAYS),
])
def test_depthFunc(win, name, value):
    old = win.depthFunc
    try:
        win.depthFunc = name
        assert win.depthFunc == name
        assert _getInteger(GL.GL_DEPTH_FUNC) == value
    finally:
        win.depthFunc = old


def test_depthFunc_invalid(win):
    with pytest.raises(KeyError):
        win.depthFunc = 'sometimes'


# ------------------------------------------------------------------------------
# OBJ loading, does not require a GL context
#

# two triangles making a unit quad, every vertex has a texture coord and normal
_OBJ_ATTRIBS = """\
v 0 0 0
v 1 0 0
v 1 1 0
v 0 1 0
vt 0 0
vt 1 0
vt 1 1
vt 0 1
vn 0 0 1
"""


def _loadObj(tmp_path, text):
    objFile = tmp_path / 'mesh.obj'
    objFile.write_text(text)
    return gt.loadObjFile(str(objFile))


def test_loadObjFile_whitespace(tmp_path):
    # repeated spaces, tabs, indentation, comments and blank lines
    objModel = _loadObj(tmp_path, (
        '# comment\n'
        '\n'
        'v  0 0 0\n'
        'v\t1\t0\t0\n'
        '  v 1  1  0  \n'
        'vt  0 0\n'
        'vt\t1 0\n'
        'vt 1 1\n'
        'vn  0\t0  1\n'
        'usemtl  mat\n'
        'f  1/1/1   2/2/1\t3/3/1\n'))

    assert objModel.vertexPos.tolist() == [[0, 0, 0], [1, 0, 0], [1, 1, 0]]
    assert objModel.texCoords.tolist() == [[0, 0], [1, 0], [1, 1]]
    assert objModel.normals.tolist() == [[0, 0, 1]] * 3
    assert list(objModel.faces) == ['mat']
    assert objModel.faces['mat'].tolist() == [[0, 1, 2]]


def test_loadObjFile_no_usemtl(tmp_path):
    # faces without a material are grouped under `None`
    objModel = _loadObj(tmp_path, _OBJ_ATTRIBS + (
        'f 1/1/1 2/2/1 3/3/1\n'
        'f 1/1/1 3/3/1 4/4/1\n'))

    assert list(objModel.faces) == [None]
    assert objModel.faces[None].tolist() == [[0, 1, 2], [0, 2, 3]]
    assert objModel.mtlFile is None


def test_loadObjFile_faces_before_usemtl(tmp_path):
    objModel = _loadObj(tmp_path, _OBJ_ATTRIBS + (
        'f 1/1/1 2/2/1 3/3/1\n'
        'usemtl mat\n'
        'f 1/1/1 3/3/1 4/4/1\n'))

    assert objModel.faces[None].tolist() == [[0, 1, 2]]
    assert objModel.faces['mat'].tolist() == [[0, 2, 3]]


def test_loadObjFile_material_groups(tmp_path):
    # faces for a material are grouped even if the material is used more than
    # once, materials without any faces are omitted
    objModel = _loadObj(tmp_path, _OBJ_ATTRIBS + (
        'mtllib my materials.mtl\n'
        'usemtl unused\n'
        'usemtl a\n'
        'f 1/1/1 2/2/1 3/3/1\n'
        'usemtl b\n'
        'f 1/1/1 3/3/1 4/4/1\n'
        'usemtl a\n'
        'f 2/2/1 3/3/1 4/4/1\n'))

    assert set(objModel.faces) == {'a', 'b'}
    assert objModel.faces['a'].tolist() == [[0, 1, 2], [1, 2, 3]]
    assert objModel.faces['b'].tolist() == [[0, 2, 3]]
    # file names may contain spaces, the path is relative to the OBJ file
    assert objModel.mtlFile == str(tmp_path / 'my materials.mtl')


def _assertAttribShapes(objModel, nVertices):
    assert objModel.vertexPos.shape == (nVertices, 3)
    assert objModel.texCoords.shape == (nVertices, 2)
    assert objModel.normals.shape == (nVertices, 3)


def test_loadObjFile_position_only(tmp_path):
    # normals are computed per face and texture coordinates are zero, vertices
    # aren't shared between faces since their normals may differ
    objModel = _loadObj(tmp_path, _OBJ_ATTRIBS + (
        'f 1 2 3\n'
        'f 1 3 4\n'))

    _assertAttribShapes(objModel, 6)
    assert objModel.faces[None].tolist() == [[0, 1, 2], [3, 4, 5]]
    assert objModel.vertexPos.tolist() == [
        [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 0, 0], [1, 1, 0], [0, 1, 0]]
    assert objModel.texCoords.tolist() == [[0, 0]] * 6
    assert objModel.normals.tolist() == [[0, 0, 1]] * 6


def test_loadObjFile_generated_normal_winding(tmp_path):
    # face normals follow counter-clockwise winding
    objModel = _loadObj(tmp_path, _OBJ_ATTRIBS + (
        'f 1 2 3\n'  # counter-clockwise looking down -Z
        'f 1 4 3\n'  # clockwise
        'f 1 2 2\n'))  # degenerate

    normals = objModel.normals[objModel.faces[None]]
    assert normals.tolist() == [
        [[0, 0, 1]] * 3, [[0, 0, -1]] * 3, [[0, 0, 0]] * 3]


def test_loadObjFile_normals_only(tmp_path):
    objModel = _loadObj(tmp_path, _OBJ_ATTRIBS + (
        'f 1//1 2//1 3//1\n'
        'f 1//1 3//1 4//1\n'))

    # vertices with normals are shared between faces
    _assertAttribShapes(objModel, 4)
    assert objModel.faces[None].tolist() == [[0, 1, 2], [0, 2, 3]]
    assert objModel.texCoords.tolist() == [[0, 0]] * 4
    assert objModel.normals.tolist() == [[0, 0, 1]] * 4


def test_loadObjFile_texcoords_only(tmp_path):
    objModel = _loadObj(tmp_path, _OBJ_ATTRIBS + (
        'f 1/1 2/2 3/3\n'
        'f 1/1 3/3 4/4\n'))

    _assertAttribShapes(objModel, 6)
    assert objModel.texCoords.tolist() == [
        [0, 0], [1, 0], [1, 1], [0, 0], [1, 1], [0, 1]]
    assert objModel.normals.tolist() == [[0, 0, 1]] * 6


def test_loadObjFile_mixed_face_formats(tmp_path):
    # faces with and without texture coordinates and normals in the same file
    objModel = _loadObj(tmp_path, _OBJ_ATTRIBS + (
        'f 1/1/1 2/2/1 3/3/1\n'
        'f 1 3 4\n'
        'f 2//1 3//1 4//1\n'
        'f 1/1/ 2/2/ 4/4/\n'))  # empty normal fields

    _assertAttribShapes(objModel, 12)
    faces = objModel.faces[None]
    assert faces.tolist() == [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11]]
    assert objModel.texCoords[faces[0]].tolist() == [[0, 0], [1, 0], [1, 1]]
    assert objModel.texCoords[faces[1]].tolist() == [[0, 0]] * 3
    assert objModel.texCoords[faces[3]].tolist() == [[0, 0], [1, 0], [0, 1]]
    assert objModel.normals.tolist() == [[0, 0, 1]] * 12


def test_loadObjFile_extra_components(tmp_path):
    # vertex colors, `w` components and 1D texture coordinates
    objModel = _loadObj(tmp_path, (
        'v 0 0 0 1 0 0\n'
        'v 1 0 0 0 1 0\n'
        'v 1 1 0 1.0\n'
        'vt 0 0 0\n'
        'vt 1\n'
        'vt 1 1 0\n'
        'vn 0 0 1\n'
        'f 1/1/1 2/2/1 3/3/1\n'))

    _assertAttribShapes(objModel, 3)
    assert objModel.vertexPos.tolist() == [[0, 0, 0], [1, 0, 0], [1, 1, 0]]
    assert objModel.texCoords.tolist() == [[0, 0], [1, 0], [1, 1]]
    assert objModel.extents[1].tolist() == [1, 1, 0]


def test_loadObjFile_missing_position_index(tmp_path):
    with pytest.raises(ValueError):
        _loadObj(tmp_path, _OBJ_ATTRIBS + 'f /1/1 2/2/1 3/3/1\n')
