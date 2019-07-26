"""A stimuli class for 3D objects.
"""

# Part of the PsychoPy library
# Copyright (C) 2018 Jonathan Peirce
# Distributed under the terms of the GNU General Public License (GPL).

from __future__ import absolute_import, print_function
from psychopy.tools import gltools, mathtools
from psychopy.visual import shaders, basevisual
from psychopy.tools.attributetools import (attributeSetter, logAttrib,
                                           setAttribute)

import numpy as np
import os.path
import pyglet.gl as GL
import string
import OpenGL.GL
import OpenGL.GL as GL2
import pyglet.gl.glu as GLU
import ctypes
from io import StringIO
from collections import OrderedDict
import math


phongVertSimple = """
varying vec3 N;
varying vec3 v;

void main(void)  
{     
    v = vec3(gl_ModelViewMatrix * gl_Vertex);       
    N = normalize(gl_NormalMatrix * gl_Normal);

    gl_FrontColor = gl_Color;
    gl_TexCoord[0] = gl_MultiTexCoord0;
    gl_Position = gl_ModelViewProjectionMatrix * gl_Vertex;  
}
          
"""

phongFragSimple = """
varying vec3 N;
varying vec3 v;  

uniform sampler2D texture0;

#define MAX_LIGHTS $nlights

void main (void)  
{  
    vec3 L;
    vec4 acc = vec4(0.0, 0.0, 0.0, 0.0);
    
    for (int i=0; i < MAX_LIGHTS; i++)
    {
        if (gl_LightSource[i].position.w == 0.0) {  // is directional?
            L = normalize(-gl_LightSource[i].position.xyz);
        } else {
            L = normalize(gl_LightSource[i].position.xyz - v); 
        }
        
        vec3 E = normalize(-v);
        vec3 R = normalize(-reflect(L,N));  
        
        vec4 Iamb = clamp(gl_FrontLightProduct[i].ambient * texture2D(texture0, gl_TexCoord[0].st), 0.0, 1.0);
        
        //calculate Diffuse Term:  
        vec4 Idiff = gl_FrontLightProduct[i].diffuse * max(dot(N,L), 0.0);
        Idiff = clamp(Idiff * texture2D(texture0, gl_TexCoord[0].st), 0.0, 1.0);     
        
        // calculate Specular Term:
        vec4 Ispec = gl_FrontLightProduct[i].specular 
                * pow(max(dot(R,E),0.0), 0.3 * gl_FrontMaterial.shininess);
        Ispec = clamp(Ispec, 0.0, 1.0); 
        
        // write Total Color:  
        acc += Iamb + Idiff + Ispec;
    }
    gl_FragColor = acc; 
}
          
"""

# compile simple lighting shaders
_phongShaders = {}
for i in range(8):
    fragSrc = string.Template(phongFragSimple).substitute(nlights=i+1)
    _phongShaders[i + 1] = shaders.compileProgram(phongVertSimple, fragSrc)


