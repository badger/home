"""The real MyOctocat art: outfit rules and a progressive badge painter.

The part library is GitHub's own MyOctocat builder
(https://myoctocat.com/build-your-octocat/). The ascii_mona bake tool turned
its SVG parts into octocat.bin, and mona_parts indexes that file. Octocat art
(c) GitHub.

compose() applies the builder's paint order and hide rules (a hat hides big
hair, a prop replaces the waving hand, a long top hides the trousers) and is
plain Python, so the host tests share it with the badge. Painter streams one
outfit's polygons from flash into an offscreen image, paced by badge time
(one layer every LAYER_MS) and capped by a per-frame time budget.
"""

from array import array

import mona_parts as P

try:
    from time import ticks_diff, ticks_ms
except ImportError:
    import time

    def ticks_ms():
        return int(time.time() * 1000)

    def ticks_diff(a, b):
        return a - b


LAYER_MS = 4  # the paint-in lays one layer every LAYER_MS of badge.ticks time

EYES = 0
MOUTHS = 1
HAIR = 2
HEADGEAR = 3
TOPS = 4
BOTTOMS = 5
FOOTWEAR = 6
PROPS = 7
EYEWEAR = 8
FACEHAIR = 9
MISC = 10
PICKS = 10  # categories with one pick each; MISC takes a tuple

# Art frame in SVG units (left, top, width, height): the base Octocat with
# room for every hat, prop and pair of shoes in the library.
FRAME = (P.BOX[0], P.BOX[1], P.BOX[2] - P.BOX[0], P.BOX[3] - P.BOX[1])

CUSTOM = 0xFF
ORIGINAL = 1
MASKED = 2


def count(cat):
    return len(P.PARTS[cat])


def part_name(cat, index):
    parts = P.PARTS[cat]
    if index is None or index < 0 or index >= len(parts):
        return "None"
    return parts[index][0]


def find_part(cat, name):
    """Index of the part called name in a category, or -1."""
    parts = P.PARTS[cat]
    for i in range(len(parts)):
        if parts[i][0] == name:
            return i
    return -1


def colours(body, face, eye, hair, facehair):
    """0xRRGGBB for each paint role, in mona_parts.ROLES order."""
    b = P.BODY[body % len(P.BODY)]
    f = P.FACE[face % len(P.FACE)]
    return (
        b[0], b[1], b[2], f[0], f[1],
        P.EYE[eye % len(P.EYE)],
        P.HAIR[hair % len(P.HAIR)],
        P.FACEHAIR[facehair % len(P.FACEHAIR)],
    )


def _hidden(kind, cls, flags):
    if kind & P.K_HAIR and flags & P.F_NO_HAIR:
        return True
    if kind & P.K_BOTTOMS and flags & P.F_NO_PANTS:
        return True
    if kind & P.K_FH_BACK and flags & P.F_NO_BACK_FH:
        return True
    if kind & P.K_FH_LOW and flags & P.F_HIDE_LOW_FH:
        return True
    if cls & P.H_BIG_HAIR and flags & P.F_NO_BIG_HAIR:
        return True
    if cls & P.H_MEDIUM_HAIR and flags & P.F_NO_MEDIUM_HAIR:
        return True
    if cls & P.H_BIG_COLLAR and flags & P.F_NO_BIG_COLLARS:
        return True
    if cls & P.H_XL and flags & P.F_NO_XL:
        return True
    if cls & P.H_XXL and flags & P.F_NO_XXL:
        return True
    return False


def compose(picks, misc=()):
    """Blocks to paint for an outfit, back to front.

    picks holds one part index per category up to FACEHAIR (-1 for none) and
    misc a tuple of misc part indices. Returns (blocks, flags), where blocks
    are (offset, length) pairs in octocat.bin.
    """
    chosen = []
    for cat in range(PICKS):
        index = picks[cat] if cat < len(picks) else -1
        if index is not None and 0 <= index < len(P.PARTS[cat]):
            chosen.append(P.PARTS[cat][index])
    seen = []
    for index in misc:
        if 0 <= index < len(P.PARTS[MISC]) and index not in seen:
            seen.append(index)
            chosen.append(P.PARTS[MISC][index])

    holders = len(P.HOLDERS)
    classes = [0] * holders
    content = [None] * holders
    flags = 0
    for part in chosen:
        flags |= part[1]
        for holder, cls, offset, length in part[2]:
            classes[holder] = cls
            if content[holder] is None:
                content[holder] = []
            content[holder].append((offset, length))

    blocks = []
    for step in P.ORDER:
        if step < 0:
            base = P.BASE[~step]
            if not base[1] & flags:
                blocks.append((base[2], base[3]))
            continue
        items = content[step]
        if items and not _hidden(P.HOLDERS[step][2], classes[step], flags):
            for item in items:
                blocks.append(item)
    return blocks, flags


