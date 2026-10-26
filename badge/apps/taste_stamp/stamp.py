# Rubber-stamp artwork for Taste Stamp: a stroked block font, the stamp
# layout, and the slam, shake, strobe and ink-splatter curves.
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
SMALL = 0.42
SMALL_STROKE = 0.6
BORDER = 1.5
INNER = 0.5
INNER_GAP = 1.8
PAD_X = 2.6
PAD_Y = 1.4
RULE = 0.5
LINE_PITCH = 8.4
DIAMOND = 0.9
DIAMOND_GAP = 1.2
MAX_SINGLE_LINE = 9
MAX_GROW = 1.45
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


def _break_line(line):
    # The line break already separates the clauses, so a trailing comma would
    # only dangle down beside the next line's capitals.
    if line.endswith(","):
        bare = line[:-1].rstrip()
        if bare:
            return bare
    return line


def wrap(text, limit=MAX_SINGLE_LINE):
    # One line when short, otherwise the two-line break whose longer line is
    # shortest, preferring the longer first line on ties.
    text = text.strip()
    words = []
    for word in text.split(" "):
        if word:
            words.append(word)
    if len(text) <= limit or len(words) < 2:
        return (" ".join(words),)
    best = None
    for i in range(1, len(words)):
        first = _break_line(" ".join(words[:i]))
        second = " ".join(words[i:])
        key = (max(len(first), len(second)), -len(first))
        if best is None or key < best[0]:
            best = (key, first, second)
    return (best[1], best[2])


def chamfer_box(x0, y0, x1, y1, chamfer):
    # Closed outline starting mid-edge so both square caps overlap cleanly.
    mx = (x0 + x1) * 0.5
    return (
        (mx, y0), (x1 - chamfer, y0), (x1, y0 + chamfer), (x1, y1 - chamfer),
        (x1 - chamfer, y1), (x0 + chamfer, y1), (x0, y1 - chamfer),
        (x0, y0 + chamfer), (x0 + chamfer, y0), (mx, y0),
    )


def _diamond(cx, cy, r):
    return _positive([cx, cy - r, cx + r, cy, cx, cy + r, cx - r, cy])


def build_stamp(text, header=None, footer=None):
    # Returns (groups, width, height): contour groups centred on (0, 0).
    lines = wrap(text.upper())
    hw = STROKE * 0.5
    shw = SMALL_STROKE * 0.5
    widest = 0.0
    for line in lines:
        widest = max(widest, line_width(line))
    header_text = 0.0
    header_span = 0.0
    if header:
        header_text = line_width(header) * SMALL
        header_span = header_text + SMALL_STROKE + 2 * (DIAMOND_GAP + 2 * DIAMOND)
    footer_span = line_width(footer) * SMALL + SMALL_STROKE if footer else 0.0
    # Short verdicts grow to fill the frame the header sets.
    grow = 1.0
    if widest > 0:
        grow = min(MAX_GROW, max(1.0, max(header_span, footer_span) / (widest + STROKE)))
    main_hw = hw * grow
    content = max(widest * grow + 2 * main_hw, header_span, footer_span)
    inner_half = content * 0.5 + PAD_X
    outer_half = inner_half + INNER_GAP

    groups = []
    rules = []
    inner_top = INNER_GAP
    y = inner_top + INNER * 0.5 + PAD_Y
    if header:
        y += shw
        text_groups(header, 0.0, y, SMALL, shw, groups)
        mid = y + CAP * SMALL * 0.5
        dx = header_text * 0.5 + shw + DIAMOND_GAP + DIAMOND
        groups.append([_diamond(-dx, mid, DIAMOND), _diamond(dx, mid, DIAMOND)])
        y += CAP * SMALL + shw + 1.1 + RULE * 0.5
        rules.append(y)
        y += RULE * 0.5 + 1.6 + main_hw
    else:
        y += main_hw + 0.6
    pitch = LINE_PITCH * grow
    for i in range(len(lines)):
        text_groups(lines[i], 0.0, y + i * pitch, grow, main_hw, groups)
    y += (len(lines) - 1) * pitch + CAP * grow + main_hw
    if footer:
        y += 1.6 + RULE * 0.5
        rules.append(y)
        y += RULE * 0.5 + 1.1 + shw
        text_groups(footer, 0.0, y, SMALL, shw, groups)
        y += CAP * SMALL + shw
    else:
        y += 0.6
    inner_bottom = y + PAD_Y + INNER * 0.5
    outer_bottom = inner_bottom + INNER_GAP

    frame = []
    stroke_path(chamfer_box(-outer_half, 0.0, outer_half, outer_bottom, 2.2), BORDER * 0.5, frame)
    stroke_path(chamfer_box(-inner_half, inner_top, inner_half, inner_bottom, 1.0), INNER * 0.5, frame)
    for ry in rules:
        stroke_path(((-inner_half, ry), (inner_half, ry)), RULE * 0.5, frame, False, False)
    groups.insert(0, frame)

    shift = -outer_bottom * 0.5
    for group in groups:
        for contour in group:
            for i in range(1, len(contour), 2):
                contour[i] += shift
    return groups, 2 * outer_half + BORDER, outer_bottom + BORDER


