import os
import sys

sys.path.insert(0, "/system/apps/menu")
sys.path.insert(0, "/")
os.chdir("/system/apps/menu")

badge.mode(HIRES | VSYNC)
previous_clear = badge.default_clear
badge.default_clear = color.rgb(0, 0, 0)

import ui

from app import TILES_PER_ROW, Apps
from opening import Opening, after_cold_boot

try:
    from mona import MenuMona
    mona = MenuMona()
except (ImportError, OSError):
    mona = None

screen.antialias = image.X2
screen.fill_rule = image.NON_ZERO

apps = Apps("/system/apps")
tilt = ui.Tilt()
opening = Opening(apps) if after_cold_boot() else None

FADE_STEP = 30
fade = 0 if opening is None else 255


def restore():
    badge.default_clear = previous_clear
    badge.mode(LORES | VSYNC)


def update():
    global fade, opening

    if opening is not None:
        opening.advance()
        if opening.skippable() and badge.buttons.pressed():
            opening.finish()
        if opening.done:
            opening = None

    if badge.pressed(BUTTON_RIGHT):
        apps.move(1)
    if badge.pressed(BUTTON_LEFT):
        apps.move(-1)
    if badge.pressed(BUTTON_DOWN):
        apps.move(TILES_PER_ROW)
    if badge.pressed(BUTTON_UP):
        apps.move(-TILES_PER_ROW)

    if badge.pressed(BUTTON_SELECT):
        restore()
        return apps.active.path

    if mona is not None:
        mona.look_at(*apps.active_centre())
        mona.prepare(opening.mona_lift() if opening else 0.0)

    ribbon_hidden = 0.0
    if opening is not None:
        level = opening.background_level()
        if level > 0:
            screen.pen = color.rgb(level, level, level)
            screen.clear()
        ribbon_hidden = opening.ribbon_hidden()

    tilt.update()
    apps.draw(tilt, opening)
    ui.draw_status(apps.active_index, len(apps), ribbon_hidden)
    ui.draw_title(apps.active.name, apps.changed_at, ribbon_hidden)

    if mona is not None:
        mona.render()

    if fade < 255:
        screen.pen = color.rgb(0, 0, 0, 255 - fade)
        screen.rectangle(0, 0, screen.width, screen.height)
        fade += FADE_STEP

    return None


on_exit = run(update).result
