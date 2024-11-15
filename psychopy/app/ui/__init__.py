#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Classes for graphical user interface elements for the main application.
"""

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2024 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

__all__ = [
    "BaseAuiFrame", 
    "BaseAuiNotebookPanel",
    "BaseAuiPropertyPanel",
    "PHI_RATIO",
    "INV_PHI_RATIO"]

from psychopy.app.ui.frame import BaseAuiFrame
from psychopy.app.ui.notebook import BaseAuiNotebookPanel
from psychopy.app.ui.propertyGrid import BaseAuiPropertyPanel

# constants for golden ratio used for layout
PHI_RATIO = (1 + 5 ** 0.5) / 2
INV_PHI_RATIO = PHI_RATIO - 1


if __name__ == "__main__":
    pass
