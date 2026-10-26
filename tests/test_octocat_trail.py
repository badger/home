"""Host-side tests for The Octocat Trail (badge/apps/octocat_trail).

The app's modules load under unique names (octocat_trail_<module>) so they
never collide with other apps' modules in one test process. Every
sys.modules entry touched while loading is restored afterwards, and badge
runtime globals are patched onto the app modules, never onto builtins.
"""

import ast
import importlib.util
import io
import json
import re
import sys
import tokenize
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "badge" / "apps" / "octocat_trail"
MODULES = ("trail_map", "trail_logic")
_MISSING = object()


def load_modules(prefix="octocat_trail_", extra=None, names=MODULES):
    """Load app modules as prefix + name. While loading, the plain names
    point at the new modules so the app's own `import trail_logic as tl`
    lines resolve; afterwards sys.modules is restored exactly."""
    patch = {"aye_arr": None}
    if extra:
        patch.update(extra)
    saved = {}
    loaded = {}
    flag = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        for key, value in patch.items():
            saved.setdefault(key, sys.modules.get(key, _MISSING))
            sys.modules[key] = value
        for name in names:
            spec = importlib.util.spec_from_file_location(prefix + name, APP / (name + ".py"))
            module = importlib.util.module_from_spec(spec)
            saved.setdefault(name, sys.modules.get(name, _MISSING))
            sys.modules[name] = module
            spec.loader.exec_module(module)
            loaded[name] = module
    finally:
        for key, value in saved.items():
            if value is _MISSING:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value
        sys.dont_write_bytecode = flag
    return loaded


_APP = load_modules()
tm = _APP["trail_map"]
tl = _APP["trail_logic"]

BOTH_RIVERS = tm.deployed_bit(tm.MERGE) | tm.deployed_bit(tm.DNS)


def reachable_stops(deployed):
    dist = tm.distances(tm.START[0], tm.START[1], deployed)
    found = []
    for index in range(len(tm.STOPS)):
        stop = tm.STOPS[index]
        if dist[stop[4] * tm.W + stop[3]] != tm.UNREACHED:
            found.append(index)
    return found


class LoaderTests(unittest.TestCase):
    def test_modules_load_under_unique_names_without_leaking(self):
        for name in MODULES:
            self.assertEqual(_APP[name].__name__, "octocat_trail_" + name)
            self.assertIsNot(sys.modules.get(name), _APP[name])
            self.assertIsNot(sys.modules.get("octocat_trail_" + name), _APP[name])


class MapTests(unittest.TestCase):

    def test_out_of_bounds_is_bay_water(self):
        for x, y in ((-1, 0), (0, -1), (tm.W, 0), (0, tm.H), (-5, -5)):
            self.assertEqual(tm.terrain(x, y), tm.WATER)
            self.assertFalse(tm.walkable(x, y, BOTH_RIVERS))
            self.assertEqual(tm.stop_at(x, y), -1)

    def test_walkable_codes(self):
        walk = (tm.LOT, tm.GRASS, tm.DECK, tm.PATH, tm.DOOR, tm.DOCK, tm.FLAG)
        for code in range(len(tm.WALK)):
            self.assertEqual(tm.passable(code), code in walk, code)
        for code in (tm.WATER, tm.ROOF, tm.FENCE, tm.TREE):
            self.assertFalse(tm.passable(code, BOTH_RIVERS))

    def test_gangways_need_their_deployment(self):
        merge = tm.deployed_bit(tm.MERGE)
        dns = tm.deployed_bit(tm.DNS)
        self.assertEqual(merge, 1 << 8)
        self.assertFalse(tm.passable(tm.GANG1))
        self.assertTrue(tm.passable(tm.GANG1, merge))
        self.assertFalse(tm.passable(tm.GANG1, dns))
        self.assertFalse(tm.passable(tm.GANG2, merge))
        self.assertTrue(tm.passable(tm.GANG2, dns))

    def test_docks_span_the_water_to_their_landings(self):
        self.assertEqual(tm.landing(tm.MERGE), (34, 32))
        self.assertEqual(tm.landing(tm.DNS), (66, 36))
        self.assertIsNone(tm.landing(0))
        self.assertIsNone(tm.dock(tm.END))
        for x0, y, x1, gang, stop in tm.DOCKS:
            self.assertEqual(tm.dock(stop), (x0, y, x1, gang, stop))
            self.assertEqual(tm.terrain(x0, y), tm.DOCK)
            self.assertEqual(tm.stop_at(x0, y), stop)
            self.assertTrue(tm.walkable(x1, y))
            for x in range(x0 + 1, x1):
                self.assertEqual(tm.terrain(x, y), gang)
                self.assertFalse(tm.walkable(x, y))
                self.assertTrue(tm.walkable(x, y, tm.deployed_bit(stop)))

    def test_stops_have_walkable_unique_doors(self):
        self.assertEqual(len(tm.STOPS), 13)
        doors = set()
        for index in range(len(tm.STOPS)):
            name, short, kind, x, y = tm.STOPS[index]
            self.assertIn(kind, ("store", "sight", "heal", "meadow", "river", "end"))
            self.assertTrue(name and short)
            self.assertTrue(tm.walkable(x, y, BOTH_RIVERS), name)
            self.assertEqual(tm.stop_at(x, y), index)
            doors.add((x, y))
        self.assertEqual(len(doors), len(tm.STOPS))
        self.assertEqual(tm.START, tm.STOPS[0][3:])
        self.assertEqual(tm.STOPS[tm.MERGE][0], "Merge Conflict River")
        self.assertEqual(tm.STOPS[tm.DNS][0], "DNS Propagation Rapids")
        self.assertIn("git init", tm.STOPS[0][0])
        self.assertIn("GitHub Universe Mainstage", tm.STOPS[tm.END][0])
        self.assertEqual(tm.STOPS[tm.END][2], "end")

    def test_rivers_gate_the_venue(self):
        self.assertEqual(reachable_stops(0), list(range(0, 9)))
        self.assertEqual(reachable_stops(tm.deployed_bit(tm.MERGE)), list(range(0, 12)))
        self.assertEqual(reachable_stops(BOTH_RIVERS), list(range(0, 13)))
        self.assertEqual(tm.ROUTE, (0, 1, tm.MERGE, 9, tm.DNS, tm.END))

    def test_distances_are_breadth_first(self):
        dist = tm.distances(tm.START[0], tm.START[1], BOTH_RIVERS)
        self.assertEqual(dist[tm.START[1] * tm.W + tm.START[0]], 0)
        for y in range(tm.H):
            for x in range(tm.W):
                here = dist[y * tm.W + x]
                if here == tm.UNREACHED or here == 0:
                    continue
                self.assertTrue(tm.walkable(x, y, BOTH_RIVERS))
                best = tm.UNREACHED
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < tm.W and 0 <= ny < tm.H:
                        best = min(best, dist[ny * tm.W + nx])
                self.assertEqual(best, here - 1, (x, y))

    def test_distances_from_water_reach_nothing(self):
        dist = tm.distances(0, 0)
        self.assertEqual(tm.terrain(0, 0), tm.WATER)
        self.assertEqual(set(dist), {tm.UNREACHED})


class QuietRng(tl.Rng):
    """Deterministic test RNG. chance() follows a script, then answers False;
    randint() follows a script, then returns low; choice() takes the first
    item; uniform() returns low. Every chance() probability is recorded."""

    def __init__(self, chances=(), randints=()):
        tl.Rng.__init__(self, 99)
        self.chances = list(chances)
        self.randints = list(randints)
        self.asked = []

    def chance(self, probability):
        self.asked.append(probability)
        return self.chances.pop(0) if self.chances else False

    def randint(self, low, high):
        if self.randints:
            value = self.randints.pop(0)
            if not low <= value <= high:
                raise AssertionError("scripted randint %r outside %r..%r" % (value, low, high))
            return value
        return low

    def uniform(self, low, high):
        return low

    def choice(self, items):
        return items[0]


def stocked(role=0, rng=None, brew=200.0, lgtm=50, patches=0):
    trail = tl.Trail(role, rng or QuietRng())
    trail.supplies["brew"] = brew
    trail.supplies["lgtm"] = lgtm
    trail.supplies["patches"] = patches
    return trail


def at_river(stop, role=0, rng=None, **supplies):
    trail = stocked(role, rng, **supplies)
    door = tm.STOPS[stop]
    trail.x, trail.y = door[3], door[4]
    if stop == tm.DNS:
        trail.deployed = tm.deployed_bit(tm.MERGE)
    trail.arrive(stop, [])
    return trail


def walk_to(trail, stop, limit=3000):
    """Walk the shortest route to a stop's door, passing time as the game does."""
    door = tm.STOPS[stop]
    dist = tm.distances(door[3], door[4], trail.deployed)
    lines = []
    outcome = None
    for _ in range(limit):
        if (trail.x, trail.y) == (door[3], door[4]):
            return lines, outcome
        here = dist[trail.y * tm.W + trail.x]
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            x, y = trail.x + dx, trail.y + dy
            if tm.walkable(x, y, trail.deployed) and dist[y * tm.W + x] == here - 1:
                break
        else:
            raise AssertionError("no way forward from %r" % ((trail.x, trail.y),))
        trail.step(dx, dy)
        more, outcome = trail.after_step()
        lines.extend(more)
    raise AssertionError("walk did not finish")


def edge_of(code, deployed=0):
    """A reachable cell next to an impassable cell of the given terrain."""
    dist = tm.distances(tm.START[0], tm.START[1], deployed)
    for y in range(tm.H):
        for x in range(tm.W):
            if dist[y * tm.W + x] == tm.UNREACHED:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if tm.terrain(x + dx, y + dy) == code and not tm.walkable(x + dx, y + dy, deployed):
                    return x, y, dx, dy
    return None


class HelperTests(unittest.TestCase):

    def test_number_formatting(self):
        self.assertEqual(tl.commas(0), "0")
        self.assertEqual(tl.commas(999), "999")
        self.assertEqual(tl.commas(1000), "1,000")
        self.assertEqual(tl.commas(1234567), "1,234,567")
        self.assertEqual(tl.commas(-1234), "-1,234")
        self.assertEqual(tl.tenths(35), "3.5")
        self.assertEqual(tl.tenths(140), "14.0")
        self.assertEqual(tl.plural(1, "day"), "1 day")
        self.assertEqual(tl.plural(0, "keg"), "0 kegs")
        self.assertEqual(tl.plural(2, "patch", "es"), "2 patches")

    def test_clamps(self):
        self.assertEqual(tl.clamp(5, 0, 3), 3)
        self.assertEqual(tl.clamp(-1, 0, 3), 0)
        self.assertEqual(tl.clamp(2, 0, 3), 2)
        self.assertEqual(tl.clamp_int("7", 0, 5), 5)
        self.assertEqual(tl.clamp_int(3.9, 0, 9), 3)
        self.assertEqual(tl.clamp_int(None, 1, 9), 1)
        self.assertEqual(tl.clamp_int("x", 1, 9, 4), 4)
        self.assertEqual(tl.clamp_int(float("inf"), 0, 9), 0)

    def test_fnv1a_is_deterministic(self):
        self.assertEqual(tl.fnv1a(""), 0x811C9DC5)
        self.assertEqual(tl.fnv1a("a"), 0xE40C292C)
        self.assertEqual(tl.fnv1a(12), tl.fnv1a("12"))
        self.assertNotEqual(tl.fnv1a("wx1"), tl.fnv1a("wx2"))

    def test_wrap(self):
        self.assertEqual(tl.wrap("aa bb cc", 5, len), ["aa bb", "cc"])
        self.assertEqual(tl.wrap("a\n\nb", 10, len), ["a", "", "b"])
        self.assertEqual(tl.wrap("superlongword x", 4, len), ["superlongword", "x"])
        self.assertEqual(tl.wrap("  a  b ", 10, len), ["a b"])
        self.assertEqual(tl.wrap("", 10, len), [""])

    def test_health_tables(self):
        cases = ((100, "Good", 500), (70, "Good", 500), (69, "Fair", 400), (40, "Fair", 400),
                 (39, "Poor", 300), (20, "Poor", 300), (19, "Very poor", 200), (0, "Very poor", 200),
                 (-5, "Very poor", 200))
        for health, label, points in cases:
            self.assertEqual(tl.health_label(health), label)
            self.assertEqual(tl.health_points(health), points)

    def test_store_items(self):
        self.assertEqual(tl.store_item("brew")[1], 4)
        self.assertEqual(tl.carry_limit("patches"), 9)
        with self.assertRaises(KeyError):
            tl.store_item("credits")


