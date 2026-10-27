import math
import os
import random

APP_DIR = "/system/apps/autogpt_bounce"
os.chdir(APP_DIR)

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

NAVY = color.rgb(0, 1, 49)
WHITE = color.rgb(255, 255, 255)
SKY = color.rgb(102, 156, 246)
BRAND = [(0.0, color.rgb(66, 133, 244)), (1.0, color.rgb(153, 0, 255))]

# Same pace as the Sparkle show's bouncing Invertocat, doubled for HIRES.
SPEED = 36
MAX_STEP_MS = 100
SWAP_COOLDOWN_MS = 400
CORNER_MS = 120

LED_COUNT = 4
LED_MINIMUM = 0.025
LED_MAXIMUM = 0.68
FLASH_MS = 450
CORNER_FLASH_MS = 1600

PORTRAIT_RADIUS = 32
RING = 3

# Mona Sans draws its cap height from about 0.34 to 1.02 of the font size below
# the text origin; descenders reach 1.17. Items bounce on the visible ink.
CAP_TOP = 0.34
BASELINE = 1.02
DESCENDER = 1.17

EXPERTS = (
    ("otto", "Otto", "Head of AI"),
    ("maria", "Maria", "SEO Content Manager"),
    ("max", "Max", "Account Executive"),
    ("frankie", "Frankie", "Executive Assistant"),
    ("jules", "Jules", "Social Media Manager"),
    ("nadia", "Nadia", "Market Research Analyst"),
    ("alex", "Alex", "Product Manager"),
    ("devon", "Devon", "Application Security Engineer"),
    ("casey", "Casey", "QA Engineer"),
    ("riley", "Riley", "Customer Success Manager"),
    ("quinn", "Quinn", "Data Analyst"),
    ("mina", "Mina", "Bookkeeper"),
)

sans = font.load("/system/assets/fonts/MonaSans-Medium.af")
ring = brush.gradient(brush.LINEAR, 0.0, 0.0, 1.0, 1.0, BRAND, mat3())


class Line:
    def __init__(self, text, size, pen):
        self.text = text
        self.size = size
        self.pen = pen
        screen.font = sans
        self.w, _ = screen.measure_text(text, font_size=size)
        bottom = DESCENDER if any(c in "gjpqy," for c in text) else BASELINE
        self.h = (bottom - CAP_TOP) * size

    def draw(self, centre_x, top):
        screen.font = sans
        screen.pen = self.pen
        screen.text(self.text, round(centre_x - self.w / 2), round(top - CAP_TOP * self.size), self.size)


class Item:
    def show(self):
        pass

    def hide(self):
        pass


class Picture(Item):
    def __init__(self, path):
        self.image = image.load(path)
        self.w = self.image.width
        self.h = self.image.height

    def draw(self, x, y):
        screen.blit(self.image, vec2(x, y))


class Words(Item):
    def __init__(self, *lines):
        self.lines = []
        self.w = 0
        self.h = 0
        for text, size, pen in lines:
            line = Line(text, size, pen)
            if self.lines:
                self.h += size // 4
            self.lines.append((line, self.h))
            self.w = max(self.w, line.w)
            self.h += line.h

    def draw(self, x, y):
        for line, top in self.lines:
            line.draw(x + self.w / 2, y + top)


class Expert(Item):
    def __init__(self, slug, name, role):
        self.path = f"assets/experts/{slug}.png"
        self.portrait = None
        self.name = Line(name, 17, WHITE)
        self.role = Line(role, 12, SKY)
        diameter = (PORTRAIT_RADIUS + RING) * 2
        self.name_top = diameter + 6
        self.role_top = self.name_top + self.name.h + 4
        self.w = max(diameter, self.name.w, self.role.w)
        self.h = self.role_top + self.role.h

    def show(self):
        self.portrait = image.load(self.path)

    def hide(self):
        self.portrait = None

    def draw(self, x, y):
        outer = PORTRAIT_RADIUS + RING
        centre_x = x + self.w / 2
        left = round(centre_x - PORTRAIT_RADIUS)
        ring.geometry(0.0, 0.0, 1.0, 1.0, mat3().translate(left - RING, y).scale(outer * 2, outer * 2))
        screen.pen = ring
        screen.shape(shape.circle(left + PORTRAIT_RADIUS, y + outer, outer))
        screen.blit(self.portrait, vec2(left, y + RING))
        self.name.draw(centre_x, y + self.name_top)
        self.role.draw(centre_x, y + self.role_top)


class Playlist:
    """The logo, then an Expert, then something else, round and round."""

    def __init__(self):
        self.logo = Picture("assets/logo.png")
        self.experts = [Expert(*expert) for expert in EXPERTS]
        self.extras = [
            Picture("assets/mark.png"),
            Words(("YOUR TEAM OF", 13, SKY), ("AI EXPERTS", 28, WHITE)),
            Words(("agpt.co", 30, WHITE)),
            Words(("Let Otto", 24, WHITE), ("coordinate.", 24, SKY)),
            Words(("185K+ stars", 24, WHITE), ("on GitHub", 13, SKY)),
        ]
        self.slot = 0
        self.expert = 0
        self.extra = 0
        self.current = self.logo
        self.current.show()

    def advance(self):
        self.current.hide()
        self.slot = (self.slot + 1) % 3
        if self.slot == 0:
            self.current = self.logo
        elif self.slot == 1:
            self.current = self.experts[self.expert]
            self.expert = (self.expert + 1) % len(self.experts)
        else:
            self.current = self.extras[self.extra]
            self.extra = (self.extra + 1) % len(self.extras)
        self.current.show()
        return self.current


