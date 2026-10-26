"""Mona DNA over infrared: NEC frames out of GPIO16, in through GPIO17.

Each NEC frame carries one byte, so a Mona travels as a short packet of
frames on address 0x4C:

    0xA5 0x5A LEN payload... CRC8

The payload is a version byte (2), the 19 DNA bytes (each below 0x80), then
the GitHub handle as ASCII (empty for a mystery Mona). CRC8 uses polynomial 0x07
over LEN and the payload.
"""

import mona_dna

DNA_ADDRESS = 0x4C

VERSION = 2
SYNC_A = 0xA5
SYNC_B = 0x5A
MIN_LEN = 1 + mona_dna.SIZE
MAX_LEN = MIN_LEN + mona_dna.MAX_HANDLE


def crc8(data):
    crc = 0
    for byte in data:
        crc ^= byte & 0xFF
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x07) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


def encode_packet(handle, dna):
    """The frame bytes for one copy of a Mona."""
    handle = handle or ""
    if handle and not mona_dna.valid_handle(handle):
        raise ValueError("not a GitHub handle")
    if not mona_dna.valid_dna(dna):
        raise ValueError("not Mona DNA")
    body = [0, VERSION] + list(dna)
    for ch in handle:
        body.append(ord(ch))
    body[0] = len(body) - 1
    return [SYNC_A, SYNC_B] + body + [crc8(body)]


def parse_payload(payload):
    """(handle, dna) from a payload, or None."""
    n = len(payload)
    if n < MIN_LEN or n > MAX_LEN or payload[0] != VERSION:
        return None
    dna = tuple(payload[1:MIN_LEN])
    if not mona_dna.valid_dna(dna):
        return None
    chars = []
    for index in range(MIN_LEN, n):
        byte = payload[index]
        if byte < 33 or byte > 126:
            return None
        chars.append(chr(byte))
    handle = "".join(chars)
    if handle and not mona_dna.valid_handle(handle):
        return None
    return handle, dna
