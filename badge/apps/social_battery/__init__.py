import os
import sys

APP_DIR = "/system/apps/social_battery"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

from badgeware import State

BACKGROUND = color.rgb(13, 17, 23)
FRAME = color.rgb(216, 228, 239)
EMPTY = color.rgb(37, 49, 64)
WHITE = color.rgb(250, 252, 255)
MUTED = color.rgb(166, 183, 199)
COLORS = (
    color.rgb(255, 115, 129),
    color.rgb(255, 184, 104),
    color.rgb(250, 213, 106),
    color.rgb(116, 225, 177),
)

state = {"level": 60}
State.load("social_battery", state)
level = state["level"]
if type(level) is not int or level < 0 or level > 100 or level % 10:
    print("Social Battery: invalid saved level; resetting to 60")
    state["level"] = 60


def mood():
    level = state["level"]
    if level == 0:
        return "RECHARGING", "Not up for chatting now", COLORS[0]
    if level < 20:
        return "NEED A BREAK", "I may step away soon", COLORS[0]
    if level < 40:
        return "RUNNING LOW", "Please keep it brief", COLORS[1]
    if level < 70:
        return "GOING STEADY", "I may take a pause", COLORS[2]
    return "READY TO CONNECT", "Chats feel good today", COLORS[3]


def center_text(text, y):
    width, _ = screen.measure_text(text)
    screen.text(text, (screen.width - width) // 2, y)


def update():
    up = badge.pressed(BUTTON_UP)
    down = badge.pressed(BUTTON_DOWN)
    if up != down:
        level = state["level"]
        state["level"] = min(100, level + 10) if up else max(0, level - 10)
        if state["level"] != level:
            State.save("social_battery", state)

    heading, message, energy = mood()
    screen.pen = BACKGROUND
    screen.rectangle(screen.clip)

    screen.font = font.ziplock
    screen.pen = WHITE
    center_text("SOCIAL BATTERY", 6)

    x = (screen.width - 136) // 2
    y = (screen.height - 120) // 2 + 26
    screen.pen = FRAME
    screen.rectangle(x, y, 128, 45)
    screen.rectangle(x + 128, y + 13, 8, 19)
    screen.pen = BACKGROUND
    screen.rectangle(x + 3, y + 3, 122, 39)

    for cell in range(10):
        screen.pen = energy if cell < state["level"] // 10 else EMPTY
        screen.rectangle(x + 6 + cell * 12, y + 6, 10, 33)

    label = "%d%%" % state["level"]
    label_width, label_height = screen.measure_text(label)
    label_x = (screen.width - label_width) // 2
    screen.pen = BACKGROUND
    screen.rectangle(label_x - 3, y + 12, label_width + 6, label_height + 5)
    screen.pen = WHITE
    screen.text(label, label_x, y + 15)

    screen.font = font.nope
    screen.pen = energy
    center_text(heading, y + 51)
    screen.pen = WHITE
    center_text(message, y + 64)
    screen.pen = MUTED
    center_text("UP +10    DOWN -10", y + 76)


run(update)
