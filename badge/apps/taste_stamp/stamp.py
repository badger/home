# Rubber-stamp artwork for Taste Stamp: a stroked block font.
#
# Everything here is plain Python that emits flat [x0, y0, x1, y1, ...]
# contours for shape.custom(), so it runs unchanged on the badge and under
# CPython tests. Every contour winds the same way, so drawing a group of
# contours as one shape with the NON_ZERO fill rule paints their union.

import math

# Stamp units: capitals are CAP tall, y grows downwards.
CAP = 6.0
STROKE = 1.42
TRACKING = 2.45
SPACE = 1.8
MITER_LIMIT = 2.0

# Glyphs: character -> (width, strokes). A stroke is a tuple of points,
# optionally led by a cap code: "B." butt start, ".B" butt end, "BB" both.
# Other ends get square caps. Glyphs are 4 wide unless noted.
GLYPHS = {
    "A": (4, (((0, 6), (0, 1), (1, 0), (3, 0), (4, 1), (4, 6)), ("BB", (0, 3.5), (4, 3.5)))),
    "B": (4, ((".B", (0, 3), (3, 3), (4, 4), (4, 5), (3, 6), (0, 6), (0, 0), (3, 0), (4, 1), (4, 2), (3, 3)),)),
    "C": (4, (((4, 0), (1, 0), (0, 1), (0, 5), (1, 6), (4, 6)),)),
    "D": (4, (((0, 0), (3, 0), (4, 1), (4, 5), (3, 6), (0, 6), (0, 0)),)),
    "E": (4, (((4, 0), (0, 0), (0, 6), (4, 6)), ("B.", (0, 3), (3.2, 3)))),
    "F": (4, (((4, 0), (0, 0), (0, 6)), ("B.", (0, 3), (3.2, 3)))),
    "G": (4, (((4, 0), (1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5), (4, 3), (2, 3)),)),
    "H": (4, (((0, 0), (0, 6)), ((4, 0), (4, 6)), ("BB", (0, 3), (4, 3)))),
    "I": (2, (((0, 0), (2, 0)), ((0, 6), (2, 6)), ("BB", (1, 0), (1, 6)))),
    "J": (4, (((1.5, 0), (4, 0), (4, 5), (3, 6), (1, 6), (0, 5), (0, 4)),)),
    "K": (4, (((0, 0), (0, 6)), ((4, 0), (4, 0.6), (1.6, 3), (0, 3)), ("B.", (1.6, 3), (4, 5.4), (4, 6)))),
    "L": (4, (((0, 0), (0, 6), (4, 6)),)),
    "M": (5, (((0, 6), (0, 0)), ((5, 0), (5, 6)), ("BB", (0, 0), (2, 3.6), (3, 3.6), (5, 0)))),
    "N": (4, (((0, 6), (0, 0)), ((4, 0), (4, 6)), ("BB", (0, 0), (4, 6)))),
    "O": (4, (((0, 3), (0, 1), (1, 0), (3, 0), (4, 1), (4, 5), (3, 6), (1, 6), (0, 5), (0, 3)),)),
    "P": (4, (((0, 6), (0, 0), (3, 0), (4, 1), (4, 2.5), (3, 3.5), (0, 3.5)),)),
    "Q": (4, (((0, 3), (0, 1), (1, 0), (3, 0), (4, 1), (4, 5), (3, 6), (1, 6), (0, 5), (0, 3)), ("B.", (2.6, 4.6), (4.4, 6.4)))),
    "R": (4, (((0, 6), (0, 0), (3, 0), (4, 1), (4, 2.5), (3, 3.5), (0, 3.5)), ("B.", (2, 3.5), (4, 5), (4, 6)))),
    "S": (4, (((4, 0), (1, 0), (0, 1), (0, 2), (1, 3), (3, 3), (4, 4), (4, 5), (3, 6), (0, 6)),)),
    "T": (4, (((0, 0), (4, 0)), ("B.", (2, 0), (2, 6)))),
    "U": (4, (((0, 0), (0, 5), (1, 6), (3, 6), (4, 5), (4, 0)),)),
    "V": (4, (((0, 0), (0, 1.5), (1.6, 6), (2.4, 6), (4, 1.5), (4, 0)),)),
    "W": (5, (((0, 0), (0, 6)), ((5, 0), (5, 6)), ("BB", (0, 6), (2, 2.4), (3, 2.4), (5, 6)))),
    "X": (4, (((0, 0), (0, 0.8), (4, 5.2), (4, 6)), ((4, 0), (4, 0.8), (0, 5.2), (0, 6)))),
    "Y": (4, (((0, 0), (0, 1), (2, 3), (4, 1), (4, 0)), ("B.", (2, 3), (2, 6)))),
    "Z": (4, (((0, 0), (4, 0), (4, 0.8), (0, 5.2), (0, 6), (4, 6)),)),
    "0": (4, (((0, 3), (0, 1), (1, 0), (3, 0), (4, 1), (4, 5), (3, 6), (1, 6), (0, 5), (0, 3)), ("BB", (1, 4.6), (3, 1.4)))),
    "1": (4, (((2.2, 0), (2.2, 6)), ("B.", (2.2, 0), (0.8, 1.4)), ((0.8, 6), (3.6, 6)))),
    "2": (4, (((0, 1), (1, 0), (3, 0), (4, 1), (4, 2.2), (0, 5.2), (0, 6), (4, 6)),)),
    "3": (4, (((0, 0), (3, 0), (4, 1), (4, 2), (3, 3), (4, 4), (4, 5), (3, 6), (0, 6)), ("B.", (1.2, 3), (3, 3)))),
    "4": (4, (((0, 0), (0, 3.6), (4, 3.6)), ((3, 0), (3, 6)))),
    "5": (4, (((4, 0), (0, 0), (0, 2.6), (3, 2.6), (4, 3.6), (4, 5), (3, 6), (0, 6)),)),
    "6": (4, (((4, 0), (1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5), (4, 3.6), (3, 2.6), (0, 2.6)),)),
    "7": (4, (((0, 0), (4, 0), (4, 0.8), (1.5, 6)),)),
    "8": (4, (("BB", (1, 3), (0, 2), (0, 1), (1, 0), (3, 0), (4, 1), (4, 2), (3, 3), (1, 3), (0, 4), (0, 5), (1, 6), (3, 6), (4, 5), (4, 4), (3, 3)),)),
    "9": (4, (((4, 3.4), (1, 3.4), (0, 2.4), (0, 1), (1, 0), (3, 0), (4, 1), (4, 5), (3, 6), (0, 6)),)),
    "?": (4, (((0, 1.6), (0, 1), (1, 0), (3, 0), (4, 1), (4, 2), (3, 3), (2, 3), (2, 3.9)), ((2, 5.6), (2, 6)))),
    "!": (0, (((0, 0), (0, 3.9)), ((0, 5.6), (0, 6)))),
    ".": (0, (((0, 5.6), (0, 6)),)),
    ",": (0, (("B.", (0, 5.6), (0, 6.2), (-0.6, 7.2)),)),
    "'": (0, (((0, 0), (0, 1.6)),)),
    ":": (0, (((0, 1.6), (0, 2)), ((0, 5.6), (0, 6)))),
    "-": (3, (((0, 3.2), (3, 3.2)),)),
    "+": (4, (((2, 1.4), (2, 4.6)), ((0.4, 3), (3.6, 3)))),
    "/": (4, (((0, 6), (4, 0)),)),
}


