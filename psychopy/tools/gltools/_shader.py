#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Classes and functions for working with OpenGL shader programs and objects.

Note that this API is **unstable** and may change without notice as improvements
are made to PsychoPy's graphics API to utilize shaders more often.

"""

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2020 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

__all__ = [
    'createProgram',
    'createProgramObjectARB',
    'compileShader',
    'compileShaderObjectARB',
    'embedShaderSourceDefs',
    'deleteObject',
    'deleteObjectARB',
    'attachShader',
    'attachObjectARB',
    'detachShader',
    'detachObjectARB',
    'linkProgram',
    'linkProgramObjectARB',
    'validateProgram',
    'validateProgramARB',
    'useProgram',
    'useProgramObjectARB',
    'getInfoLog',
    'getUniformLocations',
    'getAttribLocations'
]

import ctypes
import sys
import os
from ._glenv import OpenGL
import psychopy.logging as logging

GL = OpenGL.gl


# ----------------------
# Shader Program Classes
# ----------------------
#

class Shader(object):
    """Class representing single stage of a GLSL shader program.

    Parameters
    ----------
    name : int or GLenum
        OpenGL handle (or name) for the shader program.
    shaderType : int or GLenum
        Symbolic constant representing the shader type.
    legacy : bool
        Use the older style shader format, mostly for compatibility with legacy
        hardware that does not support OpenGL 3.3 of higher.
    isCompiled : bool
        Has this shader been compiled yet?

    """
    __slots__ = ['_name', '_shaderType', '_legacy', '_isCompiled']

    def __init__(self, name, shaderType, legacy=False, isCompiled=False):
        self._name = name
        self._shaderType = shaderType
        self._legacy = legacy
        self._isCompiled = isCompiled

    @property
    def name(self):
        """OpenGL handle or name for this shader object (`int`).
        """
        return self._name

    @property
    def legacy(self):
        """Is this a legacy shader program (`int`)? If so, this object cannot be
        linked to non-legacy `Program` objects.
        """
        return self._legacy

    @property
    def isCompiled(self):
        """Has the shader program been compiled successfully (`bool`)? If so,
        then the shader program can be linked to a `Program` object.

        """
        return self._isCompiled

    @staticmethod
    def createFromSource(shaderSrc, shaderType, legacy=False):
        """Load shader GLSL source code from a text buffer and create a new
        shader program object.

        Parameters
        ----------
        shaderSrc : str
            GLSL source code text.
        shaderType : GLenum, int or str
            Symbolic constant representing the shader type.
        legacy : bool

        Returns
        -------
        Shader
            Shader object.

        """
        # create a new shader program object handle in OpenGL
        if not legacy:
            shaderId = createShader(shaderType)
        else:
            shaderId = createShaderObjectARB(shaderType)

        # create the object for the user
        toReturn = Shader(shaderId, shaderType=shaderType, legacy=legacy)
        toReturn.shaderSource(shaderSrc)

        return toReturn

    @staticmethod
    def createFromFile(filename, shaderType, legacy=False):
        """Load shader GLSL source code from file and create a new shader
        program object.

        Parameters
        ----------
        filename : str
            Path to GLSL source code.
        shaderType : GLenum, int or str
            Symbolic constant representing the shader type.
        legacy : bool

        Returns
        -------
        Shader
            Shader object.

        """
        # check if the file exists
        if not os.path.isfile(filename):
            raise FileNotFoundError(
                "Cannot find shader source file `{}`.".format(filename))

        # open the file and get the text
        shaderSrcLines = []
        with open(filename, 'r') as f:
            if f.readable():
                shaderSrcLines = f.readlines()

        # check the version
        if not shaderSrcLines[0].startswith('#version '):
            logging.warning(
                'Shader source file missing `#version` directive. This may '
                'cause compilation to fail on some platforms.'
            )

        return Shader.createFromSource(
            "".join(shaderSrcLines),
            shaderType=shaderType,
            legacy=legacy
        )

    def shaderSource(self, code):
        """Replace or set the shader source code.

        Parameters
        ----------
        code : str
            Shader GLSL source code appropriate for the shader type.

        """
        if not self._legacy:
            shaderSource(self._name, code)
        else:
            shaderSourceARB(self._name, code)

    def compile(self, raiseErr=False):
        """Compile shader GLSL code. Shader objects can then be attached to
        programs an made executable on their respective processors.

        Parameters
        ----------
        raiseErr : bool
            Raise an error if the shader program fails to compile. If `False`
            this method will return a value indicating success.

        Returns
        -------
        bool
            Compilation of the shader program was successful or not. Only
            returned if `raiseErr=False`.

        """
        if not self._legacy:
            result = compileShader(self._name)
        else:
            result = compileShaderObjectARB(self._name)

        if not result:
            errorLog = getInfoLog(self._name) + '\n'
            if raiseErr:  # failed to compile for whatever reason
                sys.stderr.write(errorLog)
                deleteObject(self._name)
                raise RuntimeError(
                    "Shader compilation failed, check log output.")
            else:
                logging.error("Failed to compile shader program.")

        # flag that the shader has been compiled
        self._isCompiled = result

        return self._isCompiled

    # @property
    # def defines(self):
    #     """Mapping of pre-processor variable names and values to define
    #     (`dict`).
    #
    #     Examples
    #     --------
    #     Set a pre-processor variable named `MAX_LIGHTS` to some value::
    #
    #         shaderCode.defines["MAX_LIGHTS"] = 4
    #
    #     Will result in the following line being inserted into the GLSL source
    #     code::
    #
    #         #define MAX_LIGHTS 4
    #
    #     """
    #     return self._defines

    # @property
    # def code(self):
    #     """GLSL source code listing after embedding `defines` (`str`)."""
    #     return self._embedShaderSourceDefs()

    def __del__(self):
        pass


