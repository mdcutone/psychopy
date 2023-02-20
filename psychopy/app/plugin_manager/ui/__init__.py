# -*- coding: utf-8 -*-

###########################################################################
## Python code generated with wxFormBuilder (version 3.10.1-0-g8feb16b)
## http://www.wxformbuilder.org/
##
## PLEASE DO *NOT* EDIT THIS FILE!
###########################################################################

import wx
import wx.xrc
import wx.dataview
import wx.adv


###########################################################################
## Class BasePluginDialog
###########################################################################

class BasePluginDialog(wx.Frame):

    def __init__(self, parent):
        wx.Frame.__init__(self, parent, id=wx.ID_ANY, title=u"Plugins & Packages", pos=wx.DefaultPosition,
                          size=wx.Size(1024, 600), style=wx.DEFAULT_FRAME_STYLE | wx.TAB_TRAVERSAL)

        self.SetSizeHints(wx.Size(800, 600), wx.DefaultSize)
        self.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_SCROLLBAR))

        szrMain = wx.BoxSizer(wx.VERTICAL)

        self.nbMain = wx.Notebook(self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, 0)
        self.pnlPlugins = wx.Panel(self.nbMain, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL)
        self.pnlPlugins.SetBackgroundColour(wx.Colour(255, 255, 255))

        szrPlugins = wx.BoxSizer(wx.VERTICAL)

        self.splPlugins = wx.SplitterWindow(self.pnlPlugins, wx.ID_ANY, wx.DefaultPosition, wx.Size(150, -1),
                                            wx.SP_NOBORDER)
        # self.splPlugins.SetSashSize( 12 )
        self.splPlugins.Bind(wx.EVT_IDLE, self.splPluginsOnIdle)
        self.splPlugins.SetMinimumPaneSize(100)

        self.splPlugins.SetMinSize(wx.Size(150, -1))

        self.pnlPluginList = wx.Panel(self.splPlugins, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL)
        self.pnlPluginList.SetBackgroundColour(wx.Colour(255, 255, 255))

        szrPluginList = wx.BoxSizer(wx.VERTICAL)

        self.txtSearchPlugins = wx.SearchCtrl(self.pnlPluginList, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition,
                                              wx.DefaultSize, wx.TE_PROCESS_ENTER)
        self.txtSearchPlugins.ShowSearchButton(True)
        self.txtSearchPlugins.ShowCancelButton(True)
        szrPluginList.Add(self.txtSearchPlugins, 0, wx.ALL | wx.EXPAND, 10)

        self.pnlAvailablePlugins = wx.ScrolledWindow(self.pnlPluginList, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize,
                                                     wx.VSCROLL)
        self.pnlAvailablePlugins.SetScrollRate(5, 5)
        szrAvailablePluginList = wx.BoxSizer(wx.VERTICAL)

        self.pnlAvailablePlugins.SetSizer(szrAvailablePluginList)
        self.pnlAvailablePlugins.Layout()
        szrAvailablePluginList.Fit(self.pnlAvailablePlugins)
        szrPluginList.Add(self.pnlAvailablePlugins, 1, wx.EXPAND | wx.ALL, 10)

        self.pnlPluginList.SetSizer(szrPluginList)
        self.pnlPluginList.Layout()
        szrPluginList.Fit(self.pnlPluginList)
        self.pnlPluginInfo = wx.Panel(self.splPlugins, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL)
        self.pnlPluginInfo.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT))
        self.pnlPluginInfo.SetBackgroundColour(wx.Colour(255, 255, 255))

        szrPluginInfo = wx.BoxSizer(wx.VERTICAL)

        gbPluginInfoCard = wx.GridBagSizer(5, 5)
        gbPluginInfoCard.SetFlexibleDirection(wx.BOTH)
        gbPluginInfoCard.SetNonFlexibleGrowMode(wx.FLEX_GROWMODE_SPECIFIED)

        self.bmpPluginInfoPicture = wx.StaticBitmap(self.pnlPluginInfo, wx.ID_ANY, wx.NullBitmap, wx.DefaultPosition,
                                                    wx.DefaultSize, 0)
        self.bmpPluginInfoPicture.SetMinSize(wx.Size(128, 128))

        gbPluginInfoCard.Add(self.bmpPluginInfoPicture, wx.GBPosition(0, 0), wx.GBSpan(4, 1), wx.ALL, 5)

        self.lblPluginInfoTitle = wx.StaticText(self.pnlPluginInfo, wx.ID_ANY, u"Plugin Title", wx.DefaultPosition,
                                                wx.DefaultSize, 0)
        self.lblPluginInfoTitle.Wrap(-1)

        self.lblPluginInfoTitle.SetFont(
            wx.Font(18, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, False, "Lucida Grande"))

        gbPluginInfoCard.Add(self.lblPluginInfoTitle, wx.GBPosition(0, 1), wx.GBSpan(1, 2), wx.EXPAND, 5)

        self.lblPluginInfoPackageName = wx.StaticText(self.pnlPluginInfo, wx.ID_ANY, u"psychopy-plugin",
                                                      wx.DefaultPosition, wx.DefaultSize, 0)
        self.lblPluginInfoPackageName.Wrap(-1)

        gbPluginInfoCard.Add(self.lblPluginInfoPackageName, wx.GBPosition(1, 1), wx.GBSpan(1, 2), wx.EXPAND, 5)

        self.cmdInstallPlugin = wx.Button(self.pnlPluginInfo, wx.ID_ANY, u"Install", wx.DefaultPosition, wx.DefaultSize, 0)
        gbPluginInfoCard.Add(self.cmdInstallPlugin, wx.GBPosition(3, 1), wx.GBSpan(1, 1),
                             wx.ALIGN_BOTTOM | wx.BOTTOM | wx.RIGHT | wx.TOP, 5)

        self.cmdGotoHomepage = wx.Button(self.pnlPluginInfo, wx.ID_ANY, u"Homepage", wx.DefaultPosition, wx.DefaultSize,
                                         0)
        gbPluginInfoCard.Add(self.cmdGotoHomepage, wx.GBPosition(3, 2), wx.GBSpan(1, 1), wx.ALIGN_BOTTOM | wx.BOTTOM, 5)

        szrPluginInfo.Add(gbPluginInfoCard, 0, wx.ALL | wx.EXPAND, 10)

        self.txtPluginInfoDescription = wx.TextCtrl(self.pnlPluginInfo, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition,
                                                    wx.DefaultSize, wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP)
        szrPluginInfo.Add(self.txtPluginInfoDescription, 1, wx.BOTTOM | wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        self.lblKeywords = wx.StaticText(self.pnlPluginInfo, wx.ID_ANY, u"Keywords:", wx.DefaultPosition,
                                         wx.DefaultSize, 0)
        self.lblKeywords.Wrap(-1)

        szrPluginInfo.Add(self.lblKeywords, 0, wx.LEFT, 10)

        self.lblPluginInfoKeywords = wx.StaticText(self.pnlPluginInfo, wx.ID_ANY, u"NULL", wx.DefaultPosition,
                                                   wx.DefaultSize, 0)
        self.lblPluginInfoKeywords.Wrap(-1)

        szrPluginInfo.Add(self.lblPluginInfoKeywords, 0, wx.BOTTOM | wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        self.stlPluginInfo = wx.StaticLine(self.pnlPluginInfo, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize,
                                           wx.LI_HORIZONTAL)
        szrPluginInfo.Add(self.stlPluginInfo, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)

        gbPluginAuthorCard = wx.GridBagSizer(0, 0)
        gbPluginAuthorCard.SetFlexibleDirection(wx.BOTH)
        gbPluginAuthorCard.SetNonFlexibleGrowMode(wx.FLEX_GROWMODE_SPECIFIED)

        self.bmpPluginAuthorAvatar = wx.StaticBitmap(self.pnlPluginInfo, wx.ID_ANY, wx.NullBitmap, wx.DefaultPosition,
                                                     wx.Size(64, 64), 0)
        self.bmpPluginAuthorAvatar.SetMinSize(wx.Size(64, 64))

        gbPluginAuthorCard.Add(self.bmpPluginAuthorAvatar, wx.GBPosition(0, 2), wx.GBSpan(2, 1), wx.ALL, 5)

        self.lblPluginInfoAuthor = wx.StaticText(self.pnlPluginInfo, wx.ID_ANY, u"Open Science Tools Ltd.",
                                                 wx.DefaultPosition, wx.DefaultSize, 0)
        self.lblPluginInfoAuthor.Wrap(-1)

        self.lblPluginInfoAuthor.SetFont(
            wx.Font(14, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, False, "Lucida Grande"))

        gbPluginAuthorCard.Add(self.lblPluginInfoAuthor, wx.GBPosition(0, 0), wx.GBSpan(1, 2), wx.RIGHT, 5)

        self.cmdAuthorGithub = wx.Button(self.pnlPluginInfo, wx.ID_ANY, u"GitHub", wx.DefaultPosition, wx.DefaultSize,
                                         wx.BU_EXACTFIT)
        gbPluginAuthorCard.Add(self.cmdAuthorGithub, wx.GBPosition(1, 0), wx.GBSpan(1, 1), wx.ALIGN_BOTTOM, 0)

        self.cmdAuthorGotoEmail = wx.Button(self.pnlPluginInfo, wx.ID_ANY, u"Email", wx.DefaultPosition, wx.DefaultSize,
                                            wx.BU_EXACTFIT)
        gbPluginAuthorCard.Add(self.cmdAuthorGotoEmail, wx.GBPosition(1, 1), wx.GBSpan(1, 1), wx.ALIGN_BOTTOM | wx.LEFT,
                               10)

        szrPluginInfo.Add(gbPluginAuthorCard, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        self.pnlPluginInfo.SetSizer(szrPluginInfo)
        self.pnlPluginInfo.Layout()
        szrPluginInfo.Fit(self.pnlPluginInfo)
        self.splPlugins.SplitVertically(self.pnlPluginList, self.pnlPluginInfo, 250)
        szrPlugins.Add(self.splPlugins, 1, wx.EXPAND, 5)

        self.pnlPlugins.SetSizer(szrPlugins)
        self.pnlPlugins.Layout()
        szrPlugins.Fit(self.pnlPlugins)
        self.nbMain.AddPage(self.pnlPlugins, u"Plugins", True)
        self.pnlPackages = wx.Panel(self.nbMain, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL)
        self.pnlPackages.SetBackgroundColour(wx.Colour(255, 255, 255))

        szrPackages = wx.BoxSizer(wx.VERTICAL)

        self.splPackages = wx.SplitterWindow(self.pnlPackages, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize,
                                             wx.SP_NOBORDER)
        # self.splPackages.SetSashSize( 12 )
        self.splPackages.Bind(wx.EVT_IDLE, self.splPackagesOnIdle)
        self.splPackages.SetMinimumPaneSize(100)

        self.splPackages.SetBackgroundColour(wx.Colour(255, 255, 255))

        self.pnlPackageList = wx.Panel(self.splPackages, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize,
                                       wx.TAB_TRAVERSAL)
        self.pnlPackageList.SetBackgroundColour(wx.Colour(255, 255, 255))

        szrPackageList = wx.BoxSizer(wx.VERTICAL)

        self.txtSearchPackages = wx.SearchCtrl(self.pnlPackageList, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition,
                                               wx.DefaultSize, style=wx.TE_PROCESS_ENTER)
        self.txtSearchPackages.ShowSearchButton(True)
        self.txtSearchPackages.ShowCancelButton(True)
        szrPackageList.Add(self.txtSearchPackages, 0, wx.ALL | wx.EXPAND, 10)

        self.tvwPackageList = wx.dataview.TreeListCtrl(self.pnlPackageList, wx.ID_ANY, wx.DefaultPosition,
                                                       wx.DefaultSize, wx.dataview.TL_SINGLE)

        szrPackageList.Add(self.tvwPackageList, 1, wx.EXPAND | wx.ALL, 10)

        szrPackageListButtons = wx.BoxSizer(wx.HORIZONTAL)

        self.cmdShowPaths = wx.Button(self.pnlPackageList, wx.ID_ANY, u"Paths ...", wx.DefaultPosition, wx.DefaultSize,
                                      0)
        szrPackageListButtons.Add(self.cmdShowPaths, 0, wx.ALL, 5)

        self.cmdInstallFromFile = wx.Button(self.pnlPackageList, wx.ID_ANY, u"Install from file ...",
                                            wx.DefaultPosition, wx.DefaultSize, 0)
        szrPackageListButtons.Add(self.cmdInstallFromFile, 0, wx.ALL, 5)

        szrPackageList.Add(szrPackageListButtons, 0, wx.ALL | wx.EXPAND, 5)

        self.pnlPackageList.SetSizer(szrPackageList)
        self.pnlPackageList.Layout()
        szrPackageList.Fit(self.pnlPackageList)
        self.pnlPackageInfo = wx.Panel(self.splPackages, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize,
                                       wx.TAB_TRAVERSAL)
        self.pnlPackageInfo.SetBackgroundColour(wx.Colour(255, 255, 255))

        szrPackageInfo = wx.BoxSizer(wx.VERTICAL)

        gbPackageInfoCard = wx.GridBagSizer(0, 0)
        gbPackageInfoCard.SetFlexibleDirection(wx.BOTH)
        gbPackageInfoCard.SetNonFlexibleGrowMode(wx.FLEX_GROWMODE_SPECIFIED)

        self.lblPackageInfoName = wx.StaticText(self.pnlPackageInfo, wx.ID_ANY, u"Package Name", wx.DefaultPosition,
                                                wx.DefaultSize, 0)
        self.lblPackageInfoName.Wrap(-1)

        self.lblPackageInfoName.SetFont(
            wx.Font(18, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, False, "Lucida Grande"))

        gbPackageInfoCard.Add(self.lblPackageInfoName, wx.GBPosition(0, 0), wx.GBSpan(1, 2), wx.ALL, 5)

        self.lblPackageInfoBy = wx.StaticText(self.pnlPackageInfo, wx.ID_ANY, u"By", wx.DefaultPosition, wx.DefaultSize,
                                              0)
        self.lblPackageInfoBy.Wrap(-1)

        gbPackageInfoCard.Add(self.lblPackageInfoBy, wx.GBPosition(1, 0), wx.GBSpan(1, 1),
                              wx.ALL | wx.LEFT | wx.ALIGN_RIGHT, 5)

        self.hypAuthorLink = wx.adv.HyperlinkCtrl(self.pnlPackageInfo, wx.ID_ANY, u"PsychoPy Team",
                                                  u"https://psychopy.org", wx.DefaultPosition, wx.DefaultSize,
                                                  wx.adv.HL_DEFAULT_STYLE)
        gbPackageInfoCard.Add(self.hypAuthorLink, wx.GBPosition(1, 1), wx.GBSpan(1, 2),
                              wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        self.lblPackageLicense = wx.StaticText(self.pnlPackageInfo, wx.ID_ANY, u"License", wx.DefaultPosition,
                                               wx.DefaultSize, 0)
        self.lblPackageLicense.Wrap(-1)

        gbPackageInfoCard.Add(self.lblPackageLicense, wx.GBPosition(2, 0), wx.GBSpan(1, 1), wx.ALL | wx.ALIGN_RIGHT, 5)

        self.lblPackageInfoLicense = wx.StaticText(self.pnlPackageInfo, wx.ID_ANY, u"NULL", wx.DefaultPosition,
                                                   wx.DefaultSize, 0)
        self.lblPackageInfoLicense.Wrap(-1)

        gbPackageInfoCard.Add(self.lblPackageInfoLicense, wx.GBPosition(2, 1), wx.GBSpan(1, 1),
                              wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        szrPackageInfo.Add(gbPackageInfoCard, 0, wx.ALL | wx.EXPAND, 10)

        self.txtPackageDescription = wx.TextCtrl(self.pnlPackageInfo, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition,
                                                 wx.DefaultSize, wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP)
        szrPackageInfo.Add(self.txtPackageDescription, 1, wx.ALL | wx.EXPAND, 10)

        szrPackageInstallButtons = wx.BoxSizer(wx.HORIZONTAL)

        self.cmdInstallPackage = wx.Button(self.pnlPackageInfo, wx.ID_ANY, u"Install", wx.DefaultPosition,
                                           wx.DefaultSize, 0)
        szrPackageInstallButtons.Add(self.cmdInstallPackage, 0, wx.ALL, 5)

        self.lblPackageInfoVersion = wx.StaticText(self.pnlPackageInfo, wx.ID_ANY, u"Version", wx.DefaultPosition,
                                                   wx.DefaultSize, 0)
        self.lblPackageInfoVersion.Wrap(-1)

        szrPackageInstallButtons.Add(self.lblPackageInfoVersion, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 5)

        cboPackageVersionChoices = [u"Not Specified"]
        self.cboPackageVersion = wx.ComboBox(self.pnlPackageInfo, wx.ID_ANY, u"Not Specified", wx.DefaultPosition,
                                             wx.DefaultSize, cboPackageVersionChoices,
                                             wx.CB_DROPDOWN | wx.CB_READONLY | wx.CB_SORT)
        self.cboPackageVersion.SetSelection(0)
        self.cboPackageVersion.SetMinSize(wx.Size(180, -1))
        szrPackageInstallButtons.Add(self.cboPackageVersion, 0, wx.ALIGN_CENTER_VERTICAL, 5)

        szrPackageInstallButtons.Add((0, 0), 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        self.cmdUninstallPackage = wx.Button(self.pnlPackageInfo, wx.ID_ANY, u"Remove", wx.DefaultPosition,
                                             wx.DefaultSize, 0)
        szrPackageInstallButtons.Add(self.cmdUninstallPackage, 0, wx.ALL, 5)

        szrPackageInfo.Add(szrPackageInstallButtons, 0, wx.ALL | wx.EXPAND, 5)

        self.pnlPackageInfo.SetSizer(szrPackageInfo)
        self.pnlPackageInfo.Layout()
        szrPackageInfo.Fit(self.pnlPackageInfo)
        self.splPackages.SplitVertically(self.pnlPackageList, self.pnlPackageInfo, 250)
        szrPackages.Add(self.splPackages, 1, wx.EXPAND, 5)

        self.pnlPackages.SetSizer(szrPackages)
        self.pnlPackages.Layout()
        szrPackages.Fit(self.pnlPackages)
        self.nbMain.AddPage(self.pnlPackages, u"Python Packages", False)
        self.pnlConsole = wx.Panel(self.nbMain, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL)
        self.pnlConsole.SetBackgroundColour(wx.Colour(255, 255, 255))

        szrConsole = wx.BoxSizer(wx.VERTICAL)

        self.txtConsole = wx.TextCtrl(self.pnlConsole, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                      wx.HSCROLL | wx.TE_MULTILINE | wx.TE_READONLY)
        szrConsole.Add(self.txtConsole, 1, wx.ALL | wx.EXPAND | wx.TOP, 10)

        szrConsoleButtons = wx.BoxSizer(wx.HORIZONTAL)

        self.cmdCopyConsole = wx.Button(self.pnlConsole, wx.ID_ANY, u"&Copy", wx.DefaultPosition, wx.DefaultSize, 0)
        szrConsoleButtons.Add(self.cmdCopyConsole, 0, wx.ALL, 5)

        self.cmdClearConsole = wx.Button(self.pnlConsole, wx.ID_ANY, u"C&lear", wx.DefaultPosition, wx.DefaultSize, 0)
        szrConsoleButtons.Add(self.cmdClearConsole, 0, wx.ALL, 5)

        szrConsole.Add(szrConsoleButtons, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        self.pnlConsole.SetSizer(szrConsole)
        self.pnlConsole.Layout()
        szrConsole.Fit(self.pnlConsole)
        self.nbMain.AddPage(self.pnlConsole, u"Console", False)

        szrMain.Add(self.nbMain, 1, wx.EXPAND | wx.ALL, 5)

        self.pnlDlgCtrls = wx.Panel(self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL)
        szrDlgCtrls = wx.GridSizer(1, 2, 0, 0)

        self.cmdHelp = wx.Button(self.pnlDlgCtrls, wx.ID_ANY, u"Help", wx.DefaultPosition, wx.DefaultSize,
                                 wx.BU_EXACTFIT)
        szrDlgCtrls.Add(self.cmdHelp, 0, wx.ALL, 5)

        self.cmdCloseDlg = wx.Button(self.pnlDlgCtrls, wx.ID_ANY, u"&Close", wx.DefaultPosition, wx.DefaultSize, 0)
        szrDlgCtrls.Add(self.cmdCloseDlg, 0, wx.ALL | wx.ALIGN_RIGHT, 5)

        self.pnlDlgCtrls.SetSizer(szrDlgCtrls)
        self.pnlDlgCtrls.Layout()
        szrDlgCtrls.Fit(self.pnlDlgCtrls)
        szrMain.Add(self.pnlDlgCtrls, 0, wx.ALL | wx.EXPAND, 5)

        self.SetSizer(szrMain)
        self.Layout()

        self.Centre(wx.BOTH)

        # Connect Events
        self.nbMain.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.onNotebookPageChanged)
        # self.txtSearchPlugins.Bind( wx.EVT_SEARCHCTRL_CANCEL_BTN, self.onPluginCancelButtonClicked )
        # self.txtSearchPlugins.Bind( wx.EVT_SEARCHCTRL_SEARCH_BTN, self.onPluginSearchButtonClicked )
        self.txtSearchPlugins.Bind(wx.EVT_TEXT, self.onPluginSearchText)
        self.txtSearchPlugins.Bind(wx.EVT_TEXT_ENTER, self.onPluginSearchEnter)
        self.pnlAvailablePlugins.Bind(wx.EVT_LEFT_UP, self.onPluginListClicked)
        self.pnlAvailablePlugins.Bind(wx.EVT_LEFT_DOWN, self.onPluginListMouseEvents)
        self.pnlAvailablePlugins.Bind(wx.EVT_LEFT_UP, self.onPluginListMouseEvents)
        self.pnlAvailablePlugins.Bind(wx.EVT_MIDDLE_DOWN, self.onPluginListMouseEvents)
        self.pnlAvailablePlugins.Bind(wx.EVT_MIDDLE_UP, self.onPluginListMouseEvents)
        self.pnlAvailablePlugins.Bind(wx.EVT_RIGHT_DOWN, self.onPluginListMouseEvents)
        self.pnlAvailablePlugins.Bind(wx.EVT_RIGHT_UP, self.onPluginListMouseEvents)
        # self.pnlAvailablePlugins.Bind( wx.EVT_AUX1_DOWN, self.onPluginListMouseEvents )
        # self.pnlAvailablePlugins.Bind( wx.EVT_AUX1_UP, self.onPluginListMouseEvents )
        # self.pnlAvailablePlugins.Bind( wx.EVT_AUX2_DOWN, self.onPluginListMouseEvents )
        # self.pnlAvailablePlugins.Bind( wx.EVT_AUX2_UP, self.onPluginListMouseEvents )
        self.pnlAvailablePlugins.Bind(wx.EVT_MOTION, self.onPluginListMouseEvents)
        self.pnlAvailablePlugins.Bind(wx.EVT_LEFT_DCLICK, self.onPluginListMouseEvents)
        self.pnlAvailablePlugins.Bind(wx.EVT_MIDDLE_DCLICK, self.onPluginListMouseEvents)
        self.pnlAvailablePlugins.Bind(wx.EVT_RIGHT_DCLICK, self.onPluginListMouseEvents)
        # self.pnlAvailablePlugins.Bind( wx.EVT_AUX1_DCLICK, self.onPluginListMouseEvents )
        # self.pnlAvailablePlugins.Bind( wx.EVT_AUX2_DCLICK, self.onPluginListMouseEvents )
        self.pnlAvailablePlugins.Bind(wx.EVT_LEAVE_WINDOW, self.onPluginListMouseEvents)
        self.pnlAvailablePlugins.Bind(wx.EVT_ENTER_WINDOW, self.onPluginListMouseEvents)
        self.pnlAvailablePlugins.Bind(wx.EVT_MOUSEWHEEL, self.onPluginListMouseEvents)
        self.pnlAvailablePlugins.Bind(wx.EVT_MOUSEWHEEL, self.onPluginListMouseWheel)
        self.pnlAvailablePlugins.Bind(wx.EVT_SIZE, self.onPluginListSize)
        self.cmdInstallPlugin.Bind(wx.EVT_BUTTON, self.onPluginInstallClicked)
        self.cmdGotoHomepage.Bind(wx.EVT_BUTTON, self.onPluginHomepageClicked)
        self.cmdAuthorGithub.Bind(wx.EVT_BUTTON, self.onPluginAuthorClicked)
        self.cmdAuthorGotoEmail.Bind(wx.EVT_BUTTON, self.onPluginEmailClicked)
        self.txtSearchPackages.Bind(wx.EVT_SEARCH_CANCEL, self.onPackageSearchCancelClicked)
        self.txtSearchPackages.Bind(wx.EVT_SEARCH, self.onPackageSearchButtonClicked)
        # self.txtSearchPackages.Bind( wx.EVT_TEXT, self.onPackageSearchText )
        self.txtSearchPackages.Bind(wx.EVT_SEARCH, self.onPackageSearchEnter)
        # self.tvwPackageList.Bind(wx.dataview.EVT_TREELIST_ITEM_ACTIVATED, self.onPackageListActivated)
        # self.tvwPackageList.Bind(wx.dataview.EVT_TREELIST_ITEM_CONTEXT_MENU, self.onPackageListContextMenu)
        self.tvwPackageList.Bind(wx.dataview.EVT_TREELIST_SELECTION_CHANGED, self.onPackageListSelChanged)
        self.cmdShowPaths.Bind(wx.EVT_BUTTON, self.onPackagePathsClicked)
        self.cmdInstallFromFile.Bind(wx.EVT_BUTTON, self.onInstallFromFileClicked)
        self.hypAuthorLink.Bind(wx.adv.EVT_HYPERLINK, self.onPackageAuthorURLClicked)
        self.cmdInstallPackage.Bind(wx.EVT_BUTTON, self.onPackageInstallClicked)
        self.cboPackageVersion.Bind(wx.EVT_COMBOBOX, self.onVersionChoice)
        self.cboPackageVersion.Bind(wx.EVT_COMBOBOX_DROPDOWN, self.onVersionChoiceDropdown)
        self.cmdUninstallPackage.Bind(wx.EVT_BUTTON, self.onPackageUninstallClicked)
        self.cmdCopyConsole.Bind(wx.EVT_BUTTON, self.onConsoleCopy)
        self.cmdClearConsole.Bind(wx.EVT_BUTTON, self.onConsoleClear)
        self.cmdHelp.Bind(wx.EVT_BUTTON, self.onHelpClicked)
        self.cmdCloseDlg.Bind(wx.EVT_BUTTON, self.onCloseClicked)

    def __del__(self):
        pass

    # Virtual event handlers, override them in your derived class
    def onNotebookPageChanged(self, event):
        event.Skip()

    def onPluginCancelButtonClicked(self, event):
        event.Skip()

    def onPluginSearchButtonClicked(self, event):
        event.Skip()

    def onPluginSearchText(self, event):
        event.Skip()

    def onPluginSearchEnter(self, event):
        event.Skip()

    def onPluginListClicked(self, event):
        event.Skip()

    def onPluginListMouseEvents(self, event):
        event.Skip()

    def onPluginListMouseWheel(self, event):
        event.Skip()

    def onPluginListSize(self, event):
        event.Skip()

    def onPluginInstallClicked(self, event):
        event.Skip()

    def onPluginHomepageClicked(self, event):
        event.Skip()

    def onPluginAuthorClicked(self, event):
        event.Skip()

    def onPluginEmailClicked(self, event):
        event.Skip()

    def onPackageSearchCancelClicked(self, event):
        event.Skip()

    def onPackageSearchButtonClicked(self, event):
        event.Skip()

    def onPackageSearchText(self, event):
        event.Skip()

    def onPackageSearchEnter(self, event):
        event.Skip()

    def onPackageListActivated(self, event):
        event.Skip()

    def onPackageListContextMenu(self, event):
        event.Skip()

    def onPackageListSelChanged(self, event):
        event.Skip()

    def onPackagePathsClicked(self, event):
        event.Skip()

    def onInstallFromFileClicked(self, event):
        event.Skip()

    def onPackageAuthorURLClicked(self, event):
        event.Skip()

    def onPackageInstallClicked(self, event):
        event.Skip()

    def onVersionChoice(self, event):
        event.Skip()

    def onVersionChoiceDropdown(self, event):
        event.Skip()

    def onPackageUninstallClicked(self, event):
        event.Skip()

    def onConsoleCopy(self, event):
        event.Skip()

    def onConsoleClear(self, event):
        event.Skip()

    def onHelpClicked(self, event):
        event.Skip()

    def onCloseClicked(self, event):
        event.Skip()

    def splPluginsOnIdle(self, event):
        self.splPlugins.SetSashPosition(380)
        self.splPlugins.Unbind(wx.EVT_IDLE)

    def splPackagesOnIdle(self, event):
        self.splPackages.SetSashPosition(380)
        self.splPackages.Unbind(wx.EVT_IDLE)


class BasePluginInfoCard(wx.Panel):
    def __init__(self, parent, id=wx.ID_ANY, pos=wx.DefaultPosition, size=wx.Size(320, 80),
                 style=wx.BORDER_NONE | wx.TAB_TRAVERSAL, name=wx.EmptyString):
        wx.Panel.__init__(self, parent, id=id, pos=pos, size=size, style=style, name=name)

        self.SetBackgroundColour(wx.Colour(255, 255, 255))

        szrMain = wx.BoxSizer(wx.HORIZONTAL)

        self.bmpPluginIcon = wx.StaticBitmap(self, wx.ID_ANY, wx.NullBitmap, wx.DefaultPosition, wx.Size(48, 48), 0)
        self.bmpPluginIcon.SetMinSize(wx.Size(48, 48))

        szrMain.Add(self.bmpPluginIcon, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 2)

        szrInfoText = wx.BoxSizer(wx.VERTICAL)

        self.lblPluginTitle = wx.StaticText(self, wx.ID_ANY, u"", wx.DefaultPosition,
                                            wx.DefaultSize, wx.ST_NO_AUTORESIZE)
        self.lblPluginTitle.Wrap(-1)

        self.lblPluginTitle.SetFont(
            wx.Font(wx.NORMAL_FONT.GetPointSize(), wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD,
                    False, wx.EmptyString))

        szrInfoText.Add(self.lblPluginTitle, 0, wx.ALL | wx.EXPAND, 1)

        self.txtPluginExtraInfo = wx.StaticText(self, wx.ID_ANY, u"",
                                                wx.DefaultPosition, wx.DefaultSize, wx.ST_NO_AUTORESIZE)
        self.txtPluginExtraInfo.Wrap(-1)

        szrInfoText.Add(self.txtPluginExtraInfo, 0, wx.ALL | wx.EXPAND, 1)

        szrBottomRow = wx.BoxSizer(wx.HORIZONTAL)

        self.hypLink = wx.adv.HyperlinkCtrl(self, wx.ID_ANY, u"Author", u"http://www.wxformbuilder.org",
                                            wx.DefaultPosition, wx.DefaultSize, wx.adv.HL_ALIGN_LEFT)
        szrBottomRow.Add(self.hypLink, 1, wx.EXPAND | wx.LEFT, 3)

        self.cmdChangeInstall = wx.Button(self, wx.ID_ANY, u"Install", wx.DefaultPosition, wx.DefaultSize, 0)
        self.cmdChangeInstall.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW))

        szrBottomRow.Add(self.cmdChangeInstall, 0, wx.ALL, 2)

        szrInfoText.Add(szrBottomRow, 0, wx.EXPAND, 5)

        szrMain.Add(szrInfoText, 1, wx.ALL | wx.EXPAND, 5)

        self.SetSizer(szrMain)
        self.Layout()

        # Connect Events
        self.Bind(wx.EVT_LEFT_UP, self.onLeftUp)
        self.bmpPluginIcon.Bind(wx.EVT_LEFT_UP, self.onPluginIconLeftUp)
        self.lblPluginTitle.Bind(wx.EVT_LEFT_UP, self.onPluginTitleLeftUp)
        self.txtPluginExtraInfo.Bind(wx.EVT_LEFT_UP, self.onPluginExtraInfoLeftUp)
        self.cmdChangeInstall.Bind(wx.EVT_BUTTON, self.onChangeInstall)

    def __del__(self):
        pass

    # Virtual event handlers, override them in your derived class
    def onLeftUp(self, event):
        event.Skip()

    def onPluginIconLeftUp(self, event):
        event.Skip()

    def onPluginTitleLeftUp(self, event):
        event.Skip()

    def onPluginExtraInfoLeftUp(self, event):
        event.Skip()

    def onChangeInstall(self, event):
        event.Skip()

