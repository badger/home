"""Host regressions, not measurements of the badge's native renderer or viper."""

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import struct
import sys
import types
import unittest
from unittest.mock import Mock, patch

APP = Path(__file__).resolve().parents[1] / "badge/apps/twelve_clocks"


def load(name, path, extra=None):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    module.__dict__.update(extra or {})
    spec.loader.exec_module(module)
    return module


with patch.dict(sys.modules, {"micropython": types.SimpleNamespace(viper=lambda f: f)}):
    work = load("clockwork", APP / "clockwork.py", {"ptr8": lambda b: b})


class Matrix:
    def translate(self, *args):
        self.check(args)
        return self

    rotate = translate
    scale = translate

    @staticmethod
    def check(args):
        for arg in args:
            assert isinstance(arg, (int, float)) and math.isfinite(arg), arg


class NativeShape:
    transform = None

    def stroke(self, width):
        assert width > 0
        return self


class Surface:
    def __init__(self, width=320, height=240):
        self.width, self.height = width, height
        self.antialias = 0
        self.fill_rule = 0
        self.font = "previous-font"
        self.pen = None
        self.calls = 0
        self.labels = []

    def clear(self):
        self.calls += 1

    def shape(self, shape):
        assert isinstance(shape, NativeShape)
        self.calls += 1

    def rectangle(self, *args):
        Matrix.check(args)
        assert args[-2] > 0 and args[-1] > 0
        self.calls += 1

    def line(self, *args):
        Matrix.check(args)
        self.calls += 1

    def text(self, value, x, y):
        self.labels.append(value)
        self.calls += 1

    def blit(self, source, point):
        assert isinstance(source, Surface)
        self.calls += 1


def graphics():
    def rgb(*args):
        assert len(args) in (3, 4)
        assert all(isinstance(x, int) and 0 <= x <= 255 for x in args), args
        return args

    def primitive(*args):
        Matrix.check(args)
        return NativeShape()

    def custom(*paths):
        assert all(len(path) >= 3 for path in paths)
        return NativeShape()

    Surface.X2 = 2
    Surface.EVEN_ODD = 1
    return {
        "screen": Surface(), "image": Surface,
        "color": types.SimpleNamespace(rgb=rgb),
        "shape": types.SimpleNamespace(circle=primitive, arc=primitive, custom=custom),
        "vec2": lambda x, y: (x, y), "mat3": Matrix,
        "font": types.SimpleNamespace(sins="sins"),
    }


