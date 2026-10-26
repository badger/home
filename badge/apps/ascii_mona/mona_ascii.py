"""ASCII Mona: an independent MicroPython take on Ascii-Motion's techniques.

The technique ideas come from Cameron Foxly's Ascii-Motion
(https://github.com/CameronFoxly/Ascii-Motion): 6D shape-vector glyph
matching, Bayer 4x4 ordered dithering, Sobel edge line-art and
ANSI/Phosphor/Amber/Primer character and colour palettes. This module is
written from scratch for the badge and shares no code with it.

The painted Mona (192x216, transparent around her) is halved twice into a
transparent 48x54 sample image, so every sample keeps her coverage as alpha.
Covered samples get a minimum level, which keeps dark bodies visible on a
dark terminal. Each 8x12 teatime cell covers a 2x3 block of samples, which
gives the six-number "shape vector" for that cell. The grid types itself into
a cached image like a terminal, one row every ROW_MS of badge time and never
more than a couple of rows a frame, and is only rebuilt when the Mona, style
or palette changes.
"""

COLS = 24
ROWS = 18
CELL_W = 8
CELL_H = 12
WIDTH = COLS * CELL_W
HEIGHT = ROWS * CELL_H
HALF_W = WIDTH // 2
HALF_H = HEIGHT // 2
SAMPLE_W = COLS * 2
SAMPLE_H = ROWS * 3
BLINK_MS = 500
ROW_MS = 25  # the type-in adds one grid row every ROW_MS of badge.ticks time
FLOOR = 64  # level of a fully covered black sample

SHAPES = 1
DITHER = 2
EDGES = 3

PALETTE_NAMES = ("Primer", "ANSI", "Phosphor", "Amber")
PRIMER = 0
ANSI = 1
PHOSPHOR = 2
AMBER = 3

RAMPS = (" .:+*o%e&@", " .-=?o%S&@", " .:;!*xtk$", " .-=~*oO0@")
BACKS = ((13, 17, 23), (0, 0, 0), (2, 14, 6), (16, 9, 0))
TINTS = (None, None, (51, 255, 102), (255, 176, 0))
# How strongly a covered cell's background takes its glyph colour, per
# style (vector, shapes, dither, edges), like ANSI art's background colours.
BG_PERCENT = (0, 24, 16, 0)
COVERED = 96  # cell coverage (0..255) that earns a background tint

# Primer dark-theme foreground tokens, picked by hue band (upper bound, rgb)
PRIMER_FG = (230, 237, 243)
PRIMER_MUTED = (125, 133, 144)
PRIMER_HUES = (
    (15, (248, 81, 73)),
    (40, (219, 109, 40)),
    (70, (210, 153, 34)),
    (160, (63, 185, 80)),
    (200, (86, 211, 196)),
    (250, (88, 166, 255)),
    (290, (163, 113, 247)),
    (345, (219, 97, 162)),
    (361, (248, 81, 73)),
)
# ANSI hues: red, yellow, green, cyan, blue, magenta as (normal, bright)
ANSI_HUES = (
    ((170, 0, 0), (255, 85, 85)),
    ((170, 170, 0), (255, 255, 85)),
    ((0, 170, 0), (85, 255, 85)),
    ((0, 170, 170), (85, 255, 255)),
    ((0, 0, 170), (85, 85, 255)),
    ((170, 0, 170), (255, 85, 255)),
)
ANSI_GREYS = ((85, 85, 85), (170, 170, 170), (255, 255, 255))

BAYER = (0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5)

# Teatime glyphs that have distinct 6D vectors. Each vector holds the lit
# pixel counts of the glyph's 4x4 regions (2 columns x 3 rows), 2 hex digits
# each. '[' and ']' are left out because the text renderer reads them as
# markup.
CHARS = ' !"#$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVXYZ\\_`abcdefghijklmnopqrstvxyz{|}~'
VEC = "00000000000000010404010102020303000002010906050402030706050402000505020402010805040301010201000003020800050202030008020500000306020200000303010100000000040200000202000000000000010100010305030002020609030401010504040402020506050303020108030400020609000403020704030402020906040403030206020202020808040402020809010400000101010100000101040200000303010300000202020200000303030102020306010102020808040302020906040203010905050302030800040303010804050302030902040302030902040002030804040402010906040203030404040400030008030402010907040302000800050302010907040201010a070403020208040403030209050400020208040405020209050402020206040304030304040202020108040403020108040302020107040402020107050202030303050503010005030003000000000303010100020000000004070405020009040503000006030403000204090305000007060403010309020400000004060509020009040402010104030404000200070306010009050404030008000303000006050403000007040402000006040403000007040903000004060309000007030400000006040304010009030303000006030302000005030402000003060509000004060503030206020502020204040303020302060205000006050001"
GLYPH_MAX = 10


