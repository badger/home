# Your apps directory
APP_DIR = "/system/apps/tennis"

import os
import sys

# Standalone bootstrap for finding app assets
os.chdir(APP_DIR)

# Standalone bootstrap for module imports
sys.path.insert(0, APP_DIR)

import math
import random

# We'll use hight resolution mode for this app!
screen.pen = color.rgb(0, 0, 0)
badge.mode(HIRES)

# center points of the display
CX, CY = screen.width / 2, screen.height / 2

# load in our large font
large_font = font.ignore


class GameState:
    INTRO = 1
    PLAYING = 2
    GAME_OVER = 3


def normalise(x, y):
    dist = math.sqrt(x ** 2 + y ** 2)
    if dist == 0:
        return (0, 0)
    return (x / dist, y / dist)


class Ball:

    def __init__(self, dx):
        self.position = vec2(CX, CY)
        self.direction = vec2(dx, 0.5)
        self.w, self.h = 5, 5
        self.speed = 2

    def check_collision(self, a, b):
        return a.position.x + a.w >= b.position.x and a.position.x <= b.position.x + b.w and a.position.y + a.h >= b.position.y and a.position.y <= b.position.y + b.h

    def update(self):
        for _step in range(self.speed):
            # new positions
            self.position.x += self.direction.x
            self.position.y += self.direction.y

            # change direction of the ball if it hits the top of bottom
            if self.position.y <= 2 or self.position.y + self.h > screen.height - 2:
                self.direction.y = -self.direction.y

            # check if the ball has hit either of the bats this frame
            for bat in Bat.bats:
                if self.check_collision(bat, self):
                    bat_center_y = bat.position.y + bat.h / 2
                    y_diff = self.position.y - bat_center_y
                    self.direction.x = -self.direction.x
                    self.direction.y += y_diff / 50
                    self.direction.y = min((max(self.direction.y, -1), 1))
                    self.direction.x, self.direction.y = normalise(self.direction.x, self.direction.y)
                    self.speed += 0.2

            self.draw()

    def is_out(self):
        return self.position.x < 0 or self.position.x > screen.width

    def draw(self):
        screen.pen = color.rgb(255, 255, 255)
        x, y = self.position.x, self.position.y
        screen.shape(shape.rectangle(x, y, self.w, self.h))


class Bat:

    bats = []

    def __init__(self, player=True, auto=False):
        self.auto = auto
        self.player = player

        self.w, self.h = 6, 40
        self.position = vec2(screen.width - self.w if self.player else 0, CY)

        self.score = 0
        self.timer = 0
        self.movement = 10
        self.offset = 2
        Bat.bats.append(self)

    def bat_update(self):

        self.offset = random.randint(0, 5)

        if not self.auto:

            if badge.held(BUTTON_UP):
                self.position.y -= self.movement
            if badge.held(BUTTON_DOWN):
                self.position.y += self.movement

            # clamp position to screen bounds
            self.position.y = min(screen.height - self.h, max(0, self.position.y))

        else:
            # we want to move the CPU bat in a way that looks natural and actually allows the player to win
            # the cpu bat starts moving towards the ball when the ball is in its half of the screen
            # when its in the players half it starts moving back to the center position
            x_dist = abs(ball.position.x - self.position.x)
            target_y_1 = (screen.height // 2) - (self.h / 2)
            target_y_2 = ball.position.y + self.offset
            weight_1 = min(1, x_dist / (CX))
            weight_2 = 1 - weight_1
            target_y = (weight_1 * target_y_1) + (weight_2 * target_y_2)

            self.movement = min(5, max(-5, target_y - self.position.y))
            self.position.y += self.movement

            # clamp position to screen bounds
            self.position.y = min(screen.height - self.h, max(0, self.position.y))

        self.draw()

    def draw(self):
        screen.pen = color.rgb(255, 255, 255)
        screen.shape(shape.rectangle(self.position.x, self.position.y, self.w, self.h))

    @staticmethod
    def update():
        for bat in Bat.bats:
            bat.bat_update()


# Called once to initialise your app.
def init():
    pass


# setup for our game objects
# we set the player bat to run automatically so it plays against the CPU on the menu
player = Bat(player=True, auto=True)
cpu = Bat(player=False, auto=True)
ball = Ball(1)
state = GameState.INTRO


# helper functions to add shadow to text
def shadow_text(text, x, y):
    screen.pen = color.rgb(20, 40, 60, 100)
    screen.text(text, x + 1, y + 1)
    screen.pen = color.rgb(255, 255, 255)
    screen.text(text, x, y)


# center text
def center_text(text, y):
    w, _ = screen.measure_text(text)
    shadow_text(text, screen.width / 2 - (w / 2), y)


def intro():
    global state, player, cpu, ball

    # draw title
    screen.font = large_font
    center_text("TENNIS", CY - 30)
    # blink button message
    if int(badge.ticks / 500) % 2:
        center_text("Press SELECT to start", CY + 20)

    # update the position for the bats and ball
    ball.update()
    Bat.update()

    # if the user presses SELECT, we'll set everything for them to take over control of our Player
    if badge.pressed(BUTTON_SELECT):
        state = GameState.PLAYING

        # Remove the auto player and create a user controlled on
        Bat.bats.remove(player)
        player = Bat(True)

        # create a new ball
        ball = Ball(-1)


# Called every frame, update and render as you see fit!
def update():
    global ball, state, player, cpu

    screen.pen = color.rgb(20, 20, 20)
    screen.clear()
    screen.pen = color.rgb(255, 255, 255)

    # draw the score board
    screen.font = large_font
    screen.text(f"{player.score}", screen.width - CX / 2, 10)
    screen.text(f"{cpu.score}", CX / 2 - 10, 10)

    # draw the court
    screen.shape(shape.rectangle(CX, 0, 3, screen.height))
    screen.shape(shape.line(0, 1, screen.width, 1, 2))
    screen.shape(shape.line(0, screen.height - 1, screen.width, screen.height - 1, 2))

    if state == GameState.INTRO:
        intro()

    if state == GameState.PLAYING:

        # if the ball is out of bounds, we check to see who gets the point.
        if ball.is_out():
            if ball.position.x < CX:
                player.score += 1
                ball = Ball(1)
            else:
                cpu.score += 1
                ball = Ball(-1)

            # if someone has a score of 6, the game is over.
            if 6 in (player.score, cpu.score):
                state = GameState.GAME_OVER

        ball.update()
        Bat.update()

    if state == GameState.GAME_OVER:
        # Work out who won and show this on screen
        center_text("GAME OVER", CY - 60)
        if player.score == 6:
            center_text("YOU WIN", CY)
        elif cpu.score == 6:
            center_text("CPU WINS", CY)

        center_text("Press SELECT to return to menu", CY + 60)

        # reset the game
        if badge.pressed(BUTTON_SELECT):
            state = GameState.INTRO
            player.score = 0
            player.auto = True
            cpu.score = 0


# Handle saving your app state here
def on_exit():
    pass


init()
run(update)
