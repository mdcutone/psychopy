#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Classes for drawing custom widgets.
"""

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2024 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

import wx
import wx.lib.agw.aui as aui


class BaseCustomDrawArea(wx.Panel):
    """Base class for custom draw areas.

    This class is a subclass of `wx.Panel` and provides a basic framework for
    custom drawing areas. This class is intended to provide a means to draw
    custom graphics in a window using a device context. This allows for the 
    creation of custom widgets for adding functionality beyond what can be 
    achieved with standard controls.
    
    Do not use this class directly, instead subclass it and override the 
    `OnPaint` method which should contain the custom drawing code. All drawing
    is buffered.

    There are many methods provided for drawing shapes, text, and images. The 
    drawing methods must be called between `beginDrawing` and `endDrawing` 
    calls.

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
        Initial size of the window in desktop units.
    style : int
        Style flags for the window. Default is the combination of
        `wx.TAB_TRAVERSAL`.
    name : str
        Window name.

    Examples
    --------
    To create a custom draw area, subclass `BaseCustomDrawArea` and override the
    `OnPaint` method. The following example creates a custom draw area that
    draws a red rectangle::

        import wx
        from psychopy.app.ui.drawArea import BaseCustomDrawArea

        class MyDrawArea(BaseCustomDrawArea):
            def OnPaint(self, event):
                dc = self.beginDrawing()
                dc.SetPen(wx.Pen(wx.RED, 1))
                dc.SetBrush(wx.Brush(wx.RED, wx.SOLID))
                dc.DrawRectangle(10, 10, 100, 100)
                self.endDrawing()

    Pens and brushes can be added to memory for later use. The following example
    creates a custom draw area that draws a blue rectangle using a saved pen and
    brush::

        class MyDrawArea(BaseCustomDrawArea):
            def __init__(self, parent):
                BaseCustomDrawArea.__init__(self, parent)

                # add pens for later use
                self.addPen('blue', wx.BLUE, 1)
                self.addBrush('blue', wx.BLUE, wx.SOLID)

            def OnPaint(self, event):
                # using class methods to interact with the device context
                dc = self.beginDrawing()
                self.setPen('blue')
                self.setBrush('blue')
                self.drawRectangle(10, 10, 100, 100)
                self.endDrawing()

    """
    def __init__(self, 
                 parent, 
                 id=wx.ID_ANY, 
                 pos=wx.DefaultPosition, 
                 size=wx.DefaultSize, 
                 style=wx.TAB_TRAVERSAL, 
                 name=wx.EmptyString):
        wx.Panel.__init__ (self, parent, id=id, pos=pos, size=size, style=style, 
                name=name)

        self._dc = None

        # pens and brushes
        self._pens = {'default': wx.Pen(wx.BLACK, 1, wx.SOLID)}
        self._brushes = {'default': wx.Brush(wx.WHITE, wx.SOLID)}

        # settings for drawing
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        # events
        self.Bind(aui.EVT_AUI_RENDER, self.OnAuiRender)
        self.Bind(wx.EVT_CHAR, self.OnChar)
        self.Bind(wx.EVT_CHAR_HOOK, self.OnCharHook)
        self.Bind(wx.EVT_ENTER_WINDOW, self.OnEnterWindow)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind(wx.EVT_KEY_UP, self.OnKeyUp)
        self.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeaveWindow)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDClick)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.Bind(wx.EVT_MIDDLE_DCLICK, self.OnMiddleDClick)
        self.Bind(wx.EVT_MIDDLE_DOWN, self.OnMiddleDown)
        self.Bind(wx.EVT_MIDDLE_UP, self.OnMiddleUp)
        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)
        self.Bind(wx.EVT_MOVE, self.OnMove)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_RIGHT_DCLICK, self.OnRightDClick)
        self.Bind(wx.EVT_RIGHT_DOWN, self.OnRightDown)
        self.Bind(wx.EVT_RIGHT_UP, self.OnRightUp)
        self.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_UPDATE_UI, self.OnUpdateUI)

    def __del__(self):
        pass

    def addPen(self, name, color, width=1, style=wx.SOLID):
        """Add a pen to memory for later use in drawing.

        This adds a pen to memory for later use in drawing. The pen can be
        retrieved by name using the `setPenByName` method.

        Parameters
        ----------
        name : str
            Name of the pen.
        color : wx.Colour
            Pen color.
        width : int
            Pen width.
        style : int
            Pen style.

        """
        self._pens[name] = wx.Pen(color, width, style)
    
    def addBrush(self, name, color, style=wx.SOLID):
        """Add a brush to memory for later use in drawing.

        Parameters
        ----------
        name : str
            Name of the brush.
        color : wx.Colour
            Brush color.
        style : int
            Brush style.

        """
        self._brushes[name] = wx.Brush(color, style)

    def removePen(self, name):
        """Remove a pen from memory.

        Parameters
        ----------
        name : str
            Name of the pen to remove.

        """
        if name in self._pens:
            del self._pens[name]
        
    def removeBrush(self, name):
        """Remove a brush from memory.

        Parameters
        ----------
        name : str
            Name of the brush to remove.

        """
        if name in self._brushes:
            del self._brushes[name]

    def beginDrawing(self):
        """Aquire a device context and start drawing.

        Returns
        -------
        wx.DC
            Device context for drawing.

        """
        self._dc = wx.AutoBufferedPaintDC(self)

        return self._dc

    def endDrawing(self):
        """Finish drawing and release the device context.

        """
        self._dc = None

    def setClippingRegion(self, x, y, width, height):
        """Set a clipping region.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        x : int
            X-coordinate of the top-left corner.
        y : int
            Y-coordinate of the top-left corner.
        width : int
            Width of the clipping region.
        height : int
            Height of the clipping region.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        self._dc.SetClippingRegion(x, y, width, height)

    def destroyClippingRegion(self):
        """Destroy the clipping region.

        Must be called after `beginDrawing` and before `endDrawing`.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        self._dc.DestroyClippingRegion()

    def getDeviceScale(self):
        """Get the device scale.

        Must be called after `beginDrawing` and before `endDrawing`.

        Returns
        -------
        Tuple[float, float]
            X and Y scale factors.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        return self._dc.GetDeviceScale()

    def setDeviceScale(self, x, y):
        """Set the device scale.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        x : float
            X-scale factor.
        y : float
            Y-scale factor.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        self._dc.SetDeviceScale(x, y)

    def setUserScale(self, x, y):
        """Set the user scale.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        x : float
            X-scale factor.
        y : float
            Y-scale factor.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        self._dc.SetUserScale(x, y)

    def getLogicalScale(self):
        """Get the logical scale.

        Must be called after `beginDrawing` and before `endDrawing`.

        Returns
        -------
        Tuple[float, float]
            X and Y scale factors.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        return self._dc.GetLogicalScale()

    def setLogicalScale(self, x, y):
        """Set the logical scale.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        x : float
            X-scale factor.
        y : float
            Y-scale factor.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        self._dc.SetLogicalScale(x, y)
    
    def getLogicalOrigin(self):
        """Get the logical origin.

        Must be called after `beginDrawing` and before `endDrawing`.

        Returns
        -------
        Tuple[int, int]
            X and Y coordinates of the origin.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        return self._dc.GetLogicalOrigin()

    def setLogicalOrigin(self, x, y):
        """Set the logical origin.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        x : int
            X-coordinate of the origin.
        y : int
            Y-coordinate of the origin.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        self._dc.SetLogicalOrigin(x, y)

    def getDeviceOrigin(self):
        """Get the device origin.

        Must be called after `beginDrawing` and before `endDrawing`.

        Returns
        -------
        Tuple[int, int]
            X and Y coordinates of the origin.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        return self._dc.GetDeviceOrigin()

    def setDeviceOrigin(self, x, y):
        """Set the device origin.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        x : int
            X-coordinate of the origin.
        y : int
            Y-coordinate of the origin.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        self._dc.SetDeviceOrigin(x, y)

    def logicalToDevice(self, x, y):
        """Convert logical coordinates to device coordinates.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        x : int
            X-coordinate in logical units.
        y : int
            Y-coordinate in logical units.

        Returns
        -------
        Tuple[int, int]
            X and Y coordinates in device units.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        return self._dc.DeviceToLogical(x, y)

    def deviceToLogical(self, x, y):
        """Convert device coordinates to logical coordinates.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        x : int
            X-coordinate in device units.
        y : int
            Y-coordinate in device units.

        Returns
        -------
        Tuple[int, int]
            X and Y coordinates in logical units.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        return self._dc.LogicalToDevice(x, y)

    def clear(self):
        """Clear the drawing area.

        Must be called after `beginDrawing` and before `endDrawing`.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        self._dc.Clear()

    def setPen(self, name='default'):
        """Use a saved pen for successive drawing operations.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        name : str
            Name of the pen to use as was added with `addPen`.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        if name in self._pens:
            self._dc.SetPen(self._pens[name])

    def setBrush(self, name='default'):
        """Use a saved brush for successive drawing operations.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        name : str
            Name of the brush to use as was added with `addBrush`.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        if name in self._brushes:
            self._dc.SetBrush(self._brushes[name])

    def setBackground(self, color, style=wx.SOLID):
        """Set the background color.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        color : wx.Colour
            Background color.
        style : int
            Background style.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        lastBrush = self._dc.GetBackground()
        self._dc.SetBackground(wx.Brush(color, style))
        self._dc.Clear()
        self._dc.SetBrush(lastBrush)  # restore brush

    def drawLine(self, x1, y1, x2, y2):
        """Draw a line.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        x1 : int
            X-coordinate of the starting point.
        y1 : int
            Y-coordinate of the starting point.
        x2 : int
            X-coordinate of the ending point.
        y2 : int
            Y-coordinate of the ending point.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        self._dc.DrawLine(x1, y1, x2, y2)
    
    def drawLines(self, points):
        """Draw a series of connected lines.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        points : List[Tuple[int, int]]
            List of points to draw.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        self._dc.DrawLines(points)

    def drawPolygon(self, points):
        """Draw a polygon.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        points : List[Tuple[int, int]]
            List of points to draw.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        self._dc.DrawPolygon(points)
    
    def drawRectangle(self, x, y, width, height):
        """Draw a rectangle.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        x : int
            X-coordinate of the top-left corner.
        y : int
            Y-coordinate of the top-left corner.
        width : int
            Width of the rectangle.
        height : int
            Height of the rectangle.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        self._dc.DrawRectangle(x, y, width, height)

    def drawEllipse(self, x, y, width, height):
        """Draw an ellipse.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        x : int
            X-coordinate of the top-left corner of the bounding rectangle.
        y : int
            Y-coordinate of the top-left corner of the bounding rectangle.
        width : int
            Width of the bounding rectangle.
        height : int
            Height of the bounding rectangle.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        self._dc.DrawEllipse(x, y, width, height)
    
    def drawCircle(self, x, y, radius):
        """Draw a circle.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        x : int
            X-coordinate of the center.
        y : int
            Y-coordinate of the center.
        radius : int
            Radius of the circle.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        self._dc.DrawCircle(x, y, radius)

    def drawArc(self, x, y, width, height, startAngle, endAngle):
        """Draw an arc.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        x : int
            X-coordinate of the top-left corner of the bounding rectangle.
        y : int
            Y-coordinate of the top-left corner of the bounding rectangle.
        width : int
            Width of the bounding rectangle.
        height : int
            Height of the bounding rectangle.
        startAngle : float
            Starting angle in degrees.
        endAngle : float
            Ending angle in degrees.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        self._dc.DrawArc(x, y, width, height, startAngle, endAngle)

    def drawRotatedText(self, text, x, y, angle):
        """Draw rotated text.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        text : str
            Text to draw.
        x : int
            X-coordinate of the starting point.
        y : int
            Y-coordinate of the starting point.
        angle : float
            Rotation angle in degrees.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        self._dc.DrawRotatedText(text, x, y, angle)

    def drawCheckMark(self, x, y, width, height):
        """Draw a check mark.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        x : int
            X-coordinate of the top-left corner.
        y : int
            Y-coordinate of the top-left corner.
        width : int
            Width of the check mark.
        height : int
            Height of the check mark.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        self._dc.DrawCheckMark(x, y, width, height)

    def drawSpline(self, points):
        """Draw a spline.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        points : List[Tuple[int, int]]
            List of points to draw.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        self._dc.DrawSpline(points)

    def drawRoundedRectangle(self, x, y, width, height, radius):
        """Draw a rounded rectangle.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        x : int
            X-coordinate of the top-left corner.
        y : int
            Y-coordinate of the top-left corner.
        width : int
            Width of the rectangle.
        height : int
            Height of the rectangle.
        radius : int
            Radius of the corners.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        self._dc.DrawRoundedRectangle(x, y, width, height, radius)
    
    def setTextForeground(self, color):
        """Set the text foreground color.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        color : wx.Colour
            Text color.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        self._dc.SetTextForeground(color)
    
    def setTextBackground(self, color):
        """Set the text background color.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        color : wx.Colour
            Text background color.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        self._dc.SetTextBackground(color)
    
    def drawText(self, text, x, y):
        """Draw text.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        text : str
            Text to draw.
        x : int
            X-coordinate of the starting point.
        y : int
            Y-coordinate of the starting point.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        self._dc.DrawText(text, x, y)

    def drawBitmap(self, bitmap, x, y):
        """Draw a bitmap.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        bitmap : wx.Bitmap
            Bitmap to draw.
        x : int
            X-coordinate of the top-left corner.
        y : int
            Y-coordinate of the top-left corner.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        self._dc.DrawBitmap(bitmap, x, y)

    # utilites
    def getTextExtent(self, text):
        """Get the extent of the text.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        text : str
            Text to measure.

        Returns
        -------
        Tuple[int, int]
            Width and height of the text.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        return self._dc.GetTextExtent(text)

    def floodFill(self, x, y, color, style=wx.SOLID):
        """Flood fill an area.

        Must be called after `beginDrawing` and before `endDrawing`.

        Parameters
        ----------
        x : int
            X-coordinate of the starting point.
        y : int
            Y-coordinate of the starting point.
        color : wx.Colour
            Fill color.
        style : int
            Fill style.

        """
        assert self._dc is not None, "Must call `beginDrawing` before drawing."
        self._dc.FloodFill(x, y, color, style)

    # events related to the window
    def OnSize(self, event):
        """Called when the window is resized.

        By default, this method calls the `Refresh` method to update the
        window. Override this method in subclasses to provide custom behavior.

        Parameters
        ----------
        event : wx.SizeEvent
            Size event.

        """
        self.Refresh()
        event.Skip()

    def OnPaint(self, event):
        """Called when the window is painted.

        Override this method in subclasses to provide custom drawing behavior.

        Parameters
        ----------
        event : wx.PaintEvent
            Paint event.

        """
        event.Skip()

    def OnAuiRender(self, event):
        event.Skip()

    # window events related to input
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

    def OnMouseWheel(self, event):
        event.Skip()

    def OnMove(self, event):
        event.Skip()

    def OnRightDClick(self, event):
        event.Skip()

    def OnRightDown(self, event):
        event.Skip()

    def OnRightUp(self, event):
        event.Skip()

    def OnSetFocus(self, event):
        event.Skip()

    def OnUpdateUI(self, event):
        event.Skip()


if __name__ == '__main__':
    pass
