# Taste Stamp: a Creative Director's rubber stamp.
#
# Press DOWN to slam a verdict onto the brief.

import os
import random
import sys
from array import array

APP_DIRS = ("/remote/apps/taste_stamp", "/system/apps/taste_stamp", "/apps/taste_stamp", "/taste_stamp")


def find_app_dir():
    for path in APP_DIRS:
        try:
            if is_dir(path):
                return path
        except Exception:
            pass
    return APP_DIRS[1]


APP_DIR = find_app_dir()
try:
    os.chdir(APP_DIR)
except OSError:
    pass
sys.path.insert(0, APP_DIR)

import stamp  # noqa: E402
import verdicts  # noqa: E402

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2
screen.fill_rule = image.EVEN_ODD
W = screen.width
H = screen.height

UI_FONT = font.nope
SMALL_FONT = font.sins
screen.font = UI_FONT


def rgb(c, alpha=255):
    return color.rgb(c[0], c[1], c[2], alpha)


def lighten(c, amount):
    return (
        int(c[0] + (255 - c[0]) * amount),
        int(c[1] + (255 - c[1]) * amount),
        int(c[2] + (255 - c[2]) * amount),
    )


DESK = (13, 17, 23)
PAPER = (241, 236, 224)
STRIP = (232, 226, 212)
LINE_GREY = (212, 205, 190)
HEADING_GREY = (186, 178, 162)
PAPER_TEXT = (150, 142, 128)
WHITE = (240, 246, 252)
DIM = (139, 148, 158)

DESK_C = rgb(DESK)
PAPER_C = rgb(PAPER)
STRIP_C = rgb(STRIP)
LINE_C = rgb(LINE_GREY)
HEADING_C = rgb(HEADING_GREY)
PAPER_TEXT_C = rgb(PAPER_TEXT)
SHADOW_C = color.rgb(0, 0, 0, 110)
WHITE_C = rgb(WHITE)
DIM_C = rgb(DIM)
PILL_C = color.rgb(33, 38, 45, 235)

# Layout.
TITLE_Y = 4
PAPER_X = 14
PAPER_Y = 26
PAPER_W = W - 2 * PAPER_X
PAPER_H = 190
PAPER_CX = PAPER_X + PAPER_W // 2
PAPER_CY = PAPER_Y + PAPER_H // 2
STRIP_H = 20
TEXT_X = PAPER_X + 16
TEXT_W = PAPER_W - 32
BOTTOM_Y = PAPER_Y + PAPER_H + 6

# The brief under the stamps: bar widths as fractions of the text column.
# Negative values are headings and 0 is a paragraph gap.
BRIEF = (-0.42, 0.94, 0.88, 0.97, 0.52, 0, -0.3, 0.9, 0.96, 0.84, 0.6, 0, 0.91, 0.7)

INK_ALPHA = 225
STAMP_MAX_W = 220.0
STAMP_MAX_H = 136.0
STAMP_MAX_SCALE = 5.5

TOAST_MS = 1800


def text_width(text):
    width, _ = screen.measure_text(text)
    return width


def make_seed():
    seed = 0
    try:
        seed = random.getrandbits(32)
    except Exception:
        pass
    try:
        seed ^= int(badge.ticks) & 0xFFFFFFFF
    except Exception:
        pass
    return seed


rng = verdicts.Rng(make_seed())

# Stamp artwork is built once per verdict, lazily, as (outlines, width, height)
# in stamp units centred on the origin.
STAMPS = [None] * len(verdicts.VERDICTS)


def contour_shape(contours):
    return shape.custom(*[array("f", c) for c in contours])


def stamp_shapes(index):
    cached = STAMPS[index]
    if cached is None:
        groups, w, h = stamp.build_stamp(verdicts.VERDICTS[index], verdicts.STAMP_HEADER, verdicts.FOOTERS[index])
        outlines = []
        for group in groups:
            outlines.append(contour_shape(group))
        cached = (outlines, w, h)
        STAMPS[index] = cached
    return cached


