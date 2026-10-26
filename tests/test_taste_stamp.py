"""Tests for the Taste Stamp & Creative 8-Ball app in badge/apps/taste_stamp.

The app's modules are loaded under unique taste_stamp_* names and are never
registered in sys.modules, so these tests can share a process with other
apps' tests that vendor helpers with generic names. AppTests runs the whole
app against a fake badge runtime; it imports the helpers under their real
names inside a patched sys.modules, sys.path and importer cache, all of
which are restored after every test.
"""

import array
import ast
import collections
import contextlib
import copy
import math
import os
import random
import re
import struct
import sys
import tokenize
import types
import unittest
import zlib
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "badge" / "apps" / "taste_stamp"
HELPERS = ("beam", "eightball", "motion", "stamp", "verdicts")
APP_FILES = ("__init__.py",) + tuple(name + ".py" for name in HELPERS)


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

    def test_symmetries_map_the_d20_onto_itself(self):
        ball = E.Ball(V.Rng(13).random)
        poses = []
        for index in range(20):
            for corner in range(3):
                g = ball.symmetry(index, corner)
                for v in ball.verts:
                    moved = rotate(g, v)
                    self.assertLess(min(math.dist(moved, w) for w in ball.verts), 1e-9)
                self.assertLess(math.dist(rotate(g, ball.normals[0]), ball.normals[index]), 1e-9)
                for other in poses:
                    self.assertGreater(E.q_angle(g, other), 1.0)
                poses.append(g)
        self.assertLess(E.q_angle(ball.symmetry(0, 0), (1.0, 0.0, 0.0, 0.0)), 1e-6)

    def test_spins_reroll_only_while_the_numbers_are_hidden(self):
        # A reroll shows up as a jump bigger than one frame of spin. A kick
        # just past BLUR_SPEED drops below it within a frame, so it shows its
        # numbers and must never reroll.
        step = E.MAX_SPIN * 16 / 1000 + 0.01
        for strength, rerolls in ((18, 1), (E.BLUR_SPEED + 0.1, 0), (5, 0)):
            ball = E.Ball(V.Rng(14).random)
            q = ball.q
            ball.kick(strength, 0)
            jumps = []
            t = 0
            while ball.state != E.LANDED:
                t += 16
                ball.update(16, t)
                if E.q_angle(q, ball.q) > step:
                    jumps.append(ball.speed())
                q = ball.q
            self.assertEqual(len(jumps), rerolls, strength)
            for speed in jumps:
                self.assertGreaterEqual(speed, E.BLUR_SPEED)

    def test_a_nudge_never_rerolls_just_before_the_numbers_show(self):
        # A reversal nudge adds to a d20 that may have slowed enough to show
        # its numbers. Rerolling just past BLUR_SPEED showed them again a
        # frame later on different faces, so a reroll must leave them hidden
        # for at least a quarter of a second.
        step = E.MAX_SPIN * 16 / 1000 + 0.01
        hidden = []
        for seed in range(120):
            for slow in (E.BLUR_SPEED, 4.9):
                ball = E.Ball(V.Rng(seed).random)
                ball.kick(18, 0)
                t = 0
                while ball.speed() >= slow:
                    t += 16
                    ball.update(16, t)
                ball.kick(5, t)
                q = ball.q
                swapped = None
                while ball.state == E.SPINNING:
                    t += 16
                    ball.update(16, t)
                    if E.q_angle(q, ball.q) > step:
                        self.assertIsNone(swapped, seed)
                        swapped = t
                    q = ball.q
                    if swapped is not None and ball.speed() < E.BLUR_SPEED:
                        hidden.append(t - swapped)
                        break
        self.assertGreaterEqual(len(hidden), 10)
        self.assertGreaterEqual(min(hidden), 250)

    def test_repeat_spins_land_fairly(self):
        # Friction turns the d20 through nearly the same angle on every spin,
        # so without the reroll back-to-back DOWN presses landed on the same
        # face or a neighbour about 70% of the time. A fair d20 does that 20%
        # of the time, and each landing is uncorrelated with the last.
        faces = self.faces
        near = [[j for j in range(20) if len(set(faces[i]) & set(faces[j])) >= 2] for i in range(20)]
        for strength in (18, 16, 14):
            ball = E.Ball(V.Rng(strength).random)
            counts = [0] * 20
            close = 0
            dots = 0.0
            t = 0
            for trial in range(401):
                last = ball.face
                ball.kick(strength, t)
                while ball.state != E.LANDED:
                    t += 16
                    ball.update(16, t)
                if trial == 0:
                    continue
                counts[ball.face] += 1
                if ball.face in near[last]:
                    close += 1
                dots += sum(a * b for a, b in zip(ball.normals[ball.face], ball.normals[last]))
            self.assertNotIn(0, counts, strength)
            self.assertTrue(0.12 < close / 400 < 0.28, (strength, close))
            self.assertLess(abs(dots / 400), 0.12, (strength, dots))

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
    def make_beam(self, sender=None, receiving=False):
        return B.Beam(len(V.VERDICTS), len(V.PROMPTS), sender, receiving)

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

    def test_own_frames_are_ignored_as_echoes(self):
        fake = FakeIR()
        link = self.make_beam(self.make_sender(fake))
        link.send(B.VERDICT, 3, 1000)
        link.pump(1000)
        link.heard(3)
        self.assertIsNone(link.receive(1016))
        self.assertEqual(link.count, 0)
        link.pump(1167)
        link.pump(1334)
        link.heard(3)
        self.assertIsNone(link.receive(1334 + B.ECHO_MS - 1))
        link.heard(3)
        self.assertIsNone(link.receive(1334 + 400))
        link.heard(5)
        self.assertEqual(link.receive(1334 + 450), (B.VERDICT, 5))

    def test_the_inbox_keeps_the_first_16_frames(self):
        link = self.make_beam()
        for cmd in range(0x40, 0x54):
            link.heard(cmd)
        self.assertEqual(link.count, B.INBOX_LIMIT)
        self.assertEqual(link.inbox, list(range(0x40, 0x50)))
        self.assertEqual(link.receive(5000), (B.PROMPT, 15))
        self.assertEqual(link.count, 0)
        self.assertIsNone(link.receive(5001))

    def test_receive_skips_foreign_bytes(self):
        link = self.make_beam()
        link.heard(2)
        link.heard(0x30)
        self.assertEqual(link.receive(5000), (B.VERDICT, 2))
        link.heard(0xFF)
        self.assertIsNone(link.receive(5100))

    def test_repeats_are_deduped_until_the_sender_goes_quiet(self):
        link = self.make_beam()
        results = []
        for now in (10000, 10500, 11600, 12900):
            link.heard(3)
            link.heard(3)
            results.append(link.receive(now))
        self.assertEqual(results, [(B.VERDICT, 3), None, None, (B.VERDICT, 3)])
        link.heard(4)
        self.assertEqual(link.receive(12950), (B.VERDICT, 4))

    def test_close_releases_ir_once(self):
        fake = FakeIR()
        with fake.patch():
            link = self.make_beam(B.make_sender(), receiving=True)
            link.close()
            link.close()
        self.assertEqual(fake.senders[0].stopped, 1)
        self.assertEqual(fake.closed, 1)
        self.assertIsNone(link.tx)
        self.assertFalse(link.receiving)
        self.assertFalse(link.can_send())

    def test_close_swallows_ir_errors(self):
        fake = FakeIR(stop_error=OSError("stop"), close_error=OSError("close"))
        with fake.patch():
            link = self.make_beam(B.make_sender(), receiving=True)
            link.close()
        self.assertIsNone(link.tx)
        self.assertFalse(link.receiving)


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

    def test_sections_cover_usage_hardware_and_simulator(self):
        headings = [line for line in self.text.splitlines() if line.startswith("#")]
        for heading in ("## Usage", "### Stamp mode", "### Creative 8-Ball mode", "### Beaming",
                        "## Hardware", "## Badge Simulator", "## Files"):
            self.assertIn(heading, headings)
        self.assertLess(headings.index("## Usage"), headings.index("## Hardware"))

    def test_readme_documents_the_hardware_contract(self):
        for phrase in ("running Taste Stamp", "badge.upside_down()", "badge.imu()", "GPIO16",
                       "GPIO17", "badgeware.ir", "0x53", "never transmits on `0x45`"):
            self.assertIn(phrase, self.text)
        for verdict in V.VERDICTS:
            self.assertIn(verdict, self.text)
        for name in APP_FILES:
            self.assertIn("`" + name + "`", self.text)


STR_METHODS = {"isalnum", "ljust", "rjust", "title", "zfill", "capitalize", "removeprefix",
               "removesuffix", "casefold", "swapcase", "isnumeric", "isprintable", "format_map"}
