"""A stimuli class for 3D objects.
"""

# Part of the PsychoPy library
# Copyright (C) 2018 Jonathan Peirce
# Distributed under the terms of the GNU General Public License (GPL).

from __future__ import absolute_import, print_function
from psychopy.tools import gltools
from psychopy.core import getTime

import numpy as np
import os.path
import pyglet.gl as GL
import pyglet.gl.glu as GLU
import ctypes
import math


class TransformMixin(object):
    """Mixin class for characterizing and manipulating the pose of 2- and 3-D
    objects in a scene.

    Poses are defined by a quaternion and vector for orientation and position,
    respectively. These components can be set directly or computed using various
    class methods. Ultimately, these transformation components are used to
    create a 4x4 model matrix.

    Notes
    -----
        The orientation of the object is specified using an axis and angle,
        where orientation is stored internally using a quaternion derived from
        them. This quaternion is updated automatically when either 'ori' of
        'axis' are changed. The quaternion can be specified directly if one
        wishes, however the values of 'angle' and 'axis' will be invalid.
        Regardless of how the orientation is set, the quaternion is used to
        derive the rotation groups of the model matrix.

    """

    def __init__(self,
                 pos=(0., 0., 0.),
                 ori=(0., 0., 0., 1.),
                 scale=1.0,
                 *args, **kwargs):
        """Constructor for TransformMixin.

        Parameters
        ----------
        pos : ndarray, list or tuple of float
            Position of stimuli in world coordinates.
        ori : ndarray, list or tuple of float
            Orientation quaternion in form [x, y, z, w] where w is real and
            x, y, z are imaginary components.
        scale : float
            Scaling factor for the stimuli, applied to the computed model
            matrix. Does not affect 'pos' or 'ori'.

        """
        # orientations are stored as quaternions
        self._rquat = np.asarray(ori, dtype=float)

        # transformation matrices, these are composed to create the final model
        # matrix
        self._S = np.zeros((4, 4), dtype=float)
        np.fill_diagonal(self._S, 1.0)
        self._R = np.zeros((4, 4), dtype=float)
        np.fill_diagonal(self._R, 1.0)
        self._T = np.zeros((4, 4), dtype=float)
        np.fill_diagonal(self._T, 1.0)

        # model matrix used for transformations
        self._M = np.zeros((4, 4), dtype=float)
        np.fill_diagonal(self._M, 1.0)

        # Try to be as consistent as possible with how other stimuli are
        # positioned, advanced users might want to work with the quaternions
        # and vectors directly.
        #
        self._pos = np.asarray(pos, dtype=float)  # position vector
        self._ori = 0.0  # rotation angle
        self._scale = 0.0  # scaling factor

        # compute initial matrices
        self.setScale(scale)
        self.setPos(pos)

        # flag that the model matrix needs updating
        self._updateModelMatrix = True

    @property
    def pos(self):
        """Position of the object in the scene (3-vector)."""
        return self._pos

    @pos.setter
    def pos(self, xyz):
        self.setPos(xyz)

    def getPos(self):
        """Get the current position/translation of the object."""
        return self._pos

    def setPos(self, pos):
        """Set the position/translation of the object in the scene.

        Parameters
        ----------
        pos : ndarray, list or tuple of float
            Vector to translate by (x, y, z).

        Returns
        -------
        None

        Notes
        -----
            Setting the position vector will update the translation component of
            the model matrix.

        """
        self._pos[:] = pos[:]
        self._T.fill(0.0)
        np.fill_diagonal(self._T, 1.0)
        self._T[:3, 3] = self._pos[:]

        self._updateModelMatrix = True

    @property
    def ori(self):
        """Orientation of the stimulus in degrees about axis."""
        return self._ori

    @ori.setter
    def ori(self, value):
        self.setOri(value)

    def setOri(self, quat):
        """Set the orientation using the specified quaternion. This is used to
        derive the rotation groups of the model matrix.

        Parameters
        ----------
        quat : ndarray, list or tuple of float
            Quaternion defining the orientation of the object as a length 4
            vector. Where the first three values are the imaginary components
            and the last one is real.

        Returns
        -------
        None

        Notes
        -----
            The rotation component of the model matrix is computed upon setting
            the quaternion.

        """
        self._rquat[:] = quat[:]
        a = self._rquat[3]
        b, c, d = self._rquat[:3]

        a2 = a * a
        b2 = b * b
        c2 = c * c
        d2 = d * d

        # no need to clear the matrix, all values are set
        #
        self._R[0, 0] = (a2 + b2 - c2 - d2)
        self._R[1, 0] = 2.0 * (b * c + a * d)
        self._R[2, 0] = 2.0 * (b * d - a * c)
        self._R[3, 0] = 0.0

        self._R[0, 1] = 2.0 * (b * c - a * d)
        self._R[1, 1] = (a2 - b2 + c2 - d2)
        self._R[2, 1] = 2.0 * (c * d + a * b)
        self._R[3, 1] = 0.0

        self._R[0, 2] = 2.0 * (b * d + a * c)
        self._R[1, 2] = 2.0 * (c * d - a * b)
        self._R[2, 2] = (a2 - b2 - c2 + d2)
        self._R[3, 2] = 0.0

        self._R[:3, 3] = 0.0
        self._R[3, 3] = 1.0

        self._updateModelMatrix = True

    def rotateAxisAngle(self, axis, angle, degrees=False, clear=True):
        """Rotate the stimuli about a specified 'axis' by 'angle'.

        Parameters
        ----------
        axis : tuple, list or ndarray of float
            Axis of rotation (X, Y, Z). Should be normalized.
        angle : float
            Rotation angle in radians. Rotations are right-handed about the
            specified axis.
        degrees : bool
            Convert 'angle' to degrees from radians.
        clear : bool
            Clear previous rotations. If False, the specified rotation adds to
            the current orientation.

        Returns
        -------
        None

        """
        rad = math.radians(float(angle)) if degrees else float(angle)
        q = np.zeros((4,), dtype=float)
        np.multiply(axis, np.sin(rad / 2.0), out=q[:3])
        q[3] = math.cos(rad / 2.0)

        # multiply the current quaternion, combining their orientations
        if not clear:
            self.multQuat(q)
        else:
            self.setOri(q)

    def multQuat(self, quat):
        """Multiply the current orientation by a quaternion, combining their
        orientations.

        Parameters
        ----------
        quat : ndarray, list or tuple of float
            Quaternion defining the orientation of the object as a length 4
            vector. Where the first three values are the imaginary components
            and the last one is real.

        Returns
        -------
        None

        """
        p = np.zeros((4,), dtype=float)
        p[:3] = np.cross(self._rquat[:3], quat[:3]) + \
            self._rquat[:3] * quat[3] + quat[:3] * self._rquat[3]
        p[3] = self._rquat[3] * quat[3] - self._rquat[:3].dot(quat[:3])

    @property
    def scale(self):
        """Scaling (uniform) factor for the stimuli."""
        return self.getScale()

    @scale.setter
    def scale(self, value):
        self.setScale(value)

    def getScale(self):
        """Get the scaling factor for the stimuli."""
        return self._scale

    def setScale(self, factor):
        """Set the scale factor for the stimuli."""
        self._scale = float(factor)

        self._S.fill(0.0)
        self._S[0, 0] = self._scale
        self._S[1, 1] = self._scale
        self._S[2, 2] = self._scale
        self._S[3, 3] = 1.0

        self._updateModelMatrix = True

    @property
    def modelMatrix(self):
        """Computed model matrix."""
        return self.getModelMatrix()

    @modelMatrix.setter
    def modelMatrix(self, value):
        self._M[:, :] = value[:, :]

        # prevent the model matrix from updating if set directly by the user
        self._updateModelMatrix = False

        if self._M.shape != (4, 4):
            raise ValueError("modelMatrix must be 4x4.")

    def getModelMatrix(self):
        """Get the current model matrix. The matrix is recomputed if any
        related parameter was updated.

        """
        # compose the rotation, translation and scaling matrices into a
        # model matrix
        if self._updateModelMatrix:
            np.matmul(self._S, self._R, self._M)
            np.matmul(self._T, self._M, self._M)
            self._updateModelMatrix = False

        return np.asarray(self._M, dtype=np.float32)

    @property
    def dataPtr(self):
        """Model matrix as ctypes pointer.

        """
        return self.modelMatrix.ctypes.data_as(ctypes.POINTER(ctypes.c_float))