class Program(object):
    """Class representing a shader program.

    Parameters
    ----------
    name : int
        Handle for the shader program.

    """
    __slots__ = [
        '_name',
        '_legacy',
        '_compiled'
    ]

    def __init__(self, name, legacy=False):
        self._name = name
        self._legacy = legacy

    @staticmethod
    def create(legacy=False):
        """Create a new shader program object.

        Returns
        -------
        Program
            Shader program object.

        """
        progHandle = \
            GL.glCreateProgramObjectARB() if legacy else GL.glCreateProgram()

        return Program(progHandle, legacy=legacy)

    @property
    def compiled(self):
        """`True` if all attached shader programs have been successfully
        compiled (`bool`).
        """
        return self._compiled

    def use(self):
        """Install this shader program object into the current context.
        """
        GL.glUseProgram(self._name)


nullProgram = Program(0)


# -------------------------------
# Shader Program Helper Functions
# -------------------------------
#

def createProgram():
    """Create an empty program object for shaders.

    Returns
    -------
    int
        OpenGL program object handle retrieved from a `glCreateProgram` call.

    Examples
    --------
    Building a program with vertex and fragment shader attachments::

        myProgram = createProgram()  # new shader object

        # compile vertex and fragment shader sources
        vertexShader = compileShader(vertShaderSource, GL.GL_VERTEX_SHADER)
        fragmentShader = compileShader(fragShaderSource, GL.GL_FRAGMENT_SHADER)

        # attach shaders to program
        attachShader(myProgram, vertexShader)
        attachShader(myProgram, fragmentShader)

        # link the shader, makes `myProgram` attachments executable by their
        # respective processors and available for use
        linkProgram(myProgram)

        # optional, validate the program
        validateProgram(myProgram)

        # optional, detach and discard shader objects
        detachShader(myProgram, vertexShader)
        detachShader(myProgram, fragmentShader)

        deleteObject(vertexShader)
        deleteObject(fragmentShader)

    You can install the program for use in the current rendering state by
    calling::

        useProgram(myShader) # OR glUseProgram(myShader)
        # set uniforms/attributes and start drawing here ...

    """
    return GL.glCreateProgram()