class RngTests(unittest.TestCase):
    def test_xorshift_sequence_is_portable(self):
        # Pure masked integer arithmetic, so the badge draws the same values.
        rng = tl.Rng(1)
        self.assertEqual([rng.next32() for _ in range(3)], [270369, 67634689, 2647435461])
        self.assertEqual(tl.Rng(0).state, 0x6D2B79F5)
        self.assertEqual(tl.Rng(1 << 32).state, 0x6D2B79F5)

    def test_same_seed_same_draws(self):
        a = tl.Rng(42)
        b = tl.Rng(42)
        self.assertEqual([a.randint(0, 9) for _ in range(50)], [b.randint(0, 9) for _ in range(50)])

    def test_ranges(self):
        rng = tl.Rng(7)
        seen = set()
        for _ in range(2000):
            value = rng.randint(3, 6)
            self.assertTrue(3 <= value <= 6)
            seen.add(value)
            self.assertTrue(0.0 <= rng.random() < 1.0)
            self.assertTrue(2.0 <= rng.uniform(2.0, 4.0) <= 4.0)
            self.assertIn(rng.choice("abc"), "abc")
        self.assertEqual(seen, {3, 4, 5, 6})
        self.assertFalse(any(rng.chance(0.0) for _ in range(200)))
        self.assertTrue(all(rng.chance(1.0) for _ in range(200)))

    def test_weighted(self):
        rng = tl.Rng(3)
        self.assertIsNone(rng.weighted(((0, "a"),)))
        self.assertIsNone(rng.weighted(()))
        for _ in range(100):
            self.assertEqual(rng.weighted(((0, "a"), (2, "b"))), "b")
        self.assertEqual(set(rng.weighted(((1, "a"), (1, "b"))) for _ in range(200)), {"a", "b"})


class MemberTests(unittest.TestCase):
    def test_status(self):
        member = tl.Member("Mona")
        self.assertEqual((member.health, member.illness, member.alive), (100, -1, True))
        self.assertEqual(member.status(), "Good")
        member.health = 30
        self.assertEqual(member.status(), "Poor")
        member.illness = 1
        self.assertEqual(member.status(), "Has AI Slop Fever")
        member.alive = False
        member.cause = 0
        self.assertEqual(member.status(), "Died of node_modules dysentery")


class TrailTests(unittest.TestCase):
    def test_new_trail(self):
        trail = tl.Trail(0, QuietRng())
        self.assertEqual(trail.supplies, {"credits": 1600, "brew": 0.0, "lgtm": 0, "patches": 0})
        self.assertEqual([member.name for member in trail.members], list(tl.PARTY))
        self.assertEqual((trail.x, trail.y), tm.START)
        self.assertEqual((trail.at, trail.day, trail.steps), (0, 1, 0))
        self.assertEqual(trail.current_stop(), tm.STOPS[0])
        self.assertTrue(trail.at_kind("store"))
        self.assertEqual(trail.ticker, "Outfit the wagon at the Gatehouse store.")
        self.assertEqual(trail.next_stop(), 1)
        self.assertEqual([tl.Trail(r, QuietRng()).supplies["credits"] for r in range(3)], [1600, 1000, 600])
        self.assertEqual([tl.Trail(r, QuietRng()).multiplier() for r in range(3)], [1, 2, 3])
        self.assertEqual(tl.Trail(9, QuietRng()).role, 2)
        self.assertEqual(tl.Trail(-3, QuietRng()).role, 0)
        self.assertEqual(tl.Trail("x", QuietRng()).role, 0)

    def test_calendar(self):
        trail = tl.Trail(0, QuietRng())
        expected = ((1, "September 1, 2026", "Tue"), (4, "September 4, 2026", "Fri"),
                    (122, "December 31, 2026", "Thu"), (123, "January 1, 2027", "Fri"),
                    (366, "September 1, 2027", "Wed"))
        for day, text, weekday in expected:
            trail.day = day
            self.assertEqual(trail.date_text(), text)
            self.assertEqual(trail.weekday(), weekday)
            self.assertIn(trail.weather(), tl.WEATHER)
            self.assertEqual(trail.weather(), trail.weather())

    def test_walk_to_the_shop(self):
        trail = stocked()
        door = tm.STOPS[1]
        tiles = tm.distances(door[3], door[4])[tm.START[1] * tm.W + tm.START[0]]
        self.assertEqual(trail.steps_to_next(), tiles * tm.STEPS_PER_TILE)
        self.assertIs(trail.guide(), trail.guide())
        self.assertEqual(trail.tile_ms(), 256)
        lines, outcome = walk_to(trail, 1)
        self.assertEqual((outcome, trail.at, lines), ("stop", 1, []))
        self.assertEqual(trail.steps, tiles * tm.STEPS_PER_TILE)
        days = tiles * 256 // tl.DAY_MS
        self.assertEqual(trail.day, 1 + days)
        self.assertAlmostEqual(trail.supplies["brew"], 200.0 - days)
        self.assertEqual([member.health for member in trail.members], [100] * 5)
        self.assertTrue(trail.has_visited(1))
        self.assertEqual(trail.next_stop(), tm.MERGE)

    def test_step(self):
        trail = stocked()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if tm.walkable(tm.START[0] + dx, tm.START[1] + dy):
                break
        self.assertEqual(trail.step(dx, dy), 256)
        self.assertEqual((trail.x, trail.y), (tm.START[0] + dx, tm.START[1] + dy))
        self.assertEqual((trail.at, trail.steps, trail.pending_ms), (-1, 8, 256))
        self.assertEqual(trail.step(0, 0), 0)
        trail.x, trail.y = 0, 0
        self.assertEqual(trail.step(-1, 0), 0)
        self.assertEqual(trail.facing, -1)
        self.assertEqual(trail.step(1, 0), 0)
        self.assertEqual(trail.facing, 1)
        self.assertEqual((trail.x, trail.y, trail.steps), (0, 0, 8))

    def test_steps_per_day_modifiers(self):
        trail = stocked()
        speeds = []
        for pace in range(3):
            trail.pace = pace
            speeds.append(trail.steps_per_day())
        self.assertEqual(speeds, [20, 26, 34])
        trail.pace = 0
        trail.turbo_days = 1
        self.assertEqual(trail.steps_per_day(), 35)
        trail.turbo_days = 0
        trail.tailwind = 2
        self.assertEqual(trail.steps_per_day(), 35)
        trail.tailwind = 0
        trail.supplies["brew"] = 0
        self.assertEqual(trail.steps_per_day(), 15)
        for member in trail.members:
            member.health = 30
        self.assertEqual(trail.steps_per_day(), 12)

    def test_blocked_reasons(self):
        trail = stocked()
        cases = ((tm.FENCE, 0, "Load-in zone: no entry from the plaza."),
                 (tm.GANG1, 0, "Gangway is up. Cross at the dock."),
                 (tm.GANG2, tm.deployed_bit(tm.MERGE), "Gangway is up. Cross at the dock."),
                 (tm.WATER, 0, "That way lies San Francisco Bay."),
                 (tm.ROOF, 0, ""),
                 (tm.TREE, 0, ""))
        for code, deployed, reason in cases:
            found = edge_of(code, deployed)
            self.assertIsNotNone(found, code)
            x, y, dx, dy = found
            trail.x, trail.y, trail.deployed = x, y, deployed
            self.assertEqual(trail.blocked_reason(dx, dy), reason, code)
            self.assertEqual(trail.step(dx, dy), 0)
            self.assertEqual((trail.x, trail.y), (x, y))
        trail.x, trail.y = 0, 0
        self.assertEqual(trail.blocked_reason(-1, 0), "That way lies San Francisco Bay.")

    def test_after_step_passes_days(self):
        trail = stocked()
        trail.pending_ms = tl.DAY_MS * 2 + 5
        self.assertEqual(trail.after_step(), ([], None))
        self.assertEqual((trail.day, trail.day_ms, trail.pending_ms), (3, 5, 0))
        self.assertAlmostEqual(trail.supplies["brew"], 198.0)

    def test_rest_day_heals(self):
        trail = stocked()
        for member in trail.members:
            member.health = 50
        self.assertEqual(trail.rest_day(), [])
        self.assertEqual([member.health for member in trail.members], [56] * 5)
        self.assertEqual(trail.day, 2)
        self.assertAlmostEqual(trail.supplies["brew"], 199.0)

    def test_running_dry_kills_by_withdrawal(self):
        trail = stocked(brew=0.0)
        for member in trail.members:
            member.health = 5
        lines = []
        trail.idle_days(1, lines)
        self.assertTrue(trail.all_dead())
        self.assertEqual(trail.last_cause, tl.CAUSE_WITHDRAWAL)
        self.assertIn("Markus has died of caffeine withdrawal.", lines)
        self.assertEqual(trail.ticker, "Out of Cold Brew Kegs! The party is fading.")
        self.assertEqual((trail.score(), trail.average_health()), (0, 0))
        self.assertEqual(trail.step(1, 0), 0)
        self.assertEqual(trail.after_step(), ([], "game_over"))
        trail.idle_days(3, lines)
        self.assertEqual(trail.day, 2)

    def test_death_march_exhaustion(self):
        trail = stocked()
        trail.pace = 2
        for member in trail.members:
            member.health = 2
        trail.idle_days(1, [])
        self.assertTrue(trail.all_dead())
        self.assertEqual(trail.last_cause, tl.CAUSE_EXHAUSTION)
        self.assertEqual(trail.tombstone(3), [0, tl.CAUSE_EXHAUSTION, 3, 0, 0])


