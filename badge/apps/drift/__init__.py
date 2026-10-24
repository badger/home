APP_DIR = "/system/apps/drift"

import math
import os
from array import array
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
DRAG = 0.45              # per second; low so motion keeps floating momentum
MAX_SPEED = 260.0
WANDER = 16.0            # px/s^2 of ambient drift
JOSTLE_RATE = 0.6        # random nudges per square per second
JOSTLE_KICK = 26.0       # px/s nudge for a mid-sized square
RESTITUTION = 0.9
WALL_RESTITUTION = 0.85
BURST = 140.0
WALL_MARGIN = 26.0       # soft cushion that eases squares back off the edges
WALL_PUSH = 70.0
SPACE = 5.0              # personal space kept between neighbouring squares
SPACE_PUSH = 30.0
LOGO_SIZE = 0.15         # logo radius as a fraction of screen width
LOGO_RGB = (210, 206, 245)


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
        self.freq = random.uniform(0.2, 0.45)
        # Smaller squares feel lighter and react more to tilt.
        self.response = 0.55 + 10.0 / size
        self.glow = 0.0
        self.corner = max(1, size * 0.24)
        self.line = max(2, round(size * 0.12))


def overlaps(a, x, y, items, gap):
    lx = x - LOGO_X
    ly = y - LOGO_Y
    clear = LOGO_R + a.h * 1.42 + gap
    if lx * lx + ly * ly < clear * clear:
        return True
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

    # Tiny specks drift behind the squares for depth. They ignore the squares
    # but are kept clear of the logo so none are ever hidden behind it.
    specks = []
    for _ in range(26):
        rgb = random.choice((WHITE, LAVENDER, VIOLET, INDIGO))
        sq = Square(random.choice((3, 4, 4, 5, 6)), FILL, rgb)
        while True:
            sq.x = random.uniform(4, W - 4)
            sq.y = random.uniform(4, H - 4)
            dx = sq.x - LOGO_X
            dy = sq.y - LOGO_Y
            if dx * dx + dy * dy > (LOGO_R + sq.h + 4) ** 2:
                break
        sq.vx *= 0.5
        sq.vy *= 0.5
        sq.response = 0.35
        specks.append(sq)
    return bodies, specks


# Invertocat outline from GitHub_Invertocat_White.svg, flattened to a
# polygon and normalised so the outer circle has radius 1 about (0, 0).

