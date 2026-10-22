"""Host-side checks for countdown timing and text-only presentation changes."""

import types
import unittest
from unittest.mock import Mock, patch

from PIL import Image

import test_connections

APP = test_connections.APP


class CameraUITests(unittest.TestCase):
    def setUp(self):
        test_connections.ConnectionTests.setUp(self)
        self.app.countdown_since = None
        self.app.mona = types.SimpleNamespace(width=104, height=89)
        self.app.menu_mona = None
        self.app.wireless_icon = types.SimpleNamespace(width=80, height=80)
        self.app.store = Mock()
        self.app.store.photos = ["photo-a", "photo-b"]
        self.app.rotation = 3
        self.app.message = ""
        self.app.detail = ""
        self.app.mode = "LIVE"
        self.screen = self.namespace["screen"]
        self.screen.measure_text.side_effect = lambda text, size=1: (len(text) * 7 * size, 13 * size)
        self.namespace.update({"color": Mock(), "mat3": Mock(), "brush": Mock()})
        self.namespace["color"].rgb.side_effect = lambda *rgba: rgba
        self.namespace["color"].white = "white"
        self.namespace["color"].black = "black"

    def render(self):
        self.namespace["CameraApp"].draw(self.app)

    def texts(self):
        return [call.args[0] for call in self.screen.text.call_args_list]

    def test_select_starts_three_second_countdown_without_capture(self):
        self.namespace["badge"].pressed.side_effect = lambda key: key == self.namespace["BUTTON_SELECT"]
        request = Mock()
        request.return_value.step.return_value = None
        with patch.dict(self.namespace, {"Request": request}):
            self.app.update()
            self.assertEqual(self.app.mode, "COUNTDOWN")
            self.assertEqual(self.app.countdown_since, 100)
            self.assertIsNone(self.app.pending)
            self.app.store.begin.assert_not_called()
            request.assert_not_called()
            self.namespace["badge"].pressed.return_value = False
            self.namespace["badge"].pressed.side_effect = None
            with patch.object(self.namespace["time"], "ticks_ms", return_value=3099):
                self.app.update()
            request.assert_not_called()
            with patch.object(self.namespace["time"], "ticks_ms", return_value=3100):
                self.app.update()
            self.assertEqual(self.app.mode, "CAPTURING")
            self.app.store.begin.assert_called_once()
            request.assert_called_once()
            self.assertEqual(request.call_args.args[-1], 30000)
            request.return_value.step.assert_not_called()
            self.app.update()
            self.app.store.begin.assert_called_once()

    def test_countdown_ignores_capture_navigation_and_repeated_select(self):
        self.app.begin_countdown()
        self.app.show_gallery = Mock()
        self.app.rotate = Mock()
        self.namespace["badge"].pressed.side_effect = lambda key: key != self.namespace["BUTTON_BACK"]
        self.app.update()
        self.assertEqual(self.app.mode, "COUNTDOWN")
        self.app.show_gallery.assert_not_called()
        self.app.rotate.assert_not_called()
        self.app.store.begin.assert_not_called()

    def test_back_cancels_countdown_without_pending_photo(self):
        self.app.begin_countdown()
        self.namespace["badge"].pressed.side_effect = lambda key: key == self.namespace["BUTTON_BACK"]
        self.assertIs(self.app.update(), False)
        self.app.store.begin.assert_not_called()
        self.assertIsNone(self.app.pending)

    def test_countdown_numbers_and_mona_slide(self):
        self.app.begin_countdown()
        positions = []
        for now, expected in ((100, "3"), (240, "3"), (380, "3"), (1100, "2"), (2100, "1")):
            with patch.object(self.namespace["time"], "ticks_ms", return_value=now):
                self.render()
            self.assertEqual(self.texts()[-1], expected)
            positions.append(self.screen.rectangle.call_args.args[1])
        self.assertEqual(positions[0], 240)
        self.assertGreater(positions[0], positions[1])
        self.assertEqual(positions[2:], [120, 120, 120])

    def test_capturing_is_entirely_white(self):
        self.app.mode = "CAPTURING"
        self.render()
        self.assertEqual(self.screen.pen, (255, 255, 255))
        self.screen.clear.assert_called_once()
        self.screen.text.assert_not_called()
        self.screen.rectangle.assert_not_called()

    def test_countdown_uses_native_menu_mona_when_available(self):
        self.app.menu_mona = Mock()
        self.app.begin_countdown()
        self.render()
        self.app.menu_mona.look_at.assert_called_once_with(160, 70)
        self.app.menu_mona.prepare.assert_called_once_with(-1.2)
        self.app.menu_mona.render.assert_called_once()
        self.namespace["brush"].image.assert_not_called()

    def test_live_has_no_labels_or_help(self):
        self.render()
        self.screen.text.assert_not_called()
        self.screen.rectangle.assert_not_called()

    def test_live_still_shows_explicit_sd_warning(self):
        self.app.operation = "status"
        self.app.received(b'{"protocol":1,"camera":true,"sd":false,"camera_id":"test"}')
        self.render()
        self.assertEqual(self.texts(), ["SD missing - preview only"])

    def test_review_keeps_only_photo_counter(self):
        for mode in ("FROZEN", "GALLERY"):
            self.screen.reset_mock()
            self.app.mode = mode
            self.app.message = "Photo 2 / 2"
            self.render()
            self.assertEqual(self.texts(), ["Photo 2 / 2"])

    def test_saved_thumbnail_retains_frozen_review_and_storage(self):
        self.app.pending = "0011223344556677"
        self.app.operation = "thumbnail"
        self.app.set_frame = Mock()
        self.app.received(b"jpeg")
        self.assertEqual(self.app.mode, "FROZEN")
        self.assertEqual(self.app.gallery_index, 1)
        self.assertEqual(self.app.message, "Photo 2 / 2")
        self.assertEqual(self.app.detail, "")
        self.app.store.add.assert_called_once_with("0011223344556677", b"jpeg")
        self.app.store.finish.assert_called_once()
        self.assertIsNone(self.app.pending)

    def test_connecting_has_one_heading_and_wireless_icon(self):
        self.app.mode = "CONNECTING"
        self.app.message = "Connecting to camera..."
        self.app.detail = "Camera needs separate USB power"
        self.render()
        self.assertEqual(self.texts(), ["Connecting to", "your camera..."])
        self.namespace["brush"].image.assert_called_once()
        self.assertEqual(self.screen.pen, "white")

    def test_first_use_has_friendly_connect_prompt_not_an_error(self):
        self.app.mode = "WELCOME"
        self.app.message = "Connect new camera"
        self.app.detail = "Press Select to pair"
        self.render()
        self.assertEqual(self.texts(), ["Connect new camera", "Press Select to pair"])
        self.assertEqual(self.screen.pen, "white")
        self.namespace["brush"].image.assert_called_once()

    def test_pairing_keeps_camera_choice_and_replaces_code_with_proximity(self):
        self.app.mode = "PAIRING"
        self.app.provisioner = types.SimpleNamespace(state="CHOOSE", camera_name=lambda: "BadgeCam-test")
        self.render()
        self.assertEqual(self.texts().count("Pick your camera"), 1)
        self.assertIn("BadgeCam-test", self.texts())
        self.screen.reset_mock()
        self.app.provisioner.state = "NEARBY"
        self.render()
        self.assertEqual(self.texts(), ["Hold your badge", "against camera"])
        self.assertEqual(self.screen.pen, "white")

    def test_errors_are_not_repeated_in_title_and_body(self):
        self.app.mode = "ERROR"
        self.app.message = "Camera unavailable"
        self.app.detail = "Select to reconnect"
        self.render()
        self.assertEqual(self.texts(), ["Camera unavailable", "Select to reconnect"])

    def test_installed_assets_have_expected_dimensions_and_transparency(self):
        for path, size in ((APP / "icon.png", (24, 24)),
                           (APP / "assets/camera-wireless.png", (80, 80)),
                           (APP / "assets/mona.png", (104, 89))):
            with Image.open(path) as asset:
                self.assertEqual(asset.size, size)
                self.assertEqual(asset.mode, "RGBA")
                self.assertEqual(asset.getchannel("A").getextrema(), (0, 255))
        self.assertTrue((APP / "assets/LICENSE-MDI.txt").is_file())
