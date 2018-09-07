#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tools for stereoscopy.

"""

# Part of the PsychoPy library
# Copyright (C) 2018 Jonathan Peirce
# Distributed under the terms of the GNU General Public License (GPL).

import math
import numpy as np
from collections import namedtuple

Frustum = namedtuple(
    'Frustum',
    ['left', 'right', 'bottom', 'top', 'nearVal', 'farVal'])


def visualAngle(size, distance):
    """Compute the visual angle of an object.

    """
    return 2.0 * math.atan(size / (2.0 * distance))


def computeFrustum(scrWidth,
                   scrAspect,
                   scrDist,
                   convergeOffset=0.0,
                   eyeOffset=0.0,
                   nearClip=0.01,
                   farClip=100.0):
    """Calculate frustum parameters for rendering stimuli with perspective. If
    an eye offset is provided, an asymmetric frustum is returned which can be
    used for stereoscopic rendering.

    Parameters
    ----------
    scrWidth : float
        The display's width in meters.
    scrAspect : float
        Aspect ratio of the display (width / height).
    scrDist : float
        Distance to the screen from the view in meters. Measured from the center
        of their eyes.
    convergeOffset : float
        Offset of the convergence plane from the screen. Objects falling on this
        plane will have zero disparity. For best results, the convergence plane
        should be set to the same distance as the screen (0.0 by default).
    eyeOffset : float
        Half the inter-ocular separation (i.e. the horizontal distance between
        the nose and center of the pupil) in meters. If eyeOffset is 0.0, a
        symmetric frustum is returned.
    nearClip : float
        Distance to the near clipping plane in meters from the viewer. Should be
        at least less than scrDist.
    farClip : float
        Distance to the far clipping plane from the viewer in meters. Must be
        >nearClip.

    Returns
    -------
    Frustum
        Namedtuple with frustum parameters. Can be directly passed to
        glFrustum (e.g. glFrustum(*f)).

    Notes
    -----
    1.  The view point must be transformed for objects to appear correctly.
        Offsets in the X-direction must be applied +/- eyeOffset to account for
        inter-ocular separation. A transforqmation in the Z-direction must be
        applied to account for screen distance. These offsets MUST be applied to
        the MODELVIEW matrix, not the PROJECTION matrix! Doing so will break
        lighting calculations.

    """
    d = scrWidth * (convergeOffset + scrDist)
    ratio = nearClip / float((convergeOffset + scrDist))

    right = (d - eyeOffset) * ratio
    left = (d + eyeOffset) * -ratio
    top = (scrWidth / float(scrAspect)) * nearClip
    bottom = -top

    return Frustum(left, right, bottom, top, nearClip, farClip)


def frustumToProjectionMatrix(f):
    """Generate a projection matrix with the provided frustum.

    Parameters
    ----------
    f : Frustum
        The frustum to convert.

    Returns
    -------
    numpy.ndarray
        4x4 projection matrix.

    """
    mOut = np.zeros((4, 4), float)
    mOut[0, 0] = (2.0 * f.nearVal) / (f.right - f.left)
    mOut[1, 1] = (2.0 * f.nearVal) / (f.top - f.bottom)
    mOut[2, 0] = (f.right + f.left) / (f.right - f.left)
    mOut[2, 1] = (f.top + f.bottom) / (f.top - f.bottom)
    mOut[2, 2] = (f.farVal + f.nearVal) / (f.farVal - f.nearVal)
    mOut[2, 3] = -1.0
    mOut[3, 2] = (2.0 * f.farVal * f.nearVal) / (f.farVal - f.nearVal)

    return mOut


# Anaglyph color filters
AnaglyphFilter = namedtuple(
    'AnaglyphFilter', ['maskLeft', 'maskRight', 'colorBias'])

AnaglyphRedCyan = AnaglyphFilter((True, False, False, False),
                                 (False, True, True, False),
                                 (1.0, 1.0, 1.0))