def warm_stamps():
    # Builds at most one missing stamp per frame so the first slam is smooth.
    for i in range(len(STAMPS)):
        if STAMPS[i] is None:
            stamp_shapes(i)
            return


def draw_stamp(target, index, x, y, rot, scale, alpha):
    outlines, w, h = stamp_shapes(index)
    transform = mat3().translate(x, y).rotate(rot).scale(scale)
    target.pen = rgb(verdicts.INKS[index], alpha)
    target.fill_rule = image.NON_ZERO
    for s in outlines:
        s.transform = transform
        target.shape(s)
    target.fill_rule = image.EVEN_ODD


class Slam:
    # One stamp impression: it falls, lands and is then baked into the desk
    # image, where it stays as a mark.

    def __init__(self, index, now):
        outlines, w, h = stamp_shapes(index)
        self.index = index
        self.start = now
        self.scale = min(STAMP_MAX_W / w, STAMP_MAX_H / h, STAMP_MAX_SCALE)
        self.w = w
        self.h = h
        self.x = PAPER_CX + rng.uniform(-10.0, 10.0)
        self.y = PAPER_CY + rng.uniform(-6.0, 6.0)
        self.rot = rng.uniform(-10.0, 10.0)
        self.spin = rng.uniform(-stamp.DROP_SPIN, stamp.DROP_SPIN)
        self.inked = False


