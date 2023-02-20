# -*- coding: utf-8 -*-
"""Python environment management dialog box.

This dialog allows the user to make changes to the packages associated with the
current environment.

"""
import os
import sys
import wx
import pkg_resources
from psychopy.app.plugin_manager.ui import BasePluginDialog, BasePluginInfoCard
from psychopy.localization import _translate
import psychopy.tools.pkgtools as pkgtools
from PIL import Image as pil
from pypi_search import search as pypi
import subprocess as sp
import psychopy.plugins as plugins
import psychopy.app.jobs as jobs
from psychopy.app.utils import ImageData
from psychopy.app.plugin_manager import utils

pkgtools.refreshPackages()  # build initial package cache


class PluginInfoCard(BasePluginInfoCard):
    """Class representing information 'cards' which are displayed in the plugin
    list panel.
    """
    def __init__(self, parent):
        BasePluginInfoCard.__init__(self, parent=parent)

        # plugin information associated with instances of this class
        self._info = {}

        # avatar graphics used in various places on the interface
        self._avatarGraphics = wx.Bitmap()
        self._avatarImage = None
        self._avatarImageLarge = None
        self._requestedAuthorImage = None
        self._authorImage = None

        # package state information
        self._installed = False

        # search and indexing
        self._searchValue = ''

    def setCardInfo(self, cardInfo):
        """Set the information the card is displaying.

        Parameters
        ----------
        cardInfo : dict
            Mapping of card information extracted from the `plugins.json` file.

        """
        self._info = cardInfo  # update info

        # set labels
        self.lblPluginTitle.SetLabelText(self.name)
        self.txtPluginExtraInfo.SetLabelText(self.summary)
        projectWebsite = self._info.get('homepage', None)

        # author information
        authorDesc = self._info.get('author', None)
        if authorDesc is not None:
            authorName = authorDesc.get('name', 'Not Specified')
            self._requestedAuthorImage = authorDesc.get('avatar', None)
        else:
            authorName = 'Not Specified'
            self._requestedAuthorImage = None

        # set author name and homepage
        self.hypLink.SetLabelText(authorName)
        if projectWebsite is not None:  # set website URL
            self.hypLink.SetURL(projectWebsite)

        # handle avatar graphics
        avatar = self._info.get('icon', None)
        if avatar is not None:
            self._avatarGraphics = ImageData(avatar)
            self._avatarImage = EnvironmentManagerDlg._createIconBitmap(
                self._avatarGraphics, (48, 48))
            self.bmpPluginIcon.SetBitmap(self._avatarImage)

        # generate searchable string
        searchables = [self.name, self.pipname] + self.keywords
        self._searchValue = " ".join([item.lower() for item in searchables])

        self.Refresh()

    def _setPluginInfo(self):
        """Set the window plugin information to match this selection.
        """
        win = self.GetTopLevelParent()
        win.setPluginInfoFromCard(self)  # pass self to window

    @property
    def searchValue(self):
        """String which contains all the values needed for search (`str`).

        Example
        -------
        Search for a keyword::

            match = 'hardware' in self.searchValue

        Search for by (partial) project name::

            match = 'psychopy-' in self.searchValue

        """
        return self._searchValue

    @property
    def authorImage(self):
        """Small avatar image used for the author details on the main plugin
        information panel.

        Returns
        -------
        wx.Bitmap
            Author graphics downloaded from the internet sized to 48x48.

        """
        if self._authorImage is None:
            if self._requestedAuthorImage is not None:
                self._authorImage = EnvironmentManagerDlg._createIconBitmap(
                    ImageData(self._requestedAuthorImage), (64, 64))
            else:
                self._authorImage = wx.Bitmap()

        return self._authorImage

    @property
    def avatarImage(self):
        """Small avatar image used by the widget.

        Returns
        -------
        wx.Bitmap
            Avatar graphics downloaded from the internet sized to 48x48.

        """
        return self._avatarImage  # loaded during set info

    @property
    def avatarImageLarge(self):
        """Large avatar image used in the plugin information field.

        Returns
        -------
        wx.Bitmap
            Avatar graphics downloaded from the internet sized to 128x128.

        """
        if self._avatarImageLarge is None:  # memoize graphics
            if self._avatarGraphics is not None:
                self._avatarImageLarge = \
                        EnvironmentManagerDlg._createIconBitmap(
                            self._avatarGraphics, (128, 128))
            else:
                self._avatarImageLarge = wx.Bitmap()  # empty or default

        return self._avatarImageLarge

    def getInfo(self):
        """Get information contained by this object.

        Returns
        -------
        dict or None
            Mapping of plugin information extracted from the `plugin.json` file
            associated with the plugin represented by this object. If `None`,
            no data has been set yet.

        """
        return self._info

    @property
    def isInstalled(self):
        """Is this package marked as installed (`bool`)?
        """
        return self._installed

    @property
    def name(self):
        """Name of the plugin (`str`). Returns 'Unspecified' if the name field
        is missing.
        """
        return self._info.get('name', 'Unspecified')

    @property
    def pipname(self):
        """Project (or PyPI) package name for the plugin (`str`) or empty string
        if the field missing.
        """
        return self._info.get('pipname', '')

    @property
    def authorName(self):
        """The primary author name (`str`). Returns 'Unspecified' if the author
        name is missing.
        """
        return self._info['author'].get('name', 'Unspecified')

    @property
    def authorEmail(self):
        """Contact email of the primary author (`str`). Returns empty
        string if the author name is missing.
        """
        return self._info['author'].get('email', '')

    @property
    def projectWebsite(self):
        """Personal or organizational homepage of the project maintainer
        (`str`). This value can point to a lab, business, etc. website that the
        author is affiliated with. Returns empty string if the author name is
        missing.
        """
        return self._info.get('projectWebsite', '')

    @property
    def homepage(self):
        """Project homepage for the plugin (`str`) or `None` if the field is
        missing.
        """
        return self._info.get('homepage', None)

    @property
    def codeRepo(self):
        """Online code repository for the plugin (`str`), if available. `None`
        if the field is missing.
        """
        return self._info.get('repo', None)

    @property
    def summary(self):
        """Project summary text for the plugin (`str`) or empty string if the
        field missing.
        """
        return self._info.get('description', '')

    @property
    def keywords(self):
        """List (`list`) of keywords (`str`) associated with this project. Empty
        list is returned if there are no keywords.
        """
        return self._info.get('keywords', [])

    def setInstallationState(self, installed):
        """Set whether the package is installed or not.

        Parameters
        ----------
        installed : bool
            Show as installed if `True`. If not installed or remote, set as
            `False` instead.

        """
        self._installed = bool(installed)
        self.cmdChangeInstall.SetLabelText(
            'Remove' if self._installed else 'Install')
        self.cmdChangeInstall.Refresh()
        self.Refresh()

    def showSelected(self):
        """Change the background color to indicate that this control has been
        selected in the plugin list.
        """
        self.SetBackgroundColour(
            wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT))
        self.Refresh()

    def showDeselected(self):
        """Change the background color to indicate that this control has been
        deselected in the plugin list.
        """
        self.SetBackgroundColour(wx.Colour(255, 255, 255))
        self.Refresh()

    def onChangeInstall(self, event):
        """Event called when the 'Install' or 'Remove' button on the item is
        clicked. This will initiate an installation or uninstallation.
        """
        win = self.GetTopLevelParent()
        if not self._installed:
            wx.CallAfter(win.installPackage, self.pipname)
        else:
            wx.CallAfter(win.uninstallPackage, self.pipname)

    def onPluginExtraInfoLeftUp(self, event):
        self._setPluginInfo()

    def onPluginIconLeftUp(self, event):
        self._setPluginInfo()

    def onPluginTitleLeftUp(self, event):
        self._setPluginInfo()

    def onLeftUp(self, event):
        self._setPluginInfo()


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
    # page indices for the dialog
    PLUGINS_PAGE_IDX = 0
    PACKAGES_PAGE_IDX = 1
    CONSOLE_PAGE_IDX = 2

    def __init__(self, parent):
        BasePluginDialog.__init__(self, parent=parent)

        # internal variables to keep track of things
        self._foundPlugins = {}

        # default icons
        # self._defaultIcon =
        self._initPackageListCtrl()
        self.refreshPackageList()

        # info cards for the plugins list, these are displayed on the panel
        self.pluginInfoCards = []
        self.populatePluginList()

        self.currentPlugin = None

        self.pipProcess = None

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

    @staticmethod
    def getPackageVersionInfo(packageName):
        """Query packages for available versions.

        This function invokes the `pip index versions` ins a subprocess and
        parses the results.

        Parameters
        ----------
        packageName : str
            Name of the package to get available versions of.

        Returns
        -------
        dict
            Mapping of versions information. Keys are `'All'` (`list`),
            `'Current'` (`str`), and `'Latest'` (`str`).

        """
        cmd = [sys.executable, "-m", "pip", "index", "versions", packageName,
               '--no-input', '--no-color']
        # run command in subprocess
        output = sp.Popen(
            cmd,
            stdout=sp.PIPE,
            stderr=sp.PIPE,
            shell=False,
            universal_newlines=True)
        stdout, stderr = output.communicate()  # blocks until process exits
        nullVersion = {'All': [], 'Installed': '', 'Latest': ''}

        # if stderr:  # error pipe has something, give nothing
        #     return nullVersion

        # parse versions
        if stdout:
            allVersions = installedVersion = latestVersion = None
            for line in stdout.splitlines(keepends=False):
                line = line.strip()  # remove whitespace
                if line.startswith("Available versions:"):
                    allVersions = (line.split(': ')[1]).split(', ')
                elif line.startswith("LATEST:"):
                    latestVersion = line.split(': ')[1].strip()
                elif line.startswith("INSTALLED:"):
                    installedVersion = line.split(': ')[1].strip()

            if installedVersion is None:  # not present, use first entry
                installedVersion = allVersions[0]
            if latestVersion is None:  # ditto
                latestVersion = allVersions[0]

            toReturn = {
                'All': allVersions,
                'Installed': installedVersion,
                'Latest': latestVersion}

            return toReturn

        return nullVersion

    def _writeOutput(self, text, flush=True):
        """Write out bytes coming from the current subprocess.

        Parameters
        ----------
        text : str or bytes
            Text to write.
        flush : bool
            Flush text so it shows up immediately on the pipe.

        """
        if isinstance(text, bytes):
            text = text.decode('utf-8')

        self.txtConsole.AppendText(text)

    def _onInputCallback(self, streamBytes):
        """Callback to process data from the input stream of the subprocess.
        This is called when `~psychopy.app.jobs.Jobs.poll` is called and only if
        there is data in the associated pipe.

        Parameters
        ----------
        streamBytes : bytes or str
            Data from the 'stdin' streams connected to the subprocess.

        """
        self._writeOutput(streamBytes)

    def _onErrorCallback(self, streamBytes):
        """Callback to process data from the error stream of the subprocess.
        This is called when `~psychopy.app.jobs.Jobs.poll` is called and only if
        there is data in the associated pipe.

        Parameters
        ----------
        streamBytes : bytes or str
            Data from the 'sdterr' streams connected to the subprocess.

        """
        self._onInputCallback(streamBytes)

    def _onTerminateCallback(self, pid, exitCode):
        """Callback invoked when the subprocess exits.

        Parameters
        ----------
        pid : int
            Process ID number for the terminated subprocess.
        exitCode : int
            Program exit code.

        """
        # write a close message, shows the exit code
        closeMsg = " Package installation complete "
        closeMsg = closeMsg.center(80, '#') + '\n'
        self._writeOutput(closeMsg)

        self.pipProcess = None  # clear Job object

        pkgtools.refreshPackages()

        # refresh package list
        self.refreshPackageList(
            subset=self.txtSearchPackages.GetValue(), includeRemotes=True)

        # make sure plugin list installation states match
        pluginListItems = self.getAllPluginListItems()
        for pluginItem in pluginListItems:
            pkgName = pkg_resources.safe_name(pluginItem.pipname)
            pluginItem.setInstallationState(pkgtools.isInstalled(pkgName))

        if self.currentPlugin is not None:
            self.cmdInstallPlugin.SetLabelText(
                'Remove' if self.currentPlugin.isInstalled else 'Add')

    @property
    def isBusy(self):
        """`True` if there is currently a `pip` subprocess running.
        """
        return self.pipProcess is not None

    def uninstallPackage(self, packageName):
        """Uninstall a package.

        This deletes any bundles in the user's package directory, or uninstalls
        packages from `site-packages`.

        Parameters
        ----------
        packageName : str
            Name of the package to install. Should be the project name but other
            formats may work.

        """
        if self.isBusy:
            msg = wx.MessageDialog(
                self,
                ("Cannot remove package. Wait for the installation already in "
                 "progress to complete first."),
                "Uninstallation Failed", wx.OK | wx.ICON_WARNING
            )
            msg.ShowModal()
            return

        self.nbMain.SetSelection(self.CONSOLE_PAGE_IDX)  # go to console page

        if pkgtools._isUserPackage(packageName):
            msg = 'Uninstalling package bundle for `{}` ...\n'.format(
                packageName)
            self._writeOutput(msg)

            success = pkgtools._uninstallUserPackage(packageName)
            if success:
                msg = 'Successfully removed package `{}`.\n'.format(
                    packageName)
            else:
                msg = ('Failed to remove package `{}`, check log for '
                       'details.\n').format(packageName)

            self._writeOutput(msg)

            self.refreshPackageList(
                subset=self.txtSearchPackages.GetValue(), includeRemotes=True)

            # make sure plugin list installation states match
            pluginListItems = self.getAllPluginListItems()
            for pluginItem in pluginListItems:
                pkgName = pkg_resources.safe_name(pluginItem.pipname)
                pluginItem.setInstallationState(pkgtools.isInstalled(pkgName))

            if self.currentPlugin is not None:
                self.cmdInstallPlugin.SetLabelText(
                    'Remove' if self.currentPlugin.isInstalled else 'Install')

            return

        # interpreter path
        pyExec = sys.executable

        # build the shell command to run the script
        command = [pyExec, '-m', 'pip', 'uninstall', packageName, '--yes']

        # create a new job with the user script
        self.pipProcess = jobs.Job(
            self,
            command=command,
            # flags=execFlags,
            inputCallback=self._onInputCallback,  # both treated the same
            errorCallback=self._onErrorCallback,
            terminateCallback=self._onTerminateCallback
        )
        self.pipProcess.start()

    def installPackage(self, packageName, version=None):
        """Install a package.

        Calling this will invoke a `pip` command which will install the
        specified package. Packages are installed to bundles and added to the
        system path when done.

        During an installation, the UI will make the console tab visible. It
        will display any messages coming from the subprocess. No way to cancel
        and installation midway at this point.

        Parameters
        ----------
        packageName : str
            Name of the package to install. Should be the project name but other
            formats may work.
        version : str or None
            Version of the package to install. If `None`, the latest version
            will be installed.

        """
        if self.isBusy:
            msg = wx.MessageDialog(
                self,
                ("Cannot install package. Wait for the installation already in "
                 "progress to complete first."),
                "Installation Failed", wx.OK | wx.ICON_WARNING
            )
            msg.ShowModal()
            return

        self.nbMain.SetSelection(self.CONSOLE_PAGE_IDX)  # go to console page

        # interpreter path
        pyExec = sys.executable

        # determine installation path for bundle, create it if needed
        bundlePath = plugins.getBundleInstallTarget(packageName)
        if not os.path.exists(bundlePath):
            self._writeOutput(
                "Creating bundle path `{}` for package `{}`.\n".format(
                    bundlePath, packageName))
            os.mkdir(bundlePath)  # make the directory
        else:
            self._writeOutput(
                "Using existing bundle path `{}` for package `{}`.\n".format(
                    bundlePath, packageName))

        # add the bundle to path, refresh makes it discoverable after install
        if bundlePath not in sys.path:
            sys.path.insert(0, bundlePath)

        # build the shell command to run the script
        command = [pyExec, '-m', 'pip', 'install', packageName, '--target',
                   bundlePath]

        # create a new job with the user script
        self.pipProcess = jobs.Job(
            self,
            command=command,
            # flags=execFlags,
            inputCallback=self._onInputCallback,  # both treated the same
            errorCallback=self._onErrorCallback,
            terminateCallback=self._onTerminateCallback
        )
        self.pipProcess.start()

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

        self.txtPluginInfoDescription.SetValue(summaryText)

    def setPluginIcon(self, icon):
        """Set the graphic representing the plugin icon.

        Parameters
        ----------
        icon : wx.Bitmap, PIL.Image or None
            Bitmap to display as the plugin icon.

        """
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
        keywords = pluginInfo.get('keywords', [])
        authorName = pluginInfo.get('authorName', 'Unknown')

        self.setPluginTitle(pluginTitle)
        self.setPluginProjectName(projectName)
        self.setPluginSummary(summary)
        self.setPluginKeywordsList(keywords)
        self.setPluginAuthorCardName(authorName)

    def setPluginInfoFromCard(self, infoCard):
        """Set plugin info from an info card object. This sets the current
        selection for the dialog.

        Parameters
        ----------
        infoCard : PluginInfoCard or None
            Plugin info card which has been selected, either by the user
            clicking on it or done programmatically. If `None`, no selection
            will be made and the plugin info panel should display a placeholder.

        """
        # do deselection of old selection
        if self.currentPlugin is not None:
            self.currentPlugin.showDeselected()

        cardCtrl = self.currentPlugin = infoCard

        # handle empty or wrong object
        if infoCard is None or not isinstance(infoCard, PluginInfoCard):
            return

        self.setPluginTitle(cardCtrl.name)
        self.setPluginProjectName(cardCtrl.pipname)
        self.setPluginSummary(cardCtrl.summary)
        self.setPluginKeywordsList(cardCtrl.keywords)
        self.setPluginAuthorCardName(cardCtrl.authorName)

        # set project image, if available
        if self.currentPlugin.avatarImageLarge is not None:
            self.setPluginIcon(self.currentPlugin.avatarImageLarge)

        # set author image, if available
        if self.currentPlugin.authorImage is not None:
            self.setPluginAuthorCardAvatar(self.currentPlugin.authorImage)

        # enable/disable buttons
        self.cmdInstallPlugin.SetLabelText(
            'Remove' if cardCtrl.isInstalled else 'Install')

        self.currentPlugin.showSelected()

    def getAllPluginListItems(self):
        """Get a list of all plugin list items in the order they appear.

        Returns
        -------
        `list` of `wx.Panel` or `PluginInfoCard`
            List of widgets currently present in the plugin panel.

        """
        sizer = self.pnlAvailablePlugins.GetSizer()
        sizerItems = sizer.GetChildren()
        toReturn = [item.GetWindow() for item in sizerItems]

        return toReturn

    def populatePluginList(self, subset=''):
        """Populate the plugin list panel.

        This generates info cards and presents them on the panel. The order
        which items appear is the same as they appear in the `plugins.json`
        file.

        Parameters
        ----------
        subset : str
            Subset plugin list based on string. This will reduce the number of
            options available to those where `PluginInfoCard.searchValue`
            contains a match. However, items are only hidden.

        """
        pluginListSizer = self.pnlAvailablePlugins.GetSizer()

        # get curated plugins list for `plugins.json`
        pluginInfo = utils.getAllPluginDetails()

        # generate widgets
        if not self.pluginInfoCards:
            for info in pluginInfo:
                newInfoCard = PluginInfoCard(self.pnlAvailablePlugins)
                newInfoCard.setCardInfo(info)

                newInfoCard.setInstallationState(
                    pkgtools.isInstalled(info['pipname']))

                self.pluginInfoCards.append(newInfoCard)

        for infoCard in self.pluginInfoCards:
            pluginListSizer.Add(infoCard, 0, wx.EXPAND, 1)

        pluginListSizer.Layout()

        self.pnlAvailablePlugins.Refresh()

    def onPluginListSize(self, event):
        """Handle when the plugin list is resized.
        """
        pass

    def onPluginHomepageClicked(self, event):
        pass

    def onPluginEmailClicked(self, event):
        pass

    def onPluginInstallClicked(self, event):
        """Event called when the plugin installation button in the info panel is
        clicked.
        """
        if self.currentPlugin is not None:
            packageName = self.currentPlugin.pipname
            if pkgtools.isInstalled(packageName):
                self.uninstallPackage(packageName)
            else:
                self.installPackage(packageName)

    # Packages -----------------------------------------------------------------

    def _initPackageListCtrl(self):
        """Initialize the package list control. This clears it and creates the
        required columns.
        """
        self.tvwPackageList.AppendColumn(_translate("Name"), 220)
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

    def setPackageVersions(self, currentVersion, allVersions=None):
        """Populates the combobox which shows available package versions.

        Parameters
        ----------
        currentVersion : str
            Current or installed version.
        allVersions : list or None
            All available versions. List must contain `currentVersion`.

        """
        if allVersions is None:  # single, no cache
            self.cboPackageVersion.SetItems([currentVersion])
            self.cboPackageVersion.SetSelection(0)
            return

        # try:
        #     currentVersionIndex = allVersions.index(currentVersion)
        # except ValueError:
        #     raise ValueError(
        #         'Value of `allVersions` must contain `currentVersion`.')

        self.cboPackageVersion.SetItems(allVersions)
        showVersion = self.cboPackageVersion.FindString(currentVersion)
        self.cboPackageVersion.SetSelection(showVersion)

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
        packageName = packageInfo.get('Name', 'Unknown')
        self.setPackageProjectName(packageName)
        authorName = packageInfo.get('Author', 'Unknown')
        authorMail = packageInfo.get('Author-email', None)
        self.setPackageAuthorURL(authorName, authorMail)
        packageLicense = packageInfo.get('License', 'Not Specified')
        self.setPackageLicense(packageLicense)
        packageSummary = packageInfo.get('Summary', '')
        self.setPackageSummary(packageSummary)
        packageVersion = packageInfo.get('Version', 'N/A')
        self.setPackageVersions(packageVersion, None)

        isLocal = packageInfo.get('Local', False)  # check if local/installed

        # set button status based on installation status
        self.cmdInstallPackage.Enable(not isLocal)
        self.cmdUninstallPackage.Enable(isLocal)

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

    def onVersionChoiceDropdown(self, event):
        """Event called when the version dropdown is created.
        """
        selectedPackage = self.tvwPackageList.GetSelection()
        if not selectedPackage.IsOk():  # no selection
            return

        clientData = self.tvwPackageList.GetItemData(selectedPackage)
        if clientData is None:  # items has not data
            return

        packageName = clientData['Name']

        # cache version info
        if 'Version-info' not in clientData.keys():
            versionData = EnvironmentManagerDlg.getPackageVersionInfo(
                packageName)
            clientData.update({'Version-info': versionData})
            self.tvwPackageList.SetItemData(selectedPackage, clientData)

        packageVersionInfo = clientData['Version-info']
        self.setPackageVersions(
            packageVersionInfo['Installed'], packageVersionInfo['All'])

    def onPackageInstallClicked(self, event):
        """Event called when the package installation button is clicked.
        """
        selectedPackage = self.tvwPackageList.GetSelection()
        if not selectedPackage.IsOk():  # no selection
            return

        clientData = self.tvwPackageList.GetItemData(selectedPackage)
        if clientData is None:  # items has not data
            return

        packageName = clientData['Name']
        # todo - handle version
        wx.CallAfter(self.installPackage, packageName)

    def onPackageUninstallClicked(self, event):
        """Event called when the package uninstallation button is clicked.
        """
        selectedPackage = self.tvwPackageList.GetSelection()
        if not selectedPackage.IsOk():  # no selection
            return

        clientData = self.tvwPackageList.GetItemData(selectedPackage)
        if clientData is None:  # items has not data
            return

        packageName = clientData['Name']

        wx.CallAfter(self.uninstallPackage, packageName)

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

