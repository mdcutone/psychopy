#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2024 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

import wx
import wx.xrc
import wx.grid
import csv

# Constants for the data editor actions

DV_ACTION_INSERT_COL = 101
DV_ACTION_DELETE_COL = 102
DV_ACTION_RENAME_COL = 103
DV_ACTION_FILL_COL = 104


class BaseDataEditor(wx.Panel):
    """Base class for the DataEditor panel in the Coder view. 

    This class is a wx.Panel that contains a wx.grid.Grid object for editing
    tabulardata without the need for external software. It is used in the Coder
    view of the PsychoPy application. 

    """
    def __init__(self, parent, id = wx.ID_ANY, pos = wx.DefaultPosition, 
            size = wx.Size( 500,300 ), style = wx.TAB_TRAVERSAL, 
            name = wx.EmptyString ):

        wx.Panel.__init__ (self, parent, id=id, pos=pos, size=size, style=style, 
                name=name)

        szrDataEditorMain = wx.BoxSizer( wx.VERTICAL )

        self.ibrDataEditorInfoBar = wx.InfoBar( self )
        self.ibrDataEditorInfoBar.SetShowHideEffects(
            wx.SHOW_EFFECT_NONE, wx.SHOW_EFFECT_NONE)
        self.ibrDataEditorInfoBar.SetEffectDuration( 500 )
        self.ibrDataEditorInfoBar.Hide()

        szrDataEditorMain.Add(self.ibrDataEditorInfoBar, 0, wx.EXPAND, 5)

        self.grdDataEditor = wx.grid.Grid(
            self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, 0)

        # Grid
        #self.grdDataEditor.CreateGrid( 5, 5 )
        self.grdDataEditor.EnableEditing( True )
        self.grdDataEditor.EnableGridLines( True )
        self.grdDataEditor.EnableDragGridSize( False )
        self.grdDataEditor.SetMargins( 0, 0 )

        # Columns
        self.grdDataEditor.EnableDragColMove( False )
        self.grdDataEditor.EnableDragColSize( True )
        self.grdDataEditor.SetColLabelAlignment( wx.ALIGN_CENTER, wx.ALIGN_CENTER )

        # Rows
        self.grdDataEditor.EnableDragRowMove( True )
        self.grdDataEditor.EnableDragRowSize( True )
        self.grdDataEditor.SetRowLabelAlignment( wx.ALIGN_CENTER, wx.ALIGN_CENTER )

        # Label Appearance

        # Cell Defaults
        self.grdDataEditor.SetDefaultCellAlignment( wx.ALIGN_LEFT, wx.ALIGN_TOP )
        szrDataEditorMain.Add( self.grdDataEditor, 1, wx.ALL|wx.EXPAND, 0 )


        self.SetSizer( szrDataEditorMain )
        self.Layout()

        # Connect Events
        self.grdDataEditor.Bind( wx.grid.EVT_GRID_CELL_CHANGED, self.OnGridCellChange )
        self.grdDataEditor.Bind( wx.grid.EVT_GRID_CELL_LEFT_CLICK, self.OnGridCellLeftClick )
        self.grdDataEditor.Bind( wx.grid.EVT_GRID_CELL_RIGHT_CLICK, self.OnGridCellRightClick )
        self.grdDataEditor.Bind( wx.grid.EVT_GRID_CELL_CHANGED, self.OnGridCmdCellChange )
        self.grdDataEditor.Bind( wx.grid.EVT_GRID_SELECT_CELL, self.OnGridCmdSelectCell )
        self.grdDataEditor.Bind( wx.grid.EVT_GRID_EDITOR_CREATED, self.OnGridEditorCreated )
        self.grdDataEditor.Bind( wx.grid.EVT_GRID_LABEL_LEFT_CLICK, self.OnGridLabelLeftClick )
        self.grdDataEditor.Bind( wx.grid.EVT_GRID_LABEL_RIGHT_CLICK, self.OnGridLabelRightClick )
        # self.grdDataEditor.Bind( wx.grid.EVT_GRID_RANGE_SELECT, self.OnGridRangeSelect )
        # self.grdDataEditor.Bind( wx.grid.EVT_GRID_SELECT_CELL, self.OnGridSelectCell )

    def __del__( self ):
        pass

    def OnGridCellChange( self, event ):
        event.Skip()

    def OnGridCellLeftClick( self, event ):
        event.Skip()

    def OnGridCellRightClick( self, event ):
        event.Skip()

    def OnGridCmdCellChange( self, event ):
        event.Skip()

    def OnGridCmdSelectCell( self, event ):
        event.Skip()

    def OnGridEditorCreated( self, event ):
        event.Skip()

    def OnGridLabelLeftClick( self, event ):
        event.Skip()

    def OnGridLabelRightClick( self, event ):
        event.Skip()

    def OnGridRangeSelect( self, event ):
        event.Skip()

    def OnGridSelectCell( self, event ):
        event.Skip()


