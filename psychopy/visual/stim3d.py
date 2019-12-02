#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Classes for 3D stimuli."""

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

from psychopy import logging
from psychopy.tools.attributetools import attributeSetter, setAttribute
from psychopy.visual.basevisual import WindowMixin, ColorMixin
from psychopy.visual.helpers import setColor
import psychopy.tools.mathtools as mt
import psychopy.tools.gltools as gt
import psychopy.tools.arraytools as at
import psychopy.tools.viewtools as vt
import psychopy.visual.shaders as _shaders

import os
from io import StringIO
from PIL import Image

import numpy as np
import ctypes

import pyglet.gl as GL

_GLTF_COMPONENT_TYPE_ = None
_GLTF_TYPE_SIZE_ = None

try:
    import pygltflib
    _HAS_GLTF_IMPORTER_ = True

    _GLTF_COMPONENT_TYPE_ = {
        5120: ctypes.sizeof(GL.GLbyte),  # byte
        5121: ctypes.sizeof(GL.GLubyte),  # unsigned byte
        5122: ctypes.sizeof(GL.GLshort),  # short
        5123: ctypes.sizeof(GL.GLushort),  # unsigned short
        5124: ctypes.sizeof(GL.GLuint),  # unsigned int
        5126: ctypes.sizeof(GL.GLfloat)   # float
    }

    _GLTF_TYPE_SIZE_ = {
        pygltflib.VEC2: 2,
        pygltflib.VEC3: 3,
        pygltflib.VEC4: 4,
        pygltflib.SCALAR: 1,
        pygltflib.MAT2: 4,
        pygltflib.MAT3: 9,
        pygltflib.MAT4: 16
    }

except ImportError:
    _HAS_GLTF_IMPORTER_ = False

# ------------------------------------------------------------------------------
# Cache for shaders
#
# Each shader created by a material is compiled and added to the cache, each key
# is a tuple indicating the combined shader flags and the number of lights
# associated with it. Upon creating a material, shaders for its configuration
# and range of lights are created. These are cached, so changing the number of
# lights does not require additional shaders to be compiled. If a material was
# created before another, the newest material will look into the shader cache
# for a matching configuration before creating a new one.
#

# Shader flags used to specify the configuration of a shader. This is a hashable
# value that can be used to determine what the capabilities of a shader in
# cache are. Each configuration in cache should have at least 8 possible shaders
# to use, where 8 is the maximum number of punctual lights supported.
SHADER_SPECULARGLOSSINESS = 1 << 0
SHADER_METALLICROUGHNESS = 1 << 1
SHADER_HAS_NORMALS = 1 << 2
SHADER_HAS_UV_SET1 = 1 << 3
SHADER_HAS_UV_SET2 = 1 << 4
SHADER_HAS_TANGENTS = 1 << 5
SHADER_USE_PUNCTUAL = 1 << 6
SHADER_HAS_NORMAL_MAP = 1 << 7
SHADER_HAS_DIFFUSE_MAP = 1 << 8
SHADER_HAS_SPECULAR_GLOSSINESS_MAP = 1 << 9
SHADER_HAS_METALLIC_ROUGHNESS_MAP = 1 << 10
SHADER_HAS_OCCLUSION_MAP = 1 << 11
SHADER_HAS_EMISSIVE_MAP = 1 << 12
SHADER_USE_IBL = 1 << 13
SHADER_ALPHAMODE_MASK = 1 << 14
SHADER_ALPHAMODE_OPAQUE = 1 << 15
SHADER_TONEMAP_UNCHARTED = 1 << 16
SHADER_TONEMAP_HEJLRICHARD = 1 << 17
SHADER_TONEMAP_ACES = 1 << 18
SHADER_HAS_BASE_COLOR_MAP = 1 << 19
SHADER_USE_HDR = 1 << 20
SHADER_MATERIAL_UNLIT = 1 << 21

# Mapping for define statements used when building the shader. These need to be
# defined in accordance to the shader configuration flags in use when building
# the shader.
SHADER_DEFS = {
    SHADER_SPECULARGLOSSINESS: "MATERIAL_SPECULARGLOSSINESS",
    SHADER_METALLICROUGHNESS: "MATERIAL_METALLICROUGHNESS",
    SHADER_HAS_NORMALS: "HAS_NORMALS",
    SHADER_HAS_UV_SET1: "HAS_UV_SET1",
    SHADER_HAS_UV_SET2: "HAS_UV_SET2",
    SHADER_HAS_TANGENTS: "HAS_TANGENTS",
    SHADER_USE_PUNCTUAL: "USE_PUNCTUAL",
    SHADER_HAS_DIFFUSE_MAP: "HAS_DIFFUSE_MAP",
    SHADER_HAS_BASE_COLOR_MAP: "HAS_BASE_COLOR_MAP",
    SHADER_HAS_SPECULAR_GLOSSINESS_MAP: "HAS_SPECULAR_GLOSSINESS_MAP",
    SHADER_HAS_METALLIC_ROUGHNESS_MAP: "HAS_METALLIC_ROUGHNESS_MAP",
    SHADER_HAS_OCCLUSION_MAP: "HAS_OCCLUSION_MAP",
    SHADER_HAS_EMISSIVE_MAP: "HAS_EMISSIVE_MAP",
    SHADER_USE_IBL: "USE_IBL",
    SHADER_ALPHAMODE_MASK: "ALPHAMODE_MASK",
    SHADER_ALPHAMODE_OPAQUE: "ALPHAMODE_OPAQUE",
    SHADER_TONEMAP_UNCHARTED: "TONEMAP_UNCHARTED",
    SHADER_TONEMAP_HEJLRICHARD: "TONEMAP_HEJLRICHARD",
    SHADER_TONEMAP_ACES: "TONEMAP_ACES",
    SHADER_USE_HDR: "USE_HDR",
    SHADER_MATERIAL_UNLIT: "MATERIAL_UNLIT",
    SHADER_HAS_NORMAL_MAP: "HAS_NORMAL_MAP"}


# Shader GLSL source code, individual materials will use this source and
# generate the appropriate shader by setting #DEFINE flags
includes = [r'psychopy\visual\shaders\tonemapping.glsl',
            r'psychopy\visual\shaders\textures.glsl',
            r'psychopy\visual\shaders\functions.glsl',
            r'psychopy\visual\shaders\animation.glsl']

with open(r'psychopy\visual\shaders\metallic-roughness.frag', 'r') as f:
    GLSL_KHRONOS_PBR_FRAG = gt.embedShaderIncludes(f.read(), includes)

with open(r'psychopy\visual\shaders\primitive.vert', 'r') as f:
    GLSL_KHRONOS_PBR_VERT = gt.embedShaderIncludes(f.read(), includes)

# the shader cache
_SHADER_CACHE_ = {}

# cache light uniform strings
_SHADER_LIGHT_UNIFORMS_ = {}
for i in range(8):
    structField = b'u_Lights[' + str(i).encode() + b'].'
    _SHADER_LIGHT_UNIFORMS_[i] = (
        structField + b'direction',
        structField + b'range',
        structField + b'color',
        structField + b'intensity',
        structField + b'position',
        structField + b'innerConeCos',
        structField + b'outerConeCos',
        structField + b'type')


def cacheShaderPBR(flags, nLights=8):
    """Create an appropriate PBR shader for the provided material configuration
    flags and cache it.

    A shader is generated for the specified configuration and a given number of
    lights. This prevents needing to cache a new shader if the number of lights
    changes. This also includes a shader if no lights are being used.

    Parameters
    ----------
    flags : int
        Shader configuration flags.
    nLights : int
        Number of punctual lights to cache for the given configuration. This
        also includes the `unlit` configuration if no lights are available.

    """
    # shader #DEFINE statements to embed, punctual lighting is ALWAYS used
    shaderDefs = {}
    for key, val in SHADER_DEFS.items():
        if (flags & key) == key:
            shaderDefs[val] = 1

    global _SHADER_CACHE_
    # compile a shader for each number of lights
    for lightIdx in range(0, nLights):  # max lights allowed are 8
        # generate a hashable key for the shader cache
        shaderKey = (flags, lightIdx)

        # check if a shader of this configuration has been cached already
        if _SHADER_CACHE_.get(shaderKey, False):
            continue

        # the shader is not in cache, build it ...
        shaderProg = gt.createProgram()

        # no lights, unlit condition just shows base color only
        if lightIdx == 0:
            fragShaderSrc = gt.embedShaderSourceDefs(
                GLSL_KHRONOS_PBR_FRAG, {'MATERIAL_UNLIT': 1})
            fragShaderSrc = gt.embedShaderSourceDefs(
                fragShaderSrc, shaderDefs)
        else:
            shaderDefs[SHADER_DEFS[SHADER_USE_PUNCTUAL]] = 1
            fragShaderSrc = gt.embedShaderSourceDefs(
                GLSL_KHRONOS_PBR_FRAG, {'LIGHT_COUNT': lightIdx})

        vertShaderSrc = gt.embedShaderSourceDefs(
            GLSL_KHRONOS_PBR_VERT, shaderDefs)
        fragShaderSrc = gt.embedShaderSourceDefs(fragShaderSrc, shaderDefs)

        # compile them
        vertShader = gt.compileShader(vertShaderSrc, GL.GL_VERTEX_SHADER)
        fragShader = gt.compileShader(fragShaderSrc, GL.GL_FRAGMENT_SHADER)

        # attach shaders to program
        gt.attachShader(shaderProg, vertShader)
        gt.attachShader(shaderProg, fragShader)

        # link the shader
        gt.linkProgram(shaderProg)

        # optional, validate the program
        # gt.validateProgram(shaderProg)

        # optional, detach and discard shader objects
        gt.detachShader(shaderProg, vertShader)
        gt.detachShader(shaderProg, fragShader)
        gt.deleteObject(vertShader)
        gt.deleteObject(fragShader)

        # get and cache uniform locations within the shader
        unifLoc = gt.getUniformLocations(shaderProg)

        # add to shader cache
        _SHADER_CACHE_[shaderKey] = (shaderProg, unifLoc)


# BRDF LUT that ships with the shader
GLTF2_BRDF_LUT = gt.createTexImage2dFromFile(r'psychopy\visual\shaders\brdfLUT.png')

# ------------------------------------------------------------------------------
# Mesh configuration

# These flags are used to determine what buffers are in use by a given mesh
# stimulus.
MESH_HAS_POSITION = 1 << 0
MESH_HAS_NORMALS = 1 << 1
MESH_HAS_TANGENTS = 1 << 2
MESH_HAS_UV_SET1 = 1 << 3
MESH_HAS_UV_SET2 = 1 << 4
MESH_HAS_INDICES = 1 << 5


class LightSource(object):
    """Class for representing a light source in a scene.

    Only point and directional lighting is supported by this object for now. The
    ambient color of the light source contributes to the scene ambient color
    defined by :py:attr:`~psychopy.visual.Window.ambientLight`.

    Warnings
    --------
    This class is experimental and may result in undefined behavior.

    """
    def __init__(self,
                 win,
                 pos=(0., 0., 0.),
                 direction=(0., -1., 0.),
                 color=(1., 1., 1.),
                 colorSpace='rgb',
                 intensity=1.0,
                 maxDist=10.0,
                 lightType='point',
                 innerConeCos=0.0,
                 outerConeCos=0.1):
        """
        Parameters
        ----------
        win : `~psychopy.visual.Window`
            Window associated with this light source.
        pos : array_like
            Position of the light source (x, y, z).
        direction : array_like
            Direction of the lights source as vector (x, y, z). Should be
            normalized. Only applicable for 'spot' and 'directional'
            `lightTypes`.
        color : array_like
            Light color in linear space.
        colorSpace : str
            Colorspace for `color`.
        intensity : float
            Intensity or brightness of the light source. For point and spot
            lights intensity is in candelas (lm/sr) while directional lights use
            lux (lm/m^2).
        maxDist : float
            Distance from light source in meters where it can be considered near
            to have reached zero. Distance should always be >0.
        lightType : str
            Light source type. Valid values are 'point', 'directional', and
            'spot'.

        """
        self.win = win

        self._pos = np.zeros((3,), np.float32)
        self._dir = np.zeros((3,), np.float32)
        self._color = np.zeros((3,), np.float32)
        self._maxDist = 0.0
        self._intensity = 0.0

        self._innerConeCos = innerConeCos
        self._outerConeCos = outerConeCos

        # internal RGB values post colorspace conversion
        self._colorRGB = np.array((0., 0., 0., 1.), np.float32)

        self.colorSpace = colorSpace
        self.color = color

        self._lightType = 0
        self.lightType = lightType
        self.pos = pos
        self.direction = direction
        self.intensity = intensity
        self.maxDist = maxDist

    @property
    def pos(self):
        """Position of the light source in the scene in scene units."""
        return self._pos

    @pos.setter
    def pos(self, value):
        self._pos[:] = value

    @property
    def direction(self):
        """Direction vector of a light source."""
        return self._dir

    @direction.setter
    def direction(self, value):
        self._dir[:] = value

    @property
    def intensity(self):
        """Intensity or brightness of the light source. For point and spot
        lights intensity is in candelas (lm/sr) while directional lights use
        lux (lm/m^2).
        """
        return self._intensity

    @intensity.setter
    def intensity(self, value):
        self._intensity = value

    @property
    def maxDist(self):
        """Maximum distance cut-off of a light source."""
        return self._maxDist

    @maxDist.setter
    def maxDist(self, value):
        self._maxDist = value

    @property
    def lightType(self):
        """Type of light source, can be 'point', 'directional' or 'spot'."""
        if self._lightType == 0:
            return 'directional'
        elif self._lightType == 1:
            return 'point'
        else:
            return 'spot'

    @lightType.setter
    def lightType(self, value):
        if value == 'directional':
            self._lightType = 0
        elif value == 'point':
            self._lightType = 1
        elif value == 'spot':
            self._lightType = 2
        else:
            raise ValueError(
                "Unknown `lightType` specified, must be 'directional', "
                "'point' or 'spot'.")

    @property
    def color(self):
        """Diffuse color of the material."""
        return self._color

    @color.setter
    def color(self, value):
        self._color = np.asarray(value, np.float32)
        setColor(self, value, colorSpace=self.colorSpace, operation=None,
                 rgbAttrib='colorRGB', colorAttrib='color',
                 colorSpaceAttrib='colorSpace')

    @property
    def colorRGB(self):
        """Diffuse color of the material."""
        return self._colorRGB[:3]

    @colorRGB.setter
    def colorRGB(self, value):
        # make sure the color we got is 32-bit float
        self._colorRGB = np.zeros((4,), np.float32)
        self._colorRGB[:3] = (value + 1) / 2.0
        self._colorRGB[3] = 1.0


