# pydaqs

A collection of wrapper functions for DAQ packages and libraries in Python. 

The wrappers follow a simple protocol for data acqusition, which is compatible with [axopy](https://github.com/axopy/axopy). 
Each device implements a `read()` method which returns a numpy array with shape (`n_channels`, `samples_per_read`). This method needs to be called in a loop from the main application. The frequency the method is called needs to be at least equal to the rate data are streamed from the DAQ device.

Mainly intended for internal use.