class RigidBodyPose(object):
    """Class for representing rigid body poses in 3D space.

    The pose of rigid bodies are represented by a position vector [x, y, z] and
    orientation quaternion [x, y, z, w]. Poses are mainly used to define the
    spatial configuration of objects and stimuli in the scene.

    Parameters
    ----------
    pos : array_like
        Position vector (x, y, z).
    ori : array_like
        Orientation quaternion vector (x, y, z, w).

    """
    def __init__(self, pos=(0., 0., 0.), ori=(0., 0., 0., 1.)):
        self._pos = np.zeros((3,), dtype=np.float32)
        self._ori = np.zeros((4,), dtype=np.float32)

        # transformation matrices
        self._R = np.identity(4, dtype=np.float32)
        self._T = np.identity(4, dtype=np.float32)
        self._M = np.identity(4, dtype=np.float32)

        # cache this, adds to much overhead to create on the fly
        self._ptrM = self._M.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

        # only update the matrix when changes are made
        self._updateTranslationMatrix = False
        self._updateRotationMatrix = False
        self._updateModelMatrix = False

        self.pos = pos
        self.ori = ori

    @property
    def pos(self):
        """Position coordinates [x, y, z]."""
        return self._pos

    @pos.setter
    def pos(self, value):
        self._pos[:] = value
        self._updateModelMatrix = self._updateTranslationMatrix = True

    @property
    def ori(self):
        """Orientation quaternion [x, y, z, w]."""
        return self._ori

    @ori.setter
    def ori(self, value):
        self._ori[:] = value

        # normalize the quaternion
        norm = np.linalg.norm(self._ori)
        if not np.isclose(norm, 0.0):
            self._ori /= norm

        self._updateModelMatrix = self._updateRotationMatrix = True

    @property
    def posOri(self):
        """Combined position and orientation."""
        return self._pos, self._ori

    @posOri.setter
    def posOri(self, value):
        self._pos[:] = value[0]
        self._ori[:] = value[1]

    def clear(self):
        """Clear all transformation stored in this pose. This zeros `pos` and
        sets `ori` to and identity quaternion.

        """
        self._ori[:3].fill(0.0)
        self._ori[3] = 1.0
        self._pos.fill(0.0)

        # Clear matrices here, this is much faster than computing matrices only
        # for them to return identity when getMatrix is called.
        self._T.fill(0.0)
        np.fill_diagonal(self._T, 1.0)
        self._R.fill(0.0)
        np.fill_diagonal(self._R, 1.0)
        self._M.fill(0.0)
        np.fill_diagonal(self._M, 1.0)

        self._updateTranslationMatrix = False
        self._updateRotationMatrix = False
        self._updateModelMatrix = False

    def __mul__(self, other):
        """Multiplication operator `*` for rigid body poses. This puts the
        second operand into the reference frame of the first.

        """
        p = other.ori
        # multiply the quaternions of the poses
        to_return = RigidBodyPose()
        to_return.ori[:3] = np.cross(self._ori[:3], p[:3]) + \
            self._ori[:3] * p[3] + p[:3] * self._ori[3]
        to_return.ori[3] = self._ori[3] * p[3] - self._ori[:3].dot(p[:3])

        # apply translation
        to_return.pos = self._pos + other.pos

        return to_return

    def __imul__(self, other):
        pass

    def __invert__(self):
        pass

    def getOriAxisAngle(self, degrees=True):
        """Get the orientation of this pose as an axis and angle.

        Parameters
        ----------
        degrees : bool, optional
            Return angle in degrees if `True`, else the result will be in
            radians.

        Returns
        -------
        tuple
            Orientation axis [ax, ay, az] and angle.

        Examples
        --------
        Get the axis of rotation and angle in radians of a `RigidBodyPose`::

            axis, angle = myPose.getOriAxisAngle(degrees=False)

        """
        dtype = np.dtype(self._ori.dtype).type

        v = np.sqrt(np.sum(np.square(self._ori[:3])))
        axis = self._ori[:3] / v
        angle = dtype(2.0) * np.arctan2(v, self._ori[3])

        return axis, np.degrees(angle) if degrees else degrees

    def setOriAxisAngle(self, axis, angle, acc=False, degrees=True):
        """Set the orientation of this pose using an axis and angle.

        Parameters
        ----------
        axis : array_like
            Vector defining the rotation axis in world space [ax, ay, az].
        angle : float
            Angle to rotate about `axis`.
        acc : bool, optional
            Accumulate rotations. If `True` the new rotation will be combined with
            the pose's current rotation. If `False`, the specified rotation will
            overwrite the current rotation.
        degrees : bool, optional
            Angle is specified as degrees if `True`, else the angle is in
            radians.

        Examples
        --------
        Set the orientation of a pose using an axis and angle::

            axis = (0., 0., -1.)  # -Z is axis of rotation
            angle = 90.0  # angle to rotate the rigid body about

            myPose.setOriAxisAngle(axis, angle)

        Rotate the rigid body about different axes, having their rotations
        accumulate by setting `acc=True`::

            myPose.setOriAxisAngle((1., 0., 0.), angleX)  # +X axis
            myPose.setOriAxisAngle((0., 1., 0.), angleY, acc=True)  # +Y axis
            myPose.setOriAxisAngle((0., 0., -1.), angleZ, acc=True)  # -Z axis

        """
        dtype = np.dtype(self._ori.dtype).type

        if degrees:
            halfRad = np.radians(angle, dtype=dtype) / dtype(2.0)
        else:
            halfRad = np.dtype(dtype).type(angle) / dtype(2.0)

        # normalize input axis
        norm = np.linalg.norm(np.asarray(axis, dtype=dtype))
        axis /= norm
        np.nan_to_num(axis, copy=False)  # fix NaNs

        if not acc:
            # overwrite rotation
            np.multiply(axis, np.sin(halfRad), out=self._ori[:3])
            self._ori[3] = np.cos(halfRad)
        else:
            # rotations are accumulated
            q = self._ori.copy()
            p = np.zeros((4,), dtype=dtype)
            np.multiply(axis, np.sin(halfRad), out=p[:3])
            p[3] = np.cos(halfRad)

            # multiply the quaternions of the poses
            self._ori[:3] = np.cross(q[:3], p[:3]) + q[:3] * p[3] + p[:3] * q[3]
            self._ori[3] = q[3] * p[3] - q[:3].dot(p[:3])

    def getAngleTo(self, p, degrees=True):
        """Get the relative angle to a point from this pose's forward direction.

        Parameters
        ----------
        p : array_like
            Point to compute angle to.
        degrees : bool, optional
            Return angle in degrees if `True`, else the result will be in
            radians.

        Returns
        -------
        float
            Angle between forward vector of this pose and point `p`.

        """
        pass

    def invert(self):
        """Get the inverse of this rigid body pose.

        Returns
        -------
        RigidBodyPose
            Inverse of this rigid body pose.

        """
        pass

    def transform(self, p):
        """Inverse transform a point.

        Parameters
        ----------
        p : array_like
            Points to transform.

        Returns
        -------
        ndarray
            Transformed point `p`.

        """
        pointIn = np.asarray(p, dtype=np.float32)

        # rotate the point using the quaternion @ ori
        u = np.cross(self._ori[:3], pointIn) * np.float32(2.0)
        toReturn = pointIn + self._ori[3] * u + np.cross(self._ori[:3], u)
        toReturn += self._pos

        # now translate it by the pose's translation
        return toReturn

    def inverseTransform(self, p):
        """Inverse transform a point.

        Parameters
        ----------
        p : array_like
            Points to transform.

        Returns
        -------
        ndarray
            Inverse transformed point `p`.

        """
        pointIn = np.asarray(p, dtype=np.float32)

        # inverse rotate
        pointIn -= self._pos
        u = np.cross(self._ori[:3], pointIn) * np.float32(2.0)
        toReturn = pointIn - self._ori[3] * u + np.cross(self._ori[:3], u)

        return toReturn

    def interp(self, to, weight):
        """Interpolate this pose."""
        pass

    def getModelMatrix(self, inverse=False, out=None):
        """Construct a 4x4 homogeneous transformation matrix from this pose.

        Parameters
        ----------
        inverse : bool
            Return the inverse matrix.
        out : ndarray, optional
            Optional 4x4 array to write values to.

        Returns
        -------
        ndarray
            4x4 homogeneous transformation matrix (row-major).

        """
        if not self._updateModelMatrix:
            return self._M

        # translation matrix
        if self._updateTranslationMatrix:
            self._T.fill(0.0)
            np.fill_diagonal(self._T, 1.0)
            self._T[:3, 3] = self._pos[:]

            self._updateTranslationMatrix = False

        # rotation matrix
        if self._updateRotationMatrix:
            b, c, d, a = self._ori[:]

            a2 = a * a
            b2 = b * b
            c2 = c * c
            d2 = d * d

            ab = a * b
            ac = a * c
            ad = a * d
            bc = b * c
            bd = b * d
            cd = c * d

            # no need to clear the matrix, all values are set
            u = np.float32(2.0)
            self._R[0, 0] = a2 + b2 - c2 - d2
            self._R[1, 0] = u * (bc + ad)
            self._R[2, 0] = u * (bd - ac)

            self._R[0, 1] = u * (bc - ad)
            self._R[1, 1] = a2 - b2 + c2 - d2
            self._R[2, 1] = u * (cd + ab)

            self._R[0, 2] = u * (bd + ac)
            self._R[1, 2] = u * (cd - ab)
            self._R[2, 2] = a2 - b2 - c2 + d2

            self._R[:3, 3] = 0.0
            self._R[3, 3] = 1.0

            self._updateRotationMatrix = False

        np.matmul(self._T, self._R, self._M)

        self._updateModelMatrix = False

        return self._M

    def distanceTo(self, p):
        """Distance from the position of this pose to `p`."""
        pass


