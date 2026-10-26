"""Rules for The Octocat Trail.

Pure game logic with no badge runtime globals, so the same code runs on the
badge's MicroPython and under CPython tests. Randomness comes from an
injected Rng, ordered data lives in tuples (MicroPython dicts are unordered),
and only APIs that exist in MicroPython 1.29 are used.
"""

import trail_map as tm
MAX_STEPS = 99999
PARTY = ("Markus", "Mona", "Cameron", "Hubot", "Tufty")
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

# (title, handle, starting Copilot Credits, score multiplier, perk)
ROLES = (
    ("Creative Director", "@wmarkus", 1600, 1, "Deep pockets for a comfortable run."),
    ("Staff Rustacean", "@mona", 1000, 2, "Every Hotfix Patch also heals the party."),
    ("ATC Control Lead", "@kdaigle", 600, 3, "Calm air traffic: safer deploys at rivers."),
)

SUPPLIES = (
    ("credits", "Copilot Credits"),
    ("brew", "Cold Brew Kegs"),
    ("lgtm", "LGTM Stamps"),
    ("patches", "Hotfix Patches"),
)

# (supply key, base price in credits, quantity per press, carry limit, blurb)
STORE_ITEMS = (
    ("brew", 4, 10, 500, "The party drinks about a keg a day."),
    ("lgtm", 1, 10, 300, "Hunt ammo and deploy approvals."),
    ("patches", 25, 1, 9, "Fixes broken CI and reverts force-pushes."),
)
# (stop, price percent): stores and the Firehouse, which only sells patches.
STORE_MARKUP = ((0, 100), (1, 125), (9, 150), (6, 160))
FIREHOUSE = 6

# (name, steps per day, daily health change)
PACES = (
    ("Sustainable", 20, 0),
    ("Crunch", 26, -1),
    ("Death March", 34, -3),
)
DAY_MS = 640
# (name, kegs per person per day, daily health change)
RATIONS = (
    ("Nitro", 0.3, 2),
    ("Drip", 0.2, 1),
    ("Decaf", 0.1, -1),
)

MONTHS = (
    ("September", 30), ("October", 31), ("November", 30), ("December", 31),
    ("January", 31), ("February", 28), ("March", 31), ("April", 30),
    ("May", 31), ("June", 30), ("July", 31), ("August", 31),
)
WEATHER = ("Foggy", "Sunny", "Breezy", "Foggy", "Drizzle", "Karl the Fog", "Sunny", "Cool")

HEALTH_LABELS = ((70, "Good"), (40, "Fair"), (20, "Poor"), (0, "Very poor"))

MASK32 = 0xFFFFFFFF


def clamp(value, low, high):
    if value < low:
        return low
    if value > high:
        return high
    return value


def clamp_int(value, low, high, default=None):
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return low if default is None else default
    return clamp(number, low, high)


def commas(value):
    number = int(value)
    sign = "-" if number < 0 else ""
    digits = str(abs(number))
    tail = ""
    while len(digits) > 3:
        tail = "," + digits[-3:] + tail
        digits = digits[:-3]
    return sign + digits + tail