class ClockworkTests(unittest.TestCase):
    def test_font_is_exact_pinned_source(self):
        rows = {char: [[(row >> (4 - x)) & 1 for x in range(5)] for row in bits]
                for char, bits in work.FONT.items() if char != " "}
        paths = {char: [[[int(p[i]), int(p[i + 1])] for i in range(0, len(p), 2)]
                        for p in contours]
                 for char, contours in work.CONTOURS.items() if char != " "}
        for value, digest in (
            (rows, "0fd3ad35a8a89faf79f7dee0d2894f7e41a6cc0a4480047c92e4a5e1c56a8559"),
            (paths, "b92d611a500f1c59fc18647fd982d72209fefeeb824b30b5a3f981d0b363b087"),
        ):
            self.assertEqual(hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest(), digest)
        self.assertEqual(sum(map(len, work.FONT.values())), 105)

    def test_selection_validation(self):
        for index in range(12):
            self.assertEqual(work.selected_index(index), index)
        for invalid in (-1, 12, 999999, None, "3", 4.0, True, False, [], {}):
            self.assertEqual(work.selected_index(invalid), 0)

    def test_noon_midnight_and_padding(self):
        self.assertEqual(work.clock_text(0, 0, 0), "12:00:00")
        self.assertEqual(work.clock_text(12, 59, 59), "12:59:59")
        self.assertEqual(work.clock_text(13, 0), " 1:00")
        self.assertEqual(work.clock_text(23, 59, 59), "11:59:59")

    def test_history_jumps_are_bounded(self):
        history = work.History(355)
        for now in (86398, 86399, 86400, 86401, 10**9, 1, 1):
            history.update(now)
            entries = list(history.entries())
            self.assertLessEqual(len(entries), 25)
            self.assertEqual(entries[-1], (now, history.hue, 0))
            self.assertEqual([entry[0] for entry in entries], list(range(now - len(entries) + 1, now + 1)))
        self.assertEqual(history.count, 25)
        self.assertEqual(len(vars(history)), 3)

    def test_history_initial_fill_and_hue_rollover(self):
        history = work.History(355)
        history.update(86399)
        self.assertEqual(list(history.entries()), [(86399, 355, 0)])
        history.update(86400)
        self.assertEqual(list(history.entries()), [(86399, 355, 1), (86400, 0, 0)])

    def test_phase_independent_of_frame_partition(self):
        for index, period in ((0, 2000), (2, 6000), (7, 2000 * math.pi / 1.5), (10, 5000)):
            a, b = work.Timing(index), work.Timing(index)
            for _ in range(120):
                a.advance(25, 100, False)
            b.advance(3000, 100, False)
            self.assertAlmostEqual(a.phase, b.phase)
            b.advance(10**9, 100, False)
            self.assertTrue(0 <= b.phase < period)

    def test_static_faces_and_blink_skip_unchanged_frames(self):
        for index in (1, 3, 4, 8, 9, 11):
            timing = work.Timing(index)
            self.assertTrue(timing.advance(0, 100, False))
            self.assertFalse(timing.advance(10000, 100, True))
            self.assertTrue(timing.advance(0, 101, False))
            self.assertTrue(timing.advance(0, 101, False, True))
        timing = work.Timing(6)
        self.assertTrue(timing.advance(0, 100, False))
        self.assertFalse(timing.advance(100, 100, False))
        self.assertTrue(timing.advance(400, 100, True))

    def test_life_keeps_50ms_target_without_catchup_queue(self):
        timing = work.Timing(5)
        timing.advance(0, 100, False)
        self.assertFalse(timing.advance(49, 101, False))
        self.assertTrue(timing.advance(1, 100, False))
        self.assertTrue(timing.advance(10**9, 100, False))
        self.assertFalse(timing.advance(0, 100, False))

    def test_life_matches_finite_reference(self):
        rng = random.Random(12)
        source = bytearray(rng.randrange(2) for _ in range(1890))
        target = bytearray(1890)
        expected = bytearray(1890)
        for y in range(30):
            for x in range(63):
                neighbours = sum(source[yy * 63 + xx]
                                 for yy in range(max(0, y - 1), min(30, y + 2))
                                 for xx in range(max(0, x - 1), min(63, x + 2))
                                 if (xx, yy) != (x, y))
                expected[y * 63 + x] = neighbours == 3 or (
                    neighbours == 2 and source[y * 63 + x])
        work.life_step(source, target)
        self.assertEqual(target, expected)
        source[:] = bytes(1890)
        source[0] = source[62] = source[1827] = 1
        work.life_step(source, target)
        self.assertEqual(sum(target), 0)

    def test_life_reuses_buffers_and_reseeds_time(self):
        life = work.Life()
        ids = {id(life.front), id(life.back)}
        for second in range(60):
            text = work.clock_text(12, 59, second)
            life.step(text)
            self.assertEqual({id(life.front), id(life.back)}, ids)
            self.assertEqual(len(life.front) + len(life.back), 3780)
            for x, y in work.pixels(text):
                self.assertEqual(life.front[(y + 11) * 63 + x + 8], 0)
                self.assertEqual(life.back[(y + 11) * 63 + x + 8], 1)


