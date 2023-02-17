# -*- coding: utf-8 -*-
"""Python environment management dialog box.

This dialog allows the user to make changes to the packages associated with the
current environment.

"""

import sys
import wx
from psychopy.app.plugin_manager.ui import BasePluginDialog
from psychopy.localization import _translate
import psychopy.tools.pkgtools as pkgtools
from PIL import Image as pil
from pypi_search import search as pypi

pkgtools.refreshPackages()  # build initial package cache


class EnvironmentManagerDlg(BasePluginDialog):
    """Class for the environment manager dialog.

    This creates a dialog which affords the user various means of modifying the
    packages in the current environment. For now, this only works on the
    interpreter which is currently executing the application's code.

    Parameters
    ----------
    parent : wx.Window or None
        Parent window associated with this dialog. If `None`, the window will
        not have a parent assigned to it.

    """
    def __init__(self, parent):
        BasePluginDialog.__init__(self, parent=parent)

        # internal variables to keep track of things
        self._foundPlugins = {}

        # default icons
        # self._defaultIcon =

        self._initPackageListCtrl()
        self.refreshPackageList()

    # --------------------------------------------------------------------------
    # Utilities
    #

    @staticmethod
    def _truncateText(text, maxLen=128):
        """Truncate long strings.

        Reduces the length of a string to prevent issues arising from bad input.

        Parameters
        ----------
        text : str
            String to truncate.
        maxLen : int
            Maximum length of a string, defaults at 255.

        """
        if len(text) > maxLen:
            return text[:maxLen]

        return text

    @staticmethod
    def _createIconBitmap(iconBitmap, resizeTo=(128, 128)):
        """Create an icon bitmap.

        This produces icons which can be used for various things in this dialog.

        Parameters
        ----------
        iconBitmap : wx.Bitmap, PIL.Image or None
            Bitmap to display as the plugin icon.
        resizeTo : wx.Size or tuple
            Size of the final bitmap.

        Returns
        -------
        wx.Bitmap
            Bitmap which can be used for icons.

        """
        # based on Todd's code for avatar bitmaps
        if iconBitmap is None:
            return wx.Bitmap()
        elif isinstance(iconBitmap, pil.Image):
            # resize to fit ctrl
            icon = iconBitmap.resize(size=resizeTo)

            # supply an alpha channel if there is one
            if "A" in icon.getbands():
                alpha = icon.tobytes("raw", "A")
            else:
                alpha = None

            iconBitmap = wx.Bitmap.FromBufferAndAlpha(
                width=icon.size[0],
                height=icon.size[1],
                data=icon.tobytes("raw", "RGB"),
                alpha=alpha)

        elif not isinstance(iconBitmap, wx.Bitmap):
            iconBitmap = wx.Bitmap(iconBitmap)  # do resize?
        else:
            raise TypeError('Wrong type for parameter `icon` specified.')

        return iconBitmap

    # --------------------------------------------------------------------------
    # User interface and events
    #

    def setPluginAuthorCardName(self, authorName):
        """Set the name of the author card on the plugin panel.

        Parameters
        ----------
        authorName : str
            Author name.

        """
        if not isinstance(authorName, str):
            raise TypeError("Parameter `authorName` must be type `str`.")

        self.lblPluginInfoAuthor.SetLabelText(authorName)

    def setPluginAuthorCardAvatar(self, icon):
        """Set the avatar icon for the plugin author.

        Parameters
        ----------
        icon : wx.Bitmap, PIL.Image or None
            Bitmap to display as the plugin icon.

        """
        icon = EnvironmentManagerDlg._createIconBitmap(icon)
        self.bmpPluginAuthorAvatar.SetBitmap(icon)

    def setPluginKeywordsList(self, keywordsList):
        """Set the list of keywords associated with the plugin.

        Parameters
        ----------
        keywordsList : list or tuple
            List of strings representing keywords associated with the plugin.

        """
        if not isinstance(keywordsList, (list, tuple,)):
            raise TypeError(
                "Parameter `keywordsList` must be type `tuple` or `list`.")

        labelText = " ".join(keywordsList)
        self.lblPluginInfoKeywords.SetLabelText(labelText)

    def setPluginTitle(self, titleText):
        """Set the title of the plugin info card.

        Parameters
        ----------
        titleText : str
            Name of the plugin.

        """
        if not isinstance(titleText, str):
            raise TypeError("Parameter `titleText` must be type `str`.")

        self.lblPluginInfoTitle.SetLabelText(titleText)

    def setPluginProjectName(self, projectNameText):
        """Set the project name of the plugin info card.

        Parameters
        ----------
        projectNameText : str
            Plugin project or package name.

        """
        if not isinstance(projectNameText, str):
            raise TypeError("Parameter `projectNameText` must be type `str`.")

        self.lblPluginInfoPackageName.SetLabelText(projectNameText)

    def setPluginSummary(self, summaryText):
        """Set plugin summary text.

        Parameters
        ----------
        summaryText : str
            Summary (description) of the plugin.

        """
        if not isinstance(summaryText, str):
            raise TypeError("Parameter `summaryText` must be type `str`.")

        self.txtPluginInfoDescription.SetLabelText(summaryText)

    def setPluginIcon(self, icon):
        """Set the graphic representing the plugin icon.

        Parameters
        ----------
        icon : wx.Bitmap, PIL.Image or None
            Bitmap to display as the plugin icon.

        """
        icon = EnvironmentManagerDlg._createIconBitmap(icon)
        self.bmpPluginInfoPicture.SetBitmap(icon)

    def setPluginInfo(self, pluginInfo):
        """Populate the plugin info page.

        Parameters
        ----------
        pluginInfo : dict
            Mapping of plugin information.

        """
        # pull values and supply defaults to missing ones
        pluginTitle = pluginInfo.get('pluginTitle', 'Unknown')
        projectName = pluginInfo.get('projectName', 'Unknown')
        summary = pluginInfo.get('description', '')
        keywords = pluginInfo.get('keywords', '')
        authorName = pluginInfo.get('authorName', 'Unknown')

        self.setPluginTitle(pluginTitle)
        self.setPluginProjectName(projectName)
        self.setPluginSummary(summary)
        self.setPluginKeywordsList(keywords)
        self.setPluginAuthorCardName(authorName)

    # Packages -----------------------------------------------------------------

    def _initPackageListCtrl(self):
        """Initialize the package list control. This clears it and creates the
        required columns.
        """
        self.tvwPackageList.AppendColumn(_translate("Name"), 150)
        self.tvwPackageList.AppendColumn(_translate("Version"), -1)

        self.installedRoot = self.tvwPackageList.AppendItem(
            self.tvwPackageList.RootItem, _translate("Installed") + " (0)")
        self.notInstalledRoot = self.tvwPackageList.AppendItem(
            self.tvwPackageList.RootItem, _translate("Not Installed") + " (0)")

    def _clearPackageList(self):
        """Clear all items in the package list.

        Needed to write our own routine because the extant `TreeListCtrl`
        methods like `DeleteAllItems()` and `ClearColumns()` are broken, causing
        the app to freeze intermittently on MacOS when the user interacts with
        the UI.

        """
        for treeRoot in [self.installedRoot, self.notInstalledRoot]:
            item = self.tvwPackageList.GetFirstChild(treeRoot)
            while item.IsOk():
                self.tvwPackageList.DeleteItem(item)
                item = self.tvwPackageList.GetNextSibling(item)

        self.tvwPackageList.SetItemText(
            self.installedRoot, 0, _translate("Installed") + " (0)")
        self.tvwPackageList.SetItemText(
            self.notInstalledRoot, 0, _translate("Not Installed") + " (0)")

    def refreshPackageList(self, subset='', includeRemotes=False):
        """Refresh and populate the package list.

        Parameters
        ----------
        subset : str
            Search/filter term. If empty, only the installed packages will be
            displayed.
        includeRemotes : bool
            Show results from a pip search.

        """
        self._clearPackageList()

        installedPackages = pkgtools.getInstalledPackages()

        if subset:  # subset packages for search
            pkgTemp = []
            for pkgInfo in installedPackages:
                pkgName, _ = pkgInfo
                if subset not in pkgName:
                    continue
                pkgTemp.append(pkgInfo)

            installedPackages = pkgTemp

        # Create the root "Installed" category, this also shows the number of
        # installed packages in parentheses.
        installedCount = len(installedPackages)
        installedRootText = "{} ({})".format(
            _translate("Installed"), str(installedCount))

        self.tvwPackageList.SetItemText(
            self.installedRoot, 0, installedRootText)

        # create items rto display installed packages
        for pkgInfo in installedPackages:
            pkgName, pkgVersion = pkgInfo
            newItem = self.tvwPackageList.AppendItem(
                self.installedRoot, pkgName)
            self.tvwPackageList.SetItemText(newItem, 1, pkgVersion)
            clientData = {
                'Name': pkgName,
                'Version': pkgVersion,
                'Local': True}
            # clientData = pkgtools.getPackageMetadata(pkgName)
            self.tvwPackageList.SetItemData(newItem, clientData)

        if not includeRemotes:  # done here
            self.tvwPackageList.Expand(self.installedRoot)  # expand the list
            return

        # do a search of remote packages
        foundPackages = pypi.find_packages(subset)

        # Create the root "Installed" category, this also shows the number of
        # installed packages in parentheses.
        notInstalledCount = len(foundPackages)
        notInstalledRootText = "{} ({})".format(
            _translate("Not Installed"), str(notInstalledCount))

        self.tvwPackageList.SetItemText(
            self.notInstalledRoot, 0, notInstalledRootText)

        # create items to display remote packages
        for pkgInfo in foundPackages:
            pkgName = EnvironmentManagerDlg._truncateText(pkgInfo['name'], 255)
            pkgVersion = pkgInfo['version']
            pkgSummary = EnvironmentManagerDlg._truncateText(
                pkgInfo['description'], 255)
            newItem = self.tvwPackageList.AppendItem(
                self.notInstalledRoot, pkgName)
            self.tvwPackageList.SetItemText(newItem, 1, pkgVersion)
            clientData = {
                'Name': pkgName,
                'Version': pkgVersion,
                'Summary': pkgSummary,
                'Local': False}
            self.tvwPackageList.SetItemData(newItem, clientData)

        self.tvwPackageList.Expand(self.installedRoot)  # expand the list
        self.tvwPackageList.Expand(self.notInstalledRoot)  # expand the list

    def setPackageProjectName(self, projectNameText):
        """Set the package info card project name.

        Parameters
        ----------
        projectNameText : str
            Package project or package name.

        """
        if not isinstance(projectNameText, str):
            raise TypeError("Parameter `projectNameText` must be type `str`.")

        self.lblPackageInfoName.SetLabelText(projectNameText)

    def setPackageLicense(self, licenceText):
        """Set the package info card licence field.

        Parameters
        ----------
        licenceText : str
            License text.

        """
        if not isinstance(licenceText, str):
            raise TypeError("Parameter `licenceText` must be type `str`.")

        licenceText = EnvironmentManagerDlg._truncateText(licenceText)
        self.lblPackageInfoLicense.SetLabelText(licenceText)

    def setPackageAuthorURL(self, authorName, authorMail=None):
        """Set the package info card author name hyperlink.

        Parameters
        ----------
        authorName : str
            Author name used as the hyperlink label.
        authorMail : str or None
            Web address contact the author. If not provided, the hyperlink will
            be disabled.

        """
        if not isinstance(authorName, str):
            raise TypeError("Parameter `authorName` must be type `str`.")

        # sanitize input to prevent label from being too large
        authorName = EnvironmentManagerDlg._truncateText(authorName)
        self.hypAuthorLink.SetLabelText(authorName)

        if authorMail is not None:
            self.hypAuthorLink.Enable()
            self.hypAuthorLink.SetURL(authorMail)
        else:
            self.hypAuthorLink.Disable()

    def setPackageSummary(self, summaryText):
        """Set the package summary text.

        Parameters
        ----------
        summaryText : str
            Summary text.

        """
        if not isinstance(summaryText, str):
            raise TypeError("Parameter `summaryText` must be type `str`.")

        self.txtPackageDescription.SetValue(summaryText)

    def setPackageInfo(self, packageInfo):
        """Set package info for display.

        Parameters
        ----------
        packageInfo : dict or None
            Package metadata as a mapping. Usually pass objects returned by
            calling :func:`pkgtools.getPackageMetadata()`. If `None`, the
            package information panel will be cleared.

        """
        if packageInfo is None:
            return  # do nothing for now

        # get values from metadata, have defaults if not present
        self.setPackageProjectName(packageInfo.get('Name', 'Unknown'))
        authorName = packageInfo.get('Author', 'Unknown')
        authorMail = packageInfo.get('Author-email', None)
        self.setPackageAuthorURL(authorName, authorMail)
        packageLicense = packageInfo.get('License', 'Not Specified')
        self.setPackageLicense(packageLicense)
        packageSummary = packageInfo.get('Summary', '')
        self.setPackageSummary(packageSummary)

    def onPackageListSelChanged(self, event):
        """Event generated when the user selects an item in the package list.
        """
        selectedItem = event.GetItem()
        clientData = self.tvwPackageList.GetItemData(selectedItem)
        if clientData is None:
            return

        # cache full metadata if local
        if clientData['Local']:
            clientData = pkgtools.getPackageMetadata(clientData["Name"])
            clientData.update({'Local': True})
            self.tvwPackageList.SetItemData(selectedItem, clientData)  # cache

        self.setPackageInfo(clientData)

        event.Skip()

    def onPackageSearchEnter(self, event):
        """Event generated when the user searches for a package.

        This updates the package list to  show only a subset of distributions
        which contain the character typed it.
        """
        self.refreshPackageList(subset=event.GetString(), includeRemotes=True)

    def onPackageSearchCancelClicked(self, event):
        """Event called when the cancel icon is clicked in the package search
        field.
        """
        self.refreshPackageList()

    def onPackageSearchButtonClicked(self, event):
        """Event called when the search icon is clicked in the package search
        field.
        """
        self.refreshPackageList(subset=event.GetString(), includeRemotes=True)

    # Console ------------------------------------------------------------------

    def clearConsoleText(self):
        """Clear the console.
        """
        self.txtConsole.Clear()

    def onConsoleClear(self, event):
        """Event when the console 'Clear' button is clicked.
        """
        self.clearConsoleText()

    def copyConsoleText(self):
        """Copy currently selected or all console text to clipboard.
        """
        # check if we have a selection
        selStart, selEnd = self.txtConsole.GetSelection()

        # has selection, use control copy method
        hasSelection = selStart < selEnd
        if self.txtConsole.CanCopy() and hasSelection:
            self.txtConsole.Copy()
            return

        # copy all the text if not specified
        copyText = wx.TextDataObject(self.txtConsole.GetValue())

        # pass to the clipboard directly since we don't have selection
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(copyText)
            wx.TheClipboard.Close()

    def onConsoleCopy(self, event):
        """Event when the console 'Copy' button is clicked.

        Copies the text selection if available, or the whole text if not.

        """
        self.copyConsoleText()

    def onClose(self, event=None):
        if event is None:
            return

        event.Skip()

    def onCloseClicked(self, event=None):
        """Close the window."""
        if event is None:
            return

        event.Skip()


if __name__ == "__main__":
    pass

