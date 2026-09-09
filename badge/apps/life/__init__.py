import os
import random
import sys

APP_DIRS = ("/remote/apps/life", "/system/apps/life", "/apps/life", "/life")
APP_DIR = next(path for path in APP_DIRS if is_dir(path))
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

COLS = 40
ROWS = 30
CELL = 4
STEP_MS = 120

PALETTES = (
    (color.rgb(13, 17, 23), color.rgb(46, 160, 67)),
    (color.rgb(238, 246, 255), color.rgb(9, 105, 218)),
    (color.rgb(24, 12, 38), color.rgb(201, 87, 255)),
    (color.rgb(20, 20, 20), color.rgb(255, 180, 30)),
)

grid = []
next_grid = []
palette = 0
last_step = badge.ticks


def randomize():
    global grid, next_grid
    grid = [[random.getrandbits(1) for _ in range(COLS)] for _ in range(ROWS)]
    next_grid = [[0 for _ in range(COLS)] for _ in range(ROWS)]


def step():
    global grid, next_grid
    for y in range(ROWS):
        for x in range(COLS):
            neighbors = 0
            for oy in (-1, 0, 1):
                for ox in (-1, 0, 1):
                    if ox or oy:
                        neighbors += grid[(y + oy) % ROWS][(x + ox) % COLS]
            next_grid[y][x] = 1 if neighbors == 3 or (grid[y][x] and neighbors == 2) else 0
    grid, next_grid = next_grid, grid


def update():
    global last_step, palette

    if badge.pressed(BUTTON_SELECT):
        randomize()
    if badge.pressed(BUTTON_RIGHT):
        palette = (palette + 1) % len(PALETTES)

    if badge.ticks - last_step >= STEP_MS:
        step()
        last_step = badge.ticks

    background, foreground = PALETTES[palette]
    screen.pen = background
    screen.clear()
    screen.pen = foreground
    for y in range(ROWS):
        for x in range(COLS):
            if grid[y][x]:
                screen.shape(shape.rectangle(x * CELL, y * CELL, CELL, CELL))


randomize()
run(update)