class RenderTests(unittest.TestCase):
    def test_all_faces_at_rollovers(self):
        g = graphics()
        with patch.dict(sys.modules, {"clockwork": work}):
            faces = load("faces_test", APP / "faces.py", g)
        for index in range(12):
            face = faces.Face(index)
            self.assertEqual(face.life is not None, index == 5)
            self.assertEqual(face.history is not None, index == 3)
            for h, m, s, epoch in ((12, 59, 59, 46799), (13, 0, 0, 46800),
                                    (23, 59, 59, 86399), (0, 0, 0, 86400)):
                for phase in (0, 500, 1500):
                    before = g["screen"].calls
                    face.draw(h, m, s, epoch, phase, True)
                    self.assertGreater(g["screen"].calls, before)
            if index == 8:
                self.assertEqual((face.cached.width, face.cached.height), (9, 9))
            if index == 9:
                self.assertEqual((face.cached.width, face.cached.height), (320, 240))

    def test_icon_is_24_pixel_png(self):
        data = (APP / "icon.png").read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", data[16:24]), (24, 24))


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.g = graphics()
        self.pressed = set()
        self.badge = types.SimpleNamespace(
            ticks=0, ticks_delta=16, default_clear="previous-clear",
            pressed=lambda key: key in self.pressed, mode=Mock())
        self.state = types.SimpleNamespace(load=Mock(), save=Mock())
        self.native_face = Mock()
        self.path = types.SimpleNamespace(path=list(sys.path))
        self.clock = types.SimpleNamespace(time=lambda: 86400, localtime=lambda now: (2026, 10, 27, 0, 0, 0, 1, 300))
        self.modules = {
            "clockwork": work, "faces": types.SimpleNamespace(Face=self.native_face),
            "badgeware": types.SimpleNamespace(State=self.state),
            "os": types.SimpleNamespace(chdir=Mock()), "sys": self.path, "time": self.clock,
        }
        self.g.update(badge=self.badge, HIRES=1, VSYNC=2, run=Mock())
        for key in ("LEFT", "RIGHT", "UP", "DOWN", "MENU", "SELECT", "BACK"):
            self.g["BUTTON_" + key] = key

    def start(self, stored=0):
        self.state.load.side_effect = lambda key, state: state.update(face=stored)
        with patch.dict(sys.modules, self.modules):
            self.app = load("twelve_test", APP / "__init__.py", self.g)

    def frame(self, *buttons, delta=16):
        self.pressed.clear()
        self.pressed.update(buttons)
        self.badge.ticks += delta
        self.badge.ticks_delta = delta
        self.app.update()

    def test_wrap_navigation_and_debounced_persistence(self):
        self.start()
        self.frame("LEFT")
        self.assertEqual(self.app.index, 11)
        self.frame("RIGHT")
        self.assertEqual(self.app.index, 0)
        self.frame(delta=799)
        self.state.save.assert_not_called()
        self.frame(delta=1)
        self.state.save.assert_called_once_with("twelve_clocks", {"face": 0})
        self.frame(delta=1000)
        self.state.save.assert_called_once()

    def test_menu_lists_all_faces_and_pauses_active_one(self):
        self.start()
        self.frame()
        calls = self.app.face.draw.call_count
        self.frame("MENU")
        self.assertEqual(self.app.face.draw.call_count, calls)
        self.assertEqual(sum(any(name in label for label in self.g["screen"].labels)
                             for name in work.NAMES), 12)
        self.frame("DOWN")
        self.assertEqual(self.app.index, 0)
        self.frame("BACK")
        self.assertFalse(self.app.menu_open)
        self.frame("MENU")
        self.frame("DOWN")
        self.frame("SELECT")
        self.assertEqual(self.app.index, 1)
        self.assertFalse(self.app.menu_open)

    def test_exit_restores_settings_and_flushes_selection(self):
        self.start(9)
        self.frame("RIGHT")
        self.app.on_exit()
        self.state.save.assert_called_once_with("twelve_clocks", {"face": 10})
        self.assertEqual(self.badge.default_clear, "previous-clear")
        self.assertEqual(self.g["screen"].antialias, 0)
        self.assertEqual(self.g["screen"].fill_rule, 0)
        self.assertEqual(self.g["screen"].font, "previous-font")
        self.assertNotIn(self.app.APP_DIR, self.path.path)
        self.assertIsNone(self.app.face)
        self.app.on_exit()
        self.state.save.assert_called_once()

    def test_invalid_state_and_save_errors_are_visible(self):
        self.start("invalid")
        self.assertEqual(self.app.index, 0)
        self.assertEqual(self.app.notice, "Selection reset")
        self.state.save.side_effect = OSError("disk full")
        self.frame("RIGHT")
        self.frame(delta=800)
        self.assertEqual(self.app.notice, "Selection not saved")

    def test_unset_rtc_warns_without_network(self):
        self.start()
        self.clock.localtime = lambda now: (2000, 1, 1, 0, 0, 0, 0, 0)
        self.frame()
        self.assertIn("RTC unset: use Clock app", self.g["screen"].labels)


if __name__ == "__main__":
    unittest.main()
