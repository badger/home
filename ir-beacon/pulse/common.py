# SPDX-FileCopyrightText: 2025 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

from machine import Pin
from collections import namedtuple

# Tuple for storing pulse parameters
Pulse = namedtuple("Pulse", ("burst", "idle"))


# Class for easily having optional debug pins
class DebugPin:
    def __init__(self, *args):
        if len(args) > 0 and args[0] is not None:
            self.__pin = Pin(*args)
            self.on = self.__pin.on
            self.off = self.__pin.off
        else:
            self.on = self.__dummy
            self.off = self.__dummy

    def __dummy(self):
        pass
