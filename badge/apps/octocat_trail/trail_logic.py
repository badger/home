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
RUSTACEAN = 1

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
TRAIL_WEAR = 1
REST_HEAL = 5
DRY_STRAIN = 7
SICK_DANGER = 35
SICK_DEATH = 0.12
# (stop, supply or "health", amount, line) granted on the first visit.
SIGHTS = (
    (2, "lgtm", 20, "The maintainers stamped 20 LGTMs for the road."),
    (3, "health", 10, "Hugs all round at GitHub Central. Health +10."),
    (4, "patches", 1, "An expert pair-programmed you a Hotfix Patch."),
    (5, "brew", 15, "A recruiter slipped you 15 Cold Brew Kegs."),
    (10, "health", 10, "A standing ovation lifts every spirit. Health +10."),
)
HEAL_DAYS = 5
HEAL_AMOUNT = 15

MONTHS = (
    ("September", 30), ("October", 31), ("November", 30), ("December", 31),
    ("January", 31), ("February", 28), ("March", 31), ("April", 30),
    ("May", 31), ("June", 30), ("July", 31), ("August", 31),
)
WEATHER = ("Foggy", "Sunny", "Breezy", "Foggy", "Drizzle", "Karl the Fog", "Sunny", "Cool")

CAUSES = (
    "node_modules dysentery",
    "AI Slop Fever",
    "YAML indentation fatigue",
    "a merge-queue migraine",
    "exhaustion",
    "caffeine withdrawal",
    "an unresolved merge conflict",
    "DNS propagation",
    "a Python 2 dependency",
    "a Friday force-push",
)
CAUSE_EXHAUSTION = 4
CAUSE_WITHDRAWAL = 5
CAUSE_PYTHON2 = 8

# (cause index, fewest sick days, most sick days, daily health drain)
ILLNESSES = (
    (0, 3, 6, 9),
    (1, 3, 6, 10),
    (2, 2, 5, 7),
    (3, 2, 5, 8),
)

HEALTH_LABELS = ((70, "Good"), (40, "Fair"), (20, "Poor"), (0, "Very poor"))

EVENT_CHANCE = 0.09
ILLNESS_CHANCE = 0.06

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
        self.name = name
        self.health = 100
        self.illness = -1
        self.sick_days = 0
        self.alive = True
        self.cause = -1

    def status(self):
        if not self.alive:
            return "Died of " + CAUSES[self.cause]
        if self.illness >= 0:
            return "Has " + CAUSES[ILLNESSES[self.illness][0]]
        return health_label(self.health)


