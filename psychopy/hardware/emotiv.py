#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2022 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

"""Classes for Emotiv hardware.
"""
__all__ = [
    'Cortex',
    'CortexApiException',
    'CortexTimingException',
    'CortexNoHeadsetException'
]

import psychopy.logging as logging

try:
    from psychopy_emotiv.emotiv import (  # from extension package
        Cortex,
        CortexApiException,
        CortexTimingException,
        CortexNoHeadsetException)
except (ModuleNotFoundError, ImportError):
    logging.error(
        "Support for Emotiv hardware is not available this session. Please "
        "install `psychopy-emotiv` and restart the session to enable support.")

if __name__ == "__main__":
    pass
