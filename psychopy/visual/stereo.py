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
    def frustum(self):
        """Get the current view buffer's frustum parameters.

        Returns
        -------
        namedtuple

        """
        if self._buffer == 'left':
            return self._frustum[0]
        elif self._buffer == 'right':
            return self._frustum[1]

        return self._frustum

    def nearClip(self):
        pass

    def farClip(self):
        pass

    def setDefaultView(self, clearDepth=True):
        """Use the default orthographic projection for successive drawing
        operations.

        Parameters
        ----------
        clearDepth : boolean
            Clear the depth buffer prior after configuring the view parameters.

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

    def setOffAxisView(self, clearDepth=True):
        """Apply an off-axis projection for stereoscopic rendering.

        Parameters
        ----------
        clearDepth
        forceBuffer

        Returns
        -------

        """
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()
        GL.glFrustum(*self.frustum)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glLoadIdentity()

        eyeOffset = self._iod / 2.0
        if self._buffer == 'left':
            GL.glTranslatef(eyeOffset, 0.0, -(self.scrDistCM / 100.0))
        elif self._buffer == 'right':
            GL.glTranslatef(-eyeOffset, 0.0, -(self.scrDistCM / 100.0))

        if clearDepth:
            GL.glClear(GL.GL_DEPTH_BUFFER_BIT)

        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDepthFunc(GL.GL_LEQUAL)
        GL.glDepthMask(GL.GL_TRUE)


class StereoMixin(object):
    """Mixin class for stereoscopy."""

    @property
    def iod(self):
        return self.getInterocularDistance()

    @iod.setter
    def iod(self, value):
        self.setInterocularDistance(value)

    def getInterocularDistance(self):
        """Get the interocular distance/separation presently used for view
        calculations.

        Returns
        -------
        float
            The current IOD in centimeters.

        """
        # this value is internally stored as meters!
        return self._iod * 100.0

    def setInterocularDistance(self, dist):
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
        #return self._iod * 100.0
        pass

    def setConvergeDist(self, dist):
        """Set the distance of the convergence plane in centimeters.

        Parameters
        ----------
        dist : float
            Distance to the convergence plane in centimeters.

        """
        #self._iod = float(dist) / 100.0
        pass

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
        if self.stereo is True:  # legacy mode
            pass

        # using multiple stereo buffers
        if hasattr(self, '_stereoBuffers'):
            try:
                GL.glBindFramebuffer(
                    GL.GL_FRAMEBUFFER,
                    self._stereoBuffers[buffer].id)
                GL.glReadBuffer(GL.GL_COLOR_ATTACHMENT0)
                GL.glDrawBuffer(GL.GL_COLOR_ATTACHMENT0)
            except KeyError:
                print("Invalid buffer specified. Exiting.")

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
        self._stereoBuffers = {
            'left': gltools.createFBO(),
            'right': gltools.createFBO()}

        # setup image attachments for each FBO
        for eye in ('left', 'right'):
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
        for eye in ('left', 'right'):
            GL.glBindTexture(
                GL.GL_TEXTURE_2D,
                self._stereoBuffers[eye].userData["frameTexture"].id)

            GL.glColor3f(1.0, 1.0, 1.0)  # glColor multiplies with texture
            if eye == 'left':
                GL.glColorMask(True, False, False, True)
            else:
                GL.glColorMask(False, True, True, True)

            GL.glBegin(GL.GL_TRIANGLE_STRIP)
            GL.glTexCoord2f(0.0, 1.0)
            GL.glVertex2f(-1.0, 1.0)
            GL.glTexCoord2f(0.0, 0.0)
            GL.glVertex2f(-1.0, -1.0)
            GL.glTexCoord2f(1.0, 1.0)
            GL.glVertex2f(1.0, 1.0)
            GL.glTexCoord2f(1.0, 0.0)
            GL.glVertex2f(1.0, -1.0)
            GL.glEnd()

        GL.glEnable(GL.GL_BLEND)
        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glUseProgram(0)