# SPDX-FileCopyrightText: 2025 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

NEC_FREQUENCY = const(38000)

NEC_START_BURST_US = const(9000)
NEC_START_DATA_US = const(4500)
NEC_START_REPEAT_US = const(2250)

NEC_DATA_BURST_US = const(560)
NEC_DATA_ZERO_US = const(NEC_DATA_BURST_US)
NEC_DATA_ONE_US = const(NEC_DATA_BURST_US * 3)
NEC_DATA_LOCKOUT_US = const(9500)       # Set to be longer than the time of the receiver code's lockout

NEC_REPEAT = const(-1)
NEC_ALLOWED_DEVIATION_PERCENT = const(0.3)
NEC_REPEAT_TIMEOUT_MS = const(150)


def pulse_us_valid(us, expected_us):
    return abs(us - expected_us) < expected_us * NEC_ALLOWED_DEVIATION_PERCENT
