import badger2040
import random
import time

WIDTH        = 45
HEIGHT       = 12
CELL         = '+'
EMPTY_CELL   = ' '
DEBUG        = False
RUNNING      = True
REFRESH_RATE = 0.5

def initialize_grid():
    return [[random.choice([EMPTY_CELL, CELL]) for _ in range(WIDTH)] for _ in range(HEIGHT)]

def print_grid(grid):
    badger.set_pen(0)
    badger.clear()
    badger.set_pen(15)
    badger.set_font("bitmap8")
    badger.set_thickness(1)

    for k, row in enumerate(grid):
        badger.text(''.join(row), 0, k*10)
    
    badger.update()
    
def write_text(text):
    badger.set_pen(0)
    badger.clear()
    badger.set_pen(15)
    badger.set_font("bitmap8")
    badger.set_thickness(1)
    badger.text(text, 25, 25)
    badger.update()
    time.sleep(1)

def count_neighbors(grid, x, y):
    neighbors = [
        (-1, -1), (-1, 0), (-1, 1),
        (0, -1),           (0, 1),
        (1, -1),   (1, 0), (1, 1)
    ]
    
    count = 0
    for dx, dy in neighbors:
        nx, ny = x + dx, y + dy
        if 0 <= nx < HEIGHT and 0 <= ny < WIDTH:
            if grid[nx][ny] == CELL:
                count += 1
    return count

def update_grid(grid):
    new_grid = [[EMPTY_CELL for _ in range(WIDTH)] for _ in range(HEIGHT)]
    
    for x in range(HEIGHT):
        for y in range(WIDTH):
            
            neighbors = count_neighbors(grid, x, y)
            
            if grid[x][y] == CELL:
                if neighbors in [2, 3]:
                    new_grid[x][y] = CELL
                else:
                    new_grid[x][y] = EMPTY_CELL
            else:
                if neighbors == 3:
                    new_grid[x][y] = CELL
    return new_grid
                        
# ----------------------------------------------------------------
# Main loop
# ----------------------------------------------------------------
badger = badger2040.Badger2040()
badger.set_update_speed(2)
grid = initialize_grid()

while True:
    if badger.pressed(badger2040.BUTTON_A):
        # Re-initialize the grid with a new random pattern
        grid = initialize_grid()
        write_text('Grid re-initialized')
        if DEBUG:
            print('BUTTON_A: grid re-initialized')
    
    if badger.pressed(badger2040.BUTTON_B):
        # Toggle the running state
        RUNNING = not RUNNING
        write_text('Running: ' + str(RUNNING))
        if DEBUG:
            print('BUTTON_B: toggle running state: ', RUNNING)

    if badger.pressed(badger2040.BUTTON_UP):
        # Increase the refresh rate (lower is faster)
        if REFRESH_RATE - 0.1 > 0:
            REFRESH_RATE -= 0.1
        write_text('Refresh rate: ' + str(REFRESH_RATE))
        if DEBUG:
            print('BUTTON_UP: refresh rate inc: ', REFRESH_RATE)
    
    if badger.pressed(badger2040.BUTTON_DOWN):
        # Decrease the refresh rate (higher is slower)
        REFRESH_RATE += 0.1
        write_text('Refresh rate: ' + str(REFRESH_RATE))
        if DEBUG:
            print('BUTTON_DOWN: refresh rate dec: ', REFRESH_RATE)

    if RUNNING:
        print_grid(grid)
        grid = update_grid(grid)
        time.sleep(REFRESH_RATE)

