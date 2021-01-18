#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests to ensure the API for PsychoPy stimuli classes is stable.

These tests simply check if public properties and methods for stimuli classes
correctly handle values passed to them correctly. This ensures that if changes
are made to the underlying implementation within those classes, we can be
confident that users will not notice those changes. These tests also ensure that
class properties (setters/getters) that accept various data formats to specify
the same thing result in the same value being returned when accessed. For
instance, the `ColorMixin` allows the color `red` to be set in many ways::

    # all these are the same
    myStim.color = (1, -1, -1)  # tuple of ints
    myStim.color = [1., -1., -1.]  # list of floats
    myStim.color = '#FF0000'  # hex string
    myStim.color = numpy.array([1., -1., -1.])  # numpy array

However, when the `color` property is accessed it should always return
`array([1. -1. -1.])` regardless of what was specified above. This is what we're
looking for with these tests. No matter what format the data is being specified
as, what is stored is always in the same format.

Here we don't test routines for correctness (eg., colors are being correctly
computed), that should be done in separate tests suites.

"""

from __future__ import division

import pytest
from psychopy.visual.window import Window
from psychopy.visual.shape import ShapeStim
from psychopy.visual.rect import Rect
from psychopy.visual.circle import Circle

import numpy as np


@pytest.mark.StimuliClasses
class Test_StimuliClasses(object):
    """General test suite for stimuli classes.

    Creating tests for API stability involves the following:

        1. Instance a class you would like to test.
        2. For each attribute and method, check whether the default value has
           the correct type and value.
        3. If the attribute is a setter/getter, set the value and check if the
           return value has the correct type/value when accessed. Try this for
           all types the attribute accepts. Methods and functions can be tested
           to check if they return values with the appropriate type.

    A test should be successful if:

        1. The same value is returned regardless of the input type, as long as
           the input represents the same value (i.e. [1., 1.] and (1, 1) being
           passed to the `pos` attribute should always return `array([1. 1.])`
           when accessed). As a rule, methods and properties should always
           return values valid within a single domain (eg., integers, floats,
           etc.)
        2. The value being stored does not have the same identity as the input.
           This can lead to undefined behaviour if the object used as input is
           modified outside of the class attribute.

    """
    def setup_class(self):
        self.win = Window([128, 128], pos=[50, 50], allowGUI=False,
                          autoLog=False)

    def teardown_class(self):
        self.win.close()

    def test_stim_properties(self):
        """Test various stimuli class properties (setters/getters)."""

        testValues = {'pos': ([0.5, -0.25], np.array([0.5, -0.25])),
                      'ori': (45.6, 45.6),
                      'size': ([1.0, 0.5], np.array([1.0, 0.5])),
                      #'color': ((1., 1., 1.), np.array([1., 1., 1.])),
                      #'opacity': (0.5, 0.5),
                      #'contrast': (0.25, 0.25)
                      }

        for stimType in (ShapeStim, Rect, Circle,):
            stim = stimType(self.win,
                            pos=testValues['pos'][0],
                            size=testValues['size'][0],
                            ori=testValues['ori'][0],
                            units='height')

            # test setter/getters for various attributes associated with the class
            for attrName, vals in testValues.items():
                inputVal, outputVal = vals
                check_vector_set_and_get(stim, attrName, inputVal, outputVal)


def check_vector_set_and_get(_obj, _attr, inputVal, outVal=None):
    """Test a setter and getter property.

    This checks whether a setter/getter for a class is correctly storing and
    returning a value after the user sets it. This function raises errors if
    if a getter/setter behaves unexpectedly.

    Parameters
    ----------
    _obj : object
        Instance of the class whose attributes are being tested.
    _attr : str
        Name of the attribute to test.
    inputVal : array_like
        Value to set the attribute with.
    outVal : array_like, optional
        Expected value to be returned when the attribute is accessed. If `None`,
        the value of `inputVal` will be used.

    """
    expectedType = type(inputVal) if outVal is None else type(outVal)

    if hasattr(type(inputVal), '__iter__') and not isinstance(inputVal, str):
        # test for each valid data type the user may set an attribute with
        for inputType in (list, tuple, np.array):
            # set the data type for input
            vin = inputType(inputVal)
            setattr(_obj, _attr, vin)  # set class attribute
            # now check the stored value
            # return type check, always converted to ndarray
            try:
                assert isinstance(getattr(_obj, _attr), expectedType)
            except AssertionError:
                raise TypeError(
                    "Expected return type for `{}.{}` is `{}` got `{}` "
                    "instead.".format(
                        _obj.__class__.__name__, _attr,
                        expectedType.__name__,
                        type(getattr(_obj, _attr)).__name__))
            # return value check, see if it equals the expected value
            assert np.allclose(getattr(_obj, _attr), vin)
            # Make sure that the internal object does not reference the
            # object it was set to (bad).
            assert id(vin) != id(getattr(_obj, _attr))
    elif isinstance(inputVal, str):  # strings
        pass
    elif isinstance(inputVal, (float, int,)):  # numbers
        for inputType in (float, int,):
            vin = inputType(inputVal)
            setattr(_obj, _attr, vin)  # set class attribute
            try:
                assert isinstance(getattr(_obj, _attr), expectedType)
            except AssertionError:
                raise TypeError(
                    "Expected return type for `{}.{}` is `{}` got `{}` "
                    "instead.".format(
                        _obj.__class__.__name__, _attr,
                        expectedType.__name__,
                        type(getattr(_obj, _attr)).__name__))
