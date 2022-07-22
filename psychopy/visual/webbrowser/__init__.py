#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Web browser stimulus to display HTML and web content using Chromium."""

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2022 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

import pyglet
pyglet.options['debug_gl'] = False
import ctypes
GL = pyglet.gl

import platform
import numpy
from PIL import Image
import psychopy  # so we can get the __path__
from psychopy import logging, colors, layout
from psychopy.tools.attributetools import attributeSetter, setAttribute
from psychopy.visual.basevisual import BaseVisualStim
from psychopy.visual.basevisual import (ContainerMixin, ColorMixin,
                                        TextureMixin)

try:
    from cefpython3 import cefpython as cef
except ImportError:
    raise ImportError()

# is CEF is initialized?
_cefInitialized = False

if platform.platform() == 'Darwin':
    try:
        import AppKit
    except ImportError:
        raise ImportError()


class LoadHandler(object):
    """Simple handler for loading URLs."""

    def OnLoadingStateChange(self, is_loading, **_):
        if not is_loading:
            logging.info("Page loading complete")

    def OnLoadError(self, frame, failed_url, **_):
        if not frame.IsMain():
            return
        logging.error("Failed to load %s" % failed_url)


class RenderHandler(object):
    """
    Handler for rendering web pages to the
    screen via SDL2.

    The object's texture property is exposed
    to allow the main rendering loop to access
    the SDL2 texture.
    """

    def __init__(self, renderer, width, height):
        self.__width = width
        self.__height = height
        self.__renderer = renderer
        self.texture = None

    def GetViewRect(self, rect_out, **_):
        rect_out.extend([0, 0, self.__width, self.__height])
        return True

    def OnPaint(self, element_type, paint_buffer, **_):
        """
        Using the pixel data from CEF's offscreen rendering
        the data is converted by PIL into a SDL2 surface
        which can then be rendered as a SDL2 texture.
        """
        if element_type == cef.PET_VIEW:
            image = Image.frombuffer(
                'RGBA',
                (self.__width, self.__height),
                paint_buffer.GetString(mode="rgba", origin="top-left"),
                'raw',
                'BGRA'
            )
            mode = image.mode



class BrowserStim(BaseVisualStim, ContainerMixin, ColorMixin, TextureMixin):
    """Embed a web browser within a :class:`psychopy.visual.Window`.

    Locally this class uses the Chromium Embedded Framework (CEF) to render rich
    web content within a PsychoPy window. One can display any content which
    Chromium is capable of displaying, such as web pages (HTML5), PDF documents,
    videos and images.

    Parameters
    ----------
    win : :class:`psychopy.visual.Window`
        A window which this stimulus can be drawn to.
    url : str or None
        Initial document to load and show. This can be a URL or path (local or
        network).

    """
    def __init__(self,
                 win,
                 url=None,
                 mask=None,
                 units="",
                 pos=(0.0, 0.0),
                 size=None,
                 anchor="center",
                 ori=0.0,
                 color=(1.0, 1.0, 1.0),
                 colorSpace='rgb',
                 contrast=1.0,
                 opacity=None,
                 depth=0,
                 interpolate=False,
                 flipHoriz=False,
                 flipVert=False,
                 texRes=128,
                 name=None,
                 autoLog=None,
                 maskParams=None):

        # __repr__
        self._initParams = dir()
        self._initParams.remove('self')

        super(BrowserStim, self).__init__(
            win, units=units, name=name, autoLog=False)

        # use shaders if available by default, this is a good thing
        self.__dict__['useShaders'] = win._haveShaders

        # initialise textures for stimulus
        self._texID = GL.GLuint()
        GL.glGenTextures(1, ctypes.byref(self._texID))
        self._maskID = GL.GLuint()
        GL.glGenTextures(1, ctypes.byref(self._maskID))
        self._pixbuffID = GL.GLuint()
        GL.glGenBuffers(1, ctypes.byref(self._pixbuffID))
        self.__dict__['maskParams'] = maskParams
        self.__dict__['mask'] = mask
        # Not pretty (redefined later) but it works!
        self.__dict__['texRes'] = texRes

        # data
        self._browser = None
        self._url = url

        self._initCEF()  # initialize the browser object

    def __repr__(self):
        return f"BrowserStim(win={self.win}, url={self.url})"

    @property
    def url(self):
        """URL or path to the content (`str`). This value changes depending on
        the current state of the browser.
        """
        return self._url  # get this value from the actual CEF handle

    @url.setter
    def url(self, value):
        assert isinstance(value, str), "Value for `.url` must by type `str`."
        self._url = value

    def back(self):
        """Go to the last document visited.
        """
        pass

    def forward(self):
        """Go forward to the next document.
        """
        pass

    def home(self):
        """Return to the first document visited.
        """
        pass

    def _assertCEF(self):
        """Assert that CEF has been initialized.
        """
        if not _cefInitialized:
            raise AssertionError()

    def _initCEF(self):
        """Initialize the CEF backend."""
        global _cefInitialized

        # Initialize CEF, this needs to be done only on the first instance
        if not _cefInitialized:
            switches = {
                # Tweaking OSR performance by setting the same Chromium flags
                # as in upstream cefclient (Issue #240).
                "disable-surfaces": "",
                "disable-gpu": "",
                "disable-gpu-compositing": "",
                "enable-begin-frame-scheduling": "",
            }
            browser_settings = {
                # Tweaking OSR performance (Issue #240)
                "windowless_frame_rate": 100
            }
            cef.Initialize(settings={"windowless_rendering_enabled": True},
                           switches=switches)
            if platform.platform() == 'Darwin':
                AppKit.NSApplication.sharedApplication().setActivationPolicy_(
                    AppKit.NSApplicationActivationPolicyRegular)

            _cefInitialized = True

        # configure and create the off-screen window
        window_info = cef.WindowInfo()
        window_info.SetAsOffscreen(0)

        # create the texture here

        # create the actual browser interface
        self._browser = cef.CreateBrowserSync(
            window_info,
            url="https://www.google.com/",
            settings=browser_settings)

        self._browser.SetClientHandler(LoadHandler())
        # self._browser.SetClientHandler(renderHandler)
        # Must call WasResized at least once to let know CEF that
        # viewport size is available and that OnPaint may be called.
        self._browser.SendFocusEvent(True)
        self._browser.WasResized()

    def _destroyCEF(self):
        """Teardown the CEF instance and do clean-up."""
        pass

    def _pixelTransfer(self):
        """Copy pixel data from the off-screen CEF buffer to an OpenGL texture.
        """
        pass

    def __del__(self):
        pass


if __name__ == "__main__":
    pass
