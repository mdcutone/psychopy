#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Part of the PsychoPy library
# Copyright (C) 2009 Jonathan Peirce
# Distributed under the terms of the GNU General Public License (GPL).

import os
import textwrap
import wx
import wx.stc
from psychopy.app import dialogs

from ..utils import FileDropTarget
from psychopy.app.coder.codeEditorBase import BaseCodeEditor
from psychopy.app.themes import ThemeMixin
from psychopy.app.coder.folding import CodeEditorFoldingMixin
import psychopy.logging as logging
from psychopy.localization import _translate

try:
    import jedi
    _hasJedi = True
except ImportError:
    logging.error(
        "Package `jedi` not installed, code auto-completion and calltips will "
        "not be available.")
    _hasJedi = False


class CodeEditor(BaseCodeEditor, CodeEditorFoldingMixin, ThemeMixin):
    """Code editor class for the Coder GUI.
    """
    def __init__(self, parent, ID, frame,
                 # set the viewer to be small, then it will increase with aui
                 # control
                 pos=wx.DefaultPosition, size=wx.Size(100, 100),
                 style=wx.BORDER_NONE, readonly=False):
        BaseCodeEditor.__init__(self, parent, ID, pos, size, style)

        self.parent = parent  # page in the auiNotebook
        self.pageIdx = ID
        self.coder = frame
        self.prefs = self.coder.prefs
        self.paths = self.coder.paths
        self.app = self.coder.app
        self.SetViewWhiteSpace(self.coder.appData['showWhitespace'])
        self.SetViewEOL(self.coder.appData['showEOLs'])
        self.Bind(wx.EVT_DROP_FILES, self.coder.filesDropped)
        self.Bind(wx.stc.EVT_STC_MODIFIED, self.onModified)
        self.Bind(wx.stc.EVT_STC_UPDATEUI, self.OnUpdateUI)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyPressed)
        self.Bind(wx.EVT_KEY_UP, self.OnKeyReleased)
        self.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)

        if hasattr(self, 'OnMarginClick'):
            self.Bind(wx.stc.EVT_STC_MARGINCLICK, self.OnMarginClick)

        # black-and-white text signals read-only file open in Coder window
        # if not readonly:
        #     self.setFonts()
        self.SetDropTarget(FileDropTarget(targetFrame=self.coder))

        # set to python syntax code coloring
        self.setLexerFromFileName()

        # Keep track of visual aspects of the source tree viewer when working
        # with this document. This makes sure the tree maintains it's state when
        # moving between documents.
        self.expandedItems = {}

        # show the long line edge guide, enabled if >0
        self.edgeGuideColumn = self.coder.prefs['edgeGuideColumn']
        self.edgeGuideVisible = self.edgeGuideColumn > 0

        # give a little space between the margin and text
        self.SetMarginLeft(4)

        # caret info, these are updated by calling updateCaretInfo()
        self.indentSize = self.GetIndent()
        self.caretCurrentPos = self.GetCurrentPos()
        self.caretVisible, self.caretColumn, self.caretLine = \
            self.PositionToXY(self.caretCurrentPos)

        # where does the line text start?
        self.caretLineIndentCol = \
            self.GetColumn(self.GetLineIndentPosition(self.caretLine))

        # what is the indent level of the line the caret is located
        self.caretLineIndentLevel = self.caretLineIndentCol / self.indentSize

        # is the caret at an indentation level?
        self.caretAtIndentLevel = \
            (self.caretLineIndentCol % self.indentSize) == 0

        # # should hitting backspace result in an untab?
        # self.shouldBackspaceUntab = \
        #     self.caretAtIndentLevel and \
        #     0 < self.caretColumn <= self.caretLineIndentCol
        self.SetBackSpaceUnIndents(True)

        # set the current line and column in the status bar
        self.coder.SetStatusText(
            'Line: {} Col: {}'.format(
                self.caretLine + 1, self.caretColumn + 1), 1)

        # calltips
        self.CallTipSetBackground('#fffdcc')
        self.AutoCompSetIgnoreCase(True)
        self.AutoCompSetAutoHide(True)
        self.AutoCompStops('. ')

        # better font rendering and less flicker on Windows by using Direct2D
        # for rendering instead of GDI
        if wx.Platform == '__WXMSW__':
            self.SetTechnology(3)

        # double buffered better rendering except if retina
        self.SetDoubleBuffered(self.coder.IsDoubleBuffered())

        self.theme = self.prefs['theme']

    def OnSetFocus(self, event):
        """Called when the editor window gets focus."""
        self.coder.currentDoc = self
        self.coder.SetLabel('%s - PsychoPy Coder' % self.filename)

        self.coder.statusBar.SetStatusText(self.getFileType(), 2)

        docId = self.coder.findDocID(self.filename)
        self.parent.SetSelection(docId)

        if hasattr(self.coder, 'structureWindow'):
            self.analyseScript()

        # todo: reduce redundancy w.r.t OnIdle()
        if not self.coder.expectedModTime(self):
            filename = os.path.basename(self.filename)
            msg = _translate("'%s' was modified outside of PsychoPy:\n\n"
                             "Reload (without saving)?") % filename
            dlg = dialogs.MessageDialog(self, message=msg, type='Warning')
            if dlg.ShowModal() == wx.ID_YES:
                self.coder.statusBar.SetStatusText(_translate('Reloading file'))
                self.coder.fileReload(event,
                                      filename=self.filename,
                                      checkSave=False)
                self.coder.setFileModified(False)
            self.coder.statusBar.SetStatusText('')
            try:
                dlg.Destroy()
            except Exception:
                pass

        event.Skip()

    def setFonts(self):
        """Make some styles,  The lexer defines what each style is used for,
        we just have to define what each style looks like.  This set is
        adapted from Scintilla sample property files."""

        if wx.Platform == '__WXMSW__':
            faces = {'size': 10}
        elif wx.Platform == '__WXMAC__':
            faces = {'size': 14}
        else:
            faces = {'size': 12}
        if self.coder.prefs['codeFontSize']:
            faces['size'] = int(self.coder.prefs['codeFontSize'])
        faces['small'] = faces['size'] - 2
        # Global default styles for all languages
        # ,'Arial']  # use arial as backup
        faces['code'] = self.coder.prefs['codeFont']
        # ,'Arial']  # use arial as backup
        faces['comment'] = self.coder.prefs['codeFont']

        # apply the theme to the lexer
        self.theme = self.coder.prefs['theme']

    def setLexerFromFileName(self):
        """Set the lexer to one that best matches the file name."""
        # best matching lexers for a given file type
        lexers = {'Python': 'python',
                  'HTML': 'html',
                  'C/C++': 'cpp',
                  'GLSL': 'cpp',
                  'Arduino': 'cpp',
                  'MATLAB': 'matlab',
                  'YAML': 'yaml',
                  'R': 'R',
                  'JavaScript': 'cpp',
                  'Plain Text': 'null'}

        self.setLexer(lexers[self.getFileType()])

    def getFileType(self):
        """Get the file type from the extension."""
        if os.path.isabs(self.filename):
            _, filen = os.path.split(self.filename)
        else:
            filen = self.filename

        # get the extension, if any
        fsplit = filen.split('.')
        if len(fsplit) > 1:   # has enough splits to have an extension
            ext = fsplit[-1]
        else:
            ext = 'txt'  # assume a text file if we're able to open it

        if ext in ('py', 'pyx', 'pxd', 'pxi',):  # python/cython files
            return 'Python'
        elif ext in ('html',):  # html file
            return 'HTML'
        elif ext in ('cpp', 'c', 'h', 'mex', 'hpp'):  # c-like file
            return 'C/C++'
        elif ext in ('glsl', 'vert', 'frag'):  # OpenGL shader program
            return 'GLSL'
        elif ext in ('m',):  # MATLAB
            return 'MATLAB'
        elif ext in ('ino',):  # Arduino
            return 'Arduino'
        elif ext in ('R',):  # R
            return 'R'
        elif ext in ('yaml',):  # R
            return 'YAML'
        elif ext in ('js',):  # R
            return 'JavaScript'
        else:
            return 'Plain Text'  # default

    def getTextUptoCaret(self):
        """Get the text upto the caret."""
        return self.GetTextRange(0, self.caretCurrentPos)

    def OnKeyReleased(self, event):
        """Called after a key is released."""

        if hasattr(self.coder, "useAutoComp"):
            keyCode = event.GetKeyCode()
            _mods = event.GetModifiers()
            if keyCode == ord('.'):
                if self.coder.useAutoComp:
                    # A dot was entered, get suggestions if part of a qualified name
                    wx.CallAfter(self.ShowAutoCompleteList)  # defer
                else:
                    self.coder.SetStatusText(
                        'Press Ctrl+Space to show code completions', 0)
            elif keyCode == ord('9') and wx.MOD_SHIFT == _mods:
                # A left bracket was entered, check if there is a calltip available
                if self.coder.useAutoComp:
                    if not self.CallTipActive():
                        wx.CallAfter(self.ShowCalltip)
                else:
                    self.coder.SetStatusText(
                        'Press Ctrl+Space to show calltip', 0)
            else:
                self.coder.SetStatusText('', 0)

        event.Skip()

    def OnKeyPressed(self, event):
        """Called when a key is pressed."""
        # various stuff to handle code completion and tooltips
        # enable in the _-init__
        keyCode = event.GetKeyCode()
        _mods = event.GetModifiers()
        # handle some special keys
        if keyCode == ord('[') and wx.MOD_CONTROL == _mods:
            self.indentSelection(-4)
            # if there are no characters on the line then also move caret to
            # end of indentation
            txt, charPos = self.GetCurLine()
            if charPos == 0:
                # if caret is at start of line, move to start of text instead
                self.VCHome()
        elif keyCode == ord(']') and wx.MOD_CONTROL == _mods:
            self.indentSelection(4)
            # if there are no characters on the line then also move caret to
            # end of indentation
            txt, charPos = self.GetCurLine()
            if charPos == 0:
                # if caret is at start of line, move to start of text instead
                self.VCHome()

        elif keyCode == ord('/') and wx.MOD_CONTROL == _mods:
            self.commentLines()
        elif keyCode == ord('/') and wx.MOD_CONTROL | wx.MOD_SHIFT == _mods:
            self.uncommentLines()

        # show completions, very simple at this point
        elif keyCode == wx.WXK_SPACE and wx.MOD_CONTROL == _mods:
            self.ShowAutoCompleteList()

        # show a calltip with signiture
        elif keyCode == wx.WXK_SPACE and wx.MOD_CONTROL | wx.MOD_SHIFT == _mods:
            self.ShowCalltip()

        elif keyCode == wx.WXK_ESCAPE:  # close overlays
            if self.AutoCompActive():
                self.AutoCompCancel()  # close the auto completion list
            if self.CallTipActive():
                self.CallTipCancel()

        elif keyCode == wx.WXK_RETURN: # and not self.AutoCompActive():
            if not self.AutoCompActive():
                # process end of line and then do smart indentation
                event.Skip(False)
                self.CmdKeyExecute(wx.stc.STC_CMD_NEWLINE)
                self.smartIdentThisLine()
                self.analyseScript()
                return  # so that we don't reach the skip line at end

        # quote line
        elif keyCode == ord("'"):
            #raise RuntimeError
            start, end = self.GetSelection()
            if end - start > 0:
                txt = self.GetSelectedText()
                txt = "'" + txt.replace('\n', "'\n'") + "'"
                self.ReplaceSelection(txt)
                event.Skip(False)
                return

        event.Skip()

    def ShowAutoCompleteList(self):
        """Show autocomplete list at the current caret position."""
        if _hasJedi and self.getFileType() == 'Python':
            self.coder.SetStatusText(
                'Retrieving code completions, please wait ...', 0)
            # todo - create Script() periodically
            compList = [i.name for i in jedi.Script(
                self.getTextUptoCaret(),
                path=self.filename if os.path.isabs(self.filename) else
                None).completions(fuzzy=False)]
            # todo - check if have a perfect match and veto AC
            self.coder.SetStatusText('', 0)
            if compList:
                self.AutoCompShow(0, " ".join(compList))

    def ShowCalltip(self):
        """Show a calltip at the current caret position."""
        if _hasJedi and self.getFileType() == 'Python':
            self.coder.SetStatusText('Retrieving calltip, please wait ...', 0)
            foundRefs = jedi.Script(self.getTextUptoCaret()).get_signatures()
            self.coder.SetStatusText('', 0)

            if foundRefs:
                # enable text wrapping
                calltipText = foundRefs[0].to_string()
                if calltipText:
                    calltipText = '\n    '.join(
                        textwrap.wrap(calltipText, 76))  # 80 cols after indent
                    y, x = foundRefs[0].bracket_start
                    self.CallTipShow(
                        self.XYToPosition(x + 1, y - 1), calltipText)

    def MacOpenFile(self, evt):
        logging.debug('PsychoPyCoder: got MacOpenFile event')

    def OnUpdateUI(self, evt):
        """Runs when the editor is changed in any way."""
        # check for matching braces
        braceAtCaret = -1
        braceOpposite = -1
        charBefore = None
        caretPos = self.GetCurrentPos()

        if caretPos > 0:
            charBefore = self.GetCharAt(caretPos - 1)
            styleBefore = self.GetStyleAt(caretPos - 1)

        # check before
        if charBefore and chr(charBefore) in "[]{}()":
            if styleBefore == wx.stc.STC_P_OPERATOR:
                braceAtCaret = caretPos - 1

        # check after
        if braceAtCaret < 0:
            charAfter = self.GetCharAt(caretPos)
            styleAfter = self.GetStyleAt(caretPos)
            if charAfter and chr(charAfter) in "[]{}()":
                if styleAfter == wx.stc.STC_P_OPERATOR:
                    braceAtCaret = caretPos

        if braceAtCaret >= 0:
            braceOpposite = self.BraceMatch(braceAtCaret)

        if braceAtCaret != -1 and braceOpposite == -1:
            self.BraceBadLight(braceAtCaret)
        else:
            self.BraceHighlight(braceAtCaret, braceOpposite)

        # Update data about caret position, this can be done once per UI update
        # to eliminate the need to recalculate these values when needed
        # elsewhere.
        self.updateCaretInfo()

        # set the current line and column in the status bar
        self.coder.SetStatusText('Line: {} Col: {}'.format(
            self.caretLine + 1, self.caretColumn + 1), 1)

    def updateCaretInfo(self):
        """Update information related to the current caret position in the text.

        This is done once per UI update which reduces redundant calculations of
        these values.

        """
        self.indentSize = self.GetIndent()
        self.caretCurrentPos = self.GetCurrentPos()
        self.caretVisible, self.caretColumn, self.caretLine = \
            self.PositionToXY(self.caretCurrentPos)
        self.caretLineIndentCol = \
            self.GetColumn(self.GetLineIndentPosition(self.caretLine))
        self.caretLineIndentLevel = self.caretLineIndentCol / self.indentSize
        self.caretAtIndentLevel = \
            (self.caretLineIndentCol % self.indentSize) == 0
        # self.shouldBackspaceUntab = \
        #     self.caretAtIndentLevel and \
        #     0 < self.caretColumn <= self.caretLineIndentCol

    def commentLines(self):
        # used for the comment/uncomment machinery from ActiveGrid
        newText = ""
        for lineNo in self._GetSelectedLineNumbers():
            lineText = self.GetLine(lineNo)
            oneSharp = bool(len(lineText) > 1 and lineText[0] == '#')
            # todo: is twoSharp ever True when oneSharp is not?
            twoSharp = bool(len(lineText) > 2 and lineText[:2] == '##')
            lastLine = bool(lineNo == self.GetLineCount() - 1
                            and self.GetLineLength(lineNo) == 0)
            if oneSharp or twoSharp or lastLine:
                newText = newText + lineText
            else:
                newText = newText + "#" + lineText

        self._ReplaceSelectedLines(newText)

    def uncommentLines(self):
        # used for the comment/uncomment machinery from ActiveGrid
        newText = ""
        for lineNo in self._GetSelectedLineNumbers():
            lineText = self.GetLine(lineNo)
            # todo: is the next line ever True? seems like should be == '##'
            if len(lineText) >= 2 and lineText[:2] == "#":
                lineText = lineText[2:]
            elif len(lineText) >= 1 and lineText[:1] == "#":
                lineText = lineText[1:]
            newText = newText + lineText
        self._ReplaceSelectedLines(newText)

    def increaseFontSize(self):
        self.SetZoom(self.GetZoom() + 1)

    def decreaseFontSize(self):
        # Minimum zoom set to - 6
        if self.GetZoom() == -6:
            self.SetZoom(self.GetZoom())
        else:
            self.SetZoom(self.GetZoom() - 1)

    def resetFontSize(self):
        """Reset the zoom level."""
        self.SetZoom(0)

    # the Source Assistant and introspection functinos were broekn and removed frmo PsychoPy 1.90.0
    def analyseScript(self):
        """Parse the abstract syntax tree for the current document.

        This function gets a list of functions, classes and methods in the
        source code.

        """
        # scan the AST for objects we care about
        if hasattr(self.coder, 'structureWindow'):
            self.coder.structureWindow.refresh()

    def setLexer(self, lexer=None):
        """Lexer is a simple string (e.g. 'python', 'html')
        that will be converted to use the right STC_LEXER_XXXX value
        """
        lexer = 'null' if lexer is None else lexer
        try:
            lex = getattr(wx.stc, "STC_LEX_%s" % (lexer.upper()))
        except AttributeError:
            logging.warn("Unknown lexer %r. Using plain text." % lexer)
            lex = wx.stc.STC_LEX_NULL
            lexer = 'null'
        # then actually set it
        self.SetLexer(lex)
        self.setFonts()

        if lexer == 'python':
            self.SetIndentationGuides(self.coder.appData['showIndentGuides'])
            self.SetProperty("fold", "1")  # allow folding
            self.SetProperty("tab.timmy.whinge.level", "1")
        elif lexer.lower() == 'html':
            self.SetProperty("fold", "1")  # allow folding
            # 4 means 'tabs are bad'; 1 means 'flag inconsistency'
            self.SetProperty("tab.timmy.whinge.level", "1")
        elif lexer == 'cpp':  # JS, C/C++, GLSL, mex, arduino
            self.SetIndentationGuides(self.coder.appData['showIndentGuides'])
            self.SetProperty("fold", "1")
            self.SetProperty("tab.timmy.whinge.level", "1")
        elif lexer == 'R':
            # self.SetKeyWords(0, " ".join(['function']))
            self.SetIndentationGuides(self.coder.appData['showIndentGuides'])
            self.SetProperty("fold", "1")
            self.SetProperty("tab.timmy.whinge.level", "1")
        else:
            self.SetIndentationGuides(0)
            self.SetProperty("tab.timmy.whinge.level", "0")

        # keep text from being squashed and hard to read
        self.SetStyleBits(self.GetStyleBitsNeeded())
        spacing = self.coder.prefs['lineSpacing'] / 2.
        self.SetExtraAscent(int(spacing))
        self.SetExtraDescent(int(spacing))
        self.Colourise(0, -1)

    def onModified(self, event):
        # update the UNSAVED flag and the save icons
        #notebook = self.GetParent()
        #mainFrame = notebook.GetParent()
        self.coder.setFileModified(True)

    def DoFindNext(self, findData, findDlg=None):
        # this comes straight from wx.py.editwindow  (which is a subclass of
        # STC control)
        backward = not (findData.GetFlags() & wx.FR_DOWN)
        matchcase = (findData.GetFlags() & wx.FR_MATCHCASE) != 0
        end = self.GetLength()
        textstring = self.GetTextRange(0, end)
        findstring = findData.GetFindString()
        if not matchcase:
            textstring = textstring.lower()
            findstring = findstring.lower()
        if backward:
            start = self.GetSelection()[0]
            loc = textstring.rfind(findstring, 0, start)
        else:
            start = self.GetSelection()[1]
            loc = textstring.find(findstring, start)

        # if it wasn't found then restart at begining
        if loc == -1 and start != 0:
            if backward:
                start = end
                loc = textstring.rfind(findstring, 0, start)
            else:
                start = 0
                loc = textstring.find(findstring, start)

        # was it still not found?
        if loc == -1:
            dlg = dialogs.MessageDialog(self, message=_translate(
                'Unable to find "%s"') % findstring, type='Info')
            dlg.ShowModal()
            dlg.Destroy()
        else:
            # show and select the found text
            line = self.LineFromPosition(loc)
            # self.EnsureVisible(line)
            self.GotoLine(line)
            self.SetSelection(loc, loc + len(findstring))
        if findDlg:
            if loc == -1:
                wx.CallAfter(findDlg.SetFocus)
                return
            else:
                findDlg.Close()
