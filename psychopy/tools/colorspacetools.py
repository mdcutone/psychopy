#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

"""Functions and classes related to color space conversion.
"""
from __future__ import absolute_import, division, print_function

__all__ = [
    'srgbTF',
    'rec709TF',
    'cielab2rgb',
    'cielch2rgb',
    'dkl2rgb',
    'dklCart2rgb',
    'rgb2dklCart',
    'hsv2rgb',
    'rgb2lms',
    'lms2rgb',
    'cielab2xyz',
    'xyz2rgb',
    'chromaTransform',
    'gammaTransform',
    'createConversionMatrix',
    'rgb2xyz',
    'ILLUMINANT_A',
    'ILLUMINANT_B',
    'ILLUMINANT_C',
    'ILLUMINANT_D50',
    'ILLUMINANT_D55',
    'ILLUMINANT_D65',
    'ILLUMINANT_D75',
    'ILLUMINANT_E',
    'ILLUMINANT_F2',
    'ILLUMINANT_F7',
    'ILLUMINANT_F11',
    'xyz2xyY',
    'xyz2cielab',
    'cielch2xyz',
    'xyY2xyz',
    'srgbTransform'
]

from past.utils import old_div
import numpy
from psychopy import logging
from psychopy.tools.coordinatetools import sph2cart

# standard illuminants
ILLUMINANT_A = numpy.array((1.09850, 1.00000, 0.35585))
ILLUMINANT_B = numpy.array((0.99072, 1.00000, 0.85223))
ILLUMINANT_C = numpy.array((0.98074, 1.00000, 1.18232))
ILLUMINANT_D50 = numpy.array((0.96422, 1.00000, 0.82521))
ILLUMINANT_D55 = numpy.array((0.95682, 1.00000, 0.92149))
ILLUMINANT_D65 = numpy.array((0.95047, 1.00000, 1.08883))
ILLUMINANT_D75 = numpy.array((0.94972, 1.00000, 1.22638))
ILLUMINANT_E = numpy.array((1.00000, 1.00000, 1.00000))
ILLUMINANT_F2 = numpy.array((0.99186, 1.00000, 0.67393))
ILLUMINANT_F7 = numpy.array((0.95041, 1.00000, 1.08747))
ILLUMINANT_F11 = numpy.array((1.00962, 1.00000, 0.64350))

# bradford cone-response matrices for chromatic adaptation transforms
_BRADFORD_CRM = numpy.ascontiguousarray([
    [0.8951, 0.2664, -0.1614],
    [-0.7502, 1.7135, 0.0367],
    [0.0389, -0.0685, 1.0296]
])
_BRADFORD_CRM_INV = numpy.linalg.inv(_BRADFORD_CRM)

# vob Kries cone-response matrices
_VONKRIES_CRM = numpy.ascontiguousarray([
    [0.40024, 0.7076, -0.08081],
    [-0.2263, 1.16532, 0.0457],
    [0.0,  0.0,  0.91822]
])
_VONKRIES_CRM_INV = numpy.linalg.inv(_VONKRIES_CRM)


def unpackColors(colors):  # used internally, not exported by __all__
    """Reshape an array of color values to Nx3 format.

    Many color conversion routines operate on color data in Nx3 format, where
    rows are color space coordinates. 1x3 and NxNx3 input are converted to Nx3
    format. The original shape and dimensions are also returned, allowing the
    color values to be returned to their original format using 'reshape'.

    Parameters
    ----------
    colors : ndarray, list or tuple of floats
        Nx3 or NxNx3 array of colors, last dim must be size == 3 specifying each
        color coordinate.

    Returns
    -------
    tuple
        Nx3 ndarray of converted colors, original shape, original dims.

    """
    # handle the various data types and shapes we might get as input
    colors = numpy.asarray(colors, dtype=float)

    orig_shape = colors.shape
    orig_dim = colors.ndim
    if orig_dim == 1 and orig_shape[0] == 3:
        colors = numpy.array(colors, ndmin=2)
    elif orig_dim == 2 and orig_shape[1] == 3:
        pass  # NOP, already in correct format
    elif orig_dim == 3 and orig_shape[2] == 3:
        colors = numpy.reshape(colors, (-1, 3))
    else:
        raise ValueError(
            "Invalid input dimensions or shape for input colors.")

    return colors, orig_shape, orig_dim


def srgbTF(rgb, reverse=False, **kwargs):
    """Apply sRGB transfer function (or gamma) to linear RGB values.

    Input values must have been transformed using a conversion matrix derived
    from sRGB primaries relative to D65.

    Parameters
    ----------
    rgb : tuple, list or ndarray of floats
        Nx3 or NxNx3 array of linear RGB values, last dim must be size == 3
        specifying RBG values.
    reverse : boolean
        If True, the reverse transfer function will convert sRGB -> linear RGB.

    Returns
    -------
    ndarray
        Array of transformed colors with same shape as input.

    """
    rgb, orig_shape, orig_dim = unpackColors(rgb)

    # apply the sRGB TF
    if not reverse:
        # applies the sRGB transfer function (linear RGB -> sRGB)
        to_return = numpy.where(
            rgb <= 0.0031308,
            rgb * 12.92,
            (1.0 + 0.055) * rgb ** (1.0 / 2.4) - 0.055)
    else:
        # do the inverse (sRGB -> linear RGB)
        to_return = numpy.where(
            rgb <= 0.04045,
            rgb / 12.92,
            ((rgb + 0.055) / 1.055) ** 2.4)

    if orig_dim == 1:
        to_return = to_return[0]
    elif orig_dim == 3:
        to_return = numpy.reshape(to_return, orig_shape)

    return to_return