class Trail:
    """One journey on foot from the Gatehouse to the Mainstage."""

    def __init__(self, role, rng):
        self.rng = rng
        self.role = clamp_int(role, 0, len(ROLES) - 1)
        self.supplies = {"credits": ROLES[self.role][2], "brew": 0.0, "lgtm": 0, "patches": 0}
        self.members = [Member(name) for name in PARTY]
        self.x = tm.START[0]
        self.y = tm.START[1]
        self.facing = 1
        self.steps = 0
        self.day_ms = 0
        self.pending_ms = 0
        self.day = 1
        self.pace = 0
        self.rations = 1
        self.at = 0
        self.visited = 1
        self.deployed = 0
        self.healed_day = -HEAL_DAYS
        self.basket = {}
        self.tailwind = 0
        self.last_cause = CAUSE_EXHAUSTION
        self.ticker = "Outfit the wagon at the Gatehouse store."
        self._guide = None
        self._guide_key = -1

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

    def sights_seen(self):
        count = 0
        for entry in SIGHTS:
            if self.has_visited(entry[0]):
                count += 1
        return count

    def next_stop(self):
        """The next stop on the direct trail past the furthest one reached.
        A river only counts as reached once the party has crossed it."""
        index = 0
        for i in range(len(tm.ROUTE)):
            if self.has_visited(tm.ROUTE[i]):
                index = i
        return tm.ROUTE[min(index + 1, len(tm.ROUTE) - 1)]

    def guide(self):
        """Distance field (in tiles) to next_stop(); rebuilt only on change."""
        stop = self.next_stop()
        key = stop * 4096 + self.deployed
        if self._guide is None or self._guide_key != key:
            entry = tm.STOPS[stop]
            self._guide = tm.distances(entry[3], entry[4], self.deployed)
            self._guide_key = key
        return self._guide

    def steps_to_next(self):
        """Steps to the next landmark, or -1 if it cannot be reached yet."""
        tiles = self.guide()[self.y * tm.W + self.x]
        if tiles == tm.UNREACHED:
            return -1
        return tiles * tm.STEPS_PER_TILE

    # ----- walking ------------------------------------------------------------
    def steps_per_day(self):
        steps = PACES[self.pace][1]
        if self.tailwind > 0:
            steps = steps * 7 // 4
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
        self.day_ms += self.pending_ms
        self.pending_ms = 0
        while self.day_ms >= DAY_MS:
            self.day_ms -= DAY_MS
            self._upkeep(lines)
            self._end_day()
            if not self.all_dead():
                self._roll_event(lines)
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
        first = not self.has_visited(stop)
        self.visited |= 1 << stop
        if kind == "end":
            return "victory"
        if first:
            for entry in SIGHTS:
                if entry[0] == stop:
                    self._gift(entry, lines)
        if kind == "heal":
            self._firehouse(lines)
        return "stop"

    def _gift(self, entry, lines):
        _stop, key, amount, line = entry
        if key == "health":
            for member in self.living():
                member.health = clamp(member.health + amount, 0, 100)
        else:
            self.supplies[key] = min(carry_limit(key), self.supplies[key] + amount)
        lines.append(line)

    def heal_ready(self):
        return self.day - self.healed_day >= HEAL_DAYS

    def _firehouse(self, lines):
        if not self.heal_ready():
            wait = HEAL_DAYS - (self.day - self.healed_day)
            lines.append("The crew is out on a call. Come back in %s." % plural(wait, "day"))
            return
        self.healed_day = self.day
        cured = 0
        for member in self.living():
            member.health = clamp(member.health + HEAL_AMOUNT, 0, 100)
            if member.illness >= 0:
                member.illness = -1
                member.sick_days = 0
                cured += 1
        lines.append("The Hotfix HQ crew patched up the party. Health +%d." % HEAL_AMOUNT)
        if cured:
            lines.append("They cured %s, too." % plural(cured, "illness", "es"))

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

    # ----- daily upkeep -----------------------------------------------------
    def _kill(self, member, cause, lines):
        member.alive = False
        member.health = 0
        member.cause = cause
        member.illness = -1
        member.sick_days = 0
        self.last_cause = cause
        lines.append("%s has died of %s." % (member.name, CAUSES[cause]))

    def _upkeep(self, lines, resting=False):
        living = self.living()
        if not living:
            return
        need = len(living) * RATIONS[self.rations][1]
        dry = self.supplies["brew"] + 0.0001 < need
        self.supplies["brew"] = max(0.0, self.supplies["brew"] - need)
        for member in living:
            delta = -DRY_STRAIN if dry else RATIONS[self.rations][2]
            if resting:
                delta += REST_HEAL
            else:
                delta += PACES[self.pace][2] - TRAIL_WEAR
            sick = member.illness >= 0
            if sick:
                delta -= ILLNESSES[member.illness][3]
                member.sick_days -= 2 if resting else 1
            member.health = clamp(member.health + delta, 0, 100)
            if sick and 0 < member.health < SICK_DANGER and self.rng.chance(SICK_DEATH):
                member.health = 0
            if member.health <= 0:
                if member.illness >= 0:
                    cause = ILLNESSES[member.illness][0]
                elif dry:
                    cause = CAUSE_WITHDRAWAL
                else:
                    cause = CAUSE_EXHAUSTION
                self._kill(member, cause, lines)
            elif member.illness >= 0 and member.sick_days <= 0:
                lines.append("%s recovered from %s." % (member.name, CAUSES[ILLNESSES[member.illness][0]]))
                member.illness = -1
                member.sick_days = 0
        if dry:
            self.ticker = "Out of Cold Brew Kegs! The party is fading."

    def _end_day(self):
        self.day += 1
        if self.tailwind > 0:
            self.tailwind -= 1

    def idle_days(self, days, lines, resting=False):
        for _ in range(days):
            if self.all_dead():
                return
            self._upkeep(lines, resting)
            self._end_day()

    def rest_day(self):
        lines = []
        self.idle_days(1, lines, resting=True)
        return lines

    # ----- events -------------------------------------------------------------
    def _illness_chance(self):
        chance = ILLNESS_CHANCE + (0.0, 0.015, 0.035)[self.pace]
        if self.rations == 2:
            chance += 0.02
        if self.supplies["brew"] <= 0:
            chance += 0.03
        if self.average_health() < 50:
            chance += 0.02
        return chance

    def _roll_event(self, lines):
        rng = self.rng
        if rng.chance(self._illness_chance()):
            self._fall_ill(lines)
        elif rng.chance(EVENT_CHANCE):
            event = rng.weighted((
                (3, self._broken_ci),
                (2, self._dependabot),
                (2, self._abandoned_wagon),
                (2, self._rate_limited),
                (2, self._typosquatter),
                (2, self._shortcut),
                (1, self._stale_readme),
                (2, self._python2),
                (1, self._unicorn),
            ))
            event(lines)

    def _use_patch(self, lines):
        self.supplies["patches"] -= 1
        if self.role == RUSTACEAN:
            for member in self.living():
                member.health = clamp(member.health + 10, 0, 100)
            lines.append("Rustacean hotfix: the party feels better.")

    def _fall_ill(self, lines):
        healthy = [member for member in self.living() if member.illness < 0]
        if not healthy:
            return
        member = self.rng.choice(healthy)
        member.illness = self.rng.randint(0, len(ILLNESSES) - 1)
        cause, low, high, _drain = ILLNESSES[member.illness]
        member.sick_days = self.rng.randint(low, high)
        lines.append("%s has %s." % (member.name, CAUSES[cause]))

    def _broken_ci(self, lines):
        lines.append("A CI axle broke on the trail.")
        if self.supplies["patches"] > 0:
            lines.append("You swapped in a Hotfix Patch.")
            self._use_patch(lines)
        else:
            lines.append("No Hotfix Patch. Rebuilt it from source: lost 2 days.")
            self.idle_days(2, lines)

    def _dependabot(self, lines):
        kegs = min(self.rng.randint(8, 24), int(carry_limit("brew") - self.supplies["brew"]))
        if kegs <= 0:
            lines.append("A Dependabot caravan waved hello.")
            return
        self.supplies["brew"] += kegs
        lines.append("A Dependabot caravan shared %s." % plural(kegs, "Cold Brew Keg"))

    def _abandoned_wagon(self, lines):
        stamps = max(0, min(self.rng.randint(10, 30), carry_limit("lgtm") - int(self.supplies["lgtm"])))
        self.supplies["lgtm"] += stamps
        lines.append("You found an abandoned wagon with %s." % plural(stamps, "LGTM Stamp"))
        if self.rng.chance(0.35) and self.supplies["patches"] < carry_limit("patches"):
            self.supplies["patches"] += 1
            lines.append("There was a Hotfix Patch inside, too.")

    def _rate_limited(self, lines):
        lines.append("Rate limited by the trail API. Lost 1 day.")
        self.idle_days(1, lines)

    def _typosquatter(self, lines):
        kegs = min(self.rng.randint(5, 15), int(self.supplies["brew"]))
        if kegs <= 0:
            lines.append("An npm typosquatter found nothing worth taking.")
            return
        self.supplies["brew"] -= kegs
        lines.append("An npm typosquatter made off with %s." % plural(kegs, "keg"))

    def _shortcut(self, lines):
        self.tailwind = max(self.tailwind, 2)
        lines.append("Copilot found a shortcut. The next 2 days fly by.")

    def _stale_readme(self, lines):
        lines.append("You followed a stale README. Lost 2 days.")
        self.idle_days(2, lines)

    def _python2(self, lines):
        living = self.living()
        if not living:
            return
        member = self.rng.choice(living)
        member.health = clamp(member.health - 20, 0, 100)
        lines.append("%s was bitten by a Python 2 dependency." % member.name)
        if member.health <= 0:
            self._kill(member, CAUSE_PYTHON2, lines)

    def _unicorn(self, lines):
        for member in self.living():
            member.health = clamp(member.health + 8, 0, 100)
        lines.append("You spotted the GitHub unicorn. Morale soars.")
