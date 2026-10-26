# The Octocat Trail renderer. Original screens in the style of 1980s 8-bit
# educational games (numbered menus, inverse bars, a double-ruled status box
# and chunky pixel type), drawn with art made for this app. The badge globals
# (screen, color, font, image, rect, shape, vec2) are only looked up while
# drawing, so the module imports anywhere. Nothing larger than the screen is
# ever allocated: the walk view draws only the tiles inside the camera.

import trail_art as ta
import trail_logic as tl
import trail_map as tm

W = 320
H = 240
ROW = 12
MARGIN = 8
TEXT_W = W - 2 * MARGIN
VIEW_H = 132
BOX_Y = 146
HINT_Y = 228
TOAST_Y = 18
BLINK_MS = 400
CACHE_LIMIT = 160
TILE = tm.TILE
# The pixel font's space is only 2 px wide; three read as a word gap.
SPACE = "   "
TEXT_DY = 0
DASHES = "-" * 43

BLACK, WHITE, GREEN, VIOLET, ORANGE = ta.BLACK, ta.WHITE, ta.GREEN, ta.VIOLET, ta.ORANGE
BLUE, NAVY, GREY, DKGREEN, YELLOW = ta.BLUE, ta.NAVY, ta.GREY, ta.DKGREEN, ta.YELLOW
PINK, PURPLE, MAGENTA, AQUA, BROWN = ta.PINK, ta.PURPLE, ta.MAGENTA, ta.AQUA, ta.BROWN
LTBLUE, GOLD, PLUM = ta.LTBLUE, ta.GOLD, ta.PLUM

# Colour of each map tile code on the walk view (BASE) and the overview (CHART).
BASE = (NAVY, BLACK, GREEN, GREY, BROWN, ORANGE, BLACK, GREEN, NAVY, NAVY, VIOLET, BROWN, GREEN)
FIREHOUSE = 5
GATEHOUSE = 6

# Arrival picture for each stop: (style, sign, accent colour).
FACADES = (
    ("booth", "GATEHOUSE", WHITE),
    ("shop", "GITHUB SHOP", VIOLET),
    ("hall", "OPEN SOURCE ZONE", GREEN),
    ("hall", "GITHUB CENTRAL", BLUE),
    ("hall", "EXPERT CENTER", VIOLET),
    ("hall", "CAREER CORNER", YELLOW),
    ("fire", "HOTFIX HQ", MAGENTA),
    ("meadow", "", GREEN),
    ("river", "", NAVY),
    ("pavilion", "MAKERSPACE", AQUA),
    ("theater", "COWELL THEATER", YELLOW),
    ("river", "", NAVY),
    ("pavilion", "MAINSTAGE", VIOLET),
)