LOGO_OUTLINE = (
    -0.1543, 0.4364, -0.2292, 0.4225, -0.2990, 0.4000, -0.3629, 0.3693,
    -0.4204, 0.3312, -0.4707, 0.2863, -0.5133, 0.2350, -0.5476, 0.1781,
    -0.5728, 0.1162, -0.5884, 0.0497, -0.5938, -0.0206, -0.5927, -0.0501,
    -0.5896, -0.0798, -0.5846, -0.1094, -0.5776, -0.1388, -0.5688, -0.1676,
    -0.5583, -0.1955, -0.5461, -0.2224, -0.5323, -0.2480, -0.5169, -0.2719,
    -0.5000, -0.2940, -0.5067, -0.3154, -0.5117, -0.3402, -0.5150, -0.3675,
    -0.5167, -0.3963, -0.5166, -0.4259, -0.5149, -0.4552, -0.5116, -0.4834,
    -0.5067, -0.5095, -0.5002, -0.5326, -0.4922, -0.5519, -0.4680, -0.5533,
    -0.4426, -0.5519, -0.4164, -0.5479, -0.3898, -0.5415, -0.3633, -0.5328,
    -0.3372, -0.5222, -0.3120, -0.5098, -0.2882, -0.4958, -0.2661, -0.4805,
    -0.2461, -0.4640, -0.2237, -0.4706, -0.2010, -0.4766, -0.1779, -0.4819,
    -0.1543, -0.4865, -0.1301, -0.4903, -0.1053, -0.4935, -0.0798, -0.4960,
    -0.0535, -0.4977, -0.0262, -0.4988, 0.0020, -0.4991, 0.0301, -0.4988,
    0.0573, -0.4977, 0.0836, -0.4960, 0.1090, -0.4936, 0.1335, -0.4906,
    0.1573, -0.4869, 0.1804, -0.4826, 0.2029, -0.4776, 0.2248, -0.4721,
    0.2461, -0.4659, 0.2656, -0.4819, 0.2874, -0.4968, 0.3112, -0.5104,
    0.3364, -0.5226, 0.3625, -0.5331, 0.3893, -0.5416, 0.4160, -0.5479,
    0.4424, -0.5519, 0.4679, -0.5533, 0.4922, -0.5519, 0.4997, -0.5337,
    0.5057, -0.5114, 0.5103, -0.4859, 0.5134, -0.4581, 0.5149, -0.4291,
    0.5148, -0.3996, 0.5131, -0.3706, 0.5098, -0.3430, 0.5048, -0.3179,
    0.4980, -0.2960, 0.5159, -0.2730, 0.5320, -0.2486, 0.5463, -0.2230,
    0.5587, -0.1962, 0.5693, -0.1686, 0.5781, -0.1400, 0.5849, -0.1109,
    0.5898, -0.0811, 0.5928, -0.0510, 0.5937, -0.0206, 0.5884, 0.0496,
    0.5728, 0.1158, 0.5474, 0.1774, 0.5131, 0.2338, 0.4702, 0.2846,
    0.4195, 0.3291, 0.3616, 0.3669, 0.2970, 0.3975, 0.2264, 0.4201,
    0.1504, 0.4345, 0.1696, 0.4488, 0.1875, 0.4660, 0.2037, 0.4859,
    0.2183, 0.5080, 0.2310, 0.5324, 0.2417, 0.5586, 0.2502, 0.5866,
    0.2565, 0.6161, 0.2604, 0.6468, 0.2617, 0.6786, 0.2617, 0.8817,
    0.2631, 0.8985, 0.2673, 0.9136, 0.2738, 0.9268, 0.2827, 0.9379,
    0.2935, 0.9467, 0.3060, 0.9530, 0.3201, 0.9567, 0.3355, 0.9576,
    0.3519, 0.9555, 0.3691, 0.9501, 0.4727, 0.9032, 0.5705, 0.8441,
    0.6613, 0.7734, 0.7439, 0.6920, 0.8171, 0.6007, 0.8798, 0.5004,
    0.9305, 0.3917, 0.9683, 0.2757, 0.9919, 0.1529, 1.0000, 0.0243,
    0.9869, -0.1381, 0.9489, -0.2923, 0.8880, -0.4363, 0.8065, -0.5678,
    0.7063, -0.6849, 0.5895, -0.7854, 0.4582, -0.8672, 0.3145, -0.9282,
    0.1604, -0.9664, -0.0020, -0.9796, -0.1642, -0.9664, -0.3180, -0.9282,
    -0.4613, -0.8672, -0.5920, -0.7854, -0.7083, -0.6849, -0.8079, -0.5678,
    -0.8889, -0.4363, -0.9493, -0.2923, -0.9870, -0.1381, -1.0000, 0.0243,
    -0.9919, 0.1520, -0.9684, 0.2744, -0.9305, 0.3904, -0.8793, 0.4994,
    -0.8159, 0.6002, -0.7414, 0.6921, -0.6568, 0.7742, -0.5633, 0.8454,
    -0.4618, 0.9050, -0.3535, 0.9520, -0.3378, 0.9563, -0.3225, 0.9575,
    -0.3079, 0.9559, -0.2943, 0.9516, -0.2820, 0.9450, -0.2713, 0.9362,
    -0.2624, 0.9254, -0.2557, 0.9129, -0.2515, 0.8989, -0.2500, 0.8837,
    -0.2500, 0.7274, -0.2672, 0.7340, -0.2858, 0.7394, -0.3051, 0.7435,
    -0.3246, 0.7461, -0.3438, 0.7470, -0.3809, 0.7449, -0.4150, 0.7386,
    -0.4464, 0.7283, -0.4751, 0.7138, -0.5015, 0.6955, -0.5256, 0.6731,
    -0.5477, 0.6470, -0.5679, 0.6170, -0.5864, 0.5832, -0.6035, 0.5458,
    -0.6100, 0.5306, -0.6168, 0.5168, -0.6239, 0.5042, -0.6315, 0.4931,
    -0.6396, 0.4833, -0.6582, 0.4680, -0.6805, 0.4585, -0.6934, 0.4560,
    -0.7056, 0.4539, -0.7178, 0.4479, -0.7244, 0.4360, -0.7202, 0.4193,
    -0.7084, 0.4080, -0.6909, 0.3992, -0.6696, 0.3935, -0.6465, 0.3915,
    -0.6297, 0.3926, -0.6134, 0.3957, -0.5974, 0.4010, -0.5816, 0.4085,
    -0.5662, 0.4181, -0.5509, 0.4299, -0.5357, 0.4439, -0.5205, 0.4600,
    -0.5054, 0.4784, -0.4902, 0.4989, -0.4785, 0.5150, -0.4665, 0.5292,
    -0.4544, 0.5416, -0.4420, 0.5523, -0.4294, 0.5612, -0.4165, 0.5684,
    -0.4033, 0.5739, -0.3897, 0.5779, -0.3757, 0.5802, -0.3613, 0.5810,
    -0.3472, 0.5804, -0.3339, 0.5788, -0.3213, 0.5759, -0.3092, 0.5719,
    -0.2974, 0.5666, -0.2857, 0.5599, -0.2739, 0.5518, -0.2619, 0.5422,
    -0.2494, 0.5311, -0.2363, 0.5185, -0.2266, 0.5086, -0.2173, 0.4990,
    -0.2084, 0.4898, -0.1999, 0.4809, -0.1837, 0.4642, -0.1686, 0.4493,
    -0.1543, 0.4364,
)