def createProgramObjectARB():
    """Create an empty program object for shaders.

    This creates an *Architecture Review Board* (ARB) program variant which is
    compatible with older GLSL versions and OpenGL coding practices (eg.
    immediate mode) on some platforms. Use *ARB variants of shader helper
    functions (eg. `compileShaderObjectARB` instead of `compileShader`) when
    working with these ARB program objects. This was included for legacy support
    of existing PsychoPy shaders. However, it is recommended that you use
    :func:`createShader` and follow more recent OpenGL design patterns for new
    code (if possible of course).

    Returns
    -------
    int
        OpenGL program object handle retrieved from a `glCreateProgramObjectARB`
        call.

    Examples
    --------
    Building a program with vertex and fragment shader attachments::

        myProgram = createProgramObjectARB()  # new shader object

        # compile vertex and fragment shader sources
        vertexShader = compileShaderObjectARB(
            vertShaderSource, GL.GL_VERTEX_SHADER_ARB)
        fragmentShader = compileShaderObjectARB(
            fragShaderSource, GL.GL_FRAGMENT_SHADER_ARB)

        # attach shaders to program
        attachObjectARB(myProgram, vertexShader)
        attachObjectARB(myProgram, fragmentShader)

        # link the shader, makes `myProgram` attachments executable by their
        # respective processors and available for use
        linkProgramObjectARB(myProgram)

        # optional, validate the program
        validateProgramARB(myProgram)

        # optional, detach and discard shader objects
        detachObjectARB(myProgram, vertexShader)
        detachObjectARB(myProgram, fragmentShader)

        deleteObjectARB(vertexShader)
        deleteObjectARB(fragmentShader)

    Use the program in the current OpenGL state::

        useProgramObjectARB(myProgram)

    """
    return GL.glCreateProgramObjectARB()


def createShader(shaderType):
    """Create a new shader object.

    Parameters
    ----------
    shaderType : GLenum, int or str
        Shader program type (eg. `GL_VERTEX_SHADER`, `GL_FRAGMENT_SHADER`,
        `GL_GEOMETRY_SHADER`, etc.)

    Returns
    -------
    int
        OpenGL shader object handle retrieved from a `glCreateShader` call.

    """
    return GL.glCreateShader(shaderType)


def createShaderObjectARB(shaderType):
    """Create a new shader object (legacy).

    Parameters
    ----------
    shaderType : GLenum, int or str
        Shader program type. Must be *_ARB enums such as `GL_VERTEX_SHADER_ARB`,
        `GL_FRAGMENT_SHADER_ARB`, `GL_GEOMETRY_SHADER_ARB`, etc.

    Returns
    -------
    int
        OpenGL shader object handle retrieved from a `glCreateShaderObjectARB`
        call.

    """
    return GL.glCreateShaderObjectARB(shaderType)


def shaderSource(shaderId, code):
    """Replaces the source code inside a shader object.

    Parameters
    ----------
    shaderId : int
        Handle of shader object to attach. Must have originated from a
        :func:`createShader` or `glCreateShader` call.
    code : str
        Text buffer containing the GLSL source code appropriate for the shader
        type.

    """
    if isinstance(code, (list, tuple,)):
        nSources = len(code)
        srcPtr = (ctypes.c_char_p * nSources)()
        srcPtr[:] = [i.encode() for i in code]
    else:
        nSources = 1
        srcPtr = ctypes.c_char_p(code.encode())

    GL.glShaderSource(
        shaderId,
        nSources,
        ctypes.cast(
            ctypes.byref(srcPtr),
            ctypes.POINTER(ctypes.POINTER(ctypes.c_char))),
        None)


def shaderSourceARB(shaderId, code):
    """Replaces the source code inside a shader object (legacy).

    Parameters
    ----------
    shader : int
        Handle of shader object to attach. Must have originated from a
        :func:`createShaderARB` or `glCreateShaderObjectARB` call.
    code : str
        Text buffer containing the GLSL source code appropriate for the shader
        type.

    """
    if isinstance(code, (list, tuple,)):
        nSources = len(code)
        srcPtr = (ctypes.c_char_p * nSources)()
        srcPtr[:] = [i.encode() for i in code]
    else:
        nSources = 1
        srcPtr = ctypes.c_char_p(code.encode())

    GL.glShaderSourceARB(
        shaderId,
        nSources,
        ctypes.cast(
            ctypes.byref(srcPtr),
            ctypes.POINTER(ctypes.POINTER(ctypes.c_char))),
        None)