MODULE_ATTRS = {
    "random": {"shuffle", "sample", "choices", "Random"},
    "math": {"hypot", "dist", "prod", "gcd", "fsum"},
    "time": {"monotonic", "perf_counter", "strftime"},
    "hashlib": {"md5", "sha1"},
    "collections": {"Counter"},
    "json": {"JSONDecodeError"},
    "functools": {"lru_cache", "cache", "cmp_to_key"},
    "operator": {"itemgetter"},
    "itertools": {"product", "permutations", "combinations", "groupby", "zip_longest",
                  "takewhile", "dropwhile", "pairwise"},
    "os": {"urandom", "environ", "walk", "replace"},
    "os.path": {"splitext", "getsize"},
}
BANNED_MODULES = {"textwrap", "dataclasses", "typing", "enum", "bisect", "__future__", "abc",
                  "datetime", "pathlib"}
BANNED_EXCEPTIONS = {
    "FileNotFoundError", "FileExistsError", "PermissionError", "IsADirectoryError",
    "NotADirectoryError", "TimeoutError", "ConnectionError", "ConnectionResetError",
    "ConnectionAbortedError", "ConnectionRefusedError", "BrokenPipeError", "InterruptedError",
    "BlockingIOError", "ChildProcessError", "ProcessLookupError", "UnicodeDecodeError",
    "UnicodeEncodeError", "ModuleNotFoundError", "RecursionError", "UnboundLocalError", "IOError",
    "EnvironmentError", "Warning", "UserWarning", "DeprecationWarning", "RuntimeWarning",
    "FutureWarning", "PendingDeprecationWarning", "SyntaxWarning", "ImportWarning",
    "UnicodeWarning", "BytesWarning", "ResourceWarning", "EncodingWarning",
}
BANNED_ATTRS = {"bit_length", "hexdigest", "_replace", "_asdict", "__doc__", "__qualname__"}
# App policy: dict and set order is hash order on the badge, and sorts are unstable.
POLICY_METHODS = {"sort", "keys", "values", "items"}
ALLOWED_IMPORTS = {"os", "random", "sys", "array", "math", "aye_arr.nec",
                   "aye_arr.nec.remotes.descriptor", "badgeware.ir"} | set(HELPERS)


def dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def check_call(node):
    func = node.func
    name = func.id if isinstance(func, ast.Name) else None
    attr = func.attr if isinstance(func, ast.Attribute) else None
    words = {k.arg for k in node.keywords}
    nargs = len(node.args)
    if attr in STR_METHODS:
        yield "str." + attr + "() is missing"
    if attr == "split" and words:
        yield "str.split takes no keywords"
    if attr == "center" and nargs > 1:
        yield "str.center takes no fillchar"
    if attr == "union" and nargs > 1:
        yield "set.union takes one argument"
    if attr == "from_bytes" and "signed" in words:
        yield "from_bytes(signed=) is a TypeError"
    if "deque" in (name, attr) and (words or nargs != 2):
        yield "deque needs exactly (iterable, maxlen)"
    if dotted(func) in ("json.dumps", "json.dump") and words:
        yield "json.dumps takes no keywords"
    if name == "open" and "newline" in words:
        yield "open(newline=) is a TypeError"
    if (name == "sum" and "start" in words) or (name == "round" and "ndigits" in words):
        yield name + "() keyword is a TypeError"
    if name == "iter" and nargs == 2:
        yield "iter(callable, sentinel) is missing"
    if name == "isinstance" and nargs == 2 and isinstance(node.args[1], ast.BinOp):
        yield "isinstance(x, A | B) is a TypeError"
    if name in ("vars", "hash"):
        yield name + "() is missing or differs"
    if name == "sorted" or attr in POLICY_METHODS:
        yield "unstable sort or hash-ordered dict view"
    if dotted(func) == "random.getrandbits":
        arg = node.args[0] if node.args else None
        if not (isinstance(arg, ast.Constant) and isinstance(arg.value, int) and arg.value <= 32):
            yield "getrandbits needs a constant <= 32"


def check_node(node, parent):
    if isinstance(node, ast.Call):
        yield from check_call(node)
    elif isinstance(node, ast.Attribute):
        module, _, attr = (dotted(node) or "").rpartition(".")
        if attr in MODULE_ATTRS.get(module, ()):
            yield module + "." + attr + " is missing"
        if node.attr in BANNED_ATTRS:
            yield node.attr + " is missing"
    elif isinstance(node, ast.Name):
        if node.id in BANNED_EXCEPTIONS or node.id == "__builtins__":
            yield node.id + " is undefined"
    elif isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name.split(".")[0] in BANNED_MODULES:
                yield "module " + alias.name + " is missing"
    elif isinstance(node, ast.ImportFrom):
        module = node.module or ""
        if module.split(".")[0] in BANNED_MODULES:
            yield "module " + module + " is missing"
        for alias in node.names:
            if alias.name in MODULE_ATTRS.get(module, ()):
                yield module + "." + alias.name + " is missing"
    elif isinstance(node, ast.Slice):
        if node.step is not None:
            yield "step slices raise NotImplementedError"
    elif isinstance(node, ast.Starred):
        if isinstance(parent, (ast.List, ast.Tuple, ast.Set)) and isinstance(node.ctx, ast.Load):
            yield "starred display is a SyntaxError"
    elif isinstance(node, ast.Dict):
        if None in node.keys:
            yield "dict ** display is a SyntaxError"
    elif isinstance(node, ast.ClassDef):
        if any(k.arg == "metaclass" for k in node.keywords):
            yield "metaclass= is unsupported"
    elif isinstance(node, ast.FunctionDef):
        if node.name == "__init_subclass__":
            yield "__init_subclass__ is never called"
    for name in ("Match", "TryStar", "TypeAlias"):
        cls = getattr(ast, name, None)
        if cls is not None and isinstance(node, cls):
            yield name + " syntax is unsupported"


def parenthesized_with(source):
    tokens = [t for t in tokenize.generate_tokens(iter(source.splitlines(True)).__next__)
              if t.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT)]
    for i, tok in enumerate(tokens[:-1]):
        if tok.string == "with" and tokens[i + 1].string == "(":
            depth = 0
            for later in tokens[i + 1:]:
                depth += {"(": 1, ")": -1}.get(later.string, 0)
                if depth == 1 and later.string == "as":
                    yield tok.start[0]
                    break
                if depth == 0:
                    break


def scan(source):
    tree = ast.parse(source)
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    found = []
    for node in ast.walk(tree):
        for message in check_node(node, parents.get(node)):
            found.append((getattr(node, "lineno", 0), message))
    for line in parenthesized_with(source):
        found.append((line, "parenthesized with-items are a SyntaxError"))
    return found


BAD_SNIPPETS = (
    "s.ljust(4)", "s.rjust(4)", "s.zfill(3)", "s.title()", "s.isalnum()", "s.capitalize()",
    "s.removeprefix('a')", "s.casefold()", "s.swapcase()", "s.isnumeric()", "s.isprintable()",
    "s.format_map({})", "s.split(sep=' ')", "s.split(' ', maxsplit=1)", "s.center(9, '*')",
    "random.shuffle(x)", "random.sample(x, 2)", "random.choices(x)", "random.Random(3)",
    "from random import shuffle", "math.hypot(1, 2)", "math.dist(a, b)", "math.prod(x)",
    "math.gcd(4, 6)", "math.fsum(x)", "n.bit_length()", "time.monotonic()",
    "time.perf_counter()", "time.strftime('%H')", "hashlib.md5(b'')", "hashlib.sha1(b'')",
    "h.hexdigest()", "from collections import Counter", "collections.Counter(x)",
    "deque((), maxlen=4)", "deque()", "deque(x)", "json.dumps(x, indent=2)",
    "json.dumps(x, ensure_ascii=False)", "json.JSONDecodeError", "import textwrap",
    "import dataclasses", "from typing import List", "import enum", "import bisect",
    "from __future__ import annotations", "import abc", "import datetime",
    "from pathlib import Path", "functools.lru_cache(None)", "from functools import cache",
    "from operator import itemgetter", "itertools.product(a, b)", "from itertools import groupby",
    "itertools.zip_longest(a, b)", "os.path.splitext(p)", "os.path.getsize(p)", "os.urandom(4)",
    "os.environ", "os.walk('.')", "os.replace(a, b)", "vars(x)", "hash(x)", "__builtins__",
    "p._replace(x=1)", "p._asdict()", "f.__doc__", "f.__qualname__",
    "class A:\n    def __init_subclass__(cls):\n        pass\n",
    "open(p, newline='')", "int.from_bytes(b, 'big', signed=True)", "sum(x, start=1)",
    "round(x, ndigits=2)", "iter(f, None)", "a.union(b, c)", "class A(metaclass=M):\n    pass\n",
    "isinstance(x, int | float)", "with (open(a) as f, open(b) as g):\n    pass\n",
    "s[::-1]", "x[::2]", "del x[::2]", "x[1:9:3]", "[*a, *b]", "(*a, b)", "{*a}", "{**d, 'k': 1}",
    "def f():\n    return *a, b\n", "try:\n    pass\nexcept FileNotFoundError:\n    pass\n",
    "try:\n    pass\nexcept (ValueError, IOError):\n    pass\n", "raise ModuleNotFoundError()",
    "except_ = TimeoutError", "UnicodeDecodeError", "RecursionError", "EnvironmentError",
    "ConnectionResetError", "UserWarning", "sorted(x)", "x.sort()", "d.keys()", "d.values()",
    "d.items()", "random.getrandbits(40)", "random.getrandbits(n)",
)