LOGO_X = W / 2
LOGO_Y = H / 2
LOGO_R = W * LOGO_SIZE

logo_points = array("f", LOGO_OUTLINE)
for k in range(0, len(logo_points), 2):
    logo_points[k] = LOGO_X + logo_points[k] * LOGO_R
    logo_points[k + 1] = LOGO_Y + logo_points[k + 1] * LOGO_R
logo = shape.custom(logo_points)
logo_glow = 0.0

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
    if random.random() < JOSTLE_RATE * dt:
        # Smaller squares get knocked about more than big ones.
        kick = JOSTLE_KICK * random.uniform(0.5, 1.0) * min(2.0, 12.0 / sq.h)
        angle = random.uniform(0, 2 * math.pi)
        sq.vx += math.cos(angle) * kick
        sq.vy += math.sin(angle) * kick
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

    sq.glow = max(0.0, sq.glow - dt * 3.5)


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


def keep_off_logo(sq):
    dx = sq.x - LOGO_X
    dy = sq.y - LOGO_Y
    clear = LOGO_R + sq.h * 1.42 + 1
    d2 = dx * dx + dy * dy
    if d2 >= clear * clear:
        return
    dist = math.sqrt(d2) or 1.0
    nx = dx / dist
    ny = dy / dist
    sq.x = LOGO_X + nx * clear
    sq.y = LOGO_Y + ny * clear
    vn = sq.vx * nx + sq.vy * ny
    if vn < 0:
        sq.vx -= (1 + RESTITUTION) * vn * nx
        sq.vy -= (1 + RESTITUTION) * vn * ny


def hit_logo(sq, dt):
    # The logo is an anchored circle with infinite mass: only the square moves.
    global logo_glow
    h = sq.h
    cx = min(max(LOGO_X, sq.x - h), sq.x + h)
    cy = min(max(LOGO_Y, sq.y - h), sq.y + h)
    dx = cx - LOGO_X
    dy = cy - LOGO_Y
    dist = math.sqrt(dx * dx + dy * dy)
    if dist == 0:
        dx = sq.x - LOGO_X
        dy = sq.y - LOGO_Y
        dist = math.sqrt(dx * dx + dy * dy) or 1.0
        gap = -(LOGO_R + h)
    else:
        gap = dist - LOGO_R
    if gap >= SPACE:
        return
    nx = dx / dist
    ny = dy / dist
    if gap > 0:
        if dt:
            push = SPACE_PUSH * (1 - gap / SPACE) * dt
            sq.vx += nx * push
            sq.vy += ny * push
        return
    sq.x -= nx * gap
    sq.y -= ny * gap
    vn = sq.vx * nx + sq.vy * ny
    if vn < 0:
        sq.vx -= (1 + RESTITUTION) * vn * nx
        sq.vy -= (1 + RESTITUTION) * vn * ny
        flash = min(1.0, -vn / 35)
        sq.glow = max(sq.glow, flash)
        logo_glow = max(logo_glow, flash * 0.8)


def bump(a, b, speed):
    flash = min(1.0, speed / 35)
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
    global logo_glow
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
        keep_off_logo(sq)
    for sq in bodies:
        integrate(sq, t, dt, ax, ay, damp)

    count = len(bodies)
    for step_dt in (dt, 0, 0):
        for i in range(count):
            a = bodies[i]
            for j in range(i + 1, count):
                collide(a, bodies[j], step_dt)
            hit_logo(a, step_dt)
    logo_glow = max(0.0, logo_glow - dt * 2.5)

    screen.blit(backdrop, vec2(0, 0))
    screen.antialias = image.OFF
    for sq in specks:
        draw_speck(sq, t)
    screen.antialias = image.X4
    screen.pen = tint(LOGO_RGB, logo_glow)
    screen.shape(logo)
    for sq in bodies:
        draw_square(sq)


run(update)
