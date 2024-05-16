#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Classes for graphical user interface elements for the main application.
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
        """Handle of the AUI manager for this frame (`wx.aui.AuiManager`).
        """
        return self.getAuiManager()

    def getAuiManager(self):
        """Get the AUI manager instance for this window.

        Returns
        -------
        wx.aui.AuiManager
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


class BaseAuiNotebookPanel(wx.Panel):
    """Base class for AUI managed notebook panels.

    This class is a base class for panels that are managed by an AUI notebook
    manager. It provides a simple interface for adding and removing pages from
    the notebook.

    Parameters
    ----------
    parent : wx.Window or None
        Parent window.
    id : int
        Unique ID for this window, default is `wx.ID_ANY`.
    pos : ArrayLike or `wx.Position`
        Initial position of the window on the desktop. Default is
        `wx.DefaultPosition`.
    size : ArrayLike or `wx.Size`
        Initial sie of the window in desktop units. Default is `wx.DefaultSize`.
    style : int
        Style flags for the window. Default is the combination of
        `wx.TAB_TRAVERSAL`.
    name : str
        Name for this window. Default is an empty string.

    """
    def __init__(self, 
                 parent, 
                 id=wx.ID_ANY, 
                 pos=wx.DefaultPosition, 
                 size=wx.DefaultSize,
                 style=wx.TAB_TRAVERSAL, 
                 name=wx.EmptyString):

        wx.Panel.__init__ (self, parent, id=id, pos=pos, size=-size, 
                           style=style, name=name)

        # sizer for the panel
        szNotebookPanel = wx.BoxSizer(wx.VERTICAL)
        self.nbMain = wx.aui.AuiNotebook(
            self, 
            wx.ID_ANY, 
            wx.DefaultPosition, 
            wx.DefaultSize,
            wx.aui.AUI_NB_SCROLL_BUTTONS|wx.aui.AUI_NB_TOP|
                wx.aui.AUI_NB_WINDOWLIST_BUTTON)
        szNotebookPanel.Add(self.nbMain, 1, wx.EXPAND|wx.ALL, 5)
        self.SetSizer(szNotebookPanel)
        self.Layout()

        # events for the notebook
        self.nbMain.Bind(wx.aui.EVT_AUINOTEBOOK_ALLOW_DND, 
            self.OnNotebookAllowDND)
        self.nbMain.Bind(wx.aui.EVT_AUINOTEBOOK_BG_DCLICK, 
            self.OnNotebookBGDClick)
        self.nbMain.Bind(wx.aui.EVT_AUINOTEBOOK_BEGIN_DRAG, 
            self.OnNotebookBeginDrag)
        self.nbMain.Bind(wx.aui.EVT_AUINOTEBOOK_BUTTON, 
            self.OnNotebookButton)
        self.nbMain.Bind(wx.aui.EVT_AUINOTEBOOK_DRAG_DONE, 
            self.OnNotebookDragDone)
        self.nbMain.Bind(wx.aui.EVT_AUINOTEBOOK_DRAG_MOTION, 
            self.OnNotebookDragMotion)
        self.nbMain.Bind(wx.aui.EVT_AUINOTEBOOK_END_DRAG, 
            self.OnNotebookEndDrag)
        self.nbMain.Bind(wx.aui.EVT_AUINOTEBOOK_PAGE_CHANGED, 
            self.OnNotebookPageChanged)
        self.nbMain.Bind(wx.aui.EVT_AUINOTEBOOK_PAGE_CHANGING, 
            self.OnNotebookPageChanging)
        self.nbMain.Bind(wx.aui.EVT_AUINOTEBOOK_PAGE_CLOSE, 
            self.OnNotebookPageClose)
        self.nbMain.Bind(wx.aui.EVT_AUINOTEBOOK_PAGE_CLOSED, 
            self.OnNotebookPageClosed)
        self.nbMain.Bind(wx.aui.EVT_AUINOTEBOOK_TAB_MIDDLE_DOWN, 
            self.OnNotebookTabMiddleDown)
        self.nbMain.Bind(wx.aui.EVT_AUINOTEBOOK_TAB_MIDDLE_UP, 
            self.OnNotebookTabMiddleUp)
        self.nbMain.Bind(wx.aui.EVT_AUINOTEBOOK_TAB_RIGHT_DOWN, 
            self.OnNotebookTabRightDown)
        self.nbMain.Bind(wx.aui.EVT_AUINOTEBOOK_TAB_RIGHT_UP, 
            self.OnNotebookTabRightUp)

    def __del__( self ):
        pass
    
    # event handlers for the notebook, override these in subclasses
    def OnNotebookAllowDND(self, event):
        event.Skip()

    def OnNotebookBGDClick(self, event):
        event.Skip()

    def OnNotebookBeginDrag(self, event):
        event.Skip()

    def OnNotebookButton(self, event):
        event.Skip()

    def OnNotebookDragDone(self, event):
        event.Skip()

    def OnNotebookDragMotion(self, event):
        event.Skip()

    def OnNotebookEndDrag(self, event):
        event.Skip()

    def OnNotebookPageChanged(self, event):
        event.Skip()

    def OnNotebookPageChanging(self, event):
        event.Skip()

    def OnNotebookPageClose(self, event):
        event.Skip()

    def OnNotebookPageClosed(self, event):
        event.Skip()

    def OnNotebookTabMiddleDown(self, event):
        event.Skip()

    def OnNotebookTabMiddleUp(self, event):
        event.Skip()

    def OnNotebookTabRightDown(self, event):
        event.Skip()

    def OnNotebookTabRightUp(self, event):
        event.Skip()

    # notebook properties
    @property
    def notebook(self):
        """Handle of the AUI notebook for this panel (`wx.aui.AuiNotebook`).
        """
        return self.getNotebook()
    
    @property
    def pageCount(self):
        """Number of pages in the notebook.
        """
        return self.getPageCount()

    # panel methods
    def setArtProvider(self, artProvider):
        """Set the art provider for the notebook.

        Parameters
        ----------
        artProvider : wx.aui.AuiTabArt
            Art provider to set for the notebook.

        """
        if not isinstance(artProvider, wx.aui.AuiTabArt):
            raise TypeError(
                "`artProvider` must be an instance of wx.aui.AuiTabArt")

        self.nbMain.SetArtProvider(artProvider)

    def getNotebook(self):
        """Get the AUI notebook instance for this panel.

        Returns
        -------
        wx.aui.AuiNotebook
            Handle for the AUI notebook instance associated with this panel.

        """
        return self.nbMain

    def addPage(self, page, caption, select=False, imageIndex=-1):
        """Add a new page to the notebook.

        Parameters
        ----------
        page : wx.Window or wx.Panel
            Window to add to the notebook.
        caption : str
            Caption to display on the tab.
        select : bool
            Select the new page after adding it. Default is `False`.
        imageIndex : int
            Index of the image to display on the tab. Default is `-1` for no
            image in tab.

        """
        self.nbMain.AddPage(page, caption, select)

        # image for the page if art provider available
        if imageIndex >= 0:
            imageList = self.nbMain.GetImageList()
            if imageIndex < imageList.GetImageCount():
                self.nbMain.SetPageImage(
                    self.nbMain.GetPageCount() - 1, 
                    imageIndex)

    def removePage(self, page):
        """Remove a page from the notebook.

        Parameters
        ----------
        page : wx.Window or wx.Panel
            Page to remove from the notebook.

        """
        self.nbMain.RemovePage(page)

    def getPage(self, index):
        """Get the page at the specified index.

        Parameters
        ----------
        index : int
            Index of the page to retrieve.

        Returns
        -------
        wx.Window or wx.Panel
            Page at the specified index.

        """
        return self.nbMain.GetPage(index)
    
    def getCurrentPage(self):
        """Get the currently selected page.

        Returns
        -------
        wx.Window or wx.Panel
            Currently selected page.

        """
        return self.nbMain.GetCurrentPage()

    def getCurrentPageIdx(self):
        """Get the index of the currently selected page.

        Returns
        -------
        int
            Index of the currently selected page.

        """
        return self.nbMain.GetSelection()
    
    def getPageCount(self):
        """Get the number of pages in the notebook.

        Returns
        -------
        int
            Number of pages in the notebook.

        """
        return self.nbMain.GetPageCount()
    
    def getPageText(self, index):
        """Get the caption of the page at the specified index.

        Parameters
        ----------
        index : int
            Index of the page to retrieve the caption for.

        Returns
        -------
        str
            Caption of the page at the specified index.

        """
        return self.nbMain.GetPageText(index)

    def setPageText(self, index, caption):
        """Set the caption of the page at the specified index.

        Parameters
        ----------
        index : int
            Index of the page to set the caption for.
        caption : str
            Caption to set for the page.

        """
        self.nbMain.SetPageText(index, caption)
    
    def setPageToolTip(self, index, tooltip):
        """Set the tooltip for the page at the specified index.

        Parameters
        ----------
        index : int
            Index of the page to set the tooltip for.
        tooltip : str
            Tooltip to set for the page.

        """
        self.nbMain.SetPageToolTip(index, tooltip)

    def setPageImage(self, index, imageIndex):
        """Set the image for the page at the specified index.

        Parameters
        ----------
        index : int
            Index of the page to set the image for.
        imageIndex : int
            Index of the image to set for the page.

        """
        self.nbMain.SetPageImage(index, imageIndex)
    
    def setPageBitmap(self, index, bitmap):
        """Set the bitmap for the page at the specified index.

        Parameters
        ----------
        index : int
            Index of the page to set the bitmap for.
        bitmap : wx.Bitmap
            Bitmap to set for the page.

        """
        self.nbMain.SetPageBitmap(index, bitmap)

    def advanceSelection(self, forward=True):
        """Advance the selection to the next page.

        Parameters
        ----------
        forward : bool
            Advance the selection forward. Default is `True`.

        """
        self.nbMain.AdvanceSelection(forward)

    def setSelection(self, index):
        """Set the selection to the page at the specified index.

        Parameters
        ----------
        index : int
            Index of the page to select.

        """
        self.nbMain.SetSelection(index)

    def changeSelection(self, index):
        """Change the selection to the page at the specified index.

        Parameters
        ----------
        index : int
            Index of the page to change the selection to.

        Returns
        -------
        int
            Index of the page that was selected before changing.

        """
        return self.nbMain.ChangeSelection(index)
    
    def clearPages(self):
        """Remove all pages from the notebook.
        """
        self.nbMain.DeleteAllPages() 



if __name__ == "__main__":
    pass
