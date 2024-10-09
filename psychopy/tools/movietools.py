#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Classes and functions for working with movies in PsychoPy.
"""

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2024 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

__all__ = [
    'MovieFileWriter',
    'MovieFileReader',
    'closeAllMovieWriters',
    'addAudioToMovie',
    'MOVIE_READER_FFPYPLAYER',
    'MOVIE_WRITER_FFPYPLAYER',
    'MOVIE_READER_OPENCV',
    'MOVIE_WRITER_OPENCV',
    'MOVIE_WRITER_NULL',
    'VIDEO_RESOLUTIONS'
]

import os
import time
import threading
import queue
import atexit
import numpy as np
import psychopy.logging as logging
import sys

# constants for specifying encoders for the movie writer
MOVIE_WRITER_FFPYPLAYER = MOVIE_READER_FFPYPLAYER = u'ffpyplayer'
MOVIE_WRITER_OPENCV = MOVIE_READER_OPENCV = u'opencv'
MOVIE_WRITER_NULL = u'null'   # use prefs for default

# Common video resolutions in pixels (width, height). Users should be able to
# pass any of these strings to fields that require a video resolution. Setters
# should uppercase the string before comparing it to the keys in this dict.
VIDEO_RESOLUTIONS = {
    'VGA': (640, 480),
    'SVGA': (800, 600),
    'XGA': (1024, 768),
    'SXGA': (1280, 1024),
    'UXGA': (1600, 1200),
    'QXGA': (2048, 1536),
    'WVGA': (852, 480),
    'WXGA': (1280, 720),
    'WXGA+': (1440, 900),
    'WSXGA+': (1680, 1050),
    'WUXGA': (1920, 1200),
    'WQXGA': (2560, 1600),
    'WQHD': (2560, 1440),
    'WQXGA+': (3200, 1800),
    'UHD': (3840, 2160),
    '4K': (4096, 2160),
    '8K': (7680, 4320)
}

# Keep track of open movie writers here. This is used to close all movie writers
# when the main thread exits. Any waiting frames are flushed to the file before 
# the file is finalized. We identify movie writers by hashing the filename they 
# are presently writing to. 
_openMovieWriters = set()

# Keep track of movie readers here. This is used to close all movie readers
# when the main thread exits. We identify movie readers by hashing the filename
# they are presently reading from.
_openMovieReaders = set()


class MovieMetadata:
    """Class for storing metadata about a movie file.

    This class is used to store metadata about a movie file. This includes
    information about the video and audio tracks in the movie. Metadata is
    extracted from the movie file when the movie reader is opened.

    This class is not intended to be used directly by users. It is used
    internally by the `MovieFileReader` class to store metadata about the movie
    file being read.

    Parameters
    ----------
    filename : str
        The name (or path) of the movie file to extract metadata from.
    size : tuple
        The size of the movie in pixels (width, height).
    frameRate : float
        The frame rate of the movie in frames per second.
    duration : float
        The duration of the movie in seconds.
    
    """
    def __init__(self, filename, size, frameRate, duration, colorFormat):
        self._filename = filename
        self._size = size
        self._frameRate = frameRate
        self._duration = duration
        self._colorFormat = colorFormat

    def __repr__(self):
        return (
            f"MovieMetadata(filename={self.filename}, "
            f"size={self.size}, "
            f"frameRate={self.frameRate}, "
            f"duration={self.duration})")
        
    def __str__(self):
        return (
            f"MovieMetadata(filename={self.filename}, "
            f"size={self.size}, "
            f"frameRate={self.frameRate}, "
            f"duration={self.duration})")

    @property
    def filename(self):
        """The name (path) of the movie file (`str`).

        """
        return self._filename

    @property
    def size(self):
        """The size of the movie in pixels (`tuple`).

        """
        return self._size

    @property
    def frameRate(self):
        """The frame rate of the movie in frames per second (`float`).

        """
        return self._frameRate
    
    @property
    def duration(self):
        """The duration of the movie in seconds (`float`).

        """
        return self._duration

    @property
    def colorFormat(self):
        """The color format of the movie (`str`).

        """
        return self._colorFormat
    

class MovieFileReader:
    """Read movie frames from file.

    This class allows for the reading of movie frames from a file for playback
    or analysis. Reading frames from a movie file is a slow process, so this
    class uses a separate thread to decode movie frames in the background.
    
    Frame color and audio data is output as Numpy arrays. These arrays can be 
    passed directly to texture or audio buffers, respectivley.

    Parameters
    ----------
    filename : str
        The name (or path) of the file to read the movie from.
    decoderLib : str
        The library to use to handle decoding the movie. The default is
        'ffpyplayer'.
    decoderOpts : dict or None
        A dictionary of options to pass to the decoder. These option can be used
        to control the quality of the movie, for example. The options depend on
        the `decoderLib` in use. If `None`, the reader will use the default
        options for the backend.
    maxQueueSize : int
        The maximum number of frames to queue in memory. If the queue is full,
        the reader will wait until a frame is removed from the queue before
        adding a new frame. Consider reducing this value to reduce CPU usage if
        you are presenting frames slower than they are being read from the movie
        file. If `0`, the queue size is unlimited. Value must be >=0.

    Notes
    -----
    * If `decoderLib='ffpyplayer'`, audio playback is handled externally by 
      SDL2. This means that audio playback is not synchronized with frame 
      presentation in PsychoPy. However, playback will not begin until the audio 
      track starts playing.
    * Do not access private attributes or methods of this class directly since 
      doing so is not thread-safe. Use the public methods provided by this class
      to interact with the movie reader.

    """
    def __init__(self, 
                 filename, 
                 decoderLib='ffpyplayer', 
                 decoderOpts=None, 
                 maxQueueSize=32):
        
        if maxQueueSize < 0:
            raise ValueError('`maxQueueSize` must be >=0.')

        self._filename = filename
        self._decoderLib = decoderLib
        self._decoderOpts = {} if decoderOpts is None else decoderOpts

        # thread for the reader
        self._player = None  # player interface object
        self._readerThread = None
        self._lastFrame = None
        self._lastFrameInterval = (-1.0, 0.0)
        self._exitEvent = threading.Event()  # signal to exit the reader thread
        self._exitEvent.clear()

        # movie information
        self._frameInterval = -1.0
        self._srcFrameSize = (-1, -1)
        self._frameRate = -1.0
        self._frameInterval = -1.0
        self._duration = -1.0
        self._srcPixelFormat = None

        # queues for video and audio frames
        self._frameQueue = queue.Queue(maxsize=maxQueueSize)
        self._audioQueue = queue.Queue(maxsize=maxQueueSize)
        
        # This lock is used to prevent the reader thread from get frames while
        # another thread is accessing playback controls (e.g. play, pause, seek)
        self._readLock = threading.Lock()

        # barrier used to synchronize the reader thread with other threads
        self._warmupBarrier = None

        # store decoded video segmenets in memory
        self._videoSegments = []

        # video segment format
        # [{'video': videoFrame, 'audio': audioFrame, 'pts': pts}, ...]

    def __hash__(self):
        """Use the absolute file path as the hash value since we only allow one
        instance per file.
        """
        return hash(os.path.abspath(self._filename))
    
    def _clearFrameQueue(self):
        """Clear the frame queue in a thread-safe way.
        """
        with self._frameQueue.mutex:
            self._frameQueue.queue.clear()

    @property
    def decoderLib(self):
        """The library used to decode the movie (`str`).

        """
        return self._decoderLib

    @property
    def frameSize(self):
        """The frame size of the movie in pixels (`tuple`).

        This is only valid after calling `open()`. If not, the value is 
        `(-1, -1)`.

        """
        return self._srcFrameSize

    @property
    def frameInterval(self):
        """The interval between frames in the movie in seconds (`float`).

        This is only valid after calling `open()`. If not, the value is `-1`.

        """
        return self._frameInterval

    @property
    def frameRate(self):
        """The frame rate of the movie in frames per second (`float`).

        This is only valid after calling `open()`. If not, the value is `-1`.

        """
        return self._frameRate

    @property
    def duration(self):
        """The duration of the movie in seconds (`float`).

        This is only valid after calling `open()`. If not, the value is `-1`.

        """
        return self._duration
    
    @property
    def filename(self):
        """The name (path) of the movie file (`str`).

        This cannot be changed after the reader has been opened.

        """
        return self._filename
    
    def load(self, filename):
        """Load a movie file.

        This is an alias for `setMovie()` to synchronize naming with other video
        classes around PsychoPy.

        Parameters
        ----------
        filename : str
            The name (path) of the file to read the movie from.

        """
        self.setMovie(filename)

    def setMovie(self, filename):
        """Set the movie file to read from and open it.

        If there is a movie file currently open, it will be closed before
        opening the new movie file. Playback will be reset to the beginning of
        the movie.
        
        Parameters
        ----------
        filename : str
            The name (path) of the file to read the movie from.
        
        """
        if self.isOpen:
            self.close()

        # check if the file exists and is readable
        if not os.path.isfile(filename):
            raise IOError('Movie file does not exist: {}'.format(filename))

        self._filename = filename

        self.open()

    def _openFFPyPlayer(self):
        """Open a movie reader using FFPyPlayer.
        """
        # import in the class too avoid hard dependency on ffpyplayer
        try:
            from ffpyplayer.player import MediaPlayer
        except ImportError:
            raise ImportError(
                'The `ffpyplayer` library is required to read movie files with '
                '`decoderLib=ffpyplayer`.')

        def _asyncFrameReader(moviePlayer, frameQueue, readLock, exitEvent,
                              warmupBarrier=None):
            """Local function used to read frames from the movie file.

            This is executed in a thread to allow the main thread to continue
            adding frames to the movie while the movie is being written to
            disk.

            Parameters
            ----------
            moviePlayer : ffpyplayer.player.MediaPlayer
                The movie player object used to read frames from the movie file.
            frameQueue : queue.Queue
                A queue containing the frames read from the movie file.
            readLock : threading.Lock
                A lock used to synchronize access to the movie reader object for
                accessing playback controls.
            exitEvent : threading.Event
                An event used to signal the reader thread to exit.
            warmupBarrier : threading.Barrier or None
                A `threading.Barrier` object used to synchronize the movie
                reader with other threads. This guarantees that the movie reader
                is ready before frames are passed te the queue. If `None`,
                no synchronization is performed.

            """
            # wait until initialized
            while not exitEvent.is_set():  # quit if signaled
                with readLock:
                    frame, status = moviePlayer.get_frame(show=True)

                if frame is None:
                    continue

                # waits for queue to have space before adding more frames, this
                # will govern the rate of which frames are read from the movie
                img, pts = frame
                frameQueue.put((img, pts, status))
                    
                if status == 'eof':  # thread should exit if stream is done
                    break
                elif status == 'paused':
                    time.sleep(0.001)

            # if we're here, the reader thread should exit
            with readLock:
                moviePlayer.set_pause(True)
                moviePlayer.close_player()

        logging.info("Opening movie file: {}".format(self._filename))

        # default options
        defaultFFOpts = {
            'paused': True,
            # 'loop': 1
        }

        # merge user settings with defaults, user settings take precedence
        defaultFFOpts.update(self._decoderOpts)
        self._decoderOpts = defaultFFOpts

        # create media player
        self._player = MediaPlayer(
            self._filename,
            ff_opts=self._decoderOpts)

        # wait for valid metadata to be available
        logging.debug("Waiting for movie metadata...")
        while 1:
            movieMetadata = self._player.get_metadata()
            if movieMetadata['src_vid_size'] != (0, 0):
                break

        # movie metadata
        numer, denom = movieMetadata['frame_rate']
        self._srcFrameSize = movieMetadata['src_vid_size']
        self._frameRate = numer / denom
        self._frameInterval = 1.0 / self._frameRate
        self._duration = movieMetadata['duration']
        self._srcPixelFormat = movieMetadata['src_pix_fmt']
        if isinstance(self._srcPixelFormat, bytes):
            self._srcPixelFormat = self._srcPixelFormat.decode('utf-8')

        logging.debug("Movie metadata: {}".format(movieMetadata))

        # initialize the thread, the thread will wait on frames to be added to
        # the queue
        logging.debug("Starting movie reader thread...")

        self._readerThread = threading.Thread(
            target=_asyncFrameReader,
            args=(
                self._player, 
                self._frameQueue, 
                self._readLock,
                self._exitEvent,
                self._warmupBarrier))
        
        logging.debug("Waiting for movie reader thread to start...")

        self._readerThread.start()

        logging.debug("Movie reader thread started.")

    def open(self):
        """Open the movie file for reading.

        """
        self._exitEvent.clear()  # clear the exit event
        
        logging.debug("Using decoder library: {}".format(self._decoderLib))
        if self._decoderLib == 'ffpyplayer':
            self._openFFPyPlayer()
        elif self._decoderLib == 'opencv':
            self._openOpenCV()
        else:
            raise ValueError(
                'Unknown decoder library: {}'.format(self._decoderLib))

        # register the reader with the global list of open movie readers
        if self in _openMovieReaders:
            raise RuntimeError(
                'Movie reader already open for file: {}'.format(self._filename))
        
        _openMovieReaders.add(self)

    @property
    def isOpen(self):
        """Whether the movie file is open (`bool`).

        If `True`, the movie file is open and frames can be read from it. If
        `False`, the movie file is closed and no more frames can be read from
        it.

        """
        return self._readerThread is not None and self._readerThread.is_alive()

    def close(self):
        """Close the movie file.

        """
        if self._readerThread is None:
            return
        
        # signal the reader thread to exit
        self._exitEvent.set()
        self._readerThread.join()

        # remove the reader from the global list of open movie readers
        if self in _openMovieReaders:
            _openMovieReaders.remove(self)

    def _defragVideoSegments(self):
        """Defragment the video segment buffer.

        This function defragments the video segment buffer by removing segments
        which are no longer needed. This is used to prevent the video segment
        buffer from growing indefinitely.

        """
        if not self._videoSegments:
            return

    def _frameInSegmentBuffer(self, pts):
        """Check if a frame is in the video segment buffer.

        Parameters
        ----------
        pts : float
            The presentation timestamp (PTS) of the frame to check.

        Returns
        -------
        bool
            `True` if the frame is in the video segment buffer. `False` if the
            frame is not in the buffer.

        """
        for segment in self._videoSegments:
            if segment[0] <= pts < segment[1]:
                return True

        return False

    def startDecoding(self, initialPTS=0.0):
        """Start decoding movie frames in background thread.

        This begins decoding movie frames from the movie file and adding them to
        the frame queue. This will continue until either: the frame queue is 
        full, the `stop()` method is called, the file is closed, or the end of 
        the movie is reached.

        If an audio track is present, audio samples will be decoded and added to
        the audio queue (if appicable).

        Parameters
        ----------
        initialPTS : float, None
            The initial presentation timestamp (PTS) to start decoding frames
            from in seconds. If `0.0`, decoding will start from the beginning of
            the movie. If `None`, decoding will start from the current position
            in the movie.

        """
        if not self.isOpen:
            self.open()  # call open if not already open
            logging.warning(
                'Movie reader is not open. Opening movie file: {}'.format(
                    self._filename))

        # use the read lock to prevent the reader thread from interacting with
        # the media reader object
        with self._readLock:
            if self._decoderLib == 'ffpyplayer':
                # seek to the initial PTS
                self._player.set_pause(True)
                self._player.seek(initialPTS, relative=False, accurate=True)
                # unpause the movie to begin decoding frames
                self._player.set_pause(False)
            elif self._decoderLib == 'opencv':
                raise NotImplementedError(
                    'The `opencv` library is not supported for movie reading.')
            else:
                raise ValueError(
                    'Unknown decoder library: {}'.format(self._decoderLib))

    def stopDecoding(self):
        """Stop decoding movie frames in background thread.

        This halts the decoding of movie frames from the movie file and stops
        adding them to the frame queue. This will not close the movie file.

        """
        with self._readLock:
            if self._decoderLib == 'ffpyplayer':
                self._player.set_pause(True)
            elif self._decoderLib == 'opencv':
                raise NotImplementedError(
                    'The `opencv` library is not supported for movie reading.')
            else:
                raise ValueError(
                    'Unknown decoder library: {}'.format(self._decoderLib))

    @property
    def isDecoding(self):
        """Whether the movie reader is decoding frames (`bool`).

        If `True`, the movie reader is decoding frames from the movie file. If
        `False`, the movie reader is paused.

        """
        return self.isPlaying

    @property
    def memoryUsed(self):
        """Get the amount of memory used to store decoded frames.

        Returns
        -------
        int
            The amount of memory used by the movie reader in bytes.

        """
        # sum of bytes used by video segments
        totalFramesDecoded = self._frameQueue.qsize() + len(self._videoSegments)
        pixelSize = 3 if 'rgb' in self._srcPixelFormat else 4
        pixelCount = self._srcFrameSize[0] * self._srcFrameSize[1]

        return totalFramesDecoded * pixelCount * pixelSize

    def clearSegments(self):
        """Clear all buffered video segments.

        This function clears all buffered video segments from memory. This is
        useful if you want to free up memory used by the video segment buffer.

        """
        self._videoSegments = []

    def _dequeueFrames(self):
        """Dequeue frames from the frame queue.

        This function dequeues frames from the frame queue and stores them in the
        video segment buffer. This is used to store frames in memory for quick
        access when seeking to a specific frame.

        Returns
        -------
        list
            A list of frames that have been dequeued from the frame queue.

        """
        queuedFrames = []
        while self._frameQueue.qsize() > 0:
            try:
                frameData = self._frameQueue.get_nowait()
            except queue.Empty:
                break

            queuedFrames.append(frameData)
        
        return queuedFrames

    def _getFrameFFPyPlayer(self, pts=0.0, dropFrame=True):
        """Get a frame from the movie file using FFPyPlayer.

        This must be called after `start()` to get frames from the movie file.

        Parameters
        ----------
        pts : float or None
            The presentation timestamp (PTS) of the frame to get in seconds.
            Timestamps can be as precise as 6 decimal places.
        dropFrame : bool
            If `True`, the frame is dropped if it is not available, and the 
            most recent frame will be returned immediately. If `False`, the 
            function will block until the desired frame is returned.

        Returns
        -------
        tuple
            Video data.

        """
        # round the PTS to 6 decimal places
        pts = round(pts, 6)

        # check if the frame is within the range of the movie
        if pts >= self.duration:
            toReturn = self._videoSegments[-1]
            return toReturn

        # do we have any frames in the queue?
        if self._frameQueue.qsize() > 0:
            with self._readLock:
                self._videoSegments += self._dequeueFrames()

        # check if we need to seek first
        if self._videoSegments:
            # we have a segment, but wee need to check if the frame is in the
            # segment buffer. If not, we'll need to seek to the frame
            segmentStart = self._videoSegments[0][1]
            segmentEnd = self._videoSegments[-1][1] + self._frameInterval
            # is the pts outside the current segment buffer? seek if so
            needSeek = not segmentStart <= pts < segmentEnd
        else:
            # check the position of the movie
            with self._readLock:
                currentPos = self._player.get_pts()
            # check if the requested pts is within the current position
            needSeek = not currentPos <= pts < currentPos + self._frameInterval

        # do we need to seek to the frame?
        if needSeek:
            with self._readLock:
                self._player.set_pause(True)
                self._player.seek(
                    pts, relative=False, seek_by_bytes=False, accurate=True)
                # clear out the frame queue
                _ = self._dequeueFrames()
                self._videoSegments.clear()
                self._player.set_pause(False)

                # seeking gets us close to the frame, so we need to pull down
                # the frames until we get to the desired frame
                while 1:
                    frame, status = self._player.get_frame(show=True)
                    if frame is None:
                        continue

                    img, curPts = frame
                    curPts = round(curPts, 6)
                    
                    # check if the pts falls within the interval of this frame
                    if curPts <= pts < curPts + self._frameInterval:
                        self._videoSegments.append((img, curPts, status))
                        break  
                    elif status == 'eof':  # handle this case at some point
                        break

        # get the PTS of the last video frame to be decoded
        endPts = self._videoSegments[-1][1] if self._videoSegments else -1.0

        if pts >= endPts:
            print('Frame not available. End of stream.')
            if self._videoSegments:
                return self._videoSegments[-1]
            return None

        # estimate the frame index that contains the desired frame, this is used
        # to avoid needing to iterate over all the frames in the video segment
        # find one with the closest PTS
        segmentStartIdx = int(self._videoSegments[0][1] / self.frameInterval)
        estFrameIndex = int(pts / self.frameInterval) - segmentStartIdx

        # get the frame from the video segment buffer
        try:
            toReturn = self._videoSegments[estFrameIndex]
        except IndexError:
            toReturn = self._videoSegments[-1]

        # get the next frame that falls within the interval
        for i, segment in enumerate(self._videoSegments[estFrameIndex:]):
            beginFrameTime = segment[1]

            # look ahead to get the next frame start time
            if i + 1 >= len(self._videoSegments):  
                toReturn = self._videoSegments[-1]
                break

            nextFrame = self._videoSegments[estFrameIndex + i + 1]
            nextFrameTime = nextFrame[1]

            # check if it falls within the interval for the current frame index
            if beginFrameTime <= pts < nextFrameTime:
                toReturn = segment
                break

        return toReturn

    def getFrame(self, pts=0.0, dropFrame=True):
        """Get a frame from the movie file at the specified presentation 
        timestamp.

        Parameters
        ----------
        pts : float or None
            The presentation timestamp (PTS) of the frame to get in seconds.
            Timestamps can be as precise as six decimal places.
        dropFrame : bool
            If `True`, the frame is dropped if it is not available, and the 
            most recent frame will be returned immediately. If `False`, the 
            function will block until the desired frame is returned.

        Returns
        -------
        tuple
            Video data.

        """
        if self._decoderLib == 'ffpyplayer':
            return self._getFrameFFPyPlayer(pts, dropFrame)

    def __del__(self):
        """Close the movie file when the object is deleted.
        """
        if hasattr(self, '_readerThread') and self._readerThread is not None:
            self.close()



class MovieFileWriter:
    """Create movies from a sequence of images.

    This class allows for the creation of movies from a sequence of images using
    FFMPEG (via the `ffpyplayer` or `cv2` libraries). Writing movies to disk is 
    a slow process, so this class uses a separate thread to write the movie in 
    the background. This means that you can continue to add images to the movie 
    while frames are still being written to disk. Movie writers are closed 
    automatically when the main thread exits. Any remaining frames are flushed 
    to the file before the file is finalized.

    Writing audio tracks is not supported. If you need to add audio to your 
    movie, create the file with the video content first, then add the audio 
    track to the file. The :func:`addAudioToMovie` function can be used to do 
    this after the video and audio files have been saved to disk.

    Parameters
    ----------
    filename : str
        The name (or path) of the file to write the movie to. The file extension
        determines the movie format if `codec` is `None` for some backends.
        Otherwise it must be explicitly specified.
    size : tuple or str
        The size of the movie in pixels (width, height). If a string is passed,
        it should be one of the keys in the `VIDEO_RESOLUTIONS` dictionary.
    fps : float
        The number of frames per second.
    codec : str or None
        The codec to use for encoding the movie. This may be a codec identifier
        (e.g., 'libx264') or a FourCC code. The value depends of the 
        `encoderLib` in use. If `None`, the writer will select the codec based
        on the file extension of `filename` (if supported by the backend).
    pixelFormat : str
        Pixel format for frames being added to the movie. This should be 
        either 'rgb24' or 'rgba32'. The default is 'rgb24'. When passing frames
        to `addFrame()` as a numpy array, the array should be in the format
        specified here.
    encoderLib : str
        The library to use to handle encoding and writing the movie to disk. The 
        default is 'ffpyplayer'.
    encoderOpts : dict or None
        A dictionary of options to pass to the encoder. These option can be used
        to control the quality of the movie, for example. The options depend on
        the `encoderLib` in use. If `None`, the writer will use the default
        options for the backend.

    Examples
    --------
    Create a movie from a sequence of generated noise images::

        import psychopy.tools.movietools as movietools
        import numpy as np

        # create a movie writer
        writer = movietools.MovieFileWriter(
            filename='myMovie.mp4', 
            size=(640, 480), 
            fps=30)
        
        # open the movie for writing
        writer.open()
            
        # add some frames to the movie
        for i in range(5 * writer.fps):  # 5 seconds of video
            # create a frame, just some random noise
            frame = np.random.randint(0, 255, (640, 480, 3), dtype=np.uint8)
            # add the frame to the movie
            writer.addFrame(frame)

        # close the movie, this completes the writing process
        writer.close()
    
    Setting additional options for the movie encoder requires passing a
    dictionary of options to the `encoderOpts` parameter. The options depend on
    the encoder library in use. For example, to set the quality of the movie
    when using the `ffpyplayer` library, you can do the following::

        ffmpegOpts = {'preset': 'medium', 'crf': 16}  # medium quality, crf=16
        writer = movietools.MovieFileWriter(
            filename='myMovie.mp4', 
            size='720p', 
            fps=30,
            encoderLib='ffpyplayer',
            encoderOpts=ffmpegOpts)
        
    The OpenCV backend specifies options differently. To set the quality of the
    movie when using the OpenCV library with a codec that support variable 
    quality, you can do the following::

        cvOpts = {'quality': 80}  # set the quality to 80 (0-100)
        writer = movietools.MovieFileWriter(
            filename='myMovie.mp4', 
            size='720p',
            fps=30,
            encoderLib='opencv',
            encoderOpts=cvOpts)
        
    """
    # supported pixel formats as constants
    PIXEL_FORMAT_RGB24 = 'rgb24'
    PIXEL_FORMAT_RGBA32 = 'rgb32'

    def __init__(self, filename, size, fps, codec=None, pixelFormat='rgb24',
                 encoderLib='ffpyplayer', encoderOpts=None):
        
        # objects needed to build up the asynchronous movie writer interface
        self._writerThread = None  # thread for writing the movie file
        self._frameQueue = queue.Queue()  # queue for frames to be written
        self._dataLock = threading.Lock()  # lock for accessing shared data
        self._lastVideoFile = None  # last video file we wrote to

        # set the file name
        self._filename = None
        self._absPath = None  # use for generating a hash of the filename
        self.filename = filename  # use setter to init self._filename

        # Select the default codec based on the encoder library, we want to use
        # H264 for OpenCV and libx264 for ffpyplayer. If the user specifies a
        # codec, we use that instead.
        if encoderLib == 'ffpyplayer':
            self._codec = codec or 'libx264'  # default codec
        elif encoderLib == 'opencv':
            self._codec = codec or 'mp4v'
            if len(self._codec) != 4:
                raise ValueError('OpenCV codecs must be FourCC codes')
        else:
            raise ValueError('Unknown encoder library: {}'.format(encoderLib))
        self._encoderLib = encoderLib
        self._encoderOpts = {} if encoderOpts is None else encoderOpts

        self._size = None
        self.size = size  # use setter to init self._size
        self._fps = None
        self.fps = fps  # use setter to init self._fps
        self._pixelFormat = pixelFormat
        
        # frame interval in seconds
        self._frameInterval = 1.0 / self._fps

        # keep track of the number of bytes we saved to the movie file
        self._pts = 0.0  # most recent presentation timestamp
        self._bytesOut = 0
        self._framesOut = 0

    def __hash__(self):
        """Use the absolute file path as the hash value since we only allow one 
        instance per file.
        """
        return hash(self._absPath)

    @property
    def filename(self):
        """The name (path) of the movie file (`str`).

        This cannot be changed after the writer has been opened.

        """
        return self._filename

    @filename.setter
    def filename(self, value):
        if self.isOpen:
            raise RuntimeError(
                'Cannot change `filename` after the writer has been opened.')

        self._filename = value
        self._absPath = os.path.abspath(self._filename)
    
    @property
    def size(self):
        """The size `(w, h)` of the movie in pixels (`tuple` or `str`).
        
        If a string is passed, it should be one of the keys in the 
        `VIDEO_RESOLUTIONS` dictionary.

        This can not be changed after the writer has been opened.

        """
        return self._size

    @size.setter
    def size(self, value):
        if self.isOpen:
            raise RuntimeError(
                'Cannot change `size` after the writer has been opened.')

        # if a string is passed, try to look up the size in the dictionary
        if isinstance(value, str):
            try:
                value = VIDEO_RESOLUTIONS[value.upper()]
            except KeyError:
                raise ValueError(
                    f'Unknown video resolution: {value}. Must be one of: '
                    f'{", ".join(VIDEO_RESOLUTIONS.keys())}.')
        
        if len(value) != 2:
            raise ValueError('`size` must be a collection of two integers.')

        self._size = tuple(value)

    @property
    def frameSize(self):
        """The size `(w, h)` of the movie in pixels (`tuple`).

        This is an alias for `size` to synchronize naming with other video
        classes around PsychoPy.

        """
        return self._size
    
    @frameSize.setter
    def frameSize(self, value):
        self.size = value
    
    @property
    def fps(self):
        """Output frames per second (`float`).

        This is the number of frames per second that will be written to the
        movie file. The default is 30.

        """
        return self._fps
    
    @fps.setter
    def fps(self, value):
        if self.isOpen:
            raise RuntimeError(
                'Cannot change `fps` after the writer has been opened.')
        
        if value <= 0:
            raise ValueError('`fps` must be greater than 0.')

        self._fps = value
        self._frameInterval = 1.0 / self._fps

    @property
    def frameRate(self):
        """Output frames per second (`float`).

        This is an alias for `fps` to synchronize naming with other video
        classes around PsychoPy.

        """
        return self._fps
    
    @frameRate.setter
    def frameRate(self, value):
        self.fps = value
    
    @property
    def codec(self):
        """The codec to use for encoding the movie (`str`). 
        
        This may be a codec identifier (e.g., 'libx264'), or a FourCC code (e.g. 
        'MPV4'). The  value depends of the `encoderLib` in use. If `None`, the a 
        codec  determined by the file extension will be used.

        """
        return self._codec
    
    @codec.setter
    def codec(self, value):
        if self.isOpen:
            raise RuntimeError(
                'Cannot change `codec` after the writer has been opened.')

        self._codec = value
    
    @property
    def pixelFormat(self):
        """Pixel format for frames being added to the movie (`str`).

        This should be either 'rgb24' or 'rgba32'. The default is 'rgb24'. When
        passing frames to `addFrame()` as a numpy array, the array should be in
        the format specified here.

        """
        return self._pixelFormat

    @pixelFormat.setter
    def pixelFormat(self, value):
        if self.isOpen:
            raise RuntimeError(
                'Cannot change `pixelFormat` after the writer has been opened.')

        self._pixelFormat = value

    @property
    def encoderLib(self):
        """The library to use for writing the movie (`str`).

        Can only be set before the movie file is opened. The default is
        'ffpyplayer'.

        """
        return self._encoderLib
    
    @encoderLib.setter
    def encoderLib(self, value):
        if not self.isOpen:
            raise RuntimeError(
                'Cannot change `encoderLib` after the writer has been opened.')

        self._encoderLib = value

    @property
    def encoderOpts(self):
        """Encoder options (`dict`).

        These are passed directly to the encoder library. The default is an
        empty dictionary.

        """
        return self._encoderOpts
    
    @encoderOpts.setter
    def encoderOpts(self, value):
        if not self.isOpen:
            raise RuntimeError(
                'Cannot change `encoderOpts` after the writer has been opened.')

        self._encoderOpts = value

    @property
    def lastVideoFile(self):
        """The name of the last video file written to disk (`str` or `None`).

        This is `None` if no video file has been written to disk yet. Only valid
        after the movie file has been closed (i.e. after calling `close()`.)

        """
        return self._lastVideoFile
    
    @property
    def isOpen(self):
        """Whether the movie file is open (`bool`).

        If `True`, the movie file is open and frames can be added to it. If
        `False`, the movie file is closed and no more frames can be added to it.
        
        """
        if self._writerThread is None:
            return False
        
        return self._writerThread.is_alive()
    
    @property
    def framesOut(self):
        """Total number of frames written to the movie file (`int`).

        Use this to monitor the progress of the movie file writing. This value
        is updated asynchronously, so it may not be accurate if you are adding
        frames to the movie file very quickly.

        This value is retained after the movie file is closed. It is cleared
        when a new movie file is opened.

        """
        with self._dataLock:
            return self._framesOut

    @property
    def bytesOut(self):
        """Total number of bytes (`int`) saved to the movie file.

        Use this to monitor how much disk space is occupied by the frames that 
        have been written so far. This value is updated asynchronously, so it 
        may not be accurate if you are adding frames to the movie file very 
        quickly.

        This value is retained after the movie file is closed. It is cleared
        when a new movie file is opened.

        """
        with self._dataLock:
            return self._bytesOut

    @property
    def framesWaiting(self):
        """The number of frames waiting to be written to disk (`int`).

        This value increases when you call `addFrame()` and decreases when the
        frame is written to disk. This number can be reduced to zero by calling
        `flush()`.

        """
        return self._frameQueue.qsize()
    
    @property
    def totalFrames(self):
        """The total number of frames that will be written to the movie file
        (`int`). 
        
        This incudes frames that have already been written to disk and frames 
        that are waiting to be written to disk.

        """
        return self.framesOut + self.framesWaiting
    
    @property
    def frameInterval(self):
        """The time interval between frames (`float`).

        This is the time interval between frames in seconds. This is the
        reciprocal of the frame rate.

        """
        return self._frameInterval
    
    @property
    def duration(self):
        """The duration of the movie in seconds (`float`).

        This is the total duration of the movie in seconds based on the number 
        of frames that have been added to the movie and the frame rate. This 
        does not represent the actual duration of the movie file on disk, which
        may be longer if frames are still being written to disk.

        """
        return self.totalFrames * self._frameInterval
    
    def _openFFPyPlayer(self):
        """Open a movie writer using FFPyPlayer.

        This is called by `open()` if `encoderLib` is 'ffpyplayer'. It will 
        create a background thread to write the movie file. This method is not
        intended to be called directly.

        """
        # import in the class too avoid hard dependency on ffpyplayer
        from ffpyplayer.writer import MediaWriter
        from ffpyplayer.pic import SWScale

        def _writeFramesAsync(filename, writerOpts, libOpts, frameQueue, readyBarrier,
                             dataLock):
            """Local function used to write frames to the movie file.

            This is executed in a thread to allow the main thread to continue
            adding frames to the movie while the movie is being written to
            disk.

            Parameters
            ----------
            filename : str
                Path of the movie file to write.
            writerOpts : dict
                Options to configure the movie writer. These are FFPyPlayer
                settings and are passed directly to the `MediaWriter` object.
            libOpts : dict
                Option to configure FFMPEG with.
            frameQueue : queue.Queue
                A queue containing the frames to write to the movie file.
                Pushing `None` to the queue will cause the thread to exit.
            readyBarrier : threading.Barrier or None
                A `threading.Barrier` object used to synchronize the movie
                writer with other threads. This guarantees that the movie writer
                is ready before frames are passed te the queue. If `None`, 
                no synchronization is performed.
            dataLock : threading.Lock
                A lock used to synchronize access to the movie writer object for
                accessing variables.

            """
            # create the movie writer, don't manipulate this object while the 
            # movie is being written to disk
            try:
                writer = MediaWriter(filename, [writerOpts], libOpts=libOpts)
            except Exception:  # catch all exceptions
                raise RuntimeError("Failed to open movie file.")

            # wait on a barrier
            if readyBarrier is not None:
                readyBarrier.wait()

            while True:
                frame = frameQueue.get()  # waited on until a frame is added
                if frame is None:
                    break

                # get the frame data
                colorData, pts = frame
                
                # do color conversion
                frameWidth, frameHeight = colorData.get_size()
                sws = SWScale(
                    frameWidth, frameHeight,
                    colorData.get_pixel_format(),
                    ofmt='yuv420p')

                # write the frame to the file
                bytesOut = writer.write_frame(
                    img=sws.scale(colorData),
                    pts=pts,
                    stream=0)
                
                # update the number of bytes saved
                with dataLock:
                    self._bytesOut += bytesOut
                    self._framesOut += 1

            writer.close()

        # options to configure the writer
        frameWidth, frameHeight = self.size
        writerOptions = {
            'pix_fmt_in': 'yuv420p',  # default for now using mp4
            'width_in': frameWidth,
            'height_in': frameHeight,
            'codec': self._codec,
            'frame_rate': (int(self._fps), 1)}
        
        # create a barrier to synchronize the movie writer with other threads
        self._syncBarrier = threading.Barrier(2)

        # initialize the thread, the thread will wait on frames to be added to 
        # the queue
        self._writerThread = threading.Thread(
            target=_writeFramesAsync,
            args=(self._filename, 
                  writerOptions, 
                  self._encoderOpts,
                  self._frameQueue,
                  self._syncBarrier,
                  self._dataLock))
        
        self._writerThread.start()

        logging.debug("Waiting for movie writer thread to start...")
        self._syncBarrier.wait()  # wait for the thread to start
        logging.debug("Movie writer thread started.")

    def _openOpenCV(self):
        """Open a movie writer using OpenCV.
        
        This is called by `open()` if `encoderLib` is 'opencv'. It will create
        a background thread to write the movie file. This method is not
        intended to be called directly.

        """
        import cv2

        def _writeFramesAsync(writer, filename, frameSize, frameQueue, 
                              readyBarrier, dataLock):
            """Local function used to write frames to the movie file.

            This is executed in a thread to allow the main thread to continue
            adding frames to the movie while the movie is being written to
            disk.

            Parameters
            ----------
            writer : cv2.VideoWriter
                A `cv2.VideoWriter` object used to write the movie file.
            filename : str
                Path of the movie file to write.
            frameSize : tuple
                The size of the frames in pixels as a `(width, height)` tuple.
            frameQueue : queue.Queue
                A queue containing the frames to write to the movie file.
                Pushing `None` to the queue will cause the thread to exit.
            readyBarrier : threading.Barrier or None
                A `threading.Barrier` object used to synchronize the movie
                writer with other threads. This guarantees that the movie writer
                is ready before frames are passed te the queue. If `None`, 
                no synchronization is performed.
            dataLock : threading.Lock
                A lock used to synchronize access to the movie writer object for
                accessing variables.

            """                        
            frameWidth, frameHeight = frameSize
            # wait on a barrier
            if readyBarrier is not None:
                readyBarrier.wait()

            # we can accept frames for writing now
            while True:
                frame = frameQueue.get()
                if frame is None:   # exit if we get `None`
                    break

                colorData, _ = frame  # get the frame data
                
                # Resize and color conversion, this puts the data in the correct 
                # format for OpenCV's frame writer
                colorData = cv2.resize(colorData, (frameWidth, frameHeight))
                colorData = cv2.cvtColor(colorData, cv2.COLOR_RGB2BGR)

                # write the actual frame out to the file
                writer.write(colorData)

                # number of bytes the last frame took
                # bytesOut = writer.get(cv2.VIDEOWRITER_PROP_FRAMEBYTES)
                bytesOut = os.stat(filename).st_size

                # update values in a thread safe manner
                with dataLock:
                    self._bytesOut = bytesOut
                    self._framesOut += 1

            writer.release()

        # Open the writer outside of the thread so exception opening it can be
        # caught beforehand.
        writer = cv2.VideoWriter(
            self._filename, 
            cv2.CAP_FFMPEG,  # use ffmpeg
            cv2.VideoWriter_fourcc(*self._codec),
            float(self._fps),
            self._size, 
            1)  # is color image?
        
        if self._encoderOpts:
            # only supported option for now is `quality`, this doesn't really
            # work for teh default OpenCV codec for some reason :(
            quality = self._encoderOpts.get('VIDEOWRITER_PROP_QUALITY', None) \
                or self._encoderOpts.get('quality', None)
            if quality is None:
                quality = writer.get(cv2.VIDEOWRITER_PROP_QUALITY)
                logging.debug("Quality not specified, using default value of "
                                f"{quality}.")
                
            writer.set(cv2.VIDEOWRITER_PROP_QUALITY, float(quality))
            logging.info(f"Setting movie writer quality to {quality}.")
    
        if not writer.isOpened():
            raise RuntimeError("Failed to open movie file.")

        # create a barrier to synchronize the movie writer with other threads
        self._syncBarrier = threading.Barrier(2)

        # initialize the thread, the thread will wait on frames to be added to 
        # the queue
        self._writerThread = threading.Thread(
            target=_writeFramesAsync,
            args=(writer,
                  self._filename,
                  self._size,
                  self._frameQueue,
                  self._syncBarrier,
                  self._dataLock))
        
        self._writerThread.start()
        _openMovieWriters.add(self)   # add to the list of open movie writers

        logging.debug("Waiting for movie writer thread to start...")
        self._syncBarrier.wait()  # wait for the thread to start
        logging.debug("Movie writer thread started.")
        
    def open(self):
        """Open the movie file for writing.

        This creates a new thread that will write the movie file to disk in
        the background.

        After calling this method, you can add frames to the movie using
        `addFrame()`. When you are done adding frames, call `close()` to
        finalize the movie file.

        """
        if self.isOpen:
            raise RuntimeError('Movie writer is already open.')
        
        # register ourselves as an open movie writer
        global _openMovieWriters
        # check if we already have a movie writer for this file
        if self in _openMovieWriters:
            raise ValueError(
                'A movie writer is already open for file {}'.format(
                    self._filename))
        
        logging.debug('Creating movie file for writing %s', self._filename)

        # reset counters
        self._bytesOut = self._framesOut = 0
        self._pts = 0.0

        # eventually we'll want to support other encoder libraries, for now
        # we're just going to hardcode the encoder libraries we support
        if self._encoderLib == 'ffpyplayer':
            self._openFFPyPlayer()
        elif self._encoderLib == 'opencv':
            self._openOpenCV()
        else:
            raise ValueError(
                "Unknown encoder library '{}'.".format(self._encoderLib))
        
        _openMovieWriters.add(self)   # add to the list of open movie writers
        logging.info("Movie file '%s' opened for writing.", self._filename)
        
    def flush(self):
        """Flush waiting frames to the movie file.

        This will cause all frames waiting in the queue to be written to disk
        before continuing the program i.e. the thread that called this method. 
        This is useful for ensuring that all frames are written to disk before 
        the program exits.

        """
        # check if the writer thread present and is alive
        if not self.isOpen:
            raise RuntimeError('Movie writer is not open.')

        # block until the queue is empty
        nWaitingAtStart = self.framesWaiting
        while not self._frameQueue.empty():
            # simple check to see if the queue size is decreasing monotonically
            nWaitingNow = self.framesWaiting
            if nWaitingNow > nWaitingAtStart:
                logging.warn(
                    "Queue length not decreasing monotonically during "
                    "`flush()`. This may indicate that frames are still being "
                    "added ({} -> {}).".format(
                        nWaitingAtStart, nWaitingNow)
                )
            nWaitingAtStart = nWaitingNow
            time.sleep(0.001)  # sleep for 1 ms

    def close(self):
        """Close the movie file.

        This shuts down the background thread and finalizes the movie file. Any
        frames still waiting in the queue will be written to disk before the
        movie file is closed. This will block the program until all frames are
        written, therefore, it is recommended for `close()` to be called outside
        any time-critical code.

        """
        if self._writerThread is None:
            return
        
        logging.debug("Closing movie file '{}'.".format(self.filename))

        # if the writer thread is alive still, then we need to shut it down
        if self._writerThread.is_alive():
            self._frameQueue.put(None)  # signal the thread to exit
            # flush remaining frames, if any
            msg = ("File '{}' still has {} frame(s) queued to be written to "
                   "disk, waiting to complete.")
            nWaiting = self.framesWaiting
            if nWaiting > 0:
                logging.warning(msg.format(self.filename, nWaiting))
                self.flush()

            self._writerThread.join()  # waits until the thread exits

        # unregister ourselves as an open movie writer
        try:
            global _openMovieWriters
            _openMovieWriters.remove(self)
        except AttributeError:
            pass
        
        # set the last video file for later use. This is handy for users wanting
        # to add audio tracks to video files they created
        self._lastVideoFile = self._filename

        self._writerThread = None

        logging.info("Movie file '{}' closed.".format(self.filename))
    
    def _convertImage(self, image):
        """Convert an image to a pixel format appropriate for the encoder. 

        This is used internally to convert an image (i.e. frame) to the native 
        frame format which the encoder library can work with. At the very least, 
        this function should accept a `numpy.array` as a valid type for `image` 
        no matter what encoder library is being used.

        Parameters
        ----------
        image : Any
            The image to convert.

        Returns
        -------
        Any
            The converted image. Resulting object type depends on the encoder
            library being used.

        """
        # convert the image to a format that the selected encoder library can
        # work with
        if self._encoderLib == 'ffpyplayer':  # FFPyPlayer `MediaWriter`
            import ffpyplayer.pic as pic
            if isinstance(image, np.ndarray): 
                # make sure we are the correct format
                image = np.ascontiguousarray(image, dtype=np.uint8).tobytes()
                return pic.Image(
                    plane_buffers=[image], 
                    pix_fmt=self._pixelFormat, 
                    size=self._size)
            elif isinstance(image, pic.Image):
                # check if the format is valid
                if image.get_pixel_format() != self._pixelFormat:
                    raise ValueError('Invalid pixel format for `image`.')
                return image
            else:
                raise TypeError(
                    'Unsupported `image` type for OpenCV '
                    '`MediaWriter.write_frame().')
        elif self._encoderLib == 'opencv':  # OpenCV `VideoWriter`
            if isinstance(image, np.ndarray):
                image = image.reshape(self._size[0], self._size[1], 3)
                return np.ascontiguousarray(image, dtype=np.uint8)
            else:
                raise TypeError(
                    'Unsupported `image` type for OpenCV `VideoWriter.write().')
        else:
            raise RuntimeError('Unsupported encoder library specified.')

    def addFrame(self, image, pts=None):
        """Add a frame to the movie.

        This adds a frame to the movie. The frame will be added to a queue and
        written to disk by a background thread. This method will block until the
        frame is added to the queue. 
        
        Any color space conversion or resizing will be performed in the caller's 
        thread. This may be threaded too in the future.

        Parameters
        ----------
        image : numpy.ndarray or ffpyplayer.pic.Image
            The image to add to the movie. The image must be in RGB format and 
            have the same size as the movie. If the image is an `Image` 
            instance, it must have the same size as the movie.
        pts : float or None
            The presentation timestamp for the frame. This is the time at which 
            the frame should be displayed. The presentation timestamp is in 
            seconds and should be monotonically increasing. If `None`, the 
            presentation timestamp will be automatically generated based on the 
            chosen frame rate for the output video. Not all encoder libraries
            support presentation timestamps, so this parameter may be ignored.

        Returns
        -------
        float
            Presentation timestamp assigned to the frame. Should match the value 
            passed in as `pts` if provided, otherwise it will be the computed
            presentation timestamp.

        """
        if not self.isOpen:
            # nb - eventually we can allow frames to be added to a closed movie
            # object and have them queued until the movie is opened which will
            # commence writing
            raise RuntimeError('Movie file not open for writing.')
        
        # convert to a format for the selected writer library
        colorData = self._convertImage(image)

        # get computed presentation timestamp if not provided
        pts = self._pts if pts is None else pts

        # pass the image data to the writer thread
        self._frameQueue.put((colorData, pts))

        # update the presentation timestamp after adding the frame
        self._pts += self._frameInterval

        return pts

    def __del__(self):
        """Close the movie file when the object is deleted.
        """
        try:
            self.close()
        except AttributeError:
            pass


def closeAllMovieReaders():
    """Signal all movie readers to close.

    This function should only be called once at the end of the program. This can 
    be registered `atexit` to ensure that all movie writers are closed when the 
    program exits.

    """
    global _openMovieReaders

    if not _openMovieReaders:  # do nothing if no movie writers are open
        return

    logging.info('Closing all open ({}) movie readers now'.format(
        len(_openMovieReaders)))

    for movieReader in _openMovieReaders.copy():
        movieReader.close()
        
    _openMovieReaders.clear()  # clear the set to free references


def closeAllMovieWriters():
    """Signal all movie writers to close.

    This function should only be called once at the end of the program. This can 
    be registered `atexit` to ensure that all movie writers are closed when the 
    program exits. If there are open file writers with frames still queued, this 
    function will block until all frames remaining are written to disk. 

    Use caution when calling this function when file writers are being used in a
    multi-threaded environment. Threads that are writing movie frames must be
    stopped prior to calling this function. If not, the thread may continue to
    write frames to the queue during the flush operation and never exit.

    """
    global _openMovieWriters

    if not _openMovieWriters:  # do nothing if no movie writers are open
        return

    logging.info('Closing all open ({}) movie writers now'.format(
        len(_openMovieWriters)))

    for movieWriter in _openMovieWriters.copy():
        # flush the movie writer, this will block until all frames are written
        movieWriter.close()
        
    _openMovieWriters.clear()  # clear the set to free references


# register the cleanup function to run when the program exits
atexit.register(closeAllMovieReaders)
atexit.register(closeAllMovieWriters)


def addAudioToMovie(outputFile, videoFile, audioFile, useThreads=True, 
                    removeFiles=False, writerOpts=None):
    """Add an audio track to a video file.

    This function will add an audio track to a video file. If the video file
    already has an audio track, it will be replaced with the audio file
    provided. If no audio file is provided, the audio track will be removed
    from the video file.

    The audio track should be exactly the same length as the video track.

    Parameters
    ----------
    outputFile : str
        Path to the output video file where audio and video will be merged.
    videoFile : str
        Path to the input video file.
    audioFile : str or None
        Path to the audio file to add to the video file.
    codec : str
        The name of the audio codec to use. This should be a valid codec name
        for the encoder library being used. If `None`, the default codec for
        the encoder library will be used.
    useThreads : bool
        If `True`, the audio will be added in a separate thread. This allows the
        audio to be added in the background while the program continues to run.
        If `False`, the audio will be added in the main thread and the program
        will block until the audio is added. Defaults to `True`.
    removeFiles : bool
        If `True`, the input video (`videoFile`) and audio (`audioFile`) files 
        will be removed (i.e. deleted from disk) after the audio has been added 
        to the video. Defaults to `False`.
    writerOpts : dict or None
        Options to pass to the movie writer. This should be a dictionary of
        keyword arguments to pass to the movie writer. If `None`, the default
        options for the movie writer will be used. Defaults to `None`. See
        documentation for `moviepy.video.io.VideoFileClip.write_videofile` for 
        possible values.

    Examples
    --------
    Combine a video file and an audio file into a single video file::

        from psychopy.tools.movietools import addAudioToMovie
        addAudioToMovie('output.mp4', 'video.mp4', 'audio.mp3')

    """
    from moviepy.video.io.VideoFileClip import VideoFileClip
    from moviepy.audio.io.AudioFileClip import AudioFileClip
    from moviepy.audio.AudioClip import CompositeAudioClip

    # default options for the writer
    moviePyOpts = {
        'verbose': False, 
        'logger': None
    }

    if writerOpts is not None:  # make empty dict if not provided
        moviePyOpts.update(writerOpts)

    def _renderVideo(outputFile, videoFile, audioFile, removeFiles, writerOpts):
        """Render the video file with the audio track.
        """
        # merge audio and video tracks, we use MoviePy for this
        videoClip = VideoFileClip(videoFile)
        audioClip = AudioFileClip(audioFile)
        videoClip.audio = CompositeAudioClip([audioClip])

        # transcode with the format the user wants
        videoClip.write_videofile(
            outputFile, 
            **writerOpts)  # expand out options

        if removeFiles:
            # remove the input files
            os.remove(videoFile)
            os.remove(audioFile)

    # run the audio/video merge in the main thread
    if not useThreads:
        logging.debug('Adding audio to video file in main thread')
        _renderVideo(
            outputFile, 
            videoFile, 
            audioFile, 
            removeFiles, 
            moviePyOpts)
        return

    # run the audio/video merge in a separate thread
    logging.debug('Adding audio to video file in separate thread')
    compositorThread = threading.Thread(
        target=_renderVideo, 
        args=(outputFile, 
              videoFile, 
              audioFile, 
              removeFiles,
              moviePyOpts))
    compositorThread.start()


if __name__ == "__main__":
    pass
