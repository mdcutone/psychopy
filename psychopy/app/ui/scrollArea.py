#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Classes for scrollable areas in the main application.
"""

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2024 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).


import wx


class BaseScrollableArea(wx.Panel):
    """Base class for a scrollable area.

    This class is a base class for a scrollable area. It provides a scrolled
    window that can be used to display content that is larger than the window
    itself. The class provides a number of event handlers that can be
    overridden in subclasses to provide custom behavior.

    Parameters
    ----------
    parent : wx.Window
        Parent window.
    id : int, optional
        Window identifier. A value of -1 indicates a default value.
    pos : wx.Point, optional
        Window position.
    size : wx.Size, optional
        Window size.
    style : int, optional
        Window style flags. Default is `wx.TAB_TRAVERSAL`.
    name : str, optional
        Window name.
    scrollVert : bool, optional
        Allow vertical scrolling. Appends `wx.VSCROLL` to the style flags.
    scrollHorz : bool, optional
        Allow horizontal scrolling. Appends `wx.HSCROLL` to the style flags.
    scrollRateVert : int, optional
        Vertical scroll rate. Default is 5.
    scrollRateHorz : int, optional
        Horizontal scroll rate. Default is 5.
    alwaysShowScrollbars : bool, optional
        Always show scrollbars. Appends `wx.ALWAYS_SHOW_SB` to the style flags.
    backgroundColor : wx.Colour, optional
        Background color for the scrollable area.

    Examples
    --------
    Create a scrollable area with a number of text boxes::

        scrollArea = BaseScrollableArea(frame)

        # add text boxes, must be children of the scrollable area
        widgetParent = scrollArea.getScrollArea()
        for i in range(100):
            txt = wx.TextCtrl(widgetParent, wx.ID_ANY, "Text Box %d" % i)
            scrollArea.addWidget(txt)

        # set the header as a static label
        header = wx.StaticText(scrollArea, wx.ID_ANY, "Header")
        scrollArea.setPanelHeader(header)

        # set the footer as a static label
        footer = wx.StaticText(scrollArea, wx.ID_ANY, "Footer")
        scrollArea.setPanelFooter(footer)

    """
    def __init__(self, 
                 parent, 
                 id=wx.ID_ANY, 
                 pos=wx.DefaultPosition, 
                 size=wx.DefaultSize, 
                 style=wx.TAB_TRAVERSAL, 
                 name=wx.EmptyString,
                 scrollVert=True,
                 scrollHorz=False,
                 scrollRateVert=5,
                 scrollRateHorz=5,
                 alwaysShowScrollbars=False,
                 backgroundColor=wx.NullColour):

        wx.Panel.__init__ (self, parent, id=id, pos=pos, size=size, style=style, 
                name=name)

        # set background color
        if isinstance(backgroundColor, str):
            backgroundColor = wx.Colour(backgroundColor)
        elif isinstance(backgroundColor, (list, tuple,)):
            backgroundColor = wx.Colour(*backgroundColor)
        elif isinstance(backgroundColor, wx.Colour):
            pass
        else:
            backgroundColor = wx.NullColour

        if backgroundColor.IsOk():
            self.SetBackgroundColour(backgroundColor)

        styleFlags = style
        
        # apply style flags
        if scrollVert and scrollHorz:
            styleFlags = styleFlags | wx.HSCROLL | wx.VSCROLL
        elif scrollVert:
            styleFlags = styleFlags | wx.VSCROLL
        elif scrollHorz:
            styleFlags = styleFlags | wx.HSCROLL

        if alwaysShowScrollbars:
            styleFlags = styleFlags | wx.ALWAYS_SHOW_SB

        self.szrMain = wx.BoxSizer(wx.VERTICAL)
        self.pnlScrollArea = wx.ScrolledWindow(
            self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, styleFlags)

        self.pnlScrollArea.SetScrollRate(scrollRateVert, scrollRateHorz)
        szrScrollArea = wx.BoxSizer(wx.VERTICAL)
        self.pnlScrollArea.SetSizer(szrScrollArea)
        self.pnlScrollArea.Layout()
        szrScrollArea.Fit(self.pnlScrollArea)
        self.szrMain.Add(self.pnlScrollArea, 1, wx.EXPAND, 0)
        self.SetSizer(self.szrMain)
        self.Layout()

        # keep track if header and footer are present
        self._hasHeader = False
        self._hasFooter = False
        
        # set events this way to allow for subclassing
        self._bindEvents()
        
    def __del__(self):
        pass

    def _bindEvents(self):
        """Bind events to the panel.
        """
        self.pnlScrollArea.Bind(wx.EVT_CHAR, self.OnChar)
        self.pnlScrollArea.Bind(wx.EVT_CHAR_HOOK, self.OnCharHook)
        self.pnlScrollArea.Bind(wx.EVT_ENTER_WINDOW, self.OnEnterWindow)
        self.pnlScrollArea.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.pnlScrollArea.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.pnlScrollArea.Bind(wx.EVT_KEY_UP, self.OnKeyUp)
        self.pnlScrollArea.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)
        self.pnlScrollArea.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeaveWindow)
        self.pnlScrollArea.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDClick)
        self.pnlScrollArea.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.pnlScrollArea.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.pnlScrollArea.Bind(wx.EVT_MIDDLE_DCLICK, self.OnMiddleDClick)
        self.pnlScrollArea.Bind(wx.EVT_MIDDLE_DOWN, self.OnMiddleDown)
        self.pnlScrollArea.Bind(wx.EVT_MIDDLE_UP, self.OnMiddleUp)
        self.pnlScrollArea.Bind(wx.EVT_MOTION, self.OnMotion)
        self.pnlScrollArea.Bind(wx.EVT_LEFT_DOWN, self.OnMouseEvents)
        self.pnlScrollArea.Bind(wx.EVT_LEFT_UP, self.OnMouseEvents)
        self.pnlScrollArea.Bind(wx.EVT_MIDDLE_DOWN, self.OnMouseEvents)
        self.pnlScrollArea.Bind(wx.EVT_MIDDLE_UP, self.OnMouseEvents)
        self.pnlScrollArea.Bind(wx.EVT_RIGHT_DOWN, self.OnMouseEvents)
        self.pnlScrollArea.Bind(wx.EVT_RIGHT_UP, self.OnMouseEvents)
        self.pnlScrollArea.Bind(wx.EVT_MOTION, self.OnMouseEvents)
        self.pnlScrollArea.Bind(wx.EVT_LEFT_DCLICK, self.OnMouseEvents)
        self.pnlScrollArea.Bind(wx.EVT_MIDDLE_DCLICK, self.OnMouseEvents)
        self.pnlScrollArea.Bind(wx.EVT_RIGHT_DCLICK, self.OnMouseEvents)
        self.pnlScrollArea.Bind(wx.EVT_LEAVE_WINDOW, self.OnMouseEvents)
        self.pnlScrollArea.Bind(wx.EVT_ENTER_WINDOW, self.OnMouseEvents)
        self.pnlScrollArea.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseEvents)
        self.pnlScrollArea.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)
        self.pnlScrollArea.Bind(wx.EVT_MOVE, self.OnMove)
        self.pnlScrollArea.Bind(wx.EVT_PAINT, self.OnPaint)
        self.pnlScrollArea.Bind(wx.EVT_RIGHT_DCLICK, self.OnRightDClick)
        self.pnlScrollArea.Bind(wx.EVT_RIGHT_DOWN, self.OnRightDown)
        self.pnlScrollArea.Bind(wx.EVT_RIGHT_UP, self.OnRightUp)
        self.pnlScrollArea.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        self.pnlScrollArea.Bind(wx.EVT_SIZE, self.OnSize)
        self.pnlScrollArea.Bind(wx.EVT_UPDATE_UI, self.OnUpdateUI)

    def _getPanelSizer(self):
        """Get the sizer for the panel.

        Returns
        -------
        wx.Sizer
            Sizer for the panel.

        """
        return self.GetSizer()

    def _getScrollAreaSizer(self):
        """Get the sizer for the scrollable area.

        Returns
        -------
        wx.Sizer
            Sizer for the scrollable area.

        """
        return self.pnlScrollArea.GetSizer()

    def setPanelHeader(self, panelHeader):
        """Set the panel header.

        This can be used to add a header to the scrollable area which remains 
        static at the top of the area when scrolling.

        Parameters
        ----------
        panelHeader : wx.Window
            Panel header to set.

        """
        self._getPanelSizer().Prepend(panelHeader, 0, wx.EXPAND, 0)
        self.Layout()
        self._hasHeader = True

    def setPanelFooter(self, panelFooter):
        """Set the panel footer.

        This can be used to add a footer to the scrollable area which remains
        static at the bottom of the area when scrolling. This can be used to 
        add buttons or other controls that should always be visible.

        Parameters
        ----------
        panelFooter : wx.Window
            Panel footer to set.

        """
        self._getPanelSizer().Add(panelFooter, 0, wx.EXPAND, 0)
        self.Layout()
        self._hasFooter = True
    
    def showHeader(self, show=True):
        """Show or hide the panel header.

        Parameters
        ----------
        show : bool, optional
            Show or hide the panel header. Default is `True`.

        """
        if self._hasHeader:
            self._getPanelSizer().Show(0, show)
            self.Layout()

    def showFooter(self, show=True):
        """Show or hide the panel footer.

        Parameters
        ----------
        show : bool, optional
            Show or hide the panel footer. Default is `True`.

        """
        if self._hasFooter:
            szr = self._getPanelSizer()
            szr.Show(szr.GetItemCount()-1, show)
            self.Layout()

    def getScrollArea(self):
        """Get a reference to the scrollable area.

        Returns
        -------
        wx.ScrolledWindow
            Scrollable area.

        """
        return self.pnlScrollArea

    def addWidget(self, widget, proportion=0, expand=True, border=0):
        """Add a widget to the scrollable area.

        Parameters
        ----------
        widget : wx.Window
            Widget to add to the scrollable area.
        proportion : int, optional
            Proportion for the widget. Default is 0.
        expand : bool, optional
            Expand the widget. Default is `True`.
        border : int, optional
            Border size. Default is 0.

        """
        flags = 0
        if expand:
            flags = wx.EXPAND

        if border > 0:
            flags = flags | wx.ALL

        szr = self._getScrollAreaSizer()
        szr.Add(widget, proportion, flags, border)
        szr.Layout()
    
    def removeWidget(self, widget):
        """Remove a widget from the scrollable area.

        Parameters
        ----------
        widget : wx.Window
            Widget to remove from the scrollable area.

        """
        szr = self._getScrollAreaSizer()
        szr.Remove(widget)
        szr.Layout()
    
    def clearWidgets(self):
        """Remove all widgets from the scrollable area.
        """
        szr = self._getScrollAreaSizer()
        szr.Clear()
        szr.Layout()

    # event handlers

    def OnChar(self, event):
        event.Skip()

    def OnCharHook(self, event):
        event.Skip()

    def OnEnterWindow(self, event):
        event.Skip()

    def OnEraseBackground(self, event):
        event.Skip()

    def OnKeyDown(self, event):
        event.Skip()

    def OnKeyUp(self, event):
        event.Skip()

    def OnKillFocus(self, event):
        event.Skip()

    def OnLeaveWindow(self, event):
        event.Skip()

    def OnLeftDClick(self, event):
        event.Skip()

    def OnLeftDown(self, event):
        event.Skip()

    def OnLeftUp(self, event):
        event.Skip()

    def OnMiddleDClick(self, event):
        event.Skip()

    def OnMiddleDown(self, event):
        event.Skip()

    def OnMiddleUp(self, event):
        event.Skip()

    def OnMotion(self, event):
        event.Skip()

    def OnMouseEvents(self, event):
        event.Skip()

    def OnMouseWheel(self, event):
        event.Skip()

    def OnMove(self, event):
        event.Skip()

    def OnPaint(self, event):
        event.Skip()

    def OnRightDClick(self, event):
        event.Skip()

    def OnRightDown(self, event):
        event.Skip()

    def OnRightUp(self, event):
        event.Skip()

    def OnSetFocus(self, event):
        event.Skip()

    def OnSize(self, event):
        event.Skip()

    def OnUpdateUI(self, event):
        event.Skip()


if __name__ == "__main__":
    # # test the scrollable area by adding loads of text boxes
    # app = wx.App(False)
    # frame = wx.Frame(None, wx.ID_ANY, "Scrollable Area Test")

    # scrollArea = BaseScrollableArea(frame)

    # # add text boxes, must be children of the scrollable area
    # widgetParent = scrollArea.getScrollArea()
    # for i in range(100):
    #     txt = wx.TextCtrl(widgetParent, wx.ID_ANY, "Text Box %d" % i)
    #     scrollArea.addWidget(txt)

    # # set the header as a static label
    # header = wx.StaticText(scrollArea, wx.ID_ANY, "Header")
    # scrollArea.setPanelHeader(header)

    # # set the footer as a static label
    # footer = wx.StaticText(scrollArea, wx.ID_ANY, "Footer")
    # scrollArea.setPanelFooter(footer)
    
    # frame.Show()
    # app.MainLoop()
    pass