def compileShader(shaderId):
    """Compile shader GLSL code and return a shader object. Shader objects can
    then be attached to programs an made executable on their respective
    processors.

    Parameters
    ----------
    shaderId : int
        Handle of shader object to attach. Must have originated from a
        :func:`createShader` or `glCreateShader` call.

    Returns
    -------
    int
        OpenGL shader object handle retrieved from a `glCreateShader` call.

    Examples
    --------
    Compiling GLSL source code and attaching it to a program object::

        # GLSL vertex shader source
        vertexSource = \
            '''
            #version 330 core
            layout (location = 0) in vec3 vertexPos;

            void main()
            {
                gl_Position = vec4(vertexPos, 1.0);
            }
            '''
        # create a new shader object of type `GL_VERTEX_SHADER`
        vertexShader = createShader(GL_VERTEX_SHADER)
        # set shader sources
        shaderSource(vertexShader, vertexSource)
        # compile it
        vertexShader = compileShader(vertexShader, GL.GL_VERTEX_SHADER)
        attachShader(myProgram, vertexShader)  # attach it to `myProgram`

    """
    GL.glCompileShader(shaderId)

    result = GL.GLint()
    GL.glGetShaderiv(
        shaderId, GL.GL_COMPILE_STATUS, ctypes.byref(result))

    if result.value == GL.GL_FALSE:  # failed to compile for whatever reason
        sys.stderr.write(getInfoLog(shaderId) + '\n')
        deleteObject(shaderId)
        raise RuntimeError("Shader compilation failed, check log output.")

    return shaderId


def compileShaderObjectARB(shaderId):
    """Compile shader GLSL code and return a shader object. Shader objects can
    then be attached to programs an made executable on their respective
    processors.

    Parameters
    ----------
    shaderId : int
        Handle of shader object to attach. Must have originated from a
        :func:`createShaderARB` or `glCreateShaderObjectARB` call.

    Returns
    -------
    int
        OpenGL shader object handle retrieved from a `glCreateShaderObjectARB`
        call.

    """
    GL.glCompileShaderARB(shaderId)

    result = GL.GLint()
    GL.glGetObjectParameterivARB(
        shaderId, GL.GL_OBJECT_COMPILE_STATUS_ARB, ctypes.byref(result))

    compileFailed = result.value == GL.GL_FALSE

    if compileFailed:  # failed to compile for whatever reason
        sys.stderr.write(getInfoLog(shaderId) + '\n')
        deleteObjectARB(shaderId)
        raise RuntimeError("Shader compilation failed, check log output.")

    return compileFailed


