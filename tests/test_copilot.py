"""Host-side checks for the standalone October 2026 Copilot app."""

import gc
import hashlib
import json
from pathlib import Path
import random
import sys
import types
import unittest
from unittest.mock import Mock
import weakref

from PIL import Image


APP = Path(__file__).resolve().parents[1] / "badge/apps/Copilot"
sys.path.insert(0, str(APP))
PERIOD = 1 << 30


class Clock:
    def __init__(self):
        self.now = 100

    def ticks_ms(self):
        return self.now

    def ticks_diff(self, a, b):
        return (a - b + PERIOD // 2) % PERIOD - PERIOD // 2

    def ticks_add(self, a, b):
        return (a + b) % PERIOD

    def advance(self, ms):
        self.now = self.ticks_add(self.now, ms)


class CopilotTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.keys = set()
        self.screen = Mock()
        self.screen.measure_text.side_effect = lambda text: (len(text) * 7, 13)
        self.badge = Mock()
        self.badge.pressed.side_effect = lambda key: key in self.keys
        self.image = Mock()
        self.image.load.side_effect = lambda path: types.SimpleNamespace(width=192, height=180)
        self.namespace = {
            "badge": self.badge, "screen": self.screen,
            "color": Mock(), "font": Mock(), "image": self.image,
            "rect": lambda *args: args, "HIRES": 1, "VSYNC": 2,
        }
        for key in ("BACK", "LEFT", "RIGHT", "UP", "DOWN", "SELECT"):
            self.namespace["BUTTON_" + key] = key
        source = (APP / "__init__.py").read_text().split("\napp = CopilotApp()")[0]
        exec(compile(source, str(APP / "__init__.py"), "exec"), self.namespace)
        self.namespace["time"] = self.clock
        self.namespace["random"] = random.Random(42)
        self.app = self.namespace["CopilotApp"](monitor=False)

    def press(self, key):
        self.keys.add(key)
        try:
            return self.app.update()
        finally:
            self.keys.clear()

    def labels(self):
        return [call.args[0] for call in self.screen.text.call_args_list]

    def test_native_runtime_and_initial_offline_render(self):
        self.app.update()
        self.badge.mode.assert_called_once_with(3)
        self.image.load.assert_called_once_with("/system/apps/Copilot/assets/neutral.png")
        self.screen.blit.assert_called_once_with(self.app.sprite, (64, 22, 192, 180))
        self.assertEqual(self.namespace["color"].rgb.call_args_list[0].args, (0, 0, 0))
        self.assertIn("GitHub Copilot", self.labels())
        self.assertIn("Your Agent Buddy", self.labels())
        self.assertNotIn("Offline demo", self.labels())

    def test_right_and_left_wrap_modes(self):
        for mode in ("working", "attention", "complete", "idle"):
            self.press("RIGHT")
            self.assertEqual(self.app.mode, mode)
        self.press("LEFT")
        self.assertEqual(self.app.mode, "complete")

    def test_hello_finishes_at_exact_boundary(self):
        self.press("UP")
        self.assertEqual(self.app.mode, "surprise")
        self.clock.advance(959)
        self.app.update()
        self.assertEqual(self.app.mode, "surprise")
        self.assertEqual(self.app.sprite_name, "surprise-11")
        self.clock.advance(1)
        self.app.update()
        self.assertEqual(self.app.mode, "idle")

    def test_complete_is_transient_but_work_and_attention_are_not(self):
        for mode in ("working", "attention", "complete"):
            self.app.set_mode(mode, self.clock.now)
            self.clock.advance(5000)
            self.app.update()
            self.assertEqual(self.app.mode, "idle" if mode == "complete" else mode)

    def test_demo_visits_all_states_and_wraps(self):
        self.press("SELECT")
        self.assertTrue(self.app.demo)
        self.assertEqual(self.app.mode, "surprise")
        for duration, expected in ((960, "working"), (6000, "attention"), (5000, "complete"),
                                   (4000, "idle"), (5000, "surprise")):
            self.clock.advance(duration - 1)
            previous = self.app.mode
            self.app.update()
            self.assertEqual(self.app.mode, previous)
            self.clock.advance(1)
            self.app.update()
            self.assertEqual(self.app.mode, expected)
        self.assertTrue(self.app.demo)

    def test_select_stops_demo_and_manual_input_cancels_it(self):
        self.press("SELECT")
        self.press("SELECT")
        self.assertFalse(self.app.demo)
        self.assertEqual(self.app.mode, "idle")
        for key in ("LEFT", "RIGHT", "UP", "DOWN"):
            self.app.start_demo(self.clock.now)
            self.press(key)
            self.assertFalse(self.app.demo)

    def test_sleep_at_two_minutes_not_before(self):
        self.clock.advance(119999)
        self.app.update()
        self.assertEqual(self.app.mode, "idle")
        self.clock.advance(1)
        self.app.update()
        self.assertEqual(self.app.mode, "sleep")
        self.assertEqual(self.app.sprite_name, "blink-4")

    def test_nap_and_wake_reset_inactivity(self):
        self.clock.advance(119000)
        self.press("DOWN")
        self.assertEqual(self.app.mode, "sleep")
        self.clock.advance(50000)
        self.press("SELECT")
        self.assertFalse(self.app.demo)
        self.assertEqual(self.app.mode, "idle")
        self.clock.advance(119999)
        self.app.update()
        self.assertEqual(self.app.mode, "idle")
        self.press("DOWN")
        self.press("DOWN")
        self.assertEqual(self.app.mode, "idle")

    def test_back_exits_from_every_mode_and_error(self):
        for mode in ("idle", "working", "attention", "complete", "surprise", "sleep"):
            self.app.set_mode(mode, self.clock.now)
            self.assertIs(self.press("BACK"), False)
        self.app.error = "Missing or invalid artwork"
        self.assertIs(self.press("BACK"), False)

    def test_standalone_entry_point_runs_and_cleans_up_on_exit(self):
        self.keys.add("BACK")
        run = Mock(side_effect=lambda update: self.assertIs(update(), False))
        self.namespace["run"] = run
        source = (APP / "__init__.py").read_text()
        exec("\napp = CopilotApp()" + source.split("\napp = CopilotApp()")[1], self.namespace)
        run.assert_called_once_with(self.namespace["app"].update)
        self.assertIsNone(self.namespace["app"].sprite)

    def test_idle_blink_sequence_and_next_deadline(self):
        self.app.next_look = self.clock.ticks_add(self.clock.now, 10000)
        self.clock.now = self.app.next_blink
        for expected in (1, 2, 3, 4, 3, 2, 1):
            self.app.update()
            self.assertEqual(self.app.sprite_name, "blink-%d" % expected)
            self.clock.advance(45)
        self.app.update()
        self.assertEqual(self.app.sprite_name, "neutral")
        self.assertGreater(self.clock.ticks_diff(self.app.next_blink, self.clock.now), 0)

    def test_idle_look_goes_out_and_back_without_invalid_indices(self):
        self.app.next_blink = self.clock.ticks_add(self.clock.now, 20000)
        self.clock.now = self.app.next_look
        self.app.update()
        look = self.app.look
        self.assertIn(look, self.namespace["LOOKS"])
        names = [self.app.sprite_name]
        for _ in range(23):
            self.clock.advance(80)
            self.app.update()
            names.append(self.app.sprite_name)
        self.assertEqual(names[0], look + "-00")
        self.assertEqual(names[11], look + "-11")
        self.assertEqual(names[22], look + "-00")
        self.assertEqual(names[23], "neutral")

    def test_expression_ping_pong_has_no_wrap_snap(self):
        self.app.set_mode("working", self.clock.now)
        names = []
        for _ in range(24):
            names.append(self.app.animate(self.clock.now))
            self.clock.advance(80)
        self.assertEqual(names[:3], ["working-00", "working-01", "working-02"])
        self.assertEqual(names[11:14], ["working-11", "working-10", "working-09"])
        self.assertEqual(names[21:24], ["working-01", "working-00", "working-01"])

    def test_tick_rollover_preserves_sleep_and_hello_timing(self):
        self.clock.now = PERIOD - 500
        self.app.last_input = self.clock.now
        self.app.set_mode("idle", self.clock.now)
        self.press("UP")
        self.clock.advance(960)
        self.app.update()
        self.assertEqual(self.app.mode, "idle")
        self.clock.advance(120000 - 960)
        self.app.update()
        self.assertEqual(self.app.mode, "sleep")

    def test_deadlines_remain_future_across_tick_rollover(self):
        self.clock.now = PERIOD - 500
        self.app.last_input = self.clock.now
        self.app.set_mode("idle", self.clock.now)
        self.assertEqual(self.app.animate(self.clock.now), "neutral")
        self.assertGreater(self.clock.ticks_diff(self.app.next_blink, self.clock.now), 0)
        self.assertGreater(self.clock.ticks_diff(self.app.next_look, self.clock.now), 0)

    def test_unchanged_frame_is_not_redecoded(self):
        self.app.update()
        for _ in range(20):
            self.clock.advance(1)
            self.app.update()
        self.image.load.assert_called_once()

    def test_previous_image_is_released_before_decode(self):
        class Sprite:
            pass
        old = Sprite()
        reference = weakref.ref(old)
        self.app.sprite = old
        self.app.sprite_name = "neutral"
        del old

        def load(path):
            gc.collect()
            self.assertIsNone(reference())
            return Sprite()

        self.image.load.side_effect = load
        self.app.load_frame("working-00")
        self.assertEqual(self.app.sprite_name, "working-00")
        self.app.close()
        self.assertIsNone(self.app.sprite)

    def test_missing_and_corrupt_assets_are_reported_without_retry_loop(self):
        for error in (OSError("missing"), ValueError("invalid PNG"), RuntimeError("decode failed")):
            with self.subTest(error=error):
                self.app.error = None
                self.image.load.reset_mock()
                self.image.load.side_effect = error
                self.app.update()
                self.assertEqual(self.app.error, "Missing or invalid artwork")
                self.assertIn("Copy the complete assets folder", self.labels())
                self.app.update()
                self.image.load.assert_called_once()
                self.image.load.side_effect = lambda path: object()
                self.press("SELECT")
                self.assertIsNone(self.app.error)
                self.assertIsNotNone(self.app.sprite)
                self.app.sprite_name = None

    def test_all_runtime_frame_names_exist_and_have_bounded_dimensions(self):
        expected = {"neutral", "blink-1", "blink-2", "blink-3", "blink-4"}
        for track in (*self.namespace["LOOKS"], "surprise", "working", "attention", "complete"):
            expected.update("%s-%02d" % (track, index) for index in range(12))
        assets = APP / "assets"
        self.assertEqual({path.stem for path in assets.glob("*.png")}, expected)
        for name in expected:
            with Image.open(assets / (name + ".png")) as frame:
                self.assertEqual(frame.size, (192, 180))
                self.assertEqual(frame.mode, "RGB")
                frame.verify()
            with Image.open(assets / (name + ".png")) as frame:
                # Every visible pose must clear the status label at y=194.
                bounds = frame.point(lambda value: 255 if value > 16 else 0).getbbox()
                self.assertLess(bounds[3] + 22, 194)
        with Image.open(APP / "icon.png") as icon:
            self.assertEqual(icon.size, (24, 24))
            self.assertEqual(icon.mode, "RGB")
        self.assertLess(sum(path.stat().st_size for path in assets.iterdir()), 3_000_000)

    def test_source_metadata_and_mit_license_ship_with_assets(self):
        assets = APP / "assets"
        metadata = json.loads((assets / "sources.json").read_text())
        self.assertEqual(metadata["revision"], "c246248cc091b59fb199c54ad7f40fab0836e00a")
        self.assertEqual(len(metadata["files"]), 101)
        for entry in metadata["files"]:
            self.assertEqual(hashlib.sha256((assets / entry["file"]).read_bytes()).hexdigest(),
                             entry["sha256"])
        license_text = (assets / "LICENSE.txt").read_text()
        self.assertIn("MIT License", license_text)
        self.assertIn("Copyright (c) 2026 Dan Wahlin", license_text)


if __name__ == "__main__":
    unittest.main()
