#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Part of the PsychoPy library
# Copyright (C) 2009 Jonathan Peirce
# Distributed under the terms of the GNU General Public License (GPL).

import sys
import os
import io
import wx
import wx.lib.agw.aui as aui
from psychopy.app import dialogs
from psychopy.app.coder.codeEditor import CodeEditor
from psychopy.localization import _translate


class EditorNotebook(aui.AuiNotebook):
    """Class for the Editor notebook. This class manages opened documents and
    handles focus.

    """
    def __init__(self, parent, coder, app):
        super(EditorNotebook, self).__init__(
            parent, id=wx.ID_ANY, pos=wx.DefaultPosition, size=wx.DefaultSize,
            style=0, agwStyle=aui.AUI_NB_DEFAULT_STYLE, name="AuiNotebook")

        self.app = app
        self.coder = coder
        self._untitledDocs = 0  # used for naming untitled documents

        self.Bind(aui.EVT_AUINOTEBOOK_PAGE_CLOSE, self.onPageClose)
        self.Bind(aui.EVT_AUINOTEBOOK_PAGE_CHANGED, self.onPageChanged)

    @property
    def currentDoc(self):
        """Document for the currently selected page."""
        return self.GetCurrentPage()

    @property
    def currentPageIdx(self):
        """Index of the currently selected page."""
        return self.GetSelection()

    def _setFrameTitle(self, filename):
        """Show the file name in the header."""
        self.coder.SetLabel(filename + ' - PsychoPy Coder')

    def getOpenFileNames(self):
        """Return the full filename of each open tab.

        Returns
        -------
        list
            List of files currently opened in the editor. An empty list means
            that no files are opened.

        """
        return [self.GetPage(i).filename for i in range(self.GetPageCount())]

    @property
    def openFileNames(self):
        """List of open file names. An empty list indicates no files are
        currently opened."""
        return self.getOpenFileNames()

    def getPages(self):
        """Get a list of pages."""
        return [self.GetPage(i) for i in range(self.GetPageCount())]

    @property
    def pages(self):
        """List of editor pages."""
        return self.getPages()

    def _canReadFile(self, filename):
        """Check if a text file can be opened and raise errors.

        Parameters
        ----------
        filename : str
            File to check if it can be opened.

        Returns
        -------
        bool
            `True` if the file can be read.

        """
        # no document is present, open the file
        if not os.path.isfile(filename):  # check if file exists
            # show file not found dialog
            dlg = dialogs.MessageDialog(
                self.coder,
                message='Failed to open {}. Not a file.'.format(filename),
                type='Info')
            dlg.ShowModal()
            dlg.Destroy()
            return False

        # check if we have read access the file
        if not self.checkCanReadFile(filename):
            # show a message that we don't have permission to read the file
            dlg = dialogs.MessageDialog(
                self.coder,
                message='Failed to open {}, no read permission on file.'.format(
                    filename),
                type='Info')
            dlg.ShowModal()
            dlg.Destroy()
            return False

        return True

    def _readFileText(self, filename):
        """Read a file, getting its text and line endings.
        """
        if not self._canReadFile(filename):
            return None

        # now open the file and hold text in a buffer
        try:
            with io.open(filename, 'r', encoding='utf-8-sig') as f:
                fileText = f.read()
                newlines = f.newlines
        except UnicodeDecodeError:
            # show unicode error
            dlg = dialogs.MessageDialog(self, message=_translate(
                'Failed to open `{}`. Make sure that encoding of '
                'the file is utf-8.').format(filename), type='Info')
            dlg.ShowModal()
            dlg.Destroy()
            return None

        return fileText, newlines

    def onPageChanged(self, event):
        """Event called when a page changes."""
        if self.currentDoc is not None:
            self.currentDoc.SetFocus()

        self.updateCoderFrame()

        event.Skip()

    def onPageClose(self, event):
        """Event called when a page closes."""
        event.Skip()

    def updateCoderFrame(self):
        """Update information in the coder frame."""
        self._setFrameTitle(self.currentDoc.filename)

    def newDocument(self, namePrefix='untitled', docType='python'):
        """Create a new document. New documents don't have a file associated
        with them until they are saved.

        Parameters
        ----------
        namePrefix : str
            Prefix to use for the file name. This can be changed for
            localization.
        docType : str
            Document type to use.

        """
        # file extensions for different document types
        fileExts = {'python': '.py', 'plaintext': '.txt'}

        # get next free untitled file name
        while 1:
            tempName = namePrefix + str(self._untitledDocs) + fileExts[docType]
            if self.findDocID(tempName) != -1:  # not free, increment suffix
                self._untitledDocs += 1
            else:
                break

        # create a new editor object, set the file name
        doc = CodeEditor(self, -1, frame=self.coder)
        doc.filename = tempName
        doc.EmptyUndoBuffer()

        # add a new page, configure it
        self.AddPage(doc, tempName, select=True)
        doc.setLexerFromFileName()  # chose the best lexer

        self._untitledDocs += 1  # increment the document number

    def openDocument(self, filename, keepHidden=False):
        """Open a file and add the page to the editor. Will not create another
        page if a document with the same file name is already opened unless it's
        newer on the disk.

        Parameters
        ----------
        filename : str
            Name of the file to make current.

        Returns
        -------
        bool
            `True` if the document has been loaded successfully or exists
            already.

        """
        # check if the document is already open
        docIdx = self.findDocID(filename)
        if docIdx >= 0:
            if self.checkModifiedOnDisk(filename):
                # ask if the user wants to reload the file
                dlg = wx.MessageDialog(
                    self.coder,
                    ("File currently opened but a newer version exists on disk."
                     " Would you like to continue opening the file? Changes "
                     "will be overwritten."),
                    caption="Reload file?",
                    style=wx.YES_NO | wx.CENTRE | wx.NO_DEFAULT,
                    pos=wx.DefaultPosition)
                if dlg.ShowModal() == wx.ID_YES:
                    self.reloadDocument(filename)
                dlg.Destroy()

            # returns whether the document is opened or not
            return self.setDocument(docIdx)

        # read the file
        fileInfo = self._readFileText(filename)
        if fileInfo is None:  # failed to read file
            return False

        # create a new editor object, set the file name
        doc = CodeEditor(self, -1, frame=self.coder)
        doc.filename = filename

        # set the text read from the file
        fileText, newlines = fileInfo
        doc.SetText(fileText)
        doc.newlines = newlines
        del fileText  # delete the buffer

        # set the file modification and configure the undo buffer
        doc.fileModTime = os.path.getmtime(filename)
        doc.EmptyUndoBuffer()
        doc.setLexerFromFileName()  # chose the best lexer

        # add a new page, name it and configure
        _, shortName = os.path.split(filename)
        self.AddPage(doc, shortName, select=(not keepHidden))

        # set the page and raise coder
        if not keepHidden:
            self.coder.Raise()

        return True

    def closeDocument(self, filename=None):
        """Close a document. If file name is not specified, the current document
        will be closed.
        """
        pass

    def setDocument(self, docIdx):
        """Set the current document. Automatically switches to the tab the
        document is opened and sets focus to the editor. Also checks if the file
        has been modified on the disk requesting whether to reload it.

        Parameters
        ----------
        docIdx : idx
            Page index of the document.

        """
        self._setFrameTitle(self.currentDoc.filename)

        if hasattr(self, 'structureWindow'):
            self.coder.statusBar.SetStatusText(_translate('Analyzing code'))
            self.currentDoc.analyseScript()
            self.coder.statusBar.SetStatusText('')

        self.coder._applyAppTheme()

    def getDocument(self, filename=None):
        """Get the editor object associated with a given file name. If `None`
        the current focused document is returned."""
        if filename is None:
            return self.currentDoc

        doc = self.findDocID(filename)
        if doc != -1:
            return self.GetPage(doc)

    def saveDocument(self, filename=None):
        """Save the current document to a file.

        Parameters
        ----------
        filename : str
            File name of document to save. If `None`, the document with focus
            will be saved.

        """
        pass

    def saveAsDocument(self, filename=None):
        """Save document to another file. Will prompt for another file name and
        update document's file name.

        Parameters
        ----------
        filename : str
            File name of document to save and rename. If `None`, the document
            with focus will be saved.

        """
        pass

    def checkModifiedOnDisk(self, filename=None):
        """Check if there is a modified version of the file on disk."""
        doc = self.getDocument(filename)

        if doc is None:  # if the document does not exist
            return False

        return doc.fileModTime > os.path.getmtime(filename)

    def reloadDocument(self, filename=None, checkSave=False):
        """Reload a document. Loads text from the file associated with the text
        on the disk and overwrites the content of the editor.

        """
        doc = self.getDocument(filename)  # get handle to the document

        if doc is None:  # might happen, nop
            return False

        # ask if the user wants to save the current file to another before
        # proceeding
        if checkSave:
            pass  # prompt and save

        # read the file
        fileInfo = self._readFileText(doc.filename)
        if fileInfo is None:  # failed to read file
            return False

        # set the text read from the file
        fileText, newlines = fileInfo
        doc.SetText(fileText)
        doc.newlines = newlines
        del fileText  # delete the buffer

        # set the file modification
        doc.fileModTime = os.path.getmtime(doc.filename)

        return True

    def findDocID(self, filename):
        """Get the ID of the page a particular document is on.

        Parameters
        ----------
        filename : str
            Name of the file to make current.

        Returns
        -------
        int
            Page index. If -1, no page exists for the given document.

        """
        for ii in range(self.GetPageCount()):
            if self.GetPage(ii).filename == filename:
                return ii

        return -1

    def setAllReadOnly(self, enable=True):
        """Set all documents as read-only.

        Parameters
        ----------
        enable : bool
            Read-only mode for all documents.

        """
        for ii in range(self.GetPageCount()):
            self.GetPage(ii).readonly = enable

    def getReadOnly(self, filename=None):
        """Get a document to read only.

        Parameters
        ----------
        filename : str
            Name of the file to check if read-only. If `None`, the current
            document will be used.

        Returns
        -------
        bool
            `True` if specified document is read-only.

        """
        if self.currentDoc is not None:
            return self.currentDoc.readonly

    def setReadOnly(self, filename=None, readOnly=True):
        """Set a document to read only.

        Parameters
        ----------
        filename : str
            Name of the file to set as read-only. If `None`, the current
            document will be used.
        readOnly : bool
            Allow writing. Set as `True` to make the document read only.

        """
        if filename is None and self.currentDoc is not None:
            self.currentDoc.readonly = readOnly

    def closeOtherDocs(self, filename=None):
        """Close all other documents other than `filename`. This can be invoked
        to clean up the editor workspace."""

        doc = self.getDocument(filename)

        # no-op if there are no documents open of the file name is invalid
        if doc is None:
            return

        # go over the pages, closing those the do not have the filename
        for page in self.pages:
            if page.filename != doc.filename:
                # since we need the index of the pages, and they change as we
                # close them, lookup the page index of the document
                pageIdxToClose = self.findDocID(page.filename)
                # close the document here ...

    def applyEditorTheme(self):
        """Apply the editor theme to currently opened documents. Needs to be
        called after changing the theme spec. Does not need to be called
        every time a new document page is created, only if the theme prefs have
        changed.

        """
        for ed in self.pages:
            ed.setFont()

    def checkFileOverwrite(self, filename=None):
        """Check if we are going to overwrite a file.

        Returns
        -------
        bool
            `True` if there is a file present that would be overwritten by a
            save operation.

        """
        if filename is None:  # get the file name of current document
            doc = self.getDocument(filename)
            if doc is None:
                return False

            filename = doc.filename

        if not os.path.isabs(filename):  # not absolute path, use CWD
            filename = os.path.join(os.getcwd(), filename)

        return os.path.isfile(filename) and os.access(filename, os.W_OK)

    def checkCanWriteFile(self, filename=None):
        """Check if the file has write access on the disk.

        Returns
        -------
        bool
            `True` if we have write access the the file on disk when this
            function was called. If the file is not present on the disk and
            `filename` is not a absolute path, this will check if we have
            permission to write the file to the current working directory.

        """
        if filename is None:  # get the file name of current document
            doc = self.getDocument(filename)
            if doc is None:
                return False

            filename = doc.filename

        if os.path.isfile(filename):  # is a file
            return os.access(filename, os.W_OK)
        else:  # not a file, check if we can write it
            if os.path.isabs(filename):  # absolute path
                directory, _ = os.path.split(filename)
                return os.access(directory, os.W_OK)
            else:
                return os.access(os.getcwd(), os.W_OK)

    def checkCanReadFile(self, filename=None):
        """Check if we have read access for a file on disk.

        Returns
        -------
        bool
            `True` if we have read access the the file on disk when this
            function was called. Returns `False` if there is not file saved on
            the disk matching `filename`.

        """
        if filename is None:  # get the file name of current document
            doc = self.getDocument(filename)
            if doc is None:
                return False

            filename = doc.filename

        if not os.path.isfile(filename):
            return False

        return os.access(filename, os.R_OK)

    def fileOnDisk(self, filename=None):
        """Check if a given document references a file on disk. If `False`, the
        document is likely in memory and needs to be saved.

        """
        if filename is None:  # get the file name of current document
            doc = self.getDocument(filename)
            if doc is None:
                return False

            filename = doc.filename

        return os.path.isfile(filename)