class SceneSkybox(object):
    """Class to render scene skyboxes.

    A skybox provides background imagery to serve as a visual reference for the
    scene. Background images are projected onto faces of a cube centered about
    the viewpoint regardless of any viewpoint translations, giving the illusion
    that the background is very far away. Usually, only one skybox can be
    rendered per buffer each frame. Render targets must have a depth buffer
    associated with them.

    Background images are specified as a set of image paths passed to
    `faceTextures`::

        sky = SceneSkybox(
            win, ('rt.jpg', 'lf.jpg', 'up.jpg', 'dn.jpg', 'bk.jpg', 'ft.jpg'))

    The skybox is rendered by calling `draw()` after drawing all other 3D
    stimuli.

    Skyboxes are not affected by lighting, however, their colors can be
    modulated by setting the window's `sceneAmbient` value. Skyboxes should be
    drawn after all other 3D stimuli, but before any successive call that clears
    the depth buffer (eg. `setPerspectiveView`, `resetEyeTransform`, etc.)


    """
    def __init__(self, win, tex=(), ori=0.0, axis=(0, 1, 0)):
        """
        Parameters
        ----------
        win : `~psychopy.visual.Window`
            Window this skybox is associated with.
        tex : list or tuple or TexCubeMap
            List of files paths to images to use for each face. Images are
            assigned to faces depending on their index within the list ([+X,
            -X, +Y, -Y, +Z, -Z] or [right, left, top, bottom, back, front]). If
            `None` is specified, the cube map may be specified later by setting
            the `cubemap` attribute. Alternatively, you can specify a
            `TexCubeMap` object to set the cube map directly.
        ori : float
            Rotation of the skybox about `axis` in degrees.
        axis : array_like
            Axis [ax, ay, az] to rotate about, default is (0, 1, 0).

        """
        self.win = win

        self._ori = ori
        self._axis = np.ascontiguousarray(axis, dtype=np.float32)

        if tex:
            if isinstance(tex, (list, tuple,)):
                if len(tex) == 6:
                    imgFace = []
                    for img in tex:
                        im = Image.open(img)
                        im = im.convert("RGBA")
                        pixelData = np.array(im).ctypes
                        imgFace.append(pixelData)

                    width = imgFace[0].shape[1]
                    height = imgFace[0].shape[0]

                    self._skyCubemap = gt.createCubeMap(
                        width,
                        height,
                        internalFormat=GL.GL_RGBA,
                        pixelFormat=GL.GL_RGBA,
                        dataType=GL.GL_UNSIGNED_BYTE,
                        data=imgFace,
                        unpackAlignment=1,
                        texParams={
                            GL.GL_TEXTURE_MAG_FILTER: GL.GL_LINEAR,
                            GL.GL_TEXTURE_MIN_FILTER: GL.GL_LINEAR,
                            GL.GL_TEXTURE_WRAP_S: GL.GL_CLAMP_TO_EDGE,
                            GL.GL_TEXTURE_WRAP_T: GL.GL_CLAMP_TO_EDGE,
                            GL.GL_TEXTURE_WRAP_R: GL.GL_CLAMP_TO_EDGE})
                else:
                   raise ValueError("Not enough textures specified, must be 6.")
            elif isinstance(tex, gt.TexCubeMap):
                self._skyCubemap = tex
            else:
                raise TypeError("Invalid type specified to `tex`.")
        else:
            self._skyCubemap = None

        # create cube vertices and faces, discard texcoords and normals
        vertices, _, _, faces = gt.createBox(1.0, True)

        # upload to buffers
        vertexVBO = gt.createVBO(vertices)

        # create an index buffer with faces
        indexBuffer = gt.createVBO(
            faces.flatten(),
            target=GL.GL_ELEMENT_ARRAY_BUFFER,
            dataType=GL.GL_UNSIGNED_SHORT)

        # create the VAO for drawing
        self._vao = gt.createVAO(
            {GL.GL_VERTEX_ARRAY: vertexVBO},
            indexBuffer=indexBuffer,
            legacy=True)

        # shader for the skybox
        self._shaderProg = _shaders.compileProgram(
            _shaders.vertSkyBox, _shaders.fragSkyBox)

        # store the skybox transformation matrix, this is not to be updated
        # externally
        self._skyboxViewMatrix = np.identity(4, dtype=np.float32)
        self._prtSkyboxMatrix = at.array2pointer(self._skyboxViewMatrix)

    @property
    def skyCubeMap(self):
        """Cubemap for the sky."""
        return self._skyCubemap

    @skyCubeMap.setter
    def skyCubeMap(self, value):
        self._skyCubemap = value

    def draw(self, win=None):
        """Draw the skybox.

        This should be called last after drawing other 3D stimuli for
        performance reasons.

        Parameters
        ----------
        win : `~psychopy.visual.Window`, optional
            Window to draw the skybox to. If `None`, the window set when
            initializing this object will be used. The window must share a
            context with the window which this objects was initialized with.

        """
        if self._skyCubemap is None:  # nop if no cubemap is assigned
            return

        if win is None:
            win = self.win
        else:
            win._makeCurrent()

        # enable 3D drawing
        win.draw3d = True

        # do transformations
        GL.glPushMatrix()
        GL.glLoadIdentity()

        # rotate the skybox if needed
        if self._ori != 0.0:
            GL.glRotatef(self._ori, *self._axis)

        # get/set the rotation sub-matrix from the current view matrix
        self._skyboxViewMatrix[:3, :3] = win.viewMatrix[:3, :3]
        GL.glMultTransposeMatrixf(self._prtSkyboxMatrix)

        # use the shader program
        gt.useProgram(self._shaderProg)

        # enable texture sampler
        GL.glEnable(GL.GL_TEXTURE_2D)
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_CUBE_MAP, self._skyCubemap.name)

        # draw the cube VAO
        oldDepthFunc = win.depthFunc
        win.depthFunc = 'lequal'  # optimized for being drawn last
        gt.drawVAO(self._vao, GL.GL_TRIANGLES)
        win.depthFunc = oldDepthFunc
        gt.useProgram(0)

        # disable sampler
        GL.glBindTexture(GL.GL_TEXTURE_CUBE_MAP, 0)
        GL.glDisable(GL.GL_TEXTURE_2D)

        # return to previous transformation
        GL.glPopMatrix()

        # disable 3D drawing
        win.draw3d = False


class BlinnPhongMaterial(object):
    """Class representing a material using the Blinn-Phong lighting model.

    This class stores material information to modify the appearance of drawn
    primitives with respect to lighting, such as color (diffuse, specular,
    ambient, and emission), shininess, and textures. Simple materials are
    intended to work with features supported by the fixed-function OpenGL
    pipeline.

    If shaders are enabled, the colors of objects will appear different than
    without. This is due to the lighting/material colors being computed on a
    per-pixel basis, and the formulation of the lighting model. The Phong shader
    determines the ambient color/intensity by adding up both the scene and light
    ambient colors, then multiplies them by the diffuse color of the
    material, as the ambient light's color should be a product of the surface
    reflectance (albedo) and the light color (the ambient light needs to reflect
    off something to be visible). Diffuse reflectance is Lambertian, where the
    cosine angle between the incident light ray and surface normal determines
    color. The size of specular highlights are related to the `shininess` factor
    which ranges from 1.0 to 128.0. The greater this number, the tighter the
    specular highlight making the surface appear smoother. If shaders are not
    being used, specular highlights will be computed using the Phong lighting
    model. The emission color is optional, it simply adds to the color of every
    pixel much like ambient lighting does. Usually, you would not really want
    this, but it can be used to add bias to the overall color of the shape.

    If there are no lights in the scene, the diffuse color is simply multiplied
    by the scene and material ambient color to give the final color.

    Lights are attenuated (fall-off with distance) using the formula::

        attenuationFactor = 1.0 / (k0 + k1 * distance + k2 * pow(distance, 2))

    The coefficients for attenuation can be specified by setting `attenuation`
    in the lighting object. Values `k0=1.0, k1=0.0, and k2=0.0` results in a
    light that does not fall-off with distance.

    Warnings
    --------
    This class is experimental and may result in undefined behavior.

    """
    def __init__(self,
                 win=None,
                 diffuseColor=(.5, .5, .5),
                 specularColor=(-1., -1., -1.),
                 ambientColor=(-1., -1., -1.),
                 emissionColor=(-1., -1., -1.),
                 shininess=10.0,
                 colorSpace='rgb',
                 diffuseTexture=None,
                 opacity=1.0,
                 contrast=1.0,
                 face='front'):
        """
        Parameters
        ----------
        win : `~psychopy.visual.Window` or `None`
            Window this material is associated with, required for shaders and
            some color space conversions.
        diffuseColor : array_like
            Diffuse material color (r, g, b, a) with values between 0.0 and 1.0.
        specularColor : array_like
            Specular material color (r, g, b, a) with values between 0.0 and
            1.0.
        ambientColor : array_like
            Ambient material color (r, g, b, a) with values between 0.0 and 1.0.
        emissionColor : array_like
            Emission material color (r, g, b, a) with values between 0.0 and
            1.0.
        shininess : float
            Material shininess, usually ranges from 0.0 to 128.0.
        colorSpace : float
            Color space for `diffuseColor`, `specularColor`, `ambientColor`, and
            `emissionColor`.
        diffuseTexture : TexImage2D
        opacity : float
            Opacity of the material. Ranges from 0.0 to 1.0 where 1.0 is fully
            opaque.
        contrast : float
            Contrast of the material colors.
        face : str
            Face to apply material to. Values are `front`, `back` or `both`.
        textures : dict, optional
            Texture maps associated with this material. Textures are specified
            as a list. The index of textures in the list will be used to set
            the corresponding texture unit they are bound to.
        """
        self.win = win

        self._diffuseColor = np.zeros((3,), np.float32)
        self._specularColor = np.zeros((3,), np.float32)
        self._ambientColor = np.zeros((3,), np.float32)
        self._emissionColor = np.zeros((3,), np.float32)
        self._shininess = float(shininess)

        # internal RGB values post colorspace conversion
        self._diffuseRGB = np.array((0., 0., 0., 1.), np.float32)
        self._specularRGB = np.array((0., 0., 0., 1.), np.float32)
        self._ambientRGB = np.array((0., 0., 0., 1.), np.float32)
        self._emissionRGB = np.array((0., 0., 0., 1.), np.float32)

        # internal pointers to arrays, initialized below
        self._ptrDiffuse = None
        self._ptrSpecular = None
        self._ptrAmbient = None
        self._ptrEmission = None

        # which faces to apply the material
        if face == 'front':
            self._face = GL.GL_FRONT
        elif face == 'back':
            self._face = GL.GL_BACK
        elif face == 'both':
            self._face = GL.GL_FRONT_AND_BACK
        else:
            raise ValueError("Invalid `face` specified, must be 'front', "
                             "'back' or 'both'.")

        self.colorSpace = colorSpace
        self.opacity = opacity
        self.contrast = contrast

        self.diffuseColor = diffuseColor
        self.specularColor = specularColor
        self.ambientColor = ambientColor
        self.emissionColor = emissionColor

        self._diffuseTexture = diffuseTexture
        self._normalTexture = None

        self._useTextures = False  # keeps track if textures are being used
        self._useShaders = False

    @property
    def diffuseTexture(self):
        """Diffuse color of the material."""
        return self._diffuseTexture

    @diffuseTexture.setter
    def diffuseTexture(self, value):
        self._diffuseTexture = value

    @property
    def diffuseColor(self):
        """Diffuse color of the material."""
        return self._diffuseColor

    @diffuseColor.setter
    def diffuseColor(self, value):
        self._diffuseColor = np.asarray(value, np.float32)
        setColor(self, value, colorSpace=self.colorSpace, operation=None,
                 rgbAttrib='diffuseRGB', colorAttrib='diffuseColor',
                 colorSpaceAttrib='colorSpace')

    @property
    def diffuseRGB(self):
        """Diffuse color of the material."""
        return self._diffuseRGB[:3]

    @diffuseRGB.setter
    def diffuseRGB(self, value):
        # make sure the color we got is 32-bit float
        self._diffuseRGB = np.zeros((4,), np.float32)
        self._diffuseRGB[:3] = (value * self.contrast + 1) / 2.0
        self._diffuseRGB[3] = self.opacity

        self._ptrDiffuse = np.ctypeslib.as_ctypes(self._diffuseRGB)

    @property
    def specularColor(self):
        """Specular color of the material."""
        return self._specularColor

    @specularColor.setter
    def specularColor(self, value):
        self._specularColor = np.asarray(value, np.float32)
        setColor(self, value, colorSpace=self.colorSpace, operation=None,
                 rgbAttrib='specularRGB', colorAttrib='specularColor',
                 colorSpaceAttrib='colorSpace')

    @property
    def specularRGB(self):
        """Diffuse color of the material."""
        return self._specularRGB[:3]

    @specularRGB.setter
    def specularRGB(self, value):
        # make sure the color we got is 32-bit float
        self._specularRGB = np.zeros((4,), np.float32)
        self._specularRGB[:3] = (value * self.contrast + 1) / 2.0
        self._specularRGB[3] = self.opacity

        self._ptrSpecular = np.ctypeslib.as_ctypes(self._specularRGB)

    @property
    def ambientColor(self):
        """Ambient color of the material."""
        return self._ambientColor

    @ambientColor.setter
    def ambientColor(self, value):
        self._ambientColor = np.asarray(value, np.float32)
        setColor(self, value, colorSpace=self.colorSpace, operation=None,
                 rgbAttrib='ambientRGB', colorAttrib='ambientColor',
                 colorSpaceAttrib='colorSpace')

    @property
    def ambientRGB(self):
        """Diffuse color of the material."""
        return self._ambientRGB[:3]

    @ambientRGB.setter
    def ambientRGB(self, value):
        # make sure the color we got is 32-bit float
        self._ambientRGB = np.zeros((4,), np.float32)
        self._ambientRGB[:3] = (value * self.contrast + 1) / 2.0
        self._ambientRGB[3] = self.opacity

        self._ptrAmbient = np.ctypeslib.as_ctypes(self._ambientRGB)

    @property
    def emissionColor(self):
        """Emission color of the material."""
        return self._emissionColor

    @emissionColor.setter
    def emissionColor(self, value):
        self._emissionColor = np.asarray(value, np.float32)
        setColor(self, value, colorSpace=self.colorSpace, operation=None,
                 rgbAttrib='emissionRGB', colorAttrib='emissionColor',
                 colorSpaceAttrib='colorSpace')

    @property
    def emissionRGB(self):
        """Diffuse color of the material."""
        return self._emissionRGB[:3]

    @emissionRGB.setter
    def emissionRGB(self, value):
        # make sure the color we got is 32-bit float
        self._emissionRGB = np.zeros((4,), np.float32)
        self._emissionRGB[:3] = (value * self.contrast + 1) / 2.0
        self._emissionRGB[3] = self.opacity

        self._ptrEmission = np.ctypeslib.as_ctypes(self._emissionRGB)

    @property
    def shininess(self):
        return self._shininess

    @shininess.setter
    def shininess(self, value):
        self._shininess = float(value)

    def begin(self, useTextures=True, useShaders=False):
        """Use this material for successive rendering calls.

        Parameters
        ----------
        useTextures : bool
            Enable textures.

        """
        GL.glDisable(GL.GL_COLOR_MATERIAL)  # disable color tracking
        face = self._face

        if useShaders:
            # number of scene lights
            self._useShaders = True
            nLights = len(self.win.lights)
            useTextures = useTextures and self.diffuseTexture is not None
            shaderKey = (nLights, useTextures)
            gt.useProgram(self.win._shaders['stim3d_phong'][shaderKey])

        # pass values to OpenGL
        GL.glMaterialfv(face, GL.GL_DIFFUSE, self._ptrDiffuse)
        GL.glMaterialfv(face, GL.GL_SPECULAR, self._ptrSpecular)
        GL.glMaterialfv(face, GL.GL_AMBIENT, self._ptrAmbient)
        GL.glMaterialfv(face, GL.GL_EMISSION, self._ptrEmission)
        GL.glMaterialf(face, GL.GL_SHININESS, self.shininess)

        # setup textures
        if useTextures and self.diffuseTexture is not None:
            self._useTextures = True
            GL.glEnable(GL.GL_TEXTURE_2D)
            gt.bindTexture(self.diffuseTexture, 0)

    def end(self, clear=True):
        """Stop using this material.

        Must be called after `begin` before using another material or else later
        drawing operations may have undefined behavior.

        Upon returning, `GL_COLOR_MATERIAL` is enabled so material colors will
        track the current `glColor`.

        Parameters
        ----------
        clear : bool
            Overwrite material state settings with default values. This
            ensures material colors are set to OpenGL defaults. You can forgo
            clearing if successive materials are used which overwrite
            `glMaterialfv` values for `GL_DIFFUSE`, `GL_SPECULAR`, `GL_AMBIENT`,
            `GL_EMISSION`, and `GL_SHININESS`. This reduces a bit of overhead
            if there is no need to return to default values intermittently
            between successive material `begin` and `end` calls. Textures and
            shaders previously enabled will still be disabled.

        """
        if clear:
            GL.glMaterialfv(
                self._face,
                GL.GL_DIFFUSE,
                (GL.GLfloat * 4)(0.8, 0.8, 0.8, 1.0))
            GL.glMaterialfv(
                self._face,
                GL.GL_SPECULAR,
                (GL.GLfloat * 4)(0.0, 0.0, 0.0, 1.0))
            GL.glMaterialfv(
                self._face,
                GL.GL_AMBIENT,
                (GL.GLfloat * 4)(0.2, 0.2, 0.2, 1.0))
            GL.glMaterialfv(
                self._face,
                GL.GL_EMISSION,
                (GL.GLfloat * 4)(0.0, 0.0, 0.0, 1.0))
            GL.glMaterialf(self._face, GL.GL_SHININESS, 0.0)

        if self._useTextures:
            self._useTextures = False
            gt.unbindTexture(self.diffuseTexture)
            GL.glDisable(GL.GL_TEXTURE_2D)

        if self._useShaders:
            gt.useProgram(0)
            self._useShaders = False

        GL.glEnable(GL.GL_COLOR_MATERIAL)