class DataEditor(BaseDataEditor):
    """DataEditor class for the Coder view in PsychoPy.

    This class is a wx.Panel that contains a wx.grid.Grid object for editing
    tabular data without the need for external software. It is used in the Coder
    view of the PsychoPy application and appears in the document pane of the
    Coder view.

    This object suppors basic grid editing features such as inserting, deleting,
    and renaming columns, as well as inserting and deleting rows. It also has an
    undo/redo stack for reverting changes to the data.

    Parameters
    ----------
    parent : wx.Window
        The parent window of the DataEditor panel.
    id : int
        The window identifier for the DataEditor panel.
    pos : wx.Point
        The position of the DataEditor panel.
    size : wx.Size
        The size of the DataEditor panel.
    style : int
        The window style of the DataEditor panel.
    name : str
        The name of the DataEditor panel.

    """
    def __init__(self, parent, id = wx.ID_ANY, pos = wx.DefaultPosition, 
            size = wx.Size( 500,300 ), style = wx.TAB_TRAVERSAL, 
            name = wx.EmptyString):
        super(DataEditor, self).__init__(parent, id, pos, size, style, name)

        self._readOnly = False
        self._data = []  # store the data in a 2D list

        # undo and redo stacks
        self._undoStack = []

    @property
    def readOnly(self, value):
        """Flag to set the DataEditor grid to read-only mode. This prevents
        accidentatlly editing the data in the grid.
        """
        return self._readOnly

    @readOnly.setter
    def readOnly(self, value):
        self._readOnly = value
        self.grdDataEditor.EnableEditing(not value)

    def _showDataImportDialog(self):
        """Show dialog to provide options on how to load the file."""
        pass

    def _showDataExportDialog(self):
        """Show dialog to provide options on how to save the file."""
        pass

    def loadFile(self, filename, header=True, delimiter=','):
        """Load a CSV file into the DataEditor grid.

        Parameters
        ----------
        filename : str
            The filename of the CSV file to load into the DataEditor grid.

        """
        # load a CSV file into the grid, replacing the current data
        with open(filename, 'r') as f:
            reader = csv.reader(f)
            self._data = list(reader)

        # clear the grid
        self.grdDataEditor.ClearGrid()

        # set the grid size to match the data
        self.grdDataEditor.CreateGrid(len(self._data), len(self._data[0]))

        # if we have a header, use the first row as the column labels
        if header:
            for j, cell in enumerate(self._data[0]):
                self.grdDataEditor.SetColLabelValue(j, cell)

            # remove the header from the data
            self._data = self._data[1:]

        # populate the grid with the data
        for i, row in enumerate(self._data):
            for j, cell in enumerate(row):
                self.grdDataEditor.SetCellValue(i, j, cell)

        # resize all the columns to fit the data
        self.grdDataEditor.AutoSizeColumns()

    def saveFile(self, filename):
        """Save the DataEditor grid to a CSV file.

        Parameters
        ----------
        filename : str
            The filename of the CSV file to save the DataEditor grid to.

        """
        # get all the data from the grid and create a 2D list
        data = []
        for i in range(self.grdDataEditor.GetNumberRows()):
            row = []
            for j in range(self.grdDataEditor.GetNumberCols()):
                row.append(self.grdDataEditor.GetCellValue(i, j))
            data.append(row)

        # write the data to a CSV file
        with open(filename, 'w') as f:
            writer = csv.writer(f)
            writer.writerows(data)

    def refreshRowLabels(self):
        """Refresh the row labels in the DataEditor grid.
        """
        # refresh the row labels in the grid widget
        for i in range(self.grdDataEditor.GetNumberRows()):
            self.grdDataEditor.SetRowLabelValue(i, str(i))

    def coordValid(self, coord):
        """Check if the given coordinate is valid for the DataEditor grid.

        Parameters
        ----------
        coord : tuple
            The (row, column) index to check.

        Returns
        -------
        bool
            True if the coordinate is valid, False otherwise.

        """
        nRow = self.grdDataEditor.GetNumberRows()
        nCol = self.grdDataEditor.GetNumberCols()
        return coord[0] >= 0 and coord[0] < nRow and coord[1] >= 0 and \
            coord[1] < nCol

    def clearSelection(self):
        """Clear the selection in the DataEditor grid.
        """
        # clear the selection in the grid widget
        self.grdDataEditor.ClearSelection()

    def renameColumn(self, index, newName):
        """Rename a column in the DataEditor grid.

        Parameters
        ----------
        index : int
            The index of the column to rename.
        newName : str
            The new name for the column.

        """
        # show a text entry dialog to get the new column name
        currentLabel = self.grdDataEditor.GetColLabelValue(index)
        dlg = wx.TextEntryDialog(self, 'Enter the new column name:', 
                'Rename Column', value=currentLabel)

        if dlg.ShowModal() == wx.ID_OK:
            newName = dlg.GetValue()
            self.grdDataEditor.SetColLabelValue(index, newName)
            # rename a column in the grid widget
            self.grdDataEditor.SetColLabelValue(index, newName)

        dlg.Destroy()

    def insertColumn(self, index):
        """Insert a column into the DataEditor grid.

        Parameters
        ----------
        index : int
            The index to insert the new column at.

        """
        # insert a new column into the grid widget
        self.grdDataEditor.InsertCols(index)

    def deleteColumn(self, index):
        """Delete a column from the DataEditor grid.

        Parameters
        ----------
        index : int
            The index of the column to delete.

        """
        # clear selection to prevent error when deleting the last column
        self.clearSelection()
        # delete a column from the grid widget
        self.grdDataEditor.DeleteCols(index)

    def insertRow(self, index):
        """Insert a row into the DataEditor grid.

        Parameters
        ----------
        index : int
            The index to insert the new row at.

        """
        # insert a new row into the grid widget
        self.grdDataEditor.InsertRows(index)

    def deleteRow(self, index):
        """Delete a row from the DataEditor grid.

        Parameters
        ----------
        index : int
            The index of the row to delete.

        """
        # clear selection to prevent error when deleting the last row
        self.clearSelection()
        # delete a row from the grid widget
        self.grdDataEditor.DeleteRows(index)

    def fillColumn(self, index, value):
        """Fill a column in the DataEditor grid with a value.

        Parameters
        ----------
        index : int
            The index of the column to fill.
        value : str
            The value to fill the column with.

        """
        # fill a column in the grid widget with a value
        for i in range(self.grdDataEditor.GetNumberRows()):
            self.grdDataEditor.SetCellValue(i, index, value)

    def fillCellRange(self, topLeft, bottomRight, value):
        """Fill a range of cells in the DataEditor grid with a value.

        Parameters
        ----------
        topLeft : tuple
            The (row, column) index of the top left cell in the range.
        bottomRight : tuple
            The (row, column) index of the bottom right cell in the range.
        value : str
            The value to fill the range of cells with.

        """
        # fill a range of cells in the grid widget with a value
        for i in range(topLeft[0], bottomRight[0]+1):
            for j in range(topLeft[1], bottomRight[1]+1):
                self.grdDataEditor.SetCellValue(i, j, value)
    
    def fillCellSelection(self, value):
        """Fill the selected cells in the DataEditor grid with a value.

        This method will fill the selected cells with the given value. If no
        cells are selected, it will fill the cell at the cursor.

        Parameters
        ----------
        value : str
            The value to fill the selected cells with.

        """
        selectedCells = self.grdDataEditor.GetSelectedCells()  # buggy
        if not selectedCells:
            topLeftCoord = self.grdDataEditor.GetSelectionBlockTopLeft()
            if topLeftCoord:
                bottomRightCoord = \
                    self.grdDataEditor.GetSelectionBlockBottomRight()
                # fill the cell range with the value
                self.fillCellRange(topLeftCoord[0], bottomRightCoord[0], value)
            else:
                # get the cell at the cursor and fill it with the value
                cursor = self.getCursorCoord()
                self.grdDataEditor.SetCellValue(cursor[0], cursor[1], value)
        else:
            for cell in cells:
                self.grdDataEditor.SetCellValue(cell[0], cell[1], value)
    
    def getCursorCoord(self):
        """Get the current cursor coordinates in the DataEditor grid.

        Returns
        -------
        tuple
            The (row, column) index of the current cursor position.

        """
        return self.grdDataEditor.GetGridCursorCoords()

    def getCursorValue(self):
        """Get the value of the cell at the current cursor position.

        Returns
        -------
        str
            The value of the cell at the current cursor position.

        """
        cursor = self.getCursorCoord()
        return self.grdDataEditor.GetCellValue(cursor[0], cursor[1])

    def gotoCell(self, row, col):
        """Move the cursor to a specific cell in the DataEditor grid and make it
        visible.

        Parameters
        ----------
        row : int
            The row index of the cell to move to.
        col : int
            The column index of the cell to move to.

        """
        if row < 0 or col < 0:
            return

        # check if we are outside of the grid range
        if row >= self.grdDataEditor.GetNumberRows() or \
                col >= self.grdDataEditor.GetNumberCols():
            return

        # move the cursor to the cell and make it visible
        self.grdDataEditor.GoToCell(row, col)

    def OnGridLabelRightClick(self, event):
        """Handle right click on a column label."""
        # show a menu with options to rename, insert, or delete a column

        selectedColumn = event.GetCol()
        if selectedColumn == -1:
            return

        currentLabel = self.grdDataEditor.GetColLabelValue(selectedColumn)

        def OnColumnMenu(_event):
            """Handle the column menu events.
            """
            id = _event.GetId()
            if id == 101:
                # rename highlighted column
                self.renameColumn(selectedColumn, '')
            elif id == 102:
                # insert a new column
                self.insertColumn(selectedColumn)
            elif id == 103:
                # delete highlighted column
                self.deleteColumn(selectedColumn)
            elif id == 104:
                # fill highlighted column with...
                dlg = wx.TextEntryDialog(self, 
                        'Enter the value to fill the column with:', 
                        'Fill Column', value='')
                if dlg.ShowModal() == wx.ID_OK:
                    value = dlg.GetValue()
                    self.fillColumn(selectedColumn, value)
                dlg.Destroy()
            elif id == 105:
                # auto size the column
                self.grdDataEditor.AutoSizeColumn(selectedColumn)

        # bring up the column menu
        menu = wx.Menu()
        menu.Append(101, "Rename ({})".format(currentLabel))
        menu.Append(102, "Insert")
        menu.Append(103, "Delete")
        menu.AppendSeparator()
        menu.Append(104, "Fill column with...")
        menu.AppendSeparator()
        menu.Append(105, "Auto Size")
        self.Bind(wx.EVT_MENU, OnColumnMenu, id=101)
        self.Bind(wx.EVT_MENU, OnColumnMenu, id=102)
        self.Bind(wx.EVT_MENU, OnColumnMenu, id=103)
        self.Bind(wx.EVT_MENU, OnColumnMenu, id=104)
        self.Bind(wx.EVT_MENU, OnColumnMenu, id=105)
        self.PopupMenu(menu)
        menu.Destroy()

    def OnGridCellRightClick(self, event):
        """Handle right click on a cell."""
        # show a menu with options to insert or delete a row

        selectedRow = event.GetRow()
        selectedColumn = event.GetCol()
        if selectedRow == -1 or selectedColumn == -1:
            return

        def OnCellMenu(_event):
            """Handle the cell menu events.
            """
            id = _event.GetId()
            if id == 201:
                # insert a new row
                self.insertRow(selectedRow)
            elif id == 202:
                # delete highlighted row
                self.deleteRow(selectedRow)
            elif id == 203:
                # fill highlighted cell with...
                currentCellValue = self.getCursorValue()
                dlg = wx.TextEntryDialog(self, 
                        'Enter the value to fill the cell(s) with:', 
                        'Fill Cell(s)', value=str(currentCellValue))
                if dlg.ShowModal() == wx.ID_OK:
                    value = dlg.GetValue()
                    self.fillCellSelection(value)
                dlg.Destroy()

        # bring up the cell menu
        menu = wx.Menu()
        menu.Append(201, "Insert")
        menu.Append(202, "Delete")
        menu.AppendSeparator()
        menu.Append(203, "Fill cell with...")
        self.Bind(wx.EVT_MENU, OnCellMenu, id=201)
        self.Bind(wx.EVT_MENU, OnCellMenu, id=202)
        self.Bind(wx.EVT_MENU, OnCellMenu, id=203)
        self.PopupMenu(menu)
        menu.Destroy()


if __name__ == '__main__':
    pass