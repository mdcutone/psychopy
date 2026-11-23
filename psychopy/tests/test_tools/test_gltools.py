"""Tests for OpenGL state set by `psychopy.tools.gltools` and the window.
"""
import ctypes
import os

import numpy as np
import pytest
from PIL import Image

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


def test_loadObjFile_quads(tmp_path):
    # polygons are split into triangle fans around their first vertex
    objModel = _loadObj(tmp_path, _OBJ_ATTRIBS + 'f 1/1/1 2/2/1 3/3/1 4/4/1\n')

    _assertAttribShapes(objModel, 4)
    assert objModel.faces[None].tolist() == [[0, 1, 2], [0, 2, 3]]


def test_loadObjFile_polygons(tmp_path):
    # mixed triangles, quads and a pentagon in the same group
    objModel = _loadObj(tmp_path, _OBJ_ATTRIBS + (
        'v 0.5 1.5 0\n'
        'f 1 2 3\n'
        'f 1 2 3 4\n'
        'f 1 2 3 5 4\n'))

    faces = objModel.faces[None]
    assert faces.shape == (1 + 2 + 3, 3)
    assert faces.tolist()[3:] == [[7, 8, 9], [7, 9, 10], [7, 10, 11]]

    # all triangles of a polygon share its vertices and flat normal
    _assertAttribShapes(objModel, 3 + 4 + 5)
    assert objModel.normals.tolist() == [[0, 0, 1]] * 12


def test_loadObjFile_quad_winding(tmp_path):
    # triangles keep the winding of the polygon
    objModel = _loadObj(tmp_path, _OBJ_ATTRIBS + 'f 1 4 3 2\n')

    vertices = objModel.vertexPos[objModel.faces[None]]
    for a, b, c in vertices:
        assert np.cross(b - a, c - a).tolist() == [0, 0, -1]
    assert objModel.normals.tolist() == [[0, 0, -1]] * 4


def test_loadObjFile_ignores_non_polygons(tmp_path):
    objModel = _loadObj(tmp_path, _OBJ_ATTRIBS + (
        'f 1 2\n'
        'f 1 2 3\n'))
    assert objModel.faces[None].tolist() == [[0, 1, 2]]

    with pytest.raises(RuntimeError):
        _loadObj(tmp_path, _OBJ_ATTRIBS + 'f 1 2\n')


def test_loadObjFile_negative_indices(tmp_path):
    expected = _loadObj(tmp_path, _OBJ_ATTRIBS + (
        'f 1/1/1 2/2/1 3/3/1\n'
        'f 1/1/1 3/3/1 4/4/1\n'))
    objModel = _loadObj(tmp_path, _OBJ_ATTRIBS + (
        'f -4/-4/-1 -3/-3/-1 -2/-2/-1\n'
        'f 1/-4/1 -2/3/-1 -1/-1/1\n'))

    assert objModel.faces[None].tolist() == expected.faces[None].tolist()
    assert objModel.vertexPos.tolist() == expected.vertexPos.tolist()
    assert objModel.texCoords.tolist() == expected.texCoords.tolist()
    assert objModel.normals.tolist() == expected.normals.tolist()


def test_loadObjFile_negative_indices_are_relative(tmp_path):
    # negative indices count back from the last attribute defined before the
    # face, not the end of the file
    objModel = _loadObj(tmp_path, (
        'v 0 0 0\n'
        'v 1 0 0\n'
        'v 1 1 0\n'
        'f -3 -2 -1\n'
        'v 5 5 5\n'
        'v 6 5 5\n'
        'v 6 6 5\n'
        'f -3 -2 -1\n'))

    vertices = objModel.vertexPos[objModel.faces[None]]
    assert vertices.tolist() == [
        [[0, 0, 0], [1, 0, 0], [1, 1, 0]],
        [[5, 5, 5], [6, 5, 5], [6, 6, 5]]]


def test_loadObjFile_utf8(tmp_path):
    objFile = tmp_path / 'mesh.obj'
    objFile.write_text(
        _OBJ_ATTRIBS + 'usemtl Mätérial\nf 1 2 3\n', encoding='utf-8')
    objModel = gt.loadObjFile(str(objFile))
    assert list(objModel.faces) == ['Mätérial']


@pytest.mark.parametrize('face', [
    'f 0 1 2',      # indices start at 1
    'f -5 -4 -3',   # only 4 positions defined
    'f 1 2 5',      # undefined position
    'f 1/5 2/1 3/1',  # undefined texture coordinate
    'f 1//2 2//1 3//1',  # undefined normal
])
def test_loadObjFile_invalid_indices(tmp_path, face):
    with pytest.raises(ValueError):
        _loadObj(tmp_path, _OBJ_ATTRIBS + face + '\n')


# ------------------------------------------------------------------------------
# MTL loading
#

def _parseMtl(tmp_path, text):
    mtlFile = tmp_path / 'materials.mtl'
    mtlFile.write_text(text, encoding='utf-8')
    return gt._parseMtlFile(str(mtlFile))


