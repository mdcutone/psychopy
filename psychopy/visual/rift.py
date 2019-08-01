#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Oculus Rift HMD support for PsychoPy.

Copyright (C) 2019 - Matthew D. Cutone, The Centre for Vision Research, Toronto,
Ontario, Canada

Uses PsychXR to interface with the Oculus Rift runtime. See http://psychxr.org
for more information.

"""

# Part of the PsychoPy library
# Copyright (C) 2018 Jonathan Peirce
# Distributed under the terms of the GNU General Public License (GPL).

_HAS_PSYCHXR_ = True

try:
    import psychxr.libovr as libovr
except ImportError:
    _HAS_PSYCHXR_ = False

from . import window

import platform
import ctypes
from psychopy import platform_specific, logging
import pyglet.gl as GL
from psychopy.tools.attributetools import setAttribute
import numpy as np
import warnings

reportNDroppedFrames = 5

RIFT_CONTROLLER_TYPES = {
    'Xbox': libovr.CONTROLLER_TYPE_XBOX,
    'Remote': libovr.CONTROLLER_TYPE_REMOTE,
    'Touch': libovr.CONTROLLER_TYPE_TOUCH,
    'LeftTouch': libovr.CONTROLLER_TYPE_LTOUCH,
    'RightTouch': libovr.CONTROLLER_TYPE_RTOUCH,
    "Object0": libovr.CONTROLLER_TYPE_OBJECT0,
    "Object1": libovr.CONTROLLER_TYPE_OBJECT1,
    "Object2": libovr.CONTROLLER_TYPE_OBJECT2,
    "Object3": libovr.CONTROLLER_TYPE_OBJECT3
}

RIFT_BUTTON_TYPES = {
    "A": libovr.BUTTON_A,
    "B": libovr.BUTTON_B,
    "RThumb": libovr.BUTTON_RTHUMB,
    "RShoulder": libovr.BUTTON_RSHOULDER,
    "X": libovr.BUTTON_X,
    "Y": libovr.BUTTON_Y,
    "LThumb": libovr.BUTTON_LTHUMB,
    "LShoulder": libovr.BUTTON_LSHOULDER,
    "Up": libovr.BUTTON_UP,
    "Down": libovr.BUTTON_DOWN,
    "Left": libovr.BUTTON_LEFT,
    "Right": libovr.BUTTON_RIGHT,
    "Enter": libovr.BUTTON_ENTER,
    "Back": libovr.BUTTON_BACK,
    "VolUp": libovr.BUTTON_VOLUP,
    "VolDown": libovr.BUTTON_VOLDOWN,
    "Home": libovr.BUTTON_HOME,
}

RIFT_TRACKED_DEVICE_TYPES = {
    "HMD" : libovr.TRACKED_DEVICE_TYPE_HMD,
    "LTouch": libovr.TRACKED_DEVICE_TYPE_LTOUCH,
    "RTouch": libovr.TRACKED_DEVICE_TYPE_RTOUCH,
    "Touch": libovr.TRACKED_DEVICE_TYPE_TOUCH,
    "Object0": libovr.TRACKED_DEVICE_TYPE_OBJECT0,
    "Object1": libovr.TRACKED_DEVICE_TYPE_OBJECT1,
    "Object2": libovr.TRACKED_DEVICE_TYPE_OBJECT2,
    "Object3": libovr.TRACKED_DEVICE_TYPE_OBJECT3
}

RIFT_TRACKING_ORIGIN_TYPE = {
    "floor": libovr.TRACKING_ORIGIN_FLOOR_LEVEL,
    "eye": libovr.TRACKING_ORIGIN_EYE_LEVEL
}

RIFT_PERF_HUD_MODES = {
    'PerfSummary': libovr.PERF_HUD_PERF_SUMMARY,
    'Off': libovr.PERF_HUD_OFF}

RIFT_BOUNDARY_TYPE = {
    'PlayArea': libovr.BOUNDARY_PLAY_AREA,
    'Outer': libovr.BOUNDARY_OUTER
}

class LibOVRError(Exception):
    """Exception for LibOVR errors."""
    pass


class Rift(window.Window):
    """Class provides a display and peripheral interface for the Oculus Rift
    (see: https://www.oculus.com/) head-mounted display.

    """

    def __init__(
            self,
            fovType='recommended',
            trackingOriginType='floor',
            texelsPerPixel=1.0,
            headLocked=False,
            highQuality=True,
            monoscopic=False,
            samples=1,
            mirrorRes=None,
            legacyOpenGL=True,
            warnAppFrameDropped=True,
            autoUpdatePoses=True,
            *args,
            **kwargs):
        """

        Parameters
        ----------
        fovType : :obj:`str`
            Field-of-view (FOV) configuration type. Using 'recommended'
            auto-configures the FOV using the recommended parameters computed by
            the runtime. Using 'symmetric' forces a symmetric FOV using optimal
            parameters from the SDK.
        trackingOriginType : :obj:`str`
            Specify the HMD origin type. If 'floor', the height of the user
            is added to the head tracker by LibOVR.
        texelsPerPixel : :obj:`float`
            Texture pixels per display pixel at FOV center. A value of 1.0
            results in 1:1 mapping. A fractional value results in a lower
            resolution draw buffer which may increase performance.
        headLocked : :obj:`bool`
            Lock the compositor render layer in-place. Enable this if you plan
            on computing eye poses using custom or modified head poses.
        highQuality : :obj:`bool`
            Configure the compositor to use anisotropic texture sampling (4x).
            This reduces aliasing artifacts resulting from high frequency
            details particularly in the periphery.
        nearClip : :obj:`float`
            Location of the near clipping plane in GL units (meters by default)
            from the viewer.
        farClip : :obj:`float`
            Location of the far clipping plane in GL units (meters by default)
            from the viewer.
        monoscopic : :obj:`bool`
            Enable monoscopic rendering mode which presents the same image to
            both eyes. Eye poses used will be both centered at the HMD origin.
            Monoscopic mode uses a separate rendering pipeline which reduces
            VRAM usage. When in monoscopic mode, you do not need to call
            'setBuffer' prior to rendering (doing so will do have no effect).
        samples : :obj:`int`
            Specify the number of samples for anti-aliasing. When >1,
            multi-sampling logic is enabled in the rendering pipeline. If 'max'
            is specified, the largest number of samples supported by the
            platform is used. If floating point textures are used, MSAA sampling
            is disabled. Must be power of two value.
        legacyOpenGL : :obj:`bool`
            Disable 'immediate mode' OpenGL calls in the rendering pipeline.
            Specifying False maintains compatibility with existing PsychoPy
            stimuli drawing routines. Use True when computing transformations
            using some other method and supplying shaders matrices directly.
        mirrorMode : str
            On-screen mirror mode.
        mirrorRes : :obj:`list` of :obj:`int`
            Resolution of the mirror texture. If None, the resolution will
            match the window size.
        warnAppFrameDropped : :obj:`bool`
            Log a warning if the application drops a frame. This occurs when
            the application fails to submit a frame to the compositor on-time.
            Application frame drops can have many causes, such as running
            routines in your application loop that take too long to complete.
            However, frame drops can happen sporadically due to driver bugs and
            running background processes (such as Windows Update). Use the
            performance HUD to help diagnose the causes of frame drops.
        autoUpdatePoses : :obj:`bool`
            Automatically update and use tracked poses at the beginning of each
            frame.

        """

        if not _HAS_PSYCHXR_:
            raise ModuleNotFoundError(
                "PsychXR must be installed to use the Rift class. Exiting.")

        self._closed = False
        self._legacyOpenGL = legacyOpenGL
        self._monoscopic = monoscopic
        self._texelsPerPixel = texelsPerPixel
        self._headLocked = headLocked
        self._highQuality = highQuality
        self.autoUpdatePoses = autoUpdatePoses

        self._samples = samples
        self._mirrorRes = mirrorRes
        self._drawMirrorTex = False

        # this can be changed while running
        self.warnAppFrameDropped = warnAppFrameDropped

        # check if we are using Windows
        if platform.system() != 'Windows':
            raise RuntimeError("Rift class only supports Windows OS at this " +
                               "time, exiting.")

        # check if we are using 64-bit Python
        if platform.architecture()[0] != '64bit':  # sys.maxsize != 2**64
            raise RuntimeError("Rift class only supports 64-bit Python, " +
                               "exiting.")

        # check if the background service is running and an HMD is connected
        if not libovr.isOculusServiceRunning():
            raise RuntimeError("HMD service is not available or started, " +
                               "exiting.")

        if not libovr.isHmdConnected():
            raise RuntimeError("Cannot find any connected HMD, check " +
                               "connections and try again.")

        # create a VR session, do some initial configuration
        initResult = libovr.initialize()
        if libovr.failure(initResult):
            _, msg = libovr.getLastErrorInfo()
            raise LibOVRError(msg)

        if libovr.failure(libovr.create()):
            _, msg = libovr.getLastErrorInfo()
            raise LibOVRError(msg)

        # update session status object
        _, status = libovr.getSessionStatus()
        self._sessionStatus = status

        # get HMD information
        self._hmdInfo = libovr.getHmdInfo()

        # configure the internal render descriptors based on the requested
        # viewing parameters.
        if fovType == 'symmetric' or self._monoscopic:
            # Use symmetric FOVs for cases where off-center frustums are not
            # desired. This is required for monoscopic rendering to permit
            # comfortable binocular fusion.
            eyeFovs = self._hmdInfo.symmetricEyeFov
            logging.info('Using symmetric eye FOVs.')
        elif fovType == 'recommended' or fovType == 'default':
            # use the recommended FOVs, these have wider FOVs looking outward
            # due to off-center frustums.
            eyeFovs = self._hmdInfo.defaultEyeFov
            logging.info('Using default/recommended eye FOVs.')
        elif fovType == 'max':
            # the maximum FOVs for the HMD supports
            eyeFovs = self._hmdInfo.maxEyeFov
            logging.info('Using maximum eye FOVs.')
        else:
            raise ValueError(
                "Invalid FOV type '{}' specified.".format(fovType))

        # pass the FOVs to PsychXR
        for eye, fov in enumerate(eyeFovs):
            libovr.setEyeRenderFov(eye, fov)

        libovr.setHeadLocked(headLocked)  # enable head locked mode
        libovr.setHighQuality(highQuality)  # enable high quality mode

        # Compute texture sizes for render buffers, these are reported by the
        # LibOVR SDK based on the FOV settings specified above.
        texSizeLeft = libovr.calcEyeBufferSize(libovr.EYE_LEFT)
        texSizeRight = libovr.calcEyeBufferSize(libovr.EYE_RIGHT)

        # we are using a shared texture, so we need to combine dimensions
        if not self._monoscopic:
            hmdBufferWidth = texSizeLeft[0] + texSizeRight[0]
        else:
            hmdBufferWidth = max(texSizeLeft[0], texSizeRight[0])

        hmdBufferHeight = max(texSizeLeft[1], texSizeRight[1])

        # buffer viewport size
        self._hmdBufferSize = hmdBufferWidth, hmdBufferHeight
        logging.info(
            'Required HMD buffer size is {}x{}.'.format(*self._hmdBufferSize))

        # Calculate the swap texture size. These can differ in later
        # configurations, right now they are the same.
        self._swapTextureSize = self._hmdBufferSize

        # Compute the required viewport parameters for the given buffer and
        # texture sizes. If we are using a power of two texture, we need to
        # centre the viewports on the textures.
        if not self._monoscopic:
            leftViewport = (0, 0, texSizeLeft[0], texSizeLeft[1])
            rightViewport = (texSizeLeft[0], 0, texSizeRight[0], texSizeRight[1])
        else:
            # In mono mode, we use the same viewport for both eyes. Therefore,
            # the swap texture only needs to be half as wide. This save VRAM
            # and does not require buffer changes when rendering.
            leftViewport = (0, 0, texSizeLeft[0], texSizeLeft[1])
            rightViewport = (0, 0, texSizeRight[0], texSizeRight[1])

        libovr.setEyeRenderViewport(libovr.EYE_LEFT, leftViewport)
        logging.info(
            'Set left eye viewport to: x={}, y={}, w={}, h={}.'.format(
                *leftViewport))

        libovr.setEyeRenderViewport(libovr.EYE_RIGHT, rightViewport)
        logging.info(
            'Set right eye viewport to: x={}, y={}, w={}, h={}.'.format(
                *rightViewport))

        self.scrWidthPIX = max(texSizeLeft[0], texSizeRight[0])

        # frame index
        self._frameIndex = 0

        # setup a mirror texture
        self._mirrorRes = mirrorRes

        # view buffer to divert operations to, if None, drawing is sent to the
        # on-screen window.
        self.buffer = None

        # View matrices, these are updated every frame based on computed head
        # position. Projection matrices need only to be computed once.
        if not self._monoscopic:
            self._projectionMatrix = [
                np.identity(4, dtype=np.float32),
                np.identity(4, dtype=np.float32)]
            self._viewMatrix = [
                np.identity(4, dtype=np.float32),
                np.identity(4, dtype=np.float32)]
        else:
            self._projectionMatrix = np.identity(4, dtype=np.float32)
            self._viewMatrix = np.identity(4, dtype=np.float32)

        # disable v-sync since the HMD runs at a different frequency
        kwargs['waitBlanking'] = False

        # force checkTiming and quad-buffer stereo off
        kwargs["checkTiming"] = False
        kwargs["stereo"] = False
        kwargs['useFBO'] = True
        kwargs['multiSample'] = False
        # kwargs['waitBlanking'] = False

        # do not allow 'endFrame' to be called until _startOfFlip is called
        self._allowHmdRendering = False

        # VR pose data, updated every frame
        self._headPose = libovr.LibOVRPose()

        # set the tracking origin type
        self.trackingOriginType = trackingOriginType

        # performance information
        self.nDroppedFrames = 0
        self.controllerPollTimes = {}

        # call up a new window object
        super(Rift, self).__init__(*args, **kwargs)

        self._updateProjectionMatrix()

    @property
    def size(self):
        """Size property to get the dimensions of the view buffer instead of
        the window. If there are no view buffers, always return the dims of the
        window.

        """
        # this is a hack to get stimuli to draw correctly
        if self.buffer is None:
            return self.__dict__['size']
        else:
            if self._monoscopic:
                return np.array(
                    (self._hmdBufferSize[0], self._hmdBufferSize[1]),
                    np.int)
            else:
                return np.array(
                    (int(self._hmdBufferSize[0] / 2), self._hmdBufferSize[1]),
                    np.int)

    @size.setter
    def size(self, value):
        """Set the size of the window.

        """
        self.__dict__['size'] = np.array(value, np.int)

    def setSize(self, value, log=True):
        setAttribute(self, 'size', value, log=log)

    def perfHudMode(self, mode='Off'):
        """Set the performance HUD mode.

        Parameters
        ----------
        mode : str
            HUD mode to use.

        """
        result = libovr.setInt(libovr.PERF_HUD_MODE, RIFT_PERF_HUD_MODES[mode])
        logging.info("Performance HUD mode set to '{}'.".format(mode))

    def hidePerfHud(self):
        """Hide the performance HUD."""
        result = libovr.setInt(libovr.PERF_HUD_MODE, libovr.PERF_HUD_OFF)
        logging.info('Performance HUD disabled.')

    @property
    def userHeight(self):
        """Get user height in meters (`float`)."""
        return libovr.getFloat(libovr.KEY_PLAYER_HEIGHT,
                               libovr.DEFAULT_PLAYER_HEIGHT)

    @property
    def eyeHeight(self):
        """Eye height in meters (`float`)."""
        return libovr.getFloat(libovr.KEY_EYE_HEIGHT,
                               libovr.DEFAULT_EYE_HEIGHT)

    @property
    def eyeToNoseDistance(self):
        """Eye to nose distance in meters (`float`).

        Examples
        --------

        Generate your own eye poses::

            leftEyePose = createPose((-self.eyeToNoseDistance, 0., 0.))
            rightEyePose = createPose((self.eyeToNoseDistance, 0., 0.))
            self.hmdToEyePoses = [leftEyePose, rightEyePose]

        Get the inter-axial separation (IAS) reported by LibOVR::

            iad = self.eyeToNoseDistance * 2.0

        """
        eyeToNoseDist = np.zeros((2,), dtype=np.float32)
        result = libovr.getFloatArray(libovr.KEY_EYE_TO_NOSE_DISTANCE,
                                      eyeToNoseDist)

        return eyeToNoseDist

    @property
    def iod(self):
        """Inter-axial separation in meters (`float`).

        Value is applied to the poses in :py:class:`~Rift.hmdToEyePoses`.

        """
        if self.hmdToEyePoses is not None:
            return -self.hmdToEyePoses[0].pos[0] + self.hmdToEyePoses[1].pos[0]

    @iod.setter
    def iod(self, value):
        if self.hmdToEyePoses is not None:
            halfIAS = value / 2.0
            self.hmdToEyePoses = [libovr.LibOVRPose((halfIAS, 0.0, 0.0)),
                                  libovr.LibOVRPose((-halfIAS, 0.0, 0.0))]
            logging.info(
                'Inter-axial separation set to {} meters.'.format(value))

    @property
    def productName(self):
        """Get the HMD's product name (`str`).
        """
        return self._hmdInfo.productName

    @property
    def manufacturer(self):
        """Get the connected HMD's manufacturer (`str`).
        """
        return self._hmdInfo.manufacturer

    @property
    def serialNumber(self):
        """Get the connected HMD's unique serial number (`str`).

        Use this to identify a particular unit if you own many.
        """
        return self._hmdInfo.serialNumber

    @property
    def hid(self):
        """USB human interface device (HID) identifiers (`int`, `int`).

        """
        return self._hmdInfo.hid

    @property
    def firmwareVersion(self):
        """Get the firmware version of the active HMD (`int`, `int`).

        """
        return self._hmdInfo.firmwareVersion

    @property
    def displayResolution(self):
        """Get the HMD's raster display size (`int`, `int`).

        """
        return self._hmdInfo.resolution

    @property
    def displayRefreshRate(self):
        """Get the HMD's display refresh rate in Hz (`float`).

        """
        return self._hmdInfo.refreshRate

    @property
    def pixelsPerTanAngleAtCenter(self):
        """Horizontal and vertical per tangent angle (=1) at the center of the
        display.

        """
        return [libovr.getPixelsPerTanAngleAtCenter(libovr.EYE_LEFT),
                libovr.getPixelsPerTanAngleAtCenter(libovr.EYE_RIGHT)]

    def tanAngleToNDC(self, horzTan, vertTan):
        """Convert tan angles to the normalized device coordinates for the
        current buffer.

        Parameters
        ----------
        horzTan : float
            Horizontal tan angle.
        vertTan : float
            Vertical tan angle.

        Returns
        -------
        tuple of float
            Normalized device coordinates X, Y. Coordinates range between -1.0
            and 1.0. Returns `None` if an invalid buffer is selected.

        """
        if self.buffer == 'left':
            return libovr.getTanAngleToRenderTargetNDC(
                libovr.EYE_LEFT, (horzTan, vertTan))
        elif self.buffer == 'right':
            return libovr.getTanAngleToRenderTargetNDC(
                libovr.EYE_RIGHT, (horzTan, vertTan))

    @property
    def trackerCount(self):
        """Number of attached trackers."""
        return libovr.getTrackerCount()

    def getTrackerInfo(self, trackerIdx):
        """Get tracker information.

        Parameters
        ----------
        trackerIdx : int
            Tracker index, ranging from 0 to :py:class:`~Rift.trackerCount`.

        Returns
        -------
        LibOVRTrackerInfo
            Object containing tracker information.

        Raises
        ------
        IndexError
            Raised when `trackerIdx` out of range.

        """
        if 0 <= trackerIdx < libovr.getTrackerCount():
            return libovr.getTrackerInfo(trackerIdx)
        else:
            raise IndexError(
                "Tracker index '{}' out of range.".format(trackerIdx))

    @property
    def headLocked(self):
        """`True` if head locking is enabled."""
        return libovr.isHeadLocked()

    @headLocked.setter
    def headLocked(self, value):
        libovr.setHeadLocked(value)

    @property
    def trackingOriginType(self):
        """Current tracking origin type (`str`).

        Valid tracking origin types are 'floor' and 'eye'.

        """
        originType = libovr.getTrackingOriginType()

        if originType == libovr.TRACKING_ORIGIN_FLOOR_LEVEL:
            return 'floor'
        elif originType == libovr.TRACKING_ORIGIN_EYE_LEVEL:
            return 'eye'
        else:
            raise ValueError("LibOVR returned unknown tracking origin type.")

    @trackingOriginType.setter
    def trackingOriginType(self, value):
        libovr.setTrackingOriginType(RIFT_TRACKING_ORIGIN_TYPE[value])

    def recenterTrackingOrigin(self):
        """Recenter the tracking origin using the current head position."""
        libovr.recenterTrackingOrigin()

    def specifyTrackingOrigin(self, pose):
        """Specify a tracking origin.

        Parameters
        ----------
        pose : LibOVRPose
            Tracking origin pose.

        """
        libovr.specifyTrackingOrigin(pose)

    def specifyTrackingOriginPosOri(self, pos=(0., 0., 0.), ori=(0., 0., 0., 1.)):
        """Specify a tracking origin using a pose and orientation.

        Parameters
        ----------
        pos : tuple or list of float, or ndarray
            Position coordinate of origin (x, y, z).
        ori : tuple or list of float, or ndarray
            Quaternion specifying orientation (x, y, z, w).

        """
        libovr.specifyTrackingOrigin(libovr.LibOVRPose(pos, ori))

    def clearShouldRecenterFlag(self):
        """Clear the 'shouldRecenter' status flag at the API level."""
        libovr.clearShouldRecenterFlag()

    def testBoundary(self, deviceType, bounadryType='PlayArea'):
        """Test if tracked devices are colliding with the play area boundary.

        """
        if isinstance(deviceType, (list, tuple,)):
            deviceBits = 0x00000000
            for device in deviceType:
                deviceBits |= RIFT_TRACKED_DEVICE_TYPES[device]
        elif isinstance(deviceType, str):
            deviceBits = RIFT_TRACKED_DEVICE_TYPES[deviceType]
        elif isinstance(deviceType, int):
            deviceBits = deviceType
        else:
            raise TypeError("Invalid type specified for `deviceType`.")

        result, testResult = libovr.testBoundary(
            deviceBits, RIFT_BOUNDARY_TYPE[bounadryType])

        if libovr.failure(result):
            raise RuntimeError('Failed to get boundary test result')

        return testResult

    def getDevicePose(self, deviceName, absTime, latencyMarker=False):
        """Get the pose of a tracked device.

        Parameters
        ----------
        deviceName : str
            Name of the device. Valid device names are: 'HMD', 'LTouch',
            'RTouch', 'Touch', 'Object0', 'Object1', 'Object2', and 'Object3'.
        absTime : float
            Absolute time in seconds the device pose refers to.
        latencyMarker : bool
            Insert a marker for motion-to-photon latency calculation. Should
            only be True if the HMD pose is being used to compute eye poses.

        Returns
        -------
        `LibOVRPoseState` or `None`
            Pose state object. `None` if device tracking was lost.

        """
        deviceStatus, devicePose = libovr.getDevicePoses(
            [RIFT_TRACKED_DEVICE_TYPES[deviceName]], absTime, latencyMarker)

        # check if tracking was lost
        if deviceStatus == libovr.ERROR_LOST_TRACKING:
            return None

        return devicePose[0]

    def getTrackingState(self, absTime=None, latencyMarker=True):
        """Get the tracking state of the head and hands.

        Parameters
        ----------
        absTime : float, optional
            Absolute time the the tracking state refers to. If not specified,
            the predicted display time is used.
        latencyMarker : bool
            Set a latency marker upon getting the tracking state. This is used
            for motion-to-photon calculations.

        Returns
        -------
        LibOVRTrackingState
            Tracking state object.

        See Also
        --------
        getPredictedDisplayTime
            Time at mid-frame for the current frame index.

        """
        if absTime is None:
            absTime = self.getPredictedDisplayTime()

        return libovr.getTrackingState(absTime, latencyMarker)

    def calcEyePoses(self, headPose, originPose=None):
        """Calculate eye poses from a given head pose.

        Frame rendering is stalled until this function returns. If `headPose` is
        not from a recent tracking state, ensure ``headLocked=True`` to prevent
        the rendered image from 'slipping' due to ASW.

        Once this function returns, `setBuffer` can be called and frame
        rendering can commence. The computed eye pose for the selected buffer is
        accessible through the :py:attr:`eyeRenderPose` attribute after calling
        :py:method:`setBuffer`. If `monoscopic=True`, the eye poses are set to
        the head pose.

        Parameters
        ----------
        headPose : LibOVRPose
            Head pose to use.
        originPose : LibOVRPose, optional
            Origin of tracking in the VR scene.

        Examples
        --------
        Get the tracking state and calculate the eye poses::

            # get tracking state at predicted mid-frame time
            trackingState = hmd.getTrackingState()

            # get the head pose from the tracking state
            headPose = trackingState.headPose.thePose
            hmd.calcEyePoses(headPose)  # compute eye poses

            # begin rendering to each eye
            for eye in ('left', 'right'):
                hmd.setBuffer(eye)
                hmd.setRiftView()
                # draw stuff here ...

        Using a custom head pose (make sure ``headLocked=True`` before doing
        this)::

            headPose = createPose((0., 1.75, 0.))
            hmd.calcEyePoses(headPose)  # compute eye poses

        """
        if not self._allowHmdRendering:
            return

        libovr.calcEyePoses(headPose, originPose)
        self._headPose = headPose

        # Calculate eye poses, this needs to be called every frame.
        # apply additional transformations to eye poses
        if not self._monoscopic:
            for eye, matrix in enumerate(self._viewMatrix):
                # compute each eye's transformation modelMatrix from returned poses
                libovr.getEyeViewMatrix(eye, matrix)
        else:
            # view modelMatrix derived from head position when in monoscopic mode
            self._viewMatrix = headPose.getViewMatrix()

        self._startHmdFrame()

    @property
    def eyeRenderPose(self):
        """Computed eye pose for the current buffer. Only valid after calling
        :func:`calcEyePoses`.

        """
        if not self._monoscopic:
            if self.buffer == 'left':
                return libovr.getEyeRenderPose(libovr.EYE_LEFT)
            elif self.buffer == 'right':
                return libovr.getEyeRenderPose(libovr.EYE_RIGHT)
        else:
            return self._headPose

    @property
    def shouldQuit(self):
        """`True` if the user requested the application should quit through the
        headset's interface.
        """
        return self._sessionStatus.shouldQuit

    @property
    def isVisible(self):
        """`True` if the app has focus in the HMD and is visible to the viewer.
        """
        return self._sessionStatus.isVisible

    @property
    def hmdMounted(self):
        """`True` if the HMD is mounted on the user's head.
        """
        return self._sessionStatus.hmdMounted

    @property
    def hmdPresent(self):
        """`True` if the HMD is present.
        """
        return self._sessionStatus.hmdPresent

    @property
    def shouldRecenter(self):
        """`True` if the user requested the origin be re-centered through the
        headset's interface.
        """
        return self._sessionStatus.shouldRecenter

    @property
    def hasInputFocus(self):
        """`True` if the application currently has input focus.
        """
        return self._sessionStatus.hasInputFocus

    @property
    def overlayPresent(self):
        return self._sessionStatus.overlayPresent

    def _setupFrameBuffer(self):
        """Override the default framebuffer init code in window.Window to use
        the HMD swap chain. The HMD's swap texture and render buffer are
        configured here.

        If multisample anti-aliasing (MSAA) is enabled, a secondary render
        buffer is created. Rendering is diverted to the multi-sample buffer
        when drawing, which is then resolved into the HMD's swap chain texture
        prior to committing it to the chain. Consequently, you cannot pass
        the texture attached to the FBO specified by frameBuffer until the MSAA
        buffer is resolved. Doing so will result in a blank texture.

        """
        # create a texture swap chain for both eye textures
        result = libovr.createTextureSwapChainGL(
            libovr.TEXTURE_SWAP_CHAIN0,
            self._swapTextureSize[0],
            self._swapTextureSize[1])

        if libovr.success(result):
            logging.info(
                'Created texture swap chain with dimensions {w}x{h}.'.format(
                    w=self._swapTextureSize[0],
                    h=self._swapTextureSize[1]))
        else:
            _, msg = libovr.getLastErrorInfo()
            raise LibOVRError(msg)

        # assign the same swap chain to both eyes
        for eye in range(libovr.EYE_COUNT):
            libovr.setEyeColorTextureSwapChain(eye, libovr.TEXTURE_SWAP_CHAIN0)

        # Use MSAA if more than one sample is specified. If enabled, a render
        # buffer will be created.
        #
        max_samples = GL.GLint()
        GL.glGetIntegerv(GL.GL_MAX_SAMPLES, max_samples)
        if isinstance(self._samples, int):
            if (self._samples & (self._samples - 1)) != 0:
                # power of two?
                logging.warning(
                    'Invalid number of MSAA samples provided, must be '
                    'power of two. Disabling.')
            elif 0 > self._samples > max_samples.value:
                # check if within range
                logging.warning(
                    'Invalid number of MSAA samples provided, outside of valid '
                    'range. Disabling.')
        elif isinstance(self._samples, str):
            if self._samples == 'max':
                self._samples = max_samples.value

        # create an MSAA render buffer if self._samples > 1
        self.frameBufferMsaa = GL.GLuint()  # is zero if not configured
        if self._samples > 1:
            logging.info(
                'Samples > 1, creating multi-sample framebuffer with dimensions'
                '{w}x{h}.'.format(w=int(self._swapTextureSize[0]),
                                  h=int(self._swapTextureSize[1])))

            # multi-sample FBO and rander buffer
            GL.glGenFramebuffers(1, ctypes.byref(self.frameBufferMsaa))
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.frameBufferMsaa)

            # we don't need a multi-sample texture
            rb_color_msaa_id = GL.GLuint()
            GL.glGenRenderbuffers(1, ctypes.byref(rb_color_msaa_id))
            GL.glBindRenderbuffer(GL.GL_RENDERBUFFER, rb_color_msaa_id)
            GL.glRenderbufferStorageMultisample(
                GL.GL_RENDERBUFFER,
                self._samples,
                GL.GL_RGBA8,
                int(self._swapTextureSize[0]),
                int(self._swapTextureSize[1]))
            GL.glFramebufferRenderbuffer(
                GL.GL_FRAMEBUFFER,
                GL.GL_COLOR_ATTACHMENT0,
                GL.GL_RENDERBUFFER,
                rb_color_msaa_id)
            GL.glBindRenderbuffer(GL.GL_RENDERBUFFER, 0)

            rb_depth_msaa_id = GL.GLuint()
            GL.glGenRenderbuffers(1, ctypes.byref(rb_depth_msaa_id))
            GL.glBindRenderbuffer(GL.GL_RENDERBUFFER, rb_depth_msaa_id)
            GL.glRenderbufferStorageMultisample(
                GL.GL_RENDERBUFFER,
                self._samples,
                GL.GL_DEPTH24_STENCIL8,
                int(self._swapTextureSize[0]),
                int(self._swapTextureSize[1]))
            GL.glFramebufferRenderbuffer(
                GL.GL_FRAMEBUFFER,
                GL.GL_DEPTH_ATTACHMENT,
                GL.GL_RENDERBUFFER,
                rb_depth_msaa_id)
            GL.glFramebufferRenderbuffer(
                GL.GL_FRAMEBUFFER,
                GL.GL_STENCIL_ATTACHMENT,
                GL.GL_RENDERBUFFER,
                rb_depth_msaa_id)

            GL.glBindRenderbuffer(GL.GL_RENDERBUFFER, 0)
            GL.glClear(GL.GL_STENCIL_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)

        # create a frame buffer object as a render target for the HMD textures
        self.frameBuffer = GL.GLuint()
        GL.glGenFramebuffers(1, ctypes.byref(self.frameBuffer))
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.frameBuffer)

        # initialize the frame texture variable
        self.frameTexture = 0

        # create depth and stencil render buffers
        depth_rb_id = GL.GLuint()
        GL.glGenRenderbuffers(1, ctypes.byref(depth_rb_id))
        GL.glBindRenderbuffer(GL.GL_RENDERBUFFER, depth_rb_id)
        GL.glRenderbufferStorage(
            GL.GL_RENDERBUFFER,
            GL.GL_DEPTH24_STENCIL8,
            int(self._swapTextureSize[0]),
            int(self._swapTextureSize[1]))
        GL.glFramebufferRenderbuffer(
            GL.GL_FRAMEBUFFER,
            GL.GL_DEPTH_ATTACHMENT,
            GL.GL_RENDERBUFFER,
            depth_rb_id)
        GL.glFramebufferRenderbuffer(
            GL.GL_FRAMEBUFFER,
            GL.GL_STENCIL_ATTACHMENT,
            GL.GL_RENDERBUFFER,
            depth_rb_id)
        GL.glBindRenderbuffer(GL.GL_RENDERBUFFER, 0)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
        self._frameStencil = depth_rb_id  # should make this the MSAA's?

        GL.glClear(GL.GL_STENCIL_BUFFER_BIT)
        GL.glClear(GL.GL_DEPTH_BUFFER_BIT)

        # Setup the mirror texture framebuffer. The swap chain is managed
        # internally by PsychXR.
        self._mirrorFbo = GL.GLuint()
        GL.glGenFramebuffers(1, ctypes.byref(self._mirrorFbo))

        if self._mirrorRes is None:
            self._mirrorRes = self.__dict__['size']

        mirrorW, mirrorH = self._mirrorRes
        if libovr.success(libovr.createMirrorTexture(mirrorW, mirrorH)):
            logging.info(
                'Created mirror texture with dimensions {w} x {h}'.format(
                    w=mirrorW, h=mirrorH))
        else:
            _, msg = libovr.getLastErrorInfo()
            raise LibOVRError(msg)

        GL.glDisable(GL.GL_TEXTURE_2D)
        # GL.glClear(GL.GL_COLOR_BUFFER_BIT)

        return True  # assume the FBOs are complete for now

    def _resolveMSAA(self):
        """Resolve multisample anti-aliasing (MSAA). If MSAA is enabled, drawing
        operations are diverted to a special multisample render buffer. Pixel
        data must be 'resolved' by blitting it to the swap chain texture. If
        not, the texture will be blank.

        Notes
        -----
        You cannot perform operations on the default FBO (at frameBuffer) when
        MSAA is enabled. Any changes will be over-written when 'flip' is called.

        """
        # if multi-sampling is off just NOP
        if self._samples == 1:
            return

        # bind framebuffer
        GL.glBindFramebuffer(GL.GL_READ_FRAMEBUFFER, self.frameBufferMsaa)
        GL.glBindFramebuffer(GL.GL_DRAW_FRAMEBUFFER, self.frameBuffer)

        # bind the HMD swap texture to the draw buffer
        GL.glFramebufferTexture2D(
            GL.GL_DRAW_FRAMEBUFFER,
            GL.GL_COLOR_ATTACHMENT0,
            GL.GL_TEXTURE_2D,
            self.frameTexture,
            0)

        # blit the texture
        fbo_w, fbo_h = self._swapTextureSize
        GL.glViewport(0, 0, fbo_w, fbo_h)
        GL.glScissor(0, 0, fbo_w, fbo_h)
        GL.glBlitFramebuffer(
            0, 0, fbo_w, fbo_h,
            0, 0, fbo_w, fbo_h,  # flips texture
            GL.GL_COLOR_BUFFER_BIT,
            GL.GL_NEAREST)

        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)

    def _prepareMonoFrame(self, clear=True):
        """Prepare a frame for monoscopic rendering. This is called
        automatically after :func:`_startHmdFrame` if monoscopic rendering is
        enabled.

        """
        # bind the framebuffer, if MSAA is enabled binding the texture is
        # deferred until the MSAA buffer is resolved.
        if self._samples > 1:
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.frameBufferMsaa)
        else:
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.frameBuffer)
            GL.glFramebufferTexture2D(
                GL.GL_FRAMEBUFFER,
                GL.GL_COLOR_ATTACHMENT0,
                GL.GL_TEXTURE_2D,
                self.frameTexture,
                0)

        # use the mono viewport
        self.buffer = 'mono'
        GL.glEnable(GL.GL_SCISSOR_TEST)

        viewPort = libovr.getEyeRenderViewport(libovr.EYE_LEFT)  # mono mode
        GL.glViewport(*viewPort)
        GL.glScissor(*viewPort)
        GL.glDepthMask(GL.GL_TRUE)

        if clear:
            self.setColor(self.color)  # clear the texture to the window color
            GL.glClear(
                GL.GL_COLOR_BUFFER_BIT |
                GL.GL_DEPTH_BUFFER_BIT |
                GL.GL_STENCIL_BUFFER_BIT
            )

        # if self.sRGB:
        #    GL.glDisable(GL.GL_FRAMEBUFFER_SRGB)

        if self._samples > 1:
            GL.glEnable(GL.GL_MULTISAMPLE)

        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glEnable(GL.GL_BLEND)

    def setBuffer(self, buffer, clear=True):
        """Set the active stereo draw buffer.

        Warnings
        --------
        The window.Window.size property will return the buffer's dimensions in
        pixels instead of the window's when `setBuffer` is set to 'left' or
        'right'.

        Parameters
        ----------
        buffer : str
            View buffer to divert successive drawing operations to, can be
            either 'left' or 'right'.
        clear : boolean
            Clear the color, stencil and depth buffer.

        """
        # if monoscopic, nop
        if self._monoscopic:
            warnings.warn("`setBuffer` called in monoscopic mode.",
                          RuntimeWarning)
            return

        # check if the buffer name is valid
        if buffer not in ('left', 'right'):
            raise RuntimeError("Invalid buffer name specified.")

        # bind the framebuffer, if MSAA is enabled binding the texture is
        # deferred until the MSAA buffer is resolved.
        if self._samples > 1:
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.frameBufferMsaa)
        else:
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.frameBuffer)
            GL.glFramebufferTexture2D(
                GL.GL_FRAMEBUFFER,
                GL.GL_COLOR_ATTACHMENT0,
                GL.GL_TEXTURE_2D,
                self.frameTexture,
                0)

        self.buffer = buffer  # set buffer string
        GL.glEnable(GL.GL_SCISSOR_TEST)

        if buffer == 'left':
            viewPort = libovr.getEyeRenderViewport(libovr.EYE_LEFT)
            GL.glViewport(*viewPort)
            GL.glScissor(*viewPort)
        elif buffer == 'right':
            viewPort = libovr.getEyeRenderViewport(libovr.EYE_RIGHT)
            GL.glViewport(*viewPort)
            GL.glScissor(*viewPort)

        if clear:
            self.setColor(self.color)  # clear the texture to the window color
            GL.glClearDepth(1.0)
            GL.glDepthMask(GL.GL_TRUE)
            GL.glClear(
                GL.GL_COLOR_BUFFER_BIT |
                GL.GL_DEPTH_BUFFER_BIT |
                GL.GL_STENCIL_BUFFER_BIT)

        # if self.sRGB:
        #    GL.glDisable(GL.GL_FRAMEBUFFER_SRGB)

        if self._samples > 1:
            GL.glEnable(GL.GL_MULTISAMPLE)

        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glEnable(GL.GL_BLEND)

    def getPredictedDisplayTime(self):
        """Get the predicted time the next frame will be displayed.

        Returns
        -------
        float
            Absolute frame mid-point time for the given frame index in seconds.

        See Also
        --------


        """
        return libovr.getPredictedDisplayTime(self._frameIndex)

    def getTimeInSeconds(self):
        """Absolute time in seconds.

        Returns
        -------
        float
            Time in seconds.

        """
        return libovr.timeInSeconds()

    @property
    def viewMatrix(self):
        """Get the view matrix for the current eye buffer. Only valid after a
        :func:`calcEyePoses` call.

        """
        if not self._monoscopic:
            if self.buffer == 'left':
                return self._viewMatrix[libovr.EYE_LEFT]
            elif self.buffer == 'right':
                return self._viewMatrix[libovr.EYE_RIGHT]
        else:
            return self._viewMatrix

    @property
    def projectionMatrix(self):
        """Get the projection matrix for the current eye buffer."""
        if not self._monoscopic:
            if self.buffer == 'left':
                return self._projectionMatrix[libovr.EYE_LEFT]
            elif self.buffer == 'right':
                return self._projectionMatrix[libovr.EYE_RIGHT]
        else:
            return self._projectionMatrix

    @property
    def isBoundaryVisible(self):
        """True if the VR boundary is visible.
        """
        result, is_visible = libovr.getBoundaryVisible()
        return bool(is_visible)

    @property
    def boundaryClosetDistance(self):
        """Distance to the closest point of the boundary."""
        return self._boundaryTestResult.closestDistance

    def getBoundaryDimensions(self, boundaryType='PlayArea'):
        """Get boundary dimensions.

        Parameters
        ----------
        boundaryType : str
            Boundary type, can be 'PlayArea' or 'Outer'.

        Returns
        -------
        ndarray
            Dimensions of the boundary meters [x, y, z].

        """
        result, dims = libovr.getBoundaryDimensions(
            RIFT_BOUNDARY_TYPE[boundaryType])

        return dims

    @property
    def connectedControllers(self):
        """Connected controller types (`list` of `str`)"""
        controllers = libovr.getConnectedControllerTypes()
        ctrlKeys = {val: key for key, val in RIFT_CONTROLLER_TYPES.items()}

        return [ctrlKeys[ctrl] for ctrl in controllers]

    def updateInputState(self, controllers=None):
        """Update all connected controller states.

        Parameters
        ----------
        controllers : tuple or list of str, optional
            List of controllers to poll. If None, all available controllers will
            be polled.

        Examples
        --------

        Poll the state of specific controllers by name::

            controllers = ['XBox', 'Touch']
            updateInputState(controllers)

        """
        if controllers is None:
            toPoll = libovr.getConnectedControllerTypes()
        elif isinstance(controllers, (list, tuple,)):
            toPoll = [RIFT_CONTROLLER_TYPES[ctrl] for ctrl in controllers]
        else:
            raise TypeError("Argument 'controllers' must be iterable type.")

        for i in toPoll:
            result, t_sec = libovr.updateInputState(i)
            self.controllerPollTimes[i] = t_sec

    def _waitToBeginHmdFrame(self):
        """Wait until the HMD surfaces are available for rendering.
        """
        # First time this function is called, make True.
        if not self._allowHmdRendering:
            self._allowHmdRendering = True

        # update session status
        result, status = libovr.getSessionStatus()
        self._sessionStatus = status

        # Wait for the buffer to be freed by the compositor, this is like
        # waiting for v-sync.
        result = libovr.waitToBeginFrame(self._frameIndex)
        #if result == ovr.SUCCESS_NOT_VISIBLE:
        #    pass
        #self.updateInputState()  # poll controller states

        # # update the tracking state
        # if self.autoUpdatePoses:
        #     # get the current frame time
        #     absTime = libovr.getPredictedDisplayTime(self._frameIndex)
        #     # Get the current tracking state structure, estimated poses for the
        #     # head and hands are stored here. The latency marker for computing
        #     # motion-to-photon latency is set when this function is called.
        #     self.calcEyePoses()

    def _startHmdFrame(self):
        """Prepare to render an HMD frame. This must be called every frame
        before flipping or setting the view buffer.

        This function will wait until the HMD is ready to begin rendering before
        continuing. The current frame texture from the swap chain are pulled
        from the SDK and made available for binding.

        """
        # begin frame
        libovr.beginFrame(self._frameIndex)
        # get the next available buffer texture in the swap chain
        result, swapChainIdx = libovr.getTextureSwapChainCurrentIndex(
            libovr.TEXTURE_SWAP_CHAIN0)
        result, colorTextureId = libovr.getTextureSwapChainBufferGL(
            libovr.TEXTURE_SWAP_CHAIN0, swapChainIdx)
        self.frameTexture = colorTextureId

        # If mono mode, we want to configure the render framebuffer at this
        # point since 'setBuffer' will not be called.
        if self._monoscopic:
            self._prepareMonoFrame()

    def _startOfFlip(self):
        """Custom :py:class:`~Rift._startOfFlip` for HMD rendering. This
        finalizes the HMD texture before diverting drawing operations back to
        the on-screen window. This allows :py:class:`~Rift.flip` to swap the
        on-screen and HMD buffers when called. This function always returns
        `True`.

        Returns
        -------
        True

        """
        # Switch off multi-sampling
        GL.glDisable(GL.GL_MULTISAMPLE)

        if self._allowHmdRendering:
            # resolve MSAA buffers
            self._resolveMSAA()

            # commit current texture buffer to the swap chain
            libovr.commitTextureSwapChain(libovr.TEXTURE_SWAP_CHAIN0)

            # Call end_frame and increment the frame index, no more rendering to
            # HMD's view texture at this point.
            result, _ = libovr.endFrame(self._frameIndex)

            if libovr.failure(result):
                if result == libovr.ERROR_DISPLAY_LOST:  # display lost!
                    libovr.destroyMirrorTexture()
                    libovr.destroyTextureSwapChain(libovr.TEXTURE_SWAP_CHAIN0)
                    libovr.destroy()
                    libovr.shutdown()

                _, msg = libovr.getLastErrorInfo()
                raise LibOVRError(msg)

            self._frameIndex += 1  # increment frame index

        # Set to None so the 'size' attribute returns the on-screen window size.
        self.buffer = None

        # Make sure this is called after flipping, this updates VR information
        # and diverts rendering to the HMD texture.
        #self.callOnFlip(self._waitToBeginHmdFrame)

        # Call frame timing routines
        #self.callOnFlip(self._updatePerformanceStats)

        # This always returns True
        return True

    def flip(self, clearBuffer=True):
        """Submit view buffer images to the HMD's compositor for display at next
        V-SYNC and draw the mirror texture to the on-screen window. This must
        be called every frame.

        Parameters
        ----------
        clearBuffer : bool
            Clear the frame after flipping.

        Returns
        -------
        float
            Absolute time in seconds when control was given back to the
            application. The difference between the current and previous values
            should be very close to 1 / refreshRate of the HMD.

        Notes
        -----

        * The HMD compositor and application are asynchronous, therefore there is
          no guarantee that the timestamp returned by 'flip' corresponds to the
          exact vertical retrace time of the HMD.

        """
        # NOTE: Most of this code is shared with the regular Window's flip
        # function for compatibility. We're only concerned with calling the
        # _startOfFlip function and drawing the mirror texture to the onscreen
        # window. Display timing functions are kept in for now, but they are not
        # active.
        #

        flipThisFrame = self._startOfFlip()
        if flipThisFrame:
            self._prepareFBOrender()
            # need blit the framebuffer object to the actual back buffer
            result, mirrorTexId = libovr.getMirrorTexture()
            if libovr.failure(result):
                _, msg = libovr.getLastErrorInfo()
                raise LibOVRError(msg)

            # unbind the framebuffer as the render target
            GL.glBindFramebufferEXT(GL.GL_FRAMEBUFFER_EXT, 0)
            GL.glDisable(GL.GL_BLEND)
            stencilOn = GL.glIsEnabled(GL.GL_STENCIL_TEST)
            GL.glDisable(GL.GL_STENCIL_TEST)

            win_w, win_h = self.__dict__['size']
            GL.glViewport(0, 0, win_w, win_h)
            GL.glScissor(0, 0, win_w, win_h)

            # draw the mirror texture, if not anything drawn to the backbuffer
            # will be displayed instead
            if self._drawMirrorTex:
                # blit mirror texture
                GL.glBindFramebuffer(GL.GL_READ_FRAMEBUFFER, self._mirrorFbo)
                GL.glBindFramebuffer(GL.GL_DRAW_FRAMEBUFFER, 0)

                GL.glEnable(GL.GL_FRAMEBUFFER_SRGB)
                # bind the rift's texture to the framebuffer
                GL.glFramebufferTexture2D(
                    GL.GL_READ_FRAMEBUFFER,
                    GL.GL_COLOR_ATTACHMENT0,
                    GL.GL_TEXTURE_2D, mirrorTexId, 0)

                tex_w, tex_h = self._mirrorRes
                GL.glViewport(0, 0, win_w, win_h)
                GL.glScissor(0, 0, win_w, win_h)
                GL.glClearColor(0.0, 0.0, 0.0, 1.0)
                GL.glClear(GL.GL_COLOR_BUFFER_BIT)
                GL.glBlitFramebuffer(0, 0, tex_w, tex_h,
                                     0, win_h, win_w, 0,  # flips texture
                                     GL.GL_COLOR_BUFFER_BIT,
                                     GL.GL_LINEAR)

                GL.glDisable(GL.GL_FRAMEBUFFER_SRGB)
                GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)

            self._finishFBOrender()

        # call this before flip() whether FBO was used or not
        self._afterFBOrender()

        # flip the mirror window
        self.backend.swapBuffers(flipThisFrame)

        if flipThisFrame:
            # set rendering back to the framebuffer object
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
            #GL.glReadBuffer(GL.GL_BACK)
            #GL.glDrawBuffer(GL.GL_BACK)
            GL.glClearColor(0.0, 0.0, 0.0, 1.0)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT)
            # set to no active rendering texture
            GL.glActiveTexture(GL.GL_TEXTURE0)
            GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
            if stencilOn:
                GL.glEnable(GL.GL_STENCIL_TEST)

        # reset returned buffer for next frame
        self._endOfFlip(clearBuffer)

        # wait until surfaces are available for drawing
        self._waitToBeginHmdFrame()

        # get timestamp at the point control is handed back to the application
        now = logging.defaultClock.getTime()

        # run other functions immediately after flip completes
        for callEntry in self._toCall:
            callEntry['function'](*callEntry['args'], **callEntry['kwargs'])
        del self._toCall[:]

        # do bookkeeping
        if self.recordFrameIntervals:
            self.frames += 1
            deltaT = now - self.lastFrameT
            self.lastFrameT = now
            if self.recordFrameIntervalsJustTurnedOn:  # don't do anything
                self.recordFrameIntervalsJustTurnedOn = False
            else:  # past the first frame since turned on
                self.frameIntervals.append(deltaT)
                if deltaT > self.refreshThreshold:
                    self.nDroppedFrames += 1
                    if self.nDroppedFrames < reportNDroppedFrames:
                        txt = 't of last frame was %.2fms (=1/%i)'
                        msg = txt % (deltaT * 1000, 1 / deltaT)
                        logging.warning(msg, t=now)
                    elif self.nDroppedFrames == reportNDroppedFrames:
                        logging.warning("Multiple dropped frames have "
                                        "occurred - I'll stop bothering you "
                                        "about them!")

        # log events
        for logEntry in self._toLog:
            # {'msg':msg, 'level':level, 'obj':copy.copy(obj)}
            logging.log(msg=logEntry['msg'],
                        level=logEntry['level'],
                        t=now,
                        obj=logEntry['obj'])
        del self._toLog[:]

        # keep the system awake (prevent screen-saver or sleep)
        platform_specific.sendStayAwake()

        return now

    def multiplyViewMatrixGL(self):
        """Multiply the local eye pose transformation modelMatrix obtained from the
        SDK using ``glMultMatrixf``. The modelMatrix used depends on the current eye
        buffer set by :func:`setBuffer`.

        Returns
        -------
        None

        """
        if not self._legacyOpenGL:
            return

        if not self._monoscopic:
            if self.buffer == 'left':
                GL.glMultTransposeMatrixf(
                    self._viewMatrix[0].flatten().ctypes.data_as(
                        ctypes.POINTER(ctypes.c_float)))
            elif self.buffer == 'right':
                GL.glMultTransposeMatrixf(
                    self._viewMatrix[1].flatten().ctypes.data_as(
                        ctypes.POINTER(ctypes.c_float)))
        else:
            GL.glMultTransposeMatrixf(self._viewMatrix.ctypes.data_as(
                        ctypes.POINTER(ctypes.c_float)))

    def multiplyProjectionMatrixGL(self):
        """Multiply the current projection modelMatrix obtained from the SDK using
        ``glMultMatrixf``. The modelMatrix used depends on the current eye buffer set
        by :func:`setBuffer`.

        """
        if not self._legacyOpenGL:
            return

        if not self._monoscopic:
            if self.buffer == 'left':
                GL.glMultTransposeMatrixf(
                    self._projectionMatrix[0].flatten().ctypes.data_as(
                        ctypes.POINTER(ctypes.c_float)))
            elif self.buffer == 'right':
                GL.glMultTransposeMatrixf(
                    self._projectionMatrix[1].flatten().ctypes.data_as(
                        ctypes.POINTER(ctypes.c_float)))
        else:
            GL.glMultTransposeMatrixf(
                self._projectionMatrix.flatten().ctypes.data_as(
                    ctypes.POINTER(ctypes.c_float)))

    def setRiftView(self, clearDepth=True):
        """Set head-mounted display view. Gets the projection and view matrices
        from the HMD and applies them.

        Note: This only has an effect if using Rift in legacy immediate mode
        OpenGL.

        Parameters
        ----------
        clearDepth : bool
            Clear the depth buffer prior after configuring the view parameters.

        """
        if self._legacyOpenGL:
            GL.glMatrixMode(GL.GL_PROJECTION)
            GL.glLoadIdentity()
            self.multiplyProjectionMatrixGL()

            GL.glMatrixMode(GL.GL_MODELVIEW)
            GL.glLoadIdentity()
            self.multiplyViewMatrixGL()

        if clearDepth:
            GL.glClear(GL.GL_DEPTH_BUFFER_BIT)

    def setDefaultView(self, clearDepth=True):
        """Return to default projection. Call this before drawing PsychoPy's
        2D stimuli after a stereo projection change.

        Note: This only has an effect if using Rift in legacy immediate mode
        OpenGL.

        Parameters
        ----------
        clearDepth : bool
            Clear the depth buffer prior after configuring the view parameters.

        """
        if self._legacyOpenGL:
            GL.glMatrixMode(GL.GL_PROJECTION)
            GL.glLoadIdentity()
            GL.glOrtho(-1, 1, -1, 1, -1, 1)
            GL.glMatrixMode(GL.GL_MODELVIEW)
            GL.glLoadIdentity()

        if clearDepth:
            GL.glClear(GL.GL_DEPTH_BUFFER_BIT)

    def _updateProjectionMatrix(self):
        """Update or re-calculate projection matrices based on the current
        render descriptor configuration.
        """
        if not self._monoscopic:
            libovr.getEyeProjectionMatrix(
                libovr.EYE_LEFT,
                self._nearClip,
                self._farClip,
                self._projectionMatrix[0])
            libovr.getEyeProjectionMatrix(
                libovr.EYE_RIGHT,
                self._nearClip,
                self._farClip,
                self._projectionMatrix[1])
        else:
            libovr.getEyeProjectionMatrix(
                libovr.EYE_LEFT,
                self._nearClip,
                self._farClip,
                self._projectionMatrix)

    def getThumbstickValues(self, controller='Xbox', deadzone=False):
        """Get controller thumbstick values.

        Parameters
        ----------
        controller : str
            Name of the controller to get thumbstick values. Possible values for
            `controller` are 'Xbox', 'Touch', 'RTouch', 'LTouch', 'Object0',
            'Object1', 'Object2', and 'Object3'; the only devices with
            thumbsticks the SDK manages. For additional controllers, use
            PsychPy's built-in event or hardware support.
        deadzone : bool
            Apply the deadzone to thumbstick values. This pre-filters stick
            input to apply a dead-zone where 0.0 will be returned if the sticks
            return a displacement within -0.2746 to 0.2746.

        Returns
        -------
        tuple
            Left and right, X and Y thumbstick values. Axis displacements are
            represented in each tuple by a floats ranging from -1.0
            (full left/down) to 1.0 (full right/up). The returned values
            reflect the controller state since the last
            :py:class:`~Rift.updateInputState` or :py:class:`~Rift.flip` call.

        """
        return libovr.getThumbstickValues(controller, deadzone)

    def getIndexTriggerValues(self, controller='Xbox', deadzone=False):
        """Get the values of the index triggers.

        Parameters
        ----------
        controller : str
            Name of the controller to get index trigger values. Possible values
            for `controller` are 'Xbox', 'Touch', 'RTouch', 'LTouch', 'Object0',
            'Object1', 'Object2', and 'Object3'; the only devices with index
            triggers the SDK manages. For additional controllers, use PsychPy's
            built-in event or hardware support.
        deadzone : bool
            Apply the deadzone to index trigger values. This pre-filters stick
            input to apply a dead-zone where 0.0 will be returned if the trigger
            returns a displacement within 0.2746.

        Returns
        -------
        tuple of float
            Left and right index trigger values. Displacements are represented
            as `tuple` of two float representing the left anr right displacement
            values, which range from 0.0 to 1.0. The returned values reflect the
            controller state since the last :py:class:`~Rift.updateInputState`
            or :py:class:`~Rift.flip` call.

        """
        return libovr.getIndexTriggerValues(RIFT_CONTROLLER_TYPES[controller],
                                            deadzone)

    def getHandTriggerValues(self, controller='Touch', deadzone=False):
        """Get the values of the hand triggers.

        Parameters
        ----------
        controller : str
            Name of the controller to get hand trigger values. Possible values
            for `controller` are 'Touch', 'RTouch', 'LTouch', 'Object0',
            'Object1', 'Object2', and 'Object3'; the only devices with hand
            triggers the SDK manages. For additional controllers, use PsychPy's
            built-in event or hardware support.
        deadzone : bool
            Apply the deadzone to hand trigger values. This pre-filters stick
            input to apply a dead-zone where 0.0 will be returned if the trigger
            returns a displacement within 0.2746.

        Returns
        -------
        tuple
            Left and right hand trigger values. Displacements are represented
            as `tuple` of two float representing the left anr right displacement
            values, which range from 0.0 to 1.0. The returned values reflect the
            controller state since the last :py:class:`~Rift.updateInputState`
            or :py:class:`~Rift.flip` call.

        """
        return libovr.getHandTriggerValues(RIFT_CONTROLLER_TYPES[controller],
                                           deadzone)

    def getButtons(self, buttons, controller='Xbox', testState='continuous'):
        """Get button states from a controller.

        Returns `True` if any names specified to `buttons` reflect `testState`
        since the last :py:class:`~Rift.updateInputState` or
        :py:class:`~Rift.flip` call. If multiple button names are specified as a
        `list` or `tuple` to `buttons`, multiple button states are tested,
        returning `True` if all the buttons presently satisfy the `testState`.
        Note that not all controllers available share the same buttons. If a
        button is not available, this function will always return `False`.

        Parameters
        ----------
        buttons : `list` of `str` or `str`
            Buttons to test. Valid `buttons` names are 'A', 'B', 'RThumb',
            'RShoulder' 'X', 'Y', 'LThumb', 'LShoulder', 'Up', 'Down', 'Left',
            'Right', 'Enter', 'Back', 'VolUp', 'VolDown', and 'Home'. Names can
            be passed as a `list` to test multiple button states.
        controller : `str`
            Controller name.
        testState : `str`
            State to test. Valid values are:

            * **continuous** - Button is presently being held down.
            * **rising** or **pressed** - Button has been *pressed* since
              the last update.
            * **falling** or **released** - Button has been *released* since
              the last update.

        Returns
        -------
        tuple of bool, float
            Button state and timestamp in seconds the controller was polled.

        Examples
        --------

        Check if the 'Enter' button on the Oculus remote was released::

            isPressed = hmd.getButtons(['Enter'], 'Remote', 'falling')

        Check if the 'A' button was pressed on the touch controller::

            isPressed = hmd.getButtons(['A'], 'Touch', 'pressed')

        """
        if isinstance(buttons, str):  # single value
            _, state = libovr.getButton(
                RIFT_CONTROLLER_TYPES[controller],
                RIFT_BUTTON_TYPES[buttons],
                testState)
            return state, self.controllerPollTimes[controller]
        elif isinstance(buttons, (list, tuple,)):  # combine buttons
            buttonBits = 0x00000000
            for buttonName in buttons:
                buttonBits |= RIFT_BUTTON_TYPES[buttonName]
            _, state = libovr.getButton(
                RIFT_CONTROLLER_TYPES[controller],
                buttonBits,
                testState)
            return state, self.controllerPollTimes[controller]
        elif isinstance(buttons, int):  # using enums directly
            _, state = libovr.getButton(
                RIFT_CONTROLLER_TYPES[controller],
                buttons,
                testState)
            return state, self.controllerPollTimes[controller]
        else:
            ValueError("Invalid 'buttonNames' specified.")

    def startHaptics(self, controller, frequency='low', amplitude=1.0):
        """Start haptic feedback (vibration).

        Vibration is constant at fixed frequency and amplitude. Vibration lasts
        2.5 seconds, so this function needs to be called more often than that
        for sustained vibration. Only controllers which support vibration can be
        used here.

        There are only two frequencies permitted 'high' and 'low', however,
        amplitude can vary from 0.0 to 1.0. Specifying `frequency`='off' stops
        vibration if in progress.

        Parameters
        ----------
        controller : str
            Name of the controller to vibrate.
        frequency : str
            Vibration frequency. Valid values are: 'off', 'low', or 'high'.
        amplitude : float
            Vibration amplitude in the range of [0.0 and 1.0]. Values outside
            this range are clamped.

        """
        libovr.setControllerVibration(
            RIFT_CONTROLLER_TYPES[controller],
            frequency,
            amplitude)

    def stopHaptics(self, controller):
        """Stop haptic feedback.

        Convenience function to stop controller vibration initiated by the last
        :py:class:`~Rift.vibrateController` call. This is the same as calling
        ``vibrateController(controller, frequency='off')``.

        Parameters
        ----------
        controller : str
            Name of the controller to stop vibrating.

        """
        libovr.setControllerVibration(
            RIFT_CONTROLLER_TYPES[controller], 'off', 0.0)

    @staticmethod
    def createHapticsBuffer(samples):
        """Create a new haptics buffer.

        A haptics buffer is object which stores vibration amplitude samples for
        playback through the Touch controllers. To play a haptics buffer, pass
        it to :py:method:`submitHapticsBuffer`.

        Parameters
        ----------
        samples : array_like
            1-D array of amplitude samples, ranging from 0 to 1. Values outside
            of this range will be clipped. The buffer must not exceed
            `HAPTICS_BUFFER_SAMPLES_MAX` samples, any additional samples will be
            dropped.

        Returns
        -------
        LibOVRHapticsBuffer
            Haptics buffer object.

        Notes
        -----
        Methods `startHaptics` and `stopHaptics` cannot be used interchangeably
        with this function.

        Examples
        --------
        Create a haptics buffer where vibration amplitude ramps down over the
        course of playback::

            samples = np.linspace(
                1.0, 0.0, num=HAPTICS_BUFFER_SAMPLES_MAX-1, dtype=np.float32)
            hbuff = Rift.createHapticsBuffer(samples)

            # vibrate right Touch controller
            hmd.submitControllerVibration(CONTROLLER_TYPE_RTOUCH, hbuff)

        """
        if len(samples) > libovr.HAPTICS_BUFFER_SAMPLES_MAX:
            samples = samples[:libovr.HAPTICS_BUFFER_SAMPLES_MAX]

        return libovr.LibOVRHapticsBuffer(samples)

    def submitControllerVibration(self, controller, hapticsBuffer):
        """Submit a haptics buffer to begin controller vibration.

        Parameters
        ----------
        controller : str
            Name of controller to vibrate.
        hapticsBuffer : LibOVRHapticsBuffer
            Haptics buffer to playback.

        Notes
        -----
        Methods `startHaptics` and `stopHaptics` cannot be used interchangeably
        with this function.

        """
        libovr.submitControllerVibration(
            RIFT_CONTROLLER_TYPES[controller], hapticsBuffer)

    @staticmethod
    def createPose(pos=(0., 0., 0.), ori=(0., 0., 0., 1.)):
        """Create a new Rift pose object (``psychxr.libovr.LibOVRPose``).

        `LibOVRPose` is used to represent a rigid body pose mainly for use with the
        PsychXR's LibOVR module. There are several methods associated with the
        object to manipulate the pose.

        Parameters
        ----------
        pos : tuple, list, or ndarray of float
            Position vector/coordinate (x, y, z).
        ori : tuple, list, or ndarray of float
            Orientation quaternion (x, y, z, w).

        Returns
        -------
        LibOVRPose
            Object representing a rigid body pose for use with LibOVR.

        """
        return libovr.LibOVRPose(pos, ori)

    # def getTouches(self, touchNames, stateMode='continuous'):
    #     """Returns True if any buttons are touched using sensors. This feature
    #     is used to estimate finger poses and can be used to read gestures. An
    #     example of a possible use case is a pointing task, where responses are
    #     only valid if the user's index finger is extended away from the index
    #     trigger button.
    #
    #     Currently, this feature is only available with the Oculus Touch
    #     controllers.
    #
    #     Returns
    #     -------
    #     None
    #
    #     """
    #     return ovr.getTouches('Touch', touchNames, stateMode)



