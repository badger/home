"""Swap Mona cards over the Bluetooth badge link (badgeware.link).

A card carries a GitHub handle, Mona DNA (as hex) and a display name.
Contacts cards carry no DNA, so they get the Mona for their handle.
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
