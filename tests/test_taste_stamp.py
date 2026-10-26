"""Tests for the Taste Stamp & Creative 8-Ball app in badge/apps/taste_stamp.

The app's modules are loaded under unique taste_stamp_* names and are never
registered in sys.modules, so these tests can share a process with other
apps' tests that vendor helpers with generic names.
"""

import ast
import copy
import math
import struct
import sys
import types
import unittest
import zlib
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

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
B = load(APP / "beam.py", "taste_stamp_beam")
README_CHECK = load(ROOT / ".github" / "scripts" / "validate_app_readmes.py", "taste_stamp_validate_app_readmes")

REST_UP = (0, 16384, 0, 0, 0, 0)  # hardware, badge upright
REST_SIM = (0, -16384, 0, 0, 0, 0)  # Badge Simulator, badge upright
SPIKE = (30000, 16384, 0, 0, 0, 0)

IR_MODULES = (
    "aye_arr",
    "aye_arr.nec",
    "aye_arr.nec.remotes",
    "aye_arr.nec.remotes.descriptor",
    "badgeware",
    "badgeware.ir",
)


class FakeIR:
    # Stands in for aye_arr's NECSender and RemoteDescriptor and for the
    # badgeware.ir receiver. present=False makes every IR import fail;
    # sender=False and descriptor=False mimic the simulator's empty aye_arr.

    def __init__(self, clock=None, present=True, sender=True, descriptor=True, bind_returns="self",
                 init_error=None, start_error=None, send_error=None, stop_error=None,
                 bind_error=None, close_error=None):
        self.clock = clock or (lambda: 0)
        self.present = present
        self.sender = sender
        self.descriptor = descriptor
        self.bind_returns = bind_returns
        self.init_error = init_error
        self.start_error = start_error
        self.send_error = send_error
        self.stop_error = stop_error
        self.bind_error = bind_error
        self.close_error = close_error
        self.senders = []
        self.bound = []
        self.stubs = []
        self.closed = 0
        self.descriptor_inits = 0

    @property
    def frames(self):
        out = []
        for sender in self.senders:
            out.extend(sender.frames)
        return out

    def deliver(self, cmd):
        # Calls the on_any handler the app left on whatever ir.bind returned.
        target = self.stubs[-1] if self.bind_returns == "stub" else self.bound[-1]
        target.on_any(cmd)
        target.on_known(cmd)

    def modules(self):
        mods = dict.fromkeys(IR_MODULES)
        if not self.present:
            return mods
        fake = self

        class NECSender:
            def __init__(self, pin, pio, sm):
                if fake.init_error is not None:
                    raise fake.init_error
                self.args = (pin, pio, sm)
                self.started = False
                self.stopped = 0
                self.frames = []
                fake.senders.append(self)

            def start(self):
                if fake.start_error is not None:
                    raise fake.start_error
                self.started = True

            def stop(self):
                self.stopped += 1
                if fake.stop_error is not None:
                    raise fake.stop_error

            def send_addr_cmd(self, address, cmd):
                if fake.send_error is not None:
                    raise fake.send_error
                self.frames.append((address, cmd, fake.clock()))

        class RemoteDescriptor:
            def __init__(self):
                fake.descriptor_inits += 1
                self.on_known = None
                self.on_any = None

        class Port:
            def bind(self, descriptor):
                if fake.bind_error is not None:
                    raise fake.bind_error
                fake.bound.append(descriptor)
                if fake.bind_returns == "self":
                    return descriptor
                if fake.bind_returns == "stub":
                    stub = SimpleNamespace()
                    fake.stubs.append(stub)
                    return stub
                return None

            def close(self):
                fake.closed += 1
                if fake.close_error is not None:
                    raise fake.close_error

        aye = types.ModuleType("aye_arr")
        mods["aye_arr"] = aye
        if self.sender or self.descriptor:
            aye.__path__ = []
            nec = types.ModuleType("aye_arr.nec")
            nec.__path__ = []
            aye.nec = nec
            mods["aye_arr.nec"] = nec
            if self.sender:
                nec.NECSender = NECSender
            if self.descriptor:
                remotes = types.ModuleType("aye_arr.nec.remotes")
                remotes.__path__ = []
                descriptor = types.ModuleType("aye_arr.nec.remotes.descriptor")
                descriptor.RemoteDescriptor = RemoteDescriptor
                remotes.descriptor = descriptor
                nec.remotes = remotes
                mods["aye_arr.nec.remotes"] = remotes
                mods["aye_arr.nec.remotes.descriptor"] = descriptor
        package = types.ModuleType("badgeware")
        package.__path__ = []
        ir_module = types.ModuleType("badgeware.ir")
        ir_module.ir = Port()
        package.ir = ir_module
        mods["badgeware"] = package
        mods["badgeware.ir"] = ir_module
        self.RemoteDescriptor = RemoteDescriptor
        return mods

    def patch(self):
        return mock.patch.dict(sys.modules, self.modules())


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
        for value in (V.VERDICTS, V.INKS, V.FOOTERS, V.PROMPTS):
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

    def test_prompts_fill_a_d20_and_are_drawable(self):
        self.assertEqual(len(V.PROMPTS), 20)
        self.assertEqual(len(set(V.PROMPTS)), 20)
        self.assertEqual(V.PROMPTS[12], "STEAL FROM THE TERMINAL")
        for prompt in V.PROMPTS:
            self.assertEqual(prompt, prompt.upper())
            self.assertLessEqual(set(prompt) - {" "}, set(S.GLYPHS), prompt)
            lines = S.wrap(prompt, 14)
            self.assertTrue(1 <= len(lines) <= 2)
            self.assertTrue(all(lines))

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
        texts = list(V.VERDICTS) + list(V.FOOTERS) + [V.STAMP_HEADER] + list(V.PROMPTS)
        return texts + [str(n) for n in range(1, 21)] + ["6.", "9."]

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
        for prompt in V.PROMPTS:
            for line in S.wrap(prompt, 14)[:-1]:
                self.assertFalse(line.endswith(","), prompt)

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