def rec709TF(rgb, **kwargs):
    """Apply the Rec. 709 transfer function (or gamma) to linear RGB values.

    This transfer function is defined in the ITU-R BT.709 (2015) recommendation
    document (http://www.itu.int/rec/R-REC-BT.709-6-201506-I/en) and is
    commonly used with HDTV televisions.

    Parameters
    ----------
    rgb : tuple, list or ndarray of floats
        Nx3 or NxNx3 array of linear RGB values, last dim must be size == 3
        specifying RBG values.

    Returns
    -------
    ndarray
        Array of transformed colors with same shape as input.

    """
    rgb, orig_shape, orig_dim = unpackColors(rgb)

    # applies the Rec.709 transfer function (linear RGB -> Rec.709 RGB)
    # mdc - I didn't compute the inverse for this one.
    to_return = numpy.where(rgb >= 0.018,
                            1.099 * rgb ** 0.45 - 0.099,
                            4.5 * rgb)

    if orig_dim == 1:
        to_return = to_return[0]
    elif orig_dim == 3:
        to_return = numpy.reshape(to_return, orig_shape)

    return to_return


def cielab2rgb(lab,
               whiteXYZ=None,
               conversionMatrix=None,
               transferFunc=None,
               clip=False,
               **kwargs):
    """Transform CIE L*a*b* (1976) color space coordinates to RGB tristimulus
    values.

    CIE L*a*b* are first transformed into CIE XYZ (1931) color space, then the
    RGB conversion is applied. By default, the sRGB conversion matrix is used
    with a reference D65 white point. You may specify your own RGB conversion
    matrix and white point (in CIE XYZ) appropriate for your display.

    Parameters
    ----------
    lab : tuple, list or ndarray
        1-, 2-, 3-D vector of CIE L*a*b* coordinates to convert. The last
        dimension should be length-3 in all cases specifying a single
        coordinate.
    whiteXYZ : tuple, list or ndarray
        1-D vector coordinate of the white point in CIE-XYZ color space. Must be
        the same white point needed by the conversion matrix. The default
        white point is D65 if None is specified, defined as X, Y, Z = 0.9505,
        1.0000, 1.0890.
    conversionMatrix : tuple, list or ndarray
        3x3 conversion matrix to transform CIE-XYZ to RGB values. The default
        matrix is sRGB with a D65 white point if None is specified. Note that
        values must be gamma corrected to appear correctly according to the sRGB
        standard.
    transferFunc : pyfunc or None
        Signature of the transfer function to use. If None, values are kept as
        linear RGB (it's assumed your display is gamma corrected via the
        hardware CLUT). The TF must be appropriate for the conversion matrix
        supplied (default is sRGB). Additional arguments to 'transferFunc' can
        be passed by specifying them as keyword arguments. Gamma functions that
        come with PsychoPy are 'srgbTF' and 'rec709TF', see their docs for more
        information.
    clip : bool
        Make all output values representable by the display. However, colors
        outside of the display's gamut may not be valid!

    Returns
    -------
    ndarray
        Array of RGB tristimulus values.

    Example
    -------
    Converting a CIE L*a*b* color to linear RGB::

        import psychopy.tools.colorspacetools as cst
        cielabColor = (53.0, -20.0, 0.0)  # greenish color (L*, a*, b*)
        rgbColor = cst.cielab2rgb(cielabColor)

    Using a transfer function to convert to sRGB::

        rgbColor = cst.cielab2rgb(cielabColor, transferFunc=cst.srgbTF)

    """
    lab, orig_shape, orig_dim = unpackColors(lab)

    if conversionMatrix is None:
        # XYZ -> sRGB conversion matrix, assumes D65 white point
        # mdc - computed using makeXYZ2RGB with sRGB primaries
        conversionMatrix = numpy.asmatrix([
            [3.24096994, -1.53738318, -0.49861076],
            [-0.96924364, 1.8759675, 0.04155506],
            [0.05563008, -0.20397696, 1.05697151]
        ])

    if whiteXYZ is None:
        # D65 white point in CIE-XYZ color space
        #   See: https://en.wikipedia.org/wiki/SRGB
        whiteXYZ = numpy.asarray([0.9505, 1.0000, 1.0890])

    L = lab[:, 0]  # lightness
    a = lab[:, 1]  # green (-)  <-> red (+)
    b = lab[:, 2]  # blue (-) <-> yellow (+)
    wht_x, wht_y, wht_z = whiteXYZ  # white point in CIE-XYZ color space

    # convert Lab to CIE-XYZ color space
    # uses reverse transformation found here:
    #   https://en.wikipedia.org/wiki/Lab_color_space
    xyz_array = numpy.zeros(lab.shape)
    s = (L + 16.0) / 116.0
    xyz_array[:, 0] = s + (a / 500.0)
    xyz_array[:, 1] = s
    xyz_array[:, 2] = s - (b / 200.0)

    # evaluate the inverse f-function
    delta = 6.0 / 29.0
    xyz_array = numpy.where(xyz_array > delta,
                            xyz_array ** 3.0,
                            (xyz_array - (4.0 / 29.0)) * (3.0 * delta ** 2.0))

    # multiply in white values
    xyz_array[:, 0] *= wht_x
    xyz_array[:, 1] *= wht_y
    xyz_array[:, 2] *= wht_z

    # convert to sRGB using the specified conversion matrix
    rgb_out = numpy.asarray(numpy.dot(xyz_array, conversionMatrix.T))

    # apply sRGB gamma correction if requested
    if transferFunc is not None:
        rgb_out = transferFunc(rgb_out, **kwargs)

    # clip unrepresentable colors if requested
    if clip:
        rgb_out = numpy.clip(rgb_out, 0.0, 1.0)

    # make the output match the dimensions/shape of input
    if orig_dim == 1:
        rgb_out = rgb_out[0]
    elif orig_dim == 3:
        rgb_out = numpy.reshape(rgb_out, orig_shape)

    return rgb_out * 2.0 - 1.0


