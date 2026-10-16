import sys
import os
import math
import random
from draw_tufty import Renderer

sys.path.insert(0, "/system/apps/extend_a_squirrel")
os.chdir("/system/apps/extend_a_squirrel")


class Platform:
    TUFTY = 1
    BADGER = 2
    BLINKY = 3


class GameState:
    INTRO = 1
    PLAYING = 2
    GAME_OVER = 3


# Dictionary to translate speed level to number of milliseconds between updates.
speeds = {
    1: 500,
    2: 440,
    3: 380,
    4: 320,
    5: 260,
    6: 200,
    7: 140,
    8: 80,
    9: 20
}

state = GameState.INTRO
renderer = None
platform = Platform.TUFTY
game_speed = 1
grid_size = 1
score = 0

renderer = Renderer()

timer = badge.ticks


# The Snake class stores the location and direction of the head,
# as well as all of the body squares and the current length of the tail.
class Snake:
    def __init__(self):
        self.x = math.floor(renderer.X_CELLS / 2)
        self.y = math.floor(renderer.Y_CELLS / 2)
        self.lastpos = [self.x, self.y]
        self.direction = 0
        self.tail = 1
        self.body = [[self.x, self.y + 1]]

    # This method adds the current head position to the list of body squares,
    # and if it's longer than the current tail length drops the last one off the list.
    def advance(self):
        self.body.insert(0, self.lastpos)
        self.lastpos = [self.x, self.y]
        if len(self.body) > self.tail:
            self.body.pop()

    def detect_collision(self, x, y, include_head=False):
        if include_head:
            if self.x == x and self.y == y:
                return True
            if self.lastpos[0] == x and self.lastpos[1] == y:
                return True
        for segment in self.body:
            if segment[0] == x and segment[1] == y:
                return True
        return False


# The Apple class just stores a location for the apple,
# as well as a method to randomise that location.
class Apple:
    global snake

    def __init__(self):
        self.x = random.randint(0, renderer.X_CELLS - 1)
        self.y = random.randint(0, renderer.Y_CELLS - 1)

    def relocate(self):
        self.x = random.randint(0, renderer.X_CELLS - 1)
        self.y = random.randint(0, renderer.Y_CELLS - 1)
        if snake.detect_collision(self.x, self.y, True):
            self.relocate()


snake = Snake()
apple = Apple()

newdirection = 0


# Just detects buttons on the intro screen and sets settings appropriately
def intro_controls():
    global game_speed, grid_size, state

    if badge.pressed(BUTTON_LEFT):
        if game_speed > 1:
            game_speed -= 1

    elif badge.pressed(BUTTON_SELECT):
        state = GameState.PLAYING

    elif badge.pressed(BUTTON_RIGHT):
        if game_speed < 9:
            game_speed += 1

    elif badge.pressed(BUTTON_UP):
        if grid_size < 5:
            grid_size += 1

    elif badge.pressed(BUTTON_DOWN):
        if grid_size > 1:
            grid_size -= 1


# Simple method to check for button presses and alter the snake's direction accordingly.
def game_controls():
    global newdirection

    if badge.pressed(BUTTON_RIGHT) and snake.direction != 3:
        newdirection = 1
    elif badge.pressed(BUTTON_LEFT) and snake.direction != 1:
        newdirection = 3
    elif badge.pressed(BUTTON_UP) and snake.direction != 2:
        newdirection = 0
    elif badge.pressed(BUTTON_DOWN) and snake.direction != 0:
        newdirection = 2


# Changes the snake's head location based on its direction.
def move_snake():
    global state, renderer, snake, apple, score, game_speed

    if snake.direction == 0:
        snake.y -= 1
    elif snake.direction == 2:
        snake.y += 1
    elif snake.direction == 1:
        snake.x += 1
    elif snake.direction == 3:
        snake.x -= 1

    if snake.x > renderer.X_CELLS - 1:
        snake.x = 0
    if snake.x < 0:
        snake.x = renderer.X_CELLS - 1
    if snake.y > renderer.Y_CELLS - 1:
        snake.y = 0
    if snake.y < 0:
        snake.y = renderer.Y_CELLS - 1

    # This checks the snake's head location and if it's the same as the apple,
    # add one to the tail and score and relocate the apple.
    # If the score is a multiple of 10, then bump up the speed one notch.
    if snake.x == apple.x and snake.y == apple.y:
        snake.tail += 1
        score += 1
        if score % 10 == 0 and score > 0 and game_speed <= 9:
            game_speed += 1
        apple.relocate()

    # This handles shifting along the array for the snake's tail.
    snake.advance()

    # Checks if the new head position is on our own tail, and game-overs us if it is.
    if snake.detect_collision(snake.x, snake.y):
        state = GameState.GAME_OVER


# The main loop switches behaviour depending on game state.
def update():
    global timer, state, snake, apple, newdirection, score, game_speed, grid_size

    # If we're in the intro, check for the button presses
    # to change settings and start the game, then draw the intro screen.
    if state == GameState.INTRO:
        intro_controls()
        renderer.draw_intro(game_speed, grid_size)

    # If we're in the game, this is the gameplay loop:
    # Check for control inputs, and then when enough time has elapsed,
    # update the snake's direction and move it along.
    # Once the new frame of the game has been sorted, draw it to the screen.
    elif state == GameState.PLAYING:
        game_controls()

        if badge.ticks - timer > speeds[game_speed]:
            snake.direction = newdirection
            move_snake()
            timer = badge.ticks

        renderer.draw_play(snake, apple, score)

    # If we're on the game over screen, reset the game state and go back into the intro when the button is pressed.
    elif state == GameState.GAME_OVER:
        if badge.pressed(BUTTON_SELECT):
            game_speed = 1
            grid_size = 1
            score = 0
            snake = Snake()
            state = GameState.INTRO
        renderer.draw_gameover()


run(update)
