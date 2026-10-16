import os
import sys

APP_DIR = "/system/apps/flappy"

os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

from badgeware import State
from mona import Mona
from obstacle import Obstacle

background = image.load("assets/background.png")
grass = image.load("assets/grass.png")
cloud = image.load("assets/cloud.png")
large_font = font.ziplock
small_font = font.nope
mona = None

score = {
    "highscore": 0
}

State.load("flappy_mona", score)


class GameState:
    INTRO = 1
    PLAYING = 2
    GAME_OVER = 3


state = GameState.INTRO
background_offset = 0


def update():
    draw_background()

    if state == GameState.INTRO:
        intro()
    elif state == GameState.PLAYING:
        play()
    else:
        game_over()


def reset_state():
    global state, mona

    state = GameState.PLAYING
    Obstacle.obstacles = []
    Obstacle.next_spawn_time = badge.ticks + 500
    mona = Mona()

    # Give the player a moment to react instead of dropping immediately.
    mona.jump()


def intro():
    screen.font = large_font
    center_text("FLAPPY MONA", 38)

    screen.font = small_font
    center_text("High Score: %d" % score["highscore"], 56)

    if int(badge.ticks / 500) % 2:
        center_text("Press SELECT to start", 80)

    if badge.pressed(BUTTON_SELECT):
        reset_state()


def play():
    global state

    if not mona.is_dead() and badge.pressed(BUTTON_SELECT):
        mona.jump()

    mona.update()

    if (
        not mona.is_dead()
        and Obstacle.next_spawn_time
        and badge.ticks > Obstacle.next_spawn_time
    ):
        Obstacle.spawn()

    for obstacle in Obstacle.obstacles:
        if not mona.is_dead():
            obstacle.update()
        obstacle.draw()

    mona.draw()

    screen.font = small_font
    shadow_text("Score: %d" % mona.score, 3, 0)

    if mona.is_dead() and mona.is_done_dying():
        state = GameState.GAME_OVER


def game_over():
    if mona.score > score["highscore"]:
        score["highscore"] = mona.score
        State.save("flappy_mona", score)

    screen.font = large_font
    center_text("GAME OVER!", 18)

    screen.font = small_font
    center_text("Final Score: %d" % mona.score, 40)
    center_text("High Score: %d" % score["highscore"], 56)

    if int(badge.ticks / 500) % 2:
        center_text("Press SELECT to restart", 80)

    if badge.pressed(BUTTON_SELECT):
        reset_state()


def draw_background():
    global background_offset

    screen.pen = color.rgb(73, 219, 255)
    screen.shape(shape.rectangle(0, 0, screen.width, screen.height))

    if mona is None or not mona.is_dead() or state == GameState.INTRO:
        background_offset += 30 * (badge.ticks_delta / 1000)

    for i in range(3):
        offset = ((-background_offset / 8) % background.width) - screen.width
        screen.blit(
            background,
            vec2(offset + background.width * i, screen.height - background.height),
        )

        offset = ((-background_offset / 8) % (cloud.width * 2)) - screen.width
        screen.blit(cloud, vec2(offset + cloud.width * 2 * i, 20))

    for i in range(3):
        offset = ((-background_offset / 4) % grass.width) - screen.width
        screen.blit(
            grass,
            vec2(offset + grass.width * i, screen.height - grass.height),
        )


def shadow_text(text, x, y):
    screen.pen = color.rgb(20, 40, 60, 100)
    screen.text(text, x + 1, y + 1)
    screen.pen = color.rgb(255, 255, 255)
    screen.text(text, x, y)


def center_text(text, y):
    width, _ = screen.measure_text(text)
    shadow_text(text, (screen.width - width) / 2, y)


run(update)
