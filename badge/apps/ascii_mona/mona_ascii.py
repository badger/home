"""ASCII Mona: an independent MicroPython take on Ascii-Motion's techniques.

The technique ideas come from Cameron Foxly's Ascii-Motion
(https://github.com/CameronFoxly/Ascii-Motion): 6D shape-vector glyph
matching and Bayer 4x4 ordered dithering. This module is written from
scratch for the badge and shares no code with it.
"""

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
