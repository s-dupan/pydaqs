from threading import Thread, Lock
import time

import numpy as np
from serial import SerialException
from serial.tools import list_ports
from pyfirmata2 import Arduino, ArduinoMega, ArduinoDue, ArduinoNano
from .base import _BaseDAQ


class DebugPrinter(object):
    def __init__(self):
        self.last_read_time = None

    def print(self, sample):
        t = time.time()
        if self.last_read_time is None:
            pass
        else:
            ms = (t - self.last_read_time)
            debug_string = 'ms: {:.4f} sample: {}'.format(ms, sample)
            print(debug_string)
        self.last_read_time = t

    def reset(self):
        self.last_read_time = None


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
    arduino : string, optional (default: ``Arduino``)
        Select between Arduino boards supported by pyfirmata. Options are
        ``Arduino``, ``ArduinoMega``, ``port='COM5',`` and ``ArduinoNano``.
    name : string, optional (default: ``Arduino``)
        String which will be searched for when looking for device name on
        as a COM port.


    Attributes
    ----------
    board : arduino
        Arduino instance.
    """

    def __init__(self,
                 rate,
                 pins,
                 samples_per_read,
                 port=None,
                 baudrate=57600,
                 zero_based=True,
                 arduino='Arduino',
                 name='Arduino'):

        self.rate = rate
        self.pins = pins
        self.samples_per_read = samples_per_read
        self.port = port
        self.baudrate = baudrate
        self.zero_based = zero_based
        self.arduino = arduino
        self.name = name

        # If port is not given find the Arduino one
        if self.port is None:
            self.port = self.get_arduino_port()

        self._init()

    def _init(self):
        self.pins_ = self.pins if self.zero_based else \
            list(map(lambda x: x-1, self.pins))

        if self.arduino == 'Arduino':
            _board = Arduino
        elif self.arduino == 'ArduinoMega':
            _board = ArduinoMega
        elif self.arduino == 'ArduinoDue':
            _board = ArduinoDue
        elif self.arduino == 'ArduinoNano':
            _board = ArduinoNano

        self.board = _board(self.port, baudrate=self.baudrate)

        self._resetboard()

        self.board.samplingOn(1000 / self.rate)
        self.board.analog[0].register_callback(self._callback)
        for pin in self.pins_:
            self.board.analog[pin].enable_reporting()
        self._lock = Lock()
        self._sample = 0
        self._buffer = np.zeros((len(self.pins_), self.samples_per_read))
        self._data = np.zeros((len(self.pins_), self.samples_per_read))
        self._data_ready = False

        self._debug_print = DebugPrinter()

    def __del__(self):
        """Call stop() on destruct."""
        self.stop()

    def get_arduino_port(self):
        device = None
        comports = list_ports.comports()
        for port in comports:
            if port.description.startswith(self.name):
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
                # Introduces bug when using pyfirmata2 callback method
                # while self.board.bytes_available():
                #    self.board.iterate()

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

    def _resetboard(self):
        """
        Reset properties on the board.

        Improper shutdown / startup creates instability.
        """
        try:
            for pin in self.pins_:
                self.board.analog[pin].disable_reporting()       
        except (SerialException):
            pass
        except Exception as e:
            raise
        # Callback and sampling off
        self.board.analog[0].unregiser_callback()
        self.board.samplingOff()
        # Flush remaining data
        while self.board.bytes_available():
            self.board.iterate()

    def stop(self):
        self._resetboard()
        self.board.exit()

        self._flag = False

    def read(self):
        """
        Request a sample of data from the device.

        This method blocks (calls ``time.sleep()``) to emulate other data
        acquisition units which wait for the requested number of samples to be
        read. The amount of time to block is dependent on rate and on the
        samples_per_read. Calls will return with relatively constant frequency,
        assuming calls occur faster than required (i.e. processing doesn't fall behind).

        Returns
        -------
        data : ndarray, shape=(n_pins, samples_per_read)
            Data read from the device. Each pin is a row and each column
            is a point in time.
        """
        if self._flag:
            while (not self._data_ready):
                # cannot time smaller than 10 - 15 ms in Windows
                # this delays copying a chunk, not reading samples
                time.sleep(0.01)
            with self._lock:
                data = self._data
                self._data_ready = False
            #     s = self._sample
            # self._debug_print.print(s)
            return data

        else:
            raise SerialException("Serial port is closed.")

    def _callback(self, data):
        """
        Pyfirmata2 triggered callback.

        This callback is triggered by the Arduino. Data is read from the pins
        and copied to a buffer. Once the buffer is full is is copied to a read
        buffer. The samples_per_read relative to rate must allow sufficient
        time for the read buffer self._data to be output by the read() function.
        """
        with self._lock:
            for j, pin in enumerate(self.pins_):
                _s = self.board.analog[pin].read()
                if _s:
                    self._buffer[j, self._sample] = _s
            self._sample += 1
            if (self._sample >= self.samples_per_read):
                self._data = self._buffer
                self._data_ready = True
                self._sample = 0