def shake_pattern(y, segments, rest_frames=10, per_segment=4, amplitude=13107):
    samples = [(0, y, 0, 0, 0, 0)] * rest_frames
    for k in range(segments):
        x = amplitude if k % 2 == 0 else -amplitude
        samples.extend([(x, y, 0, 0, 0, 0)] * per_segment)
    return samples


def run_shake(detector, samples, dt=16, start=0):
    log = []
    t = start
    for sample in samples:
        detector.update(sample, dt, t)
        log.append((t, bool(detector.shaking), bool(detector.reversed)))
        t += dt
    return log


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

    def check_shake(self, y):
        d = M.ShakeDetector()
        log = run_shake(d, shake_pattern(y, 6))

        def seg(k):
            return 10 + 4 * k

        reversals = [i for i, entry in enumerate(log) if entry[2]]
        self.assertEqual(reversals, [seg(k) for k in range(1, 6)])
        self.assertFalse(any(entry[1] for entry in log[:seg(2)]))
        self.assertTrue(all(entry[1] for entry in log[seg(2):]))

    def test_shake_on_hardware_gravity(self):
        self.check_shake(16384)

    def test_shake_on_simulator_gravity(self):
        self.check_shake(-16384)

    def test_shaking_ends_after_the_hold(self):
        d = M.ShakeDetector()
        log = run_shake(d, shake_pattern(16384, 4) + [REST_UP] * 60)
        last = max(t for t, _, reversed_ in log if reversed_)
        ends = [t for t, shaking, _ in log if t > last and not shaking]
        self.assertTrue(ends)
        self.assertGreater(ends[0] - last, 450)
        self.assertLessEqual(ends[0] - last, 450 + 16)
        self.assertTrue(all(not shaking for t, shaking, _ in log if t >= ends[0]))
        self.assertEqual(d.times, [])

    def test_a_new_shake_after_one_ends_needs_fresh_reversals(self):
        d = M.ShakeDetector()
        first = run_shake(d, shake_pattern(16384, 4) + [REST_UP] * 30)
        self.assertFalse(first[-1][1])
        t = len(first) * 16
        second = run_shake(d, shake_pattern(16384, 3, rest_frames=0), start=t)
        reversals = [i for i, entry in enumerate(second) if entry[2]]
        self.assertTrue(reversals)
        self.assertFalse(any(entry[1] for entry in second[:reversals[0] + 1]))
        self.assertTrue(second[-1][1])

    def test_a_single_flip_is_not_a_shake(self):
        d = M.ShakeDetector()
        log = run_shake(d, [REST_UP] * 30 + [REST_SIM] * 63)
        self.assertEqual(sum(1 for entry in log if entry[2]), 0)
        self.assertFalse(any(entry[1] for entry in log))
        log = run_shake(d, [REST_UP] * 63, start=93 * 16)
        self.assertEqual(sum(1 for entry in log if entry[2]), 1)
        self.assertFalse(any(entry[1] for entry in log))

    def test_the_first_reading_only_seeds_the_average(self):
        d = M.ShakeDetector()
        self.assertIsNone(d.slow)
        d.update((0, 0, 0, 0, 0, 0), 16, 0)
        self.assertIsNone(d.slow)
        d.update((13107, 16384, 0, 0, 0, 0), 16, 16)
        self.assertIsNotNone(d.slow)
        self.assertFalse(d.reversed)
        self.assertFalse(d.shaking)


