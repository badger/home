"""Rules for The Octocat Trail.

Pure game logic with no badge runtime globals, so the same code runs on the
badge's MicroPython and under CPython tests. Randomness comes from an
injected Rng, ordered data lives in tuples (MicroPython dicts are unordered),
and only APIs that exist in MicroPython 1.29 are used.
"""

import math

import trail_map as tm

TRAIL_STEPS = 2000
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
ATC_LEAD = 2

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
MEADOW = 7

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
TURBO_DAYS = 6
TURBO_COOLDOWN = 8
TURBO_BREW = 1.5
TURBO_STRAIN = 2

STOP_BLURBS = (
    "The gate is open and the repo is empty. Outfit the wagon before you go.",
    "Plushies, hoodies and supplies, at venue prices.",
    "Maintainers trade stickers and stamp each other's pull requests.",
    "The hub of the show floor. Somebody is handing out hugs.",
    "Ask anything. Someone here has already debugged it.",
    "Recruiters, resumes and an alarming amount of free cold brew.",
    "Hotfix HQ. The crew patches up the party every few days.",
    "Recess on the grass, with the Golden Gate in view. Bugs swarm here.",
    "Two branches meet here and neither will yield.",
    "Soldering irons, spare parts and the last store before the show.",
    "A keynote rehearsal is running. The seats are warm.",
    "Fast water. The far pier resolves eventually.",
    "The lights are up and the crowd is waiting.",
)
# (stop, supply or "health", amount, line) granted on the first visit.
SIGHTS = (
    (2, "lgtm", 20, "The maintainers stamped 20 LGTMs for the road."),
    (3, "health", 10, "Hugs all round at GitHub Central. Health +10."),
    (4, "patches", 1, "An expert pair-programmed you a Hotfix Patch."),
    (5, "brew", 15, "A recruiter slipped you 15 Cold Brew Kegs."),
    (10, "health", 10, "A standing ovation lifts every spirit. Health +10."),
)
SIGHT_POINTS = 40
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
CAUSE_FORCE_PUSH = 9

# (cause index, fewest sick days, most sick days, daily health drain)
ILLNESSES = (
    (0, 3, 6, 9),
    (1, 3, 6, 10),
    (2, 2, 5, 7),
    (3, 2, 5, 8),
)

# (stop index, shallowest, deepest (tenths of a foot), narrowest, widest,
#  ferry credits, cause of death)
RIVERS = (
    (tm.MERGE, 20, 60, 140, 180, 40, 6),
    (tm.DNS, 35, 95, 150, 190, 70, 7),
)
RIVER_OPTIONS = ("YOLO deploy (ford)", "Ship with 2 LGTMs", "Ask Copilot (ferry)", "Wait for review")
FORD, CAULK, FERRY, WAIT = 0, 1, 2, 3

EPITAPHS = (
    "LGTM",
    "It worked on my machine",
    "rm -rf node_modules",
    "404: party not found",
    "Should have pinned it",
    "git push --force",
    "Ship it",
    "Merged with love",
)

FORT_TIPS = (
    "The piers are fenced off for load-in. Deploy a gangway from Pier 1.",
    "The Firehouse crew patches the whole party every few days.",
    "Sights pay out on your first visit, and they count toward your score.",
    "Ford only where the diff is shallow.",
    "LGTM Stamps stop bugs and steady a raft.",
    "Never force-push on a Friday. Pack a Hotfix Patch anyway.",
    "Shake your badge to sprint, but sprinting drinks cold brew.",
    "When the lights go out, the party makes Dark Mode Camp.",
    "AI slop is slow, but it takes two stamps to clean up.",
    "Decaf saves kegs. It does not save morale.",
    "Hold your badge to a friend's to beam tombstones and victories.",
    "Copilot ferries are pricey but rarely tip over.",
)

HEALTH_LABELS = ((70, "Good"), (40, "Fair"), (20, "Poor"), (0, "Very poor"))
HEALTH_POINTS = ((70, 500), (40, 400), (20, 300), (0, 200))

EVENT_CHANCE = 0.09
FRIDAY_FORCE_PUSH = 0.12
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


