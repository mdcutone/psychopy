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


def _drawnTriangles(win, vao, **kwargs):
    """Draw two triangles from a VAO in white on black, return whether the
    first (lower-left) and second (upper-right) triangles were drawn.
    """
    win.resetEyeTransform()  # vertex coordinates are -1 to 1 across the window
    GL.glUseProgram(0)
    GL.glClearColor(0., 0., 0., 1.)
    GL.glClear(GL.GL_COLOR_BUFFER_BIT)
    GL.glColor4f(1., 1., 1., 1.)
    gt.drawVAO(vao, GL.GL_TRIANGLES, **kwargs)
    assert GL.glGetError() == GL.GL_NO_ERROR

    frame = np.asarray(win.getMovieFrame(buffer='back'))[:, :, 0]
    win.movieFrames = []
    win.flip()
    h, w = frame.shape
    return frame[int(h * 0.9), int(w * 0.1)] > 128, \
        frame[int(h * 0.4), int(w * 0.6)] > 128


@pytest.mark.parametrize('indexType', [np.uint32, np.uint16, None])
@pytest.mark.parametrize('instanceCount', [None, 1])
@pytest.mark.parametrize('count', [3, None])
def test_drawVAO_start(win, indexType, instanceCount, count):
    # `start` is the first element (vertex or index) to draw, not a byte offset
    vertices = gt.createVBO(np.array(
        [[-1, -1, 0], [0, -1, 0], [-1, 0, 0],  # lower-left triangle
         [0, 0, 0], [1, 0, 0], [0, 1, 0]],  # upper-right triangle
        dtype=np.float32))
    indices = None
    if indexType is not None:
        indices = gt.createVBO(
            np.arange(6, dtype=indexType),
            target=GL.GL_ELEMENT_ARRAY_BUFFER,
            dataType=gt.ARRAY_TYPES[indexType][0])
    vao = gt.createVAO(
        {GL.GL_VERTEX_ARRAY: vertices}, indexBuffer=indices, legacy=True)

    assert _drawnTriangles(win, vao) == (True, True)
    assert _drawnTriangles(
        win, vao, start=3, count=count, instanceCount=instanceCount) == \
        (False, True)
    assert _drawnTriangles(win, vao, start=0, count=3) == (True, False)

    gt.deleteVAO(vao)
    gt.deleteVBO(vertices)
    if indices is not None:
        gt.deleteVBO(indices)


_TRIANGLES = np.array(
    [[-1, -1], [0, -1], [-1, 0],  # lower-left triangle
     [0, 0], [1, 0], [0, 1]],  # upper-right triangle
    dtype=np.float32)


def _renderClientArrays(win, attribs):
    """Draw triangles with `drawClientArrays` in white on black, return which
    pixels were drawn.
    """
    win.resetEyeTransform()
    GL.glUseProgram(0)
    GL.glClearColor(0., 0., 0., 1.)
    GL.glClear(GL.GL_COLOR_BUFFER_BIT)
    GL.glColor4f(1., 1., 1., 1.)
    gt.drawClientArrays(attribs, 'GL_TRIANGLES')
    assert GL.glGetError() == GL.GL_NO_ERROR

    frame = np.asarray(win.getMovieFrame(buffer='back'))[:, :, 0] > 128
    win.movieFrames = []
    win.flip()
    return frame


def _assertSameAsReference(win, attribs):
    """Check triangles drawn from `attribs` match `_TRIANGLES` drawn from a
    plain array.
    """
    expected = _renderClientArrays(win, {'gl_Vertex': _TRIANGLES})
    actual = _renderClientArrays(win, attribs)
    assert np.array_equal(actual, expected), \
        '{} pixels differ'.format(np.count_nonzero(actual != expected))


