from fish import Fish
from world import HEIGHT, SPEED, WIDTH, overlaps

# Floating islands of brick: stairs up the left, a deck on top, then steps down
# the right. The big roof also has spikes and rollers. A low tunnel runs
# underneath every island, so climbing is always optional. Positions are world
# coordinates (a tall deck sits above y=0); Course and Mona add the camera
# offset when they draw.

roof = image.load("assets/roof.png").spritesheet(6, 1)
lip = image.load("assets/roof_lip.png").spritesheet(2, 1)
underside = image.load("assets/roof_under.png")
spike_art = image.load("assets/spike.png")
roller_art = image.load("assets/roller.png").spritesheet(4, 1)

STRIPS = [roof.sprite(i, 0) for i in range(6)]  # index = course * 2 + column parity
LIPS = [lip.sprite(i, 0) for i in range(2)]
ROLLER_FRAMES = [roller_art.sprite(i, 0) for i in range(4)]

WALL, SPIKE, ROLLER = 1, 2, 3  # what hits() can report

COL = 24  # width of one brick column
COURSE = 16  # height of one course of bricks
LIP_H = 4
UNDER_W = 48
UNDER_H = 20

FIRST_TREAD_Y = 88  # top of the lowest stair
TREAD_RISE = 16
UNDERSIDE_Y = 124  # bottom of the artwork
INSET = 4  # forgiving margin between the underside art and its hit area
STEP_UP = 20  # tallest ledge Mona can haul herself onto
MASS_BOTTOM = UNDERSIDE_Y - INSET

DECK_SCREEN_Y = 150  # where a deck sits on screen while Mona is up there

SPIKE_H = 14
SPIKE_HIT = (2, 2, 12, 12)  # x, y, w, h inside the artwork

ROLLER_SIZE = 32
ROLLER_HIT = (3, 4, 26, 28)  # x, y, w, h inside the artwork
ROLLER_SPEED = 60  # px/s along the roof, on top of the tower's own scroll
RELEASE_X = WIDTH + 10  # a roller waits off screen until it gets this close
ROLLER_LEAD = 137  # a roller waiting at roof x meets Mona where a spike at x - ROLLER_LEAD would
ROLLER_STARTS = tuple(meet + ROLLER_LEAD for meet in (160, 320))
ROLLER_FRAME_PX = 6.25  # px rolled per frame: a 22.5 degree turn of the 16 px radius drum



class Layout:
    """The shape of one tower: stairs up, a flat deck, stairs down, and what sits on the deck."""

    def __init__(self, up, deck_cols, down, spikes=(), rollers=(), fish=(), fish_lift=124):
        self.deck_y = FIRST_TREAD_Y - TREAD_RISE * up  # surface of the deck
        self.deck_start = up * COL  # x of the deck, measured from the tower's left edge
        self.tops = tuple(
            [FIRST_TREAD_Y - TREAD_RISE * i for i in range(up)]
            + [self.deck_y] * deck_cols
            + [self.deck_y + TREAD_RISE * (i + 1) for i in range(down)]
        )
        self.columns = len(self.tops)  # must be even: the underside is tiled two columns at a time
        self.length = self.columns * COL
        self.spikes = spikes  # deck x of each spike
        self.rollers = rollers  # deck x where each roller waits
        self.fish = fish  # deck x of each fish
        self.fish_y = self.deck_y - fish_lift  # the default sits level with the top of a jump
        self.cam_max = DECK_SCREEN_Y - self.deck_y  # how far the camera rises to show the deck


LAYOUTS = {
    # the big one: a long deck of spikes and rollers that ends on a cliff
    "roof": Layout(8, 20, 4, spikes=(76, 240), rollers=ROLLER_STARTS, fish=(224, 300)),
    # a lower deck with one spike and stairs all the way back down
    "hill": Layout(6, 8, 6, spikes=(96,), fish=(80,)),
    # a short hop up and over with nothing to fear and a fish to jump for
    "steps": Layout(4, 4, 4, fish=(24,), fish_lift=96),
}


