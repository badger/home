import contextlib
import builtins
import datetime
import io
import json
import struct
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch, MagicMock
import os

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
import config
import feed

TEST_CHANNEL_ID = "UC" + "0" * 22

def entry(number, title="GitHub Copilot agents", description="Python debugging testing",
          channel=TEST_CHANNEL_ID, views="1234"):
    statistics = "" if views is None else '<media:statistics views="%s"/>' % views
    return (
        "<entry><yt:videoId>video%06d</yt:videoId><yt:channelId>%s</yt:channelId>"
        "<title>%s</title><published>2026-10-%02dT07:00:00+00:00</published>"
        "<media:description>%s</media:description>%s</entry>"
    ) % (number, channel, title, number, description, statistics)


def document(*entries):
    return '<feed xmlns:yt="youtube" xmlns:media="media">' + "".join(entries) + "</feed>"


class FeedTests(unittest.TestCase):
    def test_clock_payload_validation(self):
        payload = {"year": 2026, "month": 10, "day": 27, "hour": 21,
                   "minute": 12, "seconds": 32, "timeZone": "UTC"}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "clock.json"
            path.write_text(json.dumps(payload))
            self.assertEqual(feed.read_clock(path), (2026, 10, 27, 1, 21, 12, 32, 0))
            for key, invalid in [("year", 2000), ("month", 13), ("hour", 24),
                                 ("minute", 60), ("seconds", -1), ("timeZone", "Europe/Amsterdam")]:
                with self.subTest(key=key):
                    path.write_text(json.dumps(dict(payload, **{key: invalid})))
                    with self.assertRaises(ValueError):
                        feed.read_clock(path)

    def test_relative_date_thresholds(self):
        today = datetime.date(2026, 10, 27)
        cases = [
            (0, "Today"), (1, "Yesterday"), (2, "2 days ago"), (6, "6 days ago"),
            (7, "A week ago"), (13, "A week ago"), (14, "2 weeks ago"),
            (30, "4 weeks ago"), (31, "More than a month ago"),
            (59, "More than a month ago"), (60, "2 months ago"),
            (364, "12 months ago"), (365, "A year ago"), (729, "A year ago"),
            (730, "2 years ago"),
        ]
        for days, expected in cases:
            with self.subTest(days=days):
                published = str(today - datetime.timedelta(days=days)) + "T07:00:00+00:00"
                self.assertEqual(feed.relative_date(published, (2026, 10, 27)), expected)

    def test_relative_dates_cross_leap_days_and_year_boundaries(self):
        self.assertEqual(feed.relative_date("2024-02-28", (2024, 3, 1)), "2 days ago")
        self.assertEqual(feed.relative_date("2025-02-28", (2025, 3, 1)), "Yesterday")
        self.assertEqual(feed.relative_date("2025-12-31", (2026, 1, 1)), "Yesterday")
        self.assertEqual(feed.relative_date("2026-10-28", (2026, 10, 27)), "Check badge clock")
        self.assertEqual(feed.relative_date("2026-10-23", (2000, 1, 1)), "Check badge clock")

    def test_invalid_calendar_dates_are_rejected(self):
        for date in ("2026-02-29", "2026-13-01", "2026-00-01", "2026-10-32"):
            xml = document(entry(1)).replace("2026-10-01", date)
            with self.subTest(date=date), self.assertRaises(ValueError):
                feed.parse_feed(xml, TEST_CHANNEL_ID)

    def test_newest_six_sorted_and_deduplicated(self):
        xml = document(*(entry(i) for i in [3, 1, 8, 2, 5, 6, 4, 7, 8]))
        videos = feed.parse_feed(xml, TEST_CHANNEL_ID)
        self.assertEqual([v["id"] for v in videos],
                         ["video000008", "video000007", "video000006",
                          "video000005", "video000004", "video000003"])

    def test_fewer_than_six_and_empty(self):
        self.assertEqual(len(feed.parse_feed(document(entry(1)), TEST_CHANNEL_ID)), 1)
        self.assertEqual(feed.parse_feed(document(), TEST_CHANNEL_ID), [])

    def test_entities_unicode_and_cdata(self):
        xml = document(entry(1, "Code &amp; caf&#233; &#x1F680;",
                             "<![CDATA[Python & testing]]>"))
        video = feed.parse_feed(xml, TEST_CHANNEL_ID)[0]
        self.assertEqual(video["title"], "Code & caf\u00e9 \U0001f680")
        self.assertEqual(video["views"], 1234)
        self.assertEqual(feed.unescape("&unknown; &amp;lt;"), "&unknown; &lt;")

    def test_views_present_missing_and_zero(self):
        for value, expected in [("1234567", 1234567), ("0", 0), (None, None)]:
            with self.subTest(value=value):
                video = feed.parse_feed(document(entry(1, views=value)), TEST_CHANNEL_ID)[0]
                self.assertEqual(video["views"], expected)
                self.assertNotIn("keywords", video)

    def test_invalid_views_are_rejected(self):
        for value in ("-1", "unknown", "1.5", ""):
            with self.subTest(value=value), self.assertRaises(ValueError):
                feed.parse_feed(document(entry(1, views=value)), TEST_CHANNEL_ID)

    def test_views_accept_extra_attributes_and_single_quotes(self):
        self.assertEqual(feed.view_count("<media:statistics other='x' views='987'/>"), 987)
        self.assertIsNone(feed.view_count("<media:statistics other='x'/>"))

    def test_video_url_points_to_video_and_rejects_paths(self):
        self.assertEqual(feed.video_url("video000001"), "https://youtu.be/video000001")
        with self.assertRaises(ValueError):
            feed.video_url("../badpath")

    def test_malformed_wrong_channel_invalid_id_and_oversize(self):
        bad = [
            "<html>Not a feed</html>",
            document(entry(1))[:-7],
            document(entry(1)).replace("</entry>", ""),
            document(entry(1, channel="UCwrong")),
            document(entry(1)).replace("video000001", "../badpath"),
            document(entry(1)).replace("</title>", ""),
            document() + " " * feed.MAX_FEED_BYTES,
        ]
        for xml in bad:
            with self.subTest(xml=xml[:70]), self.assertRaises(ValueError):
                feed.parse_feed(xml, TEST_CHANNEL_ID)

    def test_thumbnail_url_is_fixed_size_png_and_rejects_paths(self):
        url = feed.thumbnail_url("video000001")
        self.assertIn("output=png", url)
        self.assertIn("w=192&h=108", url)
        with self.assertRaises(ValueError):
            feed.thumbnail_url("../../escape")

    def test_missing_closing_tag_before_next_entry_is_rejected(self):
        xml = document(entry(1), entry(2)).replace("</entry>", "", 1)
        with self.assertRaisesRegex(ValueError, "Incomplete video entry"):
            feed.parse_feed(xml, TEST_CHANNEL_ID)