def test_drawClientArrays_reference(win):
    # the reference draws the lower-left and upper-right triangles only
    frame = _renderClientArrays(win, {'gl_Vertex': _TRIANGLES})
    h, w = frame.shape
    assert frame[int(h * 0.9), int(w * 0.1)]  # lower-left
    assert frame[int(h * 0.4), int(w * 0.6)]  # upper-right
    assert not frame[int(h * 0.1), int(w * 0.1)]  # upper-left
    assert not frame[int(h * 0.9), int(w * 0.9)]  # lower-right


@pytest.mark.parametrize('dtype', [np.float32, np.float64])
def test_drawClientArrays_interleaved(win, dtype):
    # attributes at an offset within interleaved rows
    other = np.full((6, 3), 99, dtype=dtype)
    interleaved, sizes, offsets = gt.interleaveAttributes(
        [other, _TRIANGLES.astype(dtype)])
    interleaved = interleaved.astype(dtype)
    assert offsets[1] == 3
    _assertSameAsReference(
        win, {'gl_Vertex': (interleaved, sizes[1], offsets[1])})


def test_drawClientArrays_non_contiguous(win):
    # a view of some columns of a larger array
    wide = np.hstack([np.full((6, 2), 99, dtype=np.float32), _TRIANGLES])
    view = wide[:, 2:]
    assert not view.flags['C_CONTIGUOUS']
    _assertSameAsReference(win, {'gl_Vertex': view})


def test_drawClientArrays_list(win):
    # lists are vertex data, not attribute specifications
    _assertSameAsReference(win, {'gl_Vertex': _TRIANGLES.tolist()})


def _createIndexBuffer(n=6):
    return gt.createVBO(
        np.arange(n, dtype=np.uint32), target=GL.GL_ELEMENT_ARRAY_BUFFER,
        dataType=GL.GL_UNSIGNED_INT)


@pytest.fixture
def indexedVAO(win):
    """VAO drawing `_TRIANGLES` with an index buffer, and its index buffer."""
    vertices = gt.createVBO(
        np.hstack([_TRIANGLES, np.zeros((6, 1), np.float32)]))
    indices = _createIndexBuffer()
    vao = gt.createVAO(
        {GL.GL_VERTEX_ARRAY: vertices}, indexBuffer=indices, legacy=True)
    yield vao, indices
    gt._glBindVertexArray(0)
    gt.deleteVAO(vao)
    gt.deleteVBO(vertices)
    gt.deleteVBO(indices)


def _vaoIndexBuffer(vao):
    """Get the index buffer of a VAO, leaving the bound VAO unchanged."""
    bound = _boundVAO()
    gt._glBindVertexArray(vao.name)
    name = _getInteger(GL.GL_ELEMENT_ARRAY_BUFFER_BINDING)
    gt._glBindVertexArray(bound)
    return name


def _assertVAOIntact(win, vao, indices):
    assert _vaoIndexBuffer(vao) == indices.name.value
    assert _drawnTriangles(win, vao) == (True, True)


def test_createVBO_keeps_bindings(win, indexedVAO):
    vao, indices = indexedVAO
    other = gt.createVBO(np.zeros((2, 3), dtype=np.float32))

    gt._glBindVertexArray(vao.name)
    gt.bindVBO(other)
    newIndices = _createIndexBuffer()
    newVertices = gt.createVBO(np.zeros((2, 3), dtype=np.float32))
    assert _getInteger(GL.GL_ARRAY_BUFFER_BINDING) == other.name.value
    gt.unbindVBO(other)
    gt._glBindVertexArray(0)

    _assertVAOIntact(win, vao, indices)
    for buffer in (other, newIndices, newVertices):
        gt.deleteVBO(buffer)