def cielch2rgb(lch,
               whiteXYZ=None,
               conversionMatrix=None,
               transferFunc=None,
               clip=False,
               **kwargs):
    """Transform CIE L*C*h* coordinates to RGB tristimulus values.

    Parameters
    ----------
    lch : tuple, list or ndarray
        1-, 2-, 3-D vector of CIE L*C*h* coordinates to convert. The last
        dimension should be length-3 in all cases specifying a single
        coordinate. The hue angle *h is expected in degrees.
    whiteXYZ : tuple, list or ndarray
        1-D vector coordinate of the white point in CIE-XYZ color space. Must be
        the same white point needed by the conversion matrix. The default
        white point is D65 if None is specified, defined as X, Y, Z = 0.9505,
        1.0000, 1.0890
    conversionMatrix : tuple, list or ndarray
        3x3 conversion matrix to transform CIE-XYZ to RGB values. The default
        matrix is sRGB with a D65 white point if None is specified. Note that
        values must be gamma corrected to appear correctly according to the sRGB
        standard.
    transferFunc : pyfunc or None
        Signature of the transfer function to use. If None, values are kept as
        linear RGB (it's assumed your display is gamma corrected via the
        hardware CLUT). The TF must be appropriate for the conversion matrix
        supplied. Additional arguments to 'transferFunc' can be passed by
        specifying them as keyword arguments. Gamma functions that come with
        PsychoPy are 'srgbTF' and 'rec709TF', see their docs for more
        information.
    clip : boolean
        Make all output values representable by the display. However, colors
        outside of the display's gamut may not be valid!

    Returns
    -------
    ndarray
        array of RGB tristimulus values

    """
    lch, orig_shape, orig_dim = unpackColors(lch)

    # convert values to L*a*b*
    lab = numpy.empty(lch.shape, dtype=lch.dtype)
    lab[:, 0] = lch[:, 0]
    lab[:, 1] = lch[:, 1] * numpy.math.cos(numpy.math.radians(lch[:, 2]))
    lab[:, 2] = lch[:, 1] * numpy.math.sin(numpy.math.radians(lch[:, 2]))

    # convert to RGB using the CIE L*a*b* function
    rgb_out = cielab2rgb(lab,
                         whiteXYZ=whiteXYZ,
                         conversionMatrix=conversionMatrix,
                         transferFunc=transferFunc,
                         clip=clip,
                         **kwargs)

    # make the output match the dimensions/shape of input
    if orig_dim == 1:
        rgb_out = rgb_out[0]
    elif orig_dim == 3:
        rgb_out = numpy.reshape(rgb_out, orig_shape)

    return rgb_out  # don't do signed RGB conversion, done by cielab2rgb


def xyz2rgb(xyz, conversionMatrix=None, clip=True, signed=False):
    """Convert CIE-XYZ to linear RGB colors.

    Parameters
    ----------
    xyz : array_like
        1-, 2-, 3-D vector of CIE-XYZ coordinates to convert. The last
        dimension should be length-3 in all cases specifying a single
        coordinate.
    conversionMatrix : array_like
        Conversion matrix to use, if `None`, the sRGB conversion matrix is used,
        assuming a D65 white point.
    clip : boolean
        Make all output values representable by the display. However, colors
        outside of the display's gamut may not be valid!
    signed : bool
        Use signed [-1:1] PsychoPy colors. If `False`, valid colors will be
        output within the range of [0:1].

    Returns
    -------
    ndarray
        Array RGB color values with similar shape to `xyz` input.

    """
    xyz, orig_shape, orig_dim = unpackColors(xyz)

    # XYZ -> sRGB conversion matrix, assumes D65 white point
    if conversionMatrix is None:
        conversionMatrix = numpy.asarray([
            [3.24096994, -1.53738318, -0.49861076],
            [-0.96924364, 1.8759675, 0.04155506],
            [0.05563008, -0.20397696, 1.05697151]])
    else:
        assert conversionMatrix.shape == (3, 3)

    rgb_out = xyz.dot(conversionMatrix.T)

    # clip unrepresentable colors if requested
    if clip:
        rgb_out = numpy.clip(rgb_out, 0.0, 1.0)

    if orig_dim == 1:
        rgb_out = rgb_out[0]
    elif orig_dim == 3:
        rgb_out = numpy.reshape(rgb_out, orig_shape)

    return rgb_out * 2.0 - 1.0 if signed else rgb_out


def rgb2xyz(rgb, conversionMatrix=None, signed=False):
    """Convert linear RGB to CIE-XYZ.

    Parameters
    ----------
    rgb : array_like
        1-, 2-, 3-D vector of linear RGB color coordinates to convert. The last
        dimension should be length-3 in all cases specifying a single
        coordinate.
    conversionMatrix : array_like
        Conversion matrix to use, if `None`, the sRGB conversion matrix is used,
        assuming a D65 white point.
    signed : bool
        Input is using PsychoPy's signed color convention [-1:1]. If `False`,
        colors are assumed to range between [0:1].

    Returns
    -------
    ndarray
        Array CIE-XYZ color values with similar shape to `xyz` input.

    """
    rgb, orig_shape, orig_dim = unpackColors(rgb)

    if signed:
        rgb = (rgb / 2.0) + 1.0

    # XYZ -> sRGB conversion matrix, assumes D65 white point
    if conversionMatrix is None:
        conversionMatrix = numpy.asarray([
            [3.24096994, -1.53738318, -0.49861076],
            [-0.96924364, 1.8759675, 0.04155506],
            [0.05563008, -0.20397696, 1.05697151]])
    else:
        assert conversionMatrix.shape == (3, 3)

    rgb_out = rgb.dot(numpy.linalg.inv(conversionMatrix).T)

    # clip unrepresentable colors if requested
    if orig_dim == 1:
        rgb_out = rgb_out[0]
    elif orig_dim == 3:
        rgb_out = numpy.reshape(rgb_out, orig_shape)

    return rgb_out


