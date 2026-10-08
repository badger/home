APP_DIR = "/system/apps/brattal"

import os
import random
import sys

os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

import brand

badge.mode(HIRES | VSYNC)
badge.autorotate(False)

screen.antialias = image.OFF

WIDTH = screen.width
HEIGHT = screen.height

SOIL = color.rgb(46, 32, 24)
SOIL_DARK = color.rgb(34, 24, 18)
DUST = color.rgb(62, 44, 31)
CRATER = color.rgb(26, 18, 14)
GRIME = color.rgb(18, 12, 10)
STEEL = brand.LIGHT_GREY
PLATE = brand.LIGHT_GREY
CHALK = brand.GREY_0
DIM = color.rgb(96, 78, 64)
RUST = color.rgb(168, 88, 38)
RUST_DARK = color.rgb(112, 56, 26)
SPARK = color.rgb(255, 216, 128)
EMBER = brand.ORANGE_2
GREEN = brand.GREEN_1
DEEP_GREEN = brand.GREEN_3
VEIL = color.rgb(10, 6, 4, 170)

HUD_FONT = font.smart
HINT_FONT = font.smart
SHOUT_FONT = font.sins
TITLE_FONT = font.more

HUD_H = 20
BAND_H = 84
DIVIDER_H = HEIGHT - HUD_H * 2 - BAND_H * 2

TOP_BAND = (HUD_H, HUD_H + BAND_H)
BOTTOM_BAND = (HEIGHT - HUD_H - BAND_H, HEIGHT - HUD_H)
DIVIDER = (TOP_BAND[1], BOTTOM_BAND[0])

RIG_W = 16
RIG_H = 13
SPEED = 2.05
SHOT_SPEED = 4.4
SHOT_W = 3
SHOT_H = 7
RELOAD_MS = 250
START_SCRAP = 6

BARRIER_ROWS = 2
BARRIER_COLS = 13
BARRIER_W = 18
BARRIER_H = 7
BARRIER_GAP = 5
BARRIER_HP = 3

DIN_MAX = 260
SHAKE_DECAY = 0.86
LIGHT_MAX = 0.35
LIGHT_EASE = 0.04

BOT_FIRE_CHANCE = 0.06
BOT_DODGE_RANGE = 46
BOT_AIM_SPREAD = 24
BOT_ALERTNESS = 0.5
OVER_HOLD_MS = 1200

WORDS = ("CLANG", "CLATTER", "RACKET", "DIN", "CRASH", "RATTLE", "BANG", "SKREEK")
CALLOUTS = ("RACKET!", "SCRAPPED!")

MARGIN = 12
MAX_CHUNKS = 90

DOT_RADIUS = 7
DOT_SPACING = DOT_RADIUS * 2 + 6
DPAD_OFFSET = (DOT_RADIUS * 2 + 3) / 1.4142

PAD_FIRE = (BUTTON_SELECT, BUTTON_BACK)
BUTTON_FIRE = (BUTTON_SELECT,)


def on_screen(x, y, w=0, h=0):
    return -w - MARGIN <= x <= WIDTH + MARGIN and -h - MARGIN <= y <= HEIGHT + MARGIN


class Phase:
    ATTRACT = 0
    FIGHT = 1
    OVER = 2


class Label:
    def __init__(self, text, typeface, pen, scale=1, layers=(), both_ways=True):
        screen.font = typeface
        text_w, text_h = screen.measure_text(text)
        border = max([max(abs(dx), abs(dy)) for dx, dy, _pen in layers] + [0])
        self.width = int(text_w * scale) + border * 2
        self.height = int(text_h * scale) + border * 2
        strokes = tuple(layers) + ((0, 0, pen),)
        self.upright = self.render(text, typeface, scale, border, strokes, False)
        self.flipped = self.render(text, typeface, scale, border, strokes, True) if both_ways else None

    def render(self, text, typeface, scale, border, strokes, flipped):
        canvas = image(self.width, self.height)
        canvas.antialias = image.OFF
        canvas.font = typeface
        for dx, dy, pen in strokes:
            transform = mat3()
            if flipped:
                transform.translate(vec2(self.width, self.height)).rotate(180)
            transform.translate(vec2(border + dx, border + dy)).scale(scale, scale)
            canvas.pen = pen
            canvas.text(text, vec2(0, 0), transform=transform)
        return canvas