@pytest.mark.parametrize('method', ['mapBuffer', 'mappedBuffer', 'updateVBO'])
def test_mapBuffer_keeps_bindings(win, indexedVAO, method):
    # mapping another index buffer while a VAO is bound doesn't change the
    # VAO's index buffer, and array buffer bindings are restored too
    vao, indices = indexedVAO
    other = gt.createVBO(np.zeros((2, 3), dtype=np.float32))
    otherIndices = _createIndexBuffer()
    vertices = gt.createVBO(
        np.zeros((2, 3), dtype=np.float32), usage=GL.GL_DYNAMIC_DRAW)

    gt._glBindVertexArray(vao.name)
    gt.bindVBO(other)
    for vbo in (otherIndices, vertices):
        if method == 'mapBuffer':
            gt.mapBuffer(vbo)
            assert gt.unmapBuffer(vbo)
        elif method == 'mappedBuffer':
            with gt.mappedBuffer(vbo):
                pass
        else:
            assert gt.updateVBO(vbo, np.zeros(vbo.shape))
    assert _getInteger(GL.GL_ELEMENT_ARRAY_BUFFER_BINDING) == \
        indices.name.value
    assert _getInteger(GL.GL_ARRAY_BUFFER_BINDING) == other.name.value
    gt.unbindVBO(other)
    gt._glBindVertexArray(0)

    _assertVAOIntact(win, vao, indices)
    assert GL.glGetError() == GL.GL_NO_ERROR
    for buffer in (other, otherIndices, vertices):
        gt.deleteVBO(buffer)


def test_unmapBuffer_other_vao_bound(win, indexedVAO):
    # changing the bound VAO while an index buffer is mapped doesn't change
    # the index buffer of either VAO
    vao, indices = indexedVAO
    otherIndices = _createIndexBuffer()
    otherVAO = gt.createVAO(
        {GL.GL_VERTEX_ARRAY: gt.createVBO(np.zeros((3, 3), np.float32))},
        indexBuffer=otherIndices, legacy=True)
    mapped = _createIndexBuffer()

    gt._glBindVertexArray(vao.name)
    gt.mapBuffer(mapped)
    gt._glBindVertexArray(otherVAO.name)
    assert gt.unmapBuffer(mapped)
    assert _boundVAO() == otherVAO.name
    gt._glBindVertexArray(0)

    assert _vaoIndexBuffer(otherVAO) == otherIndices.name.value
    _assertVAOIntact(win, vao, indices)
    assert GL.glGetError() == GL.GL_NO_ERROR

    for buffer in [otherIndices, mapped] + list(
            otherVAO.activeAttribs.values()):
        gt.deleteVBO(buffer)
    gt.deleteVAO(otherVAO)


def test_drawClientArrays_keeps_vao_index_buffer(win, indexedVAO):
    # drawing client arrays while a VAO is bound doesn't remove its index
    # buffer
    vao, indices = indexedVAO
    gt._glBindVertexArray(vao.name)
    _renderClientArrays(win, {'gl_Vertex': _TRIANGLES})
    _assertVAOIntact(win, vao, indices)


def test_drawVAO_invalid_range(win, vao):
    for start, count in [(-1, None), (4, None), (1, 3)]:
        with pytest.raises(ValueError):
            gt.drawVAO(vao, GL.GL_TRIANGLES, start=start, count=count)


def _readBuffer(vbo):
    """Read the contents of a float32 VBO without mapping it."""
    data = np.zeros(vbo.shape, dtype=np.float32)
    GL.glBindBuffer(vbo.target, vbo.name)
    GL.glGetBufferSubData(
        vbo.target, 0, vbo.size, data.ctypes.data_as(ctypes.c_void_p))
    GL.glBindBuffer(vbo.target, 0)
    return data


@pytest.fixture
def vbo4x3(win):
    data = np.arange(12, dtype=np.float32).reshape((4, 3))
    vbo = gt.createVBO(data, usage=GL.GL_DYNAMIC_DRAW)
    yield vbo, data
    gt.deleteVBO(vbo)