class TrailEventTests(unittest.TestCase):
    def test_illness_and_recovery(self):
        trail = stocked(rng=QuietRng(randints=(0, 3, 1, 4)))
        lines = []
        trail._fall_ill(lines)
        trail._fall_ill(lines)
        self.assertEqual(lines, ["Markus has node_modules dysentery.", "Mona has AI Slop Fever."])
        self.assertEqual(trail.members[0].status(), "Has node_modules dysentery")
        self.assertEqual((trail.members[0].sick_days, trail.members[1].sick_days), (3, 4))
        trail.idle_days(4, lines)
        self.assertIn("Markus recovered from node_modules dysentery.", lines)
        self.assertIn("Mona recovered from AI Slop Fever.", lines)
        self.assertEqual([member.health for member in trail.members[:3]], [73, 60, 100])
        self.assertEqual(trail.members[0].status(), "Good")

    def test_illness_can_kill(self):
        trail = stocked(rng=QuietRng(chances=(True,)))
        member = trail.members[2]
        member.illness, member.sick_days, member.health = 1, 5, 20
        lines = []
        trail.idle_days(1, lines)
        self.assertFalse(member.alive)
        self.assertEqual(member.cause, 1)
        self.assertIn("Cameron has died of AI Slop Fever.", lines)
        self.assertEqual(trail.rng.asked, [tl.SICK_DEATH])

    def test_illness_chance_rises_with_strain(self):
        trail = stocked()
        self.assertAlmostEqual(trail._illness_chance(), 0.06)
        trail.pace, trail.rations, trail.supplies["brew"] = 2, 2, 0.0
        for member in trail.members:
            member.health = 45
        self.assertAlmostEqual(trail._illness_chance(), 0.165)

    def test_friday_force_push_without_patch(self):
        trail = stocked(rng=QuietRng(chances=(True,)))
        trail.day = 4
        lines = []
        trail._roll_event(lines)
        self.assertEqual(lines[:2], ["Force-pushed to main on Friday!",
                                     "No Hotfix Patch. Rebuilding history by hand: lost 3 days."])
        self.assertEqual(trail.day, 7)
        self.assertEqual(trail.members[0].health, 85)
        self.assertEqual(trail.rng.asked[0], tl.FRIDAY_FORCE_PUSH)

    def test_friday_force_push_with_patch(self):
        for role, healed in ((0, False), (tl.RUSTACEAN, True)):
            trail = stocked(role, QuietRng(chances=(True,)), patches=2)
            trail.day = 4
            for member in trail.members:
                member.health = 50
            lines = []
            trail._roll_event(lines)
            self.assertEqual(lines[:2], ["Force-pushed to main on Friday!", "A Hotfix Patch reverted it. Lost 1 day."])
            self.assertEqual((trail.supplies["patches"], trail.day), (1, 5))
            self.assertEqual("Rustacean hotfix: the party feels better." in lines, healed)
            self.assertEqual(trail.members[0].health, 60 if healed else 50)

    def test_weekday_skips_force_push(self):
        trail = stocked(rng=QuietRng(chances=(True,), randints=(1, 3)))
        lines = []
        trail._roll_event(lines)
        self.assertEqual(lines, ["Markus has AI Slop Fever."])
        self.assertEqual(trail.rng.asked, [tl.ILLNESS_CHANCE])

    def test_random_event_or_nothing(self):
        trail = stocked(rng=QuietRng(chances=(False, True)))
        lines = []
        trail._roll_event(lines)
        self.assertTrue(lines)
        quiet = stocked()
        lines = []
        quiet._roll_event(lines)
        self.assertEqual(lines, [])

    def test_each_trail_event(self):
        trail = stocked(brew=100.0, lgtm=0)
        lines = []
        trail._broken_ci(lines)
        self.assertEqual(lines[-1], "No Hotfix Patch. Rebuilt it from source: lost 2 days.")
        trail.supplies["patches"] = 1
        trail._broken_ci(lines)
        self.assertEqual((lines[-1], trail.supplies["patches"]), ("You swapped in a Hotfix Patch.", 0))
        trail._dependabot(lines)
        self.assertEqual(lines[-1], "A Dependabot caravan shared 8 Cold Brew Kegs.")
        trail._abandoned_wagon(lines)
        self.assertEqual(lines[-1], "You found an abandoned wagon with 10 LGTM Stamps.")
        self.assertEqual(trail.supplies["lgtm"], 10)
        trail._typosquatter(lines)
        self.assertEqual(lines[-1], "An npm typosquatter made off with 5 kegs.")
        day = trail.day
        trail._rate_limited(lines)
        trail._stale_readme(lines)
        self.assertEqual(trail.day, day + 3)
        trail._shortcut(lines)
        self.assertEqual((trail.tailwind, trail.steps_per_day()), (2, 35))
        trail.members[0].health = 15
        trail._python2(lines)
        self.assertEqual(lines[-2:], ["Markus was bitten by a Python 2 dependency.",
                                      "Markus has died of a Python 2 dependency."])
        trail.members[1].health = 95
        trail._unicorn(lines)
        self.assertEqual(trail.members[1].health, 100)
        trail.supplies["brew"] = 500.0
        trail._dependabot(lines)
        self.assertEqual(lines[-1], "A Dependabot caravan waved hello.")
        trail.supplies["brew"] = 0.0
        trail._typosquatter(lines)
        self.assertEqual(lines[-1], "An npm typosquatter found nothing worth taking.")

    def test_sights_pay_out_once(self):
        trail = stocked(lgtm=0)
        lines = []
        self.assertEqual(trail.arrive(2, lines), "stop")
        self.assertEqual(lines, ["The maintainers stamped 20 LGTMs for the road."])
        lines = []
        trail.arrive(2, lines)
        self.assertEqual((lines, trail.supplies["lgtm"], trail.sights_seen()), ([], 20, 1))
        for member in trail.members:
            member.health = 95
        trail.arrive(3, lines)
        self.assertEqual([member.health for member in trail.members], [100] * 5)
        self.assertEqual(trail.sights_seen(), 2)

    def test_firehouse_heals_every_few_days(self):
        trail = stocked()
        trail.members[0].illness, trail.members[0].sick_days = 2, 4
        for member in trail.members:
            member.health = 50
        lines = []
        self.assertEqual(trail.arrive(tl.FIREHOUSE, lines), "stop")
        self.assertEqual(lines, ["The Hotfix HQ crew patched up the party. Health +15.", "They cured 1 illness, too."])
        self.assertEqual([member.health for member in trail.members], [65] * 5)
        self.assertEqual(trail.members[0].illness, -1)
        lines = []
        trail.arrive(tl.FIREHOUSE, lines)
        self.assertEqual(lines, ["The crew is out on a call. Come back in 5 days."])
        trail.day += 5
        self.assertTrue(trail.heal_ready())
        self.assertEqual(trail.store_keys(), ("patches",))
        self.assertEqual(trail.price("patches"), 40)

    def test_arrive_kinds(self):
        trail = stocked()
        trail.turbo_days = 3
        self.assertEqual(trail.arrive(tm.END, []), "victory")
        self.assertEqual(trail.turbo_days, 0)
        self.assertTrue(trail.finished())
        river = stocked()
        self.assertEqual(river.arrive(tm.MERGE, []), "river")
        self.assertEqual(river.river, [20, 140])
        self.assertFalse(river.has_visited(tm.MERGE))


class TrailShopRiverTests(unittest.TestCase):
    def test_store_prices(self):
        trail = stocked()
        for stop, prices in ((0, (4, 1, 25)), (1, (5, 2, 32)), (9, (6, 2, 38))):
            trail.at = stop
            self.assertTrue(trail.at_store())
            self.assertEqual(trail.store_keys(), ("brew", "lgtm", "patches"))
            self.assertEqual(tuple(trail.price(key) for key in ("brew", "lgtm", "patches")), prices)
        trail.at = 2
        self.assertEqual((trail.at_store(), trail.markup(), trail.price("brew")), (False, 0, 4))

    def test_buy_and_sell_back(self):
        trail = tl.Trail(0, QuietRng())
        self.assertEqual(trail.buy("patches", 20), 9)
        self.assertEqual(trail.supplies["credits"], 1375)
        self.assertEqual(trail.buy("patches", 1), 0)
        self.assertEqual(trail.buy("brew", 1000), 343)
        self.assertEqual(trail.supplies["credits"], 3)
        self.assertEqual(trail.buy("lgtm", 10), 3)
        self.assertEqual(trail.buy("lgtm", 10), 0)
        self.assertEqual(trail.sell_back("brew", 50), 50)
        self.assertEqual(trail.supplies["credits"], 200)
        self.assertEqual(trail.basket, {"patches": 9, "brew": 293, "lgtm": 3})
        trail.arrive(1, [])
        self.assertEqual(trail.basket, {})
        self.assertEqual(trail.sell_back("brew", 10), 0)

    def test_turbo_sprint_cycle(self):
        trail = stocked(brew=0.0)
        self.assertFalse(trail.can_sprint())
        self.assertFalse(trail.start_sprint())
        trail.supplies["brew"] = 100.0
        self.assertTrue(trail.start_sprint())
        self.assertEqual((trail.turbo_days, trail.ticker), (tl.TURBO_DAYS, "Turbo sprint! 6 days of hustle."))
        self.assertFalse(trail.start_sprint())
        self.assertAlmostEqual(trail.brew_per_day(), 1.5)
        trail.idle_days(1, [])
        self.assertAlmostEqual(trail.supplies["brew"], 98.5)
        self.assertEqual(trail.members[0].health, 98)
        for _ in range(5):
            trail._end_day()
        self.assertEqual((trail.turbo_days, trail.turbo_cooldown), (0, tl.TURBO_COOLDOWN))
        self.assertEqual(trail.ticker, "Turbo sprint over. Catch your breath.")
        self.assertFalse(trail.can_sprint())
        for _ in range(tl.TURBO_COOLDOWN):
            trail._end_day()
        self.assertTrue(trail.can_sprint())

    def test_river_risk(self):
        trail = at_river(tm.MERGE)
        self.assertEqual(trail.river, [20, 140])
        self.assertEqual(trail.crossing_risk(tl.FORD), 0.0)
        trail.river[0] = 60
        risks = [trail.crossing_risk(option) for option in range(4)]
        for got, want in zip(risks, (0.7, 0.2, 0.02, 0.0)):
            self.assertAlmostEqual(got, want)
        atc = at_river(tm.MERGE, role=tl.ATC_LEAD)
        atc.river[0] = 60
        for option in range(3):
            self.assertAlmostEqual(atc.crossing_risk(option), risks[option] * 0.6)
        trail.river[0] = 999
        self.assertEqual(trail.crossing_risk(tl.FORD), 0.95)
        self.assertEqual((trail.ferry_cost(), at_river(tm.DNS).ferry_cost(), stocked().ferry_cost()), (40, 70, 0))
        self.assertEqual(stocked().crossing_risk(tl.FORD), 0.0)

    def test_river_options_need_supplies(self):
        trail = at_river(tm.DNS, role=tl.ATC_LEAD, lgtm=1)
        self.assertEqual([trail.river_option_ok(option) for option in range(5)], [True, False, True, True, False])
        trail.supplies["credits"] = 69
        self.assertFalse(trail.river_option_ok(tl.FERRY))
        self.assertEqual(trail.cross(tl.CAULK), ([], False))
        self.assertEqual(trail.cross(tl.FERRY), ([], False))
        self.assertEqual(stocked().cross(tl.FORD), ([], False))

    def test_wait_for_review(self):
        trail = at_river(tm.MERGE, rng=QuietRng(randints=(40, 140, 5)))
        self.assertEqual(trail.river, [40, 140])
        lines, crossed = trail.cross(tl.WAIT)
        self.assertFalse(crossed)
        self.assertEqual(trail.river, [45, 140])
        self.assertEqual(lines, ["You waited a day for review. The river is now 4.5 ft deep."])
        self.assertEqual((trail.day, trail.at), (2, tm.MERGE))

    def test_ford_success_lands_on_the_far_pier(self):
        trail = at_river(tm.MERGE)
        lines, crossed = trail.cross(tl.FORD)
        self.assertTrue(crossed)
        self.assertEqual(lines, ["YOLO! The deploy went green across Merge Conflict River."])
        self.assertEqual((trail.x, trail.y), tm.landing(tm.MERGE))
        self.assertEqual(trail.steps, 160)
        self.assertTrue(trail.deployed & tm.deployed_bit(tm.MERGE))
        self.assertTrue(trail.has_visited(tm.MERGE))
        self.assertEqual((trail.at, trail.river, trail.day), (-1, None, 2))
        self.assertEqual(trail.next_stop(), 9)
        trail.x = tm.dock(tm.MERGE)[0] + 1
        self.assertTrue(trail.step(-1, 0))
        self.assertEqual(trail.after_step(), ([], None))

    def test_caulk_and_ferry(self):
        trail = at_river(tm.MERGE, lgtm=5)
        lines, crossed = trail.cross(tl.CAULK)
        self.assertTrue(crossed)
        self.assertEqual(lines, ["Two LGTMs and a prayer: the gangway is down."])
        self.assertEqual(trail.supplies["lgtm"], 3)
        ferry = at_river(tm.DNS)
        lines, crossed = ferry.cross(tl.FERRY)
        self.assertTrue(crossed)
        self.assertEqual(lines, ["Copilot queued your ferry. Waited 1 day.", "Copilot ferried the wagon safely across."])
        self.assertEqual((ferry.supplies["credits"], ferry.day), (1600 - 70, 3))
        self.assertEqual((ferry.x, ferry.y), tm.landing(tm.DNS))
        self.assertEqual(ferry.next_stop(), tm.END)

    def test_failed_deploy_can_cost_a_life(self):
        trail = at_river(tm.MERGE, rng=QuietRng(chances=(True, True)), lgtm=10)
        trail.river[0] = 60
        lines, crossed = trail.cross(tl.FORD)
        self.assertTrue(crossed)
        self.assertEqual(lines[0], "The deploy failed in Merge Conflict River!")
        self.assertTrue(lines[1].startswith("Lost "))
        self.assertIn("Markus has died of an unresolved merge conflict.", lines)
        self.assertEqual(trail.living_count(), 4)
        self.assertEqual(len(trail.rng.asked), 2)
        self.assertAlmostEqual(trail.rng.asked[0], 0.7)
        self.assertAlmostEqual(trail.rng.asked[1], 0.33)
        self.assertLess(trail.supplies["brew"], 200.0)


