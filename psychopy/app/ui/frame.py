#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Classes for main application windows/frames.
"""

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2024 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

import wx
import wx.lib.agw.aui as aui

# default values
DEFAULT_FRAME_SIZE = wx.Size(800, 600)
DEFAULT_FRAME_TITLE = u"PsychoPy"
DEFAULT_AUI_STYLE_FLAGS = (  # flags for AUI
        aui.AUI_MGR_DEFAULT | aui.AUI_MGR_RECTANGLE_HINT)


class BaseAuiFrame(wx.Frame):
    """Base class for AUI managed frames.

    Takes the same arguments as `wx.Frame`. This frame is AUI managed which
    allows for sub-windows to be attached to it. No application logic should be
    implemented in this class, only its sub-classes.

    Parameter
    ---------
    parent : wx.Window or None
        Parent window.
    id : int
        Unique ID for this window, default is `wx.ID_ANY`.
    title : str
        Window title to use. Can be set later.
    pos : ArrayLike or `wx.Position`
        Initial position of the window on the desktop. Default is
        `wx.DefaultPosition`.
    size : ArrayLike or `wx.Size`
        Initial sie of the window in desktop units.
    style : int
        Style flags for the window. Default is the combination of
        `wx.DEFAULT_FRAME_STYLE` and `wx.TAB_TRAVERSAL`.

    """
    def __init__(self,
                 parent,
                 id=wx.ID_ANY,
                 title=DEFAULT_FRAME_TITLE,
                 pos=wx.DefaultPosition,
                 size=DEFAULT_FRAME_SIZE,
                 style=wx.DEFAULT_FRAME_STYLE | wx.TAB_TRAVERSAL):
        # subclass `wx.Frame`
        wx.Frame.__init__(self, parent, id=id, title=title, pos=pos, size=size,
                          style=style)

        # defaults for window
        self.SetSizeHints(wx.DefaultSize, wx.DefaultSize)

        # create the AUI manager and attach it to this window
        self.m_mgr = aui.AuiManager(self, agwFlags=DEFAULT_AUI_STYLE_FLAGS)
        self.m_mgr.Update()

        self.Centre(wx.BOTH)

        # events associated with this window
        self.Bind(aui.EVT_AUI_PANE_ACTIVATED, self.onAuiPaneActivate)
        self.Bind(aui.EVT_AUI_PANE_BUTTON, self.onAuiPaneButton)
        self.Bind(aui.EVT_AUI_PANE_CLOSE, self.onAuiPaneClose)
        self.Bind(aui.EVT_AUI_PANE_MAXIMIZE, self.onAuiPaneMaximize)
        self.Bind(aui.EVT_AUI_PANE_RESTORE, self.onAuiPaneRestore)
        self.Bind(wx.EVT_CLOSE, self.onClose)
        self.Bind(wx.EVT_IDLE, self.onIdle)

    def __del__(self):
        # called when tearing down the window
        self.m_mgr.UnInit()

    # --------------------------------------------------------------------------
    # Class properties and methods
    #

    @property
    def manager(self):
        """Handle of the AUI manager for this frame (`aui.AuiManager`).
        """
        return self.getAuiManager()

    def getAuiManager(self):
        """Get the AUI manager instance for this window.

        Returns
        -------
        aui.AuiManager
            Handle for the AUI manager instance associated with this window.

        """
        return self.m_mgr

    def setTitle(self, title=DEFAULT_FRAME_TITLE, document=None):
        """Set the window title.

        Use this method to set window titles to ensure that PsychoPy windows use
        similar formatting for them.

        Parameters
        ----------
        title : str
            Window title to set. Default is `DEFAULT_FRAME_TITLE`.
        document : str or None
            Optional document file name or path. Will be appended to the title
            bar with a `' - '` separator.

        Examples
        --------
        Set the window title for the new document::

            someFrame.setTitle(document='mycode.py')
            # title set to: "mycode.py - PsychoPy"

        """
        if document is not None:
            self.SetTitle(" - ".join([document, title]))
        else:
            self.SetTitle(title)

    def getTitle(self):
        """Get the window frame title.

        Returns
        -------
        str
            Current window frame title.

        """
        return self.GetTitle()
    
    def addPane(self, pane, caption, dockPosition=aui.AUI_DOCK_CENTER):
        """Add a new pane to the AUI manager.

        Parameters
        ----------
        pane : wx.Window or wx.Panel
            Pane to add to the AUI manager.
        caption : str
            Caption to display on the pane.
        dockPosition : int
            Dock position for the pane. Default is `aui.AUI_DOCK_CENTER`.

        """
        self.m_mgr.AddPane(pane, aui.AuiPaneInfo().Caption(caption).Bottom()
                           .CloseButton(True).MaximizeButton(True)
                           .Dockable(True).Dock())

    def removePane(self, pane):
        """Remove a pane from the AUI manager.

        Parameters
        ----------
        pane : wx.Window or wx.Panel
            Pane to remove from the AUI manager.

        """
        self.m_mgr.DetachPane(pane)

    def showPane(self, pane, show=True):
        """Show or hide a pane in the AUI manager.

        Parameters
        ----------
        pane : wx.Window or wx.Panel
            Pane to show or hide.
        show : bool
            Show the pane if `True`, hide it if `False`. Default is `True`.

        """
        self.m_mgr.GetPane(pane).Show(show)
    
    def hidePane(self, pane):
        """Hide a pane in the AUI manager.

        Parameters
        ----------
        pane : wx.Window or wx.Panel
            Pane to hide.

        """
        self.showPane(pane, False)

    # --------------------------------------------------------------------------
    # Events for the AUI frame
    #
    # AUI events can be used to monitor changes to the pane layout. These can
    # then be used to update the appropriate menu item.
    #

    def onAuiPaneActivate(self, event):
        """Called when the pane gets focused or is activated.
        """
        event.Skip()

    def onAuiPaneButton(self, event):
        """Called when an AUI pane button is clicked.
        """
        event.Skip()

    def onAuiPaneClose(self, event):
        """Called when an AUI pane is closed.
        """
        event.Skip()

    def onAuiPaneMaximize(self, event):
        """Called when an AUI pane is maximized.
        """
        event.Skip()

    def onAuiPaneRestore(self, event):
        """Called when a AUI pane is restored.
        """
        event.Skip()

    def onClose(self, event):
        """Event handler for `EVT_CLOSE` events. This is usually called when the
        user clicks the close button on the frame's title bar.
        """
        event.Skip()

    def onIdle(self, event):
        """Event handler for `EVT_IDLE` events. Called periodically when the
        user is not interacting with the UI.
        """
        event.Skip()


if __name__ == "__main__":
    pass