@pytest.mark.parametrize('start, length, expected', [
    (0, None, np.arange(12).reshape((4, 3))),  # whole buffer, keeps its shape
    (3, 6, np.arange(3, 9).reshape((2, 3))),  # whole rows
    (6, None, np.arange(6, 12).reshape((2, 3))),  # rows to the end
    (4, 2, np.arange(4, 6)),  # part of a row
    (2, 4, np.arange(2, 6)),  # crosses rows
    (11, 1, np.arange(11, 12)),  # last value
])
def test_mapBuffer_range(vbo4x3, start, length, expected):
    vbo, data = vbo4x3
    arr = gt.mapBuffer(vbo, start=start, length=length)
    assert arr.shape == expected.shape
    assert arr.tolist() == expected.tolist()

    # only the mapped values are changed
    arr *= 10
    assert gt.unmapBuffer(vbo)
    gt.unbindVBO(vbo)
    changed = data.flatten()
    changed[start:start + expected.size] *= 10
    assert _readBuffer(vbo).flatten().tolist() == changed.tolist()


def test_mappedBuffer_range(vbo4x3):
    vbo, data = vbo4x3
    with gt.mappedBuffer(vbo, start=3, length=3) as arr:
        assert arr.shape == (1, 3)
        arr[:] = -1
    gt.unbindVBO(vbo)
    assert _readBuffer(vbo)[1].tolist() == [-1, -1, -1]
    assert _readBuffer(vbo)[[0, 2, 3]].tolist() == data[[0, 2, 3]].tolist()


def _isMapped(vbo):
    mapped = GL.GLint()
    GL.glBindBuffer(vbo.target, vbo.name)
    GL.glGetBufferParameteriv(
        vbo.target, GL.GL_BUFFER_MAPPED, ctypes.byref(mapped))
    GL.glBindBuffer(vbo.target, 0)
    return bool(mapped.value)


def test_mappedBuffer_unmaps(vbo4x3):
    vbo, _ = vbo4x3
    with gt.mappedBuffer(vbo) as arr:
        assert _isMapped(vbo)
        arr[0] = -1
    assert not _isMapped(vbo)
    assert _readBuffer(vbo)[0].tolist() == [-1, -1, -1]


def test_mappedBuffer_unmaps_on_exception(vbo4x3):
    vbo, _ = vbo4x3
    with pytest.raises(RuntimeError, match='in the block'):
        with gt.mappedBuffer(vbo) as arr:
            arr[0] = -1
            raise RuntimeError('in the block')

    # unmapped, and values written before the exception are kept
    assert not _isMapped(vbo)
    assert _readBuffer(vbo)[0].tolist() == [-1, -1, -1]
    assert GL.glGetError() == GL.GL_NO_ERROR


def test_mappedBuffer_unmaps_own_buffer(vbo4x3):
    # binding another buffer in the block doesn't affect which is unmapped
    vbo, _ = vbo4x3
    other = gt.createVBO(np.zeros((2, 3), dtype=np.float32))
    with gt.mappedBuffer(vbo) as arr:
        gt.bindVBO(other)
        arr[0] = -1
    assert not _isMapped(vbo)
    assert not _isMapped(other)
    assert _readBuffer(vbo)[0].tolist() == [-1, -1, -1]
    assert GL.glGetError() == GL.GL_NO_ERROR

    gt.deleteVBO(other)


@pytest.mark.parametrize('kwargs, expected', [
    ({}, GL.GL_MAP_READ_BIT | GL.GL_MAP_WRITE_BIT),
    ({'read': False}, GL.GL_MAP_WRITE_BIT),
    ({'write': False}, GL.GL_MAP_READ_BIT),
    # reading isn't allowed when not synchronizing or invalidating
    ({'noSync': True}, GL.GL_MAP_WRITE_BIT | GL.GL_MAP_UNSYNCHRONIZED_BIT),
    ({'invalidate': True},
     GL.GL_MAP_WRITE_BIT | GL.GL_MAP_INVALIDATE_BUFFER_BIT),
    ({'invalidate': True, 'start': 3, 'length': 3},
     GL.GL_MAP_WRITE_BIT | GL.GL_MAP_INVALIDATE_RANGE_BIT),
    ({'invalidate': True, 'noSync': True},
     GL.GL_MAP_WRITE_BIT | GL.GL_MAP_INVALIDATE_BUFFER_BIT |
     GL.GL_MAP_UNSYNCHRONIZED_BIT),
])
def test_mapBuffer_access_flags(vbo4x3, kwargs, expected):
    vbo, _ = vbo4x3
    gt.mapBuffer(vbo, **kwargs)
    flags = GL.GLint()
    GL.glGetBufferParameteriv(
        vbo.target, GL.GL_BUFFER_ACCESS_FLAGS, ctypes.byref(flags))
    assert gt.unmapBuffer(vbo)
    gt.unbindVBO(vbo)

    assert flags.value == expected
    assert GL.glGetError() == GL.GL_NO_ERROR


