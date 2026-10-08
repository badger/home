import random

sprites = image.load("assets/obstacles.png").spritesheet(2, 1)


class Obstacle:
    obstacles = []
    next_spawn_time = None

    @staticmethod
    def spawn():
        Obstacle.obstacles.append(Obstacle())
        Obstacle.next_spawn_time = badge.ticks + 1500
        Obstacle.obstacles = [
            obstacle for obstacle in Obstacle.obstacles if obstacle.x > -24
        ]

    def __init__(self):
        self.x = screen.width
        self.gap_height = 60
        self.gap_y = random.randint(
            15,
            screen.height - self.gap_height - 15,
        )
        self.passed = False

    def update(self):
        self.x -= 30 * (badge.ticks_delta / 1000)

    def bounds(self):
        bottom_y = self.gap_y + self.gap_height
        return (
            (self.x, 0, 24, self.gap_y - 2),
            (self.x, bottom_y + 2, 24, screen.height - bottom_y - 2),
        )

    def draw(self):
        screen.blit(
            sprites.sprite(0, 0),
            rect(self.x, self.gap_y - 72, 24, 24),
        )
        screen.blit(
            sprites.sprite(0, 0),
            rect(self.x, self.gap_y - 48, 24, 24),
        )
        screen.blit(
            sprites.sprite(1, 0),
            rect(self.x, self.gap_y - 24, 24, 24),
        )

        bottom_y = self.gap_y + self.gap_height
        screen.blit(sprites.sprite(1, 0), rect(self.x, bottom_y, 24, -24))
        screen.blit(sprites.sprite(0, 0), rect(self.x, bottom_y + 24, 24, -24))
        screen.blit(sprites.sprite(0, 0), rect(self.x, bottom_y + 48, 24, -24))
