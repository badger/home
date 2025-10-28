import random
from badgeware import SpriteSheet, io, screen

sprites = SpriteSheet("assets/obstacles.png", 2, 1)


class Obstacle:
    # the list of active obstacles
    obstacles = []
    next_spawn_time = None

    def spawn():
        # create a new obstacle and reset the obstacle spawn timer
        Obstacle.obstacles.append(Obstacle())
        Obstacle.next_spawn_time = io.ticks + 1500

        # clean up any obstacles that are now off screen and can be removed
        Obstacle.obstacles = [o for o in Obstacle.obstacles if o.x > -24]

    def __init__(self):
        # position the new obstacle off the right hand side of the screen and
        # randomise the height of the gap
        self.x = screen.width
        self.gap_height = 60
        self.gap_y = random.randint(15, screen.height - self.gap_height - 15)

        # when mona passes an obstacle we flag it so the score is only increased once
        self.passed = False

    def update(self):
        # moves the obstacle to the left by one pixel each frame
        self.x -= 1

    def bounds(self):
        # be a little generous with obstacle bounding boxes for collisions
        return (
            (self.x, 0, 24, self.gap_y - 2),
            (self.x, self.gap_y + self.gap_height + 2,
                24, 120 - self.gap_y + self.gap_height - 2)
        )

    def draw(self):
        # draw the top half off the obstacle
        screen.scale_blit(sprites.sprite(0, 0), self.x,
                          self.gap_y - 72, 24, 24)
        screen.scale_blit(sprites.sprite(0, 0), self.x,
                          self.gap_y - 48, 24, 24)
        screen.scale_blit(sprites.sprite(1, 0), self.x,
                          self.gap_y - 24, 24, 24)  # spikes, yikes!

        # draw the bottom half off the obstacle
        screen.scale_blit(sprites.sprite(1, 0), self.x, self.gap_y +
                          self.gap_height, 24, -24)  # spikes, yikes!
        screen.scale_blit(sprites.sprite(0, 0), self.x,
                          self.gap_y + self.gap_height + 24, 24, -24)
        screen.scale_blit(sprites.sprite(0, 0), self.x,
                          self.gap_y + self.gap_height + 48, 24, -24)