def cielab2xyz(lab, whiteXYZ=ILLUMINANT_D65, exact=True):
    """Transform CIE L*a*b* (1976) color space coordinates to CIE-XYZ color
    space.

    Parameters
    ----------
    lab : tuple, list or ndarray
        1-, 2-, 3-D vector of CIE L*a*b* coordinates to convert. The last
        dimension should be length-3 in all cases specifying a single
        coordinate.
    whiteXYZ : tuple, list or ndarray
        1-D vector coordinate of the white point in CIE-XYZ color space. By
        default `ILLUMINANT_D65` is used.
    exact : bool
        Use exact values (or as close as possible) for some values defined
        with low-precision in the CIE standard. If `False`, the values specified
        by the CIE standard are used.

    Returns
    -------
    ndarray
        Array of CIE-XYZ colors coordinates with similar shape to `lab`.

    """
    lab, orig_shape, orig_dim = unpackColors(lab)

    # based off formulas from http://brucelindbloom.com
    L = lab[:, 0]  # lightness
    a = lab[:, 1] / 500.  # green (-)  <-> red (+)
    b = lab[:, 2] / 200.  # blue (-) <-> yellow (+)

    f = numpy.empty_like(lab)
    f[:, 1] = (L + 16) / 116.
    f[:, 0] = a + f[:, 1]
    f[:, 2] = f[:, 1] - b

    if exact:
        eta = 216 / 24389.
        kappa = 24389 / 27.
    else:
        eta = 0.008856
        kappa = 903.3

    xyz = numpy.zeros_like(lab)
    xyz[:, (0, 2)] = numpy.where(
        f[:, (0, 2)] ** 3 > eta,
        f[:, (0, 2)] ** 3,
        (116 * f[:, (0, 2)] - 16) / kappa)
    xyz[:, 1] = numpy.where(L > eta * kappa, f[:, 1] ** 3, L / kappa)
    xyz *= numpy.asarray(whiteXYZ)

    if orig_dim == 1:
        xyz = xyz[0]
    elif orig_dim == 3:
        xyz = numpy.reshape(xyz, orig_shape)

    return xyz


def xyz2cielab(xyz, whiteXYZ=ILLUMINANT_D65, exact=True):
    """Convert CIE-XYZ coordinates to CIE L*a*b* (1976).

    Parameters
    ----------
    lab : tuple, list or ndarray
        1-, 2-, 3-D vector of CIE-XYZ coordinates to convert. The last dimension
        should be length-3 in all cases specifying a single coordinate.
    whiteXYZ : tuple, list or ndarray
        1-D vector coordinate of the white point in CIE-XYZ color space. By
        default `ILLUMINANT_D65` is used.
    exact : bool
        Use exact values (or as close as possible) for `kappa` and `eta`. If
        `False`, the values specified by the CIE standard are used.

    Returns
    -------
    ndarray
        Array of CIE L*a*b* (1976) colors coordinates with similar shape to
        `xyz`.

    """
    xyz, orig_shape, orig_dim = unpackColors(xyz)

    lab = numpy.empty_like(xyz)
    r = xyz / numpy.asarray(whiteXYZ)

    if exact:
        # from http://brucelindbloom.com/index.html?Eqn_ChromAdapt.html
        eta = 216 / 24389.
        kappa = 24389 / 27.
    else:
        eta = 0.008856
        kappa = 903.3

    f = numpy.where(r > eta, numpy.cbrt(r), ((kappa * r) + 16) / 116.)

    lab[:, 0] = 116 * f[:, 1] - 16
    lab[:, 1] = 500 * (f[:, 0] - f[:, 1])
    lab[:, 2] = 200 * (f[:, 1] - f[:, 2])

    # make the output match the dimensions/shape of input
    if orig_dim == 1:
        lab = lab[0]
    elif orig_dim == 3:
        lab = numpy.reshape(lab, orig_shape)

    return lab


def cielch2xyz(lch, whiteXYZ=ILLUMINANT_D65):
    """Transform CIE L*C*h* coordinates to CIE-XYZ color space.

    Parameters
    ----------
    lch : tuple, list or ndarray
        1-, 2-, 3-D vector of CIE L*C*h* coordinates to convert. The last
        dimension should be length-3 in all cases specifying a single
        coordinate. The hue angle *h is expected in degrees.
    whiteXYZ : tuple, list or ndarray
        1-D vector coordinate of the white point in CIE-XYZ color space. By
        default `ILLUMINANT_D65` is used.

    Returns
    -------
    ndarray
        Array of CIE-XYZ colors coordinates with similar shape to `lch`.

    """
    lch, orig_shape, orig_dim = unpackColors(lch)

    # convert values to L*a*b*
    lab = numpy.empty(lch.shape, dtype=lch.dtype)
    lab[:, 0] = lch[:, 0]
    lab[:, 1] = lch[:, 1] * numpy.math.cos(numpy.math.radians(lch[:, 2]))
    lab[:, 2] = lch[:, 1] * numpy.math.sin(numpy.math.radians(lch[:, 2]))

    # convert to RGB using the CIE L*a*b* function
    xyz_out = cielab2xyz(lab, whiteXYZ=whiteXYZ)

    # make the output match the dimensions/shape of input
    if orig_dim == 1:
        xyz_out = xyz_out[0]
    elif orig_dim == 3:
        xyz_out = numpy.reshape(xyz_out, orig_shape)

    return xyz_out


