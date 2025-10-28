from badgeware import screen, SpriteSheet, io
from obstacle import Obstacle

sprites = SpriteSheet("assets/mona.png", 7, 2)
alive = sprites.animation(0, 0, 7)
dead = sprites.animation(0, 1, 5)


class Mona:
    def __init__(self):
        self.pos = (10, 50)
        self.score = 0
        self.velocity = 0
        self.gravity = 7
        self.last_update = None
        self.died_at = None
        self.done_dying = False

    def update(self):
        # don't do any of the mona update stuff if they're dead
        if self.is_dead():
            return

        if self.last_update:
            # apply gravity to mona's velocity based on the time since the last update
            time_delta = (io.ticks - self.last_update) / 1000
            self.velocity = self.velocity + (self.gravity * time_delta)

            # move mona based on their current velocity
            self.pos = (self.pos[0], self.pos[1] + self.velocity)

            # if mona falls off the bottom of the screen it's GAME OVER
            if self.pos[1] > 92:
                self.die()

            # but if mona bangs their head on the ceiling it's ok, we'll just take away any upward momentum
            if self.pos[1] <= 0:
                self.pos = (self.pos[0], 0)
                self.velocity = 0

        self.last_update = io.ticks

        # check if we've passed or hit any obstacles
        mona_bounds = self.bounds()
        for obstacle in Obstacle.obstacles:
            # perform an intersection test between mona's hit box and the hit box
            # of this obstacles top and bottom sections
            for obstacle_bounds in obstacle.bounds():
                x1 = max(obstacle_bounds[0], mona_bounds[0])
                y1 = max(obstacle_bounds[1], mona_bounds[1])
                x2 = min(
                    obstacle_bounds[0] + obstacle_bounds[2], mona_bounds[0] + mona_bounds[2])
                y2 = min(
                    obstacle_bounds[1] + obstacle_bounds[3], mona_bounds[1] + mona_bounds[3])

                if x1 < x2 and y1 < y2:  # true if the two bounds overlap
                    self.die()

            # if we haven't passed this obstacle before but we are past it now then
            # let's have some sweet sweet points!
            if not obstacle.passed and obstacle.x < self.pos[0]:
                obstacle.passed = True
                self.score += 1

    def is_dead(self):
        # return true if mona has died :-(
        return self.died_at is not None

    def is_done_dying(self):
        # return true once mona's death animation cycle has completed
        return (io.ticks - self.died_at) > 1500

    def die(self):
        # set the timestamp for when mona died so we can pace her death animation
        # and redirect to the GAME OVER screen after 1.5 seconds
        if not self.died_at:
            self.died_at = io.ticks

    def jump(self):
        # up, up, up, and away!
        self.velocity = -2

    def bounds(self):
        # be a little generous with monas bounding box for collisions
        return (self.pos[0] + 3, self.pos[1] + 2, 18, 20)

    def draw(self):
        if not self.is_dead():
            # this is a bit gnarly but basically we want to convert mona's currently
            # velocity into the correct animation frame for her motion.
            # clamp velocity to between 0 and 3
            frame = max(-1, min(self.velocity, 2)) + 1

            # monas animation frames are ordered from flying to falling, so scale the
            # clamped velocity to the 0...7 sprites that represent her
            frame = int(frame * 2)
            sprite = alive.frame(int(frame))
            screen.blit(sprite, self.pos[0], self.pos[1])
        else:
            # if mona is dying then play the death animation
            frame = (io.ticks - self.died_at) / 100
            if frame < dead.count():
                sprite = dead.frame(frame)
                screen.blit(sprite, self.pos[0], self.pos[1])