class RigidBodyPoseMixin(basevisual.MinimalStim):
    """Mixin class for 3D stimuli whose poses are represented by a
    `RigidBodyPose` object or similar.

    Sub-classes will inherit a common interface for using `RigidBodyPose`-like
    classes to specify how they are positioned and rendered in a scene.

    Parameters
    ----------
    win : `~psychopy.visual.Window`
        Window object this pose refers to.
    pos : array_like
        Position vector [x, y, z].
    ori : array_like
        Orientation quaternion [x, y, z, w].

    """
    def __init__(self, pos=(0., 0., 0.), ori=(0., 0., 0., 1.), *args, **kwargs):
        """
        Attributes
        ----------
        thePose : Rigid body pose object.
        """
        super(RigidBodyPoseMixin, self).__init__(*args, **kwargs)
        self._thePose = RigidBodyPose(pos, ori)

    @property
    def thePose(self):
        """The rigid body pose object.

        By default a `RigidBodyPose` object is used. However, you can substitute
        this object with any class, as long as they expose a similar interface
        (eg. `LibOVRPose` from PsychXR).

        At the very least, objects set as `thePose` must have the following
        attributes and methods essential for rendering stimuli:

            * `pos` - Position vector [x, y, z].
            * `ori` - Orientation quaternion [x, y, z, w].
            * `getModelMatrix()` - Get pose transformations as a 4x4 matrix
              (row-order).

        Returned data must be Numpy arrays with type `ndarray`. Other than the
        above attributes, classes may differ greatly in terms of features which
        the user can access by directly manipulating the object referenced by
        `thePose`.

        Examples
        --------
        Rotating a rigid body stimulus 90 degrees about the -Z axis::

            rotationPose = RigidBodyPose()
            rotationPose.setOriAxisAngle((0., 0., -1.), 90., degrees=True)
            my3dStim.thePose *= rotationPose

        Using a compatible pose object (eg. from PsychXR)::

            # `my3dStim` is a subclass of `RigidBodyPoseMixin`
            my3dStim.thePose = hmd.trackedHandPoses[1]  # right hand pose
            my3dStim.draw()

        """
        return self._thePose

    @thePose.setter
    def thePose(self, value):
        self._thePose = value


