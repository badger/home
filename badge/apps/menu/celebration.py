import math
import random
from array import array

import ui
from achievements import ACHIEVEMENT_NAMES, draw_achievement, location_rgb
from easing import easeOutBack, easeOutCubic

ACHIEVEMENT_X = 107
ACHIEVEMENT_Y = 108
ACHIEVEMENT_SIZE = 124
LABEL_WIDTH = 210
LABEL_Y = 192
LINE_HEIGHT = 22
COVER_MS = 320
COVER_RADIUS = 420
POP_DELAY_MS = 140
POP_MS = 460
DISMISS_AFTER_MS = 600
EXIT_MS = 240

WIGGLE_EVERY_MS = 1700
WIGGLE_MS = 650
WIGGLE_DEGREES = 14
WIGGLE_TURNS = 3

RING_SPACING = 46
RING_SPEED = 0.025

HEART_EVERY_MS = 120
HEART_LIFE_MS = 1800
HEART_ORIGIN_X = 282
HEART_ORIGIN_Y = 160
HEART_SPREAD = 26
HEART_POINTS = 24

pink = (255, 125, 237)


def build_heart():
    values = []
    for step in range(HEART_POINTS):
        angle = step * 2 * math.pi / HEART_POINTS
        x = 16 * math.sin(angle) ** 3
        y = -(13 * math.cos(angle) - 5 * math.cos(2 * angle) - 2 * math.cos(3 * angle) - math.cos(4 * angle))
        values.extend((x / 17, y / 17))
    return shape.custom(array("f", values))


heart_shape = None


def heart():
    global heart_shape
    if heart_shape is None:
        heart_shape = build_heart()
    return heart_shape


def label_lines(label):
    if screen.measure_text(label)[0] <= LABEL_WIDTH:
        return [label]
    words = label.split()
    best = None
    for split in range(1, len(words)):
        lines = [" ".join(words[:split]), " ".join(words[split:])]
        widest = max(screen.measure_text(line)[0] for line in lines)
        if best is None or widest < best[0]:
            best = (widest, lines)
    return best[1] if best else [label]


def clamp01(value):
    return max(0.0, min(1.0, value))


class Heart:
    def __init__(self, born):
        self.born = born
        self.x = HEART_ORIGIN_X + random.uniform(-HEART_SPREAD, HEART_SPREAD)
        self.speed = random.uniform(55, 95)
        self.sway = random.uniform(5, 12)
        self.phase = random.uniform(0, 2 * math.pi)
        self.size = random.uniform(9, 16)
        self.rgb = pink if random.random() < 0.5 else (255, 255, 255)

    def alive(self, now):
        return now - self.born < HEART_LIFE_MS

    def draw(self, now):
        age = now - self.born
        life = age / HEART_LIFE_MS
        x = self.x + math.sin(self.phase + age / 280) * self.sway
        y = HEART_ORIGIN_Y - self.speed * age / 1000
        size = self.size * (0.4 + 0.6 * clamp01(age / 260))
        alpha = round(255 * clamp01((1 - life) / 0.45))
        shape_ = heart()
        shape_.transform = mat3().translate(x, y).scale(size)
        screen.pen = color.rgb(*self.rgb, alpha)
        screen.shape(shape_)


class Celebration:
    def __init__(self, index, origin):
        self.index = index
        self.origin = origin
        self.started = badge.ticks
        self.exit_at = None
        self.hearts = []
        self.next_heart = self.started + COVER_MS
        rgb = location_rgb(index)
        self.background = color.rgb(*rgb)
        self.ring = ui.shade(tuple(min(255, channel + 40) for channel in rgb), 1.0)
        self.label = ui.lowercase(ACHIEVEMENT_NAMES[index])

    def dismiss(self):
        if self.exit_at is None and badge.ticks - self.started >= DISMISS_AFTER_MS:
            self.exit_at = badge.ticks

    @property
    def done(self):
        return self.exit_at is not None and badge.ticks - self.exit_at >= EXIT_MS

    def cover(self):
        now = badge.ticks
        amount = easeOutCubic(clamp01((now - self.started) / COVER_MS))
        if self.exit_at is not None:
            amount *= 1 - easeOutCubic(clamp01((now - self.exit_at) / EXIT_MS))
        return amount

    @property
    def covering(self):
        return self.exit_at is None and badge.ticks - self.started >= COVER_MS

    def achievement_scale(self):
        now = badge.ticks
        local = clamp01((now - self.started - POP_DELAY_MS) / POP_MS)
        scale = easeOutBack(local) if local > 0 else 0.0
        if self.exit_at is not None:
            scale *= 1 - easeOutCubic(clamp01((now - self.exit_at) / EXIT_MS))
        return scale

    def wiggle(self):
        age = badge.ticks - self.started - POP_DELAY_MS - POP_MS
        if age < 0:
            return 0.0
        local = age % WIGGLE_EVERY_MS
        if local >= WIGGLE_MS:
            return 0.0
        progress = local / WIGGLE_MS
        return WIGGLE_DEGREES * math.sin(progress * WIGGLE_TURNS * 2 * math.pi) * (1 - progress)

    def look_target(self):
        return ACHIEVEMENT_X, ACHIEVEMENT_Y

    def draw_back(self, tilt):
        now = badge.ticks
        cover = self.cover()
        if cover <= 0:
            return
        origin_x, origin_y = self.origin
        centre_x = origin_x + (ACHIEVEMENT_X - origin_x) * cover
        centre_y = origin_y + (ACHIEVEMENT_Y - origin_y) * cover
        radius = COVER_RADIUS * cover

        screen.clip = rect(0, 0, screen.width, screen.height)
        antialias = screen.antialias
        screen.antialias = image.OFF
        screen.pen = self.background
        screen.shape(shape.circle(centre_x, centre_y, radius))

        offset = (now * RING_SPEED) % (RING_SPACING * 2)
        ring = radius - (RING_SPACING * 2 - offset)
        while ring > 0:
            screen.pen = self.ring
            screen.shape(shape.circle(centre_x, centre_y, ring))
            screen.pen = self.background
            screen.shape(shape.circle(centre_x, centre_y, max(0, ring - RING_SPACING)))
            ring -= RING_SPACING * 2
        screen.antialias = antialias

        scale = self.achievement_scale()
        if scale > 0:
            size = ACHIEVEMENT_SIZE * scale
            draw_achievement(self.index, True, centre_x - size / 2, centre_y - size / 2, size, tilt, True, 2 * scale, self.wiggle())

        if self.covering:
            screen.font = ui.status_font
            screen.pen = ui.white
            caption = "Location unlocked!"
            width, _ = screen.measure_text(caption)
            screen.text(caption, ACHIEVEMENT_X - width / 2, 12)
            screen.font = ui.title_font
            lines = label_lines(self.label)
            top = LABEL_Y - (len(lines) - 1) * LINE_HEIGHT / 2
            for index, line in enumerate(lines):
                width, _ = screen.measure_text(line)
                screen.text(line, ACHIEVEMENT_X - width / 2, top + index * LINE_HEIGHT)

    def draw_front(self):
        now = badge.ticks
        if self.exit_at is None:
            while now >= self.next_heart:
                self.hearts.append(Heart(self.next_heart))
                self.next_heart += HEART_EVERY_MS
        self.hearts = [item for item in self.hearts if item.alive(now)]
        screen.clip = rect(0, 0, screen.width, screen.height)
        for item in self.hearts:
            item.draw(now)
