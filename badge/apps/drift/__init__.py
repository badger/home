APP_DIR = "/system/apps/drift"

import math
import os
import random
import sys

os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

badge.mode(HIRES | VSYNC)

W = screen.width
H = screen.height

BG = color.rgb(9, 8, 15)
GRID_DOT = color.rgb(26, 24, 40)

WHITE = (236, 234, 250)
LAVENDER = (160, 150, 255)
VIOLET = (112, 102, 232)
INDIGO = (84, 76, 196)

FILL = 0
OUTLINE = 1
HATCH = 2

IMU_GRAVITY = 16384.0
TILT_ACCEL = 900.0       # px/s^2 per g of tilt change
BASELINE_TAU = 3.0       # seconds for "level" to catch up with a held tilt
DRAG = 0.55              # per second; low so motion keeps floating momentum
MAX_SPEED = 260.0
WANDER = 9.0             # px/s^2 of ambient drift
RESTITUTION = 0.55
WALL_RESTITUTION = 0.6
BURST = 140.0
WALL_MARGIN = 26.0       # soft cushion that eases squares back off the edges
WALL_PUSH = 70.0
SPACE = 16.0             # personal space kept between neighbouring squares
SPACE_PUSH = 80.0


class Square:
    def __init__(self, size, style, rgb):
        self.s = size
        self.h = size / 2
        self.mass = size * size
        self.inv_mass = 1.0 / self.mass
        self.style = style
        self.rgb = rgb
        self.x = 0.0
        self.y = 0.0
        self.vx = random.uniform(-12, 12)
        self.vy = random.uniform(-12, 12)
        self.phase = random.uniform(0, 2 * math.pi)
        self.freq = random.uniform(0.12, 0.3)
        # Smaller squares feel lighter and react more to tilt.
        self.response = 0.55 + 10.0 / size
        self.glow = 0.0
        self.corner = max(1, size * 0.24)
        self.line = max(2, round(size * 0.12))


def overlaps(a, x, y, items, gap):
    for b in items:
        if abs(x - b.x) < a.h + b.h + gap and abs(y - b.y) < a.h + b.h + gap:
            return True
    return False


def place(sq, items, gap=4):
    for _ in range(80):
        x = random.uniform(sq.h + 2, W - sq.h - 2)
        y = random.uniform(sq.h + 2, H - sq.h - 2)
        if not overlaps(sq, x, y, items, gap):
            sq.x, sq.y = x, y
            return True
    return False


def build():
    bodies = []
    recipe = (
        # size range, style, colour, count
        ((30, 40), OUTLINE, INDIGO, 3),
        ((24, 32), FILL, VIOLET, 2),
        ((24, 30), HATCH, INDIGO, 1),
        ((20, 28), FILL, LAVENDER, 3),
        ((20, 26), FILL, WHITE, 3),
        ((20, 28), OUTLINE, WHITE, 2),
        ((14, 22), OUTLINE, VIOLET, 3),
        ((10, 14), FILL, VIOLET, 4),
        ((8, 12), FILL, WHITE, 3),
    )
    for (lo, hi), style, rgb, count in recipe:
        for _ in range(count):
            sq = Square(random.randint(lo, hi), style, rgb)
            if place(sq, bodies):
                bodies.append(sq)

    # Tiny specks drift behind the squares for depth and never collide.
    specks = []
    for _ in range(26):
        rgb = random.choice((WHITE, LAVENDER, VIOLET, INDIGO))
        sq = Square(random.choice((3, 4, 4, 5, 6)), FILL, rgb)
        sq.x = random.uniform(4, W - 4)
        sq.y = random.uniform(4, H - 4)
        sq.vx *= 0.5
        sq.vy *= 0.5
        sq.response = 0.35
        specks.append(sq)
    return bodies, specks


bodies, specks = build()

backdrop = image(W, H)
backdrop.pen = BG
backdrop.clear()
backdrop.pen = GRID_DOT
for gy in range(4, H, 8):
    for gx in range(4, W, 8):
        backdrop.rectangle(gx, gy, 1, 1)

hatch = brush.pattern(color.rgb(LAVENDER[0], LAVENDER[1], LAVENDER[2], 170), color.rgb(0, 0, 0, 0), (
    0b10101010,
    0b00000000,
    0b10101010,
    0b00000000,
    0b10101010,
    0b00000000,
    0b10101010,
    0b00000000))

baseline = None
was_upside_down = None


def read_tilt(dt):
    """Return tilt change in g, relative to a slowly adapting baseline."""
    global baseline, was_upside_down
    reading = badge.imu()
    x = reading[0] / IMU_GRAVITY
    y = reading[1] / IMU_GRAVITY
    flipped = badge.upside_down()
    if flipped:
        x, y = -x, -y
    if baseline is None or flipped != was_upside_down or not any(reading[:3]):
        baseline = [x, y]
        was_upside_down = flipped
        return 0.0, 0.0
    k = min(1.0, dt / BASELINE_TAU)
    baseline[0] += (x - baseline[0]) * k
    baseline[1] += (y - baseline[1]) * k
    return x - baseline[0], y - baseline[1]


def cushion(p, h, size):
    near = p - h
    if near < WALL_MARGIN:
        return WALL_PUSH * (1 - near / WALL_MARGIN)
    far = size - p - h
    if far < WALL_MARGIN:
        return -WALL_PUSH * (1 - far / WALL_MARGIN)
    return 0.0


