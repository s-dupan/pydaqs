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

    Attributes
    ----------
    connection_params : dict
            Connection parameters.
    """

    def __init__(self, channels, samples_per_read):
        self.channels = channels
        self.samples_per_read = samples_per_read

        self._initialize()

    def _initialize(self):
        result, return_dict = cbpy.open(
            connection='default',
            parameter=cbpy.defaultConParams())
        err_msg = "Connection to NSP/Central not established successfully."
        self._check_result(result, ConnectionError, err_msg)
        self.connection_params = return_dict

    def start(self):
        """
        Tell the device to begin streaming data.

        You should call ``read()`` soon after this.
        """
        buffer_parameter = {
            'double': True,
            'continuous_length': self.samples_per_read
        }
        range_parameter = {
            'begin_channel': self.channels[0],
            'end_channel': self.channels[-1]
        }
        result, _ = cbpy.trial_config(
            reset=True,
            buffer_parameter=buffer_parameter,
            range_parameter=range_parameter)
        err_msg = "Trial configuration was not set successfully."
        self._check_result(result, RuntimeError, err_msg)

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
        result, trial = cbpy.trial_continuous(reset=True)
        trial.sort(key=lambda x: x[0])  # Sort by increasing channel number
        for i, channel_list in enumerate(trial):
            data[i, :] = channel_list[1]

        return data

    def stop(self):
        """Tell the device to stop streaming data."""
        result = cbpy.close()
        err_msg = "Connection to NSP/Central not closed successfully."
        self._check_result(result, ConnectionError, err_msg)

    def reset(self):
        """Restart the connection to NSP server."""
        self._initialize()

    def _check_result(self, result, error_type, error_msg):
        if result != 0:
            raise error_type(error_msg)