class TrailScoreSaveTests(unittest.TestCase):
    def test_score(self):
        self.assertEqual(tl.Trail(0, QuietRng()).score(), 2870)
        self.assertEqual(tl.Trail(tl.ATC_LEAD, QuietRng()).score(), (2500 + 50 + 120) * 3)
        trail = stocked(patches=3, lgtm=120, brew=260.0)
        trail.visited |= 1 << 2
        trail.members[0].health = 30
        trail.members[1].alive = False
        self.assertEqual(trail.score(), 300 + 1500 + 50 + 6 + 2 + 10 + 320 + 40)

    def test_save_round_trip(self):
        trail = at_river(tm.MERGE, rng=QuietRng(randints=(33, 150)), lgtm=7, patches=2)
        trail.supplies["brew"] = 12.34
        trail.steps, trail.day, trail.pace, trail.rations = 777, 40, 1, 2
        trail.day_ms, trail.turbo_cooldown, trail.tailwind, trail.healed_day = 300, 4, 1, 30
        trail.members[1].illness, trail.members[1].sick_days, trail.members[1].health = 2, 3, 61
        trail.members[4].alive, trail.members[4].health, trail.members[4].cause = False, 0, 9
        data = trail.to_dict()
        self.assertEqual((data["v"], data["brew"], data["river"]), (2, 123, [33, 150]))
        restored = tl.Trail.from_dict(json.loads(json.dumps(data)), QuietRng())
        self.assertIsNotNone(restored)
        self.assertEqual(restored.to_dict(), data)
        self.assertAlmostEqual(restored.supplies["brew"], 12.3)
        self.assertEqual(restored.ticker, "Welcome back to Fort Mason.")
        self.assertEqual(restored.members[4].status(), "Died of a Friday force-push")
        self.assertEqual(restored.members[1].status(), "Has YAML indentation fatigue")


class TrailRestoreTests(unittest.TestCase):
    def setUp(self):
        self.base = tl.Trail(0, QuietRng()).to_dict()

    def restore(self, **changes):
        data = dict(self.base)
        data.update(changes)
        return tl.Trail.from_dict(data, QuietRng())

    def test_rejects_unusable_saves(self):
        self.assertIsNone(tl.Trail.from_dict(None, QuietRng()))
        self.assertIsNone(tl.Trail.from_dict([], QuietRng()))
        self.assertIsNone(self.restore(v=1))
        missing = dict(self.base)
        del missing["party"]
        self.assertIsNone(tl.Trail.from_dict(missing, QuietRng()))
        self.assertIsNone(self.restore(x=0, y=0))
        self.assertIsNone(self.restore(party=self.base["party"][:4]))
        self.assertIsNone(self.restore(party=[[1, 2]] + self.base["party"][1:]))
        self.assertIsNone(self.restore(party="nope"))
        self.assertIsNone(self.restore(party=[[0, -1, 0, 0, 1]] * 5))
        both = tm.deployed_bit(tm.MERGE) | tm.deployed_bit(tm.DNS)
        end = tm.STOPS[tm.END]
        self.assertIsNone(self.restore(x=end[3], y=end[4], at=tm.END, deployed=both))

    def test_far_pier_needs_the_crossing(self):
        x, y = tm.landing(tm.MERGE)
        self.assertIsNone(self.restore(x=x, y=y))
        trail = self.restore(x=x, y=y, deployed=tm.deployed_bit(tm.MERGE))
        self.assertIsNotNone(trail)
        self.assertEqual(trail.next_stop(), 9)

    def test_clamps_values(self):
        trail = self.restore(credits=-5, brew=99999, lgtm=-1, patches=99, role=7, pace=9, rations=-2, day=0,
                             deployed=(1 << len(tm.STOPS)) - 1, visited=0, facing=7, tail="x", last=None, healed=None)
        self.assertEqual(trail.supplies, {"credits": 0, "brew": 500.0, "lgtm": 0, "patches": 9})
        self.assertEqual((trail.role, trail.pace, trail.rations, trail.day), (2, 2, 0, 1))
        both = tm.deployed_bit(tm.MERGE) | tm.deployed_bit(tm.DNS)
        self.assertEqual((trail.deployed, trail.visited), (both, both | 1))
        self.assertEqual((trail.facing, trail.tailwind, trail.last_cause), (1, 0, tl.CAUSE_EXHAUSTION))
        self.assertEqual(trail.healed_day, -tl.HEAL_DAYS)
        party = [list(entry) for entry in self.base["party"]]
        party[0] = [0, 9, 99, 1, 3]
        party[1] = [55, 2, 4, 0, 99]
        trail = self.restore(party=party)
        first, second = trail.members[0], trail.members[1]
        self.assertEqual((first.health, first.illness, first.sick_days, first.alive), (1, 3, 30, True))
        self.assertEqual((second.health, second.illness, second.alive, second.cause), (0, -1, False, len(tl.CAUSES) - 1))

    def test_stop_must_match_position(self):
        self.assertEqual(self.restore(at=3).at, -1)
        self.assertEqual(self.restore(at=0).at, 0)

    def test_river_resume(self):
        door = tm.STOPS[tm.MERGE]
        trail = self.restore(x=door[3], y=door[4], at=tm.MERGE, river=None)
        self.assertEqual((trail.at, trail.river), (tm.MERGE, [20, 140]))
        trail = self.restore(x=door[3], y=door[4], at=tm.MERGE, river=[0, 9999])
        self.assertEqual(trail.river, [16, 180])
        trail = self.restore(x=door[3], y=door[4], at=tm.MERGE, deployed=tm.deployed_bit(tm.MERGE))
        self.assertEqual((trail.at, trail.river), (-1, None))


