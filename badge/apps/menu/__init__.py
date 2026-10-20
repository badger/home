import os
import sys

sys.path.insert(0, "/system/apps/menu")
sys.path.insert(0, "/")
os.chdir("/system/apps/menu")

badge.mode(HIRES)
display.set_async(True)
previous_clear = badge.default_clear
badge.default_clear = color.rgb(0, 0, 0)

import ui

from app import shared as shared_apps
from achievements import draw_marquee
from celebration import Celebration
from gallery import Viewer, prefetch
from opening import Opening, after_cold_boot

try:
    import sparkle
except ImportError:
    sparkle = None

try:
    from mona import shared as shared_mona
    mona = shared_mona()
except (ImportError, OSError):
    mona = None

screen.antialias = image.X2
screen.fill_rule = image.NON_ZERO

apps = shared_apps("/system/apps")
apps.achievements.listen()
tilt = ui.Tilt()
opening = Opening(apps) if after_cold_boot() else None

FADE_STEP = 30
IDLE_MS = 600
fade = 0 if opening is None else 255
viewer = None
celebration = None


def resume_sparkle():
    if sparkle is not None:
        sparkle.resume()


def restore():
    resume_sparkle()
    apps.achievements.close()
    badge.default_clear = previous_clear
    display.set_async(False)
    badge.mode(LORES | VSYNC)


def update():
    global fade, opening, viewer, celebration

    if opening is not None:
        opening.advance()
        if opening.skippable() and badge.buttons.pressed():
            opening.finish()
        if opening.done:
            opening = None

    if apps.achievements.pending is not None:
        viewer = None
        if apps.picker is not None:
            apps.picker.close()
        apps.select(apps.achievements_tile.index)
        left, top, width, height = apps.achievements_tile.bounds(apps.scroll)
        celebration = Celebration(apps.achievements.pending, (left + width / 2, top + height / 2))
        apps.achievements.pending = None

    picker = apps.picker
    if celebration is not None:
        if badge.pressed():
            celebration.dismiss()
        if celebration.done:
            celebration = None
    elif viewer is not None:
        if badge.pressed():
            viewer.close()
        if viewer.done:
            viewer = None
    elif picker is not None and picker.is_open:
        if badge.pressed(BUTTON_RIGHT):
            picker.move(1)
        if badge.pressed(BUTTON_LEFT):
            picker.move(-1)
        if badge.pressed(BUTTON_SELECT) and picker.choose():
            picker.close()
        if badge.pressed(BUTTON_BACK) or badge.pressed(BUTTON_UP):
            picker.close()
    else:
        if badge.pressed(BUTTON_RIGHT):
            apps.move(1)
        if badge.pressed(BUTTON_LEFT):
            apps.move(-1)
        if badge.pressed(BUTTON_DOWN):
            apps.move_vertical(1)
        if badge.pressed(BUTTON_UP):
            apps.move_vertical(-1)

        if badge.pressed(BUTTON_SELECT):
            if apps.active is apps.achievements_tile:
                apps.open_picker()
            elif apps.active.path is None:
                viewer = Viewer(apps.active, apps.scroll, tilt)
            else:
                restore()
                return apps.active.path

    active = apps.active
    if viewer is None and celebration is None and active.path is None and active is not apps.achievements_tile:
        prefetch(active.slug, apps.changed_at)
    if opening is None and viewer is None and celebration is None:
        apps.load_photos(badge.ticks - apps.changed_at >= IDLE_MS)

    if viewer is not None and viewer.covering:
        viewer.draw()
        return None

    if mona is not None:
        mona.look_at(*(celebration.look_target() if celebration is not None else apps.active_centre()))
        mona.prepare(opening.mona_lift() if opening else 0.0)

    if celebration is not None and celebration.covering:
        tilt.update()
        celebration.draw_back(tilt)
        if mona is not None:
            mona.render()
        celebration.draw_front()
        return None

    ribbon_hidden = 0.0
    if opening is not None:
        level = opening.background_level()
        if level > 0:
            screen.pen = color.rgb(level, level, level)
            screen.clear()
        ribbon_hidden = opening.ribbon_hidden()

    tilt.update()
    apps.draw(tilt, opening, viewer.target() if viewer is not None else None)
    ui.draw_status(apps.active_index, len(apps), ribbon_hidden)
    message = picker.message() if picker is not None and picker.is_open else None
    if message is not None:
        draw_marquee(*message)
    elif picker is not None and picker.is_open:
        ui.draw_title(picker.title(), picker.changed_at, ribbon_hidden)
    else:
        ui.draw_title(apps.active.name, apps.changed_at, ribbon_hidden)

    if celebration is not None:
        celebration.draw_back(tilt)

    if mona is not None:
        mona.render()

    if celebration is not None:
        celebration.draw_front()

    if viewer is not None:
        viewer.draw()

    if fade < 255:
        screen.pen = color.rgb(0, 0, 0, 255 - fade)
        screen.rectangle(0, 0, screen.width, screen.height)
        fade += FADE_STEP

    if opening is None and fade >= 255:
        resume_sparkle()

    return None


on_exit = run(update).result