def integrate(sq, t, dt, ax, ay, damp):
    wx = math.sin(t * sq.freq + sq.phase) * WANDER
    wy = math.cos(t * sq.freq * 0.8 + sq.phase * 1.7) * WANDER
    wx += cushion(sq.x, sq.h, W)
    wy += cushion(sq.y, sq.h, H)
    sq.vx = (sq.vx + (ax * sq.response + wx) * dt) * damp
    sq.vy = (sq.vy + (ay * sq.response + wy) * dt) * damp

    speed = math.sqrt(sq.vx * sq.vx + sq.vy * sq.vy)
    if speed > MAX_SPEED:
        sq.vx *= MAX_SPEED / speed
        sq.vy *= MAX_SPEED / speed

    sq.x += sq.vx * dt
    sq.y += sq.vy * dt

    h = sq.h
    if sq.x < h:
        sq.x = h
        if sq.vx < 0:
            sq.vx = -sq.vx * WALL_RESTITUTION
    elif sq.x > W - h:
        sq.x = W - h
        if sq.vx > 0:
            sq.vx = -sq.vx * WALL_RESTITUTION
    if sq.y < h:
        sq.y = h
        if sq.vy < 0:
            sq.vy = -sq.vy * WALL_RESTITUTION
    elif sq.y > H - h:
        sq.y = H - h
        if sq.vy > 0:
            sq.vy = -sq.vy * WALL_RESTITUTION

    sq.glow = max(0.0, sq.glow - dt * 1.6)


def collide(a, b, dt):
    dx = b.x - a.x
    reach = a.h + b.h
    px = reach - abs(dx)
    if px <= -SPACE:
        return
    dy = b.y - a.y
    py = reach - abs(dy)
    if py <= -SPACE:
        return
    if px <= 0 or py <= 0:
        if dt:
            repel(a, b, dx, dy, min(px, py), dt)
        return

    total = a.inv_mass + b.inv_mass
    # Resolve along the axis of least penetration so squares slide past each
    # other instead of sticking at corners.
    if px < py:
        n = 1 if dx >= 0 else -1
        a.x -= n * px * a.inv_mass / total
        b.x += n * px * b.inv_mass / total
        rel = (b.vx - a.vx) * n
        if rel < 0:
            j = -(1 + RESTITUTION) * rel / total
            a.vx -= n * j * a.inv_mass
            b.vx += n * j * b.inv_mass
            bump(a, b, -rel)
    else:
        n = 1 if dy >= 0 else -1
        a.y -= n * py * a.inv_mass / total
        b.y += n * py * b.inv_mass / total
        rel = (b.vy - a.vy) * n
        if rel < 0:
            j = -(1 + RESTITUTION) * rel / total
            a.vy -= n * j * a.inv_mass
            b.vy += n * j * b.inv_mass
            bump(a, b, -rel)


def repel(a, b, dx, dy, gap, dt):
    # Close but not touching: nudge apart so the field slowly evens out.
    d = math.sqrt(dx * dx + dy * dy) or 1.0
    push = SPACE_PUSH * (1 + gap / SPACE) * dt / (a.inv_mass + b.inv_mass)
    nx = dx / d
    ny = dy / d
    a.vx -= nx * push * a.inv_mass
    a.vy -= ny * push * a.inv_mass
    b.vx += nx * push * b.inv_mass
    b.vy += ny * push * b.inv_mass


def bump(a, b, speed):
    flash = min(1.0, speed / 70)
    a.glow = max(a.glow, flash)
    b.glow = max(b.glow, flash)


def burst():
    cx = W / 2
    cy = H / 2
    for group in (bodies, specks):
        for sq in group:
            dx = sq.x - cx
            dy = sq.y - cy
            d = math.sqrt(dx * dx + dy * dy) or 1.0
            push = BURST * sq.response * 0.6
            sq.vx += dx / d * push
            sq.vy += dy / d * push


def tint(rgb, glow, alpha=255):
    if glow <= 0:
        return color.rgb(rgb[0], rgb[1], rgb[2], alpha)
    return color.rgb(
        int(rgb[0] + (255 - rgb[0]) * glow),
        int(rgb[1] + (255 - rgb[1]) * glow),
        int(rgb[2] + (255 - rgb[2]) * glow),
        alpha)


def draw_square(sq):
    s = sq.s
    body = shape.rounded_rectangle(sq.x - sq.h, sq.y - sq.h, s, s, sq.corner)
    if sq.style == FILL:
        screen.pen = tint(sq.rgb, sq.glow)
        screen.shape(body)
    elif sq.style == OUTLINE:
        screen.pen = tint(sq.rgb, sq.glow)
        screen.shape(body.stroke(sq.line))
    else:
        screen.pen = hatch
        screen.shape(body)
        screen.pen = tint(sq.rgb, sq.glow)
        screen.shape(body.stroke(sq.line))


def draw_speck(sq, t):
    twinkle = 0.55 + 0.45 * math.sin(t * 1.3 + sq.phase * 3)
    screen.pen = tint(sq.rgb, 0, int(70 + 150 * twinkle))
    screen.rectangle(int(sq.x - sq.h), int(sq.y - sq.h), sq.s, sq.s)


def update():
    dt = min(badge.ticks_delta / 1000, 0.05)
    t = badge.ticks / 1000

    if badge.pressed(BUTTON_SELECT):
        burst()

    tx, ty = read_tilt(dt)
    ax = tx * TILT_ACCEL
    ay = ty * TILT_ACCEL
    damp = math.exp(-DRAG * dt)

    for sq in specks:
        integrate(sq, t, dt, ax, ay, damp)
    for sq in bodies:
        integrate(sq, t, dt, ax, ay, damp)

    count = len(bodies)
    for step_dt in (dt, 0):
        for i in range(count):
            a = bodies[i]
            for j in range(i + 1, count):
                collide(a, bodies[j], step_dt)

    screen.blit(backdrop, vec2(0, 0))
    screen.antialias = image.OFF
    for sq in specks:
        draw_speck(sq, t)
    screen.antialias = image.X4
    for sq in bodies:
        draw_square(sq)


run(update)
