"""Exercise the real app connection state machine with host-side hardware fakes."""

from pathlib import Path
import sys
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
