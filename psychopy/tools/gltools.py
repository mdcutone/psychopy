#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""OpenGL related helper functions.

"""

# Part of the PsychoPy library
# Copyright (C) 2018 Jonathan Peirce
# Distributed under the terms of the GNU General Public License (GPL).

import ctypes
import array
from io import StringIO
from collections import namedtuple, OrderedDict
import pyglet.gl as GL  # using Pyglet for now
from contextlib import contextmanager
from PIL import Image
import numpy as np
import os
from psychopy import logging


# -------------------------
# Framebuffer Objects (FBO)
# -------------------------
#
class FramebufferInfo(object):
    """Framebuffer data descriptor. This class only stores information used to
    create and access framebuffers. There is no guarantee the data stored
    represents the current state of the framebuffer it references.

    """
    __slots__ = [
        'id',
        'target',
        'width',
        'height',
        'samples',
        'imageAttachments',
        'renderPass']

    def __init__(self,
                 name=GL.GLuint(0),
                 target=GL.GL_FRAMEBUFFER,
                 width=0,
                 height=0,
                 samples=1,
                 imageAttachments=None,
                 renderPass=None):
        """Constructor for FramebufferInfo. No framebuffer is created during the
        initialization of this class.

        Parameters
        ----------
        name : GLuint
            Assigned framebuffer name, uninitialized if 0.
        target : int
            Framebuffer target (either GL_FRAMEBUFFER or GL_FRAMEBUFFER_EXT).
        width and height : int
            Dimensions of the framebuffer in pixels. Dimensions are only
            informative to ensure attachments have appropriate dimensions. Both
            values must be >0 at initialization.
        samples : int
            Number of samples for multisample image attachments. This is only
            informative, allowing us to check if all attachments use the same
            number of samples.
        imageAttachments : dict
            Image attachments associated with this framebuffer. Attachments are
            specified as a dictionary where keys are attachment points (e.g.
            GL_COLOR_ATTACHMENT0) and color buffer descriptor types
            (RenderbufferInfo or TexImage2D) are values.

        Notes
        -----
        If using multisample buffers, all attachment images must use the same
        number of samples!.

        """
        self.id = name
        self.target = target
        self.width = int(width)
        self.height = int(height)
        self.samples = int(samples)
        self.imageAttachments = \
            dict() if imageAttachments is None else imageAttachments

    def __eq__(self, other):
        # equivalent if the target and ID are the same
        if not isinstance(other, FramebufferInfo):
            raise TypeError(
                "Incompatible type '{}' for binary operator '=='.".format(
                    type(other).__name__))

        return self.id == other.id and self.target == other.target


def createFramebuffer(fboInfo, configAttachments=True):
    """Create a Framebuffer Object.

    Parameters
    ----------
    fboInfo : :obj:`FramebufferInfo`
        Framebuffer data descriptor.
    configAttachments : :obj:`bool`
        Configure any uninitialized attachments to match the framebuffer's
        properties.

    Returns
    -------
    :obj:`bool`
        True or False, whether the framebuffer is complete.

    Notes
    -----
        1. All buffers must have the same number of samples.
        2. The 'userData' field of the returned descriptor is a dictionary that
          can be used to store arbitrary data associated with the FBO.
        3. Framebuffers need a single attachment to be complete.

    Examples
    --------
    Setting up a framebuffer with image attachments::
        # create some color and depth buffers, these will automatically adopt
        # the dimensions of the framebuffer
        colorTex = gltools.TexImage2dInfo()
        depthRb = gltools.RenderbufferInfo(
            internalFormat=GL.GL_DEPTH24_STENCIL8)
        fbo = gltools.FramebufferInfo(
            width=800,
            height=600,
            imageAttachments={GL.GL_COLOR_ATTACHMENT0: colorBuffer,
                              GL.GL_DEPTH_STENCIL_ATTACHMENT: depthBuffer})
        isComplete = gltools.createFramebuffer(fbo)

        # adding attachments can be deferred to after framebuffer initialization
        gltools.updateFramebuffer(fbo, {GL.GL_COLOR_ATTACHMENT1: colorTex2})

    """
    # create a framebuffer descriptor
    GL.glGenFramebuffers(1, ctypes.byref(fboInfo.id))

    # setup attachments
    if fboInfo.imageAttachments:
        return updateFramebuffer(
            fboInfo, fboInfo.imageAttachments, configAttachments)

    return False  # no attachments, buffer is incomplete


def updateFramebuffer(fboInfo,
                      imageAttachments=None,
                      configAttachments=True,
                      keepBindState=False):
    """Update a framebuffer's image attachments.

    Parameters
    ----------
    fboInfo : FramebufferInfo
        Framebuffer descriptor to update attachments.
    imageAttachments : dict
        Image attachments to update. Attachments are specified as a dictionary
        where keys are attachment points (e.g. GL_COLOR_ATTACHMENT0,
        GL_DEPTH_STENCIL_ATTACHMENT etc.) and image buffer descriptor types
        (RenderbufferInfo or TexImage2dInfo) are values. If descriptors are not
        initialized (name == 0), they will be before binding.
    configAttachments : :obj:`bool`
        Configure any uninitialized attachments, matching the framebuffer's
        properties within their descriptors.
    keepBindState : bool
        Keep the current framebuffer binding state. This is not required if the
        FBO referenced in fboInfo is currently bound. This incurs some
        additional overhead but may be necessary if you want to make changes to
        the FBO without disturbing the current binding state.

    Returns
    -------
    bool
        Completeness status of the framebuffer after adding attachments.

    Examples
    --------
    Adding attachments can be deferred to after framebuffer initialization::
        gltools.updateFramebuffer(fbo, {GL.GL_COLOR_ATTACHMENT1: colorTex2})

    """
    # handle framebuffer bindings
    prevFBO = 0
    if not keepBindState:  # avoid the unnecessary glGet* call
        prevFBO = getIntegerv(GL.GL_FRAMEBUFFER_BINDING)
        # don't rebind if the target FBO is already bound
        if fboInfo.id != prevFBO:
            GL.glBindFramebuffer(fboInfo.target, fboInfo.id)

    # update color and depth-stencil attachments
    if imageAttachments is not None:
        for attachPoint, imageBuffer in fboInfo.imageAttachments.items():
            # attach the buffer, how it's done depends on the type
            if isinstance(imageBuffer, TexImage2dInfo):
                if imageBuffer.id.value == GL.GL_NONE:  # not initialized
                    if configAttachments:
                        imageBuffer.width = fboInfo.width
                        imageBuffer.height = fboInfo.height
                        if imageBuffer.isMultisample():
                            imageBuffer.samples = fboInfo.samples
                    createTexImage2D(imageBuffer)
                GL.glFramebufferTexture2D(
                    fboInfo.target, attachPoint, imageBuffer.target,
                    imageBuffer.id, 0)
            elif isinstance(imageBuffer, RenderbufferInfo):
                if imageBuffer.id.value == GL.GL_NONE:  # not initialized
                    if configAttachments:
                        imageBuffer.width = fboInfo.width
                        imageBuffer.height = fboInfo.height
                        imageBuffer.samples = fboInfo.samples
                    createRenderbuffer(imageBuffer)
                GL.glFramebufferRenderbuffer(
                    fboInfo.target, attachPoint, imageBuffer.target,
                    imageBuffer.id)

            # update the attachment point in the descriptor
            fboInfo.imageAttachments[attachPoint] = imageBuffer

    # check the FBO for completeness
    isComplete = GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER) == \
                 GL.GL_FRAMEBUFFER_COMPLETE

    # rebind previous framebuffer
    if not keepBindState and fboInfo.id != prevFBO:
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, prevFBO)

    return isComplete


def validateFramebuffer(fboInfo, keepBindState=False):
    """Check if all references in the framebuffer descriptor match the OpenGL
    state. This is intended for debugging purposes only.

    Parameters
    ----------
    fboInfo : FramebufferInfo
        Framebuffer descriptor to query.
    keepBindState : bool
        Keep the current framebuffer binding state. This is not required if the
        FBO referenced in fboInfo is currently bound. This incurs some
        additional overhead but may be necessary if you want to make changes to
        the FBO without disturbing the current binding state.

    Returns
    -------
    bool
        True if all descriptor values are congruent with the driver's.

    """
    # handle framebuffer bindings
    prevFBO = 0
    if not keepBindState:
        prevFBO = getIntegerv(GL.GL_FRAMEBUFFER_BINDING)
        # don't rebind if the target FBO is already bound
        if fboInfo.id != prevFBO:
            GL.glBindFramebuffer(fboInfo.target, fboInfo.id)

    isValid = True
    if fboInfo.imageAttachments is not None:
        objType = GL.GLint()
        objName = GL.GLint()
        for attachPoint, imageBuffer in fboInfo.imageAttachments.items():
            GL.glGetFramebufferAttachmentParameteriv(
                fboInfo.target, attachPoint,
                GL.GL_FRAMEBUFFER_ATTACHMENT_OBJECT_TYPE,
                ctypes.byref(objType))

            isTextureType = isinstance(imageBuffer, TexImage2dInfo)
            isRenderBufferType = isinstance(imageBuffer, RenderbufferInfo)

            if objType.value == GL.GL_TEXTURE and isTextureType or \
                    objType.value == GL.GL_RENDERBUFFER and isRenderBufferType:
                GL.glGetFramebufferAttachmentParameteriv(
                    fboInfo.target, attachPoint,
                    GL.GL_FRAMEBUFFER_ATTACHMENT_OBJECT_NAME,
                    ctypes.byref(objName))
                if imageBuffer.id.value != objName.value:
                    isValid = False
            else:
                isValid = False

    # rebind previous framebuffer
    if not keepBindState and fboInfo.id != prevFBO:
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, prevFBO)

    return isValid


def isFramebufferComplete():
    """Check if the currently bound framebuffer is complete.

    Returns
    -------
    :obj:`bool'

    """
    return GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER) == \
           GL.GL_FRAMEBUFFER_COMPLETE


def deleteFramebuffer(fboInfo):
    """Delete a framebuffer.

    Returns
    -------
    :obj:`None'

    """
    GL.glDeleteFramebuffers(1, fboInfo.id)


def blitFramebuffer(srcRect, dstRect=None, filter=GL.GL_LINEAR):
    """Copy a block of pixels between framebuffers via blitting. Read and draw
    framebuffers must be bound prior to calling this function. Beware, the
    scissor box and viewport are changed when this is called to dstRect.

    Parameters
    ----------
    srcRect : :obj:`list` of :obj:`int`
        List specifying the top-left and bottom-right coordinates of the region
        to copy from (<X0>, <Y0>, <X1>, <Y1>).
    dstRect : :obj:`list` of :obj:`int` or :obj:`None`
        List specifying the top-left and bottom-right coordinates of the region
        to copy to (<X0>, <Y0>, <X1>, <Y1>). If None, srcRect is used for
        dstRect.
    filter : :obj:`int`
        Interpolation method to use if the image is stretched, default is
        GL_LINEAR, but can also be GL_NEAREST.

    Returns
    -------
    None

    Examples
    --------
    # bind framebuffer to read pixels from
    GL.glBindFramebuffer(GL.GL_READ_FRAMEBUFFER, srcFbo)

    # bind framebuffer to draw pixels to
    GL.glBindFramebuffer(GL.GL_DRAW_FRAMEBUFFER, dstFbo)

    gltools.blitFBO((0,0,800,600), (0,0,800,600))

    # unbind both read and draw buffers
    GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)

    """
    # in most cases srcRect and dstRect will be the same.
    if dstRect is None:
        dstRect = srcRect

    # GL.glViewport(*dstRect)
    # GL.glEnable(GL.GL_SCISSOR_TEST)
    # GL.glScissor(*dstRect)
    GL.glBlitFramebuffer(srcRect[0], srcRect[1], srcRect[2], srcRect[3],
                         dstRect[0], dstRect[1], dstRect[2], dstRect[3],
                         GL.GL_COLOR_BUFFER_BIT,  # colors only for now
                         filter)

    # GL.glDisable(GL.GL_SCISSOR_TEST)


@contextmanager
def useFBO(fbo):
    """Context manager for Framebuffer Object bindings. This function yields
    the framebuffer name as an integer.

    Parameters
    ----------
    fbo :obj:`int` or :obj:`Framebuffer`
        OpenGL Framebuffer Object name/ID or descriptor.

    Yields
    -------
    int
        OpenGL name of the framebuffer bound in the context.

    Returns
    -------
    None

    Examples
    --------
    # FBO bound somewhere deep in our code
    GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, someOtherFBO)

    ...

    # create a new FBO, but we have no idea what the currently bound FBO is
    fbo = createFBO()

    # use a context to bind attachments
    with bindFBO(fbo):
        attach(GL.GL_COLOR_ATTACHMENT0, colorTex)
        attach(GL.GL_DEPTH_ATTACHMENT, depthRb)
        attach(GL.GL_STENCIL_ATTACHMENT, depthRb)
        isComplete = gltools.isComplete()

    # someOtherFBO is still bound!

    """
    prevFBO = GL.GLint()
    GL.glGetIntegerv(GL.GL_FRAMEBUFFER_BINDING, ctypes.byref(prevFBO))
    toBind = fbo.id if isinstance(fbo, FramebufferInfo) else int(fbo)
    GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, toBind)
    try:
        yield toBind
    finally:
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, prevFBO.value)


# ------------------------------
# Renderbuffer Objects Functions
# ------------------------------
#
class RenderbufferInfo(object):
    """Renderbuffers contain image data and are optimized for use as render
    targets. See https://www.khronos.org/opengl/wiki/Renderbuffer_Object for
    more information.

    Parameters
    ----------
    name : :obj:`GLuint`
        OpenGL name/ID. The renderbuffer is not initialized if 0.
    target : :obj:`int`
        The target renderbuffer.
    width : :obj:`int`
        Buffer width in pixels.
    height : :obj:`int`
        Buffer height in pixels.
    internalFormat : :obj:`int`
        Format for renderbuffer data (e.g. GL_RGBA8, GL_DEPTH24_STENCIL8).
    samples : :obj:`int`
        Number of samples for multi-sampling, should be >1 and power-of-two.
        Works with one sample, but will raise a warning.

    """
    __slots__ = ['id', 'target', 'width', 'height', 'internalFormat', 'samples']

    def __init__(self,
                 name=GL.GLuint(0),
                 target=GL.GL_RENDERBUFFER,
                 width=0,
                 height=0,
                 internalFormat=GL.GL_RGBA8,
                 samples=1):
        self.id = name
        self.target = target
        self.width = width
        self.height = height
        self.internalFormat = internalFormat
        self.samples = samples

    def __eq__(self, other):
        # equivalent if the target and ID are the same
        if not isinstance(other, RenderbufferInfo):
            raise TypeError()

        return self.id == other.id and self.target == other.target

    @property
    def isMultisample(self):
        return self.samples > 1


def createRenderbuffer(rbInfo):
    """Create a new Renderbuffer Object with a specified descriptor. A
    multisample storage buffer is created if samples > 1.

    Renderbuffers contain image data and are optimized for use as render
    targets. See https://www.khronos.org/opengl/wiki/Renderbuffer_Object for
    more information.

    Parameters
    ----------
    rbInfo : :obj:`RenderbufferInfo`
        Renderbuffer descriptor.

    """
    # create a new renderbuffer ID
    GL.glGenRenderbuffers(1, ctypes.byref(rbInfo.id))
    GL.glBindRenderbuffer(GL.GL_RENDERBUFFER, rbInfo.id)

    if rbInfo.samples > 1:
        # determine if the 'samples' value is valid
        maxSamples = getIntegerv(GL.GL_MAX_SAMPLES)
        if (rbInfo.samples & (rbInfo.samples - 1)) != 0:
            raise ValueError('Invalid number of samples, must be power-of-two.')
        elif rbInfo.samples > maxSamples:
            raise ValueError('Invalid number of samples, must be <{}.'.format(
                maxSamples))

        # create a multisample render buffer storage
        GL.glRenderbufferStorageMultisample(
            rbInfo.target,
            rbInfo.samples,
            rbInfo.internalFormat,
            rbInfo.width,
            rbInfo.height)

    else:
        print("make rb")
        GL.glRenderbufferStorage(
            rbInfo.target,
            rbInfo.internalFormat,
            rbInfo.width,
            rbInfo.height)

    # done, unbind it
    GL.glBindRenderbuffer(rbInfo.target, 0)


def deleteRenderbuffer(rbInfo):
    """Free the resources associated with a renderbuffer. This invalidates the
    renderbuffer's ID.

    """
    GL.glDeleteRenderbuffers(1, rbInfo.id)


# -----------------
# Texture Functions
# -----------------
#
class TexImage2dInfo(object):
    """Framebuffer data descriptor. This class only stores information used to
    create and access framebuffers. There is no guarantee the data stored
    represents the current state of the framebuffer it references.

    """
    __slots__ = [
        'id',
        'target',
        'width',
        'height',
        'level',
        'samples',
        'internalFormat',
        'pixelFormat',
        'dataType',
        'unpackAlignment',
        'texParameters',
        'dataPtr']

    def __init__(self,
                 name=GL.GLuint(0),
                 target=GL.GL_TEXTURE_2D,
                 width=0,
                 height=0,
                 level=0,
                 samples=1,
                 internalFormat=GL.GL_RGBA8,
                 pixelFormat=GL.GL_RGBA,
                 dataType=GL.GL_FLOAT,
                 unpackAlignment=4,
                 texParameters=None,
                 dataPtr=None):
        """Constructor for TexImage2dInfo. No texture is initialized until
        passed to createTexImage2D.

        Parameters
        ----------
        name : :obj:`GLuint`
            OpenGL name/ID. The texture is not initialized if 0.
        target : :obj:`int`
            The target texture should only be either GL_TEXTURE_2D,
            GL_TEXTURE_RECTANGLE, or GL_TEXTURE_2D_MULTISAMPLE.
        width : :obj:`int`
            Texture width in pixels.
        height : :obj:`int`
            Texture height in pixels.
        level : :obj:`int`
            LOD number of the texture, should be 0 if GL_TEXTURE_RECTANGLE is
            the target. Only applicable if 'target' is GL_TEXTURE_2D or
            GL_TEXTURE_RECTANGLE.
        samples : :obj:`int`
            Number of samples per-pixel. This only applies when 'target' is
            GL_TEXTURE_2D_MULTISAMPLE. If using any other 2D texture target,
            'samples' should == 1. Should be >1 and power-of-two. Works with one
            sample, but will raise a warning.
        internalFormat : :obj:`int`
            Internal format for texture data (e.g. GL_RGBA8, GL_R11F_G11F_B10F).
        pixelFormat : :obj:`int`
            Pixel data format (e.g. GL_RGBA, GL_DEPTH_STENCIL). Only applicable
            if 'target' is GL_TEXTURE_2D or GL_TEXTURE_RECTANGLE.
        dataType : :obj:`int`
            Data type for pixel data (e.g. GL_FLOAT, GL_UNSIGNED_BYTE).
        dataPtr : :obj:`ctypes` or :obj:`None`
            Ctypes pointer to image data. If None is specified, the texture will
            be created but pixel data will be uninitialized. Only applicable
            if 'target' is GL_TEXTURE_2D or GL_TEXTURE_RECTANGLE. The data type
            of the data should be compatible with 'dataType'.
        unpackAlignment : :obj:`int`
            Alignment requirements of each row in memory. Default is 4. Only
            applicable if 'target' is GL_TEXTURE_2D or GL_TEXTURE_RECTANGLE.
        texParameters : :obj:`dict`
            Optional texture parameters specified as a dictionary. These
            values are passed to 'glTexParameteri'.

        Examples
        --------
        Creating an empty texture::

            import pyglet.gl as GL
            textureDesc = createTexImage2D(
                1024, 1024, internalFormat=GL.GL_RGBA8)

        Loading an image from file into video memory::

            from PIL import Image
            import numpy as np
            im = Image.open(imageFile)  # 8bpp!
            im = im.transpose(Image.FLIP_TOP_BOTTOM)  # origin is at bottom
            im = im.convert("RGBA")
            pixelData = np.array(im).ctypes  # convert to ctypes!

            # fill out a descriptor
            width = pixelData.shape[1]
            height = pixelData.shape[0]
            textureDesc = gltools.TexImage2dInfo(
                width,
                height,
                internalFormat=GL.GL_RGBA,
                pixelFormat=GL.GL_RGBA,
                dataType=GL.GL_UNSIGNED_BYTE,
                data=texture_array.ctypes,
                unpackAlignment=1,
                texParameters={GL.GL_TEXTURE_MAG_FILTER: GL.GL_LINEAR,
                               GL.GL_TEXTURE_MIN_FILTER: GL.GL_LINEAR})


            createTexImage2D(textureDesc)  # create the texture
            GL.glBindTexture(GL.GL_TEXTURE_2D, textureDesc.id)  # use it

        """
        self.id = name
        self.target = target
        self.width = int(width)
        self.height = int(height)
        self.level = int(level)
        self.samples = int(samples)
        self.internalFormat = int(internalFormat)
        self.pixelFormat = pixelFormat
        self.dataType = dataType
        self.unpackAlignment = unpackAlignment
        self.dataPtr = dataPtr
        self.texParameters = texParameters

    def __eq__(self, other):
        # equivalent if the target and ID are the same
        if not isinstance(other, FramebufferInfo):
            raise TypeError(
                "Incompatible type '{}' for binary operator '=='.".format(
                    type(other).__name__))

        return self.id == other.id and self.target == other.target

    def isMultisample(self):
        return self.target == GL.GL_TEXTURE_2D_MULTISAMPLE

    @property
    def isInitialized(self):
        return self.id.value > 0


def createTexImage2D(textureInfo):
    """Create a 2D texture in video memory. This can only create a single 2D
    texture with targets GL_TEXTURE_2D, GL_TEXTURE_RECTANGLE or
    GL_TEXTURE_2D_MULTISAMPLE.

    Parameters
    ----------
    textureInfo : TexImage2dInfo
        2D texture descriptor.

    Notes
    -----
    Previous textures are unbound after calling 'createTexImage2D'.

    Examples
    --------
    Creating a texture from a TexImage2dInfo object::

        createTexImage2D(textureDesc)
        GL.glBindTexture(GL.GL_TEXTURE_2D, textureDesc.id)  # use it

    """
    width = int(textureInfo.width)
    height = int(textureInfo.height)

    if width <= 0 or height <= 0:
        raise ValueError("Invalid image dimensions {} x {}.".format(
            width, height))

    if textureInfo.target == GL.GL_TEXTURE_RECTANGLE:
        if textureInfo.level != 0:
            raise ValueError("Invalid level for target GL_TEXTURE_RECTANGLE, "
                             "must be 0.")
        GL.glEnable(GL.GL_TEXTURE_RECTANGLE)

    if textureInfo.target in (GL.GL_TEXTURE_RECTANGLE, GL.GL_TEXTURE_2D):
        GL.glGenTextures(1, ctypes.byref(textureInfo.id))
        GL.glBindTexture(textureInfo.target, textureInfo.id)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, textureInfo.unpackAlignment)
        GL.glTexImage2D(textureInfo.target,
                        textureInfo.level,
                        textureInfo.internalFormat,
                        width, height, 0,
                        textureInfo.pixelFormat,
                        textureInfo.dataType,
                        textureInfo.dataPtr)
    elif textureInfo.target == GL.GL_TEXTURE_2D_MULTISAMPLE:
        # determine if the 'samples' value is valid
        maxSamples = getIntegerv(GL.GL_MAX_SAMPLES)
        if (textureInfo.samples & (textureInfo.samples - 1)) != 0:
            raise ValueError('Invalid number of samples, must be power-of-two.')
        elif textureInfo.samples <= 0 or textureInfo.samples > maxSamples:
            raise ValueError('Invalid number of samples, must be <{}.'.format(
                maxSamples))

        colorTexId = GL.GLuint()
        GL.glGenTextures(1, ctypes.byref(colorTexId))
        GL.glBindTexture(textureInfo.target, colorTexId)
        GL.glTexImage2DMultisample(
            textureInfo.target,
            textureInfo.samples,
            textureInfo.internalFormat,
            width, height, GL.GL_TRUE)
    else:
        raise ValueError("Unsupported texture target specified.")

    # apply texture parameters
    if textureInfo.texParameters:
        for pname, param in textureInfo.texParameters.items():
            GL.glTexParameteri(textureInfo.target, pname, param)

    GL.glBindTexture(textureInfo.target, 0)


def deleteTexture(texture):
    """Free the resources associated with a texture. This invalidates the
    texture's ID.

    Returns
    -------
    :obj:`None'

    """
    GL.glDeleteTextures(1, texture.id)


# ---------------------------
# Vertex Buffer Objects (VBO)
# ---------------------------
#
class VertexBufferInfo(object):
    """Single-storage array buffer data descriptor."""

    __slots__ = [
        'name',
        'target',
        'dataType',
        'dataPtr',
        'usage',
        'vectorSize']

    def __init__(self,
                 name=GL.GLuint(0),
                 target=GL.GL_ARRAY_BUFFER,
                 dataType=GL.GL_FLOAT,
                 dataPtr=None,
                 usage=GL.GL_STATIC_DRAW,
                 vectorSize=3):
        self.name = name
        self.target = target
        self.dataType = dataType
        self.dataPtr = dataPtr  # only valid if isInitialized > 0
        self.usage = usage
        self.vectorSize = vectorSize

    @property
    def isInitialized(self):
        return self.name.value > 0


def createVertexBuffer(vboInfo, uploadArray=None):
    """Create a single-storage array buffer, often referred to as Vertex Buffer
    Object (VBO).

    Parameters
    ----------
    vboInfo : :obj:`VertexBufferInfo`
        Vertex buffer data descriptor.
    uploadArray : :obj:`list` of :obj:`float` or :obj:`int`, optional
        Coordinates as a 1D array of values (e.g. [X0, Y0, X1, Y1, ...]) to
        upload. The 'dataPtr' in the descriptor will be assigned a ctypes
        pointer to the array. The value of 'dataPtr' will be overwritten if
        uploadArray is not None. Values in the provided array will be re-cast to
        something compatible with 'dataType'.

    Notes
    -----
    Creating vertex buffers is a computationally expensive operation. Be sure to
    load all resources before entering your experiment's main loop.

    Examples
    --------
    # vertices of a triangle
    verts = [ 1.0,  1.0, 0.0,   # v0
              0.0, -1.0, 0.0,   # v1
             -1.0,  1.0, 0.0]   # v2

    # load vertices to graphics device, return a descriptor
    vboDesc = createVBO(verts, 3)

    # draw
    GL.glBindBuffer(GL.GL_ARRAY_BUFFER, vboDesc.id)
    GL.glVertexPointer(vboDesc.vertexSize, vboDesc.dtype, 0, None)
    GL.glEnableClientState(vboDesc.bufferType)
    GL.glDrawArrays(GL.GL_TRIANGLES, 0, vboDesc.indices)
    GL.glFlush()

    """
    if uploadArray is not None:
        if vboInfo.dataType == GL.GL_FLOAT:
            useType = GL.GLfloat
        elif vboInfo.dataType == GL.GL_DOUBLE:
            useType = GL.GLdouble
        elif vboInfo.dataType == GL.GL_UNSIGNED_INT:
            useType = GL.GLuint
        elif vboInfo.dataType == GL.GL_UNSIGNED_SHORT:
            useType = GL.GLushort
        else:
            raise ValueError(
                "Invalid GL data type specified, must be GL_FLOAT, GL_DOUBLE, "
                "GL_UNSIGNED_INT, or GL_UNSIGNED_SHORT.")
        if isinstance(uploadArray, array.array):
            addr, count = uploadArray.buffer_info()
            vboInfo.dataPtr = ctypes.cast(
                addr, ctypes.POINTER((useType * count)))[0]
        else:
            count = len(uploadArray)
            vboInfo.dataPtr = (useType * count)(*uploadArray)
    else:
        if vboInfo.dataPtr is None:
            raise ValueError("No data pointer in vertex buffer descriptor!")

    GL.glGenBuffers(1, ctypes.byref(vboInfo.name))
    GL.glBindBuffer(vboInfo.target, vboInfo.name)
    GL.glBufferData(vboInfo.target,
                    ctypes.sizeof(vboInfo.dataPtr),
                    vboInfo.dataPtr,
                    vboInfo.usage)
    GL.glBindBuffer(vboInfo.target, 0)


class VertexArrayInfo(object):
    """Single-storage array buffer data descriptor."""

    __slots__ = [
        'name',
        'vertexBuffers',
        'indexBuffer',
        'indices',
        'drawMode']

    def __init__(self,
                 name=GL.GLuint(0),
                 vertexBuffers=None,
                 indexBuffer=None,
                 indices=0,
                 drawMode=GL.GL_TRIANGLES):
        self.name = name
        self.vertexBuffers = dict() if vertexBuffers is None else vertexBuffers
        self.indexBuffer = indexBuffer
        self.indices = indices  # only valid if isInitialized == True
        self.drawMode = drawMode

        if self.indexBuffer is not None:
            if self.indexBuffer.target != GL.GL_ELEMENT_ARRAY_BUFFER:
                raise ValueError(
                    "Index buffer target must be GL_ELEMENT_ARRAY_BUFFER.")

    @property
    def isIndexed(self):
        return self.indexBuffer is not None

    @property
    def isInitialized(self):
        return self.name.value > 0


def createVertexArray(vaoInfo):
    """Create a Vertex Array Object (VAO) with specified Vertex Buffer Objects.
    VAOs store buffer binding states, reducing CPU overhead when drawing objects
    with vertex data stored in VBOs.

    Parameters
    ----------
    vertexBuffers : :obj:`dict`
        Specify vertex attributes VBO descriptors apply to.
    indexBuffer : :obj:`list` of :obj:`int`, optional
        Index array of elements. If provided, an element array is created from
        the array. The returned descriptor will have isIndexed=True. This
        requires the VAO be drawn with glDrawElements instead of glDrawArrays.

    Returns
    -------
    VertexArrayObject
        A descriptor with vertex array information.

    Examples
    --------
    # create a VAO
    vaoDesc = createVAO(vboVerts, vboTexCoords, vboNormals)

    # draw the VAO, renders the mesh
    drawVAO(vaoDesc, GL.GL_TRIANGLES)

    """
    if not vaoInfo.vertexBuffers:  # in case an empty list is passed
        raise ValueError("No buffers specified in VAO descriptor.")

    # create a vertex buffer ID
    GL.glGenVertexArrays(1, ctypes.byref(vaoInfo.name))
    print(vaoInfo.name)
    GL.glBindVertexArray(vaoInfo.name)

    for attr, vboInfo in vaoInfo.vertexBuffers.items():
        GL.glBindBuffer(vboInfo.target, vboInfo.name)
        if attr == GL.GL_VERTEX_ARRAY:
            GL.glVertexPointer(vboInfo.vectorSize, vboInfo.dataType, 0, None)
            GL.glEnableClientState(GL.GL_VERTEX_ARRAY)
        elif attr == GL.GL_TEXTURE_COORD_ARRAY:
            GL.glTexCoordPointer(vboInfo.vectorSize, vboInfo.dataType, 0, None)
            GL.glEnableClientState(GL.GL_TEXTURE_COORD_ARRAY)
        elif attr == GL.GL_NORMAL_ARRAY:
            GL.glNormalPointer(vboInfo.dataType, 0, None)
            GL.glEnableClientState(GL.GL_NORMAL_ARRAY)
        elif attr == GL.GL_COLOR_ARRAY:
            GL.glColorPointer(vboInfo.vectorSize, vboInfo.dataType, 0, None)
            GL.glEnableClientState(GL.GL_COLOR_ARRAY)
        elif isinstance(attr, int):  # generic attributes
            GL.glVertexAttribPointer(
                attr, vboInfo.vectorSize, GL.GL_FLOAT, GL.GL_FALSE, 0, None)
            GL.glEnableVertexAttribArray(attr)

    # if not hasVertexArray:
    #    # delete the VAO we created
    #    GL.glBindVertexArray(0)
    #    GL.glDeleteVertexArrays(1, vaoId)
    #    raise RuntimeError("Failed to create VAO, no vertex data specified.")

    # bind the EBO if available
    if vaoInfo.isIndexed:
        GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, vaoInfo.indexBuffer.name)
        vaoInfo.indices = \
            ctypes.sizeof(vaoInfo.indexBuffer.dataPtr) / \
            ctypes.sizeof(vaoInfo.indexBuffer.dataPtr._type_)
    else:
        vertexBuffer = vaoInfo.vertexBuffers[GL.GL_VERTEX_ARRAY]
        vaoInfo.indices = \
            ctypes.sizeof(vertexBuffer.dataPtr) / \
            ctypes.sizeof(vertexBuffer.dataPtr._type_) / vertexBuffer.vectorSize

    GL.glBindVertexArray(0)


def drawVertexArrays(vaoInfo, flush=False):
    """Draw a vertex array using glDrawArrays. This method does not require
    shaders.

    Parameters
    ----------
    vao : :obj:`VertexArrayObject`
        Vertex Array Object (VAO) to draw.
    mode : :obj:`int`, optional
        Drawing mode to use (e.g. GL_TRIANGLES, GL_QUADS, GL_POINTS, etc.)
    flush : :obj:`bool`, optional
        Flush queued drawing commands before returning.

    Returns
    -------
    None

    Examples
    --------
    # create a VAO
    vaoDesc = createVAO(vboVerts, vboTexCoords, vboNormals)

    # draw the VAO, renders the mesh
    drawVAO(vaoDesc, GL.GL_TRIANGLES)

    """
    GL.glBindVertexArray(vaoInfo.name)
    if vaoInfo.isIndexed:
        GL.glDrawElements(vaoInfo.drawMode,
                          int(vaoInfo.indices),
                          vaoInfo.indexBuffer.dataType,
                          None)
    else:
        GL.glDrawArrays(vaoInfo.drawMode, 0, int(vaoInfo.indices))

    if flush:
        GL.glFlush()

    # reset
    GL.glBindVertexArray(0)


def deleteVertexBuffer(vbo):
    """Delete a Vertex Buffer Object (VBO).

    Returns
    -------
    :obj:`None'

    """
    GL.glDeleteBuffers(1, vbo.id)


def deleteVertexArray(vao):
    """Delete a Vertex Array Object (VAO). This does not delete array buffers
    bound to the VAO.

    Returns
    -------
    :obj:`None'

    """
    GL.glDeleteVertexArrays(1, vao.id)


# -------------------------
# Material Helper Functions
# -------------------------
#
#  These helper functions and
# datatypes simplify the creation of materials for rendering stimuli.
#

class Material(object):
    """Material descriptor class. Materials affect the appearance of rendered
    faces in terms of color and shading.

    """
    def __init__(self, params=None, textures=None, face=GL.GL_FRONT_AND_BACK):
        self.face = face
        self.params = {
            GL.GL_AMBIENT: (GL.GLfloat * 4)(0.2, 0.2, 0.2, 1.0),
            GL.GL_DIFFUSE: (GL.GLfloat * 4)(0.8, 0.8, 0.8, 1.0),
            GL.GL_SPECULAR: (GL.GLfloat * 4)(0.0, 0.0, 0.0, 1.0),
            GL.GL_EMISSION: (GL.GLfloat * 4)(0.0, 0.0, 0.0, 1.0),
            GL.GL_SHININESS: GL.GLfloat(0.0)
        }
        self.textures = {}

        # convert any input parameters to ctypes
        if params:
            for param, value in params.items():
                if hasattr(value, "__len__"):
                    self.params[param] = (GL.GLfloat * len(value))(*value)
                else:
                    self.params[param] = GL.GLfloat(value)

        # add texture descriptors
        if textures:
            maxTexUnits = getIntegerv(GL.GL_MAX_COMBINED_TEXTURE_IMAGE_UNITS)
            for unit, texInfo in textures:
                if unit <= GL.GL_TEXTURE0 + (maxTexUnits - 1):
                    self.textures[unit] = texInfo
                else:
                    raise ValueError("Invalid texture unit enum.")


def createMaterial(params=(), textures=(), face=GL.GL_FRONT_AND_BACK):
    """Create a new material.

    Parameters
    ----------
    params : :obj:`list` of :obj:`tuple`, optional
        List of material modes and values. Each mode is assigned a value as
        (mode, color). Modes can be GL_AMBIENT, GL_DIFFUSE, GL_SPECULAR,
        GL_EMISSION, GL_SHININESS or GL_AMBIENT_AND_DIFFUSE. Colors must be
        a tuple of 4 floats which specify reflectance values for each RGBA
        component. The value of GL_SHININESS should be a single float. If no
        values are specified, an empty material will be created.
    textures :obj:`list` of :obj:`tuple`, optional
        List of texture units and TexImage2D descriptors. These will be written
        to the 'textures' field of the returned descriptor. For example,
        [(GL.GL_TEXTURE0, texDesc0), (GL.GL_TEXTURE1, texDesc1)]. The number of
        texture units per-material is GL_MAX_COMBINED_TEXTURE_IMAGE_UNITS.
    face : :obj:`int`, optional
        Faces to apply material to. Values can be GL_FRONT_AND_BACK, GL_FRONT
        and GL_BACK. The default is GL_FRONT_AND_BACK.

    Returns
    -------
    Material
        A descriptor with material properties.

    Examples
    --------
    # The values for the material below can be found at
    # http://devernay.free.fr/cours/opengl/materials.html

    # create a gold material
    gold = createMaterial([
        (GL.GL_AMBIENT, (0.24725, 0.19950, 0.07450, 1.0)),
        (GL.GL_DIFFUSE, (0.75164, 0.60648, 0.22648, 1.0)),
        (GL.GL_SPECULAR, (0.628281, 0.555802, 0.366065, 1.0)),
        (GL.GL_SHININESS, 0.4 * 128.0)])

    # use the material when drawing
    useMaterial(gold)
    drawVAO( ... )  # all meshes will be gold
    useMaterial(None)  # turn off material when done

    # create a red plastic material, but define reflectance and shine later
    red_plastic = createMaterial()

    # you need to convert values to ctypes!
    red_plastic.values[GL_AMBIENT] = (GLfloat * 4)(0.0, 0.0, 0.0, 1.0)
    red_plastic.values[GL_DIFFUSE] = (GLfloat * 4)(0.5, 0.0, 0.0, 1.0)
    red_plastic.values[GL_SPECULAR] = (GLfloat * 4)(0.7, 0.6, 0.6, 1.0)
    red_plastic.values[GL_SHININESS] = 0.25 * 128.0

    # set and draw
    useMaterial(red_plastic)
    drawVertexbuffers( ... )  # all meshes will be red plastic
    useMaterial(None)

    """
    # setup material mode/value slots
    matDesc = Material(
        face,
        {mode: None for mode in (
            GL.GL_AMBIENT,
            GL.GL_DIFFUSE,
            GL.GL_SPECULAR,
            GL.GL_EMISSION,
            GL.GL_SHININESS)},
        dict(),
        dict())
    if params:
        for mode, param in params:
            matDesc.params[mode] = \
                (GL.GLfloat * 4)(*param) \
                    if mode != GL.GL_SHININESS else GL.GLfloat(param)
    if textures:
        maxTexUnits = getIntegerv(GL.GL_MAX_COMBINED_TEXTURE_IMAGE_UNITS)
        for unit, texDesc in textures:
            if unit <= GL.GL_TEXTURE0 + (maxTexUnits - 1):
                matDesc.textures[unit] = texDesc
            else:
                raise ValueError("Invalid texture unit enum.")

    return matDesc


def useMaterial(material, useTextures=True):
    """Use a material for proceeding vertex draws.

    Parameters
    ----------
    material : :obj:`Material` or None
        Material descriptor to use. Default material properties are set if None
        is specified. This is equivalent to disabling materials.
    useTextures : :obj:`bool`
        Enable textures. Textures specified in a material descriptor's 'texture'
        attribute will be bound and their respective texture units will be
        enabled. Note, when disabling materials, the value of useTextures must
        match the previous call. If there are no textures attached to the
        material, useTexture will be silently ignored.

    Returns
    -------
    None

    Notes
    -----
    1.  If a material mode has a value of None, a color with all components 0.0
        will be assigned.
    2.  Material colors and shininess values are accessible from shader programs
        after calling 'useMaterial'. Values can be accessed via built-in
        'gl_FrontMaterial' and 'gl_BackMaterial' structures (e.g.
        gl_FrontMaterial.diffuse).

    Examples
    --------
    # use the material when drawing
    useMaterial(metalMaterials.gold)
    drawVAO( ... )  # all meshes drawn will be gold
    useMaterial(None)  # turn off material when done

    """
    if material is not None:
        # setup material color params
        for mode, param in material.params.items():
            if param is not None:
                GL.glMaterialfv(material.face, mode, param)
        # setup textures
        if useTextures and material.textures:
            GL.glEnable(GL.GL_TEXTURE_2D)
            for unit, desc in material.textures.items():
                GL.glActiveTexture(unit)
                GL.glColor4f(1.0, 1.0, 1.0, 1.0)
                GL.glColorMask(True, True, True, True)
                GL.glBindTexture(GL.GL_TEXTURE_2D, desc.id)
    else:
        for mode, param in defaultMaterial.params.items():
            GL.glMaterialfv(GL.GL_FRONT_AND_BACK, mode, param)
        if useTextures:
            GL.glActiveTexture(GL.GL_TEXTURE0)
            GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
            GL.glDisable(GL.GL_TEXTURE_2D)


# -------------------------
# Lighting Helper Functions
# -------------------------

Light = namedtuple('Light', ['params', 'userData'])


def createLight(params=()):
    """Create a point light source.

    """
    # setup light mode/value slots
    lightDesc = Light({mode: None for mode in (
        GL.GL_AMBIENT,
        GL.GL_DIFFUSE,
        GL.GL_SPECULAR,
        GL.GL_POSITION,
        GL.GL_SPOT_CUTOFF,
        GL.GL_SPOT_DIRECTION,
        GL.GL_SPOT_EXPONENT,
        GL.GL_CONSTANT_ATTENUATION,
        GL.GL_LINEAR_ATTENUATION,
        GL.GL_QUADRATIC_ATTENUATION)}, dict())

    # configure lights
    if params:
        for mode, value in params:
            if value is not None:
                if mode in [GL.GL_AMBIENT, GL.GL_DIFFUSE, GL.GL_SPECULAR,
                            GL.GL_POSITION]:
                    lightDesc.params[mode] = (GL.GLfloat * 4)(*value)
                elif mode == GL.GL_SPOT_DIRECTION:
                    lightDesc.params[mode] = (GL.GLfloat * 3)(*value)
                else:
                    lightDesc.params[mode] = GL.GLfloat(value)

    return lightDesc


def useLights(lights, setupOnly=False):
    """Use specified lights in successive rendering operations. All lights will
    be transformed using the present modelview matrix.

    Parameters
    ----------
    lights : :obj:`List` of :obj:`Light` or None
        Descriptor of a light source. If None, lighting is disabled.
    setupOnly : :obj:`bool`, optional
        Do not enable lighting or lights. Specify True if lighting is being
        computed via fragment shaders.

    Returns
    -------
    None

    """
    if lights is not None:
        if len(lights) > getIntegerv(GL.GL_MAX_LIGHTS):
            raise IndexError("Number of lights specified > GL_MAX_LIGHTS.")

        GL.glEnable(GL.GL_NORMALIZE)

        for index, light in enumerate(lights):
            enumLight = GL.GL_LIGHT0 + index
            # light properties
            for mode, value in light.params.items():
                if value is not None:
                    GL.glLightfv(enumLight, mode, value)

            if not setupOnly:
                GL.glEnable(enumLight)

        if not setupOnly:
            GL.glEnable(GL.GL_LIGHTING)
    else:
        # disable lights
        if not setupOnly:
            for enumLight in range(getIntegerv(GL.GL_MAX_LIGHTS)):
                GL.glDisable(GL.GL_LIGHT0 + enumLight)

            GL.glDisable(GL.GL_NORMALIZE)
            GL.glDisable(GL.GL_LIGHTING)


def setAmbientLight(color):
    """Set the global ambient lighting for the scene when lighting is enabled.
    This is equivalent to GL.glLightModelfv(GL.GL_LIGHT_MODEL_AMBIENT, color)
    and does not contribute to the GL_MAX_LIGHTS limit.

    Parameters
    ----------
    color : :obj:`tuple`
        Ambient lighting RGBA intensity for the whole scene.

    Returns
    -------
    None

    Notes
    -----
    If unset, the default value is (0.2, 0.2, 0.2, 1.0) when GL_LIGHTING is
    enabled.

    """
    GL.glLightModelfv(GL.GL_LIGHT_MODEL_AMBIENT, (GL.GLfloat * 4)(*color))


# -------------------------
# 3D Model Helper Functions
# -------------------------
#
# These functions are used in the creation, manipulation and rendering of 3D
# model data.
#

# Header
WavefrontObj = namedtuple(
    'WavefrontObj',
    ['mtlFile',
     'drawGroups',
     'posBuffer',
     'texCoordBuffer',
     'normBuffer',
     'userData']
)


def loadObjFile(objFile):
    """Load a Wavefront OBJ file (*.obj).

    Parameters
    ----------
    objFile : :obj:`str`
        Path to the *.OBJ file to load.

    Returns
    -------
    WavefrontObjModel

    Notes
    -----
    1. This importer should work fine for most sanely generated files.
       Export your model with Blender for best results, even if you used some
       other package to create it.
    2. The model must be triangulated, quad faces are not supported.

    Examples
    --------
    # load a model from file
    objModel = loadObjFile('/path/to/file.obj')

    # load the material (*.mtl) file, textures are also loaded
    materials = loadMtl('/path/to/' + objModel.mtlFile)

    # apply settings
    GL.glEnable(GL.GL_CULL_FACE)
    GL.glEnable(GL.GL_DEPTH_TEST)
    GL.glDepthFunc(GL.GL_LEQUAL)
    GL.glDepthMask(GL.GL_TRUE)
    GL.glShadeModel(GL.GL_SMOOTH)
    GL.glCullFace(GL.GL_BACK)
    GL.glDisable(GL.GL_BLEND)

    # lights
    useLights(light0)

    # draw the model
    for group, vao in obj.drawGroups.items():
        useMaterial(materials[group])
        drawVAO(vao)

    # disable materials and lights
    useMaterial(None)
    useLights(None)

    """
    # open the file, read it into memory
    with open(objFile, 'r') as objFile:
        objBuffer = StringIO(objFile.read())

    nVertices = nTextureCoords = nNormals = nFaces = nObjects = nMaterials = 0
    matLibPath = None

    # first pass, examine the file
    for line in objBuffer.readlines():
        if line.startswith('v '):
            nVertices += 1
        elif line.startswith('vt '):
            nTextureCoords += 1
        elif line.startswith('vn '):
            nNormals += 1
        elif line.startswith('f '):
            nFaces += 1
        elif line.startswith('o '):
            nObjects += 1
        elif line.startswith('usemtl '):
            nMaterials += 1
        elif line.startswith('mtllib '):
            matLibPath = line.strip()[7:]

    # error check
    if nVertices == 0:
        raise RuntimeError(
            "Failed to load OBJ file, file contains no vertices.")

    objBuffer.seek(0)

    # attribute data lists
    positionDefs = []
    texCoordDefs = []
    normalDefs = []

    # attribute lists to upload
    vertexAttrList = []
    texCoordAttrList = []
    normalAttrList = []

    # store vertex attributes in dictionaries for easy re-mapping if needed
    vertexAttrs = OrderedDict()
    vertexIndices = OrderedDict()

    # group faces by material, each one will get its own VAO
    materialGroups = OrderedDict()
    materialOffsets = OrderedDict()

    # Parse the buffer for vertex attributes. We would like to create an index
    # buffer were there are no duplicate vertices. So we load attributes and
    # check if it's a duplicate against previously loaded attributes. If so, we
    # re-map it instead of creating a new attribute. Attributes are considered
    # equal if they share the same position, texture coordinate and normal.
    #
    vertexIdx = faceIdx = 0
    materialGroup = None
    for line in objBuffer.readlines():
        line = line.strip()

        if line.startswith('v '):  # new vertex position
            positionDefs.append(tuple(map(float, line[2:].split(' '))))
        elif line.startswith('vt '):  # new vertex texture coordinate
            texCoordDefs.append(tuple(map(float, line[3:].split(' '))))
        elif line.startswith('vn '):  # new vertex normal
            normalDefs.append(tuple(map(float, line[3:].split(' '))))
        elif line.startswith('f '):
            faceDef = []
            for attrs in line[2:].split(' '):
                # check if vertex attribute already loaded, create a new index
                # if not.
                if attrs not in vertexAttrs.keys():
                    p, t, n = map(int, attrs.split('/'))
                    # add to attribute lists
                    vertexAttrList.extend(positionDefs[p - 1])
                    texCoordAttrList.extend(texCoordDefs[t - 1])
                    normalAttrList.extend(normalDefs[n - 1])
                    vertexIndices[attrs] = vertexIdx
                    vertexIdx += 1
                faceDef.append(vertexIndices[attrs])  # attribute exists? remap
            materialGroups[materialGroup].extend(faceDef)
            faceIdx += 1  # for computing material offsets
        # elif line.startswith('o '):
        #    pass
        elif line.startswith('usemtl '):
            materialGroup = line[7:]
            if materialGroup not in materialGroups.keys():
                materialGroups[materialGroup] = []
                materialOffsets[materialGroup] = faceIdx

    # Load all vertex attribute data to the graphics device. If anyone cares,
    # try to make this work by interleaving attributes so we can read from a
    # single buffer. Regardless, we're using VAOs and EBOs when rendering
    # primitives which speeds things up considerably, so it's not needed right
    # now.
    #
    posVBO = createVBO(vertexAttrList)
    texVBO = createVBO(texCoordAttrList, 2)
    normVBO = createVBO(normalAttrList)

    # Create a VAO for each material in the file, each gets it own element
    # buffer array for indexed drawing.
    #
    objVAOs = {}
    for group, elements in materialGroups.items():
        objVAOs[group] = createVAO((
            (GL.GL_VERTEX_ARRAY, posVBO),
            (GL.GL_TEXTURE_COORD_ARRAY, texVBO),
            (GL.GL_NORMAL_ARRAY, normVBO)),
            createVBO(elements,
                      dtype=GL.GL_UNSIGNED_INT,
                      target=GL.GL_ELEMENT_ARRAY_BUFFER))

    return WavefrontObj(matLibPath, objVAOs, posVBO, texVBO, normVBO, dict())


def loadMtlFile(mtlFilePath, texParameters=None):
    """Load a material library (*.mtl).

    """
    # open the file, read it into memory
    with open(mtlFilePath, 'r') as mtlFile:
        mtlBuffer = StringIO(mtlFile.read())

    # default texture parameters
    if texParameters is None:
        texParameters = [(GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR),
                         (GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)]

    foundMaterials = {}
    foundTextures = {}
    thisMaterial = 0
    for line in mtlBuffer.readlines():
        line = line.strip()
        if line.startswith('newmtl '):  # new material
            thisMaterial = line[7:]
            foundMaterials[thisMaterial] = createMaterial()
        elif line.startswith('Ns '):  # specular exponent
            foundMaterials[thisMaterial].params[GL.GL_SHININESS] = \
                GL.GLfloat(float(line[3:]))
        elif line.startswith('Ks '):  # specular color
            foundMaterials[thisMaterial].params[GL.GL_SPECULAR] = \
                (GL.GLfloat * 4)(*list(map(float, line[3:].split(' '))) + [1.0])
        elif line.startswith('Kd '):  # diffuse color
            foundMaterials[thisMaterial].params[GL.GL_DIFFUSE] = \
                (GL.GLfloat * 4)(*list(map(float, line[3:].split(' '))) + [1.0])
        elif line.startswith('Ka '):  # ambient color
            foundMaterials[thisMaterial].params[GL.GL_AMBIENT] = \
                (GL.GLfloat * 4)(*list(map(float, line[3:].split(' '))) + [1.0])
        elif line.startswith('map_Kd '):  # diffuse color map
            # load a diffuse texture from file
            textureName = line[7:]
            if textureName not in foundTextures.keys():
                im = Image.open(
                    os.path.join(os.path.split(mtlFilePath)[0], textureName))
                im = im.transpose(Image.FLIP_TOP_BOTTOM)
                im = im.convert("RGBA")
                pixelData = np.array(im).ctypes
                width = pixelData.shape[1]
                height = pixelData.shape[0]
                foundTextures[textureName] = createTexImage2D(
                    width,
                    height,
                    internalFormat=GL.GL_RGBA,
                    pixelFormat=GL.GL_RGBA,
                    dataType=GL.GL_UNSIGNED_BYTE,
                    data=pixelData,
                    unpackAlignment=1,
                    texParameters=texParameters)
            foundMaterials[thisMaterial].textures[GL.GL_TEXTURE0] = \
                foundTextures[textureName]

    return foundMaterials


# -----------------------------
# Misc. OpenGL Helper Functions
# -----------------------------

def getIntegerv(parName):
    """Get a single integer parameter value, return it as a Python integer.

    Parameters
    ----------
    pName : :obj:`int'
        OpenGL property enum to query (e.g. GL_MAJOR_VERSION).

    Returns
    -------
    int

    """
    val = GL.GLint()
    GL.glGetIntegerv(parName, val)

    return int(val.value)


def getFloatv(parName):
    """Get a single float parameter value, return it as a Python float.

    Parameters
    ----------
    pName : :obj:`float'
        OpenGL property enum to query.

    Returns
    -------
    int

    """
    val = GL.GLfloat()
    GL.glGetFloatv(parName, val)

    return float(val.value)


def getString(parName):
    """Get a single string parameter value, return it as a Python UTF-8 string.

    Parameters
    ----------
    pName : :obj:`int'
        OpenGL property enum to query (e.g. GL_VENDOR).

    Returns
    -------
    str

    """
    val = ctypes.cast(GL.glGetString(parName), ctypes.c_char_p).value
    return val.decode('UTF-8')


# OpenGL information type
OpenGLInfo = namedtuple(
    'OpenGLInfo',
    ['vendor',
     'renderer',
     'version',
     'majorVersion',
     'minorVersion',
     'doubleBuffer',
     'maxTextureSize',
     'stereo',
     'maxSamples',
     'extensions',
     'userData'])


def getOpenGLInfo():
    """Get general information about the OpenGL implementation on this machine.
    This should provide a consistent means of doing so regardless of the OpenGL
    interface we are using.

    Returns are dictionary with the following fields:

        vendor, renderer, version, majorVersion, minorVersion, doubleBuffer,
        maxTextureSize, stereo, maxSamples, extensions

    Supported extensions are returned as a list in the 'extensions' field. You
    can check if a platform supports an extension by checking the membership of
    the extension name in that list.

    Returns
    -------
    OpenGLInfo

    """
    return OpenGLInfo(getString(GL.GL_VENDOR),
                      getString(GL.GL_RENDERER),
                      getString(GL.GL_VERSION),
                      getIntegerv(GL.GL_MAJOR_VERSION),
                      getIntegerv(GL.GL_MINOR_VERSION),
                      getIntegerv(GL.GL_DOUBLEBUFFER),
                      getIntegerv(GL.GL_MAX_TEXTURE_SIZE),
                      getIntegerv(GL.GL_STEREO),
                      getIntegerv(GL.GL_MAX_SAMPLES),
                      [i for i in getString(GL.GL_EXTENSIONS).split(' ')],
                      dict())


# ---------------------
# OpenGL/VRML Materials
# ---------------------
#
# A collection of pre-defined materials for stimuli. Keep in mind that these
# materials only approximate real-world equivalents. Values were obtained from
# http://devernay.free.fr/cours/opengl/materials.html (08/24/18). There are four
# material libraries to use, where individual material descriptors are accessed
# via property names.
#
# Usage:
#
#   useMaterial(metalMaterials['gold'])
#   drawVAO(myObject)
#   ...
#
BasicMaterials = {
    # minerals
    'emerald': Material(
        {GL.GL_AMBIENT: (0.0215, 0.1745, 0.0215, 1.0),
         GL.GL_DIFFUSE: (0.07568, 0.61424, 0.07568, 1.0),
         GL.GL_SPECULAR: (0.633, 0.727811, 0.633, 1.0),
         GL.GL_SHININESS: 0.6 * 128.0}),
    'jade': Material(
        {GL.GL_AMBIENT: (0.135, 0.2225, 0.1575, 1.0),
         GL.GL_DIFFUSE: (0.54, 0.89, 0.63, 1.0),
         GL.GL_SPECULAR: (0.316228, 0.316228, 0.316228, 1.0),
         GL.GL_SHININESS: 0.1 * 128.0}),
    'obsidian': Material(
        {GL.GL_AMBIENT: (0.05375, 0.05, 0.06625, 1.0),
         GL.GL_DIFFUSE: (0.18275, 0.17, 0.22525, 1.0),
         GL.GL_SPECULAR: (0.332741, 0.328634, 0.346435, 1.0),
         GL.GL_SHININESS: 0.3 * 128.0}),
    'pearl': Material(
        {GL.GL_AMBIENT: (0.25, 0.20725, 0.20725, 1.0),
         GL.GL_DIFFUSE: (1, 0.829, 0.829, 1.0),
         GL.GL_SPECULAR: (0.296648, 0.296648, 0.296648, 1.0),
         GL.GL_SHININESS: 0.088 * 128.0}),
    'ruby': Material(
        {GL.GL_AMBIENT: (0.1745, 0.01175, 0.01175, 1.0),
         GL.GL_DIFFUSE: (0.61424, 0.04136, 0.04136, 1.0),
         GL.GL_SPECULAR: (0.727811, 0.626959, 0.626959, 1.0),
         GL.GL_SHININESS: 0.6 * 128.0}),
    'turquoise': Material(
        {GL.GL_AMBIENT: (0.1, 0.18725, 0.1745, 1.0),
         GL.GL_DIFFUSE: (0.396, 0.74151, 0.69102, 1.0),
         GL.GL_SPECULAR: (0.297254, 0.30829, 0.306678, 1.0),
         GL.GL_SHININESS: 0.1 * 128.0}),
    # metals
    'brass': Material(
        {GL.GL_AMBIENT, (0.329412, 0.223529, 0.027451, 1.0),
         GL.GL_DIFFUSE, (0.780392, 0.568627, 0.113725, 1.0),
         GL.GL_SPECULAR, (0.992157, 0.941176, 0.807843, 1.0),
         GL.GL_SHININESS, 0.21794872 * 128.0}),
    'bronze': Material(
        {GL.GL_AMBIENT, (0.2125, 0.1275, 0.054, 1.0),
         GL.GL_DIFFUSE, (0.714, 0.4284, 0.18144, 1.0),
         GL.GL_SPECULAR, (0.393548, 0.271906, 0.166721, 1.0),
         GL.GL_SHININESS, 0.2 * 128.0}),
    'chrome' : Material(
        {GL.GL_AMBIENT, (0.25, 0.25, 0.25, 1.0),
         GL.GL_DIFFUSE, (0.4, 0.4, 0.4, 1.0),
         GL.GL_SPECULAR, (0.774597, 0.774597, 0.774597, 1.0),
         GL.GL_SHININESS, 0.6 * 128.0}),
    'copper': Material(
        {GL.GL_AMBIENT, (0.19125, 0.0735, 0.0225, 1.0),
         GL.GL_DIFFUSE, (0.7038, 0.27048, 0.0828, 1.0),
         GL.GL_SPECULAR, (0.256777, 0.137622, 0.086014, 1.0),
         GL.GL_SHININESS, 0.1 * 128.0}),
    'gold': Material(
        {GL.GL_AMBIENT, (0.24725, 0.1995, 0.0745, 1.0),
         GL.GL_DIFFUSE, (0.75164, 0.60648, 0.22648, 1.0),
         GL.GL_SPECULAR, (0.628281, 0.555802, 0.366065, 1.0),
         GL.GL_SHININESS, 0.4 * 128.0}),
    'silver': Material(
        {GL.GL_AMBIENT, (0.19225, 0.19225, 0.19225, 1.0),
         GL.GL_DIFFUSE, (0.50754, 0.50754, 0.50754, 1.0),
         GL.GL_SPECULAR, (0.508273, 0.508273, 0.508273, 1.0),
         GL.GL_SHININESS, 0.4 * 128.0}),
    # plastics
    'black' : Material(
        {GL.GL_AMBIENT, (0, 0, 0, 1.0),
         GL.GL_DIFFUSE, (0.01, 0.01, 0.01, 1.0),
         GL.GL_SPECULAR, (0.5, 0.5, 0.5, 1.0),
         GL.GL_SHININESS, 0.25 * 128.0}),
    'cyan': Material(
        {GL.GL_AMBIENT, (0, 0.1, 0.06, 1.0),
         GL.GL_DIFFUSE, (0.06, 0, 0.50980392, 1.0),
         GL.GL_SPECULAR, (0.50196078, 0.50196078, 0.50196078, 1.0),
         GL.GL_SHININESS, 0.25 * 128.0}),
    'green': Material(
        {GL.GL_AMBIENT, (0, 0, 0, 1.0),
         GL.GL_DIFFUSE, (0.1, 0.35, 0.1, 1.0),
         GL.GL_SPECULAR, (0.45, 0.55, 0.45, 1.0),
         GL.GL_SHININESS, 0.25 * 128.0}),
    'red': Material(
        {GL.GL_AMBIENT, (0, 0, 0, 1.0),
         GL.GL_DIFFUSE, (0.5, 0, 0, 1.0),
         GL.GL_SPECULAR, (0.7, 0.6, 0.6, 1.0),
         GL.GL_SHININESS, 0.25 * 128.0}),
    'white': Material(
        {GL.GL_AMBIENT, (0, 0, 0, 1.0),
         GL.GL_DIFFUSE, (0.55, 0.55, 0.55, 1.0),
         GL.GL_SPECULAR, (0.7, 0.7, 0.7, 1.0),
         GL.GL_SHININESS, 0.25 * 128.0}),
    'yellow': Material(
        {GL.GL_AMBIENT, (0, 0, 0, 1.0),
         GL.GL_DIFFUSE, (0.5, 0.5, 0, 1.0),
         GL.GL_SPECULAR, (0.6, 0.6, 0.5, 1.0),
         GL.GL_SHININESS, 0.25 * 128.0})
    # rubber
}


rubberMaterials = namedtuple(
    'rubberMaterials',
    ['black', 'cyan', 'green', 'red', 'white', 'yellow'])(
    Material(
        {GL.GL_AMBIENT, (0.02, 0.02, 0.02, 1.0),
         GL.GL_DIFFUSE, (0.01, 0.01, 0.01, 1.0),
         GL.GL_SPECULAR, (0.4, 0.4, 0.4, 1.0),
         GL.GL_SHININESS, 0.078125 * 128.0}),
    Material(
        {GL.GL_AMBIENT, (0, 0.05, 0.05, 1.0),
         GL.GL_DIFFUSE, (0.4, 0.5, 0.5, 1.0),
         GL.GL_SPECULAR, (0.04, 0.7, 0.7, 1.0),
         GL.GL_SHININESS, 0.078125 * 128.0}),
    Material(
        {GL.GL_AMBIENT, (0, 0.05, 0, 1.0),
         GL.GL_DIFFUSE, (0.4, 0.5, 0.4, 1.0),
         GL.GL_SPECULAR, (0.04, 0.7, 0.04, 1.0),
         GL.GL_SHININESS, 0.078125 * 128.0}),
    Material(
        {GL.GL_AMBIENT, (0.05, 0, 0, 1.0),
         GL.GL_DIFFUSE, (0.5, 0.4, 0.4, 1.0),
         GL.GL_SPECULAR, (0.7, 0.04, 0.04, 1.0),
         GL.GL_SHININESS, 0.078125 * 128.0}),
    Material(
        {GL.GL_AMBIENT, (0.05, 0.05, 0.05, 1.0),
         GL.GL_DIFFUSE, (0.5, 0.5, 0.5, 1.0),
         GL.GL_SPECULAR, (0.7, 0.7, 0.7, 1.0),
         GL.GL_SHININESS, 0.078125 * 128.0}),
    Material(
        {GL.GL_AMBIENT, (0.05, 0.05, 0, 1.0),
         GL.GL_DIFFUSE, (0.5, 0.5, 0.4, 1.0),
         GL.GL_SPECULAR, (0.7, 0.7, 0.04, 1.0),
         GL.GL_SHININESS, 0.078125 * 128.0})
)

# default material according to the OpenGL spec.
defaultMaterial = Material(
    [GL.GL_AMBIENT, (0.2, 0.2, 0.2, 1.0)),
     GL.GL_DIFFUSE, (0.8, 0.8, 0.8, 1.0)),
     GL.GL_SPECULAR, (0.0, 0.0, 0.0, 1.0)),
     GL.GL_EMISSION, (0.0, 0.0, 0.0, 1.0)),
     GL.GL_SHININESS, 0})
