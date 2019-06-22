#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Various math functions for working with vectors, matrices, and quaternions.

"""

# Part of the PsychoPy library
# Copyright (C) 2018 Jonathan Peirce
# Distributed under the terms of the GNU General Public License (GPL).

__all__ = ['normalize', 'lerp', 'slerp', 'multQuat', 'quatFromAxisAngle',
           'matrixFromQuat', 'scaleMatrix', 'rotationMatrix',
           'translationMatrix', 'concatenate', 'applyMatrix', 'invertQuat',
           'quatToAxisAngle', 'poseToMatrix', 'applyQuat', 'orthogonalize',
           'reflect', 'cross', 'distance']

import numpy as np
import functools


# ------------------------------------------------------------------------------
# Vector Operations
#

def normalize(v, out=None, dtype=None):
    """Normalize a vector or quaternion.

    v : ndarray
        Vector to normalize, can be Nx2, Nx3, or Nx4. If a 2D array is
        specified, rows are treated as separate vectors.
    out : ndarray, optional
        Optional output array. Must have same shape as `v`.
    dtype : dtype or str, optional
        Data type for arrays, can either be 'float32' or 'float64'. If `None` is
        specified, the data type is inferred by `out`. If `out` is not provided,
        the default is 'float64'.

    Returns
    -------
    ndarray
        Normalized vector `v`.

    Notes
    -----
    * If the vector is degenerate (length is zero), a vector of all zeros is
      returned.

    Examples
    --------
    Normalize a vector::

        v = [1., 2., 3., 4.]
        vn = normalize(v)

    The `normalize` function is vectorized. It's considerably faster to
    normalize large arrays of vectors than to call `normalize` separately for
    each one::

        v = np.random.uniform(-1.0, 1.0, (1000, 4,))  # 1000 length 4 vectors
        vn = np.zeros((1000, 4))  # place to write values
        normalize(v, out=vn)  # very fast!

        # don't do this!
        for i in range(1000):
            vn[i, :] = normalize(v[i, :])

    """
    if out is None:
        dtype = np.float64 if dtype is None else np.dtype(dtype).type
        toReturn = np.array(v, dtype=dtype)
    else:
        toReturn = out

    v2d = np.atleast_2d(toReturn)  # 2d view of array
    norm = np.linalg.norm(v2d, axis=1)
    norm[norm == 0.0] = np.NaN  # make sure if length==0 division succeeds
    v2d /= norm[:, np.newaxis]
    np.nan_to_num(v2d, copy=False)  # fix NaNs

    return toReturn


def orthogonalize(v, n, out=None, dtype=None):
    """Orthogonalize a vector relative to a normal vector.

    This function ensures that `v` is perpendicular (or orthogonal) to `n`.

    Parameters
    ----------
    v : array_like
        Vector to orthogonalize, can be Nx2, Nx3, or Nx4. If a 2D array is
        specified, rows are treated as separate vectors.
    n : array_like
        Normal vector, must have same shape as `v`.
    out : ndarray, optional
        Optional output array. Must have same shape as `v` and `n`.
    dtype : dtype or str, optional
        Data type for arrays, can either be 'float32' or 'float64'. If `None` is
        specified, the data type is inferred by `out`. If `out` is not provided,
        the default is 'float64'.

    Returns
    -------
    ndarray
        Orthogonalized vector `v` relative to normal vector `n`.

    Warnings
    --------
    If `v` and `n` are the same, the direction of the perpendicular vector is
    indeterminate. The resulting vector is degenerate (all zeros).

    """
    if out is None:
        dtype = np.float64 if dtype is None else np.dtype(dtype).type
    else:
        dtype = np.dtype(out.dtype).type

    v = np.asarray(v, dtype=dtype)
    n = np.asarray(n, dtype=dtype)

    if out is None:
        toReturn = np.zeros_like(v, dtype=dtype)
    else:
        toReturn = out
        toReturn.fill(0.0)

    v, n, vr = np.atleast_2d(v, n, toReturn)

    vr[:, :] = v
    vr[:, :] -= n * np.sum(n * v, axis=1)[:, np.newaxis]  # dot product
    normalize(vr, out=vr)

    return toReturn


def reflect(v, n, out=None, dtype=None):
    """Reflection of a vector.

    Get the reflection of `v` relative to normal `n`.

    Parameters
    ----------
    v : array_like
        Vector to reflect, can be Nx2, Nx3, or Nx4. If a 2D array is specified,
        rows are treated as separate vectors.
    n : array_like
        Normal vector, must have same shape as `v`.
    out : ndarray, optional
        Optional output array. Must have same shape as `v` and `n`.
    dtype : dtype or str, optional
        Data type for arrays, can either be 'float32' or 'float64'. If `None` is
        specified, the data type is inferred by `out`. If `out` is not provided,
        the default is 'float64'.

    Returns
    -------
    ndarray
        Reflected vector `v` off normal `n`.

    """
    # based off https://github.com/glfw/glfw/blob/master/deps/linmath.h
    if out is None:
        dtype = np.float64 if dtype is None else np.dtype(dtype).type
    else:
        dtype = np.dtype(out.dtype).type

    v = np.asarray(v, dtype=dtype)
    n = np.asarray(n, dtype=dtype)

    if out is None:
        toReturn = np.zeros_like(v, dtype=dtype)
    else:
        toReturn = out
        toReturn.fill(0.0)

    v, n, vr = np.atleast_2d(v, n, toReturn)

    u = dtype(2.0)
    vr[:, :] = v
    vr[:, :] -= (u * np.sum(n * v, axis=1))[:, np.newaxis] * n

    return toReturn


def cross(v0, v1, out=None, dtype=None):
    """Cross product of two 3D vectors.

    Parameters
    ----------
    v0, v1 : array_like
        Vector(s) in form [x, y, z] or [x, y, z, 1].
    out : ndarray, optional
        Optional output array with same shape as `v0` and `v1`. If `v0` and `v1`
        are 2-D, this array can be either Nx3 or Nx4 but, must have the same
        number of rows.
    dtype : dtype or str, optional
        Data type for arrays, can either be 'float32' or 'float64'. If `None` is
        specified, the data type is inferred by `out`. If `out` is not provided,
        the default is 'float64'.

    Returns
    -------
    ndarray
        Cross product of `v0` and `v1`.

    Notes
    -----
    * If input vectors are 4D, the last value of cross product vectors is always
      set to 1.
    * If input vectors `v0` and `v1` are Nx3 and `out` is Nx4, the cross product
      is computed and the last column of `out` is filled with 1.

    """
    if out is None:
        dtype = np.float64 if dtype is None else np.dtype(dtype).type
    else:
        dtype = np.dtype(out.dtype).type

    v0 = np.asarray(v0, dtype=dtype)
    v1 = np.asarray(v1, dtype=dtype)

    assert v0.shape == v1.shape
    if out is None:
        toReturn = np.zeros(v0.shape, dtype=dtype)
    else:
        toReturn = out
        toReturn.fill(0.0)

    v0, v1, vr = np.atleast_2d(v0, v1, toReturn)

    vr[:, 0] = v0[:, 1] * v1[:, 2]
    vr[:, 1] = v0[:, 2] * v1[:, 0]
    vr[:, 2] = v0[:, 0] * v1[:, 1]
    vr[:, 0] -= v0[:, 2] * v1[:, 1]
    vr[:, 1] -= v0[:, 0] * v1[:, 2]
    vr[:, 2] -= v0[:, 1] * v1[:, 0]

    if vr.shape[1] == 4:  # if 4D, fill the last component with zeros
        vr[:, 3] = dtype(1.0)

    return toReturn


def lerp(v0, v1, t, out=None, dtype=None):
    """Linear interpolation (LERP) between two vectors/coordinates.

    Parameters
    ----------
    v0 : array_like
        Initial vector/coordinate. Can be 2D where each row is a point.
    v1 : array_like
        Final vector/coordinate. Must be the same shape as `v0`.
    t : float
        Interpolation weight factor [0, 1].
    out : ndarray, optional
        Optional output array. Must have the same `shape` and `dtype` as `v0`.
    dtype : dtype or str, optional
        Data type for arrays, can either be 'float32' or 'float64'. If `None` is
        specified, the data type is inferred by `out`. If `out` is not provided,
        the default is 'float64'.

    Returns
    -------
    ndarray
        Vector  at `t` with same shape as `v0` and `v1`.

    Examples
    --------
    Find the coordinate of the midpoint between two vectors::

        u = [0., 0., 0.]
        v = [0., 0., 1.]
        midpoint = lerp(u, v, 0.5)  # 0.5 to interpolate half-way between points

    """
    if out is None:
        dtype = np.float64 if dtype is None else np.dtype(dtype).type
    else:
        dtype = np.dtype(out.dtype).type

    t = dtype(t)
    t0 = dtype(1.0) - t
    v0 = np.asarray(v0, dtype=dtype)
    v1 = np.asarray(v1, dtype=dtype)

    toReturn = np.zeros_like(v0, dtype=dtype) if out is None else out
    toReturn.fill(0.0)

    v0, v1, vr = np.atleast_2d(v0, v1, toReturn)

    vr[:, :] = v0 * t0
    vr[:, :] += v1 * t

    return toReturn


def distance(v0, v1, out=None, dtype=None):
    """Get the distance between vectors/coordinates.

    Parameters
    ----------
    v0, v1 : array_like
        Vectors to compute the distance between.
    out : ndarray, optional
        Optional output array. Must have same number of rows as `v0` and `v1`.
    dtype : dtype or str, optional
        Data type for arrays, can either be 'float32' or 'float64'. If `None` is
        specified, the data type is inferred by `out`. If `out` is not provided,
        the default is 'float64'.

    Returns
    -------
    ndarray
        Distance between vectors `v0` and `v1`.

    """
    if out is None:
        dtype = np.float64 if dtype is None else np.dtype(dtype).type
    else:
        dtype = np.dtype(out.dtype).type

    v0, v1 = np.atleast_2d(np.asarray(v0, dtype=dtype),
                           np.asarray(v1, dtype=dtype))

    dist = np.zeros((v0.shape[0],), dtype=dtype) if out is None else out
    dist.fill(0.0)

    # compute distance
    dist[:] = np.sqrt(np.sum(np.square(v1 - v0), axis=1))

    return dist


# ------------------------------------------------------------------------------
# Quaternion Operations
#

def slerp(q0, q1, t, shortest=True, out=None, dtype=None):
    """Spherical linear interpolation (SLERP) between two quaternions.

    The behaviour of this function depends on the types of arguments:

    * If `q0` and `q1` are both 1-D and `t` is scalar, the interpolation at `t`
      is returned.
    * If `q0` and `q1` are both 2-D Nx4 arrays and `t` is scalar, an Nx4 array
      is returned with each row containing the interpolation at `t` for each
      quaternion pair at matching row indices in `q0` and `q1`.

    Parameters
    ----------
    q0 : array_like
        Initial quaternion in form [x, y, z, w] where w is real and x, y, z
        are imaginary components.
    q1 : array_like
        Final quaternion in form [x, y, z, w] where w is real and x, y, z
        are imaginary components.
    t : float
        Interpolation weight factor within interval 0.0 and 1.0.
    shortest : bool, optional
        Ensure interpolation occurs along the shortest arc along the 4-D
        hypersphere (default is `True`).
    out : ndarray, optional
        Optional output array. Must be same shape as the expected returned array
        if `out` was not specified.
    dtype : dtype or str, optional
        Data type for arrays, can either be 'float32' or 'float64'. If `None` is
        specified, the data type is inferred by `out`. If `out` is not provided,
        the default is 'float64'.

    Returns
    -------
    ndarray
        Quaternion [x, y, z, w] at `t`.

    Examples
    --------
    Interpolate between two orientations::

        q0 = quatFromAxisAngle([0., 0., -1.], 90.0, degrees=True)
        q1 = quatFromAxisAngle([0., 0., -1.], -90.0, degrees=True)
        # halfway between 90 and -90 is 0.0 or quaternion [0. 0. 0. 1.]
        qr = slerp(q0, q1, 0.5)

    """
    # Implementation based on code found here:
    #  https://en.wikipedia.org/wiki/Slerp
    #
    if out is None:
        dtype = np.float64 if dtype is None else np.dtype(dtype).type
    else:
        dtype = np.dtype(out.dtype).type

    q0 = normalize(q0, dtype=dtype)
    q1 = normalize(q1, dtype=dtype)
    assert q0.shape == q1.shape

    toReturn = np.zeros(q0.shape, dtype=dtype) if out is None else out
    toReturn.fill(0.0)
    t = dtype(t)
    q0, q1, qr = np.atleast_2d(q0, q1, toReturn)

    dot = np.clip(np.sum(q0 * q1, axis=1), -1.0, 1.0)
    if shortest:
        dot[dot < 0.0] *= -1.0
        q1[dot < 0.0] *= -1.0

    theta0 = np.arccos(dot)
    theta = theta0 * t
    sinTheta = np.sin(theta)
    s1 = sinTheta / np.sin(theta0)
    s0 = np.cos(theta[:, np.newaxis]) - \
         dot[:, np.newaxis] * s1[:, np.newaxis]
    qr[:, :] = q0 * s0
    qr[:, :] += q1 * s1[:, np.newaxis]
    qr[:, :] += 0.0

    return toReturn


def quatToAxisAngle(q, degrees=False, dtype=None):
    """Convert a quaternion to `axis` and `angle` representation.

    This allows you to use quaternions to set the orientation of stimuli that
    have an `ori` property.

    Parameters
    ----------
    q : tuple, list or ndarray of float
        Quaternion in form [x, y, z, w] where w is real and x, y, z
        are imaginary components.
    degrees : bool
        Indicate `angle` is to be returned in degrees, otherwise `angle` will be
        returned in radians.
    dtype : dtype or str, optional
        Data type for arrays, can either be 'float32' or 'float64'. If `None` is
        specified, the data type is inferred by `out`. If `out` is not provided,
        the default is 'float64'.

    Returns
    -------
    tuple
        Axis and angle of quaternion in form ([ax, ay, az], angle). If `degrees`
        is `True`, the angle returned is in degrees, radians if `False`.

    Examples
    --------
    Using a quaternion to rotate a stimulus each frame::

        # initial orientation, axis rotates in the Z direction
        qr = quatFromAxisAngle(0.0, [0., 0., -1.], degrees=True)
        # rotation per-frame, here it's 0.1 degrees per frame
        qf = quatFromAxisAngle(0.1, [0., 0., -1.], degrees=True)

        # ---- within main experiment loop ----
        # myStim is a GratingStim or anything with an 'ori' argument which
        # accepts angle in degrees
        qr = multQuat(qr, qf)  # cumulative rotation
        _, angle = quatToAxisAngle(qr)  # discard axis, only need angle
        myStim.ori = angle
        myStim.draw()

    """
    dtype = np.float64 if dtype is None else np.dtype(dtype).type
    q = normalize(q, dtype=dtype)  # returns ndarray
    v = np.sqrt(np.sum(np.square(q[:3])))
    axis = q[:3] / v
    angle = dtype(2.0) * np.arctan2(v, q[3])
    axis += 0.0

    return axis, np.degrees(angle) if degrees else angle


def quatFromAxisAngle(axis, angle, degrees=False, dtype=None):
    """Create a quaternion to represent a rotation about `axis` vector by
    `angle`.

    Parameters
    ----------
    axis : tuple, list or ndarray of float
        Axis of rotation [x, y, z].
    angle : float
        Rotation angle in radians (or degrees if `degrees` is `True`. Rotations
        are right-handed about the specified `axis`.
    degrees : bool
        Indicate `angle` is in degrees, otherwise `angle` will be treated as
        radians.
    dtype : dtype or str, optional
        Data type for arrays, can either be 'float32' or 'float64'. If `None` is
        specified, 'float64' is used.

    Returns
    -------
    ndarray
        Quaternion [x, y, z, w].

    Examples
    --------
    Create a quaternion from specified `axis` and `angle`::

        axis = [0., 0., -1.]  # rotate about -Z axis
        angle = 90.0  # angle in degrees
        ori = quatFromAxisAngle(axis, angle, degrees=True)  # using degrees!

    """
    dtype = np.float64 if dtype is None else np.dtype(dtype).type
    toReturn = np.zeros((4,), dtype=dtype)

    if degrees:
        halfRad = np.radians(angle, dtype=dtype) / dtype(2.0)
    else:
        halfRad = np.dtype(dtype).type(angle) / dtype(2.0)

    axis = normalize(axis, dtype=dtype)
    np.multiply(axis, np.sin(halfRad), out=toReturn[:3])
    toReturn[3] = np.cos(halfRad)
    toReturn += 0.0  # remove negative zeros

    return toReturn


def multQuat(q0, q1, out=None, dtype=None):
    """Multiply quaternion `q0` and `q1`.

    The orientation of the returned quaternion is the combination of the input
    quaternions.

    Parameters
    ----------
    q0, q1 : array_like
        Quaternions to multiply in form [x, y, z, w] where w is real and x, y, z
        are imaginary components. If 2D (Nx4) arrays are specified, quaternions
        are multiplied row-wise between each array.
    out : ndarray, optional
        Alternative array to write values. Must be have the same shape as `q0`
        and `q1`.
    dtype : dtype or str, optional
        Data type for arrays, can either be 'float32' or 'float64'. If `None` is
        specified, the data type is inferred by `out`. If `out` is not provided,
        the default is 'float64'.

    Returns
    -------
    ndarray
        Combined orientations of `q0` amd `q1`.

    Notes
    -----
    * Quaternions are normalized prior to multiplication.

    Examples
    --------
    Combine the orientations of two quaternions::

        a = quatFromAxisAngle([0., 0., -1.], 45.0, degrees=True)
        b = quatFromAxisAngle([0., 0., -1.], 90.0, degrees=True)
        c = multQuat(a, b)  # rotates 135 degrees about -Z axis

    """
    if out is None:
        dtype = np.float64 if dtype is None else np.dtype(dtype).type
    else:
        dtype = np.dtype(out.dtype).type

    q0 = normalize(q0, dtype=dtype)
    q1 = normalize(q1, dtype=dtype)
    assert q0.shape == q1.shape
    toReturn = np.zeros(q0.shape, dtype=dtype) if out is None else out
    toReturn.fill(0.0)  # clear array
    q0, q1, qr = np.atleast_2d(q0, q1, toReturn)

    # multiply quaternions for each row of the operand arrays
    qr[:, :3] = np.cross(q0[:, :3], q1[:, :3], axis=1)
    qr[:, :3] += q0[:, :3] * np.expand_dims(q1[:, 3], axis=1)
    qr[:, :3] += q1[:, :3] * np.expand_dims(q0[:, 3], axis=1)
    qr[:, 3] = q0[:, 3]
    qr[:, 3] *= q1[:, 3]
    qr[:, 3] -= np.sum(np.multiply(q0[:, :3], q1[:, :3]), axis=1)  # dot product
    qr += 0.0

    return toReturn


def invertQuat(q, out=None, dtype=None):
    """Get tht multiplicative inverse of a quaternion.

    This gives a quaternion which rotates in the opposite direction with equal
    magnitude. Multiplying a quaternion by its inverse returns an identity
    quaternion as both orientations cancel out.

    Parameters
    ----------
    q : ndarray, list, or tuple of float
        Quaternion to invert in form [x, y, z, w] where w is real and x, y, z
        are imaginary components. If `q` is 2D (Nx4), each row is treated as a
        separate quaternion and inverted.
    out : ndarray, optional
        Alternative array to write values. Must have the same shape as `q`.
    dtype : dtype or str, optional
        Data type for arrays, can either be 'float32' or 'float64'. If `None` is
        specified, the data type is inferred by `out`. If `out` is not provided,
        the default is 'float64'.

    Returns
    -------
    ndarray
        Inverse of quaternion `q`.

    Examples
    --------
    Show that multiplying a quaternion by its inverse returns an identity
    quaternion where [x=0, y=0, z=0, w=1]::

        angle = 90.0
        axis = [0., 0., -1.]
        q = quatFromAxisAngle(axis, angle, degrees=True)
        qinv = invertQuat(q)
        qr = multQuat(q, qinv)
        qi = np.array([0., 0., 0., 1.])  # identity quaternion
        print(np.allclose(qi, qr))   # True

    Notes
    -----
    * Quaternions are normalized prior to inverting.

    """
    if out is None:
        dtype = np.float64 if dtype is None else np.dtype(dtype).type
    else:
        dtype = np.dtype(out.dtype).type

    q = normalize(q, dtype=dtype)
    toReturn = np.zeros(q.shape, dtype=dtype) if out is None else out
    qn, qinv = np.atleast_2d(q, toReturn)  # 2d views

    # conjugate the quaternion
    qinv[:, :3] = -qn[:, :3]
    qinv[:, 3] = qn[:, 3]
    qinv /= np.sum(np.square(qn), axis=1)[:, np.newaxis]
    qinv += 0.0  # remove negative zeros

    return toReturn


def applyQuat(q, points, out=None, dtype=None):
    """Rotate points/coordinates using a quaternion.

    This is similar to using `applyMatrix` with a rotation matrix. However, it
    is computationally less intensive to use `applyQuat` if one only wishes to
    rotate points.

    Parameters
    ----------
    q : array_like
        Quaternion to invert in form [x, y, z, w] where w is real and x, y, z
        are imaginary components.
    points : array_like
        2D array of points/coordinates to transform, where each row is a single
        point. Only the x, y, and z components (the first three columns) are
        rotated. Additional columns are copied.
    out : ndarray, optional
        Optional output array to write values. Must be same `shape` and `dtype`
        as `points`.
    dtype : dtype or str, optional
        Data type for arrays, can either be 'float32' or 'float64'. If `None` is
        specified, the data type is inferred by `out`. If `out` is not
        provided, the default is 'float64'.

    Returns
    -------
    ndarray
        Transformed points.

    Examples
    --------
    Rotate points using a quaternion::

        points = [[1., 0., 0.], [0., -1., 0.]]
        quat = quatFromAxisAngle([0., 0., -1.], -90.0, degrees=True)
        pointsRotated = applyQuat(quat, points)
        # [[0. 1. 0.]
        #  [1. 0. 0.]]

    Show that you get the same result as a rotation matrix::

        axis = [0., 0., -1.]
        angle = -90.0
        rotMat = rotationMatrix(angle, axis)[:3, :3]  # rotation sub-matrix only
        rotQuat = quatFromAxisAngle(axis, angle, degrees=True)
        points = [[1., 0., 0.], [0., -1., 0.]]
        isClose = np.allclose(applyMatrix(rotMat, points),  # True
                              applyQuat(rotQuat, points))

    """
    # based on 'quat_mul_vec3' implementation from linmath.h
    if out is None:
        dtype = np.float64 if dtype is None else np.dtype(dtype).type
    else:
        assert points.shape == out.shape
        dtype = np.dtype(out.dtype).type

    points = np.asarray(points, dtype=dtype)
    qin = np.asarray(q, dtype=dtype)
    toReturn = np.zeros(points.shape, dtype=dtype) if out is None else out

    pin, pout = np.atleast_2d(points, toReturn)
    if qin.ndim == 1:  # tile if quaternion is 1D for broadcasting
        qin = np.tile(qin, (pin.shape[0], 1))

    pout[:, :] = pin[:, :]  # copy values into output array
    t = np.cross(qin[:, :3], pin[:, :3], axis=1)
    t *= dtype(2.0)
    u = np.cross(qin[:, :3], t, axis=1)
    t *= np.expand_dims(qin[:, 3], axis=1)
    pout[:, :3] += t
    pout[:, :3] += u
    pout += 0.0  # remove negative zeros
    # remove values very close to zero
    pout[np.abs(pout) <= np.finfo(dtype).eps] = 0.0

    return toReturn


# ------------------------------------------------------------------------------
# Matrix Operations
#

def matrixFromQuat(q, out=None, dtype=None):
    """Create a rotation matrix from a quaternion.

    Parameters
    ----------
    q : tuple, list or ndarray of float
        Quaternion to convert in form [x, y, z, w] where w is real and x, y, z
        are imaginary components.
    out : ndarray or None
        Alternative array to write values. Must be `shape` == (4,4,) and same
        `dtype` as the `dtype` argument.
    dtype : dtype or str, optional
        Data type for arrays, can either be 'float32' or 'float64'. If `None` is
        specified, the data type is inferred by `out`. If `out` is not provided,
        the default is 'float64'.

    Returns
    -------
    ndarray or None
        4x4 rotation matrix in row-major order.

    Examples
    --------
    Convert a quaternion to a rotation matrix::

        point = [0., 1., 0., 1.]  # 4-vector form [x, y, z, 1.0]
        ori = [0., 0., 0., 1.]
        rotMat = matrixFromQuat(ori)
        # rotate 'point' using matrix multiplication
        newPoint = np.matmul(rotMat.T, point)  # returns [-1., 0., 0., 1.]

    Rotate all points in an array (each row is a coordinate)::

        points = np.asarray([[0., 0., 0., 1.],
                             [0., 1., 0., 1.],
                             [1., 1., 0., 1.]])
        newPoints = points.dot(rotMat)

    Notes
    -----
    * Quaternions are normalized prior to conversion.

    """
    # based off implementations from
    # https://github.com/glfw/glfw/blob/master/deps/linmath.h
    if out is None:
        dtype = np.float64 if dtype is None else np.dtype(dtype).type
        R = np.zeros((4, 4,), dtype=dtype)
    else:
        dtype = np.dtype(out.dtype).type
        R = out
        R.fill(0.0)

    q = normalize(q, dtype=dtype)
    b, c, d, a = q[:]
    vsqr = np.square(q)

    u = dtype(2.0)
    R[0, 0] = vsqr[3] + vsqr[0] - vsqr[1] - vsqr[2]
    R[1, 0] = u * (b * c + a * d)
    R[2, 0] = u * (b * d - a * c)

    R[0, 1] = u * (b * c - a * d)
    R[1, 1] = vsqr[3] - vsqr[0] + vsqr[1] - vsqr[2]
    R[2, 1] = u * (c * d + a * b)

    R[0, 2] = u * (b * d + a * c)
    R[1, 2] = u * (c * d - a * b)
    R[2, 2] = vsqr[3] - vsqr[0] - vsqr[1] + vsqr[2]

    R[3, 3] = dtype(1.0)
    R[:, :] += 0.0  # remove negative zeros

    return R


def scaleMatrix(s, out=None, dtype=None):
    """Create a scaling matrix.

    The resulting matrix is the same as a generated by a `glScale` call.

    Parameters
    ----------
    s : array_like or float
        Scaling factor(s). If `s` is scalar (float), scaling will be uniform.
        Providing a vector of scaling values [sx, sy, sz] will result in an
        anisotropic scaling matrix if any of the values differ.
    out : ndarray, optional
        Optional output array.
    dtype : dtype or str, optional
        Data type for arrays, can either be 'float32' or 'float64'. If `None` is
        specified, the data type is inferred by `out`. If `out` is not provided,
        the default is 'float64'.

    Returns
    -------
    ndarray
        4x4 scaling matrix in row-major order.

    """
    # from glScale
    if out is None:
        dtype = np.float64 if dtype is None else np.dtype(dtype).type
        S = np.zeros((4, 4,), dtype=dtype)
    else:
        dtype = out.dtype
        S = out
        S.fill(0.0)

    if isinstance(s, (float, int,)):
        s = dtype(s)
        S[0, 0] = s
        S[1, 1] = s
        S[2, 2] = s
    else:
        S[0, 0] = dtype(s[0])
        S[1, 1] = dtype(s[1])
        S[2, 2] = dtype(s[2])

    S[3, 3] = 1.0

    return S


def rotationMatrix(angle, axis, out=None, dtype=None):
    """Create a rotation matrix.

    The resulting matrix will rotate points about `axis` by `angle`. The
    resulting matrix is similar to that produced by a `glRotate` call.

    Parameters
    ----------
    angle : float
        Rotation angle in degrees.
    axis : ndarray, list, or tuple of float
        Axis vector components.
    out : ndarray, optional
        Optional 4x4 output array. All computations will use the data type of
        this array.
    dtype : dtype or str, optional
        Data type for arrays, can either be 'float32' or 'float64'. If `None` is
        specified, the data type is inferred by `out`. If `out` is not provided,
        the default is 'float64'.

    Returns
    -------
    ndarray
        4x4 scaling matrix in row-major order. Will be the same array as `out`
        if specified, if not, a new array will be allocated.

    Notes
    -----
    * Vector `axis` is normalized before creating the matrix.

    """
    if out is None:
        dtype = np.float64 if dtype is None else np.dtype(dtype).type
        R = np.zeros((4, 4,), dtype=dtype)
    else:
        dtype = out.dtype
        R = out
        R.fill(0.0)

    axis = normalize(axis, dtype=dtype)
    angle = np.radians(angle, dtype=dtype)
    c = np.cos(angle, dtype=dtype)
    s = np.sin(angle, dtype=dtype)

    xs, ys, zs = axis * s
    x2, y2, z2 = np.square(axis)  # type inferred by input
    x, y, z = axis
    cd = dtype(1.0) - c

    R[0, 0] = x2 * cd + c
    R[0, 1] = x * y * cd - zs
    R[0, 2] = x * z * cd + ys

    R[1, 0] = y * x * cd + zs
    R[1, 1] = y2 * cd + c
    R[1, 2] = y * z * cd - xs

    R[2, 0] = x * z * cd - ys
    R[2, 1] = y * z * cd + xs
    R[2, 2] = z2 * cd + c

    R[3, 3] = dtype(1.0)
    R[:, :] += 0.0  # remove negative zeros

    return R


def translationMatrix(t, out=None, dtype=None):
    """Create a translation matrix.

    The resulting matrix is the same as generated by a `glTranslate` call.

    Parameters
    ----------
    t : ndarray, tuple, or list of float
        Translation vector [tx, ty, tz].
    out : ndarray, optional
        Optional 4x4 output array. All computations will use the data type of
        this array.
    dtype : dtype or str, optional
        Data type for arrays, can either be 'float32' or 'float64'. If `None` is
        specified, the data type is inferred by `out`. If `out` is not
        specified, the default is 'float64'.

    Returns
    -------
    ndarray
        4x4 translation matrix in row-major order. Will be the same array as
        `out` if specified, if not, a new array will be allocated.

    """
    if out is None:
        dtype = np.float64 if dtype is None else np.dtype(dtype).type
        T = np.identity(4, dtype=dtype)
    else:
        dtype = out.dtype
        T = out
        T.fill(0.0)
        np.fill_diagonal(T, 1.0)

    T[:3, 3] = np.asarray(t, dtype=dtype)

    return T


def concatenate(m, out=None, dtype=None):
    """Concatenate matrix transformations.

    Combine 4x4 transformation matrices into a single matrix. This is similar to
    what occurs when building a matrix stack in OpenGL using `glRotate`,
    `glTranslate`, and `glScale` calls. Matrices are multiplied together from
    right-to-left, or the last item to first. Note that changing the order of
    the input matrices changes the final result.

    The data types of input matrices are coerced to match that of `out` or
    `dtype` if `out` is `None`. For performance reasons, it is best that all
    arrays passed to this function should have matching data types.

    Parameters
    ----------
    m : list or tuple
        List of matrices to concatenate. All matrices must be 4x4.
    out : ndarray, optional
        Optional 4x4 output array.
    dtype : dtype or str, optional
        Data type for arrays, can either be 'float32' or 'float64'. If `None` is
        specified, the data type is inferred by `out`. If `out` is not provided,
        the default is 'float64'.

    Returns
    -------
    ndarray
        Concatenation of input matrices as a 4x4 matrix in row-major order.

    Examples
    --------
    Create an SRT (scale, rotate, and translate) matrix to convert model-space
    coordinates to world-space::

        S = scaleMatrix([2.0, 2.0, 2.0])  # scale model 2x
        R = rotationMatrix(-90., [0., 0., -1])  # rotate -90 about -Z axis
        T = translationMatrix([0., 0., -5.])  # translate point 5 units away
        SRT = concatenate([S, R, T])

        # transform a point in model-space coordinates to world-space
        pointModel = np.array([0., 1., 0., 1.])
        pointWorld = np.matmul(SRT, pointModel.T)  # point in WCS
        # ... or ...
        pointWorld = matrixApply(SRT, pointModel)

    Create a model-view matrix from a world-space pose represented by an
    orientation (quaternion) and position (vector). The resulting matrix will
    transform model-space coordinates to eye-space::

        # stimulus pose as quaternion and vector
        stimOri = quatFromAxisAngle([0., 0., -1.], -45.0)
        stimPos = [0., 1.5, -5.]

        # create model matrix
        R = matrixFromQuat(stimOri)
        T = translationMatrix(stimPos)
        M = concatenate(R, T)  # model matrix

        # create a view matrix, can also be represented as 'pos' and 'ori'
        eyePos = [0., 1.5, 0.]
        eyeFwd = [0., 0., -1.]
        eyeUp = [0., 1., 0.]
        V = lookAt(eyePos, eyeFwd, eyeUp)  # from viewtools

        # modelview matrix
        MV = concatenate([M, V])

    You can put the created matrix in the OpenGL matrix stack as shown below.
    Note that the matrix must have a 32-bit floating-point data type and needs
    to be loaded transposed.::

        GL.glMatrixMode(GL.GL_MODELVIEW)
        MV = np.asarray(MV, dtype='float32')  # must be 32-bit float!
        ptrMV = MV.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        GL.glLoadTransposeMatrixf(ptrMV)

    Furthermore, you can go from model-space to homogeneous clip-space by
    concatenating the projection, view, and model matrices::

        # compute projection matrix, functions here are from 'viewtools'
        screenWidth = 0.52
        screenAspect = w / h
        scrDistance = 0.55
        frustum = computeFrustum(screenWidth, screenAspect, scrDistance)
        P = perspectiveProjectionMatrix(*frustum)

        # multiply model-space points by MVP to convert them to clip-space
        MVP = concatenate(M, V, P)
        pointModel = np.array([0., 1., 0., 1.])
        pointClipSpace = np.matmul(MVP, pointModel.T)

    """
    if out is None:
        dtype = np.float64 if dtype is None else np.dtype(dtype).type
        toReturn = np.zeros((4, 4,), dtype=dtype)
    else:
        dtype = np.dtype(dtype).type
        toReturn = out
        toReturn.fill(0.0)

    toReturn[:, :] = functools.reduce(
        np.matmul, map(lambda x: np.asarray(x, dtype=dtype), reversed(m)))

    return toReturn


def applyMatrix(m, points, out=None, dtype=None):
    """Apply a transformation matrix over a 2D array of points.

    Parameters
    ----------
    m : array_like
        Transformation matrix.
    points : array_like
        2D array of points/coordinates to transform, where each row is a single
        point and the number of columns should match the dimensions of the
        matrix.
    out : ndarray, optional
        Optional output array to write values. Must be same `shape` and `dtype`
        as `points`.
    dtype : dtype or str, optional
        Data type for arrays, can either be 'float32' or 'float64'. If `None` is
        specified, the data type is inferred by `out`. If `out` is not
        specified, the default is 'float64'.

    Returns
    -------
    ndarray
        Transformed points.

    Examples
    --------
    Transform an array of points by some transformation matrix::

        S = scaleMatrix([5.0, 5.0, 5.0])  # scale 2x
        R = rotationMatrix(180., [0., 0., -1])  # rotate 180 degrees
        T = translationMatrix([0., 1.5, -3.])  # translate point up and away
        M = concatenate([S, R, T])  # create transform matrix

        # points to transform, must be 2D!
        points = np.array([[0., 1., 0., 1.], [-1., 0., 0., 1.]]) # [x, y, z, w]
        newPoints = applyMatrix(M, points)  # apply the transformation

    Extract the 3x3 rotation sub-matrix from a 4x4 matrix and apply it to
    points. Here the result in written to an already allocated array::

        points = np.array([[0., 1., 0.], [-1., 0., 0.]])  # [x, y, z]
        outPoints = np.zeros(points.shape)
        M = rotationMatrix(90., [1., 0., 0.])
        M3x3 = M[:3, :3]  # extract rotation groups from the 4x4 matrix
        # apply transformations, write to result to existing array
        applyMatrix(M3x3, points, out=outPoints)

    """
    if out is None:
        dtype = np.float64 if dtype is None else np.dtype(dtype).type
    else:
        dtype = np.dtype(out.dtype).type

    m = np.asarray(m, dtype=dtype)
    points = np.asarray(points, dtype=dtype)

    if out is None:
        toReturn = np.zeros_like(points, dtype=dtype)
    else:
        toReturn = out

    pout, points = np.atleast_2d(toReturn, points)

    np.dot(points, m.T, out=pout)
    pout[np.abs(pout) <= np.finfo(dtype).eps] = 0.0

    return toReturn


def poseToMatrix(pos, ori, out=None, dtype=None):
    """Convert a pose to a 4x4 transformation matrix.

    A pose is represented by a position coordinate `pos` and orientation
    quaternion `ori`.

    Parameters
    ----------
    pos : ndarray, tuple, or list of float
        Position vector [x, y, z].
    ori : tuple, list or ndarray of float
        Orientation quaternion in form [x, y, z, w] where w is real and x, y, z
        are imaginary components.
    out : ndarray, optional
        Optional output array for 4x4 matrix. All computations will use the data
        type of this array.
    dtype : dtype or str, optional
        Data type for arrays, can either be 'float32' or 'float64'. If `None` is
        specified, the data type is inferred by `out`. If `out` is not
        specified, the default is 'float64'.

    Returns
    -------
    ndarray
        4x4 transformation matrix.

    """
    if out is None:
        dtype = np.float64 if dtype is None else np.dtype(dtype).type
        toReturn = np.zeros((4, 4,), dtype=dtype)
    else:
        dtype = np.dtype(dtype).type
        toReturn = out

    transMat = translationMatrix(pos, dtype=dtype)
    rotMat = matrixFromQuat(ori, dtype=dtype)

    if out is not None:
        return np.matmul(rotMat, transMat, out=toReturn)

    return np.matmul(rotMat, transMat)


def transform(pos, ori, points, out=None, dtype=None):
    """Transform points using a position and orientation. Points are rotated
    then translated.

    Parameters
    ----------
    pos : array_like
        Position vector in form [x, y, z] or [x, y, z, 1].
    ori : array_like
        Orientation quaternion in form [x, y, z, w] where w is real and x, y, z
        are imaginary components.
    points : array_like
        Point(s) [x, y, z] to transform.
    out : ndarray, optional
        Optional output array for 4x4 matrix. All computations will use the data
        type of this array.
    dtype : dtype or str, optional
        Data type for arrays, can either be 'float32' or 'float64'. If `None` is
        specified, the data type is inferred by `out`. If `out` is not
        specified, the default is 'float64'.

    Returns
    -------
    ndarray
        Transformed points.

    Examples
    --------
    Transform points by a position coordinate and orientation quaternion::

        # pose
        ori = quatFromAxisAngle([0., 0., -1.], 90.0, degrees=True)
        pos = [0., 1.5, -3.]
        # points to transform
        points = np.array([[0., 1., 0., 1.], [-1., 0., 0., 1.]])  # [x, y, z, 1]
        outPoints = np.zeros_like(points)  # output array
        transform(pos, ori, points, out=outPoints)  # do the transformation

    You can get the same results as the previous example using a matrix by doing
    the following::

        R = rotationMatrix(90., [0., 0., -1])
        T = translationMatrix([0., 1.5, -3.])
        M = concatenate([R, T])
        applyMatrix(M, points, out=outPoints)

    Notes
    -----
    * In performance tests, `applyMatrix` is noticeably faster than `transform`
      for very large arrays.
    * If the input arrays for `points` or `pos` is Nx4, the last column is
      ignored.

    """
    if out is None:
        dtype = np.float64 if dtype is None else np.dtype(dtype).type
    else:
        dtype = np.dtype(dtype).type

    pos = np.asarray(pos, dtype=dtype)
    ori = np.asarray(ori, dtype=dtype)
    points = np.asarray(points, dtype=dtype)

    if out is None:
        toReturn = np.zeros_like(points, dtype=dtype)
    else:
        if out.shape != points.shape:
            raise ValueError(
                "Array 'out' and 'points' do not have matching shapes.")

        toReturn = out

    pout, points = np.atleast_2d(toReturn, points)  # create 2d views

    # apply rotation
    applyQuat(ori, points, out=pout)

    # apply translation
    pout[:, 0] += pos[0]
    pout[:, 1] += pos[1]
    pout[:, 2] += pos[2]

    return toReturn
