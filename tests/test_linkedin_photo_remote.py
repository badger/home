import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "badge" / "apps" / "linkedin_photo"
spec = importlib.util.spec_from_file_location("photo_remote", APP / "remote_batch.py")
remote = importlib.util.module_from_spec(spec)
spec.loader.exec_module(remote)
URL = "https://photos.example/batch.json"


def png(size=(240, 240)):
    output = io.BytesIO()
    Image.new("RGB", size, "blue").save(output, format="PNG")
    return output.getvalue()


class RemoteTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.cache = remote.BatchCache(self.directory.name + "/cache")
        # MicroPython's /state filesystem has POSIX rename-over-existing semantics.
        self.rename = patch.object(remote.os, "rename", side_effect=os.replace)
        self.rename.start()
        self.addCleanup(self.rename.stop)
        self.console = contextlib.redirect_stdout(io.StringIO())
        self.console.__enter__()
        self.addCleanup(self.console.__exit__, None, None, None)

    def fake_transport(self, responses):
        requests = []

        class Fetch:
            ERROR = -1

            def __init__(self, host, port, **kwargs):
                self.options = kwargs
                self.host = host
                self.closed = False
                self.done = False
                self.status = 0
                self.http_status = 200
                self.steps = 0
                requests.append(self)

            def on_error(self, callback):
                self.error_callback = callback

            def fetch(self, path, headers):
                self.path = path

            def update(self):
                self.steps += 1
                if self.steps < 2:
                    return
                response = responses[self.path]
                if isinstance(response, Exception):
                    raise response
                self.http_status, self.body = response
                if len(self.body) > self.options["max_bytes"]:
                    raise ValueError("Response exceeds max_bytes")
                if self.http_status != 200:
                    self.status = self.ERROR
                else:
                    self.done = True

            def to_json(self):
                return json.loads(self.body)

            def reset(self):
                self.closed = True

        return SimpleNamespace(AsyncFetch=Fetch), requests

    def start(self, responses, validate=None, connected=True):
        fetch, requests = self.fake_transport(responses)
        self.modules = patch.dict("sys.modules", {
            "secrets": SimpleNamespace(WIFI_SSID="test"),
            "wifi": SimpleNamespace(connect=Mock(return_value=connected),
                                    is_connected=Mock(return_value=connected),
                                    disconnect=Mock()),
            "fetch": fetch,
        })
        self.modules.start()
        self.addCleanup(self.modules.stop)
        refresh = remote.BatchRefresh(self.cache, validate or self.validate)
        refresh.start(URL)
        return refresh, requests

    @staticmethod
    def validate(path):
        with Image.open(path) as photo:
            photo.verify()

    def finish(self, refresh):
        for _ in range(100):
            if not refresh.busy:
                return
            refresh.poll(16)
        self.fail("Refresh never completed")

    def existing_batch(self):
        slot = self.cache.begin()
        Path(self.cache.path(slot, 0)).write_bytes(png())
        paths = self.cache.commit(slot, 1, URL)
        return paths, Path(self.cache.root, "active.json").read_bytes()

    def test_batch_is_committed_only_after_all_images_validate(self):
        manifest = json.dumps({"photos": [
            "https://photos.example/one.png", "https://photos.example/two.png",
        ]}).encode()
        refresh, requests = self.start({
            "/batch.json": (200, manifest),
            "/one.png": (200, png()),
            "/two.png": (200, png((320, 120))),
        })
        for _ in range(5):
            refresh.poll(16)
            self.assertFalse(Path(self.cache.root, "active.json").exists())
        self.finish(refresh)
        self.assertFalse(refresh.failed)
        self.assertEqual(len(refresh.result), 2)
        self.assertEqual(self.cache.cached(URL), refresh.result)
        self.assertEqual(requests[0].options["max_bytes"], 8192)
        self.assertEqual(requests[1].options["max_bytes"], 128 * 1024)
        self.assertTrue(all(request.closed for request in requests))

    def test_failed_image_keeps_last_complete_batch(self):
        paths, record = self.existing_batch()
        refresh, requests = self.start({
            "/batch.json": (200, b'{"photos":["https://photos.example/bad.png"]}'),
            "/bad.png": (200, b"<html>not a photo</html>"),
        })
        self.finish(refresh)
        self.assertTrue(refresh.failed)
        self.assertIsNone(refresh.result)
        self.assertEqual(self.cache.cached(URL), paths)
        self.assertEqual(Path(self.cache.root, "active.json").read_bytes(), record)
        self.assertTrue(all(request.closed for request in requests))

    def test_repeated_refresh_uses_alternating_slots(self):
        old_paths, _ = self.existing_batch()
        refresh, _ = self.start({
            "/batch.json": (200, b'{"photos":["https://photos.example/new.png"]}'),
            "/new.png": (200, png()),
        })
        self.finish(refresh)
        self.assertNotEqual(refresh.result, old_paths)
        self.assertTrue(Path(old_paths[0]).exists())
        self.assertEqual(remote.BatchCache(self.cache.root).cached(URL), refresh.result)
        refresh.start(URL)
        self.finish(refresh)
        self.assertEqual(refresh.result, old_paths)

    def test_http_failure_and_redirect_are_not_accepted(self):
        for status in (301, 404, 500):
            with self.subTest(status=status):
                refresh, requests = self.start({"/batch.json": (status, b"error")})
                self.finish(refresh)
                self.assertTrue(refresh.failed)
                self.assertIn(str(status), refresh.message)
                self.assertTrue(requests[0].closed)

    def test_oversized_manifest_and_photo_fail_without_commit(self):
        for responses in (
            {"/batch.json": (200, b"x" * 8193)},
            {"/batch.json": (200, b'{"photos":["https://photos.example/huge.png"]}'),
             "/huge.png": (200, b"x" * (128 * 1024 + 1))},
        ):
            with self.subTest(responses=list(responses)):
                refresh, _ = self.start(responses)
                self.finish(refresh)
                self.assertTrue(refresh.failed)
                self.assertIsNone(refresh.result)

    def test_decode_and_disk_failures_preserve_active_record(self):
        paths, record = self.existing_batch()
        responses = {
            "/batch.json": (200, b'{"photos":["https://photos.example/ok.png"]}'),
            "/ok.png": (200, png()),
        }
        for error in (ValueError("decoder failed"), OSError("disk full"), MemoryError()):
            with self.subTest(error=type(error).__name__):
                refresh, _ = self.start(responses, validate=Mock(side_effect=error))
                self.finish(refresh)
                self.assertTrue(refresh.failed)
                self.assertEqual(Path(self.cache.root, "active.json").read_bytes(), record)
                self.assertEqual(self.cache.cached(URL), paths)

    def test_failed_pointer_commit_preserves_old_batch(self):
        paths, record = self.existing_batch()
        refresh, _ = self.start({
            "/batch.json": (200, b'{"photos":["https://photos.example/new.png"]}'),
            "/new.png": (200, png()),
        })
        with patch.object(remote.os, "rename", side_effect=OSError("disk full")):
            self.finish(refresh)
        self.assertTrue(refresh.failed)
        self.assertEqual(Path(self.cache.root, "active.json").read_bytes(), record)
        self.assertEqual(self.cache.cached(URL), paths)

    def test_wifi_timeout_leaves_existing_batch_and_no_request(self):
        paths, _ = self.existing_batch()
        refresh, requests = self.start({}, connected=False)
        refresh.poll(30001)
        self.assertTrue(refresh.failed)
        self.assertEqual(requests, [])
        self.assertEqual(self.cache.cached(URL), paths)

    def test_request_timeout_and_exit_close_socket(self):
        refresh, requests = self.start({"/batch.json": (200, b"{}")})
        refresh.poll(16)
        refresh.poll(30001)
        self.assertTrue(refresh.failed)
        self.assertTrue(requests[0].closed)
        refresh.start(URL)
        refresh.poll(16)
        refresh.close()
        self.assertFalse(refresh.busy)
        self.assertTrue(requests[-1].closed)

    def test_missing_wifi_is_actionable_without_network_import(self):
        with patch.dict("sys.modules", {"secrets": SimpleNamespace(WIFI_SSID="")}):
            refresh = remote.BatchRefresh(self.cache, self.validate)
            refresh.start(URL)
        self.assertFalse(refresh.busy)
        self.assertTrue(refresh.failed)
        self.assertIn("Wi-Fi", refresh.message)

    def test_simulator_fetch_stub_is_reported_without_crashing(self):
        with patch.dict("sys.modules", {
            "secrets": SimpleNamespace(WIFI_SSID="test"),
            "wifi": SimpleNamespace(),
            "fetch": SimpleNamespace(AsyncFetch=type("StubFetch", (), {})),
        }):
            refresh = remote.BatchRefresh(self.cache, self.validate)
            refresh.start(URL)
        self.assertTrue(refresh.failed)
        self.assertFalse(refresh.busy)
        self.assertIn("Download API unavailable", refresh.message)

    def test_cached_batch_does_not_apply_to_different_source(self):
        self.existing_batch()
        self.assertEqual(self.cache.cached("https://other.example/batch.json"), [])

    def test_bad_cache_records_cannot_escape_or_expand_cache(self):
        self.cache.begin()
        for record in ([], {"slot": "../", "count": 1}, {"slot": "a", "count": True},
                       {"slot": "a", "count": 21}, {"slot": "b", "count": 0}):
            Path(self.cache.root, "active.json").write_text(json.dumps(record))
            with self.subTest(record=record), self.assertRaises(ValueError):
                self.cache.cached(URL)

    def test_malformed_json_does_not_replace_cache(self):
        paths, record = self.existing_batch()
        refresh, _ = self.start({"/batch.json": (200, b'{"photos":')})
        self.finish(refresh)
        self.assertTrue(refresh.failed)
        self.assertEqual(Path(self.cache.root, "active.json").read_bytes(), record)
        self.assertEqual(self.cache.cached(URL), paths)

    def test_second_photo_failure_does_not_publish_partial_batch(self):
        paths, record = self.existing_batch()
        refresh, _ = self.start({
            "/batch.json": (200, b'{"photos":["https://photos.example/ok.png",'
                                b'"https://photos.example/fail.png"]}'),
            "/ok.png": (200, png()),
            "/fail.png": OSError("network interrupted"),
        })
        self.finish(refresh)
        self.assertTrue(refresh.failed)
        self.assertEqual(Path(self.cache.root, "active.json").read_bytes(), record)
        self.assertEqual(self.cache.cached(URL), paths)

    def test_config_and_manifest_validation(self):
        for value in (None, [], {}, {"photos": []}, {"photos": [URL] * 21},
                      {"photos": ["file:///etc/passwd"]}, {"photos": [2]}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                remote.manifest_urls(value)
        self.assertEqual(remote.manifest_urls({"photos": [URL]}), [URL])
        config = Path(self.directory.name, "config.json")
        self.assertEqual(remote.read_config(str(config)), "")
        for value in ([], {"batch_url": 123}, {"batch_url": "javascript:x"}):
            config.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                remote.read_config(str(config))
        config.write_text(json.dumps({"batch_url": URL}))
        self.assertEqual(remote.read_config(str(config)), URL)

    def test_url_parsing_rejects_bad_inputs(self):
        self.assertEqual(remote.parse_url("http://localhost:8765/a?b=c"),
                         (False, "localhost", 8765, "/a?b=c"))
        self.assertEqual(remote.parse_url("https://host?batch=1"),
                         (True, "host", 443, "/?batch=1"))
        for url in ("", "ftp://host/x", "https://", "https://user:pass@host/a",
                    "https://host/a\r\nX: bad", "https://host/x#frag",
                    "https://host:99999/x", "https://host\\bad/x", 123):
            with self.subTest(url=url), self.assertRaises(ValueError):
                remote.parse_url(url)

    def test_png_limits_and_format(self):
        remote.check_png(png())
        for data in (b"not png", png((321, 240)), png((320, 241))):
            with self.subTest(length=len(data)), self.assertRaises(ValueError):
                remote.check_png(data)


if __name__ == "__main__":
    unittest.main()
