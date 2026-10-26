"""Deterministic MyOctocat DNA for a GitHub handle.

Everything here is plain integer Python that behaves the same on the badge's
MicroPython and on CPython, so a handle grows the same Mona on the badge that
beams it, the badge that receives it and in the host tests. Python's hash()
differs between the two (and CPython randomises it per process), so seeds come
from FNV-1a with a murmur3 finaliser and picks from a xorshift32 generator
rather than the random module.
"""

MASK = 0xFFFFFFFF
MAX_HANDLE = 39
HANDLE_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
PREFIXES = ("https://", "http://", "www.", "github.com/", "@")


def handle_problem(text):
    """Why text is not a GitHub handle, or "" when it is one.

    No regex: MicroPython's re reads {1,39} as literal braces.
    """
    if not isinstance(text, str) or not text:
        return "type a handle"
    if len(text) > MAX_HANDLE:
        return "39 characters max"
    for ch in text:
        if ch not in HANDLE_CHARS:
            return "letters, digits and - only"
    if text[0] == "-" or text[-1] == "-":
        return "no - at either end"
    if "--" in text:
        return "no double hyphens"
    return ""


def valid_handle(text):
    return handle_problem(text) == ""


def clean_handle(text):
    """"@Mona", "github.com/mona" or a profile URL become "mona"; junk becomes ""."""
    if isinstance(text, (bytes, bytearray)):
        try:
            text = bytes(text).decode()
        except UnicodeError:
            return ""
    if not isinstance(text, str):
        return ""
    text = text.strip()
    for prefix in PREFIXES:
        if text.lower().startswith(prefix):
            text = text[len(prefix):]
    for stop in "/?#":
        cut = text.find(stop)
        if cut >= 0:
            text = text[:cut]
    text = text.strip()
    if handle_problem(text):
        return ""
    return text.lower()


def clean_text(text, limit):
    """Printable ASCII the badge fonts can draw, trimmed to limit.

    Square brackets become parentheses because the vector font has no glyphs
    for them.
    """
    if isinstance(text, (bytes, bytearray)):
        try:
            text = bytes(text).decode()
        except UnicodeError:
            return ""
    if not isinstance(text, str):
        return ""
    out = []
    for ch in text:
        if ch == "[":
            out.append("(")
        elif ch == "]":
            out.append(")")
        elif ch == "\n" or ch == "\t":
            out.append(" ")
        elif " " <= ch <= "~":
            out.append(ch)
    return "".join(out).strip()[:limit]


def fnv1a(data):
    h = 0x811C9DC5
    for byte in data:
        h = ((h ^ byte) * 0x01000193) & MASK
    return h


def fmix32(h):
    h ^= h >> 16
    h = (h * 0x85EBCA6B) & MASK
    h ^= h >> 13
    h = (h * 0xC2B2AE35) & MASK
    h ^= h >> 16
    return h


def seed_of(text):
    return fmix32(fnv1a(text.encode()))


class Rng:
    """xorshift32, so seeded picks match on every runtime."""

    def __init__(self, seed):
        self.state = (seed & MASK) or 0x9E3779B9

    def next(self):
        x = self.state
        x ^= (x << 13) & MASK
        x ^= x >> 17
        x ^= (x << 5) & MASK
        self.state = x
        return x

    def below(self, n):
        return self.next() % n
