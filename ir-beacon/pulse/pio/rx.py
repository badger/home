# SPDX-FileCopyrightText: 2025 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

# This implementation is derived from: https://github.com/rdear4/Pico_PIO_IR_Receiver/blob/main/PulseReader.py
# It features improved timing accuracy and reduces counters to 16 bits,allowing both low (burst) and high (idle)
# phases to be sent together, which along with a joined RX FIFO gives more time for the main program to handle data.

import rp2

# Constants
FREQUENCY = const(2000000)  # Set to a value to give 1us resolution
BURST_BITS = const(14)
IDLE_BITS = const(13)
BURST_COUNT_TIMEOUT = const((2 ** BURST_BITS) - 1)
IDLE_COUNT_TIMEOUT = const((2 ** IDLE_BITS) - 1)
TIMEOUT_REACHED = const(0xffffffff)


# Conversion Functions
def count_to_burst_us(count):
    return int(BURST_COUNT_TIMEOUT - (count - 5)) * 2 * 1000000 / FREQUENCY


def count_to_idle_us(count):
    return int(IDLE_COUNT_TIMEOUT - (count - 5)) * 2 * 1000000 / FREQUENCY


# Normal Program
@rp2.asm_pio(out_shiftdir=rp2.PIO.SHIFT_LEFT, fifo_join=rp2.PIO.JOIN_RX)
def pulsereader():
    wait(1, pin, 0)                 # Wait for the receiving pin to go high

    # Sig ‾‾‾‾‾‾‾‾‾

    wait(0, pin, 0)                 # Wait for the receiving pin to go low, signaling the start of a pulse

    # Sig ‾‾‾‾|____

    nop().delay(5)                  # Add delay to cover time it takes to output data at the end
    label("low_setup")
    mov(osr, invert(null))          # Fill the OSR with 0xffffffff for setting up the low timeout
    out(x, BURST_BITS).delay(1)     # Set the low timeout by shifting a number of 1s from the OSR and into X

    # Loop
    label("while_low")
    jmp(pin, "high_setup")          # Break out of the loop if the receiving pin has gone high
    jmp(x_dec, "while_low")         # Loop until the low timeout reaches zero
                                    # Each decrement loop takes 2 cycles

    jmp("timeout_reached")          # The low timeout has expired, so jump to timeout_reached

    # Sig ____|‾‾‾‾

    label("high_setup")
    nop().delay(5)                  # Add delay to cover time it takes to output data at the end
    mov(osr, invert(null))          # Fill the OSR with 0xffffffff for setting up the high timeout
    out(y, IDLE_BITS).delay(1)      # Set the high timeout by shifting a number of 1s from the OSR and into Y

    # Loop
    label("while_high")
    jmp(pin, "still_high")          # Continue with the loop if the receiving pin is still high

    # Sig ‾‾‾‾|____

    # Write
    in_(x, 16)                      # Shift the remaining low timeout into the ISR
    in_(y, 16)                      # Shift the remaining high timeout into the ISR
    push()                          # Push the contents of the ISR into the RX FIFO
    irq(rel(0)).delay(1)            # Raise an interrupt so the main program can grab the data
    jmp("low_setup")                # Jump back to the low_setup for the next pulse

    # Sig ‾‾‾‾‾‾‾‾‾

    label("still_high")
    jmp(y_dec, "while_high")        # Loop until the high timeout reaches zero
                                    # Each decrement loop takes 2 cycles

    # The high timeout has expired, so fall through to timeout_reached

    label("timeout_reached")
    mov(isr, invert(null))          # Set the ISR to 0xffffffff to denote the timeouts have expired
    push()                          # Push the contents of the ISR into the RX FIFO
    irq(rel(0))                     # Raise an interrupt so the main program can grab the data


# Program with Debugging
@rp2.asm_pio(sideset_init=(rp2.PIO.OUT_LOW, rp2.PIO.OUT_LOW),
             out_shiftdir=rp2.PIO.SHIFT_LEFT, fifo_join=rp2.PIO.JOIN_RX)
def pulsereader_debug():
    wait(1, pin, 0)                         # Wait for the receiving pin to go high

    # Sig ‾‾‾‾‾‾‾‾‾

    wait(0, pin, 0)                         # Wait for the receiving pin to go low, signaling the start of a pulse

    # Sig ‾‾‾‾|____

    nop().delay(2).side(0b10)               # Add delay to cover time it takes to output data at the end
    nop().delay(2)                          # Delay is split across two operations due to sideset bits
    label("low_setup")
    mov(osr, invert(null))                  # Fill the OSR with 0xffffffff for setting up the low timeout
    out(x, BURST_BITS).delay(1)             # Set the low timeout by shifting a number of 1s from the OSR and into X

    # Loop
    label("while_low")
    jmp(pin, "high_setup").side(0b11)       # Break out of the loop if the receiving pin has gone high
    jmp(x_dec, "while_low").side(0b10)      # Loop until the low timeout reaches zero
                                            # Each decrement loop takes 2 cycles

    jmp("timeout_reached")                  # The low timeout has expired, so jump to timeout_reached

    # Sig ____|‾‾‾‾

    label("high_setup")
    nop().delay(2)                          # Add delay to cover time it takes to output data at the end
    nop().delay(2)                          # Delay is split across two operations due to sideset bits
    mov(osr, invert(null)).side(0b00)       # Fill the OSR with 0xffffffff for setting up the high timeout
    out(y, IDLE_BITS).delay(1)              # Set the high timeout by shifting a number of 1s from the OSR and into Y

    # Loop
    label("while_high")
    jmp(pin, "still_high").side(0b01)       # Continue with the loop if the receiving pin is still high

    # Sig ‾‾‾‾|____

    # Write
    in_(x, 16).side(0b00)                   # Shift the remaining low timeout into the ISR
    in_(y, 16)                              # Shift the remaining high timeout into the ISR
    push()                                  # Push the contents of the ISR into the RX FIFO
    irq(rel(0)).delay(1)                    # Raise an interrupt so the main program can grab the data
    jmp("low_setup")                        # Jump back to the low_setup for the next pulse

    # Sig ‾‾‾‾‾‾‾‾‾

    label("still_high")
    jmp(y_dec, "while_high").side(0b00)     # Loop until the high timeout reaches zero
                                            # Each decrement loop takes 2 cycles

    # The high timeout has expired, so fall through to timeout_reached

    label("timeout_reached")
    mov(isr, invert(null)).side(0b00)       # Set the ISR to 0xffffffff to denote the timeouts have expired
    push()                                  # Push the contents of the ISR into the RX FIFO
    irq(rel(0))                             # Raise an interrupt so the main program can grab the data
