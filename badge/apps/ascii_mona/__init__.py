"""ASCII Mona: a custom MyOctocat for any GitHub handle.

A handle becomes 19 numbers of Mona DNA that pick parts and colours from
GitHub's own MyOctocat library (myoctocat.com). The badge paints that outfit
as vector art, or as ASCII art built with Ascii-Motion's techniques. Handles
come from the badge owner, from saved Contacts cards or from the arcade
letter wheel.
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
import mona_link
import mona_net
import mona_octo
import mona_wheel


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
MONO_FONT = getattr(font, "badgewaremax", None) or font.teatime


def _mono_size():
    screen.font = MONO_FONT
    try:
        w, h = screen.measure_text("W")
        return int(w + 0.5), int(h + 0.5)
    except Exception:
        return 8, 12


MONO_W, MONO_H = _mono_size()


def _art_file():
    for path in (APP_DIR + "/octocat.bin", "octocat.bin"):
        try:
            os.stat(path)
            return path
        except OSError:
            pass
    return APP_DIR + "/octocat.bin"


ART_FILE = _art_file()

try:
    MENU_BUTTON = BUTTON_MENU
except NameError:
    MENU_BUTTON = None

# (wheel name, logical button) pairs the letter wheel listens to
BUTTONS = (
    ("up", BUTTON_UP),
    ("down", BUTTON_DOWN),
    ("left", BUTTON_LEFT),
    ("right", BUTTON_RIGHT),
    ("select", BUTTON_SELECT),
    ("back", BUTTON_BACK),
    ("menu", MENU_BUTTON),
)

STATE_KEY = "ascii_mona"
CONTACTS_FILE = "/state/contacts.json"
BADGE_USER_FILE = "/state/badge_user.json"
MAX_RECENT = 8
MAX_CONTACTS = 24

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
WHO_ROWS = 6
WHEEL_SLOTS = 13
SLOT_W = 21
PREVIEW = (208, 100, 96, 108)

TOAST_MS = 2600
HINT_SWAP_MS = 4000
PAINT_DELAY_MS = 250

MAIN = 0
WHO = 1
WHEEL = 2

STYLES = ("Vector", "Shapes", "Dither", "Edges")
VECTOR = 0
ASCII_STYLE = (0, mona_ascii.SHAPES, mona_ascii.DITHER, mona_ascii.EDGES)
# (saved value, what the panel calls it)
VIAS = (
    ("you", "Your Mona"),
    ("typed", "Typed in"),
    ("contact", "From Contacts"),
    ("surprise", "Surprise Mona"),
    ("saved", "Saved Mona"),
)

WHITE = color.rgb(240, 246, 252)
DIM = color.rgb(255, 255, 255, 150)
FAINT = color.rgb(255, 255, 255, 50)
INK = color.rgb(1, 4, 9)
BAR = color.rgb(22, 27, 34)
PANEL = color.rgb(13, 17, 23, 238)
PICKED = color.rgb(110, 64, 201, 170)
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


def mono(text, x, y, pen):
    screen.font = MONO_FONT
    screen.pen = pen
    screen.text(text, x, y)


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


ROW_TYPE = 0
ROW_PICK = 1
ROW_SURPRISE = 2


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


def via_label(via):
    for key, label in VIAS:
        if key == via:
            return label
    return "Saved Mona"


def known_via(via):
    for key, _ in VIAS:
        if key == via:
            return True
    return False


def make_record(handle, dna, name, via):
    return {"github": handle, "dna": mona_dna.dna_hex(dna), "name": name, "via": via}


def read_record(value):
    """(handle, dna, name, via) from a saved record, or None."""
    card = mona_link.read_card(value)
    if card is None:
        return None
    via = value.get("via")
    if not known_via(via):
        via = "saved"
    return (card[0], card[1], card[2], via)


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


def load_contacts():
    """(handle, dna, name) for cards saved by the Contacts app, newest first."""
    data = read_json(CONTACTS_FILE)
    cards = data.get("cards") if isinstance(data, dict) else None
    out = []
    if isinstance(cards, list):
        for card in cards:
            got = mona_link.read_card(card)
            if got is not None and got[0]:
                out.append(got)
                if len(out) >= MAX_CONTACTS:
                    break
    return out


def who_label(handle, dna):
    if handle:
        return "@" + handle
    return "Mystery Mona #" + mona_dna.short_id(dna)


def backdrop_key(handle, dna):
    """What a cached backdrop depends on."""
    who = handle.lower() if handle else mona_dna.short_id(dna)
    return "%s:%d:%d" % (who, dna[mona_dna.BODY], dna[mona_dna.BACKDROP])


class MonaApp:
    def __init__(self):
        self.recent = []
        self.style = VECTOR
        self.palette = mona_ascii.PRIMER
        self.typed = ""
        self.current = None
        self.load()
        self.owner = load_owner()
        if self.current is None or self.current[3] == "you":
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
        self.pending = None
        self.pending_at = 0
        self.art_warned = False
        self.ascii = mona_ascii.AsciiView()
        self.ascii_warned = False
        self.rng = mona_dna.Rng(mona_dna.fmix32((mona_dna.seed_of(badge_uid()) ^ badge.ticks) & mona_dna.MASK))

        self.view = MAIN
        self.info = False
        self.rows = []
        self.row = 0
        self.wheel = None
        self.wheel_text = None
        self.wheel_dna = None
        self.toast = ""
        self.toast_pen = WHITE
        self.toast_until = 0
        self.closed = False

    def me(self):
        return (self.owner[0], self.owner[1], self.owner[2], "you")

    def load(self):
        data = {"current": None, "recent": [], "style": VECTOR, "palette": 0, "typed": ""}
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
        typed = data.get("typed")
        if isinstance(typed, str) and mona_dna.valid_handle(typed):
            self.typed = typed
        recent = data.get("recent")
        if isinstance(recent, list):
            for item in recent:
                rec = read_record(item)
                if rec is not None and len(self.recent) < MAX_RECENT:
                    self.recent.append(rec)
        self.current = read_record(data.get("current"))

    def save(self):
        data = {
            "current": make_record(self.current[0], self.current[1], self.current[2], self.current[3]),
            "recent": [make_record(r[0], r[1], r[2], r[3]) for r in self.recent],
            "style": self.style,
            "palette": self.palette,
            "typed": self.typed,
        }
        try:
            STORE.save(STATE_KEY, data)
        except Exception:
            pass

    def remember(self, rec):
        """Put a Mona at the top of the recent list (not you, no repeats)."""
        handle, dna = rec[0], rec[1]
        if rec[3] == "you" or same(handle, self.owner[0]):
            return
        keep = [rec]
        for old in self.recent:
            if handle and same(old[0], handle):
                continue
            if not handle and not old[0] and old[1] == dna:
                continue
            if len(keep) < MAX_RECENT:
                keep.append(old)
        self.recent = keep

    def tuned(self, handle):
        """Mona DNA for a handle."""
        return mona_dna.dna_for(handle)

    def adopt(self, handle, dna, name, via):
        rec = (handle or "", tuple(dna), name or "", via)
        self.remember(rec)
        self.info = False
        self.show(rec)
        self.save()

    def show(self, rec):
        self.current = rec

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
            if self.style == VECTOR or self.info:
                self.info = not self.info
            else:
                self.palette = (self.palette + 1) % len(mona_ascii.PALETTE_NAMES)
                self.save()
        elif badge.pressed(BUTTON_DOWN):
            self.open_who()
        elif badge.pressed(BUTTON_BACK):
            if self.info:
                self.info = False
            else:
                self.leave()

    def set_style(self, style):
        self.style = style % len(STYLES)
        self.info = False
        self.save()

    def open_who(self):
        """The handle picker: type, you, recent Monas, contacts, surprise."""
        me = self.me()
        rows = [(ROW_TYPE, "Type a handle", "letter wheel", None)]
        rows.append((ROW_PICK, who_label(me[0], me[1]), "you", me))
        seen = [me[0].lower()] if me[0] else []
        for rec in self.recent:
            if rec[0]:
                if rec[0].lower() in seen:
                    continue
                seen.append(rec[0].lower())
            rows.append((ROW_PICK, who_label(rec[0], rec[1]), via_label(rec[3]), rec))
        for handle, dna, name in load_contacts():
            if handle.lower() in seen:
                continue
            seen.append(handle.lower())
            rows.append((ROW_PICK, "@" + handle, name or "contact", (handle, self.tuned(handle), name, "contact")))
        rows.append((ROW_SURPRISE, "Surprise me", "random DNA", None))
        self.rows = rows
        self.row = 1
        for i in range(len(rows)):
            rec = rows[i][3]
            if rec is not None and rec[0] == self.current[0] and rec[1] == self.current[1]:
                self.row = i
                break
        self.view = WHO

    def who_input(self, now):
        count = len(self.rows)
        if badge.pressed(BUTTON_UP):
            self.row = (self.row - 1) % count
        elif badge.pressed(BUTTON_DOWN):
            self.row = (self.row + 1) % count
        elif badge.pressed(BUTTON_SELECT):
            self.pick(self.rows[self.row], now)
        elif badge.pressed(BUTTON_BACK) or badge.pressed(BUTTON_LEFT):
            self.view = MAIN

    def pick(self, row, now):
        kind, rec = row[0], row[3]
        if kind == ROW_TYPE:
            self.wheel = mona_wheel.Wheel(self.current[0] or self.typed)
            self.wheel_text = None
            self.view = WHEEL
            return
        self.view = MAIN
        if kind == ROW_SURPRISE:
            dna = mona_dna.random_dna((self.rng.next() ^ now) & mona_dna.MASK)
            self.adopt("", dna, "", "surprise")
            self.say("A mystery Mona appears", ACCENT)
        else:
            self.adopt(rec[0], rec[1], rec[2], rec[3])

    def wheel_input(self, now):
        pressed = []
        held = []
        for name, button in BUTTONS:
            if button is None:
                continue
            if badge.pressed(button):
                pressed.append(name)
            if badge.held(button):
                held.append(name)
        result = self.wheel.update(now, pressed, held)
        if result == "cancel":
            self.view = MAIN
        elif result == "done":
            handle = self.wheel.text
            self.typed = handle
            self.view = MAIN
            if same(handle, self.owner[0]):
                self.info = False
                self.show(self.me())
                self.save()
                self.say("That's you, @" + handle, GREEN)
            else:
                self.adopt(handle, self.tuned(handle), "", "typed")
                self.say("Hello, @" + handle, GREEN)

    def update_wheel_dna(self):
        text = self.wheel.text
        if text != self.wheel_text:
            self.wheel_text = text
            self.wheel_dna = self.tuned(text) if mona_dna.valid_handle(text) else None

    # -- painting ---------------------------------------------------------------

    def wanted(self):
        """The DNA the art should show right now, or None to keep it."""
        if self.view == WHEEL:
            return self.wheel_dna
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
        if want is None or want == self.shown:
            self.pending = None
        else:
            if want != self.pending:
                self.pending = want
                slow = self.view == WHEEL
                self.pending_at = now + (PAINT_DELAY_MS if slow else 0)
            if now - self.pending_at >= 0:
                self.pending = None
                self.start_paint(want)
        if self.shown is None or self.painted:
            return
        if self.view == WHEEL:
            budget = 12
        else:
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
        if self.view == WHEEL:
            self.wheel_input(now)
        elif self.view == WHO:
            self.who_input(now)
        else:
            self.main_input(now)
        if self.closed:
            return
        if self.view == WHEEL:
            self.update_wheel_dna()
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
        if self.view == WHEEL:
            self.draw_wheel()
        elif self.view == WHO:
            self.draw_who()
        else:
            self.draw_stage(now)
            if self.info:
                self.draw_info()
            else:
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
        write(via_label(via), left, y + 150, SMALL_SIZE, DIM, room)
        write(self.style_label(), left, y + 166, SMALL_SIZE, DIM, room)
        text, pen, percent = self.status(now)
        write(text, left, y + 186, SMALL_SIZE, pen, room)
        if percent is not None:
            bar(left, y + 204, room, 4, percent, pen)

    def draw_info(self):
        x, y, w, h = 6, 4, 308, 212
        box(x, y, w, h, PANEL, 10)
        handle, dna, name, via = self.current
        via_text = write(via_label(via), x + w - 10, y + 9, SMALL_SIZE, DIM, 0, "r")
        write(who_label(handle, dna), x + 10, y + 6, TITLE_SIZE, WHITE, w - 30 - measure(via_text, SMALL_SIZE))
        rows = mona_dna.describe(dna)
        half = (len(rows) + 1) // 2
        for i in range(len(rows)):
            label, value = rows[i]
            cx = x + 10 + (i // half) * 150
            cy = y + 28 + (i % half) * 17
            write(label, cx, cy, SMALL_SIZE, DIM)
            write(value, cx + 58, cy, SMALL_SIZE, WHITE, 86)
        if name:
            write(name, x + 10, y + 148, SMALL_SIZE, WHITE, w - 20)
        elif not handle:
            write("Mystery Mona: no GitHub profile", x + 10, y + 148, SMALL_SIZE, DIM, w - 20)
        write("DNA " + mona_dna.dna_hex(dna), x + 10, y + 196, SMALL_SIZE, DIM, w - 20)

    def draw_who(self):
        screen.pen = INK
        screen.clear()
        count = len(self.rows)
        write("Who gets a Mona?", 16, 8, TITLE_SIZE, WHITE)
        write("%d/%d" % (self.row + 1, count), WIDTH - 16, 10, SMALL_SIZE, DIM, 0, "r")
        first = max(0, min(self.row - WHO_ROWS // 2, count - WHO_ROWS))
        for i in range(first, min(count, first + WHO_ROWS)):
            kind, label, note, rec = self.rows[i]
            y = 34 + (i - first) * 27
            if i == self.row:
                box(10, y, WIDTH - 20, 25, PICKED, 6)
            note = write(note, WIDTH - 18, y + 6, SMALL_SIZE, DIM, 110, "r") if note else ""
            room = WIDTH - 52 - (measure(note, SMALL_SIZE) if note else 0)
            write(label, 18, y + 4, BODY_SIZE, WHITE if kind == ROW_PICK else ACCENT, room)

    def draw_wheel(self):
        screen.pen = INK
        screen.clear()
        wheel = self.wheel
        write("Type a GitHub handle", 16, 6, TITLE_SIZE, WHITE)
        write("%d/%d" % (len(wheel.text), mona_dna.MAX_HANDLE), WIDTH - 16, 8, SMALL_SIZE, DIM, 0, "r")

        first, slots = wheel.window(WHEEL_SLOTS)
        count = len(slots)
        left = (WIDTH - count * SLOT_W) // 2
        top = 52
        pad = (SLOT_W - MONO_W) // 2
        for i in range(count):
            x = left + i * SLOT_W
            ch = mona_wheel.CHARS[slots[i]]
            if first + i == wheel.cursor:
                box(x + 1, top - 4, SLOT_W - 2, MONO_H + 8, PICKED, 4)
                mono(wheel.letter(1), x + pad, top - MONO_H - 8, FAINT)
                mono(wheel.letter(-1), x + pad, top + MONO_H + 8, FAINT)
            else:
                box(x + 1, top - 4, SLOT_W - 2, MONO_H + 8, BAR, 4)
            if ch == " ":
                mono("_", x + pad, top, FAINT)
            else:
                mono(ch, x + pad, top, WHITE)
        if first > 0:
            mono("<", left - MONO_W - 2, top, DIM)
        if first + count < len(wheel.slots):
            mono(">", left + count * SLOT_W + 2, top, DIM)

        text = wheel.text
        dna = self.wheel_dna if self.wheel_text == text else None
        write("@" + text, 16, 100, TITLE_SIZE, WHITE, 180)
        if dna is not None:
            write(mona_dna.title_of(dna), 16, 122, SMALL_SIZE, ACCENT, 180)
            items = mona_dna.highlights(dna, 3)
            for i in range(len(items)):
                write(items[i], 16, 140 + i * 16, SMALL_SIZE, WHITE, 180)
        if wheel.nudge:
            write(wheel.nudge, 16, 194, SMALL_SIZE, RED, 180)
        elif wheel.problem:
            write(wheel.problem, 16, 194, SMALL_SIZE, DIM, 180)
        else:
            write("SELECT makes this Mona", 16, 194, SMALL_SIZE, GREEN, 180)

        px, py, pw, ph = PREVIEW
        box(px, py, pw, ph, BAR, 8)
        if dna is None:
            write("?", px + pw / 2, py + ph / 2 - 9, TITLE_SIZE, FAINT, 0, "c")
        elif dna != self.shown or self.art_problem():
            write("...", px + pw / 2, py + ph / 2 - 9, TITLE_SIZE, FAINT, 0, "c")
        else:
            main = rgb_of(mona_dna.body_rgb(dna)[0])
            box(px, py, pw, ph, pen_of(mix(NIGHT, main, 22)), 8)
            screen.blit(self.art, rect(0, 0, ART_W, ART_H), rect(px, py, pw, ph), image.BILINEAR)

    def hints(self):
        menu = MENU_BUTTON is not None
        if self.view == WHEEL:
            first = "UP/DOWN letter  LEFT/RIGHT move"
            if menu:
                first = first + "  MENU delete"
            return (first, "SELECT done  BACK cancel")
        if self.view == WHO:
            return ("UP/DOWN choose  SELECT pick  BACK close",)
        if self.info:
            return ("UP/BACK close",)
        first = "LEFT/RIGHT style  UP " + ("info" if self.style == VECTOR else "colours")
        second = "DOWN pick a handle  BACK exit"
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