class View:
    def __init__(self, flipped):
        self.flipped = flipped

    def rect(self, x, y, w, h):
        if self.flipped:
            x = WIDTH - x - w
            y = HEIGHT - y - h
        screen.rectangle(x, y, w, h)

    def circle(self, x, y, radius):
        if self.flipped:
            x = WIDTH - x
            y = HEIGHT - y
        screen.circle(vec2(x, y), radius)

    def point(self, x, y):
        return vec2(WIDTH - x, HEIGHT - y) if self.flipped else vec2(x, y)

    def triangle(self, a, b, c):
        screen.triangle(self.point(*a), self.point(*b), self.point(*c))

    def label(self, label, x, y):
        if self.flipped:
            screen.blit(label.flipped, vec2(WIDTH - x - label.width, HEIGHT - y - label.height))
        else:
            screen.blit(label.upright, vec2(x, y))

    def centred(self, label, y, cx=WIDTH / 2):
        self.label(label, cx - label.width / 2, y)


def shout_label(text, pen):
    return Label(text, SHOUT_FONT, pen, layers=((1, 1, GRIME),))


SHOUTS = {word: (shout_label(word, SPARK), shout_label(word, EMBER)) for word in WORDS + CALLOUTS}

TITLE = Label("BRATTAL", TITLE_FONT, SPARK, 3, (
    (-3, 0, GRIME), (3, 0, GRIME), (0, -3, GRIME), (0, 3, GRIME),
    (6, 6, GRIME), (3, 3, RUST),
), both_ways=False)

MOVE_LABEL = Label("MOVE", HINT_FONT, CHALK)
START_LABEL = Label("SHOOT TO START", HINT_FONT, SPARK)
AGAIN_LABEL = Label("SHOOT TO GO AGAIN", HINT_FONT, SPARK)
RACKET_LABEL = Label("RACKET", HUD_FONT, DIM)
WIN_LABEL = Label("YOU WIN", TITLE_FONT, SPARK, 2, ((3, 3, GRIME), (2, 2, RUST)))
LOSE_LABEL = Label("SCRAPPED", TITLE_FONT, EMBER, 2, ((3, 3, GRIME), (2, 2, RUST_DARK)))


PIXEL_BYTES = len(screen.raw) // (WIDTH * HEIGHT)


def screen_like_image():
    if PIXEL_BYTES == 2:
        return image(WIDTH, HEIGHT, bytearray(WIDTH * HEIGHT * 2), image.RGB565)
    return image(WIDTH, HEIGHT)


def build_ground():
    ground = screen_like_image()
    ground.antialias = image.OFF

    ground.pen = brush.pattern(SOIL, DUST, 20)
    ground.rectangle(0, 0, WIDTH, HEIGHT)

    ground.pen = brush.pattern(SOIL_DARK, SOIL, 23)
    ground.rectangle(0, DIVIDER[0], WIDTH, DIVIDER_H)

    for _ in range(9):
        x = random.randint(10, WIDTH - 10)
        y = random.randint(HUD_H + 8, HEIGHT - HUD_H - 8)
        radius = random.randint(5, 13)
        ground.pen = brush.pattern(CRATER, SOIL_DARK, 9)
        ground.circle(vec2(x, y), radius)
        ground.pen = brush.pattern(SOIL_DARK, DUST, 1)
        ground.circle(vec2(x - 1, y - 1), max(2, radius - 4))

    for _ in range(26):
        ground.pen = DUST if random.random() < 0.6 else RUST_DARK
        ground.rectangle(random.randint(0, WIDTH), random.randint(HUD_H, HEIGHT - HUD_H), random.randint(1, 3), random.randint(1, 2))

    for edge, pen in ((TOP_BAND[1] - 1, DEEP_GREEN), (BOTTOM_BAND[0], RUST_DARK)):
        ground.pen = pen
        for x in range(0, WIDTH, 8):
            ground.rectangle(x, edge, 5, 1)

    return ground