def area2(contour):
    # Twice the signed area of a flat contour (shoelace formula).
    total = 0.0
    n = len(contour)
    for i in range(0, n, 2):
        j = (i + 2) % n
        total += contour[i] * contour[j + 1] - contour[j] * contour[i + 1]
    return total


def _positive(contour):
    if area2(contour) >= 0:
        return contour
    flipped = []
    for i in range(len(contour) - 2, -1, -2):
        flipped.append(contour[i])
        flipped.append(contour[i + 1])
    return flipped


def _join(px, py, ax, ay, bx, by, cos, cross, hw, out):
    # Fill the outer wedge of a turn sharper than 90 degrees with a mitre, or
    # a bevel when the mitre would be longer than MITER_LIMIT stroke halves.
    side = -hw if cross > 0 else hw
    oax = -ay * side
    oay = ax * side
    obx = -by * side
    oby = bx * side
    half_cos = math.sqrt(max(0.0, (1.0 + cos) * 0.5))
    if half_cos * MITER_LIMIT >= 1.0:
        k = 1.0 / (1.0 + cos)
        poly = [px, py, px + oax, py + oay, px + (oax + obx) * k, py + (oay + oby) * k, px + obx, py + oby]
    else:
        poly = [px, py, px + oax, py + oay, px + obx, py + oby]
    out.append(_positive(poly))