def cielch2rgb(lch,
               whiteXYZ=None,
               conversionMatrix=None,
               transferFunc=None,
               clip=False,
               **kwargs):
    """Transform CIE L*C*h* coordinates to RGB tristimulus values.

    Parameters
    ----------
    lch : tuple, list or ndarray
        1-, 2-, 3-D vector of CIE L*C*h* coordinates to convert. The last
        dimension should be length-3 in all cases specifying a single
        coordinate. The hue angle *h is expected in degrees.
    whiteXYZ : tuple, list or ndarray
        1-D vector coordinate of the white point in CIE-XYZ color space. Must be
        the same white point needed by the conversion matrix. The default
        white point is D65 if None is specified, defined as X, Y, Z = 0.9505,
        1.0000, 1.0890
    conversionMatrix : tuple, list or ndarray
        3x3 conversion matrix to transform CIE-XYZ to RGB values. The default
        matrix is sRGB with a D65 white point if None is specified. Note that
        values must be gamma corrected to appear correctly according to the sRGB
        standard.
    transferFunc : pyfunc or None
        Signature of the transfer function to use. If None, values are kept as
        linear RGB (it's assumed your display is gamma corrected via the
        hardware CLUT). The TF must be appropriate for the conversion matrix
        supplied. Additional arguments to 'transferFunc' can be passed by
        specifying them as keyword arguments. Gamma functions that come with
        PsychoPy are 'srgbTF' and 'rec709TF', see their docs for more
        information.
    clip : boolean
        Make all output values representable by the display. However, colors
        outside of the display's gamut may not be valid!

    Returns
    -------
    ndarray
        array of RGB tristimulus values

    """
    lch, orig_shape, orig_dim = unpackColors(lch)

    # convert values to L*a*b*
    lab = numpy.empty(lch.shape, dtype=lch.dtype)
    lab[:, 0] = lch[:, 0]
    lab[:, 1] = lch[:, 1] * numpy.math.cos(numpy.math.radians(lch[:, 2]))
    lab[:, 2] = lch[:, 1] * numpy.math.sin(numpy.math.radians(lch[:, 2]))

    # convert to RGB using the CIE L*a*b* function
    rgb_out = cielab2rgb(lab,
                         whiteXYZ=whiteXYZ,
                         conversionMatrix=conversionMatrix,
                         transferFunc=transferFunc,
                         clip=clip,
                         **kwargs)

    # make the output match the dimensions/shape of input
    if orig_dim == 1:
        rgb_out = rgb_out[0]
    elif orig_dim == 3:
        rgb_out = numpy.reshape(rgb_out, orig_shape)

    return rgb_out  # don't do signed RGB conversion, done by cielab2rgb


def cielch2xyz(lch, whiteXYZ=ILLUMINANT_D65, exact=True):
    """Transform CIE L*C*h* coordinates to CIE-XYZ color space.

    Parameters
    ----------
    lch : tuple, list or ndarray
        1-, 2-, 3-D vector of CIE L*C*h* coordinates to convert. The last
        dimension should be length-3 in all cases specifying a single
        coordinate. The hue angle *h is expected in degrees.
    whiteXYZ : tuple, list or ndarray
        1-D vector coordinate of the white point in CIE-XYZ color space. By
        default `ILLUMINANT_D65` is used.
    exact : bool
        Use exact values (or as close as possible) for some values defined
        with low-precision in the CIE standard. If `False`, the values specified
        by the CIE standard are used.

    Returns
    -------
    ndarray
        Array of CIE-XYZ colors coordinates with similar shape to `lch`.

    """
    lch, orig_shape, orig_dim = unpackColors(lch)

    # convert values to L*a*b*
    lab = numpy.empty(lch.shape, dtype=lch.dtype)
    lab[:, 0] = lch[:, 0]
    lab[:, 1] = lch[:, 1] * numpy.math.cos(numpy.math.radians(lch[:, 2]))
    lab[:, 2] = lch[:, 1] * numpy.math.sin(numpy.math.radians(lch[:, 2]))

    # convert to RGB using the CIE L*a*b* function
    xyz_out = cielab2xyz(lab, whiteXYZ=whiteXYZ, exact=exact)

    # make the output match the dimensions/shape of input
    if orig_dim == 1:
        xyz_out = xyz_out[0]
    elif orig_dim == 3:
        xyz_out = numpy.reshape(xyz_out, orig_shape)

    return xyz_out


def xyz2xyY(xyz, discardY=False):
    """Convert CIE-XYZ to CIE-xyY (1931) chromaticity coordinates.

    Parameters
    ----------
    xyz : tuple, list or ndarray
        1-, 2-, 3-D vector of CIE-XYZ [X, Y, Z] coordinates to convert. The last
        dimension should be length-3 in all cases specifying a single
        coordinate.
    discardY : bool
        Remove the `Y` component of the converted coordinates.

    Returns
    -------
    ndarray
        Converted chromaticity coordinates with the same shape as `xyz`. If
        `discardY=True`, the last dimension will be truncated to 2.

    Examples
    --------
    Convert a standard illuminant (D65) to CIE-xyY::

        x, y, Y = cst.xyz2xyY(cst.ILLUMINANT_D65)

    """
    xyz, orig_shape, orig_dim = unpackColors(xyz)

    if not discardY:
        to_return = numpy.zeros_like(xyz)
    else:
        to_return = numpy.zeros((xyz.shape[0], 2,))

    sum_xyz = xyz[:, 0] + xyz[:, 1] + xyz[:, 2]

    to_return[:, 0] = xyz[:, 0] / sum_xyz
    to_return[:, 1] = xyz[:, 1] / sum_xyz

    if not discardY:
        to_return[:, 2] = xyz[:, 1]

    # make the output match the dimensions/shape of input
    if orig_dim == 1:
        to_return = to_return[0]
    elif orig_dim == 3:
        if not discardY:
            to_return = numpy.reshape(to_return, orig_shape)
        else:
            newShape = (orig_shape[0], orig_shape[1], 2)
            to_return = numpy.reshape(to_return, newShape)

    return to_return


def xyY2xyz(xyY):
    """Convert CIE-xyY (1931) to CIE-XYZ chromaticity coordinates.

    Parameters
    ----------
    xyY : tuple, list or ndarray
        1-, 2-, 3-D vector of CIE-xyY (1931) [x, y, Y] coordinates to convert.
        The last dimension should be length-3 in all cases specifying a single
        coordinate.
    discardY : bool
        Remove the `Y` component of the converted coordinates.

    Returns
    -------
    ndarray
        Converted chromaticity coordinates with the same shape as `xyY`.

    """
    xyY, orig_shape, orig_dim = unpackColors(xyY)

    to_return = numpy.empty_like(xyY)

    to_return[:, 0] = (xyY[:, 0] * xyY[:, 2]) / xyY[:, 1]
    to_return[:, 1] = xyY[:, 2]
    to_return[:, 2] = ((1 - xyY[:, 0] - xyY[:, 1]) * xyY[:, 2]) / xyY[:, 1]

    # make the output match the dimensions/shape of input
    if orig_dim == 1:
        to_return = to_return[0]
    elif orig_dim == 3:
        to_return = numpy.reshape(to_return, orig_shape)

    return to_return