FIELD = rect(0, HUD_H, WIDTH, HEIGHT - HUD_H * 2)
SCREEN = rect(0, 0, WIDTH, HEIGHT)
FIELD_START = HUD_H * WIDTH * PIXEL_BYTES
FIELD_END = (HEIGHT - HUD_H) * WIDTH * PIXEL_BYTES
GROUND = memoryview(build_ground().raw)[FIELD_START:FIELD_END]
BARRIER_BRUSH = brush.pattern(RUST, RUST_DARK, 11)
WORN_BRUSH = brush.pattern(EMBER, RUST_DARK, 11)


class Human:
    def __init__(self, controls, fire):
        self.controls = controls
        self.fire = fire
        self.rig = None
        self.arena = None

    def steer(self):
        return self.controls.direction()

    def trigger(self):
        for action in self.fire:
            if self.controls.held(action):
                return True
        return False


class Bot:
    def __init__(self):
        self.target = vec2(WIDTH / 2, 0)
        self.retarget_at = 0
        self.alert = False
        self.rig = None
        self.arena = None

    def steer(self):
        rig = self.rig
        if badge.ticks >= self.retarget_at:
            rival = self.arena.bottom if rig is self.arena.top else self.arena.top
            self.target = vec2(
                min(WIDTH - RIG_W - 4, max(4, rival.x + random.uniform(-BOT_AIM_SPREAD, BOT_AIM_SPREAD))),
                random.uniform(rig.band[0] + 2, rig.band[1] - RIG_H - 2),
            )
            self.alert = random.random() < BOT_ALERTNESS
            self.retarget_at = badge.ticks + random.randint(400, 1200)

        for shot in self.arena.shots:
            if not self.alert or shot.aim == rig.aim:
                continue
            ahead = (rig.y - shot.y) * shot.aim
            if 0 < ahead < BOT_DODGE_RANGE and abs(shot.x - rig.cx) < RIG_W:
                self.target.x = rig.x + (RIG_W * 2 if shot.x < rig.cx else -RIG_W * 2)
                break

        dx = max(-1, min(1, (self.target.x - rig.x) / 8))
        dy = max(-1, min(1, (self.target.y - rig.y) / 8))
        return vec2(dx, dy)

    def trigger(self):
        return random.random() < BOT_FIRE_CHANCE


class Rig:
    def __init__(self, band, aim, pen, pilot):
        self.band = band
        self.aim = aim
        self.pen = pen
        self.pilot = pilot
        self.x = WIDTH / 2 - RIG_W / 2
        self.y = (band[0] + band[1]) / 2 - RIG_H / 2
        self.scrap = START_SCRAP
        self.reload_at = 0
        self.rattle = 0.0
        self.muzzle = 0
        self.tread = 0.0

    @property
    def cx(self):
        return self.x + RIG_W / 2

    @property
    def nose(self):
        return self.y + RIG_H if self.aim > 0 else self.y

    def steer(self, dt):
        move = self.pilot.steer()
        if move.length():
            self.x += move.x * SPEED * dt
            self.y += move.y * SPEED * dt
            self.tread += (abs(move.x) + abs(move.y)) * dt
        self.x = min(WIDTH - RIG_W - 2, max(2, self.x))
        self.y = min(self.band[1] - RIG_H - 1, max(self.band[0] + 1, self.y))

    def wants_to_fire(self):
        if badge.ticks < self.reload_at or not self.pilot.trigger():
            return False
        self.reload_at = badge.ticks + RELOAD_MS
        self.muzzle = 5
        return True

    def take_hit(self):
        self.scrap -= 1
        self.rattle = 5.0

    def draw(self, ox, oy):
        x = int(self.x + ox + random.uniform(-self.rattle, self.rattle))
        y = int(self.y + oy + random.uniform(-self.rattle, self.rattle))

        screen.pen = GRIME
        screen.rectangle(x + 1, y + 2, RIG_W, RIG_H)

        screen.pen = GRIME
        screen.rectangle(x, y, 4, RIG_H)
        screen.rectangle(x + RIG_W - 4, y, 4, RIG_H)
        screen.pen = DIM
        phase = int(self.tread) % 3
        for row in range(phase, RIG_H, 3):
            screen.rectangle(x, y + row, 4, 1)
            screen.rectangle(x + RIG_W - 4, y + row, 4, 1)

        screen.pen = self.pen
        screen.rectangle(x + 3, y + 1, RIG_W - 6, RIG_H - 2)
        screen.pen = GRIME
        screen.rectangle(x + 5, y + 3, RIG_W - 10, RIG_H - 6)
        screen.pen = PLATE
        screen.rectangle(x + 6, y + 4, RIG_W - 12, RIG_H - 8)

        barrel_y = y + RIG_H if self.aim > 0 else y - 4
        screen.pen = STEEL
        screen.rectangle(x + RIG_W / 2 - 1, barrel_y, 3, 4)

        if self.muzzle:
            screen.pen = SPARK
            screen.circle(vec2(x + RIG_W / 2, barrel_y + 2 + self.aim * 2), 3)