class MetallicRoughnessMaterial(object):
    """Class for materials using Physically-Based Rendering (PBR) of microfacet
    surfaces.

    The shader used here is the reference implementation for Physically Based
    Shading of a microfacet surface material.

    The appearance of a material will be determined by `roughness` or scattering
    of incident light due to micro-facets on the surface and `metallic` which
    represents the dielectric property of the material.
    """
    def __init__(self,
                 win=None,
                 color=(0, 0, 0),
                 colorSpace='rgb',
                 colorTexture=None,
                 metallicRoughnessTexture=None,
                 roughnessFactor=0.0,
                 metallicFactor=0.0,
                 normalTexture=None,
                 normalFactor=1.0,
                 occulusionTexture=None,
                 occulusionStrength=1.0,
                 emissiveTexture=None,
                 emissiveFactor=(1., 1., 1.),
                 diffuseIBL=None,
                 alphaMode=None,
                 alphaCutoff=1.0,
                 toneMap=None,
                 hdr=False,
                 unlit=False,
                 meshFlags=MESH_HAS_POSITION | MESH_HAS_NORMALS):
        """
        Parameters
        ----------
        win : `~psychopy.visual.Window`
            Window associated with this material.
        color : array_like
            Base color for the material.
        colorSpace : str
            Colorspace of `color`.
        colorTexture : `~psychopy.tools.gltools.TexImage2D`
            Color texture to use for diffuse reflectance.
        roughnessFactor : float
            Roughness gain factor between 0.0 and 1.0.
        metallicFactor : float
            Metallic gain factor between 0.0 and 1.0.
        metallicRoughnessTexture : `~psychopy.tools.gltools.TexImage2D`
            Texture for metallic and roughness. Metallic information is stored
            on the red and roughness on the green color channel of this texture.
        normalTexture : `~psychopy.tools.gltools.TexImage2D`
            Normal map for the material in tangent space.
        normalFactor : float
            Gain factor for normal map, can range between -1.0 and 1.0. Only
            applicable if the target object has tangents.
        normalUVSet : int
            UV texture coordinate set to use when sampling the normal map. Can
            be 0 or 1.
        occlusionTexture : `~psychopy.tools.gltools.TexImage2D`
            Ambient occlusion texture map.
        occlusionStrength : float
            Gain factor for the ambient occlusion map, can range between 0.0
            and 1.0.
        occlusionUVSet : int
            UV texture coordinate set to use when sampling the occusion map. Can
            be 0 or 1.
        emissiveTexture : `~psychopy.tools.gltools.TexImage2D`
            Texture map for emmision.
        emissiveFactor : array_like
            Emmission strength for each color channel of the emmision map.
        diffuseIBL : `~psychopy.tools.gltools.TexCumeMap`
            Cubemap for the diffuse component of Image Based Lighting (IBL) or
            diffuse irradiance from the environment.
        alphaMode : str
            Alpha mode to use, possible values are 'opaque', 'mask' and 'blend'.
        alphaCutoff : float
            Cut-off alpha value from the color texture to reject a fragment if
            `alphaMode` is 'mask'. All fragments with an alpha value less than
            this will be rejected.
        toneMap : str or None
            Tonemapping function to use. If `None`, no tonemapping will be
            applied.
        hdr : bool
            Enable HDR mode. If `True`, the resulting color values will be
            output as-is in linear RGB without gamma correction. If `False`,
            the material will be rendered with sRGB gamma correction applied
            to it's colors.
        unlit : bool
            If `False` shading of this object is disabled.
        meshFlags : int
            Flags indicating the available attributes associated with the mesh.
            By default, it is assumed the mesh has attribute buffers for
            position and normals. Values for this field are created by combining
            multiple values using an OR operation.

        """
        self.win = win
        self._meshFlags = meshFlags

        # set colors
        self._color = np.zeros((3,), np.float32)
        self._colorTexture = colorTexture

        # internal RGB values post colorspace conversion
        self._colorRGB = np.array((0., 0., 0., 1.), np.float32)
        self._ptrColor = None

        self.colorSpace = colorSpace
        self.color = color

        self.diffuseIBL = diffuseIBL

        self._roughnessFactor = float(roughnessFactor)
        self._metallicFactor = float(metallicFactor)

         # textures
        self._metallicRoughnessTexture = metallicRoughnessTexture
        self._normalTexture = normalTexture
        self._occlusionTexture = occulusionTexture
        self._emissiveTexture = emissiveTexture
        self._emissiveFactor = emissiveFactor

        # indirect lighting cubemap
        self._IBLMap = None

        self._exposure = 1.0
        self._useToneMap = toneMap
        self._useHDR = hdr

        # setup the shader
        self._shaderConfig = self._generateConfigFlags()
        cacheShaderPBR(self._shaderConfig)

        # Keep track of the presently active shader, these are not None only
        # between `begin` and `end calls. If these values are None, you can
        # assume that the material is not in use.
        self._activeShader = None
        self._activeUnifLoc = None

        # Cache uniform locations for punctual lights so we dont need to splice
        # byte strings during the rendering loop.
        self._shaderLightUnifs = {}
        for i in range(8):
            structField = b'u_Lights[' + str(i).encode() + b'].'
            self._shaderLightUnifs[i] = (
                structField + b'direction',
                structField + b'range',
                structField + b'color',
                structField + b'intensity',
                structField + b'position',
                structField + b'innerConeCos',
                structField + b'outerConeCos',
                structField + b'type')

        # Number of active samplers, this tells us how many samplers are active
        # after `begin` is called. When `end` is called, we loop over the number
        # of active samplers and disable them. This number is non-zero only
        # after begin is called and textures are assigned.
        self._nActiveSamplers = 0

        # use lights
        self._useLights = False

    @property
    def color(self):
        """Diffuse color of the material."""
        return self._diffuseColor

    @color.setter
    def color(self, value):
        self._diffuseColor = np.asarray(value, np.float32)
        setColor(self, value, colorSpace=self.colorSpace, operation=None,
                 rgbAttrib='colorRGB', colorAttrib='color',
                 colorSpaceAttrib='colorSpace')

    @property
    def colorRGB(self):
        """Diffuse color of the material."""
        return self._colorRGB[:3]

    @colorRGB.setter
    def colorRGB(self, value):
        # make sure the color we got is 32-bit float
        self._colorRGB = np.zeros((4,), np.float32)
        self._colorRGB[:3] = (value + 1) / 2.0
        self._colorRGB[3] = 1.0

        self._ptrColor = np.ctypeslib.as_ctypes(self._colorRGB)

    @property
    def colorTexture(self):
        """Diffuse color of the material."""
        return self._colorTexture

    @colorTexture.setter
    def colorTexture(self, value):
        self._colorTexture = value

    @property
    def normalTexture(self):
        """Normal map color of the material."""
        return self._normalTexture

    @normalTexture.setter
    def normalTexture(self, value):
        self._normalTexture = value

    @property
    def roughnessFactor(self):
        """Surface roughness for the material."""
        return self._roughnessFactor

    @roughnessFactor.setter
    def roughnessFactor(self, value):
        self._roughnessFactor = float(value)

    def _generateConfigFlags(self):
        """Generate shader flags from the current material settings.
        """
        if (self._meshFlags & MESH_HAS_POSITION) != MESH_HAS_POSITION:
            raise ValueError("Mesh flags must have position.")

        flags = SHADER_METALLICROUGHNESS

        if (self._meshFlags & MESH_HAS_UV_SET1) == MESH_HAS_UV_SET1:
            flags |= SHADER_HAS_UV_SET1

        if (self._meshFlags & MESH_HAS_UV_SET2) == MESH_HAS_UV_SET2:
            flags |= SHADER_HAS_UV_SET2

        if (self._meshFlags & MESH_HAS_NORMALS) == MESH_HAS_NORMALS:
            flags |= SHADER_HAS_NORMALS

        if (self._meshFlags & MESH_HAS_TANGENTS) == MESH_HAS_TANGENTS:
            flags |= SHADER_HAS_TANGENTS

            # can't use these with our shader unless you have tangents
            if self._normalTexture is not None:
                flags |= SHADER_HAS_NORMAL_MAP

        if self._metallicRoughnessTexture is not None:
            flags |= SHADER_HAS_METALLIC_ROUGHNESS_MAP

        if self._colorTexture is not None:
            flags |= SHADER_HAS_BASE_COLOR_MAP

        if self._emissiveTexture is not None:
            flags |= SHADER_HAS_EMISSIVE_MAP

        if self._occlusionTexture is not None:
            flags |= SHADER_HAS_OCCLUSION_MAP

        if self._useHDR:
            flags |= SHADER_USE_HDR

        if self.diffuseIBL:
            flags |= SHADER_USE_IBL

        # tone mapping, optional
        if self._useToneMap is not None:
            if self._useToneMap == 'aces':
                toneMap = SHADER_TONEMAP_ACES
            elif self._useToneMap == 'uncharted':
                toneMap = SHADER_TONEMAP_UNCHARTED
            elif self._useToneMap == 'hejlrichard':
                toneMap = SHADER_TONEMAP_HEJLRICHARD
            else:
                raise ValueError(
                    'Invalid tone map `{}` specified.'.format(self._useToneMap))

            flags |= toneMap

        return flags

    def use(self, mesh):
        """Use this material to render a stimulus."""
        pass

    def begin(self, modelMatrix):
        """Use this material for successive rendering calls.

        The material shader is installed and configured upon calling this
        function. Successive primitive drawing operations will be affected by
        the shader. If the material has textures, they will be bound to
        sequential texture units.

        You must call the `end()` method after the material is no longer
        needed.

        Parameters
        ----------
        modelMatrix : array_like
            4x4 model matrix associated with the mesh. This is required to
            transform the model within the shader.

        """
        # create pointers to model and normal matrix
        modelMatrix = np.asarray(modelMatrix, dtype=np.float32)
        normalMatrix = at.array2pointer(
            np.transpose(np.linalg.inv(modelMatrix)))
        modelMatrix = at.array2pointer(modelMatrix)
        viewProjectionMatrix = at.array2pointer(self.win._viewProjectionMatrix)

        # get the key to access the shader in cache
        self._useLights = len(self.win.lights) > 0

        # generate the key to access the shader in cache
        shaderKey = (self._shaderConfig, len(self.win.lights))

        # set the active shader and uniform locations
        self._activeShader, self._unifLoc = _SHADER_CACHE_[shaderKey]

        # install the shader program
        gt.useProgram(self._activeShader)

        # set matrices, if unlit the normal matrix does not need to be set
        GL.glUniformMatrix4fv(
            self._unifLoc[b'u_ViewProjectionMatrix'], 1, GL.GL_TRUE,
            viewProjectionMatrix)
        GL.glUniformMatrix4fv(
            self._unifLoc[b'u_ModelMatrix'], 1, GL.GL_TRUE, modelMatrix)

        if self._useLights:
            # iterate over all scene lights
            for idx, light in enumerate(self.win.lights):
                self._setupLight(idx, light)

            GL.glUniformMatrix4fv(self._unifLoc[b'u_NormalMatrix'],
                                  1, GL.GL_TRUE, normalMatrix)

        self._setupCamera()
        self._setupNormalSampler()
        self._setupEmissiveSampler()
        self._setupOcculusionSampler()
        self._setupBaseColorSampler()
        self._setupMetallicRoughnessSampler()
        self._setupIBL()

        if self._nActiveSamplers > 0:
            GL.glEnable(GL.GL_TEXTURE_2D)

    def end(self):
        """Stop using the material.

        Disables using the material for successive primitive draw
        operations. Any textures which were bound when `begin` was called will
        be disabled.

        """
        # uninstall the shader program
        gt.useProgram(0)

        # if there are any textures in use, disable them all
        if self._nActiveSamplers > 0:
            for i in range(self._nActiveSamplers):
                GL.glActiveTexture(GL.GL_TEXTURE0 + i)
                GL.glBindTexture(GL.GL_TEXTURE_2D, 0)

            GL.glDisable(GL.GL_TEXTURE_2D)

            self._nActiveSamplers = 0

        self._activeShader = self._unifLoc = None

    def _setupIBL(self):
        """Setup indirect lighting."""
        if not self._useLights:
            return

        if self.diffuseIBL is None:
            return

        sampler = self._nActiveSamplers
        GL.glActiveTexture(GL.GL_TEXTURE0 + sampler)
        GL.glBindTexture(GL.GL_TEXTURE_CUBE_MAP, self.diffuseIBL.name)
        GL.glUniform1i(self._unifLoc[b'u_DiffuseEnvSampler'], sampler)
        self._nActiveSamplers += 1

        sampler = self._nActiveSamplers
        GL.glActiveTexture(GL.GL_TEXTURE0 + sampler)
        GL.glBindTexture(GL.GL_TEXTURE_CUBE_MAP, self.diffuseIBL.name)
        GL.glUniform1i(self._unifLoc[b'u_SpecularEnvSampler'], sampler)
        self._nActiveSamplers += 1

        sampler = self._nActiveSamplers
        GL.glActiveTexture(GL.GL_TEXTURE0 + sampler)
        GL.glBindTexture(GL.GL_TEXTURE_2D, GLTF2_BRDF_LUT.name)
        GL.glUniform1i(self._unifLoc[b'u_brdfLUT'], sampler)
        self._nActiveSamplers += 1

    def _setupLight(self, index, light):
        """Setup a light in the shader.

        Pass lighting data to the fragment shader for use. This should only be
        called if the scene specifies at least one light, if the shader has
        `PUNCTUAL_LIGHTS` and `NUM_LIGHTS` defined, and `MATERIAL_UNLIT` is not
        defined.

        """
        global _SHADER_LIGHT_UNIFORMS_
        uDir, uRange, uColor, uInt, uPos, uInner, uOuter, uType = \
            _SHADER_LIGHT_UNIFORMS_[index]

        GL.glUniform1i(self._unifLoc[uType], light._lightType)
        GL.glUniform1f(self._unifLoc[uInt], light._intensity)
        GL.glUniform1f(self._unifLoc[uRange], light._maxDist)
        GL.glUniform3f(self._unifLoc[uPos], *light._pos)
        GL.glUniform3f(self._unifLoc[uColor], 1.0, 1.0, 1.0)

        if light._lightType != 1:  # directional types only
            GL.glUniform3f(self._unifLoc[uDir], *light._dir)

            if light._lightType == 2:  # spotlights
                GL.glUniform1f(self._unifLoc[uInner], light._innerConeCos)
                GL.glUniform1f(self._unifLoc[uOuter], light._outerConeCos)

    def _setupNormalSampler(self, uvSet=0):
        """Setup the shader to render surface normals.

        This should only be called if the scene specifies at least one light,
        and if the shader has `PUNCTUAL_LIGHTS` and `NUM_LIGHTS` defined. If
        not, normals will have no effect on material appearance.

        The number of active samplers `_nActiveSamplers` is incremented upon
        calling this function.

        Parameters
        ----------
        uvSet : int
            UV set or texture coordinates to use for the normal map.

        """
        if not self._useLights:
            return

        if self._normalTexture is None or \
                (self._meshFlags & MESH_HAS_TANGENTS) != MESH_HAS_TANGENTS:
            return

        sampler = self._nActiveSamplers
        GL.glActiveTexture(GL.GL_TEXTURE0 + sampler)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._normalTexture.name)
        GL.glUniform1i(self._unifLoc[b'u_NormalSampler'], sampler)
        GL.glUniform1i(self._unifLoc[b'u_NormalUVSet'], uvSet)
        GL.glUniform1f(self._unifLoc[b'u_NormalScale'], 1.0)
        self._nActiveSamplers += 1

    def _setupEmissiveSampler(self, uvSet=0):
        """Setup the shader to render an emissive map.

        This should only be called if the scene specifies at least one light,
        and if the shader has `PUNCTUAL_LIGHTS` and `NUM_LIGHTS` defined.

        The number of active samplers `_nActiveSamplers` is incremented upon
        calling this function.

        Parameters
        ----------
        uvSet : int
            UV set or texture coordinates to use for the emissive map.

        """
        if not self._useLights:
            return

        if self._emissiveTexture is None:
            return

        sampler = self._nActiveSamplers
        GL.glActiveTexture(GL.GL_TEXTURE0 + sampler)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._emissiveTexture.name)
        GL.glUniform3f(self._unifLoc[b'u_EmissiveFactor'], 1.0, 1.0, 1.0)
        GL.glUniform1i(self._unifLoc[b'u_EmissiveSampler'], sampler)
        GL.glUniform1i(self._unifLoc[b'u_EmissiveUVSet'], uvSet)
        self._nActiveSamplers += 1

    def _setupBaseColorSampler(self, uvSet=0):
        """Setup the shader to render an base color/albiedo map.

        The number of active samplers `_nActiveSamplers` is incremented upon
        calling this function.

        Parameters
        ----------
        uvSet : int
            UV set or texture coordinates to use for the base color map.

        """
        GL.glUniform4f(self._unifLoc[b'u_BaseColorFactor'], 1.0, 1.0, 1.0, 1.0)

        if self._colorTexture is None:
            return  # nop if model has no normal texture of tangents

        sampler = self._nActiveSamplers
        GL.glActiveTexture(GL.GL_TEXTURE0 + sampler)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._colorTexture.name)
        GL.glUniform1i(self._unifLoc[b'u_BaseColorSampler'], sampler)
        GL.glUniform1i(self._unifLoc[b'u_BaseColorUVSet'], uvSet)
        self._nActiveSamplers += 1

    def _setupMetallicRoughnessSampler(self, uvSet=0):
        if not self._useLights:
            return

        GL.glUniform1f(self._unifLoc[b'u_MetallicFactor'], 1.0)
        GL.glUniform1f(self._unifLoc[b'u_RoughnessFactor'], 1.0)

        if self._metallicRoughnessTexture is None:
            return

        sampler = self._nActiveSamplers
        GL.glActiveTexture(GL.GL_TEXTURE0 + sampler)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._metallicRoughnessTexture.name)
        GL.glUniform1i(self._unifLoc[b'u_MetallicRoughnessSampler'], sampler)
        GL.glUniform1i(self._unifLoc[b'u_MetallicRoughnessUVSet'], uvSet)

        self._nActiveSamplers += 1

    def _setupOcculusionSampler(self, uvSet=0):
        if not self._useLights or self._occlusionTexture is None:
            return

        sampler = self._nActiveSamplers
        GL.glActiveTexture(GL.GL_TEXTURE0 + sampler)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._occlusionTexture.name)
        GL.glUniform1i(self._unifLoc[b'u_OcclusionSampler'], sampler)
        GL.glUniform1i(self._unifLoc[b'u_OcclusionUVSet'], uvSet)
        GL.glUniform1f(self._unifLoc[b'u_OcclusionStrength'], 1.0)

        self._nActiveSamplers += 1

    def _setupCamera(self):
        """Setup camera.

        Passes camera parameters to the shader program such as exposure and
        position. These values are gathered from the window object associated
        with the material.

        """
        if not self._useLights:
            return

        GL.glUniform3f(self._unifLoc[b'u_Camera'], *self.win._eyePos)
        GL.glUniform1f(self._unifLoc[b'u_Exposure'], self.win._exposure)


