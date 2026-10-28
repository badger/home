"""Mona Swim simulation. No display dependencies; distances are in pixels."""

import math
import random

LEFT, TOP, RIGHT, BOTTOM = 12, 44, 308, 222
MONA_RADIUS = 10
TAIL_RADIUS = 4
SHARK_RADIUS = 12
SPACING = 4.0
START_LENGTH = 16
GROWTH = 6
SHARK_WARNING_MS = 1800
LANES = (82, 178, 130)


def distance2(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


class Shark:
    def __init__(self, index):
        self.x = RIGHT - 24 if index % 2 == 0 else LEFT + 24
        self.y = LANES[index]
        self.direction = -1 if index % 2 == 0 else 1
        self.warning = SHARK_WARNING_MS

    def step(self, dt, level):
        if self.warning > 0:
            self.warning = max(0, self.warning - dt)
            return
        self.x += self.direction * (0.030 + min(level - 1, 6) * 0.003) * dt
        low, high = LEFT + 24, RIGHT - 24
        if self.x < low:
            self.x = low + (low - self.x)
            self.direction = 1
        elif self.x > high:
            self.x = high - (self.x - high)
            self.direction = -1


class Swim:
    def __init__(self):
        self.reset()

    @property
    def level(self):
        return 1 + self.score // 5

    @property
    def speed(self):
        return min(0.105, 0.062 + (self.level - 1) * 0.006)

    def reset(self):
        self.head = (160.0, 144.0)
        self.heading = -math.pi / 2
        self.path = [(160.0, 144.0 + i * SPACING) for i in range(START_LENGTH)]
        self.target_length = START_LENGTH
        self.since_sample = 0.0
        self.score = 0
        self.elapsed = 0
        self.dead = False
        self.reason = ""
        self.sharks = [Shark(0)]
        self.floatie = None
        self.splash = 0
        self.spawn_floatie()

    def safe_floatie(self, point):
        # Leave enough room to approach a pickup, including the patrol lanes.
        return (distance2(point, self.head) >= 36 ** 2
                and all(distance2(point, p) >= 20 ** 2 for p in self.path)
                and all(abs(point[1] - s.y) >= 22 for s in self.sharks))

    def spawn_floatie(self):
        for _ in range(80):
            point = (random.randint(LEFT + 22, RIGHT - 22),
                     random.randint(TOP + 18, BOTTOM - 18))
            if self.safe_floatie(point):
                self.floatie = point
                return
        # A finite search prevents a full pool from hanging the badge.
        for y in range(TOP + 18, BOTTOM - 17, 4):
            for x in range(LEFT + 22, RIGHT - 21, 4):
                if self.safe_floatie((x, y)):
                    self.floatie = (x, y)
                    return
        self.floatie = None
        self.finish("Pool party complete!")

    def finish(self, reason):
        self.dead = True
        self.reason = reason

    def step(self, dt, steering=0):
        if self.dead:
            return
        # Small physics steps catch collisions even when a display frame stalls.
        remaining = min(max(dt, 0), 80)
        while remaining > 0 and not self.dead:
            step = min(remaining, 16)
            remaining -= step
            self.advance(step, max(-1, min(1, steering)))

    def advance(self, dt, steering):
        self.elapsed += dt
        self.splash = max(0, self.splash - dt)
        # Constant turning radius as the game speeds up.
        self.heading += steering * 0.0043 * (self.speed / 0.062) * dt
        old = self.head
        travel = self.speed * dt
        dx, dy = math.cos(self.heading), math.sin(self.heading)
        self.head = (old[0] + dx * travel, old[1] + dy * travel)
        at = SPACING - self.since_sample
        while at <= travel:
            self.path.insert(0, (old[0] + dx * at, old[1] + dy * at))
            at += SPACING
        self.since_sample = (self.since_sample + travel) % SPACING
        del self.path[self.target_length:]

        for shark in self.sharks:
            shark.step(dt, self.level)

        x, y = self.head
        if (x < LEFT + MONA_RADIUS or x > RIGHT - MONA_RADIUS
                or y < TOP + MONA_RADIUS or y > BOTTOM - MONA_RADIUS):
            self.finish("You bumped the pool edge!")
        elif any(distance2(self.head, p) < (MONA_RADIUS + TAIL_RADIUS) ** 2
                 for p in self.path[8:]):
            self.finish("Tangled in your floaties!")
        elif any(s.warning <= 0 and distance2(self.head, (s.x, s.y))
                 < (MONA_RADIUS + SHARK_RADIUS) ** 2 for s in self.sharks):
            self.finish("Shark in the swimming lane!")
        elif self.floatie is not None and distance2(self.head, self.floatie) < 17 ** 2:
            self.score += 1
            self.target_length += GROWTH
            self.splash = 350
            wanted = min(3, 1 + self.score // 5)
            if len(self.sharks) < wanted:
                self.sharks.append(Shark(len(self.sharks)))
            self.spawn_floatie()