GOOD_SNIPPETS = (
    "s.center(9)", "s.split(' ', 1)", "s.split()", "s.upper().strip()", "random.randint(0, 3)",
    "random.getrandbits(32)", "random.choice(x)", "math.sqrt(2)", "deque((), 4)",
    "json.dumps(x)", "a, *rest = x", "for a, *b in x:\n    pass\n", "f(*a, **kw)",
    "shape.custom(*[array('f', c) for c in cs])", "x[1:3]", "x[:]", "x[::]", "del x[:2]",
    "with open(p) as f:\n    pass\n", "with (open(p)) as f:\n    pass\n",
    "try:\n    pass\nexcept OSError:\n    pass\n",
    "try:\n    pass\nexcept (ValueError, ImportError, UnicodeError):\n    pass\n",
    "isinstance(x, (int, float))", "open(p, encoding='utf-8')", "import os",
    "''.join(reversed(s))", "round(x, 2)", "iter(x)", "a.union(b)", "sum(x)",
    "int.from_bytes(b, 'big')", "class A(B):\n    pass\n", "def f(x: int) -> int:\n    return x\n",
    "self.title_text = 1", "self.items_count += 1", "d = {'k': 1}", "t = (a, b)", "s = {a, b}",
    "import builtins", "x = 0x53",
)


class MicroPythonCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {name: (APP / name).read_text(encoding="utf-8") for name in APP_FILES}
        cls.trees = {name: ast.parse(src, name) for name, src in cls.sources.items()}

    def test_scanner_flags_known_badge_crashes(self):
        for snippet in BAD_SNIPPETS:
            self.assertTrue(scan(snippet), snippet)

    def test_scanner_allows_badge_safe_forms(self):
        for snippet in GOOD_SNIPPETS:
            self.assertEqual(scan(snippet), [], snippet)

    def test_app_sources_are_badge_safe(self):
        problems = []
        for name, source in self.sources.items():
            for line, message in scan(source):
                problems.append("%s:%d %s" % (name, line, message))
        self.assertEqual(problems, [])

    def test_imports_are_on_the_allowlist(self):
        for name, tree in self.trees.items():
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    modules = [node.module]
                else:
                    continue
                for module in modules:
                    self.assertIn(module, ALLOWED_IMPORTS, name + " imports " + str(module))

    def test_never_uses_the_event_beacon_address(self):
        for name, source in self.sources.items():
            tokens = tokenize.generate_tokens(iter(source.splitlines(True)).__next__)
            for tok in tokens:
                if tok.type == tokenize.NUMBER and tok.string.lower().startswith("0x"):
                    self.assertNotEqual(int(tok.string, 16), 0x45, "%s:%d" % (name, tok.start[0]))

    def test_every_ir_frame_goes_to_the_app_address(self):
        calls = []
        for tree in self.trees.values():
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                        and node.func.attr == "send_addr_cmd":
                    calls.append(node)
        self.assertTrue(calls)
        for call in calls:
            self.assertIsInstance(call.args[0], ast.Name)
            self.assertEqual(call.args[0].id, "ADDRESS")

    def test_sources_are_ascii(self):
        for name in APP_FILES + ("README.md",):
            data = (APP / name).read_bytes()
            self.assertTrue(all(b < 128 for b in data), name)

    def test_timing_constants_are_integer_milliseconds(self):
        floats_allowed = {"SPLAT_DRAG_MS"}
        checked = 0
        for name, tree in self.trees.items():
            for node in ast.walk(tree):
                if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
                    continue
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.endswith(("_MS", "_PCT")):
                        checked += 1
                        if target.id not in floats_allowed:
                            self.assertIsInstance(node.value.value, int, name + " " + target.id)
        self.assertGreater(checked, 20)

    def test_does_not_import_badge_or_write_secrets(self):
        for name, source in self.sources.items():
            self.assertNotIn("import badge", source, name)
            self.assertNotIn("secrets", source, name)


# A fake badge runtime for AppTests. The fakes check their arguments the way
# the firmware needs them and record every problem on the runtime, because
# the app deliberately swallows some exceptions.

Vec2 = collections.namedtuple("Vec2", "x y")
BUTTONS = {"UP": 1, "DOWN": 2, "LEFT": 4, "RIGHT": 8, "SELECT": 16, "BACK": 32}
HIRES = 0x100
VSYNC = 0x200
FONT_METRICS = {"font:nope": (6, 12), "font:sins": (5, 8)}


def finite_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def is_rgb(v):
    return isinstance(v, tuple) and len(v) == 5 and v[0] == "rgb"


def is_pen(v):
    return is_rgb(v) or (isinstance(v, tuple) and len(v) == 4 and v[0] == "pattern")


def pen(c, alpha=255):
    return ("rgb", c[0], c[1], c[2], alpha)


class FakeMat3:
    # An immutable affine transform (a, b, c, d, e, f) mapping (x, y) to
    # (ax + by + c, dx + ey + f). Calls post-multiply like the firmware's
    # mat3, so mat3().translate(x, y).rotate(r) rotates about (x, y).

    def __init__(self, rt, m=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0)):
        self.rt = rt
        self.m = m

    def _then(self, a, b, c, d, e, f):
        m = self.m
        return FakeMat3(self.rt, (
            m[0] * a + m[1] * d, m[0] * b + m[1] * e, m[0] * c + m[1] * f + m[2],
            m[3] * a + m[4] * d, m[3] * b + m[4] * e, m[3] * c + m[4] * f + m[5],
        ))

    def translate(self, x, y):
        self.rt.check(finite_number(x) and finite_number(y), "mat3.translate", (x, y))
        return self._then(1.0, 0.0, x, 0.0, 1.0, y)

    def rotate(self, degrees):
        self.rt.check(finite_number(degrees), "mat3.rotate", degrees)
        a = math.radians(degrees)
        return self._then(math.cos(a), -math.sin(a), 0.0, math.sin(a), math.cos(a), 0.0)

    def scale(self, sx, sy=None):
        if sy is None:
            sy = sx
        self.rt.check(finite_number(sx) and finite_number(sy), "mat3.scale", (sx, sy))
        return self._then(sx, 0.0, 0.0, 0.0, sy, 0.0)

    def apply(self, x, y):
        m = self.m
        return (m[0] * x + m[1] * y + m[2], m[3] * x + m[4] * y + m[5])


class FakeShape:
    def __init__(self, rt, kind, args, arrays=(), width=None):
        self.rt = rt
        self.kind = kind
        self.args = args
        self.arrays = arrays
        self.copies = [list(a) for a in arrays]
        self.width = width
        self.transform = None

    def stroke(self, width):
        self.rt.check(finite_number(width) and width > 0, "shape.stroke", width)
        return FakeShape(self.rt, self.kind, self.args, self.arrays, width)


class FakeShapeModule:
    def __init__(self, rt):
        self.rt = rt

    def numbers(self, what, values):
        self.rt.check(all(finite_number(v) for v in values), what, values)

    def circle(self, x, y, r):
        self.numbers("shape.circle", (x, y, r))
        self.rt.check(r > 0, "shape.circle radius", r)
        return FakeShape(self.rt, "circle", (x, y, r))

    def rounded_rectangle(self, x, y, w, h, r):
        self.numbers("shape.rounded_rectangle", (x, y, w, h, r))
        self.rt.check(w > 0 and h > 0 and r >= 0, "shape.rounded_rectangle size", (w, h, r))
        return FakeShape(self.rt, "rounded_rectangle", (x, y, w, h, r))

    def line(self, x1, y1, x2, y2, width):
        self.numbers("shape.line", (x1, y1, x2, y2, width))
        self.rt.check(width > 0, "shape.line width", width)
        return FakeShape(self.rt, "line", (x1, y1, x2, y2, width))

    def custom(self, *arrays):
        ok = len(arrays) > 0
        for a in arrays:
            ok = ok and isinstance(a, array.array) and a.typecode == "f"
            ok = ok and len(a) >= 6 and len(a) % 2 == 0 and all(math.isfinite(v) for v in a)
        self.rt.check(ok, "shape.custom", arrays)
        return FakeShape(self.rt, "custom", (), arrays)


class FakeColor:
    def __init__(self, rt):
        self.rt = rt

    def rgb(self, r, g, b, a=255):
        values = (r, g, b, a)
        ok = all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 255 for v in values)
        self.rt.check(ok, "color.rgb", values)
        return ("rgb", r, g, b, a)


class FakeBrush:
    def __init__(self, rt):
        self.rt = rt

    def pattern(self, first, second, rows):
        ok = is_rgb(first) and is_rgb(second) and isinstance(rows, (tuple, list)) and len(rows) == 8
        ok = ok and all(isinstance(v, int) and 0 <= v <= 255 for v in rows)
        self.rt.check(ok, "brush.pattern", (first, second, rows))
        return ("pattern", first, second, tuple(rows))