class RigidBodyPose(object):
    """Class for representing rigid body poses.

    This class is an abstract representation of a rigid body pose, where the
    position of the body in a scene is represented by a vector/coordinate and
    the orientation with a quaternion. Pose can be manipulated and interacted
    with using class methods and attributes. Rigid body poses assume a
    right-handed coordinate system (-Z is forward and +Y is up).

    Poses can be converted to 4x4 transformation matrices with `getModelMatrix`.
    One can use these matrices when rendering to transform the vertices of a
    model associated with the pose by passing them to OpenGL. Matrices are
    cached internally to avoid recomputing them if `pos` and `ori` attributes
    have not been updated.

    Operators `*` and `~` can be used on `RigidBodyPose` objects to combine and
    invert poses. For instance, you can multiply (`*`) poses to get a new pose
    which is the combination of both orientations and translations by::

        newPose = rb1 * rb2

    Likewise, a pose can be inverted by using the `~` operator::

        invPose = ~rb

    Multiplying a pose by its inverse will result in an identity pose with no
    translation and default orientation where `pos=[0, 0, 0]` and
    `ori=[0, 0, 0, 1]`::

        identityPose = ~rb * rb

    Warnings
    --------
    This class is experimental and may result in undefined behavior.

    """
    def __init__(self, pos=(0., 0., 0.), ori=(0., 0., 0., 1.)):
        """
        Parameters
        ----------
        pos : array_like
            Position vector `[x, y, z]` for the origin of the rigid body.
        ori : array_like
            Orientation quaternion `[x, y, z, w]` where `x`, `y`, `z` are
            imaginary and `w` is real.

        """
        self._pos = np.ascontiguousarray(pos, dtype=np.float32)
        self._ori = np.ascontiguousarray(ori, dtype=np.float32)

        self._modelMatrix = mt.posOriToMatrix(
            self._pos, self._ori, dtype=np.float32)

        # computed only if needed
        self._normalMatrix = np.zeros((4, 4), dtype=np.float32, order='C')
        self._invModelMatrix = np.zeros((4, 4), dtype=np.float32, order='C')

        # additional useful vectors
        self._at = np.zeros((3,), dtype=np.float32, order='C')
        self._up = np.zeros((3,), dtype=np.float32, order='C')

        # compute matrices only if `pos` and `ori` attributes have been updated
        self._matrixNeedsUpdate = False
        self._invMatrixNeedsUpdate = True
        self._normalMatrixNeedsUpdate = True

        self.pos = pos
        self.ori = ori

        self._bounds = None

    def __repr__(self):
        return 'RigidBodyPose({}, {}), %s)'.format(self.pos, self.ori)

    @property
    def bounds(self):
        """Bounding box associated with this pose."""
        return self._bounds

    @bounds.setter
    def bounds(self, value):
        self._bounds = value

    @property
    def pos(self):
        """Position vector (X, Y, Z)."""
        return self._pos

    @pos.setter
    def pos(self, value):
        self._pos = np.ascontiguousarray(value, dtype=np.float32)
        self._normalMatrixNeedsUpdate = self._matrixNeedsUpdate = \
            self._invMatrixNeedsUpdate = True

    @property
    def ori(self):
        """Orientation quaternion (X, Y, Z, W)."""
        return self._ori

    @ori.setter
    def ori(self, value):
        self._ori = np.ascontiguousarray(value, dtype=np.float32)
        self._normalMatrixNeedsUpdate = self._matrixNeedsUpdate = \
            self._invMatrixNeedsUpdate = True

    @property
    def posOri(self):
        """The position (x, y, z) and orientation (x, y, z, w)."""
        return self._pos, self._ori

    @posOri.setter
    def posOri(self, value):
        self._pos = np.ascontiguousarray(value[0], dtype=np.float32)
        self._ori = np.ascontiguousarray(value[1], dtype=np.float32)
        self._matrixNeedsUpdate = self._invMatrixNeedsUpdate = \
            self._normalMatrixNeedsUpdate = True

    @property
    def at(self):
        """Vector defining the forward direction (-Z) of this pose."""
        if self._matrixNeedsUpdate:  # matrix needs update, this need to be too
            atDir = [0., 0., -1.]
            self._at = mt.applyQuat(self.ori, atDir, out=self._at)

        return self._at

    @property
    def up(self):
        """Vector defining the up direction (+Y) of this pose."""
        if self._matrixNeedsUpdate:  # matrix needs update, this need to be too
            upDir = [0., 1., 0.]
            self._up = mt.applyQuat(self.ori, upDir, out=self._up)

        return self._up

    def __mul__(self, other):
        """Multiply two poses, combining them to get a new pose."""
        newOri = mt.multQuat(self._ori, other.ori)
        return RigidBodyPose(mt.transform(other.pos, newOri, self._pos), newOri)

    def __imul__(self, other):
        """Inplace multiplication. Transforms this pose by another."""
        self._ori = mt.multQuat(self._ori, other.ori)
        self._pos = mt.transform(other.pos, self._ori, self._pos)

    def copy(self):
        """Get a new `RigidBodyPose` object which copies the position and
        orientation of this one. Copies are independent and do not reference
        each others data.

        Returns
        -------
        RigidBodyPose
            Copy of this pose.

        """
        return RigidBodyPose(self._pos, self._ori)

    def isEqual(self, other):
        """Check if poses have similar orientation and position.

        Parameters
        ----------
        other : `RigidBodyPose`
            Other pose to compare.

        Returns
        -------
        bool
            Returns `True` is poses are effectively equal.

        """
        return np.isclose(self._pos, other.pos) and \
            np.isclose(self._ori, other.ori)

    def setIdentity(self):
        """Clear rigid body transformations.
        """
        self._pos.fill(0.0)
        self._ori[:3] = 0.0
        self._ori[3] = 1.0
        self._matrixNeedsUpdate = self._invMatrixNeedsUpdate = True

    def getOriAxisAngle(self, degrees=True):
        """Get the axis and angle of rotation for the rigid body. Converts the
        orientation defined by the `ori` quaternion to and axis-angle
        representation.

        Parameters
        ----------
        degrees : bool, optional
            Specify ``True`` if `angle` is in degrees, or else it will be
            treated as radians. Default is ``True``.

        Returns
        -------
        tuple
            Axis [rx, ry, rz] and angle.

        """
        return mt.quatToAxisAngle(self._ori, degrees)

    def setOriAxisAngle(self, axis, angle, degrees=True):
        """Set the orientation of the rigid body using an `axis` and
        `angle`. This sets the quaternion at `ori`.

        Parameters
        ----------
        axis : array_like
            Axis of rotation [rx, ry, rz].
        angle : float
            Angle of rotation.
        degrees : bool, optional
            Specify ``True`` if `angle` is in degrees, or else it will be
            treated as radians. Default is ``True``.

        """
        self.ori = mt.quatFromAxisAngle(axis, angle, degrees)

    def getYawPitchRoll(self, degrees=True):
        """Get the yaw, pitch and roll angles for this pose relative to the -Z
        world axis.

        Parameters
        ----------
        degrees : bool, optional
            Specify ``True`` if `angle` is in degrees, or else it will be
            treated as radians. Default is ``True``.

        """
        return mt.quatYawPitchRoll(self._ori, degrees)

    @property
    def modelMatrix(self):
        """Pose as a 4x4 model matrix (read-only)."""
        if not self._matrixNeedsUpdate:
            return self._modelMatrix
        else:
            return self.getModelMatrix()

    @property
    def inverseModelMatrix(self):
        """Inverse of the pose as a 4x4 model matrix (read-only)."""
        if not self._invMatrixNeedsUpdate:
            return self._invModelMatrix
        else:
            return self.getModelMatrix(inverse=True)

    @property
    def normalMatrix(self):
        """The normal transformation matrix."""
        if not self._normalMatrixNeedsUpdate:
            return self._normalMatrix
        else:
            return self.getNormalMatrix()

    def getNormalMatrix(self, out=None):
        """Get the present normal matrix.

        Parameters
        ----------
        out : ndarray or None
            Optional 4x4 array to write values to. Values written are computed
            using 32-bit float precision regardless of the data type of `out`.

        Returns
        -------
        ndarray
            4x4 normal transformation matrix.

        """
        if not self._normalMatrixNeedsUpdate:
            return self._normalMatrix

        self._normalMatrix[:, :] = np.linalg.inv(self.modelMatrix).T

        if out is not None:
            out[:, :] = self._normalMatrix[:, :]

        self._normalMatrixNeedsUpdate = False

        return self._normalMatrix

    def getModelMatrix(self, inverse=False, out=None):
        """Get the present rigid body transformation as a 4x4 matrix.

        Matrices are computed only if the `pos` and `ori` attributes have been
        updated since the last call to `getModelMatrix`. The returned matrix is
        an `ndarray` and row-major.

        Parameters
        ----------
        inverse : bool, optional
            Return the inverse of the model matrix.
        out : ndarray or None
            Optional 4x4 array to write values to. Values written are computed
            using 32-bit float precision regardless of the data type of `out`.

        Returns
        -------
        ndarray
            4x4 transformation matrix.

        Examples
        --------
        Using a rigid body pose to transform something in OpenGL::

            rb = RigidBodyPose((0, 0, -2))  # 2 meters away from origin

            # Use `array2pointer` from `psychopy.tools.arraytools` to convert
            # array to something OpenGL accepts.
            mv = array2pointer(rb.modelMatrix)

            # use the matrix to transform the scene
            glMatrixMode(GL_MODELVIEW)
            glPushMatrix()
            glLoadIdentity()
            glMultTransposeMatrixf(mv)

            # draw the thing here ...

            glPopMatrix()

        """
        if self._matrixNeedsUpdate:
            self._modelMatrix = mt.posOriToMatrix(
                self._pos, self._ori, out=self._modelMatrix)

            self._matrixNeedsUpdate = False
            self._normalMatrixNeedsUpdate = self._invMatrixNeedsUpdate = True

        # only update and return the inverse matrix if requested
        if inverse:
            if self._invMatrixNeedsUpdate:
                self._invModelMatrix = mt.invertMatrix(
                    self._modelMatrix, out=self._invModelMatrix)
                self._invMatrixNeedsUpdate = False

            if out is not None:
                out[:, :] = self._invModelMatrix[:, :]

            return self._invModelMatrix  # return the inverse

        if out is not None:
            out[:, :] = self._modelMatrix[:, :]

        return self._modelMatrix

    def getViewMatrix(self, inverse=False):
        """Convert this pose into a view matrix.

        Creates a view matrix which transforms points into eye space using the
        current pose as the eye position in the scene. Furthermore, you can use
        view matrices for rendering shadows if light positions are defined
        as `RigidBodyPose` objects.

        Parameters
        ----------
        inverse : bool
            Return the inverse of the view matrix. Default is `False`.

        Returns
        -------
        ndarray
            4x4 transformation matrix.

        """
        axes = np.asarray([[0, 0, -1], [0, 1, 0]], dtype=np.float32)

        rotMatrix = mt.quatToMatrix(self._ori, dtype=np.float32)
        transformedAxes = mt.applyMatrix(rotMatrix, axes, dtype=np.float32)

        fwdVec = transformedAxes[0, :] + self._pos
        upVec = transformedAxes[1, :]

        viewMatrix = vt.lookAt(self._pos, fwdVec, upVec, dtype=np.float32)

        if inverse:
            viewMatrix = mt.invertMatrix(viewMatrix, homogeneous=True)

        return viewMatrix

    def transform(self, v, out=None):
        """Transform a vector using this pose.

        Parameters
        ----------
        v : array_like
            Vector to transform [x, y, z].
        out : ndarray or None, optional
            Optional array to write values to. Must have the same shape as
            `v`.

        Returns
        -------
        ndarray
            Transformed points.

        """
        return mt.transform(self._pos, self._ori, points=v, out=out)

    def transformNormal(self, n):
        """Rotate a normal vector with respect to this pose.

        Rotates a normal vector `n` using the orientation quaternion at `ori`.

        Parameters
        ----------
        n : array_like
            Normal to rotate (1-D with length 3).

        Returns
        -------
        ndarray
            Rotated normal `n`.

        """
        pout = np.zeros((3,), dtype=np.float32)
        pout[:] = n
        t = np.cross(self._ori[:3], n[:3]) * 2.0
        u = np.cross(self._ori[:3], t)
        t *= self._ori[3]
        pout[:3] += t
        pout[:3] += u

        return pout

    def __invert__(self):
        """Operator `~` to invert the pose. Returns a `RigidBodyPose` object."""
        return RigidBodyPose(
            -self._pos, mt.invertQuat(self._ori, dtype=np.float32))

    def invert(self):
        """Invert this pose.
        """
        self._ori = mt.invertQuat(self._ori, dtype=np.float32)
        self._pos *= -1.0

    def inverted(self):
        """Get a pose which is the inverse of this one.

        Returns
        -------
        RigidBodyPose
            This pose inverted.

        """
        return RigidBodyPose(
            -self._pos, mt.invertQuat(self._ori, dtype=np.float32))

    def distanceTo(self, v):
        """Get the distance to a pose or point in scene units.

        Parameters
        ----------
        v : RigidBodyPose or array_like
            Pose or point [x, y, z] to compute distance to.

        Returns
        -------
        float
            Distance to `v` from this pose's origin.

        """
        if hasattr(v, 'pos'):  # v is pose-like object
            targetPos = v.pos
        else:
            targetPos = np.asarray(v[:3])

        return np.sqrt(np.sum(np.square(targetPos - self.pos)))

    def interp(self, end, s):
        """Interpolate between poses.

        Linear interpolation is used on position (Lerp) while the orientation
        has spherical linear interpolation (Slerp) applied taking the shortest
        arc on the hypersphere.

        Parameters
        ----------
        end : LibOVRPose
            End pose.
        s : float
            Interpolation factor between interval 0.0 and 1.0.

        Returns
        -------
        RigidBodyPose
            Rigid body pose whose position and orientation is at `s` between
            this pose and `end`.

        """
        if not (hasattr(end, 'pos') and hasattr(end, 'ori')):
            raise TypeError("Object for `end` does not have attributes "
                            "`pos` and `ori`.")

        interpPos = mt.lerp(self._pos, end.pos, s)
        interpOri = mt.slerp(self._ori, end.ori, s)

        return RigidBodyPose(interpPos, interpOri)

    def alignTo(self, alignTo):
        """Align this pose to another point or pose.

        This sets the orientation of this pose to one which orients the forward
        axis towards `alignTo`.

        Parameters
        ----------
        alignTo : array_like or LibOVRPose
            Position vector [x, y, z] or pose to align to.

        """
        if hasattr(alignTo, 'pos'):  # v is pose-like object
            targetPos = alignTo.pos
        else:
            targetPos = np.asarray(alignTo[:3])

        fwd = np.asarray([0, 0, -1], dtype=np.float32)
        toTarget = targetPos - self._pos
        invPos = mt.applyQuat(
            mt.invertQuat(self._ori, dtype=np.float32),
            toTarget, dtype=np.float32)
        invPos = mt.normalize(invPos)

        self.ori = mt.multQuat(
            self._ori, mt.alignTo(fwd, invPos, dtype=np.float32))


