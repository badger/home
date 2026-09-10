import sys
import os

sys.path.insert(0, "/system/apps/plucky_cluck")
os.chdir("/system/apps/plucky_cluck")

from badgeware import State
from chicken import Chicken
from obstacle import Obstacle

background = image.load("assets/background.png")
grass = image.load("assets/grass.png")
cloud = image.load("assets/cloud.png")
large_font = font.ziplock
small_font = font.nope
chicken = None

score = {
    "highscore": 0
}

State.load("flappy", score)


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


def reset_state():
    global state, chicken

    # reset game state
    state = GameState.PLAYING
    Obstacle.obstacles = []
    Obstacle.next_spawn_time = badge.ticks + 500
    chicken = Chicken()

    # give the player a moment to react by launching the chicken upwards
    # instead of letting her drop the instant the game starts
    chicken.jump()


# handle the intro screen of the game, shows the game title and a message to
# tell the player how to start the game
def intro():
    global state, chicken, score

    # draw title
    screen.font = large_font
    center_text("Plucky Cluck", 38)

    # blink button message
    if int(badge.ticks / 500) % 2:
        screen.font = small_font
        center_text("Press SELECT to start", 68)

    # show off the high score!
    screen.font = small_font
    hs = str(score["highscore"])
    center_text(f"High Score: {hs}", 95)

    if badge.pressed(BUTTON_SELECT):
        reset_state()

# handle the main game loop and user input. each tick we'll update the game
# state (read button input, move chicken, create new obstacles, etc..) then
# draw the background and sprites


def play():
    global state

    # if the user has pressed SELECT then make chicken jump for her life!
    if not chicken.is_dead() and badge.pressed(BUTTON_SELECT):
        chicken.jump()

    # update player and check for collision
    chicken.update()

    # spawn a new obstacle if the spawn timer has elapsed
    if not chicken.is_dead() and Obstacle.next_spawn_time and badge.ticks > Obstacle.next_spawn_time:
        Obstacle.spawn()

    # update obstacle positions and draw them
    for obstacle in Obstacle.obstacles:
        if not chicken.is_dead():
            obstacle.update()
        obstacle.draw()

    # draw our hero, chicken
    chicken.draw()

    # show the player their current score
    screen.font = small_font
    shadow_text(f"Score: {chicken.score}", 3, 0)

    # has chicken died this frame? if so it's... GAME OVER
    if chicken.is_dead():
        if chicken.is_done_dying():
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
    center_text(f"Final score: {chicken.score}", 40)

    # save the score if the previous high score has been beaten
    if chicken.score > score["highscore"]:
        score["highscore"] = chicken.score
        State.save("flappy", score)

    # flash press button message
    if int(badge.ticks / 500) % 2:
        screen.pen = color.rgb(255, 255, 255)
        center_text("Press SELECT to restart", 70)

    if badge.pressed(BUTTON_SELECT):
        reset_state()
        state = GameState.PLAYING


# draw the scrolling background with parallax layers
background_offset = 0


def draw_background():
    global background_offset

    # clear the whole screen in a bright blue
    screen.pen = color.rgb(250, 198, 104)
    screen.shape(shape.rectangle(0, 0, 160, 120))

    # if we're on the intro screen or chicken is alive then scroll the background
    # at a framerate-independent 30 pixels/second (was one pixel per frame at 30fps)
    if not chicken or not chicken.is_dead() or state == GameState.INTRO:
        background_offset += 30 * (badge.ticks_delta / 1000)

    for i in range(3):
        # draw the distance background
        bo = ((-background_offset / 8) % background.width) - screen.width
        screen.blit(background, vec2(bo + (background.width * i),
                    115 - background.height))

        # draw the cloud background
        bo = ((-background_offset / 8) % (cloud.width * 2)) - screen.width
        screen.blit(cloud, vec2(bo + (cloud.width * 2 * i), 20))

    for i in range(3):
        # draw the grass layer
        bo = ((-background_offset / 4) % (grass.width)) - screen.width
        screen.blit(grass, vec2(bo + (grass.width * i), 120 - grass.height))


# a couple of helper functions for formatting text


def shadow_text(text, x, y):
    screen.pen = color.rgb(20, 40, 60, 100)
    screen.text(text, x + 1, y + 1)
    screen.pen = color.rgb(255, 255, 255)
    screen.text(text, x, y)


def center_text(text, y):
    w, _ = screen.measure_text(text)
    shadow_text(text, 80 - (w / 2), y)


run(update)
