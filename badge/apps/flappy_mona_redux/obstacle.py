import random

from world import HEIGHT, SPEED, WIDTH, overlaps

sprites = image.load("assets/obstacles.png").spritesheet(2, 1)
BRICK = sprites.sprite(0, 0)
CAP = sprites.sprite(1, 0)

TILE = 48
GAP = 120
MIN_WALL = 30  # shortest wall left above or below the gap
INSET = 4  # forgiving margin between the art and the hit area


class Obstacle:
    def __init__(self):
        self.x = float(WIDTH)
        self.gap_y = random.randint(MIN_WALL, HEIGHT - GAP - MIN_WALL)
        self.passed = False

    def update(self, dt):
        self.x -= SPEED * dt

    def solids(self):
        bottom = self.gap_y + GAP
        return (
            (self.x, 0, TILE, self.gap_y - INSET),
            (self.x, bottom + INSET, TILE, HEIGHT - bottom - INSET),
        )

    def hits(self, box):
        for solid in self.solids():
            if overlaps(solid, box):
                return True
        return False

    def draw(self, cam=0):
        x = int(self.x)

        y = self.gap_y - TILE
        screen.blit(CAP, vec2(x, y + cam))
        y -= TILE
        while y + cam > -TILE:
            screen.blit(BRICK, vec2(x, y + cam))
            y -= TILE

        bottom = self.gap_y + GAP
        screen.blit(CAP, rect(x, bottom + cam, TILE, -TILE))
        y = bottom + TILE
        while y + cam < HEIGHT:
            screen.blit(BRICK, rect(x, y + cam, TILE, -TILE))
            y += TILE
