"""Swap Mona cards over the Bluetooth badge link (badgeware.link).

A card carries a GitHub handle, Mona DNA (as hex) and a display name.
Contacts cards carry no DNA, so they get the Mona for their handle.

Messages reuse the Contacts chunking: kind, part index, part count, data.
"""

import json

import mona_dna

CARD_VERSION = 2
MAX_NAME = 40


def clean_text(text, limit):
    return mona_dna.clean_text(text, limit)


def make_card(handle, dna, name=""):
    card = {"v": CARD_VERSION, "github": handle or "", "dna": mona_dna.dna_hex(dna)}
    name = clean_text(name, MAX_NAME)
    if name:
        card["name"] = name
    return card


def read_card(value):
    """(handle, dna, name) from a card dict, or None.

    Works for ASCII Mona cards and Contacts cards (which carry no DNA).
    """
    if not isinstance(value, dict):
        return None
    raw = value.get("github")
    handle = ""
    if isinstance(raw, str) and raw.strip():
        handle = mona_dna.clean_handle(raw)
        if handle and raw.strip().lower() == handle:
            handle = raw.strip()
    dna = mona_dna.parse_hex(value.get("dna"))
    if dna is None:
        if not handle:
            return None
        dna = mona_dna.dna_for(handle)
    return handle, dna, clean_text(value.get("name"), MAX_NAME)


def decode_card(data):
    try:
        return read_card(json.loads(data))
    except (ValueError, TypeError):
        return None


class Outbox:
    """One message split into link-sized chunks, resent until accepted."""

    def __init__(self, kind, payload):
        self.kind = kind
        self.payload = payload
        self.chunks = None
        self.sent = 0

    @property
    def done(self):
        return self.chunks is not None and self.sent >= len(self.chunks)

    def pump(self, link):
        if self.chunks is None:
            size = max(1, link.capacity() - 3)
            chunks = []
            for start in range(0, len(self.payload), size):
                chunks.append(self.payload[start:start + size])
            self.chunks = chunks[:255]
        while self.sent < len(self.chunks):
            message = self.kind + bytes((self.sent, len(self.chunks))) + self.chunks[self.sent]
            if not link.send(message):
                return False
            self.sent += 1
        return True


class Inbox:
    """Reassembles one chunked message."""

    def __init__(self):
        self.parts = {}
        self.total = 0

    def add(self, message):
        """Returns the whole payload once every part has arrived."""
        if len(message) < 3:
            return None
        index = message[1]
        total = message[2]
        if total == 0 or index >= total:
            return None
        if total != self.total:
            self.parts = {}
            self.total = total
        self.parts[index] = message[3:]
        if len(self.parts) < total:
            return None
        data = b"".join(self.parts[part] for part in range(total))
        self.parts = {}
        self.total = 0
        return data