def test_mapBuffer_invalidate_range(vbo4x3):
    # only the mapped values are discarded
    vbo, data = vbo4x3
    with gt.mappedBuffer(vbo, start=3, length=3, invalidate=True) as arr:
        arr[:] = -1
    gt.unbindVBO(vbo)

    expected = data.copy()
    expected[1] = -1
    assert _readBuffer(vbo).tolist() == expected.tolist()


@pytest.mark.parametrize('kwargs', [
    {'read': False, 'write': False},
    {'write': False, 'noSync': True},
    {'write': False, 'invalidate': True},
])
def test_mapBuffer_no_access(vbo4x3, kwargs):
    vbo, _ = vbo4x3
    with pytest.raises(ValueError):
        gt.mapBuffer(vbo, **kwargs)
    assert not _isMapped(vbo)


def test_updateVBO_1d(win):
    # index buffers are 1D
    indices = _createIndexBuffer()
    assert gt.updateVBO(indices, np.arange(6)[::-1])
    data = np.zeros(6, dtype=np.uint32)
    GL.glBindBuffer(indices.target, indices.name)
    GL.glGetBufferSubData(
        indices.target, 0, indices.size, data.ctypes.data_as(ctypes.c_void_p))
    GL.glBindBuffer(indices.target, 0)
    assert data.tolist() == [5, 4, 3, 2, 1, 0]
    gt.deleteVBO(indices)


@pytest.mark.parametrize('noSync', [False, True])
def test_updateVBO(vbo4x3, monkeypatch, noSync):
    vbo, data = vbo4x3

    # the buffer is only mapped for writing, and invalidated if `noSync`
    calls = []
    mapBuffer = gt.mapBuffer
    def spyMapBuffer(*args, **kwargs):
        calls.append(kwargs)
        return mapBuffer(*args, **kwargs)
    monkeypatch.setattr(gt, 'mapBuffer', spyMapBuffer)

    assert gt.updateVBO(vbo, -data, noSync=noSync)
    gt.unbindVBO(vbo)
    assert calls == [{'read': False, 'invalidate': noSync}]
    assert _readBuffer(vbo).tolist() == (-data).tolist()
    assert GL.glGetError() == GL.GL_NO_ERROR


def test_VertexBufferInfo_validate(vbo4x3):
    vbo, _ = vbo4x3
    indices = gt.createVBO(
        np.arange(3, dtype=np.uint32), target=GL.GL_ELEMENT_ARRAY_BUFFER,
        dataType=GL.GL_UNSIGNED_INT)
    assert vbo.validate()
    assert indices.validate()

    # descriptors which don't match the buffer are invalid
    vbo.size += 4
    assert not vbo.validate()
    vbo.size -= 4

    gt.deleteVBO(indices)
    assert not indices.validate()