CULL_FACE = {
    'back': GL.GL_BACK,
    'front': GL.GL_FRONT,
    GL.GL_BACK: 'back',
    GL.GL_FRONT: 'front'}

SHADE_MODEL = {'smooth': GL.GL_SMOOTH, 'flat': GL.GL_FLAT}


class MeshStimMixin(RigidBodyPoseMixin):
    """Mixin class for 3D mesh stimuli.

    """
    def __init__(self,
                 win,
                 pos=(0., 0., 0.),
                 ori=(0., 0., 0., 1.),
                 shadeModel='smooth',
                 cullFace='back'):

        self.win = win
        self._cullFace = CULL_FACE[cullFace]
        self._shadeModel = SHADE_MODEL[shadeModel]
        self.depthFunc = GL.GL_LEQUAL
        super(MeshStimMixin, self).__init__(pos, ori)

    def _prepareDraw(self):
        """Prepare for 3D stimulus rendering.

        This configures depth testing, face culling, and model transformation
        prior to rendering. The transformation of the model is computed from the
        associated rigid body pose object referenced by `thePose`.

        """
        # setup face culling
        GL.glCullFace(self._cullFace)
        GL.glEnable(GL.GL_CULL_FACE)

        # setup depth testing
        GL.glShadeModel(self._shadeModel)
        GL.glDepthMask(GL.GL_TRUE)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDepthFunc(self.depthFunc)

        GL.glEnable(GL.GL_BLEND)

        # get the model matrix
        M = self.thePose.getModelMatrix().ctypes.data_as(ctypes.POINTER(ctypes.c_float))

        GL.glPushMatrix()
        GL.glMultTransposeMatrixf(M)

    def _endDraw(self):
        """End 3D stimulus rendering.

        """
        GL.glPopMatrix()
        GL.glDisable(GL.GL_CULL_FACE)
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glEnable(GL.GL_BLEND)
        GL.glDepthMask(GL.GL_FALSE)

    def draw(self, win=None):
        raise NotImplementedError(
            'Stimulus classes must override visual.MeshStimMixin.draw')