def chromaTransform(xyz, srcWhiteXYZ, dstWhiteXYZ, method='bfd'):
    """Change the illuminant (white point) of a CIE-XYZ color using a chromatic
    adaptation transform.

    This offers a faster method for changing the white-point of extant color
    coordinates than recomputing them, however the results are somewhat less
    accurate.

    Parameters
    ----------
    xyz : tuple, list or ndarray
        1-, 2-, 3-D vector of CIE-XYZ [X, Y, Z] coordinates to convert. The last
        dimension should be length-3 in all cases specifying a single
        coordinate.
    srcWhiteXYZ : array_like
        CIE-XYZ color coordinates [X, Y, Z] of the white point used by `xyz`
        colors. If `None`, a standard D65 illuminant is used.
    dstWhiteXYZ : array_like
        CIE-XYZ color coordinates [X, Y, Z] of the white point to transform
        colors to.
    method : str
        Adaptation method to use. Options are 'scale', 'bfd' (Bradford), and
        'vk' (von Kries). The default is 'bfd'.

    Returns
    -------
    ndarray
        Transformed colors in CIE-XYZ color space.

    Notes
    -----
    * When converting to RGB after chromatic adaptation, you may want to clip
      the values to ensure they are representable on the display.

    Examples
    --------
    Apply chromatic adaptation to an image loaded from a file::

        # open with PIL
        im = Image.open("my_image.jpg")

        # convert to a NumPy array with values between 0 and 1
        im = np.array(im, dtype="uint8") / 255.0

        # convert to XYZ, note that you may want to apply the inverse of gamma
        im = cst.rgb2xyz(data)

        # Specify the illuminant present in the image and the one you want to
        # adapt to.
        im = cst.chromaTransform(im, cst.ILLUMINANT_D50, cst.ILLUMINANT_D65)

        # convert back to RGB, apply gamma if needed
        im = cst.xyz2rgb(im)

        # convert to 8-bit bitmap with color values between 0 and 255
        im = np.array(im * 255.0, dtype='uint8')
        # Note that you can also create an ImageStim with the resulting image,
        # or save it to a file.

    """
    xyz, orig_shape, orig_dim = unpackColors(xyz)

    srcXYZ = numpy.asarray(srcWhiteXYZ)
    dstXYZ = numpy.asarray(dstWhiteXYZ)

    if method == 'bfd':
        srcRGB = srcXYZ.dot(_BRADFORD_CRM.T)
        dstRGB = dstXYZ.dot(_BRADFORD_CRM.T)
        mCAT = numpy.matmul(
            _BRADFORD_CRM_INV,
            numpy.matmul(numpy.diagflat(dstRGB / srcRGB), _BRADFORD_CRM))
    elif method == 'vk':
        srcRGB = srcXYZ.dot(_VONKRIES_CRM.T)
        dstRGB = dstXYZ.dot(_VONKRIES_CRM.T)
        mCAT = numpy.matmul(
            _VONKRIES_CRM_INV,
            numpy.matmul(numpy.diagflat(dstRGB / srcRGB), _VONKRIES_CRM))
    elif method == 'scale':
        mCAT = numpy.diagflat(dstXYZ / srcXYZ)
    else:
        raise ValueError("Invalid value for `method`. Valid methods are 'bfd', "
                         "'vk', and 'scale'.")

    # apply the transformation
    xyz_array = xyz.dot(mCAT.T)

    # restore color array to original shape
    if orig_dim == 1:
        xyz_array = xyz_array[0]
    elif orig_dim == 3:
        xyz_array = numpy.reshape(xyz_array, orig_shape)

    return xyz_array


def gammaTransform(rgb, gamma=2.2, inverse=False, signed=False):
    """Apply a gamma transformation to linear RGB values.

    Parameters
    ----------
    rgb : tuple, list or ndarray of floats
        Nx3 or NxNx3 array of linear RGB values, last dim must be size == 3
        specifying RGB values.
    inverse : bool
        If True, the reverse transfer function will convert non-linear RGB to
        linear RGB.
    signed : bool
        Output colors in the range of [-1:1] instead of [0:1].

    Returns
    -------
    ndarray
        Array of transformed colors with same shape as input.

    """
    rgb, orig_shape, orig_dim = unpackColors(rgb)

    if not inverse:
        rgb_array = numpy.power(rgb, 1. / gamma)
    else:
        rgb_array = numpy.power(rgb, gamma)

    # restore color array to original shape
    if orig_dim == 1:
        rgb_array = rgb_array[0]
    elif orig_dim == 3:
        rgb_array = numpy.reshape(rgb_array, orig_shape)

    return rgb_array * 2.0 - 1.0 if signed else rgb_array


def srgbTransform(rgb, inverse=False, signed=False):
    """Apply the sRGB transfer function to linear RGB values.

    Input values must have been transformed using a conversion matrix derived
    from sRGB primaries relative to D65 as per the sRGB standard.

    Parameters
    ----------
    rgb : tuple, list or ndarray of floats
        Nx3 or NxNx3 array of linear RGB values, last dim must be size == 3
        specifying RGB values.
    inverse : bool
        If True, the reverse transfer function will convert sRGB -> linear RGB.
    signed : bool
        Output colors in the range of [-1:1] instead of [0:1].

    Returns
    -------
    ndarray
        Array of transformed colors with same shape as input.

    """
    rgb, orig_shape, orig_dim = unpackColors(rgb)

    # apply the sRGB TF
    if not inverse:
        # applies the sRGB transfer function (linear RGB -> sRGB)
        to_return = numpy.where(
            rgb <= 0.0031308,
            rgb * 12.92,
            (1.0 + 0.055) * rgb ** (1.0 / 2.4) - 0.055)
    else:
        # do the inverse (sRGB -> linear RGB)
        to_return = numpy.where(
            rgb <= 0.04045,
            rgb / 12.92,
            ((rgb + 0.055) / 1.055) ** 2.4)

    if orig_dim == 1:
        to_return = to_return[0]
    elif orig_dim == 3:
        to_return = numpy.reshape(to_return, orig_shape)

    return to_return * 2.0 - 1.0 if signed else to_return


