# pydaqs

A collection of wrapper functions for DAQ packages and libraries in Python. 

The wrappers follow a simple protocol for data acqusition, which is compatible with [axopy](https://github.com/axopy/axopy). 
Each device implements a `read()` method which returns a numpy array with shape (`n_channels`, `samples_per_read`). This method needs to be called in a loop from the main application. The frequency the method is called needs to be at least equal to the rate data are streamed from the DAQ device.

Mainly intended for internal use.

Package requirements:

* MYO armband: [myo-python](https://github.com/NiklasRosenstein/myo-python)
* NI DAQs: [nidaqmx-python](https://github.com/ni/nidaqmx-python)
* Blackrock hardware (Cerebus, Neuroport): [CereLink](https://github.com/dashesy/CereLink)

Note that some DAQs also require proprietary software to be running concurrentely for data acquistion to work.

* Myo armband: Armband manager
* Blackrock harware (Cerebus, Neuroport): Central Software Suite
