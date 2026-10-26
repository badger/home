# Taste Stamp: a Creative Director's rubber stamp and a Creative 8-Ball.
#
# Stamp mode: flip the badge over, karate-chop it or press DOWN to slam a
# verdict onto the brief, with screen shake and a case-light strobe.
# 8-Ball mode: shake the badge (or press DOWN) to tumble a dithered d20 that
# lands on a Studio creative direction.
# SELECT beams the verdict or prompt over IR to nearby badges that are
# running Taste Stamp.

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

# The helpers have generic names, so drop copies another app may have left
# in sys.modules before importing this app's own.
HELPERS = ("beam", "eightball", "motion", "stamp", "verdicts")


def forget_helpers():
    for name in HELPERS:
        if name in sys.modules:
            del sys.modules[name]


forget_helpers()

import beam  # noqa: E402
import eightball  # noqa: E402
import motion  # noqa: E402
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
BLUE = (88, 166, 255)

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
CARD_C = color.rgb(22, 27, 34)
CARD_EDGE_C = color.rgb(48, 54, 61)
EDGE_C = color.rgb(150, 200, 255, 160)

# Stamp mode layout.
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
# Older impressions fade as new ones land on the same sheet.
FADES = (150, 95, 55)
SPLATS = 14
SPECKS = 90
STAMP_MAX_W = 220.0
STAMP_MAX_H = 136.0
STAMP_MAX_SCALE = 5.5
MOTION_COOLDOWN_MS = 650

# 8-Ball layout.
BALL_X = W // 2
BALL_Y = 100
BALL_R = 76
WINDOW_R = 57
LIQUID_R = 54
D20_SCALE = 24
CARD_X = 16
CARD_Y = 180
CARD_W = W - 2 * CARD_X
CARD_H = 56
REVEAL_MS = 18
NUMBER_SCALE = 0.078
NUMBER_HW = 0.065
GLOW_MS = 400

TOAST_MS = 1800
STAMP_HINT = "STAMP SOMETHING FIRST"
SPIN_HINT = "SHAKE TO SPIN FIRST"
LAND_HINT = "LET IT LAND FIRST"
HINTS = (STAMP_HINT, SPIN_HINT, LAND_HINT)
RING_COUNT = 3
RING_GAP_MS = 140
RING_MS = 560

STAMP_MODE = 0
BALL_MODE = 1


def screen_like_image():
    # Match the screen's pixel format, as brattal does, so blits are copies.
    try:
        if len(screen.raw) == W * H * 2:
            return image(W, H, bytearray(W * H * 2), image.RGB565)
    except Exception:
        pass
    return image(W, H)


def read_imu():
    try:
        values = badge.imu()
        if len(values) >= 6:
            return values
    except Exception:
        pass
    return None


def read_upside_down():
    try:
        return bool(badge.upside_down())
    except Exception:
        return False


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
    # One stamp impression: it falls, lands, flings ink and is then baked
    # into the desk image, where it stays as a mark.

    def __init__(self, index, now):
        outlines, w, h = stamp_shapes(index)
        self.index = index
        self.start = now
        self.scale = min(STAMP_MAX_W / w, STAMP_MAX_H / h, STAMP_MAX_SCALE)
        self.w = w
        self.h = h
        self.half_w = w * self.scale * 0.5
        self.half_h = h * self.scale * 0.5
        self.x = PAPER_CX + rng.uniform(-10.0, 10.0)
        self.y = PAPER_CY + rng.uniform(-6.0, 6.0)
        self.rot = rng.uniform(-10.0, 10.0)
        self.spin = rng.uniform(-stamp.DROP_SPIN, stamp.DROP_SPIN)
        self.phase = rng.uniform(0.0, 6.28)
        self.seed = rng.next_u32()
        self.splats = None
        self.dots = []
        self.specks = None
        self.inked = False
        self.dried = False


def specks_for(mark):
    # Paper-coloured flecks knocked out of the ink, in stamp units, so they
    # follow the stamp's own transform.
    if mark.specks is None:
        r = verdicts.Rng(mark.seed)
        contours = []
        for _ in range(SPECKS):
            x = r.uniform(-0.5 * mark.w, 0.5 * mark.w)
            y = r.uniform(-0.5 * mark.h, 0.5 * mark.h)
            s = r.uniform(0.12, 0.42)
            contours.append([x, y - s, x + s, y, x, y + s, x - s, y])
        mark.specks = contour_shape(contours)
    return mark.specks


