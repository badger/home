APP_DIR = "/system/apps/sketchy_sketch"

import sys
import os

# Standalone bootstrap for finding app assets
os.chdir(APP_DIR)

# Standalone bootstrap for module imports
sys.path.insert(0, APP_DIR)

badge.mode(HIRES)

import ui

canvas = image(ui.canvas_area[2], ui.canvas_area[3])
cursor = (ui.canvas_area[2] / 2, ui.canvas_area[3] / 2)

last_cursor_move = None
last_cursor = None


def update_cursor():
    global cursor, last_cursor_move, last_cursor
    global left_dial_angle, right_dial_angle

    # update the cursor position based on user input and shift the dial animation
    if not last_cursor_move or (badge.ticks - last_cursor_move) > 20:
        last_cursor = cursor
        if badge.held(BUTTON_LEFT):
            cursor = (cursor[0] - 4, cursor[1])
        if badge.held(BUTTON_RIGHT):
            cursor = (cursor[0] + 4, cursor[1])
        if badge.held(BUTTON_UP):
            cursor = (cursor[0], cursor[1] - 4)
        if badge.held(BUTTON_DOWN):
            cursor = (cursor[0], cursor[1] + 4)
        last_cursor_move = badge.ticks

    # clamp cursor to canvas bounds
    cursor = (
        min(ui.canvas_area[2] - 3, max(2, cursor[0])),
        min(ui.canvas_area[3] - 3, max(2, cursor[1]))
    )

    # set the dial angles relative to the cursor position so they animate as
    # the cursor moves
    left_dial_angle = -cursor[0] * 3
    right_dial_angle = cursor[1] * 3

    if not last_cursor or int(last_cursor[0]) != int(cursor[0]) or int(last_cursor[1]) != int(cursor[1]):
        # draw to the canvas at the cursor position
        canvas.pen = color.rgb(105, 105, 105)
        # draw a small circle to clean up the joins between the lines
        canvas.shape(shape.circle(vec2(int(last_cursor[0]), int(last_cursor[1])), 0.5))
        # draw the line
        canvas.shape(shape.line(int(last_cursor[0]), int(last_cursor[1]), int(cursor[0]), int(cursor[1]), 1))
    last_cursor = cursor


def update():

    update_cursor()

    ui.draw_background()

    screen.blit(canvas, vec2(ui.canvas_area[0], ui.canvas_area[1]))
    ui.draw_cursor(cursor)

    ui.draw_dial(left_dial_angle, (5, screen.height - 5))
    ui.draw_dial(right_dial_angle, (screen.width - 5, screen.height - 5))


run(update)
