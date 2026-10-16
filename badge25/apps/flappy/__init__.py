import sys
import os

sys.path.insert(0, "/system/apps/flappy")
os.chdir("/system/apps/flappy")

from badgeware import screen, Image, PixelFont, SpriteSheet, io, brushes, shapes, run, State
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

# High score tracking
high_score = 0
new_high_score_achieved = False

# Load high score from persistent storage
try:
    wrap = {"hiscore": 0}
    State.load("flappy_hiscore", wrap)
    high_score = int(wrap.get("hiscore", 0))
except Exception:
    # Ignore errors loading high score (e.g., file missing or corrupt); use default of 0.
    pass


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

    if high_score > 0:
        # show high score on intro screen
        screen.font = small_font
        center_text(f"High Score: {high_score}", 56)

    # blink button message
    if int(io.ticks / 500) % 2:
        screen.font = small_font
        center_text("Press A to start", 80)

    if io.BUTTON_A in io.pressed:
        # reset game state
        global new_high_score_achieved
        state = GameState.PLAYING
        new_high_score_achieved = False
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
    global state, high_score, new_high_score_achieved

    # check if current score beats high score (only on first entry to game over)
    if mona.score > high_score:
        new_high_score_achieved = True
        high_score = mona.score
        try:
            State.save("flappy_hiscore", {"hiscore": high_score})
        except Exception:
            # Ignore errors saving high score (e.g., file system full or read-only).
            pass

    # game over caption
    screen.font = large_font
    center_text("GAME OVER!", 18)

    # players final score
    screen.font = small_font
    center_text(f"Final Score: {mona.score}", 40)
        
    if new_high_score_achieved:
        center_text(f"New High Score!", 56)
    else:
        center_text(f"High Score: {high_score}", 56)

    # flash press button message
    if int(io.ticks / 500) % 2:
        screen.brush = brushes.color(255, 255, 255)
        center_text("Press A to restart", 80)

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
