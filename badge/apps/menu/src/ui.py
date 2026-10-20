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
BATTERY_MS = 1000

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


battery = {"read_at": None, "charging": False, "level": 0}


def read_battery():
    now = badge.ticks
    if battery["read_at"] is None or now - battery["read_at"] >= BATTERY_MS:
        battery["read_at"] = now
        battery["charging"] = badge.is_charging()
        battery["level"] = badge.battery_level()
    return battery["charging"], battery["level"]


def draw_battery(right, top):
    charging, level = read_battery()
    if charging:
        level = (badge.ticks / 20) % 100
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


status_count = (None, "", 0)


def draw_status(index, total, hidden=0.0):
    global status_count
    top = 3 - round(STATUS_HEIGHT * hidden)
    screen.font = status_font
    screen.pen = white
    screen.text(OS_NAME, OS_X, top)
    key, count, x = status_count
    if key != (index, total):
        count = f"{index + 1:02d} / {total:02d}"
        width, _ = screen.measure_text(count)
        x = (320 - width) / 2
        status_count = ((index, total), count, x)
    screen.pen = dim_white
    screen.text(count, x, top)
    draw_battery(320 - OS_X, top + 2)


def lowercase(text):
    return " ".join(word if len(word) > 1 and word.isupper() else word.lower() for word in text.split(" "))


titles = {}


def draw_title(name, changed_at, hidden=0.0):
    text = titles.get(name)
    if text is None:
        text = titles[name] = lowercase(name)
    y = TITLE_Y + round((240 - RIBBON_TOP) * hidden)
    screen.font = title_font
    screen.pen = white
    elapsed = badge.ticks - changed_at
    if elapsed >= TITLE_SLIDE_MS:
        screen.text(text, TITLE_X, y)
        return
    eased = 1 - (1 - elapsed / TITLE_SLIDE_MS) ** 3
    screen.alpha = round(255 * eased)
    screen.text(text, TITLE_X + TITLE_SLIDE_PX * (1 - eased), y)
    screen.alpha = 255
