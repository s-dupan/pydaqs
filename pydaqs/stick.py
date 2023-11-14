from axopy.gui.main import get_qtapp
import numpy as np
import time

from PyQt5 import QtCore
import pygame

import queue

class _Sleeper(object):

    def __init__(self, read_time):
        self.read_time = read_time
        self.last_read_time = None

    def sleep(self):
        t = time.time()
        if self.last_read_time is None:
            time.sleep(self.read_time)
        else:
            try:
                time.sleep(self.read_time - (t - self.last_read_time))
            except ValueError:
                # if we're not meeting real-time requirement, don't wait
                pass

        self.last_read_time = time.time()

    def reset(self):
        self.last_read_time = None


class Stick(QtCore.QObject):
    def __init__(self, rate = 1000, dev_id = 0, mode = 'full'):
        super(Stick, self).__init__()
        self.data_queue = queue.Queue()
        self.rate = rate
        self.dev_id = dev_id
        self.mode = mode

        pygame.display.init()
        pygame.joystick.init()

        self._sleeper = _Sleeper(1.0 / rate)

    def start(self):
        self.controller = pygame.joystick.Joystick(self.dev_id)
        self.controller.init()
        get_qtapp().installEventFilter(self)
        self._dataPre = np.zeros([self.controller.get_numaxes() + self.controller.get_numbuttons(), 1])

    def read(self):
        self._sleeper.sleep()
        pygame.event.pump()
        for i in range(0, self.controller.get_numaxes()):
            self._dataPre[i] = self.controller.get_axis(i)
        for i in range(0, self.controller.get_numbuttons()):
            self._dataPre[i+self.controller.get_numaxes()] = self.controller.get_button(i)
        if(self.mode == 'full'):
            self._data = self._dataPre
        elif(self.mode == 'divaxis'):
            self._data = np.zeros([4, 1])

            # to be analogues with EMG, we split the axis into two (left/right and up/down)
            if self._dataPre[0] <= 0:
                self._data[0] = abs(self._dataPre[0])
                self._data[1] = 0
            else:
                self._data[0] = 0
                self._data[1] = abs((self._dataPre[0]))

            if self._dataPre[1] <= 0:
                self._data[2] = abs(self._dataPre[1])
                self._data[3] = 0
            else:
                self._data[2] = 0
                self._data[3] = abs((self._dataPre[1]))

        pygame.event.clear(pump=True)
        out = self._data.copy()
        self._data *= 0
        self._dataPre *= 0
        return out

    def stop(self):
        get_qtapp().removeEventFilter(self)

    def reset(self):
        self._sleeper.reset()
        self.data_queue.queue.clear()