class BoundingBox(object):
    """Class for representing object bounding boxes.

    A bounding box is a construct which represents a 3D rectangular volume about
    some pose, defined by its minimum and maximum extents in the reference frame
    of the pose. The axes of the bounding box are aligned to the axes of the
    world or the associated pose.

    Bounding boxes are primarily used for visibility testing; to determine if
    the extents of an object associated with a pose (eg. the vertices of a
    model) falls completely outside of the viewing frustum. If so, the model can
    be culled during rendering to avoid wasting CPU/GPU resources on objects not
    visible to the viewer.

    """
    def __init__(self, extents=None):
        self._extents = np.zeros((2, 3), np.float32)
        self._posCorners = np.zeros((8, 4), np.float32)

        if extents is not None:
            self._extents[0, :] = extents[0]
            self._extents[1, :] = extents[1]
        else:
            self.clear()

        self._computeCorners()

    def _computeCorners(self):
        """Compute the corners of the bounding box.

        These values are cached to speed up computations if extents hasn't been
        updated.

        """
        for i in range(8):
            self._posCorners[i, 0] = \
                self._extents[1, 0] if (i & 1) else self._extents[0, 0]
            self._posCorners[i, 1] = \
                self._extents[1, 1] if (i & 2) else self._extents[0, 1]
            self._posCorners[i, 2] = \
                self._extents[1, 2] if (i & 4) else self._extents[0, 2]
            self._posCorners[i, 3] = 1.0

    @property
    def isValid(self):
        """`True` if the bounding box is valid."""
        return np.all(self._extents[0, :] <= self._extents[1, :])

    @property
    def extents(self):
        return self._extents

    @extents.setter
    def extents(self, value):
        self._extents[0, :] = value[0]
        self._extents[1, :] = value[1]
        self._computeCorners()

    def fit(self, verts):
        """Fit the bounding box to vertices."""
        np.amin(verts, axis=0, out=self._extents[0])
        np.amax(verts, axis=0, out=self._extents[1])
        self._computeCorners()

    def clear(self):
        """Clear a bounding box, invalidating it."""
        self._extents[0, :] = np.finfo(np.float32).max
        self._extents[1, :] = np.finfo(np.float32).min
        self._computeCorners()


