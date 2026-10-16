from obstacle import Obstacle

sprites = image.load("assets/chicken.png").spritesheet(7, 2)
ALIVE_FRAMES = 7  # row 0
DEAD_FRAMES = 5   # row 1


class Chicken:
    def __init__(self):
        self.pos = (10, 50)
        self.score = 0
        # velocity is in pixels/second and gravity in pixels/second^2 so the
        # game plays the same however fast the display refreshes. these values
        # reproduce the original feel from when the badge ran at 30fps
        # (-4px/frame jump, +9px/frame/s gravity).
        self.velocity = 0
        self.gravity = 270
        self.last_update = None
        self.died_at = None
        self.done_dying = False

    def update(self):
        # don't do any of the chicken update stuff if they're dead
        if self.is_dead():
            return

        if self.last_update:
            # apply gravity to chicken's velocity based on the time since the last update
            time_delta = (badge.ticks - self.last_update) / 1000
            self.velocity = self.velocity + (self.gravity * time_delta)

            # move chicken based on their current velocity and the elapsed time
            self.pos = (self.pos[0], self.pos[1] + self.velocity * time_delta)

            # if chicken falls off the bottom of the screen it's GAME OVER
            if self.pos[1] > 92:
                self.die()

            # but if chicken bangs their head on the ceiling it's ok, we'll just take away any upward momentum
            if self.pos[1] <= 0:
                self.pos = (self.pos[0], 0)
                self.velocity = 0

        self.last_update = badge.ticks

        # check if we've passed or hit any obstacles
        chicken_bounds = self.bounds()
        for obstacle in Obstacle.obstacles:
            # perform an intersection test between chicken's hit box and the hit box
            # of this obstacles top and bottom sections
            for obstacle_bounds in obstacle.bounds():
                x1 = max(obstacle_bounds[0], chicken_bounds[0])
                y1 = max(obstacle_bounds[1], chicken_bounds[1])
                x2 = min(
                    obstacle_bounds[0] + obstacle_bounds[2], chicken_bounds[0] + chicken_bounds[2])
                y2 = min(
                    obstacle_bounds[1] + obstacle_bounds[3], chicken_bounds[1] + chicken_bounds[3])

                if x1 < x2 and y1 < y2:  # true if the two bounds overlap
                    self.die()

            # if we haven't passed this obstacle before but we are past it now then
            # let's have some sweet sweet points!
            if not obstacle.passed and obstacle.x < self.pos[0] - 16:
                obstacle.passed = True
                self.score += 1

    def is_dead(self):
        # return true if chicken has died :-(
        return self.died_at is not None

    def is_done_dying(self):
        # return true once chicken's death animation cycle has completed
        return (badge.ticks - self.died_at) > 900

    def die(self):
        # set the timestamp for when chicken died so we can pace her death animation
        # and redirect to the GAME OVER screen after 1.5 seconds
        if not self.died_at:
            self.died_at = badge.ticks

    def jump(self):
        # up, up, up, and away! (pixels/second)
        self.velocity = -120

    def bounds(self):
        # be a little generous with chickens bounding box for collisions
        return (self.pos[0] + 3, self.pos[1] + 2, 18, 20)

    def draw(self):
        if not self.is_dead():
            # this is a bit gnarly but basically we want to convert chicken's current
            # velocity into the correct animation frame for her motion.
            # velocity is now in pixels/second, so scale it back to the per-frame
            # range (-1..2) the animation frames were authored against.
            frame = max(-1, min(self.velocity / 30, 2)) + 1

            # chickens animation frames are ordered from flying to falling, so scale the
            # clamped velocity to the 0...7 sprites that represent her
            frame = int(frame * 2)
            sprite = sprites.sprite(frame % ALIVE_FRAMES, 0)
            screen.blit(sprite, vec2(self.pos[0], self.pos[1]))
        else:
            # if chicken is dying then play the death animation
            frame = (badge.ticks - self.died_at) / 100
            if frame < DEAD_FRAMES:
                sprite = sprites.sprite(int(frame) % DEAD_FRAMES, 1)
                screen.blit(sprite, vec2(self.pos[0], self.pos[1]))
