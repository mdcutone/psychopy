#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Extensions which expand the capabilities of the Window class."""

# Part of the PsychoPy library
# Copyright (C) 2018 Jonathan Peirce
# Distributed under the terms of the GNU General Public License (GPL).

import sys
import platform
import ctypes
import math
from psychopy import platform_specific, logging
from psychopy.visual import window
import pyglet.gl as GL
from psychopy.tools.attributetools import setAttribute
import numpy as np
import psychopy.tools.stereotools as stereotools
import psychopy.tools.gltools as gltools


class ViewMixin(object):
    """Mixin class for handling projections."""

    @property
    def frameBufferAspect(self):
        """Get the aspect ratio of the current buffer."""
        return self.size[0] / self.size[1]

    @frameBufferAspect.setter
    def frameBufferAspect(self, value):
        raise NotImplementedError(
            "Attribute 'frameBufferAspect' is read-only. Exiting.")

    @property
    def frameBufferSize(self):
        """Dimensions of the current frame buffer in pixels. This can differ
        from the window size.

        """
        # Stimulus classes should access this property when checking the size
        # of the render area instead of the window size since they can
        # frequently differ.
        #
        return self.size

    @frameBufferSize.setter
    def frameBufferSize(self, value):
        raise NotImplementedError(
            "Attribute 'frameBufferSize' is read-only. Exiting.")

    @property
    def projectionMatrix(self):
        """Projection matrix. The matrix is specified as a 4x4 Numpy array. If
        'frustum' was previously set, the projection matrix computed from those
        values will appear here.

        Notes
        -----
        Setting projectionMatrix directly invalidates any frustum previously
        set!

        """
        return self._projectionMatrix

    @projectionMatrix.setter
    def projectionMatrix(self, value):
        # if specified directly, the values of frustum are no longer valid!
        #
        self._projectionMatrix = value

    @property
    def frustum(self):
        """Frustum parameters for the projection. The specified values are used
        to compute the projection matrix. If None is specified, an orthogonal
        projection matrix is used.

        """
        return self._frustum

    @frustum.setter
    def frustum(self, value):
        self._frustum = value

        if self._frustum is None:
            # default orthographic projection matrix
            self._projectionMatrix = orthoProjectionMatrix(
                -1.0, 1.0, -1.0, 1.0, -1.0, 1.0)
        else:
            # with perspective
            self._projectionMatrix = perspectiveProjectionMatrix(*self._frustum)

    @property
    def nearClip(self):
        """Near clipping plane distance from viewer in centimeters. The near
        clipping plane can be between the screen and observer.

        """
        return self._nearClipM

    @nearClip.setter
    def nearClip(self, value):
        value /= 100.0
        if self._nearClipM >= value:
            raise ValueError("Near clipping plane must be < farClip.")

        self._nearClipM = value

    @property
    def farClip(self):
        """Far clipping plane distance from viewer in centimeters."""
        return self._farClipM * 100.0

    @farClip.setter
    def farClip(self, value):
        value /= 100.0
        if self._farClipM >= value:
            raise ValueError("Far clipping plane must be > nearClip.")

        self._farClipM = value

    @property
    def viewMatrix(self):
        """The view matrix. This describes the global transformation of the
        scene which positions the origin at the viewer. The matrix is specified
        as a 4x4 Numpy array.

        """
        return self._viewMatrix

    @viewMatrix.setter
    def viewMatrix(self, value):
        self._viewMatrix = value

    def setPerspectiveView(self, clearDepth=True):
        """Enable perspective projection. This will apply the current projection
        and view transformation matrices.

        Parameters
        ----------
        clearDepth : bool
            Clear the depth buffer.

        """
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()
        GL.glMultMatrixf(self._projectionMatrix.ctypes.data_as(
            ctypes.POINTER(ctypes.c_float)))

        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glLoadIdentity()
        GL.glMultMatrixf(self._viewMatrix.ctypes.data_as(
            ctypes.POINTER(ctypes.c_float)))

        if clearDepth:
            GL.glClear(GL.GL_DEPTH_BUFFER_BIT)

        # for 3D drawing
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDepthFunc(GL.GL_LEQUAL)
        GL.glDepthMask(GL.GL_TRUE)

    def setDefaultView(self, clearDepth=True):
        """Use the default orthographic projection for successive drawing
        operations.

        Parameters
        ----------
        clearDepth : boolean
            Clear the depth buffer.

        Returns
        -------
        None

        """
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()
        GL.glOrtho(-1, 1, -1, 1, -1, 1)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glLoadIdentity()

        if clearDepth:
            GL.glClear(GL.GL_DEPTH_BUFFER_BIT)


