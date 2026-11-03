import math
import random

from world import HEIGHT as SCREEN_HEIGHT
from world import SPEED, overlaps

sheet = image.load("assets/fish.png").spritesheet(4, 1)
FRAMES = [sheet.sprite(i, 0) for i in range(4)]

WIDTH = 48
HEIGHT = 32
HIT = (4, 4, 40, 24)
WIGGLE_FPS = 8
BOB_PIXELS = 4


class Fish:
    def __init__(self, x, y):
        self.x = x
        self.base_y = y
        self.age = random.random() * 6.28

    def update(self, dt):
        self.x -= SPEED * dt
        self.age += dt

    def y(self):
        return self.base_y + math.sin(self.age * 4) * BOB_PIXELS

    def bounds(self):
        return (self.x + HIT[0], self.y() + HIT[1], HIT[2], HIT[3])

    def touches(self, box):
        return overlaps(self.bounds(), box)

    def draw(self, cam=0):
        y = int(self.y()) + cam
        if -HEIGHT < y < SCREEN_HEIGHT:
            frame = FRAMES[int(self.age * WIGGLE_FPS) % len(FRAMES)]
            screen.blit(frame, vec2(int(self.x), y))
