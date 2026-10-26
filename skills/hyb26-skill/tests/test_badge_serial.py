from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import badge_serial  # noqa: E402

DEVS = """\
/dev/cu.Bluetooth-Incoming-Port None 0000:0000 None None
/dev/cu.usbmodem2101 5db304b0e9a89057 2e8a:1101 Pimoroni Pimoroni Tufty 2350 MicroPython
COM7 5db304b0e9a89058 2e8a:1101 Pimoroni Pimoroni Tufty 2350 MicroPython
"""


def fake_run(stdout: str = "", exc: Exception | None = None):
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if exc:
            raise exc
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")

    return run, calls


class BadgeSerialTests(unittest.TestCase):
    def test_parse_devs_selects_only_badges(self):
        self.assertEqual(
            badge_serial.parse_devs(DEVS), ["/dev/cu.usbmodem2101", "COM7"]
        )

    def test_find_port_requires_exactly_one_badge(self):
        run, _ = fake_run(DEVS.splitlines()[1] + "\n")
        self.assertEqual(badge_serial.find_port(["mpremote"], run), "/dev/cu.usbmodem2101")
        for output in ("", DEVS):
            run, _ = fake_run(output)
            with self.subTest(output=output[:20]), self.assertRaises(badge_serial.SerialError):
                badge_serial.find_port(["mpremote"], run)

    def test_disk_mode_calls_reset_into_msc_and_waits_for_mount(self):
        with tempfile.TemporaryDirectory() as temp:
            mount = Path(temp)
            for exc in (None, subprocess.TimeoutExpired("mpremote", 20)):
                run, calls = fake_run("HYB26:MSC\n", exc)
                found = badge_serial.disk_mode(
                    ["mpremote"], "COM7", 0, run, lambda: [mount]
                )
                self.assertEqual(found, mount)
                self.assertEqual(calls[0][:4], ["mpremote", "connect", "COM7", "exec"])
                self.assertIn("powman.reset_into_msc()", calls[0][4])

    def test_disk_mode_reports_old_firmware_and_missing_mount(self):
        run, _ = fake_run("HYB26:NO_MSC\n")
        with self.assertRaises(badge_serial.SerialError):
            badge_serial.disk_mode(["mpremote"], "COM7", 0, run, lambda: [])
        run, _ = fake_run("HYB26:MSC\n")
        missing = Path(tempfile.gettempdir()) / "hyb26-no-such-badger"
        self.assertIsNone(
            badge_serial.disk_mode(["mpremote"], "COM7", 0, run, lambda: [missing])
        )

    def test_default_candidates_include_badger(self):
        self.assertIn("BADGER", {path.name for path in badge_serial.default_candidates()})

    def test_eject_posix_raises_only_if_still_mounted(self):
        with tempfile.TemporaryDirectory() as temp:
            mount = Path(temp)

            def failing(args, **kwargs):
                return subprocess.CompletedProcess(args, 1, stdout="", stderr="busy")

            with self.assertRaises(badge_serial.SerialError):
                badge_serial.eject_posix(mount, failing)
        badge_serial.eject_posix(
            Path(tempfile.gettempdir()) / "hyb26-no-such-badger", failing
        )

    def test_wait_until_gone(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertFalse(badge_serial.wait_until_gone(Path(temp), 0))
        self.assertTrue(
            badge_serial.wait_until_gone(Path(tempfile.gettempdir()) / "hyb26-no-such-badger", 0)
        )

    def test_eject_without_badger_fails_cleanly(self):
        missing = Path(tempfile.gettempdir()) / "hyb26-no-such-badger"
        self.assertEqual(badge_serial.main(["eject", "--mount", str(missing)]), 1)

    def test_device_snippets_compile(self):
        compile(badge_serial.INFO_CODE, "info", "exec")
        compile(badge_serial.DISK_MODE_CODE, "disk", "exec")


if __name__ == "__main__":
    unittest.main()