class HuntTests(unittest.TestCase):
    def quiet_hunt(self, stamps=10):
        hunt = tl.Hunt(tl.Rng(5), stamps)
        hunt.cover = []
        hunt.targets = []
        hunt.spawn_in = 10 ** 9
        return hunt

    def target(self, hunt, kind, offset):
        target = [kind, hunt.x + offset, hunt.y, 0.0, 0.0, tl.TARGET_KINDS[kind][3], 10 ** 6]
        hunt.targets.append(target)
        return target

    def test_cover_layout(self):
        for seed in range(25):
            for meadow, count in ((False, 7), (True, 9)):
                hunt = tl.Hunt(tl.Rng(seed), 10, meadow)
                self.assertEqual(len(hunt.cover), count)
                for x, y, radius, kind in hunt.cover:
                    self.assertEqual(radius, tl.COVER[kind][1])
                    self.assertTrue(radius + 6 <= x <= hunt.width - radius - 6)
                    self.assertTrue(radius + 6 <= y <= hunt.height - radius - 6)
                self.assertFalse(hunt.blocked(hunt.x, hunt.y, tl.HUNTER_RADIUS + 20))

    def test_no_stamps_no_hunt(self):
        hunt = tl.Hunt(tl.Rng(1), 0)
        self.assertEqual((hunt.done, hunt.reason), (True, "stamps"))
        self.assertFalse(hunt.fire())
        hunt.update(100, 1, 0, True)
        self.assertEqual(hunt.elapsed, 0)

    def test_walking_is_frame_rate_independent(self):
        hunt = self.quiet_hunt()
        x0, y0 = hunt.x, hunt.y
        hunt.update(100, 1, 0)
        self.assertAlmostEqual(hunt.x, x0 + 7.0)
        self.assertEqual((hunt.aim_x, hunt.aim_y, hunt.walk_ms), (1, 0, 100))
        hunt.update(100, 1, 1)
        self.assertAlmostEqual(hunt.x, x0 + 7.0 + 7.0 * 0.7071)
        self.assertAlmostEqual(hunt.y, y0 + 7.0 * 0.7071)
        for _ in range(100):
            hunt.update(100, -1, -1)
        self.assertEqual((hunt.x, hunt.y), (tl.HUNTER_RADIUS, tl.HUNTER_RADIUS))
        hunt.update(5000)
        self.assertEqual(hunt.elapsed, 103 * 100)
        self.assertEqual(hunt.remaining_ms(), tl.HUNT_MS - 10300)

    def test_cover_blocks_mona(self):
        hunt = self.quiet_hunt()
        x0 = hunt.x
        hunt.cover = [(x0 + 20, hunt.y, 9, 0)]
        for _ in range(20):
            hunt.update(100, 1, 0)
        self.assertEqual(hunt.x, x0)
        hunt.update(100, 0, 1)
        self.assertGreater(hunt.y, tl.HUNT_H / 2.0)

    def test_stamp_squashes_a_bug(self):
        hunt = self.quiet_hunt(5)
        self.target(hunt, tl.BUG, 40)
        self.assertTrue(hunt.fire())
        self.assertEqual((hunt.stamps, hunt.thrown, len(hunt.flying)), (4, 1, 1))
        hits = []
        for _ in range(5):
            hunt.update(100)
            hits.append(hunt.last_hit)
        self.assertEqual(hits, [False, True, False, False, False])
        self.assertEqual((hunt.kills, hunt.bounty, hunt.targets, hunt.flying), ([1, 0], 6, [], []))
        self.assertEqual(hunt.splats[0][3], tl.BUG)

    def test_slop_takes_two_stamps(self):
        hunt = self.quiet_hunt(5)
        slop = self.target(hunt, tl.SLOP, 60)
        hunt.fire()
        for _ in range(4):
            hunt.update(100)
        self.assertEqual((slop[5], hunt.kills, hunt.bounty), (1, [0, 0], 0))
        hunt.update(100, fire=True)
        for _ in range(4):
            hunt.update(100)
        self.assertEqual((hunt.kills, hunt.bounty), ([0, 1], 25))

    def test_cover_stops_stamps(self):
        hunt = self.quiet_hunt(5)
        hunt.cover = [(hunt.x + 30, hunt.y, 5, 2)]
        self.target(hunt, tl.BUG, 60)
        hunt.fire()
        for _ in range(2):
            hunt.update(100)
        self.assertEqual((hunt.kills, len(hunt.targets), hunt.flying), ([0, 0], 1, []))
        self.assertEqual(hunt.splats[-1][3], -1)
        for _ in range(3):
            hunt.update(100)
        self.assertEqual(hunt.splats, [])

    def test_three_stamps_in_the_air(self):
        hunt = self.quiet_hunt()
        hunt.aim_x, hunt.aim_y = 1, -1
        self.assertEqual([hunt.fire() for _ in range(4)], [True, True, True, False])
        self.assertEqual((hunt.stamps, len(hunt.flying)), (7, tl.MAX_SHOTS))
        self.assertAlmostEqual(hunt.flying[0][2], tl.SHOT_SPEED * 0.7071)
        self.assertAlmostEqual(hunt.flying[0][3], -tl.SHOT_SPEED * 0.7071)
        for _ in range(20):
            hunt.update(100)
        self.assertEqual(hunt.flying, [])
        self.assertTrue(hunt.fire())

    def test_endings(self):
        hunt = self.quiet_hunt(1)
        hunt.fire()
        hunt.update(100)
        self.assertFalse(hunt.done)
        for _ in range(10):
            hunt.update(100)
        self.assertEqual((hunt.done, hunt.reason), (True, "stamps"))
        timed = self.quiet_hunt()
        for _ in range(tl.HUNT_MS // 100 - 1):
            timed.update(100)
        self.assertEqual((timed.done, timed.remaining_ms()), (False, 100))
        timed.update(100)
        self.assertEqual((timed.done, timed.reason, timed.remaining_ms()), (True, "time", 0))
        timed.finish()
        self.assertEqual(timed.reason, "time")
        quit_early = self.quiet_hunt()
        quit_early.finish()
        self.assertEqual((quit_early.done, quit_early.reason), (True, "quit"))

    def test_targets_spawn_from_edges(self):
        hunt = self.quiet_hunt()
        for _ in range(80):
            kind, x, y, vx, vy, hp, turn = hunt.spawn()
            radius = tl.TARGET_KINDS[kind][1]
            self.assertEqual(hp, tl.TARGET_KINDS[kind][3])
            self.assertTrue(300 <= turn <= 800)
            if x == -radius:
                self.assertGreater(vx, 0)
            elif x == hunt.width + radius:
                self.assertLess(vx, 0)
            elif y == -radius:
                self.assertGreater(vy, 0)
            else:
                self.assertEqual(y, hunt.height + radius)
                self.assertLess(vy, 0)
        live = tl.Hunt(tl.Rng(11), 10, True)
        most = 0
        for _ in range(200):
            live.update(100)
            most = max(most, len(live.targets))
        self.assertTrue(0 < most <= tl.MAX_TARGETS)

    def test_haul_and_summary(self):
        hunt = self.quiet_hunt()
        hunt.bounty = 150
        self.assertEqual([hunt.haul(0), hunt.haul(450), hunt.haul(500), hunt.haul(600)], [100, 50, 0, 0])
        hunt.kills, hunt.bounty = [2, 1], 37
        self.assertEqual(hunt.summary(37), ["You stamped out 2 bugs and 1 AI slop blob.", "Bounty: 37 kegs of cold brew."])
        self.assertEqual(hunt.summary(10)[-1], "You could only haul 10 kegs back to the wagon.")
        hunt.kills, hunt.bounty, hunt.thrown = [0, 0], 0, 3
        self.assertEqual(hunt.summary(0), ["You stamped out 0 bugs and 0 AI slop blobs.",
                                           "No bounty this time. Used 3 LGTM Stamps."])

    def test_trail_hunt_round_trip(self):
        trail = stocked(lgtm=12, brew=450.0)
        trail.at = -1
        hunt = trail.start_hunt()
        self.assertEqual((hunt.stamps, hunt.meadow), (12, trail.in_meadow()))
        hunt.stamps, hunt.bounty, hunt.kills = 9, 80, [5, 2]
        lines = trail.finish_hunt(hunt)
        self.assertEqual(lines, ["You stamped out 5 bugs and 2 AI slop blobs.", "Bounty: 80 kegs of cold brew.",
                                 "You could only haul 50 kegs back to the wagon."])
        self.assertEqual((trail.supplies["lgtm"], trail.day), (9, 2))
        self.assertAlmostEqual(trail.supplies["brew"], 499.0)
        trail.at = tl.MEADOW
        self.assertTrue(trail.start_hunt().meadow)


def feed_light(detector, steps, start=0, dt=50):
    """Feed (value, duration_ms) pairs and return the [(event, ms)] it raised."""
    events = []
    now = start
    for value, duration in steps:
        for _ in range(duration // dt):
            now += dt
            event = detector.update(now, dt, value)
            if event:
                events.append((event, now))
    return events


class DetectorTests(unittest.TestCase):
    def test_shake_fires_once_per_burst(self):
        for sign in (1, -1):
            shake = tl.ShakeDetector()
            self.assertFalse(shake.update(0, 0, 16384 * sign, 0))
            fired = [shake.update((i + 1) * 50, 0, (40000 if i % 2 == 0 else 16384) * sign, 0) for i in range(12)]
            self.assertEqual((fired.index(True), fired.count(True)), (4, 1))

    def test_shake_ignores_steady_and_slow_motion(self):
        for value in (16384, -16384, 0):
            steady = tl.ShakeDetector()
            self.assertFalse(any(steady.update(t * 50, 0, value, 0) for t in range(100)))
        slow = tl.ShakeDetector()
        slow.update(0, 0, 16384, 0)
        self.assertFalse(any(slow.update((i + 1) * 500, 0, 40000 if i % 2 == 0 else 16384, 0) for i in range(20)))
        tilted = tl.ShakeDetector()
        tilted.update(0, 0, 16384, 0)
        self.assertFalse(any(tilted.update(t * 50, 16384, 0, 0) for t in range(1, 50)))

    def test_room_going_dark_and_light(self):
        detector = tl.DarkDetector()
        events = feed_light(detector, ((40000, 3000), (0, 2000), (40000, 3000)))
        self.assertEqual([event for event, _ms in events], ["dark", "light"])
        self.assertTrue(4000 <= events[0][1] <= 5000 and 6000 <= events[1][1] <= 7000)

    def test_no_sensor_never_camps(self):
        zero = tl.DarkDetector()
        self.assertEqual(feed_light(zero, ((0, 10000),)), [])
        self.assertFalse(zero.armed())
        bright = tl.DarkDetector()
        self.assertEqual(feed_light(bright, ((40000, 20000),)), [])
        self.assertTrue(bright.armed())

    def test_brief_shadow_is_ignored(self):
        detector = tl.DarkDetector()
        self.assertEqual(feed_light(detector, ((40000, 3000), (0, 800), (40000, 3000))), [])

    def test_suppress_waits_for_light(self):
        detector = tl.DarkDetector()
        feed_light(detector, ((40000, 3000),))
        detector.suppress()
        self.assertEqual(feed_light(detector, ((0, 3000), (40000, 3000)), 3000), [])
        self.assertFalse(detector.suppressed)
        self.assertEqual([event for event, _ms in feed_light(detector, ((0, 3000),), 9000)], ["dark"])


class PacketTests(unittest.TestCase):
    def test_round_trip(self):
        packet = tl.encode_packet(tl.KIND_VICTORY, 0x15, 123456, 4, 77, 2)
        self.assertEqual((len(packet), packet[0]), (tl.PACKET_LEN, 0xA2))
        self.assertTrue(all(byte < 0x80 for byte in packet[1:]))
        self.assertEqual(tl.decode_packet(packet), {"kind": 2, "nonce": 0x15, "value": 123456, "a": 4, "b": 77, "c": 2})
        self.assertEqual(tl.decode_packet(tl.encode_packet(1, 0xFF, -5, 200, 0, 0))["value"], 0)
        self.assertEqual(tl.decode_packet(tl.encode_packet(1, 1, 10 ** 9, 0, 0, 0))["value"], tl.MAX_VALUE)

    def test_rejects_corruption(self):
        good = tl.encode_packet(tl.KIND_TOMBSTONE, 3, 500, 1, 2, 0)
        self.assertIsNotNone(tl.decode_packet(good))
        self.assertIsNone(tl.decode_packet(good[:-1]))
        for index, change in ((8, lambda b: b ^ 1), (0, lambda b: 0xA3), (0, lambda b: 0xB1), (3, lambda b: b | 0x80)):
            bad = list(good)
            bad[index] = change(bad[index])
            self.assertIsNone(tl.decode_packet(bad), index)

    def test_reader_resyncs_and_times_out(self):
        packet = tl.encode_packet(tl.KIND_TOMBSTONE, 9, 1234, 2, 3, 1)
        reader = tl.PacketReader()
        out = [reader.feed(byte, 0) for byte in [5, 6] + packet]
        self.assertEqual(out[:-1], [None] * 10)
        self.assertEqual(out[-1]["value"], 1234)
        self.assertEqual([reader.feed(byte) for byte in packet[:4] + packet][-1]["nonce"], 9)
        for byte in packet[:5]:
            reader.feed(byte, 1000)
        self.assertEqual([reader.feed(byte, 2000) for byte in packet[5:]], [None] * 4)
        for byte in packet[:5]:
            reader.feed(byte, 3000)
        reader.feed(0xFF, 3000)
        self.assertEqual([reader.feed(byte, 3000) for byte in packet[5:]], [None] * 4)

    def test_inbox_ignores_echoes_and_repeats(self):
        inbox = tl.IrInbox(0xD5)
        own = tl.encode_packet(tl.KIND_VICTORY, 0x55, 10, 1, 2, 0)
        self.assertEqual([inbox.feed(byte, 0) for byte in own], [None] * 9)
        other = tl.encode_packet(tl.KIND_VICTORY, 0x21, 10, 1, 2, 0)
        self.assertEqual([inbox.feed(byte, 100) for byte in other][-1]["nonce"], 0x21)
        self.assertEqual([inbox.feed(byte, 200) for byte in other], [None] * 9)
        self.assertEqual([inbox.feed(byte, 20100) for byte in other][-1]["nonce"], 0x21)

    def test_records(self):
        record = tl.tombstone_record(1234, 1, 2, 1, False)
        packet = tl.decode_packet(tl.tombstone_packet(7, record))
        self.assertEqual(tl.tombstone_from_packet(packet), [1234, 1, 2, 1, 1])
        self.assertIsNone(tl.victory_from_packet(packet))
        win = tl.decode_packet(tl.victory_packet(7, 9999, 4, 300, 2))
        self.assertEqual(tl.victory_from_packet(win), (9999, 4, 127, 2))
        self.assertIsNone(tl.tombstone_from_packet(win))
        self.assertIsNone(tl.tombstone_from_packet(None))
        self.assertIsNone(tl.victory_from_packet(None))
        forged = tl.decode_packet(tl.encode_packet(tl.KIND_VICTORY, 1, 5, 99, 3, 99))
        self.assertEqual(tl.victory_from_packet(forged), (5, 5, 3, 2))
        self.assertEqual(tl.tombstone_record(-1, 99, 99, 99, 0), [0, len(tl.CAUSES) - 1, len(tl.EPITAPHS) - 1, 2, 0])
        lines = tl.tombstone_lines([1234, 0, 0, 2, 1])
        self.assertEqual(lines, ("Step 1,234", "Here lies the ATC Control Lead's party", "Died of node_modules dysentery",
                                 '"' + tl.EPITAPHS[0] + '"', "Beamed in over IR"))
        self.assertEqual(tl.tombstone_lines([5, 0, 0, 0, 0])[4], "From your own wagon")


class SaveDataTests(unittest.TestCase):
    def test_clean_save(self):
        self.assertEqual(tl.clean_save(None), tl.default_save())
        self.assertEqual(tl.clean_save("junk"), tl.default_save())
        stones = [[i, 0, 0, 0, 0] for i in range(15)] + ["bad", [1, 2]]
        clean = tl.clean_save({"best": -4, "visual": 7, "auto_camp": False, "tombstones": stones, "victories": "3",
                               "runs": 2.5, "beamed": None, "met": 10 ** 9, "run": {"v": 2}})
        self.assertEqual((clean["best"], clean["visual"], clean["auto_camp"]), (0, 1, False))
        self.assertEqual((clean["victories"], clean["runs"], clean["beamed"], clean["met"]), (3, 2, 0, 100000))
        self.assertEqual(len(clean["tombstones"]), tl.MAX_TOMBSTONES)
        self.assertEqual(clean["tombstones"][0], [3, 0, 0, 0, 0])
        self.assertEqual(clean["run"], {"v": 2})
        self.assertIsNone(tl.clean_save({"run": [1]})["run"])
        self.assertTrue(tl.clean_save({"auto_camp": 0})["auto_camp"])
        self.assertIsNot(tl.default_save()["tombstones"], tl.default_save()["tombstones"])

    def test_add_tombstone(self):
        save = tl.default_save()
        tl.add_tombstone(save, [10, 1, 2, 0, 0])
        tl.add_tombstone(save, [10, 1, 2, 0, 1])
        self.assertEqual(save["tombstones"], [[10, 1, 2, 0, 1]])
        for i in range(20):
            tl.add_tombstone(save, [i + 100, 0, 0, 0, 0])
        self.assertEqual(len(save["tombstones"]), tl.MAX_TOMBSTONES)
        self.assertEqual(save["tombstones"][-1][0], 119)


class FakeDevice:
    """Stands in for the runtime `badge` object's sensor and light calls."""

    def __init__(self, imu=(0, 16384, 0, 0, 0, 0), light=40000, lights_error=None):
        self.imu_value = imu
        self.light_value = light
        self.lights_error = lights_error
        self.lights = []

    def imu(self):
        if isinstance(self.imu_value, Exception):
            raise self.imu_value
        return self.imu_value

    def light_level(self):
        if isinstance(self.light_value, Exception):
            raise self.light_value
        return self.light_value

    def caselights(self, *values):
        if self.lights_error:
            raise self.lights_error
        self.lights.append(values)
        return list(values)


# ----- the renderer, through strict fakes of the badge drawing globals --------------------------

def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


class DrawLog:
    """Misuse of the badge drawing API seen by the fakes below."""

    def __init__(self):
        self.problems = []
        self.images = []
        self.colors = 0

    def bad(self, message):
        if len(self.problems) < 20:
            self.problems.append(message)


class FakePen:
    def __init__(self, r, g, b):
        self.rgb = (r, g, b)


class FakeShape:
    def __init__(self, log, kind, args):
        self.log = log
        self.kind = kind
        if not all(is_int(value) for value in args):
            log.bad("%s%r: non-integer argument" % (kind, args))

    def stroke(self, width):
        if not is_int(width) or width <= 0:
            self.log.bad("%s.stroke(%r)" % (self.kind, width))
        return self


class FakeBox:
    """What the rect() and vec2() globals return."""

    def __init__(self, log, kind, args):
        self.kind = kind
        self.args = args
        if not all(is_int(value) for value in args):
            log.bad("%s%r: non-integer argument" % (kind, args))


def text_width(text):
    """Rough pixel-font metrics: spaces are 2 px, everything else 7 px."""
    width = 0
    for char in text:
        width += 2 if char == " " else 7
    return width


class FakeSurface:
    """The screen or an offscreen image, checking every drawing call."""

    def __init__(self, log, width, height, is_screen=False):
        self.log = log
        self.width = width
        self.height = height
        self.is_screen = is_screen
        self.font = None
        self.antialias = None
        self.fill_rule = None
        self.calls = 0
        self.texts = []
        self.off_screen = []
        self._pen = None

    @property
    def pen(self):
        return self._pen

    @pen.setter
    def pen(self, value):
        if not isinstance(value, FakePen):
            self.log.bad("pen = %r" % (value,))
        self._pen = value

    def inked(self, what):
        self.calls += 1
        if self._pen is None:
            self.log.bad(what + " without a pen")

    def clear(self):
        self.inked("clear")

    def rectangle(self, *args):
        self.inked("rectangle")
        if len(args) != 4 or not all(is_int(value) for value in args):
            self.log.bad("rectangle%r" % (args,))
        elif args[2] <= 0 or args[3] <= 0:
            self.log.bad("empty rectangle%r" % (args,))

    def shape(self, value):
        self.inked("shape")
        if not isinstance(value, FakeShape):
            self.log.bad("shape(%r)" % (value,))

    def text(self, text, x, y):
        self.inked("text")
        if not isinstance(text, str) or not is_int(x) or not is_int(y):
            self.log.bad("text(%r, %r, %r)" % (text, x, y))
            return
        if self.font is None:
            self.log.bad("text without a font")
        words = " ".join(text.split())
        if self.is_screen and len(words) > 1:
            self.texts.append(words)
            right = x + text_width(text)
            if x < -1 or right > self.width + 1 or y < -2 or y + 12 > self.height + 2:
                self.off_screen.append((words, x, y))

    def measure_text(self, text):
        if not isinstance(text, str):
            self.log.bad("measure_text(%r)" % (text,))
        return (text_width(text), 12)

    def blit(self, source, target):
        self.calls += 1
        if not isinstance(source, FakeSurface) or source.is_screen:
            self.log.bad("blit source %r" % (source,))
        if not isinstance(target, FakeBox):
            self.log.bad("blit target %r" % (target,))


# ----- the launcher (__init__.py), run against fake runtime globals -----------------------------

class LauncherBadge(FakeDevice):
    """The runtime `badge` object as the launcher uses it."""

    def __init__(self, **kw):
        FakeDevice.__init__(self, **kw)
        self.ticks = 5000
        self.default_clear = "default-clear"
        self.modes = []
        self.down = set()
        self.holding = set()
        self.key_error = None

    def mode(self, value):
        self.modes.append(value)

    def pressed(self, button):
        if self.key_error:
            raise self.key_error
        return button in self.down

    def held(self, button):
        if self.key_error:
            raise self.key_error
        return button in self.holding


# ---------------------------------------------------------------------------
# Source scan: a CPython stand-in for the badge's MicroPython 1.29, so CI
# catches APIs and syntax that pass unittest but crash on the badge.
# ---------------------------------------------------------------------------

# Missing on the badge, or avoided here: datetime, abc and pathlib are unverified on the
# device, and re silently differs (no \b, {m,n} or .span()).
FORBIDDEN_MODULES = frozenset((
    "__future__", "abc", "bisect", "colorsys", "contextlib", "dataclasses", "datetime", "decimal",
    "enum", "fractions", "numbers", "pathlib", "re", "shutil", "statistics", "subprocess",
    "textwrap", "threading", "traceback", "typing", "typing_extensions", "urllib", "uuid", "warnings",
))
# Port modules the simulator lacks, plus hardware this app only reaches through a fallback.
GUARDED_MODULES = frozenset((
    "_thread", "aye_arr", "badgelink", "badgeware.ir", "badgeware.link", "cryptolib", "machine",
    "network", "powman", "rp2", "socket", "ssl", "urequests", "usocket", "ussl",
))
IMPORT_GUARDS = ("ImportError", "Exception", "BaseException")
MISSING_ATTRS = {
    "collections": ("Counter", "ChainMap"),
    "functools": ("lru_cache", "cache", "cmp_to_key", "total_ordering", "cached_property", "singledispatch"),
    "hashlib": ("md5", "sha1"),
    "itertools": ("product", "permutations", "combinations", "combinations_with_replacement", "groupby",
                  "zip_longest", "takewhile", "dropwhile", "compress", "pairwise", "batched", "filterfalse"),
    "json": ("JSONDecodeError",),
    "math": ("hypot", "dist", "prod", "gcd", "lcm", "isqrt", "comb", "perm", "fsum", "cbrt", "exp2"),
    "micropython": ("native", "viper"),
    "operator": ("itemgetter", "methodcaller"),
    "os": ("makedirs", "environ", "walk", "scandir", "replace", "fsync", "getenv", "urandom", "sync"),
    "os.path": ("splitext", "getsize", "getmtime", "realpath", "expanduser", "isabs"),
    "random": ("Random", "SystemRandom", "shuffle", "sample", "choices", "gauss", "triangular", "expovariate"),
    "struct": ("iter_unpack",),
    "sys": ("exc_info", "getsizeof", "setrecursionlimit"),
    "time": ("monotonic", "perf_counter", "process_time", "strftime"),
}
MISSING_NAMES = frozenset((
    "BlockingIOError", "BrokenPipeError", "BufferError", "ChildProcessError", "ConnectionAbortedError",
    "ConnectionError", "ConnectionRefusedError", "ConnectionResetError", "EnvironmentError",
    "ExceptionGroup", "FileExistsError", "FileNotFoundError", "FloatingPointError", "IOError",
    "InterruptedError", "IsADirectoryError", "ModuleNotFoundError", "NotADirectoryError",
    "PermissionError", "ProcessLookupError", "RecursionError", "ReferenceError", "TabError",
    "TimeoutError", "UnboundLocalError", "UnicodeDecodeError", "UnicodeEncodeError",
    "__builtins__", "__doc__", "__qualname__", "aiter", "anext", "ascii", "breakpoint", "exit",
    "format", "quit", "vars",
))
MISSING_METHODS = frozenset((
    "_asdict", "_replace", "bit_count", "bit_length", "capitalize", "casefold", "expandtabs",
    "format_map", "from_iterable", "groupdict", "groups", "hexdigest", "is_integer", "isalnum",
    "isascii", "isdecimal", "isidentifier", "isnumeric", "isprintable", "ljust", "move_to_end",
    "removeprefix", "removesuffix", "rjust", "span", "swapcase", "title", "zfill",
))
MISSING_OBJECT_ATTRS = frozenset(("__doc__", "__qualname__", "__traceback__", "maxlen"))
BAD_KEYWORDS = {"int": ("base",), "open": ("newline", "errors"), "print": ("flush",), "range": None,
                "round": ("ndigits",), "sum": ("start",), "zip": ("strict",)}
ALLOWED_KEYWORDS = {("collections", "deque"): (), ("collections", "namedtuple"): (),
                    ("json", "dump"): ("separators",), ("json", "dumps"): ("separators",),
                    ("json", "load"): (), ("json", "loads"): ()}


def within(name, table):
    parts = name.split(".")
    return any(".".join(parts[:end]) in table for end in range(1, len(parts) + 1))


def catches_imports(handler):
    if handler.type is None:
        return True
    kinds = handler.type.elts if isinstance(handler.type, ast.Tuple) else (handler.type,)
    return any(isinstance(kind, ast.Name) and kind.id in IMPORT_GUARDS for kind in kinds)


def bound_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((alias.asname or alias.name).split(".")[0] for alias in node.names)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            names.update(node.names)
    return names


def is_text(node):
    return isinstance(node, ast.JoinedStr) or (isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)))