class StereoMixin(object):
    """Window mixin class for stereoscopy."""

    @property
    def iod(self):
        return self.getIOD()

    @iod.setter
    def iod(self, value):
        self.setIOD(value)

    def getIOD(self):
        """Get the interocular distance/separation presently used for view
        calculations.

        Returns
        -------
        float
            The current IOD in centimeters.

        """
        # This value is internally stored as meters, using centimeters for
        # consistency with other PsychoPy functions.
        #
        return self._iod * 100.0

    def setIOD(self, dist):
        """Set the interocular distance/separation for stereoscopy.

        Parameters
        ----------
        dist : float
            Distance between the viewer's pupils in centimeters.

        """
        self._iod = float(dist) / 100.0

    @property
    def convergeDist(self):
        return self.getConvergeDist()

    @convergeDist.setter
    def convergeDist(self, value):
        self.setConvergeDist(value)

    def getConvergeDist(self):
        """Get the convergence distance presently used for view calculations.

        Returns
        -------
        float
            The current convergence distance in centimeters.

        """
        # this value is internally stored as meters!
        return self._convergeDist * 100.0

    def setConvergeDist(self, dist):
        """Set the distance of the convergence plane in centimeters.

        Parameters
        ----------
        dist : float
            Distance to the convergence plane in centimeters.

        """
        self._convergeDist = float(dist) / 100.0

    def setBuffer(self, buffer, clear=True):
        """Choose which buffer to draw to ('left' or 'right').

        Requires the Window to be initialised with stereo=True and requires a
        graphics card that supports quad buffering (e,g nVidia Quadro series)

        PsychoPy always draws to the back buffers, so 'left' will use
        GL_BACK_LEFT This then needs to be flipped once both eye's buffers
        have been rendered.

        Typical usage::

            win = visual.Window(...., stereo=True)
            while True:
                # clear may not actually be needed
                win.setBuffer('left', clear=True)
                # do drawing for left eye
                win.setBuffer('right', clear=True)
                # do drawing for right eye
                win.flip()

        """
        # If 'stereo' is True, behave exactly like previous versions of PsychoPy
        # for backwards compatibility.
        if self.stereo is True:
            if buffer == 'left':
                GL.glDrawBuffer(GL.GL_BACK_LEFT)
            elif buffer == 'right':
                GL.glDrawBuffer(GL.GL_BACK_RIGHT)
            else:
                raise ValueError(
                    "Unknown buffer '%s' requested in Window.setBuffer" %
                    buffer)

            if clear:
                self.clearBuffer()

            return

        # using multiple stereo buffers
        if hasattr(self, '_stereoBuffers'):
            if buffer == 'left':
                GL.glBindFramebuffer(
                    GL.GL_FRAMEBUFFER,
                    self._stereoBuffers[0].id)
            elif buffer == 'right':
                GL.glBindFramebuffer(
                    GL.GL_FRAMEBUFFER,
                    self._stereoBuffers[1].id)
            else:
                raise ValueError(
                    "Unknown buffer '%s' requested in Window.setBuffer" %
                    buffer)

            GL.glReadBuffer(GL.GL_COLOR_ATTACHMENT0)
            GL.glDrawBuffer(GL.GL_COLOR_ATTACHMENT0)

        self._buffer = buffer

        # setup viewport for this buffer
        GL.glViewport(0, 0, self.size[0], self.size[1])
        GL.glScissor(0, 0, self.size[0], self.size[1])  # sometimes needed

        if clear:
            self.setColor(self.color)  # clear the texture to the window color
            GL.glClear(
                GL.GL_COLOR_BUFFER_BIT |
                GL.GL_DEPTH_BUFFER_BIT |
                GL.GL_STENCIL_BUFFER_BIT
            )

        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glEnable(GL.GL_BLEND)

    def _setupStereoBuffers(self):
        """Create additional framebuffers for multi-view rendering required for
        stereoscopy. When called, the Window class will gain the
        '_stereoBuffers' attribute which contains descriptors for each view
        buffer. The dimensions of the stereobuffers will be appropriate for the
        type of display being used.

        Returns
        -------
        None

        """
        # texture parameters for the render target to use
        texPars = ((GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR),
                   (GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR))

        # create the _stereoBuffers attribute here
        self._stereoBuffers = (gltools.createFBO(), gltools.createFBO())

        # setup image attachments for each FBO
        for eye in range(2):
            colorTex = gltools.createTexImage2D(
                self.size[0], self.size[1],
                internalFormat=GL.GL_RGBA32F_ARB,
                texParameters=texPars)
            depthRb = gltools.createRenderbuffer(
                self.size[0], self.size[1],
                internalFormat=GL.GL_DEPTH24_STENCIL8)
            GL.glBindFramebuffer(
                GL.GL_FRAMEBUFFER, self._stereoBuffers[eye].id)
            gltools.attach(GL.GL_COLOR_ATTACHMENT0, colorTex)
            gltools.attach(GL.GL_DEPTH_STENCIL_ATTACHMENT, depthRb)
            # keep track of the image descriptors
            self._stereoBuffers[eye].userData["frameTexture"] = colorTex
            self._stereoBuffers[eye].userData["stencilTexture"] = depthRb
            self.clearBuffer()

        # Create vertex buffers to store the plane for rendering the stereo
        # buffer.
        leftVertices = gltools.createVBO(
            [-1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0, -1.0],
            size=2, dtype=GL.GL_FLOAT, target=GL.GL_ARRAY_BUFFER)
        leftTexCoords = gltools.createVBO(
            [0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 1.0, 0.0],
            size=2, dtype=GL.GL_FLOAT, target=GL.GL_ARRAY_BUFFER)

        leftVAO = gltools.createVAO((
            (GL.GL_VERTEX_ARRAY, leftVertices),
            (GL.GL_TEXTURE_COORD_ARRAY, leftTexCoords)))

        self._stereoFrameVAOs = (leftVAO, leftVAO)

    def _prepareAnaglyph(self):
        """Render a stereoscopic anaglyph image to the display framebuffer. This
        is happens automatically when 'flip' is called.

        Returns
        -------
        None

        """
        colorMasks = {
            "rc": ((True, False, False, True), (False, True, True, True)),
            "rg": ((True, False, False, True), (False, True, False, True)),
            "rb": ((True, False, False, True), (True, True, True, True)),
        }

        # use the fragment shader
        GL.glUseProgram(self._progFBOtoFrame)
        # need blit the framebuffer object to the actual back buffer
        # unbind the framebuffer as the render target
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER_EXT, self.frameBuffer)
        GL.glDisable(GL.GL_BLEND)
        stencilOn = GL.glIsEnabled(GL.GL_STENCIL_TEST)
        GL.glDisable(GL.GL_STENCIL_TEST)

        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glEnable(GL.GL_TEXTURE_2D)
        self.setDefaultView()
        for eye in range(2):
            GL.glBindTexture(
                GL.GL_TEXTURE_2D,
                self._stereoBuffers[eye].userData["frameTexture"].id)

            GL.glColor3f(1.0, 1.0, 1.0)  # glColor multiplies with texture
            if eye == 0:
                GL.glColorMask(True, False, False, True)
            else:
                GL.glColorMask(False, True, True, True)
            # GL.glFrontFace(GL.GL_CW)
            gltools.drawVAO(self._stereoFrameVAOs[eye], GL.GL_TRIANGLE_STRIP)

        GL.glEnable(GL.GL_BLEND)
        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glUseProgram(0)


