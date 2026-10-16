import math
import os
import random
import sys

APP_DIRS = ("/remote/apps/commits", "/system/apps/commits", "/apps/commits", "/commits")
APP_DIR = next(path for path in APP_DIRS if is_dir(path))
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

screen.font = font.nope
screen.antialias = image.X2

WIDTH = screen.width
HEIGHT = screen.height
PADDLE_SPEED = 150
BALL_SPEED = 105
BRICK_ROWS = 5
BRICK_COLS = 10

WHITE = color.rgb(245, 245, 245)
GREEN = color.rgb(46, 160, 67)
DARK_GREEN = color.rgb(15, 92, 40)
BACKGROUND = color.rgb(13, 17, 23)
DIM = color.rgb(139, 148, 158)

STATE_INTRO = 0
STATE_PLAYING = 1
STATE_GAME_OVER = 2

state = STATE_INTRO
score = 0
lives = 3
autoplay = False
paddle_x = WIDTH / 2
ball_x = WIDTH / 2
ball_y = 91
ball_dx = 0
ball_dy = 0
bricks = []


def reset_bricks():
    global bricks
    bricks = [[True for _ in range(BRICK_COLS)] for _ in range(BRICK_ROWS)]


def reset_ball():
    global ball_x, ball_y, ball_dx, ball_dy
    ball_x = paddle_x
    ball_y = 91
    ball_dx = 0
    ball_dy = 0


def reset_game():
    global score, lives, paddle_x, state
    score = 0
    lives = 3
    paddle_x = WIDTH / 2
    reset_bricks()
    reset_ball()
    state = STATE_PLAYING


def launch_ball():
    global ball_dx, ball_dy
    if ball_dy == 0:
        angle = random.uniform(-0.65, 0.65)
        ball_dx = math.sin(angle) * BALL_SPEED
        ball_dy = -math.cos(angle) * BALL_SPEED


def center_text(text, y):
    width, _ = screen.measure_text(text)
    screen.text(text, (WIDTH - width) / 2, y)


def update_game():
    global paddle_x, ball_x, ball_y, ball_dx, ball_dy, lives, score, state

    seconds = min(badge.ticks_delta / 1000, 0.05)
    direction = 0
    if badge.held(BUTTON_LEFT):
        direction -= 1
    if badge.held(BUTTON_RIGHT):
        direction += 1
    if autoplay and ball_dy != 0:
        direction = -1 if ball_x < paddle_x else 1

    paddle_x = clamp(paddle_x + direction * PADDLE_SPEED * seconds, 18, WIDTH - 18)

    if ball_dy == 0:
        ball_x = paddle_x
        if badge.pressed(BUTTON_SELECT):
            launch_ball()
        return

    next_x = ball_x + ball_dx * seconds
    next_y = ball_y + ball_dy * seconds

    if next_x <= 3 or next_x >= WIDTH - 3:
        ball_dx = -ball_dx
        next_x = clamp(next_x, 3, WIDTH - 3)
    if next_y <= 17:
        ball_dy = abs(ball_dy)
        next_y = 17

    if ball_dy > 0 and 96 <= next_y <= 102 and abs(next_x - paddle_x) <= 19:
        offset = clamp((next_x - paddle_x) / 18, -0.9, 0.9)
        ball_dx = offset * BALL_SPEED
        ball_dy = -math.sqrt(max(1, BALL_SPEED * BALL_SPEED - ball_dx * ball_dx))
        next_y = 95

    brick_w = WIDTH / BRICK_COLS
    brick_h = 9
    row = int((next_y - 23) / brick_h)
    col = int(next_x / brick_w)
    if 0 <= row < BRICK_ROWS and 0 <= col < BRICK_COLS and bricks[row][col]:
        bricks[row][col] = False
        score += 1
        ball_dy = -ball_dy

    ball_x = next_x
    ball_y = next_y

    if ball_y > HEIGHT + 5:
        lives -= 1
        if lives <= 0:
            state = STATE_GAME_OVER
        else:
            reset_ball()

    if score == BRICK_ROWS * BRICK_COLS:
        reset_bricks()


def draw_game():
    screen.pen = BACKGROUND
    screen.clear()

    screen.pen = WHITE
    screen.text("COMMITS %d" % score, 4, 4)
    screen.text("LIVES %d" % lives, 112, 4)

    brick_w = WIDTH / BRICK_COLS
    for row in range(BRICK_ROWS):
        for col in range(BRICK_COLS):
            if bricks[row][col]:
                intensity = 90 + row * 30
                screen.pen = color.rgb(25, intensity, 55)
                screen.shape(shape.rounded_rectangle(col * brick_w + 1, 23 + row * 9, brick_w - 2, 7, 2))

    screen.pen = GREEN
    screen.shape(shape.rounded_rectangle(paddle_x - 18, 99, 36, 5, 2))
    screen.pen = WHITE
    screen.shape(shape.circle(ball_x, ball_y, 3))

    if autoplay:
        screen.pen = DIM
        screen.text("AUTO", 68, 109)


def update():
    global state, autoplay

    if badge.pressed(BUTTON_DOWN):
        autoplay = not autoplay

    if state == STATE_INTRO:
        screen.pen = BACKGROUND
        screen.clear()
        screen.pen = GREEN
        center_text("COMMIT BREAKOUT", 25)
        screen.pen = WHITE
        center_text("LEFT / RIGHT TO MOVE", 50)
        center_text("SELECT TO LAUNCH", 65)
        center_text("DOWN TO TOGGLE AUTO", 80)
        if badge.pressed(BUTTON_SELECT):
            reset_game()
        return

    if state == STATE_GAME_OVER:
        draw_game()
        screen.pen = DARK_GREEN
        screen.shape(shape.rounded_rectangle(25, 35, 110, 48, 5))
        screen.pen = WHITE
        center_text("GAME OVER", 45)
        center_text("SELECT TO RESTART", 65)
        if badge.pressed(BUTTON_SELECT):
            reset_game()
        return

    update_game()
    draw_game()


reset_bricks()
run(update)
