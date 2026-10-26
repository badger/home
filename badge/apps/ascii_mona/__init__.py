"""ASCII Mona: a custom MyOctocat for any GitHub handle.

A handle becomes 19 numbers of Mona DNA that pick parts and colours from
GitHub's own MyOctocat library (myoctocat.com). The badge paints its owner's
Mona as vector art, or as ASCII art built with Ascii-Motion's techniques.
"""

import gc
import json
import math
import os
import sys

APP_DIRS = ("/remote/apps/ascii_mona", "/system/apps/ascii_mona", "/apps/ascii_mona", "/ascii_mona")
APP_DIR = APP_DIRS[1]
for _dir in APP_DIRS:
    try:
        if is_dir(_dir):
            APP_DIR = _dir
            break
    except Exception:
        break
try:
    os.chdir(APP_DIR)
except OSError:
    pass
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

try:
    from badgeware import State
except ImportError:
    State = None

import mona_ascii
import mona_dna
import mona_net
import mona_octo


class _NoState:
    """Stands in for badgeware.State where a runtime has none."""

    def load(self, key, data):
        return data

    def save(self, key, data):
        return None


STORE = State if State is not None else _NoState()

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2
try:
    # Mona Sans needs even-odd filling; the menu leaves NON_ZERO behind.
    screen.fill_rule = image.EVEN_ODD
except Exception:
    pass


def _body_font():
    try:
        import missing_details
        return missing_details.mona_sans()
    except Exception:
        return None


BODY_FONT = _body_font()
VECTOR_TEXT = BODY_FONT is not None
if BODY_FONT is None:
    BODY_FONT = font.sins


def _art_file():
    for path in (APP_DIR + "/octocat.bin", "octocat.bin"):
        try:
            os.stat(path)
            return path
        except OSError:
            pass
    return APP_DIR + "/octocat.bin"


ART_FILE = _art_file()

STATE_KEY = "ascii_mona"
BADGE_USER_FILE = "/state/badge_user.json"

WIDTH = 320
HEIGHT = 240
FOOT_Y = 220
ART_X = 2
ART_Y = 2
ART_W = mona_ascii.WIDTH
ART_H = mona_ascii.HEIGHT
FIT = mona_octo.fit(ART_W, ART_H, 2)
CENTRE_X = ART_X + ART_W // 2
CENTRE_Y = ART_Y + 100
PANEL_X = 198
PANEL_W = WIDTH - PANEL_X - 2
TITLE_SIZE = 15
BODY_SIZE = 14
SMALL_SIZE = 12

TOAST_MS = 2600
HINT_SWAP_MS = 4000

STYLES = ("Vector", "Shapes", "Dither", "Edges")
VECTOR = 0
ASCII_STYLE = (0, mona_ascii.SHAPES, mona_ascii.DITHER, mona_ascii.EDGES)

WHITE = color.rgb(240, 246, 252)
DIM = color.rgb(255, 255, 255, 150)
FAINT = color.rgb(255, 255, 255, 50)
BAR = color.rgb(22, 27, 34)
PANEL = color.rgb(13, 17, 23, 238)
ACCENT = color.rgb(191, 135, 255)
GREEN = color.rgb(86, 211, 100)
RED = color.rgb(255, 123, 114)
CLEAR = color.rgb(0, 0, 0, 0)

NIGHT = (13, 17, 23)
# GitHub's contribution graph greens, empty to busiest
CONTRIB = ((22, 27, 34), (14, 68, 41), (0, 109, 50), (38, 166, 65), (57, 211, 83))


def measure(text, size=BODY_SIZE):
    screen.font = BODY_FONT
    if VECTOR_TEXT:
        return screen.measure_text(text, font_size=size)[0]
    return screen.measure_text(text)[0]


def trim(text, width, size=BODY_SIZE):
    """Trim text with "..." until it is at most width pixels wide."""
    if measure(text, size) <= width:
        return text
    while text and measure(text + "...", size) > width:
        text = text[:-1]
    return text + "..." if text else ""


def write(text, x, y, size=BODY_SIZE, pen=None, width=0, align="l"):
    """Draw body text; align is "l", "c" (x is the centre) or "r" (x is the right)."""
    if width:
        text = trim(text, width, size)
    if align != "l":
        w = measure(text, size)
        x = x - w / 2 if align == "c" else x - w
    screen.font = BODY_FONT
    if pen is not None:
        screen.pen = pen
    if VECTOR_TEXT:
        screen.text(text, x, y, size)
    else:
        screen.text(text, x, y)
    return text


def box(x, y, w, h, pen, r=0):
    screen.pen = pen
    if r:
        screen.shape(shape.rounded_rectangle(x, y, w, h, r))
    else:
        screen.shape(shape.rectangle(x, y, w, h))