def names_trail_address(node):
    return (isinstance(node, ast.Name) and node.id == "IR_ADDRESS") or (
        isinstance(node, ast.Attribute) and node.attr == "IR_ADDRESS")


def field_access(text):
    from string import Formatter
    try:
        fields = [field for _literal, field, _spec, _conversion in Formatter().parse(text) if field]
    except ValueError:
        return False
    return any("." in field or "[" in field for field in fields)


class BadgeScan(ast.NodeVisitor):
    """Flags code that CPython accepts but the badge's MicroPython 1.29 rejects."""

    def __init__(self, tree):
        self.problems = []
        self.aliases = {}
        self.bound = bound_names(tree)
        self.guarded = [False]

    def flag(self, node, message):
        self.problems.append("line %d: %s" % (getattr(node, "lineno", 0), message))

    def resolve(self, node):
        if isinstance(node, ast.Name):
            return self.aliases.get(node.id)
        if isinstance(node, ast.Attribute):
            base = self.resolve(node.value)
            if base and ":" not in base:
                return base + "." + node.attr
        return None

    def call_target(self, func):
        if isinstance(func, ast.Attribute):
            base = self.resolve(func.value)
            if base and ":" not in base:
                return base, func.attr
        elif isinstance(func, ast.Name):
            alias = self.aliases.get(func.id, "")
            if ":" in alias:
                return tuple(alias.split(":", 1))
        return None

    # Only a try body whose handlers catch ImportError guards an import, and a function
    # body runs later, outside any try around its def.
    def visit_Try(self, node):
        self.guarded.append(self.guarded[-1] or any(catches_imports(handler) for handler in node.handlers))
        for statement in node.body:
            self.visit(statement)
        self.guarded.pop()
        for part in node.handlers + node.orelse + node.finalbody:
            self.visit(part)

    def visit_TryStar(self, node):
        self.flag(node, "except* is a SyntaxError on the badge")
        self.visit_Try(node)

    def visit_FunctionDef(self, node):
        if node.args.posonlyargs:
            self.flag(node, "positional-only parameters are a SyntaxError on the badge")
        if getattr(node, "type_params", None):
            self.flag(node, "type parameters are a SyntaxError on the badge")
        if node.name == "__init_subclass__":
            self.flag(node, "__init_subclass__ is never called on the badge")
        for decorator in node.decorator_list:
            self.check_decorator(decorator)
        self.guarded.append(False)
        self.generic_visit(node)
        self.guarded.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node):
        if node.args.posonlyargs:
            self.flag(node, "positional-only parameters are a SyntaxError on the badge")
        self.guarded.append(False)
        self.generic_visit(node)
        self.guarded.pop()

    def visit_ClassDef(self, node):
        if node.keywords:
            self.flag(node, "class keywords such as metaclass= raise TypeError on the badge")
        if getattr(node, "type_params", None):
            self.flag(node, "type parameters are a SyntaxError on the badge")
        for decorator in node.decorator_list:
            self.check_decorator(decorator)
        self.generic_visit(node)

    def check_decorator(self, decorator):
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        while isinstance(target, ast.Attribute):
            target = target.value
        if not isinstance(target, ast.Name):
            self.flag(decorator, "relaxed decorator expressions are a SyntaxError on the badge")

    def visit_Match(self, node):
        self.flag(node, "match statements are a SyntaxError on the badge")
        self.generic_visit(node)

    def visit_TypeAlias(self, node):
        self.flag(node, "type aliases are a SyntaxError on the badge")
        self.generic_visit(node)

    def check_module(self, name, node):
        if name == "badge" or name.startswith("badge."):
            self.flag(node, "imports badge, which is a runtime global")
        elif within(name, FORBIDDEN_MODULES):
            self.flag(node, "imports %s, which the badge lacks or this app avoids" % name)
        elif within(name, GUARDED_MODULES) and not self.guarded[-1]:
            self.flag(node, "imports %s without a try/except ImportError fallback" % name)

    def visit_Import(self, node):
        for alias in node.names:
            self.check_module(alias.name, node)
            if alias.asname:
                self.aliases[alias.asname] = alias.name
            else:
                top = alias.name.split(".")[0]
                self.aliases[top] = top

    def visit_ImportFrom(self, node):
        base = node.module or ""
        count = len(self.problems)
        self.check_module(base, node)
        for alias in node.names:
            if len(self.problems) == count:
                self.check_module(base + "." + alias.name, node)
            if alias.name in MISSING_ATTRS.get(base, ()):
                self.flag(node, "%s.%s is missing on the badge" % (base, alias.name))
            local = alias.asname or alias.name
            self.aliases[local] = "os.path" if (base, alias.name) == ("os", "path") else base + ":" + alias.name

    def visit_Attribute(self, node):
        base = self.resolve(node.value)
        if base and ":" not in base and node.attr in MISSING_ATTRS.get(base, ()):
            self.flag(node, "%s.%s is missing on the badge" % (base, node.attr))
        if node.attr in MISSING_OBJECT_ATTRS or node.attr.startswith("tm_"):
            self.flag(node, ".%s is missing on the badge" % node.attr)
        if isinstance(node.value, ast.Name) and (node.value.id, node.attr) == ("str", "maketrans"):
            self.flag(node, "str.maketrans is missing on the badge")
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and node.id not in self.bound and (
                node.id in MISSING_NAMES or node.id.endswith("Warning")):
            self.flag(node, "%s is undefined on the badge" % node.id)

    def visit_Call(self, node):
        func = node.func
        keywords = [keyword.arg for keyword in node.keywords if keyword.arg]
        if isinstance(func, ast.Name) and func.id not in self.bound:
            self.check_builtin(func.id, node, keywords)
        target = self.call_target(func)
        if target:
            allowed = ALLOWED_KEYWORDS.get(target)
            for key in keywords if allowed is not None else ():
                if key not in allowed:
                    self.flag(node, "%s.%s(%s=) raises TypeError on the badge" % (target + (key,)))
            if target == ("collections", "deque") and len(node.args) != 2:
                self.flag(node, "deque() needs (iterable, maxlen) positionally on the badge")
            if target == ("random", "seed") and node.args and is_text(node.args[0]):
                self.flag(node, "random.seed() takes an int on the badge")
        if isinstance(func, ast.Attribute):
            self.check_method(func, node, keywords)
        self.generic_visit(node)

    def check_builtin(self, name, node, keywords):
        bad = BAD_KEYWORDS.get(name, ())
        for key in keywords:
            if bad is None or key in bad:
                self.flag(node, "%s(%s=) raises TypeError on the badge" % (name, key))
        if name == "hash":
            self.flag(node, "hash() differs between CPython and the badge")
        elif name == "iter" and len(node.args) == 2:
            self.flag(node, "iter(callable, sentinel) raises TypeError on the badge")
        elif name in ("isinstance", "issubclass") and len(node.args) > 1 and isinstance(
                node.args[1], ast.BinOp) and isinstance(node.args[1].op, ast.BitOr):
            self.flag(node, "%s() with A | B raises TypeError on the badge" % name)

    def check_method(self, func, node, keywords):
        name, args = func.attr, node.args
        if name in MISSING_METHODS:
            self.flag(node, ".%s() is missing on the badge" % name)
        elif name == "group" and len(args) != 1:
            self.flag(node, ".group() needs exactly one index on the badge")
        elif name == "center" and len(args) > 1:
            self.flag(node, ".center() takes no fill character on the badge")
        elif name in ("split", "rsplit") and keywords:
            self.flag(node, ".%s() takes no keywords on the badge" % name)
        elif name == "rsplit" and args and isinstance(args[0], ast.Constant) and args[0].value is None:
            self.flag(node, ".rsplit(None, n) is not implemented on the badge")
        elif name == "decode" and "errors" in keywords:
            self.flag(node, ".decode(errors=) raises TypeError on the badge")
        elif name == "from_bytes" and "signed" in keywords:
            self.flag(node, ".from_bytes(signed=) raises TypeError on the badge")
        elif name == "union" and len(args) > 1:
            self.flag(node, ".union() takes one argument on the badge")
        elif name == "translate" and len(args) == 1 and isinstance(args[0], (ast.Dict, ast.DictComp)):
            self.flag(node, "str.translate() with a table is missing on the badge")
        elif name == "format" and isinstance(func.value, ast.Constant) and isinstance(
                func.value.value, str) and field_access(func.value.value):
            self.flag(node, "format fields cannot use . or [] access on the badge")
        elif name == "send_addr_cmd" and not (args and names_trail_address(args[0])):
            self.flag(node, "beams must use the trail's IR_ADDRESS (0x54)")

    def check_display(self, node):
        if not isinstance(getattr(node, "ctx", None), (ast.Store, ast.Del)) and any(
                isinstance(item, ast.Starred) for item in node.elts):
            self.flag(node, "starred items in a display are a SyntaxError on the badge")
        self.generic_visit(node)

    visit_List = visit_Tuple = visit_Set = check_display

    def visit_Dict(self, node):
        if None in node.keys:
            self.flag(node, "{**d} displays are a SyntaxError on the badge")
        self.generic_visit(node)

    def visit_Subscript(self, node):
        if isinstance(node.slice, ast.Slice) and node.slice.step is not None:
            self.flag(node, "step slices fail on str, tuple and bytes on the badge")
        self.generic_visit(node)