# Slam timeline, in milliseconds from the trigger.
DROP_MS = 140
SQUASH_MS = 120
BAKE_MS = DROP_MS + SQUASH_MS
SHAKE_MS = 450
SHAKE_PX = 9.0
STROBE_MS = 1000
SPLAT_MS = 400
DROP_SCALE = 2.6
DROP_SPIN = 20.0
SQUASH = 0.06


def slam_pose(t):
    # (scale factor, wobble factor 0-1, alpha 0-255, landed) at t ms.
    if t < DROP_MS:
        p = max(0.0, t / DROP_MS)
        return DROP_SCALE - (DROP_SCALE - 1.0) * p * p, (1.0 - p) * (1.0 - p), int(70 + 185 * p), False
    q = min(1.0, (t - DROP_MS) / SQUASH_MS)
    return 1.0 - SQUASH * (1.0 - q) * (1.0 - q), 0.0, 255, True


def shake_offset(t, phase=0.0):
    # Decaying screen shake, t ms after impact.
    if t < 0 or t >= SHAKE_MS:
        return 0.0, 0.0
    a = SHAKE_PX * (1.0 - t / SHAKE_MS) ** 2
    return a * math.sin(0.09 * t + phase), a * math.cos(0.13 * t + phase)


def strobe_levels(t):
    # Case-light levels (0-1, one per LED) t ms after impact, or None when
    # the strobe has finished: flash, blackout, chase, then fade.
    if t < 0 or t >= STROBE_MS:
        return None
    if t < 80:
        return (1.0, 1.0, 1.0, 1.0)
    if t < 140:
        return (0.0, 0.0, 0.0, 0.0)
    if t < 700:
        lit = int((t - 140) // 70) % 4
        levels = []
        for i in range(4):
            levels.append(1.0 if i == lit else 0.15)
        return tuple(levels)
    v = 0.6 * (1.0 - (t - 700) / 300.0)
    return (v, v, v, v)


def make_splats(rand, count, cx, cy, half_w, half_h):
    # Ink droplets flung from the stamp's rim: [x, y, vx, vy, radius].
    splats = []
    for _ in range(count):
        a = rand() * 6.2831853
        c = math.cos(a)
        s = math.sin(a)
        speed = 60.0 + 170.0 * rand()
        splats.append([cx + c * half_w * 0.92, cy + s * half_h * 0.92, c * speed, s * speed, 0.8 + 1.7 * rand()])
    return splats


SPLAT_DRAG_MS = 110.0


def step_splats(splats, dt):
    # Exact exponential drag, so any frame rate lands droplets in one place.
    decay = math.exp(-dt / SPLAT_DRAG_MS)
    travel = SPLAT_DRAG_MS / 1000.0 * (1.0 - decay)
    for s in splats:
        s[0] += s[2] * travel
        s[1] += s[3] * travel
        s[2] *= decay
        s[3] *= decay
