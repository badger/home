import os
import sys
import time

from badgeware import get_backlight, set_backlight

try:
    import secrets
except ImportError:
    secrets = None

# Works whatever the app folder is called (speaker, speaker-2026, ...).
try:
    APP_DIR = __file__.rsplit("/", 1)[0]
except NameError:
    APP_DIR = "/system/apps/speaker"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

badge.mode(HIRES | VSYNC)
screen.antialias = image.X4  # smooth Lato text and microphone

# --- Talk details: edit these, or put them in talk.py (see README) ----------

SPEAKER = ""  # blank: use Contact Name from Settings
CONFERENCE = "YOUR CONFERENCE '26"
TITLE = ("Your talk title", "goes here")  # one string per line
WHEN = "Day, time, room"
AFTER_TALK = "Ask me about my talk"  # replaces WHEN after the talk

# (label, url, Mona animation shown beside the QR code)
# A page with a blank url is hidden. A blank LinkedIn url uses
# LinkedIn Profile from Settings.
PAGES = (
    ("talk", None, None),
    ("Session", "", "dance"),
    ("Sample code", "", "code"),
    ("LinkedIn", "", "heart"),
)
# Page order after the talk (Select switches): follow-up links first.
AFTER_ORDER = ("talk", "Sample code", "LinkedIn", "Session")

# talk.py next to this file overrides any of the settings above.
try:
    import talk
except ImportError:
    talk = None
for _name in ("SPEAKER", "CONFERENCE", "TITLE", "WHEN", "AFTER_TALK", "PAGES", "AFTER_ORDER"):
    if hasattr(talk, _name):
        globals()[_name] = getattr(talk, _name)

# --- Power -------------------------------------------------------------------

AWAKE_MS = 30000        # full brightness this long after the last touch
AWAKE_BACKLIGHT = 100   # percent
DIM_BACKLIGHT = 70      # percent after that; never off. Check the lowest visible level on the badge
DIM_FRAME_MS = 60       # extra pause per frame while dimmed to idle the CPU

# -----------------------------------------------------------------------------

WIDTH = 320
HEIGHT = 240
QR_SIDE = 186  # leaves room for the label underneath
QR_X = WIDTH - QR_SIDE - 14  # right-aligned, clear of the page dots
QR_Y = 8
QR_MARGIN = 6  # white border so phones find the code against the black screen
MONA_FRAME_MS = 120

# Frame counts match the sprite sheets (see monapet).
MONA_FRAMES = {"dance": 6, "code": 4, "heart": 14}

black = color.rgb(0, 0, 0)
white = color.rgb(255, 255, 255)
dim = color.rgb(140, 148, 158)
accent = color.rgb(15, 191, 62)

heavy = font.load("/system/assets/fonts/lato-900.af")
light = font.load("/system/assets/fonts/lato-400.af")
# (typeface, size in px) for each kind of text
CONFERENCE_TEXT = (heavy, 20)
TITLE_TEXT = (heavy, 30)
NAME_TEXT = (light, 26)
WHEN_TEXT = (light, 20)
LABEL_TEXT = (heavy, 24)
TITLE_GAP = 10  # between the title lines
MIC_WIDTH = 18
MIC_HEIGHT = 30
MIC_GAP = 8

monas = {
    name: image.load("assets/mona-sprites/mona-%s.png" % name).spritesheet(frames, 1)
    for name, frames in MONA_FRAMES.items()
}


def setting(key):
    # Values from the badge's Settings app, stored in secrets.py.
    return str(getattr(secrets, key, "") or "").strip()


def linkedin_url(value):
    # Settings may hold a full URL, a bare linkedin.com address or a handle.
    value = value.strip().rstrip("/")
    if not value or value.startswith("https://"):
        return value
    if "linkedin.com" in value:
        return "https://" + value.split("://")[-1]
    return "https://www.linkedin.com/in/" + value.split("/")[-1]


SPEAKER = SPEAKER or setting("CONTACT_NAME") or "Your Name"
PAGES = tuple(
    (label, linkedin_url(setting("CONTACT_LINKEDIN")), mona) if label == "LinkedIn" and not url else (label, url, mona)
    for label, url, mona in PAGES
)
PAGES = tuple(p for p in PAGES if p[1] is None or p[1])  # hide QR pages without a URL
AFTER_ORDER = tuple(label for label in AFTER_ORDER if label in [p[0] for p in PAGES])


def measure(text, style):
    typeface, size = style
    screen.font = typeface
    w, h = screen.measure_text(text, font_size=size)
    return int(w), int(h)


def draw_text(text, x, y, style, pen):
    typeface, size = style
    screen.font = typeface
    screen.pen = pen
    screen.text(text, x, y, size)


