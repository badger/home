# SPDX-FileCopyrightText: 2025 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

import rp2

# Constants
CLOCKS_PER_CYCLE = const(2)


# Normal Program
@rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW, autopull=True, pull_thresh=32, fifo_join=rp2.PIO.JOIN_TX)
def pulsesender():
    # Pulse High (4 Cycles)
    out(y, 16).delay(1)                     # Set the high counter
    label("high_count_check")
    nop().side(1)                           # Set the side pin to high
    jmp(y_dec, "high_count_check").side(0)  # Decrement the high counter until it is zero,
                                            # and set the side pin to low

    # Pulse Low (4 Cycles)
    out(x, 16).side(1)                      # Set the low counter, and set the side pin to high
    nop().side(0)                           # Set the side pin to low
    label("low_count_check")
    nop()
    jmp(x_dec, "low_count_check")           # Decrement the low counter until it is zero


# Program with Debugging
@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW, sideset_init=rp2.PIO.OUT_LOW,
             autopull=True, pull_thresh=32, fifo_join=rp2.PIO.JOIN_TX)
def pulsesender_debug():
    # Pulse High (4 Cycles)
    out(y, 16).delay(1)                     # Set the high counter
    label("high_count_check")
    set(pins, 1).side(1)                    # Set the side pin and set pin to high
    jmp(y_dec, "high_count_check").side(0)  # Decrement the high counter until it is zero,
                                            # and set the side pin to low

    # Pulse Low (4 Cycles)
    out(x, 16).side(1)                      # Set the low counter, and set the side pin to high
    nop().side(0)                           # Set the side pin to low
    label("low_count_check")
    set(pins, 0)                            # Set the set pin to low
    jmp(x_dec, "low_count_check")           # Decrement the low counter until it is zero