def token_problems(text):
    problems = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError):
        return ["the tokenizer failed"]
    for index, token in enumerate(tokens):
        line = token.start[0]
        if token.type == tokenize.NUMBER and token.string.lower() == "0x45":
            problems.append("line %d: 0x45 is the menu's event-beacon address" % line)
        elif token.type == tokenize.STRING and "\\N{" in token.string and "r" not in re.match(
                r"[A-Za-z]*", token.string).group(0).lower():
            problems.append("line %d: \\N{} escapes are not implemented on the badge" % line)
        elif token.type == tokenize.NAME and token.string == "with" and tokens[index + 1].string == "(":
            depth = 0
            for later in tokens[index + 1:]:
                if later.type == tokenize.OP and later.string in ("(", "[", "{"):
                    depth += 1
                elif later.type == tokenize.OP and later.string in (")", "]", "}"):
                    depth -= 1
                    if not depth:
                        break
                elif depth == 1 and later.type == tokenize.NAME and later.string == "as":
                    problems.append("line %d: parenthesized with ... as is a SyntaxError on the badge" % line)
                    break
    return problems


def scan_source(text, name="snippet"):
    try:
        tree = ast.parse(text, filename=name)
    except SyntaxError as error:
        return ["line %s: CPython SyntaxError %s" % (error.lineno, error.msg)]
    scan = BadgeScan(tree)
    scan.visit(tree)
    return scan.problems + token_problems(text)