def embedShaderSourceDefs(shaderSrc, defs):
    """Embed preprocessor definitions into GLSL source code.

    This function generates and inserts ``#define`` statements into existing
    GLSL source code, allowing one to use GLSL preprocessor statements to alter
    program source at compile time.

    Passing ``{'MAX_LIGHTS': 8, 'NORMAL_MAP': False}`` to `defs` will create and
    insert the following ``#define`` statements into `shaderSrc`::

        #define MAX_LIGHTS 8
        #define NORMAL_MAP 0

    As per the GLSL specification, the ``#version`` directive must be specified
    at the top of the file before any other statement (with the exception of
    comments). If a ``#version`` directive is present, generated ``#define``
    statements will be inserted starting at the following line. If no
    ``#version`` directive is found in `shaderSrc`, the statements will be
    prepended to `shaderSrc`.

    Using preprocessor directives, multiple shader program routines can reside
    in the same source text if enclosed by ``#ifdef`` and ``#endif`` statements
    as shown here::

        #ifdef VERTEX
            // vertex shader code here ...
        #endif

        #ifdef FRAGMENT
            // pixel shader code here ...
        #endif

    Both the vertex and fragment shader can be built from the same GLSL code
    listing by setting either ``VERTEX`` or ``FRAGMENT`` as `True`::

        vertexShader = gltools.compileShaderObjectARB(
            gltools.embedShaderSourceDefs(glslSource, {'VERTEX': True}),
            GL.GL_VERTEX_SHADER_ARB)
        fragmentShader = gltools.compileShaderObjectARB(
            gltools.embedShaderSourceDefs(glslSource, {'FRAGMENT': True}),
            GL.GL_FRAGMENT_SHADER_ARB)

    In addition, ``#ifdef`` blocks can be used to prune render code paths. Here,
    this GLSL snippet shows a shader having diffuse color sampled from a texture
    is conditional on ``DIFFUSE_TEXTURE`` being `True`, if not, the material
    color is used instead::

        #ifdef DIFFUSE_TEXTURE
            uniform sampler2D diffuseTexture;
        #endif
        ...
        #ifdef DIFFUSE_TEXTURE
            // sample color from texture
            vec4 diffuseColor = texture2D(diffuseTexture, gl_TexCoord[0].st);
        #else
            // code path for no textures, just output material color
            vec4 diffuseColor = gl_FrontMaterial.diffuse;
        #endif

    This avoids needing to provide two separate GLSL program sources to build
    shaders to handle cases where a diffuse texture is or isn't used.

    Parameters
    ----------
    shaderSrc : str
        GLSL shader source code.
    defs : dict
       Names and values to generate ``#define`` statements. Keys must all be
       valid GLSL preprocessor variable names of type `str`. Values can only be
       `int`, `float`, `str`, `bytes`, or `bool` types. Boolean values `True`
       and `False` are converted to integers `1` and `0`, respectively.

    Returns
    -------
    str
        GLSL source code with ``#define`` statements inserted.

    Examples
    --------
    Defining ``MAX_LIGHTS`` as `8` in a fragment shader program at runtime::

        fragSrc = embedShaderSourceDefs(fragSrc, {'MAX_LIGHTS': 8})
        fragShader = compileShaderObjectARB(fragSrc, GL_FRAGMENT_SHADER_ARB)

    """
    # generate GLSL `#define` statements
    glslDefSrc = ""
    for varName, varValue in defs.items():
        if not isinstance(varName, str):
            raise ValueError("Definition name must be type `str`.")

        if isinstance(varValue, (int, bool,)):
            varValue = int(varValue)
        elif isinstance(varValue, (float,)):
            pass
            # varValue = varValue
        elif isinstance(varValue, bytes):
            varValue = '"{}"'.format(varValue.decode('UTF-8'))
        elif isinstance(varValue, str):
            varValue = '"{}"'.format(varValue)
        else:
            raise TypeError("Invalid type for value of `{}`.".format(varName))

        glslDefSrc += '#define {n} {v}\n'.format(n=varName, v=varValue)

    # find where the `#version` directive occurs
    versionDirIdx = shaderSrc.find("#version")
    if versionDirIdx != -1:
        srcSplitIdx = shaderSrc.find("\n", versionDirIdx) + 1  # after newline
        srcOut = shaderSrc[:srcSplitIdx] + glslDefSrc + shaderSrc[srcSplitIdx:]
    else:
        # no version directive in source, just prepend defines
        srcOut = glslDefSrc + shaderSrc

    return srcOut


def deleteObject(obj):
    """Delete a shader or program object.

    Parameters
    ----------
    obj : int
        Shader or program object handle. Must have originated from a
        :func:`createProgram`, :func:`compileShader`, `glCreateProgram` or
        `glCreateShader` call.

    """
    if GL.glIsShader(obj):
        GL.glDeleteShader(obj)
    elif GL.glIsProgram(obj):
        GL.glDeleteProgram(obj)
    else:
        raise ValueError('Cannot delete, not a program or shader object.')


def deleteObjectARB(obj):
    """Delete a program or shader object.

    Parameters
    ----------
    obj : int
        Program handle to attach `shader` to. Must have originated from a
        :func:`createProgramObjectARB`, :func:`compileShaderObjectARB,
        `glCreateProgramObjectARB` or `glCreateShaderObjectARB` call.

    """
    GL.glDeleteObjectARB(obj)


def attachShader(program, shader):
    """Attach a shader to a program.

    Parameters
    ----------
    program : int
        Program handle to attach `shader` to. Must have originated from a
        :func:`createProgram` or `glCreateProgram` call.
    shader : int
        Handle of shader object to attach. Must have originated from a
        :func:`compileShader` or `glCreateShader` call.

    """
    if not GL.glIsProgram(program):
        raise ValueError("Value `program` is not a program object.")
    elif not GL.glIsShader(shader):
        raise ValueError("Value `shader` is not a shader object.")
    else:
        GL.glAttachShader(program, shader)