def bar(x, y, w, h, percent, pen):
    """A progress bar; percent is an int from 0 to 100."""
    box(x, y, w, h, FAINT, h / 2)
    percent = max(0, min(100, percent))
    if percent > 0:
        box(x, y, max(h, w * percent // 100), h, pen, h / 2)


def rgb_of(value):
    return ((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF)


def mix(a, b, percent):
    """Blend from colour a towards b by an int percent."""
    return (
        a[0] + (b[0] - a[0]) * percent // 100,
        a[1] + (b[1] - a[1]) * percent // 100,
        a[2] + (b[2] - a[2]) * percent // 100,
    )


def luma(rgb):
    return (54 * rgb[0] + 183 * rgb[1] + 19 * rgb[2]) >> 8


def pen_of(rgb, alpha=255):
    return color.rgb(rgb[0], rgb[1], rgb[2], alpha)


def new_image(w, h):
    try:
        gc.collect()
    except Exception:
        pass
    try:
        return image(w, h)
    except Exception:
        return None


# -- identity and saved Monas -------------------------------------------

def secret(key):
    try:
        import secrets
        return str(getattr(secrets, key, "") or "").strip()
    except Exception:
        return ""


def read_json(path):
    try:
        with open(path) as file:
            return json.load(file)
    except Exception:
        return None


def same(a, b):
    return bool(a) and bool(b) and a.lower() == b.lower()


def nice_handle(text):
    """A handle that keeps its case when it is already valid."""
    if not isinstance(text, str):
        return ""
    text = text.strip()
    return text if mona_dna.valid_handle(text) else mona_dna.clean_handle(text)


def badge_uid():
    try:
        uid = badge.uid
        if callable(uid):
            uid = uid()
        return str(uid) or "badge"
    except Exception:
        return "badge"


def load_owner():
    """(handle, dna, name, profile) for whoever wears this badge."""
    profile = mona_net.slim(read_json(BADGE_USER_FILE))
    handle = nice_handle(secret("GITHUB_USERNAME"))
    if not handle and profile is not None:
        handle = profile["login"]
    if profile is not None and not same(profile["login"], handle):
        profile = None
    name = profile.get("name", "") if profile is not None else ""
    if handle:
        dna = mona_dna.dna_for(handle)
        if profile is not None:
            dna = mona_dna.apply_profile(dna, profile)[0]
    else:
        dna = mona_dna.dna_for_uid(badge_uid())
    return (handle, dna, name, profile)


def backdrop_key(handle, dna):
    """What a cached backdrop depends on."""
    who = handle.lower() if handle else mona_dna.short_id(dna)
    return "%s:%d:%d" % (who, dna[mona_dna.BODY], dna[mona_dna.BACKDROP])


class MonaApp:
    def __init__(self):
        self.style = VECTOR
        self.palette = mona_ascii.PRIMER
        self.load()
        self.owner = load_owner()
        self.current = self.me()

        self.art = new_image(ART_W, ART_H)
        self.back = new_image(WIDTH, FOOT_Y)
        if self.back is not None:
            self.back.antialias = image.X2
        self.back_for = None
        self.back_base = NIGHT
        self.back_glow = NIGHT
        self.back_dark = False
        self.painter = mona_octo.Painter(ART_FILE)
        self.shown = None
        self.painted = False
        self.art_warned = False
        self.ascii = mona_ascii.AsciiView()
        self.ascii_warned = False

        self.toast = ""
        self.toast_pen = WHITE
        self.toast_until = 0
        self.closed = False

    def me(self):
        return (self.owner[0], self.owner[1], self.owner[2], "you")

    def load(self):
        data = {"style": VECTOR, "palette": 0}
        try:
            STORE.load(STATE_KEY, data)
        except Exception:
            pass
        style = data.get("style")
        if isinstance(style, int) and 0 <= style < len(STYLES):
            self.style = style
        palette = data.get("palette")
        if isinstance(palette, int) and 0 <= palette < len(mona_ascii.PALETTE_NAMES):
            self.palette = palette

    def save(self):
        data = {
            "style": self.style,
            "palette": self.palette,
        }
        try:
            STORE.save(STATE_KEY, data)
        except Exception:
            pass

    def say(self, text, pen=WHITE):
        self.toast = mona_dna.clean_text(text, 60)
        self.toast_pen = pen
        self.toast_until = badge.ticks + TOAST_MS

    # -- input ---------------------------------------------------------------

    def main_input(self, now):
        if badge.pressed(BUTTON_LEFT):
            self.set_style(self.style - 1)
        elif badge.pressed(BUTTON_RIGHT):
            self.set_style(self.style + 1)
        elif badge.pressed(BUTTON_UP):
            if self.style != VECTOR:
                self.palette = (self.palette + 1) % len(mona_ascii.PALETTE_NAMES)
                self.save()
        elif badge.pressed(BUTTON_BACK):
            self.leave()

    def set_style(self, style):
        self.style = style % len(STYLES)
        self.save()

    # -- painting ---------------------------------------------------------------

    def wanted(self):
        """The DNA the art should show right now, or None to keep it."""
        return self.current[1]

    def start_paint(self, dna):
        self.shown = dna
        self.painted = False
        self.ascii.clear()
        art = self.art
        art.pen = CLEAR
        art.clear()
        picks, misc = mona_dna.picks_of(dna)
        blocks, flags = mona_octo.compose(picks, misc)
        scale, x, y = FIT
        self.painter.start(art, blocks, flags, mona_dna.colours_of(dna), scale, x, y)

    def paint(self, now):
        if self.art is None:
            return
        want = self.wanted()
        if want != self.shown:
            self.start_paint(want)
        if self.shown is None or self.painted:
            return
        budget = 20
        if self.painter.step(budget):
            self.painted = True
            if self.painter.failed:
                if not self.art_warned:
                    self.art_warned = True
                    self.say("Octocat " + self.painter.failed, RED)
            else:
                self.ascii.set_source(self.art)

    def art_problem(self):
        if self.art is None:
            return "no memory for the art"
        return self.painter.failed

    def paint_backdrop(self, key, dna):
        """Cache the backdrop behind the shown Mona; colours follow its body."""
        self.back_for = key
        main, light, accent = [rgb_of(v) for v in mona_dna.body_rgb(dna)]
        base = mix(NIGHT, main, 22)
        glow = light if luma(light) >= luma(accent) else accent
        self.back_base = base
        self.back_glow = glow
        self.back_dark = luma(main) < 90
        img = self.back
        if img is None:
            return
        img.pen = pen_of(base)
        img.clear()
        kind = mona_dna.backdrop_of(dna)
        rng = mona_dna.Rng(mona_dna.seed_of("back:" + key))
        if kind == 1:
            for row in range(18):
                for col in range(26):
                    roll = rng.below(100)
                    level = 0 if roll < 50 else 1 if roll < 75 else 2 if roll < 88 else 3 if roll < 96 else 4
                    img.pen = pen_of(mix(base, CONTRIB[level], 70 if level == 0 else 50))
                    img.shape(shape.rounded_rectangle(5 + col * 12, 3 + row * 12, 10, 10, 2))
        elif kind == 2:
            for _ in range(70):
                x = rng.below(WIDTH)
                y = rng.below(FOOT_Y)
                img.pen = color.rgb(255, 255, 255, 90 + rng.below(141))
                img.shape(shape.circle(x, y, 0.8 if rng.below(100) < 75 else 1.4))
            for _ in range(4):
                img.pen = pen_of(glow, 210)
                img.shape(shape.star(10 + rng.below(WIDTH - 20), 10 + rng.below(FOOT_Y - 20), 4, 1.2, 5.0))
        elif kind == 3:
            for i in range(5):
                img.pen = pen_of(glow, 90 - 12 * i)
                img.shape(shape.circle(CENTRE_X, CENTRE_Y, 40 + 22 * i).stroke(1.5))
            for _ in range(3):
                radius = 40 + 22 * (1 + rng.below(4))
                angle = rng.below(360) * math.pi / 180
                img.pen = pen_of(accent, 220)
                img.shape(shape.circle(CENTRE_X + radius * math.cos(angle), CENTRE_Y + radius * math.sin(angle), 3))
        self.halo(img)

    def halo(self, target):
        """A soft light behind Mona so dark bodies stand out."""
        strong = 64 if self.back_dark else 34
        target.pen = pen_of(self.back_glow, strong // 2)
        target.shape(shape.circle(CENTRE_X, CENTRE_Y, 92))
        target.pen = pen_of(self.back_glow, strong)
        target.shape(shape.circle(CENTRE_X, CENTRE_Y, 64))

    # -- lifecycle --------------------------------------------------------------

    def update(self):
        if self.closed:
            return
        now = badge.ticks
        self.main_input(now)
        if self.closed:
            return
        self.paint(now)
        self.draw(now)

    def leave(self):
        self.shutdown()
        try:
            reset()
        except Exception:
            pass

    def shutdown(self):
        if self.closed:
            return
        self.closed = True
        self.painter.close()
        self.save()

    # -- drawing ----------------------------------------------------------------

    def draw(self, now):
        self.draw_stage(now)
        self.draw_panel(now)
        self.draw_footer(now)
        if self.toast and now - self.toast_until < 0:
            self.draw_toast()

    def draw_stage(self, now):
        """The backdrop and the Mona, as vector art or as ASCII art."""
        if self.style != VECTOR and self.painted and not self.art_problem():
            view = self.ascii
            if not view.failed:
                view.set_mode(ASCII_STYLE[self.style], self.palette)
                view.step(2)
            if not view.failed:
                screen.pen = pen_of(mona_ascii.BACKS[self.palette])
                screen.clear()
                if view.draw(screen, ART_X, ART_Y, now):
                    return
            if view.failed and not self.ascii_warned:
                self.ascii_warned = True
                self.say("No memory for ASCII art, showing vector", RED)
        self.draw_backdrop()
        self.draw_art(now)

    def draw_backdrop(self):
        dna = self.shown if self.shown is not None else self.current[1]
        key = backdrop_key(self.current[0], dna)
        if key != self.back_for:
            self.paint_backdrop(key, dna)
        if self.back is not None:
            screen.blit(self.back, vec2(0, 0))
        else:
            screen.pen = pen_of(self.back_base)
            screen.clear()
            self.halo(screen)

    def draw_art(self, now):
        problem = self.art_problem()
        if problem:
            write("Octocat art", CENTRE_X, 88, TITLE_SIZE, RED, ART_W - 16, "c")
            write(problem, CENTRE_X, 110, SMALL_SIZE, WHITE, ART_W - 16, "c")
            write("copy octocat.bin with the app", CENTRE_X, 128, SMALL_SIZE, DIM, ART_W - 16, "c")
            return
        bob = 0
        if self.painted and self.style == VECTOR:
            bob = int(round(2 * math.sin(now / 650.0)))
        screen.blit(self.art, vec2(ART_X, ART_Y + bob))

    def status(self, now):
        """(text, pen, percent or None) for the bottom of the panel."""
        problem = self.art_problem()
        if problem:
            return (problem, RED, None)
        if not self.painted:
            done = self.painter.progress()
            return ("Painting %d%%" % done, DIM, done)
        if self.style != VECTOR and self.ascii.typing:
            return ("Converting", DIM, self.ascii.row * 100 // mona_ascii.ROWS)
        return ("Ready", GREEN, None)

    def style_label(self):
        if self.style == VECTOR:
            return "Vector art"
        return STYLES[self.style] + " / " + mona_ascii.PALETTE_NAMES[self.palette]

    def draw_panel(self, now):
        x, y, w, h = PANEL_X, 2, PANEL_W, FOOT_Y - 4
        box(x, y, w, h, PANEL, 8)
        handle, dna, name, via = self.current
        left = x + 8
        room = w - 16
        if handle:
            write("@" + handle, left, y + 6, TITLE_SIZE, WHITE, room)
            sub = name
        else:
            write("Mystery Mona", left, y + 6, TITLE_SIZE, WHITE, room)
            sub = name or ("#" + mona_dna.short_id(dna))
        ty = y + 26
        if sub:
            write(sub, left, ty, SMALL_SIZE, DIM, room)
            ty += 16
        write(mona_dna.title_of(dna), left, ty, SMALL_SIZE, ACCENT, room)
        ty += 22
        items = mona_dna.highlights(dna, 4)
        if not items:
            items = ["Classic Mona"]
        for item in items:
            screen.pen = ACCENT
            screen.shape(shape.circle(left + 3, ty + 7, 2))
            write(item, left + 10, ty, SMALL_SIZE, WHITE, room - 10)
            ty += 17
        write("Your Mona", left, y + 150, SMALL_SIZE, DIM, room)
        write(self.style_label(), left, y + 166, SMALL_SIZE, DIM, room)
        text, pen, percent = self.status(now)
        write(text, left, y + 186, SMALL_SIZE, pen, room)
        if percent is not None:
            bar(left, y + 204, room, 4, percent, pen)

    def hints(self):
        first = "LEFT/RIGHT style" + ("" if self.style == VECTOR else "  UP colours")
        second = "BACK exit"
        return (first, second)

    def draw_footer(self, now):
        box(0, FOOT_Y, WIDTH, HEIGHT - FOOT_Y, BAR)
        lines = self.hints()
        text = lines[(now // HINT_SWAP_MS) % len(lines)]
        write(text, WIDTH / 2, FOOT_Y + 4, SMALL_SIZE, DIM, WIDTH - 12, "c")

    def draw_toast(self):
        text = trim(self.toast, WIDTH - 60, BODY_SIZE)
        w = measure(text, BODY_SIZE) + 24
        x = (WIDTH - w) / 2
        box(x, 192, w, 24, PANEL, 12)
        write(text, x + 12, 196, BODY_SIZE, self.toast_pen)


app = MonaApp()


def update():
    app.update()


def on_exit():
    app.shutdown()


run(update)
