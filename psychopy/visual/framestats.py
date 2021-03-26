#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Classes and functions for assessing frame timing performance.
"""

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2021 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

__all__ = [
    'WindowPerfStats',
    'FramePerfStats'
]
import numpy as np
import collections
import psychopy.logging as logging


class FramePerfStats(object):
    """Class for storing and producing frame statistics.

    This object stores data and computes frame performance statistics that can
    be used for diagnosing timing problems and assessing performance in general.

    Parameters
    ----------
    frameIndex : float
        Frame index these stats are referring to (`int`). Increments every time
        `flip()` is called. Valid performance stats will have a frame index
        equal to or greater than 0.
    droppedFrameCount : float
        Number of frames dropped since the start of the application (`int`).

    """
    __slots__ = [
        '_frameIndex',
        '_droppedFrameCount',
        '_absFrameStartTime',
        '_absFlipStartTime',
        '_absVSyncTime',
        '_absFlipEndTime'
    ]

    def __init__(self,
                 frameIndex=-1,
                 droppedFrameCount=0,
                 absFrameStartTime=0.0,
                 absFlipStartTime=0.0,
                 absVSyncTime=0.0,
                 absFlipEndTime=0.0):

        self.frameIndex = frameIndex
        self.droppedFrameCount = droppedFrameCount
        self.absFrameStartTime = absFrameStartTime
        self.absFlipStartTime = absFlipStartTime
        self.absFlipEndTime = absFlipEndTime
        self.absVSyncTime = absVSyncTime

    @property
    def frameIndex(self):
        """Frame index these stats are referring to (`int`). Increments every
        time `flip()` is called."""
        return self._frameIndex

    @frameIndex.setter
    def frameIndex(self, value):
        self._frameIndex = value

    @property
    def droppedFrameCount(self):
        """Number of frames dropped since the start of the application (`int`).
        """
        return self._droppedFrameCount

    @droppedFrameCount.setter
    def droppedFrameCount(self, value):
        self._droppedFrameCount = value

    @property
    def absFrameStartTime(self):
        """Absolute time that the frame began (`float`)."""
        return self._absFrameStartTime

    @absFrameStartTime.setter
    def absFrameStartTime(self, value):
        self._absFrameStartTime = value

    @property
    def absFlipStartTime(self):
        """Absolute flip that the frame began (`float`)."""
        return self._absFlipStartTime

    @absFlipStartTime.setter
    def absFlipStartTime(self, value):
        self._absFlipStartTime = value

    @property
    def absVSyncTime(self):
        """Absolute time of the vertical retrace (`float`)."""
        return self._absVSyncTime

    @absVSyncTime.setter
    def absVSyncTime(self, value):
        self._absVSyncTime = value

    @property
    def absFlipEndTime(self):
        """Absolute time that the frame began (`float`)."""
        return self._absFlipEndTime

    @absFlipEndTime.setter
    def absFlipEndTime(self, value):
        self._absFlipEndTime = value

    @property
    def userElapsedTime(self):
        """Time elapsed between calls of `flip()`."""
        return self._absFlipStartTime - self._absFrameStartTime

    @property
    def flipElapsedTime(self):
        """Time elapsed between calls of `flip()`."""
        return self._absFlipEndTime - self._absFlipStartTime

    @property
    def frameElapsedTime(self):
        """Time elapsed between calls of `flip()`."""
        return self._absFlipEndTime - self._absFrameStartTime

    @property
    def flipToVsyncElapsedTime(self):
        """Time elapsed in seconds since `flip()` was called and vertical
        retrace occurred (`float`).
        """
        return self._absVSyncTime - self._absFlipStartTime

    @property
    def userHeadroom(self):
        """Headroom that was available to the user this frame (`float`)."""
        return self.flipElapsedTime / self.frameElapsedTime

    @property
    def frameRate(self):
        """Estimated frame rate based on total elapsed frame time (`float`)."""
        return 1.0 / self.frameElapsedTime


NULL_FRAME_PERF_STATS = FramePerfStats(frameIndex=-1)


class WindowPerfStats(object):
    """Container class for window performance stats.

    Usually one of these objects is associated with a Window. Users usually will
    not create instances of this class themselves.

    """
    def __init__(self, maxFrameStats=512, nominalRefreshRate=None,
                 smoothSamples=16):
        self._maxFrameStats = int(maxFrameStats)
        self._framePerfStats = None  # deque, created later when clear is called

        # keep track of the current frame index
        self._currentFrameIndex = None  # set later to 0

        # time stamps at critical events needed to generate perf stats
        self._absReadyTime = 0.0
        self._absFlipStartTime = 0.0
        self._absSwapFinishedTime = 0.0
        self._absFlipEndTime = 0.0

        # clock to use
        self._defaultClock = logging.defaultClock

        # stats about the refresh rate
        self._nominalRefreshRate = nominalRefreshRate

        # incremented after a frame is dropped, set later
        self._droppedFrameCount = None

        # number of values to buffer for smoothing headroom and FPS values
        self._smoothSamples = int(smoothSamples)
        self._frameStatBuffer = None

        self.clear()  # allocate buffers and setup

    def markSwapFinished(self):
        """Call after the GPU is done swapping buffers. Corresponds closely to
        the time of the vertical retrace."""
        self._absSwapFinishedTime = self._defaultClock.getTime()

    def markFlipStart(self):
        """Call at the beginning of the `flip` call."""
        self._absFlipStartTime = self._defaultClock.getTime()

    def markFlipFinished(self):
        """Call this at the end of the flip function.

        Returns
        -------
        float
            Current time in seconds taken form the default clock.

        """
        self._absFlipEndTime = self._defaultClock.getTime()

        # deal with the case that flip hasn't been called yet
        if self.frameIndex > -1:
            lastFrameTime = self._framePerfStats[0].absFlipEndTime
        else:
            lastFrameTime = self._absReadyTime

        # create a new frame stats object
        frameStats = FramePerfStats(
            frameIndex=self._currentFrameIndex,
            droppedFrameCount=self._droppedFrameCount,
            absFrameStartTime=lastFrameTime,
            absFlipStartTime=self._absFlipStartTime,
            absVSyncTime=self._absSwapFinishedTime,
            absFlipEndTime=self._absFlipEndTime)

        # add the new frame stats object
        self._framePerfStats.appendleft(frameStats)

        # add data to the buffer for smoothing
        self._frameStatBuffer[self.frameIndex % 16, 0] = \
            frameStats.frameElapsedTime
        self._frameStatBuffer[self.frameIndex % 16, 1] = frameStats.userHeadroom

        self._currentFrameIndex += 1  # increment the current frame index
        return self._absFlipEndTime

    @property
    def frameIndex(self):
        """The current frame index (`int`).
        """
        return self._framePerfStats[0].frameIndex

    @property
    def droppedFrameCount(self):
        """Most recent number of frames dropped (`int`)."""
        return self._framePerfStats[0].droppedFrameCount

    @property
    def lastFrameStat(self):
        """Most recent (complete) frame stat object (`FramePerfStats`). The
        frame index of this item will be `frameIndex - 1`.
        """
        return self._framePerfStats[0]

    @property
    def smoothSamples(self):
        """Number of samples to smooth framerate and headroom calculations
        (`int`)."""
        return self._smoothSamples

    @smoothSamples.setter
    def smoothSamples(self, value):
        self._smoothSamples = int(value)

        # allocate new array
        self._frameStatBuffer = np.empty(
            (self._smoothSamples, 2), dtype=np.float32)
        self._frameStatBuffer[:] = np.nan

    def summarize(self, what='userElapsedTime', count=None):
        """Compute summary statistics for performance stats contained by this
        object.

        Parameters
        ----------
        what : str
            Name of attribute to summarize (e.g., 'userElapsedTime').
        count : int or None
            Number of stats to use for generating summary statistics. If
            specified the last `count` frame stats will be used.

        Returns
        -------
        tuple
            mean, standard deviation, minimum, maximum

        """
        if count is not None:
            numStats = len(self._framePerfStats)
            count = count if count <= numStats else numStats
            frameStats = [self._framePerfStats[i] for i in range(count)]
        else:
            frameStats = self._framePerfStats

        vals = np.asarray([getattr(v, what) for v in frameStats])

        return vals.mean(), vals.std(), vals.min(), vals.max()

    def getFrameRate(self):
        """Get the framerate.

        Computes the framerate based by averaging the total time between calls
        of flip for the last 16 frames.

        Returns
        -------
        float
            Frame rate in Hertz (Hz).

        """
        if self._currentFrameIndex >= self._smoothSamples:
            return 1. / self._frameStatBuffer[:, 0].mean()

        return 1. / np.nanmean(self._frameStatBuffer[:, 0])

    def getHeadroom(self):
        """Compute the headroom available last frame.

        This indicates the proportion of processing time each frame that is
        available to the user after factoring in overhead incurred by PsychoPy's
        `flip()` call. The lower the number, the higher the chances are of
        dropping frames.

        Returns
        -------
        float
            Frame headroom.

        """
        if self._currentFrameIndex >= self._smoothSamples:
            return self._frameStatBuffer[:, 1].mean()

        return np.nanmean(self._frameStatBuffer[:, 1])

    def clear(self):
        """Clear all summary statistics.
        """
        self._currentFrameIndex = 0
        self._droppedFrameCount = 0
        self._framePerfStats = collections.deque([], maxlen=self._maxFrameStats)
        self._frameStatBuffer = np.empty(
            (self._smoothSamples, 2), dtype=np.float32)
        self._frameStatBuffer[:] = np.nan
        self._framePerfStats.appendleft(NULL_FRAME_PERF_STATS)

    def saveFrameIntervals(self, filepath):
        """Save frame data to a CSV file.

        Dumps the following fields of all the buffered `FramePerfStats` objects
        to a comma-separated values (CSV) file:

            - frameIndex
            - absFrameStartTime
            - absFlipStartTime
            - absFlipEndTime
            - absVSyncTime
            - frameElapsedTime
            - flipElapsedTime

        Data for each frame is stored as a row in the file. Do not call this
        function during any time sensitive operations.

        Parameters
        ----------
        filepath : str
            File name including path.

        """
        headerFields = (
            'frameIndex', 'absFrameStartTime', 'absFlipStartTime',
            'absFlipEndTime', 'absVSyncTime', 'frameElapsedTime',
            'flipElapsedTime', 'frameRate', 'headRoom')
        headerText = ",".join(headerFields) + '\n'

        with open(filepath, 'a') as f:
            f.write(headerText)  # write the header
            for stat in reversed(self._framePerfStats):
                if stat is NULL_FRAME_PERF_STATS:
                    continue  # ignore "dummy" frame data

                valuesToWrite = (
                    stat.frameIndex,
                    stat.absFrameStartTime,
                    stat.absFlipStartTime,
                    stat.absFlipEndTime,
                    stat.absVSyncTime,
                    stat.frameElapsedTime,
                    stat.flipElapsedTime,
                    stat.frameRate,
                    stat.userHeadroom
                )
                newLine = ",".join([str(v) for v in valuesToWrite]) + '\n'
                f.write(newLine)


# dummy objects used as sentinels and for testing
NULL_WINDOW_PREF_STATS = WindowPerfStats(maxFrameStats=1)

if __name__ == "__main__":
    pass