class SphereStim(TransformMixin):
    """Class for rendering spheres. Spheres drawn using gluQuadrics.

    """
    def __init__(self,
                 win,
                 radius=0.5,
                 slices=16,
                 stacks=32,
                 color=(0, 0, 0),
                 *args, **kwargs):
        """Constructor for SphereStim.

        Parameters
        ----------
        win : :class:`~psychopy.visual.Window`
            The :class:`~psychopy.visual.Window` object in which the stimulus
            will be rendered by default. (required)
        radius : float
            Radius of the sphere in meters.
        slices : int
            Subdivisions about the z-axis.
        stacks : int
            Subdivisions along the z-axis.
        color : ndarray, tuple or list of float
            RGB color of the sphere.
        args
        kwargs

        """
        self.win = win

        self.radius = radius
        self.slices = slices
        self.stacks = stacks

        self._quadric = GLU.gluNewQuadric()
        GLU.gluQuadricNormals(self._quadric, GL.GLU_SMOOTH)
        GLU.gluQuadricOrientation(self._quadric, GL.GLU_OUTSIDE)

        super(SphereStim, self).__init__(*args, **kwargs)

    def draw(self, win=None):
        if win is not None:
            win.backend.setCurrent()

        GL.glCullFace(GL.GL_BACK)
        GL.glShadeModel(GL.GL_SMOOTH)
        GL.glDepthMask(GL.GL_TRUE)
        GL.glEnable(GL.GL_CULL_FACE)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_BLEND)
        GL.glDepthFunc(GL.GL_LEQUAL)

        GL.glPushMatrix()
        #GL.glMultMatrixf(self.dataPtr)
        #GL.glTranslatef(0.0, 0.0, -1.5)
        GL.glMultMatrixf(self.dataPtr)
        #GL.glColor3f(1.0, 1.0, 1.0)
        GLU.gluSphere(self._quadric, self.radius, self.slices, self.stacks)
        GL.glPopMatrix()

        GL.glDisable(GL.GL_CULL_FACE)
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glEnable(GL.GL_BLEND)
        GL.glDepthMask(GL.GL_FALSE)


