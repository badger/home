import errno
import io
import json
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "badge/apps/camera"))
import camera_core as core


def jpeg(width=200, height=150):
    output = io.BytesIO()
    Image.new("RGB", (width, height), (210, 30, 40)).save(output, "JPEG")
    return output.getvalue()


def response():
    result = core.Request.__new__(core.Request)
    result.header = bytearray()
    result.body = None
    result.received = 0
    result.status = 0
    result.limit = core.MAX_THUMB
    return result


class TransportTests(unittest.TestCase):
    def test_fragmented_headers_and_body(self):
        request = response()
        data = b"HTTP/1.0 200 OK\r\nContent-Length: 3\r\n\r\nabc"
        for value in data:
            request.feed(bytes([value]))
        self.assertEqual(request.status, 200)
        self.assertEqual(request.body, b"abc")
        self.assertEqual(request.received, 3)

    def test_invalid_lengths_and_transfer_encoding(self):
        for header in (
            b"Content-Length: 32769", b"Content-Length: -1",
            b"Content-Length: 1\r\nTransfer-Encoding: chunked",
            b"Content-Type: image/jpeg",
        ):
            with self.subTest(header=header), self.assertRaises(core.CameraError):
                response().feed(b"HTTP/1.0 200 OK\r\n" + header + b"\r\n\r\n")

    def test_overrun(self):
        with self.assertRaises(core.CameraError):
            response().feed(b"HTTP/1.0 200 OK\r\nContent-Length: 1\r\n\r\nab")

    def test_header_limit(self):
        with self.assertRaises(core.CameraError):
            response().feed(b"x" * 2049)

    def test_zero_length(self):
        request = response()
        request.feed(b"HTTP/1.0 200 OK\r\nContent-Length: 0\r\n\r\n")
        self.assertEqual(request.body, b"")

    def test_timeout_closes_socket(self):
        request = response()
        request.started = 0
        request.timeout = 100
        request.close = unittest.mock.Mock()
        with patch.object(time, "ticks_ms", return_value=101, create=True), \
                patch.object(time, "ticks_diff", side_effect=lambda a, b: a - b, create=True):
            with self.assertRaisesRegex(core.CameraError, "timed out"):
                request.step()
        request.close.assert_called_once()


class SocketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                body = b"SD card unavailable" if self.path == "/error" else b"abc"
                length = 8 if self.path == "/short" else len(body)
                if self.path == "/large":
                    length = 65537
                self.send_response(507 if self.path == "/error" else 200)
                self.send_header("Content-Length", str(length))
                self.end_headers()
                self.wfile.write(body)

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()

    def request(self, path):
        request = core.Request("127.0.0.1", self.server.server_port, path)
        try:
            while True:
                result = request.step()
                if result is not None:
                    return result
                time.sleep(0.001)
        finally:
            self.assertIsNone(request.socket, "Transport must release the socket")

    def setUp(self):
        self.clock = patch.object(time, "ticks_ms",
                                  side_effect=lambda: int(time.monotonic() * 1000),
                                  create=True)
        self.diff = patch.object(time, "ticks_diff", side_effect=lambda a, b: a - b,
                                 create=True)
        self.clock.start()
        self.diff.start()
        self.addCleanup(self.clock.stop)
        self.addCleanup(self.diff.stop)

    def test_real_socket_success(self):
        self.assertEqual(self.request("/ok"), b"abc")

    def test_truncated_socket_response(self):
        with self.assertRaisesRegex(core.CameraError, "interrupted"):
            self.request("/short")

    def test_http_error_is_not_success(self):
        with self.assertRaisesRegex(core.CameraError, "SD card unavailable"):
            self.request("/error")

    def test_oversized_socket_response(self):
        with self.assertRaisesRegex(core.CameraError, "too large"):
            self.request("/large")


