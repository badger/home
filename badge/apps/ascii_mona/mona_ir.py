"""Mona DNA over infrared: NEC frames out of GPIO16, in through GPIO17.

Each NEC frame carries one byte, so a Mona travels as a short packet of
frames on address 0x4C:

    0xA5 0x5A LEN payload... CRC8

The payload is a version byte (2), the 19 DNA bytes (each below 0x80), then
the GitHub handle as ASCII (empty for a mystery Mona). CRC8 uses polynomial 0x07
over LEN and the payload.

Sending blocks for about 77 ms a frame, so the app sends at most one frame
per update.
"""

import mona_dna

DNA_ADDRESS = 0x4C

VERSION = 2
SYNC_A = 0xA5
SYNC_B = 0x5A
MIN_LEN = 1 + mona_dna.SIZE
MAX_LEN = MIN_LEN + mona_dna.MAX_HANDLE

FRAME_MS = 80
COPIES = 2
COPY_GAP_MS = 250


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


def beam_frames(handle, dna):
    """(address, command, wait ms before it) for everything one press sends."""
    packet = encode_packet(handle, dna)
    frames = []
    for copy in range(COPIES):
        for index in range(len(packet)):
            wait = COPY_GAP_MS if copy and index == 0 else 0
            frames.append((DNA_ADDRESS, packet[index], wait))
    return frames


class Beam:
    """The frames for one press, paced one per update."""

    def __init__(self, handle, dna, live):
        self.handle = handle or ""
        self.dna = dna
        self.frames = beam_frames(handle, dna)
        self.live = live
        self.index = 0
        self.next_at = None
        self.error = ""

    @property
    def done(self):
        return self.index >= len(self.frames)

    def progress(self):
        """Percent sent, 0 to 100."""
        return self.index * 100 // len(self.frames)

    def step(self, now, send):
        """Send the next frame when it is due; True when one went out."""
        if self.done or (self.next_at is not None and now - self.next_at < 0):
            return False
        address, command, _ = self.frames[self.index]
        if send is not None:
            try:
                send(address, command)
            except Exception as err:
                self.error = "IR send failed: %s" % err
                self.index = len(self.frames)
                return False
        self.index += 1
        wait = self.frames[self.index][2] if self.index < len(self.frames) else 0
        self.next_at = now + FRAME_MS + wait
        return True
