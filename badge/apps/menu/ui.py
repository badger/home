import math


def shade(rgb, strength):
    return color.rgb(*(round(channel * strength) for channel in rgb))


PALETTE = [
    (88, 58, 247),
    (22, 143, 251),
    (15, 191, 62),
    (247, 54, 120),
    (192, 82, 0),
    (187, 160, 10),
    (8, 135, 43),
    (255, 125, 237),
]

white = color.rgb(255, 255, 255)
black = color.rgb(0, 0, 0)
dim_white = color.rgb(255, 255, 255, 140)
accent = color.rgb(95, 237, 131)

STATUS_HEIGHT = 21
RIBBON_TOP = 198
TITLE_X = 8
TITLE_Y = 202
OS_NAME = "MonaOS 4.0"
OS_X = 8
TITLE_SLIDE_MS = 220
TITLE_SLIDE_PX = 18

status_font = font.salty
title_font = font.ignore


class Tilt:
    GRAVITY = 16384.0
    SMOOTH_MS = 120
    RECENTRE_MS = 2800

    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.rest_z = None
        self.last_ticks = None

    def update(self):
        ax, _, az = badge.imu()[:3]
        now = badge.ticks
        dt = min(now - self.last_ticks, 200) if self.last_ticks is not None else 0
        self.last_ticks = now
        smooth = 1 - math.exp(-dt / self.SMOOTH_MS)
        recentre = 1 - math.exp(-dt / self.RECENTRE_MS)
        if self.rest_z is None:
            self.rest_z = az
        self.rest_z += (az - self.rest_z) * recentre
        target_x = max(-1.0, min(1.0, -ax / self.GRAVITY * 2))
        target_y = max(-1.0, min(1.0, (az - self.rest_z) / self.GRAVITY * 2))
        self.x += (target_x - self.x) * smooth
        self.y += (target_y - self.y) * smooth


def draw_battery(right, top):
    if badge.is_charging():
        level = (badge.ticks / 20) % 100
    else:
        level = badge.battery_level()
    width, height = 22, 11
    left = right - width - 2
    screen.pen = white
    screen.rectangle(left, top, width, height)
    screen.rectangle(left + width, top + 4, 2, 3)
    screen.pen = black
    screen.rectangle(left + 1, top + 1, width - 2, height - 2)
    screen.pen = white
    screen.rectangle(left + 2, top + 2, round((width - 4) * level / 100), height - 4)
    return left


def draw_status(index, total, hidden=0.0):
    top = 3 - round(STATUS_HEIGHT * hidden)
    screen.font = status_font
    screen.pen = white
    screen.text(OS_NAME, OS_X, top)
    count = f"{index + 1:02d} / {total:02d}"
    width, _ = screen.measure_text(count)
    screen.pen = dim_white
    screen.text(count, (320 - width) / 2, top)
    draw_battery(320 - OS_X, top + 2)


def draw_title(name, changed_at, hidden=0.0):
    progress = min(1.0, (badge.ticks - changed_at) / TITLE_SLIDE_MS)
    eased = 1 - (1 - progress) ** 3
    x = TITLE_X + TITLE_SLIDE_PX * (1 - eased)

    screen.font = title_font
    screen.pen = white
    screen.alpha = round(255 * eased)
    screen.text(name.lower(), x, TITLE_Y + round((240 - RIBBON_TOP) * hidden))
    screen.alpha = 255