class BaseRigidBodyStim(ColorMixin, WindowMixin):
    """Base class for rigid body 3D stimuli.

    This class handles the pose of a rigid body 3D stimulus. Poses are
    represented by a `RigidBodyClass` object accessed via `thePose` attribute.

    Any class the implements `pos` and `ori` attributes can be used in place of
    a `RigidBodyPose` instance for `thePose`. This common interface allows for
    custom classes which handle 3D transformations to be used for stimulus
    transformations (eg. `LibOVRPose` in PsychXR can be used instead of
    `RigidBodyPose` which supports more VR specific features).

    Warnings
    --------
    This class is experimental and may result in undefined behavior.

    """
    def __init__(self,
                 win,
                 pos=(0., 0., 0.),
                 ori=(0., 0., 0., 1.),
                 color=(0.0, 0.0, 0.0),
                 colorSpace='rgb',
                 contrast=1.0,
                 opacity=1.0,
                 useShaders=False,
                 name='',
                 autoLog=True):
        """
        Parameters
        ----------
        win : `~psychopy.visual.Window`
            Window this stimulus is associated with. Stimuli cannot be shared
            across windows unless they share the same context.
        pos : array_like
            Position vector `[x, y, z]` for the origin of the rigid body.
        ori : array_like
            Orientation quaternion `[x, y, z, w]` where `x`, `y`, `z` are
            imaginary and `w` is real.

        """
        self.autoLog = autoLog
        self.name = name

        super(BaseRigidBodyStim, self).__init__()

        self.win = win

        self.colorSpace = colorSpace
        self.contrast = contrast
        self.opacity = opacity
        self.color = color

        self._thePose = RigidBodyPose(pos, ori)
        self._useShaders = useShaders
        self.material = None

        self._vao = None

    @property
    def thePose(self):
        """The pose of the rigid body. This is a class which has `pos` and `ori`
        attributes."""
        return self._thePose

    @thePose.setter
    def thePose(self, value):
        if hasattr(value, 'pos') and hasattr(value, 'ori'):
            self._thePose = value
        else:
            raise AttributeError(
                'Class set to `thePose` does not implement `pos` or `ori`.')

    @property
    def pos(self):
        """Position vector (X, Y, Z)."""
        return self.thePose.pos

    @pos.setter
    def pos(self, value):
        self.thePose.pos = value

    def getPos(self):
        return self.thePose.pos

    def setPos(self, pos):
        self.thePose.pos = pos

    @property
    def ori(self):
        """Orientation quaternion (X, Y, Z, W)."""
        return self.thePose.ori

    @ori.setter
    def ori(self, value):
        self.thePose.ori = value

    def getOri(self):
        return self.thePose.ori

    def setOri(self, ori):
        self.thePose.ori = ori

    def getOriAxisAngle(self, degrees=True):
        """Get the axis and angle of rotation for the 3D stimulus. Converts the
        orientation defined by the `ori` quaternion to and axis-angle
        representation.

        Parameters
        ----------
        degrees : bool, optional
            Specify ``True`` if `angle` is in degrees, or else it will be
            treated as radians. Default is ``True``.

        Returns
        -------
        tuple
            Axis `[rx, ry, rz]` and angle.

        """
        return self.thePose.getOriAxisAngle(degrees)

    def setOriAxisAngle(self, axis, angle, degrees=True):
        """Set the orientation of the 3D stimulus using an `axis` and
        `angle`. This sets the quaternion at `ori`.

        Parameters
        ----------
        axis : array_like
            Axis of rotation [rx, ry, rz].
        angle : float
            Angle of rotation.
        degrees : bool, optional
            Specify ``True`` if `angle` is in degrees, or else it will be
            treated as radians. Default is ``True``.

        """
        self.thePose.setOriAxisAngle(axis, angle, degrees)

    def _createVAO(self, vertices, textureCoords, normals, faces):
        """Create a vertex array object for handling vertex attribute data.
        """
        self.thePose.bounds = BoundingBox()
        self.thePose.bounds.fit(vertices)

        # upload to buffers
        vertexVBO = gt.createVBO(vertices)
        texCoordVBO = gt.createVBO(textureCoords)
        normalsVBO = gt.createVBO(normals)

        # create an index buffer with faces
        indexBuffer = gt.createVBO(
            faces.flatten(),
            target=GL.GL_ELEMENT_ARRAY_BUFFER,
            dataType=GL.GL_UNSIGNED_INT)

        return gt.createVAO({GL.GL_VERTEX_ARRAY: vertexVBO,
                             GL.GL_TEXTURE_COORD_ARRAY: texCoordVBO,
                             GL.GL_NORMAL_ARRAY: normalsVBO},
                            indexBuffer=indexBuffer, legacy=True)

    def draw(self, win=None):
        """Draw the stimulus.

        This should work for stimuli using a single VAO and material. More
        complex stimuli with multiple materials should override this method to
        correctly handle that case.

        Parameters
        ----------
        win : `~psychopy.visual.Window`
            Window this stimulus is associated with. Stimuli cannot be shared
            across windows unless they share the same context.

        """
        if win is None:
            win = self.win
        else:
            self._selectWindow(win)

        # nop if there is no VAO to draw
        if self._vao is None:
            return

        win.draw3d = True

        # apply transformation to mesh
        GL.glPushMatrix()
        GL.glMultTransposeMatrixf(at.array2pointer(self.thePose.modelMatrix))

        if self.material is not None:  # has a material, use it
            if self._useShaders:
                useTexture = self.material.diffuseTexture is not None
                self.material.begin(useTexture, useShaders=True)
                gt.drawVAO(self._vao, GL.GL_TRIANGLES)
                self.material.end()
            else:
                self.material.begin(self.material.diffuseTexture is not None)
                gt.drawVAO(self._vao, GL.GL_TRIANGLES)
                self.material.end()
        else:  # doesn't have a material, use class colors
            r, g, b = self._getDesiredRGB(
                self.rgb, self.colorSpace, self.contrast)
            color = np.ctypeslib.as_ctypes(
                np.array((r, g, b, self.opacity), np.float32))

            if self._useShaders:
                nLights = len(self.win.lights)
                shaderKey = (nLights, False)
                gt.useProgram(self.win._shaders['stim3d_phong'][shaderKey])

                # pass values to OpenGL as material
                GL.glColor4f(r, g, b, self.opacity)
                GL.glMaterialfv(GL.GL_FRONT, GL.GL_DIFFUSE, color)
                GL.glMaterialfv(GL.GL_FRONT, GL.GL_AMBIENT, color)

                gt.drawVAO(self._vao, GL.GL_TRIANGLES)

                gt.useProgram(0)
            else:
                # material tracks color
                GL.glEnable(GL.GL_COLOR_MATERIAL)  # enable color tracking
                GL.glDisable(GL.GL_TEXTURE_2D)
                GL.glColorMaterial(GL.GL_FRONT, GL.GL_AMBIENT_AND_DIFFUSE)
                GL.glMaterialfv(GL.GL_FRONT, GL.GL_AMBIENT, color)
                # 'rgb' is created and set when color is set
                GL.glColor4f(r, g, b, self.opacity)

                # draw the shape
                gt.drawVAO(self._vao, GL.GL_TRIANGLES)
                GL.glDisable(GL.GL_COLOR_MATERIAL)  # enable color tracking

        GL.glPopMatrix()

        win.draw3d = False

    @attributeSetter
    def useShaders(self, value):
        """Should shaders be used to render the stimulus
        (typically leave as `True`)

        If the system support the use of OpenGL shader language then leaving
        this set to True is highly recommended. If shaders cannot be used then
        various operations will be slower (notably, changes to stimulus color
        or contrast)
        """
        if value is True and self.win._haveShaders is False:
            logging.error("Shaders were requested but aren't available. "
                          "Shaders need OpenGL 2.0+ drivers")
        if value != self._useShaders:  # if there's a change...
            self._useShaders = value

    def setUseShaders(self, value=True, log=None):
        """Usually you can use 'stim.attribute = value' syntax instead,
        but use this method if you need to suppress the log message"""
        setAttribute(self, 'useShaders', value, log)  # call attributeSetter

    @attributeSetter
    def units(self, value):
        """
        None, 'norm', 'cm', 'deg', 'degFlat', 'degFlatPos', or 'pix'

        If None then the current units of the
        :class:`~psychopy.visual.Window` will be used.
        See :ref:`units` for explanation of other options.

        Note that when you change units, you don't change the stimulus
        parameters and it is likely to change appearance. Example::

            # This stimulus is 20% wide and 50% tall with respect to window
            stim = visual.PatchStim(win, units='norm', size=(0.2, 0.5)

            # This stimulus is 0.2 degrees wide and 0.5 degrees tall.
            stim.units = 'deg'
        """
        if value is not None and len(value):
            self.__dict__['units'] = value
        else:
            self.__dict__['units'] = self.win.units

    def _updateList(self):
        """The user shouldn't need this method since it gets called
        after every call to .set()
        Chooses between using and not using shaders each call.
        """
        pass

    def isVisible(self):
        """Check if the object is visible to the observer.

        Test if a pose's bounding box or position falls outside of an eye's view
        frustum.

        Poses can be assigned bounding boxes which enclose any 3D models
        associated with them. A model is not visible if all the corners of the
        bounding box fall outside the viewing frustum. Therefore any primitives
        (i.e. triangles) associated with the pose can be culled during rendering
        to reduce CPU/GPU workload.

        Returns
        -------
        bool
            `True` if the object's bounding box is visible.

        Examples
        --------
        You can avoid running draw commands if the object is not visible by
        doing a visibility test first::

            if myStim.isVisible():
                myStim.draw()

        """
        if self.thePose.bounds is None:
            return True

        if not self.thePose.bounds.isValid:
            return True

        # transformation matrix
        mvpMatrix = np.zeros((4, 4), dtype=np.float32)
        np.matmul(self.win.projectionMatrix, self.win.viewMatrix, out=mvpMatrix)
        np.matmul(mvpMatrix, self.thePose.modelMatrix, out=mvpMatrix)

        # compute bounding box corners in current view
        corners = self.thePose.bounds._posCorners.dot(mvpMatrix.T)

        # check if corners are completely off to one side of the frustum
        if not np.any(corners[:, 0] > -corners[:, 3]):
            return False

        if not np.any(corners[:, 0] < corners[:, 3]):
            return False

        if not np.any(corners[:, 1] > -corners[:, 3]):
            return False

        if not np.any(corners[:, 1] < corners[:, 3]):
            return False

        if not np.any(corners[:, 2] > -corners[:, 3]):
            return False

        if not np.any(corners[:, 2] < corners[:, 3]):
            return False

        return True

    def getRayIntersectBounds(self, rayOrig, rayDir):
        """Get the point which a ray intersects the bounding box of this mesh.

        Parameters
        ----------
        rayOrig : array_like
            Origin of the ray in space [x, y, z].
        rayDir : array_like
            Direction vector of the ray [x, y, z], should be normalized.

        Returns
        -------
        tuple
            Coordinate in world space of the intersection and distance in scene
            units from `rayOrig`. Returns `None` if there is no intersection.

        """
        if self.thePose.bounds is None:
            return None  # nop

        return mt.intersectRayOBB(rayOrig,
                                  rayDir,
                                  self.thePose.modelMatrix,
                                  self.thePose.bounds.extents,
                                  dtype=np.float32)


class SphereStim(BaseRigidBodyStim):
    """Class for drawing a UV sphere.

    The resolution of the sphere mesh can be controlled by setting `sectors`
    and `stacks` which controls the number of latitudinal and longitudinal
    subdivisions, respectively. The radius of the sphere is defined by setting
    `radius` expressed in scene units (meters if using a perspective
    projection).

    Calling the `draw` method will render the sphere to the current buffer. The
    render target (FBO or back buffer) must have a depth buffer attached to it
    for the object to be rendered correctly. Shading is used if the current
    window has light sources defined and lighting is enabled (by setting
    `useLights=True` before drawing the stimulus).

    Warnings
    --------
    This class is experimental and may result in undefined behavior.

    Examples
    --------
    Creating a red sphere 1.5 meters away from the viewer with radius 0.25::

        redSphere = SphereStim(win,
                               pos=(0., 0., -1.5),
                               radius=0.25,
                               color=(1, 0, 0))

    """
    def __init__(self,
                 win,
                 radius=0.5,
                 subdiv=(32, 32),
                 flipFaces=False,
                 pos=(0., 0., 0.),
                 ori=(0., 0., 0., 1.),
                 color=(0., 0., 0.),
                 colorSpace='rgb',
                 contrast=1.0,
                 opacity=1.0,
                 useMaterial=None,
                 useShaders=False,
                 name='',
                 autoLog=True):
        """
        Parameters
        ----------
        win : `~psychopy.visual.Window`
            Window this stimulus is associated with. Stimuli cannot be shared
            across windows unless they share the same context.
        radius : float
            Radius of the sphere in scene units.
        subdiv : array_like
            Number of latitudinal and longitudinal subdivisions `(lat, long)`
            for the sphere mesh. The greater the number, the smoother the sphere
            will appear.
        flipFaces : bool, optional
            If `True`, normals and face windings will be set to point inward
            towards the center of the sphere. Texture coordinates will remain
            the same. Default is `False`.
        pos : array_like
            Position vector `[x, y, z]` for the origin of the rigid body.
        ori : array_like
            Orientation quaternion `[x, y, z, w]` where `x`, `y`, `z` are
            imaginary and `w` is real. If you prefer specifying rotations in
            axis-angle format, call `setOriAxisAngle` after initialization.
        useMaterial : PhongMaterial, optional
            Material to use. The material can be configured by accessing the
            `material` attribute after initialization. If not material is
            specified, the diffuse and ambient color of the shape will be set
            by `color`.
        color : array_like
            Diffuse and ambient color of the stimulus if `useMaterial` is not
            specified. Values are with respect to `colorSpace`.
        colorSpace : str
            Colorspace of `color` to use.
        contrast : float
            Contrast of the stimulus, value modulates the `color`.
        opacity : float
            Opacity of the stimulus ranging from 0.0 to 1.0. Note that
            transparent objects look best when rendered from farthest to
            nearest.
        name : str
            Name of this object for logging purposes.
        autoLog : bool
            Enable automatic logging on attribute changes.

        """
        super(SphereStim, self).__init__(win,
                                         pos=pos,
                                         ori=ori,
                                         color=color,
                                         colorSpace=colorSpace,
                                         contrast=contrast,
                                         opacity=opacity,
                                         useShaders=useShaders,
                                         name=name,
                                         autoLog=autoLog)

        # create a vertex array object for drawing
        vertices, textureCoords, normals, faces = gt.createUVSphere(
            sectors=subdiv[0],
            stacks=subdiv[1],
            radius=radius,
            flipFaces=flipFaces)
        self._vao = self._createVAO(vertices, textureCoords, normals, faces)

        self.material = useMaterial
        self._useShaders = useShaders

        self._radius = radius  # for raypicking

        self.extents = (vertices.min(axis=0), vertices.max(axis=0))

    def getRayIntersectSphere(self, rayOrig, rayDir):
        """Get the point which a ray intersects the sphere.

        Parameters
        ----------
        rayOrig : array_like
            Origin of the ray in space [x, y, z].
        rayDir : array_like
            Direction vector of the ray [x, y, z], should be normalized.

        Returns
        -------
        tuple
            Coordinate in world space of the intersection and distance in scene
            units from `rayOrig`. Returns `None` if there is no intersection.

        """
        return mt.intersectRaySphere(rayOrig,
                                     rayDir,
                                     self.thePose.pos,
                                     self._radius,
                                     dtype=np.float32)