def rotate(q, v):
    r = E.q_matrix(q)
    return tuple(r[i][0] * v[0] + r[i][1] * v[1] + r[i][2] * v[2] for i in range(3))


def random_quaternion(rng):
    return E.q_normalise(tuple(rng.uniform(-1.0, 1.0) for _ in range(4)))


def spin_out(ball, start=0, dt=16, until=6000, agitated=False):
    landings = []
    t = start
    while t < until:
        t += dt
        if ball.update(dt, t, agitated):
            landings.append(t)
    return landings


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

    def test_targets_turn_each_face_up_with_its_number_upright(self):
        ball = E.Ball(V.Rng(3).random)
        for i in range(20):
            ball.q = ball.target_for(i)
            self.assertEqual(ball.facing_face(), i)
            self.assertGreater(rotate(ball.q, ball.normals[i])[2], 0.999)
            top = rotate(ball.q, ball.verts[ball.faces[i][0]])
            centre = rotate(ball.q, ball.centres[i])
            self.assertAlmostEqual(top[0], centre[0], places=6)
            self.assertGreater(top[1] - centre[1], 1.0)
            self.assertEqual(ball.face_for_number(ball.numbers[i]), i)

    def test_idle_ball_drifts_slowly(self):
        ball = E.Ball(V.Rng(4).random)
        self.assertEqual(ball.state, E.IDLE)
        q0 = ball.q
        self.assertEqual(spin_out(ball, until=992), [])
        self.assertEqual(ball.state, E.IDLE)
        self.assertTrue(0.5 < E.q_angle(q0, ball.q) < 0.9)

    def test_kick_caps_the_spin_and_holds_it(self):
        ball = E.Ball(V.Rng(5).random)
        ball.kick(100, 1000)
        self.assertEqual(ball.state, E.SPINNING)
        self.assertAlmostEqual(ball.speed(), E.MAX_SPIN, places=6)
        self.assertEqual(ball.hold_until, 1000 + E.MIN_SPIN_MS)
        ball.kick(5, 1100)
        self.assertLessEqual(ball.speed(), E.MAX_SPIN + 1e-9)
        self.assertEqual(ball.hold_until, 1700)

    def test_lands_exactly_once_facing_the_viewer(self):
        ball = E.Ball(V.Rng(6).random)
        ball.kick(18, 0)
        landings = spin_out(ball, until=5000)
        self.assertEqual(len(landings), 1)
        self.assertTrue(1800 <= landings[0] <= 3000, landings)
        self.assertEqual(ball.state, E.LANDED)
        self.assertEqual(ball.landed_at, landings[0])
        self.assertEqual(ball.facing_face(), ball.face)
        self.assertEqual(ball.number(), ball.numbers[ball.face])
        self.assertLess(E.q_angle(ball.q, ball.target_for(ball.face)), 1e-3)

    def test_forced_numbers_land_on_their_face(self):
        for forced in (1, 13, 20):
            ball = E.Ball(V.Rng(forced).random)
            ball.kick(16, 0, forced)
            spin_out(ball)
            self.assertEqual(ball.state, E.LANDED)
            self.assertEqual(ball.number(), forced)

    def test_invalid_forced_numbers_are_ignored(self):
        for forced in (0, 21, -3):
            ball = E.Ball(V.Rng(8).random)
            ball.kick(16, 0, forced)
            spin_out(ball)
            self.assertEqual(ball.state, E.LANDED)
            self.assertIn(ball.number(), range(1, 21))

    def test_agitation_keeps_the_ball_spinning(self):
        ball = E.Ball(V.Rng(9).random)
        ball.kick(18, 0)
        self.assertEqual(spin_out(ball, until=2992, agitated=True), [])
        self.assertEqual(ball.state, E.SPINNING)
        self.assertGreater(ball.speed(), 17.0)
        self.assertGreaterEqual(ball.hold_until, 2992 + 300)
        self.assertEqual(len(spin_out(ball, start=2992, until=9000)), 1)
        self.assertEqual(ball.state, E.LANDED)

    def test_reset_returns_to_idle(self):
        ball = E.Ball(V.Rng(10).random)
        ball.kick(18, 0, 7)
        spin_out(ball)
        ball.reset()
        self.assertEqual(ball.state, E.IDLE)
        self.assertIsNone(ball.face)
        self.assertIsNone(ball.forced)

    def test_spin_down_is_frame_rate_independent(self):
        starts = []
        for dt in (16, 33):
            ball = E.Ball(V.Rng(11).random)
            ball.kick(18, 0)
            t = 0
            while ball.state == E.SPINNING and t < 6000:
                t += dt
                ball.update(dt, t)
            starts.append(ball.settle_start)
        self.assertLess(abs(starts[0] - starts[1]), 50)
        self.assertAlmostEqual(starts[0], E.FRICTION_TAU * math.log(18 / E.LAND_SPEED), delta=60)

    def test_projection_stays_inside_the_liquid(self):
        rng = V.Rng(12)
        ball = E.Ball(rng.random)
        for _ in range(200):
            ball.q = random_quaternion(rng)
            points, visible = ball.project(160, 100, 24)
            self.assertEqual(len(points), 12)
            for x, y in points:
                self.assertLess(math.hypot(x - 160, y - 100), 54)
            self.assertIn(ball.facing_face(), [entry[0] for entry in visible])
            for i, level, nz in visible:
                self.assertIn(level, range(E.LEVELS + 1))
                self.assertGreater(nz, 0)

    def test_bayer_levels_nest(self):
        flat = []
        for item in E.BAYER:
            flat.extend(item if isinstance(item, (tuple, list)) else [item])
        self.assertEqual(sorted(flat), list(range(64)))
        self.assertEqual(E.bayer_rows(0), (0,) * 8)
        self.assertEqual(E.bayer_rows(E.LEVELS), (0xFF,) * 8)
        previous = (0,) * 8
        for level in range(E.LEVELS + 1):
            rows = E.bayer_rows(level)
            self.assertIsInstance(rows, tuple)
            self.assertEqual(len(rows), 8)
            self.assertEqual(sum(bin(r).count("1") for r in rows), 4 * level)
            for old, new in zip(previous, rows):
                self.assertTrue(0 <= new <= 0xFF)
                self.assertEqual(old & ~new & 0xFF, 0)
            previous = rows

    def test_face_uv_maps_corners_and_centroid(self):
        r = E.FACE_R
        uv = E.to_face_uv([[0.0, -r, -1.0, r / 2, 1.0, r / 2, 0.0, 0.0]])[0]
        for a, b in zip(uv, [0, 0, 1, 0, 0, 1, 1 / 3, 1 / 3]):
            self.assertAlmostEqual(a, b, places=9)
        mapped = E.map_uv([[0, 0, 1, 0, 0, 1, 0.5, 0.5]], (10, 20), (0, 40), (20, 40))[0]
        self.assertEqual(mapped, [10, 20, 0, 40, 20, 40, 10, 40])

    def test_quaternion_helpers(self):
        q = E.q_axis_angle((0.0, 0.0, 1.0), math.pi / 2)
        for a, b in zip(rotate(q, (1.0, 0.0, 0.0)), (0.0, 1.0, 0.0)):
            self.assertAlmostEqual(a, b, places=9)
        for seed in range(1, 20):
            a = random_quaternion(V.Rng(seed))
            self.assertLess(E.q_angle(a, E.q_from_rows(E.q_matrix(a))), 1e-5)
        ident = (1.0, 0.0, 0.0, 0.0)
        turn = E.q_axis_angle((0.0, 1.0, 0.0), 1.0)
        self.assertAlmostEqual(E.q_angle(ident, turn), 1.0, places=6)
        self.assertAlmostEqual(E.q_angle(ident, E.q_mul(turn, turn)), 2.0, places=6)
        self.assertAlmostEqual(E.q_angle(ident, E.q_slerp(ident, turn, 0.5)), 0.5, places=6)
        self.assertLess(E.q_angle(E.q_slerp(ident, turn, 0.0), ident), 1e-5)
        self.assertLess(E.q_angle(E.q_slerp(ident, turn, 1.0), turn), 1e-5)
        self.assertEqual((E.smoothstep(-1), E.smoothstep(0.5), E.smoothstep(2)), (0.0, 0.5, 1.0))
        axis = E.random_axis(V.Rng(3).random)
        self.assertAlmostEqual(math.sqrt(sum(v * v for v in axis)), 1.0, places=9)

    def test_affine_parts_rebuilds_the_map_uv_placement(self):
        # mat3().translate(tx, ty).rotate(phi).scale(sx, sy).rotate(theta)
        # post-multiplies, so the linear part is R(phi) * S * R(theta).
        def turn(degrees):
            a = math.radians(degrees)
            return ((math.cos(a), -math.sin(a)), (math.sin(a), math.cos(a)))

        def times(p, q):
            return tuple(tuple(sum(p[i][k] * q[k][j] for k in range(2)) for j in range(2)) for i in range(2))

        rng = V.Rng(21)
        triangles = [
            ((160.0, 80.0), (140.0, 120.0), (180.0, 120.0)),
            ((160.0, 80.0), (180.0, 120.0), (140.0, 120.0)),
            ((100.0, 100.0), (100.0, 100.5), (130.0, 100.0)),
            ((50.0, 60.0), (50.0, 60.0), (50.0, 60.0)),
        ]
        for _ in range(300):
            triangles.append(tuple((rng.uniform(40.0, 280.0), rng.uniform(20.0, 180.0)) for _ in range(3)))
        samples = [0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1 / 3, 1 / 3, 0.25, 0.6, -0.2, 1.3]
        signs = set()
        for top, left, right in triangles:
            tx, ty, phi, sx, sy, theta = E.affine_parts(top, left, right)
            m = times(turn(phi), times(((sx, 0.0), (0.0, sy)), turn(theta)))
            expected = E.map_uv([samples], top, left, right)[0]
            for k in range(0, len(samples), 2):
                s, t = samples[k], samples[k + 1]
                self.assertAlmostEqual(tx + m[0][0] * s + m[0][1] * t, expected[k], places=6)
                self.assertAlmostEqual(ty + m[1][0] * s + m[1][1] * t, expected[k + 1], places=6)
            # sx * sy is the determinant, so sy < 0 exactly when the face
            # is mirrored.
            det = (left[0] - top[0]) * (right[1] - top[1]) - (left[1] - top[1]) * (right[0] - top[0])
            self.assertGreaterEqual(sx, 0.0)
            self.assertAlmostEqual(sx * sy, det, delta=1e-6 * max(1.0, abs(det)))
            if abs(det) > 1e-6:
                signs.add(sy < 0)
        self.assertEqual(signs, {True, False})

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
        self.assertEqual(E.Ball(V.Rng(1).random).edges, edges)

    def test_projection_and_culling_match_the_3d_camera(self):
        # project() culls by screen winding; in perspective that must agree
        # with facing the camera at (0, 0, CAMERA) in 3D.
        rng = V.Rng(22)
        ball = E.Ball(rng.random)
        cx, cy, scale = 160, 100, 24
        checked = 0
        for _ in range(300):
            ball.q = random_quaternion(rng)
            m = E.q_matrix(ball.q)

            def world(v):
                return [m[r][0] * v[0] + m[r][1] * v[1] + m[r][2] * v[2] for r in range(3)]

            points, visible = ball.project(cx, cy, scale)
            for v, p in zip(ball.verts, points):
                x, y, z = world(v)
                k = scale * E.CAMERA / (E.CAMERA - z)
                self.assertAlmostEqual(p[0], cx + x * k, places=6)
                self.assertAlmostEqual(p[1], cy - y * k, places=6)
            shown = {}
            for i, level, nz in visible:
                shown[i] = nz
            for i in range(len(ball.faces)):
                n = world(ball.normals[i])
                c = world(ball.centres[i])
                facing = -c[0] * n[0] - c[1] * n[1] + (E.CAMERA - c[2]) * n[2]
                if i in shown:
                    self.assertAlmostEqual(shown[i], n[2], places=9)
                if abs(facing) < 1e-6:
                    continue
                self.assertEqual(i in shown, facing > 0, (i, facing))
                checked += 1
        self.assertGreater(checked, 5900)


