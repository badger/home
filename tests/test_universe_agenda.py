"""Host regression tests; not a substitute for firmware or physical checks."""

import ast
import builtins
import calendar
import copy
import io
import json
from pathlib import Path
import struct
import time
import types
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]


class Harness:
    def __init__(self):
        self.files = {}
        self.now = calendar.timegm((2026, 10, 29, 16, 50, 0))
        self.time = types.SimpleNamespace(
            time=lambda: self.now,
            gmtime=lambda stamp=None: time.gmtime(self.now if stamp is None else stamp),
            localtime=lambda stamp=None: time.gmtime(self.now if stamp is None else stamp),
            mktime=lambda value: calendar.timegm(tuple(value[:6]) + (0, 0, 0)),
        )
        self.state = types.SimpleNamespace(save=self.save)
        self.rtc = Mock()
        self.ntp = types.SimpleNamespace(settime=Mock())
        self.fake_builtins = types.SimpleNamespace(rtc=self.rtc)
        self.modules = {
            "time": self.time, "utime": self.time,
            "badgeware": types.SimpleNamespace(State=self.state),
            "ntptime": self.ntp, "builtins": self.fake_builtins,
        }
        self.clock = self.load("utc_clock", ROOT / "badge" / "utc_clock.py")
        self.agenda = self.load("universe_agenda", ROOT / "badge" / "universe_agenda.py")
        self.clock._synced = True

    def save(self, key, value):
        self.files["/state/" + key + ".json"] = json.dumps(value)

    def open(self, path, *args, **kwargs):
        path = str(path)
        if path not in self.files:
            raise OSError(2, "File not found")
        return io.StringIO(self.files[path])

    def importer(self, name, globals=None, locals=None, fromlist=(), level=0):
        if name in self.modules:
            return self.modules[name]
        return builtins.__import__(name, globals, locals, fromlist, level)

    def load(self, name, path):
        module = types.ModuleType(name)
        module.__dict__.update({
            "__builtins__": dict(vars(builtins), __import__=self.importer, open=self.open),
            "rtc": self.rtc,
        })
        exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)
        self.modules[name] = module
        return module

    def event(self, identity="one", start="2026-10-29T17:00:00Z"):
        return {
            "id": identity, "title": "Synthetic test session", "start": start,
            "end": "2026-10-29T18:00:00Z", "location": "Test room",
        }

    def import_events(self, agenda, events):
        self.files[self.agenda.IMPORT_PATH] = json.dumps({"source": "Synthetic test fixture", "events": events})
        agenda.import_agenda()

    def prepared(self, events=None):
        agenda = self.agenda.Agenda()
        self.import_events(agenda, events if events is not None else [self.event()])
        return agenda


class AgendaTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()

    def test_empty_account_has_no_invented_sessions(self):
        agenda = self.h.agenda.Agenda()
        self.assertEqual(agenda.events, [])
        self.assertEqual(agenda.state["source"], "")
        agenda.tick(16)
        self.assertIsNone(agenda.current)

    def test_lead_boundary_and_once_after_home_reset(self):
        agenda = self.h.prepared()
        self.h.now -= 1
        agenda.tick(16)
        self.assertIsNone(agenda.current)
        self.h.now += 1
        agenda.tick(16)
        self.assertEqual(agenda.current["id"], "one")
        self.assertEqual(agenda.remaining, 12000)
        restarted = self.h.agenda.Agenda()
        restarted.tick(16)
        self.assertIsNone(restarted.current)

    def test_simultaneous_sessions_queue_and_expire(self):
        agenda = self.h.prepared([self.h.event("one"), self.h.event("two")])
        agenda.tick(16)
        self.h.now += 11
        agenda.tick(11000)
        self.assertEqual(agenda.current["id"], "one")
        self.h.now += 1
        agenda.tick(1000)
        self.assertEqual(agenda.current["id"], "two")
        self.h.now += 12
        agenda.tick(12000)
        self.assertIsNone(agenda.current)

    def test_current_or_past_sessions_do_not_notify(self):
        agenda = self.h.prepared()
        self.h.now += 600
        agenda.tick(16)
        self.assertIsNone(agenda.current)
        self.h.now += 1
        agenda.tick(16)
        self.assertIsNone(agenda.current)

    def test_disabled_then_enabled_within_window(self):
        agenda = self.h.prepared()
        agenda.save({"enabled": False})
        agenda.tick(16)
        self.assertIsNone(agenda.current)
        agenda.save({"enabled": True})
        self.h.now += 1
        agenda.tick(16)
        self.assertIsNotNone(agenda.current)
        agenda.save({"enabled": False})
        agenda.tick(16)
        self.assertIsNone(agenda.current)

    def test_unset_clock_holds_reminders_until_sync(self):
        agenda = self.h.prepared()
        self.h.clock._synced = False
        agenda.tick(16)
        self.assertIsNone(agenda.current)
        self.h.clock.sync()
        self.h.now += 1
        agenda.tick(16)
        self.assertIsNotNone(agenda.current)

    def test_reboot_to_2021_does_not_trust_saved_sync(self):
        self.h.save("utc_clock", {"synced": True})
        self.h.clock._synced = None
        self.h.now = calendar.timegm((2021, 1, 1, 0, 0, 0))
        self.assertFalse(self.h.clock.ready())

    def test_moved_session_can_notify_again(self):
        agenda = self.h.prepared()
        agenda.tick(16)
        self.h.import_events(agenda, [self.h.event(start="2026-10-29T17:05:00Z")])
        self.h.now += 300
        agenda.tick(16)
        self.assertIsNotNone(agenda.current)

    def test_import_does_not_replay_already_notified_session(self):
        agenda = self.h.prepared()
        agenda.tick(16)
        self.h.import_events(agenda, [self.h.event()])
        self.h.now += 1
        agenda.tick(16)
        self.assertIsNone(agenda.current)

    def test_invalid_import_is_all_or_nothing(self):
        agenda = self.h.prepared()
        before = copy.deepcopy(agenda.state)
        for events in (
            [self.h.event(), self.h.event()],
            [self.h.event(start="2026-02-30T17:00:00Z")],
            [dict(self.h.event(), end="2026-10-29T16:00:00Z")],
            [dict(self.h.event(), title=123)],
            [dict(self.h.event(), location=0)],
            [self.h.event(str(i)) for i in range(129)],
        ):
            with self.subTest(events=str(events)[:60]):
                with self.assertRaises((ValueError, TypeError)):
                    self.h.import_events(agenda, events)
                self.assertEqual(agenda.state, before)

    def test_clear_and_oversize_import(self):
        agenda = self.h.prepared()
        self.h.import_events(agenda, [])
        self.assertEqual(agenda.events, [])
        self.h.files[self.h.agenda.IMPORT_PATH] = " " * 65537
        with self.assertRaisesRegex(ValueError, "64 KiB"):
            agenda.import_agenda()

    def test_invalid_stored_settings_keep_usable_defaults_and_report(self):
        self.h.save("universe_agenda", {"lead_minutes": "broken"})
        agenda = self.h.agenda.Agenda()
        self.assertTrue(agenda.error)
        self.assertEqual(agenda.state["lead_minutes"], 10)
        agenda.tick(16)
        self.assertIsNone(agenda.current)

    def test_silently_failed_firmware_save_does_not_claim_notification(self):
        agenda = self.h.prepared()
        self.h.state.save = Mock()
        agenda.tick(16)
        self.assertIsNone(agenda.current)
        self.assertIn("did not save", agenda.error)

    def test_corrupt_storage_is_reported_not_shown_as_empty_success(self):
        self.h.files["/state/universe_agenda.json"] = "{"
        self.assertTrue(self.h.agenda.Agenda().error)

    def test_lead_time_is_persistent_and_used(self):
        agenda = self.h.prepared()
        agenda.save({"lead_minutes": 5})
        agenda = self.h.agenda.Agenda()
        agenda.tick(16)
        self.assertIsNone(agenda.current)
        self.h.now += 300
        agenda.tick(16)
        self.assertIsNotNone(agenda.current)


class ClockTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()

    def test_sync_keeps_rtc_in_utc_and_verifies_marker(self):
        self.h.clock.sync()
        self.h.ntp.settime.assert_called_once()
        self.h.rtc.localtime_to_rtc.assert_called_once_with()
        self.h.rtc.datetime.assert_not_called()
        self.h.clock._synced = None
        self.assertTrue(self.h.clock.ready())

    def test_failed_ntp_or_rtc_save_is_not_reported_as_synced(self):
        self.h.ntp.settime.side_effect = OSError("timeout")
        with self.assertRaises(OSError):
            self.h.clock.sync()
        self.assertFalse(self.h.clock.ready())
        self.h.ntp.settime.side_effect = None
        self.h.state.save = Mock()
        with self.assertRaises(OSError):
            self.h.clock.sync()
        self.assertFalse(self.h.clock.ready())

    def test_pacific_daylight_saving_exact_boundaries(self):
        cases = {
            "2026-03-08T09:59:59Z": (1, 59, 59),
            "2026-03-08T10:00:00Z": (3, 0, 0),
            "2026-11-01T08:59:59Z": (1, 59, 59),
            "2026-11-01T09:00:00Z": (1, 0, 0),
            "2026-10-29T17:00:00Z": (10, 0, 0),
        }
        for stamp, expected in cases.items():
            with self.subTest(stamp=stamp):
                self.assertEqual(self.h.clock.pacific_time(self.h.clock.parse_utc(stamp))[3:6], expected)

    def test_bad_utc_dates_are_rejected(self):
        for stamp in ("2026-02-30T17:00:00Z", "2026-10-29T25:00:00Z",
                      "2026-10-29T17:00:00-07:00", "2026-10-29", None,
                      "9999-10-29T17:00:00Z", "2026-13-29T17:00:00Z",
                      "2026-+1-29T17:00:00Z"):
            with self.subTest(stamp=stamp):
                with self.assertRaises(ValueError):
                    self.h.clock.parse_utc(stamp)

    def test_existing_clock_failure_waits_for_explicit_retry(self):
        path = ROOT / "badge" / "apps" / "clock" / "__init__.py"
        tree = ast.parse(path.read_text())
        nodes = [node for node in tree.body if
                 (isinstance(node, ast.FunctionDef) and node.name == "update")
                 or (isinstance(node, ast.ClassDef) and node.name == "ClockState")]
        namespace = {
            "badge": types.SimpleNamespace(pressed=lambda *args: False),
            "utc_clock": types.SimpleNamespace(ready=lambda: False),
            "state": {}, "user_message": Mock(), "update_time": Mock(return_value=False),
            "wifi": types.SimpleNamespace(connect=Mock(return_value=False)),
            "REGION": "us", "TIMEZONE": -8,
        }
        for button in ("UP", "DOWN", "LEFT", "RIGHT", "SELECT"):
            namespace["BUTTON_" + button] = button
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
        namespace["clock_state"] = namespace["ClockState"].UpdateTime
        namespace["update"]()
        self.assertEqual(namespace["clock_state"], namespace["ClockState"].Error)
        namespace["update"]()
        namespace["update_time"].assert_called_once()
        namespace["clock_state"] = namespace["ClockState"].ConnectWiFi
        namespace["update"]()
        namespace["update"]()
        namespace["wifi"].connect.assert_called_once()

    def test_epoch_independent_timestamp_parsing(self):
        epoch_2000 = calendar.timegm((2000, 1, 1, 0, 0, 0))
        self.h.time.gmtime = lambda stamp=None: time.gmtime(
            (self.h.now if stamp is None else stamp) + epoch_2000)
        self.h.time.mktime = lambda value: calendar.timegm(tuple(value[:6]) + (0, 0, 0)) - epoch_2000
        stamp = self.h.clock.parse_utc("2026-10-29T17:00:00Z")
        self.assertEqual(self.h.clock.pacific_time(stamp)[3:6], (10, 0, 0))

    def test_existing_clock_converts_display_without_rtc_offset_writes(self):
        path = ROOT / "badge" / "apps" / "clock" / "__init__.py"
        tree = ast.parse(path.read_text())
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name in ("display_time", "update_time")]
        namespace = {
            "time": self.h.time, "utc_clock": self.h.clock,
            "display_zone": types.SimpleNamespace(localtime=lambda stamp: stamp - 7 * 3600),
            "DisplayType": types.SimpleNamespace(textclock=1, dotsclock=2, nixie=3, sevenseg=4),
            "state": {"clock_style": 1}, "draw_text_clock": Mock(),
        }
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"), namespace)
        self.assertTrue(namespace["update_time"]("us", -8))
        namespace["display_time"]()
        displayed = namespace["draw_text_clock"].call_args.args[0]
        self.assertEqual(displayed[3:6], (9, 50, 0))
        self.h.rtc.datetime.assert_not_called()

    def test_existing_dst_uses_utc_boundaries_in_both_hemispheres(self):
        dst_module = self.h.load("daylightsaving", ROOT / "badge" / "apps" / "clock" / "daylightsaving.py")
        policy = dst_module.DaylightSavingPolicy
        with patch("sys.stdout", new=io.StringIO()):
            us = dst_module.DaylightSaving(policy(0, 2, 3, 6, 2, -420), policy(0, 1, 11, 6, 2, -480))
            au = dst_module.DaylightSaving(policy(1, 1, 10, 6, 2, 660), policy(1, 1, 4, 6, 3, 600))
        for rule, stamp, offset in (
            (us, "2026-03-08T09:59:59Z", -480),
            (us, "2026-03-08T10:00:00Z", -420),
            (us, "2026-11-01T09:00:00Z", -480),
            (au, "2026-10-03T15:59:59Z", 600),
            (au, "2026-10-03T16:00:00Z", 660),
            (au, "2026-04-04T16:00:00Z", 600),
        ):
            with self.subTest(stamp=stamp):
                utc = self.h.clock.parse_utc(stamp)
                self.assertEqual(rule.localtime(utc) - utc, offset * 60)