class Bouncer:
    def __init__(self, item):
        self.item = item
        self.x = random.randint(0, int(screen.width - item.w))
        self.y = random.randint(0, int(screen.height - item.h))
        self.vx = SPEED if random.randint(0, 1) else -SPEED
        self.vy = SPEED if random.randint(0, 1) else -SPEED

    def limits(self):
        return screen.width - self.item.w, screen.height - self.item.h

    def step(self, seconds):
        self.x += self.vx * seconds
        self.y += self.vy * seconds
        limit_x, limit_y = self.limits()
        hit_x = hit_y = False
        if self.x <= 0:
            self.x, self.vx, hit_x = -self.x, abs(self.vx), True
        elif self.x >= limit_x:
            self.x, self.vx, hit_x = 2 * limit_x - self.x, -abs(self.vx), True
        if self.y <= 0:
            self.y, self.vy, hit_y = -self.y, abs(self.vy), True
        elif self.y >= limit_y:
            self.y, self.vy, hit_y = 2 * limit_y - self.y, -abs(self.vy), True
        self.x = max(0, min(limit_x, self.x))
        self.y = max(0, min(limit_y, self.y))
        return hit_x, hit_y

    def swap(self, item, hit_x, hit_y):
        # Pin the new item to the wall that was just hit so the bounce reads as
        # one motion; on the other axis keep it centred on the old item.
        centre_x = self.x + self.item.w / 2
        centre_y = self.y + self.item.h / 2
        self.item = item
        limit_x, limit_y = self.limits()
        if hit_x:
            self.x = 0 if self.vx > 0 else limit_x
        else:
            self.x = max(0, min(limit_x, centre_x - item.w / 2))
            # A bigger item can land against a wall; turn it around quietly
            # instead of counting a second bounce.
            if (self.x <= 0 and self.vx < 0) or (self.x >= limit_x and self.vx > 0):
                self.vx = -self.vx
        if hit_y:
            self.y = 0 if self.vy > 0 else limit_y
        else:
            self.y = max(0, min(limit_y, centre_y - item.h / 2))
            if (self.y <= 0 and self.vy < 0) or (self.y >= limit_y and self.vy > 0):
                self.vy = -self.vy

    def draw(self):
        self.item.draw(round(self.x), round(self.y))


class Lights:
    def __init__(self):
        self.leds = [(random.randint(0, 999), random.randint(700, 1200)) for _ in range(LED_COUNT)]
        self.flash_at = None
        self.corner_at = None

    def flash(self, corner=False):
        self.flash_at = badge.ticks
        if corner:
            self.corner_at = badge.ticks

    def update(self):
        now = badge.ticks
        if self.corner_at is not None and now - self.corner_at < CORNER_FLASH_MS:
            level = 1.0 if (now - self.corner_at) // 100 % 2 == 0 else 0.1
            badge.caselights(level, level, level, level)
            return
        flash = 0.0
        if self.flash_at is not None:
            flash = max(0.0, 1.0 - (now - self.flash_at) / FLASH_MS)
        levels = []
        for offset, period in self.leds:
            phase = ((now + offset) % period) / period
            envelope = (math.sin(phase * math.pi * 2 - math.pi / 2) + 1) / 2
            levels.append(max(flash, LED_MINIMUM + envelope * (LED_MAXIMUM - LED_MINIMUM)))
        badge.caselights(*levels)


random.seed(badge.ticks)
playlist = Playlist()
bouncer = Bouncer(playlist.current)
lights = Lights()
swapped_at = None
hit_at = [None, None]
previous_clear = badge.default_clear
badge.default_clear = NAVY


def update():
    global swapped_at

    now = badge.ticks
    if badge.pressed(BUTTON_SELECT):
        bouncer.swap(playlist.advance(), False, False)
        swapped_at = now
        lights.flash()

    hit_x, hit_y = bouncer.step(min(badge.ticks_delta, MAX_STEP_MS) / 1000)
    if hit_x or hit_y:
        if hit_x:
            hit_at[0] = now
        if hit_y:
            hit_at[1] = now
        lights.flash(None not in hit_at and abs(hit_at[0] - hit_at[1]) <= CORNER_MS)
        # Near-corner double bounces only change the item once.
        if swapped_at is None or now - swapped_at >= SWAP_COOLDOWN_MS:
            bouncer.swap(playlist.advance(), hit_x, hit_y)
            swapped_at = now

    bouncer.draw()
    lights.update()


def on_exit():
    badge.caselights(0)
    badge.default_clear = previous_clear


run(update)
