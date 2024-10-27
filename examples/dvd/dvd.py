import badger2040
import pngdec
import random
import time

# Global Constants
WIDTH = badger2040.WIDTH
HEIGHT = badger2040.HEIGHT
IMG_WIDTH = 52
IMG_HEIGHT = 28

SPEED = 10
SLEEP_TIME = 0.3

DIR_NW = 0
DIR_NE = 1
DIR_SW = 2
DIR_SE = 3

def draw_image(x, y):
    display.set_pen(15)
    display.clear()
    png.open_file("/examples/dvd.png")
    png.decode(x, y)

    min_x = x - SPEED
    min_y = (y - SPEED) // 8 * 8      
    max_x = IMG_WIDTH + SPEED * 2
    max_y = ((IMG_HEIGHT + SPEED * 2) // 8 * 8) + 8
       
    display.partial_update(
        max(0, min_x),
        max(0, min_y),
        min(max_x, WIDTH - min_x),
        min(max_y, HEIGHT - min_y)
    )
    

def move_image(x, y, dir):

    if dir == DIR_NW:
        dx = -1 * SPEED
        dy = -1 * SPEED
    elif dir == DIR_NE:
        dx = 1 * SPEED
        dy = -1 * SPEED
    elif dir == DIR_SE:
        dx = 1 * SPEED
        dy = 1 * SPEED
    elif dir == DIR_SW:
        dx = -1 * SPEED
        dy = 1 * SPEED

    # Bounce off the top of the screen.
    if y + dy < 0:
        dy = 0
        y = 0
        dir = dir + 2
    
    # Bounce off the bottom of the screen.
    if y + dy > HEIGHT - IMG_HEIGHT:
        dy = 0
        y = HEIGHT - IMG_HEIGHT
        dir = dir - 2

    # Bounce off the left of the screen.
    if x + dx < 0:
        dx = 0
        x = 0
        dir = dir + 1

    # Bounce off the right of the screen.
    if x + dx > WIDTH - IMG_WIDTH:
        dx = 0
        x = WIDTH - IMG_WIDTH
        dir = dir - 1

    return (x + dx, y + dy, dir)


display = badger2040.Badger2040()
display.set_update_speed(badger2040.UPDATE_FAST)
png = pngdec.PNG(display.display)

# Wipe the screen clean.
display.set_pen(15)
display.clear()
display.update()

# ------------------------------
#       Main program loop
# ------------------------------

RUNNING = True

current_x = random.randint(0, WIDTH - IMG_WIDTH - 1)
current_y = random.randint(0, HEIGHT - IMG_HEIGHT - 1)
current_dir = random.randint(0, 3)

draw_image(current_x, current_y)

while True:
    # Sometimes a button press or hold will keep the system
    # powered *through* HALT, so latch the power back on.
    display.keepalive()

    # Was the pause button pressed?
    if display.pressed(badger2040.BUTTON_A):
        RUNNING = not RUNNING        

    # Was the reset button pressed?
    if display.pressed(badger2040.BUTTON_B):
        current_x = random.randint(0, WIDTH - IMG_WIDTH)
        current_y = random.randint(0, HEIGHT - IMG_HEIGHT)

    # Was the speed up button pressed?
    if display.pressed(badger2040.BUTTON_UP):
        SLEEP_TIME = max(SLEEP_TIME - 0.1, 0.1)

    # Was the speed down button pressed?
    if display.pressed(badger2040.BUTTON_DOWN):
        SLEEP_TIME = min(SLEEP_TIME + 0.1, 1)

    if RUNNING:
        (current_x, current_y, current_dir) = move_image(current_x, current_y, current_dir)
        draw_image(current_x, current_y)

    time.sleep(SLEEP_TIME)