def dim(rgb):
    """Dark Mode Camp: the whole screen at about half brightness."""
    return (rgb[0] * 11 // 20, rgb[1] * 11 // 20, rgb[2] * 11 // 20)


def lcg(seed):
    return (seed * 1103515245 + 12345) & 0x7FFFFFFF


def scatter(count, seed, x0, y0, w, h):
    """Deterministic (x, y, index) points, so scenery never flickers."""
    points = []
    for index in range(count):
        seed = lcg(seed)
        x = x0 + seed % w
        seed = lcg(seed)
        y = y0 + seed % h
        points.append((x, y, index))
    return tuple(points)


class Renderer:
    def __init__(self):
        self.now = 0
        self.pens = None
        self.pen_key = -1
        self.pen_sets = {}
        self.slot = -1
        self.face = None
        self.widths = {}
        self.wraps = {}
        self.fits = {}
        self.banner = None
        self.banner_key = None
        self.banner_w = 0
        self.chart = None
        self.chart_key = None
        self.failed = {}
        self.tokens = (ta.token_parts(0), ta.token_parts(1))
        self.stars = scatter(40, 11, 0, 2, W, 92)

    # ----- frame setup ------------------------------------------------------------
    def draw(self, game):
        self.now = int(game.now)
        self.begin(game.visual() == 1, bool(game.dark()))
        view = game.view()
        kind = view.kind
        self.pen(BLACK)
        screen.clear()
        try:
            getattr(self, "draw_" + kind)(view, game)
        except Exception as error:
            self.fallback(view, kind, error)
        if kind != "map":
            self.chart = None
            self.chart_key = None
        toast = game.current_toast()
        if toast:
            self.draw_toast(toast)

    def begin(self, green, dark):
        face = self.face
        if face is None:
            try:
                face = font.teatime
            except Exception:
                face = font.nope
            self.face = face
        screen.font = face
        key = (1 if green else 0) + (2 if dark else 0)
        if key != self.pen_key:
            pens = self.pen_sets.get(key)
            if pens is None:
                made = []
                for rgb in ta.palette(green):
                    if dark:
                        rgb = dim(rgb)
                    made.append(color.rgb(rgb[0], rgb[1], rgb[2]))
                pens = tuple(made)
                self.pen_sets[key] = pens
            self.pens = pens
            self.pen_key = key
        self.slot = -1

    def fallback(self, view, kind, error):
        if kind not in self.failed:
            self.failed[kind] = repr(error)
            print("octocat_trail: the %s screen failed: %r" % (kind, error))
        self.slot = -1
        self.pen(BLACK)
        screen.clear()
        y = self.bar(view.title or "The Octocat Trail")
        self.lines(view.lines, y)
        self.hint(view.hint)

    # ----- pens and boxes -----------------------------------------------------------
    def pen(self, slot):
        if slot != self.slot:
            self.slot = slot
            screen.pen = self.pens[slot]

    def fill(self, slot, x, y, w, h):
        if w > 0 and h > 0:
            self.pen(slot)
            screen.rectangle(int(x), int(y), int(w), int(h))

    def outline(self, x, y, w, h):
        box = screen.rectangle
        box(x, y, w, 1)
        box(x, y + h - 1, w, 1)
        box(x, y, 1, h)
        box(x + w - 1, y, 1, h)

    def circle(self, slot, x, y, r, ring=0):
        self.pen(slot)
        if ring:
            screen.shape(shape.circle(int(x), int(y), r).stroke(ring))
        else:
            screen.shape(shape.circle(int(x), int(y), r))

    def line(self, slot, x0, y0, x1, y1, width=1):
        self.pen(slot)
        screen.shape(shape.line(x0, y0, x1, y1, width))

    def arrow(self, x, y, up):
        for i in range(4):
            screen.rectangle(x - i, y + i if up else y + 3 - i, 1 + 2 * i, 1)

    # ----- type ------------------------------------------------------------------------
    def raw_width(self, text):
        return int(screen.measure_text(text.replace(" ", SPACE))[0])

    def measure(self, text):
        width = self.widths.get(text)
        if width is None:
            if len(self.widths) > CACHE_LIMIT:
                self.widths = {}
            width = self.raw_width(text)
            self.widths[text] = width
        return width

    def text(self, text, x, y):
        screen.text(text.replace(" ", SPACE), int(x), int(y) + TEXT_DY)

    def centred(self, text, y, cx=W // 2):
        self.text(text, cx - self.measure(text) // 2, y)

    def right(self, text, x, y):
        self.text(text, x - self.measure(text), y)

    def wrap(self, text, width=TEXT_W):
        key = (text, width)
        rows = self.wraps.get(key)
        if rows is None:
            if len(self.wraps) > CACHE_LIMIT:
                self.wraps = {}
            rows = tuple(tl.wrap(text, width, self.raw_width))
            self.wraps[key] = rows
        return rows

    def fit(self, text, width):
        if self.measure(text) <= width:
            return text
        key = (text, width)
        cut = self.fits.get(key)
        if cut is None:
            if len(self.fits) > CACHE_LIMIT:
                self.fits = {}
            end = len(text)
            while end > 0 and self.raw_width(text[:end] + "...") > width:
                end -= 1
            cut = text[:end].rstrip() + "..."
            self.fits[key] = cut
        return cut

    def lines(self, lines, y, x=MARGIN, width=TEXT_W, slot=WHITE, limit=HINT_Y - 2):
        self.pen(slot)
        for line in lines:
            for row in self.wrap(line, width):
                if y + ROW > limit:
                    return y
                self.text(row, x, y)
                y += ROW
        return y

    def big_text(self, text, y, ink=WHITE, shade=VIOLET):
        """Twice-size title: the pixel font drawn once into a small image,
        then blitted at 2x so it stays crisp and chunky."""
        key = (text, self.pen_key, ink, shade)
        if self.banner_key != key:
            self.banner_key = key
            self.banner = None
            try:
                width = self.measure(text) + 1
                art = image(width, ROW + 1)
                try:
                    art.antialias = image.OFF
                except Exception:
                    pass
                art.font = self.face
                art.pen = self.pens[BLACK]
                art.clear()
                spaced = text.replace(" ", SPACE)
                art.pen = self.pens[shade]
                art.text(spaced, 1, 1 + TEXT_DY)
                art.pen = self.pens[ink]
                art.text(spaced, 0, TEXT_DY)
                self.banner = art
                self.banner_w = width
            except Exception:
                self.banner = None
        if self.banner is not None:
            width = self.banner_w
            screen.blit(self.banner, rect((W - 2 * width) // 2, y, 2 * width, 2 * (ROW + 1)))
        else:
            self.pen(ink)
            self.centred(text, y + 6)

    # ----- page furniture --------------------------------------------------------------
    def bar(self, title, y=0):
        self.fill(WHITE, 0, y, W, ROW + 2)
        self.pen(BLACK)
        self.centred(self.fit(title, W - 8), y + 1)
        return y + ROW + 4

    def hint(self, text, y=HINT_Y, slot=GREY):
        if text:
            self.pen(slot)
            self.centred(self.fit(text, W - 4), y)

    def dashes(self, y, slot=GREY):
        self.pen(slot)
        self.centred(DASHES, y)

    def options(self, options, cursor, y, bottom):
        count = len(options)
        rows = (bottom - y) // ROW
        if rows < 1 or count == 0:
            return
        first = 0
        if count > rows:
            first = max(0, min(cursor - rows // 2, count - rows))
        last = min(count, first + rows)
        for index in range(first, last):
            label, value, enabled = options[index]
            top = y + (index - first) * ROW
            if index == cursor:
                self.fill(WHITE if enabled else GREY, MARGIN - 2, top - 1, W - 2 * MARGIN + 4, ROW)
                self.pen(BLACK)
            else:
                self.pen(WHITE if enabled else GREY)
            self.right("%d." % (index + 1), MARGIN + 22, top)
            room = W - 2 * MARGIN - 30
            if value:
                value = self.fit(str(value), room // 2)
                width = self.measure(value)
                self.text(value, W - MARGIN - width, top)
                room -= width + 8
            self.text(self.fit(label, room), MARGIN + 28, top)
        if first > 0 or last < count:
            self.pen(GREY)
            if first > 0:
                self.arrow(W - 4, y, True)
            if last < count:
                self.arrow(W - 4, y + rows * ROW - 6, False)

    def prompt(self, view, note, y):
        if note:
            self.pen(WHITE)
            for row in note:
                self.text(row, MARGIN, y)
                y += ROW
            return
        if view.cursor < 0:
            return
        label = "Your pick: %d" % (view.cursor + 1)
        self.pen(WHITE)
        self.text(label, MARGIN, y)
        if not (self.now // BLINK_MS) & 1:
            screen.rectangle(MARGIN + self.measure(label) + 4, y + 1, 7, 10)

    def menu_block(self, view, y, bottom=HINT_Y - 2, rule=False):
        """Numbered options, the prompt and footer lines between y and bottom."""
        foot = []
        for line in view.foot:
            for row in self.wrap(line):
                foot.append(row)
        note = self.wrap(view.note)[:2] if view.note else ()
        foot_top = bottom - len(foot) * ROW
        if foot and rule:
            foot_top -= ROW
        prompt_top = foot_top - max(1, len(note)) * ROW - (3 if foot else 0)
        self.options(view.options, view.cursor, y, prompt_top - 2)
        self.prompt(view, note, prompt_top)
        if foot:
            if rule:
                self.dashes(foot_top)
                foot_top += ROW
            self.pen(WHITE)
            for row in foot:
                self.text(row, MARGIN, foot_top)
                foot_top += ROW

    def draw_toast(self, text):
        text = self.fit(text, W - 28)
        width = self.measure(text) + 12
        x = (W - width) // 2
        self.fill(BLACK, x - 2, TOAST_Y - 2, width + 4, ROW + 8)
        self.fill(WHITE, x, TOAST_Y, width, ROW + 4)
        self.pen(BLACK)
        self.text(text, x + 6, TOAST_Y + 2)

    # ----- sprites ------------------------------------------------------------------------
    def sprite(self, rows, x, y, scale=1, mirror=False):
        _w, _h, runs = ta.sprite(rows, mirror)
        box = screen.rectangle
        pens = self.pens
        x = int(x)
        y = int(y)
        last = self.slot
        for rx, ry, count, slot in runs:
            if slot != last:
                last = slot
                screen.pen = pens[slot]
            box(x + rx * scale, y + ry * scale, count * scale, scale)
        self.slot = last

    def token(self, x, y, frame=0, mirror=False, scale=1):
        """The party: Mona riding the wagon, pulled by the GitHub Ducky."""
        for rows, px, py in self.tokens[frame & 1]:
            if mirror:
                px = ta.TOKEN_W - px - ta.size(rows)[0]
            self.sprite(rows, x + px * scale, y + py * scale, scale, mirror)

    # ----- shared scenery ----------------------------------------------------------------
    def waves(self, x, y, w, h, count, slot=BLUE):
        self.pen(slot)
        shift = self.now // 80
        span = max(1, w - 4)
        rows = max(1, h)
        for i in range(count):
            screen.rectangle(x + (i * 53 + shift) % span, y + (i * 17) % rows, 4, 1)

    def bay_scene(self, top):
        """Hills, the bay and the Golden Gate behind a strip of grass, 46 px tall."""
        for hx, hr in ((24, 12), (62, 16), (104, 11), (140, 8)):
            self.circle(DKGREEN, hx, top + 20, hr)
        self.fill(NAVY, 0, top + 20, W, 18)
        self.waves(0, top + 23, W, 12, 9)
        self.pen(ORANGE)
        box = screen.rectangle
        for tx in (196, 276):
            box(tx, top + 2, 4, 36)
            box(tx - 2, top + 8, 8, 2)
            box(tx - 2, top + 18, 8, 2)
        box(150, top + 28, W - 150, 3)
        cable = top + 3
        sag = top + 22
        for x0, y0, x1, y1 in ((150, top + 27, 198, cable), (198, cable, 238, sag),
                               (238, sag, 278, cable), (278, cable, W, sag)):
            screen.shape(shape.line(x0, y0, x1, y1, 1))
        self.fill(GREEN, 0, top + 38, W, 8)

    def sign(self, text, cx, y, bg, ink=BLACK):
        width = self.measure(text) + 12
        x = cx - width // 2
        self.fill(bg, x, y, width, ROW + 3)
        self.pen(ink)
        self.text(text, x + 6, y + 2)

    # ----- menus and text pages ------------------------------------------------------------
    def draw_title(self, view, game):
        self.big_text(view.title, 4)
        self.bay_scene(34)
        x = (self.now // 30) % (W + 64) - 64
        self.token(x, 48, (self.now // 200) & 1, False, 2)
        if view.lines:
            self.pen(WHITE)
            self.centred(self.fit(view.lines[0], TEXT_W), 86)
        if len(view.lines) > 1:
            self.pen(GREY)
            self.centred(self.fit(view.lines[1], TEXT_W), 98)
        self.menu_block(view, 114)
        self.hint(view.hint)

    def draw_menu(self, view, game):
        y = self.bar(view.title)
        y = self.lines(view.lines, y)
        self.menu_block(view, y + 2)
        self.hint(view.hint)

    def draw_store(self, view, game):
        y = self.bar(view.title)
        self.pen(WHITE)
        for line in view.lines:
            self.centred(self.fit(line, TEXT_W), y)
            y += ROW
        self.dashes(y)
        self.menu_block(view, y + ROW + 2, rule=True)
        self.hint(view.hint)

    def draw_help(self, view, game):
        y = self.bar(view.title) + 4
        for line in view.lines:
            y = self.lines((line,), y, limit=176) + 6
        self.fill(GREEN, 0, 204, W, 4)
        x = (self.now // 30) % (W + 64) - 64
        self.token(x, 180, (self.now // 200) & 1, False, 2)
        self.hint(view.hint)

    def draw_card(self, view, game):
        back = view.data
        trail = game.trail
        if back == "roam" and trail is not None:
            self.walk_view(game, trail)
            self.fill(BLACK, 0, VIEW_H, W, H - VIEW_H)
        elif back == "camp" and trail is not None:
            self.camp_scene()
        else:
            y = self.bar(view.title) + 8
            for line in view.lines:
                y = self.lines((line,), y) + 6
            self.hint(view.hint)
            return
        self.card_box(view)

    def card_box(self, view):
        rows = []
        for line in view.lines:
            for row in self.wrap(line, W - 32):
                rows.append(row)
        height = len(rows) * ROW + 2 * ROW + 16
        top = max(20, min(BOX_Y, H - 2 - height))
        self.fill(BLACK, 2, top - 2, W - 4, H - top + 2)
        self.fill(WHITE, 4, top, W - 8, H - 2 - top)
        self.pen(BLACK)
        self.outline(6, top + 2, W - 12, H - 6 - top)
        self.centred(self.fit(view.title, W - 24), top + 5)
        y = top + ROW + 9
        limit = H - 6 - ROW
        for row in rows:
            if y + ROW > limit:
                break
            self.text(row, 16, y)
            y += ROW
        self.centred(self.fit(view.hint, W - 24), limit)

    # ----- arriving at a stop ------------------------------------------------------------------
    def draw_stop(self, view, game):
        stop = view.data if isinstance(view.data, int) else 3
        self.facade(stop)
        y = self.bar(view.title, 128)
        if view.foot:
            self.pen(GREY)
            self.centred(view.foot[0], y)
            y += ROW + 2
        self.lines(view.lines, y)
        self.hint(view.hint)

    def facade(self, stop, party_x=6, frame=0):
        """A picture of the stop: 128 px of building, scenery and ground."""
        style, sign, accent = FACADES[stop if 0 <= stop < len(FACADES) else 3]
        blink = (self.now // BLINK_MS) & 1
        if style == "meadow":
            self.bay_scene(48)
            self.fill(GREEN, 0, 94, W, 18)
            for tx, ty, scale in ((110, 70, 3), (250, 78, 2), (286, 74, 3), (160, 84, 2)):
                self.sprite(ta.TREE, tx, ty, scale)
            self.sprite(ta.FLAG, 220, 88, 3)
        elif style == "river":
            self.fill(NAVY, 0, 70, W, 42)
            self.waves(0, 74, W, 34, 10)
            self.fill(BROWN, 0, 62, 70, 8)
            self.fill(BROWN, 250, 62, 70, 8)
            self.pen(GREY)
            for px in (8, 30, 52, 258, 280, 302):
                screen.rectangle(px, 70, 3, 12)
        elif style == "booth":
            for fx in range(4, 120, 16):
                self.fill(WHITE, fx, 92, 2, 20)
            self.fill(WHITE, 0, 96, 120, 1)
            self.fill(WHITE, 0, 104, 120, 1)
            self.fill(WHITE, 128, 64, 48, 48)
            self.fill(BLUE, 134, 70, 36, 16)
            self.fill(WHITE, 151, 70, 2, 16)
            self.fill(NAVY, 140, 90, 14, 22)
            self.fill(ORANGE, 120, 58, 64, 6)
            self.fill(ORANGE, 126, 52, 52, 6)
            self.fill(GREY, 184, 80, 4, 32)
            for i in range(10):
                self.fill(WHITE if i & 1 else MAGENTA, 188 + i * 10, 84, 10, 4)
            self.sign(sign, 152, 32, accent)
        elif style == "shop":
            self.fill(WHITE, 40, 44, 240, 68)
            self.fill(ORANGE, 34, 36, 252, 8)
            self.sign(sign, 160, 46, accent)
            for i in range(10):
                self.fill(accent if i & 1 == 0 else PINK, 60 + i * 20, 64, 20, 8)
            self.fill(NAVY, 64, 74, 128, 32)
            self.sprite(ta.MONA[blink], 80, 78, 2)
            self.sprite(ta.DUCK[0], 132, 82, 2)
            self.fill(BLACK, 212, 72, 32, 40)
            self.fill(GREY, 236, 92, 3, 3)
        elif style == "hall":
            self.fill(WHITE, 16, 40, 288, 72)
            self.fill(ORANGE, 10, 30, 300, 10)
            self.fill(accent, 16, 40, 288, 3)
            for wx in range(28, 296, 32):
                self.fill(NAVY, wx, 46, 12, 10)
                if wx < 136 or wx > 180:
                    self.fill(NAVY, wx, 82, 12, 16)
                    self.fill(WHITE, wx + 5, 82, 2, 16)
            self.sign(sign, 160, 62, accent)
            self.fill(BLACK, 140, 80, 40, 32)
        elif style == "fire":
            self.fill(MAGENTA, 60, 44, 200, 68)
            self.fill(GREY, 54, 36, 212, 8)
            self.fill(GREY, 152, 34, 16, 2)
            self.fill(YELLOW if blink else ORANGE, 156, 24, 8, 10)
            self.sign(sign, 160, 48, WHITE)
            self.fill(WHITE, 112, 68, 96, 44)
            for gy in range(76, 112, 8):
                self.fill(GREY, 112, gy, 96, 1)
            for wx in (72, 220):
                self.fill(NAVY, wx, 70, 28, 20)
                self.fill(WHITE, wx + 13, 70, 2, 20)
        elif style == "pavilion":
            if stop == tm.END:
                self.line(YELLOW, 60, 54, 20, 0, 2)
                self.line(YELLOW, 260, 54, 300, 0, 2)
            self.fill(WHITE, 20, 54, 280, 58)
            for i in range(14):
                self.fill(ORANGE, 14 + i * 10, 52 - 2 * i, 292 - 20 * i, 2)
            for wx in (40, 70, 234, 264):
                self.fill(NAVY, wx, 66, 16, 20)
            self.circle(BLACK, 160, 82, 24)
            self.fill(BLACK, 136, 82, 48, 30)
            self.sign(sign, 160, 34, accent)
        elif style == "theater":
            self.fill(WHITE, 40, 40, 240, 72)
            self.fill(ORANGE, 34, 32, 252, 8)
            self.fill(BLACK, 64, 48, 192, 30)
            for i in range(16):
                slot = YELLOW if (i + blink) & 1 else ORANGE
                self.fill(slot, 68 + i * 12, 50, 3, 3)
                self.fill(slot, 68 + i * 12, 73, 3, 3)
            self.pen(WHITE)
            self.centred(sign, 57)
            for dx in (96, 146, 196):
                self.fill(BLACK, dx, 86, 28, 26)
        self.fill(GREEN, 0, 112, W, 16)
        self.token(party_x, 88, frame, False, 2)

    # ----- walking the venue ----------------------------------------------------------------
    def draw_roam(self, view, game):
        trail = view.data if view.data is not None else game.trail
        self.walk_view(game, trail)
        self.fill(BLACK, 0, VIEW_H, W, H - VIEW_H)
        self.hint(view.hint, VIEW_H + 1)
        self.status_box(view)

    def walk_view(self, game, trail, height=VIEW_H):
        """Top-down Fort Mason: only the tiles inside the camera are drawn."""
        px, py = game.party_px()
        cx, cy = tm.camera(px + TILE // 2, py + TILE // 2, W, height)
        self.terrain(cx, cy, height, trail.deployed)
        self.landmarks(cx, cy, height, trail)
        self.next_marker(cx, cy, height, trail)
        sx = px - cx
        sy = py - cy
        mirror = trail.facing < 0
        if trail.turbo_days > 0:
            self.speed_lines(sx, sy, mirror)
        self.token(sx - 12, sy - 2, game.walk_frame(), mirror)

    def terrain(self, cx, cy, height, deployed):
        rows = tm.runs()
        c0 = cx // TILE
        c1 = (cx + W - 1) // TILE
        r0 = cy // TILE
        r1 = min(tm.H - 1, (cy + height - 1) // TILE)
        box = screen.rectangle
        pens = self.pens
        last = self.slot
        specials = []
        for ty in range(r0, r1 + 1):
            sy = ty * TILE - cy
            top = sy if sy > 0 else 0
            bottom = sy + TILE if sy + TILE < height else height
            for x, n, code in rows[ty]:
                end = x + n - 1
                if end < c0 or x > c1:
                    continue
                a = x if x > c0 else c0
                b = end if end < c1 else c1
                slot = BASE[code]
                if slot != last:
                    last = slot
                    screen.pen = pens[slot]
                box(a * TILE - cx, top, (b - a + 1) * TILE, bottom - top)
                if code >= tm.FENCE and code != tm.DOOR:
                    specials.append((a, b, sy, code))
        self.slot = last
        self.specials(specials, cx, deployed)
        self.details(cx, cy, c0, c1, r0, r1)

    def specials(self, specials, cx, deployed):
        box = screen.rectangle
        for a, b, sy, code in specials:
            x0 = a * TILE - cx
            width = (b - a + 1) * TILE
            if code == tm.FENCE:
                self.pen(WHITE)
                box(x0, sy + 2, width, 1)
                box(x0, sy + 5, width, 1)
                for tx in range(a, b + 1):
                    box(tx * TILE - cx + 3, sy + 1, 2, 7)
            elif code == tm.TREE:
                for tx in range(a, b + 1):
                    self.sprite(ta.TREE, tx * TILE - cx, sy)
            elif code == tm.GANG1 or code == tm.GANG2:
                stop = tm.MERGE if code == tm.GANG1 else tm.DNS
                if deployed & (1 << stop):
                    self.fill(BROWN, x0, sy + 1, width, 6)
                    self.pen(ORANGE)
                    for tx in range(a, b + 1):
                        box(tx * TILE - cx + 3, sy + 1, 1, 6)
                    self.pen(WHITE)
                    box(x0, sy, width, 1)
                    box(x0, sy + 7, width, 1)
                else:
                    self.pen(GREY)
                    for tx in range(a, b + 1):
                        box(tx * TILE - cx + 2, sy + 3, 4, 1)
            elif code == tm.DOCK:
                self.pen(BLACK)
                box(x0, sy + 2, width, 1)
                box(x0, sy + 5, width, 1)
            elif code == tm.FLAG:
                for tx in range(a, b + 1):
                    self.sprite(ta.FLAG, tx * TILE - cx + 1, sy)

    def details(self, cx, cy, c0, c1, r0, r1):
        rows = tm.details()
        box = screen.rectangle
        phase = self.now // 500
        for ty in range(r0, r1 + 1):
            sy = ty * TILE - cy
            for x, kind in rows[ty]:
                if x < c0 or x > c1:
                    continue
                sx = x * TILE - cx
                if kind == 0:
                    self.pen(BLUE)
                    box(sx + 1 + ((phase + x) & 1) * 2, sy + 3, 4, 1)
                else:
                    self.pen(DKGREEN)
                    box(sx + 2, sy + 4, 1, 2)
                    box(sx + 4, sy + 3, 1, 3)
                    box(sx + 6, sy + 4, 1, 2)

    def landmarks(self, cx, cy, height, trail):
        box = screen.rectangle
        self.pen(GREY)
        for col, y0, y1 in tm.PARKING:
            sx = col * TILE - cx + 4
            top = y0 * TILE - cy
            end = (y1 + 1) * TILE - cy
            if sx < -8 or sx > W + 8 or end <= 0 or top >= height:
                continue
            box(sx, max(0, top), 1, min(end, height) - max(0, top))
            for ty in range(y0, y1 + 1, 2):
                sy = ty * TILE - cy
                if 0 <= sy < height:
                    box(sx - 6, sy, 13, 1)
        for index in range(len(tm.BUILDINGS)):
            name, x0, y0, x1, y1 = tm.BUILDINGS[index]
            bx = x0 * TILE - cx
            by = y0 * TILE - cy
            bw = (x1 - x0 + 1) * TILE
            bh = (y1 - y0 + 1) * TILE
            if bx >= W or by >= height or bx + bw <= 0 or by + bh <= 0:
                continue
            if index == FIREHOUSE:
                self.fill(MAGENTA, bx, by, bw, bh)
                self.fill(WHITE, bx + 8, by + bh - 9, bw - 16, 8)
            elif index == GATEHOUSE:
                self.fill(WHITE, bx, by, bw, bh)
                self.fill(ORANGE, bx, by, bw, 5)
            self.pen(BLACK)
            self.outline(bx, by, bw, bh)
            mid = bx + bw // 2
            if name and -8 < mid < W + 8:
                for ly in range(y0 + 4, y1 - 1, 12):
                    sy = ly * TILE - cy
                    if -ROW < sy < height:
                        self.centred(name, sy, mid)
        self.pen(BLACK)
        for x0, y0, x1, y1 in tm.SHEDS:
            bx = x0 * TILE - cx
            by = y0 * TILE - cy
            bw = (x1 - x0 + 1) * TILE
            bh = (y1 - y0 + 1) * TILE
            if bx < W and by < height and bx + bw > 0 and by + bh > 0:
                self.outline(bx, by, bw, bh)
        for stop in range(len(tm.STOPS)):
            entry = tm.STOPS[stop]
            if entry[2] == "river" or entry[2] == "meadow":
                continue
            sx = entry[3] * TILE - cx
            sy = entry[4] * TILE - cy
            if -TILE < sx < W and -TILE < sy < height:
                self.fill(GREEN if trail.has_visited(stop) else VIOLET, sx, sy, TILE, TILE)
                self.fill(BLACK, sx + 2, sy + 2, 4, 6)
        self.labels(cx, cy, height)

    def labels(self, cx, cy, height):
        for text, lx, ly, vertical in tm.LABELS:
            sx = lx - cx
            sy = ly - cy
            if vertical:
                if sx < -8 or sx > W + 8:
                    continue
                shadow = text == "GITHUB UNIVERSE"
                y = sy
                for ch in text:
                    if ch == " ":
                        y += 6
                        continue
                    if -ROW < y < height:
                        x = sx - self.measure(ch) // 2
                        if shadow:
                            self.pen(BLACK)
                            self.text(ch, x + 1, y + 1)
                            self.pen(WHITE)
                        else:
                            self.pen(BLACK)
                        self.text(ch, x, y)
                    y += 11
            else:
                width = self.measure(text)
                x = sx - width // 2
                if x >= W or x + width <= 0 or sy <= -ROW or sy >= height:
                    continue
                self.pen(BLACK)
                self.text(text, x + 1, sy + 1)
                self.pen(WHITE)
                self.text(text, x, sy)

    def next_marker(self, cx, cy, height, trail):
        if (self.now // BLINK_MS) & 1:
            return
        stop = trail.next_stop()
        if stop < 0 or stop >= len(tm.STOPS):
            return
        entry = tm.STOPS[stop]
        sx = entry[3] * TILE - cx
        sy = entry[4] * TILE - cy
        self.pen(WHITE)
        if -TILE < sx < W and -TILE < sy < height:
            self.outline(sx - 2, sy - 2, TILE + 4, TILE + 4)
            self.outline(sx - 3, sy - 3, TILE + 6, TILE + 6)
            return
        mx = max(2, min(W - 8, sx))
        my = max(2, min(height - 8, sy))
        screen.rectangle(mx, my, 6, 6)
        self.fill(BLACK, mx + 2, my + 2, 2, 2)

    def speed_lines(self, sx, sy, mirror):
        self.pen(WHITE)
        shift = (self.now // 60) % 6
        for i in range(3):
            length = 6 + (i * 3 + shift) % 5
            y = sy + i * 3
            if mirror:
                screen.rectangle(sx + 22 + shift, y, length, 1)
            else:
                screen.rectangle(sx - 14 - length - shift, y, length, 1)

    def status_box(self, view):
        self.pen(WHITE)
        self.outline(2, BOX_Y, W - 4, H - BOX_Y)
        self.outline(4, BOX_Y + 2, W - 8, H - BOX_Y - 4)
        rows = view.rows
        note = self.wrap(view.note, W - 24) if view.note else ()
        if len(note) > 1:
            rows = rows[:5]
            note = note[:2]
        y = BOX_Y + 5
        for label, value in rows:
            self.right(label + ":", 112, y)
            self.text(self.fit(value, W - 130), 118, y)
            y += ROW
        y = 224 - ROW * (len(note) - 1)
        for row in note:
            self.centred(row, y)
            y += ROW

    # ----- Dark Mode Camp ------------------------------------------------------------------------
    def camp_scene(self):
        """The party beds down by the bay under the stars, above VIEW_H."""
        box = screen.rectangle
        twinkle = self.now // 350
        self.pen(WHITE)
        for x, y, i in self.stars:
            if 16 <= y <= 78 and (i + twinkle) % 9:
                box(x, y, 1, 1)
        self.circle(WHITE, 264, 36, 10)
        self.circle(BLACK, 269, 32, 9)
        for hx, hr in ((196, 9), (228, 14), (266, 10), (300, 13)):
            self.circle(DKGREEN, hx, 84, hr)
        self.fill(NAVY, 0, 82, W, 14)
        self.waves(0, 84, W, 10, 8)
        self.fill(DKGREEN, 0, 96, W, VIEW_H - 96)
        wx = 28
        wy = 100
        self.sprite(ta.WAGON, wx, wy, 2)
        self.fill(DKGREEN, wx + 26, wy, 10, 12)
        self.sprite(ta.WHEEL[0], wx + 4, wy + 14, 2)
        self.sprite(ta.WHEEL[0], wx + 24, wy + 14, 2)
        self.sprite(ta.DUCK[0], 92, 102, 2)
        self.pen(WHITE)
        if (self.now // 600) & 1:
            self.text("z", 114, 90)
        else:
            self.text("Z", 122, 80)
        self.sprite(ta.FIRE[(self.now // 200) & 1], 146, 97, 3)
        self.sprite(ta.MONA[0], 196, 98, 2, True)
        self.bar("Dark Mode Camp")

    def draw_camp(self, view, game):
        self.camp_scene()
        self.hint(view.hint, VIEW_H + 1)
        self.pen(WHITE)
        self.outline(2, BOX_Y, W - 4, H - BOX_Y)
        self.outline(4, BOX_Y + 2, W - 8, H - BOX_Y - 4)
        self.lines(view.lines, BOX_Y + 6, 14, W - 28, WHITE, 214)
        progress = view.progress if view.progress is not None else 0.0
        self.pen(WHITE)
        self.outline(14, 220, W - 28, 8)
        self.fill(GREEN, 16, 222, int((W - 32) * progress), 4)
