"""
Conway's Game of Life on a wrapping board.

Controls:
* Enter = New random board
* Hold Enter = Clear the board and paint
* Up / Down / Left / Right = Pause and paint
* While painting: Enter = Toggle a cell, hold Enter or Back = Run
"""

import micropython
import random

import hints

previous_clear = badge.default_clear

badge.mode(HIRES)
badge.default_clear = None

CELL = micropython.const(5)
COLS = micropython.const(64)
ROWS = micropython.const(48)
STEP_MS = 120
HOLD_MS = 500
REPEAT_DELAY_MS = 300
REPEAT_MS = 70
BLINK_MS = 400
PRIMER_MS = 3000
PRIMER_PADDING = 8
PRIMER_GAP = 4
PRIMER_MARGIN = 10

PALETTES = (
    (color.rgb(13, 17, 23), color.rgb(46, 160, 67), color.rgb(242, 245, 243)),
    (color.rgb(238, 246, 255), color.rgb(9, 105, 218), color.rgb(13, 17, 23)),
    (color.rgb(24, 12, 38), color.rgb(201, 87, 255), color.rgb(242, 245, 243)),
    (color.rgb(20, 20, 20), color.rgb(255, 180, 30), color.rgb(242, 245, 243)),
)

GRAY_1 = color.rgb(242, 245, 243)
GRAY_4 = color.rgb(144, 150, 146)
GRAY_6 = color.rgb(16, 20, 17)
HINT_STYLE = hints.Style(GRAY_1, GRAY_4, GRAY_6)
HINT_SHAPE = (BUTTON_UP, BUTTON_DOWN, BUTTON_LEFT, BUTTON_RIGHT, BUTTON_SELECT, BUTTON_BACK)
HINT_RADIUS = 5
LABEL = font.bacteria

DIRECTIONS = ((BUTTON_UP, 0, -1), (BUTTON_DOWN, 0, 1), (BUTTON_LEFT, -1, 0), (BUTTON_RIGHT, 1, 0))

cells = bytearray(COLS * ROWS)
next_cells = bytearray(COLS * ROWS)

palette = 0
painting = False
cursor_x = COLS // 2
cursor_y = ROWS // 2
cursor_shown = None
last_step = badge.ticks
select_down_at = None
select_hold_used = False
repeat_at = None
primer_until = 0
redraw = True


@micropython.viper
def step(source, target):
    src = ptr8(source)
    dst = ptr8(target)
    cols = int(COLS)
    rows = int(ROWS)
    for y in range(rows):
        above = ((y + rows - 1) % rows) * cols
        here = y * cols
        below = ((y + 1) % rows) * cols
        for x in range(cols):
            left = (x + cols - 1) % cols
            right = (x + 1) % cols
            neighbours = (src[above + left] + src[above + x] + src[above + right]
                          + src[here + left] + src[here + right]
                          + src[below + left] + src[below + x] + src[below + right])
            dst[here + x] = 1 if neighbours == 3 or (neighbours == 2 and src[here + x]) else 0


def randomise():
    global redraw
    for i in range(COLS * ROWS):
        cells[i] = random.getrandbits(1)
    redraw = True


def clear():
    global redraw
    for i in range(COLS * ROWS):
        cells[i] = 0
    redraw = True


def draw_cell(index, alive):
    background, foreground, _cursor = PALETTES[palette]
    screen.pen = foreground if alive else background
    fill_cell(index)