def draw_mark(target, mark, alpha):
    draw_stamp(target, mark.index, mark.x, mark.y, mark.rot, mark.scale, alpha)
    specks = specks_for(mark)
    specks.transform = mat3().translate(mark.x, mark.y).rotate(mark.rot).scale(mark.scale)
    target.pen = rgb(PAPER, alpha * 190 // INK_ALPHA)
    target.fill_rule = image.NON_ZERO
    target.shape(specks)
    target.fill_rule = image.EVEN_ODD
    if mark.dots:
        target.pen = rgb(verdicts.INKS[mark.index], alpha)
        for d in mark.dots:
            target.shape(shape.circle(d[0], d[1], d[2]))


def number_shape(n):
    # A d20 face number as one shape in (s, t) face coordinates, built once;
    # each frame only sets its transform. 6 and 9 get a dot like real dice.
    text = str(n)
    if n == 6 or n == 9:
        text += "."
    groups = []
    stamp.text_groups(text, 0.0, -stamp.CAP * NUMBER_SCALE * 0.5, NUMBER_SCALE, NUMBER_HW, groups)
    flat = []
    for group in groups:
        for contour in group:
            flat.append(contour)
    return contour_shape(eightball.to_face_uv(flat))


NUMBER_SHAPES = [None]
for _n in range(1, 21):
    NUMBER_SHAPES.append(number_shape(_n))


def place_number(n, top, left, right):
    tx, ty, phi, sx, sy, theta = eightball.affine_parts(top, left, right)
    s = NUMBER_SHAPES[n]
    s.transform = mat3().translate(tx, ty).rotate(phi).scale(sx, sy).rotate(theta)
    return s


# One reused buffer for the d20's triangles; each is drawn before the next
# is written.
FACE_POINTS = array("f", [0.0] * 6)

# Two-colour ordered dithers make a 17-step ramp from navy to GitHub blue.
SHADE_DARK = color.rgb(10, 14, 46)
SHADE_MID = color.rgb(30, 62, 160)
SHADE_LIGHT = rgb(BLUE)
SHADES = []
for _level in range(eightball.LEVELS + 1):
    if _level <= 8:
        SHADES.append(brush.pattern(SHADE_MID, SHADE_DARK, eightball.bayer_rows(2 * _level)))
    else:
        SHADES.append(brush.pattern(SHADE_LIGHT, SHADE_MID, eightball.bayer_rows(2 * (_level - 8))))


def build_ball_bg():
    g = screen_like_image()
    g.antialias = image.X2
    g.pen = DESK_C
    g.clear()
    g.pen = color.rgb(88, 166, 255, 14)
    g.shape(shape.circle(BALL_X, BALL_Y, BALL_R + 10))
    g.pen = color.rgb(88, 166, 255, 10)
    g.shape(shape.circle(BALL_X, BALL_Y, BALL_R + 5))
    g.pen = color.rgb(10, 12, 16)
    g.shape(shape.circle(BALL_X, BALL_Y, BALL_R))
    # Stacked faint circles drifting up and left make a soft highlight.
    for i in range(6):
        g.pen = color.rgb(255, 255, 255, 7)
        g.shape(shape.circle(BALL_X - 28 * i / 5.0, BALL_Y - 30 * i / 5.0, BALL_R - 9 * i))
    g.pen = color.rgb(255, 255, 255, 70)
    g.shape(shape.circle(BALL_X - 40, BALL_Y - 44, 7))
    g.pen = color.rgb(48, 54, 61)
    g.shape(shape.circle(BALL_X, BALL_Y, WINDOW_R))
    g.pen = color.rgb(6, 10, 30)
    g.shape(shape.circle(BALL_X, BALL_Y, LIQUID_R))
    g.pen = color.rgb(30, 62, 160, 30)
    g.shape(shape.circle(BALL_X, BALL_Y, 44))
    g.pen = color.rgb(30, 62, 160, 24)
    g.shape(shape.circle(BALL_X, BALL_Y, 30))
    return g


# Shapes that never move are built once rather than every frame.
CARD = shape.rounded_rectangle(CARD_X, CARD_Y, CARD_W, CARD_H, 8)
CARD_EDGE = shape.rounded_rectangle(CARD_X, CARD_Y, CARD_W, CARD_H, 8).stroke(1)
GLINT = shape.circle(BALL_X - 22, BALL_Y - 25, 10)
GLINT_C = color.rgb(255, 255, 255, 26)


def set_lights(levels):
    try:
        if levels is None:
            badge.caselights(0)
        else:
            badge.caselights(levels[0], levels[1], levels[2], levels[3])
    except Exception:
        pass


class App:
    def __init__(self):
        self.mode = STAMP_MODE
        self.choice = None
        self.bag = verdicts.ShuffleBag(len(verdicts.VERDICTS), rng)
        self.slam = None
        self.marks = []
        self.last_verdict = None
        self.desk = screen_like_image()
        self.desk.antialias = image.X2
        # The brief's header is vector text, which needs EVEN_ODD.
        self.desk.fill_rule = image.EVEN_ODD
        self.ball_bg = None
        self.ball = eightball.Ball(rng.random)
        self.prompt = None
        self.flip = motion.FlipDetector(read_upside_down())
        self.chop = motion.ChopDetector()
        self.shake = motion.ShakeDetector()
        self.was_shaking = False
        self.last_motion = None
        self.toast_text = None
        self.toast_until = 0
        self.fx_start = None
        self.fx_incoming = False
        self.glow_start = None
        self.lights = None
        self.link = beam.Beam(len(verdicts.VERDICTS), len(verdicts.PROMPTS), beam.make_sender())
        self.link.receiving = beam.listen(self.link.heard)
        self.render_desk()

    # Frame loop.

    def update(self):
        now = badge.ticks
        dt = max(0, min(100, badge.ticks_delta))
        flipped = self.flip.update(read_upside_down(), now)
        chopped = False
        shaking = False
        reversal = False
        imu = read_imu()
        if imu is not None:
            chopped = self.chop.update(imu, dt, now)
            shaking = self.shake.update(imu, dt, now)
            reversal = self.shake.reversed
        if not self.handle_buttons(now):
            on_exit()
            return False
        self.handle_motion(now, flipped, chopped, shaking, reversal)
        self.handle_ir(now)
        if self.slam is not None:
            self.advance_slam(now, dt)
        if self.mode == BALL_MODE and self.ball.update(dt, now, shaking):
            self.landed(now)
        if self.mode == STAMP_MODE:
            self.draw_stamp_mode(now)
        else:
            self.draw_ball_mode(now)
        self.draw_beam_fx(now)
        self.draw_toast(now)
        self.update_lights(now)
        if self.slam is None:
            warm_stamps()
        return None

    def handle_buttons(self, now):
        # Returns False when the app should exit.
        if badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_RIGHT):
            self.switch_mode(BALL_MODE if self.mode == STAMP_MODE else STAMP_MODE)
        if badge.pressed(BUTTON_BACK):
            return self.back(now)
        if self.mode == STAMP_MODE:
            if badge.pressed(BUTTON_UP):
                self.cycle_choice(now)
            if badge.pressed(BUTTON_DOWN):
                self.start_slam(self.next_verdict(), now)
            if badge.pressed(BUTTON_SELECT):
                self.beam_verdict(now)
        else:
            if badge.pressed(BUTTON_DOWN) or badge.pressed(BUTTON_UP):
                self.kick(18, now)
            if badge.pressed(BUTTON_SELECT):
                self.beam_prompt(now)
        return True

    def back(self, now):
        if self.mode == STAMP_MODE:
            if self.slam is not None or self.marks:
                self.finish_slam()
                self.marks = []
                self.last_verdict = None
                self.render_desk()
                self.toast("FRESH PAPER", now)
                return True
            return False
        if self.ball.state != eightball.IDLE:
            self.ball.reset()
            self.prompt = None
            return True
        return False

    def handle_motion(self, now, flipped, chopped, shaking, reversal):
        if self.mode == STAMP_MODE:
            if flipped or chopped:
                # One physical move can read as both a flip and a chop.
                if self.last_motion is None or now - self.last_motion >= MOTION_COOLDOWN_MS:
                    self.last_motion = now
                    self.start_slam(self.next_verdict(), now)
        else:
            if flipped:
                self.kick(16, now)
            if shaking and not self.was_shaking:
                self.kick(14, now)
            elif reversal:
                self.kick(5, now)
        self.was_shaking = shaking

    def handle_ir(self, now):
        if not self.link.pump(now):
            self.toast("IR SEND FAILED", now)
        message = self.link.receive(now)
        if message is None:
            return
        kind, index = message
        if kind == beam.VERDICT:
            self.switch_mode(STAMP_MODE)
            self.start_slam(index, now)
            self.toast("FROM A NEARBY BADGE", now)
        else:
            self.switch_mode(BALL_MODE)
            self.kick(16, now, index + 1)
            self.toast("INCOMING PROMPT", now)
        self.fx_start = now
        self.fx_incoming = True

    # Modes and choices.

    def switch_mode(self, mode):
        if mode == self.mode:
            return
        if self.mode == STAMP_MODE:
            self.finish_slam()
        self.mode = mode
        if mode == BALL_MODE and self.ball_bg is None:
            self.ball_bg = build_ball_bg()

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

    def kick(self, strength, now, forced=None):
        self.ball.kick(strength, now, forced)
        self.prompt = None
        self.drop_hint()

    def toast(self, text, now):
        self.toast_text = text
        self.toast_until = now + TOAST_MS

    def drop_hint(self):
        # A "do this first" hint is stale once the user has done it.
        if self.toast_text in HINTS:
            self.toast_text = None

    # Beaming.

    def beam_verdict(self, now):
        if self.last_verdict is None:
            self.toast(STAMP_HINT, now)
            return
        self.send_beam(beam.VERDICT, self.last_verdict, now)

    def beam_prompt(self, now):
        number = self.ball.number()
        if self.ball.state != eightball.LANDED or number is None:
            self.toast(SPIN_HINT if self.ball.state == eightball.IDLE else LAND_HINT, now)
            return
        self.send_beam(beam.PROMPT, number - 1, now)

    def send_beam(self, kind, index, now):
        if self.link.busy():
            self.toast("STILL BEAMING", now)
            return
        if self.link.send(kind, index, now):
            self.toast("BEAMING TO NEARBY BADGES", now)
        else:
            self.toast("NO IR HERE: BEAM SIMULATED", now)
        self.fx_start = now
        self.fx_incoming = False

    # Stamp slams.

    def start_slam(self, index, now):
        self.finish_slam()
        while len(self.marks) > len(FADES):
            self.marks.pop(0)
        if self.marks:
            self.render_desk()
        self.slam = Slam(index, now)
        self.last_verdict = index
        self.drop_hint()

    def advance_slam(self, now, dt):
        s = self.slam
        t = now - s.start
        if s.splats is None:
            if t >= stamp.DROP_MS:
                s.splats = stamp.make_splats(rng.random, SPLATS, s.x, s.y, s.half_w, s.half_h)
                stamp.step_splats(s.splats, t - stamp.DROP_MS)
        elif not s.dried:
            stamp.step_splats(s.splats, dt)
        if not s.inked and t >= stamp.BAKE_MS:
            self.bake_stamp(s)
        if not s.dried and s.splats is not None and t >= stamp.DROP_MS + stamp.SPLAT_MS:
            self.bake_splats(s)
        if s.inked and s.dried and t >= stamp.DROP_MS + stamp.STROBE_MS:
            self.slam = None

    def finish_slam(self):
        # Lands the current slam at once, ink and splats included.
        s = self.slam
        if s is None:
            return
        if s.splats is None:
            s.splats = stamp.make_splats(rng.random, SPLATS, s.x, s.y, s.half_w, s.half_h)
        if not s.dried:
            stamp.step_splats(s.splats, 2000)
        if not s.inked:
            self.bake_stamp(s)
        if not s.dried:
            self.bake_splats(s)
        self.slam = None

    def bake_stamp(self, s):
        s.inked = True
        self.marks.append(s)
        d = self.desk
        draw_stamp(d, s.index, s.x, s.y, s.rot, s.scale, INK_ALPHA)
        specks = specks_for(s)
        specks.transform = mat3().translate(s.x, s.y).rotate(s.rot).scale(s.scale)
        d.pen = rgb(PAPER, 190)
        d.fill_rule = image.NON_ZERO
        d.shape(specks)
        d.fill_rule = image.EVEN_ODD

    def bake_splats(self, s):
        s.dried = True
        dots = []
        for p in s.splats:
            dots.append((p[0], p[1], p[4]))
        s.dots = dots
        self.desk.pen = rgb(verdicts.INKS[s.index], INK_ALPHA)
        for d in dots:
            self.desk.shape(shape.circle(d[0], d[1], d[2]))

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
        n = len(self.marks)
        for i in range(n):
            age = n - 1 - i
            if age < len(FADES):
                draw_mark(d, self.marks[i], FADES[age])

    # Drawing.

    def draw_stamp_mode(self, now):
        s = self.slam
        ox = 0
        oy = 0
        if s is not None:
            dx, dy = stamp.shake_offset(now - s.start - stamp.DROP_MS, s.phase)
            ox = int(round(dx))
            oy = int(round(dy))
        if ox or oy:
            screen.pen = DESK_C
            screen.clear()
        screen.blit(self.desk, vec2(ox, oy))
        if s is None and not self.marks:
            self.draw_idle_box()
        if s is not None:
            t = now - s.start
            if not s.inked:
                self.draw_falling(s, t, ox, oy)
            if s.splats is not None and not s.dried:
                screen.pen = rgb(verdicts.INKS[s.index], INK_ALPHA)
                for p in s.splats:
                    screen.shape(shape.circle(p[0] + ox, p[1] + oy, p[4]))
        self.draw_title("TASTE STAMP", "< 8-BALL >")
        screen.font = SMALL_FONT
        if self.choice is None:
            screen.pen = DIM_C
        else:
            screen.pen = rgb(lighten(verdicts.INKS[self.choice], 0.45))
        screen.text("NEXT: " + self.choice_label(), PAPER_X, BOTTOM_Y)
        if self.last_verdict is not None:
            hint = "SELECT: BEAM"
            screen.pen = DIM_C
            screen.text(hint, W - PAPER_X - text_width(hint), BOTTOM_Y)
        screen.font = UI_FONT

    def draw_falling(self, s, t, ox, oy):
        k, wobble, alpha, landed = stamp.slam_pose(t)
        rot = s.rot + wobble * s.spin
        scale = s.scale * k
        if not landed:
            # The stamp block's shadow closes in as it drops.
            lift = (k - 1.0) * 10.0
            block = shape.rounded_rectangle(-s.w * 0.5, -s.h * 0.5, s.w, s.h, 2)
            block.transform = mat3().translate(s.x + ox + lift, s.y + oy + lift * 1.3).rotate(rot).scale(scale)
            screen.pen = color.rgb(0, 0, 0, 50)
            screen.shape(block)
        draw_stamp(screen, s.index, s.x + ox, s.y + oy, rot, scale, min(alpha, INK_ALPHA))

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
        self.centred("FLIP OR CHOP TO STAMP", y + 12, PAPER_TEXT_C)
        screen.font = SMALL_FONT
        self.centred("OR PRESS DOWN", y + 32, PAPER_TEXT_C)
        screen.font = UI_FONT

    def draw_title(self, title, hint):
        screen.font = UI_FONT
        screen.pen = WHITE_C
        screen.text(title, 10, TITLE_Y)
        screen.font = SMALL_FONT
        screen.pen = DIM_C
        screen.text(hint, W - 10 - text_width(hint), TITLE_Y + 2)
        screen.font = UI_FONT

    def centred(self, text, y, pen):
        screen.pen = pen
        screen.text(text, (W - text_width(text)) // 2, y)

    def landed(self, now):
        self.prompt = self.build_prompt(verdicts.PROMPTS[self.ball.number() - 1])
        self.glow_start = now
        self.drop_hint()

    def build_prompt(self, text):
        lines = stamp.wrap(text, 14)
        widest = 1.0
        for line in lines:
            widest = max(widest, stamp.line_width(line))
        scale = min(1.9, (CARD_W - 24) / widest)
        hw = stamp.STROKE * 0.5 * scale * 0.85
        pitch = stamp.LINE_PITCH * scale
        block = stamp.CAP * scale + (len(lines) - 1) * pitch
        top = CARD_Y + 21 - block * 0.5
        groups = []
        for i in range(len(lines)):
            stamp.text_groups(lines[i], W * 0.5, top + i * pitch, scale, hw, groups)
        outlines = []
        for group in groups:
            outlines.append(contour_shape(group))
        return outlines

    def draw_ball_mode(self, now):
        if self.ball_bg is None:
            self.ball_bg = build_ball_bg()
        screen.blit(self.ball_bg, vec2(0, 0))
        ball = self.ball
        points, visible = ball.project(BALL_X, BALL_Y, D20_SCALE)
        faces = ball.faces
        buf = FACE_POINTS
        shown = bytearray(len(faces))
        for f, level, nz in visible:
            shown[f] = 1
            face = faces[f]
            a = points[face[0]]
            b = points[face[1]]
            c = points[face[2]]
            buf[0] = a[0]
            buf[1] = a[1]
            buf[2] = b[0]
            buf[3] = b[1]
            buf[4] = c[0]
            buf[5] = c[1]
            screen.pen = SHADES[level]
            screen.shape(shape.custom(buf))
        screen.pen = EDGE_C
        for i, j, f, g in ball.edges:
            if shown[f] or shown[g]:
                p = points[i]
                q = points[j]
                screen.shape(shape.line(p[0], p[1], q[0], q[1], 1.3))
        if ball.speed() < eightball.BLUR_SPEED or ball.state == eightball.SETTLING or ball.state == eightball.LANDED:
            screen.fill_rule = image.NON_ZERO
            for f, level, nz in visible:
                if nz <= 0.3:
                    continue
                face = faces[f]
                screen.pen = rgb(WHITE, min(255, int((nz - 0.3) * 637.5)))
                screen.shape(place_number(ball.numbers[f], points[face[0]], points[face[1]], points[face[2]]))
            screen.fill_rule = image.EVEN_ODD
        screen.pen = GLINT_C
        screen.shape(GLINT)
        self.draw_card(now)
        self.draw_title("CREATIVE 8-BALL", "< STAMP >")

    def draw_card(self, now):
        screen.pen = CARD_C
        screen.shape(CARD)
        screen.pen = CARD_EDGE_C
        screen.shape(CARD_EDGE)
        state = self.ball.state
        if state == eightball.LANDED and self.prompt is not None:
            shown = (now - self.ball.landed_at) // REVEAL_MS + 1
            screen.pen = WHITE_C
            screen.fill_rule = image.NON_ZERO
            for i in range(min(shown, len(self.prompt))):
                screen.shape(self.prompt[i])
            screen.fill_rule = image.EVEN_ODD
            screen.font = SMALL_FONT
            self.centred("SELECT: BEAM IT", CARD_Y + CARD_H - 15, DIM_C)
            screen.font = UI_FONT
        elif state == eightball.IDLE:
            screen.font = UI_FONT
            self.centred("SHAKE FOR A CREATIVE DIRECTION", CARD_Y + 12, WHITE_C)
            screen.font = SMALL_FONT
            self.centred("OR PRESS DOWN", CARD_Y + 32, DIM_C)
            screen.font = UI_FONT
        else:
            base = "CONSULTING THE STUDIO"
            screen.font = UI_FONT
            x = (W - text_width(base + "...")) // 2
            screen.pen = WHITE_C
            screen.text(base + "." * (1 + (now // 300) % 3), x, CARD_Y + 21)

    def draw_beam_fx(self, now):
        if self.fx_start is None:
            return
        t = now - self.fx_start
        if t >= RING_GAP_MS * (RING_COUNT - 1) + RING_MS:
            self.fx_start = None
            return
        for i in range(RING_COUNT):
            u = t - i * RING_GAP_MS
            if u < 0 or u >= RING_MS:
                continue
            p = u / RING_MS
            if self.fx_incoming:
                r = 160.0 - 150.0 * p
            else:
                r = 10.0 + 150.0 * p
            screen.pen = rgb(BLUE, int(200 * (1.0 - p)))
            screen.shape(shape.circle(W // 2, -6, r).stroke(2))

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

    def update_lights(self, now):
        levels = None
        if self.slam is not None:
            levels = stamp.strobe_levels(now - self.slam.start - stamp.DROP_MS)
        if self.fx_start is not None:
            chase = beam.lights(now - self.fx_start)
            if chase is not None:
                levels = chase
        if levels is None and self.glow_start is not None:
            t = now - self.glow_start
            if t < GLOW_MS:
                v = 0.5 * (1.0 - t / GLOW_MS)
                levels = (v, v, v, v)
            else:
                self.glow_start = None
        if levels != self.lights:
            self.lights = levels
            set_lights(levels)


previous_clear = badge.default_clear
# Every frame blits a full-screen image, so the firmware's clear is wasted.
badge.default_clear = None
app = App()


def update():
    return app.update()


def on_exit():
    set_lights(None)
    try:
        app.link.close()
    except Exception:
        pass
    try:
        badge.default_clear = previous_clear
    except Exception:
        pass
    forget_helpers()


run(update)
