import os
import sys

APP_DIRS = ("/remote/apps/super_mona", "/system/apps/super_mona", "/apps/super_mona", "/super_mona")
APP_DIR = next(path for path in APP_DIRS if is_dir(path))
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

badge.mode(LORES | VSYNC)
screen.antialias = image.OFF
screen.fill_rule = image.EVEN_ODD

from badgeware import State
import game
from levels import LEVELS
import render
from render import Renderer, centre, text, hero_sprite, item_sprite, item_name

TITLE, INTRO, PLAY, PAUSE, OVER, WIN = range(6)
PAGES = ("PAUSED", "MAP", "ITEMS", "HERO")

saved = {"high": 0}
State.load("super_mona", saved)

state = TITLE
state_time = 0.0
session = None
world = None
view = None
controls = game.Controls()
page = 0
cursor = 0
title_level = LEVELS[0]()
title_view = Renderer(title_level)


def down(button):
    return badge.held(button) or badge.pressed(button)


def read_controls():
    c = controls
    c.left = down(BUTTON_LEFT)
    c.right = down(BUTTON_RIGHT)
    c.up = down(BUTTON_UP)
    c.down = down(BUTTON_DOWN)
    c.jump_pressed = badge.pressed(BUTTON_SELECT)
    c.jump = down(BUTTON_SELECT)
    c.run = down(BUTTON_BACK)
    return c


def set_state(new):
    global state, state_time
    state = new
    state_time = 0.0


def save_high():
    if session and session.high > saved["high"]:
        saved["high"] = session.high
        State.save("super_mona", saved)


def new_game():
    global session
    session = game.Session(saved["high"])
    start_level()


def start_level():
    global world, view
    world = None
    view = None
    level = LEVELS[session.level]()
    view = Renderer(level)
    world = game.World(level, session)
    session.events = []
    set_state(INTRO)


def panel(y, h):
    screen.pen = render.PANEL
    screen.rectangle(8, y, 144, h)


def hints(msg):
    screen.font = render.HUD_FONT
    centre(msg, 108, render.GOLD)


# States ------------------------------------------------------------------
def draw_title(t):
    title_view.draw(title_world, t)
    centre("SUPER MONA", 22, render.GOLD, render.TITLE_FONT)
    screen.font = render.HUD_FONT
    centre("HIGH %06d" % saved["high"], 44)
    if int(t * 2) % 2:
        centre("PRESS A TO START", 84)
    if badge.pressed(BUTTON_SELECT):
        new_game()


def draw_intro(t):
    screen.pen = render.BLACK
    screen.clear()
    centre(world.level.name, 34, render.WHITE, render.TITLE_FONT)
    screen.blit(hero_sprite(session.character, session.big), vec2(62, 58))
    screen.font = render.HUD_FONT
    text("x %d" % session.lives, 84, 62)
    if world.level.switch:
        centre("SWAP HERO IN MENU", 92, render.GOLD)
    if t > 2.0 or (t > 0.4 and badge.pressed(BUTTON_SELECT)):
        set_state(PLAY)


def play(dt, t):
    global page, cursor
    if badge.pressed(BUTTON_MENU) and world.state == "play":
        page = 0
        cursor = 0
        set_state(PAUSE)
        return draw_paused(t)
    world.step(dt, read_controls())
    view.draw(world, t)
    view.draw_hud(world)
    if world.state == "dead":
        session.lives -= 1
        save_high()
        if session.lives > 0:
            start_level()
        else:
            set_state(OVER)
    elif world.state == "clear":
        save_high()
        session.level += 1
        if session.level >= len(LEVELS):
            set_state(WIN)
        else:
            start_level()
    del session.events[:]


def draw_paused(t):
    global page, cursor, state
    view.draw(world, t)
    view.draw_hud(world)
    screen.pen = render.DIM
    screen.rectangle(0, 10, 160, 110)
    if badge.pressed(BUTTON_LEFT):
        page = (page - 1) % len(PAGES)
    if badge.pressed(BUTTON_RIGHT):
        page = (page + 1) % len(PAGES)
    screen.font = render.HUD_FONT
    x = 6
    for i, name in enumerate(PAGES):
        w, _ = screen.measure_text(name)
        text(name, x, 14, render.GOLD if i == page else render.WHITE)
        x += w + 10
    name = PAGES[page]
    if name == "PAUSED":
        panel(30, 70)
        centre(world.level.name, 36)
        centre("SCORE %06d" % session.score, 50)
        centre("HIGH  %06d" % max(session.high, saved["high"]), 62)
        centre("HOME TO QUIT", 80, render.GOLD)
    elif name == "MAP":
        panel(30, 70)
        centre(world.level.name, 34)
        view.draw_map(world, 12, 50, 136, 45)
    elif name == "ITEMS":
        panel(30, 70)
        inv = session.inventory
        if not inv:
            centre("NO ITEMS YET", 50)
            centre("SPARE CHIPS GO HERE", 66)
        else:
            if badge.pressed(BUTTON_UP):
                cursor = (cursor - 1) % len(inv)
            if badge.pressed(BUTTON_DOWN):
                cursor = (cursor + 1) % len(inv)
            cursor = min(cursor, len(inv) - 1)
            for i, kind in enumerate(inv):
                y = 36 + i * 16
                screen.blit(item_sprite(kind), vec2(30, y + 2))
                text(item_name(kind), 44, y, render.GOLD if i == cursor else render.WHITE)
                if i == cursor:
                    text(">", 20, y, render.GOLD)
            if badge.pressed(BUTTON_SELECT) and world.use_item(cursor):
                set_state(PLAY)
                return
    else:
        panel(30, 70)
        for i, who in enumerate(game.CHARACTER_ORDER):
            x = 34 + i * 60
            screen.blit(hero_sprite(who, session.big), vec2(x + 8, 38))
            pen = render.GOLD if who == world.player.character else render.WHITE
            screen.font = render.HUD_FONT
            text(game.CHARACTERS[who]["name"], x + 4, 56, pen)
        centre(game.CHARACTERS[world.player.character]["about"], 70)
        if world.level.switch:
            centre("A: SWAP HERO", 84, render.GOLD)
            if badge.pressed(BUTTON_SELECT):
                world.switch_character()
        else:
            centre("NO SWAP ON THIS STAGE", 84)
    hints("< > PAGE   MENU/B RESUME")
    # state_time is 0 on the frame Menu opened the pause screen; ignore that press.
    if state_time > 0 and (badge.pressed(BUTTON_MENU) or badge.pressed(BUTTON_BACK)):
        set_state(PLAY)


def draw_end(t, title):
    screen.pen = render.BLACK
    screen.clear()
    centre(title, 30, render.GOLD, render.TITLE_FONT)
    screen.font = render.HUD_FONT
    centre("SCORE %06d" % session.score, 56)
    centre("HIGH  %06d" % saved["high"], 68)
    if t > 1.0 and int(t * 2) % 2:
        centre("PRESS A", 92)
    if t > 1.0 and badge.pressed(BUTTON_SELECT):
        set_state(TITLE)


title_session = game.Session()
title_world = game.World(title_level, title_session)


def update():
    global state_time
    dt = min(badge.ticks_delta, 50) / 1000
    state_time += dt
    t = badge.ticks / 1000
    if state == TITLE:
        draw_title(t)
    elif state == INTRO:
        draw_intro(state_time)
    elif state == PLAY:
        play(dt, t)
    elif state == PAUSE:
        draw_paused(t)
    elif state == OVER:
        draw_end(state_time, "GAME OVER")
    else:
        draw_end(state_time, "YOU WIN!")


def on_exit():
    save_high()


run(update)