def test_parseMtlFile_colors(tmp_path):
    materials = _parseMtl(tmp_path, (
        '# comment\n'
        'newmtl  first \n'
        'Ka 0.1 0.2 0.3\n'
        'Kd\t0.5  0.25\t1\n'
        'Ks 0.75\n'  # one value is used for all components
        'Ke 2 -1 0.5\n'  # clamped to 0-1
        '\n'
        'newmtl second\n'
        'Kd spectral file.rfl\n'  # unsupported, ignored
        'Ks xyz 0.5 0.5 0.5\n'))

    assert set(materials) == {'first', 'second'}
    first = materials['first']
    assert first['ambientColor'] == pytest.approx((0.1, 0.2, 0.3))
    assert first['diffuseColor'] == pytest.approx((0.5, 0.25, 1))
    assert first['specularColor'] == pytest.approx((0.75, 0.75, 0.75))
    assert first['emissionColor'] == pytest.approx((1, 0, 0.5))

    # only properties in the file are present
    assert materials['second'] == {}


@pytest.mark.parametrize('ns, expected', [
    ('10', 10.0), ('128', 128.0), ('500', 128.0), ('-5', 0.0)])
def test_parseMtlFile_shininess(tmp_path, ns, expected):
    materials = _parseMtl(tmp_path, 'newmtl mat\nNs {}\n'.format(ns))
    assert materials['mat']['shininess'] == expected


@pytest.mark.parametrize('statements, expected', [
    (['d 0.25'], 0.25),
    (['d -halo 0.25'], 0.25),
    (['Tr 0.25'], 0.75),
    (['d 0.25', 'Tr 0.5'], 0.25),  # `d` takes precedence over `Tr`
    (['Tr 0.5', 'd 0.25'], 0.25),
    (['d 1.5'], 1.0),
])
def test_parseMtlFile_opacity(tmp_path, statements, expected):
    materials = _parseMtl(tmp_path, 'newmtl mat\n{}\n'.format(
        '\n'.join(statements)))
    assert materials['mat']['opacity'] == pytest.approx(expected)


def test_parseMtlFile_dissolve_per_material(tmp_path):
    # `d` in one material doesn't stop `Tr` being used in the next
    materials = _parseMtl(tmp_path, (
        'newmtl a\nd 0.5\n'
        'newmtl b\nTr 0.25\n'))
    assert materials['a']['opacity'] == pytest.approx(0.5)
    assert materials['b']['opacity'] == pytest.approx(0.75)


@pytest.mark.parametrize('statement, fileName', [
    ('map_Kd tex.png', 'tex.png'),
    ('map_Kd  my texture.png', 'my texture.png'),
    ('map_Kd -s 1 1 1 tex.png', 'tex.png'),
    ('map_Kd -s 2 -o 0.5 0.5 tex.png', 'tex.png'),
    ('map_Kd -clamp on -bm 0.5 -mm 0 1 -texres 512 tex.png', 'tex.png'),
    ('map_Kd -blendu off -blendv off -imfchan l -type sphere tex.png',
     'tex.png'),
    ('map_Kd textures\\wood.png', 'textures/wood.png'),
])
def test_parseMtlFile_map_kd(tmp_path, statement, fileName):
    materials = _parseMtl(tmp_path, 'newmtl mat\n{}\n'.format(statement))
    expected = os.path.normpath(str(tmp_path / fileName))
    assert materials['mat']['diffuseTexture'] == expected


def test_parseMtlFile_map_kd_absolute(tmp_path):
    texFile = str(tmp_path / 'elsewhere' / 'tex.png')
    materials = _parseMtl(
        tmp_path, 'newmtl mat\nmap_Kd {}\n'.format(texFile))
    assert materials['mat']['diffuseTexture'] == os.path.normpath(texFile)


def test_parseMtlFile_invalid_statements(tmp_path):
    # invalid statements are ignored, the rest of the file is still loaded
    materials = _parseMtl(tmp_path, (
        'Kd 1 0 0\n'  # before any material
        'newmtl mat\n'
        'Ns shiny\n'
        'Kd\n'
        'd\n'
        'map_Kd -s 1 1 1\n'
        'illum 2\n'  # unsupported, ignored
        'Ka 0.5 0.5 0.5\n'))
    assert materials == {'mat': {'ambientColor': (0.5, 0.5, 0.5)}}


def test_parseMtlFile_utf8(tmp_path):
    materials = _parseMtl(tmp_path, 'newmtl Mätérial\nKd 1 1 1\n')
    assert list(materials) == ['Mätérial']


def test_loadMtlFile_textures(win, tmp_path):
    Image.new('RGB', (4, 4), (255, 0, 0)).save(tmp_path / 'red.png')
    mtlFile = tmp_path / 'materials.mtl'
    mtlFile.write_text(
        'newmtl a\nKd 1 1 1\nmap_Kd red.png\n'
        'newmtl b\nmap_Kd -s 1 1 1 red.png\n'
        'newmtl c\nmap_Kd missing.png\n'
        'newmtl d\nKd 1 1 1\n')

    materials = gt.loadMtlFile(str(mtlFile))
    texture = materials['a']['diffuseTexture']
    assert isinstance(texture, gt.TexImage2DInfo)
    assert (texture.width, texture.height) == (4, 4)

    # textures are only loaded once
    assert materials['b']['diffuseTexture'] is texture

    # textures which can't be loaded are left out
    assert 'diffuseTexture' not in materials['c']
    assert 'diffuseTexture' not in materials['d']
    assert materials['d']['diffuseColor'] == (1, 1, 1)

    gt.deleteTexture(texture)