class Screen:
    width = 320
    height = 240

    def __init__(self):
        self.texts = []
        self.blits = []
        self.rectangles = []
        self.text_calls = []

    def measure_text(self, text, font_size=16):
        return len(text) * font_size * 0.55, font_size

    def text(self, text, *args, **kwargs):
        self.texts.append(text)
        self.text_calls.append((text, args))

    def clear(self):
        self.texts.clear()

    def rectangle(self, *args):
        self.rectangles.append((self.pen, args))

    def blit(self, *args):
        self.blits.append(args)


class AppIconTests(unittest.TestCase):
    def test_app_icon_is_24_by_24_rgba_png(self):
        data = (APP / "icon.png").read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(data[12:16], b"IHDR")
        self.assertEqual(struct.unpack(">IIBB", data[16:26]), (24, 24, 8, 6))


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        search_path = patch.object(sys, "path", list(sys.path))
        search_path.start()
        self.addCleanup(search_path.stop)
        settings = patch.multiple(config, CHANNEL_ID=TEST_CHANNEL_ID, CHANNEL_HANDLE="@example")
        settings.start()
        self.addCleanup(settings.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "state").mkdir()
        self.screen = Screen()
        self.keys = set()
        self.badge = types.SimpleNamespace(
            ticks=0, mode=lambda mode: None, pressed=lambda button: button in self.keys
        )
        self.requests = []
        self.no_wifi = []
        self.qr_urls = []
        self.rtc = types.SimpleNamespace(datetime=MagicMock())
        self.reset = MagicMock()
        self.chdir = MagicMock()

        def mapped(path):
            return self.root / str(path).lstrip("/")

        self.mapped = mapped
        fake_os = types.SimpleNamespace(
            chdir=self.chdir,
            stat=lambda path: os.stat(mapped(path)),
            mkdir=lambda path: os.mkdir(mapped(path)),
            listdir=lambda path: os.listdir(mapped(path)),
            remove=lambda path: os.remove(mapped(path)),
            # MicroPython's filesystem replaces existing destinations.
            rename=lambda source, dest: os.replace(mapped(source), mapped(dest)),
        )

        def start_request(url, headers):
            class Download:
                error = None
                ready = False

                def __bool__(self):
                    return self.ready

                def to(self, path):
                    self.path = path
                    self.requests.append(self)
                    return self

                def succeed(self, payload):
                    mapped(self.path).write_bytes(payload)
                    self.ready = True

            download = Download()
            download.requests = self.requests
            download.url = url
            return download

        fake_fetch = types.SimpleNamespace(url=start_request)
        fake_missing = types.SimpleNamespace(
            mona_sans=lambda: object(), missing=lambda *args: self.no_wifi,
            show=lambda *args: self.screen.text("Configure Wi-Fi"),
        )
        modules = patch.dict(sys.modules, {
            "os": fake_os, "fetch": fake_fetch, "missing_details": fake_missing,
            "machine": types.SimpleNamespace(RTC=lambda: self.rtc),
        })
        modules.start()
        self.addCleanup(modules.stop)
        reader = patch.object(feed, "read_feed",
                              lambda path, channel: feed.parse_feed(
                                  mapped(path).read_text(encoding="utf-8"), channel))
        reader.start()
        self.addCleanup(reader.stop)
        read_clock = feed.read_clock
        clock_reader = patch.object(feed, "read_clock", lambda path: read_clock(mapped(path)))
        clock_reader.start()
        self.addCleanup(clock_reader.stop)

    def boot(self):
        self.app = {
            "badge": self.badge, "screen": self.screen, "HIRES": 1, "VSYNC": 2,
            "image": types.SimpleNamespace(
                X2=2, CENTER=0, NEAREST=0, BILINEAR=1, QR_LOW=0, load=self.load_image,
                qr=self.make_qr,
            ),
            "color": types.SimpleNamespace(rgb=lambda *args: args),
            "rect": lambda *args: args, "LEFT": 0, "TOP": 0,
            "BUTTON_LEFT": "left", "BUTTON_RIGHT": "right",
            "BUTTON_SELECT": "select", "BUTTON_UP": "up",
            "BUTTON_DOWN": "down", "reset": self.reset,
            "run": lambda callback: None,
        }
        with contextlib.redirect_stdout(io.StringIO()):
            exec(compile((APP / "__init__.py").read_text(), str(APP / "__init__.py"), "exec"),
                 self.app)

    def test_channel_handle_accepts_optional_at_prefix(self):
        for value, expected in [
            ("example", "@example"),
            ("@example", "@example"),
            ("  example  ", "@example"),
            ("  @example  ", "@example"),
            ("", ""),
            ("   ", ""),
        ]:
            with self.subTest(handle=value), patch.object(config, "CHANNEL_HANDLE", value):
                self.boot()
                self.assertEqual(self.app["CHANNEL_HANDLE"], expected)
                self.assertEqual(config.CHANNEL_HANDLE, value)

    def make_qr(self, url, correction, scale):
        self.qr_urls.append(url)
        return types.SimpleNamespace(width=50, height=50, url=url)

    def load_image(self, path):
        if self.mapped(path).read_bytes() != b"PNG":
            raise ValueError("Invalid PNG")
        return types.SimpleNamespace(width=192, height=108)

    def tick(self, milliseconds=0, key=None):
        self.badge.ticks += milliseconds
        self.keys.clear()
        if key:
            self.keys.add(key)
        with contextlib.redirect_stdout(io.StringIO()):
            self.app["update"]()
        self.keys.clear()

    def seed_cache(self):
        cache = self.root / "state" / "youtube"
        cache.mkdir()
        (cache / "feed.xml").write_text(document(*(entry(i) for i in range(1, 9))))
        (cache / "video000008.png").write_bytes(b"PNG")

    def test_app_directory_is_bootstrapped_before_local_imports(self):
        original_import = builtins.__import__
        imported = []

        def checked_import(name, *args, **kwargs):
            if name in ("config", "feed"):
                self.chdir.assert_called_once_with("/system/apps/youtube")
                self.assertEqual(sys.path[0], "/system/apps/youtube")
                imported.append(name)
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=checked_import):
            self.boot()
        self.assertEqual(imported, ["config", "feed"])
        self.assertEqual(self.app["APP_DIR"], "/system/apps/youtube")

    def test_malformed_refresh_preserves_cached_videos_and_thumbnails(self):
        self.seed_cache()
        cache = self.mapped("/state/youtube/feed.xml")
        thumbnail = self.mapped("/state/youtube/video000008.png")
        original_cache = cache.read_bytes()
        original_thumbnail = thumbnail.read_bytes()
        self.boot()
        original_videos = list(self.app["videos"])
        self.tick()
        malformed = document(entry(1), entry(2)).replace("</entry>", "", 1)
        self.requests[-1].succeed(malformed.encode())
        self.tick()
        self.assertEqual(self.app["videos"], original_videos)
        self.assertEqual(cache.read_bytes(), original_cache)
        self.assertEqual(thumbnail.read_bytes(), original_thumbnail)
        self.assertIn("Incomplete video entry", self.app["errors"]["feed"])
        self.assertFalse(self.mapped("/state/youtube/feed.xml.tmp").exists())

    def test_first_boot_fetch_and_thumbnail(self):
        self.boot()
        self.tick()
        self.assertIn("youtube.com/feeds", self.requests[0].url)
        self.requests[0].succeed(document(*(entry(i) for i in range(1, 9))).encode())
        self.tick()
        self.assertEqual(len(self.app["videos"]), 6)
        self.tick()
        self.assertIn("video000008", self.requests[1].url)
        self.requests[1].succeed(b"PNG")
        self.tick()
        self.tick()
        self.assertIsNotNone(self.app["photo"])
        self.assertTrue(self.screen.blits)
        self.assertTrue(self.mapped("/state/youtube/feed.xml").exists())

    def test_offline_cache_buttons_timer_and_pause(self):
        self.seed_cache()
        self.no_wifi.append("WIFI_SSID")
        self.boot()
        self.tick()
        self.assertIsNotNone(self.app["photo"])
        self.assertEqual(len(self.requests), 0)
        self.tick(config.SLIDE_MS)
        self.assertEqual(self.app["index"], 1)
        self.tick(key="left")
        self.assertEqual(self.app["index"], 0)
        self.tick(key="left")
        self.assertEqual(self.app["index"], 5)
        self.tick(key="right")
        self.assertEqual(self.app["index"], 0)
        self.tick(key="select")
        self.tick(config.SLIDE_MS * 2)
        self.assertEqual(self.app["index"], 0)
        self.tick(key="select")
        self.tick(config.SLIDE_MS)
        self.assertEqual(self.app["index"], 1)
        self.assertIn("Cached | Wi-Fi not configured", self.screen.texts)

    def test_bad_refresh_preserves_cache_and_retries(self):
        self.seed_cache()
        self.boot()
        original = self.mapped("/state/youtube/feed.xml").read_bytes()
        self.tick()
        self.requests[0].succeed(b"<html>Network login</html>")
        self.tick()
        self.assertEqual(len(self.app["videos"]), 6)
        self.assertEqual(self.mapped("/state/youtube/feed.xml").read_bytes(), original)
        self.assertIn("feed", self.app["errors"])
        self.assertEqual(self.app["next_feed"], config.RETRY_MS)
        self.tick(key="up")
        self.assertIn("youtube.com/feeds", self.requests[-1].url)

    def test_successful_refresh_keeps_selection_and_prunes_old_images(self):
        self.seed_cache()
        old_image = self.mapped("/state/youtube/video000001.png")
        old_image.write_bytes(b"PNG")
        self.boot()
        self.tick(key="right")
        current = self.app["videos"][self.app["index"]]["id"]
        self.requests[0].succeed(document(*(entry(i) for i in range(2, 10))).encode())
        self.tick()
        self.assertEqual(self.app["videos"][self.app["index"]]["id"], current)
        self.assertFalse(old_image.exists())
        self.assertEqual(self.app["next_feed"], config.REFRESH_MS)

    def test_bad_thumbnail_is_not_cached(self):
        self.boot()
        self.tick()
        self.requests[0].succeed(document(entry(1)).encode())
        self.tick()
        self.tick()
        self.requests[1].succeed(b"Not an image")
        self.tick()
        self.assertFalse(self.mapped("/state/youtube/video000001.png").exists())
        self.assertIn("video000001", self.app["thumb_retry"])
        self.tick()
        self.assertIn("Thumbnail unavailable", self.screen.texts)

    def test_network_failure_is_visible_and_retry_is_delayed(self):
        self.boot()
        self.tick()
        self.requests[0].error = "HTTP 503"
        self.tick()
        self.tick()
        self.assertTrue(any("Feed: HTTP 503" in text for text in self.screen.texts))
        self.assertEqual(len(self.requests), 1)
        self.tick(config.RETRY_MS)
        self.assertEqual(len(self.requests), 2)

    def test_feed_404_tries_uploads_playlist_and_recovers(self):
        self.seed_cache()
        self.boot()
        self.tick()
        self.assertEqual(self.requests[-1].url,
                         "https://www.youtube.com/feeds/videos.xml?channel_id=" + TEST_CHANNEL_ID)
        self.requests[-1].error = "HTTP error 404"
        self.tick()
        self.assertTrue(self.app["videos"])
        self.tick()
        self.assertEqual(self.requests[-1].url,
                         "https://www.youtube.com/feeds/videos.xml?playlist_id=UU" + TEST_CHANNEL_ID[2:])
        self.requests[-1].succeed(document(entry(8)).encode())
        self.tick()
        self.assertEqual(self.app["videos"][0]["id"], "video000008")
        self.assertNotIn("feed", self.app["errors"])
        self.assertNotIn("feed", self.app["retry_delays"])

    def test_both_feed_endpoints_404_back_off_without_losing_cache(self):
        self.seed_cache()
        self.boot()
        cached = self.mapped("/state/youtube/feed.xml").read_bytes()
        previous = list(self.app["videos"])
        self.tick()
        for delay in (config.RETRY_MS, config.RETRY_MS * 2):
            self.requests[-1].error = "HTTP error 404"
            self.tick()
            self.tick()
            self.assertIn("playlist_id=UU", self.requests[-1].url)
            self.requests[-1].error = "HTTP error 404"
            self.tick()
            self.assertEqual(self.app["retry_delays"]["feed"], delay)
            self.assertEqual(self.app["next_feed"], self.badge.ticks + delay)
            self.assertEqual(self.app["videos"], previous)
            self.assertEqual(self.mapped("/state/youtube/feed.xml").read_bytes(), cached)
            self.assertFalse(self.app["uploads_fallback"])
            self.tick(delay)
            self.assertIn("channel_id=", self.requests[-1].url)

    def test_feed_404_without_error_word_also_uses_fallback(self):
        self.boot()
        self.tick()
        self.requests[-1].error = "HTTP 404"
        self.tick()
        self.tick()
        self.assertIn("playlist_id=UU", self.requests[-1].url)

    def test_thumbnail_success_does_not_hide_feed_failure(self):
        self.seed_cache()
        self.boot()
        self.tick(key="right")
        self.requests[0].error = "HTTP 503"
        self.tick()
        self.tick()
        self.requests[1].succeed(b"PNG")
        self.tick()
        self.tick()
        self.assertTrue(any("Feed: HTTP 503" in text for text in self.screen.texts))

    def test_missing_wifi_and_empty_feed_states(self):
        self.no_wifi.append("WIFI_SSID")
        self.boot()
        self.tick()
        self.assertIn("Configure Wi-Fi", self.screen.texts)
        self.no_wifi.clear()
        self.tick(key="up")
        self.requests[0].succeed(document().encode())
        self.tick()
        self.tick()
        self.assertIn("No public uploads", self.screen.texts)

    def test_title_text_fits(self):
        self.boot()
        for title in ["word " * 80, "x" * 1000, "Short title"]:
            lines = self.app["title_lines"](title)
            self.assertLessEqual(len(lines), 2)
            for line in lines:
                self.assertLessEqual(self.screen.measure_text(line, 18)[0], 304)
        self.assertLessEqual(self.screen.measure_text(self.app["fit"]("x" * 50, 100, 14), 14)[0],
                             100)

    def test_qr_views_and_no_top_right_counter(self):
        self.seed_cache()
        self.no_wifi.append("WIFI_SSID")
        self.boot()
        self.tick()
        self.assertEqual(self.qr_urls, ["https://youtu.be/video000008"])
        self.assertIn("1,234 views", self.screen.texts)
        self.assertNotIn("1 / 6", self.screen.texts)
        self.assertNotIn("TOPICS", self.screen.texts)
        self.assertIn(((255, 255, 255), (240, 59, 72, 72)), self.screen.rectangles)
        self.assertEqual(self.screen.blits[-1][2], (240, 59, 72, 72))
        self.assertEqual(self.screen.blits[-2][2], (8, 32, 224, 126))
        self.assertGreaterEqual((224 * 126) / (192 * 108), 1.36)
        self.assertIn(("GitHub Copilot agents", (8, 178, 18)), self.screen.text_calls)
        self.assertEqual(self.screen.blits[-1][-1], 0)  # Nearest-neighbor QR rendering.
        self.tick()
        self.assertEqual(len(self.qr_urls), 1)
        self.tick(key="right")
        self.assertEqual(self.qr_urls[-1], "https://youtu.be/video000007")

    def test_view_count_labels(self):
        self.boot()
        for views, expected in [(None, "Views unavailable"), (0, "0 views"),
                                (1, "1 view"), (1234567, "1,234,567 views")]:
            self.assertEqual(self.app["views_label"](views), expected)

    def test_relative_date_is_rendered_and_updates_without_refresh(self):
        self.seed_cache()
        self.no_wifi.append("WIFI_SSID")
        self.boot()
        with patch.object(self.app["time"], "localtime", return_value=(2026, 10, 8)):
            self.tick()
            self.assertIn("Today", self.screen.texts)
            self.assertNotIn("2026-10-08", self.screen.texts)
        with patch.object(self.app["time"], "localtime", return_value=(2026, 10, 15)):
            self.tick()
            self.assertIn("A week ago", self.screen.texts)

    def test_unset_clock_syncs_without_blocking_slides(self):
        self.seed_cache()
        self.boot()
        with patch.object(self.app["time"], "localtime", return_value=(2000, 1, 1)):
            self.tick()
            self.requests[-1].succeed(document(entry(8)).encode())
            self.tick()
            self.tick()
            self.assertIn("timeapi.io", self.requests[-1].url)
            self.assertIn("Syncing date...", self.screen.texts)
            self.requests[-1].succeed(json.dumps({
                "year": 2026, "month": 10, "day": 15, "hour": 12,
                "minute": 0, "seconds": 1, "timeZone": "UTC",
            }).encode())
            self.tick()
        self.rtc.datetime.assert_called_once_with((2026, 10, 15, 3, 12, 0, 1, 0))
        with patch.object(self.app["time"], "localtime", return_value=(2026, 10, 15)):
            self.tick()
            self.assertIn("A week ago", self.screen.texts)
            self.assertFalse(self.app["clock_needs_sync"]())
        self.assertNotIn("clock", self.app["errors"])

    def test_clock_timeout_retries_with_backoff(self):
        self.seed_cache()
        self.boot()
        with patch.object(self.app["time"], "localtime", return_value=(2000, 1, 1)):
            self.app["next_feed"] = 10000000
            self.tick()
            self.requests[-1].error = "Read timeout"
            self.tick()
            self.assertEqual(self.app["next_clock"], config.RETRY_MS)
            self.tick(config.RETRY_MS)
            self.requests[-1].error = "Read timeout"
            self.tick()
            self.assertEqual(self.app["next_clock"], 3 * config.RETRY_MS)
            self.assertIn("Date sync failed", self.screen.texts)
            self.assertEqual(len(self.app["videos"]), 6)
            self.tick(key="up")
            self.assertEqual(self.app["next_clock"], 0)
        self.rtc.datetime.assert_not_called()

    def test_stale_clock_and_offline_date_state(self):
        self.seed_cache()
        self.no_wifi.append("WIFI_SSID")
        self.boot()
        with patch.object(self.app["time"], "localtime", return_value=(2025, 1, 1)):
            self.tick()
            self.assertTrue(self.app["clock_needs_sync"]())
            self.assertIn("Connect Wi-Fi for date", self.screen.texts)
            self.assertEqual(len(self.requests), 0)

    def test_down_exits_before_network_or_missing_wifi_handling(self):
        self.boot()
        self.no_wifi.append("WIFI_SSID")
        self.tick(key="down")
        self.reset.assert_called_once_with()
        self.assertEqual(self.requests, [])
        self.assertEqual(self.screen.texts, [])

    def test_down_exits_during_active_download(self):
        self.boot()
        self.tick()
        self.assertIsNotNone(self.app["download"])
        self.tick(key="down")
        self.reset.assert_called_once_with()
        self.assertEqual(len(self.requests), 1)

    def test_unconfigured_app_shows_setup_without_personal_cache_or_requests(self):
        self.seed_cache()
        with patch.multiple(config, CHANNEL_ID="", CHANNEL_HANDLE=""):
            self.boot()
        self.tick()
        self.assertIn("Set up YouTube", self.screen.texts)
        self.assertEqual(self.app["videos"], [])
        self.assertEqual(self.requests, [])
        self.tick(key="down")
        self.reset.assert_called_once_with()

    def test_feed_timeouts_back_off_exponentially_and_cap(self):
        self.boot()
        self.tick()
        for delay in [60000, 120000, 240000, 480000, 900000, 900000]:
            now = self.badge.ticks
            self.requests[-1].error = OSError(110, "ETIMEDOUT")
            self.tick()
            self.assertEqual(self.app["next_feed"], now + delay)
            self.tick(delay - 1)
            self.assertIsNone(self.app["download"])
            self.tick(1)
            self.assertIsNotNone(self.app["download"])
        self.requests[-1].succeed(document(entry(1)).encode())
        self.tick()
        self.assertNotIn("feed", self.app["retry_delays"])
        self.app["next_feed"] = 0
        self.tick()
        self.requests[-1].error = "Connection timed out"
        self.tick()
        self.assertEqual(self.app["next_feed"], self.badge.ticks + config.RETRY_MS)

    def test_thumbnail_timeouts_survive_feed_refresh_and_reset_on_success(self):
        self.boot()
        self.tick()
        self.requests[-1].succeed(document(entry(1)).encode())
        self.tick()
        self.tick()
        self.requests[-1].error = "Read timeout"
        self.tick()
        self.assertEqual(self.app["thumb_retry"]["video000001"], config.RETRY_MS)
        self.app["next_feed"] = 0
        self.tick()
        self.requests[-1].succeed(document(entry(1)).encode())
        self.tick()
        self.assertEqual(self.app["thumb_retry"]["video000001"], config.RETRY_MS)
        self.tick(config.RETRY_MS)
        self.requests[-1].error = "Read timeout"
        self.tick()
        self.assertEqual(self.app["thumb_retry"]["video000001"],
                         self.badge.ticks + 2 * config.RETRY_MS)
        self.tick(2 * config.RETRY_MS)
        self.requests[-1].succeed(b"PNG")
        self.tick()
        self.assertNotIn("video000001", self.app["retry_delays"])
        self.assertNotIn("video000001", self.app["thumb_retry"])

    def test_manual_refresh_resets_backoff(self):
        self.boot()
        self.tick()
        self.requests[-1].error = "Timeout"
        self.tick()
        self.app["retry_delays"]["video000001"] = 2 * config.RETRY_MS
        self.app["thumb_retry"]["video000001"] = 2 * config.RETRY_MS
        self.tick(key="up")
        self.assertEqual(self.app["retry_delays"], {})
        self.assertEqual(self.app["thumb_retry"], {})
        self.assertIsNotNone(self.app["download"])


if __name__ == "__main__":
    unittest.main()
