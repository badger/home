import gc
import json
import math
import os
import sys

import machine
from badgeware import State

try:
    from badgeware import link as badgelink
except ImportError:
    badgelink = None

try:
    import secrets
except ImportError:
    secrets = None

APP_DIR = "/system/apps/trainer_card"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

STATE_KEY = "trainer_card"
USER_FILE = "/state/badge_user.json"
CONTRIB_FILE = "/state/badge_contribs.json"
AVATAR_FILE = "/state/badge_avatar.png"

FONT = font.match
SCALE = 2

WIDTH, HEIGHT = 320, 240
CARD_X, CARD_Y, CARD_W, CARD_H = 4, 4, 312, 208
PANEL = (8, 34, 296, 168)
HINT_Y = 221
FLIP_MS = 420
SHINE_PERIOD_MS = 5000
SHINE_SWEEP_MS = 1400
TIP_MS = 3000

ROW_X = 16
ROW_RIGHT = 212
ROW_TOP = 40
ROW_PITCH = 26
PORTRAIT = (222, 40, 76, 76)
AVATAR = (226, 44, 68, 68)
STAR_Y = 128

GRID_X, GRID_Y = 21, 38
SLOT_W, SLOT_H = 60, 58
PITCH_X, PITCH_Y = 70, 60
COLS, ROWS = 4, 2
DIALOG = (10, 158, 292, 42)

# The eight visible Mona's Expedition locations from apps/menu/achievements.py,
# in the same order, so their indices match the saved "achievements" state.
BADGES = (
    ("DINER", "Mo's Diner", "diner"),
    ("HOOD", "Under the Hood", "frying-pan"),
    ("CABANA", "Creator Cabana", "cabana"),
    ("RECORD", "Open Source Records", "vinyl"),
    ("MAKER", "Makerspace", "keycap"),
    ("HACKER", "Hack Your Badge", "ascii-mona"),
    ("DONUT", "Demos & Donuts", "ascii-donut"),
    ("LEVEL", "Level Up Lounge", "up-arrow"),
)
CAB_INDEX = 8

clear = color.rgb(0, 0, 0, 0)
white = color.rgb(255, 255, 255)
ink = color.rgb(56, 56, 64)
label_ink = color.rgb(112, 112, 120)
ink_shadow = color.rgb(212, 212, 200)
panel_fill = color.rgb(248, 248, 236)
panel_line = color.rgb(238, 236, 218)
slot_fill = color.rgb(228, 224, 206)
slot_edge = color.rgb(204, 198, 176)
dialog_fill = color.rgb(252, 252, 252)
dialog_edge = color.rgb(72, 72, 80)
gold = color.rgb(248, 200, 48)
gold_edge = color.rgb(168, 116, 16)
star_empty = color.rgb(0, 0, 0, 40)
hint_ink = color.rgb(232, 232, 240)
shine = color.rgb(255, 255, 255, 56)
card_shadow = color.rgb(0, 0, 0, 90)


def scaled(rgb, factor):
    return color.rgb(*(int(channel * factor) for channel in rgb))


class Theme:
    def __init__(self, name, main, dark, light):
        self.name = name
        self.main = color.rgb(*main)
        self.dark = color.rgb(*dark)
        self.light = color.rgb(*light)
        self.background = scaled(dark, 0.45)
        self.stripe = scaled(dark, 0.7)


THEMES = (
    Theme("RED", (216, 56, 48), (128, 24, 24), (248, 168, 152)),
    Theme("BLUE", (48, 104, 208), (24, 48, 120), (160, 192, 248)),
    Theme("GREEN", (40, 160, 72), (16, 88, 40), (160, 224, 168)),
    Theme("GOLD", (216, 160, 32), (128, 88, 8), (248, 216, 136)),
    Theme("PURPLE", (130, 80, 223), (64, 32, 128), (200, 176, 248)),
    Theme("BLACK", (48, 54, 61), (13, 17, 23), (139, 148, 158)),
)


def setting(key):
    return str(getattr(secrets, key, "") or "").strip()


def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError, MemoryError):
        return None