def attachObjectARB(program, shader):
    """Attach a shader object to a program.

    Parameters
    ----------
    program : int
        Program handle to attach `shader` to. Must have originated from a
        :func:`createProgramObjectARB` or `glCreateProgramObjectARB` call.
    shader : int
        Handle of shader object to attach. Must have originated from a
        :func:`compileShaderObjectARB` or `glCreateShaderObjectARB` call.

    """
    if not GL.glIsProgram(program):
        raise ValueError("Value `program` is not a program object.")
    elif not GL.glIsShader(shader):
        raise ValueError("Value `shader` is not a shader object.")
    else:
        GL.glAttachObjectARB(program, shader)


def detachShader(program, shader):
    """Detach a shader object from a program.

    Parameters
    ----------
    program : int
        Program handle to detach `shader` from. Must have originated from a
        :func:`createProgram` or `glCreateProgram` call.
    shader : int
        Handle of shader object to detach. Must have been previously attached
        to `program`.

    """
    if not GL.glIsProgram(program):
        raise ValueError("Value `program` is not a program.")
    elif not GL.glIsShader(shader):
        raise ValueError("Value `shader` is not a shader object.")
    else:
        GL.glDetachShader(program, shader)


def detachObjectARB(program, shader):
    """Detach a shader object from a program.

    Parameters
    ----------
    program : int
        Program handle to detach `shader` from. Must have originated from a
        :func:`createProgramObjectARB` or `glCreateProgramObjectARB` call.
    shader : int
        Handle of shader object to detach. Must have been previously attached
        to `program`.

    """
    if not GL.glIsProgram(program):
        raise ValueError("Value `program` is not a program.")
    elif not GL.glIsShader(shader):
        raise ValueError("Value `shader` is not a shader object.")
    else:
        GL.glDetachObjectARB(program, shader)


def linkProgram(program):
    """Link a shader program. Any attached shader objects will be made
    executable to run on associated GPU processor units when the program is
    used.

    Parameters
    ----------
    program : int
        Program handle to link. Must have originated from a
        :func:`createProgram` or `glCreateProgram` call.

    Raises
    ------
    ValueError
        Specified `program` handle is invalid.
    RuntimeError
        Program failed to link. Log will be dumped to `sterr`.

    """
    if GL.glIsProgram(program):
        GL.glLinkProgram(program)
    else:
        raise ValueError("Value `program` is not a shader program.")

    # check for errors
    result = GL.GLint()
    GL.glGetProgramiv(program, GL.GL_LINK_STATUS, ctypes.byref(result))

    if result.value == GL.GL_FALSE:  # failed to link for whatever reason
        sys.stderr.write(getInfoLog(program) + '\n')
        raise RuntimeError(
            'Failed to link shader program. Check log output.')


def linkProgramObjectARB(program):
    """Link a shader program object. Any attached shader objects will be made
    executable to run on associated GPU processor units when the program is
    used.

    Parameters
    ----------
    program : int
        Program handle to link. Must have originated from a
        :func:`createProgramObjectARB` or `glCreateProgramObjectARB` call.

    Raises
    ------
    ValueError
        Specified `program` handle is invalid.
    RuntimeError
        Program failed to link. Log will be dumped to `sterr`.

    """
    if GL.glIsProgram(program):
        GL.glLinkProgramARB(program)
    else:
        raise ValueError("Value `program` is not a shader program.")

    # check for errors
    result = GL.GLint()
    GL.glGetObjectParameterivARB(
        program,
        GL.GL_OBJECT_LINK_STATUS_ARB,
        ctypes.byref(result))

    if result.value == GL.GL_FALSE:  # failed to link for whatever reason
        sys.stderr.write(getInfoLog(program) + '\n')
        raise RuntimeError(
            'Failed to link shader program. Check log output.')