class BoxStim(BaseRigidBodyStim):
    """Class for drawing 3D boxes.

    Draws a rectangular box with dimensions specified by `size` (length, width,
    height) in scene units.

    Calling the `draw` method will render the box to the current buffer. The
    render target (FBO or back buffer) must have a depth buffer attached to it
    for the object to be rendered correctly. Shading is used if the current
    window has light sources defined and lighting is enabled (by setting
    `useLights=True` before drawing the stimulus).

    Warnings
    --------
    This class is experimental and may result in undefined behavior.

    """
    def __init__(self,
                 win,
                 size=(.5, .5, .5),
                 flipFaces=False,
                 pos=(0., 0., 0.),
                 ori=(0., 0., 0., 1.),
                 color=(0., 0., 0.),
                 colorSpace='rgb',
                 contrast=1.0,
                 opacity=1.0,
                 useMaterial=None,
                 useShaders=False,
                 textureScale=None,
                 name='',
                 autoLog=True):
        """
        Parameters
        ----------
        win : `~psychopy.visual.Window`
            Window this stimulus is associated with. Stimuli cannot be shared
            across windows unless they share the same context.
        size : tuple or float
            Dimensions of the mesh. If a single value is specified, the box will
            be a cube. Provide a tuple of floats to specify the width, length,
            and height of the box (eg. `size=(0.2, 1.3, 2.1)`) in scene units.
        flipFaces : bool, optional
            If `True`, normals and face windings will be set to point inward
            towards the center of the box. Texture coordinates will remain the
            same. Default is `False`.
        pos : array_like
            Position vector `[x, y, z]` for the origin of the rigid body.
        ori : array_like
            Orientation quaternion `[x, y, z, w]` where `x`, `y`, `z` are
            imaginary and `w` is real. If you prefer specifying rotations in
            axis-angle format, call `setOriAxisAngle` after initialization.
        useMaterial : PhongMaterial, optional
            Material to use. The material can be configured by accessing the
            `material` attribute after initialization. If not material is
            specified, the diffuse and ambient color of the shape will track the
            current color specified by `glColor`.
            color : array_like
            Diffuse and ambient color of the stimulus if `useMaterial` is not
            specified. Values are with respect to `colorSpace`.
        colorSpace : str
            Colorspace of `color` to use.
        contrast : float
            Contrast of the stimulus, value modulates the `color`.
        opacity : float
            Opacity of the stimulus ranging from 0.0 to 1.0. Note that
            transparent objects look best when rendered from farthest to
            nearest.
        textureScale : array_like or float, optional
            Scaling factors for texture coordinates (sx, sy). By default,
            a factor of 1 will have the entire texture cover the surface of the
            mesh. If a single number is provided, the texture will be scaled
            uniformly.
        name : str
            Name of this object for logging purposes.
        autoLog : bool
            Enable automatic logging on attribute changes.

        """
        super(BoxStim, self).__init__(
            win,
            pos=pos,
            ori=ori,
            color=color,
            colorSpace=colorSpace,
            contrast=contrast,
            opacity=opacity,
            useShaders=useShaders,
            name=name,
            autoLog=autoLog)

        # create a vertex array object for drawing
        vertices, texCoords, normals, faces = gt.createBox(size, flipFaces)

        # scale the texture
        if textureScale is not None:
            if isinstance(textureScale, (int, float)):
                texCoords *= textureScale
            else:
                texCoords *= np.asarray(textureScale, dtype=np.float32)

        self._vao = self._createVAO(vertices, texCoords, normals, faces)

        self.setColor(color, colorSpace=self.colorSpace, log=False)
        self.material = useMaterial

        self.extents = (vertices.min(axis=0), vertices.max(axis=0))


class PlaneStim(BaseRigidBodyStim):
    """Class for drawing planes.

    Draws a plane with dimensions specified by `size` (length, width) in scene
    units.

    Calling the `draw` method will render the plane to the current buffer. The
    render target (FBO or back buffer) must have a depth buffer attached to it
    for the object to be rendered correctly. Shading is used if the current
    window has light sources defined and lighting is enabled (by setting
    `useLights=True` before drawing the stimulus).

    Warnings
    --------
    This class is experimental and may result in undefined behavior.

    """
    def __init__(self,
                 win,
                 size=(.5, .5),
                 pos=(0., 0., 0.),
                 ori=(0., 0., 0., 1.),
                 color=(0., 0., 0.),
                 colorSpace='rgb',
                 contrast=1.0,
                 opacity=1.0,
                 useMaterial=None,
                 useShaders=False,
                 textureScale=None,
                 name='',
                 autoLog=True):
        """
        Parameters
        ----------
        win : `~psychopy.visual.Window`
            Window this stimulus is associated with. Stimuli cannot be shared
            across windows unless they share the same context.
        size : tuple or float
            Dimensions of the mesh. If a single value is specified, the plane
            will be a square. Provide a tuple of floats to specify the width and
            length of the plane (eg. `size=(0.2, 1.3)`).
        pos : array_like
            Position vector `[x, y, z]` for the origin of the rigid body.
        ori : array_like
            Orientation quaternion `[x, y, z, w]` where `x`, `y`, `z` are
            imaginary and `w` is real. If you prefer specifying rotations in
            axis-angle format, call `setOriAxisAngle` after initialization. By
            default, the plane is oriented with normal facing the +Z axis of the
            scene.
        useMaterial : PhongMaterial, optional
            Material to use. The material can be configured by accessing the
            `material` attribute after initialization. If not material is
            specified, the diffuse and ambient color of the shape will track the
            current color specified by `glColor`.
        colorSpace : str
            Colorspace of `color` to use.
        contrast : float
            Contrast of the stimulus, value modulates the `color`.
        opacity : float
            Opacity of the stimulus ranging from 0.0 to 1.0. Note that
            transparent objects look best when rendered from farthest to
            nearest.
        textureScale : array_like or float, optional
            Scaling factors for texture coordinates (sx, sy). By default,
            a factor of 1 will have the entire texture cover the surface of the
            mesh. If a single number is provided, the texture will be scaled
            uniformly.
        name : str
            Name of this object for logging purposes.
        autoLog : bool
            Enable automatic logging on attribute changes.

        """
        super(PlaneStim, self).__init__(
            win,
            pos=pos,
            ori=ori,
            color=color,
            colorSpace=colorSpace,
            contrast=contrast,
            opacity=opacity,
            useShaders=useShaders,
            name=name,
            autoLog=autoLog)

        # create a vertex array object for drawing
        vertices, texCoords, normals, faces = gt.createPlane(size)

        # scale the texture
        if textureScale is not None:
            if isinstance(textureScale, (int, float)):
                texCoords *= textureScale
            else:
                texCoords *= np.asarray(textureScale, dtype=np.float32)

        self._vao = self._createVAO(vertices, texCoords, normals, faces)

        self.setColor(color, colorSpace=self.colorSpace, log=False)
        self.material = useMaterial

        self.extents = (vertices.min(axis=0), vertices.max(axis=0))


class ObjMeshStim(BaseRigidBodyStim):
    """Class for loading and presenting 3D stimuli in the Wavefront OBJ format.

    Calling the `draw` method will render the mesh to the current buffer. The
    render target (FBO or back buffer) must have a depth buffer attached to it
    for the object to be rendered correctly. Shading is used if the current
    window has light sources defined and lighting is enabled (by setting
    `useLights=True` before drawing the stimulus).

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
        of any time-critical routines! This class is experimental and may result
        in undefined behavior.

    Examples
    --------
    Loading an *.OBJ file from a disk location::

        myObjStim = ObjMeshStim(win, '/path/to/file/model.obj')

    """
    def __init__(self,
                 win,
                 objFile,
                 pos=(0, 0, 0),
                 ori=(0, 0, 0, 1),
                 useMaterial=None,
                 loadMtllib=True,
                 color=(0.0, 0.0, 0.0),
                 colorSpace='rgb',
                 contrast=1.0,
                 opacity=1.0,
                 useShaders=False,
                 name='',
                 autoLog=True):
        """
        Parameters
        ----------
        win : `~psychopy.visual.Window`
            Window this stimulus is associated with. Stimuli cannot be shared
            across windows unless they share the same context.
        size : tuple or float
            Dimensions of the mesh. If a single value is specified, the plane
            will be a square. Provide a tuple of floats to specify the width and
            length of the box (eg. `size=(0.2, 1.3)`).
        pos : array_like
            Position vector `[x, y, z]` for the origin of the rigid body.
        ori : array_like
            Orientation quaternion `[x, y, z, w]` where `x`, `y`, `z` are
            imaginary and `w` is real. If you prefer specifying rotations in
            axis-angle format, call `setOriAxisAngle` after initialization. By
            default, the plane is oriented with normal facing the +Z axis of the
            scene.
        useMaterial : PhongMaterial, optional
            Material to use for all sub-meshes. The material can be configured
            by accessing the `material` attribute after initialization. If no
            material is specified, `color` will modulate the diffuse and
            ambient colors for all meshes in the model. If `loadMtllib` is
            `True`, this value should be `None`.
        loadMtllib : bool
            Load materials from the MTL file associated with the mesh. This will
            override `useMaterial` if it is `None`. The value of `materials`
            after initialization will be a dictionary where keys are material
            names and values are materials. Any textures associated with the
            model will be loaded as per the material requirements.
        useShaders : bool
            Use shaders when rendering.

        """
        super(ObjMeshStim, self).__init__(
            win,
            pos=pos,
            ori=ori,
            color=color,
            colorSpace=colorSpace,
            contrast=contrast,
            opacity=opacity,
            useShaders=useShaders,
            name=name,
            autoLog=autoLog)

        # load the OBJ file
        objModel = gt.loadObjFile(objFile)

        # load materials from file if requested
        if loadMtllib and self.material is None:
            self.material = self._loadMtlLib(objModel.mtlFile)
        else:
            self.material = useMaterial

        # load vertex data into an interleaved VBO
        buffers = np.ascontiguousarray(
            np.hstack((objModel.vertexPos,
                       objModel.texCoords,
                       objModel.normals)),
            dtype=np.float32)

        # upload to buffer
        vertexAttr = gt.createVBO(buffers)

        # load vertex data into VAOs
        self._vao = {}  # dictionary for VAOs
        # for each material create a VAO
        # keys are material names, values are index buffers
        for material, faces in objModel.faces.items():
            # convert index buffer to VAO
            indexBuffer = \
                gt.createVBO(
                    faces.flatten(),  # flatten face index for element array
                    target=GL.GL_ELEMENT_ARRAY_BUFFER,
                    dataType=GL.GL_UNSIGNED_INT)

            # see `setVertexAttribPointer` for more information about attribute
            # pointer indices
            self._vao[material] = gt.createVAO(
                {GL.GL_VERTEX_ARRAY: (vertexAttr, 3),
                 GL.GL_TEXTURE_COORD_ARRAY: (vertexAttr, 2, 3),
                 GL.GL_NORMAL_ARRAY: (vertexAttr, 3, 5, True)},
                indexBuffer=indexBuffer, legacy=True)

        self._useShaders = useShaders
        self.extents = objModel.extents

        self.thePose.bounds = BoundingBox()
        self.thePose.bounds.fit(objModel.vertexPos)

    def _loadMtlLib(self, mtlFile):
        """Load a material library associated with the OBJ file. This is usually
        called by the constructor for this class.

        Parameters
        ----------
        mtlFile : str
            Path to MTL file.

        """
        with open(mtlFile, 'r') as mtl:
            mtlBuffer = StringIO(mtl.read())

        foundMaterials = {}
        foundTextures = {}
        thisMaterial = 0
        for line in mtlBuffer.readlines():
            line = line.strip()
            if line.startswith('newmtl '):  # new material
                thisMaterial = line[7:]
                foundMaterials[thisMaterial] = BlinnPhongMaterial(self.win)
            elif line.startswith('Ns '):  # specular exponent
                foundMaterials[thisMaterial].shininess = line[3:]
            elif line.startswith('Ks '):  # specular color
                specularColor = np.asarray(list(map(float, line[3:].split(' '))))
                specularColor = 2.0 * specularColor - 1
                foundMaterials[thisMaterial].specularColor = specularColor
            elif line.startswith('Kd '):  # diffuse color
                diffuseColor = np.asarray(list(map(float, line[3:].split(' '))))
                diffuseColor = 2.0 * diffuseColor - 1
                foundMaterials[thisMaterial].diffuseColor = diffuseColor
            elif line.startswith('Ka '):  # ambient color
                ambientColor = np.asarray(list(map(float, line[3:].split(' '))))
                ambientColor = 2.0 * ambientColor - 1
                foundMaterials[thisMaterial].ambientColor = ambientColor
            elif line.startswith('map_Kd '):  # diffuse color map
                # load a diffuse texture from file
                textureName = line[7:]
                if textureName not in foundTextures.keys():
                    im = Image.open(
                        os.path.join(os.path.split(mtlFile)[0], textureName))
                    im = im.transpose(Image.FLIP_TOP_BOTTOM)
                    im = im.convert("RGBA")
                    pixelData = np.array(im).ctypes
                    width = pixelData.shape[1]
                    height = pixelData.shape[0]
                    foundTextures[textureName] = gt.createTexImage2D(
                        width,
                        height,
                        internalFormat=GL.GL_RGBA,
                        pixelFormat=GL.GL_RGBA,
                        dataType=GL.GL_UNSIGNED_BYTE,
                        data=pixelData,
                        unpackAlignment=1,
                        texParams={GL.GL_TEXTURE_MAG_FILTER: GL.GL_LINEAR,
                                   GL.GL_TEXTURE_MIN_FILTER: GL.GL_LINEAR})
                foundMaterials[thisMaterial].diffuseTexture = \
                    foundTextures[textureName]

        return foundMaterials

    def draw(self, win=None):
        """Draw the mesh.

        Parameters
        ----------
        win : `~psychopy.visual.Window`
            Window this stimulus is associated with. Stimuli cannot be shared
            across windows unless they share the same context.

        """
        if win is None:
            win = self.win
        else:
            self._selectWindow(win)

        win.draw3d = True

        GL.glPushMatrix()
        GL.glMultTransposeMatrixf(at.array2pointer(self.thePose.modelMatrix))

        # iterate over materials, draw associated VAOs
        if self.material is not None:
            # if material is a dictionary
            if isinstance(self.material, dict):
                for materialName, materialDesc in self.material.items():
                    materialDesc.begin(useShaders=self._useShaders)
                    gt.drawVAO(self._vao[materialName], GL.GL_TRIANGLES)
                    materialDesc.end()
            else:
                # material is a single item
                self.material.begin(useShaders=self._useShaders)
                for materialName, _ in self._vao.items():
                    gt.drawVAO(self._vao[materialName], GL.GL_TRIANGLES)
                self.material.end()
        else:
            r, g, b = self._getDesiredRGB(
                self.rgb, self.colorSpace, self.contrast)
            color = np.ctypeslib.as_ctypes(
                np.array((r, g, b, self.opacity), np.float32))

            if self._useShaders:
                nLights = len(self.win.lights)
                shaderKey = (nLights, False)
                gt.useProgram(self.win._shaders['stim3d_phong'][shaderKey])

                # pass values to OpenGL as material
                GL.glColor4f(r, g, b, self.opacity)
                GL.glMaterialfv(GL.GL_FRONT, GL.GL_DIFFUSE, color)
                GL.glMaterialfv(GL.GL_FRONT, GL.GL_AMBIENT, color)

                for materialName, _ in self._vao.items():
                    gt.drawVAO(self._vao[materialName], GL.GL_TRIANGLES)

                gt.useProgram(0)
            else:
                # material tracks color
                GL.glEnable(GL.GL_COLOR_MATERIAL)  # enable color tracking
                GL.glDisable(GL.GL_TEXTURE_2D)
                GL.glColorMaterial(GL.GL_FRONT, GL.GL_AMBIENT_AND_DIFFUSE)
                GL.glMaterialfv(GL.GL_FRONT, GL.GL_DIFFUSE, color)
                GL.glMaterialfv(GL.GL_FRONT, GL.GL_AMBIENT, color)
                # 'rgb' is created and set when color is set
                GL.glColor4f(r, g, b, self.opacity)

                # draw the shape
                for materialName, _ in self._vao.items():
                    gt.drawVAO(self._vao[materialName], GL.GL_TRIANGLES)

                GL.glDisable(GL.GL_COLOR_MATERIAL)  # enable color tracking

        GL.glPopMatrix()

        win.draw3d = False


