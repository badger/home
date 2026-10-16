"""Exercise the real app connection state machine with host-side hardware fakes."""

import json
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import Mock, patch

APP = Path(__file__).resolve().parents[2] / "badge/apps/camera"
sys.path.insert(0, str(APP))
import camera_core


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.namespace = {
            "badge": Mock(), "HIRES": 1, "VSYNC": 2, "screen": Mock(),
            "font": Mock(), "image": Mock(),
        }
        for index, key in enumerate(("BACK", "LEFT", "RIGHT", "UP", "DOWN", "SELECT")):
            self.namespace["BUTTON_" + key] = index
        with patch.dict(sys.modules, {"network": Mock()}):
            exec((APP / "__init__.py").read_text().split("\napp = CameraApp()")[0], self.namespace)
        self.app = self.namespace["CameraApp"].__new__(self.namespace["CameraApp"])
        self.app.config = {"pairing": "srp-v1", "ssid": "BadgeCam-test", "password": "secret",
                           "host": "192.168.4.1", "port": 80, "camera_id": "test"}
        self.app.config_path = "/test"
        self.app.provisioner = None
        self.app.request = None
        self.app.operation = None
        self.app.camera_verified = False
        self.app.cached_wifi = False
        self.app.resume_pending = False
        self.app.pending = None
        self.app.frame = None
        self.app.draw = Mock()
        self.app.wlan = Mock()
        self.app.wlan.isconnected.return_value = False
        self.namespace["badge"].pressed.return_value = False
        self.provision = Mock()
        for target, kwargs in (
            ("ticks_ms", {"return_value": 100}),
            ("ticks_diff", {"side_effect": lambda a, b: a - b}),
        ):
            p = patch.object(time, target, create=True, **kwargs)
            p.start()
            self.addCleanup(p.stop)
        p = patch.dict(sys.modules, {"camera_ble": types.SimpleNamespace(Provisioner=self.provision)})
        p.start()
        self.addCleanup(p.stop)

    def new_app(self, config=None, pending=None):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        config_path = str(Path(directory.name) / "config.json")
        if config is not None:
            Path(config_path).write_text(json.dumps(config))
        store = Mock()
        store.rotation.return_value = 0
        store.pending.return_value = pending
        with patch.dict(self.namespace, {"PhotoStore": Mock(return_value=store)}):
            with patch.dict(sys.modules, {"mona": types.SimpleNamespace(shared=lambda: None)}):
                app = self.namespace["CameraApp"](config_path, str(Path(directory.name) / "cache"))
        app.draw = Mock()
        return app

    def test_first_use_waits_for_select_without_touching_bluetooth(self):
        for config in (None, {"pairing": "srp-v1"}):
            with self.subTest(config=config):
                app = self.new_app(config)
                self.assertEqual(app.mode, "WELCOME")
                self.assertEqual(app.message, "Connect new camera")
                self.assertEqual(app.detail, "Press Select to pair")
                self.assertIsNone(app.provisioner)
                app.update()
                self.provision.assert_not_called()
                app.wlan.connect.assert_not_called()

    def test_select_from_welcome_starts_pairing(self):
        app = self.new_app()
        self.namespace["badge"].pressed.side_effect = lambda key: key == self.namespace["BUTTON_SELECT"]
        app.update()
        self.provision.assert_called_once()
        self.assertEqual(app.mode, "PAIRING")

    def test_leaving_welcome_does_not_disconnect_existing_wifi(self):
        app = self.new_app()
        app.wlan.reset_mock()
        app.close()
        app.wlan.disconnect.assert_not_called()
        app.wlan.active.assert_not_called()

    def test_actual_bluetooth_conflict_after_select_is_not_hidden(self):
        app = self.new_app()
        self.provision.side_effect = camera_core.CameraError("Bluetooth already in use")
        self.namespace["badge"].pressed.side_effect = lambda key: key == self.namespace["BUTTON_SELECT"]
        with patch.object(sys, "print_exception", create=True):
            app.update()
        self.assertEqual(app.mode, "ERROR")
        self.assertEqual(app.message, "Bluetooth already in use")

    def test_established_pairing_still_reconnects_automatically(self):
        app = self.new_app(dict(self.app.config, pair_key="ab" * 32))
        self.assertEqual(app.mode, "CONNECTING")
        self.assertTrue(app.cached_wifi)
        app.wlan.connect.assert_called_once_with("BadgeCam-test", "secret")
        self.provision.assert_not_called()

    def test_interrupted_pairing_still_recovers_automatically(self):
        app = self.new_app({"pairing": "srp-v1", "pending_pair_key": "ab" * 32})
        self.assertEqual(app.mode, "PAIRING")
        self.provision.assert_called_once()

    def test_legacy_wifi_config_does_not_show_first_use_prompt(self):
        app = self.new_app({"ssid": "legacy", "password": "secret"})
        self.assertEqual(app.mode, "CONNECTING")
        self.assertFalse(app.cached_wifi)
        app.wlan.connect.assert_called_once_with("legacy", "secret")
        self.provision.assert_not_called()

    def test_pending_photo_takes_priority_over_welcome(self):
        app = self.new_app(pending="0011223344556677")
        self.assertEqual(app.mode, "ERROR")
        self.assertEqual(app.message, "Unfinished photo")
        self.provision.assert_not_called()

    def test_start_uses_cached_wifi_without_ble(self):
        self.app.connect()
        self.provision.assert_not_called()
        self.assertTrue(self.app.cached_wifi)
        self.app.wlan.connect.assert_called_once_with("BadgeCam-test", "secret")

    def test_missing_credentials_use_ble(self):
        self.app.config.pop("password")
        self.app.connect()
        self.provision.assert_called_once()
        self.assertEqual(self.app.mode, "PAIRING")
        self.app.wlan.connect.assert_not_called()

    def test_cached_timeout_refreshes_once(self):
        self.app.connect()
        with patch.object(time, "ticks_ms", return_value=4101):
            self.app.update()
        self.provision.assert_called_once()
        self.assertFalse(self.app.cached_wifi)
        self.assertEqual(self.app.mode, "PAIRING")
        self.assertFalse(self.app.recover_connection("another error"))

    def test_immediate_wifi_failure_refreshes_credentials(self):
        self.app.wlan.connect.side_effect = OSError("association failed")
        self.app.connect()
        self.provision.assert_called_once()
        self.assertEqual(self.app.mode, "PAIRING")

    def test_recovery_failure_is_displayed(self):
        self.app.cached_wifi = True
        self.provision.side_effect = camera_core.CameraError("Bluetooth already in use")
        self.assertTrue(self.app.recover_connection("stale password"))
        self.assertEqual(self.app.mode, "ERROR")
        self.assertIn("Bluetooth already in use", self.app.detail)
        self.assertFalse(self.app.cached_wifi)

    def test_quick_second_select_keeps_full_capture_timeout_and_id(self):
        self.app.resume_pending = True
        self.app.pending = "0011223344556677"
        self.app.rotation = 3
        self.app.store = Mock()
        request = Mock()
        with patch.dict(self.namespace, {"Request": request}):
            self.app.take_photo()
        self.assertFalse(self.app.resume_pending)
        self.assertEqual(request.call_args.args[-1], 30000)
        self.assertIn("0011223344556677", request.call_args.args[2])
        self.app.store.begin.assert_not_called()

    def test_pending_photo_reconnects_before_retry(self):
        self.app.camera_verified = True
        self.app.wlan.isconnected.return_value = True
        self.app.pending = "0011223344556677"
        self.app.resume_preview()
        self.assertTrue(self.app.cached_wifi)
        self.app.take_photo = Mock()
        self.app.operation = "status"
        self.app.received(b'{"protocol":1,"camera":true,"sd":true,"camera_id":"test"}')
        self.app.take_photo.assert_called_once()
        self.assertEqual(self.app.pending, "0011223344556677")

    def test_review_resumes_without_reconnecting(self):
        for mode in ("FROZEN", "GALLERY"):
            with self.subTest(mode=mode):
                self.app.mode = mode
                self.app.camera_verified = True
                self.app.wlan.isconnected.return_value = True
                self.namespace["badge"].pressed.side_effect = lambda key: key == self.namespace["BUTTON_SELECT"]
                with patch.dict(self.namespace, {"Request": Mock()}):
                    self.app.update()
                self.assertEqual(self.app.mode, "LIVE")
                self.assertEqual(self.app.operation, "preview")
                self.assertTrue(self.app.resume_pending)
                self.app.wlan.connect.assert_not_called()
                self.app.wlan.disconnect.assert_not_called()
                self.provision.assert_not_called()
                self.app.request = None

    def test_first_resumed_frame_clears_recovery_flag(self):
        self.app.resume_pending = True
        self.app.operation = "preview"
        self.app.set_frame = Mock()
        self.app.received(b"jpeg")
        self.assertFalse(self.app.resume_pending)

    def test_lost_connection_uses_cached_attempt(self):
        self.app.camera_verified = True
        self.app.resume_preview()
        self.assertTrue(self.app.cached_wifi)
        self.app.wlan.connect.assert_called_once()

    def test_resumed_request_failure_refreshes_credentials(self):
        self.app.mode = "LIVE"
        self.app.resume_pending = True
        self.app.request = Mock()
        self.app.request.step.side_effect = OSError("connection lost")
        with patch.object(sys, "print_exception", create=True):
            self.app.update()
        self.provision.assert_called_once()
        self.assertFalse(self.app.resume_pending)

    def test_status_confirms_identity_before_reuse(self):
        self.app.operation = "status"
        self.app.cached_wifi = True
        self.app.received(b'{"protocol":1,"camera":true,"sd":true,"camera_id":"test"}')
        self.assertTrue(self.app.camera_verified)
        self.assertFalse(self.app.cached_wifi)

    def test_wrong_camera_never_becomes_verified(self):
        self.app.operation = "status"
        with self.assertRaisesRegex(camera_core.CameraError, "Wrong Wi-Fi"):
            self.app.received(b'{"protocol":1,"camera":true,"camera_id":"other"}')
        self.assertFalse(self.app.camera_verified)
