#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Classes for the property grid in the GUI.
"""

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2024 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

import wx
import wx.lib.agw.aui as aui
import wx.propgrid as pg


class BaseAuiPropertyPanel(wx.Panel):
    """Base class for AUI managed property panels.

    This class is a base class for panels that are managed by an AUI property
    grid manager. It provides a simple interface for adding and removing pages
    from the property grid.

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

        wx.Panel.__init__ (self, parent, id=id, pos=pos, size=size, style=style, 
            name=name)

        szrPropertyPanel = wx.BoxSizer(wx.VERTICAL)

        self.pgManager = pg.PropertyGridManager(
            self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, 
            wx.propgrid.PG_DESCRIPTION|wx.propgrid.PG_NO_INTERNAL_BORDER|
                wx.propgrid.PG_TOOLTIPS|wx.propgrid.PG_SPLITTER_AUTO_CENTER)

        self.pgManager.SetExtraStyle(wx.propgrid.PG_EX_MODE_BUTTONS)
        self.pgMain = self.pgManager.AddPage(u"Page", wx.NullBitmap)
        szrPropertyPanel.Add(self.pgManager, 1, wx.EXPAND)
        self.SetSizer(szrPropertyPanel)
        self.Layout()

        # bind events
        self.pgManager.Bind(pg.EVT_PG_CHANGED, self.OnPropertyGridChanged)
        self.pgManager.Bind(pg.EVT_PG_CHANGING, self.OnPropertyGridChanging)

        # property types
        self._propTypes = {
            'String': pg.StringProperty,
            'Integer': pg.IntProperty,
            'Float': pg.FloatProperty,
            'Boolean': pg.BoolProperty,
            'Enum': pg.EnumProperty,
            'Dir': pg.DirProperty,
            'File': pg.FileProperty,
            'Date': pg.DateProperty,
            'ImageFile': pg.ImageFileProperty,
            'Colour': pg.ColourProperty,
            'Font': pg.FontProperty,
            'LongString': pg.LongStringProperty
        }


    def __del__(self):
        pass
    
    # events
    def OnPropertyGridChanged( self, event ):
        event.Skip()

    def OnPropertyGridChanging( self, event ):
        event.Skip()

    # methods for the property panel
    def getPropertyGrid(self):
        """Get the property grid instance for this panel.

        Returns
        -------
        wx.propgrid.PropertyGridManager
            Handle for the property grid instance associated with this panel.

        """
        return self.pgManager
    
    def fitColumns(self):
        """Fit the columns in the property grid.
        """
        self.pgManager.SetSplitterLeft(subProps=True)

        # self.pgMain.SetSplitterPosition(self.pgMain.GetColumnWidth(1))

    def populateGridFromDict(self, data):
        """Populate the property grid from a dictionary.

        Parameters
        ----------
        data : dict
            Dictionary to populate the property grid with.

        """
        parent = self.pgMain

        # format for the property grid data
        # dataFormat = {'Category1': 
        #     {'Name1': {'label': 'Name1', 
        #                 'value': 'Value1', 
        #                 'type': 'String', 
        #                 'hidden': False},
        #     'Name2': {'label': 'Name2',
        #                 'value': 10,
        #                 'type': 'Integer',
        #                 'hidden': False}
        #     }
        # }

        for category, props in data.items():
            cat = pg.PropertyCategory(category, category)
            parent.Append(cat)

            for name, prop in props.items():
                label = prop.get('label', name)
                value = prop.get('value', None)
                propType = prop.get('type', 'String')
                hidden = prop.get('hidden', False)

                if propType in self._propTypes:
                    prop = self._propTypes[propType](label, name, value)
                    prop.SetAttribute("Hidden", hidden)
                    parent.Append(prop)

    def expandAll(self):
        """Expand all categories in the property grid.
        """
        self.pgMain.ExpandAll()

    def collapseAll(self):
        """Collapse all categories in the property grid.
        """
        self.pgMain.CollapseAll()

    def refreshGrid(self):
        """Refresh the property grid.
        """
        self.pgMain.Refresh()

    def clearGrid(self):
        """Clear the property grid.
        """
        self.pgMain.Clear() 

    def getCategoryNames(self):
        """Get the categories in the property grid.

        Returns
        -------
        list
            List of categories in the property grid.

        """
        return self.pgMain.GetCategories()
    
    def getCategoryProperties(self, name):
        """Get the properties for a category in the property grid.

        Parameters
        ----------
        name : str
            Name of the category to get the properties for.

        Returns
        -------
        list
            List of properties for the specified category.

        """
        return self.pgMain.GetPropertyByCategory(name)

    def expandCategory(self, name):
        """Expand a category in the property grid.

        Parameters
        ----------
        name : str
            Name of the category to expand.

        """
        prop = self.pgMain.GetPropertyByName(name)
        if prop is not None:
            prop.Expand()

    def collapseCategory(self, name):
        """Collapse a category in the property grid.

        Parameters
        ----------
        name : str
            Name of the category to collapse.

        """
        prop = self.pgMain.GetPropertyByName(name)
        if prop is not None:
            prop.Collapse()
    
    def enablerProperty(self, name, enable=True):
        """Enable or disable a property in the property grid.

        Parameters
        ----------
        name : str
            Name of the property to enable or disable.
        enable : bool
            Enable the property if `True`, disable it if `False`. Default is
            `True`.

        """
        prop = self.pgMain.GetPropertyByName(name)
        if prop is not None:
            prop.Enable(enable)

    def disableProperty(self, name):
        """Disable a property in the property grid.

        Parameters
        ----------
        name : str
            Name of the property to disable.

        """
        self.enablerProperty(name, False)

    def addCategory(self, label, name=None, hint=None, expanded=False):
        """Add a category to the property grid.

        Parameters
        ----------
        label : str
            Label for the category.
        name : str or None
            Name for the category. Default is `None`.
        hint : str or None
            Hint for the category. Default is `None`.
        expanded : bool
            Set the category as expanded. Default is `False`.

        """
        if name is None:
            name = label

        cat = pg.PropertyCategory(label, name)
        cat.SetAttribute("Hint", hint)
        cat.SetAttribute("Expanded", expanded)

        self.pgMain.Append(cat)

    def _setPropAttributes(self, prop, hint, readOnly, visible, setCallback=None):
        """Set attributes for a property.

        This is used internally to set attributes for properties added to the
        property grid.

        Parameters
        ----------
        prop : wx.propgrid.PGProperty
            Property to set attributes for.
        hint : str or None
            Hint for the property. Default is `None`.
        readOnly : bool
            Set the property as read-only. Default is `False`.
        visible : bool
            Set the property as visible. Default is `True`.
        setCallback : callable or None
            Callback function to set the value of the property. Default is
            `None`.

        """
        prop.SetAttribute("Hint", hint)
        prop.SetAttribute("ReadOnly", readOnly)
        prop.SetAttribute("Visible", visible)

        if setCallback is not None:
            prop.OnSetValue = setCallback
    
    def setPropertyChildren(self, prop, children):
        """Set children for a property in the property grid.

        Parameters
        ----------
        prop : wx.propgrid.PGProperty
            Property to set the children for.
        children : list
            List of children properties to set for the property.

        """
        # self.pgMain.BeginAddChildren(prop)
        for child in children:
            self.pgMain.AppendIn(prop, child)
        # self.pgMain.EndAddChildren()
    
    def getPropertyByName(self, name):
        """Get a property from the property grid by name.

        Parameters
        ----------
        name : str
            Name of the property to retrieve.

        Returns
        -------
        wx.propgrid.PGProperty or None
            Property with the specified name, or `None` if not found.

        """
        return self.pgMain.GetPropertyByName(name)
    
    def getPropertyParent(self, prop):
        """Get the parent of a property in the property grid.

        Parameters
        ----------
        prop : wx.propgrid.PGProperty
            Property to retrieve the parent for.

        Returns
        -------
        wx.propgrid.PGProperty or None
            Parent property of the specified property, or `None` if not found.

        """
        return prop.GetParent()

    def getPropertyParentByName(self, name):
        """Get the parent of a property in the property grid.

        Parameters
        ----------
        name : str
            Name of the property to retrieve the parent for.

        Returns
        -------
        wx.propgrid.PGProperty or None
            Parent property of the specified property, or `None` if not found.

        """
        prop = self.getPropertyByName(name)
        if prop is not None:
            return prop.GetParent()

        return None

    def setPropertyChangeCallback(self, name, callback):
        """Set a callback for a property change.

        Sets a callback function to be called when the value of a property is
        changed.

        Parameters
        ----------
        name : str
            Name of the property to set the callback for.
        callback : callable
            Callback function to set for the property.

        """
        prop = self.getPropertyByName(name)
        if prop is not None:
            prop.OnSetValue = callback

    def addStringProperty(self, label, value, name=None, hint=None, 
            readOnly=False, visible=True):
        """Add a property to the property grid.

        Parameters
        ----------
        label : str
            Label for the property.
        value : Any
            Value for the property.
        name : str or None
            Name for the property. Default is `None`.
        hint : str or None
            Hint for the property. Default is `None`.
        readOnly : bool
            Set the property as read-only. Default is `False`.
        visible : bool
            Set the property as visible. Default is `True`.
        
        Returns
        -------
        wx.propgrid.PGProperty
            Property added to the property grid.

        """
        if name is None:
            name = label

        prop = pg.StringProperty(label, name, value)
        self._setPropAttributes(prop, hint, readOnly, visible)

        self.pgMain.Append(prop)

        return prop

    def addIntProperty(self, label, value, name=None, hint=None,
                readOnly=False, visible=True):
        """Add an integer property to the property grid.

        Parameters
        ----------
        label : str
            Label for the property.
        value : int
            Value for the property.
        name : str or None
            Name for the property. Default is `None`.
        hint : str or None
            Hint for the property. Default is `None`.
        readOnly : bool
            Set the property as read-only. Default is `False`.
        visible : bool
            Set the property as visible. Default is `True`.

        Returns
        -------
        wx.propgrid.PGProperty
            Property added to the property grid.

        """
        if name is None:
            name = label

        prop = pg.IntProperty(label, name, value)
        self._setPropAttributes(prop, hint, readOnly, visible)

        self.pgMain.Append(prop)

        return prop

    def addFloatProperty(self, label, value, name=None, hint=None,
                         readOnly=False, visible=True):
        """Add a float property to the property grid.

        Parameters
        ----------
        label : str
            Label for the property.
        value : float
            Value for the property.
        name : str or None
            Name for the property. Default is `None`.
        hint : str or None
            Hint for the property. Default is `None`.
        readOnly : bool
            Set the property as read-only. Default is `False`.
        visible : bool
            Set the property as visible. Default is `True`.
        
        Returns
        -------
        wx.propgrid.PGProperty
            Property added to the property grid.

        """
        if name is None:
            name = label

        prop = pg.FloatProperty(label, name, value)
        self._setPropAttributes(prop, hint, readOnly, visible)

        self.pgMain.Append(prop)

        return prop
    
    def addBoolProperty(self, label, value, name=None, hint=None,
                        readOnly=False, visible=True):
        """Add a boolean property to the property grid.

        Parameters
        ----------
        label : str
            Label for the property.
        value : bool
            Value for the property.
        name : str or None
            Name for the property. Default is `None`.
        hint : str or None
            Hint for the property. Default is `None`.
        readOnly : bool
            Set the property as read-only. Default is `False`.
        visible : bool
            Set the property as visible. Default is `True`.
        
        Returns
        -------
        wx.propgrid.PGProperty
            Property added to the property grid.

        """
        if name is None:
            name = label

        prop = pg.BoolProperty(label, name, value)
        self._setPropAttributes(prop, hint, readOnly, visible)

        self.pgMain.Append(prop)

        return prop
    
    def addEnumProperty(self, label, choices, value, name=None, hint=None,
                        readOnly=False, visible=True):
        """Add an enumeration property to the property grid.

        Parameters
        ----------
        label : str
            Label for the property.
        choices : list
            List of choices for the enumeration.
        value : Any
            Value for the property.
        name : str or None
            Name for the property. Default is `None`.
        hint : str or None
            Hint for the property. Default is `None`.
        readOnly : bool
            Set the property as read-only. Default is `False`.
        visible : bool
            Set the property as visible. Default is `True`.

        Returns
        -------
        wx.propgrid.PGProperty
            Property added to the property grid.

        """
        if name is None:
            name = label
        
        valData = wx.propgrid.PGChoices(choices)
        prop = pg.EnumProperty(label, name, valData, value)
        self._setPropAttributes(prop, hint, readOnly, visible)

        self.pgMain.Append(prop)

        return prop

    def addDirProperty(self, label, value, name=None, hint=None, readOnly=False, 
                       visible=True):
        """Add a directory property to the property grid.

        Parameters
        ----------
        label : str
            Label for the property.
        value : str
            Value for the property.
        name : str or None
            Name for the property. Default is `None`.
        hint : str or None
            Hint for the property. Default is `None`.
        readOnly : bool
            Set the property as read-only. Default is `False`.
        visible : bool
            Set the property as visible. Default is `True`.
        
        Returns
        -------
        wx.propgrid.PGProperty
            Property added to the property grid.

        """
        if name is None:
            name = label

        prop = pg.DirProperty(label, name, value)
        self._setPropAttributes(prop, hint, readOnly, visible)

        self.pgMain.Append(prop)

        return prop
        
    def addFileProperty(self, label, value, name=None, hint=None, 
                        readOnly=False, visible=True):
        """Add a file property to the property grid.

        Parameters
        ----------
        label : str
            Label for the property.
        value : str
            Value for the property.
        name : str or None
            Name for the property. Default is `None`.
        hint : str or None
            Hint for the property. Default is `None`.
        readOnly : bool
            Set the property as read-only. Default is `False`.
        visible : bool
            Set the property as visible. Default is `True`.

        Returns
        -------
        wx.propgrid.PGProperty
            Property added to the property grid.

        """
        if name is None:
            name = label

        prop = pg.FileProperty(label, name, value)
        self._setPropAttributes(prop, hint, readOnly, visible)

        self.pgMain.Append(prop)

        return prop

    def addDateProperty(self, label, value, name=None, hint=None,
                        readOnly=False, visible=True):
        """Add a date property to the property grid.

        Parameters
        ----------
        label : str
            Label for the property.
        value : wx.DateTime
            Value for the property.
        name : str or None
            Name for the property. Default is `None`.
        hint : str or None
            Hint for the property. Default is `None`.
        readOnly : bool
            Set the property as read-only. Default is `False`.
        visible : bool
            Set the property as visible. Default is `True`.

        Returns
        -------
        wx.propgrid.PGProperty
            Property added to the property grid.

        """
        if name is None:
            name = label

        prop = pg.DateProperty(label, name, value)
        self._setPropAttributes(prop, hint, readOnly, visible)

        self.pgMain.Append(prop)

        return prop

    def addImageFileProperty(self, label, value, name=None, hint=None,
                             readOnly=False, visible=True):
        """Add an image file property to the property grid.

        Parameters
        ----------
        label : str
            Label for the property.
        value : str
            Value for the property.
        name : str or None
            Name for the property. Default is `None`.
        hint : str or None
            Hint for the property. Default is `None`.
        readOnly : bool
            Set the property as read-only. Default is `False`.
        visible : bool
            Set the property as visible. Default is `True`.

        Returns
        -------
        wx.propgrid.PGProperty
            Property added to the property grid.

        """
        if name is None:
            name = label

        prop = pg.ImageFileProperty(label, name, value)
        self._setPropAttributes(prop, hint, readOnly, visible)

        self.pgMain.Append(prop)

        return prop
    
    def addColourProperty(self, label, value, name=None, hint=None,
                          readOnly=False, visible=True):
        """Add a colour property to the property grid.

        Parameters
        ----------
        label : str
            Label for the property.
        value : wx.Colour
            Value for the property.
        name : str or None
            Name for the property. Default is `None`.
        hint : str or None
            Hint for the property. Default is `None`.
        readOnly : bool
            Set the property as read-only. Default is `False`.
        visible : bool
            Set the property as visible. Default is `True`.

        Returns
        -------
        wx.propgrid.PGProperty
            Property added to the property grid.

        """
        if name is None:
            name = label

        prop = pg.ColourProperty(label, name, value)
        self._setPropAttributes(prop, hint, readOnly, visible)

        self.pgMain.Append(prop)

        return prop
    
    def addFontProperty(self, label, value, name=None, hint=None,
                        readOnly=False, visible=True):
        """Add a font property to the property grid.

        Parameters
        ----------
        label : str
            Label for the property.
        value : wx.Font
            Value for the property.
        name : str or None
            Name for the property. Default is `None`.
        hint : str or None
            Hint for the property. Default is `None`.
        readOnly : bool
            Set the property as read-only. Default is `False`.
        visible : bool
            Set the property as visible. Default is `True`.

        Returns
        -------
        wx.propgrid.PGProperty
            Property added to the property grid.

        """
        if name is None:
            name = label

        prop = pg.FontProperty(label, name, value)
        self._setPropAttributes(prop, hint, readOnly, visible)

        self.pgMain.Append(prop)

        return prop

    def addLongStringProperty(self, label, value, name=None, hint=None,
                              readOnly=False, visible=True):
        """Add a long string property to the property grid.

        Parameters
        ----------
        label : str
            Label for the property.
        value : str
            Value for the property.
        name : str or None
            Name for the property. Default is `None`.
        hint : str or None
            Hint for the property. Default is `None`.
        readOnly : bool
            Set the property as read-only. Default is `False`.
        visible : bool
            Set the property as visible. Default is `True`.

        Returns
        -------
        wx.propgrid.PGProperty
            Property added to the property grid.

        """
        if name is None:
            name = label

        prop = pg.LongStringProperty(label, name, value)
        self._setPropAttributes(prop, hint, readOnly, visible)

        self.pgMain.Append(prop)

        return prop

    def addMultiChoiceProperty(self, label, value, choices, name=None, 
                               hint=None, readOnly=False, visible=True):
        """Add a multi-choice property to the property grid.

        Parameters
        ----------
        label : str
            Label for the property.
        value : Any
            Value for the property.
        choices : list
            List of choices for the property.
        name : str or None
            Name for the property. Default is `None`.
        hint : str or None
            Hint for the property. Default is `None`.
        readOnly : bool
            Set the property as read-only. Default is `False`.
        visible : bool
            Set the property as visible. Default is `True`.

        Returns
        -------
        wx.propgrid.PGProperty
            Property added to the property grid.

        """
        if name is None:
            name = label
        
        prop = pg.MultiChoiceProperty(label, name, choices, value)
        self._setPropAttributes(prop, hint, readOnly, visible)

        self.pgMain.Append(prop)

        return prop

    def addArrayStringProperty(self, label, value, name=None, hint=None,
                               readOnly=False, visible=True):
        """Add an array string property to the property grid.

        Parameters
        ----------
        label : str
            Label for the property.
        value : list
            List of strings for the property.
        name : str or None
            Name for the property. Default is `None`.
        hint : str or None
            Hint for the property. Default is `None`.
        readOnly : bool
            Set the property as read-only. Default is `False`.
        visible : bool
            Set the property as visible. Default is `True`.

        Returns
        -------
        wx.propgrid.PGProperty
            Property added to the property grid.

        """
        if name is None:
            name = label

        prop = pg.ArrayStringProperty(label, name, value)
        self._setPropAttributes(prop, hint, readOnly, visible)

        self.pgMain.Append(prop)

        return prop

    def addNumericProperty(self, label, value, name=None, hint=None,
                           readOnly=False, visible=True):
        """Add a numeric property to the property grid.

        Parameters
        ----------
        label : str
            Label for the property.
        value : Any
            Value for the property.
        name : str or None
            Name for the property. Default is `None`.
        hint : str or None
            Hint for the property. Default is `None`.
        readOnly : bool
            Set the property as read-only. Default is `False`.
        visible : bool
            Set the property as visible. Default is `True`.

        Returns
        -------
        wx.propgrid.PGProperty
            Property added to the property grid.

        """
        if name is None:
            name = label

        prop = pg.NumericProperty(label, name, value)
        self._setPropAttributes(prop, hint, readOnly, visible)

        self.pgMain.Append(prop)

        return prop

    def addEditEnumProperty(self, label, value, choices, name=None, hint=None,
                            readOnly=False, visible=True):
        """Add an editable enumeration property to the property grid.

        Parameters
        ----------
        label : str
            Label for the property.
        value : Any
            Value for the property.
        choices : list
            List of choices for the enumeration.
        name : str or None
            Name for the property. Default is `None`.
        hint : str or None
            Hint for the property. Default is `None`.
        readOnly : bool
            Set the property as read-only. Default is `False`.
        visible : bool
            Set the property as visible. Default is `True`.

        Returns
        -------
        wx.propgrid.PGProperty
            Property added to the property grid.

        """
        if name is None:
            name = label

        prop = pg.EditEnumProperty(label, name, choices, value)
        self._setPropAttributes(prop, hint, readOnly, visible)

        self.pgMain.Append(prop)

    def addColorValueProperty(self, label, value, name=None, hint=None,
                              readOnly=False, visible=True):
        """Add a color value property to the property grid.

        Parameters
        ----------
        label : str
            Label for the property.
        value : wx.Colour
            Value for the property.
        name : str or None
            Name for the property. Default is `None`.
        hint : str or None
            Hint for the property. Default is `None`.
        readOnly : bool
            Set the property as read-only. Default is `False`.
        visible : bool
            Set the property as visible. Default is `True`.

        Returns
        -------
        wx.propgrid.PGProperty
            Property added to the property grid.

        """
        if name is None:
            name = label

        prop = pg.ColorProperty(label, name, value)
        self._setPropAttributes(prop, hint, readOnly, visible)

        self.pgMain.Append(prop)

        return prop

    def addFlagsProperty(self, label, value, choices, name=None, hint=None,
                         readOnly=False, visible=True):
        """Add a flags property to the property grid.

        Parameters
        ----------
        label : str
            Label for the property.
        value : int
            Value for the property.
        choices : list
            List of choices for the flags.
        name : str or None
            Name for the property. Default is `None`.
        hint : str or None
            Hint for the property. Default is `None`.
        readOnly : bool
            Set the property as read-only. Default is `False`.
        visible : bool
            Set the property as visible. Default is `True`.

        Returns
        -------
        wx.propgrid.PGProperty
            Property added to the property grid.

        """
        if name is None:
            name = label

        prop = pg.FlagsProperty(label, name, choices, value)
        self._setPropAttributes(prop, hint, readOnly, visible)

        self.pgMain.Append(prop)

        return prop

    def addCustomProperty(self, prop, name=None, label=None, hint=None, 
                          readOnly=False, visible=True):
        """Add a custom property to the property grid.

        Custom properties should be subclasses of `wx.propgrid.PGProperty`,
        `wx.propgrid.EditorDialogProperty` or similar.

        Parameters
        ----------
        prop : wx.propgrid.PGProperty
            Custom property to add to the property grid.
        name : str or None
            Name for the property. Default is `None`.
        hint : str or None
            Hint for the property. Default is `None`.
        readOnly : bool
            Set the property as read-only. Default is `False`.
        visible : bool
            Set the property as visible. Default is `True`.
        
        Returns
        -------
        wx.propgrid.PGProperty
            Property added to the property grid.

        """
        if name is None:
            name = label

        self._setPropAttributes(prop, hint, readOnly, visible)
        self.pgMain.Append(prop)

        return prop

    def getValues(self):
        """Get the values of all properties in the property grid.

        Returns
        -------
        dict
            Dictionary of property names and their values.

        """
        values = {}
        for prop in self.pgMain.GetProperties():
            values[prop.GetName()] = prop.GetValue()

        return values


