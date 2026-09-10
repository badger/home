import os
import sys

APP_DIRS = ("/remote/apps/monapet", "/system/apps/monapet", "/apps/monapet", "/monapet")
APP_DIR = next(path for path in APP_DIRS if is_dir(path))
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

from badgeware import State
from mona import Mona
import ui

HAPPINESS_DURATION = 1800
HUNGER_DURATION = 1200
CLEANLINESS_DURATION = 2400

screen.antialias = image.X2
mona = Mona(95)


def load_state():
    state = {"happy": 100, "hunger": 100, "clean": 100}
    if State.load("monapet", state):
        mona.load(state)


def game_update():
    global mona

    if mona.is_dead():
        mona.set_mood("dead")
        mona.set_speed(20)
        mona.unset_notify()
        mona.move_to_center()
        if badge.pressed(BUTTON_SELECT):
            mona = Mona(95)
        return

    seconds = badge.ticks_delta / 1000
    mona.happy(-(seconds / HAPPINESS_DURATION) * 100)
    mona.hunger(-(seconds / HUNGER_DURATION) * 100)
    mona.clean(-(seconds / CLEANLINESS_DURATION) * 100)

    if badge.pressed(BUTTON_LEFT):
        mona.happy(30)
        mona.unset_notify()
        mona.do_action("heart")
    if badge.pressed(BUTTON_RIGHT):
        mona.hunger(30)
        mona.unset_notify()
        mona.do_action("eating")
    if badge.pressed(BUTTON_SELECT):
        mona.clean(30)
        mona.unset_notify()
        mona.do_action("dance")

    if mona.time_since_last_position_change() > 5:
        mona.move_to_random()
    if mona.time_since_last_mood_change() > 8:
        mona.random_idle()
    if min(mona.hunger(), mona.happy(), mona.clean()) < 30:
        mona.set_notify()


def update():
    game_update()
    mona.update()
    ui.background()
    mona.draw()
    ui.draw(mona)


def on_exit():
    State.save("monapet", mona.save())


load_state()
run(update)
