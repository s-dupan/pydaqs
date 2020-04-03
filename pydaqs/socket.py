import socket
import struct

import numpy as np

from .base import _BaseDAQ

__all__ = ['TCPSocketReader', 'UDPSocketReader']


class _SocketReader(_BaseDAQ):
    """
    Base class for Socket reader devices

    Warning: This class should not be used directly.
    Use derived classes instead.
    """

    def __init__(
            self,
            ip,
            port,
            array_len,
            samples_per_read,
            precision,
            timeout):
        self.ip = ip
        self.port = port
        self.array_len = array_len
        self.samples_per_read = samples_per_read
        self.precision = precision
        self.timeout = timeout

        self._init()

    def _init(self):
        if self.precision == 'single':
            self._format = 'f'
            self._bytes_per_float = 4
        elif self.precision == 'double':
            self._format = 'd'
            self._bytes_per_float = 8
        else:
            raise ValueError(
                "Precision must be either ``single`` or ``double``, but "
                "``{}`` was provided.".format(self.precision))

        self._fmt = '<' + self._format * self.array_len * self.samples_per_read
        self._lenmsg = self.samples_per_read * self.array_len * \
            self._bytes_per_float

    def stop(self):
        self.socket.close()


class TCPSocketReader(_SocketReader):
    """
    TCP socket reader.

    Requires the MyoConnect application to be running.

    Parameters
    ----------
    ip : str
        Socket IP address.
    port : int
        Port number.
    array_len : int
        Length of array being streamed.
    samples_per_read : int
        Number of samples per channel to read in each read operation.
    precision : str {'single', 'double'}
        Floating point precision.
    timeout : float, optional
        Socket timeout time. Default is None.
    """
    def __init__(
            self,
            ip,
            port,
            array_len,
            samples_per_read,
            precision='single',
            timeout=None):
        super(TCPSocketReader, self).__init__(
            ip=ip,
            port=port,
            array_len=array_len,
            samples_per_read=samples_per_read,
            precision=precision,
            timeout=timeout)

    def start(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.ip, self.port))
        self.socket.settimeout(self.timeout)

    def read(self):
        """
        Request a sample of data from the device.

        This is a blocking method, meaning it returns only once the requested
        number of samples are available.

        Returns
        -------
        data : ndarray, shape=(array_len, samples_per_read)
            Data read from the device. Each channel is a row and each column
            is a point in time.
        """
        lenp = 0
        packets = bytes()
        try:
            while lenp < self._lenmsg:
                rec_data = self.socket.recv(self._lenmsg - lenp)
                packets += rec_data
                lenp = len(packets)
        except socket.timeout:
            raise IOError()

        data = np.asarray(
            struct.unpack(self._fmt, packets))
        data = np.transpose(data.reshape((-1, self.array_len)))

        return data


class UDPSocketReader(_SocketReader):
    """
    UDP socket reader.

    Requires the MyoConnect application to be running.

    Parameters
    ----------
    ip : str
        Socket IP address.
    port : int
        Port number.
    array_len : int
        Length of array being streamed.
    samples_per_read : int
        Number of samples per channel to read in each read operation.
    precision : str {'single', 'double'}
        Floating point precision.
    timeout : float, optional
        Socket timeout time. Default is None.
    """
    def __init__(
            self,
            ip,
            port,
            array_len,
            samples_per_read,
            precision='single',
            timeout=None):
        super(UDPSocketReader, self).__init__(
            ip=ip,
            port=port,
            array_len=array_len,
            samples_per_read=samples_per_read,
            precision=precision,
            timeout=timeout)

    def start(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((self.ip, self.port))
        self.socket.settimeout(self.timeout)

    def read(self):
        """
        Request a sample of data from the device.

        This is a blocking method, meaning it returns only once the requested
        number of samples are available.

        Returns
        -------
        data : ndarray, shape=(array_len, samples_per_read)
            Data read from the device. Each channel is a row and each column
            is a point in time.
        """
        lenp = 0
        packets = bytes()
        try:
            while lenp < self._lenmsg:
                rec_data, _ = self.socket.recvfrom(self._lenmsg - lenp)
                packets += rec_data
                lenp = len(packets)
        except socket.timeout:
            raise IOError()

        data = np.asarray(
            struct.unpack(self._fmt, packets))
        data = np.transpose(data.reshape((-1, self.array_len)))

        return data