def test_VertexBufferInfo_validate_keeps_bindings(vbo4x3):
    # bindings of the buffer's target are restored, including a VAO's index
    # buffer which is part of the VAO's state
    vbo, _ = vbo4x3
    other = gt.createVBO(np.zeros((2, 3), dtype=np.float32))
    vaoIndices = gt.createVBO(
        np.arange(3, dtype=np.uint32), target=GL.GL_ELEMENT_ARRAY_BUFFER,
        dataType=GL.GL_UNSIGNED_INT)
    indices = gt.createVBO(
        np.arange(3, dtype=np.uint32), target=GL.GL_ELEMENT_ARRAY_BUFFER,
        dataType=GL.GL_UNSIGNED_INT)
    vao = gt.createVAO(
        {GL.GL_VERTEX_ARRAY: other}, indexBuffer=vaoIndices, legacy=True)

    gt._glBindVertexArray(vao.name)
    gt.bindVBO(other)
    try:
        assert vbo.validate()
        assert indices.validate()

        assert _getInteger(GL.GL_ARRAY_BUFFER_BINDING) == other.name.value
        assert _getInteger(GL.GL_ELEMENT_ARRAY_BUFFER_BINDING) == \
            vaoIndices.name.value
        assert _boundVAO() == vao.name
        assert GL.glGetError() == GL.GL_NO_ERROR
    finally:
        gt.unbindVBO(other)
        gt._glBindVertexArray(0)

    gt.deleteVAO(vao)
    for buffer in (other, vaoIndices, indices):
        gt.deleteVBO(buffer)


@pytest.mark.parametrize('start, length', [
    (-1, 2), (0, 0), (0, 13), (10, 3), (12, None)])
def test_mapBuffer_invalid_range(vbo4x3, start, length):
    vbo, _ = vbo4x3
    with pytest.raises(ValueError):
        gt.mapBuffer(vbo, start=start, length=length)

    # the buffer isn't left mapped
    arr = gt.mapBuffer(vbo)
    assert arr.shape == (4, 3)
    assert gt.unmapBuffer(vbo)
    gt.unbindVBO(vbo)


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


def test_bindTexture_default_target(win):
    texData = np.zeros((4, 4, 4), dtype=np.uint8)
    texture = gt.createTexImage2D(
        4, 4, internalFormat=GL.GL_RGBA, pixelFormat=GL.GL_RGBA,
        dataType=GL.GL_UNSIGNED_BYTE, data=texData.ctypes, unpackAlignment=1)
    name = texture.name.value

    # the target is taken from the descriptor, or `GL_TEXTURE_2D` otherwise
    for tex in (texture, name, GL.GLuint(name)):
        gt.bindTexture(tex)
        assert _getInteger(GL.GL_TEXTURE_BINDING_2D) == name
        gt.bindTexture(None)
        assert _getInteger(GL.GL_TEXTURE_BINDING_2D) == 0

    gt.deleteTexture(texture)


# ------------------------------------------------------------------------------
# Legacy material functions
#

_GL_DEFAULT_MATERIAL = {
    GL.GL_AMBIENT: [0.2, 0.2, 0.2, 1.0],
    GL.GL_DIFFUSE: [0.8, 0.8, 0.8, 1.0],
    GL.GL_SPECULAR: [0.0, 0.0, 0.0, 1.0],
    GL.GL_EMISSION: [0.0, 0.0, 0.0, 1.0]}


def _getMaterial(mode, face=GL.GL_FRONT):
    value = (GL.GLfloat * 4)()
    GL.glGetMaterialfv(face, mode, value)
    return list(value) if mode != GL.GL_SHININESS else value[0]


def _textureBinding(unit):
    gt.activeTexture(unit)
    binding = _getInteger(GL.GL_TEXTURE_BINDING_2D)
    enabled = bool(GL.glIsEnabled(GL.GL_TEXTURE_2D))
    gt.activeTexture(GL.GL_TEXTURE0)
    return binding, enabled


def _createTexture():
    texData = np.zeros((4, 4, 4), dtype=np.uint8)
    return gt.createTexImage2D(
        4, 4, internalFormat=GL.GL_RGBA, pixelFormat=GL.GL_RGBA,
        dataType=GL.GL_UNSIGNED_BYTE, data=texData.ctypes, unpackAlignment=1)


def _assertDefaultMaterial():
    for mode, expected in _GL_DEFAULT_MATERIAL.items():
        assert _getMaterial(mode) == pytest.approx(expected), mode
    assert _getMaterial(GL.GL_SHININESS) == pytest.approx(0.0)
    assert not GL.glIsEnabled(GL.GL_COLOR_MATERIAL)


