# SPDX-FileCopyrightText: 2025 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

from rp2 import StateMachine
from machine import Pin, mem32
from .pio.tx import pulsesender, pulsesender_debug, CLOCKS_PER_CYCLE
from .common import DebugPin


# RP2 Register Constants
PIO_BASE = (0x50200000,
            0x50300000,
            0x50400000)  # RP2350 Only

PIO_FDEBUG_OFFSET = const(0x00000008)
PIO_FDEBUG_TXSTALL_LSB = 24

PIO_FSTAT_OFFSET = const(0x00000004)
PIO_FSTAT_TXEMPTY_LSB = 24


class PulseSender:
    def __init__(self, pin_num, pio, sm, carrier_freq,
                 debug_burst_pin=None, debug_send_pin=None, debug_wait_pin=None,
                 stalled_wait=True):

        if pio < 0 or pio > 1:
            raise ValueError("pio out of range. Expected 0 or 1")

        # This is a better check for PIO numbers, but PIO2 seems to stall
        # once the TX fifo is full, so avoiding it for now
        # try:
        #     _ = PIO(pio)
        # except:
        #     raise ValueError("pio out of range. Expected 0 or 1 (or 2 if on RP2350)")

        if sm < 0 or sm > 3:
            raise ValueError("sm out of range. Expected 0 to 3")

        # Select the registers to query for checking if the PIO SM has stalled
        if stalled_wait:
            self.__PIO_REG = PIO_BASE[pio] | PIO_FDEBUG_OFFSET
            self.__SM_MASK = (1 << (PIO_FDEBUG_TXSTALL_LSB + sm))
        else:
            self.__PIO_REG = PIO_BASE[pio] | PIO_FSTAT_OFFSET
            self.__SM_MASK = (1 << (PIO_FSTAT_TXEMPTY_LSB + sm))
        self.__PIO_FREQ = carrier_freq * CLOCKS_PER_CYCLE

        # Load either the regular or debug program into the chosen StateMachine
        if debug_burst_pin is None:
            self.__sm = StateMachine(sm + (pio * 4), pulsesender,
                                     freq=self.__PIO_FREQ,
                                     sideset_base=Pin(pin_num))
        else:
            self.__sm = StateMachine(sm + (pio * 4), pulsesender_debug,
                                     freq=self.__PIO_FREQ,
                                     set_base=Pin(debug_burst_pin),
                                     sideset_base=Pin(pin_num))

        # Set up debug pins for scoping
        self.__debug_send_pin = DebugPin(debug_send_pin, Pin.OUT)
        self.__debug_wait_pin = DebugPin(debug_wait_pin, Pin.OUT)

    def start(self):
        self.__sm.active(1)

    def stop(self):
        self.__sm.active(0)

    def send(self, burst_us, idle_us):
        """
        Sends a pulse with a given burst and idle duration.
        The burst phase is encoded with the carrier frequency.
        """

        # Convert the pulse times (in microseconds) into 16 bit counts the PIO program accepts
        burst = self.__pulse_us_to_count(burst_us) & 0xffff
        idle = self.__pulse_us_to_count(idle_us) & 0xffff

        self.__debug_send_pin.on()      # Show that the pulse is being passed to the SM

        # Send the burst and idle counts to the PIO program as a single 32 bit integer
        self.__sm.put((burst << 16) | idle)

        self.__debug_send_pin.off()     # Show that the SM now has the pulse

    def __pulse_us_to_count(self, us):
        return round(((us * self.__PIO_FREQ) / (CLOCKS_PER_CYCLE * 1000000)) - 2)

    def wait_for_send(self):
        """
        Waits for pulses to be sent by the PIO. There are two modes,
        depending on the value provided to `stalled_wait` during initialisation:

        - Wait for all data to have been emitted by the PIO (TX STALL)
        - Wait for all data to have been passed from the FIFO to the PIO (TX EMPTY)

        The former is the most "correct" for this function's name, but adds additional
        milliseconds of delay (with NEC IR) that could be used for other tasks.
        """

        # Clear the TXSTALL flag if selected, otherwise does nothing
        self.__clear_tx()

        self.__debug_wait_pin.on()      # Show that waiting has started

        # Wait for either the PIO to stall or its TX FIFO to empty
        while not self.__read_tx():
            pass

        self.__debug_wait_pin.off()     # Show that waiting has finished

    def __read_tx(self):
        return (mem32[self.__PIO_REG] & self.__SM_MASK) > 0

    def __clear_tx(self):
        # Clear the register if it is write-to-clear like TXSTALL
        mem32[self.__PIO_REG] = self.__SM_MASK