def createConversionMatrix(rxy, gxy, bxy, wxy, inverse=False):
    """Construct a conversion matrix to convert CIE-XYZ coordinates to RGB
    primaries or vice versa.

    Returns a matrix to convert CIE-XYZ (1931) tristimulus values to linear RGB
    given CIE-xy (1931) primaries and white point. By default, the returned
    matrix transforms CIE-XYZ to linear RGB coordinates. Use `inverse=True` to
    get the inverse transformation.

    You can obtain the appropriate chromaticity coordinates of the display's
    phosphor 'guns' by measuring them with a spectrophotometer.

    The routines here are based on methods found at:
        http://www.ryanjuckett.com/programming/rgb-color-space-conversion/

    Parameters
    ----------
    rxy : tuple, list or ndarray
        Chromaticity coordinate (CIE-xy 1931) of the 'red' gun.
    gxy : tuple, list or ndarray
        Chromaticity coordinate (CIE-xy 1931) of the 'green' gun.
    bxy : tuple, list or ndarray
        Chromaticity coordinate (CIE-xy 1931) of the 'blue' gun.
    wxy : tuple, list or ndarray
        Chromaticity coordinate (CIE-xy 1931) of the white point.
    inverse : bool
        Return the inverse transform RGB to XYZ.

    Returns
    -------
    ndarray
        3x3 conversion matrix.

    """
    mat_xy = numpy.zeros((3, 3,))
    mat_xy[:2, 0] = rxy
    mat_xy[:2, 1] = gxy
    mat_xy[:2, 2] = bxy
    mat_xy[2, :] = 1.0 - (mat_xy[0, :] + mat_xy[1, :])

    wp = 1.0 / wxy[1] * numpy.array(
        [wxy[0], wxy[1], 1.0 - (wxy[0] + wxy[1])], dtype=float)

    m = numpy.matmul(mat_xy, numpy.diagflat(wp.dot(numpy.linalg.inv(mat_xy).T)))

    if not inverse:
        m = numpy.linalg.inv(m)

    return m


def dkl2rgb(dkl, conversionMatrix=None):
    """Convert from DKL color space (Derrington, Krauskopf & Lennie) to RGB.

    Requires a conversion matrix, which will be generated from generic
    Sony Trinitron phosphors if not supplied (note that this will not be
    an accurate representation of the color space unless you supply a
    conversion matrix).

    usage::

        rgb(Nx3) = dkl2rgb(dkl_Nx3(el,az,radius), conversionMatrix)
        rgb(NxNx3) = dkl2rgb(dkl_NxNx3(el,az,radius), conversionMatrix)

    """
    if conversionMatrix is None:
        conversionMatrix = numpy.asarray([
            # (note that dkl has to be in cartesian coords first!)
            # LUMIN    %L-M    %L+M-S
            [1.0000, 1.0000, -0.1462],  # R
            [1.0000, -0.3900, 0.2094],  # G
            [1.0000, 0.0180, -1.0000]])  # B
        logging.warning('This monitor has not been color-calibrated. '
                        'Using default DKL conversion matrix.')

    if len(dkl.shape) == 3:
        dkl_NxNx3 = dkl
        # convert a 2D (image) of Spherical DKL colours to RGB space
        origShape = dkl_NxNx3.shape  # remember for later
        NxN = origShape[0] * origShape[1]  # find nPixels
        dkl = numpy.reshape(dkl_NxNx3, [NxN, 3])  # make Nx3
        rgb = dkl2rgb(dkl, conversionMatrix)  # convert
        return numpy.reshape(rgb, origShape)  # reshape and return

    else:
        dkl_Nx3 = dkl
        # its easier to use in the other orientation!
        dkl_3xN = numpy.transpose(dkl_Nx3)
        if numpy.size(dkl_3xN) == 3:
            RG, BY, LUM = sph2cart(dkl_3xN[0],
                                   dkl_3xN[1],
                                   dkl_3xN[2])
        else:
            RG, BY, LUM = sph2cart(dkl_3xN[0, :],
                                   dkl_3xN[1, :],
                                   dkl_3xN[2, :])
        dkl_cartesian = numpy.asarray([LUM, RG, BY])
        rgb = numpy.dot(conversionMatrix, dkl_cartesian)

        # return in the shape we received it:
        return numpy.transpose(rgb)


def dklCart2rgb(LUM, LM, S, conversionMatrix=None):
    """Like dkl2rgb except that it uses cartesian coords (LM,S,LUM)
    rather than spherical coords for DKL (elev, azim, contr).

    NB: this may return rgb values >1 or <-1
    """
    NxNx3 = list(LUM.shape)
    NxNx3.append(3)
    dkl_cartesian = numpy.asarray(
        [LUM.reshape([-1]), LM.reshape([-1]), S.reshape([-1])])

    if conversionMatrix is None:
        conversionMatrix = numpy.asarray([
            # (note that dkl has to be in cartesian coords first!)
            # LUMIN    %L-M    %L+M-S
            [1.0000, 1.0000, -0.1462],  # R
            [1.0000, -0.3900, 0.2094],  # G
            [1.0000, 0.0180, -1.0000]])  # B
    rgb = numpy.dot(conversionMatrix, dkl_cartesian)
    return numpy.reshape(numpy.transpose(rgb), NxNx3)