def lookAt(eyePos, centerPos, upVec):
    """Create a transformation matrix to orient towards some point. Based on the
    same algorithm as 'gluLookAt'. For more information see
    https://www.khronos.org/registry/OpenGL-Refpages/gl2.1/xhtml/gluLookAt.xml

    Parameters
    ----------
    eyePos
    centerPos
    upVec

    Returns
    -------
    ndarray
        4x4 projection matrix

    """
    eyePos = np.asarray(eyePos, np.float32)
    centerPos = np.asarray(centerPos, np.float32)
    upVec = np.asarray(upVec, np.float32)

    f = centerPos - eyePos
    f /= np.linalg.norm(f)
    upVec /= np.linalg.norm(upVec)

    s = np.cross(f, upVec)
    u = np.cross(s / np.linalg.norm(s), f)

    rotMat = np.zeros((4, 4), np.float32)
    rotMat[:3, 0] = s
    rotMat[:3, 1] = u
    rotMat[:3, 2] = -f
    rotMat[3, 3] = 1.0

    transMat = np.zeros((4, 4), np.float32)
    np.fill_diagonal(transMat, 1.0)
    transMat[3, :3] = -eyePos

    return np.matmul(transMat, rotMat)


def generalizedPerspectiveProjection(posBottomLeft,
                                     posBottomRight,
                                     posTopLeft,
                                     eyePos,
                                     nearClip=0.01,
                                     farClip=100.0):
    """Generalized derivation of projection and view matrices based on the
    physical configuration of the display system.

    This implementation is based on Robert Kooima's 'Generalized Perspective
    Projection' (see http://csc.lsu.edu/~kooima/articles/genperspective/)
    method.

    Parameters
    ----------
    posBottomLeft : list of float or ndarray
        Bottom-left 3D coordinate of the screen in meters.
    posBottomRight : list of float or ndarray
        Bottom-right 3D coordinate of the screen in meters.
    posTopLeft : list of float or ndarray
        Top-left 3D coordinate of the screen in meters.
    eyePos : list of float or ndarray
        Coordinate of the eye in meters.
    nearClip : float
        Near clipping plane distance from viewer in meters.
    farClip : float
        Far clipping plane distance from viewer in meters.

    Returns
    -------
    tuple
        The 4x4 projection and view matrix.

    Notes
    -----
    The resulting projection frustums are off-axis.

    """
    # convert everything to numpy arrays
    posBottomLeft = np.asarray(posBottomLeft, np.float32)
    posBottomRight = np.asarray(posBottomRight, np.float32)
    posTopLeft = np.asarray(posTopLeft, np.float32)
    eyePos = np.asarray(eyePos, np.float32)

    # orthonormal basis of the screen plane
    vr = posBottomRight - posBottomLeft
    vr /= np.linalg.norm(vr)
    vu = posTopLeft - posBottomLeft
    vu /= np.linalg.norm(vu)
    vn = np.cross(vr, vu)
    vn /= np.linalg.norm(vn)

    # screen corner vectors
    va = posBottomLeft - eyePos
    vb = posBottomRight - eyePos
    vc = posTopLeft - eyePos

    dist = -np.dot(va, vn)
    nearOverDist = nearClip / dist
    left = float(np.dot(vr, va) * nearOverDist)
    right = float(np.dot(vr, vb) * nearOverDist)
    bottom = float(np.dot(vu, va) * nearOverDist)
    top = float(np.dot(vu, vc) * nearOverDist)

    # projection matrix to return
    projMat = perspectiveProjectionMatrix(
        left, right, bottom, top, nearClip, farClip)

    # view matrix to return, first compute the rotation component
    rotMat = np.zeros((4, 4), np.float32)
    rotMat[:3, 0] = vr
    rotMat[:3, 1] = vu
    rotMat[:3, 2] = vn
    rotMat[3, 3] = 1.0

    transMat = np.zeros((4, 4), np.float32)
    np.fill_diagonal(transMat, 1.0)
    transMat[3, :3] = -eyePos

    return projMat, np.matmul(transMat, rotMat)


