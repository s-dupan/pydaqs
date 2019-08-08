from queue import Queue
from threading import Thread

import numpy as np
from cerebus import cbpy

from .base import _BaseDAQ

__all__ = ['Blackrock']


class Blackrock(_BaseDAQ):
    """
    Blacrock DAQ (e.g. Neuroport, Cerebus) stream reader device.

    Requires channel configuration to be set in Central Software Suite.

    Parameters
    ----------
    channels : list or tuple
        Channels to use.
    samples_per_read : int
        Number of samples per channel to read in each read operation.
    zero_based : bool, optional
        If ``True``, 0-based indexing is used for channel numbering. Default is
        ``False``.

    Attributes
    ----------
    connection_params : dict
            Connection parameters.
    """

    def __init__(self, channels, samples_per_read, zero_based=False,
                 units='raw'):
        self.channels = channels
        self.samples_per_read = samples_per_read
        self.zero_based = zero_based
        self.units = units


        self._initialize()

    def _initialize(self):
        result, return_dict = cbpy.open(
            connection='default',
            parameter=cbpy.defaultConParams())
        err_msg = "Connection to NSP/Central not established successfully."
        self._check_result(result, ConnectionError, err_msg)
        self.connection_params = return_dict

        # Buffer
        self.queue_ = [Queue() for _ in range(len(self.channels))]
        self.running_ = False

    def start(self):
        """
        Tell the device to begin streaming data.

        You should call ``read()`` soon after this.
        """
        buffer_parameter = {
            'double': True
        }
        result, _ = cbpy.trial_config(
            reset=True,
            buffer_parameter=buffer_parameter)
        err_msg = "Trial configuration was not set successfully."
        self._check_result(result, RuntimeError, err_msg)

        self.running_ = True
        self.thread_ = Thread(target=self.fetch, daemon=True)
        self.thread_.start()

    def fetch(self):
        while self.running_:
            result, trial = cbpy.trial_continuous(reset=True)
            for channel_list in trial:
                channel_number = channel_list[0]
                if channel_number in self.channels:
                    ind = self.channels.index(channel_number)
                    channel_data = channel_list[1]
                    for sample in channel_data:
                        self.queue_[ind].put(sample)

    def read(self):
        """
        Request a sample of data from the device.

        This is a blocking method, meaning it returns only once the requested
        number of samples are available.

        Returns
        -------
        data : ndarray, shape=(total_signals, num_samples)
            Data read from the device. Each channel is a row and each column
            is a point in time.
        """
        data = np.zeros((len(self.channels), self.samples_per_read))
        for sample in range(self.samples_per_read):
            for channel in range(len(self.channels)):
                data[channel, sample] = self.queue_[channel].get()

        return data

    def stop(self):
        """Tell the device to stop streaming data."""
        self.running_ = False
        result = cbpy.close()
        err_msg = "Connection to NSP/Central not closed successfully."
        self._check_result(result, ConnectionError, err_msg)

    def reset(self):
        """Restart the connection to NSP server."""
        self._initialize()

    def _check_result(self, result, error_type, error_msg):
        if result != 0:
            raise error_type(error_msg)
