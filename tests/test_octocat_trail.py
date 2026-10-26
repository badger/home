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
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "badge" / "apps" / "octocat_trail"
MODULES = ("trail_map", "trail_logic", "trail_art", "trail_game", "trail_hw", "trail_draw")
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
ta = _APP["trail_art"]
tg = _APP["trail_game"]
hw = _APP["trail_hw"]
td = _APP["trail_draw"]

BOTH_RIVERS = tm.deployed_bit(tm.MERGE) | tm.deployed_bit(tm.DNS)


def reachable_stops(deployed):
    dist = tm.distances(tm.START[0], tm.START[1], deployed)
    found = []
    for index in range(len(tm.STOPS)):
        stop = tm.STOPS[index]
        if dist[stop[4] * tm.W + stop[3]] != tm.UNREACHED:
            found.append(index)
    return found


def sprite_frames(value):
    """Flatten a sprite (rows of strings) or a tuple of frames into frames."""
    if isinstance(value, tuple) and value and isinstance(value[0], str):
        return [value]
    frames = []
    for item in value:
        frames.extend(sprite_frames(item))
    return frames


class LoaderTests(unittest.TestCase):
    def test_modules_load_under_unique_names_without_leaking(self):
        for name in MODULES:
            self.assertEqual(_APP[name].__name__, "octocat_trail_" + name)
            self.assertIsNot(sys.modules.get(name), _APP[name])
            self.assertIsNot(sys.modules.get("octocat_trail_" + name), _APP[name])

    def test_app_modules_share_one_set_of_dependencies(self):
        self.assertIs(tl.tm, tm)
        self.assertIs(tg.tl, tl)
        self.assertIs(tg.tm, tm)
        self.assertIs(hw.tl, tl)
        self.assertIs(td.ta, ta)
        self.assertIs(td.tl, tl)
        self.assertIs(td.tm, tm)

    def test_descriptor_falls_back_without_aye_arr(self):
        self.assertIs(hw._Descriptor, object)
        beam = hw.make_descriptor()
        self.assertEqual(beam.ADDRESS, 0x54)
        self.assertIsNone(beam.on_any)
        self.assertIsNone(beam.on_known)


class MapTests(unittest.TestCase):
    def test_grid_size_and_runs_tile_every_row(self):
        self.assertEqual(len(tm.grid()), tm.W * tm.H)
        rows = tm.runs()
        self.assertIs(rows, tm.runs())
        self.assertEqual(len(rows), tm.H)
        for y in range(tm.H):
            x = 0
            for start, length, code in rows[y]:
                self.assertEqual(start, x)
                self.assertGreater(length, 0)
                for i in range(length):
                    self.assertEqual(tm.terrain(start + i, y), code)
                x += length
            self.assertEqual(x, tm.W)

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

    def test_details_mark_water_and_grass(self):
        rows = tm.details()
        self.assertIs(rows, tm.details())
        self.assertEqual(len(rows), tm.H)
        kinds = set()
        for y in range(tm.H):
            for x, kind in rows[y]:
                kinds.add(kind)
                self.assertEqual(tm.terrain(x, y), tm.WATER if kind == 0 else tm.GRASS)
        self.assertEqual(kinds, {0, 1})

    def test_camera_clamps_to_the_world(self):
        self.assertEqual(tm.camera(0, 0, 320, 240), (0, 0))
        self.assertEqual(tm.camera(400, 500, 320, 240), (240, 380))
        self.assertEqual(tm.camera(10 ** 6, 10 ** 6, 320, 240), (tm.W * tm.TILE - 320, tm.H * tm.TILE - 240))

    def test_labels_name_the_venue(self):
        texts = [label[0] for label in tm.LABELS]
        self.assertIn("GITHUB UNIVERSE", texts)
        self.assertIn("SAN FRANCISCO BAY", texts)
        for text, x, y, vertical in tm.LABELS:
            self.assertEqual(text, text.upper())
            self.assertTrue(0 <= x < tm.W * tm.TILE and 0 <= y < tm.H * tm.TILE)
            self.assertIn(vertical, (0, 1))


class ArtTests(unittest.TestCase):
    SPRITES = ("DUCK", "WAGON", "WHEEL", "ROPE", "MONA", "BUG", "SLOP", "STAMP", "TREE", "FLAG", "FIRE")

    def test_palette_matches_letters(self):
        self.assertEqual(len(ta.PALETTE), 18)
        self.assertEqual(len(ta.LETTERS), len(ta.PALETTE))
        self.assertEqual(len(set(ta.LETTERS)), len(ta.LETTERS))
        self.assertNotIn(".", ta.LETTERS)
        for rgb in ta.PALETTE:
            self.assertEqual(len(rgb), 3)
            for channel in rgb:
                self.assertTrue(isinstance(channel, int) and 0 <= channel <= 255)
        self.assertEqual(ta.PALETTE[ta.BLACK], (0, 0, 0))
        self.assertEqual(ta.PALETTE[ta.WHITE], (255, 255, 255))

    def test_green_monitor_palette(self):
        self.assertIs(ta.palette(), ta.PALETTE)
        self.assertIs(ta.palette(False), ta.PALETTE)
        self.assertEqual(ta.green_rgb((0, 0, 0)), (0, 0, 0))
        self.assertEqual(ta.green_rgb((255, 255, 255)), (42, 255, 63))
        green = ta.palette(True)
        self.assertEqual(len(green), len(ta.PALETTE))
        for rgb in green[1:]:
            self.assertGreaterEqual(rgb[1], 60)
            self.assertGreater(rgb[1], rgb[0])
            self.assertGreater(rgb[1], rgb[2])

    def test_every_sprite_compiles_with_palette_letters(self):
        for name in self.SPRITES:
            frames = sprite_frames(getattr(ta, name))
            self.assertTrue(frames, name)
            for rows in frames:
                for row in rows:
                    for ch in row:
                        self.assertTrue(ch == "." or ch in ta.LETTERS, (name, ch))
                width, height, runs = ta.compile_rows(rows)
                self.assertTrue(0 < width < 64 and 0 < height < 64, name)
                self.assertTrue(runs, name)
                keys = [run[3] * 4096 + run[1] * 64 + run[0] for run in runs]
                self.assertEqual(keys, sorted(keys))
                self.assertEqual(len(set(keys)), len(keys))
                for x, y, n, slot in runs:
                    self.assertTrue(0 <= x and x + n <= width and 0 <= y < height)
                    self.assertEqual(rows[y][x:x + n], ta.LETTERS[slot] * n)

    def test_compile_rows_example_and_bad_letter(self):
        self.assertEqual(ta.compile_rows(("KK.W",)), (4, 1, ((0, 0, 2, 0), (3, 0, 1, 1))))
        with self.assertRaises(ValueError):
            ta.compile_rows(("KZ",))

    def test_mirror_and_sprite_cache(self):
        self.assertEqual(ta.mirror_runs(4, ((0, 0, 2, 0), (3, 0, 1, 1))), ((2, 0, 2, 0), (0, 0, 1, 1)))
        rows = ta.MONA[0]
        plain = ta.sprite(rows)
        mirrored = ta.sprite(rows, True)
        self.assertIs(plain, ta.sprite(rows))
        self.assertIs(mirrored, ta.sprite(rows, True))
        self.assertEqual(plain[:2], mirrored[:2])
        self.assertEqual(sorted(ta.mirror_runs(plain[0], mirrored[2])), sorted(plain[2]))
        self.assertEqual(ta.size(rows), plain[:2])

    def test_wagon_token_fits_its_box(self):
        self.assertEqual(ta.token_parts(2), ta.token_parts(0))
        for frame in (0, 1):
            parts = ta.token_parts(frame)
            self.assertEqual(len(parts), 5)
            self.assertIs(parts[0][0], ta.WAGON)
            self.assertIs(parts[-1][0], ta.DUCK[frame])
            for rows, x, y in parts:
                width, height = ta.size(rows)
                self.assertTrue(x >= 0 and y >= 0)
                self.assertLessEqual(x + width, ta.TOKEN_W)
                self.assertLessEqual(y + height, ta.TOKEN_H)


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
    def test_spec_names(self):
        self.assertEqual(tl.PARTY, ("Markus", "Mona", "Cameron", "Hubot", "Tufty"))
        self.assertEqual(tl.TRAIL_STEPS, 2000)
        self.assertEqual([tl.role_label(i) for i in range(3)], [
            "Creative Director @wmarkus", "Staff Rustacean @mona", "ATC Control Lead @kdaigle"])
        self.assertEqual([label for _key, label in tl.SUPPLIES],
                         ["Copilot Credits", "Cold Brew Kegs", "LGTM Stamps", "Hotfix Patches"])
        self.assertIn("node_modules dysentery", tl.CAUSES)
        self.assertIn("AI Slop Fever", tl.CAUSES)
        self.assertEqual(tl.CAUSES[tl.CAUSE_FORCE_PUSH], "a Friday force-push")
        self.assertEqual([tm.STOPS[spec[0]][0] for spec in tl.RIVERS],
                         ["Merge Conflict River", "DNS Propagation Rapids"])
        self.assertEqual(tl.IR_ADDRESS, 0x54)

    def test_tables_are_consistent(self):
        self.assertEqual(len(tl.STOP_BLURBS), len(tm.STOPS))
        sights = [i for i in range(len(tm.STOPS)) if tm.STOPS[i][2] == "sight"]
        self.assertEqual([entry[0] for entry in tl.SIGHTS], sights)
        keys = [key for key, _label in tl.SUPPLIES]
        for _stop, key, amount, line in tl.SIGHTS:
            self.assertTrue(key == "health" or key in keys)
            self.assertTrue(amount > 0 and line)
        for stop, percent in tl.STORE_MARKUP:
            self.assertIn(tm.STOPS[stop][2], ("store", "heal"))
            self.assertGreaterEqual(percent, 100)
        self.assertEqual(tm.STOPS[tl.FIREHOUSE][2], "heal")
        self.assertEqual(tm.STOPS[tl.MEADOW][2], "meadow")
        for cause, low, high, drain in tl.ILLNESSES:
            self.assertTrue(0 <= cause < len(tl.CAUSES) and 0 < low <= high and drain > 0)
        self.assertEqual(sum(month[1] for month in tl.MONTHS), 365)
        self.assertEqual(len(tl.RIVER_OPTIONS), 4)

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


class patched_modules:
    """Point a few sys.modules keys at fakes, restoring only those keys."""

    def __init__(self, mapping):
        self.mapping = mapping
        self.saved = {}

    def __enter__(self):
        for name, module in self.mapping.items():
            self.saved[name] = sys.modules.get(name, _MISSING)
            sys.modules[name] = module
        return self

    def __exit__(self, *exc):
        for name, old in self.saved.items():
            if old is _MISSING:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old
        return False


def module(name, **attrs):
    made = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(made, key, value)
    return made


def fake_ir(fail_slots=(), bind=None, bind_error=False, send_error=False, close_error=False):
    """Fake aye_arr.nec and badgeware.ir modules plus a log of what they saw."""
    log = {"made": [], "started": [], "sent": [], "stopped": 0, "bound": [], "closed": 0}

    class NECSender:
        def __init__(self, pin, pio, sm):
            log["made"].append((pin, pio, sm))
            if (pio, sm) in fail_slots:
                raise OSError("state machine busy")
            self.slot = (pio, sm)

        def start(self):
            log["started"].append(self.slot)

        def send_addr_cmd(self, address, command):
            if send_error:
                raise OSError("tx")
            log["sent"].append((address, command))

        def stop(self):
            log["stopped"] += 1
            if close_error:
                raise OSError("stop")

    class Ir:
        def bind(self, descriptor):
            if bind_error:
                raise RuntimeError("bind")
            log["bound"].append(descriptor)
            return bind if bind is not None else descriptor

        def close(self):
            log["closed"] += 1
            if close_error:
                raise OSError("close")

    modules = {"aye_arr": module("aye_arr"), "aye_arr.nec": module("aye_arr.nec", NECSender=NECSender),
               "badgeware": module("badgeware"), "badgeware.ir": module("badgeware.ir", ir=Ir())}
    return modules, log


NO_IR = {"aye_arr": None, "aye_arr.nec": None, "badgeware.ir": None}


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


def fake_machine(reading=1234, error=None):
    pins = []

    class ADC:
        def __init__(self, pin):
            pins.append(pin)
            if error:
                raise error

        def read_u16(self):
            return reading

    return module("machine", ADC=ADC), pins


class SensorTests(unittest.TestCase):
    def test_imu(self):
        sensors = hw.Sensors(FakeDevice(imu=(1, -16384, 3, 0, 0, 0)))
        self.assertEqual(sensors.imu(), (1.0, -16384.0, 3.0))
        broken = hw.Sensors(FakeDevice(imu=OSError("no imu")))
        self.assertIsNone(broken.imu())
        self.assertFalse(broken.imu_ok)
        broken.device.imu_value = (0, 1, 2)
        self.assertIsNone(broken.imu())

    def test_light_prefers_the_badge_api(self):
        machine, pins = fake_machine()
        with patched_modules({"machine": machine}):
            sensors = hw.Sensors(FakeDevice(light=40000))
            self.assertEqual((sensors.light(), sensors.light_source), (40000, "badge"))
            sensors.device.light_value = RuntimeError("unsupported")
            self.assertIsNone(sensors.light())
        self.assertEqual(pins, [])

    def test_light_falls_back_to_adc43(self):
        machine, pins = fake_machine(reading=777)
        with patched_modules({"machine": machine}):
            sensors = hw.Sensors(FakeDevice(light=RuntimeError("unsupported")))
            self.assertEqual((sensors.light(), sensors.light_source), (777, "adc"))
            sensors.device.light_value = 5
            self.assertEqual(sensors.light(), 777)
        self.assertEqual(pins, [hw.LIGHT_ADC_PIN])

    def test_no_light_sensor_at_all(self):
        machine, _pins = fake_machine(error=ValueError("bad pin"))
        with patched_modules({"machine": machine}):
            sensors = hw.Sensors(FakeDevice(light=RuntimeError("unsupported")))
            self.assertIsNone(sensors.light())
            self.assertTrue(sensors.light_failed)
            sensors.device.light_value = 9
            self.assertIsNone(sensors.light())


