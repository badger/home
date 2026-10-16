from obstacle import Obstacle

sprites = image.load("assets/mona.png").spritesheet(7, 2)
ALIVE_FRAMES = 7
DEAD_FRAMES = 5


class Mona:
    def __init__(self):
        self.pos = (10, 50)
        self.score = 0
        self.velocity = 0
        self.gravity = 210
        self.last_update = None
        self.died_at = None

    def update(self):
        if self.is_dead():
            return

        if self.last_update is not None:
            time_delta = (badge.ticks - self.last_update) / 1000
            self.velocity += self.gravity * time_delta
            self.pos = (
                self.pos[0],
                self.pos[1] + self.velocity * time_delta,
            )

            if self.pos[1] > screen.height - 28:
                self.die()
            elif self.pos[1] <= 0:
                self.pos = (self.pos[0], 0)
                self.velocity = 0

        self.last_update = badge.ticks

        mona_bounds = self.bounds()
        for obstacle in Obstacle.obstacles:
            for obstacle_bounds in obstacle.bounds():
                x1 = max(obstacle_bounds[0], mona_bounds[0])
                y1 = max(obstacle_bounds[1], mona_bounds[1])
                x2 = min(
                    obstacle_bounds[0] + obstacle_bounds[2],
                    mona_bounds[0] + mona_bounds[2],
                )
                y2 = min(
                    obstacle_bounds[1] + obstacle_bounds[3],
                    mona_bounds[1] + mona_bounds[3],
                )

                if x1 < x2 and y1 < y2:
                    self.die()

            if not obstacle.passed and obstacle.x < self.pos[0]:
                obstacle.passed = True
                self.score += 1

    def is_dead(self):
        return self.died_at is not None

    def is_done_dying(self):
        return badge.ticks - self.died_at > 900

    def die(self):
        if self.died_at is None:
            self.died_at = badge.ticks

    def jump(self):
        self.velocity = -60

    def bounds(self):
        return (self.pos[0] + 3, self.pos[1] + 2, 18, 20)

    def draw(self):
        if not self.is_dead():
            frame = max(-1, min(self.velocity / 30, 2)) + 1
            sprite = sprites.sprite(int(frame * 2) % ALIVE_FRAMES, 0)
            screen.blit(sprite, vec2(self.pos[0], self.pos[1]))
            return

        frame = int((badge.ticks - self.died_at) / 100)
        if frame < DEAD_FRAMES:
            sprite = sprites.sprite(frame, 1)
            screen.blit(sprite, vec2(self.pos[0], self.pos[1]))
