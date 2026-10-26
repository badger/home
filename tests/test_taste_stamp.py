"""Tests for the Taste Stamp & Creative 8-Ball app in badge/apps/taste_stamp.

The app's modules are loaded under unique taste_stamp_* names and are never
registered in sys.modules, so these tests can share a process with other
apps' tests that vendor helpers with generic names.
"""

import ast
import copy
import math
import struct
import types
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "badge" / "apps" / "taste_stamp"


def load(path, name):
    # Executes a source file as a fresh module without touching sys.modules.
    module = types.ModuleType(name)
    module.__file__ = str(path)
    code = compile(Path(path).read_text(encoding="utf-8"), str(path), "exec")
    exec(code, module.__dict__)
    return module


V = load(APP / "verdicts.py", "taste_stamp_verdicts")
S = load(APP / "stamp.py", "taste_stamp_stamp")
M = load(APP / "motion.py", "taste_stamp_motion")
E = load(APP / "eightball.py", "taste_stamp_eightball")
README_CHECK = load(ROOT / ".github" / "scripts" / "validate_app_readmes.py", "taste_stamp_validate_app_readmes")

REST_UP = (0, 16384, 0, 0, 0, 0)  # hardware, badge upright
REST_SIM = (0, -16384, 0, 0, 0, 0)  # Badge Simulator, badge upright
SPIKE = (30000, 16384, 0, 0, 0, 0)


