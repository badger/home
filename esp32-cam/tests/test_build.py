import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("camera_flash", PROJECT / "flash.py")
flash = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flash)


class FlashScriptTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.firmware = self.root / "firmware"
        self.firmware.mkdir()
        self.image = self.firmware / "esp32-cam.bin"
        self.image.write_bytes(b"unit-test-image")
        self.manifest = self.firmware / "manifest.json"
        self.manifest.write_text(json.dumps({
            "chip": "esp32", "flash_offset": "0x0",
            "sha256": {"esp32-cam.bin": hashlib.sha256(self.image.read_bytes()).hexdigest()},
        }))
        self.root_patch = patch.object(flash, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def invoke(self, *args):
        with patch.object(sys, "argv", ["flash.py", "--port", "test-camera-port", *args]):
            flash.main()

    def test_valid_image_flashes_merged_image_at_zero(self):
        with patch.object(flash.subprocess, "run") as run:
            self.invoke()
        command = run.call_args.args[0]
        self.assertEqual(command[-3:], ["write-flash", "0x0", str(self.image)])
        self.assertIn("test-camera-port", command)
        self.assertIn("115200", command)
        self.assertTrue(run.call_args.kwargs["check"])

    def test_changed_binary_never_touches_hardware(self):
        self.image.write_bytes(b"changed")
        with patch.object(flash.subprocess, "run") as run:
            with self.assertRaisesRegex(SystemExit, "checksum mismatch"):
                self.invoke()
        run.assert_not_called()

    def test_missing_package_never_touches_hardware(self):
        self.manifest.unlink()
        with patch.object(flash.subprocess, "run") as run:
            with self.assertRaisesRegex(SystemExit, "Run build.py"):
                self.invoke()
        run.assert_not_called()

    def test_existing_backup_is_not_overwritten(self):
        backup = self.root / "original.bin"
        backup.write_bytes(b"original")
        with patch.object(flash.subprocess, "run") as run:
            with self.assertRaisesRegex(SystemExit, "Backup already exists"):
                self.invoke("--backup", str(backup))
        self.assertEqual(backup.read_bytes(), b"original")
        run.assert_not_called()

    def test_backup_failure_prevents_flash(self):
        with patch.object(flash.subprocess, "run", side_effect=RuntimeError("backup failed")) as run:
            with self.assertRaisesRegex(RuntimeError, "backup failed"):
                self.invoke("--backup", str(self.root / "new.bin"))
        self.assertEqual(run.call_count, 1)
        self.assertIn("read-flash", run.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