@pytest.mark.parametrize('func, arg', [
    (gt.useMaterial, None), (gt.clearMaterial, None)])
def test_material_functions_deprecated(win, func, arg):
    with pytest.warns(DeprecationWarning, match='BlinnPhongMaterial'):
        func(arg)
    GL.glDisable(GL.GL_COLOR_MATERIAL)


def test_useMaterial_descriptor(win):
    texture = _createTexture()
    mat = gt.createMaterial(
        [(GL.GL_AMBIENT, (0.1, 0.2, 0.3, 1.0)),
         (GL.GL_DIFFUSE, (0.4, 0.5, 0.6, 1.0)),
         (GL.GL_SHININESS, 32.0)],
        textures=[(GL.GL_TEXTURE1, texture)])

    with pytest.warns(DeprecationWarning):
        gt.useMaterial(mat)
    assert _getMaterial(GL.GL_AMBIENT) == pytest.approx([0.1, 0.2, 0.3, 1.0])
    assert _getMaterial(GL.GL_DIFFUSE) == pytest.approx([0.4, 0.5, 0.6, 1.0])
    assert _getMaterial(GL.GL_SHININESS) == pytest.approx(32.0)
    # modes without a value are zero
    assert _getMaterial(GL.GL_SPECULAR) == pytest.approx([0, 0, 0, 0])
    assert not GL.glIsEnabled(GL.GL_COLOR_MATERIAL)

    # textures are bound to their units, the first unit is left active
    assert _textureBinding(GL.GL_TEXTURE1) == (texture.name.value, True)
    assert _getInteger(GL.GL_ACTIVE_TEXTURE) == GL.GL_TEXTURE0

    with pytest.warns(DeprecationWarning):
        gt.clearMaterial(mat)
    _assertDefaultMaterial()
    assert _textureBinding(GL.GL_TEXTURE1) == (0, False)

    gt.deleteTexture(texture)


def test_useMaterial_without_textures(win):
    texture = _createTexture()
    mat = gt.createMaterial(textures=[(GL.GL_TEXTURE0, texture)])

    with pytest.warns(DeprecationWarning):
        gt.useMaterial(mat, useTextures=False)
    assert _textureBinding(GL.GL_TEXTURE0) == (0, False)
    with pytest.warns(DeprecationWarning):
        gt.clearMaterial(mat)

    gt.deleteTexture(texture)


def test_useMaterial_object(win):
    from psychopy.visual.stim3d import BlinnPhongMaterial

    texture = _createTexture()
    mat = BlinnPhongMaterial(
        win, diffuseColor=(1, -1, -1), specularColor=(-1, 1, -1),
        ambientColor=(-1, -1, 1), shininess=20, diffuseTexture=texture)

    with pytest.warns(DeprecationWarning):
        gt.useMaterial(mat)
    assert _getMaterial(GL.GL_DIFFUSE) == pytest.approx([1, 0, 0, 1])
    assert _getMaterial(GL.GL_SPECULAR) == pytest.approx([0, 1, 0, 1])
    assert _getMaterial(GL.GL_AMBIENT) == pytest.approx([0, 0, 1, 1])
    assert _getMaterial(GL.GL_SHININESS) == pytest.approx(20.0)
    assert _textureBinding(GL.GL_TEXTURE0) == (texture.name.value, True)

    with pytest.warns(DeprecationWarning):
        gt.clearMaterial(mat)
    _assertDefaultMaterial()
    assert _textureBinding(GL.GL_TEXTURE0) == (0, False)

    gt.deleteTexture(texture)


