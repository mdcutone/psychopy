import threading


class IMUSample:
    """Represents a sample from an Inertial Measurement Unit (IMU) sensor.

    Parameters
    ----------
    timestamp : float
        Timestamp of the sample.
    linearAcceleration : tuple
        Linear acceleration of the sample.
    linearVelocity : tuple
        Linear velocity of the sample.
    angularAcceleration : tuple
        Angular acceleration of the sample.
    angularVelocity : tuple
        Angular velocity of the sample.
    gravityVector : tuple
        Gravity vector of the sample.
    orientation : tuple
        Orientation of the sample.
    magneticField : tuple
        Magnetic field of the sample.
    temperature : float
        Device temperature of the sample.

    """
    def __init__(
            self, 
            timestamp=-1.0, 
            linearAcceleration=None, 
            linearVelocity=None,
            angularAcceleration=None, 
            angularVelocity=None, 
            gravityVector=None, 
            orientation=None, 
            magneticField=None, 
            temperature=None):
        self._timestamp = None
        self._linearAcceleration = None
        self._linearVelocity = None
        self._angularAcceleration = None
        self._angularVelocity = None
        self._gravityVector = None
        self._orientation = None
        self._magneticField = None
        self._temperature = None

    @property
    def timestamp(self):
        """Returns the timestamp of the sample.
        """
        return self._timestamp
    
    @property
    def linearAcceleration(self):
        """Returns the linear acceleration of the sample.
        """
        return self._linearAcceleration
    
    @property
    def linearVelocity(self):
        """Returns the linear velocity of the sample.
        """
        return self._linearVelocity
    
    @property
    def angularAcceleration(self):
        """Returns the angular acceleration of the sample.
        """
        return self._angularAcceleration
    
    @property
    def angularVelocity(self):
        """Returns the angular velocity of the sample.
        """
        return self._angularVelocity
    
    @property
    def gravityVector(self):
        """Returns the gravity vector of the sample.
        """
        return self._gravityVector
    
    @property
    def orientation(self):
        """Returns the orientation of the sample.
        """
        return self._orientation
    
    @property
    def magneticField(self):
        """Returns the magnetic field of the sample.
        """
        return self._magneticField
    
    @property
    def temperature(self):
        """Returns device temperature of the sample.
        """
        return self._temperature
    
    def __del__(self):
        pass
    



class BaseIMU:
    """Base class for Inertial Measurement Unit (IMU) sensors.
    """
    _deviceName = ''
    _deviceType = ''
    _deviceVersion = ''
    _deviceManufacturer = ''
    _capabilities = {}

    def __init__(self, *args, **kwargs):
        self._interface = None  # Interface to the sensor

    @property
    def deviceName(self):
        """Returns the name of the sensor.
        """
        return self._deviceName
    
    @property
    def deviceType(self):
        """Returns the type of the sensor.
        """
        return self._deviceType
    
    @property
    def deviceVersion(self):
        """Returns the version of the sensor.
        """
        return self._deviceVersion
    
    @property
    def deviceManufacturer(self):
        """Returns the manufacturer of the sensor.
        """
        return self._deviceManufacturer

    def getCapabilities(self):
        """Returns a dictionary of the sensor's capabilities.
        """
        pass

    def open(self):
        """Opens the sensor.
        """
        pass

    def isOpen(self):
        """Returns True if the sensor is open.
        """
        return self._interface is not None

    def close(self):
        """Closes the sensor.
        """
        pass

    def poll(self):
        """Polls the sensor for samples.
        """
        pass

    def getSamples(self):
        """Returns a list of samples from the sensor.
        """
        pass

    def __del__(self):
        pass


if __name__ == "__main__":
    pass