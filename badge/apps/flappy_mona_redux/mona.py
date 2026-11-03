import math

from world import GROUND_Y

sprites = image.load("assets/mona.png").spritesheet(7, 2)
ALIVE_FRAMES = 7
DEAD_FRAMES = 5

SIZE = 48
START_X = 20
START_Y = 96
GRAVITY = 420  # while flying
FLAP_SPEED = -120
RUN_GRAVITY = 700  # while running on a tower: a quick hop
RUN_JUMP = -366  # clears a spike or a roller with time to spare
HIT = (6, 4, 36, 40)  # x, y, w, h inside the sprite
HAZARD = (12, 12, 24, 32)  # spikes and rollers use a slimmer box than walls do
FEET = HIT[1] + HIT[3]  # sprite y of the soles of her feet
FLOOR_Y = GROUND_Y + 4 - FEET  # sprite y where her feet reach the lawn

IMMORTAL_SECONDS = 5
DEATH_FRAME_SECONDS = 0.1
DEATH_DELAY_SECONDS = 0.9

LIFT_SPEED = 120  # px/s at which the pop up a stair eases out
BOB_PIXELS = 2  # bounce in her step while she runs
FLAT_SECONDS = 0.15  # how long a roller takes to squash her
FLAT_SIZE = (56, 12)  # width and height of the pancake


class Mona:
    def __init__(self):
        self.x = START_X
        self.y = START_Y
        self.vy = 0
        self.score = 0
        self.immortal = 0.0
        self.dead_for = None
        self.flat = False
        self.running = False  # on a tower's stairs or deck, where Select jumps
        self.grounded = False
        self.ground_y = 0  # the surface she last stood on, which the camera follows
        self.lift = 0.0  # drawn this far below her real position, easing out
        self.run_phase = 0.0

    def is_dead(self):
        return self.dead_for is not None

    def is_done_dying(self):
        return self.dead_for is not None and self.dead_for > DEATH_DELAY_SECONDS

    def is_immortal(self):
        return self.immortal > 0

    def flap(self):
        self.vy = FLAP_SPEED

    def press(self):
        """Select flaps in the air and jumps once she is running on a tower."""
        if not self.running:
            self.flap()
        elif self.grounded:
            self.vy = RUN_JUMP
            self.grounded = False

    def make_immortal(self):
        self.immortal = IMMORTAL_SECONDS

    def die(self):
        if self.dead_for is None:
            self.dead_for = 0.0
            self.immortal = 0.0

    def flatten(self):
        if self.dead_for is None:
            self.die()
            self.flat = True
            self.lift = 0.0
            self.vy = 0

    def update(self, dt, tower=None, cam=0):
        if self.dead_for is not None:
            self.dead_for += dt
            if self.flat:
                self.settle(dt, tower)
            return

        if self.immortal > 0:
            self.immortal = max(0.0, self.immortal - dt)

        prev_feet = self.y + FEET
        if self.grounded:
            self.vy = 0
        else:
            self.vy += (RUN_GRAVITY if self.running else GRAVITY) * dt
            self.y += self.vy * dt

        # the top of the screen is a ceiling, wherever the camera is
        if self.y + cam < 0 and self.vy < 0:
            self.y = -cam
            self.vy = 0

        self.stand_on(tower, prev_feet)

        if self.y > FLOOR_Y:
            if self.immortal > 0:
                self.y = FLOOR_Y
                self.vy = 0
            else:
                self.die()

        if self.lift > 0:
            self.lift = max(0.0, self.lift - LIFT_SPEED * dt)
        if self.grounded:
            self.run_phase += dt

    def settle(self, dt, tower):
        """A flattened Mona drops onto the roof under her and stays pinned there."""
        prev_feet = self.y + FEET
        if not self.grounded:
            self.vy += RUN_GRAVITY * dt
            self.y += self.vy * dt
        self.stand_on(tower, prev_feet)
        if self.y > FLOOR_Y:
            self.y = FLOOR_Y
            self.vy = 0

    def stand_on(self, tower, prev_feet):
        """Land on a tower's stairs or deck, or step up onto a low ledge."""
        left = self.x + HIT[0]
        right = left + HIT[2]
        if tower is None:
            self.running = self.grounded = False
            return
        first, last = tower.span(left, right)
        if first > last:
            self.running = self.grounded = False
            return

        top = tower.landing(prev_feet, self.y + FEET, left, right)
        if top is None:
            self.grounded = False
            return

        stand = top - FEET
        if self.grounded and stand < self.y:
            self.lift += self.y - stand  # draw the step as a quick climb, not a teleport
        self.y = stand
        self.vy = 0
        self.grounded = True
        self.running = True
        self.ground_y = top

    def bounds(self):
        return (self.x + HIT[0], self.y + HIT[1], HIT[2], HIT[3])

    def hazard_box(self):
        return (self.x + HAZARD[0], self.y + HAZARD[1], HAZARD[2], HAZARD[3])

    def center(self):
        return (self.x + SIZE / 2, self.y + SIZE / 2)

    def draw(self, cam=0):
        cam = int(cam)
        if self.flat:
            self.draw_flat(cam)
            return

        bob = 0
        if self.grounded and self.dead_for is None:
            bob = int(BOB_PIXELS * abs(math.sin(self.run_phase * 12)))
        pos = vec2(int(self.x), int(self.y + self.lift) + cam - bob)
        if self.dead_for is None:
            frame = max(-1, min(self.vy / 60, 2)) + 1
            screen.blit(sprites.sprite(int(frame * 2) % ALIVE_FRAMES, 0), pos)
            return

        frame = int(self.dead_for / DEATH_FRAME_SECONDS)
        if frame < DEAD_FRAMES:
            screen.blit(sprites.sprite(frame, 1), pos)

    def draw_flat(self, cam):
        """Squash her sprite flat against the roof, keeping her feet on the floor."""
        squash = max(0.0, 1.0 - self.dead_for / FLAT_SECONDS)
        w = int(FLAT_SIZE[0] - (FLAT_SIZE[0] - SIZE) * squash)
        h = int(FLAT_SIZE[1] + (SIZE - FLAT_SIZE[1]) * squash)
        feet = int(self.y) + FEET + cam
        screen.blit(sprites.sprite(2, 0), rect(int(self.x) - (w - SIZE) // 2, feet - h * FEET // SIZE, w, h))
