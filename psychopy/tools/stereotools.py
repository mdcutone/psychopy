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


def computeOffAxisFrustums(horzFov,
                           aspect,
                           scrDist,
                           convergeDist,
                           eyeOffset=0.031,
                           nearClip=0.01,
                           farClip=100.0):
    """Calculate frustum parameters for symmetric off-axis views.

    Parameters
    ----------
    horzFov : float
        The display's horizontal field of view in radians. Calculate as
        2.0 * atan(screenWidth / (2.0 * screenDistance)) with units in meters.
    aspect : float
        Aspect ratio of the display (width / height).
    convergeDist : float
        Offset of the convergence plane from the screen. Objects falling on this
        plane will have zero disparity. For best results, the convergence plane
        should be set to the same distance as the screen.
    eyeOffset : float
        Half the inter-ocular separation (i.e. the horizontal distance between
        the nose and center of the pupil) in meters.
    nearClip : float
        Distance to the near clipping plane in meters from the viewer. Should be
        at least less than scrDist.
    farClip : float
        Distance to the far clipping plane from the viewer in meters. Must be
        >nearClip.

    Returns
    -------
    tuple of Frustum
        A tuple which contains Frustum objects which stores the left and right
        frustums.

    Notes
    -----
    The view point must be transformed for objects to appear correctly. Offsets
    in the X-direction must be applied +/- eyeOffset to account for inter-ocular
    separation. A transformation in the Z-direction must be applied to account
    for screen distance. These offsets MUST be applied to the MODELVIEW matrix,
    not the PROJECTION matrix! Doing so will break lighting calculations.

    """
    halfHorzFov = math.tan(horzFov / 2.0)
    d = halfHorzFov * (convergeDist + scrDist)
    ratio = nearClip / float((convergeDist + scrDist))

    rightR = (d - eyeOffset) * ratio
    rightL = (d + eyeOffset) * ratio
    leftL = -rightR
    leftR = -rightL
    topR = topL = (halfHorzFov / float(aspect)) * nearClip
    bottomR = bottomL = -topR

    leftFrustum = Frustum(leftL, rightL, bottomL, topL, nearClip, farClip)
    rightFrustum = Frustum(leftR, rightR, bottomR, topR, nearClip, farClip)

    # apply frustums as such, for example the left eye ...
    #
    # GL.glMatrixMode(GL.GL_PROJECTION)
    # GL.glLoadIdentity()
    # GL.glFrustum(*leftFrustum)
    #
    # translate the viewer in the scene
    # GL.glMatrixMode(GL.GL_MODELVIEW)
    # GL.glTranslate(-(iod / 2.0), 0, -scrDist)

    return leftFrustum, rightFrustum


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