def fill_cell(index):
    screen.rectangle((index % COLS) * CELL, (index // COLS) * CELL, CELL, CELL)


def draw_board():
    global cursor_shown
    cursor_shown = None
    background, foreground, _cursor = PALETTES[palette]
    screen.pen = background
    screen.clear()
    screen.pen = foreground
    for i in range(COLS * ROWS):
        if cells[i]:
            screen.rectangle((i % COLS) * CELL, (i // COLS) * CELL, CELL, CELL)


def draw_changes():
    for i in range(COLS * ROWS):
        if cells[i] != next_cells[i]:
            draw_cell(i, cells[i])


def draw_cursor():
    global cursor_shown
    index = cursor_y * COLS + cursor_x
    lit = (badge.ticks // BLINK_MS) % 2 == 1
    shown = (index, lit, cells[index])
    if shown == cursor_shown:
        return
    if cursor_shown is not None and cursor_shown[0] != index:
        draw_cell(cursor_shown[0], cells[cursor_shown[0]])
    if lit:
        screen.pen = PALETTES[palette][2]
        fill_cell(index)
    else:
        draw_cell(index, cells[index])
    cursor_shown = shown


def hide_cursor():
    global cursor_shown
    if cursor_shown is not None:
        draw_cell(cursor_shown[0], cells[cursor_shown[0]])
    cursor_shown = None


def draw_primer():
    label = "toggle, hold to run"
    screen.font = LABEL
    label_width, label_height = screen.measure_text(label)
    hint_height = hints.hint_height(HINT_SHAPE, HINT_RADIUS)
    width = max(label_width, hints.hint_width(HINT_SHAPE, HINT_RADIUS)) + PRIMER_PADDING * 2
    height = hint_height + PRIMER_GAP + label_height + PRIMER_PADDING * 2
    cx = screen.width / 2
    top = screen.height - PRIMER_MARGIN - height
    screen.pen = GRAY_6
    screen.rectangle(cx - width / 2, top, width, height)
    cy = top + PRIMER_PADDING + hint_height / 2
    hints.draw_hint(HINT_STYLE, HINT_SHAPE, (BUTTON_SELECT,), cx, cy, HINT_RADIUS)
    screen.pen = GRAY_1
    screen.text(label, cx - label_width / 2, cy + hint_height / 2 + PRIMER_GAP)


def dismiss_primer():
    global primer_until, redraw
    if primer_until:
        primer_until = 0
        redraw = True


def start_painting():
    global painting, primer_until
    if not painting:
        painting = True
        primer_until = badge.ticks + PRIMER_MS
        draw_primer()


def stop_painting():
    global painting
    dismiss_primer()
    hide_cursor()
    painting = False


def move_cursor(dx, dy):
    global cursor_x, cursor_y
    cursor_x = (cursor_x + dx) % COLS
    cursor_y = (cursor_y + dy) % ROWS
    dismiss_primer()


def handle_directions():
    global repeat_at
    for button, dx, dy in DIRECTIONS:
        if badge.pressed(button):
            if painting:
                move_cursor(dx, dy)
            start_painting()
            repeat_at = badge.ticks + REPEAT_DELAY_MS
            return
    for button, dx, dy in DIRECTIONS:
        if badge.held(button):
            if painting and repeat_at is not None and badge.ticks >= repeat_at:
                move_cursor(dx, dy)
                repeat_at = badge.ticks + REPEAT_MS
            return
    repeat_at = None


def handle_select():
    global select_down_at, select_hold_used, palette
    if badge.pressed(BUTTON_SELECT):
        select_down_at = badge.ticks
        select_hold_used = False
    if select_down_at is None:
        return
    if not select_hold_used and badge.held(BUTTON_SELECT) and badge.ticks - select_down_at >= HOLD_MS:
        select_hold_used = True
        if painting:
            stop_painting()
        else:
            clear()
            start_painting()
    if badge.released(BUTTON_SELECT):
        if not select_hold_used:
            if painting:
                index = cursor_y * COLS + cursor_x
                cells[index] = 1 - cells[index]
                dismiss_primer()
            else:
                palette = (palette + 1) % len(PALETTES)
                randomise()
        select_down_at = None


def update():
    global last_step, cells, next_cells, redraw

    handle_select()
    handle_directions()
    if painting and badge.pressed(BUTTON_BACK):
        stop_painting()
    if primer_until and badge.ticks >= primer_until:
        dismiss_primer()

    if redraw:
        draw_board()
        redraw = False
        if primer_until:
            draw_primer()

    if not painting and badge.ticks - last_step >= STEP_MS:
        step(cells, next_cells)
        cells, next_cells = next_cells, cells
        draw_changes()
        last_step = badge.ticks

    if painting:
        draw_cursor()


def on_exit():
    badge.default_clear = previous_clear


randomise()
run(update)
