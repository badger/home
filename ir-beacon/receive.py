# SPDX-FileCopyrightText: 2024 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

import time
from machine import Pin
from ..pulse.common import DebugPin
from ..pulse.receive import PulseReceiver, DEFAULT_FILTER_THRESHOLD
from .common import pulse_us_valid, NEC_REPEAT, NEC_REPEAT_TIMEOUT_MS, \
                    NEC_START_BURST_US, NEC_START_REPEAT_US, NEC_START_DATA_US, \
                    NEC_DATA_BURST_US, NEC_DATA_ZERO_US, NEC_DATA_ONE_US
from .remotes import KNOWN_REMOTES


class NECReceiver(PulseReceiver):
    def __init__(self, pin_num, pio, sm, extended_addresses=False,
                 debug_pin_base=None, debug_blip_pin=None, debug_error_pin=None):
        self.__remotes = {}
        self.__last_code = NEC_REPEAT
        self.__last_rx = time.ticks_ms()
        self.__extended = extended_addresses
        self.__repeat_callbacks = []
        self.__release_callbacks = []
        super().__init__(pin_num, pio, sm, debug_pin_base, debug_blip_pin)

        # Set up debug pin for scoping
        self.__debug_error_pin = DebugPin(debug_error_pin, Pin.OUT)

    def bind(self, remote_descriptor, force=False):
        addr = remote_descriptor.ADDRESS
        if addr in self.__remotes:
            if not force:
                raise ValueError(f"A remote with the address '0x{addr:0x}' is already bound. Use a different address, or append with 'force=True'")
            self.__remotes[addr].append(remote_descriptor)
        else:
            self.__remotes[addr] = [remote_descriptor]

    def reset(self):
        self.__last_code = NEC_REPEAT
        self.__last_rx = time.ticks_ms()
        super().reset()

    def __extract_code(self, pulses, debug=False):
        while len(pulses) > 0:
            pulse = pulses[0]

            # Is the first pulse a repeat and are there no other pulses?
            if pulse_us_valid(pulse.burst, NEC_START_BURST_US) and \
               pulse_us_valid(pulse.idle, NEC_START_REPEAT_US) and \
               len(pulses) == 1:
                return NEC_REPEAT

            # Is the first pulse an invalid start?
            if not pulse_us_valid(pulse.burst, NEC_START_BURST_US) and \
               not pulse_us_valid(pulse.idle, NEC_START_DATA_US):
                self.__debug_error_pin.on()
                if debug:
                    print(f"Invalid Start [{pulse.burst}, {pulse.idle}], Exp: {NEC_START_BURST_US} then {NEC_START_DATA_US} or {NEC_START_REPEAT_US}")
                del pulses[0]
                self.__debug_error_pin.off()
                continue        # Skip to the next pulse

            # Are there fewer pulses than a full code requires?
            if len(pulses) < 33:
                return None     # No code was extracted

            # Go through the rest of the pulses and extract the code
            code = 0
            for i in range(1, 33):
                pulse = pulses[i]

                # Does the full pulse length (of the burst and idle combined) match a `Zero`?
                if pulse_us_valid(pulse.burst + pulse.idle,
                                  NEC_DATA_BURST_US + NEC_DATA_ZERO_US):
                    continue    # Skip to the next data pulse

                # Does the full pulse length (of the burst and idle combined) match a `One`?
                if pulse_us_valid(pulse.burst + pulse.idle,
                                  NEC_DATA_BURST_US + NEC_DATA_ONE_US):
                    code |= (1 << (i - 1))      # Add a 1 at the relevant bit position
                    continue    # Skip to the next data pulse

                self.__debug_error_pin.on()
                if debug:
                    print(f"Invalid Data [{pulse.burst}, {pulse.idle}], Exp {NEC_DATA_BURST_US} then {NEC_DATA_ONE_US} or {NEC_DATA_ZERO_US}")
                self.__debug_error_pin.off()
                return None     # No code was extracted

            return code     # A complete code was extracted

        return None     # No code was extracted

    def decode_no_filter(self, debug=False):
        self.__check_repeat_timeout(debug)
        super().decode_no_filter(debug)

    def decode(self, filter_threshold=DEFAULT_FILTER_THRESHOLD, debug=False):   # with filter
        self.__check_repeat_timeout(debug)
        super().decode(filter_threshold, debug)

    def __check_repeat_timeout(self, debug):
        # Expire our last code if it was received too long ago and isn't a repeat
        if time.ticks_diff(time.ticks_ms(), self.__last_rx) > NEC_REPEAT_TIMEOUT_MS and \
           self.__last_code != NEC_REPEAT:
            if debug:
                print(f"Last code 0x{self.__last_code:08x} expired")
            self.__last_code = NEC_REPEAT

            # Perform the release actions of the last command, if any
            for callback in self.__release_callbacks:
                callback()

            # Clear out the callback lists
            self.__release_callbacks.clear()
            self.__repeat_callbacks.clear()

    def __analyse(self, pulses, debug=False):
        # Attempt to extract a code from the received pulses
        code = self.__extract_code(pulses, debug)

        # Was a code was extracted?
        if code is not None:
            # Record the time of this new code
            self.__last_rx = time.ticks_ms()

            # Was the code a repeat?
            if code == NEC_REPEAT:
                if debug and self.__last_code != NEC_REPEAT:
                    print(f"Repeat received, loading code 0x{self.__last_code:08x}")

                # Perform the repeat actions of the last command, if any
                for callback in self.__repeat_callbacks:
                    callback()
                return

            # Perform the release actions of the last command, if any
            for callback in self.__release_callbacks:
                callback()

            # Clear out the callback lists
            self.__release_callbacks.clear()
            self.__repeat_callbacks.clear()

            # Update the last code
            self.__last_code = code

            # Extract the address from the code, optionally supporting extended addresses
            addr = code & 0xff          # 8 bit address
            if addr != ((code >> 8) ^ 0xff) & 0xff:
                if not self.__extended:
                    if debug:
                        print(f"Address check failed: 0x{addr:02x} != 0x{((code >> 8) ^ 0xff) & 0xff:02x}")
                    return
                addr |= code & 0xff00

            # Extract the command from the code
            cmd = (code >> 16) & 0xff
            if cmd != (code >> 24) ^ 0xff:
                if debug:
                    print(f"Command check failed: 0x{cmd:02x} != 0x{(code >> 24) ^ 0xff:02x}, Addr: {addr:02x}")
                return

            # Does the address match one of the bound remotes?
            if addr in self.__remotes:
                # Go through all the bound remotes with the address
                known = False
                for remote in self.__remotes[addr]:
                    # Perform the general callback for any command received
                    if remote.on_any is not None:
                        remote.on_any(cmd)

                    # Perform the callback only for known commands that are received
                    if remote.on_known is not None:
                        for key, val in remote.BUTTON_CODES.items():
                            if val == cmd:
                                remote.on_known(key)
                                break

                    try:
                        # Attempt to get the button associated with the command
                        # Raises a KeyError if it fails
                        button = remote.button(cmd)

                        # At least one bound remote has this button
                        known = True

                        if debug:
                            for key, val in remote.BUTTON_CODES.items():
                                if val == cmd:
                                    print(f"'{key}' (0x{cmd:02x}) received from bound remote `{remote.NAME}` (0x{addr:02x})")

                        # Perform the press action of the bound button, if present
                        if button.on_press is not None:
                            button.on_press()

                        # Queue up the repeat action of the bound button, if present
                        if button.on_repeat is not None:
                            self.__repeat_callbacks.append(button.on_repeat)

                        # Queue up the release action of the bound button, if present
                        if button.on_release is not None:
                            self.__release_callbacks.append(button.on_release)

                    except KeyError:
                        pass

                # None of the bound remotes had a button binding for the command
                if not known and debug:
                    for remote in self.__remotes[addr]:
                        print(f"Unknown command (0x{cmd:02x}) received from bound remote `{remote.NAME}` (0x{addr:02x}). ", end="")

                        keys = [key for key, val in remote.BUTTON_CODES.items() if val == cmd]
                        if len(keys) == 1:
                            print(f"Likely '{keys[0]}'")
                        else:
                            print("No known command")

            # The address does not match one of the bound remotes
            elif len(self.__remotes) == 0 or debug:
                print(f"Unknown code (Addr 0x{addr:02x}, Cmd 0x{cmd:02x}) received. ", end="")

                known = False
                for remote in KNOWN_REMOTES:
                    if remote.ADDRESS == addr:
                        print(", or " if known else "Likely from ", end="")

                        known = True
                        keys = [key for key, val in remote.BUTTON_CODES.items() if val == cmd]
                        if len(keys) == 1:
                            print(f"'{remote.NAME}.{keys[0]}'", end="")
                        else:
                            print(f"'{remote.NAME}' remote", end="")

                print("" if known else "No known remote")
