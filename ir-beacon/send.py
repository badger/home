# SPDX-FileCopyrightText: 2025 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

from ..pulse.send import PulseSender
from .common import NEC_FREQUENCY, NEC_START_BURST_US, NEC_START_DATA_US, \
                    NEC_DATA_BURST_US, NEC_DATA_ZERO_US, NEC_DATA_ONE_US, \
                    NEC_DATA_LOCKOUT_US


class NECSender(PulseSender):
    def __init__(self, pin_num, pio, sm, debug_burst_pin=None,
                 debug_send_pin=None, debug_wait_pin=None):
        super().__init__(pin_num, pio, sm, NEC_FREQUENCY,
                         debug_burst_pin, debug_send_pin, debug_wait_pin)

    def send_remote(self, remote_type, name):
        self.send_addr_cmd(remote_type.ADDRESS, remote_type.BUTTON_CODES[name])

    def send_addr_cmd(self, addr, cmd):
        if addr < 0 or addr > 0xffff:
            raise ValueError("addr out of range. Expected 0x0000 to 0xffff")

        if cmd < 0 or cmd > 0xff:
            raise ValueError("cmdr out of range. Expected 0x00 to 0xff")

        code = addr
        if addr <= 0xff:    # Handle short addresses
            code |= ((addr ^ 0xff) << 8)

        code |= (cmd | ((cmd ^ 0xff) << 8)) << 16

        self.send_code(code)

    def send_code(self, code):
        if code < 0 or code > 0xffffffff:
            raise ValueError("code out of range. Expected 0x00000000 to 0xffffffff")

        # Send the starting condition
        super().send(NEC_START_BURST_US, NEC_START_DATA_US)

        # Send each bit of the code
        for bit in range(32):
            data_us = NEC_DATA_ONE_US if code & (1 << bit) else NEC_DATA_ZERO_US
            super().send(NEC_DATA_BURST_US, data_us)

        # Send a final burst
        super().send(NEC_DATA_BURST_US, NEC_DATA_LOCKOUT_US)

        # Wait for the last burst to be sent
        super().wait_for_send()