class ObjStim(TransformMixin):
    """Class for loading and presenting 3D stimuli in the Wavefront OBJ format.

    This class provides a simplified interface similar to 2D stimuli for
    drawing and configuration.

    Only vertices, normals, texture coordinates, and faces defined in the OBJ
    file are used. Co-ordinates are loaded into vertex arrays for fast
    rendering.

    Warnings
    --------
        Loading an *.OBJ file is a slow process, be sure to do this outside
        of any time-critical routines!

    """

    def __init__(self,
                 win,
                 objFile,
                 loadMtl=True,
                 loadTextures=True,
                 *args, **kwargs):
        """Constructor for ObjStim.

        Parameters
        ----------
        win : :class:`~psychopy.visual.Window`
            The :class:`~psychopy.visual.Window` object in which the stimulus
            will be rendered by default. (required)
        objFile : str
            Path to the *.OBJ file.
        loadMtl : bool
            Load the material library (if any) referenced by the *.OBJ file. If
            the file is referenced by a relative path, and 'objFile' was
            specified as an absolute path. The absolute path to the *.OBJ file
            will be joined to the relative path of the *.MTL file. If False,
            you must specify your own material library.
        loadTextures : bool
            Load image textures referenced by materials in the *.MTL file. This
            value is ignored if loadMtl=False.
        pos : ndarray, list or tuple of float
            Position of the stimulus origin relative to the scene origin.
        ori : float
            Orientation of the stimulus about some axis in degrees (see 'axis').
        axis : ndarray, list or tuple of float
            Axis of rotation.

        """
        self.win = win

        # check if the *.OBJ file exists
        self.objFile = objFile
        if not os.path.isfile(self.objFile):
            raise FileNotFoundError(
                "Cannot find *.obj file '{}'".format(self.objFile))

        # load the OBJ file
        self._objInfo = gltools.loadObjFile(self.objFile)

        # load the *.MTL file if requested, otherwise it must be specified later
        # before rendering
        if loadMtl and self._objInfo.mtlFile is not None:
            # path might be relative but not in CWD, try to resolve the path
            if os.path.isabs(self.objFile) and not os.path.isabs(
                    self._objInfo.mtlFile):
                mtlPath = os.path.join(
                    os.path.split(self.objFile)[0], self._objInfo.mtlFile)
            else:
                mtlPath = self._objInfo.mtlFile

            if os.path.isfile(mtlPath):
                self._mtllibInfo = gltools.loadMtlFile(mtlPath)
            else:
                raise FileNotFoundError(
                    "Cannot find *.mtl file '{}'".format(mtlPath))

        super(ObjStim, self).__init__(*args, **kwargs)

    @property
    def materials(self):
        return self._mtllibInfo

    def _prepareObjDraw(self):
        """Called before drawing objects to setup the environment.

        """
        GL.glCullFace(GL.GL_BACK)
        GL.glShadeModel(GL.GL_SMOOTH)
        GL.glDepthMask(GL.GL_TRUE)
        GL.glEnable(GL.GL_CULL_FACE)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_BLEND)
        GL.glDepthFunc(GL.GL_LEQUAL)

    def _finishedObjDraw(self):
        """Called after drawing all objects.

        """
        GL.glDisable(GL.GL_CULL_FACE)
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glEnable(GL.GL_BLEND)
        GL.glDepthMask(GL.GL_FALSE)

    def draw(self, win=None):
        """Render the object.

        Parameters
        ----------
        win : :class:`~psychopy.visual.Window`
            The :class:`~psychopy.visual.Window` object in which the stimulus
            will be rendered to. The window must share a context with the
            window specified when instantiating the object.

        Returns
        -------
        None

        """
        if win is not None:
            win.backend.setCurrent()

        self._prepareObjDraw()

        GL.glPushMatrix()
        GL.glMultMatrixf(self.dataPtr)
        # draw the model
        for group, vao in self._objInfo.drawGroups.items():
            gltools.useMaterial(self._mtllibInfo[group])
            gltools.drawVAO(vao)
        GL.glPopMatrix()

        # disable materials and lightsq
        gltools.useMaterial(None)

        self._finishedObjDraw()