def skip_variant(flags):
    """Hair layers drawn only under hats are MASKED; the rest ORIGINAL."""
    return ORIGINAL if flags & P.F_NO_BIG_HAIR else MASKED


def layers(data):
    """Yield (role, rgb, alpha, variant, contours) for one block.

    role indexes mona_parts.ROLES, or is CUSTOM with rgb set. Each contour is
    bytes of little-endian int16 (x, y) pairs in SVG units * mona_parts.Q.
    """
    count = data[0] | (data[1] << 8)
    pos = 2
    for _ in range(count):
        role = data[pos]
        pos += 1
        rgb = 0
        if role == CUSTOM:
            rgb = (data[pos] << 16) | (data[pos + 1] << 8) | data[pos + 2]
            pos += 3
        alpha = data[pos]
        variant = data[pos + 1]
        contours = data[pos + 2] | (data[pos + 3] << 8)
        pos += 4
        out = []
        for _ in range(contours):
            n = (data[pos] | (data[pos + 1] << 8)) * 4
            pos += 2
            out.append(data[pos:pos + n])
            pos += n
        yield role, rgb, alpha, variant, out


def fit(width, height, margin=0):
    """(scale, x, y) that centre FRAME in a width x height box."""
    sx = (width - 2 * margin) / FRAME[2]
    sy = (height - 2 * margin) / FRAME[3]
    s = sx if sx < sy else sy
    x = (width - FRAME[2] * s) / 2 - FRAME[0] * s
    y = (height - FRAME[3] * s) / 2 - FRAME[1] * s
    return s, x, y


def check_header(head):
    return len(head) >= 6 and head[0:4] == b"OCTO" and head[4] == P.VERSION and head[5] == P.Q


class Painter:
    """Draws one outfit into an offscreen image over several frames."""

    def __init__(self, path=None):
        self.path = path or P.BIN
        self.file = None
        self.failed = ""
        self.target = None
        self.blocks = ()
        self.block = 0
        self.current = None
        self.skip = MASKED
        self.colours = None
        self.transform = None
        self.done = True
        self.drawn = 0
        self.errors = 0
        self.laid = 0
        self.since = None

    def _open(self):
        if self.file is not None or self.failed:
            return self.file is not None
        try:
            self.file = open(self.path, "rb")
            if not check_header(self.file.read(6)):
                self.failed = "art file is the wrong version"
        except OSError:
            self.failed = "art file missing"
        if self.failed and self.file is not None:
            self.close()
        return self.file is not None

    def close(self):
        if self.file is not None:
            try:
                self.file.close()
            except OSError:
                pass
        self.file = None

    def start(self, target, blocks, flags, palette, scale, x, y):
        """Begin painting blocks into target at scale, offset (x, y)."""
        self.target = target
        self.blocks = blocks
        self.block = 0
        self.current = None
        self.skip = skip_variant(flags)
        self.colours = palette
        k = scale / P.Q
        self.transform = mat3().translate(x, y).scale(k)
        self.drawn = 0
        self.errors = 0
        self.laid = 0
        self.since = None
        self.done = not self._open()
        target.antialias = image.X4
        target.fill_rule = image.NON_ZERO

    def progress(self):
        """0..100 for a progress bar."""
        if self.done or not self.blocks:
            return 100
        return self.block * 100 // len(self.blocks)

    def _next_layer(self):
        while True:
            if self.current is not None:
                for layer in self.current:
                    return layer
                self.current = None
                self.block += 1
            if self.block >= len(self.blocks):
                return None
            offset, length = self.blocks[self.block]
            try:
                self.file.seek(offset)
                data = self.file.read(length)
            except OSError:
                data = b""
            if len(data) != length:
                self.errors += 1
                self.block += 1
                continue
            self.current = layers(data)

    def _pen(self, role, rgb, alpha):
        if role != CUSTOM:
            rgb = self.colours[role] if role < len(self.colours) else 0
        return color.rgb((rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF, alpha)

    def step(self, budget_ms=18, now=None):
        """Lay the layers due by badge time now, one every LAYER_MS from the
        first step (all of them when now is None), stopping once this frame
        has spent about budget_ms; returns True once the outfit is done."""
        if self.done:
            return True
        if now is not None and self.since is None:
            self.since = now
        began = ticks_ms()
        target = self.target
        while now is None or self.laid <= (now - self.since) // LAYER_MS:
            layer = self._next_layer()
            if layer is None:
                self.done = True
                self.current = None
                return True
            role, rgb, alpha, variant, contours = layer
            if variant != self.skip and contours:
                self.laid += 1
                try:
                    made = shape.custom(*[array("f", array("h", c)) for c in contours])
                    made.transform = self.transform
                    target.pen = self._pen(role, rgb, alpha)
                    target.shape(made)
                    self.drawn += 1
                except (ValueError, TypeError, MemoryError):
                    self.errors += 1
            if ticks_diff(ticks_ms(), began) >= budget_ms:
                return False
        return False