class FakeImageModule:
    OFF = "OFF"
    X2 = "X2"
    X4 = "X4"
    EVEN_ODD = "EVEN_ODD"
    NON_ZERO = "NON_ZERO"
    RGB565 = "RGB565"

    def __init__(self, rt):
        self.rt = rt

    def __call__(self, width, height, data=None, fmt=None):
        rt = self.rt
        ok = isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0
        rt.check(ok, "image size", (width, height))
        if data is None:
            rt.check(fmt is None, "image format without data", fmt)
            return FakeImage(rt, width, height)
        ok = isinstance(data, bytearray) and len(data) == width * height * 2 and fmt == self.RGB565
        rt.check(ok, "image data", (type(data), len(data), fmt))
        return FakeImage(rt, width, height, data, fmt)


class FakeImage:
    # Records draw calls in ops, as tuples that hold the pen and fill rule
    # in force when each call was made.
    INTERNAL = ("rt", "width", "height", "raw", "fmt", "ops")

    def __init__(self, rt, width, height, raw=None, fmt=None):
        object.__setattr__(self, "rt", None)
        self.width = width
        self.height = height
        if raw is not None:
            self.raw = raw
        self.fmt = fmt
        self.ops = []
        self.pen = ("rgb", 255, 255, 255, 255)
        self.fill_rule = "EVEN_ODD"
        self.font = None
        self.antialias = "OFF"
        self.rt = rt

    def __setattr__(self, name, value):
        rt = self.rt
        if rt is not None:
            if name == "pen":
                rt.check(is_pen(value), "image.pen", value)
            elif name == "fill_rule":
                rt.check(value in ("EVEN_ODD", "NON_ZERO"), "image.fill_rule", value)
            elif name == "font":
                rt.check(value in FONT_METRICS, "image.font", value)
            elif name == "antialias":
                rt.check(value in ("OFF", "X2", "X4"), "image.antialias", value)
            else:
                rt.check(name in self.INTERNAL, "unknown image attribute", name)
        object.__setattr__(self, name, value)

    def clear(self):
        self.rt.check(is_pen(self.pen), "image.clear pen", self.pen)
        self.ops = [("clear", self.pen)]

    def shape(self, s):
        rt = self.rt
        rt.check(isinstance(s, FakeShape), "image.shape", s)
        rt.check([list(a) for a in s.arrays] == s.copies, "points changed after shape.custom", s.kind)
        rt.check(s.transform is None or isinstance(s.transform, FakeMat3), "shape.transform", s.transform)
        self.ops.append(("shape", self.pen, s, self.fill_rule, s.transform))

    def blit(self, source, pos):
        rt = self.rt
        rt.check(isinstance(source, FakeImage) and source is not self, "image.blit source", source)
        ok = isinstance(pos, Vec2) and finite_number(pos.x) and finite_number(pos.y)
        rt.check(ok, "image.blit position", pos)
        self.ops.append(("blit", source, pos))

    def text(self, s, x, y):
        rt = self.rt
        rt.check(isinstance(s, str) and len(s) > 0 and all(32 <= ord(ch) < 127 for ch in s), "image.text", s)
        rt.check(finite_number(x) and finite_number(y), "image.text position", (x, y))
        rt.check(self.fill_rule == "EVEN_ODD", "vector text needs EVEN_ODD", self.fill_rule)
        rt.check(is_rgb(self.pen), "image.text pen", self.pen)
        rt.check(self.font in FONT_METRICS, "image.text font", self.font)
        self.ops.append(("text", self.pen, s, (x, y), self.font))

    def measure_text(self, s):
        self.rt.check(isinstance(s, str) and self.font in FONT_METRICS, "image.measure_text", (s, self.font))
        w, h = FONT_METRICS[self.font]
        return (w * len(s), h)

    def rectangle(self, x, y, w, h):
        ok = all(finite_number(v) for v in (x, y, w, h)) and w > 0 and h > 0
        self.rt.check(ok, "image.rectangle", (x, y, w, h))
        self.ops.append(("rectangle", self.pen, (x, y, w, h)))

    def resize(self, width, height):
        self.width = width
        self.height = height
        if hasattr(self, "raw"):
            self.raw = bytearray(width * height * 2)