def validateProgram(program):
    """Check if the program can execute given the current OpenGL state.

    Parameters
    ----------
    program : int
        Handle of program to validate. Must have originated from a
        :func:`createProgram` or `glCreateProgram` call.

    """
    # check validation info
    result = GL.GLint()
    GL.glValidateProgram(program)
    GL.glGetProgramiv(program, GL.GL_VALIDATE_STATUS, ctypes.byref(result))

    if result.value == GL.GL_FALSE:
        sys.stderr.write(getInfoLog(program) + '\n')
        raise RuntimeError('Shader program validation failed.')


def validateProgramARB(program):
    """Check if the program can execute given the current OpenGL state. If
    validation fails, information from the driver is dumped giving the reason.

    Parameters
    ----------
    program : int
        Handle of program object to validate. Must have originated from a
        :func:`createProgramObjectARB` or `glCreateProgramObjectARB` call.

    """
    # check validation info
    result = GL.GLint()
    GL.glValidateProgramARB(program)
    GL.glGetObjectParameterivARB(
        program,
        GL.GL_OBJECT_VALIDATE_STATUS_ARB,
        ctypes.byref(result))

    if result.value == GL.GL_FALSE:
        sys.stderr.write(getInfoLog(program) + '\n')
        raise RuntimeError('Shader program validation failed.')


def useProgram(program):
    """Use a program object's executable shader attachments in the current
    OpenGL rendering state.

    In order to install the program object in the current rendering state, a
    program must have been successfully linked by calling :func:`linkProgram` or
    `glLinkProgram`.

    Parameters
    ----------
    program : int
        Handle of program to use. Must have originated from a
        :func:`createProgram` or `glCreateProgram` call and was successfully
        linked. Passing `0` or `None` disables shader programs.

    Examples
    --------
    Install a program for use in the current rendering state::

        useProgram(myShader)

    Disable the current shader program by specifying `0`::

        useProgram(0)

    """
    if program is None:
        program = 0

    if GL.glIsProgram(program) or program == 0:
        GL.glUseProgram(program)
    else:
        raise ValueError('Specified `program` is not a program object.')


def useProgramObjectARB(program):
    """Use a program object's executable shader attachments in the current
    OpenGL rendering state.

    In order to install the program object in the current rendering state, a
    program must have been successfully linked by calling
    :func:`linkProgramObjectARB` or `glLinkProgramObjectARB`.

    Parameters
    ----------
    program : int
        Handle of program object to use. Must have originated from a
        :func:`createProgramObjectARB` or `glCreateProgramObjectARB` call and
        was successfully linked. Passing `0` or `None` disables shader programs.

    Examples
    --------
    Install a program for use in the current rendering state::

        useProgramObjectARB(myShader)

    Disable the current shader program by specifying `0`::

        useProgramObjectARB(0)

    Notes
    -----
    Some drivers may support using `glUseProgram` for objects created by calling
    :func:`createProgramObjectARB` or `glCreateProgramObjectARB`.

    """
    if program is None:
        program = 0

    if GL.glIsProgram(program) or program == 0:
        GL.glUseProgramObjectARB(program)
    else:
        raise ValueError('Specified `program` is not a program object.')


def getInfoLog(obj):
    """Get the information log from a shader or program.

    This retrieves a text log from the driver pertaining to the shader or
    program. For instance, a log can report shader compiler output or validation
    results. The verbosity and formatting of the logs are platform-dependent,
    where one driver may provide more information than another.

    This function works with both standard and ARB program object variants.

    Parameters
    ----------
    obj : int
        Program or shader to retrieve a log from. If a shader, the handle must
        have originated from a :func:`compileShader`, `glCreateShader`,
        :func:`createProgramObjectARB` or `glCreateProgramObjectARB` call. If a
        program, the handle must have came from a :func:`createProgram`,
        :func:`createProgramObjectARB`, `glCreateProgram` or
        `glCreateProgramObjectARB` call.

    Returns
    -------
    str
        Information log data. Logs can be empty strings if the driver has no
        information available.

    """
    logLength = GL.GLint()
    if GL.glIsShader(obj) == GL.GL_TRUE:
        GL.glGetShaderiv(
            obj, GL.GL_INFO_LOG_LENGTH, ctypes.byref(logLength))
    elif GL.glIsProgram(obj) == GL.GL_TRUE:
        GL.glGetProgramiv(
            obj, GL.GL_INFO_LOG_LENGTH, ctypes.byref(logLength))
    else:
        raise ValueError(
            "Specified value of `obj` is not a shader or program.")

    logBuffer = ctypes.create_string_buffer(logLength.value)
    GL.glGetShaderInfoLog(obj, logLength, None, logBuffer)

    return logBuffer.value.decode('UTF-8')