def load_state(key, data):
    try:
        State.load(key, data)
    except (OSError, ValueError):
        pass
    return data


def load_image(path):
    try:
        return image.load(path)
    except (OSError, ValueError, RuntimeError, MemoryError):
        return None


def number(value):
    # Compact counts (1.2K, 12K, 3.4M) so they fit beside the big row labels.
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        return "---"
    for size, suffix in ((1000000, "M"), (1000, "K")):
        if value >= size:
            if value < size * 10:
                tenths = value * 10 // size
                return "{}.{}{}".format(tenths // 10, tenths % 10, suffix).replace(".0" + suffix, suffix)
            return "{}{}".format(value // size, suffix)
    return str(value)


class Trainer:
    def __init__(self):
        self.handle = setting("GITHUB_USERNAME")
        name = setting("CONTACT_NAME")
        self.followers = None
        self.repos = None
        self.contribs = None
        self.avatar = None
        self.synced = False

        user = read_json(USER_FILE) if self.handle else None
        if isinstance(user, dict) and str(user.get("login", "")).lower() == self.handle.lower():
            self.synced = True
            self.handle = str(user["login"])
            name = name or str(user.get("name") or "")
            self.followers = user.get("followers")
            self.repos = user.get("public_repos")
        user = None
        gc.collect()

        if self.synced:
            contribs = read_json(CONTRIB_FILE)
            if isinstance(contribs, dict):
                self.contribs = contribs.get("total_contributions")
            contribs = None
            gc.collect()
            if file_exists(AVATAR_FILE):
                self.avatar = load_image(AVATAR_FILE)

        self.name = name or self.handle

        cards = load_state("contacts", {"cards": []}).get("cards")
        self.contacts = len(cards) if isinstance(cards, list) else 0

        unlocked = load_state("achievements", {"unlocked": [], "shown": None}).get("unlocked")
        if not isinstance(unlocked, list):
            unlocked = []
        self.badges = {index for index in unlocked if isinstance(index, int) and 0 <= index <= CAB_INDEX}

        uid = bytes(machine.unique_id())
        self.badge_id = uid[:badgelink.ID_LEN] if badgelink else uid
        self.id_no = "{:05d}".format(int.from_bytes(uid, "big") % 100000)

    @property
    def earned(self):
        return sum(1 for index in range(len(BADGES)) if index in self.badges)


def measure(text):
    screen.font = FONT
    w, h = screen.measure_text(text)
    return int(w) + 2, int(h) + 1


def fit(text, max_w, scale):
    if not max_w or measure(text)[0] * scale <= max_w:
        return text, scale
    if measure(text)[0] <= max_w:
        return text, 1
    while len(text) > 1 and measure(text + "..")[0] > max_w:
        text = text[:-1]
    return text + "..", 1


def pixel_text(target, text, x, y, pen, shade=None, align="left", max_w=0, scale=SCALE):
    # Bitmap fonts don't scale, so render at 1x and blit it enlarged for chunky pixels.
    text, used = fit(text, max_w, scale)
    w, h = measure(text)
    glyphs = image(w, h)
    glyphs.antialias = image.OFF
    glyphs.font = FONT
    glyphs.pen = clear
    glyphs.clear()
    if shade is not None:
        glyphs.pen = shade
        glyphs.text(text, 1, 1)
    glyphs.pen = pen
    glyphs.text(text, 0, 0)
    sw, sh = w * used, h * used
    if used < scale:
        y += (h * scale - sh) // 2
    if align == "right":
        x -= sw
    elif align == "center":
        x -= sw // 2
    target.blit(glyphs, rect(int(x), int(y), sw, sh))
    return sw


def load_awards():
    awards = []
    for _, _, kind in BADGES:
        awards.append(load_image("assets/awards/" + kind + ".png"))
    return awards


trainer = Trainer()
awards = load_awards()
cab_award = load_image("assets/awards/cab.png")

state = load_state(STATE_KEY, {"theme": 0})
theme_index = state.get("theme")
if not isinstance(theme_index, int) or not 0 <= theme_index < len(THEMES):
    theme_index = 0

card = image(CARD_W, CARD_H)
card.antialias = image.X2

side = 0
cursor = 0
flip_start = None
flip_swapped = False

band = shape.rectangle(-12, -170, 24, 340)
sliver = shape.rectangle(-3, -170, 6, 340)
stripe = shape.line(0, -20, -260, 260, 9)


def slot_position(index):
    return GRID_X + (index % COLS) * PITCH_X, GRID_Y + (index // COLS) * PITCH_Y


def draw_frame(theme, title, right_text):
    card.pen = clear
    card.clear()
    card.pen = theme.main
    card.shape(shape.rounded_rectangle(0, 0, CARD_W, CARD_H, 12))
    card.pen = theme.light
    card.shape(shape.rounded_rectangle(3, 3, CARD_W - 6, CARD_H - 6, 10).stroke(1))
    card.pen = theme.dark
    card.shape(shape.rounded_rectangle(0, 0, CARD_W, CARD_H, 12).stroke(2))

    px, py, pw, ph = PANEL
    card.pen = panel_fill
    card.shape(shape.rounded_rectangle(px, py, pw, ph, 8))
    card.pen = panel_line
    for y in range(py + 6, py + ph - 4, 4):
        card.rectangle(px + 3, y, pw - 6, 2)
    card.pen = theme.dark
    card.shape(shape.rounded_rectangle(px, py, pw, ph, 8).stroke(2))

    title_w = pixel_text(card, title, 12, 5, white, theme.dark)
    return pixel_text(card, right_text, CARD_W - 12, 5, white, theme.dark, "right", CARD_W - 32 - title_w)


def underline(theme, y):
    card.pen = theme.light
    for x in range(ROW_X, ROW_RIGHT, 6):
        card.rectangle(x, y + 23, 3, 2)


def draw_row(theme, label, value, y):
    label_w = pixel_text(card, label, ROW_X, y, label_ink, ink_shadow)
    pixel_text(card, value, ROW_RIGHT, y, ink, ink_shadow, "right", ROW_RIGHT - ROW_X - label_w - 6)
    underline(theme, y)


def draw_portrait(theme):
    x, y, w, h = PORTRAIT
    card.pen = theme.dark
    card.shape(shape.rounded_rectangle(x, y, w, h, 6))
    card.pen = theme.light
    card.shape(shape.rounded_rectangle(x + 2, y + 2, w - 4, h - 4, 5))

    ax, ay, size, _ = AVATAR
    if trainer.avatar:
        card.blit(trainer.avatar, rect(ax, ay, size, size))
    elif badgelink:
        badgelink.draw_identicon(card, trainer.badge_id, ax, ay, size)
    else:
        card.pen = theme.dark
        card.shape(shape.circle(ax + size // 2, ay + size // 3 + 2, size // 5))
        card.shape(shape.rounded_rectangle(ax + size // 5, ay + size * 3 // 5, size * 3 // 5, size * 2 // 5, 10))


def draw_stars():
    stars = trainer.earned // 2
    centre = PORTRAIT[0] + PORTRAIT[2] // 2
    for index in range(4):
        cx = centre - 27 + index * 18
        star = shape.star(cx, STAR_Y, 5, 3.6, 8)
        if index < stars:
            card.pen = gold
            card.shape(star)
            card.pen = gold_edge
            card.shape(shape.star(cx, STAR_Y, 5, 3.6, 8).stroke(1))
        else:
            card.pen = star_empty
            card.shape(star)


def render_front(theme):
    draw_frame(theme, "TRAINER CARD", "No." + trainer.id_no)

    y = ROW_TOP
    if trainer.name:
        pixel_text(card, trainer.name, ROW_X, y, ink, ink_shadow, max_w=ROW_RIGHT - ROW_X)
        underline(theme, y)
    else:
        draw_row(theme, "NAME", "???", y)
    y += ROW_PITCH
    if trainer.handle:
        pixel_text(card, "@" + trainer.handle, ROW_X, y, theme.dark, ink_shadow, max_w=ROW_RIGHT - ROW_X)
        underline(theme, y)
    else:
        draw_row(theme, "GITHUB", "---", y)
    y += ROW_PITCH
    draw_row(theme, "CONTRIBS", number(trainer.contribs), y)
    y += ROW_PITCH
    draw_row(theme, "FOLLOWERS", number(trainer.followers), y)
    y += ROW_PITCH
    draw_row(theme, "REPOS", number(trainer.repos), y)
    y += ROW_PITCH
    draw_row(theme, "CONTACTS", number(trainer.contacts), y)

    draw_portrait(theme)
    draw_stars()
    centre = PORTRAIT[0] + PORTRAIT[2] // 2
    pixel_text(card, "BADGES", centre, 140, label_ink, None, "center", scale=1)
    pixel_text(card, "{}/{}".format(trainer.earned, len(BADGES)), centre, 154, ink, ink_shadow, "center")
    if CAB_INDEX in trainer.badges:
        pixel_text(card, "CAB MEMBER", centre, 182, gold_edge, None, "center", scale=1)


def render_back(theme):
    count = "{}/{}".format(trainer.earned, len(BADGES))
    count_w = draw_frame(theme, "BADGE CASE", count)

    for index in range(len(BADGES)):
        sx, sy = slot_position(index)
        card.pen = slot_fill
        card.shape(shape.rounded_rectangle(sx, sy, SLOT_W, SLOT_H, 8))
        card.pen = slot_edge
        card.shape(shape.rounded_rectangle(sx, sy, SLOT_W, SLOT_H, 8).stroke(1))
        art = awards[index]
        earned = index in trainer.badges
        if art:
            # Image-to-image blits fade with the destination's alpha, not the source's.
            card.alpha = 255 if earned else 48
            card.blit(art, vec2(sx + (SLOT_W - 56) // 2, sy + (SLOT_H - 56) // 2))
            card.alpha = 255
        else:
            card.pen = theme.main if earned else star_empty
            card.shape(shape.circle(sx + SLOT_W // 2, sy + SLOT_H // 2, 20))

    if cab_award and CAB_INDEX in trainer.badges:
        card.blit(cab_award, rect(CARD_W - 12 - count_w - 32, 3, 28, 28))

    dx, dy, dw, dh = DIALOG
    card.pen = dialog_fill
    card.shape(shape.rounded_rectangle(dx, dy, dw, dh, 6))
    card.pen = dialog_edge
    card.shape(shape.rounded_rectangle(dx, dy, dw, dh, 6).stroke(2))
    card.pen = theme.main
    card.shape(shape.rounded_rectangle(dx + 4, dy + 4, dw - 8, dh - 8, 4).stroke(1))

    short, place, _ = BADGES[cursor]
    pixel_text(card, short + " BADGE", dx + 10, dy + 2, ink, ink_shadow, max_w=dw - 40)
    if cursor in trainer.badges:
        detail = "Earned at " + place + "!"
    else:
        detail = "Visit " + place + " to earn it."
    pixel_text(card, detail, dx + 10, dy + 26, label_ink, None, max_w=dw - 40, scale=1)


def render():
    theme = THEMES[theme_index]
    if side == 0:
        render_front(theme)
    else:
        render_back(theme)
    gc.collect()


def draw_background(theme):
    screen.pen = theme.background
    screen.rectangle(0, 0, WIDTH, HEIGHT)
    screen.pen = theme.stripe
    offset = (badge.ticks // 60) % 28
    for index in range(22):
        stripe.transform = mat3().translate(index * 28 + offset, 0)
        screen.shape(stripe)


def draw_shine():
    phase = badge.ticks % SHINE_PERIOD_MS
    if phase >= SHINE_SWEEP_MS:
        return
    x = CARD_X - 40 + (CARD_W + 80) * phase / SHINE_SWEEP_MS
    screen.clip = rect(CARD_X + 3, CARD_Y + 3, CARD_W - 6, CARD_H - 6)
    screen.pen = shine
    band.transform = mat3().translate(x, CARD_Y + CARD_H / 2).rotate(20)
    screen.shape(band)
    sliver.transform = mat3().translate(x + 24, CARD_Y + CARD_H / 2).rotate(20)
    screen.shape(sliver)
    screen.clip = rect(0, 0, WIDTH, HEIGHT)


def draw_cursor():
    sx, sy = slot_position(cursor)
    pulse = 0.5 + 0.5 * math.sin(badge.ticks / 160)
    screen.pen = color.rgb(232, 64, 48, int(130 + 125 * pulse))
    screen.shape(shape.rounded_rectangle(CARD_X + sx - 3, CARD_Y + sy - 3, SLOT_W + 6, SLOT_H + 6, 10).stroke(3))

    if (badge.ticks // 450) % 2 == 0:
        dx, dy, dw, dh = DIALOG
        x = CARD_X + dx + dw - 26
        y = CARD_Y + dy + dh - 16
        screen.pen = color.rgb(232, 64, 48)
        for row in range(4):
            screen.rectangle(x + row * 2, y + row * 2, 14 - row * 4, 2)


def hint():
    if side == 1:
        return "ARROWS: CHOOSE    SELECT: FLIP"
    tip = (badge.ticks // TIP_MS) % 2 == 1
    if tip and not trainer.handle and not trainer.name:
        return "ADD YOUR NAME IN THE SETTINGS APP"
    if tip and trainer.handle and not trainer.synced:
        return "OPEN THE BADGE APP TO SYNC STATS"
    return "SELECT: FLIP    UP/DOWN: COLOR"


def draw_hint():
    text = hint()
    screen.font = FONT
    w, _ = screen.measure_text(text)
    screen.pen = hint_ink
    screen.text(text, int((WIDTH - w) / 2), HINT_Y)


def start_flip():
    global flip_start, flip_swapped
    flip_start = badge.ticks
    flip_swapped = False


def handle_input():
    global theme_index, cursor
    if badge.pressed(BUTTON_SELECT) or (side == 1 and badge.pressed(BUTTON_BACK)):
        start_flip()
        return

    if side == 0:
        step = (1 if badge.pressed(BUTTON_DOWN) else 0) - (1 if badge.pressed(BUTTON_UP) else 0)
        if step:
            theme_index = (theme_index + step) % len(THEMES)
            state["theme"] = theme_index
            State.save(STATE_KEY, state)
            render()
        return

    column, row = cursor % COLS, cursor // COLS
    if badge.pressed(BUTTON_LEFT):
        column = (column - 1) % COLS
    if badge.pressed(BUTTON_RIGHT):
        column = (column + 1) % COLS
    if badge.pressed(BUTTON_UP):
        row = (row - 1) % ROWS
    if badge.pressed(BUTTON_DOWN):
        row = (row + 1) % ROWS
    moved = row * COLS + column
    if moved != cursor:
        cursor = moved
        render()


def draw_card():
    global side, flip_start, flip_swapped
    if flip_start is None:
        screen.pen = card_shadow
        screen.shape(shape.rounded_rectangle(CARD_X + 4, CARD_Y + 5, CARD_W, CARD_H, 12))
        screen.blit(card, vec2(CARD_X, CARD_Y))
        draw_shine()
        if side == 1:
            draw_cursor()
        return

    t = min(1.0, (badge.ticks - flip_start) / FLIP_MS)
    if t >= 0.5 and not flip_swapped:
        side = 1 - side
        flip_swapped = True
        render()
    w = int(CARD_W * abs(math.cos(math.pi * t)))
    lift = int(10 * math.sin(math.pi * t))
    x = CARD_X + (CARD_W - w) // 2
    if w > 24:
        screen.pen = card_shadow
        screen.shape(shape.rounded_rectangle(x + 4, CARD_Y + 5, w, CARD_H, 12))
    if w > 0:
        screen.blit(card, rect(x, CARD_Y - lift, w, CARD_H))
    if t >= 1.0:
        flip_start = None


def update():
    if flip_start is None:
        handle_input()
    draw_background(THEMES[theme_index])
    draw_card()
    draw_hint()


render()
run(update)
