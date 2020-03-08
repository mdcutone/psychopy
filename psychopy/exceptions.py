#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

"""Functions and classes for handling exceptions."""

import sys
import traceback


class DependencyError(Exception):
    """The user requested something that won't be possible because
    of a dependency error (e.g. audiolib that isn't available)
    """
    pass


class SoundFormatError(Exception):
    """The user tried to create two streams (diff sample rates) on a machine
    that won't allow that
    """
    pass


class NoUserError(Exception):
    pass


class ConnectionError(Exception):
    pass


class NoGitError(DependencyError):
    pass


class ExceptionHook(object):
    """Exception hook object. Can be used as a context to envelop code with a
    custom exception hook, returning to the previous hook upon exiting or
    encountering an exception.

    You can check if a context exited prematurely using the value of the
    `success` property on the context object outside of the `with` block.

    """
    def __init__(self, hook):
        """
        Parameters
        ----------
        hook : callable
            Function to set as the exception hook with signature similar to
            `sys.__excepthook__`.

        """
        if not callable(hook):
            raise TypeError("`hook` must be callable.")

        self.exceptionHook = hook
        self._prevExceptionHook = None
        self.success = None

    def __call__(self, exc_type, exc_val, exc_tb):
        self.exceptionHook(exc_type, exc_val, exc_tb)

    def __enter__(self):
        self.success = False
        self._prevExceptionHook = getExceptionHook()
        setExceptionHook(self.exceptionHook)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        caughtException = exc_type is not None and issubclass(
            exc_type, BaseException)
        self.success = not caughtException
        setExceptionHook(self._prevExceptionHook)

        return caughtException


class suppress(object):
    """Context for suppressing errors.

    Errors that occur within this context will be caught and suppressed if
    desired. The context will exit immediately upon encountering an error and
    the program will continue executing as normal. You should be specific about
    which errors can safely be suppressed depending on the requirements of the
    application. Avoid using `suppress` as a catch-all for errors unless the
    routine in the context must be fully executed successfully and a fallback
    behaviour is defined. This provides similar functionality to that of
    `contextlib.suppress` but also supports Py2.

    Use `suppress` for cases where handling all possible exceptions within a
    routine is infeasible, but the effects of some exceptions can be safely
    ignored or recovered from with a fallback routine. You can check if a
    previously created context completed successfully by accessing the `success`
    attribute outside the `with` block (see Examples). Note that one should
    assert that pre- and post-conditions on objects outside the context
    manipulated from within it remain invariant if the context exits on an
    exception to prevent side-effects from an incomplete execution of the
    routine. Good practice would be to assign values to temporary variables
    inside the `with` block and write their values to external variables only if
    the context exits on a success condition.

    Examples
    --------
    Suppress an exception (ValueError) and recover/fallback from error::

        myList = ['this', 'is', 'an', 'example']
        with suppress(ValueError) as getIndexRoutine:
            idx = myList.index('blah')  # will fail

        if not getIndexRoutine.success:
            # run fallback code here, just give an index of -1
            idx = -1

    Note the above example can achieve the same result with a `try`-`except`
    block. However, consider the case where a bunch of other calls are made to
    functions across multiple modules. Catching an dealing with all possible
    exceptions that may occur can be difficult.

    """
    def __init__(self, excTypes=BaseException, silent=True):
        """
        Parameters
        ----------
        excTypes : object
            Exception or list of exceptions to suppress within the context. Will
            suppress any errors which are subclasses of those given. Default is
            `BaseException` which will result in all errors being suppressed.
        silent : bool
            Print the exception to stdout if `False`.

        """
        if not isinstance(excTypes, (list, tuple,)):
            excTypes = (excTypes,)

        self._excTypes = excTypes
        self.silent = silent
        self.success = None

    def __enter__(self):
        self.success = False
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        caughtException = exc_type is not None and any(
            [issubclass(exc_type, exc) for exc in self._excTypes])

        if caughtException and not self.silent:
            # this can be changed to log the error instead of print it
            traceback.print_exception(exc_type, exc_val, exc_tb)

        self.success = not caughtException

        return caughtException


class catch(object):
    """Context for catching specific errors.

    This is the opposite of :class:`suppress` where certain exceptions that
    occur within the context will halt the application. All other errors will
    be suppressed. Use this in cases where a certain type or subclass of an
    exception being raised would be unsafe for the program to continue.

    Even if the specified exceptions are not caught, any other exception will
    still cause the context block to exit. You can check if a context was fully
    executed by checking the value of the `success` property of the `catch`
    object after the `with` block (see Examples below).

    Examples
    --------
    Catch an exception (OSError)::

        with catch(OSError) as doSomethingRoutine:
            os_function()  # if this fails it raises an OSError, halts program
            do_something()  # raises any other error, just exits context

        if not doSomethingRoutine.success:
            # fallback for errors other than OSError occurring

    """
    def __init__(self, excTypes=BaseException, silent=False):
        """
        Parameters
        ----------
        excTypes : object
            Exception or list of exceptions to catch within the context. Will
            raise errors which are subclasses of those given, all others will
            be ignored. Default is `BaseException` which will result in all
            errors being caught.
        silent : bool
            Print the exception to stdout if `False`.

        """
        if not isinstance(excTypes, (list, tuple,)):
            excTypes = (excTypes,)

        self._excTypes = excTypes
        self.success = None
        self.silent = silent

    def __enter__(self):
        self.success = False
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.success = exc_type is None

        if not self.success:
            if not self.silent and \
                    any([issubclass(exc_type, exc) for exc in self._excTypes]):
                traceback.print_exception(exc_type, exc_val, exc_tb)
                sys.exit(1)

        return not self.success


def setExceptionHook(excepthook):
    """Set the exception hook to a function. This function will be called
    every time Python encounters an exception. You can use this to apply
    custom error handling (eg. write the error to a file instead of printing
    it).

    Parameters
    ----------
    excepthook : object or ExceptionHook
        Callable object with a similar signature to `sys.excepthook` or
        `ExceptionHook`.

    """
    if not callable(excepthook) or isinstance(excepthook, ExceptionHook):
        raise TypeError("Exception hook must be callable or `ExceptionHook`.")

    sys.excepthook = excepthook


def getExceptionHook():
    """Get a reference to the current exception hook.

    Returns
    -------
    callable
        Exception hook.

    """
    return sys.excepthook


def resetExceptionHook():
    """Return to using the default Python exception hook."""
    sys.excepthook = sys.__excepthook__
