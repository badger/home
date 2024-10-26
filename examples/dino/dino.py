import badger2040
import time
import random
import io
from machine import Pin

badger2040.system_speed(badger2040.SYSTEM_FAST)

# Game engine

class Image():
    def __init__(self, path):
        with open(path, "rb") as f:
            img_format = f.readline()
            if img_format != b"P4\n":
                print("Wrong image format")
                exit()
            dimensions = f.readline()
            w, h = [int(x) for x in dimensions.split(b" ")]
            img = bytearray(f.read())
        self.bitmap, self.width, self.height = img, w, h

class Sprite():
    def __init__(self, x, y, image, display):
        self.set_pos(x, y)
        self.image = image
        self.display = display

    def change_image(self, image):
        self.image = image

    def draw(self):
        if self.image is not None:
            for oy in range(self.image.height):
                for ox in range(self.image.width):
                    o = oy * (self.image.width >> 3) + (ox >> 3)
                    bm = 0b10000000 >> (ox & 0b111)
                    if self.image.bitmap[o] & bm:
                        self.display.pixel(int(self.x) + ox, int(self.y) + oy)

    def set_pos(self, x=None, y=None):
        if x is not None:
            self.x = x
        if y is not None:
            self.y = y


class MovingObject(Sprite):
    def __init__(self, x, y, image, display, ground=0, gravity=0):
        super().__init__(x, y, image, display)
        self.motion_vector = [0, 0]
        self.gravity = gravity
        self.ground = ground
        self.last_tick = 0

    def set_motion_vector(self, x, y):
        if x is not None:
            self.motion_vector[0] = x
        if y is not None:
            self.motion_vector[1] = y

    def physics_tick(self, now):
        diff = time.ticks_diff(now, self.last_tick) * 0.1
        self.motion_vector[1] += self.gravity * diff
        self.x += self.motion_vector[0] * diff
        self.y += self.motion_vector[1] * diff
        if self.gravity != 0 and self.y >= self.ground - self.image.height:
            self.y = self.ground - self.image.height
            self.motion_vector[1] = 0
        self.last_tick = now

    def on_ground(self):
        return self.y == self.ground - self.image.height

    def collision_test(self, obstacles):
        for obstacle in obstacles:
            if (self.x + self.image.width >= obstacle.x and obstacle.x + obstacle.image.width >= self.x and self.y + self.image.height >= obstacle.y and obstacle.y + obstacle.image.height >= self.y):
                return obstacle
        return None

# Global variables

button_a = Pin(badger2040.BUTTON_A, Pin.IN, Pin.PULL_DOWN)
button_up = Pin(badger2040.BUTTON_UP, Pin.IN, Pin.PULL_DOWN)

display = badger2040.Badger2040()
display_width = badger2040.WIDTH
display_height = badger2040.HEIGHT

high_score_path = "/highscore.txt"
high_score = 0
score = 0

dino_img = Image("/examples/dino.pbm")
cactus_img = Image("/examples/cactus.pbm")

player = MovingObject(10, display_height - dino_img.height, dino_img, display, ground=display_height, gravity=0.02)
cactus = MovingObject(display_width - cactus_img.width, display_height - cactus_img.height, cactus_img, display, ground=display_height)
cactus2 = MovingObject(4 * display_width - cactus_img.width, display_height - cactus_img.height, cactus_img, display, ground=display_height)

objects = [player, cactus, cactus2]
obstacles = [cactus, cactus2]

for o in obstacles:
    o.set_motion_vector(-1, 0)

def clear_screen():
    display.set_pen(15)
    display.clear()
    display.set_pen(0)

def game_loop():
    global score
    score = 0

    clear_screen()
    display.set_update_speed(badger2040.UPDATE_TURBO)
    display.update()

    now = time.ticks_ms()
    for o in objects:
        o.physics_tick(now)

    player.set_pos(10, display_height - dino_img.height)
    cactus.set_pos(display_width - cactus_img.width, display_height - cactus_img.height)
    cactus2.set_pos(4 * display_width - cactus_img.width, display_height - cactus_img.height)

    while True:
        clear_screen()
        now = time.ticks_ms()
        if display.pressed(badger2040.BUTTON_UP) and player.on_ground():
            player.set_motion_vector(0, -2)
        for o in obstacles:
            if o.x <= -cactus_img.width:
                o.set_pos(x=display_width + random.randint(0, display_width))
                score += 1
                o.set_motion_vector(-1 - score * 0.05, 0)
        for o in objects:
            o.physics_tick(now)
            o.draw()
        display.text("Score: " + str(score), 10, 10)
        display.update()
        if player.collision_test(obstacles) is not None or display.pressed(badger2040.BUTTON_A):
            break

def start_text():
    clear_screen()
    display.set_font("bitmap14_outline")
    display.text("Dino Game", 20, 20, scale=2)
    display.set_font("bitmap8")
    display.text("Press UP to start, A to abort", 20, 60, scale=2)
    display.text("High score: " + str(high_score), 20, 80, scale=2)
    display.set_update_speed(badger2040.UPDATE_FAST)
    display.update()

try:
    with io.open(high_score_path, "r") as f:
        try:
            high_score = int(f.readline())
        except ValueError:
            print("Cannot read high score")
except OSError:
    print("High score file not found")

# Main loop

def main():
    global high_score
    start_text()
    while True:
        if display.pressed(badger2040.BUTTON_UP):
            game_loop()
            if score is not None and score > high_score:
                high_score = score
                print("Saving new high score: " + str(high_score))
                with io.open(high_score_path, "w") as f:
                    f.write(str(score))
            start_text()
        elif display.pressed(badger2040.BUTTON_A):
            clear_screen()
            display.set_update_speed(badger2040.UPDATE_FAST)
            display.update()
            turn_off()

main()