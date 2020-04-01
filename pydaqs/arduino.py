from threading import Thread
import time

import numpy as np
from serial import SerialException
from serial.tools import list_ports
from pyfirmata import Arduino
from axopy.daq import _Sleeper

from .base import _BaseDAQ


class ArduinoDAQ(_BaseDAQ):
    """
    Arduino DAQ stream reader device for analog inputs.

    Requires Firmata firmware to be uploaded on the Arduino. Has been tested
    with ``SimpleAnalogFirmata`` and ``StandardFirmata``, both of them provided
    as examples in the Arduino IDE.

    Parameters
    ----------
    rate : float
        Sampling rate. Maximum allowed with the default serial parameter
        configuration  is around 1 kHz. Higher values are allowed, but
        will result in oversampling.
    pins : list of integers
        Analog pins to read data from.
    samples_per_read : int
        Number of samples to read in each read operation.
    port : str, optional (default: None)
        Serial port name (e.g., 'COM1' in Windows). If not provided, it will be
        inferred.
    baudrate : int, optional (default: 57600)
        Serial communication baud rate. If a non-default value is provided,
        the baud rate needs also to be updated in the arduino firmwire file.
    zero_based : bool, optional
        If ``True``, 0-based indexing is used for pin numbering. Default is
        ``True``.

    Attributes
    ----------
    board : arduino
        Arduino instance.
    sleeper : sleeper
        Sleeper instance required to implement the desired sampling rate.
    """

    def __init__(self,
                 rate,
                 pins,
                 samples_per_read,
                 port=None,
                 baudrate=57600,
                 zero_based=True):

        # If port is not given find the Arduino one
        if port is None:
            port = self.get_arduino_port()

        self.rate = rate
        self.pins = pins
        self.samples_per_read = samples_per_read
        self.port = port
        self.baudrate = baudrate
        self.zero_based = zero_based

        self._init()

    def _init(self):
        self.pins_ = self.pins if self.zero_based else \
            list(map(lambda x: x-1, self.pins))
        self.board = Arduino(self.port, baudrate=self.baudrate)
        for pin in self.pins_:
            self.board.analog[pin].enable_reporting()

        self.sleeper = _Sleeper(self.samples_per_read/self.rate)

    def __del__(self):
        """Call stop() on destruct."""
        self.stop()

    def get_arduino_port(self):
        device = None
        comports = list_ports.comports()
        for port in comports:
            if port.description.startswith('Arduino'):
                device = port.device

        if device is None:
            raise Exception("Arduino COM port not found.")
        else:
            return device

    def start(self):
        if not self.board.sp.is_open:
            self.board.sp.open()

        self._flag = True
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while self._flag:
            try:
                while self.board.bytes_available():
                    self.board.iterate()
                # 6 analog inputs X 10 bits/input
                time.sleep(1/(self.baudrate/60))
            except (AttributeError, TypeError, SerialException, OSError):
                # this way we can kill the thread by setting the board object
                # to None, or when the serial port is closed by board.exit()
                break
            except Exception as e:
                # catch 'error: Bad file descriptor'
                # iterate may be called while the serial port is being closed,
                # causing an "error: (9, 'Bad file descriptor')"
                if getattr(e, "errno", None) == 9:
                    break
                try:
                    if e[0] == 9:
                        break
                except (IndexError):
                    pass
                raise

    def stop(self):
        self._flag = False
        self.board.exit()

    def read(self):
        """
        Request a sample of data from the device.

        This method blocks (calls ``time.sleep()``) to emulate other data
        acquisition units which wait for the requested number of samples to be
        read. The amount of time to block is calculated such that consecutive
        calls will always return with constant frequency, assuming the calls
        occur faster than required (i.e. processing doesn't fall behind).

        Returns
        -------
        data : ndarray, shape=(n_pins, samples_per_read)
            Data read from the device. Each pin is a row and each column
            is a point in time.
        """
        if self._flag:
            self.sleeper.sleep()
            data = np.zeros((len(self.pins_), self.samples_per_read))
            for i in range(self.samples_per_read):
                for j, pin in enumerate(self.pins_):
                    data[j, i] = self.board.analog[pin].read()

            return data
        else:
            raise SerialException("Serial port is closed.")
