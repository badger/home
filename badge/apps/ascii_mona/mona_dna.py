"""Deterministic MyOctocat DNA for a GitHub handle.

A Mona is 19 small numbers: five colour swatches (body, face, eyes, hair and
facial hair), one pick for each MyOctocat part category, two extras, a title
and a backdrop. Every value is below 0x80, so the DNA travels as plain bytes
over IR and as 38 hex digits on a card.

Everything here is plain integer Python that behaves the same on the badge's
MicroPython and on CPython, so a handle grows the same Mona on the badge that
beams it, the badge that receives it and in the host tests. Python's hash()
differs between the two (and CPython randomises it per process), so seeds come
from FNV-1a with a murmur3 finaliser and picks from a xorshift32 generator
rather than the random module.
"""

import mona_octo as O
import mona_parts as P

MASK = 0xFFFFFFFF
MAX_HANDLE = 39
HANDLE_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
PREFIXES = ("https://", "http://", "www.", "github.com/", "@")

# DNA fields, in byte order
BODY = 0
FACE = 1
EYE_COLOUR = 2
HAIR_COLOUR = 3
FACEHAIR_COLOUR = 4
PART0 = 5  # PART0 + category for eyes .. faceHair: 0 none, n part n - 1
MISC_A = 15
MISC_B = 16
TITLE = 17
BACKDROP = 18
SIZE = 19

TITLES = ("Maintainer", "Hacker", "Designer", "Shipper", "Docs Wizard", "Bug Hunter", "Mentor", "Explorer")
BACKDROPS = ("Plain", "Contributions", "Stars", "Rings")

LIMITS = (
    len(P.BODY), len(P.FACE), len(P.EYE), len(P.HAIR), len(P.FACEHAIR),
    O.count(O.EYES) + 1, O.count(O.MOUTHS) + 1, O.count(O.HAIR) + 1,
    O.count(O.HEADGEAR) + 1, O.count(O.TOPS) + 1, O.count(O.BOTTOMS) + 1,
    O.count(O.FOOTWEAR) + 1, O.count(O.PROPS) + 1, O.count(O.EYEWEAR) + 1,
    O.count(O.FACEHAIR) + 1, O.count(O.MISC) + 1, O.count(O.MISC) + 1,
    len(TITLES), len(BACKDROPS),
)

# (category, chance in 100 of none), drawn in this order
ODDS = (
    (O.EYES, 0), (O.MOUTHS, 0), (O.HAIR, 15), (O.HEADGEAR, 35), (O.TOPS, 10),
    (O.BOTTOMS, 15), (O.FOOTWEAR, 20), (O.PROPS, 30), (O.EYEWEAR, 50), (O.FACEHAIR, 60),
)
MATCH_MOUTH = 50  # chance the mouth shares the eyes' expression
SAME_FACEHAIR = 75

# Random picks never choose these. Faith, national and cultural dress, the
# Pride shirt and the prosthetic hand are for people to choose for themselves
# in Tweak; the listed extras are too small to see on the badge.
NOT_RANDOM = (
    (O.HEADGEAR, ("Hijab", "Turban", "Head Wrap", "Dashiki", "Kimono", "Sombrero", "Aussie", "French Hat")),
    (O.TOPS, ("Sari", "Kimono", "Dashiki", "Chinese Dress", "Aussie", "Lederhosen", "Dirndl", "French Top", "GitHub Pride Shirt")),
    (O.BOTTOMS, ("Lederhosen", "Dirndl", "Kilt", "French Bottoms")),
    (O.FOOTWEAR, ("Kimono", "Lederhosen", "Dirndl", "French Shoes")),
    (O.PROPS, ("Kimono", "Aussie", "Prosthetic Hand")),
    (O.MISC, ("Freckles", "Nose Ring", "Eyebrow Ring", "Earrings")),
)


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


_pools = [None] * (O.MISC + 1)


def pool(cat):
    """Part indices a random pick may use in a category."""
    got = _pools[cat]
    if got is None:
        banned = []
        for entry in NOT_RANDOM:
            if entry[0] == cat:
                banned.extend(entry[1])
        got = []
        for index in range(O.count(cat)):
            if O.part_name(cat, index) not in banned:
                got.append(index)
        got = tuple(got)
        _pools[cat] = got
    return got


def random_dna(seed):
    """A whole Mona from a 32-bit seed."""
    rng = Rng(seed)
    dna = [0] * SIZE
    dna[BODY] = rng.below(LIMITS[BODY])
    dna[FACE] = rng.below(LIMITS[FACE])
    dna[EYE_COLOUR] = rng.below(LIMITS[EYE_COLOUR])
    dna[HAIR_COLOUR] = rng.below(LIMITS[HAIR_COLOUR])
    if rng.below(100) < SAME_FACEHAIR:
        dna[FACEHAIR_COLOUR] = dna[HAIR_COLOUR] % LIMITS[FACEHAIR_COLOUR]
    else:
        dna[FACEHAIR_COLOUR] = rng.below(LIMITS[FACEHAIR_COLOUR])
    for cat, none in ODDS:
        if rng.below(100) >= none:
            choices = pool(cat)
            dna[PART0 + cat] = choices[rng.below(len(choices))] + 1
        if cat == O.MOUTHS and rng.below(100) < MATCH_MOUTH:
            same = O.find_part(O.MOUTHS, O.part_name(O.EYES, dna[PART0 + O.EYES] - 1))
            if same >= 0:
                dna[PART0 + O.MOUTHS] = same + 1
    dna[TITLE] = rng.below(LIMITS[TITLE])
    dna[BACKDROP] = rng.below(LIMITS[BACKDROP])
    return tuple(dna)


def dna_for(handle):
    """The Mona DNA for a GitHub handle; case never matters."""
    return random_dna(seed_of("mona:" + handle.lower()))


def valid_dna(dna):
    if not isinstance(dna, (tuple, list)) or len(dna) != SIZE:
        return False
    for i in range(SIZE):
        value = dna[i]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value >= LIMITS[i]:
            return False
    return True


def picks_of(dna):
    """(picks, misc) for mona_octo.compose; eyes and mouth are never empty."""
    picks = []
    for cat in range(O.PICKS):
        index = dna[PART0 + cat] - 1
        if index < 0 and (cat == O.EYES or cat == O.MOUTHS):
            index = 0
        picks.append(index)
    misc = []
    for slot in (MISC_A, MISC_B):
        if dna[slot]:
            misc.append(dna[slot] - 1)
    return picks, tuple(misc)


def colours_of(dna):
    return O.colours(dna[BODY], dna[FACE], dna[EYE_COLOUR], dna[HAIR_COLOUR], dna[FACEHAIR_COLOUR])
