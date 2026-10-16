APP_DIR = "/system/apps/input_test"

import os
import sys

os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

import machine

import brand

badge.mode(HIRES | VSYNC)

screen.font = font.sins
screen.antialias = image.X4

BG = brand.GRAY_6
OUTLINE = brand.GRAY_4
LABEL = brand.GRAY_3
VALUE = brand.GRAY_1
TOUCH_ON = brand.GREEN_2
BUTTON_ON = brand.GREEN_4
ACCENT = brand.GREEN_1
ON_ACCENT = brand.BLACK

_, LINE = screen.measure_text("Ag")
LINE += 2

PAD_X = 54
PAD_Y = 116
ARM = 26
REACH = 28

DPAD = (
    (BUTTON_UP, PAD_X - ARM // 2, PAD_Y - ARM // 2 - REACH),
    (BUTTON_DOWN, PAD_X - ARM // 2, PAD_Y - ARM // 2 + REACH),
    (BUTTON_LEFT, PAD_X - ARM // 2 - REACH, PAD_Y - ARM // 2),
    (BUTTON_RIGHT, PAD_X - ARM // 2 + REACH, PAD_Y - ARM // 2),
)

ROUND_PADS = (
    ("MN", BUTTON_MENU, 116, 96, 14),
    ("HM", BUTTON_HOME, 116, 138, 14),
    ("SEL", BUTTON_SELECT, 156, 92, 17),
    ("BK", BUTTON_BACK, 156, 142, 17),
)

PHYSICAL = (
    ("UP", BUTTON_UP),
    ("DOWN", BUTTON_DOWN),
    ("LEFT", BUTTON_LEFT),
    ("RIGHT", BUTTON_RIGHT),
    ("SEL", BUTTON_SELECT),
    ("HOME", BUTTON_HOME),
)

ACTIONS = (
    ("UP", BUTTON_UP),
    ("DOWN", BUTTON_DOWN),
    ("LEFT", BUTTON_LEFT),
    ("RIGHT", BUTTON_RIGHT),
    ("SEL", BUTTON_SELECT),
    ("BACK", BUTTON_BACK),
    ("MENU", BUTTON_MENU),
    ("HOME", BUTTON_HOME),
)

DIVIDER_X = 180
RIGHT_X = 188
DIAL_X = 252
DIAL_Y = 150
DIAL_R = 32


def centred(text, x, y, pen):
    width, height = screen.measure_text(text)
    screen.pen = pen
    screen.text(text, x - width / 2, y - height / 2)


def disc(x, y, radius, pen):
    screen.pen = pen
    screen.shape(shape.circle(x, y, radius))


def ring(x, y, radius, active, pen):
    disc(x, y, radius, pen if active else OUTLINE)
    if not active:
        disc(x, y, radius - 2, BG)


def slab(x, y, width, height, active, pen):
    screen.pen = pen if active else OUTLINE
    screen.shape(shape.rounded_rectangle(x, y, width, height, 4))
    if not active:
        screen.pen = BG
        screen.shape(shape.rounded_rectangle(x + 2, y + 2, width - 4, height - 4, 3))


def heading(move):
    return int(round((move.angle() * 57.29577951308232 + 90) % 360)) % 360


def draw_pad():
    screen.pen = LABEL
    screen.text("TOUCH PAD", 8, 26)

    for action, x, y in DPAD:
        slab(x, y, ARM, ARM, badge.touched(action), TOUCH_ON)

    for label, action, x, y, radius in ROUND_PADS:
        active = badge.touched(action)
        ring(x, y, radius, active, TOUCH_ON)
        centred(label, x, y, ON_ACCENT if active else OUTLINE)


def draw_physical():
    screen.pen = LABEL
    screen.text("PHYSICAL", RIGHT_X, 26)

    for index, (label, key) in enumerate(PHYSICAL):
        x = RIGHT_X + (index % 3) * 43
        y = 44 + (index // 3) * 24
        pressed = key.value() == 0
        slab(x, y, 40, 20, pressed, BUTTON_ON)
        centred(label, x + 20, y + 10, ON_ACCENT if pressed else OUTLINE)


def draw_dial():
    screen.pen = LABEL
    screen.text("DIRECTION", RIGHT_X, 100)

    move = badge.direction()

    ring(DIAL_X, DIAL_Y, DIAL_R, False, OUTLINE)

    if move.length():
        screen.pen = ACCENT
        screen.text("%d deg" % heading(move), RIGHT_X + 74, 100)
        screen.pen = TOUCH_ON
        screen.line(DIAL_X, DIAL_Y, DIAL_X + move.x * DIAL_R, DIAL_Y + move.y * DIAL_R)
        disc(DIAL_X + move.x * DIAL_R, DIAL_Y + move.y * DIAL_R, 4, TOUCH_ON)
    else:
        disc(DIAL_X, DIAL_Y, 3, OUTLINE)


def draw_status():
    held = badge.held()
    names = [label for label, action in ACTIONS if action in held]

    y = screen.height - LINE * 3 - 4

    screen.pen = LABEL
    screen.text("held", 8, y)
    screen.pen = VALUE if names else OUTLINE
    screen.text(" ".join(names) if names else "-", 48, y)

    move = badge.direction()
    screen.pen = LABEL
    screen.text("vec", RIGHT_X, y)
    screen.pen = ACCENT if move.length() else OUTLINE
    screen.text("%.1f,%.1f" % (move.x, move.y), RIGHT_X + 32, y)

    ax, ay, az, _gx, _gy, _gz = badge.imu()
    y += LINE
    screen.pen = LABEL
    screen.text("imu", 8, y)
    screen.pen = VALUE
    screen.text("%d %d %d" % (ax, ay, az), 48, y)

    y += LINE
    screen.pen = LABEL
    screen.text("flip", 8, y)
    screen.pen = ACCENT if badge.upside_down() else OUTLINE
    screen.text("upside-down" if badge.upside_down() else "upright", 48, y)

    screen.pen = OUTLINE
    screen.text("press RESET to exit", RIGHT_X, y)


def update():
    screen.pen = VALUE
    screen.text("INPUT TEST", 8, 6)
    screen.pen = OUTLINE
    screen.line(8, 22, screen.width - 8, 22)
    screen.line(DIVIDER_X, 26, DIVIDER_X, screen.height - LINE * 3 - 12)

    draw_pad()
    draw_physical()
    draw_dial()
    draw_status()


badge.default_clear = BG

machine.Pin.board.BUTTON_HOME.irq(handler=None, trigger=0)

run(update)
