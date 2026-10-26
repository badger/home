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
WORD_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789"
HEX = "0123456789abcdefABCDEF"

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
BODY_NAMES = (
    "Classic", "Charcoal", "Indigo", "Purple", "Lavender", "Magenta",
    "Crimson", "Rust", "Brown", "Umber", "Slate", "Gold",
    "Olive", "Moss", "Teal", "Ocean", "Blue", "Periwinkle",
)
LABELS = ("Eyes", "Mouth", "Hair", "Hat", "Top", "Bottoms", "Shoes", "Prop", "Eyewear", "Face hair")
NOUNS = ("eyes", "mouth", "hair", "hat", "top", "bottoms", "shoes", "prop", "eyewear", "face hair", "extra")

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
THEME_CHANCE = 30
MATCH_MOUTH = 50  # chance the mouth shares the eyes' expression
MISC_CHANCE = 50
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
# Costume pieces only appear as a whole THEMES outfit, so a random Mona is
# either an everyday outfit or a matching costume, never a jumble of both.
THEME_ONLY = (
    (O.HEADGEAR, ("Hockey Helmet", "Panda Head", "Space Helmet", "Snow Helmet", "Cyclist Helmet", "PJ Cap",
                  "Fire Helmet", "Bunny Hood", "Armor Helmet", "Scuba Hood")),
    (O.TOPS, ("Panda Suit", "Hockey Jersey", "Football Jersey", "Robot Shirt", "Tracksuit", "Astronaut", "Cowboy Vest",
              "Ski Jacket", "Cyclist Shirt", "PJs Shirt", "Super Hero Tights", "Firefighter Jacket", "Wizard Robe",
              "Scuba Wetsuit", "Dancer Tights", "Bunny Suit", "Armor Suit", "World Cup Jersey")),
    (O.BOTTOMS, ("Panda Bottoms", "Hockey Pants", "Football Shorts", "Robot Pants", "Tracksuit Pants", "Space Pants",
                 "Snow Pants", "Cyclist Shorts", "PJ Pants", "Superhero Tights", "Firefighter Pants", "Scuba Pants",
                 "Dancer Tights", "Bunny Suit", "Armor Suit", "Soccer Shorts")),
    (O.FOOTWEAR, ("Panda Shoes", "Hockey", "Football Cleats", "Robot Shoes", "Tracksuit", "Astronaut", "Cyclist Shoes",
                  "PJ Slippers", "Superhero Boots", "Firefighter Boots", "Wizard Sandals", "Scuba Flippers",
                  "Ballet Shoes", "Bunny Suit", "Armor Suit Boots", "Cleats")),
    (O.EYEWEAR, ("Scuba Goggles",)),
)
# Extras that would clash if a Mona wore two from the same group
MISC_GROUPS = (
    ("Cowboy Buckle Belt", "Dress Buckle Belt"),
    ("Scarf", "Bow Tie", "Bolo Tie", "Oxford Tie", "Gold Chain", "Pearls"),
    ("Watch", "Bracelet"),
)
# Matching costumes from the MyOctocat library
THEMES = (
    ((O.HEADGEAR, "Space Helmet"), (O.TOPS, "Astronaut"), (O.BOTTOMS, "Space Pants"), (O.FOOTWEAR, "Astronaut")),
    ((O.HEADGEAR, "Wizard Hat"), (O.TOPS, "Wizard Robe"), (O.FOOTWEAR, "Wizard Sandals"), (O.PROPS, "Wizard Wand")),
    ((O.HEADGEAR, "Fire Helmet"), (O.TOPS, "Firefighter Jacket"), (O.BOTTOMS, "Firefighter Pants"), (O.FOOTWEAR, "Firefighter Boots")),
    ((O.HEADGEAR, "Scuba Hood"), (O.TOPS, "Scuba Wetsuit"), (O.BOTTOMS, "Scuba Pants"), (O.FOOTWEAR, "Scuba Flippers"), (O.EYEWEAR, "Scuba Goggles")),
    ((O.HEADGEAR, "Armor Helmet"), (O.TOPS, "Armor Suit"), (O.BOTTOMS, "Armor Suit"), (O.FOOTWEAR, "Armor Suit Boots"), (O.PROPS, "Sword")),
    ((O.HEADGEAR, "Bunny Hood"), (O.TOPS, "Bunny Suit"), (O.BOTTOMS, "Bunny Suit"), (O.FOOTWEAR, "Bunny Suit")),
    ((O.HEADGEAR, "Panda Head"), (O.TOPS, "Panda Suit"), (O.BOTTOMS, "Panda Bottoms"), (O.FOOTWEAR, "Panda Shoes"), (O.PROPS, "Panda")),
    ((O.HEADGEAR, "Hockey Helmet"), (O.TOPS, "Hockey Jersey"), (O.BOTTOMS, "Hockey Pants"), (O.FOOTWEAR, "Hockey"), (O.PROPS, "Hockey Stick")),
    ((O.TOPS, "Football Jersey"), (O.BOTTOMS, "Football Shorts"), (O.FOOTWEAR, "Football Cleats"), (O.PROPS, "Football")),
    ((O.TOPS, "Robot Shirt"), (O.BOTTOMS, "Robot Pants"), (O.FOOTWEAR, "Robot Shoes")),
    ((O.TOPS, "Tracksuit"), (O.BOTTOMS, "Tracksuit Pants"), (O.FOOTWEAR, "Tracksuit")),
    ((O.HEADGEAR, "Cyclist Helmet"), (O.TOPS, "Cyclist Shirt"), (O.BOTTOMS, "Cyclist Shorts"), (O.FOOTWEAR, "Cyclist Shoes")),
    ((O.HEADGEAR, "PJ Cap"), (O.TOPS, "PJs Shirt"), (O.BOTTOMS, "PJ Pants"), (O.FOOTWEAR, "PJ Slippers")),
    ((O.TOPS, "Super Hero Tights"), (O.BOTTOMS, "Superhero Tights"), (O.FOOTWEAR, "Superhero Boots"), (O.MISC, "Cape")),
    ((O.TOPS, "Dancer Tights"), (O.BOTTOMS, "Dancer Tights"), (O.FOOTWEAR, "Ballet Shoes")),
    ((O.HEADGEAR, "Snow Helmet"), (O.TOPS, "Ski Jacket"), (O.BOTTOMS, "Snow Pants"), (O.FOOTWEAR, "Snow Boots"), (O.PROPS, "Snowboard")),
    ((O.HEADGEAR, "Cowboy Hat"), (O.TOPS, "Cowboy Vest"), (O.FOOTWEAR, "Cowboy Boots"), (O.PROPS, "Lasso"), (O.MISC, "Cowboy Buckle Belt")),
    ((O.TOPS, "World Cup Jersey"), (O.BOTTOMS, "Soccer Shorts"), (O.FOOTWEAR, "Cleats"), (O.PROPS, "Soccer Ball")),
)