def stroke_path(points, hw, out, cap0=True, cap1=True):
    # Append one quad per segment (plus wedges for sharp turns) to out.
    # Turns up to 90 degrees are mitred by lengthening both segments.
    pts = []
    for p in points:
        if not pts or abs(p[0] - pts[-1][0]) > 1e-6 or abs(p[1] - pts[-1][1]) > 1e-6:
            pts.append((float(p[0]), float(p[1])))
    n = len(pts)
    if n < 2:
        return out
    ux = []
    uy = []
    for i in range(n - 1):
        dx = pts[i + 1][0] - pts[i][0]
        dy = pts[i + 1][1] - pts[i][1]
        d = math.sqrt(dx * dx + dy * dy)
        ux.append(dx / d)
        uy.append(dy / d)
    head = [0.0] * (n - 1)
    tail = [0.0] * (n - 1)
    if cap0:
        head[0] = hw
    if cap1:
        tail[n - 2] = hw
    for j in range(1, n - 1):
        ax = ux[j - 1]
        ay = uy[j - 1]
        bx = ux[j]
        by = uy[j]
        cos = ax * bx + ay * by
        cross = ax * by - ay * bx
        if cos >= 0:
            extend = hw * abs(cross) / (1.0 + cos)
            tail[j - 1] = extend
            head[j] = extend
        else:
            _join(pts[j][0], pts[j][1], ax, ay, bx, by, cos, cross, hw, out)
    for i in range(n - 1):
        dx = ux[i]
        dy = uy[i]
        sx = pts[i][0] - dx * head[i]
        sy = pts[i][1] - dy * head[i]
        ex = pts[i + 1][0] + dx * tail[i]
        ey = pts[i + 1][1] + dy * tail[i]
        nx = -dy * hw
        ny = dx * hw
        out.append([sx + nx, sy + ny, sx - nx, sy - ny, ex - nx, ey - ny, ex + nx, ey + ny])
    return out


def _caps(stroke):
    if stroke and isinstance(stroke[0], str):
        code = stroke[0]
        return code[0] != "B", code[1] != "B", stroke[1:]
    return True, True, stroke


def layout_line(text):
    # Returns ([(glyph, x)], width): x is each glyph's left stroke centre and
    # width spans the outermost stroke centres. Unknown characters are spaces.
    items = []
    x = 0.0
    right = 0.0
    for ch in text:
        glyph = GLYPHS.get(ch)
        if glyph is None:
            if items:
                x += SPACE
            continue
        items.append((glyph, x))
        right = x + glyph[0]
        x = right + TRACKING
    return items, right


def line_width(text):
    return layout_line(text.upper())[1]


def glyph_contours(glyph, left, top, scale, hw):
    out = []
    for stroke in glyph[1]:
        cap0, cap1, pts = _caps(stroke)
        path = []
        for p in pts:
            path.append((left + p[0] * scale, top + p[1] * scale))
        stroke_path(path, hw, out, cap0, cap1)
    return out


def text_groups(text, cx, top, scale, hw, groups):
    # One group per glyph keeps each shape small for the rasteriser.
    items, width = layout_line(text.upper())
    left = cx - width * scale * 0.5
    for glyph, x in items:
        contours = glyph_contours(glyph, left + x * scale, top, scale, hw)
        if contours:
            groups.append(contours)
    return width * scale
