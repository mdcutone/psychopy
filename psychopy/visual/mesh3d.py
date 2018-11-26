"""A stimuli class for 3D objects.
"""

# Part of the PsychoPy library
# Copyright (C) 2018 Jonathan Peirce
# Distributed under the terms of the GNU General Public License (GPL).

from __future__ import absolute_import, print_function
from psychopy.tools import gltools

import numpy as np
import os.path
import pyglet.gl as GL
import ctypes
import math


class TransformMixin(object):
    """Mixin class for characterizing and manipulating the pose of 2- and 3-D
    objects in a scene.

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
                 ori=0.0,
                 axis=(0., 1., 0.),
                 *args, **kwargs):
        """Constructor for TransformMixin.

        Parameters
        ----------
        pos : ndarray, list or tuple of float
            Position of model in world coordinates.
        ori : float
            Rotation about the axis in degrees.
        axis : ndarray, list or tuple of float
            Rotation axis.
        args
        kwargs
        """
        # Try to be as consistent as possible with how other stimuli are
        # positioned, advanced users might want to work with the quaternions
        # and vectors directly.
        #
        self._pos = np.asarray(pos, dtype=float)  # position vector
        self._axis = np.asarray(axis, dtype=float)  # rotation axis vector
        self._ori = ori  # rotation angle

        # orientations are stored as quaternions
        self._rquat = np.zeros((4,), dtype=float)
        self._rquat[3] = 1.0

        # model matrix used for transformations
        self._modelMatrix = np.zeros((4, 4), dtype=np.float32, order='F')
        np.fill_diagonal(self._modelMatrix, 1.0)

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
        self._modelMatrix[:3, 3] = self._pos[:]
        self._modelMatrix[3, 3] = 1.0

    @property
    def ori(self):
        """Orientation of the stimulus in degrees about axis."""
        return self._ori

    @ori.setter
    def ori(self, value):
        self.setOri(value)

    def setOri(self, degrees):
        """Set the orientation using the specified quaternion.

        Parameters
        ----------
        degrees : float
            Angle of rotation in degrees.

        Returns
        -------
        None

        Notes
        -----
            Setting the orientation will update the orientation component of the
            model matrix associated with attribute 'modelMatrix'.

        """
        self._ori = float(degrees)
        rad = math.radians(self._ori)
        q = np.zeros((4,), dtype=float)
        np.multiply(self._axis, np.sin(rad / 2.0), out=q[:3])
        q[3] = math.cos(rad / 2.0)

        self.setQuaternion(q)

    @property
    def axis(self):
        """Axis of rotation."""
        return self._axis

    @axis.setter
    def axis(self, value):
        self.setAxis(value)

    def setAxis(self, axis):
        """Set the axis of rotation.

        Parameters
        ----------
        axis : ndarray, list, or tuple of float
            Axis of rotation defined as a vector (X, Y, Z). Axes will be
            automatically normalized.

        Returns
        -------
        None

        """
        self._axis[:] = axis[:]
        k = np.linalg.norm(self._axis)
        if k > np.finfo(np.float32).eps:  # normalize
            self._axis[:] /= k

        rad = math.radians(self._ori)
        q = np.zeros((4,), dtype=float)
        np.multiply(self._axis, np.sin(rad / 2.0), out=q[:3])
        q[3] = math.cos(rad / 2.0)

        self.setQuaternion(q)

    @property
    def quat(self):
        """Orientation quaternion."""
        return self._rquat

    @quat.setter
    def quat(self, value):
        self.setQuaternion(value)

    def setQuaternion(self, quat):
        """Set the orientation quaternion. This is used to derive the rotation
        components of the model matrix.

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

        Warnings
        --------
        Setting the quaternion directly invalidates the values of 'ori' and
        'axis'. Setting any of those values will overwrite any custom
        quaternion.

        """
        self._rquat[:] = quat[:]
        a = self._rquat[3]
        b, c, d = self._rquat[:3]

        a2 = a * a
        b2 = b * b
        c2 = c * c
        d2 = d * d

        self._modelMatrix[0, 0] = a2 + b2 - c2 - d2
        self._modelMatrix[1, 0] = 2.0 * (b * c + a * d)
        self._modelMatrix[2, 0] = 2.0 * (b * d - a * c)
        self._modelMatrix[3, 0] = 0.0

        self._modelMatrix[0, 1] = 2.0 * (b * c - a * d)
        self._modelMatrix[1, 1] = a2 - b2 + c2 - d2
        self._modelMatrix[2, 1] = 2.0 * (c * d + a * b)
        self._modelMatrix[3, 1] = 0.0

        self._modelMatrix[0, 2] = 2.0 * (b * d + a * c)
        self._modelMatrix[1, 2] = 2.0 * (c * d - a * b)
        self._modelMatrix[2, 2] = a2 - b2 - c2 + d2
        self._modelMatrix[3, 2] = 0.0

    @property
    def modelMatrix(self):
        """Computed model matrix."""
        return self._modelMatrix

    @modelMatrix.setter
    def modelMatrix(self, value):
        self._modelMatrix[:, :] = value[:, :]

        if self._modelMatrix.shape != (4, 4):
            raise ValueError("modelMatrix must be 4x4.")

    @property
    def dataPtr(self):
        """Model matrix as ctypes pointer."""
        return self._modelMatrix.ctypes.data_as(ctypes.POINTER(ctypes.c_float))


class ObjStim(TransformMixin):
    """Class for loading and presenting 3D stimuli in the Wavefront OBJ format.

    Only vertices, normals, texture coordinates, and faces defined in the OBJ
    file are used. Co-ordinates are loaded into vertex arrays for fast
    rendering.

    Warnings
    --------
        Loading an *.OBJ file is a slow process, be sure to do this outside
        of any time-critical routines!

    """

    def __init__(self, win, objFile, loadMtl=True, *args, **kwargs):
        """Constructor for ObjStim.

        Parameters
        ----------
        win : :class:`~psychopy.visual.Window`
            The :class:`~psychopy.visual.Window` object in which the stimulus
            will be rendered by default. (required)
        objFile : str
            Path to the *.OBJ file.
        loadMtl : bool
            Load the material library (if any) referenced by the *.OBJ file.
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

    def draw(self, win=None):
        """

        Parameters
        ----------
        win

        Returns
        -------

        """
        if win is not None:
            win.backend.setCurrent()

        GL.glDepthMask(GL.GL_TRUE)
        GL.glEnable(GL.GL_CULL_FACE)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDepthFunc(GL.GL_LEQUAL)
        GL.glShadeModel(GL.GL_SMOOTH)
        GL.glCullFace(GL.GL_BACK)
        GL.glDisable(GL.GL_BLEND)

        GL.glPushMatrix()
        GL.glMultMatrixf(self.dataPtr)
        # draw the model
        for group, vao in self._objInfo.drawGroups.items():
            gltools.useMaterial(self._mtllibInfo[group])
            gltools.drawVAO(vao)
        GL.glPopMatrix()

        # disable materials and lightsq
        gltools.useMaterial(None)

        GL.glDisable(GL.GL_CULL_FACE)
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glDepthFunc(GL.GL_LEQUAL)
        GL.glDepthMask(GL.GL_FALSE)
