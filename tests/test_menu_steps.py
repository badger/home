"""Host-side regression checks for the home-screen step-count widget."""

import builtins
from pathlib import Path
import types
import unittest
from unittest.mock import Mock


UI = Path(__file__).resolve().parents[1] / "badge/apps/menu/src/ui.py"
PERIOD = 1 << 30


class MenuStepsTests(unittest.TestCase):
    def setUp(self):
        self.reader = Mock(return_value=123)
        self.badge = types.SimpleNamespace(
            ticks=100, _imu=types.SimpleNamespace(get_step_count=self.reader),
            is_charging=lambda: False, battery_level=lambda: 80,
        )
        self.screen = Mock()
        self.screen.measure_text.side_effect = lambda text: (len(text) * 8, 17)
        self.load_ui()

    def load_ui(self):
        self.log = Mock()
        self.ui = {
            "badge": self.badge,
            "screen": self.screen,
            "color": types.SimpleNamespace(rgb=lambda *args: args),
            "font": types.SimpleNamespace(salty="salty", ignore="ignore"),
            "print": self.log,
        }
        clock = types.SimpleNamespace(
            ticks_diff=lambda a, b: (a - b + PERIOD // 2) % PERIOD - PERIOD // 2,
        )
        real_import = builtins.__import__

        def import_module(name, *args, **kwargs):
            return clock if name == "time" else real_import(name, *args, **kwargs)

        self.ui["__builtins__"] = dict(vars(builtins), __import__=import_module)
        exec(compile(UI.read_text(), str(UI), "exec"), self.ui)

    def read_steps(self):
        self.screen.font = "salty"
        return self.ui["read_steps"]()

    def test_reads_immediately_and_refreshes_at_one_second(self):
        self.assertEqual(self.read_steps(), ("123 steps", 72))
        self.reader.return_value = 124
        for elapsed in (0, 1, 999):
            self.badge.ticks = 100 + elapsed
            self.assertEqual(self.read_steps()[0], "123 steps")
        self.reader.assert_called_once_with()
        self.badge.ticks = 1100
        self.assertEqual(self.read_steps()[0], "124 steps")
        self.assertEqual(self.reader.call_count, 2)

    def test_refreshes_across_tick_wrap(self):
        self.badge.ticks = PERIOD - 500
        self.read_steps()
        self.badge.ticks = 499
        self.read_steps()
        self.reader.assert_called_once_with()
        self.badge.ticks = 500
        self.read_steps()
        self.assertEqual(self.reader.call_count, 2)

    def test_unsigned_counter_and_hardware_reset(self):
        for raw, expected in ((0, 0), (32767, 32767), (-32768, 32768),
                              (-1, 65535), (0, 0)):
            self.reader.return_value = raw
            self.badge.ticks += 1000
            self.assertEqual(self.read_steps()[0], f"{expected} steps")
        self.assertFalse(hasattr(self.badge._imu, "reset_step_count"))

    def test_missing_firmware_api_is_visible_and_logged_once(self):
        for imu in (None, types.SimpleNamespace()):
            with self.subTest(imu=imu):
                self.badge._imu = imu
                self.load_ui()
                self.assertEqual(self.read_steps()[0], "-- steps")
                self.badge.ticks += 1000
                self.assertEqual(self.read_steps()[0], "-- steps")
                self.log.assert_called_once_with(
                    "Step counter unavailable: firmware has no IMU step API"
                )

    def test_sensor_failure_retries_without_showing_stale_count(self):
        self.read_steps()
        self.reader.side_effect = OSError("I2C unavailable")
        for _ in range(2):
            self.badge.ticks += 1000
            self.assertEqual(self.read_steps()[0], "-- steps")
        self.assertEqual(self.log.call_count, 1)
        self.reader.side_effect = None
        self.reader.return_value = 456
        self.badge.ticks += 1000
        self.assertEqual(self.read_steps()[0], "456 steps")
        self.reader.side_effect = OSError("I2C unavailable again")
        self.badge.ticks += 1000
        self.assertEqual(self.read_steps()[0], "-- steps")
        self.assertEqual(self.log.call_count, 2)

    def test_status_preserves_existing_content_and_fits_maximum_count(self):
        self.reader.return_value = -1
        self.ui["draw_status"](98, 99)
        calls = self.screen.text.call_args_list
        self.assertEqual([call.args[0] for call in calls],
                         ["MonaOS 4.0", "99 / 99", "65535 steps"])
        count, steps = calls[1].args, calls[2].args
        self.assertGreaterEqual(steps[1], count[1] + len(count[0]) * 8 + 6)
        self.assertLessEqual(steps[1] + len(steps[0]) * 8, 282)
        self.screen.text.reset_mock()
        self.ui["draw_status"](98, 99, hidden=1.0)
        self.assertTrue(all(call.args[2] == -18
                            for call in self.screen.text.call_args_list))


if __name__ == "__main__":
    unittest.main()