def orthoProjectionMatrix(left, right, bottom, top, near, far):
    """Compute an orthographic projection matrix with provided frustum
    parameters.

    Parameters
    ----------
    left : float
        Left clipping plane coordinate.
    right : float
        Right clipping plane coordinate.
    bottom : float
        Bottom clipping plane coordinate.
    top : float
        Top clipping plane coordinate.
    near : float
        Near clipping plane distance from viewer.
    far : float
        Far clipping plane distance from viewer.

    Returns
    -------
    ndarray
        4x4 projection matrix

    """
    projMat = np.zeros((4, 4), np.float32)
    projMat[0, 0] = 2.0 / (right - left)
    projMat[1, 1] = 2.0 / (top - bottom)
    projMat[2, 2] = -2.0 / (far - near)
    projMat[3, 0] = (right + left) / (right - left)
    projMat[3, 1] = (top + bottom) / (top - bottom)
    projMat[3, 2] = (far + near) / (far - near)
    projMat[3, 3] = 1.0

    return projMat


def perspectiveProjectionMatrix(left, right, bottom, top, near, far):
    """Compute an perspective projection matrix with provided frustum
    parameters. The frustum can be asymmetric.

    Parameters
    ----------
    left : float
        Left clipping plane coordinate.
    right : float
        Right clipping plane coordinate.
    bottom : float
        Bottom clipping plane coordinate.
    top : float
        Top clipping plane coordinate.
    near : float
        Near clipping plane distance from viewer.
    far : float
        Far clipping plane distance from viewer.

    Returns
    -------
    ndarray
        4x4 projection matrix

    """
    projMat = np.zeros((4, 4), np.float32)
    projMat[0, 0] = (2.0 * near) / (right - left)
    projMat[1, 1] = (2.0 * near) / (top - bottom)
    projMat[2, 0] = (right + left) / (right - left)
    projMat[2, 1] = (top + bottom) / (top - bottom)
    projMat[2, 2] = -(far + near) / (far - near)
    projMat[2, 3] = -1.0
    projMat[3, 2] = -(2.0 * far * near) / (far - near)

    return projMat
