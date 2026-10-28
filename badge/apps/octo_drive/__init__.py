import os
import sys

APP_DIRS = ("/remote/apps/octo_drive", "/system/apps/octo_drive", "/apps/octo_drive", "/octo_drive")
APP_DIR = next(path for path in APP_DIRS if is_dir(path))
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

badge.mode(LORES | VSYNC)
screen.antialias = image.OFF
screen.fill_rule = image.EVEN_ODD

from badgeware import State
import game
from game import Controls, World
import render
from render import Renderer, centre, text

TITLE, COUNTDOWN, PLAY, PAUSE, OVER, WIN = range(6)

saved = {"high": 0, "best": 0}
State.load("octo_drive", saved)

state = TITLE
state_time = 0.0
world = None
controls = Controls()
view = Renderer()


def down(button):
    return badge.held(button) or badge.pressed(button)


def read_controls():
    controls.left = down(BUTTON_LEFT)
    controls.right = down(BUTTON_RIGHT)
    controls.accelerate = down(BUTTON_SELECT) or down(BUTTON_UP)
    controls.brake = down(BUTTON_BACK) or down(BUTTON_DOWN)
    return controls


def set_state(new_state):
    global state, state_time
    state = new_state
    state_time = 0.0


def save_results():
    if world is None:
        return
    changed = False
    if world.session.high > saved["high"]:
        saved["high"] = world.session.high
        changed = True
    if world.session.best_time is not None:
        millis = int(world.session.best_time * 1000)
        if saved["best"] == 0 or millis < saved["best"]:
            saved["best"] = millis
            changed = True
    if changed:
        State.save("octo_drive", saved)


def new_game():
    global world
    world = World(saved["high"])
    set_state(COUNTDOWN)


def panel(y, height):
    screen.pen = render.PANEL
    screen.rectangle(8, y, 144, height)


def draw_title(t):
    view.draw_attract(t)
    screen.pen = render.DIM
    screen.rectangle(0, 0, 160, 120)
    centre("OCTO DRIVE", 20, render.GOLD, render.TITLE_FONT)
    centre("ARCADE ROAD RALLY", 43)
    centre("HIGH %06d" % saved["high"], 58)
    if saved["best"]:
        centre("BEST %.1fs" % (saved["best"] / 1000), 70)
    if int(t * 2) & 1:
        centre("PRESS A", 91, render.GOLD)
    centre("A GAS  B BRAKE", 106)
    if badge.pressed(BUTTON_SELECT):
        new_game()


def draw_countdown(t):
    view.draw(world, t)
    view.draw_hud(world)
    number = 3 - int(state_time)
    if number > 0:
        centre(str(number), 49, render.GOLD, render.TITLE_FONT)
    else:
        centre("GO!", 49, render.GOLD, render.TITLE_FONT)
    if state_time >= 3.4:
        set_state(PLAY)


def draw_play(dt, t):
    if badge.pressed(BUTTON_MENU):
        set_state(PAUSE)
        return draw_pause(t)
    world.step(dt, read_controls())
    view.draw(world, t)
    view.draw_hud(world)
    if world.state == "time_up":
        save_results()
        set_state(OVER)
    elif world.state == "finished":
        save_results()
        set_state(WIN)
    del world.events[:]


def draw_pause(t):
    view.draw(world, t)
    view.draw_hud(world)
    screen.pen = render.DIM
    screen.rectangle(0, 10, 160, 110)
    panel(29, 68)
    centre("PAUSED", 36, render.GOLD, render.TITLE_FONT)
    centre(world.section, 58)
    view.draw_progress(world)
    centre("MENU/B RESUME", 105)
    if state_time > 0 and (badge.pressed(BUTTON_MENU) or badge.pressed(BUTTON_BACK)):
        set_state(PLAY)


def draw_end(t, won):
    view.draw(world, t)
    screen.pen = render.DIM
    screen.rectangle(0, 0, 160, 120)
    panel(18, 83)
    centre("FINISH!" if won else "TIME UP", 25, render.GOLD, render.TITLE_FONT)
    centre("SCORE %06d" % world.session.score, 51)
    centre("HIGH  %06d" % saved["high"], 63)
    if won:
        centre("TIME %.1fs" % world.session.best_time, 75)
    view.draw_progress(world, 18, 87, 124)
    if state_time > 0.8 and int(t * 2) & 1:
        centre("PRESS A", 105)
    if state_time > 0.8 and badge.pressed(BUTTON_SELECT):
        set_state(TITLE)


def update():
    global state_time
    dt = min(badge.ticks_delta, 50) / 1000
    state_time += dt
    t = badge.ticks / 1000
    if state == TITLE:
        draw_title(t)
    elif state == COUNTDOWN:
        draw_countdown(t)
    elif state == PLAY:
        draw_play(dt, t)
    elif state == PAUSE:
        draw_pause(t)
    elif state == OVER:
        draw_end(t, False)
    else:
        draw_end(t, True)


def on_exit():
    save_results()


run(update)