def centred(text, y, style, pen):
    w, _ = measure(text, style)
    draw_text(text, (WIDTH - w) // 2, y, style, pen)


def draw_microphone(x, y):
    # 18x30 px: capsule with grille lines, U-shaped holder, stem and base.
    screen.pen = accent
    screen.shape(shape.rounded_rectangle(x + 4, y, 10, 18, 5))
    screen.shape(shape.arc(x + 9, y + 11, 7, 9, 90, 270))  # 0 is up, clockwise
    screen.shape(shape.rectangle(x + 8, y + 20, 2, 7))
    screen.shape(shape.rounded_rectangle(x + 3, y + 27, 12, 3, 1.5))
    screen.pen = black
    for row in (5, 9, 13):
        screen.shape(shape.rectangle(x + 6, y + row, 6, 1.5))


def centred_with_microphone(text, y, style, pen):
    w, h = measure(text, style)
    x = (WIDTH - (MIC_WIDTH + MIC_GAP + w)) // 2
    draw_microphone(x, y + (h - MIC_HEIGHT) // 2)
    draw_text(text, x + MIC_WIDTH + MIC_GAP, y, style, pen)


class Speaker:
    def __init__(self):
        self.page = 0
        self.after = False
        self.awake_until = badge.ticks + AWAKE_MS
        self.lit = None
        self.qr = None  # only the current page's code
        self.qr_url = None

    def awake(self):
        return badge.ticks < self.awake_until

    def pages(self):
        if not self.after:
            return PAGES
        by_label = {p[0]: p for p in PAGES}
        ordered = [by_label[label] for label in AFTER_ORDER]
        # Pages missing from AFTER_ORDER keep their place at the end.
        return ordered + [p for p in PAGES if p[0] not in AFTER_ORDER]

    def handle_input(self):
        if not badge.pressed():
            return
        was_awake = self.awake()
        self.awake_until = badge.ticks + AWAKE_MS
        # The first touch on a dimmed screen only brightens it.
        if not was_awake:
            return
        if badge.pressed(BUTTON_RIGHT) or badge.pressed(BUTTON_DOWN):
            self.page = (self.page + 1) % len(PAGES)
        if badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_UP):
            self.page = (self.page - 1) % len(PAGES)
        if badge.pressed(BUTTON_SELECT):
            # Switch between before and after the talk, back on the main screen.
            self.after = not self.after
            self.page = 0

    def set_light(self):
        level = AWAKE_BACKLIGHT if self.awake() else DIM_BACKLIGHT
        if level != self.lit:
            set_backlight(level)
            self.lit = level

    def update(self):
        self.handle_input()
        self.set_light()
        if not self.awake():
            time.sleep(DIM_FRAME_MS / 1000)
        screen.pen = black
        screen.clear()
        label, url, mona = self.pages()[self.page]
        if url is None:
            self.draw_talk()
        else:
            self.draw_qr(label, url, mona)
        self.draw_dots()

    def draw_talk(self):
        # Four blocks (conference, title, name, when) with equal gaps between them.
        small_h = measure("Ag", CONFERENCE_TEXT)[1]
        title_h = measure("Ag", TITLE_TEXT)[1]
        name_h = measure("Ag", NAME_TEXT)[1]
        used = small_h + len(TITLE) * title_h + (len(TITLE) - 1) * TITLE_GAP + name_h + small_h
        gap = (HEIGHT - 8 - used) // 3
        y = 4
        centred(CONFERENCE, y, CONFERENCE_TEXT, accent)
        y += small_h + gap
        for line in TITLE:
            centred(line, y, TITLE_TEXT, white)
            y += title_h + TITLE_GAP
        y += gap - TITLE_GAP
        centred_with_microphone(SPEAKER, y, NAME_TEXT, white)
        y += name_h + gap
        if self.after:
            centred(AFTER_TALK, y, CONFERENCE_TEXT, accent)
        else:
            centred(WHEN, y, WHEN_TEXT, dim)

    def draw_mona(self, name):
        # Mona holds still while dimmed to save power.
        frame = int(badge.ticks / MONA_FRAME_MS) % MONA_FRAMES[name] if self.awake() else 0
        sprite = monas[name].sprite(frame, 0)
        # Largest whole-number scale (up to 4x) that fits left of the QR code.
        scale = 4
        while scale > 1 and sprite.width * scale > QR_X - 4:
            scale -= 1
        w, h = sprite.width * scale, sprite.height * scale
        screen.blit(sprite, rect((QR_X - w) // 2, QR_Y + (QR_SIDE - h) // 2, w, h))

    def draw_qr(self, label, url, mona):
        if url != self.qr_url:
            self.qr = None  # free the old code before building the next
            self.qr = image.qr(url, image.QR_LOW, 1)
            self.qr_url = url
        # Every code fills the same box, whatever the URL length.
        screen.pen = white
        screen.rectangle(QR_X, QR_Y, QR_SIDE, QR_SIDE)
        inner = QR_SIDE - 2 * QR_MARGIN
        screen.blit(self.qr, rect(0, 0, self.qr.width, self.qr.height),
                    rect(QR_X + QR_MARGIN, QR_Y + QR_MARGIN, inner, inner))
        if mona:
            self.draw_mona(mona)
        w, _ = measure(label, LABEL_TEXT)
        draw_text(label, QR_X + (QR_SIDE - w) // 2, QR_Y + QR_SIDE + 6, LABEL_TEXT, white)

    def draw_dots(self):
        if len(PAGES) < 2:
            return  # nothing to page through
        for index in range(len(PAGES)):  # every order has the same number of pages
            screen.pen = white if index == self.page else dim
            screen.rectangle(WIDTH - 8, 80 + index * 16, 6 if index == self.page else 4, 8)


saved_backlight = get_backlight()
app = Speaker()
update = app.update


def on_exit():
    # Put back the brightness chosen in Settings.
    set_backlight(saved_backlight)


run(update)
