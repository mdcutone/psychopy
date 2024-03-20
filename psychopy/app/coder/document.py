#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2024 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

"""Classes and functions for editor documents. 

This module contains the classes for documents objects that can be displayed in
the coder editor view.

Coder is capable of displaying different types of documents, such as text files,
tabular data, and images. Each type of document is represented by a different
class that inherits from the BaseEditorDocument class.

"""

import wx
import wx.stc
import os.path
from pathlib import Path


class BaseEditorDocument:
    """Base class for the editor documents.

    This class is used to define the common methods and attributes of the
    different types of documents that can be opened in the Coder window.

    This class should be subclassed to create the different types of documents
    that can be opened in the Coder window. It expects that the subclass will
    handle the actual loading and saving of the file content. Actions should not
    take arguments, but should use the document's attributes to determine what
    action to take.

    Not all attributes need to be used by all subclasses and they should do
    nothing if they are not used.

    """
    # no need for an init method, subclasses are just inheriting the attributes
    _filename = ""
    _frame = None
    _notebook = None
    _parent = None
    UNSAVED = False
    _fileModTime = None
    _title = ""
    _icon = None

    @property
    def filename(self):
        return self._filename

    @filename.setter
    def filename(self, value):
        self._filename = value

    @property
    def frame(self):
        """Handle to the Coder frame that contains the document."""
        return self._frame

    @frame.setter
    def frame(self, value):
        self._frame = value

    @property
    def notebook(self):
        """Handle to the notebook that contains the document."""
        return self._notebook

    @notebook.setter
    def notebook(self, value):
        self._notebook = value

    @property
    def parent(self):
        """Handle to the parent window of the document."""
        return self._parent

    @parent.setter
    def parent(self, value):
        self._parent = value

    @property
    def modified(self):
        """Check if the document has been modified since it was last saved."""
        return self.UNSAVED

    @modified.setter
    def modified(self, value):
        self.UNSAVED = value

    @property
    def title(self):
        """The title of the document."""
        return self._title

    @title.setter
    def title(self, value):
        self._title = value

    @property
    def icon(self):
        """The icon of the document."""
        return self._icon

    @icon.setter
    def icon(self, value):
        self._icon = value

    @property
    def fileModTime(self):
        """The modification time of the file."""
        return self._fileModTime

    @fileModTime.setter
    def fileModTime(self, value):
        self._fileModTime = value

    # loaders and savers for the doucment content, these should show the
    # appropriate file dialogues
    def loadFile(self):
        """Load the file content into the document."""
        pass

    def saveFile(self):
        """Save the document content to the file."""
        pass

    def reloadFile(self):
        """Reload the file content into the document.
        
        This should also update the file modification time attribute 
        `fileModTime`.
        
        """
        pass

    def getActualModTime(self):
        """Get the current modification time of the file (`float`).
        """
        if self.filename is None:
            return -1.0

        filename = Path(self.filename)
        if not filename.is_file():
            return -1.0

        return float(os.path.getmtime(filename))

    # programmatic interfaces for the UI functions
    def undo(self):
        """Undo the last action."""
        pass

    def redo(self):
        """Redo the last action."""
        pass

    def cut(self):
        """Cut the selected editor content."""
        pass

    def copy(self):
        """Copy the selected editor content."""
        pass

    def paste(self):
        """Paste the clipboard content."""
        pass

    def analyseScript(self):
        """Analyse the script for errors."""
        pass

    def getFileType(self):
        """Get the type of the file."""
        return ''

    def checkChangesOnDisk(self):
        """Check if the file has been modified on disk.
        
        Returns
        -------
        bool
            True if the file has been modified on disk and requires resaving, 
            False otherwise.

        """
        if self.filename is None:
            return True

        # files that don't exist DO have the expected mod-time
        filename = Path(self.filename)
        if not filename.is_file():
            return True

        expectedModTime = self.fileModTime
        if abs(self.getActualModTime() - float(expectedModTime)) > 1:
            # msg = 'File %s modified outside of the Coder (IDE).' % filename
            # print(msg)
            return False

        return True
    
    # event hooks for UI functions
    def onModified(self, evt):
        """Called when the document is modified."""
        evt.Skip()

    def onIdle(self, evt):
        """Called when the application is idle."""
        evt.Skip()

    def onCopy(self, evt):
        """Called when the copy button is pressed."""
        evt.Skip()

    def onCut(self, evt):
        """Called when the cut button is pressed."""
        evt.Skip()

    def onPaste(self, evt):
        """Called when the paste button is pressed."""
        evt.Skip()

    def onUndo(self, evt):
        """Called when the undo button is pressed."""
        evt.Skip()

    def onRedo(self, evt):
        """Called when the redo button is pressed."""
        evt.Skip()

    def onSelectAll(self, evt):
        """Called when the select all button is pressed."""
        evt.Skip()

    def onFind(self, evt):
        """Called when the find button is pressed."""
        evt.Skip()


class BaseStyledTextCtrl(BaseEditorDocument, wx.stc.StyledTextCtrl):
    """Base class for the styled text control used in the editor documents.

    This class is used to define the common methods and attributes of the
    styled text control used in the editor documents.

    This class should be subclassed to create the different types of styled
    text controls that can be used in the editor documents. It expects that the
    subclass will handle

    """
    def __init__(self, parent):
        wx.stc.StyledTextCtrl.__init__(self, parent, wx.ID_ANY)


if __name__ == "__main__":
    pass