# Bio keywords, checked in order; a leading space anchors the start of a word
# and a trailing space the end of one.
TITLE_WORDS = (
    (" maintain", 0), (" open source", 0), (" oss ", 0), (" foss ", 0),
    (" hack", 1), (" security", 1), (" infosec", 1), (" ctf ", 1),
    (" design", 2), (" ux ", 2), (" ui ", 2), (" artist", 2), (" illustrat", 2),
    (" ship", 3), (" devops", 3), (" sre ", 3), (" founder", 3), (" startup", 3),
    (" docs ", 4), (" documentation", 4), (" writer", 4), (" author", 4),
    (" bug", 5), (" qa ", 5), (" tester", 5), (" testing", 5), (" quality", 5),
    (" mentor", 6), (" teach", 6), (" educat", 6), (" advocate", 6), (" devrel", 6),
    (" community", 6), (" speaker", 6),
    (" explor", 7), (" research", 7), (" student", 7), (" learn", 7), (" scien", 7),
)
# (bio keywords, items): interests a bio states, earliest first. The first
# match for a category wins.
BIO_ITEMS = (
    ((" music", " guitar", " band "), ((O.PROPS, "Guitar"),)),
    ((" design", " artist", " illustrat", " paint"), ((O.PROPS, "Paintbrush"),)),
    ((" game", " gaming"), ((O.PROPS, "Game Controller"),)),
    ((" space ", " astro", " nasa ", " rocket", " aerospace"),
     ((O.TOPS, "Astronaut"), (O.BOTTOMS, "Space Pants"), (O.FOOTWEAR, "Astronaut"))),
    ((" wizard", " magic"), ((O.HEADGEAR, "Wizard Hat"), (O.TOPS, "Wizard Robe"), (O.PROPS, "Wizard Wand"))),
    ((" security", " hacker", " infosec", " ctf "), ((O.TOPS, "Zip Up Hoodie"),)),
    ((" ship", " devops", " sre "), ((O.PROPS, "Ship It Squirrel"),)),
    ((" sponsor", " open source", " oss ", " foss "), ((O.PROPS, "Sponsor Heart"),)),
    ((" boba",), ((O.PROPS, "Boba Cup"),)),
    ((" tea ", " coffee", " espresso", " caffeine"), ((O.PROPS, "Tea Mug"),)),
    ((" scien", " research", " phd ", " lab "), ((O.TOPS, "Lab Coat"),)),
    ((" data ", " analyst", " analytics"), ((O.PROPS, "Magnifying Glass"),)),
    ((" book", " writer", " author", " docs ", " documentation", " reading"), ((O.PROPS, "Books"),)),
    ((" photo",), ((O.MISC, "Camera"),)),
    ((" ruby", " rails "), ((O.PROPS, "Ruby Gem"),)),
    ((" skate",), ((O.PROPS, "Skateboard"),)),
    ((" soccer", " football "), ((O.PROPS, "Soccer Ball"),)),
    ((" podcast", " speaker", " singer"), ((O.PROPS, "Microphone"),)),
    ((" mobile", " ios ", " android "), ((O.PROPS, "Smartphone"),)),
    ((" developer", " engineer", " programmer", " coder", " code ", " laptop"), ((O.PROPS, "Laptop"),)),
)
MAX_NOTES = 4