class CornerStim(MeshStimMixin):
    """Class for rendering a corner.

    A corner is a reference object which visually indicates the direction of a
    rigid body pose's axes. Where the +X axis is red, +Y is green, and -Z is
    blue.

    """
    def __init__(self,
                 win,
                 pos=(0., 0., 0.),
                 ori=(0., 0., 0., 1.),
                 axisLength=0.25):

        super(CornerStim, self).__init__(win, pos, ori)
        self.axisLength = axisLength

    def draw(self, win=None):
        if win is None:
            self.win.backend.setCurrent()
        else:
            win._setCurrent()

        self._prepareDraw()

        GL.glBegin(GL.GL_LINES)
        GL.glColor3f(1.0, 0.0, 0.0)
        GL.glVertex3f(0.0, 0.0, 0.0)
        GL.glVertex3f(self.axisLength, 0.0, 0.0)
        GL.glEnd()
        GL.glBegin(GL.GL_LINES)
        GL.glColor3f(0.0, 1.0, 0.0)
        GL.glVertex3f(0.0, 0.0, 0.0)
        GL.glVertex3f(0.0, self.axisLength, 0.0)
        GL.glEnd()
        GL.glBegin(GL.GL_LINES)
        GL.glColor3f(0.0, 0.0, 1.0)
        GL.glVertex3f(0.0, 0.0, 0.0)
        GL.glVertex3f(0.0, 0.0, -self.axisLength)
        GL.glEnd()

        self._endDraw()