class CaseLightTests(unittest.TestCase):
    def test_quantize(self):
        self.assertEqual([hw.quantize(v) for v in (-1, 0, 0.51, 0.53, 0.26, 2)], [0.0, 0.0, 0.5, 0.55, 0.25, 1.0])

    def test_writes_only_changes(self):
        device = FakeDevice()
        lights = hw.CaseLights(device)
        lights.set(0.5)
        lights.set(0.51)
        lights.set(2, -1, 0.25, 0.26)
        self.assertEqual(device.lights, [(0.5, 0.5, 0.5, 0.5), (1.0, 0.0, 0.25, 0.25)])
        lights.off()
        self.assertEqual(device.lights[-1], (0,))
        lights.set(1.0, 0.0, 0.25, 0.25)
        self.assertEqual(len(device.lights), 4)

    def test_failures_disable_lights(self):
        device = FakeDevice(lights_error=OSError("no lights"))
        lights = hw.CaseLights(device)
        lights.set(1)
        self.assertFalse(lights.ok)
        device.lights_error = None
        lights.set(0.5)
        self.assertEqual(device.lights, [])
        device.lights_error = OSError("still none")
        lights.off()


class IrLinkTests(unittest.TestCase):
    def test_sender_slots_skip_the_receivers_state_machine(self):
        self.assertNotIn((0, 0), hw.SENDER_SLOTS)
        modules, log = fake_ir(fail_slots=hw.SENDER_SLOTS)
        with patched_modules(modules):
            self.assertIsNone(hw.open_sender())
        self.assertEqual(log["made"], [(hw.IR_TX_PIN, pio, sm) for pio, sm in hw.SENDER_SLOTS])
        with patched_modules(NO_IR):
            self.assertIsNone(hw.open_sender())

    def test_offline_link_paces_a_simulated_beam(self):
        with patched_modules(NO_IR):
            link = hw.IrLink(0x2A).open()
        self.assertEqual((link.status(), link.can_send(), link.progress()), ("IR off", False, 1.0))
        self.assertEqual(hw.IrLink(0xFF).nonce, 0x7F)
        packet = tl.encode_packet(tl.KIND_VICTORY, 0x2A, 5, 1, 2, 3)
        self.assertTrue(link.beam(packet, repeats=2))
        self.assertEqual((link.sending(), link.total), (True, 18))
        link.update(1000)
        link.update(1050)
        self.assertEqual(len(link.queue), 17)
        link.update(1000 + hw.FRAME_MS)
        self.assertEqual(len(link.queue), 16)
        self.assertAlmostEqual(link.progress(), 2 / 18.0)
        now = 1000 + hw.FRAME_MS
        while link.sending():
            now += hw.FRAME_MS
            link.update(now)
        self.assertEqual((link.progress(), link.frames_sent), (1.0, 0))
        self.assertEqual(link.mute_until, now + hw.FRAME_MS + hw.MUTE_MS)
        link.update(now + 5000)
        link.beam([1, 2], repeats=1)
        link.beam([3], repeats=2)
        self.assertEqual((link.total, link.queue), (4, [1, 2, 3, 3]))

    def test_transmitter_sends_one_frame_per_update(self):
        modules, log = fake_ir(fail_slots=((0, 1),))
        with patched_modules(modules):
            link = hw.IrLink(0x2A).open()
        self.assertEqual(log["made"], [(16, 0, 1), (16, 1, 0)])
        self.assertEqual((log["started"], link.status()), ([(1, 0)], "IR ready"))
        packet = tl.encode_packet(tl.KIND_TOMBSTONE, 0x2A, 300, 1, 2, 0)
        link.beam(packet)
        self.assertEqual(link.total, tl.PACKET_LEN * tl.BEAM_REPEATS)
        link.update(500)
        link.update(500)
        self.assertEqual(log["sent"], [(0x54, packet[0]), (0x54, packet[1])])
        self.assertEqual((link.frames_sent, link.mute_until), (2, 500 + hw.FRAME_MS + hw.MUTE_MS))
        for tick in range(40):
            link.update(600 + tick)
        self.assertEqual([command for _address, command in log["sent"]], packet * tl.BEAM_REPEATS)
        self.assertEqual({address for address, _command in log["sent"]}, {0x54})

    def test_send_failure_falls_back_to_pacing(self):
        modules, log = fake_ir(send_error=True)
        with patched_modules(modules):
            link = hw.IrLink(1).open()
        self.assertEqual(log["started"], [(0, 1)])
        link.beam([1, 2, 3], repeats=1)
        link.update(0)
        self.assertIsNone(link.tx)
        self.assertEqual((link.frames_sent, len(link.queue), link.status()), (0, 2, "IR listening"))
        link.update(10)
        self.assertEqual(len(link.queue), 2)
        link.update(hw.FRAME_MS)
        self.assertEqual(len(link.queue), 1)

    def test_listen_binds_handlers_and_close_releases(self):
        modules, log = fake_ir()
        with patched_modules(modules):
            link = hw.IrLink(0x2A).open()
            descriptor = log["bound"][0]
            self.assertIs(link.binding, descriptor)
            self.assertEqual((descriptor.NAME, descriptor.ADDRESS, descriptor.BUTTON_CODES), ("OctocatTrail", 0x54, {}))
            descriptor.on_any(0x1A5)
            descriptor.on_known("ANY")
            self.assertEqual(link.pending, [0xA5])
            link.beam([1], repeats=1)
            link.close()
        self.assertEqual((log["stopped"], log["closed"]), (1, 1))
        self.assertEqual((link.tx, link.binding, link.listening, link.queue), (None, None, False, []))
        other = types.SimpleNamespace()
        modules, log = fake_ir(bind=other)
        with patched_modules(modules):
            link = hw.IrLink(3).open()
        self.assertIs(link.binding, other)
        self.assertEqual((other.on_any, other.on_known), (link.on_byte, link.on_known))

    def test_bind_and_close_failures_are_harmless(self):
        modules, log = fake_ir(bind_error=True)
        with patched_modules(modules):
            link = hw.IrLink(3).open()
        self.assertEqual((link.listening, link.status()), (False, "IR send only"))
        modules, log = fake_ir(close_error=True)
        with patched_modules(modules):
            link = hw.IrLink(3).open()
            link.close()
        self.assertEqual((log["stopped"], log["closed"], link.listening, link.tx), (1, 1, False, None))

    def test_process_ignores_echoes_and_mutes_while_sending(self):
        with patched_modules(NO_IR):
            link = hw.IrLink(0x2A).open()
        other = tl.encode_packet(tl.KIND_VICTORY, 0x11, 4321, 3, 40, 1)
        own = tl.encode_packet(tl.KIND_VICTORY, 0x2A, 4321, 3, 40, 1)
        self.assertEqual(link.process(0), [])
        link.beam(own, repeats=1)
        link.update(1000)
        for byte in other:
            link.on_byte(byte)
        self.assertEqual((link.process(1000), link.pending), ([], []))
        now = 1000
        while link.sending():
            now += hw.FRAME_MS
            link.update(now)
        for byte in other:
            link.on_byte(byte)
        self.assertEqual(link.process(now + hw.FRAME_MS), [])
        for byte in own + other + other:
            link.on_byte(byte)
        packets = link.process(link.mute_until)
        self.assertEqual([(p["nonce"], p["value"], p["b"]) for p in packets], [(0x11, 4321, 40)])

    def test_pending_bytes_are_bounded(self):
        link = hw.IrLink(1)
        for value in range(hw.MAX_PENDING + 20):
            link.on_byte(value)
        self.assertEqual(len(link.pending), hw.MAX_PENDING)
        self.assertEqual(link.pending[-1], hw.MAX_PENDING - 1)


class DescriptorSubclassTests(unittest.TestCase):
    def test_trail_beam_extends_the_firmware_descriptor(self):
        class RemoteDescriptor:
            def __init__(self):
                self.init_called = True
                self.on_known = 1
                self.on_any = 1

        fakes = {
            "aye_arr": module("aye_arr"),
            "aye_arr.nec": module("aye_arr.nec"),
            "aye_arr.nec.remotes": module("aye_arr.nec.remotes"),
            "aye_arr.nec.remotes.descriptor": module("aye_arr.nec.remotes.descriptor", RemoteDescriptor=RemoteDescriptor),
        }
        loaded = load_modules(prefix="octocat_trail_desc_", extra=fakes, names=("trail_map", "trail_logic", "trail_hw"))
        real = loaded["trail_hw"]
        self.assertIs(real._Descriptor, RemoteDescriptor)
        beam = real.make_descriptor()
        self.assertIsInstance(beam, RemoteDescriptor)
        self.assertTrue(beam.init_called)
        self.assertEqual((beam.on_any, beam.on_known, beam.ADDRESS), (None, None, 0x54))
        for name, fake in fakes.items():
            self.assertIsNot(sys.modules.get(name), fake)
        for name in ("trail_map", "trail_logic", "trail_hw", "octocat_trail_desc_trail_hw"):
            self.assertNotIn(name, sys.modules)
        self.assertIs(hw._Descriptor, object)


VIEW_KINDS = ("title", "menu", "store", "roam", "card", "stop", "supplies", "map", "river", "crossing", "hunt",
              "camp", "tombstone", "victory", "help")
STEP_NAMES = ((0, -1, "up"), (0, 1, "down"), (-1, 0, "left"), (1, 0, "right"))


class FakeLink:
    """Stands in for trail_hw.IrLink inside the controller."""
    nonce = 7

    def __init__(self, transmit=False):
        self.sent = []
        self.busy = False
        self.transmit = transmit

    def can_send(self):
        return self.transmit

    def sending(self):
        return self.busy

    def progress(self):
        return 0.25

    def beam(self, packet):
        self.sent.append(list(packet))
        return True


class Driver:
    """Plays trail_game.Game frame by frame with fake keys and sensors."""

    def __init__(self, seed=1, save=None, link=_MISSING, persist=True):
        self.now = 1000
        self.writes = 0
        self.save = save if save is not None else tl.default_save()
        self.link = FakeLink() if link is _MISSING else link
        self.game = tg.Game(self.save, tl.Rng(seed), self.now, self.link, self.persist if persist else None)
        self.frames = 0
        self.screens = set()

    def persist(self, data):
        # State.save stores JSON, so every persisted save must round-trip.
        self.writes += 1
        if json.loads(json.dumps(data)) != data:
            raise AssertionError("save does not round-trip through JSON")

    def frame(self, pressed=(), held=(), dt=40, imu=None, light=None):
        self.now += dt
        self.frames += 1
        game = self.game
        game.update(self.now, tg.Keys(tuple(pressed), tuple(held)), imu, light)
        view = game.view()
        if view.kind not in VIEW_KINDS:
            raise AssertionError("unknown view kind %r" % view.kind)
        self.screens.add(game.screen)
        if game.screen == "roam":
            game.party_px()
            game.walk_frame()
        for level in game.lights():
            if not 0 <= level <= 1:
                raise AssertionError("case light level %r" % level)
        game.current_toast()
        return view

    def press(self, name, **kw):
        return self.frame((name,), **kw)

    def pick(self, prefix):
        """Move the cursor to the option starting with prefix and press SELECT."""
        view = self.game.view()
        for _ in range(len(view.options) + 1):
            if view.options[view.cursor][0].startswith(prefix):
                return self.press("select")
            view = self.press("down")
        raise AssertionError("no option %r in %r" % (prefix, [o[0] for o in view.options]))


def guide_direction(trail):
    guide = trail.guide()
    here = guide[trail.y * tm.W + trail.x]
    if here == tm.UNREACHED or here == 0:
        return None
    for dx, dy, name in STEP_NAMES:
        x, y = trail.x + dx, trail.y + dy
        if 0 <= x < tm.W and 0 <= y < tm.H and guide[y * tm.W + x] == here - 1:
            return name
    return None


def roaming(seed=5, role=0, **kw):
    """A Driver whose party has just left the Gatehouse store with 10 brew packs and 3 LGTM packs."""
    driver = Driver(seed, **kw)
    driver.press("select")
    for _ in range(role):
        driver.press("down")
    driver.press("select")
    driver.press("select")
    for _ in range(10):
        driver.press("right")
    driver.press("down")
    for _ in range(3):
        driver.press("right")
    driver.pick("Hit the trail")
    if driver.game.screen != "roam":
        raise AssertionError(driver.game.screen)
    return driver


def play(seed, role=0, explore=False, limit=20000):
    """Follow the guide arrows to the Mainstage, resting, shopping and crossing like a cautious player."""
    driver = roaming(seed, role)
    game = driver.game
    explored = False
    shopped = set()
    held = None
    while driver.frames < limit:
        screen = game.screen
        trail = game.trail
        if screen == "roam":
            if game.walk is None and trail.average_health() < 45 and trail.supplies["brew"] > 5:
                driver.press("select")
                continue
            name = guide_direction(trail)
            if name is None:
                driver.press("select")
                continue
            driver.frame(pressed=(name,) if name != held else (), held=(name,))
            held = name
        elif screen in ("event", "stop", "crossing", "supplies", "map"):
            held = None
            driver.press("select")
        elif screen == "menu":
            if explore and not explored:
                explored = True
                driver.pick("Check the wagon")
                driver.press("back")
                driver.pick("Look at the venue map")
                driver.press("select")
                driver.pick("Set the pace")
                driver.press("down")
                driver.press("select")
                driver.pick("Set the rations")
                driver.press("up")
                driver.press("select")
                driver.pick("Talk to attendees")
                driver.press("select")
                driver.pick("Bug & AI Slop Hunt")
                for index in range(200):
                    if game.screen != "hunt":
                        break
                    driver.frame(pressed=("select",) if index % 9 == 0 else (),
                                 held=("left",) if index < 60 else ("up",))
                if game.screen == "hunt":
                    driver.press("back")
                continue
            if trail.average_health() < 45 and trail.supplies["brew"] > 5:
                driver.pick("Make camp and rest")
                while game.screen in ("camp", "event") and driver.frames < limit:
                    driver.press("select") if game.screen == "event" else driver.frame()
                continue
            if trail.at_store() and trail.supplies["brew"] < 60 and trail.at not in shopped:
                shopped.add(trail.at)
                driver.pick("Visit the store")
                for _ in range(8):
                    driver.press("right")
                driver.press("back")
                continue
            driver.pick("Keep shipping" if game.origin == "roam" else "Back to the river")
        elif screen == "river":
            if trail.river_option_ok(tl.FERRY) and trail.river[0] > 30:
                want = tl.FERRY
            elif trail.river_option_ok(tl.CAULK):
                want = tl.CAULK
            else:
                want = tl.FORD if trail.river[0] <= 30 else tl.WAIT
            driver.pick(tl.RIVER_OPTIONS[want])
        elif screen == "camp":
            driver.frame()
        elif screen in ("victory", "tombstone"):
            return driver
        else:
            raise AssertionError("unexpected screen " + screen)
    raise AssertionError("seed %d did not finish in %d frames" % (seed, limit))