def hsv2rgb(hsv_Nx3):
    """Convert from HSV color space to RGB gun values.

    usage::

        rgb_Nx3 = hsv2rgb(hsv_Nx3)

    Note that in some uses of HSV space the Hue component is given in
    radians or cycles (range 0:1]). In this version H is given in
    degrees (0:360).

    Also note that the RGB output ranges -1:1, in keeping with other
    PsychoPy functions.
    """
    # based on method in
    # http://en.wikipedia.org/wiki/HSL_and_HSV#Converting_to_RGB

    hsv_Nx3 = numpy.asarray(hsv_Nx3, dtype=float)
    # we expect a 2D array so convert there if needed
    origShape = hsv_Nx3.shape
    hsv_Nx3 = hsv_Nx3.reshape([-1, 3])

    H_ = old_div((hsv_Nx3[:, 0] % 360), 60.0)  # this is H' in the wikipedia version
    # multiply H and V to give chroma (color intensity)
    C = hsv_Nx3[:, 1] * hsv_Nx3[:, 2]
    X = C * (1 - abs(H_ % 2 - 1))

    # rgb starts
    rgb = hsv_Nx3 * 0  # only need to change things that are no longer zero
    II = (0 <= H_) * (H_ < 1)
    rgb[II, 0] = C[II]
    rgb[II, 1] = X[II]
    II = (1 <= H_) * (H_ < 2)
    rgb[II, 0] = X[II]
    rgb[II, 1] = C[II]
    II = (2 <= H_) * (H_ < 3)
    rgb[II, 1] = C[II]
    rgb[II, 2] = X[II]
    II = (3 <= H_) * (H_ < 4)
    rgb[II, 1] = X[II]
    rgb[II, 2] = C[II]
    II = (4 <= H_) * (H_ < 5)
    rgb[II, 0] = X[II]
    rgb[II, 2] = C[II]
    II = (5 <= H_) * (H_ < 6)
    rgb[II, 0] = C[II]
    rgb[II, 2] = X[II]
    m = (hsv_Nx3[:, 2] - C)
    rgb += m.reshape([len(m), 1])  # V-C is sometimes called m
    return rgb.reshape(origShape) * 2 - 1


def lms2rgb(lms_Nx3, conversionMatrix=None):
    """Convert from cone space (Long, Medium, Short) to RGB.

    Requires a conversion matrix, which will be generated from generic
    Sony Trinitron phosphors if not supplied (note that you will not get
    an accurate representation of the color space unless you supply a
    conversion matrix)

    usage::

        rgb_Nx3 = lms2rgb(dkl_Nx3(el,az,radius), conversionMatrix)

    """

    # its easier to use in the other orientation!
    lms_3xN = numpy.transpose(lms_Nx3)

    if conversionMatrix is None:
        cones_to_rgb = numpy.asarray([
            # L        M        S
            [4.97068857, -4.14354132, 0.17285275],  # R
            [-0.90913894, 2.15671326, -0.24757432],  # G
            [-0.03976551, -0.14253782, 1.18230333]])  # B

        logging.warning('This monitor has not been color-calibrated. '
                        'Using default LMS conversion matrix.')
    else:
        cones_to_rgb = conversionMatrix

    rgb = numpy.dot(cones_to_rgb, lms_3xN)
    return numpy.transpose(rgb)  # return in the shape we received it


def rgb2dklCart(picture, conversionMatrix=None):
    """Convert an RGB image into Cartesian DKL space.
    """
    # Turn the picture into an array so we can do maths
    picture = numpy.array(picture)
    # Find the original dimensions of the picture
    origShape = picture.shape

    # this is the inversion of the dkl2rgb conversion matrix
    if conversionMatrix is None:
        conversionMatrix = numpy.asarray([
            # LUMIN->    %L-M->        L+M-S
            [0.25145542, 0.64933633, 0.09920825],
            [0.78737943, -0.55586618, -0.23151325],
            [0.26562825, 0.63933074, -0.90495899]])
        logging.warning('This monitor has not been color-calibrated. '
                        'Using default DKL conversion matrix.')
    else:
        conversionMatrix = numpy.linalg.inv(conversionMatrix)

    # Reshape the picture so that it can multiplied by the conversion matrix
    red = picture[:, :, 0]
    green = picture[:, :, 1]
    blue = picture[:, :, 2]

    dkl = numpy.asarray([red.reshape([-1]),
                         green.reshape([-1]),
                         blue.reshape([-1])])

    # Multiply the picture by the conversion matrix
    dkl = numpy.dot(conversionMatrix, dkl)

    # Reshape the picture so that it's back to it's original shape
    dklPicture = numpy.reshape(numpy.transpose(dkl), origShape)
    return dklPicture


def rgb2lms(rgb_Nx3, conversionMatrix=None):
    """Convert from RGB to cone space (LMS).

    Requires a conversion matrix, which will be generated from generic
    Sony Trinitron phosphors if not supplied (note that you will not get
    an accurate representation of the color space unless you supply a
    conversion matrix)

    usage::

        lms_Nx3 = rgb2lms(rgb_Nx3(el,az,radius), conversionMatrix)

    """

    # its easier to use in the other orientation!
    rgb_3xN = numpy.transpose(rgb_Nx3)

    if conversionMatrix is None:
        cones_to_rgb = numpy.asarray([
            # L        M        S
            [4.97068857, -4.14354132, 0.17285275],  # R
            [-0.90913894, 2.15671326, -0.24757432],  # G
            [-0.03976551, -0.14253782, 1.18230333]])  # B

        logging.warning('This monitor has not been color-calibrated. '
                        'Using default LMS conversion matrix.')
    else:
        cones_to_rgb = conversionMatrix
    rgb_to_cones = numpy.linalg.inv(cones_to_rgb)

    lms = numpy.dot(rgb_to_cones, rgb_3xN)
    return numpy.transpose(lms)  # return in the shape we received it