# (label, field) in Tweak order
EDIT = (
    ("Body colour", BODY), ("Face colour", FACE), ("Eyes", PART0 + O.EYES),
    ("Eye colour", EYE_COLOUR), ("Mouth", PART0 + O.MOUTHS), ("Hair", PART0 + O.HAIR),
    ("Hair colour", HAIR_COLOUR), ("Hat", PART0 + O.HEADGEAR), ("Top", PART0 + O.TOPS),
    ("Bottoms", PART0 + O.BOTTOMS), ("Shoes", PART0 + O.FOOTWEAR), ("Prop", PART0 + O.PROPS),
    ("Eyewear", PART0 + O.EYEWEAR), ("Face hair", PART0 + O.FACEHAIR),
    ("Face hair colour", FACEHAIR_COLOUR), ("Extra", MISC_A), ("Second extra", MISC_B),
    ("Title", TITLE), ("Backdrop", BACKDROP),
)
SHOWCASE = (O.HEADGEAR, O.PROPS, O.TOPS, O.EYEWEAR, O.FACEHAIR, O.FOOTWEAR, O.BOTTOMS, O.HAIR)


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
_themes = []


def pool(cat):
    """Part indices a random pick may use in a category."""
    got = _pools[cat]
    if got is None:
        banned = []
        for table in (NOT_RANDOM, THEME_ONLY):
            for entry in table:
                if entry[0] == cat:
                    banned.extend(entry[1])
        got = []
        for index in range(O.count(cat)):
            if O.part_name(cat, index) not in banned:
                got.append(index)
        got = tuple(got)
        _pools[cat] = got
    return got


def themes():
    """THEMES as (category, part index) pairs, names looked up once."""
    if not _themes:
        for theme in THEMES:
            items = []
            for cat, name in theme:
                index = O.find_part(cat, name)
                if index >= 0:
                    items.append((cat, index))
            _themes.append(tuple(items))
    return _themes


def _group(index):
    name = O.part_name(O.MISC, index)
    for i in range(len(MISC_GROUPS)):
        if name in MISC_GROUPS[i]:
            return i
    return -1