class Tower:
    def __init__(self, layout):
        self.layout = layout
        self.x = float(WIDTH)
        self.passed = False

    def update(self, dt):
        self.x -= SPEED * dt

    def right_end(self):
        return self.x + self.layout.length

    def make_fish(self):
        layout = self.layout
        left = self.x + layout.deck_start
        return [Fish(left + u, layout.fish_y) for u in layout.fish]

    def camera_for(self, ground_y):
        """How far the camera rises while Mona stands at this height on the tower."""
        layout = self.layout
        t = (FIRST_TREAD_Y - ground_y) / (FIRST_TREAD_Y - layout.deck_y)
        return layout.cam_max * max(0.0, min(1.0, t))

    def span(self, left, right):
        """The first and last columns that a box from left to right overlaps."""
        first = max(0, int((left - self.x) // COL))
        last = min(self.layout.columns - 1, int((right - self.x - 0.001) // COL))
        return first, last

    def landing(self, prev_feet, feet, left, right):
        """Top of the highest column Mona can stand on or step up onto, if any."""
        tops = self.layout.tops
        first, last = self.span(left, right)
        best = None
        for c in range(first, last + 1):
            top = tops[c]
            if feet >= top and prev_feet <= top + STEP_UP and (best is None or top < best):
                best = top
        return best

    def roller_x(self, start):
        """Screen x of a roller and how far it has rolled; it speeds up once released."""
        s = self.x + self.layout.deck_start + start
        rolled = max(0.0, RELEASE_X - s) * ROLLER_SPEED / SPEED
        return s - rolled, rolled

    def hits(self, box, hazard):
        layout = self.layout
        tops = layout.tops
        first, last = self.span(box[0], box[0] + box[2])
        for c in range(first, last + 1):
            top = tops[c]
            if overlaps((self.x + c * COL, top, COL, MASS_BOTTOM - top), box):
                return WALL

        spike_top = layout.deck_y - SPIKE_H
        for u in layout.spikes:
            x = self.x + layout.deck_start + u + SPIKE_HIT[0]
            if overlaps((x, spike_top + SPIKE_HIT[1], SPIKE_HIT[2], SPIKE_HIT[3]), hazard):
                return SPIKE

        roller_top = layout.deck_y - ROLLER_SIZE
        for start in layout.rollers:
            x, _ = self.roller_x(start)
            if overlaps((x + ROLLER_HIT[0], roller_top + ROLLER_HIT[1], ROLLER_HIT[2], ROLLER_HIT[3]), hazard):
                return ROLLER
        return None

    def draw(self, cam=0):
        layout = self.layout
        tops = layout.tops
        cam = int(cam)
        base = int(self.x)
        first = max(0, (-base) // COL)
        last = min(layout.columns - 1, (WIDTH - base) // COL)
        course_end = UNDERSIDE_Y - UNDER_H

        for c in range(first, last + 1):
            sx = base + c * COL
            top = tops[c]
            half = c % 2
            y = top
            if y + cam + COURSE <= 0:
                y += ((-cam - COURSE - y) // COURSE + 1) * COURSE  # skip courses above the screen
            while y < course_end and y + cam < HEIGHT:
                index = (y - FIRST_TREAD_Y) // COURSE % 3 * 2 + half
                screen.blit(STRIPS[index], vec2(sx, y + cam))
                y += COURSE
            if -LIP_H < top + cam < HEIGHT:
                screen.blit(LIPS[half], vec2(sx, top + cam))

        under_y = course_end + cam
        if under_y < HEIGHT:
            for j in range(max(0, (-base) // UNDER_W), min(layout.length // UNDER_W - 1, (WIDTH - base) // UNDER_W) + 1):
                screen.blit(underside, vec2(base + j * UNDER_W, under_y))

        spike_y = layout.deck_y - SPIKE_H + cam
        if -SPIKE_H < spike_y < HEIGHT:
            for u in layout.spikes:
                sx = base + layout.deck_start + u
                if -16 < sx < WIDTH:
                    screen.blit(spike_art, vec2(sx, spike_y))

        roller_y = layout.deck_y - ROLLER_SIZE + cam
        if -ROLLER_SIZE < roller_y < HEIGHT:
            for start in layout.rollers:
                x, rolled = self.roller_x(start)
                if -ROLLER_SIZE < x < WIDTH:
                    # rolling left turns the drum anticlockwise, so count the frames backwards
                    frame = ROLLER_FRAMES[-int(rolled / ROLLER_FRAME_PX) % 4]
                    screen.blit(frame, vec2(int(x), roller_y))