class JpegTests(unittest.TestCase):
    def test_baseline_dimensions(self):
        self.assertEqual(core.jpeg_dimensions(jpeg()), (200, 150))
        self.assertEqual(core.jpeg_dimensions(jpeg(320, 240)), (320, 240))

    def test_reject_large_truncated_and_non_jpeg(self):
        for data in (jpeg(1600, 1200), jpeg()[:-1], b"not jpeg", b"\xff\xd8\xff\xd9"):
            with self.subTest(length=len(data)), self.assertRaises(core.CameraError):
                core.jpeg_dimensions(data)

    def test_standard_exif_orientations(self):
        for orientation, rotation in ((1, 0), (6, 1), (3, 2), (8, 3)):
            output = io.BytesIO()
            exif = Image.Exif()
            exif[274] = orientation
            Image.new("RGB", (200, 150)).save(output, "JPEG", exif=exif)
            data = output.getvalue()
            self.assertEqual(core.jpeg_rotation(data), rotation)
            self.assertEqual(core.jpeg_dimensions(data), (200, 150))

    def test_exact_firmware_exif_layout(self):
        data = jpeg()
        for orientation, rotation in ((1, 0), (6, 1), (3, 2), (8, 3)):
            exif = bytes([
                255, 225, 0, 34, 69, 120, 105, 102, 0, 0,
                73, 73, 42, 0, 8, 0, 0, 0, 1, 0,
                18, 1, 3, 0, 1, 0, 0, 0, orientation, 0, 0, 0, 0, 0, 0, 0,
            ])
            tagged = data[:2] + exif + data[2:]
            self.assertEqual(core.jpeg_rotation(tagged), rotation)
            self.assertEqual(Image.open(io.BytesIO(tagged)).getexif()[274], orientation)

    def test_absent_or_truncated_exif_uses_default(self):
        self.assertEqual(core.jpeg_rotation(jpeg(), 3), 3)
        self.assertEqual(core.jpeg_rotation(b"\xff\xd8\xff\xe1\xff\xff", 2), 2)


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name) / "camera"
        self.store = core.PhotoStore(str(self.directory))

    def tearDown(self):
        self.temp.cleanup()

    def test_last_fifteen_survive_reload_in_order(self):
        for count in range(20):
            self.store.add("%016x" % count, jpeg())
        self.assertEqual(len(self.store.photos), 15)
        reloaded = core.PhotoStore(str(self.directory))
        self.assertEqual(reloaded.photos, self.store.photos)
        self.assertEqual(reloaded.photos[0][9:25], "%016x" % 5)
        self.assertEqual(reloaded.photos[-1][9:25], "%016x" % 19)
        self.assertEqual(len(list(self.directory.glob("*.jpg"))), 15)

    def test_idempotent_add(self):
        self.store.add("0123456789abcdef", jpeg())
        self.store.add("0123456789abcdef", jpeg())
        self.assertEqual(len(self.store.photos), 1)

    def test_rotation_persists(self):
        self.assertEqual(self.store.rotation(), 0)
        self.store.set_rotation(3)
        self.assertEqual(core.PhotoStore(str(self.directory)).rotation(), 3)
        with self.assertRaises(core.CameraError):
            self.store.set_rotation(4)

    def test_pending_persists_until_cached(self):
        self.assertIsNone(self.store.pending())
        self.store.begin("0123456789abcdef")
        self.assertEqual(core.PhotoStore(str(self.directory)).pending(), "0123456789abcdef")
        self.store.add("0123456789abcdef", jpeg())
        self.store.finish()
        self.assertIsNone(self.store.pending())

    def test_only_own_photos_are_pruned(self):
        other = self.directory / "holiday.jpg"
        other.write_bytes(b"untouched")
        for count in range(17):
            self.store.add("%016x" % count, jpeg())
        self.assertEqual(other.read_bytes(), b"untouched")

    def test_low_space_does_not_evict_existing_photo(self):
        self.store.add("0000000000000001", jpeg())
        with patch.object(core.os, "statvfs", return_value=(4096, 4096, 256, 1)):
            with self.assertRaisesRegex(core.CameraError, "storage full"):
                self.store.add("0000000000000002", jpeg())
        self.assertEqual(len(self.store.photos), 1)

    def test_invalid_pending_is_explicit(self):
        (self.directory / "pending.json").write_text(json.dumps("../photo"))
        with self.assertRaises(core.CameraError):
            self.store.pending()

    def test_invalid_jpeg_never_written(self):
        with self.assertRaises(core.CameraError):
            self.store.add("0000000000000001", b"not a photo")
        self.assertEqual(self.store.photos, [])

    def test_failed_atomic_rename_keeps_old_photo_and_pending(self):
        self.store.add("0000000000000001", jpeg())
        self.store.begin("0000000000000002")
        with patch.object(core.os, "rename", side_effect=OSError(errno.ENOSPC, "full")):
            with self.assertRaises(OSError):
                self.store.add("0000000000000002", jpeg())
        self.assertEqual(len(self.store.photos), 1)
        self.assertEqual(self.store.pending(), "0000000000000002")


if __name__ == "__main__":
    unittest.main()
