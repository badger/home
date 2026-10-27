"""John Maeda's 12 o'clocks, via the CodingTrain p5.js interpretations."""

import os
import sys
import time
import gc
from badgeware import State

APP_DIR = "/system/apps/twelve_clocks"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

from clockwork import NAMES, Timing, selected_index
from faces import Face

state = {"face": 0}
notice = ""
try:
    State.load("twelve_clocks", state)
except (OSError, ValueError) as error:
    print("12 o'clocks: cannot load selection:", error)
    notice = "Selection unavailable"
index = selected_index(state.get("face"))
if index != state.get("face") or type(state.get("face")) is not int:
    print("12 o'clocks: invalid selection; using Pendulum")
    notice = "Selection reset"
state["face"] = index

previous_clear = badge.default_clear
previous_antialias = screen.antialias
previous_fill_rule = screen.fill_rule
previous_font = screen.font
badge.mode(HIRES | VSYNC)
badge.default_clear = None
screen.antialias = image.X2
screen.fill_rule = image.EVEN_ODD

face = Face(index)
timing = Timing(index)
menu_open = False
cursor = index
redraw = True
save_pending = False
save_wait = 0
closed = False
rtc_valid = True


def save_selection():
    global save_pending, notice
    if not save_pending:
        return
    try:
        State.save("twelve_clocks", state)
        notice = ""
    except OSError as error:
        print("12 o'clocks: cannot save selection:", error)
        notice = "Selection not saved"
    save_pending = False


def choose(value):
    global face, timing, index, cursor, redraw, save_pending, save_wait
    value %= len(NAMES)
    if value != index:
        face = None
        gc.collect()
        index = value
        face = Face(index)
        timing = Timing(index)
        state["face"] = index
        save_pending = True
        save_wait = 0
    cursor = index
    redraw = True


def draw_menu():
    screen.pen = color.rgb(0, 0, 0)
    screen.clear()
    screen.font = font.sins
    screen.pen = color.rgb(255, 255, 255)
    screen.text("12 o'clocks", 12, 8)
    # One list, all twelve visible; no running preview faces.
    for i, name in enumerate(NAMES):
        y = 30 + i * 15
        if i == cursor:
            screen.pen = color.rgb(255, 255, 255)
            screen.rectangle(8, y - 1, screen.width - 16, 15)
        screen.pen = color.rgb(0, 0, 0) if i == cursor else color.rgb(190, 190, 190)
        screen.text("%02d  %s%s" % (i + 1, name, " *" if i == index else ""), 12, y)
    screen.pen = color.rgb(190, 190, 190)
    screen.text(notice or ("RTC unset: use Clock app" if not rtc_valid
                          else "Up/Down: choose  Select: run"), 12, screen.height - 22)


def update():
    global menu_open, cursor, redraw, save_wait, rtc_valid
    delta = max(0, badge.ticks_delta)
    if save_pending:
        save_wait += delta
        if save_wait >= 800:
            save_selection()
            redraw = True
    if badge.pressed(BUTTON_MENU):
        menu_open = not menu_open
        cursor = index
        redraw = True
    elif menu_open:
        if badge.pressed(BUTTON_UP):
            cursor = (cursor - 1) % len(NAMES)
            redraw = True
        if badge.pressed(BUTTON_DOWN):
            cursor = (cursor + 1) % len(NAMES)
            redraw = True
        if badge.pressed(BUTTON_SELECT):
            choose(cursor)
            menu_open = False
        elif badge.pressed(BUTTON_BACK):
            menu_open = False
            redraw = True
    else:
        if badge.pressed(BUTTON_LEFT):
            choose(index - 1)
        elif badge.pressed(BUTTON_RIGHT):
            choose(index + 1)
    now = time.time()
    local = time.localtime(now)
    rtc_valid = local[0] >= 2025
    if menu_open:
        if redraw:
            draw_menu()
            redraw = False
        return
    blink = (badge.ticks // 500) % 2 == 0
    if timing.advance(delta, now, blink, redraw):
        face.draw(local[3], local[4], local[5], now, timing.phase, blink)
        if notice or not rtc_valid:
            screen.font = font.sins
            screen.pen = color.rgb(0, 0, 0)
            screen.rectangle(0, screen.height - 16, screen.width, 16)
            screen.pen = color.rgb(255, 255, 255)
            screen.text(notice or "RTC unset: use Clock app", 6, screen.height - 14)
        redraw = False


def on_exit():
    global face, closed
    if closed:
        return
    closed = True
    save_selection()
    face = None
    badge.default_clear = previous_clear
    screen.antialias = previous_antialias
    screen.fill_rule = previous_fill_rule
    screen.font = previous_font
    if APP_DIR in sys.path:
        sys.path.remove(APP_DIR)
    gc.collect()


run(update)
