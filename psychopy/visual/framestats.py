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

    Parameters
    ----------
    win : :class:`~psychopy.visual.window.Window`
        Window associated with this class.
    maxFrameStats : int
        Number of frames statistics to keep.
    monitorFrameRate : float or None
        Target frame rate of the display in Hertz (Hz). If set, calling
        `initialize()` will not attempt to measure the framerate.
    smoothSamples : int
        Number of samples to compute a rolling average of frame rate and
        headroom.

    """
    def __init__(self, win, maxFrameStats=512, monitorFrameRate=None,
                 smoothSamples=16):
        self.win = win
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
        self._monitorFrameRate = monitorFrameRate
        self._monitorFramePeriod = 1.0
        self._refreshThreshold = 1.0

        # incremented after a frame is dropped, set later
        self._droppedFrameCount = 0
        self._maxDroppedFramesToWarn = 5

        # number of values to buffer for smoothing headroom and FPS values
        self._smoothSamples = int(smoothSamples)
        self._frameStatBuffer = None

        self.clear()  # allocate buffers and setup
        self._isInitialized = False

    def initialize(self, nIdentical=10, nMaxFrames=100, nWarmUpFrames=10,
                   threshold=1):
        """Initialize the profiler.

        This determines the framerate of the display and whether a stable
        framerate is achievable. Must be called prior to giving control of the
        Window to the user, but after the Window has been spawned.

        Parameters
        ----------
        nIdentical : int, optional
            The number of consecutive frames that will be evaluated.
            Higher --> greater precision. Lower --> faster.
        nMaxFrames : int, optional
            The maximum number of frames to wait for a matching set of
            nIdentical.
        nWarmUpFrames : int, optional
            The number of frames to display before starting the test
            (this is in place to allow the system to settle after opening
            the `Window` for the first time.
        threshold : int, optional
            The threshold for the std deviation (in ms) before the set
            are considered a match.

        Returns
        -------
        float or None
            Frame rate (FPS) in seconds. If there is no such sequence of
            identical frames a warning is logged and `None` will be returned.

        """
        # create a samples buffer
        totalFrameTimes = np.empty((nIdentical,), dtype=np.float32)
        totalFrameTimes.fill(np.nan)

        threshold /= 1000.  # threshold in seconds

        # do warm up, simply call `flip()` the given number of times
        nFrame = 0
        while nFrame < nWarmUpFrames:
            self.win.flip()
            nFrame += 1

        if self._monitorFrameRate is None:
            # start sampling
            for nFrame in range(nMaxFrames):
                self.win.flip()

                if nFrame < nIdentical:
                    continue

                # add last frame time to stats buffer for processing
                totalFrameTimes[nFrame % nIdentical] = \
                    self.lastFrameStat.frameElapsedTime

                # determine if the last bunch of frames vary less than threshold
                if totalFrameTimes.std() <= threshold:
                    self._monitorFramePeriod = totalFrameTimes.mean()
                    if self.win.autoLog:
                        msg = 'Screen{} actual frame rate measured at {:.2f}'
                        logging.debug(
                            msg.format(self.win.screen,
                                       self._monitorFramePeriod))
                    return

            # cannot determine a framerate
            logging.warning(
                "Couldn't measure a consistent frame rate.\n"
                "  - Is your graphics card set to sync to vertical blank?\n"
                "  - Are you running other processes on your computer?\n"
            )
        else:
            self._monitorFramePeriod = 1.0 / self._monitorFrameRate

        self._isInitialized = True

        return self._monitorFramePeriod

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
        deltaT = frameStats.frameElapsedTime
        self._frameStatBuffer[self.frameIndex % self._smoothSamples, :] = \
            (deltaT, frameStats.userHeadroom)

        # check if we dropped a frame
        if deltaT > self._refreshThreshold:
            self._droppedFrameCount += 1
            if self._maxDroppedFramesToWarn < self._droppedFrameCount:
                txt = 't of last frame was %.2fms (=1/%i)'
                msg = txt % (deltaT * 1000, 1 / deltaT)
                logging.warning(msg, t=self._absFlipEndTime)
            elif self._maxDroppedFramesToWarn == self._droppedFrameCount:
                logging.warning(
                    "Multiple dropped frames have occurred - I'll stop "
                    "bothering you about them!")

        self._currentFrameIndex += 1  # increment the current frame index
        return self._absFlipEndTime

    @property
    def monitorFrameRate(self):
        """Frame rate of the monitor presenting the window (`float`).
        """
        return 1.0 / self._monitorFrameRate

    @property
    def monitorFramePeriod(self):
        """Nominal time per frame in seconds (`float`).
        """
        return self._monitorFramePeriod

    @monitorFramePeriod.setter
    def monitorFramePeriod(self, value):
        self._monitorFramePeriod = value

    @property
    def refreshThreshold(self):
        """Threshold for determining whether a frame has been dropped (`float`).
        """
        return self._monitorFramePeriod * 1.2

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


if __name__ == "__main__":
    pass