def _set_part(dna, cat, index):
    if cat == O.MISC:
        other = dna[MISC_B] - 1
        if other == index or (other >= 0 and _group(other) >= 0 and _group(other) == _group(index)):
            dna[MISC_B] = 0
        dna[MISC_A] = index + 1
    else:
        dna[PART0 + cat] = index + 1


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
    for slot in (MISC_A, MISC_B):
        if rng.below(100) < MISC_CHANCE:
            choices = pool(O.MISC)
            pick = choices[rng.below(len(choices))]
            other = dna[MISC_A] - 1 if slot == MISC_B else -1
            if other < 0 or (pick != other and (_group(pick) < 0 or _group(pick) != _group(other))):
                dna[slot] = pick + 1
    if rng.below(100) < THEME_CHANCE:
        costumes = themes()
        for cat, index in costumes[rng.below(len(costumes))]:
            _set_part(dna, cat, index)
    dna[TITLE] = rng.below(LIMITS[TITLE])
    dna[BACKDROP] = rng.below(LIMITS[BACKDROP])
    return tuple(dna)


def dna_for(handle):
    """The Mona DNA for a GitHub handle; case never matters."""
    return random_dna(seed_of("mona:" + handle.lower()))


def dna_for_uid(uid):
    """A mystery Mona for a badge with no GitHub handle."""
    return random_dna(seed_of("badge:" + str(uid).lower()))


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


def body_rgb(dna):
    """The body swatch (main, light, accent) as 0xRRGGBB values."""
    return P.BODY[dna[BODY] % len(P.BODY)]


def title_of(dna):
    return TITLES[dna[TITLE] % len(TITLES)]


def backdrop_of(dna):
    return dna[BACKDROP] % len(BACKDROPS)


def lowest(field):
    """The smallest value Tweak offers: eyes and mouth are never none."""
    if field == PART0 + O.EYES or field == PART0 + O.MOUTHS:
        return 1
    return 0


def nudge(dna, field, step):
    """DNA with one field moved step places, wrapping around."""
    low = lowest(field)
    value = dna[field]
    if value < low:
        value = low
    out = list(dna)
    out[field] = low + (value - low + step) % (LIMITS[field] - low)
    return tuple(out)


def value_name(dna, field):
    value = dna[field]
    if field == BODY:
        return BODY_NAMES[value % len(BODY_NAMES)]
    if field == TITLE:
        return title_of(dna)
    if field == BACKDROP:
        return BACKDROPS[backdrop_of(dna)]
    if field < PART0:
        return "Swatch %d of %d" % (value + 1, LIMITS[field])
    if field == MISC_A or field == MISC_B:
        return O.part_name(O.MISC, value - 1)
    cat = field - PART0
    if value == 0 and (cat == O.EYES or cat == O.MOUTHS):
        value = 1
    return O.part_name(cat, value - 1)


def extras(dna):
    names = []
    for slot in (MISC_A, MISC_B):
        if dna[slot]:
            names.append(O.part_name(O.MISC, dna[slot] - 1))
    return ", ".join(names) if names else "None"


def describe(dna):
    """(label, value) pairs for the info card, in display order."""
    rows = [("Title", title_of(dna)), ("Body", value_name(dna, BODY))]
    for cat in range(O.PICKS):
        rows.append((LABELS[cat], value_name(dna, PART0 + cat)))
    rows.append(("Extras", extras(dna)))
    rows.append(("Backdrop", BACKDROPS[backdrop_of(dna)]))
    return tuple(rows)


_shared = []


def item_name(cat, index):
    """A part name that reads on its own: MyOctocat names some parts after
    their outfit set, so "Aussie" becomes "Aussie hat" or "Aussie prop"."""
    if not _shared:
        seen = []
        for c in range(O.HAIR, O.MISC + 1):
            for i in range(O.count(c)):
                name = O.part_name(c, i)
                if name in seen and name not in _shared:
                    _shared.append(name)
                seen.append(name)
        _shared.append("")
    name = O.part_name(cat, index)
    if name in _shared:
        return name + " " + NOUNS[cat]
    return name


def highlights(dna, limit=4):
    """The stand-out parts, most eye-catching first, one per outfit set."""
    out = []
    seen = []
    parts = []
    for cat in SHOWCASE:
        if dna[PART0 + cat]:
            parts.append((cat, dna[PART0 + cat] - 1))
    for slot in (MISC_A, MISC_B):
        if dna[slot]:
            parts.append((O.MISC, dna[slot] - 1))
    for cat, index in parts:
        name = O.part_name(cat, index)
        if name not in seen and len(out) < limit:
            seen.append(name)
            out.append(item_name(cat, index))
    return out


