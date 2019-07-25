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
import OpenGL.GL
import OpenGL.GL as GL2
import pyglet.gl.glu as GLU
import ctypes
from io import StringIO
from collections import OrderedDict
import math


vert_prog = """
varying vec3 N;
varying vec3 v;

void main(void)  
{     
    v = vec3(gl_ModelViewMatrix * gl_Vertex);       
    N = normalize(gl_NormalMatrix * gl_Normal);

    gl_FrontColor = gl_Color;
    gl_TexCoord[0] = gl_MultiTexCoord0;
    gl_TexCoord[1] = gl_MultiTexCoord1;
    gl_TexCoord[2] = gl_MultiTexCoord2;
    gl_Position = gl_ModelViewProjectionMatrix * gl_Vertex;  
}
          
"""

#
frag_prog = """
varying vec3 N;
varying vec3 v;  

uniform sampler2D texture0;

void main (void)  
{  
   vec3 L = normalize(gl_LightSource[0].position.xyz - v);   
   vec3 E = normalize(-v); // we are in Eye Coordinates, so EyePos is (0,0,0)  
   vec3 R = normalize(-reflect(L,N));  
 
   //calculate Ambient Term:  
   vec4 Iamb = clamp(gl_FrontLightProduct[0].ambient * texture2D(texture0, gl_TexCoord[0].st), 0.0, 1.0);

   //calculate Diffuse Term:  
   vec4 Idiff = gl_FrontLightProduct[0].diffuse * max(dot(N,L), 0.0);
   Idiff = clamp(Idiff * texture2D(texture0, gl_TexCoord[0].st), 0.0, 1.0);     
   
   // calculate Specular Term:
   vec4 Ispec = gl_FrontLightProduct[0].specular 
                * pow(max(dot(R,E),0.0), 0.3 * gl_FrontMaterial.shininess);
   Ispec = clamp(Ispec, 0.0, 1.0); 

   // write Total Color:  
   gl_FragColor = Iamb + Idiff + Ispec;     
}
          
"""

prog = shaders.compileProgram(vert_prog, frag_prog)


class RigidBodyPose(object):
    """Class for representing rigid body poses in 3D space.

    The pose of rigid bodies are represented by a position vector [x, y, z] and
    orientation quaternion [x, y, z, w].

    """
    def __init__(self, pos=(0., 0., 0.), ori=(0., 0., 0., 1.)):
        # transformation matrices
        self._R = np.identity(4, dtype=np.float32)
        self._T = np.identity(4, dtype=np.float32)
        self._M = np.identity(4, dtype=np.float32)

        self._pos = np.zeros((3,), dtype=np.float32)
        self._ori = np.zeros((4,), dtype=np.float32)

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
        """Position and orientation."""
        return self._pos, self._ori

    @posOri.setter
    def posOri(self, value):
        self._pos[:] = value[0]
        self._ori[:] = value[1]

    def __mul__(self, other):
        """Multiplication operator `*` for rigid body poses."""
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

        """
        pass

    def setOriAxisAngle(self, axis, angle, degrees=True):
        """Set the orientation of this pose using an axis and angle.

        Parameters
        ----------
        axis : array_like
            Vector defining the rotation axis in world space [ax, ay, az].
        angle : float
            Angle to rotate about `axis`.
        degrees : bool, optional
            Angle is specified as degrees if `True`, else the angle is in
            radians.

        """
        pass

    def angleTo(self, p, degrees=True):
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

    def transform(self, p):
        """Transform points.

        Parameters
        ----------
        p : array_like
            Points to transform.

        Returns
        -------
        ndarray
            Transformed points `p`.

        """
        pointIn = np.zeros((3,), dtype=np.float32)
        pointIn[:] = p  # must be length 3

        # rotate the point using the quaternion @ ori
        u = np.cross(self._ori[:3], pointIn) * np.float32(2.0)
        toReturn = pointIn + self._ori[3] * u + np.cross(self._ori[:3], u)
        toReturn += self._pos

        # now translate it by the pose's translation
        return toReturn

    def inverseTransform(self, p):
        """Inverse transform a points."""
        pass

    def interp(self, to, weight):
        """Interpolate this pose."""
        pass

    @property
    def matrix(self):
        """4x4 homogeneous transformation matrix from this pose."""
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
            a = self._ori[3]
            b, c, d = self._ori[:3]

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

    @property
    def inverseMatrix(self):
        """4x4 homogeneous inverse transformation matrix from this pose."""
        return 1

    def getMatrix(self, inverse=False, out=None):
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
        pass

    def distanceTo(self, p):
        """Distance from the position of this pose to `p`."""
        pass


class RigidBodyPoseMixin(object):
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
    def __init__(self, pos=(0., 0., 0.), ori=(0., 0., 0., 1.)):
        """
        Attributes
        ----------
        thePose : Rigid body pose object.
        """
        self._thePose = RigidBodyPose(pos, ori)

    @property
    def thePose(self):
        """The rigid body pose object.

        By default a `RigidBodyPose` object is used. However, you can substitute
        this object with any class, as long as they expose a similar interface
        (eg. `LibOVRPose` from PsychXR).

        At the very least, objects set as `thePose` must have the following
        attributes essential for rendering stimuli:

            * `pos` - Position vector [x, y, z].
            * `ori` - Orientation quaternion [x, y, z, w].
            * `matrix` - Pose transformations as a 4x4 matrix (row-order).

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
        M = self.thePose.matrix.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

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


