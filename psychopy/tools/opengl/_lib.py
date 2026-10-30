#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2025 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

"""Linking OpenGL functions on first use.

Each function starts as a `GLFunction` placeholder. The first time one is
called it finds the function in the driver and replaces itself in the
namespace it was published in (`psychopy.tools.opengl`), so later calls made
through that namespace go straight to the `ctypes` function.

Error checking (calling `glGetError()` after each function) is turned on by
setting the `PSYCHOPY_DEBUG_GL` (or `PYGLET_DEBUG_GL`) environment variable.

"""

__all__ = ['GLException', 'GLFunction', 'link', 'publish', 'DEBUG_GL']

import os

from . import _platform
from ._types import FUNCTYPE


def _envFlag(name):
    return os.environ.get(name, '').strip().lower() not in ('', '0', 'false')


#: Check for OpenGL errors after every call.
DEBUG_GL = _envFlag('PSYCHOPY_DEBUG_GL') or _envFlag('PYGLET_DEBUG_GL')


class GLException(Exception):
    """Error from OpenGL, or using a function that isn't available."""


# namespace to replace placeholders in once their function is linked
_namespace = None


def publish(namespace):
    """Set the namespace placeholders replace themselves in once linked.

    Parameters
    ----------
    namespace : dict
        Globals of the module functions are published in.

    """
    global _namespace
    _namespace = namespace


class GLFunction:
    """Placeholder for an OpenGL function, which links it when first called.

    Parameters
    ----------
    name : str
        Name of the function.
    restype : type or None
        `ctypes` return type.
    argtypes : list
        `ctypes` argument types.
    requires : str
        OpenGL version or extension the function is part of, for errors.

    """
    __slots__ = ('__name__', 'restype', 'argtypes', 'requires', '_func')

    def __init__(self, name, restype, argtypes, requires):
        self.__name__ = name
        self.restype = restype
        self.argtypes = argtypes
        self.requires = requires
        self._func = None

    def __repr__(self):
        state = 'linked' if self._func is not None else 'unlinked'
        return f'<GLFunction {self.__name__} ({state})>'

    def link(self):
        """Find the function in the driver.

        Returns
        -------
        ctypes function
            The function. Calls to this placeholder are forwarded to it, and
            it replaces the placeholder in the published namespace.

        Raises
        ------
        GLException
            The driver doesn't have the function, or (on Windows) no context
            is current.

        """
        if self._func is not None:
            return self._func

        address = _platform.getProcAddress(self.__name__)
        if not address:
            # not cached, since (on Windows) it may be found once a context
            # is current
            if _platform.getCurrentContext() is None:
                reason = 'there is no current OpenGL context'
            else:
                reason = f'{self.requires} is not supported'
            raise GLException(
                f'`{self.__name__}` is unavailable, since {reason}.')

        func = FUNCTYPE(self.restype, *self.argtypes)(address)
        func.__name__ = self.__name__
        if DEBUG_GL and self.__name__ != 'glGetError':
            func.errcheck = _getErrcheck(self.__name__)
        self._func = func

        if _namespace is not None and _namespace.get(self.__name__) is self:
            _namespace[self.__name__] = func

        return func

    def __call__(self, *args):
        func = self._func
        if func is None:
            func = self.link()

        return func(*args)


def link(name, restype, argtypes, requires):
    """Create the placeholder for an OpenGL function (see `GLFunction`)."""
    return GLFunction(name, restype, argtypes, requires)


_ERROR_NAMES = {
    0x0500: 'GL_INVALID_ENUM',
    0x0501: 'GL_INVALID_VALUE',
    0x0502: 'GL_INVALID_OPERATION',
    0x0503: 'GL_STACK_OVERFLOW',
    0x0504: 'GL_STACK_UNDERFLOW',
    0x0505: 'GL_OUT_OF_MEMORY',
    0x0506: 'GL_INVALID_FRAMEBUFFER_OPERATION',
}

# `glGetError()` is itself an error between `glBegin()` and `glEnd()`
_inBeginEnd = False


def _checkError(result, func, arguments):
    if _inBeginEnd:
        return result

    error = _namespace['glGetError']()
    if error:
        raise GLException(
            f'{_ERROR_NAMES.get(error, hex(error))} after calling '
            f'`{func.__name__}`.')

    return result


def _errcheckBegin(result, func, arguments):
    global _inBeginEnd
    _inBeginEnd = True

    return result


def _errcheckEnd(result, func, arguments):
    global _inBeginEnd
    _inBeginEnd = False

    return _checkError(result, func, arguments)


def _getErrcheck(name):
    """`errcheck` function for the OpenGL function named `name`."""
    if name == 'glBegin':
        return _errcheckBegin
    if name == 'glEnd':
        return _errcheckEnd

    return _checkError