class RuntimeTests(unittest.TestCase):
    def test_wrapper_preserves_constructor_duration_progress_and_launch_result(self):
        h = Harness()
        calls = []

        class Run:
            def __init__(self, update=None, duration=None):
                self.duration = duration
                self.result = None
                self.start = 100
                if update:
                    self(update)

            @property
            def progress(self):
                return 0.5

            def __call__(self, update):
                result = update()
                calls.append("display")
                self.result = result

        h.fake_builtins.run = Run
        h.agenda.run = Run
        h.agenda.overlay = lambda: calls.append("overlay")
        h.agenda.restore_overlay = lambda: calls.append("restore")
        h.agenda.install()
        installed_run = h.fake_builtins.run
        h.agenda.install()
        self.assertIs(h.fake_builtins.run, installed_run)
        loop = installed_run(lambda: calls.append("app"), duration=500)
        self.assertEqual(calls, ["restore", "app", "overlay", "display"])
        self.assertEqual(loop.duration, 500)
        self.assertEqual(loop.progress, 0.5)
        calls.clear()
        launcher = installed_run(lambda: "/system/apps/clock")
        self.assertEqual(launcher.result, "/system/apps/clock")
        self.assertEqual(calls, ["restore", "display"])

    def test_banner_restoration_handles_incremental_drawing_and_resolution_changes(self):
        h = Harness()
        h.agenda.screen = Mock(width=160, height=120)
        h.agenda.vec2 = lambda x, y: (x, y)
        background = object()
        h.agenda._background = background
        h.agenda._covered = (160, 120, 3, 78, 154, 39)
        h.agenda.restore_overlay()
        h.agenda.screen.window.assert_called_once_with(3, 78, 154, 39)
        h.agenda.screen.window.return_value.blit.assert_called_once_with(background, (0, 0))
        self.assertIsNone(h.agenda._covered)
        h.agenda.screen.reset_mock()
        h.agenda._covered = (320, 240, 3, 198, 314, 39)
        h.agenda.restore_overlay()
        h.agenda.screen.window.assert_not_called()

    def test_main_installs_before_startup_menu_and_selected_app(self):
        h = Harness()
        actions = []
        h.modules["sys"] = types.SimpleNamespace(path=[])
        h.modules["powman"] = types.SimpleNamespace(
            get_wake_reason=lambda: 0, WAKE_DOUBLETAP=1, WAKE_WATCHDOG=2,
        )
        h.agenda.install = lambda: actions.append("install")
        def launch(path):
            actions.append(path)
            return "/system/apps/clock" if path.endswith("/menu") else None
        badge = Mock()
        badge.pressed.return_value = badge.held.return_value = badge.released.return_value = False
        namespace = {
            "__builtins__": dict(vars(builtins), __import__=h.importer),
            "badge": badge, "launch": launch, "reset": Mock(),
        }
        exec(compile((ROOT / "badge" / "main.py").read_text(), "main.py", "exec"), namespace)
        self.assertEqual(actions, ["install", "/system/apps/startup", "/system/apps/menu", "/system/apps/clock"])
        namespace["reset"].assert_called_once()

    def test_new_app_renders_empty_agenda_and_settings_without_legacy_api(self):
        h = Harness()
        h.modules["sys"] = types.SimpleNamespace(path=[])
        h.modules["os"] = types.SimpleNamespace(chdir=Mock())
        screen = Mock(width=160, height=120)
        screen.measure_text.side_effect = lambda value: (len(value) * 4, 8)
        pressed = set()
        namespace = {
            "__builtins__": dict(vars(builtins), __import__=h.importer),
            "screen": screen, "badge": types.SimpleNamespace(
                pressed=lambda button: button in pressed, ticks_delta=16),
            "image": types.SimpleNamespace(EVEN_ODD=1),
            "font": types.SimpleNamespace(ark="ark"), "color": Mock(), "shape": Mock(),
            "BUTTON_LEFT": "left", "BUTTON_RIGHT": "right", "BUTTON_UP": "up",
            "BUTTON_DOWN": "down", "BUTTON_SELECT": "select", "run": Mock(),
        }
        path = ROOT / "badge" / "apps" / "universe_agenda" / "__init__.py"
        exec(compile(path.read_text(), str(path), "exec"), namespace)
        h.agenda.color = namespace["color"]
        h.agenda.shape = namespace["shape"]
        namespace["update"]()
        self.assertTrue(any("Account not connected" == call.args[0] for call in screen.text.call_args_list))
        pressed.add("right")
        namespace["update"]()
        self.assertEqual(namespace["tab"], 1)
        pressed.clear()
        pressed.add("select")
        namespace["update"]()
        self.assertEqual(namespace["agenda"].state["lead_minutes"], 15)

    def test_icon_is_custom_48px_png_and_reproducible(self):
        path = ROOT / "tools" / "generate_universe_agenda_icon.py"
        namespace = {"__name__": "icon_under_test"}
        exec(compile(path.read_text(), str(path), "exec"), namespace)
        icon = (ROOT / "badge" / "apps" / "universe_agenda" / "icon.png").read_bytes()
        self.assertEqual(icon, namespace["icon_bytes"]())
        self.assertEqual(struct.unpack(">II", icon[16:24]), (48, 48))


if __name__ == "__main__":
    unittest.main()
