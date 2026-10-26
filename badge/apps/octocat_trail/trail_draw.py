# The Octocat Trail renderer. Original screens in the style of 1980s 8-bit
# educational games (numbered menus, inverse bars, a double-ruled status box
# and chunky pixel type), drawn with art made for this app. The badge globals
# (screen, color, font, image, rect, shape, vec2) are only looked up while
# drawing, so the module imports anywhere. Nothing larger than the screen is
# ever allocated: the walk view draws only the tiles inside the camera.

import trail_art as ta
import trail_logic as tl

W = 320
ROW = 12
MARGIN = 8
TEXT_W = W - 2 * MARGIN
HINT_Y = 228
TOAST_Y = 18
BLINK_MS = 400
CACHE_LIMIT = 160
# The pixel font's space is only 2 px wide; three read as a word gap.
SPACE = "   "
TEXT_DY = 0
DASHES = "-" * 43

BLACK, WHITE, GREEN, VIOLET, ORANGE = ta.BLACK, ta.WHITE, ta.GREEN, ta.VIOLET, ta.ORANGE
BLUE, NAVY, GREY, DKGREEN, YELLOW = ta.BLUE, ta.NAVY, ta.GREY, ta.DKGREEN, ta.YELLOW
LTBLUE, GOLD, PLUM = ta.LTBLUE, ta.GOLD, ta.PLUM


def dim(rgb):
    """Dark Mode Camp: the whole screen at about half brightness."""
    return (rgb[0] * 11 // 20, rgb[1] * 11 // 20, rgb[2] * 11 // 20)


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