class GLTFMeshStim(BaseRigidBodyStim):
    """Class for loading and presenting 3D stimuli from glTF files.

    The glTF (GL Transmission Format) is an extensible format for storing 3D
    geometry and scene information. However, this class only loads mesh and
    material data at this time (data about scene lights and cameras are
    ignored). The `pygltflib` package is required to use this class. How this
    class treats data loaded from glTF files isn't 100% compliant with the
    specification, therefore the import routines are not guaranteed to work in
    all cases.

    Only a single node can be loaded from a glTF file for use as a stimuli. The
    node must be explicitly specified by name or index. If not, the first node
    to appear in the file will be imported. Multiple groups of primitives
    associated with a mesh cannot share the same material. They should be
    combined in the 3D editor.

    """
    def __init__(self,
                 win,
                 gltfFile,
                 useNode=0,
                 pos=(0, 0, 0),
                 ori=(0, 0, 0, 1),
                 useMaterial=None,
                 color=(0.0, 0.0, 0.0),
                 colorSpace='rgb',
                 contrast=1.0,
                 opacity=1.0,
                 diffuseIBL=None,
                 name='',
                 autoLog=True):

        # check if we have a GLTF importer library installed and loaded
        if not _HAS_GLTF_IMPORTER_:
            raise ImportError("Package `pygltflib` not installed.")

        super(GLTFMeshStim, self).__init__(
            win,
            pos=pos,
            ori=ori,
            color=color,
            colorSpace=colorSpace,
            contrast=contrast,
            opacity=opacity,
            name=name,
            autoLog=autoLog)

        self._meshAttribFlags = 0x0
        self.diffuseIBL = diffuseIBL

        # new handle to glTF object
        gltf = pygltflib.GLTF2().load(gltfFile)

        # read all buffers associated with the mesh
        buffers = {}
        for idx, buffer in enumerate(gltf.buffers):
            # read the glTF buffer associated with the mesh
            bufferPath = os.path.join(os.path.split(gltfFile)[0], buffer.uri)
            with open(bufferPath, mode='rb') as bufferFile:
                buffers[idx] = bufferFile.read()

        # get the node by index or name
        if isinstance(useNode, str):
            for n in gltf.nodes:
                if n.name == useNode:
                    node = n
                    break
            else:
                raise ValueError(
                    "Cannot find specified node '{}' in glTF file.".format(
                        useNode))
        else:
            node = gltf.nodes[useNode]

        # node transformation, only scale is used to transform the data,
        # position and orientation is used for `thePose`
        nodeScale = np.ones((3,), np.float32)
        if node.scale:
            nodeScale[:] = node.scale

        nodePos = np.zeros((3,), np.float32)
        if node.translation:
            nodePos[:] = node.translation

        nodeOri = np.array((0, 0, 0, 1), np.float32)
        if node.rotation:
            nodeOri[:] = node.rotation

        self.thePose.pos = nodePos
        self.thePose.ori = nodeOri

        # primitives associated with the mesh at the node
        nodeMesh = gltf.meshes[node.mesh]
        nodePrimitives = nodeMesh.primitives

        # materials used by node primitives
        nodeMaterials = {}
        for i, prim in enumerate(nodePrimitives):
            nodeMaterials[i] = gltf.materials[prim.material]

        # attribute flags
        attribFlags = {pygltflib.POSITION: MESH_HAS_POSITION,
                       pygltflib.NORMAL: MESH_HAS_NORMALS,
                       pygltflib.TANGENT: MESH_HAS_TANGENTS,
                       pygltflib.TEXCOORD_0: MESH_HAS_UV_SET1,
                       pygltflib.TEXCOORD_1: MESH_HAS_UV_SET2}

        # go over all materials and load the data into VBOs and create a
        # material VAO
        materialVAOs = {}
        for idx, mat in nodeMaterials.items():
            materialName = mat.name
            attribVBOs = {}

            # get the primitive using the material
            prim = nodePrimitives[idx]

            # buffers for vertex attribute data to be uploaded to GPU
            attribs = ((pygltflib.POSITION, prim.attributes.POSITION),
                       (pygltflib.NORMAL, prim.attributes.NORMAL),
                       (pygltflib.TANGENT, prim.attributes.TANGENT),
                       (pygltflib.TEXCOORD_0, prim.attributes.TEXCOORD_0),
                       (pygltflib.TEXCOORD_1, prim.attributes.TEXCOORD_1))

            # attribute pointer for the buffer in the VAO
            attribPointer = 0
            # go over each primitive attribute and load the data to a VBO
            for attrib, idx in attribs:
                # don't load the buffer if the model doesn't use this attribute
                if idx is None:
                    continue

                acc = gltf.accessors[idx]
                bv = gltf.bufferViews[acc.bufferView]

                # attribute element size
                attribSize = _GLTF_COMPONENT_TYPE_[acc.componentType] * \
                             _GLTF_TYPE_SIZE_[acc.type]

                # compute buffer access offests and ranges
                accOffset = 0 if acc.byteOffset is None else acc.byteOffset
                bvOffset = 0 if bv.byteOffset is None else bv.byteOffset
                accEnd = acc.count * attribSize
                start = bvOffset + accOffset
                end = start + accEnd

                # always float, but that may change
                if acc.componentType == pygltflib.FLOAT:
                    dtype = np.float32
                elif acc.componentType == pygltflib.UNSIGNED_INT:
                    dtype = np.uint32
                elif acc.componentType == pygltflib.UNSIGNED_SHORT:
                    dtype = np.uint16
                elif acc.componentType == pygltflib.UNSIGNED_BYTE:
                    dtype = np.uint8
                elif acc.componentType == pygltflib.SHORT:
                    dtype = np.uint16
                else:
                    dtype = np.uint8

                bufferData = np.frombuffer(buffers[bv.buffer][start:end],
                                           dtype=dtype)

                # reshape according to component size
                bufferData = np.reshape(
                    bufferData, (-1, _GLTF_TYPE_SIZE_[acc.type]))

                # these are read out as VEC3, but needs to be VEC4
                if attrib == pygltflib.POSITION or attrib == pygltflib.NORMAL:
                    arr = np.zeros((bufferData.shape[0], 4), dtype=dtype)
                    arr[:, :3] = bufferData
                    arr[:, 3] = 1.0

                    # apply node scaling to the primitives
                    if attrib == pygltflib.POSITION:
                        arr[:, :3] *= nodeScale

                    attribVBOs[attribPointer] = gt.createVBO(arr)
                else:
                    attribVBOs[attribPointer] = gt.createVBO(bufferData)

                attribPointer += 1
                self._meshAttribFlags |= attribFlags[attrib]

            # load any index buffers if applicable
            indexVBO = None
            if prim.indices is not None:
                acc = gltf.accessors[prim.indices]
                bv = gltf.bufferViews[acc.bufferView]
                accOffset = 0 if acc.byteOffset is None else acc.byteOffset
                bvOffset = 0 if bv.byteOffset is None else bv.byteOffset
                attribSize = _GLTF_COMPONENT_TYPE_[acc.componentType] * \
                             _GLTF_TYPE_SIZE_[acc.type]
                accEnd = acc.count * attribSize
                start = bvOffset + accOffset
                end = start + accEnd

                if acc.componentType == pygltflib.FLOAT:
                    dtype = np.float32
                    glType = GL.GL_FLOAT
                elif acc.componentType == pygltflib.UNSIGNED_INT:
                    dtype = np.uint32
                    glType = GL.GL_UNSIGNED_INT
                elif acc.componentType == pygltflib.UNSIGNED_SHORT:
                    dtype = np.uint16
                    glType = GL.GL_UNSIGNED_SHORT
                elif acc.componentType == pygltflib.UNSIGNED_BYTE:
                    dtype = np.uint8
                    glType = GL.GL_UNSIGNED_BYTE
                elif acc.componentType == pygltflib.SHORT:
                    dtype = np.uint16
                    glType = GL.GL_SHORT
                else:
                    dtype = np.uint8
                    glType = GL.GL_BYTE

                bufferData = np.frombuffer(
                    buffers[bv.buffer][start:end],
                    dtype=dtype)
                indexVBO = gt.createVBO(bufferData,
                                        target=GL.GL_ELEMENT_ARRAY_BUFFER,
                                        dataType=glType)

                self._meshAttribFlags |= MESH_HAS_INDICES

            # create the VAO to render the material
            materialVAOs[materialName] = gt.createVAO(
                attribVBOs, indexBuffer=indexVBO, legacy=False)

        nodeTextures = {}  # keep track of textures used by the node
        # create material objects for loaded materials
        self.material = {}
        for idx, mat in nodeMaterials.items():
            imgRefs = (mat.pbrMetallicRoughness.baseColorTexture,
                       mat.pbrMetallicRoughness.metallicRoughnessTexture,
                       mat.normalTexture,
                       mat.emissiveTexture,
                       mat.occlusionTexture)

            for img in imgRefs:
                if img is not None:
                    if img.index not in nodeTextures.keys():
                        textureFile = os.path.join(
                            os.path.split(gltfFile)[0],
                            gltf.images[img.index].uri)
                        nodeTextures[img.index] = gt.createTexImage2dFromFile(
                            textureFile, transpose=False)

            # material properties
            pbr = mat.pbrMetallicRoughness

            if pbr.roughnessFactor is not None:
                roughnessFactor = pbr.roughnessFactor
            else:
                roughnessFactor = 1e-5

            if pbr.metallicFactor is not None:
                metallicFactor = pbr.metallicFactor
            else:
                metallicFactor = 1e-5

            if pbr.baseColorFactor:
                baseColorFactor = pbr.baseColorFactor
            else:
                baseColorFactor = (1, 1, 1)

            if mat.emissiveFactor:
                emissiveFactor = mat.emissiveFactor
            else:
                emissiveFactor = (1, 1, 1)

            colorTexture = pbr.baseColorTexture
            if colorTexture is not None:
                colorTexture = nodeTextures[colorTexture.index]

            metallicRoughnessTexture = pbr.metallicRoughnessTexture
            if metallicRoughnessTexture is not None:
                metallicRoughnessTexture = \
                    nodeTextures[metallicRoughnessTexture.index]

            normalTexture = mat.normalTexture
            if normalTexture is not None:
                normalTexture = nodeTextures[normalTexture.index]

            emissiveTexture = mat.emissiveTexture
            if emissiveTexture is not None:
                emissiveTexture = nodeTextures[emissiveTexture.index]

            occlusionTexture = mat.occlusionTexture
            if occlusionTexture is not None:
                occlusionTexture = nodeTextures[occlusionTexture.index]

            self.material[mat.name] = MetallicRoughnessMaterial(
                self.win,
                roughnessFactor=roughnessFactor,
                metallicFactor=metallicFactor,
                metallicRoughnessTexture=metallicRoughnessTexture,
                color=baseColorFactor,
                colorTexture=colorTexture,
                normalTexture=normalTexture,
                emissiveTexture=emissiveTexture,
                occulusionTexture=occlusionTexture,
                emissiveFactor=emissiveFactor,
                diffuseIBL=self.diffuseIBL,
                hdr=True,
                toneMap=None,
                meshFlags=self._meshAttribFlags
            )


        self._vao = materialVAOs

    def draw(self, win=None):
        """Draw the mesh.

        Parameters
        ----------
        win : `~psychopy.visual.Window`
            Window this stimulus is associated with. Stimuli cannot be shared
            across windows unless they share the same context.

        """
        if win is None:
            win = self.win
        else:
            self._selectWindow(win)
        #GL.glPushMatrix()
        #GL.glMultTransposeMatrixf(at.array2pointer(self.thePose.modelMatrix))

        # iterate over materials, draw associated VAOs
        if self.material is not None:

            # if material is a dictionary
            if isinstance(self.material, dict):
                for materialName, materialDesc in self.material.items():
                    materialDesc.begin(self.thePose.getModelMatrix())
                    gt.drawVAO(self._vao[materialName], GL.GL_TRIANGLES)
                    materialDesc.end()
            else:
                # material is a single item

                self.material.begin(self.thePose.modelMatrix)
                for materialName, _ in self._vao.items():
                    gt.drawVAO(self._vao[materialName], GL.GL_TRIANGLES)
                self.material.end()
        #GL.glPopMatrix()