def luminance(c):
    def channel(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(v) for v in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def shoelace(c):
    total = 0.0
    n = len(c) // 2
    for i in range(n):
        j = (i + 1) % n
        total += c[2 * i] * c[2 * j + 1] - c[2 * j] * c[2 * i + 1]
    return total


class VerdictsTests(unittest.TestCase):
    def test_verdicts_follow_the_spec_order(self):
        self.assertEqual(V.VERDICTS, (
            "SHIP IT",
            "CERTIFIED BANGER",
            "NEEDS MORE TEETH",
            "KILL THE FLUFF",
            "TOO SAFE",
            "WHERE IS THE TENSION?",
            "MAKE THE DEV THE HERO",
        ))

    def test_ordered_collections_are_tuples(self):
        for value in (V.VERDICTS, V.INKS, V.FOOTERS):
            self.assertIsInstance(value, tuple)

    def test_every_verdict_has_an_ink_and_a_footer(self):
        self.assertEqual(len(V.INKS), len(V.VERDICTS))
        self.assertEqual(V.FOOTERS, ("APPROVED",) * 2 + ("REVISE",) * 5)
        self.assertEqual(V.STAMP_HEADER, "CREATIVE DIRECTOR")
        for ink in V.INKS:
            self.assertEqual(len(ink), 3)
            for v in ink:
                self.assertIsInstance(v, int)
                self.assertTrue(0 <= v <= 255)

    def test_inks_read_on_paper_and_differ(self):
        paper = (241, 236, 224)
        k = 225 / 255.0
        for ink in V.INKS:
            blended = tuple(round(i * k + p * (1 - k)) for i, p in zip(ink, paper))
            self.assertGreaterEqual(contrast(blended, paper), 3.0, ink)
        for i, a in enumerate(V.INKS):
            for b in V.INKS[i + 1:]:
                self.assertGreaterEqual(math.dist(a, b), 40, (a, b))

    def test_rng_reference_values(self):
        self.assertEqual(V.Rng(1).next_u32(), 270369)
        for seed in (0, 1 << 32):
            self.assertEqual(V.Rng(seed).state, 0x2545F491)
        self.assertEqual(V.Rng().state, 0x2545F491)
        a, b = V.Rng(42), V.Rng(42)
        self.assertEqual([a.next_u32() for _ in range(50)], [b.next_u32() for _ in range(50)])

    def test_rng_ranges(self):
        rng = V.Rng(7)
        seen = set()
        for _ in range(3000):
            r = rng.random()
            self.assertTrue(0.0 <= r < 1.0)
            u = rng.uniform(-2.0, 3.0)
            self.assertTrue(-2.0 <= u < 3.0)
            n = rng.randint(2, 8)
            self.assertTrue(2 <= n <= 8)
            seen.add(n)
        self.assertEqual(seen, set(range(2, 9)))

    def test_shuffle_bag_deals_permutations_without_repeats(self):
        bag = V.ShuffleBag(7, V.Rng(5))
        dealt = [bag.next() for _ in range(7 * 40)]
        for i in range(0, len(dealt), 7):
            self.assertEqual(sorted(dealt[i:i + 7]), list(range(7)))
        for a, b in zip(dealt, dealt[1:]):
            self.assertNotEqual(a, b)
        single = V.ShuffleBag(1, V.Rng(5))
        self.assertEqual([single.next() for _ in range(5)], [0] * 5)


class StampTests(unittest.TestCase):
    def all_text(self):
        texts = list(V.VERDICTS) + list(V.FOOTERS) + [V.STAMP_HEADER]
        return texts

    def test_glyphs_cover_every_string_the_app_draws(self):
        for text in self.all_text():
            self.assertLessEqual(set(text) - {" "}, set(S.GLYPHS), text)

    def test_layout_widths(self):
        self.assertAlmostEqual(S.layout_line("AA")[1], 10.45, places=9)
        self.assertAlmostEqual(S.layout_line("A A")[1], 12.25, places=9)
        self.assertAlmostEqual(S.layout_line(" A")[1], S.layout_line("A")[1], places=9)
        self.assertAlmostEqual(S.line_width("ship it"), S.line_width("SHIP IT"), places=9)
        self.assertEqual(S.layout_line("")[1], 0.0)

    def test_wrap(self):
        cases = {
            "SHIP IT": ("SHIP IT",),
            "TOO SAFE": ("TOO SAFE",),
            "CERTIFIED BANGER": ("CERTIFIED", "BANGER"),
            "NEEDS MORE TEETH": ("NEEDS MORE", "TEETH"),
            "KILL THE FLUFF": ("KILL THE", "FLUFF"),
            "WHERE IS THE TENSION?": ("WHERE IS THE", "TENSION?"),
            "MAKE THE DEV THE HERO": ("MAKE THE DEV", "THE HERO"),
            "SUPERCALIFRAGILISTIC": ("SUPERCALIFRAGILISTIC",),
            "  SHIP   IT  ": ("SHIP IT",),
        }
        for text, expected in cases.items():
            self.assertEqual(S.wrap(text), expected, text)

    def test_wrap_drops_the_comma_at_a_line_break(self):
        self.assertEqual(S.wrap("MORE CONTRAST, LESS GRADIENT", 14), ("MORE CONTRAST", "LESS GRADIENT"))
        self.assertEqual(S.wrap("GO BOLDER, THEN EDIT", 14), ("GO BOLDER", "THEN EDIT"))
        self.assertEqual(S.wrap("FEWER WORDS, SHARPER VERBS", 14), ("FEWER WORDS", "SHARPER VERBS"))
        self.assertEqual(S.wrap("YES, AND", 14), ("YES, AND",))
        self.assertEqual(S.wrap("SHIP IT, NOW", 9), ("SHIP IT", "NOW"))
        self.assertEqual(S.wrap(", WORD", 5), (",", "WORD"))

    def test_every_stamp_is_centred_and_well_wound(self):
        for i, verdict in enumerate(V.VERDICTS):
            groups, w, h = S.build_stamp(verdict, V.STAMP_HEADER, V.FOOTERS[i])
            self.assertGreater(w, 0)
            self.assertGreater(h, 0)
            xs, ys = [], []
            for group in groups:
                self.assertTrue(group)
                for contour in group:
                    self.assertEqual(len(contour) % 2, 0)
                    self.assertGreaterEqual(len(contour), 6)
                    for v in contour:
                        self.assertTrue(math.isfinite(v))
                    self.assertGreater(shoelace(contour), 0, verdict)
                    xs.extend(contour[0::2])
                    ys.extend(contour[1::2])
            self.assertGreaterEqual(min(xs), -w / 2 - 1e-6)
            self.assertLessEqual(max(xs), w / 2 + 1e-6)
            self.assertGreaterEqual(min(ys), -h / 2 - 1e-6)
            self.assertLessEqual(max(ys), h / 2 + 1e-6)
            self.assertGreater(max(xs) - min(xs), 0.95 * w)
            self.assertGreater(max(ys) - min(ys), 0.95 * h)

    def test_build_stamp_is_deterministic(self):
        first = S.build_stamp("SHIP IT", V.STAMP_HEADER, "APPROVED")
        second = S.build_stamp("SHIP IT", V.STAMP_HEADER, "APPROVED")
        self.assertEqual(first, second)
        bare = S.build_stamp("SHIP IT", None, "APPROVED")
        self.assertLess(bare[2], first[2])

    def test_slam_pose(self):
        self.assertEqual(S.slam_pose(0), (2.6, 1.0, 70, False))
        k, wobble, alpha, landed = S.slam_pose(S.DROP_MS)
        self.assertAlmostEqual(k, 0.94)
        self.assertEqual((wobble, alpha, landed), (0.0, 255, True))
        for t in (S.BAKE_MS, 400, 5000):
            self.assertEqual(S.slam_pose(t), (1.0, 0.0, 255, True))
        previous = S.slam_pose(0)
        for t in range(1, S.DROP_MS):
            pose = S.slam_pose(t)
            self.assertLess(pose[0], previous[0])
            self.assertGreaterEqual(pose[2], previous[2])
            self.assertFalse(pose[3])
            previous = pose

    def test_shake_offset_decays_to_nothing(self):
        self.assertEqual(S.shake_offset(-1), (0.0, 0.0))
        self.assertEqual(S.shake_offset(S.SHAKE_MS), (0.0, 0.0))
        self.assertEqual(S.shake_offset(0, 0.0), (0.0, 9.0))
        for t in range(0, S.SHAKE_MS, 7):
            x, y = S.shake_offset(t, 1.3)
            limit = S.SHAKE_PX * (1 - t / S.SHAKE_MS) ** 2 + 1e-9
            self.assertLessEqual(abs(x), limit)
            self.assertLessEqual(abs(y), limit)

    def test_strobe_flashes_then_chases_then_fades(self):
        self.assertIsNone(S.strobe_levels(-1))
        self.assertIsNone(S.strobe_levels(S.STROBE_MS))
        self.assertEqual(S.strobe_levels(0), (1.0,) * 4)
        self.assertEqual(S.strobe_levels(100), (0.0,) * 4)
        lit = set()
        for t in range(140, 700, 5):
            levels = S.strobe_levels(t)
            self.assertEqual(sorted(levels), [0.15, 0.15, 0.15, 1.0])
            self.assertEqual(levels.index(1.0), ((t - 140) // 70) % 4)
            lit.add(levels.index(1.0))
        self.assertEqual(lit, {0, 1, 2, 3})
        self.assertEqual(S.strobe_levels(700), (0.6,) * 4)
        previous = 0.6
        for t in range(701, S.STROBE_MS):
            levels = S.strobe_levels(t)
            self.assertEqual(len(set(levels)), 1)
            self.assertLess(levels[0], previous)
            self.assertGreaterEqual(levels[0], 0.0)
            previous = levels[0]

    def test_splats_fly_outward_from_the_rim(self):
        rng = V.Rng(7)
        splats = S.make_splats(rng.random, 40, 160.0, 121.0, 80.0, 50.0)
        self.assertEqual(len(splats), 40)
        for x, y, vx, vy, r in splats:
            ex = (x - 160.0) / (80.0 * 0.92)
            ey = (y - 121.0) / (50.0 * 0.92)
            self.assertAlmostEqual(ex * ex + ey * ey, 1.0, places=6)
            self.assertGreaterEqual(vx * (x - 160.0), -1e-9)
            self.assertGreaterEqual(vy * (y - 121.0), -1e-9)
            self.assertTrue(60.0 - 1e-6 <= math.hypot(vx, vy) <= 230.0 + 1e-6)
            self.assertTrue(0.8 <= r <= 2.5)

    def test_splat_drag_is_frame_rate_independent(self):
        rng = V.Rng(8)
        one = S.make_splats(rng.random, 10, 0.0, 0.0, 30.0, 20.0)
        many = copy.deepcopy(one)
        start = copy.deepcopy(one)
        S.step_splats(one, 400)
        for _ in range(25):
            S.step_splats(many, 16)
        for a, b, s in zip(one, many, start):
            for i in range(4):
                self.assertAlmostEqual(a[i], b[i], delta=1e-6)
            travel = math.hypot(a[0] - s[0], a[1] - s[1])
            self.assertLessEqual(travel, math.hypot(s[2], s[3]) * S.SPLAT_DRAG_MS / 1000.0 + 1e-9)


def run_chop(detector, reading, start, end, dt=16):
    fired = []
    t = start
    while t <= end:
        if detector.update(reading, dt, t):
            fired.append(t)
        t += dt
    return fired


class MotionTests(unittest.TestCase):
    def test_flip_fires_once_the_new_orientation_settles(self):
        f = M.FlipDetector(False)
        self.assertFalse(f.update(False, 1000))
        self.assertFalse(f.update(True, 1000))
        self.assertFalse(f.update(True, 1119))
        self.assertTrue(f.update(True, 1120))
        self.assertTrue(f.state)
        self.assertFalse(f.update(True, 1500))

    def test_flip_bounce_restarts_the_settle_timer(self):
        f = M.FlipDetector(False)
        f.update(True, 1000)
        f.update(False, 1060)
        self.assertIsNone(f.pending_since)
        self.assertFalse(f.update(True, 1100))
        self.assertFalse(f.update(True, 1200))
        self.assertTrue(f.update(True, 1220))

    def test_flip_back_inside_the_cooldown_tracks_state_silently(self):
        f = M.FlipDetector(False)
        f.update(True, 1000)
        self.assertTrue(f.update(True, 1120))
        f.update(False, 1300)
        self.assertFalse(f.update(False, 1420))
        self.assertFalse(f.state)
        self.assertEqual(f.last_flip, 1120)
        f.update(True, 1800)
        self.assertTrue(f.update(True, 1920))

    def test_flip_detector_can_start_inverted(self):
        f = M.FlipDetector(True)
        self.assertTrue(f.state)
        self.assertFalse(f.update(True, 1000))
        f.update(False, 2000)
        self.assertTrue(f.update(False, 2120))
        self.assertFalse(f.state)

    def armed_chop(self, rest=REST_UP):
        c = M.ChopDetector()
        self.assertFalse(c.armed)
        self.assertEqual(run_chop(c, rest, 0, 112), [])
        self.assertFalse(c.armed)
        self.assertFalse(c.update(rest, 16, 128))
        self.assertTrue(c.armed)
        return c

    def test_chop_arms_after_calm_and_fires_on_a_spike(self):
        c = self.armed_chop()
        self.assertTrue(c.update(SPIKE, 16, 144))
        self.assertAlmostEqual(c.jolt, 108, delta=1)
        self.assertFalse(c.armed)
        self.assertEqual(c.last_chop, 144)

    def test_chop_works_with_either_gravity_sign(self):
        c = self.armed_chop(REST_SIM)
        self.assertTrue(c.update((30000, -16384, 0, 0, 0, 0), 16, 144))

    def test_a_sudden_drop_in_acceleration_also_chops(self):
        c = self.armed_chop()
        self.assertTrue(c.update((0, 1000, 0, 0, 0, 0), 16, 144))

    def test_a_moderate_jolt_needs_a_spin_to_chop(self):
        c = self.armed_chop()
        self.assertFalse(c.update((24000, 16384, 0, 0, 0, 0), 16, 144))
        c = self.armed_chop()
        self.assertTrue(c.update((24000, 16384, 0, 15000, 0, 0), 16, 144))

    def test_chop_cooldown_then_rearm(self):
        c = self.armed_chop()
        t0 = 144
        self.assertTrue(c.update(SPIKE, 16, t0))
        self.assertEqual(run_chop(c, REST_UP, t0 + 16, t0 + 288), [])
        self.assertFalse(c.update(SPIKE, 16, t0 + 304))
        self.assertEqual(run_chop(c, REST_UP, t0 + 320, t0 + 688), [])
        self.assertTrue(c.armed)
        self.assertTrue(c.update(SPIKE, 16, t0 + 704))

    def test_zero_reading_is_ignored(self):
        c = self.armed_chop()
        self.assertFalse(c.update((0, 0, 0, 0, 0, 0), 16, 144))
        self.assertTrue(c.update(SPIKE, 16, 160))

    def test_a_spike_as_the_first_reading_never_fires_and_recovers(self):
        c = M.ChopDetector()
        self.assertFalse(c.update(SPIKE, 16, 0))
        self.assertEqual(run_chop(c, REST_UP, 16, 6000), [])
        self.assertTrue(c.armed)
        self.assertEqual(run_chop(c, REST_UP, 6016, 10000), [])
        self.assertAlmostEqual(c.gravity, 16384, delta=200)
        self.assertTrue(c.update(SPIKE, 16, 10016))

    def test_a_chop_barely_moves_the_gravity_estimate(self):
        c = self.armed_chop()
        before = c.gravity
        c.update(SPIKE, 16, 144)
        c.update(SPIKE, 16, 160)
        self.assertLess(abs(c.gravity - before), 0.02 * before)


class EightBallTests(unittest.TestCase):
    def setUp(self):
        self.verts, self.faces, self.numbers = E.icosahedron()

    def test_icosahedron_is_a_d20(self):
        self.assertEqual(len(self.verts), 12)
        self.assertEqual(len(self.faces), 20)
        self.assertEqual(sorted(self.numbers), list(range(1, 21)))
        for face in self.faces:
            for i in range(3):
                edge = math.dist(self.verts[face[i]], self.verts[face[(i + 1) % 3]])
                self.assertAlmostEqual(edge, 2.0, places=9)

    def test_opposite_faces_add_up_to_21(self):
        centres = [E.face_centre(self.verts, f) for f in self.faces]
        for i, c in enumerate(centres):
            mirror = tuple(-v for v in c)
            opposite = [j for j, o in enumerate(centres) if math.dist(o, mirror) < 1e-6]
            self.assertEqual(len(opposite), 1)
            self.assertEqual(self.numbers[i] + self.numbers[opposite[0]], 21)

    def test_faces_wind_outward_consistently(self):
        edges = set()
        for face in self.faces:
            n = E.face_normal(self.verts, face)
            self.assertAlmostEqual(math.sqrt(sum(v * v for v in n)), 1.0, places=9)
            c = E.face_centre(self.verts, face)
            self.assertGreater(sum(a * b for a, b in zip(n, c)), 0)
            for i in range(3):
                edges.add((face[i], face[(i + 1) % 3]))
        self.assertEqual(len(edges), 60)
        for a, b in edges:
            self.assertIn((b, a), edges)

    def test_face_edges_lists_each_edge_once(self):
        edges = E.face_edges(self.faces)
        self.assertEqual(len(edges), 30)
        self.assertEqual(len({(i, j) for i, j, f, g in edges}), 30)
        borders = [0] * len(self.faces)
        for i, j, f, g in edges:
            self.assertLess(i, j)
            self.assertNotEqual(f, g)
            for face in (self.faces[f], self.faces[g]):
                self.assertIn(i, face)
                self.assertIn(j, face)
            borders[f] += 1
            borders[g] += 1
        self.assertEqual(borders, [3] * len(self.faces))


def read_png(path):
    data = Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    chunks = []
    pos = 8
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        (crc,) = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])
        chunks.append((kind, body, crc == zlib.crc32(kind + body) & 0xFFFFFFFF))
        pos += 12 + length
    return chunks


def png_pixels(chunks):
    width, height, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", chunks[0][1])
    bpp = {6: 4, 2: 3, 4: 2, 0: 1}[ctype]
    raw = zlib.decompress(b"".join(body for kind, body, _ in chunks if kind == b"IDAT"))
    stride = width * bpp
    rows = []
    prev = bytearray(stride)
    pos = 0
    for _ in range(height):
        kind = raw[pos]
        line = bytearray(raw[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if kind == 1:
                line[x] = (line[x] + a) & 0xFF
            elif kind == 2:
                line[x] = (line[x] + b) & 0xFF
            elif kind == 3:
                line[x] = (line[x] + (a + b) // 2) & 0xFF
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 0xFF
        rows.append([tuple(line[i:i + bpp]) for i in range(0, stride, bpp)])
        prev = line
    return rows


class IconTests(unittest.TestCase):
    def test_icon_is_a_valid_24px_rgba_png(self):
        chunks = read_png(APP / "icon.png")
        self.assertEqual(chunks[0][0], b"IHDR")
        self.assertEqual(chunks[-1][0], b"IEND")
        self.assertTrue(all(ok for _, _, ok in chunks))
        width, height, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", chunks[0][1])
        self.assertEqual((width, height, depth, ctype, interlace), (24, 24, 8, 6, 0))

    def test_icon_has_a_drawn_mark(self):
        rows = png_pixels(read_png(APP / "icon.png"))
        self.assertEqual(len(rows), 24)
        alphas = [p[3] for row in rows for p in row]
        self.assertGreaterEqual(alphas.count(255), 48)
        self.assertGreaterEqual(alphas.count(0), 24 * 24 * 2 // 5)

    def test_icon_is_white_like_the_menu_icons(self):
        rows = png_pixels(read_png(APP / "icon.png"))
        # Transparent pixels are white too, so the menu's bilinear blit has no dark fringe.
        self.assertEqual({p[:3] for row in rows for p in row}, {(255, 255, 255)})

    def test_icon_is_legible_on_every_menu_tile(self):
        # The menu blits icon.png over a palette colour (full when selected, 22% otherwise).
        tree = ast.parse((ROOT / "badge/apps/menu/src/ui.py").read_text(encoding="utf-8"))
        palette = [ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                   and any(getattr(t, "id", None) == "PALETTE" for t in node.targets)][0]
        self.assertGreaterEqual(len(palette), 8)
        for rgb in palette:
            for strength in (1.0, 0.22):
                tile = tuple(round(c * strength) for c in rgb)
                self.assertGreaterEqual(contrast((255, 255, 255), tile), 2.0, tile)


class ReadmeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (APP / "README.md").read_text(encoding="utf-8")

    def test_repository_readme_check_passes(self):
        self.assertIsNone(README_CHECK.check_app(APP))

    def test_first_paragraph_is_the_one_sentence_description(self):
        lines = self.text.splitlines()
        self.assertEqual(lines[0], "# Taste Stamp")
        i = 1
        while not lines[i].strip():
            i += 1
        paragraph = []
        while i < len(lines) and lines[i].strip():
            paragraph.append(lines[i].strip())
            i += 1
        self.assertEqual(" ".join(paragraph), (
            "Flip or karate-chop your badge to slam Creative Director verdicts, shake the "
            "Creative 8-Ball for a Studio creative direction, and beam either one to nearby "
            "badges over IR."
        ))


if __name__ == "__main__":
    unittest.main()
