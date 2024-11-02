import wx
from psychopy import experiment
from psychopy.app import utils
from psychopy.app.themes import icons
from psychopy.localization import _translate


class BuilderFindDlg(wx.Dialog):
    def __init__(self, frame, exp):
        self.frame = frame
        self.exp = exp

        self.results = []

        wx.Dialog.__init__(
            self,
            parent=frame,
            title=_translate("Find in experiment..."),
            size=(512, 512),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        # setup sizer
        self.border = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.border)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.border.Add(self.sizer, border=12, proportion=1, flag=wx.EXPAND | wx.ALL)

        # create search box and checkbox sizer
        searchSizer = wx.BoxSizer(wx.VERTICAL)

        # create search box
        self.termCtrl = wx.SearchCtrl(self)
        self.termCtrl.Bind(wx.EVT_TEXT, self.onSearchTyping)
        searchSizer.Add(self.termCtrl, flag=wx.EXPAND | wx.BOTTOM, border=6)

        # Add checkbox for case sensitivity
        self.caseSensitiveCheckbox = wx.CheckBox(self, label=_translate("Case sensitive"))
        self.caseSensitiveCheckbox.Bind(wx.EVT_CHECKBOX, self.onSearchTyping)
        searchSizer.Add(self.caseSensitiveCheckbox, flag=wx.BOTTOM, border=6)

        # Add the search sizer to the main sizer
        self.sizer.Add(searchSizer, flag=wx.EXPAND | wx.ALL, border=6)

        # create results box
        self.resultsCtrl = utils.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.resetListCtrl()
        self.resultsCtrl.Bind(wx.EVT_LIST_ITEM_SELECTED, self.onSelectResult)
        self.resultsCtrl.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.onSelectResult)
        self.resultsCtrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.onViewResult)
        self.sizer.Add(self.resultsCtrl, border=6, proportion=1, flag=wx.EXPAND | wx.ALL)

        # setup component icons
        self.imageList = wx.ImageList(16, 16)
        self.imageMap = {}
        for cls in experiment.getAllElements().values():
            i = self.imageList.Add(
                icons.ComponentIcon(cls, theme="light", size=16).bitmap
            )
            self.imageMap[cls] = i
        self.resultsCtrl.SetImageList(self.imageList, wx.IMAGE_LIST_SMALL)

        # add buttons
        btnSzr = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        self.border.Add(btnSzr, border=12, flag=wx.EXPAND | wx.ALL)
        # relabel OK to Go
        for child in btnSzr.GetChildren():
            if child.Window and child.Window.GetId() == wx.ID_OK:
                self.okBtn = child.Window
        self.okBtn.SetLabel(_translate("Go"))
        self.okBtn.Disable()
        # rebind OK to view method
        self.okBtn.Bind(wx.EVT_BUTTON, self.onViewResult)

        self.Layout()
        self.termCtrl.SetFocus()

    def resetListCtrl(self):
        self.resultsCtrl.ClearAll()
        self.resultsCtrl.AppendColumn(_translate("Component"), width=120)
        self.resultsCtrl.AppendColumn(_translate("Routine"), width=120)  # Moved to second position
        self.resultsCtrl.AppendColumn(_translate("Parameter"), width=120)
        self.resultsCtrl.AppendColumn(_translate("Value"), width=-1)
        self.resultsCtrl.resizeLastColumn(minWidth=120)
        self.selectedResult = None

    def onSearchTyping(self, evt):
        term = self.termCtrl.GetValue()
        case_sensitive = self.caseSensitiveCheckbox.GetValue()
        
        if term:
            # get locations of term in experiment
            self.results = getParamLocations(self.exp, term=term, case_sensitive=case_sensitive)
        else:
            # return nothing for blank string
            self.results = []

        # clear old output
        self.resetListCtrl()

        # show new output
        for result in self.results:
            # unpack result
            rt, comp, paramName, param = result
            # sanitize val for display
            val = str(param.val)
            if "\n" in val:
                # if multiline, show first line with match
                for line in val.split("\n"):
                    if (term in line) if case_sensitive else (term.lower() in line.lower()):
                        val = line
                        break
            # construct entry
            entry = [comp.name, rt.name, param.label, val]
            # add entry
            self.resultsCtrl.Append(entry)
            # set image for comp
            self.resultsCtrl.SetItemImage(
                item=self.resultsCtrl.GetItemCount()-1,
                image=self.imageMap[type(comp)]
            )
        
        # size
        self.resultsCtrl.Layout()
        # disable Go button until item selected
        self.okBtn.Disable()

        evt.Skip()

    def onSelectResult(self, evt):
        if evt.GetEventType() == wx.EVT_LIST_ITEM_SELECTED.typeId:
            # if item is selected, store its info
            self.selectedResult = self.results[evt.GetIndex()]
            # enable Go button
            self.okBtn.Enable()
        else:
            # if no item selected, clear its info
            self.selectedResult = None
            # disable Go button
            self.okBtn.Disable()

        evt.Skip()

    def onViewResult(self, evt):
        # there should be a selected result if this button was enabled, but just in case...
        if self.selectedResult is None:
            return
        # do usual OK button stuff
        # self.Close()
        # unpack
        rt, comp, paramName, param = self.selectedResult
        # navigate to routine
        self.frame.routinePanel.setCurrentRoutine(rt)
        # navigate to component & category
        page = self.frame.routinePanel.getCurrentPage()
        if isinstance(comp, experiment.components.BaseComponent):
            # if we have a component, open its dialog and navigate to categ page
            if hasattr(comp, 'type') and comp.type.lower() == 'code':
                # For code components, we need to find the index of the page
                openToPage = list(comp.params.keys()).index(paramName)
            else:
                openToPage = param.categ
            page.editComponentProperties(component=comp, openToPage=openToPage)
        else:
            # if we're in a standalone routine, just navigate to categ page
            i = page.ctrls.getCategoryIndex(param.categ)
            page.ctrls.ChangeSelection(i)

def getParamLocations(exp, term, case_sensitive=False):
    """
    Get locations of params containing the given term.

    Parameters
    ----------
    term : str
        Term to search for

    Returns
    -------
    list
        List of tuples, with each tuple functioning as a path to the found
        param
    """

    # array to store results in
    found = []

    def compareStrings(text, term, case_sensitive):
        if case_sensitive:
            return term in text
        else:
            return term.lower() in text.lower()

    # go through all routines
    for rt in exp.routines.values():
        if isinstance(rt, experiment.routines.BaseStandaloneRoutine):
            # find in standalone routine
            for paramName, param in rt.params.items():
                if compareStrings(str(param.val), term, case_sensitive):
                    # append path (routine -> param)
                    found.append(
                        (rt, rt, paramName, param)
                    )
        if isinstance(rt, experiment.routines.Routine):
            # find in regular routine
            for comp in rt:
                for paramName, param in comp.params.items():
                    if compareStrings(str(param.val), term, case_sensitive):
                        # append path (routine -> component -> param)
                        found.append(
                            (rt, comp, paramName, param)
                        )

    return found



