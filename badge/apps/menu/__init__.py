import os
import sys

sys.path.insert(0, "/system/apps/menu")
sys.path.insert(0, "/")
os.chdir("/system/apps/menu")

import ui

from app import Apps

title_font = font.ark
label_font = font.sins


# find installed apps and create apps
apps = Apps("/system/apps")

active = 0

MAX_ALPHA = 255
alpha = 30


def update():
    global active, apps, alpha

    # process button inputs to switch between apps
    if badge.pressed(BUTTON_RIGHT):
        if (active % 3) < 2 and active < len(apps) - 1:
            active += 1
    if badge.pressed(BUTTON_LEFT):
        if (active % 3) > 0 and active > 0:
            active -= 1
    if badge.pressed(BUTTON_UP) and active >= 3:
        active -= 3
    if badge.pressed(BUTTON_DOWN):
        active += 3
        if active >= len(apps):
            active = len(apps) - 1

    apps.activate(active)

    if badge.pressed(BUTTON_SELECT):
        return apps.active.path

    ui.draw_background()

    screen.font = title_font
    ui.draw_header()

    # draw menu apps
    apps.draw_icons()

    # draw label for active menu icon
    screen.font = label_font
    apps.draw_label()

    # draw hints for the active page
    apps.draw_pagination()

    if alpha <= MAX_ALPHA:
        screen.pen = color.rgb(0, 0, 0, 255 - alpha)
        screen.rectangle(screen.clip)
        alpha += 30

    return None

# "on_exit" will be called if callable, else returned verbatim by `launch`
on_exit = run(update).result