class Shot:
    def __init__(self, x, y, aim, pen):
        self.x = x
        self.y = y
        self.aim = aim
        self.pen = pen

    def advance(self, dt):
        self.y += self.aim * SHOT_SPEED * dt

    def offscreen(self):
        return self.y < -SHOT_H or self.y > HEIGHT + SHOT_H


class Chunk:
    def __init__(self, x, y, vx, vy, pen, life=460):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.pen = pen
        self.life = life
        self.size = random.randint(2, 4)

    def advance(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 0.09 * dt
        self.life -= badge.ticks_delta


class Shout:
    def __init__(self, text, x, y):
        self.labels = SHOUTS[text]
        self.width = self.labels[0].width
        self.x = min(WIDTH - self.width - 4, max(4, x - self.width / 2))
        self.y = y
        self.flipped = y < HEIGHT / 2
        self.drift = 0.35 if self.flipped else -0.35
        self.life = 520

    def advance(self, dt):
        self.y += self.drift * dt
        self.life -= badge.ticks_delta

    def draw(self, ox, oy):
        label = self.labels[0 if self.life > 260 else 1]
        screen.blit(label.flipped if self.flipped else label.upright, vec2(int(self.x + ox), int(self.y + oy)))


class Arena:
    def __init__(self, top_pilot, bottom_pilot):
        self.top = Rig(TOP_BAND, 1, GREEN, top_pilot)
        self.bottom = Rig(BOTTOM_BAND, -1, EMBER, bottom_pilot)
        self.rigs = (self.top, self.bottom)
        for rig in self.rigs:
            rig.pilot.rig = rig
            rig.pilot.arena = self
        self.shots = []
        self.chunks = []
        self.shouts = []
        self.barriers = []
        self.din = 0
        self.shake = 0.0
        self.build_barriers()

    def build_barriers(self):
        self.barriers = []
        span = BARRIER_COLS * BARRIER_W + (BARRIER_COLS - 1) * BARRIER_GAP
        left = int((WIDTH - span) / 2)
        top = int(DIVIDER[0] + (DIVIDER_H - (BARRIER_ROWS * BARRIER_H + BARRIER_GAP)) / 2)

        for row in range(BARRIER_ROWS):
            for col in range(BARRIER_COLS):
                if random.random() < 0.18:
                    continue
                self.barriers.append([
                    left + col * (BARRIER_W + BARRIER_GAP),
                    top + row * (BARRIER_H + BARRIER_GAP),
                    BARRIER_HP,
                ])

    @property
    def loser(self):
        for rig in self.rigs:
            if rig.scrap <= 0:
                return rig
        return None

    def shout(self, text, x, y):
        self.shouts.append(Shout(text, x, y))

    def clatter(self, x, y, pen, force=1.0, words=True):
        self.din = min(DIN_MAX, self.din + int(14 * force))
        self.shake = min(7.0, self.shake + 2.2 * force)

        if len(self.chunks) > MAX_CHUNKS:
            del self.chunks[:len(self.chunks) - MAX_CHUNKS]

        for _ in range(int(7 * force)):
            self.chunks.append(Chunk(
                x, y,
                random.uniform(-1.9, 1.9) * force,
                random.uniform(-1.9, 1.9) * force,
                pen if random.random() < 0.5 else SPARK,
            ))

        if words and random.random() < 0.55:
            self.shout(WORDS[random.randrange(len(WORDS))], x, y)

    def hit_barrier(self, shot):
        for block in self.barriers:
            if block[0] - 1 <= shot.x <= block[0] + BARRIER_W and \
                    block[1] - 2 <= shot.y <= block[1] + BARRIER_H + 2:
                block[2] -= 1
                self.clatter(shot.x, shot.y, RUST, 0.7)
                if block[2] <= 0:
                    self.barriers.remove(block)
                    self.clatter(block[0] + BARRIER_W / 2, block[1], RUST, 1.1)
                return True
        return False

    def hit_rig(self, shot, rig):
        if rig.aim == shot.aim or rig.scrap <= 0:
            return False
        if rig.x - 1 <= shot.x <= rig.x + RIG_W and rig.y - 1 <= shot.y <= rig.y + RIG_H:
            rig.take_hit()
            self.clatter(shot.x, shot.y, rig.pen, 1.6, False)
            self.shout("SKREEK" if rig.scrap else "SCRAPPED!", shot.x, shot.y)
            return True
        return False

    def unleash_avalanche(self):
        self.din = 0
        self.shout("RACKET!", WIDTH / 2, DIVIDER[0] + 4)

        for block in self.barriers:
            for _ in range(5):
                self.chunks.append(Chunk(
                    block[0] + BARRIER_W / 2, block[1] + BARRIER_H / 2,
                    random.uniform(-1.2, 1.2),
                    random.uniform(-3.4, 3.4),
                    RUST if random.random() < 0.6 else SPARK,
                    900,
                ))

        for rig in self.rigs:
            for _ in range(3):
                self.shots.append(Shot(
                    random.uniform(20, WIDTH - 20),
                    DIVIDER[0] + DIVIDER_H / 2,
                    -rig.aim,
                    RUST,
                ))

        self.build_barriers()
        self.clatter(WIDTH / 2, DIVIDER[0] + DIVIDER_H / 2, SPARK, 2.4, False)

    def advance(self, dt, live=True):
        self.shake *= SHAKE_DECAY

        if live:
            for rig in self.rigs:
                rig.steer(dt)
                if rig.wants_to_fire():
                    self.shots.append(Shot(rig.cx, rig.nose, rig.aim, rig.pen))
                    self.clatter(rig.cx, rig.nose, rig.pen, 0.35, False)

        for rig in self.rigs:
            if rig.muzzle:
                rig.muzzle -= 1
            rig.rattle *= 0.9

        for shot in self.shots[:]:
            shot.advance(dt)
            if shot.offscreen():
                self.shots.remove(shot)
                continue
            if self.hit_barrier(shot) or self.hit_rig(shot, self.top) or self.hit_rig(shot, self.bottom):
                self.shots.remove(shot)

        for chunk in self.chunks[:]:
            chunk.advance(dt)
            if chunk.life <= 0 or not on_screen(chunk.x, chunk.y, chunk.size, chunk.size):
                self.chunks.remove(chunk)

        for noise in self.shouts[:]:
            noise.advance(dt)
            if noise.life <= 0 or not on_screen(noise.x, noise.y, noise.width, 14):
                self.shouts.remove(noise)

        if live and self.din >= DIN_MAX:
            self.unleash_avalanche()

    def shaken(self):
        if self.shake < 0.4:
            return 0, 0
        return (
            int(random.uniform(-self.shake, self.shake)),
            int(random.uniform(-self.shake, self.shake)),
        )

    def draw(self):
        ox, oy = self.shaken()
        memoryview(screen.raw)[FIELD_START:FIELD_END] = GROUND
        screen.clip = FIELD

        screen.pen = GRIME
        for x, y, _hp in self.barriers:
            screen.rectangle(x + ox + 1, y + oy + 2, BARRIER_W, BARRIER_H)

        for x, y, hp in self.barriers:
            screen.pen = BARRIER_BRUSH if hp > 1 else WORN_BRUSH
            screen.rectangle(x + ox, y + oy, BARRIER_W, BARRIER_H)
            if hp < BARRIER_HP:
                screen.pen = GRIME
                screen.rectangle(x + ox + 4, y + oy + 3, BARRIER_W - 9, 2)

        for shot in self.shots:
            screen.pen = shot.pen
            screen.rectangle(int(shot.x + ox - SHOT_W / 2), int(shot.y + oy - SHOT_H / 2), SHOT_W, SHOT_H)

        for chunk in self.chunks:
            screen.pen = chunk.pen
            screen.rectangle(int(chunk.x + ox), int(chunk.y + oy), chunk.size, chunk.size)

        for rig in self.rigs:
            if rig.scrap > 0:
                rig.draw(ox, oy)

        for noise in self.shouts:
            noise.draw(ox, oy)

        screen.clip = SCREEN


def dot(view, x, y, lit):
    screen.pen = CHALK if lit else DIM
    view.circle(x, y, DOT_RADIUS)
    if not lit:
        screen.pen = GRIME
        view.circle(x, y, DOT_RADIUS - 2)


def pad_hint(view, cx, cy, move_lit, fire_lit):
    width = DPAD_OFFSET * 2 + DOT_SPACING * 2 + DOT_RADIUS * 2
    dpad_x = cx - width / 2 + DOT_RADIUS + DPAD_OFFSET
    for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
        dot(view, dpad_x + dx * DPAD_OFFSET, cy + dy * DPAD_OFFSET, move_lit)
    pair_x = dpad_x + DPAD_OFFSET + DOT_SPACING
    dot(view, pair_x, cy + DOT_SPACING / 2, fire_lit)
    dot(view, pair_x + DOT_SPACING, cy - DOT_SPACING / 2, fire_lit)


def button_hint(view, cx, cy, move_lit, fire_lit):
    width = DOT_SPACING * 2 + DOT_RADIUS * 2 + DOT_RADIUS + 6 + DOT_RADIUS * 2
    left = cx - width / 2 + DOT_RADIUS
    dot(view, left, cy, move_lit)
    dot(view, left + DOT_SPACING, cy, move_lit)
    dot(view, left + DOT_SPACING * 2, cy, fire_lit)
    marker_x = left + DOT_SPACING * 2 + DOT_RADIUS + 6 + DOT_RADIUS
    screen.pen = CHALK if move_lit else DIM
    view.triangle((marker_x, cy - 2 - DOT_RADIUS), (marker_x - DOT_RADIUS, cy - 2), (marker_x + DOT_RADIUS, cy - 2))
    view.triangle((marker_x, cy + 2 + DOT_RADIUS), (marker_x - DOT_RADIUS, cy + 2), (marker_x + DOT_RADIUS, cy + 2))


class Side:
    def __init__(self, flipped, hint, pen):
        self.view = View(flipped)
        self.hint = hint
        self.pen = pen
        self.drawn = None

    def rig(self, arena):
        return arena.top if self.view.flipped else arena.bottom

    def draw_hud(self, arena):
        view = self.view
        top = HEIGHT - HUD_H + 4
        rig = self.rig(arena)

        shown = (arena, rig.scrap, arena.din)
        if shown == self.drawn:
            return
        self.drawn = shown

        screen.pen = GRIME
        view.rect(0, HEIGHT - HUD_H, WIDTH, HUD_H)

        for index in range(START_SCRAP):
            screen.pen = self.pen if index < rig.scrap else DIM
            view.rect(8 + index * 14, top + 2, 10, 8)
            screen.pen = GRIME
            view.rect(8 + index * 14 + 3, top + 4, 4, 4)

        meter_w = 110
        meter_x = WIDTH - 8 - meter_w
        view.label(RACKET_LABEL, meter_x - RACKET_LABEL.width - 6, top - 1)
        screen.pen = DUST
        view.rect(meter_x, top + 2, meter_w, 8)
        filled = int(meter_w * arena.din / DIN_MAX)
        if filled > 0:
            screen.pen = SPARK if arena.din > DIN_MAX * 0.7 else RUST
            view.rect(meter_x, top + 2, filled, 8)

    def draw_hints(self):
        cy = HEIGHT - 44
        for cx, label, move_lit, fire_lit in (
            (WIDTH * 0.25, MOVE_LABEL, True, False),
            (WIDTH * 0.72, START_LABEL, False, True),
        ):
            self.hint(self.view, cx, cy, move_lit, fire_lit)
            self.view.centred(label, cy + 22, cx)

    def draw_verdict(self, arena, ready):
        won = self.rig(arena).scrap > 0
        self.view.centred(WIN_LABEL if won else LOSE_LABEL, HEIGHT / 2 + 8)
        if ready:
            self.view.centred(AGAIN_LABEL, HEIGHT - HUD_H - 22)


SIDES = (
    Side(True, pad_hint, GREEN),
    Side(False, button_hint, EMBER),
)


class Game:
    def __init__(self):
        self.light = 0.0
        self.attract()

    def attract(self):
        self.arena = Arena(Bot(), Bot())
        self.phase = Phase.ATTRACT

    def fight(self):
        self.arena = Arena(Human(badge.pad, PAD_FIRE), Human(badge.buttons, BUTTON_FIRE))
        self.phase = Phase.FIGHT

    def shoot_pressed(self):
        for controls, fire in ((badge.pad, PAD_FIRE), (badge.buttons, BUTTON_FIRE)):
            for action in fire:
                if controls.pressed(action):
                    return True
        return False

    def update(self):
        dt = min(2.5, max(0.4, badge.ticks_delta / 16.6))
        arena = self.arena

        if self.phase == Phase.ATTRACT:
            arena.advance(dt)
            if arena.loser:
                self.attract()
            if self.shoot_pressed():
                self.fight()
        elif self.phase == Phase.FIGHT:
            arena.advance(dt)
            if arena.loser:
                arena.shout("SCRAPPED!", WIDTH / 2, DIVIDER[0])
                self.phase = Phase.OVER
                self.over_at = badge.ticks
        else:
            arena.advance(dt, False)
            if badge.ticks - self.over_at > OVER_HOLD_MS and self.shoot_pressed():
                self.fight()

        self.light += (LIGHT_MAX * self.arena.din / DIN_MAX - self.light) * LIGHT_EASE
        badge.caselights(self.light)

        self.draw()

    def draw(self):
        arena = self.arena
        arena.draw()

        if self.phase == Phase.ATTRACT:
            screen.pen = GRIME
            screen.rectangle(0, 0, WIDTH, HUD_H)
            screen.rectangle(0, HEIGHT - HUD_H, WIDTH, HUD_H)
            screen.pen = VEIL
            screen.rectangle(0, 0, WIDTH, HEIGHT)
            for side in SIDES:
                side.draw_hints()
            ox, oy = arena.shaken()
            screen.blit(TITLE.upright, vec2((WIDTH - TITLE.width) / 2 + ox, (HEIGHT - TITLE.height) / 2 + oy))
            return

        for side in SIDES:
            side.draw_hud(arena)

        if self.phase == Phase.OVER:
            screen.pen = VEIL
            screen.rectangle(0, HUD_H, WIDTH, HEIGHT - HUD_H * 2)
            ready = badge.ticks - self.over_at > OVER_HOLD_MS
            for side in SIDES:
                side.draw_verdict(arena, ready)


game = Game()


def update():
    game.update()


def on_exit():
    badge.caselights(0)
    badge.autorotate(True)
    badge.default_clear = GRIME


badge.default_clear = None
run(update)