def getUniformLocations(program, builtins=False):
    """Get uniform names and locations from a given shader program object.

    This function works with both standard and ARB program object variants.

    Parameters
    ----------
    program : int
        Handle of program to retrieve uniforms. Must have originated from a
        :func:`createProgram`, :func:`createProgramObjectARB`, `glCreateProgram`
        or `glCreateProgramObjectARB` call.
    builtins : bool, optional
        Include built-in GLSL uniforms (eg. `gl_ModelViewProjectionMatrix`).
        Default is `False`.

    Returns
    -------
    dict
        Uniform names and locations.

    """
    if not GL.glIsProgram(program):
        raise ValueError(
            "Specified value of `program` is not a program object handle.")

    arraySize = GL.GLint()
    nameLength = GL.GLsizei()

    # cache uniform locations to avoid looking them up before setting them
    nUniforms = GL.GLint()
    GL.glGetProgramiv(program, GL.GL_ACTIVE_UNIFORMS, ctypes.byref(nUniforms))

    unifLoc = None
    if nUniforms.value > 0:
        maxUniformLength = GL.GLint()
        GL.glGetProgramiv(
            program,
            GL.GL_ACTIVE_UNIFORM_MAX_LENGTH,
            ctypes.byref(maxUniformLength))

        unifLoc = {}
        for uniformIdx in range(nUniforms.value):
            unifType = GL.GLenum()
            unifName = (GL.GLchar * maxUniformLength.value)()

            GL.glGetActiveUniform(
                program,
                uniformIdx,
                maxUniformLength,
                ctypes.byref(nameLength),
                ctypes.byref(arraySize),
                ctypes.byref(unifType),
                unifName)

            # get location
            loc = GL.glGetUniformLocation(program, unifName)
            # don't include if -1, these are internal types like 'gl_Vertex'
            if not builtins:
                if loc != -1:
                    unifLoc[unifName.value] = loc
            else:
                unifLoc[unifName.value] = loc

    return unifLoc


def getAttribLocations(program, builtins=False):
    """Get attribute names and locations from the specified program object.

    This function works with both standard and ARB program object variants.

    Parameters
    ----------
    program : int
        Handle of program to retrieve attributes. Must have originated from a
        :func:`createProgram`, :func:`createProgramObjectARB`, `glCreateProgram`
        or `glCreateProgramObjectARB` call.
    builtins : bool, optional
        Include built-in GLSL attributes (eg. `gl_Vertex`). Default is `False`.

    Returns
    -------
    dict
        Attribute names and locations.

    """
    if not GL.glIsProgram(program):
        raise ValueError(
            "Specified value of `program` is not a program object handle.")

    arraySize = GL.GLint()
    nameLength = GL.GLsizei()

    nAttribs = GL.GLint()
    GL.glGetProgramiv(program, GL.GL_ACTIVE_ATTRIBUTES, ctypes.byref(nAttribs))

    attribLoc = None
    if nAttribs.value > 0:
        maxAttribLength = GL.GLint()
        GL.glGetProgramiv(
            program,
            GL.GL_ACTIVE_ATTRIBUTE_MAX_LENGTH,
            ctypes.byref(maxAttribLength))

        attribLoc = {}
        for attribIdx in range(nAttribs.value):
            attribType = GL.GLenum()
            attribName = (GL.GLchar * maxAttribLength.value)()

            GL.glGetActiveAttrib(
                program,
                attribIdx,
                maxAttribLength,
                ctypes.byref(nameLength),
                ctypes.byref(arraySize),
                ctypes.byref(attribType),
                attribName)

            # get location
            loc = GL.glGetAttribLocation(program, attribName.value)
            # don't include if -1, these are internal types like 'gl_Vertex'
            if not builtins:
                if loc != -1:
                    attribLoc[attribName.value] = loc
            else:
                attribLoc[attribName.value] = loc

    return attribLoc


if __name__ == "__main__":
    pass