class App:
    def __init__(self):
        self.choice = None
        self.bag = verdicts.ShuffleBag(len(verdicts.VERDICTS), rng)
        self.slam = None
        self.marks = []
        self.desk = image(W, H)
        self.desk.antialias = image.X2
        # The brief's header is vector text, which needs EVEN_ODD.
        self.desk.fill_rule = image.EVEN_ODD
        self.toast_text = None
        self.toast_until = 0
        self.render_desk()

    # Frame loop.

    def update(self):
        now = badge.ticks
        if not self.handle_buttons(now):
            return False
        if self.slam is not None:
            self.advance_slam(now)
        self.draw_stamp_mode(now)
        self.draw_toast(now)
        if self.slam is None:
            warm_stamps()
        return None

    def handle_buttons(self, now):
        # Returns False when the app should exit.
        if badge.pressed(BUTTON_BACK):
            return False
        if badge.pressed(BUTTON_UP):
            self.cycle_choice(now)
        if badge.pressed(BUTTON_DOWN):
            self.start_slam(self.next_verdict(), now)
        return True

    # Modes and choices.

    def next_verdict(self):
        if self.choice is not None:
            return self.choice
        return self.bag.next()

    def cycle_choice(self, now):
        if self.choice is None:
            self.choice = 0
        elif self.choice + 1 < len(verdicts.VERDICTS):
            self.choice += 1
        else:
            self.choice = None
        self.toast("NEXT: " + self.choice_label(), now)

    def choice_label(self):
        if self.choice is None:
            return "RANDOM"
        return verdicts.VERDICTS[self.choice]

    def toast(self, text, now):
        self.toast_text = text
        self.toast_until = now + TOAST_MS

    # Stamp slams.

    def start_slam(self, index, now):
        self.finish_slam()
        self.slam = Slam(index, now)

    def advance_slam(self, now):
        s = self.slam
        t = now - s.start
        if not s.inked and t >= stamp.BAKE_MS:
            self.bake_stamp(s)
        if s.inked:
            self.slam = None

    def finish_slam(self):
        # Lands the current slam at once.
        s = self.slam
        if s is None:
            return
        if not s.inked:
            self.bake_stamp(s)
        self.slam = None

    def bake_stamp(self, s):
        s.inked = True
        self.marks.append(s)
        d = self.desk
        draw_stamp(d, s.index, s.x, s.y, s.rot, s.scale, INK_ALPHA)

    def render_desk(self):
        d = self.desk
        d.pen = DESK_C
        d.clear()
        d.pen = SHADOW_C
        d.shape(shape.rounded_rectangle(PAPER_X + 3, PAPER_Y + 4, PAPER_W, PAPER_H, 4))
        d.pen = PAPER_C
        d.shape(shape.rounded_rectangle(PAPER_X, PAPER_Y, PAPER_W, PAPER_H, 4))
        d.pen = STRIP_C
        d.shape(shape.rounded_rectangle(PAPER_X, PAPER_Y, PAPER_W, STRIP_H, 4))
        d.rectangle(PAPER_X, PAPER_Y + STRIP_H - 6, PAPER_W, 6)
        d.pen = LINE_C
        d.rectangle(PAPER_X, PAPER_Y + STRIP_H, PAPER_W, 1)
        d.font = SMALL_FONT
        d.pen = PAPER_TEXT_C
        d.text("creative-brief.md", PAPER_X + 8, PAPER_Y + 4)
        y = PAPER_Y + 30
        for v in BRIEF:
            if v < 0:
                d.pen = HEADING_C
                d.shape(shape.rounded_rectangle(TEXT_X, y - 1, -v * TEXT_W, 6, 2))
            elif v > 0:
                d.pen = LINE_C
                d.shape(shape.rounded_rectangle(TEXT_X, y, v * TEXT_W, 4, 2))
            y += 11

    # Drawing.

    def draw_stamp_mode(self, now):
        s = self.slam
        screen.blit(self.desk, vec2(0, 0))
        if s is None and not self.marks:
            self.draw_idle_box()
        if s is not None:
            t = now - s.start
            if not s.inked:
                self.draw_falling(s, t)
        self.draw_title("TASTE STAMP")
        screen.font = SMALL_FONT
        if self.choice is None:
            screen.pen = DIM_C
        else:
            screen.pen = rgb(lighten(verdicts.INKS[self.choice], 0.45))
        screen.text("NEXT: " + self.choice_label(), PAPER_X, BOTTOM_Y)
        screen.font = UI_FONT

    def draw_falling(self, s, t):
        k, wobble, alpha, landed = stamp.slam_pose(t)
        rot = s.rot + wobble * s.spin
        scale = s.scale * k
        if not landed:
            # The stamp block's shadow closes in as it drops.
            lift = (k - 1.0) * 10.0
            block = shape.rounded_rectangle(-s.w * 0.5, -s.h * 0.5, s.w, s.h, 2)
            block.transform = mat3().translate(s.x + lift, s.y + lift * 1.3).rotate(rot).scale(scale)
            screen.pen = color.rgb(0, 0, 0, 50)
            screen.shape(block)
        draw_stamp(screen, s.index, s.x, s.y, rot, scale, min(alpha, INK_ALPHA))

    def draw_idle_box(self):
        bw = 214
        bh = 56
        x = PAPER_CX - bw // 2
        y = PAPER_CY - bh // 2
        screen.pen = PAPER_C
        screen.shape(shape.rounded_rectangle(x, y, bw, bh, 6))
        screen.pen = HEADING_C
        screen.shape(shape.rounded_rectangle(x, y, bw, bh, 6).stroke(1.5))
        screen.font = UI_FONT
        self.centred("PRESS DOWN TO STAMP", y + 21, PAPER_TEXT_C)

    def draw_title(self, title):
        screen.font = UI_FONT
        screen.pen = WHITE_C
        screen.text(title, 10, TITLE_Y)

    def centred(self, text, y, pen):
        screen.pen = pen
        screen.text(text, (W - text_width(text)) // 2, y)

    def draw_toast(self, now):
        if self.toast_text is None:
            return
        if now >= self.toast_until:
            self.toast_text = None
            return
        screen.font = SMALL_FONT
        w = text_width(self.toast_text) + 20
        x = (W - w) // 2
        screen.pen = PILL_C
        screen.shape(shape.rounded_rectangle(x, 28, w, 20, 10))
        screen.pen = WHITE_C
        screen.text(self.toast_text, x + 10, 32)
        screen.font = UI_FONT


app = App()


def update():
    return app.update()


run(update)
