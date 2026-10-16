import random

sprites = image.load("assets/obstacles.png").spritesheet(2, 1)


class Obstacle:
    # the list of active obstacles
    obstacles = []
    next_spawn_time = None

    def spawn():
        # create a new obstacle and reset the obstacle spawn timer
        Obstacle.obstacles.append(Obstacle())
        Obstacle.next_spawn_time = badge.ticks + 2500

        # clean up any obstacles that are now off screen and can be removed
        Obstacle.obstacles = [o for o in Obstacle.obstacles if o.x > -32]

    def __init__(self):
        # position the new obstacle off the right hand side of the screen and
        # randomise the height of the gap
        self.x = screen.width
        self.gap_height = 50
        self.gap_y = random.randrange(10, screen.height - self.gap_height - 20, 5)

        # when chicken passes an obstacle we flag it so the score is only increased once
        self.passed = False

    def update(self):
        # move the obstacle left at a framerate-independent 30 pixels/second
        # (was one pixel per frame back when the badge ran at 30fps)
        self.x -= 30 * (badge.ticks_delta / 1000)

    def bounds(self):
        # be a little generous with obstacle bounding boxes for collisions
        return (
            (self.x, 0, 32, self.gap_y - 6),
            (self.x, self.gap_y + self.gap_height + 6,
                32, 120 - self.gap_y + self.gap_height - 6)
        )

    def draw(self):
        # draw the top half off the obstacle
        screen.blit(sprites.sprite(0, 0),
                    rect(self.x, self.gap_y - 72, 32, 32))
        screen.blit(sprites.sprite(0, 0),
                    rect(self.x, self.gap_y - 48, 32, 32))
        screen.blit(sprites.sprite(1, 0),
                    rect(self.x, self.gap_y - 32, 32, 32))  # spikes, yikes!

        # draw the bottom half off the obstacle
        screen.blit(sprites.sprite(1, 0),
                    rect(self.x, self.gap_y + self.gap_height, 32, -32))  # spikes, yikes!
        screen.blit(sprites.sprite(0, 0),
                    rect(self.x, self.gap_y + self.gap_height + 32, 32, -32))
        screen.blit(sprites.sprite(0, 0),
                    rect(self.x, self.gap_y + self.gap_height + 48, 32, -32))
