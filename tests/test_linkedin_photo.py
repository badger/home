import contextlib
import io
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from tools.prepare_linkedin_photo import make_icon, prepare


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "badge" / "apps" / "linkedin_photo"


class PreparePhotoTests(unittest.TestCase):
    def test_crop_and_resize_preserves_square_artwork(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.jpg"
            output = Path(directory) / "photo.png"
            Image.new("RGB", (474, 248), "white").save(source)
            self.assertEqual(prepare(source, output, (152, 39, 322, 209)), (240, 240))
            with Image.open(output) as result:
                self.assertEqual(result.format, "PNG")
                self.assertEqual(result.mode, "RGB")

    def test_portrait_and_landscape_keep_aspect_ratio(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            output = Path(directory) / "photo.png"
            for size, expected in (((200, 400), (120, 240)), ((800, 400), (320, 160))):
                with self.subTest(size=size):
                    Image.new("RGB", size).save(source)
                    self.assertEqual(prepare(source, output), expected)

    def test_transparency_is_composited_on_black(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            output = Path(directory) / "photo.png"
            Image.new("RGBA", (320, 240), (255, 0, 0, 0)).save(source)
            prepare(source, output)
            with Image.open(output) as result:
                self.assertEqual(result.getpixel((0, 0)), (0, 0, 0))

    def test_invalid_crop_does_not_write_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            output = Path(directory) / "photo.png"
            Image.new("RGB", (10, 10)).save(source)
            with self.assertRaises(ValueError):
                prepare(source, output, (0, 0, 20, 20))
            self.assertFalse(output.exists())

    def test_icon_is_24_pixel_rgb_png(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "icon.png"
            make_icon(output)
            with Image.open(output) as icon:
                self.assertEqual(icon.size, (24, 24))
                self.assertEqual(icon.mode, "RGB")
                self.assertEqual(icon.format, "PNG")

    def test_bundled_assets_are_ready(self):
        for name in ("photo.png", "jonlego.png"):
            with self.subTest(name=name), Image.open(APP / "assets" / name) as photo:
                self.assertEqual(photo.size, (240, 240))
                self.assertEqual(photo.mode, "RGB")
        with Image.open(APP / "icon.png") as icon:
            self.assertEqual(icon.size, (24, 24))

    def test_default_destination_preserves_existing_photo(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory)
            source = app / "new.jpg"
            original = app / "assets" / "photo.png"
            original.parent.mkdir()
            original.write_bytes(b"existing photo")
            Image.new("RGB", (20, 20)).save(source)
            with patch("tools.prepare_linkedin_photo.APP_DIR", app):
                prepare(source)
            self.assertTrue((app / "assets" / "new.png").exists())
            self.assertEqual(original.read_bytes(), b"existing photo")

    def test_lego_portraits_including_slalom_director(self):
        edits = sorted((APP / "assets").glob("[0-9][0-9]-*.png"))
        self.assertEqual(len(edits), 10)
        paths = [APP / "assets" / "jonlego.png", *edits]
        self.assertEqual(len(paths), 11)
        for path in paths:
            with self.subTest(path=path.name), Image.open(path) as photo:
                self.assertEqual(photo.size, (240, 240))
                self.assertEqual(photo.mode, "RGB")
                self.assertEqual(photo.format, "PNG")
                photo.verify()

    def test_source_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "photo.png"
            Image.new("RGB", (20, 20)).save(source)
            with self.assertRaises(ValueError):
                prepare(source, source)


class PhotoRuntimeTests(unittest.TestCase):
    def load_app(self, files=None, error=None, size=(240, 240), list_error=None):
        self.buttons = set()
        self.badge = Mock()
        self.badge.ticks_delta = 0
        self.badge.pressed.side_effect = lambda button: button in self.buttons
        self.screen = Mock(width=320, height=240)
        self.screen.measure_text.side_effect = lambda text: (len(text) * 6, 12)
        self.picture = Mock(width=size[0], height=size[1])
        self.image = Mock(load=Mock(return_value=self.picture, side_effect=error))
        runner = Mock()
        self.console = io.StringIO()
        files = ["photo.png"] if files is None else files
        with patch("os.chdir"), patch("os.listdir", return_value=files, side_effect=list_error), \
                patch("sys.path", [str(APP), *sys.path]), contextlib.redirect_stdout(self.console):
            runpy.run_path(str(APP / "__init__.py"), init_globals={
                "badge": self.badge,
                "screen": self.screen,
                "image": self.image,
                "font": Mock(),
                "color": Mock(),
                "shape": Mock(),
                "rect": lambda *values: values,
                "run": runner,
                "BUTTON_SELECT": "select",
                "BUTTON_BACK": "back",
                "BUTTON_MENU": "menu",
                "BUTTON_LEFT": "left",
                "BUTTON_RIGHT": "right",
                "BUTTON_DOWN": "down",
                "HIRES": 1,
                "VSYNC": 2,
            })
        self.update = runner.call_args.args[0]
        self.namespace = self.update.__globals__

    def texts(self):
        return [call.args[0] for call in self.screen.text.call_args_list]

    def test_photo_is_centered_without_stretching_and_loaded_once(self):
        self.load_app()
        self.update()
        self.update()
        self.screen.blit.assert_called_with(self.picture, (40, 0, 240, 240))
        self.image.load.assert_called_once_with("assets/photo.png")
        self.assertEqual(self.texts(), [])

    def test_wide_photo_is_letterboxed(self):
        self.load_app(size=(320, 160))
        self.update()
        self.screen.blit.assert_called_with(self.picture, (0, 40, 320, 160))

    def test_missing_photo_has_actionable_screen_and_diagnostic(self):
        self.load_app(files=[])
        self.update()
        self.assertIn("No photos yet", self.texts())
        self.assertIn("Add PNG photos to assets/", self.texts())
        self.assertIn("add PNGs to assets", self.console.getvalue())
        self.image.load.assert_not_called()
        self.screen.blit.assert_not_called()

    def test_invalid_photo_is_reported(self):
        for error in (OSError("bad file"), ValueError("bad PNG"),
                      RuntimeError("decoder"), MemoryError("too large")):
            with self.subTest(error=type(error).__name__):
                self.load_app(error=error)
                self.update()
                self.assertIn("Cannot open photo", self.texts())
                self.assertIn(str(error), self.console.getvalue())
                self.screen.blit.assert_not_called()

    def test_menu_toggles_help_and_back_returns_to_photo(self):
        self.load_app()
        self.buttons.add("menu")
        self.update()
        self.assertTrue(self.namespace["show_help"])
        self.update()
        self.assertFalse(self.namespace["show_help"])
        self.update()
        self.buttons = {"back"}
        self.update()
        self.assertFalse(self.namespace["show_help"])

    def test_files_are_sorted_and_non_photos_ignored(self):
        self.load_app(files=["z.PNG", ".hidden.png", "__junk.png", "notes.txt", "a.png"])
        self.assertEqual(self.namespace["photo_files"], ["a.png", "z.PNG"])
        self.image.load.assert_called_once_with("assets/a.png")

    def test_advances_at_five_seconds_and_wraps(self):
        self.load_app(files=["a.png", "b.png"])
        self.badge.ticks_delta = 4999
        self.update()
        self.assertEqual(self.namespace["photo_index"], 0)
        self.badge.ticks_delta = 1
        self.update()
        self.assertEqual(self.namespace["photo_index"], 1)
        self.image.load.assert_called_with("assets/b.png")
        self.badge.ticks_delta = 5000
        self.update()
        self.assertEqual(self.namespace["photo_index"], 0)
        self.image.load.assert_called_with("assets/a.png")

    def test_select_pauses_and_resumes_with_full_interval(self):
        self.load_app(files=["a.png", "b.png"])
        self.buttons = {"select"}
        self.update()
        self.assertTrue(self.namespace["paused"])
        self.buttons = set()
        self.badge.ticks_delta = 10000
        self.update()
        self.assertEqual(self.namespace["photo_index"], 0)
        self.assertIn("Paused 1/2", self.texts())
        self.buttons = {"select"}
        self.update()
        self.assertEqual(self.namespace["photo_index"], 0)
        self.buttons = set()
        self.badge.ticks_delta = 4999
        self.update()
        self.assertEqual(self.namespace["photo_index"], 0)
        self.badge.ticks_delta = 1
        self.update()
        self.assertEqual(self.namespace["photo_index"], 1)

    def test_browse_wraps_while_paused_and_resets_timer(self):
        self.load_app(files=["a.png", "b.png", "c.png"])
        self.namespace["paused"] = True
        self.namespace["elapsed_ms"] = 4999
        self.buttons = {"left"}
        self.update()
        self.assertEqual(self.namespace["photo_index"], 2)
        self.assertEqual(self.namespace["elapsed_ms"], 0)
        self.buttons = {"right"}
        self.update()
        self.assertEqual(self.namespace["photo_index"], 0)
        self.assertTrue(self.namespace["paused"])

    def test_series_of_three_cycles_through_every_photo(self):
        self.load_app(files=["03.png", "01.png", "02.png"])
        self.badge.ticks_delta = 5000
        for expected in (1, 2, 0, 1):
            self.update()
            self.assertEqual(self.namespace["photo_index"], expected)
        self.assertEqual(
            [call.args[0] for call in self.image.load.call_args_list],
            ["assets/01.png", "assets/02.png", "assets/03.png",
             "assets/01.png", "assets/02.png"],
        )

    def test_help_suspends_timer_and_navigation(self):
        self.load_app(files=["a.png", "b.png"])
        self.buttons = {"menu"}
        self.update()
        self.buttons = {"right"}
        self.badge.ticks_delta = 9000
        self.update()
        self.assertEqual(self.namespace["photo_index"], 0)
        self.assertEqual(self.namespace["elapsed_ms"], 0)

    def test_single_photo_is_not_reloaded_by_timer(self):
        self.load_app()
        self.badge.ticks_delta = 10000
        self.update()
        self.image.load.assert_called_once()

    def test_corrupt_slide_reports_error_then_next_slide_loads(self):
        self.load_app(files=["a.png", "b.png"])
        self.image.load.side_effect = ValueError("bad PNG")
        with contextlib.redirect_stdout(self.console):
            self.namespace["load_photo"](1)
        self.update()
        self.assertIsNone(self.namespace["photo"])
        self.assertIn("Cannot open photo", self.texts())
        self.assertIn("assets/b.png: bad PNG", self.console.getvalue())
        self.image.load.side_effect = None
        self.badge.ticks_delta = 5000
        self.update()
        self.assertEqual(self.namespace["photo_index"], 0)
        self.assertIs(self.namespace["photo"], self.picture)

    def test_missing_assets_directory_is_actionable(self):
        self.load_app(list_error=OSError(2, "missing"))
        self.update()
        self.assertIn("No photos yet", self.texts())

    def test_other_directory_errors_are_not_silenced(self):
        with self.assertRaises(OSError):
            self.load_app(list_error=OSError(13, "permission denied"))

    def test_completed_remote_batch_replaces_paths_and_resets_timer(self):
        self.load_app(files=["a.png", "b.png"])
        paths = ["/state/linkedin_photo/a-00.png", "/state/linkedin_photo/a-01.png"]
        refresh = Mock(result=paths, busy=False, failed=False)
        self.namespace["refresh"] = refresh
        self.namespace["config_error"] = "old cache warning"
        self.namespace["elapsed_ms"] = 4999
        self.update()
        self.assertEqual(self.namespace["photo_files"], paths)
        self.assertEqual(self.namespace["photo_index"], 0)
        self.assertEqual(self.namespace["elapsed_ms"], 0)
        self.assertEqual(self.namespace["config_error"], "")
        self.image.load.assert_called_with(paths[0])
        self.assertIsNone(refresh.result)

    def test_down_requests_refresh_only_when_url_is_enabled(self):
        self.load_app()
        refresh = Mock(result=None, busy=False, failed=False)
        self.namespace["refresh"] = refresh
        self.buttons = {"down"}
        self.update()
        refresh.start.assert_not_called()
        self.namespace["batch_url"] = "https://photos.example/batch.json"
        self.update()
        refresh.start.assert_called_once_with("https://photos.example/batch.json")
        self.namespace["on_exit"]()
        refresh.close.assert_called_once()

    def test_refresh_failure_keeps_local_photo_and_reports_it(self):
        self.load_app()
        refresh = Mock(result=None, busy=False, failed=True)
        self.namespace["refresh"] = refresh
        self.update()
        self.assertEqual(self.namespace["photo_files"], ["photo.png"])
        self.assertIs(self.namespace["photo"], self.picture)
        self.assertIn("Refresh failed - MENU for details", self.texts())


if __name__ == "__main__":
    unittest.main()
