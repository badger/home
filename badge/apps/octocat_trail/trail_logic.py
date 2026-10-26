"""Rules for The Octocat Trail.

Pure game logic with no badge runtime globals, so the same code runs on the
badge's MicroPython and under CPython tests. Randomness comes from an
injected Rng, ordered data lives in tuples (MicroPython dicts are unordered),
and only APIs that exist in MicroPython 1.29 are used.
"""
PARTY = ("Markus", "Mona", "Cameron", "Hubot", "Tufty")

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
# (name, kegs per person per day, daily health change)
RATIONS = (
    ("Nitro", 0.3, 2),
    ("Drip", 0.2, 1),
    ("Decaf", 0.1, -1),
)

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
        self.members = [Member(name) for name in PARTY]
        self.rations = 1

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