def _glyphs():
    flat = []
    for i in range(len(CHARS) * 6):
        flat.append(int(VEC[i * 2:i * 2 + 2], 16))
    return flat


GLYPHS = _glyphs()
GLYPH_COUNT = len(CHARS)
GAMMA = bytes([int(255 * ((i / 255.0) ** 0.7) + 0.5) for i in range(256)])

_shape_cache = {}


def match_shape(v):
    """Index into CHARS of the glyph whose shape best fits six 0..255 levels."""
    m = max(v)
    if m < 12:
        return 0
    q0 = (v[0] * v[0] // m * GLYPH_MAX + 127) // 255
    q1 = (v[1] * v[1] // m * GLYPH_MAX + 127) // 255
    q2 = (v[2] * v[2] // m * GLYPH_MAX + 127) // 255
    q3 = (v[3] * v[3] // m * GLYPH_MAX + 127) // 255
    q4 = (v[4] * v[4] // m * GLYPH_MAX + 127) // 255
    q5 = (v[5] * v[5] // m * GLYPH_MAX + 127) // 255
    key = ((((q0 * 11 + q1) * 11 + q2) * 11 + q3) * 11 + q4) * 11 + q5
    hit = _shape_cache.get(key)
    if hit is not None:
        return hit
    g = GLYPHS
    best = 0
    best_d = 1 << 30
    j = 0
    for i in range(GLYPH_COUNT):
        a = g[j] - q0
        b = g[j + 1] - q1
        c = g[j + 2] - q2
        d = g[j + 3] - q3
        e = g[j + 4] - q4
        f = g[j + 5] - q5
        dist = a * a + b * b + c * c + d * d + e * e + f * f
        if dist < best_d:
            best_d = dist
            best = i
        j += 6
    if len(_shape_cache) > 4096:
        _shape_cache.clear()
    _shape_cache[key] = best
    return best


def dither_index(level, x, y, steps):
    """Ramp index for a 0..255 level, ordered-dithered with Bayer 4x4."""
    v = level * (steps - 1) * 16 // 255
    base = v >> 4
    if (v & 15) > BAYER[(y & 3) * 4 + (x & 3)]:
        base += 1
    if base >= steps:
        base = steps - 1
    return base


def edge_char(means, x, y, ramp, cols=COLS, rows=ROWS):
    """Sobel line-art for cell (x, y) from a grid of cell levels."""

    def at(cx, cy):
        if cx < 0:
            cx = 0
        elif cx >= cols:
            cx = cols - 1
        if cy < 0:
            cy = 0
        elif cy >= rows:
            cy = rows - 1
        return means[cy * cols + cx]

    tl = at(x - 1, y - 1)
    tc = at(x, y - 1)
    tr = at(x + 1, y - 1)
    ml = at(x - 1, y)
    mr = at(x + 1, y)
    bl = at(x - 1, y + 1)
    bc = at(x, y + 1)
    br = at(x + 1, y + 1)
    gx = (tr + 2 * mr + br) - (tl + 2 * ml + bl)
    gy = (bl + 2 * bc + br) - (tl + 2 * tc + tr)
    ax = gx if gx >= 0 else -gx
    ay = gy if gy >= 0 else -gy
    if ax + ay > 220:
        if ax > 2 * ay:
            return "|"
        if ay > 2 * ax:
            return "-"
        return "/" if gx * gy > 0 else "\\"
    level = means[y * cols + x]
    if level > 200:
        return ramp[2]
    if level > 110:
        return ramp[1]
    return " "


def hue(r, g, b, mx, mn):
    d = mx - mn
    if d <= 0:
        return 0
    if mx == r:
        h = 60.0 * (g - b) / d
    elif mx == g:
        h = 60.0 * (b - r) / d + 120
    else:
        h = 60.0 * (r - g) / d + 240
    return int(h) % 360


def blend(a, b, percent):
    """Mix colour a toward b by an integer percent."""
    return (
        a[0] + (b[0] - a[0]) * percent // 100,
        a[1] + (b[1] - a[1]) * percent // 100,
        a[2] + (b[2] - a[2]) * percent // 100,
    )


def colour_for(palette, rgb, level):
    """Glyph colour for a cell's average colour and 0..255 level."""
    tint = TINTS[palette] if 0 <= palette < len(TINTS) else None
    if tint is not None:
        step = 3 + (level * 5) // 255
        return (tint[0] * step // 8, tint[1] * step // 8, tint[2] * step // 8)
    r, g, b = rgb[0], rgb[1], rgb[2]
    mx = max(r, g, b)
    mn = min(r, g, b)
    sat = (mx - mn) * 100 // mx if mx else 0
    if palette == ANSI:
        if mx < 24 or sat < 28:
            return ANSI_GREYS[2] if level > 170 else ANSI_GREYS[1] if level > 80 else ANSI_GREYS[0]
        h = (hue(r, g, b, mx, mn) + 30) % 360
        pair = ANSI_HUES[h // 60]
        return pair[1] if level > 110 else pair[0]
    if mx < 24 or sat < 12:
        return PRIMER_FG if level > 150 else PRIMER_MUTED
    h = hue(r, g, b, mx, mn)
    tone = PRIMER_FG
    for top, hue_tone in PRIMER_HUES:
        if h < top:
            tone = hue_tone
            break
    # Pale colours (Mona's lavender face) stay pale instead of turning grey.
    return blend(PRIMER_FG, tone, sat * 3 if sat < 33 else 100)


def levels_from_raw(raw, count, floor=FLOOR):
    """Per-sample levels from premultiplied RGBA: coverage-floored
    luminance, stretched so the brightest sample is 255, then gamma 0.7.
    Transparent samples stay 0 (blank)."""
    lum = bytearray(count)
    keep = 255 - floor
    hi = 0
    j = 0
    for i in range(count):
        a = raw[j + 3]
        if a:
            v = (54 * raw[j] + 183 * raw[j + 1] + 19 * raw[j + 2]) >> 8
            v = (floor * a + v * keep) // 255
            if v > 255:
                v = 255
            lum[i] = v
            if v > hi:
                hi = v
        j += 4
    if hi < 24:
        hi = 255
    lut = bytearray(256)
    for v in range(256):
        s = v * 255 // hi
        lut[v] = GAMMA[s if s < 255 else 255]
    for i in range(count):
        lum[i] = lut[lum[i]]
    return lum


def cell_samples(levels, x, y, sample_w=SAMPLE_W):
    i = y * 3 * sample_w + x * 2
    return (
        levels[i], levels[i + 1],
        levels[i + sample_w], levels[i + sample_w + 1],
        levels[i + 2 * sample_w], levels[i + 2 * sample_w + 1],
    )


def cell_rgba(raw, x, y, sample_w=SAMPLE_W):
    """Average colour of a cell's covered samples (raw is premultiplied)
    and its coverage, 0..255."""
    r = 0
    g = 0
    b = 0
    a = 0
    for dy in range(3):
        j = ((y * 3 + dy) * sample_w + x * 2) * 4
        r += raw[j] + raw[j + 4]
        g += raw[j + 1] + raw[j + 5]
        b += raw[j + 2] + raw[j + 6]
        a += raw[j + 3] + raw[j + 7]
    if a <= 0:
        return (0, 0, 0, 0)
    r = r * 255 // a
    g = g * 255 // a
    b = b * 255 // a
    return (r if r < 255 else 255, g if g < 255 else 255, b if b < 255 else 255, a // 6)


def cell_means(levels, cols=COLS, rows=ROWS):
    means = bytearray(cols * rows)
    for y in range(rows):
        for x in range(cols):
            s = cell_samples(levels, x, y, cols * 2)
            means[y * cols + x] = (s[0] + s[1] + s[2] + s[3] + s[4] + s[5]) // 6
    return means


def convert_row(style, palette, raw, levels, means, y, cols=COLS, rows=ROWS):
    """(char, fg, bg) for every cell of grid row y; fg and bg are rgb
    tuples, or None for a blank glyph or an untinted background."""
    ramp = RAMPS[palette]
    steps = len(ramp)
    back = BACKS[palette]
    pct = BG_PERCENT[style] if 0 <= style < len(BG_PERCENT) else 0
    out = []
    for x in range(cols):
        s = cell_samples(levels, x, y, cols * 2)
        mean = (s[0] + s[1] + s[2] + s[3] + s[4] + s[5]) // 6
        if style == EDGES and means is not None:
            ch = edge_char(means, x, y, ramp, cols, rows)
        elif style == DITHER:
            ch = ramp[dither_index(mean, x, y, steps)]
        else:
            ch = CHARS[match_shape(s)]
        tinted = False
        if pct:
            r, g, b, cover = cell_rgba(raw, x, y, cols * 2)
            tinted = cover >= COVERED
        if ch == " " and not tinted:
            out.append((ch, None, None))
            continue
        if not pct:
            r, g, b, cover = cell_rgba(raw, x, y, cols * 2)
        level = mean
        if style == EDGES and level < 140:
            level = 140
        tone = colour_for(palette, (r, g, b), level)
        bg = blend(back, tone, pct * cover // 255) if tinted else None
        out.append((ch, None if ch == " " else tone, bg))
    return out


def grid_text(cells):
    """Rows of (char, fg, bg) cells as plain text lines (for tests and logs)."""
    return ["".join(cell[0] for cell in row) for row in cells]


def pen_for(rgb):
    return color.rgb(rgb[0], rgb[1], rgb[2])


def cursor_colour(palette):
    return colour_for(palette, PRIMER_FG, 255)


class AsciiView:
    """Converts the painted Mona into a cached grid image, a row every ROW_MS."""

    def __init__(self):
        self.half = None
        self.sample = None
        self.cache = None
        self.source = None
        self.style = SHAPES
        self.palette = PRIMER
        self.row = 0
        self.since = None
        self.raw = None
        self.levels = None
        self.means = None
        self.ready = False
        self.dirty = False
        self.failed = False

    def _images(self):
        if self.cache is not None or self.failed:
            return not self.failed
        try:
            self.half = image(HALF_W, HALF_H)
            self.sample = image(SAMPLE_W, SAMPLE_H)
            self.cache = image(WIDTH, HEIGHT)
            self.cache.font = font.teatime
        except Exception:
            self.failed = True
            self.half = None
            self.sample = None
            self.cache = None
            return False
        self.restart()
        return True

    def set_source(self, art):
        """Convert art: a WIDTH x HEIGHT image, transparent around Mona."""
        self.source = art
        self.restart()

    def clear(self):
        """Forget the source while a new Mona paints."""
        self.source = None
        self.restart()

    def set_mode(self, style, palette):
        if style != self.style or palette != self.palette:
            self.style = style
            self.palette = palette
            self.restart()

    def restart(self):
        self.row = 0
        self.since = None
        self.ready = False
        self.dirty = self.source is not None
        self.raw = None
        self.levels = None
        self.means = None
        if self.cache is not None:
            self.cache.pen = pen_for(BACKS[self.palette])
            self.cache.clear()

    @property
    def typing(self):
        return self.dirty and self.source is not None and not self.failed

    def _sample(self):
        clear = color.rgb(0, 0, 0, 0)
        half = self.half
        half.pen = clear
        half.clear()
        half.blit(self.source, rect(0, 0, WIDTH, HEIGHT), rect(0, 0, HALF_W, HALF_H), image.BILINEAR)
        sample = self.sample
        sample.pen = clear
        sample.clear()
        sample.blit(half, rect(0, 0, HALF_W, HALF_H), rect(0, 0, SAMPLE_W, SAMPLE_H), image.BILINEAR)
        self.raw = sample.raw
        self.levels = levels_from_raw(self.raw, SAMPLE_W * SAMPLE_H)
        self.means = cell_means(self.levels) if self.style == EDGES else None

    def step(self, rows=2, now=None):
        """Type the grid rows due by badge time now, one every ROW_MS from the
        first step but at most rows a frame (rows a call when now is None);
        True when the grid completes."""
        if not self.typing or not self._images():
            return False
        if now is not None:
            if self.since is None:
                self.since = now
            rows = min(rows, (now - self.since) // ROW_MS + 1 - self.row)
        for _ in range(rows):
            if self.raw is None:
                self._sample()
            cells = convert_row(self.style, self.palette, self.raw, self.levels, self.means, self.row)
            self._paint_row(self.row, cells)
            self.row += 1
            if self.row >= ROWS:
                self.row = 0
                self.dirty = False
                self.ready = True
                self.raw = None
                self.levels = None
                self.means = None
                return True
        return False

    def _paint_row(self, y, cells):
        img = self.cache
        top = y * CELL_H
        img.pen = pen_for(BACKS[self.palette])
        img.shape(shape.rectangle(0, top, WIDTH, CELL_H))
        x = 0
        for ch, fg, bg in cells:
            if bg is not None:
                img.pen = pen_for(bg)
                img.shape(shape.rectangle(x, top, CELL_W, CELL_H))
            if fg is not None:
                img.pen = pen_for(fg)
                img.text(ch, x, top)
            x += CELL_W

    def draw(self, target, x, y, now):
        """Blit the grid, with a terminal cursor while it types itself in;
        False when there is no grid yet."""
        if self.cache is None:
            return False
        target.blit(self.cache, vec2(x, y))
        if self.typing and (now // BLINK_MS) % 2 == 0:
            target.pen = pen_for(cursor_colour(self.palette))
            target.shape(shape.rectangle(x + 1, y + self.row * CELL_H + 1, CELL_W - 2, CELL_H - 2))
        return True