def dna_hex(dna):
    return "".join(["%02x" % value for value in dna])


def parse_hex(text):
    """38 hex digits back to DNA, or None."""
    if not isinstance(text, str) or len(text) != SIZE * 2:
        return None
    for ch in text:
        if ch not in HEX:
            return None
    dna = tuple([int(text[i:i + 2], 16) for i in range(0, SIZE * 2, 2)])
    return dna if valid_dna(dna) else None


def short_id(dna):
    """Four hex digits that tell mystery Monas apart."""
    return "%04x" % (fnv1a(bytes(dna)) & 0xFFFF)


def compact(n):
    """1234 -> "1.2k", 12345 -> "12k", 1200000 -> "1.2M"."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "0"
    if n < 1000:
        return str(n)
    for div, suffix in ((1000000000, "B"), (1000000, "M"), (1000, "k")):
        if n >= div:
            tenths = n * 10 // div
            if tenths >= 100 or tenths % 10 == 0:
                return "%d%s" % (tenths // 10, suffix)
            return "%d.%d%s" % (tenths // 10, tenths % 10, suffix)
    return str(n)


def counted(n, word):
    """(1, "repo") -> "1 repo", (1234, "follower") -> "1.2k followers"."""
    return compact(n) + " " + word + ("" if _count(n) == 1 else "s")


def _words(text):
    """Lower-case text with every non [a-z0-9] run as one space, space-padded."""
    if not isinstance(text, str) or not text:
        return " "
    out = [" "]
    for ch in text.lower():
        if ch in WORD_CHARS:
            out.append(ch)
        elif out[-1] != " ":
            out.append(" ")
    if out[-1] != " ":
        out.append(" ")
    return "".join(out)


def _first_match(words, table):
    for needle, value in table:
        if needle in words:
            return value
    return None


def _count(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _year(value):
    if not isinstance(value, str) or len(value) < 4:
        return 0
    try:
        return int(value[:4])
    except ValueError:
        return 0


def _put(dna, cat, name, taken):
    """Wear a named part unless something earlier claimed its category."""
    if cat in taken:
        return False
    index = O.find_part(cat, name)
    if index < 0:
        return False
    _set_part(dna, cat, index)
    taken.append(cat)
    return True


def apply_profile(dna, profile):
    """Tune DNA with a public GitHub profile; returns (dna, notes).

    Only what a profile states changes the Mona: bio interests, activity,
    followers and join year. It never guesses faith, culture, ethnicity,
    gender or disability.
    """
    notes = []
    if not isinstance(profile, dict) or not valid_dna(dna):
        return dna, notes
    out = list(dna)
    taken = []
    bio = _words(profile.get("bio"))
    company = _words(profile.get("company"))

    title_index = _first_match(bio, TITLE_WORDS)
    if title_index is not None:
        notes.append(TITLES[title_index] + ": from bio")
    else:
        repos = _count(profile.get("public_repos"))
        gists = _count(profile.get("public_gists"))
        if repos >= 100:
            title_index = 0
            notes.append("Maintainer: %s repos" % compact(repos))
        elif gists >= 20:
            title_index = 1
            notes.append("Hacker: %s gists" % compact(gists))
    if title_index is not None:
        out[TITLE] = title_index

    staff = profile.get("site_admin") is True
    if (staff or " github " in company) and _put(out, O.PROPS, "Ship It Squirrel", taken):
        notes.append("Ship It Squirrel: " + ("GitHub staff" if staff else "works at GitHub"))

    followers = _count(profile.get("followers"))
    if followers >= 1000 and _put(out, O.HEADGEAR, "Crown", taken):
        notes.append("Crown: %s followers" % compact(followers))

    year = _year(profile.get("created_at"))
    if year and year <= 2010:
        out[BODY] = 0
        notes.append("Classic colours: joined %d" % year)

    for needles, items in BIO_ITEMS:
        hit = False
        for needle in needles:
            if needle in bio:
                hit = True
                break
        if not hit:
            continue
        first = None
        for cat, name in items:
            if _put(out, cat, name, taken) and first is None:
                first = name
        if first is not None:
            notes.append(first + ": from bio")
    return tuple(out), notes[:MAX_NOTES]