class FakeBadge:
    def __init__(self, rt, imu_value=REST_UP, flipped=False, imu_error=None, flip_error=None, light_error=None):
        self.rt = rt
        self.ticks = 1000
        self.ticks_delta = 0
        self.default_clear = "firmware-clear"
        self.buttons = 0
        self.imu_value = imu_value
        self.flipped = flipped
        self.imu_error = imu_error
        self.flip_error = flip_error
        self.light_error = light_error
        self.modes = []
        self.lights = []
        self.light_ticks = []

    def mode(self, value):
        self.modes.append(value)
        if value & HIRES:
            self.rt.screen.resize(320, 240)
        else:
            self.rt.screen.resize(160, 120)

    def pressed(self, button):
        self.rt.check(button in BUTTONS.values(), "badge.pressed", button)
        return bool(self.buttons & button)

    def upside_down(self):
        if self.flip_error is not None:
            raise self.flip_error
        return self.flipped

    def imu(self):
        if self.imu_error is not None:
            raise self.imu_error
        return self.imu_value

    def caselights(self, *levels):
        if not levels:
            return [0.0] * 4
        ok = len(levels) in (1, 4) and all(finite_number(v) and 0 <= v <= 1 for v in levels)
        self.rt.check(ok, "badge.caselights", levels)
        self.lights.append(tuple(levels))
        self.light_ticks.append(self.ticks)
        if self.light_error is not None:
            raise self.light_error
        return list(levels) * (4 // len(levels))


class FakeRuntime:
    # The globals the badge launcher gives an app.

    def __init__(self, screen_raw=True, dirs=(), is_dir_error=None, has_is_dir=True, **badge_options):
        self.problems = []
        self.runs = []
        self.dir_calls = []
        self.dirs = dirs
        self.is_dir_error = is_dir_error
        self.has_is_dir = has_is_dir
        self.image = FakeImageModule(self)
        if screen_raw:
            self.screen = self.image(160, 120, bytearray(160 * 120 * 2), FakeImageModule.RGB565)
        else:
            self.screen = self.image(160, 120)
        self.badge = FakeBadge(self, **badge_options)
        self.shape = FakeShapeModule(self)
        self.color = FakeColor(self)
        self.brush = FakeBrush(self)
        self.font = SimpleNamespace(nope="font:nope", sins="font:sins")

    def fail(self, message):
        self.problems.append(message)
        raise AssertionError(message)

    def check(self, ok, what, detail=None):
        if not ok:
            self.fail("%s: %r" % (what, detail))

    def is_dir(self, path):
        self.dir_calls.append(path)
        if self.is_dir_error is not None:
            raise self.is_dir_error
        return path in self.dirs

    def run(self, update):
        self.runs.append(update)

    def vec2(self, x, y):
        self.check(finite_number(x) and finite_number(y), "vec2", (x, y))
        return Vec2(x, y)

    def mat3(self):
        return FakeMat3(self)

    def names(self):
        names = {
            "badge": self.badge,
            "screen": self.screen,
            "image": self.image,
            "font": self.font,
            "color": self.color,
            "shape": self.shape,
            "brush": self.brush,
            "vec2": self.vec2,
            "mat3": self.mat3,
            "run": self.run,
            "HIRES": HIRES,
            "VSYNC": VSYNC,
        }
        for name, value in BUTTONS.items():
            names["BUTTON_" + name] = value
        if self.has_is_dir:
            names["is_dir"] = self.is_dir
        return names


class AppTests(unittest.TestCase):
    # Runs the whole app frame by frame against FakeRuntime and FakeIR.
    # Every step checks the runtime saw no bad calls and the frame is sane.

    @classmethod
    def setUpClass(cls):
        path = APP / "__init__.py"
        cls.code = compile(path.read_text(encoding="utf-8"), str(path), "exec")

    def setUp(self):
        saved_path = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved_path)
        for patcher in (
            mock.patch.dict(sys.modules),
            mock.patch.dict(sys.path_importer_cache),
            mock.patch.object(sys, "dont_write_bytecode", True),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(os, "chdir")
        self.chdir = patcher.start()
        self.addCleanup(patcher.stop)

    def launch(self, ir=None, rt=None, seed=0x5EED, **options):
        ir = ir or FakeIR()
        rt = rt or FakeRuntime(**options)
        ir.clock = lambda: rt.badge.ticks
        sys.modules.update(ir.modules())
        sys.path.insert(0, str(APP))
        module = types.ModuleType("taste_stamp_app")
        module.__file__ = str(APP / "__init__.py")
        module.__dict__.update(rt.names())
        with mock.patch.object(random, "getrandbits", return_value=seed):
            exec(self.code, module.__dict__)
        self.assertEqual(rt.problems, [])
        self.rt = rt
        self.ir = ir
        self.A = module
        self.app = module.app
        self.badge = rt.badge
        self.screen = rt.screen
        return module

    def step(self, *buttons, ms=16, **badge_state):
        badge = self.badge
        for name, value in badge_state.items():
            self.assertTrue(hasattr(badge, name), name)
            setattr(badge, name, value)
        badge.ticks += ms
        badge.ticks_delta = ms
        mask = 0
        for name in buttons:
            mask |= BUTTONS[name]
        badge.buttons = mask
        self.screen.ops = []
        sent = len(self.ir.frames)
        result = self.A.update()
        badge.buttons = 0
        self.assertEqual(self.rt.problems, [])
        self.assertLessEqual(len(self.ir.frames) - sent, 1)
        if result is None:
            self.check_frame()
        else:
            self.assertIs(result, False)
        return result

    def check_frame(self):
        A = self.A
        app = self.app
        ops = self.screen.ops
        self.assertTrue(ops)
        if app.mode == A.STAMP_MODE:
            if ops[0][0] == "clear":
                self.assertEqual(ops[0], ("clear", A.DESK_C))
                self.assertEqual(ops[1][:2], ("blit", app.desk))
                offset = ops[1][2]
                self.assertTrue(offset.x or offset.y)
                for v in offset:
                    self.assertIsInstance(v, int)
                    self.assertLessEqual(abs(v), 9)
            else:
                self.assertEqual(ops[0], ("blit", app.desk, Vec2(0, 0)))
        else:
            self.assertEqual(ops[0], ("blit", app.ball_bg, Vec2(0, 0)))
        self.assertEqual(self.screen.fill_rule, "EVEN_ODD")
        self.assertEqual(self.screen.font, "font:nope")
        self.assertLessEqual(len(app.marks), 4)

    def run_for(self, ms, **badge_state):
        end = self.badge.ticks + ms
        while self.badge.ticks < end:
            self.step(**badge_state)

    def run_until(self, done, limit_ms, **badge_state):
        end = self.badge.ticks + limit_ms
        while not done():
            self.assertLess(self.badge.ticks, end, "timed out")
            self.step(**badge_state)

    def spy(self, name):
        patcher = mock.patch.object(self.app, name, wraps=getattr(self.app, name))
        spy = patcher.start()
        self.addCleanup(patcher.stop)
        return spy

    def shapes(self, target=None, kind=None):
        ops = (target or self.screen).ops
        return [op for op in ops if op[0] == "shape" and (kind is None or op[2].kind == kind)]

    def texts(self, target=None):
        return [op[2] for op in (target or self.screen).ops if op[0] == "text"]

    def text_at(self, x, y):
        for op in self.screen.ops:
            if op[0] == "text" and op[3] == (x, y):
                return op
        return None

    def rings(self):
        return [op for op in self.shapes(kind="circle") if op[2].width == 2]

    def landed(self):
        return self.app.ball.state == self.A.eightball.LANDED

    def check_d20(self):
        A = self.A
        ops = self.shapes()
        faces = [op for op in ops if op[2].kind == "custom" and len(op[2].arrays) == 1
                 and op[2].arrays[0] is A.FACE_POINTS]
        self.assertTrue(5 <= len(faces) <= 20, len(faces))
        for op in faces:
            self.assertIn(op[1], A.SHADES)
            self.assertIsNone(op[4])
        lines = [op for op in ops if op[2].kind == "line"]
        self.assertTrue(1 <= len(lines) <= 30, len(lines))
        for op in lines:
            self.assertEqual((op[1], op[2].args[4]), (A.EDGE_C, 1.3))
        numbers = [op for op in ops if any(op[2] is s for s in A.NUMBER_SHAPES[1:])]
        for op in numbers:
            self.assertEqual(op[3], "NON_ZERO")
            self.assertIsInstance(op[4], FakeMat3)
        return numbers

    def test_launch_sets_up_the_screen_ir_and_desk(self):
        A = self.launch()
        rt, ir, app, badge, screen = self.rt, self.ir, self.app, self.badge, self.screen
        self.assertEqual(badge.modes, [HIRES | VSYNC])
        self.assertEqual((screen.width, screen.height), (320, 240))
        self.assertEqual((screen.antialias, screen.fill_rule, screen.font), ("X2", "EVEN_ODD", "font:nope"))
        self.assertEqual(rt.runs, [A.update])
        self.assertIsNone(badge.default_clear)
        self.assertEqual(A.previous_clear, "firmware-clear")
        self.chdir.assert_called_once_with("/system/apps/taste_stamp")
        self.assertEqual(sys.path[0], "/system/apps/taste_stamp")
        self.assertEqual(len(rt.dir_calls), 4)
        self.assertEqual(len(ir.senders), 1)
        sender = ir.senders[0]
        self.assertEqual(sender.args, (16, 0, 1))
        self.assertTrue(sender.started)
        self.assertIs(app.link.tx, sender)
        self.assertEqual(len(ir.bound), 1)
        bound = ir.bound[0]
        self.assertEqual((bound.NAME, bound.ADDRESS), ("TasteStamp", 0x53))
        self.assertIsInstance(bound, ir.RemoteDescriptor)
        self.assertEqual(bound.on_any, app.link.heard)
        self.assertTrue(app.link.receiving)
        self.assertEqual(ir.descriptor_inits, 1)
        for name in HELPERS:
            module = sys.modules[name]
            self.assertEqual(Path(module.__file__).parent, APP)
            self.assertIs(getattr(A, name), module)
        desk = app.desk
        self.assertEqual((desk.width, desk.height, desk.fmt, len(desk.raw)), (320, 240, "RGB565", 320 * 240 * 2))
        self.assertEqual(self.texts(desk), ["creative-brief.md"])
        self.assertEqual(badge.lights, [])
        self.assertEqual(A.STAMPS, [None] * 7)
        self.assertEqual(ir.frames, [])
        self.assertIsNone(app.ball_bg)

    def test_app_dir_is_the_first_that_exists(self):
        cases = (
            (dict(dirs=("/remote/apps/taste_stamp", "/system/apps/taste_stamp")), "/remote/apps/taste_stamp", 1),
            (dict(dirs=()), "/system/apps/taste_stamp", 4),
            (dict(is_dir_error=OSError(2, "no such directory")), "/system/apps/taste_stamp", 4),
            (dict(has_is_dir=False), "/system/apps/taste_stamp", 0),
        )
        for options, expected, probes in cases:
            with self.subTest(options=options):
                self.chdir.reset_mock()
                A = self.launch(**options)
                self.assertEqual(A.APP_DIR, expected)
                self.chdir.assert_called_once_with(expected)
                self.assertEqual(sys.path[0], expected)
                self.assertEqual(len(self.rt.dir_calls), probes)
                self.step("DOWN")
                self.assertIsNotNone(self.app.slam)
                A.on_exit()
        self.chdir.reset_mock()
        self.chdir.side_effect = OSError(2, "no such directory")
        self.launch()
        self.chdir.assert_called_once_with("/system/apps/taste_stamp")
        self.step("DOWN")
        self.assertIsNotNone(self.app.slam)

    def test_idle_desk_warms_one_stamp_per_frame_and_shows_controls(self):
        A = self.launch()
        for i in range(7):
            self.step()
            self.assertEqual(sum(s is not None for s in A.STAMPS), i + 1)
        texts = self.texts()
        for text in ("TASTE STAMP", "< 8-BALL >", "FLIP OR CHOP TO STAMP", "OR PRESS DOWN", "NEXT: RANDOM"):
            self.assertIn(text, texts)
        self.assertNotIn("SELECT: BEAM", texts)
        self.assertEqual(self.text_at(14, 222), ("text", A.DIM_C, "NEXT: RANDOM", (14, 222), "font:sins"))
        boxes = [(op[1], op[2].width) for op in self.shapes(kind="rounded_rectangle")]
        self.assertEqual(boxes, [(A.PAPER_C, None), (A.HEADING_C, 1.5)])
        self.run_for(500)
        self.assertEqual(self.badge.lights, [])

    def test_down_slams_a_verdict_with_shake_splats_and_strobe(self):
        A = self.launch()
        app, badge, screen = self.app, self.badge, self.screen
        self.run_for(160)
        base = list(app.desk.ops)
        lit = len(badge.lights)
        self.step("DOWN")
        s = app.slam
        start = s.start
        self.assertEqual(start, badge.ticks)
        ink = A.verdicts.INKS[s.index]
        outlines = A.STAMPS[s.index][0]
        falling = [op for op in self.shapes() if any(op[2] is o for o in outlines)]
        self.assertEqual([op[2] for op in falling], outlines)
        for op in falling:
            self.assertEqual((op[1], op[3]), (pen(ink, 70), "NON_ZERO"))
            self.assertIsInstance(op[4], FakeMat3)
        blocks = [op for op in self.shapes() if op[1] == ("rgb", 0, 0, 0, 50)]
        self.assertEqual([op[2].kind for op in blocks], ["rounded_rectangle"])
        self.assertIsInstance(blocks[0][4], FakeMat3)
        expected = []
        last = [None]

        def expect(t):
            levels = S.strobe_levels(t - S.DROP_MS)
            if levels != last[0]:
                expected.append((0,) if levels is None else levels)
                last[0] = levels

        expect(0)
        shaken = []
        while app.slam is not None:
            self.assertLess(badge.ticks - start, 1300)
            self.step()
            t = badge.ticks - start
            expect(t)
            if screen.ops[0][0] == "clear":
                shaken.append(t)
            dots = [op for op in self.shapes(kind="circle") if op[1] == pen(ink, 225)]
            self.assertEqual(len(dots), 14 if 144 <= t <= 528 else 0, t)
        self.assertEqual(badge.ticks - start, 1152)
        self.assertGreaterEqual(len(shaken), 10)
        self.assertTrue(all(140 <= t < 590 for t in shaken), shaken)
        self.assertEqual(badge.lights[lit:], expected)
        self.assertEqual(app.desk.ops[:len(base)], base)
        added = app.desk.ops[len(base):]
        n = len(outlines)
        self.assertEqual([op[2] for op in added[:n]], outlines)
        for op in added[:n]:
            self.assertEqual((op[1], op[3]), (pen(ink, 225), "NON_ZERO"))
            self.assertIsInstance(op[4], FakeMat3)
        specks = added[n]
        self.assertIs(specks[2], s.specks)
        self.assertEqual(len(specks[2].arrays), A.SPECKS)
        self.assertEqual((specks[1], specks[3]), (pen(A.PAPER, 190), "NON_ZERO"))
        dots = added[n + 1:]
        self.assertEqual([op[2].args for op in dots], s.dots)
        self.assertTrue(all(op[1] == pen(ink, 225) and op[2].kind == "circle" for op in dots))
        self.assertEqual(app.marks, [s])
        self.assertTrue(s.inked and s.dried)
        self.assertEqual(len(s.dots), 14)

    def test_up_picks_the_next_verdict(self):
        A = self.launch()
        verdicts = A.verdicts
        for i in range(7):
            self.step("UP")
            self.assertEqual(self.app.toast_text, "NEXT: " + verdicts.VERDICTS[i])
            op = self.text_at(14, 222)
            self.assertEqual(op[1:3], (pen(A.lighten(verdicts.INKS[i], 0.45)), "NEXT: " + verdicts.VERDICTS[i]))
        self.step("UP")
        self.assertEqual(self.app.toast_text, "NEXT: RANDOM")
        self.assertEqual(self.text_at(14, 222)[1], A.DIM_C)
        for _ in range(4):
            self.step("UP")
        self.step("DOWN")
        self.step("DOWN")
        self.assertEqual(self.app.slam.index, 3)
        self.assertEqual([m.index for m in self.app.marks], [3])

    def test_flipping_the_badge_slams_once_per_settled_flip(self):
        self.launch()
        start_slam = self.spy("start_slam")
        self.run_for(300, flipped=True, imu_value=REST_SIM)
        self.assertEqual(self.badge.ticks, 1304)
        self.assertEqual(start_slam.call_count, 1)
        self.assertEqual(start_slam.call_args.args[1], 1144)
        self.run_for(800)
        self.assertEqual(self.badge.ticks, 2104)
        self.assertEqual(start_slam.call_count, 1)
        self.run_for(300, flipped=False, imu_value=REST_UP)
        self.assertEqual(start_slam.call_count, 2)
        self.assertEqual(start_slam.call_args.args[1], 2248)

    def test_a_karate_chop_slams_whichever_way_gravity_reads(self):
        for rest, spike in ((REST_UP, SPIKE), (REST_SIM, (30000, -16384, 0, 0, 0, 0))):
            with self.subTest(rest=rest):
                self.launch(imu_value=rest)
                start_slam = self.spy("start_slam")
                self.run_for(400)
                self.assertEqual(self.badge.ticks, 1400)
                self.assertEqual(start_slam.call_count, 0)
                self.step(imu_value=spike)
                self.assertEqual(start_slam.call_count, 1)
                self.run_for(2000, imu_value=rest)
                self.assertEqual(self.badge.ticks, 3416)
                self.assertEqual(start_slam.call_count, 1)
                # A chop that also turns the badge over is one move, not two.
                self.step(imu_value=spike, flipped=True)
                self.assertEqual(start_slam.call_count, 2)
                self.run_for(400, imu_value=rest)
                self.assertEqual(start_slam.call_count, 2)
                self.assertTrue(self.app.flip.state)

    def test_marks_keep_the_last_four_stamps_and_fade_older_ones(self):
        A = self.launch()
        app = self.app
        dealt = []
        for _ in range(7):
            self.step("DOWN")
            dealt.append(app.slam.index)
        self.assertEqual(sorted(dealt), list(range(7)))
        self.run_until(lambda: app.slam is None, 1300)
        self.assertEqual([m.index for m in app.marks], dealt[3:])
        customs = self.shapes(app.desk, "custom")
        paper = [op[1][4] for op in customs if op[1][1:4] == A.PAPER]
        self.assertEqual(paper, [46, 80, 126, 190])
        self.assertEqual({op[1][4] for op in customs if op[1][1:4] != A.PAPER}, {55, 95, 150, 225})
        # Leaving stamp mode mid-slam lands the stamp at once.
        self.step("DOWN")
        s = app.slam
        self.run_for(208)
        self.step("RIGHT")
        self.assertIsNone(app.slam)
        self.assertTrue(s.inked and s.dried)
        self.assertEqual(app.mode, A.BALL_MODE)
        self.assertEqual(self.badge.lights[-2:], [(1.0,) * 4, (0,)])
        self.assertEqual(len(app.marks), 4)
        self.assertIs(app.marks[-1], s)

    def test_eight_ball_tumbles_lands_and_reveals_a_prompt(self):
        A = self.launch()
        app, badge = self.app, self.badge
        self.step("RIGHT")
        self.assertEqual(app.mode, A.BALL_MODE)
        texts = self.texts()
        for text in ("CREATIVE 8-BALL", "< STAMP >", "SHAKE FOR A CREATIVE DIRECTION", "OR PRESS DOWN"):
            self.assertIn(text, texts)
        self.assertTrue(self.check_d20())
        self.step("DOWN")
        self.assertEqual(app.ball.state, A.eightball.SPINNING)
        self.assertEqual(self.check_d20(), [])
        base = "CONSULTING THE STUDIO"
        consulting = [t for t in self.texts() if t.startswith(base)]
        self.assertEqual(len(consulting), 1)
        self.assertIn(consulting[0][len(base):], (".", "..", "..."))
        lit = len(badge.lights)
        end = badge.ticks + 4000
        while not self.landed():
            self.assertLess(badge.ticks, end)
            self.step()
            self.check_d20()
            if not self.landed():
                self.assertEqual(len(badge.lights), lit)
        n = app.ball.number()
        self.assertTrue(1 <= n <= 20)
        self.assertEqual(badge.lights[lit:], [(0.5,) * 4])
        prompt = app.prompt
        self.assertEqual(len(prompt), len(app.build_prompt(A.verdicts.PROMPTS[n - 1])))
        drawn = [op for op in self.shapes(kind="custom") if any(op[2] is p for p in prompt)]
        self.assertEqual([op[2] for op in drawn], prompt[:1])
        self.assertEqual((drawn[0][1], drawn[0][3]), (A.WHITE_C, "NON_ZERO"))
        self.assertIn("SELECT: BEAM IT", self.texts())
        self.run_for(18 * len(prompt))
        drawn = [op[2] for op in self.shapes(kind="custom") if any(op[2] is p for p in prompt)]
        self.assertEqual(drawn, prompt)
        top = [op for op in self.check_d20() if op[2] is A.NUMBER_SHAPES[n]]
        self.assertEqual([op[1] for op in top], [pen(A.WHITE)])
        self.run_for(500)
        tail = badge.lights[lit:]
        self.assertEqual(tail[0], (0.5,) * 4)
        self.assertEqual(tail[-1], (0,))
        glow = [levels[0] for levels in tail[:-1]]
        for levels in tail[:-1]:
            self.assertEqual(len(set(levels)), 1)
            self.assertEqual(len(levels), 4)
        self.assertTrue(all(a > b > 0 for a, b in zip(glow, glow[1:])), glow)

    def test_d20_never_shows_renumbered_faces(self):
        A = self.launch()
        app = self.app
        E8 = A.eightball
        self.step("RIGHT")
        step = E8.MAX_SPIN * 16 / 1000 + 0.01
        rerolls = 0
        for _ in range(6):
            q = app.ball.q
            self.step("DOWN")
            while True:
                numbers = self.check_d20()
                if E8.q_angle(q, app.ball.q) > step:
                    rerolls += 1
                    self.assertEqual(numbers, [])
                if numbers and app.ball.state == E8.SPINNING:
                    self.assertLess(app.ball.speed(), E8.BLUR_SPEED)
                if self.landed():
                    break
                q = app.ball.q
                self.step()
        self.assertGreaterEqual(rerolls, 5)

    def test_place_number_maps_face_corners_through_the_firmware_transform(self):
        A = self.launch()
        r = V.Rng(77)
        checked = 0
        while checked < 100:
            top = (r.uniform(40, 280), r.uniform(20, 180))
            left = (r.uniform(40, 280), r.uniform(20, 180))
            right = (r.uniform(40, 280), r.uniform(20, 180))
            cross = (left[0] - top[0]) * (right[1] - top[1]) - (left[1] - top[1]) * (right[0] - top[0])
            if abs(cross) < 50:
                continue
            n = 1 + checked % 20
            s = A.place_number(n, top, left, right)
            self.assertIs(s, A.NUMBER_SHAPES[n])
            for uv, want in (((0, 0), top), ((1, 0), left), ((0, 1), right)):
                got = s.transform.apply(*uv)
                self.assertAlmostEqual(got[0], want[0], delta=1e-6)
                self.assertAlmostEqual(got[1], want[1], delta=1e-6)
            checked += 1
        # Every number sits inside its face triangle.
        for n in range(1, 21):
            for a in A.NUMBER_SHAPES[n].arrays:
                for i in range(0, len(a), 2):
                    s, t = a[i], a[i + 1]
                    self.assertTrue(s >= 0 and t >= 0 and s + t <= 1, (n, s, t))
        self.assertEqual(self.rt.problems, [])

    def test_ball_mode_shakes_and_flips_kick_the_d20(self):
        self.launch()
        self.step("RIGHT")
        kick = self.spy("kick")
        for reading in shake_pattern(16384, 6):
            self.step(imu_value=reading)
        self.assertEqual([c.args[0] for c in kick.call_args_list], [5, 14, 5, 5, 5])
        self.run_until(self.landed, 5000, imu_value=REST_UP)
        kick.reset_mock()
        self.run_for(300, flipped=True)
        self.assertEqual([c.args[0] for c in kick.call_args_list], [16])

    def test_select_beams_the_last_verdict_as_one_burst(self):
        A = self.launch()
        app, badge, ir = self.app, self.badge, self.ir
        self.step("SELECT")
        self.assertEqual(app.toast_text, A.STAMP_HINT)
        self.assertIsNone(app.fx_start)
        self.step("DOWN")
        self.assertIsNone(app.toast_text)
        index = app.last_verdict
        self.run_until(lambda: app.slam is None, 1300)
        self.assertIsNone(app.lights)
        lit = len(badge.lights)
        self.step("SELECT")
        start = badge.ticks
        self.assertEqual(app.toast_text, "BEAMING TO NEARBY BADGES")
        self.assertEqual(ir.frames, [(0x53, index, start)])
        self.assertEqual([(op[2].args, op[1]) for op in self.rings()], [((160, -6, 10.0), pen(A.BLUE, 200))])
        self.step("SELECT")
        self.assertEqual(app.toast_text, "STILL BEAMING")
        self.assertEqual(app.fx_start, start)
        most = 0
        while app.fx_start is not None:
            self.assertLess(badge.ticks - start, 1000)
            self.step()
            rings = self.rings()
            most = max(most, len(rings))
            for op in rings:
                self.assertTrue(10 <= op[2].args[2] < 160, op[2].args)
        self.assertEqual(most, 3)
        self.assertEqual(badge.ticks - start, 848)
        self.assertEqual(ir.frames, [(0x53, index, start + d) for d in (0, 176, 352)])
        self.assertFalse(app.link.busy())
        expected = []
        last = None
        for t in range(0, 849, 16):
            levels = B.lights(t)
            if levels != last:
                expected.append((0,) if levels is None else levels)
                last = levels
        self.assertEqual(badge.lights[lit:], expected)

    def test_select_beams_the_prompt_once_the_ball_lands(self):
        A = self.launch()
        app, ir = self.app, self.ir
        self.step("RIGHT")
        self.step("SELECT")
        self.assertEqual(app.toast_text, A.SPIN_HINT)
        self.step("DOWN")
        self.assertIsNone(app.toast_text)
        self.step("SELECT")
        self.assertEqual(app.toast_text, A.LAND_HINT)
        # The face is chosen as the ball starts to settle, but nothing
        # beams until its prompt is on screen.
        self.run_until(lambda: app.ball.state == A.eightball.SETTLING, 5000)
        self.assertIsNotNone(app.ball.number())
        self.step("SELECT")
        self.assertEqual((app.ball.state, app.toast_text), (A.eightball.SETTLING, A.LAND_HINT))
        self.run_until(self.landed, 5000)
        self.assertIsNone(app.toast_text)
        self.assertEqual(ir.frames, [])
        n = app.ball.number()
        self.step("SELECT")
        start = self.badge.ticks
        self.assertEqual(app.toast_text, "BEAMING TO NEARBY BADGES")
        self.assertEqual([op[2].args for op in self.rings()], [(160, -6, 10.0)])
        self.run_for(400)
        cmd = 0x40 + n - 1
        self.assertEqual(ir.frames, [(0x53, cmd, start + d) for d in (0, 176, 352)])
        self.assertEqual(B.decode(cmd, len(V.VERDICTS), len(V.PROMPTS)), (B.PROMPT, n - 1))
        self.assertTrue(self.landed())

    def test_an_incoming_verdict_slams_once_per_beam(self):
        A = self.launch()
        app, badge, ir = self.app, self.badge, self.ir
        self.step("RIGHT")
        start_slam = self.spy("start_slam")
        lit = len(badge.lights)
        ir.deliver(4)
        self.step()
        now = badge.ticks
        self.assertEqual(app.mode, A.STAMP_MODE)
        self.assertEqual(start_slam.call_args_list, [mock.call(4, now)])
        self.assertEqual((app.slam.index, app.last_verdict), (4, 4))
        self.assertEqual(app.toast_text, "FROM A NEARBY BADGE")
        self.assertEqual([(op[2].args, op[1]) for op in self.rings()], [((160, -6, 160.0), pen(A.BLUE, 200))])
        self.assertEqual(badge.lights[lit:], [B.lights(0)])
        # The sender's burst repeats the frame; one beam is one slam.
        for _ in range(10):
            ir.deliver(4)
            self.step()
            for op in self.rings():
                self.assertLess(op[2].args[2], 160)
        self.assertEqual(start_slam.call_count, 1)
        self.run_for(1300)
        ir.deliver(4)
        self.step()
        self.assertEqual(start_slam.call_count, 2)
        self.assertEqual(ir.frames, [])

    def test_an_incoming_prompt_spins_the_ball_onto_its_face(self):
        A = self.launch()
        app, ir = self.app, self.ir
        kick = self.spy("kick")
        ir.deliver(0x40 + 12)
        self.step()
        now = self.badge.ticks
        self.assertEqual(app.mode, A.BALL_MODE)
        self.assertEqual(kick.call_args_list, [mock.call(16, now, 13)])
        self.assertEqual(app.toast_text, "INCOMING PROMPT")
        self.assertEqual([op[2].args for op in self.rings()], [(160, -6, 160.0)])
        self.run_until(self.landed, 5000)
        self.assertEqual(app.ball.number(), 13)
        self.assertEqual(len(app.prompt), len(app.build_prompt(A.verdicts.PROMPTS[12])))
        self.assertEqual(ir.frames, [])

    def test_the_badge_ignores_its_own_beam_bouncing_back(self):
        self.launch()
        app, ir = self.app, self.ir
        self.step("DOWN")
        index = app.last_verdict
        other = (index + 1) % len(V.VERDICTS)
        self.run_until(lambda: app.slam is None, 1300)
        start_slam = self.spy("start_slam")
        self.step("SELECT")
        # Frames heard mid-burst are dropped, so another badge talking over
        # the burst can't carry our own echo past the duplicate filter.
        ir.deliver(other)
        ir.deliver(index)
        self.step()
        for _ in range(60):
            ir.deliver(index)
            self.step()
        self.assertEqual(start_slam.call_count, 0)
        self.assertEqual(len(ir.frames), 3)
        # Once the echoes stop, the same verdict from another badge is news.
        self.run_for(1300)
        ir.deliver(index)
        self.step()
        self.assertEqual(start_slam.call_args.args[0], index)
        self.assertEqual(app.toast_text, "FROM A NEARBY BADGE")

    def test_back_clears_the_sheet_then_exits_and_releases_ir(self):
        A = self.launch()
        rt, app, badge, ir = self.rt, self.app, self.badge, self.ir
        self.step("DOWN")
        self.run_for(200)
        self.step("DOWN")
        self.assertIsNone(self.step("BACK"))
        self.assertEqual((app.slam, app.marks, app.last_verdict), (None, [], None))
        self.assertEqual(app.toast_text, "FRESH PAPER")
        self.assertEqual(self.shapes(app.desk, "custom"), [])
        self.assertEqual(self.shapes(app.desk, "circle"), [])
        self.assertEqual(self.texts(app.desk), ["creative-brief.md"])
        self.step("SELECT")
        self.assertEqual(app.toast_text, A.STAMP_HINT)
        self.assertIs(self.step("BACK"), False)
        sender = ir.senders[0]
        self.assertEqual((ir.closed, sender.stopped), (1, 1))
        self.assertIsNone(app.link.tx)
        self.assertFalse(app.link.receiving)
        self.assertEqual(badge.lights[-1], (0,))
        self.assertEqual(badge.default_clear, "firmware-clear")
        for name in HELPERS:
            self.assertNotIn(name, sys.modules)
        A.on_exit()
        self.assertEqual((ir.closed, sender.stopped), (1, 1))
        self.assertEqual(ir.frames, [])
        # Relaunching claims the transmitter and the receiver again.
        A = self.launch(ir=ir, rt=rt)
        self.assertEqual(len(ir.senders), 2)
        self.assertTrue(ir.senders[1].started)
        self.assertEqual(len(ir.bound), 2)
        self.assertIsNone(badge.default_clear)
        self.assertEqual(A.previous_clear, "firmware-clear")
        self.assertIs(self.step("BACK"), False)
        self.assertEqual((ir.closed, ir.senders[1].stopped), (2, 1))
        self.assertEqual(badge.default_clear, "firmware-clear")

    def test_back_in_the_8_ball_resets_it_then_exits(self):
        A = self.launch()
        app, ir = self.app, self.ir
        idle = A.eightball.IDLE
        self.step("RIGHT")
        self.step("DOWN")
        self.assertEqual(app.ball.state, A.eightball.SPINNING)
        self.assertIsNone(self.step("BACK"))
        self.assertEqual(app.ball.state, idle)
        self.step("UP")
        self.run_until(self.landed, 5000)
        self.assertIsNotNone(app.prompt)
        self.assertIsNone(self.step("BACK"))
        self.assertEqual((app.mode, app.ball.state, app.prompt), (A.BALL_MODE, idle, None))
        self.assertIn("SHAKE FOR A CREATIVE DIRECTION", self.texts())
        self.assertTrue(self.check_d20())
        self.assertIs(self.step("BACK"), False)
        self.assertEqual((ir.closed, ir.senders[0].stopped), (1, 1))
        self.assertEqual(self.badge.lights[-1], (0,))

    def test_runs_in_the_badge_simulator_without_ir_hardware(self):
        # The simulator's aye_arr is empty and its ir.bind returns a stub.
        ir = FakeIR(sender=False, descriptor=False, bind_returns="stub")
        self.launch(ir=ir, imu_value=REST_SIM)
        app = self.app
        self.assertEqual(ir.senders, [])
        self.assertIsNone(app.link.tx)
        self.assertTrue(app.link.receiving)
        self.assertEqual(ir.descriptor_inits, 0)
        self.assertEqual((ir.stubs[0].on_any, ir.bound[0].on_any), (app.link.heard, app.link.heard))
        start_slam = self.spy("start_slam")
        # The canvas rotate control turns the simulator's gravity over.
        self.run_for(300, flipped=True, imu_value=(0, 16384, 0, 0, 0, 0))
        self.assertEqual(start_slam.call_count, 1)
        self.run_until(lambda: app.slam is None, 1300)
        self.step("SELECT")
        self.assertEqual(app.toast_text, "NO IR HERE: BEAM SIMULATED")
        self.assertEqual(len(self.rings()), 1)
        self.run_for(900)
        self.assertIsNone(app.fx_start)
        self.assertEqual(ir.frames, [])
        ir.deliver(2)
        self.step()
        self.assertEqual(start_slam.call_args.args[0], 2)
        self.assertEqual(app.toast_text, "FROM A NEARBY BADGE")
        self.assertIsNone(self.step("BACK"))
        self.assertIs(self.step("BACK"), False)
        self.assertEqual(ir.closed, 1)

    def tour(self, ir=None, **options):
        # Visits every screen and control once, then exits. Returns the
        # toasts that the verdict beam and the prompt beam showed.
        self.launch(ir=ir, **options)
        app = self.app
        toasts = []
        self.step("SELECT")
        self.step("UP")
        self.step("DOWN")
        self.run_until(lambda: app.slam is None, 1300)
        self.step("SELECT")
        toasts.append(app.toast_text)
        self.run_for(900)
        self.step("RIGHT")
        self.step("SELECT")
        self.step("DOWN")
        self.run_until(self.landed, 5000)
        self.step("SELECT")
        toasts.append(app.toast_text)
        self.run_for(900)
        self.assertIsNone(self.step("BACK"))
        self.step("LEFT")
        self.assertIsNone(self.step("BACK"))
        self.assertIs(self.step("BACK"), False)
        self.assertEqual(self.badge.lights[-1], (0,))
        self.assertEqual(self.badge.default_clear, "firmware-clear")
        for name in HELPERS:
            self.assertNotIn(name, sys.modules)
        return toasts

    def test_every_screen_survives_missing_or_failing_hardware(self):
        beaming = ["BEAMING TO NEARBY BADGES"] * 2
        simulated = ["NO IR HERE: BEAM SIMULATED"] * 2
        cases = (
            ("full hardware", dict(), beaming),
            ("no IR modules", dict(ir=FakeIR(present=False)), simulated),
            ("transmitter fails to start", dict(ir=FakeIR(start_error=OSError(16))), simulated),
            ("receiver fails to bind", dict(ir=FakeIR(bind_error=OSError(5))), beaming),
            ("IR fails to release", dict(ir=FakeIR(stop_error=OSError(5), close_error=OSError(5))), beaming),
            ("IMU raises", dict(imu_error=OSError(5)), beaming),
            ("orientation raises", dict(flip_error=OSError(5)), beaming),
            ("case lights raise", dict(light_error=OSError(5)), beaming),
            ("short IMU reading", dict(imu_value=(0, 16384, 0)), beaming),
            ("screen without raw pixels", dict(screen_raw=False), beaming),
        )
        for name, options, expected in cases:
            with self.subTest(name):
                self.assertEqual(self.tour(**options), expected)

    def test_a_transmitter_that_fails_mid_beam_is_released(self):
        ir = FakeIR(send_error=OSError(110))
        self.launch(ir=ir)
        app = self.app
        sender = ir.senders[0]
        self.step("DOWN")
        self.run_until(lambda: app.slam is None, 1300)
        self.step("SELECT")
        self.assertEqual(app.toast_text, "IR SEND FAILED")
        self.assertEqual(ir.frames, [])
        self.assertEqual(sender.stopped, 1)
        self.assertIsNone(app.link.tx)
        self.assertFalse(app.link.busy())
        self.run_for(900)
        self.step("SELECT")
        self.assertEqual(app.toast_text, "NO IR HERE: BEAM SIMULATED")
        # Receiving still works without the transmitter.
        ir.deliver(6)
        self.step()
        self.assertEqual((app.slam.index, app.toast_text), (6, "FROM A NEARBY BADGE"))
        self.assertIsNone(self.step("BACK"))
        self.assertIs(self.step("BACK"), False)
        self.assertEqual((ir.closed, sender.stopped), (1, 1))

    def test_a_long_random_session_keeps_every_frame_sane(self):
        A = self.launch()
        app, badge, ir = self.app, self.badge, self.ir
        start_slam = self.spy("start_slam")
        landed = self.spy("landed")
        r = V.Rng(2026)
        buttons = ("UP", "DOWN", "LEFT", "RIGHT", "SELECT")
        modes = []
        beams = [0, 0]
        flipped = False
        # Calm and wild stretches, so the ball sometimes gets to land.
        for _ in range(30):
            wild = r.randint(0, 2)
            for _ in range(50):
                pressed = ()
                if r.randint(0, 99) < 2 + 5 * wild:
                    pressed = (buttons[r.randint(0, 4)],)
                if r.randint(0, 99) < wild:
                    flipped = not flipped
                if r.randint(0, 99) < 4 * wild:
                    reading = tuple(r.randint(-32768, 32767) for _ in range(6))
                else:
                    reading = (0, -16384 if flipped else 16384, 0, 0, 0, 0)
                if r.randint(0, 99) < 2 + 2 * wild:
                    pick = r.randint(0, 2)
                    if pick == 0:
                        ir.deliver(r.randint(0, len(V.VERDICTS) - 1))
                    elif pick == 1:
                        ir.deliver(0x40 + r.randint(0, len(V.PROMPTS) - 1))
                    else:
                        ir.deliver(r.randint(0, 255))
                self.step(*pressed, ms=r.randint(0, 120), imu_value=reading, flipped=flipped)
                if app.mode not in modes:
                    modes.append(app.mode)
                if app.fx_start == badge.ticks:
                    beams[1 if app.fx_incoming else 0] += 1
        self.assertEqual(sorted(modes), [A.STAMP_MODE, A.BALL_MODE])
        self.assertGreater(start_slam.call_count, 3)
        self.assertGreater(landed.call_count, 0)
        self.assertGreater(beams[0], 0)
        self.assertGreater(beams[1], 0)
        times = [f[2] for f in ir.frames]
        self.assertTrue(times)
        gaps = [b - a for a, b in zip(times, times[1:])]
        self.assertTrue(all(gap >= B.FRAME_MS + B.GAP_MS for gap in gaps), gaps)
        for address, cmd, _ in ir.frames:
            self.assertEqual(address, 0x53)
            self.assertIsNotNone(B.decode(cmd, len(V.VERDICTS), len(V.PROMPTS)))
        lights = badge.lights
        self.assertTrue(all(a != b for a, b in zip(lights, lights[1:])))
        A.on_exit()
        self.assertEqual(badge.lights[-1], (0,))
        self.assertEqual((ir.closed, ir.senders[0].stopped), (1, 1))


if __name__ == "__main__":
    unittest.main()