class ObjMeshStim(MeshStimMixin):
    """Class for loading and presenting 3D stimuli in the Wavefront OBJ format.

    Vertex positions, texture coordinates, and normals are loaded and packed
    into a single vertex buffer object (VBO). Vertex array objects (VAO) are
    created for each material with an index buffer referencing vertices assigned
    that material in the VBO. For maximum performance, keep the number of
    materials per object as low as possible, as switching between VAOs has some
    overhead.

    Material attributes are read from the material library file (*.MTL)
    associated with the *.OBJ file. This file will be automatically searched for
    and read during loading. Afterwards you can edit material properties by
    accessing the data structure of the `materials` attribute.

    Keep in mind that OBJ shapes are rigid bodies, the mesh itself cannot be
    deformed during runtime. However, meshes can be positioned and rotated as
    desired by manipulating the `RigidBodyPose` instance accessed through the
    `thePose` attribute.

    Warnings
    --------
        Loading an *.OBJ file is a slow process, be sure to do this outside
        of any time-critical routines!

    Examples
    --------
    Loading an *.OBJ file from a disk location::

        myObjStim = ObjMeshStim(win, '/path/to/file/model.obj')

    """
    def __init__(self,
                 win,
                 objFile,
                 pos=(0., 0., 0.),
                 ori=(0., 0., 0., 1.),
                 loadMtl=True,
                 loadTextures=True,
                 useShaders=True,
                 *args, **kwargs):
        """Constructor for ObjStim.

        Parameters
        ----------
        win : :class:`~psychopy.visual.Window`
            The :class:`~psychopy.visual.Window` object in which the stimulus
            will be rendered by default.
        objFile : str
            Path to the *.OBJ file.
        pos : array_like
            Position vector [x, y, z].
        ori : array_like
            Orientation quaternion [x, y, z, w].
        loadMtl : bool
            Load the material library (if any) referenced by the *.OBJ file. If
            the file is referenced by a relative path, and 'objFile' was
            specified as an absolute path. The absolute path to the *.OBJ file
            will be joined to the relative path of the *.MTL file. If False,
            you must specify your own material library.
        loadTextures : bool
            Load image textures referenced by materials in the *.MTL file. This
            value is ignored if loadMtl=False.

        """
        super(ObjMeshStim, self).__init__(win, pos, ori)

        self._materialVAOs = {}
        self._vertexData = None  # array for vertex data (read-only)
        self.useShaders = useShaders

        # check if the *.OBJ file exists
        self.objFile = objFile
        if not os.path.isfile(self.objFile):
            raise FileNotFoundError(
                "Cannot find *.obj file '{}'".format(self.objFile))
        self.mtlFile = None
        self._loadObjFile(self.objFile, loadMtl)  # load it

    @property
    def extents(self):
        """Minimum and maximum extents of the model in each dimension.
        """
        return self._extents

    @property
    def materials(self):
        """Materials associated with this model."""
        return self._mtllibInfo

    @materials.setter
    def materials(self, value):
        self._mtllibInfo = value

    def _loadMtlFile(self, mtlFile):
        """Load a *.MTL file and create material data structure."""
        pass

    def _loadObjFile(self, objFile, loadMtl):
        """Load and *.OBJ file and create vertex buffers."""
        # open the file, read it into memory
        with open(objFile, 'r') as f:
            objBuffer = StringIO(f.read())

        # unsorted attribute data lists
        positionDefs = []
        texCoordDefs = []
        normalDefs = []
        vertexAttrs = OrderedDict()
        faceDefs = {}
        materialFaces = {}

        nVertices = nTextureCoords = nNormals = nFaces = nMaterials = 0
        mtlFile = None
        vertexIdx = 0
        materialGroup = None
        # first pass, examine the file and load up vertex attributes
        for line in objBuffer.readlines():
            line = line.strip()  # clean up like
            if line.startswith('v '):
                positionDefs.append(tuple(map(float, line[2:].split(' '))))
                nVertices += 1
            elif line.startswith('vt '):
                texCoordDefs.append(tuple(map(float, line[3:].split(' '))))
                nTextureCoords += 1
            elif line.startswith('vn '):
                normalDefs.append(tuple(map(float, line[3:].split(' '))))
                nNormals += 1
            elif line.startswith('f '):
                faceAttrs = []
                for attrs in line[2:].split(' '):  # triangle vertex attrs
                    if attrs not in vertexAttrs.keys():  # new face
                        vertexAttrs[attrs] = vertexIdx
                        vertexIdx += 1
                    faceAttrs.append(vertexAttrs[attrs])
                faceDefs[nFaces] = faceAttrs
                materialFaces[materialGroup].append(nFaces)
                nFaces += 1
            elif line.startswith('o '):  # ignored for now
                pass
            elif line.startswith('usemtl '):
                materialGroup = line[7:]
                if materialGroup not in materialFaces.keys():
                    materialFaces[materialGroup] = []
            elif line.startswith('mtllib '):
                mtlFile = line.strip()[7:]

        # at the very least, we need vertices and facedefs
        if nVertices == 0 or nFaces == 0:
            raise RuntimeError(
                "Failed to load OBJ file, file contains no vertices or faces.")

        # Indicate if file has any texture coordinates of normals. If not, the
        # size of the storage buffer will be reduced and vertex pointers and
        # strides adjusted.
        hasTexCoords = nTextureCoords > 0
        hasNormals = nNormals > 0

        # build arrays to pass to VBO
        vertexAttrList = []
        for attrs, idx in vertexAttrs.items():
            attr = attrs.split('/')
            attrData = []
            if len(attr) > 1:  # vertices and texture coords only
                p = int(attr[0])
                attrData.extend(positionDefs[p - 1])
                if attr[1] != '':  # texcoord field not empty
                    if hasTexCoords:
                        t = int(attr[1])
                        attrData.extend(texCoordDefs[t - 1])
                else:
                    attrData.extend([0., 0.])
            if len(attr) > 2:  # has normals too
                if hasNormals:
                    n = int(attr[2])
                    attrData.extend(normalDefs[n - 1])
                else:
                    attrData.extend([0., 0., 0.])

            vertexAttrList.append(attrData)

        self._vertexData = np.asarray(vertexAttrList, dtype=np.float32)

        # compute the extents of the model
        verts = self._vertexData[:, :3]
        self._extents = (verts.min(axis=0), verts.max(axis=0))

        # create a VBO with the interleaved vertex data, loading data to VRAM
        self.win.backend.setCurrent()  # must be current
        self.vboId = GL.GLuint()
        GL.glGenBuffers(1, ctypes.byref(self.vboId))
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vboId)
        GL.glBufferData(
            GL.GL_ARRAY_BUFFER,
            self._vertexData.size * ctypes.sizeof(GL.GLfloat),
            self._vertexData.ctypes.data_as(ctypes.POINTER(GL.GLfloat)),
            GL.GL_STATIC_DRAW)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)

        # create a VAO and EBO for each material
        for materialName, materialFaceDefs in materialFaces.items():
            eboList = []
            for i in materialFaceDefs:
                eboList.extend(faceDefs[i])

            # create an element buffer object
            eboArray = np.asarray(eboList, dtype=np.uint32)
            eboId = GL.GLuint()
            GL.glGenBuffers(1, ctypes.byref(eboId))
            GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, eboId)
            GL.glBufferData(
                GL.GL_ELEMENT_ARRAY_BUFFER,
                eboArray.size * ctypes.sizeof(GL.GLuint),  # total buffer size
                eboArray.ctypes.data_as(ctypes.POINTER(GL.GLuint)),
                GL.GL_STATIC_DRAW)
            GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, 0)

            # factory for VAOs
            vaoId = GL.GLuint()
            GL.glGenVertexArrays(1, ctypes.byref(vaoId))
            GL.glBindVertexArray(vaoId)
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vboId)

            # compute VBO vertex stride
            stride = 3 * ctypes.sizeof(GL.GLfloat)
            stride += 2 * ctypes.sizeof(GL.GLfloat) if hasTexCoords else 0
            stride += 3 * ctypes.sizeof(GL.GLfloat) if hasNormals else 0

            # set attribute pointers to buffer data
            GL.glVertexAttribPointer(  # vertex
                0, 3, GL.GL_FLOAT, GL.GL_FALSE, stride, 0)
            GL.glEnableVertexAttribArray(0)

            if hasTexCoords:
                GL.glVertexAttribPointer(  # texture coord
                    8, 2, GL.GL_FLOAT, GL.GL_FALSE, stride,
                    3 * ctypes.sizeof(GL.GLfloat))
                GL.glEnableVertexAttribArray(8)

            if hasNormals:
                if hasTexCoords:
                    GL.glVertexAttribPointer(  # normals
                        2, 3, GL.GL_FLOAT, GL.GL_FALSE, stride,
                        5 * ctypes.sizeof(GL.GLfloat))
                else:
                    GL.glVertexAttribPointer(
                        2, 3, GL.GL_FLOAT, GL.GL_FALSE, stride,
                        3 * ctypes.sizeof(GL.GLfloat))
                GL.glEnableVertexAttribArray(2)

            GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, eboId)  # element array
            GL.glBindVertexArray(0)

            self._materialVAOs[materialName] = (vaoId, len(eboArray))

        # load the *.MTL file if requested, otherwise it must be specified later
        # before rendering
        if loadMtl and mtlFile is not None:
            # path might be relative but not in CWD, try to resolve the path
            if os.path.isabs(objFile) and not os.path.isabs(mtlFile):
                mtlPath = os.path.join(
                    os.path.split(objFile)[0], mtlFile)
            else:
                mtlPath = mtlFile

            if os.path.isfile(mtlPath):
                self._mtllibInfo = gltools.loadMtlFile(mtlPath)
            else:
                raise FileNotFoundError(
                    "Cannot find *.mtl file '{}'".format(mtlPath))

    def draw(self, win=None, useLights=None):
        """Render the 3D mesh to the scene.

        Parameters
        ----------
        win : :class:`~psychopy.visual.Window`
            The :class:`~psychopy.visual.Window` object in which the stimulus
            will be rendered to. The window must share a context with the
            window specified when instantiating the object.
        useLights : list or tuple
            List of lights to enable when rendering the model.

        """
        if win is None:
            self.win.backend.setCurrent()
        else:
            win._setCurrent()

        self._prepareDraw()

        # draw the model
        for group, vao in self._materialVAOs.items():
            gltools.useMaterial(self._mtllibInfo[group])
            gltools.useLights(useLights)
            GL.glBindVertexArray(vao[0])
            GL.glDrawElements(GL.GL_TRIANGLES, vao[1], GL.GL_UNSIGNED_INT, None)
            GL.glBindVertexArray(0)

        # disable materials
        gltools.useMaterial(None)
        gltools.useLights(None)

        self._endDraw()

