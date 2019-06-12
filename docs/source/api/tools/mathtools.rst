
:mod:`psychopy.tools.mathtools`
----------------------------------------

Assorted math functions for working with vectors, matrices, and
quaternions. These functions are intended to provide basic support for common
mathematical operations associated with displaying stimuli (e.g. animation,
posing, rendering, etc.)

Data Types
~~~~~~~~~~

Sub-routines used by functions here will perform arithmetic using 64-bit
floating-point precision unless otherwise specified via the `dtype` argument.
If a `dtype` is specified, input arguments will be coerced to match that type
and all floating-point arithmetic with use the precision of the type. If input
arrays have the same type as `dtype`, they will automatically pass-through
without being recast as a different type. As a performance consideration, all
input arguments should have matching types and `dtype` set accordingly.

Most functions have an `out` argument, where one can specify an array to write
values to. The value of `dtype` is ignored if `out` is provided, and all input
arrays will be converted to match the dtype of `out` (if not already).

Optimization and Performance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Most functions listed here are very fast, however they are optimized to work on
arrays of values (vectorization). Calling functions repeatedly (for instance
within a loop), should be avoided as the CPU overhead associated with each
function call (not to mention the loop itself) can be considerable.


.. automodule:: psychopy.tools.mathtools
.. currentmodule:: psychopy.tools.mathtools

.. autosummary::

    normalize
    reflect
    orthogonalize
    lerp
    slerp
    multQuat
    invertQuat
    applyQuat
    quatToAxisAngle
    quatFromAxisAngle
    matrixFromQuat
    scaleMatrix
    rotationMatrix
    translationMatrix
    concatenate
    applyMatrix
    poseToMatrix

Function details
~~~~~~~~~~~~~~~~

.. autofunction:: normalize
.. autofunction:: reflect
.. autofunction:: orthogonalize
.. autofunction:: lerp
.. autofunction:: slerp
.. autofunction:: multQuat
.. autofunction:: invertQuat
.. autofunction:: applyQuat
.. autofunction:: quatToAxisAngle
.. autofunction:: quatFromAxisAngle
.. autofunction:: matrixFromQuat
.. autofunction:: scaleMatrix
.. autofunction:: rotationMatrix
.. autofunction:: translationMatrix
.. autofunction:: concatenate
.. autofunction:: applyMatrix
.. autofunction:: poseToMatrix
