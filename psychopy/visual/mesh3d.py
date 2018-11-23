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


class TransformMixin(object):
    """Mixin class for characterizing and manipulating the pose of 2- and 3-D
    objects in a scene.

    """
    def __init__(self, *args, **kwargs):
        """Constructor for TransformMixin.

        Parameters
        ----------
        args
        kwargs

        """
        self._pos = np.zeros((3,), dtype=np.float32)  # position vector
        self._ori = np.zeros((4,), dtype=np.float32)  # orientation quaternion
        self._ori[3] = 1.0  # identity

        self._modelMatrix = np.zeros((4, 4), np.float32)
        np.fill_diagonal(self._modelMatrix, 1.0)

    @property
    def ori(self):
        """Orientation of the stimulus as a quaternion."""
        return self._ori

    @ori.setter
    def ori(self, value):
        self.setOri(value)

    def setOri(self, quat):
        """Set the orientation using the specified quaternion.

        Parameters
        ----------
        quat : ndarray, list or tuple
            Quaternion to define the orientation of the stimuli (x, y, z, w).

        Returns
        -------
        None

        Notes
        -----
        Setting the orientation will update the orientation component of the
        model matrix associated with attribute 'modelMatrix'.

        """
        self._ori = np.asarray(quat, dtype=np.float32)
        if self._ori.shape != (4,):
            raise ValueError("ori must be quaternion with shape (4,)")

        a = self._ori[3]
        b, c, d = self._ori[:3]

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

    def rotateAngleAxis(self, angle, axis, clear=False):
        """Rotate this object about a specified axis. Rotations are cumulative
        unless clear=True.

        Parameters
        ----------
        angle : float
            Rotation angle in radians.
        axis : ndarray, list or tuple of float
            Axis of rotation vector.
        clear : bool
            Clear previous rotations. If False, the rotation will be cumulative.

        Notes
        -----
        Rotations are represented internally using quaternions. This avoids
        issues such as gimbal lock and allows for interpolation between rotation
        states.

        """
        axis = np.asarray(axis, dtype=np.float32)

        q = np.zeros((4,), np.float32)
        s = np.sin(angle / 2.0)
        c = np.cos(angle / 2.0)
        np.multiply(axis, s, out=q[:3])
        q[3] = c

        if clear:
            self.setOri(q)  # update quaternion and we're done
            return

        self.setOri(TransformMixin.quatMultiply(self._ori, q))

    @property
    def pos(self):
        """Position of the object in the scene (3-vector)."""
        return self._pos

    @pos.setter
    def pos(self, value):
        self.setPos(value)

    def setPos(self, pos):
        """Set the position/translation of the object in the scene.

        Parameters
        ----------
        pos : ndarray, list or tuple
            Vector to translate by (x, y, z).

        Returns
        -------
        None

        """
        self._pos = np.asarray(pos, dtype=np.float32)
        self._modelMatrix[:3, 3] = self._pos
        self._modelMatrix[3, 3] = 1.0

    def translate(self, v, clear=False):
        """Apply translation. Multiple calls to translate are cumulative unless
        clear=True.

        """
        if clear:  # inplace translation
            self._pos += np.asarray(v, dtype=np.float32)
            self._modelMatrix[:3, 3] = self._pos
            self._modelMatrix[3, 3] = 1.0
        else:
            self.setPos(v)

    @property
    def modelMatrix(self):
        return self._modelMatrix

    @modelMatrix.setter
    def modelMatrix(self, value):
        self._modelMatrix = np.asarray(value, dtype=np.float32)

        if self._modelMatrix.shape != (4, 4):
            raise ValueError("modelMatrix must be 4x4.")

    def transform(self, obj):
        """Transform another object's position and orientation.

        Parameters
        ----------
        obj

        Returns
        -------

        """
        pass

    @staticmethod
    def quatMultiply(p, q):
        """Multiply quaternions.

        Parameters
        ----------
        q : ndarray, list or tuple of float
            Quaternion to invert.

        Returns
        -------

        """
        # see https://github.com/datenwolf/linmath.h/blob/master/linmath.h for
        # original implementation.
        #
        # multiply the new and previous quaternion to combine rotations
        p = np.asarray(p, dtype=np.float32)
        q = np.asarray(q, dtype=np.float32)

        r = np.zeros((4,), np.float32)
        r[3] = 0.0
        r[:3] = np.cross(p[:3], q[:3])
        r[:3] += p[:3] * q[3]
        r[:3] += q[:3] * p[3]
        r[3] = p[3] * q[3] - np.dot(p[:3], q[:3])

        return r

    @staticmethod
    def quatInvert(q):
        """Invert a quaternion.

        Parameters
        ----------
        q : ndarray, list or tuple of float
            Quaternion to invert.

        Returns
        -------

        """
        return np.asarray((-q[0], -q[1], -q[2], q[3]), dtype=np.float32)


class SceneContext(object):
    """Class for managing the scene.

    """
    def __init__(self):
        pass


class WavefrontObjStim(TransformMixin):
    """Class for loading and presenting 3D stimuli in the Wavefront OBJ format.

    """
    def __init__(self, win, objFile, loadMtl=True, *args, **kwargs):
        """Constructor for WavefrontObjStim.

        Parameters
        ----------
        win : Window
            pass
        objFile : str
            Path to the *.OBJ file.
        loadMtl : bool
            Load the material library (if any) referenced by the *.OBJ file.
        args
        kwargs

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

        super(WavefrontObjStim, self).__init__(*args, **kwargs)

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
        modelMatrix = np.asfortranarray(self.modelMatrix).ctypes.data_as(
            ctypes.POINTER(ctypes.c_float))
        GL.glMultMatrixf(modelMatrix)
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