def tenths(value):
    """Format an integer number of tenths, e.g. 35 -> '3.5'."""
    value = int(value)
    return "%d.%d" % (value // 10, value % 10)


def plural(count, word, suffix="s"):
    return "%d %s%s" % (count, word, "" if count == 1 else suffix)


def fnv1a(text):
    """Deterministic 32-bit string hash; hash(str) differs on MicroPython."""
    value = 0x811C9DC5
    for char in str(text):
        value ^= ord(char) & 0xFF
        value = (value * 0x01000193) & MASK32
    return value


def wrap(text, width, measure):
    """Wrap text into lines no wider than width using a measure(str) function."""
    lines = []
    for paragraph in str(text).split("\n"):
        line = ""
        for word in paragraph.split(" "):
            if not word:
                continue
            trial = word if not line else line + " " + word
            if not line or measure(trial) <= width:
                line = trial
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def health_label(health):
    for floor, label in HEALTH_LABELS:
        if health >= floor:
            return label
    return HEALTH_LABELS[-1][1]


def role_label(index):
    return ROLES[index][0] + " " + ROLES[index][1]


def store_item(key):
    for item in STORE_ITEMS:
        if item[0] == key:
            return item
    raise KeyError(key)


def carry_limit(key):
    return store_item(key)[3]


class Rng:
    """Seeded xorshift32 generator; MicroPython has no random.Random class."""

    def __init__(self, seed=1):
        self.seed(seed)

    def seed(self, value):
        self.state = (int(value) & MASK32) or 0x6D2B79F5

    def next32(self):
        x = self.state
        x ^= (x << 13) & MASK32
        x ^= x >> 17
        x ^= (x << 5) & MASK32
        self.state = x
        return x

    def random(self):
        return (self.next32() >> 8) / 16777216.0

    def randint(self, low, high):
        return low + self.next32() % (high - low + 1)

    def uniform(self, low, high):
        return low + (high - low) * self.random()

    def chance(self, probability):
        return self.random() < probability

    def choice(self, items):
        return items[self.next32() % len(items)]

    def weighted(self, pairs):
        total = 0
        for weight, _item in pairs:
            total += weight
        if total <= 0:
            return None
        pick = self.random() * total
        for weight, item in pairs:
            if pick < weight:
                return item
            pick -= weight
        return pairs[-1][1]


class Member:
    def __init__(self, name):
        self.health = 100
        self.alive = True


class Trail:
    """One journey on foot from the Gatehouse to the Mainstage."""

    def __init__(self, role, rng):
        self.role = clamp_int(role, 0, len(ROLES) - 1)
        self.supplies = {"credits": ROLES[self.role][2], "brew": 0.0, "lgtm": 0, "patches": 0}
        self.members = [Member(name) for name in PARTY]
        self.x = tm.START[0]
        self.y = tm.START[1]
        self.facing = 1
        self.steps = 0
        self.pending_ms = 0
        self.day = 1
        self.pace = 0
        self.rations = 1
        self.at = 0
        self.visited = 1
        self.deployed = 0
        self.basket = {}

    # ----- party -----------------------------------------------------------
    def living(self):
        return [member for member in self.members if member.alive]

    def living_count(self):
        return len(self.living())

    def all_dead(self):
        return self.living_count() == 0

    def average_health(self):
        living = self.living()
        if not living:
            return 0
        total = 0
        for member in living:
            total += member.health
        return total / len(living)

    def party_health(self):
        return health_label(self.average_health())

    def multiplier(self):
        return ROLES[self.role][3]

    def brew_per_day(self):
        need = self.living_count() * RATIONS[self.rations][1]
        return need

    # ----- calendar -----------------------------------------------------------
    def weekday(self):
        # Day 1 is Tuesday, September 1, 2026.
        return WEEKDAYS[self.day % 7]

    def date(self):
        """(month name, day of month, year) for the current day."""
        day = self.day - 1
        cycle = 0
        while day >= 365:
            day -= 365
            cycle += 1
        for index in range(len(MONTHS)):
            name, length = MONTHS[index]
            if day < length:
                return name, day + 1, 2026 + cycle + (1 if index >= 4 else 0)
            day -= length
        return MONTHS[-1][0], MONTHS[-1][1], 2027 + cycle

    def date_text(self):
        name, day, year = self.date()
        return "%s %d, %d" % (name, day, year)

    def weather(self):
        return WEATHER[fnv1a("wx%d" % self.day) % len(WEATHER)]

    # ----- the venue ----------------------------------------------------------
    def current_stop(self):
        return tm.STOPS[self.at] if self.at >= 0 else None

    def at_kind(self, kind):
        return self.at >= 0 and tm.STOPS[self.at][2] == kind

    def finished(self):
        return self.at == tm.END

    def has_visited(self, stop):
        return bool(self.visited & (1 << stop))

    # ----- walking ------------------------------------------------------------
    def steps_per_day(self):
        steps = PACES[self.pace][1]
        if self.supplies["brew"] <= 0:
            steps = steps * 3 // 4
        if self.average_health() < 40:
            steps = steps * 4 // 5
        return max(tm.STEPS_PER_TILE, steps)

    def tile_ms(self):
        """How long one tile takes to walk; DAY_MS is one day on the move."""
        return DAY_MS * tm.STEPS_PER_TILE // self.steps_per_day()

    def blocked_reason(self, dx, dy):
        """Why the party cannot step this way, or "" if it can."""
        x = self.x + dx
        y = self.y + dy
        if tm.walkable(x, y, self.deployed):
            return ""
        code = tm.terrain(x, y)
        if code == tm.WATER:
            return "That way lies San Francisco Bay."
        return ""

    def step(self, dx, dy):
        """Walk one tile. Returns how long the walk takes in ms, or 0 if blocked."""
        if dx:
            self.facing = 1 if dx > 0 else -1
        if self.all_dead() or (dx == 0 and dy == 0):
            return 0
        x = self.x + dx
        y = self.y + dy
        if not tm.walkable(x, y, self.deployed):
            return 0
        self.x = x
        self.y = y
        self.at = -1
        self.steps = min(MAX_STEPS, self.steps + tm.STEPS_PER_TILE)
        ms = self.tile_ms()
        self.pending_ms += ms
        return ms

    def after_step(self):
        """Finish a step: pass time, roll events and check for a stop.

        Returns (lines, outcome); outcome is None, "stop", "river",
        "victory" or "game_over"."""
        lines = []
        if self.all_dead():
            return lines, "game_over"
        stop = tm.stop_at(self.x, self.y)
        if stop < 0 or stop == self.at:
            return lines, None
        return lines, self.arrive(stop, lines)

    def arrive(self, stop, lines):
        """Reach a stop. Returns "stop", "river" or "victory"."""
        self.at = stop
        self.basket = {}
        kind = tm.STOPS[stop][2]
        self.visited |= 1 << stop
        if kind == "end":
            return "victory"
        return "stop"

    # ----- shop -------------------------------------------------------------
    def markup(self):
        """Price percent at the current stop, or 0 if it has no store."""
        for stop, percent in STORE_MARKUP:
            if stop == self.at:
                return percent
        return 0

    def at_store(self):
        return self.markup() > 0

    def store_keys(self):
        if self.at == FIREHOUSE:
            return ("patches",)
        return ("brew", "lgtm", "patches")

    def price(self, key):
        percent = self.markup() or 100
        return (store_item(key)[1] * percent + 99) // 100

    def buy(self, key, quantity):
        """Buy up to quantity, limited by carry space and credits."""
        price = self.price(key)
        room = int(carry_limit(key) - self.supplies[key])
        quantity = min(int(quantity), room, self.supplies["credits"] // price)
        if quantity <= 0:
            return 0
        self.supplies["credits"] -= quantity * price
        self.supplies[key] += quantity
        self.basket[key] = self.basket.get(key, 0) + quantity
        return quantity

    def sell_back(self, key, quantity):
        """Return supplies bought on this visit, at the price paid."""
        quantity = min(int(quantity), int(self.supplies[key]), self.basket.get(key, 0))
        if quantity <= 0:
            return 0
        self.supplies[key] -= quantity
        self.basket[key] -= quantity
        self.supplies["credits"] += quantity * self.price(key)
        return quantity
