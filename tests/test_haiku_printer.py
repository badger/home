"""Host-side checks for the haiku printer app, corpus and ESC/POS output."""

from pathlib import Path
import sys
import unittest

APP = Path(__file__).resolve().parents[1] / "badge/apps/haiku_printer"
sys.path.insert(0, str(APP))

import escpos  # noqa: E402


class FakeUart:
    def __init__(self, limit=None):
        self.data = bytearray()
        self.limit = limit

    def write(self, data):
        data = bytes(data[: self.limit] if self.limit else data)
        self.data += data
        return len(data)


class CorpusTests(unittest.TestCase):
    def setUp(self):
        self.lines = (APP / "haikus.txt").read_bytes().decode("ascii").splitlines()

    def test_has_256_unique_haiku(self):
        self.assertEqual(len(self.lines), 256)
        self.assertEqual(len({line.lower() for line in self.lines}), 256)

    def test_each_line_has_three_printable_verses(self):
        for number, line in enumerate(self.lines, 1):
            verses = line.split(" / ")
            self.assertEqual(len(verses), 3, number)
            for verse in verses:
                self.assertTrue(verse.strip(), number)
                self.assertEqual(verse, verse.strip(), number)
                self.assertLessEqual(len(verse), escpos.COLS, number)
                self.assertNotIn("/", verse, number)


class PaymentTests(unittest.TestCase):
    def test_payments_fit_paid_with_line(self):
        payments = (APP / "payments.txt").read_bytes().decode("ascii").splitlines()
        self.assertGreater(len(payments), 0)
        for payment in payments:
            self.assertTrue(payment.strip())
            self.assertLessEqual(len("PAID WITH ") + len(payment), escpos.COLS, payment)


class ReceiptTests(unittest.TestCase):
    def build(self, **kwargs):
        verses = ["A merge conflict blooms", "two branches, one ancestor", "rebase, start again"]
        return b"".join(
            escpos.receipt(
                42, verses, str(APP / "assets/logo.bin"), str(APP / "assets/qr.bin"), **kwargs
            )
        )

    def test_receipt_contents(self):
        data = self.build()
        self.assertTrue(data.startswith(escpos.INIT))
        for text in (b"GitHub Universe 2026", b"Fort Mason Center", b"CODE HAIKU #042",
                     b"two branches, one ancestor", b"gh.io/badger2026"):
            self.assertIn(text, data)
        self.assertIn(b"\x1dk\x49\x06{BH042", data)
        self.assertIn(b"\x1dH\x00", data)
        self.assertIn(b"H042\n", data)
        self.assertIn(b"BUILD FROM HERE!", data)
        self.assertIn(b"PAID WITH" + b" " * 14 + b"CURIOSITY", data)
        self.assertNotIn(b"DATE", data)

    def test_date_only_when_clock_set(self):
        self.assertIn(b"DATE 10/20/2026", self.build(date="10/20/2026", clock="18:52"))

    def test_raster_bands_cover_image(self):
        for name in ("logo", "qr"):
            path = APP / "assets" / (name + ".bin")
            raw = path.read_bytes()
            width_bytes, height = raw[0], raw[1] | raw[2] << 8
            self.assertLessEqual(width_bytes * 8, 384)
            self.assertEqual(len(raw), 3 + width_bytes * height)
            rows = 0
            for band in escpos.raster(str(path)):
                self.assertEqual(band[:4], b"\x1dv0\x00")
                band_rows = band[6] | band[7] << 8
                self.assertLessEqual(band_rows, escpos.BAND_ROWS)
                self.assertEqual(len(band), 8 + width_bytes * band_rows)
                rows += band_rows
            self.assertEqual(rows, height)

    def test_columns_fit_width(self):
        self.assertEqual(len(escpos.columns("SUBTOTAL", "$0.00")), escpos.COLS)
        self.assertEqual(len(escpos.columns("x" * 40, "$0.00")), escpos.COLS)


class PrinterTests(unittest.TestCase):
    def test_paced_send_matches_receipt(self):
        chunks = [b"a" * 100, b"b" * 300, b"c" * 5]
        uart = FakeUart(limit=7)
        printer = escpos.Printer(uart, bytes_per_second=400)
        printer.start(chunks, 405)
        frames = 0
        while printer.pump(20):
            frames += 1
            self.assertLess(frames, 10000)
        self.assertEqual(bytes(uart.data), b"".join(chunks))
        self.assertEqual(printer.progress, 1.0)

    def test_pacing_respects_rate(self):
        uart = FakeUart()
        printer = escpos.Printer(uart, bytes_per_second=400)
        printer.start([b"x" * 4000], 4000)
        for _ in range(50):
            printer.pump(20)
        self.assertLessEqual(len(uart.data), 400 + escpos.CHUNK)

    def test_cancel_feeds_paper_out(self):
        uart = FakeUart()
        printer = escpos.Printer(uart)
        printer.start([b"x" * 1000, b"never"], 1005)
        printer.pump(100)
        printer.cancel()
        while printer.pump(100):
            pass
        self.assertNotIn(b"never", uart.data)
        self.assertTrue(uart.data.endswith(escpos.feed(4) + escpos.align(escpos.LEFT)))
        self.assertTrue(printer.cancelled)
        printer.start([b"next"], 4)
        self.assertFalse(printer.cancelled)

    def test_drain_finishes_in_flight_command(self):
        uart = FakeUart()
        printer = escpos.Printer(uart)
        printer.start([b"x" * 500, b"never"], 505)
        printer.pump(20)
        self.assertTrue(printer.drain(sleep=lambda ms: None))
        self.assertFalse(printer.busy)
        self.assertNotIn(b"never", uart.data)
        self.assertTrue(uart.data.startswith(b"x" * 500))

    def test_drain_gives_up_on_stalled_uart(self):
        class Stalled:
            def write(self, data):
                return 0

        printer = escpos.Printer(Stalled())
        printer.start([b"x" * 100], 100)
        self.assertFalse(printer.drain(timeout_ms=100, sleep=lambda ms: None))


class StatusTests(unittest.TestCase):
    def test_status_byte_skips_notifications_and_prefix(self):
        self.assertEqual(escpos.status_byte(b"\xfcOK\x12"), 0x12)
        self.assertEqual(escpos.status_byte(b"\xfe#\x12"), 0x12)
        self.assertEqual(escpos.status_byte(b"\xfcOK"), None)
        self.assertEqual(escpos.status_byte(b""), None)

    def test_status_problem(self):
        self.assertIsNone(escpos.status_problem(0x12, 0x12))
        self.assertEqual(escpos.status_problem(None, 0x12), "Printer not responding")
        self.assertEqual(escpos.status_problem(0x12, 0x72), "Printer is out of paper")
        self.assertEqual(escpos.status_problem(0x1A, 0x12), "Printer is offline")


if __name__ == "__main__":
    unittest.main()