BAD_SNIPPETS = (
    ("runtime global", "import badge"),
    ("lacks", "import textwrap"),
    ("lacks", "from typing import List"),
    ("lacks", "from __future__ import annotations"),
    ("lacks", "import datetime"),
    ("lacks", "import re"),
    ("lacks", "import urllib.request"),
    ("fallback", "from aye_arr.nec import NECSender"),
    ("fallback", "from badgeware import ir"),
    ("fallback", "import machine"),
    ("fallback", "def listen():\n    from badgeware.ir import ir\n    return ir\n"),
    ("fallback", "try:\n    import powman\nexcept ValueError:\n    powman = None\n"),
    ("fallback", "try:\n    pass\nexcept ImportError:\n    import network\n"),
    ("fallback", "try:\n    def connect():\n        import socket\nexcept ImportError:\n    pass\n"),
    ("random.shuffle", "import random\nrandom.shuffle(xs)"),
    ("random.choices", "from random import choices"),
    ("math.hypot", "import math as m\nd = m.hypot(1, 2)"),
    ("os.path.splitext", "import os\nstem = os.path.splitext(p)"),
    ("os.path.getsize", "from os import path\nn = path.getsize(p)"),
    ("time.monotonic", "import time\nnow = time.monotonic()"),
    ("collections.Counter", "from collections import Counter"),
    ("json.JSONDecodeError", "import json\ntry:\n    json.loads(s)\nexcept json.JSONDecodeError:\n    pass\n"),
    ("hashlib.md5", "import hashlib\ndigest = hashlib.md5(b'x')"),
    ("micropython.native", "import micropython\n@micropython.native\ndef f():\n    pass\n"),
    ("FileNotFoundError", "try:\n    open(p)\nexcept FileNotFoundError:\n    pass\n"),
    ("TimeoutError", "try:\n    pass\nexcept (OSError, TimeoutError):\n    pass\n"),
    ("UnicodeDecodeError", "error = UnicodeDecodeError"),
    ("UserWarning", "raise UserWarning('x')"),
    ("vars", "print(vars(x))"),
    ("format", "y = format(1, 'x')"),
    ("__builtins__", "b = __builtins__"),
    ("__doc__", "d = x.__doc__"),
    ("__qualname__", "q = f.__qualname__"),
    ("__traceback__", "t = e.__traceback__"),
    ("tm_year", "import time\nyear = time.localtime().tm_year"),
    ("maxlen", "n = buf.maxlen"),
    ("__init_subclass__", "class A:\n    def __init_subclass__(cls):\n        pass\n"),
    (".ljust", "s.ljust(8)"),
    (".zfill", "s.zfill(3)"),
    (".title", "s.title()"),
    (".isalnum", "s.isalnum()"),
    (".bit_length", "n.bit_length()"),
    (".hexdigest", "h.hexdigest()"),
    ("._replace", "p._replace(x=1)"),
    (".span", "m.span()"),
    (".groups", "m.groups()"),
    (".group", "m.group()"),
    (".group", "m.group(1, 2)"),
    (".center", "s.center(9, '*')"),
    (".split", "s.split(sep=' ')"),
    (".rsplit", "s.rsplit(None, 1)"),
    (".decode", "b.decode('utf-8', errors='ignore')"),
    (".from_bytes", "int.from_bytes(b, 'big', signed=True)"),
    (".union", "a.union(b, c)"),
    ("translate", "s.translate({1: 2})"),
    ("maketrans", "table = str.maketrans('a', 'b')"),
    ("format fields", "'{0.x}'.format(p)"),
    ("format fields", "'{a[0]}'.format(a=xs)"),
    ("hash()", "h = hash('mona')"),
    ("A | B", "isinstance(x, int | float)"),
    ("iter(", "it = iter(f, None)"),
    ("print(flush=", "print('x', flush=True)"),
    ("int(base=", "n = int('7', base=8)"),
    ("zip(strict=", "pairs = zip(a, b, strict=True)"),
    ("round(ndigits=", "r = round(x, ndigits=2)"),
    ("range(stop=", "r = range(stop=3)"),
    ("sum(start=", "total = sum(xs, start=1)"),
    ("open(newline=", "fh = open(p, newline='')"),
    ("json.dumps(indent=", "import json\ntext = json.dumps(d, indent=2)"),
    ("json.loads(strict=", "import json\ndata = json.loads(s, strict=False)"),
    ("deque()", "from collections import deque\nq = deque()"),
    ("deque(maxlen=", "from collections import deque\nq = deque((), maxlen=4)"),
    ("namedtuple(defaults=", "from collections import namedtuple\nP = namedtuple('P', 'x', defaults=(0,))"),
    ("random.seed", "import random\nrandom.seed('mona')"),
    ("IR_ADDRESS", "tx.send_addr_cmd(0x54, 1)"),
    ("IR_ADDRESS", "tx.send_addr_cmd(ADDRESS, 1)"),
    ("0x45", "beacon = 0x45"),
    ("SyntaxError", "with (open(a) as f, open(b) as g):\n    pass\n"),
    ("\\N{}", "s = '\\N{BULLET}'"),
    ("SyntaxError", "xs = [*a, *b]"),
    ("SyntaxError", "t = (*a, b)"),
    ("SyntaxError", "def f():\n    return *a, b\n"),
    ("SyntaxError", "s = {*a}"),
    ("SyntaxError", "d = {**a, 'k': 1}"),
    ("step slices", "s = name[::-1]"),
    ("step slices", "del xs[::2]"),
    ("metaclass", "class A(B, metaclass=M):\n    pass\n"),
    ("SyntaxError", "def f(a, /, b):\n    pass\n"),
    ("SyntaxError", "@buttons[0].handler\ndef f():\n    pass\n"),
    ("SyntaxError", "match x:\n    case 1:\n        pass\n"),
    ("SyntaxError", "try:\n    pass\nexcept* ValueError:\n    pass\n"),
    ("SyntaxError", "type Point = tuple\n"),
    ("SyntaxError", "def first[T](xs):\n    return xs[0]\n"),
    ("SyntaxError", "if True:\n  x = ("),
)

CLEAN_SNIPPETS = (
    "try:\n    from aye_arr.nec import NECSender\nexcept ImportError:\n    NECSender = None\n",
    "def listen():\n    try:\n        from badgeware.ir import ir\n    except Exception:\n        return None\n    return ir\n",
    "try:\n    import machine\nexcept (ValueError, ImportError):\n    machine = None\n",
    "try:\n    import network\nexcept:\n    network = None\n",
    "from badgeware import State",
    "import math\nd = math.sqrt(x * x + y * y)",
    "import os\nok = os.path.exists(p)",
    "import time\nnow = time.ticks_ms()",
    "a, *rest = xs",
    "[a, *rest] = xs",
    "for a, *rest in rows:\n    pass\n",
    "f(*args, **kw)",
    "head, tail = s.split(' ', 1)",
    "s.center(20)",
    "m.group(1)",
    "from collections import deque\nq = deque((), 8)",
    "try:\n    pass\nexcept (ValueError, OSError) as error:\n    pass\n",
    "xs.sort(key=lambda x: x[0])",
    "import trail_logic as tl\ntx.send_addr_cmd(tl.IR_ADDRESS, 1)",
    "tx.send_addr_cmd(IR_ADDRESS, 7)",
    "part = xs[1:3]",
    "y = 69",
    "sender.start()",
    "import json\ntext = json.dumps(d, separators=(',', ':'))",
    "def f(format):\n    return format\n",
    "with open(p) as fh:\n    pass\n",
    "with (lock):\n    pass\n",
    "s = r'\\N{x}'",
    "class A:\n    BUTTON_CODES = {}\n",
    "matrix.rotate(0.5)",
    "text = '{0} {1}'.format(a, b)",
    "d = dict(a)\nd.update(b)",
)


class SourceScanTests(unittest.TestCase):
    """CI runs CPython, so these scans stand in for the badge's MicroPython."""

    def test_the_scan_catches_badge_incompatible_code(self):
        for keyword, snippet in BAD_SNIPPETS:
            with self.subTest(snippet=snippet):
                problems = scan_source(snippet)
                self.assertTrue(any(keyword in problem for problem in problems), problems)

    def test_the_scan_accepts_badge_safe_code(self):
        for snippet in CLEAN_SNIPPETS:
            with self.subTest(snippet=snippet):
                self.assertEqual(scan_source(snippet), [])


class PackagingTests(unittest.TestCase):
    """The folder, icon and README that the menu, CI and badgerfactory rely on."""

    def test_the_icon_is_a_square_png_of_at_least_24_pixels(self):
        data = (APP / "icon.png").read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(data[12:16], b"IHDR")
        width, height = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
        self.assertEqual(width, height)
        self.assertGreaterEqual(width, 24)

    def test_the_readme_passes_the_repository_validator(self):
        path = ROOT / ".github" / "scripts" / "validate_app_readmes.py"
        spec = importlib.util.spec_from_file_location("octocat_trail_readme_validator", path)
        validator = importlib.util.module_from_spec(spec)
        with mock.patch.object(sys, "dont_write_bytecode", True):
            spec.loader.exec_module(validator)
        self.assertIsNone(validator.check_app(APP))
        sentence = validator.first_sentence(validator.first_paragraph(APP / "README.md"))
        self.assertTrue(sentence.startswith("Lead the Studio party"), sentence)


if __name__ == "__main__":
    unittest.main()
