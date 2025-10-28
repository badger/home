import sys
import os

sys.path.insert(0, "/system/apps/flappy")
os.chdir("/system/apps/flappy")

from badgeware import screen, Image, PixelFont, SpriteSheet, io, brushes, shapes, run
from mona import Mona
from obstacle import Obstacle

background = Image.load("assets/background.png")
grass = Image.load("assets/grass.png")
cloud = Image.load("assets/cloud.png")
large_font = PixelFont.load("/system/assets/fonts/ziplock.ppf")
small_font = PixelFont.load("/system/assets/fonts/nope.ppf")
ghost = SpriteSheet("/system/assets/mona-sprites/mona-dead.png", 7, 1).animation()
mona = None


class GameState:
    INTRO = 1
    PLAYING = 2
    GAME_OVER = 3


state = GameState.INTRO


def update():
    draw_background()

    if state == GameState.INTRO:
        intro()

    if state == GameState.PLAYING:
        play()

    if state == GameState.GAME_OVER:
        game_over()


# handle the intro screen of the game, shows the game title and a message to
# tell the player how to start the game


def intro():
    global state, mona

    # draw title
    screen.font = large_font
    center_text("FLAPPY MONA", 38)

    # blink button message
    if int(io.ticks / 500) % 2:
        screen.font = small_font
        center_text("Press A to start", 70)

    if io.BUTTON_A in io.pressed:
        # reset game state
        state = GameState.PLAYING
        Obstacle.obstacles = []
        Obstacle.next_spawn_time = io.ticks + 500
        mona = Mona()

# handle the main game loop and user input. each tick we'll update the game
# state (read button input, move mona, create new obstacles, etc..) then
# draw the background and sprites


def play():
    global state

    # if the user has pressed A then make mona jump for her life!
    if not mona.is_dead() and io.BUTTON_A in io.pressed:
        mona.jump()

    # update player and check for collision
    mona.update()

    # spawn a new obstacle if the spawn timer has elapsed
    if not mona.is_dead() and Obstacle.next_spawn_time and io.ticks > Obstacle.next_spawn_time:
        Obstacle.spawn()

    # update obstacle positions and draw them
    for obstacle in Obstacle.obstacles:
        if not mona.is_dead():
            obstacle.update()
        obstacle.draw()

    # draw our hero, mona
    mona.draw()

    # show the player their current score
    screen.font = small_font
    shadow_text(f"Score: {mona.score}", 3, 0)

    # has mona died this frame? if so it's... GAME OVER
    if mona.is_dead():
        if mona.is_done_dying():
            state = GameState.GAME_OVER

# handle the GAME OVER screen. show the player what score they achieved and
# provide instructions for how to start again


def game_over():
    global state

    # game over caption
    screen.font = large_font
    center_text("GAME OVER!", 18)

    # players final score
    screen.font = small_font
    center_text(f"Final score: {mona.score}", 40)

    # flash press button message
    if int(io.ticks / 500) % 2:
        screen.brush = brushes.color(255, 255, 255)
        center_text("Press A to restart", 70)

    if io.BUTTON_A in io.pressed:
        # return game to intro state
        state = GameState.INTRO


# draw the scrolling background with parallax layers
background_offset = 0


def draw_background():
    global background_offset

    # clear the whole screen in a bright blue
    screen.brush = brushes.color(73, 219, 255)
    screen.draw(shapes.rectangle(0, 0, 160, 120))

    # if we're on the intro screen or mona is alive then scroll the background
    if not mona or not mona.is_dead() or state == GameState.INTRO:
        background_offset += 1

    for i in range(3):
        # draw the distance background
        bo = ((-background_offset / 8) % background.width) - screen.width
        screen.blit(background, bo + (background.width * i),
                    120 - background.height)

        # draw the cloud background
        bo = ((-background_offset / 8) % (cloud.width * 2)) - screen.width
        screen.blit(cloud, bo + (cloud.width * 2 * i), 20)

    for i in range(3):
        # draw the grass layer
        bo = ((-background_offset / 4) % (grass.width)) - screen.width
        screen.blit(grass, bo + (grass.width * i), 120 - grass.height)

# a couple of helper functions for formatting text


def shadow_text(text, x, y):
    screen.brush = brushes.color(20, 40, 60, 100)
    screen.text(text, x + 1, y + 1)
    screen.brush = brushes.color(255, 255, 255)
    screen.text(text, x, y)


def center_text(text, y):
    w, _ = screen.measure_text(text)
    shadow_text(text, 80 - (w / 2), y)


if __name__ == "__main__":
    run(update)
