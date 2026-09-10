import sys
import os

sys.path.insert(0, "/system/apps/sketch")
os.chdir("/system/apps/sketch")

from badgeware import Image, brushes, shapes, screen, io, run
import ui


canvas = Image(0, 0, ui.canvas_area[2], ui.canvas_area[3])
cursor = (ui.canvas_area[2] / 2, ui.canvas_area[3] / 2)
mona_position = (10, 76)
mona_target = (10, 76)
mona_direction = 1

last_cursor_move = None
last_cursor = None


def update_cursor():
    global cursor, last_cursor_move, last_cursor
    global left_dial_angle, right_dial_angle

    # update the cursor position based on user input and shift the dial animation
    if not last_cursor_move or (io.ticks - last_cursor_move) > 20:
        if io.BUTTON_A in io.held:
            cursor = (cursor[0] - 1, cursor[1])
        if io.BUTTON_C in io.held:
            cursor = (cursor[0] + 1, cursor[1])
        if io.BUTTON_UP in io.held:
            cursor = (cursor[0], cursor[1] - 1)
        if io.BUTTON_DOWN in io.held:
            cursor = (cursor[0], cursor[1] + 1)
        last_cursor_move = io.ticks

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
        canvas.brush = brushes.color(105, 105, 105)
        canvas.draw(shapes.rectangle(int(cursor[0]), int(cursor[1]), 1, 1))
    last_cursor = cursor

# animate mona to her target location


def update_mona():
    global mona_position, mona_direction
    if mona_position[0] < mona_target[0]:
        mona_position = (mona_position[0] + 1, mona_position[1])
        mona_direction = 1
    elif mona_position[0] > mona_target[0]:
        mona_position = (mona_position[0] - 1, mona_position[1])
        mona_direction = -1
    else:
        mona_direction = 1 if mona_position[0] < (
            ui.canvas_area[2] / 2) else -1


def update():
    global mona_target, mona_direction

    update_cursor()
    update_mona()

    ui.draw_background()

    # if the users cursor is too near to mona then make her run away
    if cursor[0] < 30:
        mona_target = (120, 76)
    if cursor[0] > ui.canvas_area[2] - 30:
        mona_target = (10, 76)

    screen.blit(canvas, ui.canvas_area[0], ui.canvas_area[1])
    ui.draw_cursor(cursor)

    ui.draw_mona(mona_position, mona_direction)

    ui.draw_dial(left_dial_angle, (5, 115))
    ui.draw_dial(right_dial_angle, (155, 115))


if __name__ == "__main__":
    run(update)