class ObjStim(MeshStimMixin):
    """Class for loading and presenting 3D stimuli in the Wavefront OBJ format.

    Warnings
    --------
        Loading an *.OBJ file is a slow process, be sure to do this outside
        of any time-critical routines!

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
            will be rendered by default. (required)
        pos : array_like
            Position vector [x, y, z].
        ori : array_like
            Orientation quaternion [x, y, z, w].
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

        """
        super(ObjStim, self).__init__(win, pos, ori)

        # check if the *.OBJ file exists
        self.objFile = objFile
        if not os.path.isfile(self.objFile):
            raise FileNotFoundError(
                "Cannot find *.obj file '{}'".format(self.objFile))

        self.win.backend.setCurrent()  # must be current
        self.objVAOs = {}
        self.vao = None
        self._vertexData = None
        self.useShaders = useShaders

        # load the OBJ file
        self.mtlFile = None
        self._loadObjFile(self.objFile, loadMtl)

    @property
    def vertices(self):
        """Array of loaded vertices."""
        return self._vertexData[:, :3]

    @property
    def texCoords(self):
        """Array of loaded texture coordinates."""
        return self._vertexData[:, 3:5]

    @property
    def normals(self):
        """Array of loaded vertex normals."""
        return self._vertexData[:, 5:]

    @property
    def materials(self):
        """Materials associated with this model."""
        return self._mtllibInfo

    @materials.setter
    def materials(self, value):
        self._mtllibInfo = value

    def _loadObjFile(self, objFile, loadMtl):
        """Load and obj file and create vertex buffers."""
        # open the file, read it into memory
        with open(objFile, 'r') as f:
            objBuffer = StringIO(f.read())

        nVertices = nTextureCoords = nNormals = nFaces = nObjects = nMaterials = 0
        mtlFile = None
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
                mtlFile = line.strip()[7:]

        # error check
        if nVertices == 0:
            raise RuntimeError(
                "Failed to load OBJ file, file contains no vertices.")

        objBuffer.seek(0)  # reset file position

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

        # parse attributes
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
                    if attrs not in vertexAttrs.keys():
                        p, t, n = map(int, attrs.split('/'))
                        vertexAttrList.append(positionDefs[p - 1])
                        texCoordAttrList.append(texCoordDefs[t - 1])
                        normalAttrList.append(normalDefs[n - 1])
                        vertexIndices[attrs] = vertexIdx
                        vertexIdx += 1
                    faceDef.append(vertexIndices[attrs])
                materialGroups[materialGroup].extend(faceDef)
            elif line.startswith('usemtl '):
                materialGroup = line[7:]
                if materialGroup not in materialGroups.keys():
                    materialGroups[materialGroup] = []

        # Vertex attributes are interleaved like this in the VBO
        # [v0, v1, v2, t0, t1, n0, n1, n2, ... ]
        #
        self._vertexData = np.hstack(
            (np.asarray(vertexAttrList, dtype=np.float32),
             np.asarray(texCoordAttrList, dtype=np.float32),
             np.asarray(normalAttrList, dtype=np.float32)))

        # create a VBO with the interleaved vertex data, loading data to VRAM
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
        for group, elements in materialGroups.items():
            # create an element buffer object
            elements = np.asarray(elements, dtype=np.uint32)
            eboId = GL.GLuint()
            GL.glGenBuffers(1, ctypes.byref(eboId))
            GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, eboId)
            GL.glBufferData(
                GL.GL_ELEMENT_ARRAY_BUFFER,
                elements.size * ctypes.sizeof(GL.GLuint),  # total buffer size
                elements.ctypes.data_as(ctypes.POINTER(GL.GLuint)),
                GL.GL_STATIC_DRAW)
            GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, 0)

            # factory for VAOs
            vaoId = GL.GLuint()
            GL.glGenVertexArrays(1, ctypes.byref(vaoId))
            GL.glBindVertexArray(vaoId)
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vboId)
            byte_offset = 8 * ctypes.sizeof(GL.GLfloat)  # sizeof vertex data

            # set attribute pointers to buffer data
            GL.glVertexAttribPointer(  # vertex
                0, 3, GL.GL_FLOAT, GL.GL_FALSE, byte_offset, 0)

            GL.glVertexAttribPointer(  # texture coord
                8, 2, GL.GL_FLOAT, GL.GL_FALSE, byte_offset,
                3 * ctypes.sizeof(GL.GLfloat))

            GL.glVertexAttribPointer(  # normals
                2, 3, GL.GL_FLOAT, GL.GL_FALSE, byte_offset,
                5 * ctypes.sizeof(GL.GLfloat))

            GL.glEnableVertexAttribArray(0)
            GL.glEnableVertexAttribArray(2)
            GL.glEnableVertexAttribArray(8)

            GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, eboId)  # element array
            GL.glBindVertexArray(0)

            self.objVAOs[group] = (vaoId, len(elements))

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

    def draw(self, win=None):
        """Draw the object.

        Parameters
        ----------
        win : :class:`~psychopy.visual.Window`
            The :class:`~psychopy.visual.Window` object in which the stimulus
            will be rendered to. The window must share a context with the
            window specified when instantiating the object.

        """
        if win is None:
            self.win.backend.setCurrent()
        else:
            win._setCurrent()

        self._prepareDraw()
        MVP = self.win.projectionMatrix.ctypes.data_as(ctypes.POINTER(GL.GLfloat))

        # draw the model
        for group, vao in self.objVAOs.items():

            #mvpLoc = GL.glGetUniformLocation(prog, b"MVP")

            #GL.glUseProgram(prog)
            gltools.useMaterial(self._mtllibInfo[group])
            #texId = self._mtllibInfo[group].textures[GL.GL_TEXTURE0].id
            GL.glBindVertexArray(vao[0])
            #texLoc = GL.glGetUniformLocation(prog, b"texture0")

            #GL.glUniformMatrix4fv
            #GL.glUniform1ui(texLoc, texId)
            GL.glDrawElements(GL.GL_TRIANGLES, vao[1], GL.GL_UNSIGNED_INT, None)
            GL.glBindVertexArray(0)
            #GL.glUseProgram(0)

        # disable materials
        gltools.useMaterial(None)

        self._endDraw()