def test_useMaterial_none(win):
    # resets to defaults with color tracking enabled
    mat = gt.createMaterial(
        [(GL.GL_SPECULAR, (1.0, 0.0, 0.0, 1.0)),
         (GL.GL_EMISSION, (0.0, 1.0, 0.0, 1.0)),
         (GL.GL_SHININESS, 50.0)])
    with pytest.warns(DeprecationWarning):
        gt.useMaterial(mat)
        gt.useMaterial(None)
    assert GL.glIsEnabled(GL.GL_COLOR_MATERIAL)
    assert _getMaterial(GL.GL_SPECULAR) == pytest.approx([0, 0, 0, 1])
    assert _getMaterial(GL.GL_EMISSION) == pytest.approx([0, 0, 0, 1])
    assert _getMaterial(GL.GL_SHININESS) == pytest.approx(0.0)

    # ambient and diffuse track the current color
    GL.glColor4f(0.25, 0.5, 0.75, 1.0)
    assert _getMaterial(GL.GL_DIFFUSE) == pytest.approx([0.25, 0.5, 0.75, 1])
    assert _getMaterial(GL.GL_AMBIENT) == pytest.approx([0.25, 0.5, 0.75, 1])

    GL.glDisable(GL.GL_COLOR_MATERIAL)
    GL.glColor4f(1.0, 1.0, 1.0, 1.0)


@pytest.mark.parametrize('name, fields', [
    ('mineralMaterials',
     ['emerald', 'jade', 'obsidian', 'pearl', 'ruby', 'turquoise']),
    ('metalMaterials', ['brass', 'bronze', 'chrome', 'copper', 'gold', 'silver']),
    ('plasticMaterials', ['black', 'cyan', 'green', 'red', 'white', 'yellow']),
    ('rubberMaterials', ['black', 'cyan', 'green', 'red', 'white', 'yellow']),
])
def test_material_presets(name, fields):
    with pytest.warns(DeprecationWarning, match=name):
        presets = getattr(gt, name)
    assert list(presets._fields) == fields
    assert all(isinstance(mat, gt.Material) for mat in presets)

    # presets are only created once
    with pytest.warns(DeprecationWarning):
        assert getattr(gt, name) is presets


def test_material_presets_import():
    with pytest.warns(DeprecationWarning, match='metalMaterials'):
        from psychopy.tools.gltools import metalMaterials
    gold = metalMaterials.gold
    assert list(gold.params[GL.GL_DIFFUSE]) == pytest.approx(
        [0.75164, 0.60648, 0.22648, 1.0])
    assert gold.params[GL.GL_SHININESS].value == pytest.approx(0.4 * 128.0)

    # other missing attributes still raise
    with pytest.raises(AttributeError):
        gt.notAnAttribute


def test_useMaterial_preset(win):
    with pytest.warns(DeprecationWarning):
        gold = gt.metalMaterials.gold
        gt.useMaterial(gold)
    assert _getMaterial(GL.GL_DIFFUSE, GL.GL_BACK) == pytest.approx(
        [0.75164, 0.60648, 0.22648, 1.0])
    with pytest.warns(DeprecationWarning):
        gt.clearMaterial(gold)
    _assertDefaultMaterial()


@pytest.mark.parametrize('passTexture', [True, False])
def test_unbindTexture(win, passTexture):
    texture = _createTexture()
    gt.bindTexture(texture, unit=GL.GL_TEXTURE0)
    GL.glEnable(GL.GL_TEXTURE_2D)
    assert _textureBinding(GL.GL_TEXTURE0) == (texture.name.value, True)

    with pytest.warns(DeprecationWarning, match='bindTexture'):
        gt.unbindTexture(texture if passTexture else None)
    assert _textureBinding(GL.GL_TEXTURE0) == (0, False)
    assert GL.glGetError() == GL.GL_NO_ERROR

    gt.deleteTexture(texture)


def test_all_names_exist():
    # `from psychopy.tools.gltools import *` fails if any are missing
    assert [name for name in gt.__all__ if not hasattr(gt, name)] == []


def test_SimpleMaterial_deprecated():
    with pytest.warns(DeprecationWarning, match='BlinnPhongMaterial'):
        try:
            gt.SimpleMaterial()
        except AttributeError:
            pass  # only the warning is tested, the class is known to be broken


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