class BeamTests(unittest.TestCase):
    def make_beam(self, sender=None):
        return B.Beam(sender)

    def make_sender(self, fake):
        with fake.patch():
            return B.make_sender()

    def test_codes_round_trip_and_fit_in_a_byte(self):
        vc, pc = len(V.VERDICTS), len(V.PROMPTS)
        codes = set()
        for kind, count in ((B.VERDICT, vc), (B.PROMPT, pc)):
            for i in range(count):
                cmd = B.encode(kind, i)
                self.assertTrue(0 <= cmd <= 255)
                self.assertEqual(B.decode(cmd, vc, pc), (kind, i))
                codes.add(cmd)
        self.assertEqual(len(codes), vc + pc)

    def test_decode_rejects_bytes_it_never_sends(self):
        for cmd in (7, 0x3F, 0x54, 255):
            self.assertIsNone(B.decode(cmd, 7, 20))
        self.assertEqual(B.decode(0x53, 7, 20), (B.PROMPT, 19))

    def test_beams_use_their_own_nec_address_and_pins(self):
        self.assertEqual(B.ADDRESS, 0x53)
        self.assertNotIn(B.ADDRESS, (0x45, 0x4C, 0x54))
        self.assertEqual((B.TX_PIN, B.TX_PIO, B.TX_SM), (16, 0, 1))

    def test_lights_chase_then_stop(self):
        self.assertIsNone(B.lights(-1))
        self.assertIsNone(B.lights(B.LIGHT_MS))
        lit = set()
        for t in range(0, B.LIGHT_MS, 5):
            levels = B.lights(t)
            self.assertEqual(sorted(levels), [0.1, 0.1, 0.1, 1.0])
            lit.add(levels.index(1.0))
        self.assertEqual(lit, {0, 1, 2, 3})

    def test_make_sender_claims_pio0_sm1_on_gpio16(self):
        fake = FakeIR()
        tx = self.make_sender(fake)
        self.assertIs(tx, fake.senders[0])
        self.assertEqual(tx.args, (16, 0, 1))
        self.assertTrue(tx.started)

    def test_make_sender_degrades_without_ir(self):
        cases = (
            FakeIR(present=False),
            FakeIR(sender=False, descriptor=False),
            FakeIR(init_error=OSError("busy")),
        )
        for fake in cases:
            self.assertIsNone(self.make_sender(fake))

    def test_make_sender_releases_a_sender_that_fails_to_start(self):
        fake = FakeIR(start_error=OSError("pio full"))
        self.assertIsNone(self.make_sender(fake))
        self.assertEqual(fake.senders[0].stopped, 1)
        fake = FakeIR(start_error=OSError("pio full"), stop_error=OSError("again"))
        self.assertIsNone(self.make_sender(fake))

    def test_listen_binds_the_0x53_descriptor(self):
        fake = FakeIR()
        heard = []
        with fake.patch():
            self.assertTrue(B.listen(heard.append))
        d = fake.bound[0]
        self.assertIsInstance(d, fake.RemoteDescriptor)
        self.assertEqual((d.NAME, d.ADDRESS, d.BUTTON_CODES), ("TasteStamp", 0x53, {}))
        self.assertEqual(fake.descriptor_inits, 1)
        fake.deliver(0x42)
        self.assertEqual(heard, [0x42])
        self.assertIsNone(d.on_known("anything"))

    def test_listen_sets_handlers_on_a_stub_bind_result(self):
        # The Badge Simulator's bind returns a stub without on_any.
        fake = FakeIR(bind_returns="stub")
        heard = []
        with fake.patch():
            self.assertTrue(B.listen(heard.append))
        fake.deliver(3)
        self.assertEqual(heard, [3])

    def test_listen_without_aye_arr_still_binds(self):
        fake = FakeIR(sender=False, descriptor=False)
        heard = []
        with fake.patch():
            self.assertTrue(B.listen(heard.append))
        d = fake.bound[0]
        self.assertEqual(d.ADDRESS, 0x53)
        d.on_any(9)
        self.assertEqual(heard, [9])

    def test_listen_tolerates_bind_returning_none(self):
        with FakeIR(bind_returns=None).patch():
            self.assertTrue(B.listen(lambda cmd: None))

    def test_listen_reports_missing_or_failing_receivers(self):
        with FakeIR(present=False).patch():
            self.assertFalse(B.listen(lambda cmd: None))
        with FakeIR(bind_error=OSError("pio busy")).patch():
            self.assertFalse(B.listen(lambda cmd: None))

    def test_listen_survives_a_failing_base_initialiser(self):
        fake = FakeIR()
        mods = fake.modules()

        class Broken:
            def __init__(self):
                raise RuntimeError("no super")

        mods["aye_arr.nec.remotes.descriptor"].RemoteDescriptor = Broken
        heard = []
        with mock.patch.dict(sys.modules, mods):
            self.assertTrue(B.listen(heard.append))
        fake.bound[0].on_any(4)
        self.assertEqual(heard, [4])

    def test_stop_listening_closes_the_receiver_and_never_raises(self):
        fake = FakeIR()
        with fake.patch():
            B.stop_listening()
        self.assertEqual(fake.closed, 1)
        with FakeIR(close_error=OSError("closed")).patch():
            B.stop_listening()
        with FakeIR(present=False).patch():
            B.stop_listening()

    def test_without_a_transmitter_nothing_is_queued(self):
        link = self.make_beam()
        self.assertFalse(link.can_send())
        self.assertFalse(link.send(B.VERDICT, 0, 1000))
        self.assertFalse(link.busy())
        self.assertTrue(link.pump(1000))

    def test_bursts_go_out_one_frame_per_update(self):
        clock = [0]
        fake = FakeIR(clock=lambda: clock[0])
        link = self.make_beam(self.make_sender(fake))
        self.assertTrue(link.can_send())
        self.assertTrue(link.send(B.PROMPT, 12, 1000))
        self.assertTrue(link.busy())
        for now in (1000, 1100, 1166, 1167, 1200, 1334, 2000):
            clock[0] = now
            self.assertTrue(link.pump(now))
        cmd = B.encode(B.PROMPT, 12)
        self.assertEqual(fake.frames, [(0x53, cmd, 1000), (0x53, cmd, 1167), (0x53, cmd, 1334)])
        self.assertFalse(link.busy())
        self.assertEqual(link.last_send, 1334)

    def test_a_late_update_still_sends_only_one_frame(self):
        fake = FakeIR()
        link = self.make_beam(self.make_sender(fake))
        link.send(B.VERDICT, 1, 1000)
        link.pump(5000)
        self.assertEqual(len(fake.frames), 1)
        self.assertEqual(link.next_due, 5000 + B.FRAME_MS + B.GAP_MS)

    def test_a_new_beam_waits_for_the_frame_gap(self):
        fake = FakeIR()
        link = self.make_beam(self.make_sender(fake))
        link.send(B.VERDICT, 1, 1000)
        link.pump(1000)
        link.send(B.VERDICT, 2, 1050)
        self.assertEqual(link.queue, [2] * B.BURST)
        link.pump(1050)
        self.assertEqual(len(fake.frames), 1)
        link.pump(1167)
        self.assertEqual([frame[1] for frame in fake.frames], [1, 2])

    def test_a_failed_send_drops_and_releases_the_transmitter(self):
        fake = FakeIR(send_error=OSError("pio"))
        link = self.make_beam(self.make_sender(fake))
        self.assertTrue(link.send(B.VERDICT, 0, 1000))
        self.assertFalse(link.pump(1000))
        self.assertFalse(link.busy())
        self.assertIsNone(link.tx)
        self.assertEqual(fake.senders[0].stopped, 1)
        self.assertFalse(link.send(B.VERDICT, 0, 2000))


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
