"""Host-side regression checks for System credential loading and NTP retries."""

import builtins
from pathlib import Path
import sys
import time
import types
import unittest
from unittest.mock import Mock


APP = Path(__file__).resolve().parents[1] / "badge/apps/system/__init__.py"
PERIOD = 1 << 30


class Clock:
    def __init__(self):
        self.now = 100

    def ticks_ms(self):
        return self.now

    def ticks_diff(self, a, b):
        return (a - b + PERIOD // 2) % PERIOD - PERIOD // 2

    def advance(self, ms):
        self.now = (self.now + ms) % PERIOD

    localtime = staticmethod(time.localtime)
    time = staticmethod(time.time)


class SystemTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.io = types.SimpleNamespace(
            BUTTON_A="A", BUTTON_UP="UP", BUTTON_DOWN="DOWN", pressed=set()
        )
        self.screen = Mock()
        self.screen.measure_text.return_value = (20, 8)
        self.path = types.SimpleNamespace(path=list(sys.path))
        self.ntptime = Mock()
        self.wlan = Mock()
        self.wlan.ifconfig.return_value = ("192.0.2.1", "", "", "")
        self.network = Mock()
        self.network.WLAN.return_value = self.wlan
        self.credentials = types.ModuleType("secrets")
        self.credentials.WIFI_SSID = "test-network"
        self.credentials.WIFI_PASSWORD = "test-only"
        self.import_paths = []
        self.modules = {
            "sys": self.path,
            "os": types.SimpleNamespace(chdir=Mock()),
            "badgeware": types.SimpleNamespace(
                io=self.io, brushes=Mock(), shapes=Mock(), screen=self.screen,
                PixelFont=Mock(), run=Mock(), State=Mock(),
                get_battery_level=lambda: 50, is_charging=lambda: False,
            ),
            "time": self.clock,
            "machine": Mock(),
            "network": self.network,
            "ntptime": self.ntptime,
        }
        self.namespace = {
            "__name__": "system_under_test",
            "__builtins__": dict(vars(builtins), __import__=self.import_module),
        }
        exec(compile(APP.read_text(), str(APP), "exec"), self.namespace)
        self.original_path = list(self.path.path)

    def import_module(self, name, globals=None, locals=None, fromlist=(), level=0):
        if name == "secrets":
            self.import_paths.append(list(self.path.path))
            if self.credentials is None:
                raise ImportError("No test credentials module")
            return self.credentials
        if name == "board":
            raise ImportError("No hardware RTC in host tests")
        if name in self.modules:
            return self.modules[name]
        return builtins.__import__(name, globals, locals, fromlist, level)

    def connected(self):
        self.namespace["wlan"] = self.wlan

    def tick(self):
        self.namespace["tick_network"]()

    def fail_ntp(self):
        self.ntptime.settime.side_effect = OSError("NTP unavailable")
        self.connected()
        self.tick()

    def test_missing_credentials_restore_path_on_every_frame(self):
        for missing in ("module", "WIFI_SSID", "WIFI_PASSWORD"):
            with self.subTest(missing=missing):
                credentials = self.credentials
                if missing == "module":
                    self.credentials = None
                else:
                    value = getattr(credentials, missing)
                    delattr(credentials, missing)
                try:
                    for _ in range(100):
                        self.tick()
                        self.assertEqual(self.path.path, self.original_path)
                        self.assertIsNone(self.namespace["WIFI_SSID"])
                        self.assertIsNone(self.namespace["WIFI_PASSWORD"])
                        self.assertEqual(self.namespace["status"], "No WiFi config")
                finally:
                    self.credentials = credentials
                    if missing != "module":
                        setattr(credentials, missing, value)
        self.assertTrue(all(path == ["/"] + self.original_path
                            for path in self.import_paths))
        self.network.WLAN.assert_not_called()
        self.ntptime.settime.assert_not_called()

    def test_valid_credentials_are_loaded_once_and_restore_path(self):
        self.assertTrue(self.namespace["load_credentials"]())
        self.assertTrue(self.namespace["load_credentials"]())
        self.assertEqual(len(self.import_paths), 1)
        self.assertEqual(self.path.path, self.original_path)
        self.assertIsNotNone(self.namespace["WIFI_SSID"])
        self.assertIsNotNone(self.namespace["WIFI_PASSWORD"])

    def test_unexpected_import_error_still_restores_path(self):
        def broken_import(*args, **kwargs):
            raise RuntimeError("Unexpected import failure")

        self.namespace["__builtins__"]["__import__"] = broken_import
        with self.assertRaises(RuntimeError):
            self.namespace["load_credentials"]()
        self.assertEqual(self.path.path, self.original_path)

    def test_ntp_failure_cooldown_and_exact_retry_threshold(self):
        self.fail_ntp()
        for _ in range(100):
            self.tick()
        self.clock.advance(self.namespace["NTP_RETRY_MS"] - 1)
        self.tick()
        self.assertEqual(self.ntptime.settime.call_count, 1)
        self.assertEqual(self.namespace["status"], "Sync failed")
        self.assertFalse(self.namespace["ntp_synced"])
        self.clock.advance(1)
        self.tick()
        self.assertEqual(self.ntptime.settime.call_count, 2)
        self.clock.advance(self.namespace["NTP_RETRY_MS"] - 1)
        self.tick()
        self.assertEqual(self.ntptime.settime.call_count, 2)

    def test_cooldown_starts_after_blocking_failure(self):
        def slow_failure():
            self.clock.advance(5000)
            raise OSError("NTP unavailable")

        self.ntptime.settime.side_effect = slow_failure
        self.connected()
        self.tick()
        self.clock.advance(self.namespace["NTP_RETRY_MS"] - 1)
        self.tick()
        self.assertEqual(self.ntptime.settime.call_count, 1)
        self.clock.advance(1)
        self.tick()
        self.assertEqual(self.ntptime.settime.call_count, 2)

    def test_ntp_success_after_failure_stops_automatic_retries(self):
        self.fail_ntp()
        self.ntptime.settime.side_effect = None
        rtc_write = Mock()
        self.namespace["set_hw_rtc_from_utc"] = rtc_write
        self.clock.advance(self.namespace["NTP_RETRY_MS"])
        self.tick()
        self.assertTrue(self.namespace["ntp_synced"])
        self.assertTrue(self.namespace["time_valid"])
        self.assertEqual(self.namespace["source"], "NTP")
        self.assertEqual(self.namespace["status"], "Synced")
        rtc_write.assert_called_once_with()
        self.clock.advance(self.namespace["NTP_RETRY_MS"])
        self.tick()
        self.assertEqual(self.ntptime.settime.call_count, 2)

    def test_a_bypasses_cooldown_and_can_resync_after_success(self):
        self.fail_ntp()
        self.ntptime.settime.side_effect = None
        self.io.pressed.add("A")
        self.namespace["update"]()
        self.assertEqual(self.ntptime.settime.call_count, 2)
        self.assertTrue(self.namespace["ntp_synced"])
        self.assertIsNone(self.namespace["ntp_failed_at"])
        self.namespace["update"]()
        self.assertEqual(self.ntptime.settime.call_count, 3)
        self.io.pressed.clear()
        self.namespace["update"]()
        self.assertEqual(self.ntptime.settime.call_count, 3)

    def test_rtc_clock_and_timezone_controls_work_during_cooldown(self):
        self.namespace.update(time_valid=True, source="RTC")
        self.fail_ntp()
        self.io.pressed.add("UP")
        self.namespace["update"]()
        self.assertEqual(self.ntptime.settime.call_count, 1)
        self.assertTrue(self.namespace["time_valid"])
        self.assertEqual(self.namespace["source"], "RTC")
        self.assertEqual(self.namespace["config"]["tz_offset"], 3)
        labels = [call.args[0] for call in self.screen.text.call_args_list]
        self.assertIn("via RTC - Sync failed", labels)
        self.assertIn("UTC+03:00", labels)

    def test_retry_threshold_across_timer_rollover(self):
        self.clock.now = PERIOD - 100
        self.fail_ntp()
        self.clock.advance(self.namespace["NTP_RETRY_MS"] - 1)
        self.tick()
        self.assertEqual(self.ntptime.settime.call_count, 1)
        self.clock.advance(1)
        self.tick()
        self.assertEqual(self.ntptime.settime.call_count, 2)

    def test_failure_at_zero_ticks_still_has_cooldown(self):
        self.clock.now = 0
        self.fail_ntp()
        self.tick()
        self.assertEqual(self.ntptime.settime.call_count, 1)


if __name__ == "__main__":
    unittest.main()