def health_points(health):
    for floor, points in HEALTH_POINTS:
        if health >= floor:
            return points
    return HEALTH_POINTS[-1][1]


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
        self.river = None
        self.turbo_days = 0
        self.turbo_cooldown = 0
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
        if self.turbo_days > 0:
            need *= TURBO_BREW
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
        if self.turbo_days > 0 or self.tailwind > 0:
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
        if code == tm.FENCE:
            return "Load-in zone: no entry from the plaza."
        if code == tm.GANG1 or code == tm.GANG2:
            return "Gangway is up. Cross at the dock."
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
        self.river = None
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
        if tm.STOPS[stop][2] == "river" and self.deployed & tm.deployed_bit(stop):
            return lines, None
        return lines, self.arrive(stop, lines)

    def arrive(self, stop, lines):
        """Reach a stop. Returns "stop", "river" or "victory"."""
        self.at = stop
        self.basket = {}
        kind = tm.STOPS[stop][2]
        if kind == "river":
            self.arrive_river()
            return "river"
        first = not self.has_visited(stop)
        self.visited |= 1 << stop
        if kind == "end":
            self.turbo_days = 0
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

    def tip(self):
        return self.rng.choice(FORT_TIPS)

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
        sprinting = self.turbo_days > 0 and not resting
        need = len(living) * RATIONS[self.rations][1]
        if sprinting:
            need *= TURBO_BREW
        dry = self.supplies["brew"] + 0.0001 < need
        self.supplies["brew"] = max(0.0, self.supplies["brew"] - need)
        for member in living:
            delta = -DRY_STRAIN if dry else RATIONS[self.rations][2]
            if resting:
                delta += REST_HEAL
            else:
                delta += PACES[self.pace][2] - TRAIL_WEAR
                if sprinting:
                    delta -= TURBO_STRAIN
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
        if self.turbo_days > 0:
            self.turbo_days -= 1
            if self.turbo_days == 0:
                self.turbo_cooldown = TURBO_COOLDOWN
                self.ticker = "Turbo sprint over. Catch your breath."
        elif self.turbo_cooldown > 0:
            self.turbo_cooldown -= 1

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

    # ----- sprinting ----------------------------------------------------------
    def can_sprint(self):
        return (self.turbo_days == 0 and self.turbo_cooldown == 0 and self.supplies["brew"] > 0
                and not self.all_dead())

    def start_sprint(self):
        if not self.can_sprint():
            return False
        self.turbo_days = TURBO_DAYS
        self.ticker = "Turbo sprint! %d days of hustle." % TURBO_DAYS
        return True

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
        if self.weekday() == "Fri" and rng.chance(FRIDAY_FORCE_PUSH):
            self._force_push(lines)
        elif rng.chance(self._illness_chance()):
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

    def _force_push(self, lines):
        lines.append("Force-pushed to main on Friday!")
        if self.supplies["patches"] > 0:
            lines.append("A Hotfix Patch reverted it. Lost 1 day.")
            self._use_patch(lines)
            self.idle_days(1, lines)
        else:
            lines.append("No Hotfix Patch. Rebuilding history by hand: lost 3 days.")
            self.idle_days(3, lines)
            living = self.living()
            if living:
                member = self.rng.choice(living)
                member.health = clamp(member.health - 15, 0, 100)
                if member.health <= 0:
                    self._kill(member, CAUSE_FORCE_PUSH, lines)

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

    # ----- hunting ----------------------------------------------------------
    def in_meadow(self):
        return self.at == MEADOW or tm.terrain(self.x, self.y) == tm.GRASS

    def start_hunt(self):
        return Hunt(self.rng, self.supplies["lgtm"], self.in_meadow())

    def finish_hunt(self, hunt):
        hauled = hunt.haul(self.supplies["brew"], carry_limit("brew"))
        self.supplies["lgtm"] = max(0, int(hunt.stamps))
        self.supplies["brew"] += hauled
        lines = hunt.summary(hauled)
        self.idle_days(1, lines)
        return lines

    # ----- rivers -----------------------------------------------------------
    def river_spec(self):
        for spec in RIVERS:
            if spec[0] == self.at:
                return spec
        return None

    def arrive_river(self):
        spec = self.river_spec()
        if spec is None:
            self.river = None
            return
        self.river = [self.rng.randint(spec[1], spec[2]), self.rng.randint(spec[3], spec[4])]

    def ferry_cost(self):
        spec = self.river_spec()
        return spec[5] if spec else 0

    def river_option_ok(self, option):
        if option == CAULK:
            return self.supplies["lgtm"] >= 2
        if option == FERRY:
            return self.supplies["credits"] >= self.ferry_cost()
        return option in (FORD, WAIT)

    def crossing_risk(self, option):
        if not self.river:
            return 0.0
        depth = self.river[0] / 10.0
        if option == FORD:
            risk = (depth - 2.5) * 0.2
        elif option == CAULK:
            risk = 0.05 + depth * 0.025
        elif option == FERRY:
            risk = 0.02
        else:
            return 0.0
        if self.role == ATC_LEAD:
            risk *= 0.6
        return clamp(risk, 0.0, 0.95)

    def cross(self, option):
        """Resolve a river choice. Returns (lines, crossed)."""
        lines = []
        spec = self.river_spec()
        if spec is None or self.river is None or not self.river_option_ok(option):
            return lines, False
        stop = self.at
        name = tm.STOPS[stop][0]
        if option == WAIT:
            self.idle_days(1, lines)
            low = spec[1] * 8 // 10
            self.river[0] = clamp(self.river[0] + self.rng.randint(-8, 5), low, spec[2])
            lines.append("You waited a day for review. The river is now %s ft deep." % tenths(self.river[0]))
            return lines, False
        risk = self.crossing_risk(option)
        if option == CAULK:
            self.supplies["lgtm"] -= 2
        elif option == FERRY:
            self.supplies["credits"] -= spec[5]
            wait = self.rng.randint(1, 3)
            self.idle_days(wait, lines)
            lines.append("Copilot queued your ferry. Waited %s." % plural(wait, "day"))
        if self.all_dead():
            return lines, True
        if self.rng.chance(risk):
            lines.append("The deploy failed in %s!" % name)
            brew = int(self.supplies["brew"] * self.rng.uniform(0.15, 0.4))
            stamps = int(self.supplies["lgtm"] * self.rng.uniform(0.1, 0.3))
            patches = 1 if self.supplies["patches"] > 0 and self.rng.chance(0.4) else 0
            self.supplies["brew"] -= brew
            self.supplies["lgtm"] -= stamps
            self.supplies["patches"] -= patches
            lines.append("Lost %s, %s and %s." % (
                plural(brew, "keg"), plural(stamps, "LGTM Stamp"), plural(patches, "Hotfix Patch", "es")))
            if option == FORD:
                death = 0.15 + max(0.0, self.river[0] / 10.0 - 3.0) * 0.06
            elif option == CAULK:
                death = 0.12
            else:
                death = 0.25
            living = self.living()
            if living and self.rng.chance(min(death, 0.6)):
                self._kill(self.rng.choice(living), spec[6], lines)
        elif option == FORD:
            lines.append("YOLO! The deploy went green across %s." % name)
        elif option == CAULK:
            lines.append("Two LGTMs and a prayer: the gangway is down.")
        else:
            lines.append("Copilot ferried the wagon safely across.")
        self.idle_days(1, lines)
        self._land(stop)
        return lines, True

    def _land(self, stop):
        """Lower the gangway and put the party on the far landing."""
        dock = tm.dock(stop)
        self.deployed |= tm.deployed_bit(stop)
        self.visited |= 1 << stop
        self.x, self.y = tm.landing(stop)
        self.steps = min(MAX_STEPS, self.steps + (dock[2] - dock[0]) * tm.STEPS_PER_TILE)
        self.facing = 1
        self.at = -1
        self.river = None

    # ----- scoring ----------------------------------------------------------
    def score(self):
        points = 0
        for member in self.living():
            points += health_points(member.health)
        if points:
            points += 50
            points += int(self.supplies["patches"]) * 2
            points += int(self.supplies["lgtm"]) // 50
            points += int(self.supplies["brew"]) // 25
            points += int(self.supplies["credits"]) // 5
            points += self.sights_seen() * SIGHT_POINTS
        return points * self.multiplier()

    def tombstone(self, epitaph=0):
        return tombstone_record(self.steps, self.last_cause, epitaph, self.role, False)

    # ----- persistence ------------------------------------------------------
    def to_dict(self):
        party = []
        for member in self.members:
            party.append([int(member.health), member.illness, member.sick_days, 1 if member.alive else 0, member.cause])
        return {
            "v": 2,
            "role": self.role,
            "credits": int(self.supplies["credits"]),
            "brew": int(self.supplies["brew"] * 10 + 0.5),
            "lgtm": int(self.supplies["lgtm"]),
            "patches": int(self.supplies["patches"]),
            "x": self.x,
            "y": self.y,
            "facing": self.facing,
            "steps": self.steps,
            "day_ms": self.day_ms,
            "day": self.day,
            "pace": self.pace,
            "rations": self.rations,
            "at": self.at,
            "visited": self.visited,
            "deployed": self.deployed,
            "healed": self.healed_day,
            "river": list(self.river) if self.river else None,
            "turbo": self.turbo_days,
            "cool": self.turbo_cooldown,
            "tail": self.tailwind,
            "last": self.last_cause,
            "party": party,
        }

    @staticmethod
    def from_dict(data, rng):
        """Rebuild a saved journey, or return None if the data is unusable."""
        try:
            if not isinstance(data, dict) or data.get("v") != 2:
                return None
            trail = Trail(clamp_int(data["role"], 0, len(ROLES) - 1), rng)
            trail.supplies["credits"] = clamp_int(data["credits"], 0, 100000)
            trail.supplies["brew"] = clamp_int(data["brew"], 0, carry_limit("brew") * 10) / 10.0
            trail.supplies["lgtm"] = clamp_int(data["lgtm"], 0, carry_limit("lgtm"))
            trail.supplies["patches"] = clamp_int(data["patches"], 0, carry_limit("patches"))
            every = (1 << len(tm.STOPS)) - 1
            trail.deployed = clamp_int(data["deployed"], 0, every) & (
                tm.deployed_bit(tm.MERGE) | tm.deployed_bit(tm.DNS))
            trail.visited = clamp_int(data["visited"], 0, every) | trail.deployed | 1
            x = clamp_int(data["x"], 0, tm.W - 1)
            y = clamp_int(data["y"], 0, tm.H - 1)
            if tm.distances(x, y, trail.deployed)[tm.START[1] * tm.W + tm.START[0]] == tm.UNREACHED:
                return None
            trail.x = x
            trail.y = y
            trail.facing = -1 if data.get("facing") == -1 else 1
            trail.steps = clamp_int(data["steps"], 0, MAX_STEPS)
            trail.day_ms = clamp_int(data.get("day_ms"), 0, DAY_MS - 1, 0)
            trail.day = clamp_int(data["day"], 1, 9999)
            trail.pace = clamp_int(data["pace"], 0, len(PACES) - 1)
            trail.rations = clamp_int(data["rations"], 0, len(RATIONS) - 1)
            trail.healed_day = clamp_int(data.get("healed"), -HEAL_DAYS, trail.day, -HEAL_DAYS)
            trail.turbo_days = clamp_int(data["turbo"], 0, TURBO_DAYS)
            trail.turbo_cooldown = clamp_int(data["cool"], 0, TURBO_COOLDOWN)
            trail.tailwind = clamp_int(data.get("tail"), 0, 2, 0)
            trail.last_cause = clamp_int(data.get("last"), 0, len(CAUSES) - 1, CAUSE_EXHAUSTION)
            party = data["party"]
            if not isinstance(party, list) or len(party) != len(PARTY):
                return None
            for member, saved in zip(trail.members, party):
                if not isinstance(saved, list) or len(saved) != 5:
                    return None
                health, illness, sick_days, alive, cause = saved
                member.alive = bool(alive)
                if member.alive:
                    member.health = clamp_int(health, 1, 100)
                    member.illness = clamp_int(illness, -1, len(ILLNESSES) - 1)
                    member.sick_days = clamp_int(sick_days, 0, 30) if member.illness >= 0 else 0
                    member.cause = -1
                else:
                    member.health = 0
                    member.illness = -1
                    member.sick_days = 0
                    member.cause = clamp_int(cause, 0, len(CAUSES) - 1)
            if trail.all_dead():
                return None
            at = clamp_int(data.get("at"), -1, len(tm.STOPS) - 1, -1)
            trail.at = at if at >= 0 and tm.stop_at(x, y) == at else -1
            if trail.at == tm.END:
                return None
            if trail.at_kind("river"):
                if trail.deployed & tm.deployed_bit(trail.at):
                    trail.at = -1
                else:
                    spec = trail.river_spec()
                    river = data.get("river")
                    if isinstance(river, list) and len(river) == 2:
                        trail.river = [clamp_int(river[0], spec[1] * 8 // 10, spec[2]),
                                       clamp_int(river[1], spec[3], spec[4])]
                    else:
                        trail.arrive_river()
            trail.ticker = "Welcome back to Fort Mason."
            return trail
        except Exception:
            return None


# ----- hunt mini-game -------------------------------------------------------
HUNT_MS = 30000
HUNT_CARRY = 100
HUNT_W = 320
HUNT_H = 196
HUNTER_SPEED = 70
HUNTER_RADIUS = 6
SHOT_SPEED = 220
SHOT_RADIUS = 2
MAX_SHOTS = 3
MAX_TARGETS = 6
# (name, radius px, speed px/s, hit points, bounty kegs, spawn weight)
TARGET_KINDS = (
    ("bug", 5, 50, 1, 6, 4),
    ("slop", 9, 20, 2, 25, 1),
)
BUG, SLOP = 0, 1
# (name, radius px) of the cover that blocks walking and stamps.
COVER = (("tree", 9), ("bush", 6), ("rock", 5))


def near(ax, ay, bx, by, reach):
    dx = ax - bx
    dy = ay - by
    return dx * dx + dy * dy < reach * reach


class Hunt:
    """Bug & AI Slop Hunt: walk Mona around a top-down field and throw LGTM
    Stamps the way she faces. Cover blocks both Mona and her stamps."""

    def __init__(self, rng, stamps, meadow=False, width=HUNT_W, height=HUNT_H):
        self.rng = rng
        self.width = width
        self.height = height
        self.meadow = bool(meadow)
        self.x = width / 2.0
        self.y = height / 2.0
        self.aim_x = 1
        self.aim_y = 0
        self.walk_ms = 0
        self.cover = []
        self._scatter()
        self.targets = []
        self.flying = []
        self.splats = []
        self.elapsed = 0
        self.spawn_in = 300
        self.stamps = int(stamps)
        self.thrown = 0
        self.kills = [0, 0]
        self.bounty = 0
        self.done = self.stamps <= 0
        self.reason = "stamps" if self.done else ""
        self.last_hit = False

    def _scatter(self):
        count = 9 if self.meadow else 7
        tries = 0
        while len(self.cover) < count and tries < 300:
            tries += 1
            kind = self.rng.randint(0, len(COVER) - 1)
            radius = COVER[kind][1]
            x = self.rng.uniform(radius + 6, self.width - radius - 6)
            y = self.rng.uniform(radius + 6, self.height - radius - 6)
            if near(x, y, self.x, self.y, radius + 34):
                continue
            clear = True
            for cx, cy, cr, _kind in self.cover:
                if near(x, y, cx, cy, radius + cr + 16):
                    clear = False
                    break
            if clear:
                self.cover.append((x, y, radius, kind))

    def blocked(self, x, y, radius):
        for cx, cy, cr, _kind in self.cover:
            if near(x, y, cx, cy, radius + cr):
                return True
        return False

    def remaining_ms(self):
        return max(0, HUNT_MS - self.elapsed)

    def radius(self, target):
        return TARGET_KINDS[target[0]][1]

    def spawn(self, kind=None):
        if kind is None:
            kind = self.rng.weighted(((TARGET_KINDS[BUG][5], BUG), (TARGET_KINDS[SLOP][5], SLOP)))
        _name, radius, speed, hp, _bounty, _weight = TARGET_KINDS[kind]
        speed *= self.rng.uniform(0.8, 1.25)
        drift = self.rng.uniform(-0.4, 0.4) * speed
        side = self.rng.randint(0, 3)
        if side < 2:
            x = -radius if side == 0 else self.width + radius
            y = self.rng.uniform(radius, self.height - radius)
            vx = speed if side == 0 else -speed
            vy = drift
        else:
            x = self.rng.uniform(radius, self.width - radius)
            y = -radius if side == 2 else self.height + radius
            vx = drift
            vy = speed if side == 2 else -speed
        target = [kind, x, y, vx, vy, hp, self.rng.randint(300, 800)]
        self.targets.append(target)
        return target

    def update(self, dt, dx=0, dy=0, fire=False):
        self.last_hit = False
        if self.done:
            return
        dt = clamp(int(dt), 0, 100)
        seconds = dt / 1000.0
        if dx or dy:
            self.aim_x = dx
            self.aim_y = dy
            reach = HUNTER_SPEED * seconds * (0.7071 if dx and dy else 1.0)
            x = clamp(self.x + dx * reach, HUNTER_RADIUS, self.width - HUNTER_RADIUS)
            if not self.blocked(x, self.y, HUNTER_RADIUS):
                self.x = x
            y = clamp(self.y + dy * reach, HUNTER_RADIUS, self.height - HUNTER_RADIUS)
            if not self.blocked(self.x, y, HUNTER_RADIUS):
                self.y = y
            self.walk_ms += dt
        self.elapsed += dt
        self.spawn_in -= dt
        if self.spawn_in <= 0:
            if len(self.targets) < MAX_TARGETS:
                self.spawn()
            self.spawn_in = self.rng.randint(250, 650) if self.meadow else self.rng.randint(400, 1000)
        self._move_targets(dt, seconds)
        self._move_stamps(seconds)
        aged = []
        for splat in self.splats:
            splat[2] += dt
            if splat[2] < 450:
                aged.append(splat)
        self.splats = aged
        if fire:
            self.fire()
        if self.elapsed >= HUNT_MS:
            self.done = True
            self.reason = "time"
        elif self.stamps <= 0 and not self.flying:
            self.done = True
            self.reason = "stamps"

    def _move_targets(self, dt, seconds):
        kept = []
        for target in self.targets:
            radius = TARGET_KINDS[target[0]][1]
            target[6] -= dt
            if target[6] <= 0:
                turn = self.rng.uniform(-0.8, 0.8) if target[0] == BUG else self.rng.uniform(-0.3, 0.3)
                c = math.cos(turn)
                s = math.sin(turn)
                vx = target[3]
                vy = target[4]
                target[3] = vx * c - vy * s
                target[4] = vx * s + vy * c
                target[6] = self.rng.randint(300, 800)
            x = target[1] + target[3] * seconds
            y = target[2] + target[4] * seconds
            if self.blocked(x, y, radius):
                target[3] = -target[3]
                target[4] = -target[4]
            else:
                target[1] = x
                target[2] = y
            margin = radius * 2 + 2
            if -margin <= target[1] <= self.width + margin and -margin <= target[2] <= self.height + margin:
                kept.append(target)
        self.targets = kept

    def _move_stamps(self, seconds):
        kept = []
        for stamp in self.flying:
            dx = stamp[2] * seconds
            dy = stamp[3] * seconds
            parts = int(max(abs(dx), abs(dy)) / 4) + 1
            alive = True
            for _ in range(parts):
                stamp[0] += dx / parts
                stamp[1] += dy / parts
                x = stamp[0]
                y = stamp[1]
                if x < 0 or y < 0 or x >= self.width or y >= self.height:
                    alive = False
                    break
                if self.blocked(x, y, SHOT_RADIUS):
                    self.splats.append([x, y, 0, -1])
                    alive = False
                    break
                target = self.target_at(x, y)
                if target is not None:
                    self._hit(target)
                    alive = False
                    break
            if alive:
                kept.append(stamp)
        self.flying = kept

    def target_at(self, x, y):
        for target in self.targets:
            if near(x, y, target[1], target[2], TARGET_KINDS[target[0]][1] + SHOT_RADIUS + 1):
                return target
        return None

    def _hit(self, target):
        self.last_hit = True
        target[5] -= 1
        if target[5] <= 0:
            self.targets.remove(target)
            self.kills[target[0]] += 1
            self.bounty += TARGET_KINDS[target[0]][4]
            self.splats.append([target[1], target[2], 0, target[0]])

    def fire(self):
        """Throw a stamp the way Mona faces. Returns True if one was thrown."""
        if self.done or self.stamps <= 0 or len(self.flying) >= MAX_SHOTS:
            return False
        self.stamps -= 1
        self.thrown += 1
        scale = 0.7071 if self.aim_x and self.aim_y else 1.0
        self.flying.append([
            self.x + self.aim_x * (HUNTER_RADIUS + 2),
            self.y + self.aim_y * (HUNTER_RADIUS + 2),
            self.aim_x * SHOT_SPEED * scale,
            self.aim_y * SHOT_SPEED * scale,
        ])
        return True

    def finish(self):
        if not self.done:
            self.done = True
            self.reason = "quit"

    def haul(self, current_brew, cap=500):
        return int(max(0, min(self.bounty, HUNT_CARRY, cap - current_brew)))

    def summary(self, hauled):
        lines = ["You stamped out %s and %s." % (
            plural(self.kills[BUG], "bug"), plural(self.kills[SLOP], "AI slop blob"))]
        if self.bounty <= 0:
            lines.append("No bounty this time. Used %s." % plural(self.thrown, "LGTM Stamp"))
        else:
            lines.append("Bounty: %s of cold brew." % plural(self.bounty, "keg"))
            if hauled < self.bounty:
                lines.append("You could only haul %s back to the wagon." % plural(hauled, "keg"))
        return lines


# ----- sensors --------------------------------------------------------------
class ShakeDetector:
    """Orientation- and unit-agnostic shake detection from accelerometer
    magnitude spikes around a slowly adapting gravity baseline."""

    def __init__(self, threshold=0.55, peaks=3, window_ms=1200, cooldown_ms=2000, min_baseline=0.5):
        self.threshold = threshold
        self.peaks_needed = peaks
        self.window_ms = window_ms
        self.cooldown_ms = cooldown_ms
        self.min_baseline = min_baseline
        self.baseline = 0.0
        self.above = False
        self.peaks = []
        self.quiet_until = 0

    def update(self, now_ms, ax, ay, az):
        ax = float(ax)
        ay = float(ay)
        az = float(az)
        magnitude = math.sqrt(ax * ax + ay * ay + az * az)
        if self.baseline < self.min_baseline:
            self.baseline = magnitude
            return False
        deviation = abs(magnitude - self.baseline) / self.baseline
        if deviation < self.threshold * 0.5:
            self.baseline += (magnitude - self.baseline) * 0.02
            self.above = False
        elif deviation >= self.threshold and not self.above:
            self.above = True
            self.peaks.append(now_ms)
        recent = []
        for stamp in self.peaks:
            if now_ms - stamp <= self.window_ms:
                recent.append(stamp)
        self.peaks = recent
        if now_ms < self.quiet_until:
            return False
        if len(self.peaks) >= self.peaks_needed:
            self.peaks = []
            self.quiet_until = now_ms + self.cooldown_ms
            return True
        return False


class DarkDetector:
    """Detects the room going dark relative to its own recent brightness.

    The sensor must first show a reference of at least min_ref so a missing
    or stuck-at-zero sensor never triggers. update() returns "dark" or
    "light" on transitions, otherwise None."""

    def __init__(self, dark_ratio=0.3, light_ratio=0.6, min_ref=160, hold_ms=1200,
                 fast_ms=300, rise_ms=1000, decay_ms=60000):
        self.dark_ratio = dark_ratio
        self.light_ratio = light_ratio
        self.min_ref = min_ref
        self.hold_ms = hold_ms
        self.fast_ms = fast_ms
        self.rise_ms = rise_ms
        self.decay_ms = decay_ms
        self.fast = -1.0
        self.reference = 0.0
        self.dark = False
        self.suppressed = False
        self.since = -1

    def armed(self):
        return self.reference >= self.min_ref

    def suppress(self):
        """The player broke camp by hand: wait for light before re-arming."""
        self.suppressed = True

    def update(self, now_ms, dt_ms, value):
        value = float(value)
        if self.fast < 0:
            self.fast = value
        else:
            self.fast += (value - self.fast) * min(1.0, dt_ms / float(self.fast_ms))
        if not self.dark:
            tau = self.rise_ms if self.fast > self.reference else self.decay_ms
            self.reference += (self.fast - self.reference) * min(1.0, dt_ms / float(tau))
        if not self.armed():
            self.since = -1
            return None
        if self.dark or self.suppressed:
            if self.fast <= self.reference * self.light_ratio:
                self.since = -1
                return None
            if self.since < 0:
                self.since = now_ms
            if now_ms - self.since >= self.hold_ms:
                self.since = -1
                self.suppressed = False
                if self.dark:
                    self.dark = False
                    return "light"
            return None
        if self.fast >= self.reference * self.dark_ratio:
            self.since = -1
            return None
        if self.since < 0:
            self.since = now_ms
        if now_ms - self.since >= self.hold_ms:
            self.since = -1
            self.dark = True
            return "dark"
        return None


# ----- IR packets -------------------------------------------------------------
IR_ADDRESS = 0x54
KIND_TOMBSTONE = 1
KIND_VICTORY = 2
PACKET_LEN = 9
MAX_VALUE = (1 << 21) - 1
BEAM_REPEATS = 3


def encode_packet(kind, nonce, value, a, b, c):
    """[0xA0|kind, nonce, value as 3 x 7 bits, a, b, c, checksum]. Only the
    marker sets the high bit, so a reader can resynchronise mid-stream."""
    value = clamp_int(value, 0, MAX_VALUE)
    data = [nonce & 0x7F, (value >> 14) & 0x7F, (value >> 7) & 0x7F, value & 0x7F, a & 0x7F, b & 0x7F, c & 0x7F]
    total = kind
    for byte in data:
        total += byte
    return [0xA0 | kind] + data + [total & 0x7F]


def decode_packet(packet):
    if len(packet) != PACKET_LEN:
        return None
    marker = packet[0]
    kind = marker & 0x0F
    if (marker & 0xF0) != 0xA0 or kind not in (KIND_TOMBSTONE, KIND_VICTORY):
        return None
    total = kind
    for byte in packet[1:8]:
        if byte & 0x80:
            return None
        total += byte
    if (total & 0x7F) != packet[8]:
        return None
    return {
        "kind": kind,
        "nonce": packet[1],
        "value": (packet[2] << 14) | (packet[3] << 7) | packet[4],
        "a": packet[5],
        "b": packet[6],
        "c": packet[7],
    }


class PacketReader:
    """Reassembles packets from NEC command bytes. A partial packet is
    dropped when the next byte arrives more than gap_ms after the last."""

    def __init__(self, gap_ms=900):
        self.gap_ms = gap_ms
        self.buffer = []
        self.last_ms = None

    def feed(self, byte, now_ms=None):
        byte &= 0xFF
        if now_ms is not None:
            if self.buffer and self.last_ms is not None and now_ms - self.last_ms > self.gap_ms:
                self.buffer = []
            self.last_ms = now_ms
        if byte & 0x80:
            self.buffer = [byte] if (byte & 0xF0) == 0xA0 else []
            return None
        if not self.buffer:
            return None
        self.buffer.append(byte)
        if len(self.buffer) < PACKET_LEN:
            return None
        packet = self.buffer
        self.buffer = []
        return decode_packet(packet)


class IrInbox:
    """Turns received NEC command bytes into new packets, ignoring our own
    reflections (same nonce) and the repeats of a burst."""

    def __init__(self, nonce, memory_ms=20000):
        self.nonce = nonce & 0x7F
        self.memory_ms = memory_ms
        self.reader = PacketReader()
        self.seen = []

    def feed(self, byte, now_ms):
        packet = self.reader.feed(byte, now_ms)
        if packet is None or packet["nonce"] == self.nonce:
            return None
        key = (packet["kind"], packet["nonce"], packet["value"], packet["a"], packet["b"], packet["c"])
        fresh = []
        duplicate = False
        for seen_key, stamp in self.seen:
            if now_ms - stamp < self.memory_ms:
                fresh.append((seen_key, stamp))
                if seen_key == key:
                    duplicate = True
        self.seen = fresh
        if duplicate:
            return None
        self.seen.append((key, now_ms))
        return packet


def tombstone_packet(nonce, record):
    step, cause, epitaph, role, _beamed = record
    return encode_packet(KIND_TOMBSTONE, nonce, step, cause, epitaph, role)


def victory_packet(nonce, score, survivors, days, role):
    return encode_packet(KIND_VICTORY, nonce, score, survivors, min(days, 127), role)


def tombstone_record(step, cause, epitaph, role, beamed):
    return [
        clamp_int(step, 0, MAX_STEPS),
        clamp_int(cause, 0, len(CAUSES) - 1),
        clamp_int(epitaph, 0, len(EPITAPHS) - 1),
        clamp_int(role, 0, len(ROLES) - 1),
        1 if beamed else 0,
    ]


def tombstone_from_packet(packet):
    if packet is None or packet["kind"] != KIND_TOMBSTONE:
        return None
    return tombstone_record(packet["value"], packet["a"], packet["b"], packet["c"], True)


def victory_from_packet(packet):
    """Returns (score, survivors, days, role) or None."""
    if packet is None or packet["kind"] != KIND_VICTORY:
        return None
    return (packet["value"], clamp_int(packet["a"], 0, len(PARTY)), packet["b"], clamp_int(packet["c"], 0, len(ROLES) - 1))


def tombstone_lines(record):
    step, cause, epitaph, role, beamed = record
    return (
        "Step " + commas(step),
        "Here lies the " + ROLES[role][0] + "'s party",
        "Died of " + CAUSES[cause],
        '"' + EPITAPHS[epitaph] + '"',
        "Beamed in over IR" if beamed else "From your own wagon",
    )


# ----- saved data -------------------------------------------------------------
MAX_TOMBSTONES = 12


def default_save():
    return {"best": 0, "visual": 0, "auto_camp": True, "tombstones": [], "victories": 0,
            "runs": 0, "beamed": 0, "met": 0, "run": None}


def clean_save(data):
    """Validate everything loaded from State so bad JSON cannot crash the app."""
    clean = default_save()
    if not isinstance(data, dict):
        return clean
    clean["best"] = clamp_int(data.get("best"), 0, 10000000, 0)
    clean["visual"] = clamp_int(data.get("visual"), 0, 1, 0)
    clean["auto_camp"] = data.get("auto_camp") is not False
    for key in ("victories", "runs", "beamed", "met"):
        clean[key] = clamp_int(data.get(key), 0, 100000, 0)
    stones = data.get("tombstones")
    if isinstance(stones, list):
        for stone in stones:
            if isinstance(stone, list) and len(stone) == 5:
                clean["tombstones"].append(tombstone_record(stone[0], stone[1], stone[2], stone[3], stone[4]))
    clean["tombstones"] = clean["tombstones"][-MAX_TOMBSTONES:]
    run = data.get("run")
    clean["run"] = run if isinstance(run, dict) else None
    return clean


def add_tombstone(save, record):
    stones = [stone for stone in save["tombstones"] if stone[:4] != record[:4]]
    stones.append(record)
    save["tombstones"] = stones[-MAX_TOMBSTONES:]
    return save["tombstones"]
