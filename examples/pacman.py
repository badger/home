import time
import badger2040
import jpegdec
import random

TILE_SIZE = 10  # Each tile is 10x10 pixels
HASH = "#"  # Wall character
DOT = "*"   # Dot character
PACMAN_OPEN = "C"  # Pac-Man's symbol (mouth open)
PACMAN_CLOSED = "O"  # Pac-Man's symbol (mouth closed)
COLOR_WHITE = 15
COLOR_BLACK = 0
SLEEP_DELAY = 0.1 # don't set it lower than this or the battery can't handle it!	

random.seed(time.ticks_ms())

# Initialize display
display = badger2040.Badger2040()
display.set_pen(COLOR_WHITE)  # White background
display.clear()

# Maze with walls along the edges
mazeH = [[HASH] + [HASH] * 26 + [HASH]]
mazeX = [[HASH] + [" "] * 26 + [HASH]]
maze = mazeH + [list(mazeX[0]) for _ in range(9)] + mazeH
jpeg = jpegdec.JPEG(display.display)

# Place dots at random positions in the maze
def place_random_dots(num_dots):
    for _ in range(num_dots):
        x, y = random.randint(1, 26), random.randint(1, 9)
        maze[y][x] = DOT

def choose_next_square(pac_x, pac_y, target_x, target_y):
    # Move horizontally if necessary
    if pac_x < target_x:
        return pac_x + 1, pac_y
    elif pac_x > target_x:
        return pac_x - 1, pac_y
    # Move vertically if horizontally aligned
    if pac_y < target_y:
        return pac_x, pac_y + 1
    elif pac_y > target_y:
        return pac_x, pac_y - 1
    # Pac-Man is at the target position
    return pac_x, pac_y

# Draw the maze with dots and walls
def draw_maze():
    display.clear()
    display.set_pen(0)  # Black pen for dots
    for y in range(len(maze)):
        for x in range(len(maze[y])):
            if maze[y][x] == DOT:
                display.text(DOT, x * TILE_SIZE + 8, y * TILE_SIZE + 8, TILE_SIZE)
            elif maze[y][x] == HASH:
                display.text(HASH, x * TILE_SIZE + 8, y * TILE_SIZE + 8, TILE_SIZE)
    display.update()

def update_pacman(prev_pos, new_pos):
    # erase previous position by drawing a white space over it
    display.set_pen(COLOR_WHITE)
    display.text(PACMAN_OPEN, prev_pos[0] * TILE_SIZE + 8, prev_pos[1] * TILE_SIZE + 8, TILE_SIZE)
    display.text(PACMAN_CLOSED, prev_pos[0] * TILE_SIZE + 8, prev_pos[1] * TILE_SIZE + 8, TILE_SIZE)
    # erase any eaten dots
    display.text(DOT, prev_pos[0] * TILE_SIZE + 8, prev_pos[1] * TILE_SIZE + 8, TILE_SIZE)
    display.text(DOT, new_pos[0] * TILE_SIZE + 8, new_pos[1] * TILE_SIZE + 8, TILE_SIZE)
    # draw at the new position
    display.set_pen(COLOR_BLACK)
    display.text(PACMAN_OPEN, new_pos[0] * TILE_SIZE + 8, new_pos[1] * TILE_SIZE + 8, TILE_SIZE)
    display.update()
    time.sleep(SLEEP_DELAY)

    display.set_pen(COLOR_WHITE)
    display.text(PACMAN_OPEN, new_pos[0] * TILE_SIZE + 8, new_pos[1] * TILE_SIZE + 8, TILE_SIZE)
    display.set_pen(COLOR_BLACK)
    display.text(PACMAN_CLOSED, new_pos[0] * TILE_SIZE + 8, new_pos[1] * TILE_SIZE + 8, TILE_SIZE)
    display.update()

    maze[new_pos[1]][new_pos[0]] = " "

def get_all_dots():
    dots = []
    for y in range(len(maze)):
        for x in range(len(maze[y])):
            if maze[y][x] == DOT:
                dots.append((x, y))
    return dots


def has_any_dots():
    for y in range(len(maze)):
        for x in range(len(maze[y])):
            if maze[y][x] == DOT:
                return True
    return False


# Main loop
place_random_dots(random.randint(15, 60))  # Place random dots
current_pos = (13, 5)  # Start Pac-Man in the middle of the maze
draw_maze()  # Draw initial maze
display.set_update_speed(badger2040.UPDATE_TURBO)
target_dot = None
autopilot = True

while True:
    if display.pressed(badger2040.BUTTON_B):
        autopilot = not autopilot
    # Get a random dot as the target if there isn't one
    if autopilot:
        if target_dot is None or target_dot not in get_all_dots():
            all_dots = get_all_dots()
            if all_dots:
                target_dot = random.choice(all_dots)
            else:
                break  # No more dots left to eat, exit loop

        # Determine the next position to move toward the target dot
        prev_x, prev_y = current_pos
        target_x, target_y = target_dot
        pac_x, pac_y = choose_next_square(prev_x, prev_y, target_x, target_y)
        current_pos = (pac_x, pac_y)
        
        # Check if Pac-Man has reached the dot
        if current_pos == target_dot:
            target_dot = None  # Reset target to choose a new random dot
        
        # Update Pac-Man's position on the screen
        update_pacman((prev_x, prev_y), (pac_x, pac_y))
        time.sleep(0.1)  # Delay between movements
    else:
        if not has_any_dots():
            break
        prev_x, prev_y = current_pos
        pac_x, pac_y = current_pos
        if display.pressed(badger2040.BUTTON_A):
            if pac_x > 1:
                pac_x = pac_x -1
        if display.pressed(badger2040.BUTTON_C):
            if pac_x < len(maze[0])-2:
                pac_x = pac_x + 1
        if display.pressed(badger2040.BUTTON_UP):
            if pac_y > 1:
                pac_y = pac_y -1
        if display.pressed(badger2040.BUTTON_DOWN):
            if pac_y < len(maze)-2:
                pac_y = pac_y +1

        # Update Pac-Man's position on the screen
        update_pacman((prev_x, prev_y), (pac_x, pac_y))
        current_pos = (pac_x, pac_y)
        time.sleep(SLEEP_DELAY*3) # Extra long sleep when in manual mode
display.halt()