# class VectorProperty(pg.StringProperty):
#     """Property for a vector value.

#     This class is a property for a vector value that can be displayed in the
#     property grid.

#     Parameters
#     ----------
#     label : str
#         Label for the property.
#     name : str
#         Name for the property.
#     value : Any
#         Value for the property.
#     hint : str or None
#         Hint for the property. Default is `None`.
#     readOnly : bool
#         Set the property as read-only. Default is `False`.
#     visible : bool
#         Set the property as visible. Default is `True`.

#     """
#     def __init__(self, label, name, value, hint=None, readOnly=False, 
#                  visible=True):
#         pg.StringProperty.__init__(self, label, name, value)

#         self.SetAttribute("Hint", hint)
#         self.SetAttribute("ReadOnly", readOnly)
#         self.SetAttribute("Visible", visible)

#         self._children = []
#         for lbl in ['X', 'Y', 'Z']:
#             self._children.append(pg.FloatProperty(lbl, lbl, 0.0))

#         for child in self._children:
#             self.AppendChild(child)

#     def OnSetValue(self):
#         # geet child values
#         x = self._children[0].GetValue()
#         y = self._children[1].GetValue()
#         z = self._children[2].GetValue()

#         # set the value
#         self.SetValue("({}, {}, {})".format(x, y, z))

#     def __del__(self):
#         pass


if __name__ == "__main__":
    pass