class GuidedRunTests(unittest.TestCase):
    """A cautious bot follows the guide from the Gatehouse to the Mainstage."""

    def test_guided_runs_reach_an_ending(self):
        endings = []
        seen = set()
        for seed in range(1, 25):
            role = seed % 3
            driver = play(seed * 7919, role=role, explore=seed % 4 == 0)
            game = driver.game
            endings.append(game.screen)
            self.assertIsNone(game.save["run"], seed)
            self.assertEqual(game.save["runs"], 1)
            self.assertGreater(driver.writes, 5)
            if game.screen == "victory":
                self.check_victory(driver, role)
            else:
                self.check_tombstone(driver)
            seen |= driver.screens
        self.assertGreater(endings.count("victory"), len(endings) // 2, endings)
        expected = {"title", "role", "event", "store", "roam", "stop", "menu", "river", "crossing", "supplies",
                    "map", "pace", "rations", "hunt", "victory"}
        self.assertTrue(expected <= seen, expected - seen)

    def check_victory(self, driver, role):
        game = driver.game
        trail = game.trail
        door = tm.STOPS[tm.END]
        self.assertEqual((trail.x, trail.y, trail.at), (door[3], door[4], tm.END))
        self.assertTrue(abs(trail.steps - tl.TRAIL_STEPS) <= 50, trail.steps)
        score, survivors, days, won_role, best = game.result
        self.assertEqual((won_role, survivors, days, best), (role, trail.living_count(), trail.day, True))
        self.assertGreaterEqual(survivors, 1)
        self.assertEqual((game.save["victories"], game.save["best"]), (1, score))
        driver.press("select")
        packet = tl.decode_packet(driver.link.sent[-1])
        self.assertEqual((packet["kind"], packet["nonce"]), (tl.KIND_VICTORY, FakeLink.nonce))
        self.assertEqual(tl.victory_from_packet(packet), (min(score, tl.MAX_VALUE), survivors, min(days, 127), role))
        self.assertEqual((game.save["beamed"], game.current_toast()), (1, "No IR: victory beam simulated."))
        driver.press("back")
        self.assertEqual(game.screen, "title")
        self.assertIn("Wins 1", game.view().lines[1])

    def check_tombstone(self, driver):
        game = driver.game
        self.assertTrue(game.trail.all_dead())
        stones = game.save["tombstones"]
        self.assertEqual(len(stones), 1)
        self.assertIs(stones[0], game.record)
        self.assertEqual(game.record[0], game.trail.steps)
        epitaph = game.record[2]
        driver.press("right")
        self.assertEqual(stones[0][2], (epitaph + 1) % len(tl.EPITAPHS))
        driver.press("left")
        driver.press("left")
        self.assertEqual(stones[0][2], (epitaph - 1) % len(tl.EPITAPHS))
        driver.press("select")
        packet = tl.decode_packet(driver.link.sent[-1])
        self.assertEqual(tl.tombstone_from_packet(packet)[:4], stones[0][:4])
        driver.press("back")
        self.assertEqual(game.screen, "title")
        driver.pick("Visit the graveyard")
        self.assertEqual(game.screen, "graveyard")
        driver.press("back")
        self.assertEqual(game.screen, "title")

    def test_same_seed_replays_the_same_run(self):
        first = play(4242, role=1)
        second = play(4242, role=1)
        self.assertEqual(first.frames, second.frames)
        self.assertEqual(first.game.trail.to_dict(), second.game.trail.to_dict())
        self.assertEqual(first.game.screen, second.game.screen)

    def test_a_tombstone_run(self):
        driver = roaming(5, role=2)
        game = driver.game
        doom(game.trail)
        driver.frame(pressed=("up",), held=("up",))
        while game.screen == "roam" and driver.frames < 200:
            driver.frame(held=("up",))
        self.assertEqual((game.screen, game.card_after), ("event", "tombstone"))
        lines = game.card_lines
        self.assertEqual(lines[-1], "Nobody is left to finish the trail.")
        died = [line for line in lines if line.endswith(" has died of caffeine withdrawal.")]
        self.assertEqual(len(died), len(game.trail.members))
        self.assertIsNone(game.save["run"])
        finish_cards(driver)
        self.assertEqual(game.screen, "tombstone")
        self.assertEqual((game.record[1], game.record[3]), (tl.CAUSE_WITHDRAWAL, 2))
        self.check_tombstone(driver)


def doom(trail):
    """Leave the party one day of upkeep from dying of caffeine withdrawal."""
    trail.supplies["brew"] = 0.0
    for member in trail.members:
        member.health = 1
    trail.day_ms = tl.DAY_MS - 1


def kill_all(trail):
    lines = []
    for member in trail.living():
        trail._kill(member, tl.CAUSE_EXHAUSTION, lines)
    return lines


def finish_cards(driver, limit=12):
    for _ in range(limit):
        if driver.game.screen != "event":
            return
        driver.press("select")
    raise AssertionError("cards never finished")


def river_driver(stop=tm.MERGE, seed=3, credits=None, **supplies):
    """A Driver that has resumed a saved run waiting at a river."""
    trail = at_river(stop, **supplies)
    if credits is not None:
        trail.supplies["credits"] = credits
    save = tl.default_save()
    save["run"] = trail.to_dict()
    driver = Driver(seed, save=save)
    driver.pick("Continue your run")
    if driver.game.screen != "river":
        raise AssertionError(driver.game.screen)
    return driver


def labels(view):
    return [option[0] for option in view.options]


def to_store(driver, role=0):
    driver.pick("Start a new run")
    for _ in range(role):
        driver.press("down")
    driver.press("select")
    finish_cards(driver)


class TitleFlowTests(unittest.TestCase):
    def test_fresh_title(self):
        driver = Driver()
        game = driver.game
        view = game.view()
        self.assertEqual((view.kind, view.title, view.cursor), ("title", "The Octocat Trail", 0))
        self.assertEqual(labels(view), ["Start a new run", "Visit the graveyard", "Monitor", "Dark Mode Camp sensor",
                                        "Learn how to play"])
        self.assertEqual([option[2] for option in view.options], [True, False, True, True, True])
        self.assertEqual(view.lines[1], "Best 0   Runs 0   Wins 0")
        driver.press("up")
        self.assertEqual(game.cursor, 4)
        driver.pick("Visit the graveyard")
        self.assertEqual((game.screen, game.view().note), ("title", "No tombstones yet. Give it time."))
        driver.press("down")
        self.assertEqual(game.view().note, "")

    def test_toggles_persist(self):
        driver = Driver()
        game = driver.game
        driver.pick("Monitor")
        self.assertEqual((game.save["visual"], game.current_toast()), (1, "Monitor: Green"))
        driver.press("left")
        driver.press("right")
        driver.press("right")
        self.assertEqual(game.save["visual"], 0)
        self.assertEqual(game.view().options[game.cursor][1], "Color")
        driver.press("down")
        driver.press("right")
        self.assertEqual((game.save["auto_camp"], game.view().options[game.cursor][1]), (False, "Off"))
        driver.press("select")
        self.assertTrue(game.save["auto_camp"])
        driver.press("up")
        driver.press("up")
        driver.press("right")
        self.assertEqual((game.screen, game.cursor), ("title", 1))
        self.assertEqual(driver.writes, 6)

    def test_menu_key_switches_monitor_on_any_screen(self):
        driver = roaming()
        game = driver.game
        driver.press("menu")
        self.assertEqual((game.visual(), game.screen, game.current_toast()), (1, "roam", "Monitor: Green"))
        driver.press("select")
        driver.press("menu")
        self.assertEqual((game.visual(), game.screen), (0, "menu"))

    def test_help_pages(self):
        driver = Driver()
        game = driver.game
        driver.pick("Learn how to play")
        titles = []
        while game.screen == "help":
            titles.append(game.view().title)
            driver.press("select")
        self.assertEqual(len(titles), len(tg.HELP))
        self.assertEqual(titles[0], "The Octocat Trail  (1/%d)" % len(tg.HELP))
        self.assertEqual((game.screen, game.cursor), ("title", 4))
        driver.press("select")
        driver.press("right")
        driver.press("left")
        driver.press("left")
        self.assertEqual(game.help_page, 0)
        driver.press("right")
        driver.press("back")
        self.assertEqual((game.screen, game.cursor), ("title", 4))
        for title, lines in tg.HELP:
            self.assertTrue(title and lines)
            for line in lines:
                self.assertLessEqual(len(line), 120, line)

    def test_role_choice(self):
        driver = Driver()
        game = driver.game
        driver.pick("Start a new run")
        view = game.view()
        self.assertEqual((game.screen, view.title), ("role", "Choose a role"))
        self.assertEqual(labels(view), [role[0] + " " + role[1] for role in tl.ROLES])
        driver.press("back")
        self.assertEqual(game.screen, "title")
        driver.pick("Start a new run")
        driver.press("down")
        driver.press("down")
        driver.press("select")
        self.assertEqual((game.screen, game.card_title, game.card_after), ("event", "Your Studio party", "store"))
        self.assertEqual((game.trail.role, game.save["runs"]), (2, 1))
        self.assertIsNotNone(game.save["run"])
        finish_cards(driver)
        self.assertEqual((game.screen, game.view().title), ("store", "Gatehouse General Store"))
        self.assertEqual(game.trail.supplies["credits"], tl.ROLES[2][2])


class StoreFlowTests(unittest.TestCase):
    def test_buying_and_returning(self):
        driver = Driver()
        game = driver.game
        to_store(driver, role=1)
        view = game.view()
        self.assertEqual(labels(view), ["Cold Brew Kegs", "LGTM Stamps", "Hotfix Patches", "Hit the trail"])
        self.assertEqual((view.hint, view.foot[-1]), ("RIGHT buy  LEFT return  BACK title", "Copilot Credits left: 1,000"))
        driver.press("left")
        self.assertEqual(game.view().note, "Only this visit's purchases can go back.")
        driver.press("right")
        self.assertEqual(game.view().note, "Bought 10 Cold Brew Kegs.")
        driver.press("select")
        driver.press("left")
        self.assertEqual(game.view().note, "Returned 10 Cold Brew Kegs.")
        self.assertEqual((game.trail.supplies["brew"], game.trail.supplies["credits"]), (10, 960))
        self.assertEqual(game.view().options[0][1], "10")
        driver.press("down")
        self.assertEqual(game.view().note, "")

    def test_leaving_without_brew_warns_once(self):
        driver = Driver()
        game = driver.game
        to_store(driver)
        driver.pick("Hit the trail")
        self.assertEqual((game.screen, game.view().note), ("store", "No cold brew packed! Leave again to go anyway."))
        driver.press("select")
        self.assertEqual((game.screen, game.trail.ticker), ("roam", "The Ducky leans into the harness. Onward!"))
        self.assertEqual((game.save["run"]["at"], game.save["run"]["brew"]), (0, 0))

    def test_wagon_and_wallet_limits(self):
        driver = Driver()
        game = driver.game
        to_store(driver)
        driver.press("down")
        driver.press("down")
        for _ in range(tl.carry_limit("patches") + 1):
            driver.press("right")
        self.assertEqual(game.view().note, "The wagon can't carry any more.")
        self.assertEqual(game.trail.supplies["patches"], tl.carry_limit("patches"))
        driver.press("up")
        driver.press("up")
        for _ in range(60):
            driver.press("right")
        self.assertEqual(game.view().note, "Not enough Copilot Credits.")
        self.assertLess(game.trail.supplies["credits"], tl.store_item("brew")[2] * game.trail.price("brew"))
        self.assertGreaterEqual(game.trail.supplies["credits"], 0)

    def test_back_saves_the_run_for_later(self):
        driver = Driver()
        game = driver.game
        to_store(driver)
        driver.press("right")
        driver.press("back")
        self.assertEqual(game.screen, "title")
        self.assertEqual(game.view().options[0][:2], ("Continue your run", "Step 0"))
        driver.pick("Continue your run")
        self.assertEqual((game.screen, game.trail.supplies["brew"]), ("store", 10))
        self.assertEqual(game.view().options[-1][0], "Hit the trail")


class ResumeFlowTests(unittest.TestCase):
    def resumed(self, trail):
        save = tl.default_save()
        save["run"] = trail.to_dict()
        driver = Driver(save=save)
        driver.pick("Continue your run")
        return driver

    def test_resume_lands_on_the_right_screen(self):
        self.assertEqual(self.resumed(at_river(tm.DNS)).game.screen, "river")
        trail = stocked()
        walk_to(trail, 2)
        self.assertEqual(trail.at, 2)
        game = self.resumed(trail).game
        self.assertEqual((game.screen, game.origin, game.trail.at), ("menu", "roam", 2))
        trail = stocked()
        trail.step(0, -1)
        trail.after_step()
        game = self.resumed(trail).game
        self.assertEqual((game.screen, game.trail.y), ("roam", tm.START[1] - 1))

    def test_corrupt_run_is_dropped(self):
        for bad in ({"v": 2, "party": "nope"}, {"v": 99}, {}):
            save = tl.default_save()
            save["run"] = bad
            driver = Driver(save=save)
            self.assertNotIn("Continue your run", labels(driver.game.view()))
            self.assertIsNone(save["run"])

    def test_shutdown_mid_step_saves_a_whole_tile(self):
        driver = roaming()
        game = driver.game
        driver.frame(pressed=("up",), held=("up",))
        self.assertIsNotNone(game.walk)
        writes = driver.writes
        game.shutdown()
        self.assertIsNone(game.walk)
        run = game.save["run"]
        self.assertEqual((run["x"], run["y"], run["steps"]), (tm.START[0], tm.START[1] - 1, tm.STEPS_PER_TILE))
        self.assertEqual(driver.writes, writes + 1)

    def test_shutdown_mid_step_can_end_the_run(self):
        driver = roaming()
        game = driver.game
        driver.frame(pressed=("up",), held=("up",))
        doom(game.trail)
        game.shutdown()
        self.assertTrue(game.over)
        self.assertIsNone(game.save["run"])
        self.assertEqual(game.save["tombstones"][0][1], tl.CAUSE_WITHDRAWAL)

    def test_shutdown_elsewhere_only_persists(self):
        driver = Driver()
        driver.game.shutdown()
        self.assertEqual(driver.writes, 1)
        self.assertIsNone(driver.game.save["run"])
        driver = Driver(persist=False)
        driver.game.shutdown()
        self.assertEqual(driver.game.saves, 0)


UPRIGHT = (0, 16384, 0, 0, 0, 0)
JOLT = (0, 40000, 0, 0, 0, 0)


def shake(driver, frames=6):
    """Feed one shake gesture (a resting reading, then alternating jolts); returns shakes detected."""
    before = driver.game.shakes
    for index in range(frames):
        driver.frame(imu=JOLT if index % 2 else UPRIGHT)
    return driver.game.shakes - before


def light_for(driver, value, ms, dt=40):
    """Hold the ambient light at value for ms, clicking through any cards."""
    for _ in range(ms // dt):
        if driver.game.screen == "event":
            driver.frame(("select",), dt=dt, light=value)
        else:
            driver.frame(dt=dt, light=value)


def lights_out(driver):
    light_for(driver, 40000, 3000)
    light_for(driver, 0, 2000)


def name_of(dx, dy):
    for ddx, ddy, name in STEP_NAMES:
        if (ddx, ddy) == (dx, dy):
            return name
    raise AssertionError((dx, dy))


class RoamFlowTests(unittest.TestCase):
    def test_status_rows(self):
        driver = roaming()
        view = driver.game.view()
        self.assertEqual((view.kind, view.title, view.hint), ("roam", "", "D-pad walk  SELECT menu  BACK sprint"))
        self.assertEqual([row[0] for row in view.rows],
                         ["Date", "Weather", "Health", "Cold brew", "Next stop", "Steps walked"])
        rows = dict(view.rows)
        self.assertEqual((rows["Date"], rows["Cold brew"]), ("September 1, 2026", "100 kegs"))
        self.assertEqual((rows["Next stop"], rows["Steps walked"]), ("GitHub Shop, 320 steps", "0"))
        self.assertEqual(view.note, "The Ducky leans into the harness. Onward!")
        self.assertIs(view.data, driver.game.trail)

    def test_a_step_slides_from_tile_to_tile(self):
        driver = roaming()
        game = driver.game
        trail = game.trail
        x0, y0 = tm.START
        driver.frame(pressed=("up",), held=("up",))
        self.assertEqual((trail.x, trail.y), (x0, y0 - 1))
        self.assertEqual(game.walk[2], trail.tile_ms())
        positions = [game.party_px()]
        self.assertEqual(positions[0], (x0 * tm.TILE, y0 * tm.TILE))
        while game.walk is not None:
            driver.frame()
            positions.append(game.party_px())
        self.assertEqual(positions[-1], (x0 * tm.TILE, (y0 - 1) * tm.TILE))
        ys = [y for _x, y in positions]
        self.assertEqual(ys, sorted(ys, reverse=True))
        self.assertGreater(len(set(ys)), 3)
        self.assertEqual(set(x for x, _y in positions), {x0 * tm.TILE})
        self.assertEqual((game.walk_frame(), game.stride, trail.steps), (0, 0, tm.STEPS_PER_TILE))

    def test_holding_a_direction_keeps_walking(self):
        driver = roaming()
        game = driver.game
        driver.frame(pressed=("up",), held=("up",))
        frames = set()
        for _ in range(12):
            driver.frame(held=("up",))
            self.assertIsNotNone(game.walk)
            frames.add(game.walk_frame())
        self.assertEqual(game.trail.y, tm.START[1] - 2)
        self.assertEqual(frames, {0, 1})

    def test_bumping_into_the_venue(self):
        for code, reason in ((tm.WATER, "That way lies San Francisco Bay."),
                             (tm.FENCE, "Load-in zone: no entry from the plaza."),
                             (tm.GANG1, "Gangway is up. Cross at the dock.")):
            driver = roaming()
            game = driver.game
            trail = game.trail
            x, y, dx, dy = edge_of(code)
            trail.x, trail.y, trail.at = x, y, -1
            name = name_of(dx, dy)
            driver.frame(pressed=(name,), held=(name,))
            self.assertEqual((trail.x, trail.y, game.walk), (x, y, None))
            self.assertEqual((game.current_toast(), trail.blocked_reason(dx, dy)), (reason, reason))
            for _ in range(5):
                driver.frame(held=(name,))
            self.assertEqual(len(game.toasts), 1)
            driver.frame(pressed=(name,), held=(name,))
            self.assertEqual(len(game.toasts), 2)
            driver.frame()
            self.assertEqual(game.bump, "")
            driver.frame(held=(name,))
            self.assertEqual(len(game.toasts), 3)
            self.assertEqual(trail.steps, 0)

    def test_back_sprints(self):
        driver = roaming()
        game = driver.game
        trail = game.trail
        self.assertEqual(game.sprint_state(), "Ready")
        driver.press("back")
        self.assertEqual((game.current_toast(), trail.turbo_days), ("Turbo sprint!", tl.TURBO_DAYS))
        self.assertEqual(game.view().note, "Turbo sprint: %d days left" % tl.TURBO_DAYS)
        self.assertEqual(game.sprint_state(), "Sprinting")
        self.assertEqual(game.lights()[0], 0.3 if (game.now // 250) & 1 else 0.1)
        driver.press("back")
        self.assertEqual(game.current_toast(), "Already sprinting.")
        trail.turbo_days = 0
        trail.turbo_cooldown = 2
        self.assertEqual(game.sprint_state(), "Cooling 2d")
        driver.press("back")
        self.assertEqual(game.current_toast(), "Sprint cooling down: 2 days left.")
        trail.turbo_cooldown = 1
        driver.press("back")
        self.assertEqual(game.current_toast(), "Sprint cooling down: 1 day left.")
        trail.turbo_cooldown = 0
        trail.supplies["brew"] = 0
        driver.press("back")
        self.assertEqual((game.current_toast(), game.sprint_state()), ("No cold brew to fuel a sprint.", "No brew"))
        self.assertEqual((game.screen, trail.turbo_days), ("roam", 0))

    def test_back_sprints_mid_step(self):
        # Presses last one frame, so BACK during a step must sprint at once.
        for held in (("up",), ()):
            driver = roaming()
            game = driver.game
            trail = game.trail
            x0, y0 = tm.START
            driver.frame(pressed=("up",), held=("up",))
            driver.frame(pressed=("back",), held=held)
            self.assertEqual((trail.x, trail.y), (x0, y0 - 1))
            self.assertIsNotNone(game.walk)
            self.assertEqual((game.current_toast(), trail.turbo_days), ("Turbo sprint!", tl.TURBO_DAYS))
            goal = y0 - 2 if held else y0 - 1
            for _ in range(20):
                driver.frame(held=held)
                if trail.y == goal and (held or game.walk is None):
                    break
            self.assertEqual((game.screen, trail.x, trail.y), ("roam", x0, goal))
            self.assertEqual(game.walk is not None, bool(held))

    def test_select_mid_step_opens_the_menu_when_the_step_lands(self):
        driver = roaming()
        game = driver.game
        trail = game.trail
        x0, y0 = tm.START
        driver.frame(pressed=("up",), held=("up",))
        driver.frame(pressed=("select",), held=("up",))
        self.assertEqual((game.screen, trail.y), ("roam", y0 - 1))
        self.assertIsNotNone(game.walk)
        for _ in range(20):
            if game.screen != "roam":
                break
            driver.frame(held=("up",))
        self.assertEqual((game.screen, game.origin), ("menu", "roam"))
        self.assertEqual((trail.x, trail.y, game.walk, game.stride, game.want_menu), (x0, y0 - 1, None, 0, False))
        driver.press("back")
        driver.frame(held=("up",))
        self.assertEqual((game.screen, trail.y), ("roam", y0 - 2))
        for _ in range(20):
            if game.walk is None:
                break
            driver.frame()
        self.assertEqual((game.screen, trail.y, game.walk), ("roam", y0 - 2, None))


class SensorFlowTests(unittest.TestCase):
    def test_shaking_sprints_only_while_roaming(self):
        driver = roaming()
        game = driver.game
        driver.press("select")
        self.assertEqual(shake(driver), 1)
        self.assertEqual((game.screen, game.trail.turbo_days), ("menu", 0))
        driver.press("back")
        driver.now += 2500
        self.assertEqual(shake(driver), 1)
        self.assertEqual((game.current_toast(), game.trail.turbo_days),
                         ("Shake detected: turbo sprint!", tl.TURBO_DAYS))
        self.assertEqual(shake(driver), 0)
        driver.frame(imu=(0, 0, 0, 0, 0, 0))
        self.assertEqual(game.screen, "roam")

    def test_simulator_upside_down_reading_is_not_a_shake(self):
        driver = roaming()
        for reading in ((0, -16384, 0, 0, 0, 0), (0, 16384, 0, 0, 0, 0)) * 6:
            driver.frame(imu=reading)
        self.assertEqual(driver.game.shakes, 0)

    def test_lights_out_camps_until_the_lights_return(self):
        driver = roaming()
        game = driver.game
        light_for(driver, 40000, 3000)
        self.assertEqual((game.screen, game.dark_room), ("roam", False))
        light_for(driver, 0, 2000)
        self.assertEqual((game.screen, game.camp_auto, game.camp_origin), ("camp", True, "roam"))
        self.assertTrue(game.dark() and game.dark_room)
        view = game.view()
        self.assertEqual(view.lines[0], "Lights out. The party rests until the room is bright again.")
        self.assertIs(view.data, True)
        flicker = game.lights()
        self.assertEqual((flicker[0], flicker[3]), (flicker[3], flicker[0]))
        day = game.trail.day
        light_for(driver, 0, 4400)
        self.assertGreaterEqual(game.camp_days, 1)
        self.assertGreater(game.trail.day, day)
        self.assertTrue(game.view().lines[1].startswith("Health: "))
        light_for(driver, 40000, 2000)
        self.assertEqual((game.screen, game.dark_room, game.darkness.suppressed), ("roam", False, False))
        self.assertIn("The lights are back on. Break camp!", [toast[0] for toast in game.toasts])
        self.assertEqual(game.save["run"]["day"], game.trail.day)

    def test_lights_out_while_walking_camps_when_the_step_lands(self):
        driver = roaming()
        game = driver.game
        trail = game.trail
        trail.rng = QuietRng()
        light_for(driver, 40000, 3000)
        self.assertEqual((game.screen, game.walk), ("roam", None))
        steps = trail.steps
        was_walking = False
        for _ in range(150):
            self.assertEqual(game.screen, "roam")
            name = guide_direction(trail)
            self.assertIsNotNone(name)
            was_walking = game.walk is not None
            driver.frame(held=(name,), light=0)
            if game.screen != "roam":
                break
        self.assertEqual((game.screen, game.camp_auto, game.camp_origin), ("camp", True, "roam"))
        self.assertTrue(was_walking)
        self.assertEqual((game.walk, trail.pending_ms), (None, 0))
        self.assertGreater(trail.steps, steps)

    def test_breaking_camp_by_hand_waits_for_daylight(self):
        driver = roaming()
        game = driver.game
        lights_out(driver)
        self.assertEqual(game.screen, "camp")
        driver.press("select", light=0)
        self.assertEqual((game.screen, game.darkness.suppressed), ("roam", True))
        light_for(driver, 0, 3000)
        self.assertEqual(game.screen, "roam")
        light_for(driver, 40000, 2500)
        self.assertFalse(game.darkness.suppressed or game.dark_room)
        light_for(driver, 0, 2500)
        self.assertEqual(game.screen, "camp")

    def test_darkness_while_already_resting_turns_camp_automatic(self):
        driver = roaming()
        game = driver.game
        light_for(driver, 40000, 3000)
        driver.press("select", light=40000)
        driver.pick("Make camp and rest")
        self.assertFalse(game.camp_auto)
        light_for(driver, 0, 2000)
        self.assertEqual((game.screen, game.camp_auto), ("camp", True))
        light_for(driver, 40000, 2000)
        self.assertEqual(game.screen, "menu")

    def test_sensor_off_never_camps(self):
        save = tl.default_save()
        save["auto_camp"] = False
        driver = roaming(save=save)
        game = driver.game
        lights_out(driver)
        light_for(driver, 0, 1000)
        self.assertTrue(game.dark_room)
        self.assertEqual((game.screen, game.want_camp, game.dark()), ("roam", False, False))

    def test_switching_the_sensor_off_cancels_a_pending_camp(self):
        driver = Driver()
        game = driver.game
        game.want_camp = True
        driver.pick("Dark Mode Camp sensor")
        self.assertEqual((game.save["auto_camp"], game.want_camp), (False, False))

    def test_manual_camp_rests_three_days(self):
        driver = roaming()
        game = driver.game
        driver.press("select")
        driver.pick("Make camp and rest")
        self.assertEqual((game.screen, game.camp_auto, game.camp_origin), ("camp", False, "menu"))
        view = game.view()
        self.assertEqual(view.lines, ["Resting: day 1 of 3.", "Health: %s." % game.trail.party_health()])
        self.assertEqual((view.hint, view.progress), ("SELECT break camp", 0.0))
        day = game.trail.day
        now = game.now
        driver.frame(dt=5000)
        self.assertEqual((game.camp_timer, game.now), (tg.MAX_DT, now + 5000))
        for _ in range(100):
            if game.screen == "menu":
                break
            driver.frame(("select",) if game.screen == "event" else (), dt=250)
        self.assertEqual((game.screen, game.trail.day, game.camp_days), ("menu", day + 3, 3))
        self.assertEqual(game.save["run"]["day"], day + 3)

    def test_breaking_a_manual_camp_early(self):
        driver = roaming()
        game = driver.game
        driver.press("select")
        driver.pick("Make camp and rest")
        driver.press("back")
        self.assertEqual((game.screen, game.trail.day, game.darkness.suppressed), ("menu", 1, False))


def step_once(driver, name="up"):
    driver.frame(pressed=(name,), held=(name,))
    while driver.game.walk is not None:
        driver.frame()


def in_menu(**kw):
    driver = roaming(**kw)
    driver.press("select")
    if driver.game.screen != "menu":
        raise AssertionError(driver.game.screen)
    return driver


class MenuFlowTests(unittest.TestCase):
    def test_gatehouse_menu(self):
        driver = in_menu()
        game = driver.game
        view = game.view()
        self.assertEqual((view.kind, view.title, view.hint),
                         ("menu", "The Gatehouse (git init)", "UP/DOWN choose  SELECT go  BACK walk on"))
        self.assertEqual(view.lines, ("September 1, 2026", "Weather: Sunny", "Health: Good", "You can:"))
        self.assertEqual(labels(view), ["Keep shipping", "Check the wagon", "Look at the venue map", "Set the pace",
                                        "Set the rations", "Make camp and rest", "Talk to attendees",
                                        "Visit the store", "Bug & AI Slop Hunt", "Turbo sprint", "Save and quit"])
        values = dict((option[0], option[1]) for option in view.options)
        self.assertEqual((values["Set the pace"], values["Set the rations"]), ("Sustainable", "Drip"))
        self.assertEqual((values["Bug & AI Slop Hunt"], values["Turbo sprint"]), ("30 LGTMs", "Ready"))
        driver.pick("Keep shipping")
        self.assertEqual(game.screen, "roam")
        driver.press("select")
        driver.press("back")
        self.assertEqual(game.screen, "roam")

    def test_menu_between_stops(self):
        driver = roaming()
        step_once(driver)
        finish_cards(driver)
        driver.press("select")
        view = driver.game.view()
        self.assertEqual(view.title, "Fort Mason Center")
        self.assertNotIn("Visit the store", labels(view))

    def test_wagon_and_map(self):
        driver = in_menu()
        game = driver.game
        driver.pick("Check the wagon")
        view = game.view()
        self.assertEqual((game.screen, view.kind, view.title), ("supplies", "supplies", "Your wagon"))
        self.assertEqual(view.rows, (("Copilot Credits", "1,170"), ("Cold Brew Kegs", "100"),
                                     ("LGTM Stamps", "30"), ("Hotfix Patches", "0")))
        self.assertEqual([member[0] for member in view.data], list(tl.PARTY))
        self.assertTrue(all(member[2] for member in view.data))
        self.assertEqual(view.foot, ("The party drinks %s kegs a day." % tg.kegs(game.trail.brew_per_day()),))
        driver.press("back")
        self.assertEqual((game.screen, game.cursor), ("menu", 1))
        driver.pick("Look at the venue map")
        view = game.view()
        self.assertEqual((view.kind, view.title), ("map", "Fort Mason Center"))
        self.assertEqual(view.lines, ("Next stop: GitHub Shop", "320 steps away", "Walked: 0 steps"))
        self.assertIs(view.data, game.trail)
        driver.press("select")
        self.assertEqual((game.screen, game.cursor), ("menu", 2))

    def test_pace_and_rations(self):
        driver = in_menu()
        game = driver.game
        driver.pick("Set the pace")
        view = game.view()
        self.assertEqual((game.screen, view.title, view.cursor), ("pace", "Set the pace", 0))
        self.assertEqual([option[1] for option in view.options], ["20 steps/day", "26 steps/day", "34 steps/day"])
        self.assertEqual(view.foot, (tg.PACE_NOTES[0],))
        driver.press("down")
        driver.press("back")
        self.assertEqual((game.screen, game.trail.pace), ("menu", 0))
        driver.press("select")
        driver.press("down")
        writes = driver.writes
        driver.press("select")
        self.assertEqual((game.screen, game.trail.pace, game.current_toast()), ("menu", 1, "Pace: Crunch"))
        self.assertEqual((game.save["run"]["pace"], driver.writes), (1, writes + 1))
        self.assertEqual(game.view().options[3][1], "Crunch")
        driver.pick("Set the rations")
        view = game.view()
        self.assertEqual((view.title, view.cursor), ("Set the rations", 1))
        self.assertEqual([option[1] for option in view.options], ["0.3 kegs each", "0.2 kegs each", "0.1 kegs each"])
        driver.press("down")
        self.assertEqual(game.view().foot, (tg.RATION_NOTES[2],))
        driver.press("select")
        self.assertEqual((game.trail.rations, game.current_toast()), (2, "Rations: Decaf"))

    def test_talk_to_attendees(self):
        driver = in_menu()
        game = driver.game
        driver.pick("Talk to attendees")
        view = game.view()
        self.assertEqual((view.kind, view.title, game.card_after), ("card", "Talk to attendees", "menu"))
        self.assertTrue(view.lines[0].endswith(" says:"))
        self.assertTrue(view.lines[0][:-6] in tg.SPEAKERS)
        self.assertTrue(view.lines[1].startswith('"') and view.lines[1].endswith('"'))
        self.assertEqual(view.hint, "SELECT continue")
        driver.press("select")
        self.assertEqual(game.screen, "menu")

    def test_store_from_the_menu(self):
        driver = in_menu()
        game = driver.game
        driver.pick("Visit the store")
        view = game.view()
        self.assertEqual((view.title, labels(view)[-1]), ("Gatehouse General Store", "Leave the store"))
        self.assertTrue(view.hint.endswith("BACK leave"))
        driver.press("right")
        self.assertEqual(game.trail.supplies["brew"], 110)
        driver.pick("Leave the store")
        self.assertEqual(game.screen, "menu")
        self.assertEqual(game.save["run"]["brew"], 1100)
        driver.pick("Visit the store")
        driver.press("back")
        self.assertEqual(game.screen, "menu")


def option_of(view, label):
    for option in view.options:
        if option[0] == label:
            return option
    raise AssertionError("no option %r" % label)


class MenuActionTests(unittest.TestCase):
    def test_hunt_from_the_menu(self):
        driver = in_menu()
        game = driver.game
        driver.pick("Bug & AI Slop Hunt")
        view = game.view()
        self.assertEqual((game.screen, view.kind, view.title), ("hunt", "hunt", "Bug & AI Slop Hunt"))
        self.assertEqual((view.hint, view.progress), ("D-pad walk  SELECT stamp  BACK stop", 1.0))
        self.assertIs(view.data, game.hunt)
        for _ in range(10):
            driver.frame(pressed=("select",), held=("right",))
        self.assertAlmostEqual(game.view().progress, 1 - 400.0 / tl.HUNT_MS)
        driver.press("back")
        self.assertEqual((game.screen, game.card_title, game.card_after), ("event", "Bug & AI Slop Hunt", "menu"))
        self.assertIsNone(game.hunt)
        finish_cards(driver)
        self.assertEqual(game.screen, "menu")
        self.assertLess(game.trail.supplies["lgtm"], 30)
        self.assertEqual(game.save["run"]["lgtm"], game.trail.supplies["lgtm"])

    def test_hunt_runs_out_of_time(self):
        driver = in_menu()
        game = driver.game
        driver.pick("Bug & AI Slop Hunt")
        driver.frame(dt=250)
        self.assertAlmostEqual(game.view().progress, 1 - 100.0 / tl.HUNT_MS)
        frames = 1
        while game.screen == "hunt" and frames < 400:
            driver.frame(dt=100)
            frames += 1
        self.assertEqual((game.screen, frames), ("event", tl.HUNT_MS // 100))
        self.assertEqual(game.card_title, "Bug & AI Slop Hunt")

    def test_hunt_needs_stamps(self):
        driver = in_menu()
        game = driver.game
        game.trail.supplies["lgtm"] = 0
        self.assertEqual(option_of(game.view(), "Bug & AI Slop Hunt")[1:], ("0 LGTMs", False))
        driver.pick("Bug & AI Slop Hunt")
        self.assertEqual((game.screen, game.view().note), ("menu", "You need LGTM Stamps to hunt."))

    def test_sprint_from_the_menu(self):
        driver = in_menu()
        game = driver.game
        driver.pick("Turbo sprint")
        self.assertEqual((game.screen, game.current_toast()), ("roam", "Turbo sprint!"))
        self.assertEqual(game.trail.turbo_days, tl.TURBO_DAYS)
        driver.press("select")
        self.assertEqual(option_of(game.view(), "Turbo sprint")[1:], ("Sprinting", False))
        driver.pick("Turbo sprint")
        self.assertEqual((game.screen, game.view().note), ("menu", "Already sprinting."))

    def test_save_and_quit(self):
        driver = in_menu()
        game = driver.game
        writes = driver.writes
        driver.pick("Save and quit")
        self.assertEqual((game.screen, driver.writes, game.trail), ("title", writes + 1, None))
        self.assertEqual(game.view().options[0][0], "Continue your run")
        driver.pick("Continue your run")
        self.assertEqual((game.screen, game.trail.supplies["brew"]), ("store", 100))

    def test_lights_out_in_the_menu(self):
        driver = in_menu()
        game = driver.game
        lights_out(driver)
        self.assertEqual((game.screen, game.camp_origin), ("camp", "menu"))
        light_for(driver, 40000, 2000)
        self.assertEqual(game.screen, "menu")


class RiverFlowTests(unittest.TestCase):
    def test_river_screen(self):
        driver = river_driver()
        view = driver.game.view()
        self.assertEqual((view.kind, view.title, view.data), ("river", "Merge Conflict River", tm.MERGE))
        self.assertEqual(view.lines[2:], ("Diff: 140 ft wide, 2.0 ft deep", "You can:"))
        self.assertEqual(list(view.options), [
            ("YOLO deploy (ford)", "0%", True), ("Ship with 2 LGTMs", "2 LGTMs, 10%", True),
            ("Ask Copilot (ferry)", "40 cr, 2%", True), ("Wait for review", "1 day", True), ("Plan it out", "", True)])

    def test_blocked_options_explain_themselves(self):
        driver = river_driver(lgtm=1, credits=10)
        game = driver.game
        driver.pick("Ship with 2 LGTMs")
        self.assertEqual((game.screen, game.view().note), ("river", "You need 2 LGTM Stamps to ship it."))
        driver.pick("Ask Copilot (ferry)")
        self.assertEqual((game.screen, game.view().note), ("river", "Not enough Copilot Credits for the ferry."))
        driver.press("down")
        self.assertEqual(game.view().note, "")

    def test_plan_it_out(self):
        driver = river_driver()
        game = driver.game
        driver.pick("Plan it out")
        view = game.view()
        self.assertEqual((game.screen, game.origin, labels(view)[0]), ("menu", "river", "Back to the river"))
        self.assertNotIn("Visit the store", labels(view))
        self.assertEqual(option_of(view, "Turbo sprint")[1:], ("Ready", False))
        driver.pick("Turbo sprint")
        self.assertEqual(game.view().note, "Cross the river first.")
        driver.press("back")
        self.assertEqual(game.screen, "river")
        driver.pick("Plan it out")
        driver.pick("Back to the river")
        self.assertEqual(game.screen, "river")

    def test_waiting_for_review(self):
        driver = river_driver()
        game = driver.game
        day = game.trail.day
        driver.pick("Wait for review")
        self.assertEqual((game.screen, game.card_title, game.card_after), ("event", "Merge Conflict River", "river"))
        self.assertTrue(game.card_lines[0].startswith("You waited a day for review. The river is now "))
        self.assertEqual((game.trail.day, game.save["run"]["day"]), (day + 1, day + 1))
        finish_cards(driver)
        self.assertEqual(game.screen, "river")
        self.assertIn(" %s ft deep" % tl.tenths(game.trail.river[0]), game.view().lines[2])

    def test_walking_away_and_back(self):
        driver = river_driver()
        game = driver.game
        driver.press("back")
        self.assertEqual((game.screen, game.trail.at), ("roam", tm.MERGE))
        driver.press("select")
        self.assertEqual(game.screen, "river")

    def test_select_mid_step_back_onto_the_dock(self):
        driver = river_driver()
        game = driver.game
        trail = game.trail
        trail.rng = QuietRng()
        driver.press("back")
        x0, y0 = trail.x, trail.y
        for dx, dy, name in STEP_NAMES:
            if tm.walkable(x0 + dx, y0 + dy, trail.deployed) and tm.stop_at(x0 + dx, y0 + dy) < 0:
                break
        else:
            self.fail("no way off the dock")
        driver.frame(pressed=(name,), held=(name,))
        for _ in range(20):
            if game.walk is None:
                break
            driver.frame()
        self.assertEqual((game.screen, trail.x, trail.y, trail.at), ("roam", x0 + dx, y0 + dy, -1))
        home = name_of(-dx, -dy)
        driver.frame(pressed=(home,), held=(home,))
        driver.frame(pressed=("select",))
        self.assertEqual(game.screen, "roam")
        self.assertIsNotNone(game.walk)
        for _ in range(20):
            if game.screen != "roam":
                break
            driver.frame()
        self.assertEqual((game.screen, game.cursor, trail.at, game.want_menu), ("river", 0, tm.MERGE, False))
        driver.press("back")
        driver.frame()
        self.assertEqual((game.screen, trail.at), ("roam", tm.MERGE))

    def test_ferry_crossing(self):
        driver = river_driver()
        game = driver.game
        credits = game.trail.supplies["credits"]
        driver.pick("Ask Copilot (ferry)")
        view = game.view()
        self.assertEqual((game.screen, view.kind, view.title), ("crossing", "crossing", "Merge Conflict River"))
        self.assertEqual((view.lines, view.hint, view.progress), (("Ask Copilot (ferry)",), "SELECT skip", 0.0))
        self.assertEqual(view.data[:2], (tm.MERGE, tl.FERRY))
        self.assertTrue(game.trail.deployed & tm.deployed_bit(tm.MERGE))
        self.assertEqual(game.trail.supplies["credits"], credits - 40)
        frames = 0
        while game.screen == "crossing":
            driver.frame(dt=250)
            frames += 1
        self.assertEqual(frames, 8)
        self.assertEqual((game.screen, game.card_after, game.card_back), ("event", "roam", "roam"))
        self.assertTrue(game.save["run"]["deployed"] & tm.deployed_bit(tm.MERGE))
        finish_cards(driver)
        self.assertEqual((game.screen, game.trail.at), ("roam", -1))

    def test_skipping_the_crossing(self):
        driver = river_driver()
        game = driver.game
        driver.pick("Ask Copilot (ferry)")
        driver.press("select")
        self.assertEqual((game.screen, game.card_after), ("event", "roam"))

    def test_a_fatal_crossing(self):
        driver = river_driver()
        game = driver.game
        trail = game.trail
        trail.cross = lambda option: (kill_all(trail), False)
        driver.pick("YOLO deploy (ford)")
        self.assertEqual((game.screen, game.card_title, game.card_after),
                         ("event", "Merge Conflict River", "tombstone"))
        self.assertEqual(game.card_lines[-1], "Nobody is left to finish the trail.")
        self.assertTrue(game.over)
        self.assertIsNone(game.save["run"])
        finish_cards(driver)
        self.assertEqual((game.screen, game.record[1]), ("tombstone", tl.CAUSE_EXHAUSTION))

    def test_lights_out_at_the_river(self):
        driver = river_driver()
        game = driver.game
        lights_out(driver)
        self.assertEqual((game.screen, game.camp_origin), ("camp", "river"))
        light_for(driver, 40000, 2000)
        self.assertEqual(game.screen, "river")


class EndingFlowTests(unittest.TestCase):
    def test_dying_in_camp(self):
        driver = in_menu()
        game = driver.game
        doom(game.trail)
        driver.pick("Make camp and rest")
        for _ in range(80):
            if game.screen != "camp":
                break
            driver.frame(dt=100)
        self.assertEqual((game.screen, game.card_title, game.card_after, game.card_back),
                         ("event", "Dark Mode Camp", "tombstone", "camp"))
        self.assertEqual(game.card_lines[-1], "Nobody is left to finish the trail.")
        self.assertEqual(len(game.card_lines), len(tl.PARTY) + 1)
        self.assertEqual((game.over, game.save["run"], game.record[1]), (True, None, tl.CAUSE_WITHDRAWAL))
        self.assertIs(game.save["tombstones"][-1], game.record)
        finish_cards(driver)
        view = game.view()
        self.assertEqual((game.screen, view.kind, view.title), ("tombstone", "tombstone", "Game over"))
        self.assertEqual(view.lines, tl.tombstone_lines(game.record))
        self.assertEqual((view.hint, view.progress), ("L/R epitaph  SELECT beam  BACK title", None))

    def test_dying_on_a_hunt(self):
        driver = in_menu()
        game = driver.game
        trail = game.trail
        driver.pick("Bug & AI Slop Hunt")
        trail.finish_hunt = lambda hunt: kill_all(trail)
        driver.press("back")
        self.assertEqual((game.screen, game.card_title, game.card_after),
                         ("event", "Bug & AI Slop Hunt", "tombstone"))
        self.assertEqual(game.card_lines[-1], "Nobody is left to finish the trail.")
        self.assertEqual((game.over, game.record[1], game.hunt), (True, tl.CAUSE_EXHAUSTION, None))
        finish_cards(driver)
        self.assertEqual(game.screen, "tombstone")

    def test_epitaphs_wrap_both_ways(self):
        driver = in_menu()
        game = driver.game
        kill_all(game.trail)
        game.game_over()
        game.go("tombstone")
        game.record[2] = 0
        driver.press("left")
        self.assertEqual(game.record[2], len(tl.EPITAPHS) - 1)
        self.assertEqual(game.view().lines[3], '"' + tl.EPITAPHS[-1] + '"')
        driver.press("right")
        self.assertEqual(game.save["tombstones"][-1][2], 0)
        writes = driver.writes
        driver.press("back")
        self.assertEqual((game.screen, driver.writes), ("title", writes + 1))

    def test_victory_screen(self):
        driver = roaming()
        game = driver.game
        game.win()
        game.go("victory")
        view = game.view()
        score = game.trail.score()
        self.assertEqual((view.kind, view.title, view.hint, view.progress),
                         ("victory", "You made it to the Mainstage!", "SELECT beam victory  BACK title", None))
        self.assertEqual(view.lines, ("Final score: %s  New best!" % tl.commas(score), "5 of 5 made it in 1 day.",
                                      "Creative Director @wmarkus, score x1"))
        self.assertEqual((game.save["best"], game.save["victories"], game.save["run"]), (score, 1, None))
        lit = game.lights()
        self.assertEqual(lit[(game.now // 250) % 4], 0.4)
        self.assertEqual(sorted(lit), [0.1, 0.1, 0.1, 0.4])
        driver.press("back")
        self.assertEqual(game.screen, "title")

    def test_a_lower_score_is_not_a_new_best(self):
        save = tl.default_save()
        save["best"] = 10 ** 6
        driver = roaming(save=save, role=2)
        game = driver.game
        game.win()
        game.go("victory")
        lines = game.view().lines
        self.assertEqual(lines[0], "Final score: " + tl.commas(game.trail.score()))
        self.assertEqual(lines[2], "ATC Control Lead @kdaigle, score x3")
        self.assertEqual(game.save["best"], 10 ** 6)


class ShutdownTests(unittest.TestCase):
    def test_shutdown_mid_step_saves_a_whole_tile(self):
        driver = roaming()
        game = driver.game
        driver.frame(pressed=("up",), held=("up",))
        self.assertIsNotNone(game.walk)
        writes = driver.writes
        game.shutdown()
        run = game.save["run"]
        self.assertIsNone(game.walk)
        self.assertEqual((run["x"], run["y"], run["steps"]), (tm.START[0], tm.START[1] - 1, tm.STEPS_PER_TILE))
        self.assertEqual(driver.writes, writes + 1)

    def test_shutdown_while_resting_saves_the_run(self):
        driver = roaming()
        game = driver.game
        game.trail.supplies["lgtm"] = 17
        game.shutdown()
        self.assertEqual(game.save["run"]["lgtm"], 17)

    def test_shutdown_on_the_title_just_persists(self):
        driver = Driver()
        game = driver.game
        game.shutdown()
        self.assertEqual((driver.writes, game.save["run"]), (1, None))

    def test_shutdown_after_game_over_keeps_no_run(self):
        driver = in_menu()
        game = driver.game
        kill_all(game.trail)
        game.game_over()
        writes = driver.writes
        game.shutdown()
        self.assertEqual((driver.writes, game.save["run"]), (writes + 1, None))

    def test_shutdown_finishes_a_fatal_step(self):
        driver = roaming()
        game = driver.game
        doom(game.trail)
        driver.frame(pressed=("up",), held=("up",))
        self.assertEqual((game.screen, game.over), ("roam", False))
        game.shutdown()
        self.assertEqual((game.over, game.walk, game.save["run"]), (True, None, None))
        self.assertEqual(game.save["tombstones"], [game.record])
        self.assertEqual((game.record[0], game.record[1]), (tm.STEPS_PER_TILE, tl.CAUSE_WITHDRAWAL))


def graveyard_save(count):
    save = tl.default_save()
    for index in range(count):
        save["tombstones"].append(tl.tombstone_record(100 * (index + 1), index % len(tl.CAUSES), index, index % 3, 0))
    return save


def in_graveyard(count=3, link=_MISSING):
    driver = Driver(save=graveyard_save(count), link=link)
    driver.pick("Visit the graveyard")
    if driver.game.screen != "graveyard":
        raise AssertionError(driver.game.screen)
    return driver


class BeamFlowTests(unittest.TestCase):
    def test_graveyard_browses_newest_first_and_wraps(self):
        driver = in_graveyard()
        game = driver.game
        stones = game.save["tombstones"]
        view = game.view()
        self.assertEqual((view.kind, view.title, view.hint), ("tombstone", "Graveyard 3/3", "L/R browse  SELECT beam  BACK title"))
        self.assertEqual(view.lines, tl.tombstone_lines(stones[2]))
        self.assertEqual(view.lines[0], "Step 300")
        driver.press("right")
        self.assertEqual(game.view().title, "Graveyard 1/3")
        driver.press("left")
        driver.press("left")
        self.assertEqual(game.view().title, "Graveyard 2/3")
        driver.press("select")
        packet = tl.decode_packet(driver.link.sent[-1])
        self.assertEqual(tl.tombstone_from_packet(packet), stones[1][:4] + [1])
        self.assertEqual((game.current_toast(), game.save["beamed"]), ("No IR: tombstone beam simulated.", 1))
        driver.press("back")
        self.assertEqual(game.screen, "title")

    def test_an_empty_graveyard(self):
        driver = Driver()
        game = driver.game
        option = option_of(game.view(), "Visit the graveyard")
        self.assertEqual(option[1:], ("0", False))
        driver.pick("Visit the graveyard")
        self.assertEqual((game.screen, game.view().note), ("title", "No tombstones yet. Give it time."))
        game.go("graveyard")
        view = game.view()
        self.assertEqual((view.kind, view.title, view.lines, view.hint),
                         ("tombstone", "Graveyard", ("No tombstones yet.",), "BACK title"))
        driver.frame()
        self.assertEqual(game.screen, "title")

    def test_beaming_without_ir(self):
        driver = in_graveyard(link=None)
        game = driver.game
        writes = driver.writes
        driver.press("select")
        self.assertEqual((game.current_toast(), game.save["beamed"], driver.writes),
                         ("IR is not available on this badge.", 0, writes))
        self.assertEqual((game.nonce(), game.beam_progress(), game.view().progress), (0, None, None))

    def test_beaming_over_ir(self):
        driver = in_graveyard(link=FakeLink(transmit=True))
        game = driver.game
        driver.press("select")
        self.assertEqual((game.current_toast(), game.save["beamed"]), ("Beaming your tombstone over IR.", 1))
        packet = tl.decode_packet(driver.link.sent[0])
        self.assertEqual((packet["kind"], packet["nonce"], packet["value"]), (tl.KIND_TOMBSTONE, FakeLink.nonce, 300))

    def test_one_beam_at_a_time(self):
        driver = in_graveyard()
        game = driver.game
        driver.link.busy = True
        driver.press("select")
        self.assertEqual((game.current_toast(), driver.link.sent), ("Still beaming. Hold steady.", []))
        self.assertEqual((game.beam_progress(), game.view().progress), (0.25, 0.25))
        lit = game.lights()
        self.assertEqual(lit[(game.now // 120) % 4], 0.5)
        self.assertEqual(sorted(lit), [0.05, 0.05, 0.05, 0.5])
        driver.link.busy = False
        driver.press("select")
        self.assertEqual(len(driver.link.sent), 1)

    def test_receiving_beams(self):
        driver = Driver()
        game = driver.game
        record = tl.tombstone_record(1234, 2, 3, 1, False)
        tomb = tl.decode_packet(tl.tombstone_packet(9, record))
        win = tl.decode_packet(tl.victory_packet(9, 4321, 3, 12, 2))
        self.assertTrue(game.receive([tomb, win]))
        self.assertEqual(game.save["tombstones"], [[1234, 2, 3, 1, 1]])
        self.assertEqual([toast[0] for toast in game.toasts],
                         ["Tombstone beamed in: step 1,234.", "Victory beamed in: 4,321 points!"])
        self.assertEqual((game.save["met"], driver.writes), (1, 1))
        self.assertTrue(game.receive([tomb]))
        self.assertEqual((len(game.save["tombstones"]), game.save["met"]), (1, 2))
        self.assertEqual(option_of(game.view(), "Visit the graveyard")[1:], ("1", True))

    def test_junk_is_ignored(self):
        driver = Driver()
        game = driver.game
        junk = {"kind": 9, "nonce": 1, "value": 5, "a": 0, "b": 0, "c": 0}
        self.assertFalse(game.receive([]))
        self.assertFalse(game.receive([junk, None]))
        self.assertEqual((game.save["met"], driver.writes, game.toasts), (0, 0, []))

    def test_received_tombstones_are_capped(self):
        driver = Driver()
        game = driver.game
        packets = []
        for index in range(tl.MAX_TOMBSTONES + 3):
            packets.append(tl.decode_packet(tl.tombstone_packet(index, tl.tombstone_record(index + 1, 0, 0, 0, 0))))
        game.receive(packets)
        stones = game.save["tombstones"]
        self.assertEqual(len(stones), tl.MAX_TOMBSTONES)
        self.assertEqual((stones[0][0], stones[-1][0]), (4, tl.MAX_TOMBSTONES + 3))
        self.assertEqual(len(game.toasts), 3)


class ToastLightPersistTests(unittest.TestCase):
    def test_toasts_expire(self):
        driver = Driver()
        game = driver.game
        game.toast("Hello")
        driver.frame(dt=tg.TOAST_MS - 500)
        self.assertEqual(game.current_toast(), "Hello")
        driver.frame(dt=600)
        self.assertEqual((game.current_toast(), game.toasts), (None, []))

    def test_three_toasts_at_most(self):
        game = Driver().game
        for text in ("a", "b", "c", "d"):
            game.toast(text)
        self.assertEqual([toast[0] for toast in game.toasts], ["b", "c", "d"])
        self.assertEqual(game.current_toast(), "d")

    def test_menu_key_switches_monitors_anywhere(self):
        driver = roaming()
        game = driver.game
        writes = driver.writes
        driver.press("menu")
        self.assertEqual((game.visual(), game.screen, game.current_toast()), (1, "roam", "Monitor: Green"))
        self.assertEqual(driver.writes, writes + 1)
        driver.press("select")
        driver.press("menu")
        self.assertEqual((game.visual(), game.screen, game.current_toast()), (0, "menu", "Monitor: Color"))

    def test_long_frames_are_clamped(self):
        driver = roaming()
        game = driver.game
        driver.frame(pressed=("up",), held=("up",))
        driver.frame(held=("up",), dt=60000)
        self.assertEqual(game.walk[3], tg.MAX_DT)
        driver.frame(held=("up",), dt=-500)
        self.assertEqual(game.walk[3], tg.MAX_DT)

    def test_failed_saves_are_survivable(self):
        driver = roaming()
        game = driver.game
        saves = game.saves

        def broken(data):
            raise OSError(28, "No space left on device")

        game.persist_fn = broken
        game.persist()
        driver.press("select")
        driver.pick("Save and quit")
        self.assertEqual((game.saves, game.screen), (saves, "title"))
        self.assertIsNotNone(game.save["run"])

    def test_running_without_storage(self):
        driver = roaming(persist=False)
        game = driver.game
        step_once(driver)
        finish_cards(driver)
        game.shutdown()
        self.assertEqual((game.saves, driver.writes), (0, 0))
        self.assertEqual(game.save["run"]["steps"], tm.STEPS_PER_TILE)

    def test_case_lights_follow_the_game(self):
        self.assertEqual(Driver().game.lights(), (0, 0, 0, 0))
        driver = roaming()
        game = driver.game
        self.assertEqual(game.lights(), (0, 0, 0, 0))
        driver.press("back")
        for _ in range(10):
            driver.frame()
            level = 0.3 if (game.now // 250) & 1 else 0.1
            self.assertEqual(game.lights(), (level, level, level, level))
        driver.press("select")
        self.assertEqual(game.lights(), (0, 0, 0, 0))
        driver.pick("Make camp and rest")
        seen = set()
        for _ in range(30):
            driver.frame()
            lit = game.lights()
            self.assertEqual((lit[1], lit[2], lit[3]), (lit[0] * 0.6, lit[0] * 0.6, lit[0]))
            self.assertTrue(0.08 <= lit[0] <= 0.17)
            seen.add(lit[0])
        self.assertGreater(len(seen), 2)


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


class FakeImageModule:
    """The image global: constants plus image(w, h), which must stay screen-sized or smaller."""
    OFF = "off"
    X2 = "x2"
    EVEN_ODD = "even-odd"
    NON_ZERO = "non-zero"

    def __init__(self, log):
        self.log = log
        self.fail = None

    def __call__(self, width, height):
        if self.fail is not None:
            raise self.fail
        self.log.images.append((width, height))
        if not is_int(width) or not is_int(height) or width <= 0 or height <= 0:
            self.log.bad("image(%r, %r)" % (width, height))
        elif width > 320 or height > 240:
            self.log.bad("image(%d, %d) is larger than the screen" % (width, height))
        return FakeSurface(self.log, width, height)


class FakeColorModule:
    def __init__(self, log):
        self.log = log

    def rgb(self, r, g, b, a=255):
        self.log.colors += 1
        for value in (r, g, b, a):
            if not is_int(value) or not 0 <= value <= 255:
                self.log.bad("color.rgb(%r, %r, %r, %r)" % (r, g, b, a))
                break
        return FakePen(r, g, b)


class FakeShapeModule:
    def __init__(self, log):
        self.log = log

    def circle(self, x, y, r):
        if not is_int(r) or r <= 0:
            self.log.bad("circle radius %r" % (r,))
        return FakeShape(self.log, "circle", (x, y, r))

    def line(self, x0, y0, x1, y1, width):
        return FakeShape(self.log, "line", (x0, y0, x1, y1, width))

    def rounded_rectangle(self, x, y, w, h, r):
        return FakeShape(self.log, "rounded_rectangle", (x, y, w, h, r))


def badge_globals(log):
    return {
        "screen": FakeSurface(log, 320, 240, is_screen=True),
        "image": FakeImageModule(log),
        "color": FakeColorModule(log),
        "shape": FakeShapeModule(log),
        "font": types.SimpleNamespace(teatime=object(), nope=object()),
        "rect": lambda x, y, w, h: FakeBox(log, "rect", (x, y, w, h)),
        "vec2": lambda x, y: FakeBox(log, "vec2", (x, y)),
    }


def install_globals(test, target, values):
    """Patch the badge globals onto one app module for the length of one test."""
    for name, value in values.items():
        if name in vars(target):
            raise AssertionError("%s already defines %s" % (target.__name__, name))
        setattr(target, name, value)
        test.addCleanup(delattr, target, name)


class RenderHelperTests(unittest.TestCase):
    def test_dim_is_about_half_brightness(self):
        self.assertEqual(td.dim((255, 200, 0)), (140, 110, 0))
        self.assertEqual(td.dim((0, 0, 0)), (0, 0, 0))

    def test_scatter_is_deterministic_and_in_bounds(self):
        points = td.scatter(40, 11, 6, 2, 300, 92)
        self.assertIsInstance(points, tuple)
        self.assertEqual(points, td.scatter(40, 11, 6, 2, 300, 92))
        self.assertEqual([point[2] for point in points], list(range(40)))
        for x, y, _index in points:
            self.assertTrue(6 <= x < 306 and 2 <= y < 94, (x, y))
        self.assertNotEqual(points, td.scatter(40, 12, 6, 2, 300, 92))
        self.assertGreater(len({x // 30 for x, _y, _index in points}), 5)

    def test_link_status_never_raises(self):
        game = types.SimpleNamespace(link=None)
        self.assertEqual(td.link_status(game), "IR off")

        class Broken:
            def status(self):
                raise OSError("gone")

        game.link = Broken()
        self.assertEqual(td.link_status(game), "IR off")
        link = hw.IrLink(5)
        game.link = link
        self.assertEqual(td.link_status(game), "IR off")
        link.tx = object()
        link.listening = True
        self.assertEqual(td.link_status(game), "IR ready")


MAP_LABELS = frozenset(label[0] for label in tm.LABELS if not label[3])


class BeamLink(FakeLink):
    """A transmitting FakeLink whose beam lasts a few frames."""
    FRAMES = 6

    def __init__(self):
        FakeLink.__init__(self, transmit=True)
        self.left = 0

    def status(self):
        return "IR ready"

    def beam(self, packet):
        FakeLink.beam(self, packet)
        self.left = self.FRAMES
        return True

    def tick(self):
        if self.left > 0:
            self.left -= 1

    def sending(self):
        return self.left > 0

    def progress(self):
        return 1.0 - self.left / float(self.FRAMES)


class RenderTests(unittest.TestCase):
    """Every screen drawn after every frame, through strict fakes of the badge globals."""

    def setUp(self):
        self.log = DrawLog()
        self.fakes = badge_globals(self.log)
        install_globals(self, td, self.fakes)
        self.screen = self.fakes["screen"]
        self.renderer = td.Renderer()
        self.visual = 0
        self.kinds = set()
        original = Driver.frame
        test = self

        def frame(driver, *args, **kw):
            view = original(driver, *args, **kw)
            tick = getattr(driver.link, "tick", None)
            if tick is not None:
                tick()
            test.render(driver.game)
            return view

        patcher = mock.patch.object(Driver, "frame", frame)
        patcher.start()
        self.addCleanup(patcher.stop)

    def render(self, game):
        game.save["visual"] = self.visual
        screen = self.screen
        screen.texts = []
        screen.off_screen = []
        screen.calls = 0
        self.renderer.draw(game)
        kind = game.view().kind
        self.kinds.add(kind)
        if self.renderer.failed:
            self.fail("the %s screen failed: %r" % (kind, self.renderer.failed))
        if self.log.problems:
            self.fail("the %s screen: %s" % (kind, self.log.problems))
        if not screen.calls:
            self.fail("the %s screen drew nothing" % kind)
        # Only the venue's horizontal map labels may scroll past the camera edge.
        stray = [entry for entry in screen.off_screen if entry[0] not in MAP_LABELS]
        if stray:
            self.fail("the %s screen has text off the edge: %r" % (kind, stray))
        return kind

    def beam_and_wait(self, driver, what):
        link = BeamLink()
        driver.link = link
        driver.game.link = link
        driver.press("select")
        self.assertEqual(driver.game.current_toast(), "Beaming your %s over IR." % what)
        driver.press("select")
        self.assertEqual(driver.game.current_toast(), "Still beaming. Hold steady.")
        for _ in range(8):
            driver.frame()
        self.assertFalse(link.sending())
        self.assertEqual(len(link.sent), 1)

    def tour(self, visual):
        self.visual = visual
        # The title: an empty graveyard, both ways out of the help pages, the sensor switch.
        driver = Driver(5)
        game = driver.game
        driver.frame()
        driver.pick("Visit the graveyard")
        self.assertEqual((game.screen, game.note), ("title", "No tombstones yet. Give it time."))
        driver.pick("Learn how to play")
        for _ in range(len(tg.HELP)):
            self.assertEqual(game.screen, "help")
            driver.press("right")
        self.assertEqual(game.screen, "title")
        driver.pick("Learn how to play")
        driver.press("back")
        self.assertEqual(game.screen, "title")
        driver.pick("Dark Mode Camp sensor")
        self.assertIs(game.save["auto_camp"], False)
        # A whole run to the Mainstage, then beaming the victory.
        driver = play(31676, role=1, explore=True)
        self.assertEqual(driver.game.screen, "victory")
        self.beam_and_wait(driver, "victory")
        driver.press("back")
        self.assertEqual(driver.game.screen, "title")
        # Dying in camp, choosing an epitaph and beaming the tombstone.
        driver = in_menu()
        game = driver.game
        doom(game.trail)
        driver.pick("Make camp and rest")
        for _ in range(80):
            if game.screen != "camp":
                break
            driver.frame(dt=100)
        finish_cards(driver)
        self.assertEqual(game.screen, "tombstone")
        driver.press("right")
        self.beam_and_wait(driver, "tombstone")
        driver.press("back")
        self.assertEqual(game.screen, "title")
        # Browsing and beaming from the graveyard.
        driver = in_graveyard(3, link=BeamLink())
        driver.press("left")
        driver.press("select")
        for _ in range(8):
            driver.frame()
        driver.press("back")
        self.assertEqual(driver.game.screen, "title")
        # Dark Mode Camp from the light sensor, then daylight.
        driver = roaming()
        lights_out(driver)
        self.assertEqual(driver.game.screen, "camp")
        self.assertEqual(self.renderer.pen_key, visual + 2)
        light_for(driver, 40000, 3000)
        self.assertEqual(driver.game.screen, "roam")
        self.assertEqual(self.renderer.pen_key, visual)
        # A shake-powered turbo sprint along the guide.
        driver = roaming()
        self.assertGreater(shake(driver), 0)
        self.assertGreater(driver.game.trail.turbo_days, 0)
        held = None
        for _ in range(40):
            name = guide_direction(driver.game.trail)
            if driver.game.screen != "roam" or name is None:
                break
            driver.frame(pressed=(name,) if name != held else (), held=(name,))
            held = name
        self.assertEqual(set(VIEW_KINDS) - self.kinds, set())
        self.assertEqual(set(self.renderer.pen_sets), {visual, visual + 2})
        self.assertEqual(self.log.colors, sum(len(pens) for pens in self.renderer.pen_sets.values()))
        for cache in (self.renderer.widths, self.renderer.wraps, self.renderer.fits):
            self.assertLessEqual(len(cache), td.CACHE_LIMIT + 1)
        # Offscreen images are cached (one title banner, one venue chart), never made per frame.
        self.assertLessEqual(len(self.log.images), 4)
        return driver

    def test_every_screen_on_the_color_monitor(self):
        self.tour(0)

    def test_every_screen_on_the_green_monitor(self):
        self.tour(1)

    def test_a_failing_screen_falls_back_and_reports_once(self):
        game = Driver(5).game

        def broken(renderer, view, game):
            raise ValueError("boom")

        with mock.patch.object(td.Renderer, "draw_title", broken), \
                mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            for _ in range(3):
                self.renderer.draw(game)
        self.assertIn("boom", self.renderer.failed["title"])
        self.assertEqual(out.getvalue().count("the title screen failed"), 1)
        self.assertIn("The Octocat Trail", self.screen.texts)
        self.assertEqual(self.log.problems, [])

    def test_the_nope_font_stands_in_for_teatime(self):
        nope = object()
        td.font = types.SimpleNamespace(nope=nope)
        Driver(5).frame()
        self.assertIs(self.renderer.face, nope)
        self.assertIs(self.screen.font, nope)

    def test_screens_still_draw_when_images_cannot_be_allocated(self):
        self.fakes["image"].fail = MemoryError
        driver = in_menu()
        self.assertIsNone(self.renderer.banner)
        driver.pick("Look at the venue map")
        self.assertEqual(driver.game.view().kind, "map")
        self.assertIsNone(self.renderer.chart)
        self.assertEqual(self.log.images, [])
        Driver(5).frame()
        self.assertIsNone(self.renderer.banner)
        self.assertIn("The Octocat Trail", self.screen.texts)

    def test_the_venue_chart_is_cached_only_while_the_map_is_open(self):
        driver = in_menu()
        before = len(self.log.images)
        driver.pick("Look at the venue map")
        self.assertEqual(self.log.images[before:], [(td.CHART_W, td.CHART_H)])
        chart = self.renderer.chart
        self.assertIsNotNone(chart)
        driver.frame()
        driver.frame()
        self.assertIs(self.renderer.chart, chart)
        self.assertEqual(len(self.log.images), before + 1)
        driver.press("select")
        self.assertNotEqual(driver.game.view().kind, "map")
        self.assertIsNone(self.renderer.chart)

    def test_the_title_banner_is_drawn_once_and_reused(self):
        driver = Driver(5)
        for _ in range(4):
            driver.frame()
        self.assertEqual(len(self.log.images), 1)
        width, height = self.log.images[0]
        self.assertEqual(height, td.ROW + 1)
        self.assertLessEqual(2 * width, td.W)
        banner = self.renderer.banner
        driver.press("down")
        self.assertIs(self.renderer.banner, banner)


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


class FakeState:
    """badgeware.State: load() fills the given dict in place, save() keeps a JSON copy."""

    def __init__(self, stored=None, fail_save=False):
        self.stored = stored
        self.fail_save = fail_save
        self.loads = []
        self.saves = []

    def load(self, key, data):
        self.loads.append(key)
        if self.stored is not None:
            data.update(json.loads(json.dumps(self.stored)))
        return True

    def save(self, key, data):
        if self.fail_save:
            raise OSError("flash full")
        self.saves.append((key, json.loads(json.dumps(data))))


LAUNCH_BUTTONS = (("up", 11), ("down", 12), ("left", 13), ("right", 14), ("select", 15), ("back", 16),
                  ("menu", 17))


class LauncherTests(unittest.TestCase):
    """Runs the real __init__.py with fake runtime globals, State and IR."""

    def setUp(self):
        self.runs = []

    def launch(self, ir=True, state=None, dirs=(), device=None, machine=None, rule=_MISSING):
        app = load_modules(prefix="octocat_trail_launch_")
        self.log = DrawLog()
        fakes = badge_globals(self.log)
        install_globals(self, app["trail_draw"], fakes)
        self.screen = fakes["screen"]
        if ir:
            modules, self.ir_log = fake_ir()
        else:
            modules = dict(NO_IR)
            modules["badgeware"] = module("badgeware")
            self.ir_log = None
        if state is not None:
            modules["badgeware"].State = state
        modules["machine"] = machine
        for name in MODULES:
            modules[name] = app[name]
        patch = patched_modules(modules)
        patch.__enter__()
        self.addCleanup(patch.__exit__, None, None, None)
        chdir = mock.patch("os.chdir")
        self.chdir = chdir.start()
        self.addCleanup(chdir.stop)
        saved_path = sys.path[:]
        self.addCleanup(sys.path.__setitem__, slice(None), saved_path)
        self.screen.fill_rule = "non-zero" if rule is _MISSING else rule
        self.device = device if device is not None else LauncherBadge()
        env = dict(fakes)
        env.update({"__name__": "octocat_trail_launcher", "badge": self.device, "run": self.runs.append,
                    "is_dir": lambda path: path in dirs, "HIRES": 1, "VSYNC": 2})
        for name, code in LAUNCH_BUTTONS:
            env["BUTTON_" + name.upper()] = code
        path = APP / "__init__.py"
        exec(compile(path.read_text(), str(path), "exec"), env)
        return env

    def step(self, env, *names):
        device = self.device
        device.down = {code for name, code in LAUNCH_BUTTONS if name in names}
        device.ticks += 40
        env["update"]()
        device.down = set()

    def pick(self, env, prefix):
        game = env["game"]
        for _ in range(12):
            view = game.view()
            if view.options[view.cursor][0].startswith(prefix):
                self.step(env, "select")
                return
            self.step(env, "down")
        self.fail("no option %r" % prefix)

    def test_a_full_launch_with_ir_state_and_sensors(self):
        state = FakeState({"visual": 1, "best": 1234})
        env = self.launch(state=state)
        device = self.device
        game = env["game"]
        link = env["link"]
        self.assertEqual(self.runs, [env["update"]])
        self.assertEqual(device.modes, [3])
        self.assertIsNone(device.default_clear)
        self.assertEqual((self.screen.fill_rule, self.screen.antialias), ("even-odd", "off"))
        self.assertEqual((game.save["visual"], game.save["best"]), (1, 1234))
        self.assertEqual(state.loads, ["octocat_trail"])
        self.assertEqual([descriptor.ADDRESS for descriptor in self.ir_log["bound"]], [0x54])
        self.assertEqual(self.ir_log["made"], [(16, 0, 1)])
        self.assertEqual(self.ir_log["started"], [(0, 1)])
        self.assertEqual(link.status(), "IR ready")
        self.chdir.assert_not_called()

        self.step(env)
        self.assertEqual(env["renderer"].failed, {})
        self.assertEqual(self.log.problems, [])
        self.assertTrue(any("Start a new run" in text for text in self.screen.texts))
        self.assertEqual(device.lights[-1], (0.0, 0.0, 0.0, 0.0))

        device.down = {code for _name, code in LAUNCH_BUTTONS}
        device.holding = set(device.down)
        keys = env["read_keys"]()
        self.assertEqual(list(keys.pressed), [name for name, _code in LAUNCH_BUTTONS])
        self.assertEqual(list(keys.held), ["up", "down", "left", "right"])
        device.key_error = OSError("touch controller")
        keys = env["read_keys"]()
        self.assertEqual((list(keys.pressed), list(keys.held)), ([], []))
        device.down = set()
        device.holding = set()
        device.key_error = None

        # A tombstone beamed in from another badge running the app.
        other = link.nonce % 126 + 1
        for byte in tl.tombstone_packet(other, tl.tombstone_record(1234, 1, 2, 0, False)):
            link.binding.on_any(byte)
        self.step(env)
        self.assertEqual(game.current_toast(), "Tombstone beamed in: step 1,234.")
        self.assertEqual(game.save["tombstones"], [[1234, 1, 2, 0, 1]])
        self.assertEqual(game.save["met"], 1)
        self.assertEqual(state.saves[-1][0], "octocat_trail")
        self.assertEqual(state.saves[-1][1]["tombstones"], [[1234, 1, 2, 0, 1]])

        # Beaming it back: one 77 ms NEC frame per update, the packet three times.
        self.pick(env, "Visit the graveyard")
        self.assertEqual(game.screen, "graveyard")
        sent = self.ir_log["sent"]
        self.step(env, "select")
        self.assertEqual(sent, [])
        self.assertEqual(game.current_toast(), "Beaming your tombstone over IR.")
        self.assertIn(0.5, device.lights[-1])
        packet = tl.tombstone_packet(link.nonce, [1234, 1, 2, 0, 1])
        total = len(packet) * tl.BEAM_REPEATS
        self.assertEqual(total, 27)
        for count in range(1, total + 1):
            self.step(env)
            self.assertEqual(len(sent), count)
        self.assertEqual(sent, [(0x54, byte) for byte in packet] * tl.BEAM_REPEATS)
        self.assertEqual(device.lights[-1], (0.0, 0.0, 0.0, 0.0))
        self.step(env)
        self.assertEqual(len(sent), total)
        self.assertEqual(game.save["beamed"], 1)
        self.assertEqual(self.log.problems, [])

        saves = len(state.saves)
        env["on_exit"]()
        self.assertEqual((self.ir_log["stopped"], self.ir_log["closed"]), (1, 1))
        self.assertEqual(device.lights[-1], (0,))
        self.assertEqual(device.default_clear, "default-clear")
        self.assertEqual(self.screen.fill_rule, "non-zero")
        self.assertEqual(len(state.saves), saves + 1)

    def test_a_simulator_launch_degrades_without_crashing(self):
        error = RuntimeError("unsupported")
        device = LauncherBadge(imu=error, light=error, lights_error=error)
        env = self.launch(ir=False, device=device, rule=None)
        link = env["link"]
        self.assertEqual(link.status(), "IR off")
        self.assertIsNone(link.tx)
        self.assertIsNone(env["sensors"].light())
        seen = []
        for names in ((), ("menu",), ("select",), ("select",), ("select",), ("down",), ()):
            self.step(env, *names)
            seen.append(env["game"].screen)
        self.assertEqual(seen[-1], "store")
        self.assertIn("role", seen)
        self.assertEqual(env["game"].save["visual"], 1)
        self.assertEqual(env["renderer"].failed, {})
        self.assertEqual(self.log.problems, [])
        self.assertEqual(env["game"].saves, 0)
        self.assertEqual(device.lights, [])
        env["on_exit"]()
        self.assertEqual(self.screen.fill_rule, "even-odd")
        self.assertEqual(device.default_clear, "default-clear")

    def test_a_failed_state_save_is_not_counted(self):
        state = FakeState(fail_save=True)
        env = self.launch(state=state)
        self.step(env, "menu")
        self.assertEqual(env["game"].save["visual"], 1)
        self.assertEqual((state.saves, env["game"].saves), ([], 0))
        env["on_exit"]()

    def test_the_launcher_finds_its_folder_and_restores_sys_path(self):
        before = sys.path[:]
        env = self.launch(dirs=("/apps/octocat_trail", "/system/apps/octocat_trail"))
        self.chdir.assert_called_once_with("/system/apps/octocat_trail")
        self.assertEqual(sys.path[0], "/system/apps/octocat_trail")
        env["on_exit"]()
        self.doCleanups()
        self.assertEqual(sys.path, before)
        self.runs = []
        env = self.launch()
        self.chdir.assert_not_called()
        self.assertEqual(sys.path, before)
        self.assertEqual(self.runs, [env["update"]])
        env["on_exit"]()


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

    def test_every_app_module_passes_the_scan(self):
        files = sorted(APP.glob("*.py"))
        self.assertEqual([path.name for path in files], ["__init__.py"] + ["%s.py" % name for name in sorted(MODULES)])
        for path in files:
            with self.subTest(path.name):
                self.assertEqual(scan_source(path.read_text(encoding="utf-8"), path.name), [])

    def test_ordered_tables_are_tuples_or_lists(self):
        tables = ((tl, ("ROLES", "SUPPLIES", "PACES", "RATIONS", "RIVER_OPTIONS", "PARTY", "CAUSES", "EPITAPHS")),
                  (tm, ("STOPS", "LABELS", "BUILDINGS", "PATHS", "TREES", "PARKING", "DOCKS", "FENCES")),
                  (tg, ("HELP", "MONITORS", "DIRS", "UNITS", "STORE_NAMES")),
                  (td, ("FACADES", "CONFETTI", "BASE", "CHART")),
                  (ta, ("PALETTE",)))
        for mod, names in tables:
            for name in names:
                with self.subTest(name):
                    value = getattr(mod, name)
                    self.assertIsInstance(value, (tuple, list))
                    self.assertTrue(value)

    def test_no_module_constant_is_a_dict_or_set(self):
        # Dict and set iteration is hash-ordered on the badge, so constants stay sequences.
        for mod in (tm, tl, ta, tg, hw, td):
            for name, value in vars(mod).items():
                if name.isupper():
                    with self.subTest(module=mod.__name__, name=name):
                        self.assertNotIsInstance(value, (dict, set, frozenset))

    def test_beams_only_use_the_trail_address(self):
        self.assertEqual((tl.IR_ADDRESS, hw.TrailBeam.ADDRESS), (0x54, 0x54))
        calls = []
        for path in sorted(APP.glob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "send_addr_cmd":
                    calls.append(path.name)
        self.assertEqual(calls, ["trail_hw.py"])


class PackagingTests(unittest.TestCase):
    """The folder, icon and README that the menu, CI and badgerfactory rely on."""

    def test_the_folder_ships_only_the_app_files(self):
        names = sorted(path.name for path in APP.iterdir()
                       if not path.name.startswith(".") and path.name != "__pycache__")
        expected = sorted(("README.md", "__init__.py", "assets", "icon.png")
                          + tuple("%s.py" % name for name in MODULES))
        self.assertEqual(names, expected)
        shots = sorted(path.name for path in (APP / "assets").iterdir() if not path.name.startswith("."))
        self.assertEqual(shots, ["octocat_trail_screenshot.png"])

    def test_the_screenshot_is_a_320x240_png_shown_in_the_readme(self):
        data = (APP / "assets" / "octocat_trail_screenshot.png").read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        width, height = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
        self.assertEqual((width, height), (320, 240))
        readme = (APP / "README.md").read_text(encoding="utf-8")
        self.assertIn("](assets/octocat_trail_screenshot.png)", readme)

    def test_the_icon_is_a_24x24_png(self):
        data = (APP / "icon.png").read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(data[12:16], b"IHDR")
        width, height = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
        self.assertEqual((width, height), (24, 24))

    def test_the_readme_passes_the_repository_validator(self):
        path = ROOT / ".github" / "scripts" / "validate_app_readmes.py"
        spec = importlib.util.spec_from_file_location("octocat_trail_readme_validator", path)
        validator = importlib.util.module_from_spec(spec)
        with mock.patch.object(sys, "dont_write_bytecode", True):
            spec.loader.exec_module(validator)
        self.assertIsNone(validator.check_app(APP))
        sentence = validator.first_sentence(validator.first_paragraph(APP / "README.md"))
        self.assertTrue(sentence.startswith("Lead the Studio party"), sentence)

    def test_the_readme_matches_the_code(self):
        text = (APP / "README.md").read_text(encoding="utf-8")
        lines = text.splitlines()
        self.assertEqual(lines[0], "# The Octocat Trail")
        self.assertTrue(lines[2].startswith("Lead the Studio party") and lines[2].endswith("."), lines[2])
        tree = ast.parse((APP / "__init__.py").read_text(encoding="utf-8"))
        keys = [node.value.value for node in tree.body if isinstance(node, ast.Assign)
                and [getattr(target, "id", None) for target in node.targets] == ["STATE_KEY"]]
        self.assertEqual(keys, [APP.name])
        self.assertEqual(tl.BEAM_REPEATS, 3)
        claims = (
            "under `%s`" % APP.name,
            "0x%02X" % tl.IR_ADDRESS,
            "%d-byte checksummed packet three times" % tl.PACKET_LEN,
            "up to %d tombstones" % tl.MAX_TOMBSTONES,
            "%d-day sprint" % tl.TURBO_DAYS,
            "every %d days" % tg.SAVE_EVERY_DAYS,
            "heals the party by %d and cures illness, at most once every %d days" % (tl.HEAL_AMOUNT, tl.HEAL_DAYS),
            "Ascii-Motion",
            "GPIO43",
            "GPIO16",
            "only reach badges that are running The Octocat Trail",
        )
        for claim in claims:
            with self.subTest(claim):
                self.assertIn(claim, text)
        self.assertNotIn("0x45", text)


if __name__ == "__main__":
    unittest.main()
