"""Minimal ESC/POS receipt builder and paced UART sender for the MC206H.

The printer is 58 mm (384 dots) wide, so Font A gives 32 columns.
Everything here also imports under CPython so tests can inspect the bytes.
"""

COLS = 32

ESC = b"\x1b"
GS = b"\x1d"
DLE = b"\x10"

INIT = ESC + b"@"
LEFT, CENTER, RIGHT = 0, 1, 2

STATUS_PRINTER = 1
STATUS_OFFLINE = 2
STATUS_ERROR = 3
STATUS_PAPER = 4

BAND_ROWS = 24
CHUNK = 32
# The MC206H drops data if fed at the full 9600 baud line rate (~960 B/s).
BYTES_PER_SECOND = 750


def align(mode):
    return ESC + b"a" + bytes((mode,))


def bold(on):
    return ESC + b"E" + bytes((1 if on else 0,))


def size(double_width=False, double_height=False):
    return GS + b"!" + bytes(((0x10 if double_width else 0) | (0x01 if double_height else 0),))


def reverse(on):
    return GS + b"B" + bytes((1 if on else 0,))


def feed(lines=1):
    return ESC + b"d" + bytes((lines,))


def text(line, mode=LEFT, strong=False, double_width=False, double_height=False, inverse=False):
    out = align(mode)
    if strong:
        out += bold(True)
    if double_width or double_height:
        out += size(double_width, double_height)
    if inverse:
        out += reverse(True)
    out += line.encode() + b"\n"
    if inverse:
        out += reverse(False)
    if double_width or double_height:
        out += size()
    if strong:
        out += bold(False)
    return out


def columns(left, right, width=COLS):
    gap = width - len(left) - len(right)
    if gap < 1:
        left = left[: max(0, width - len(right) - 1)]
        gap = width - len(left) - len(right)
    return left + " " * gap + right


def rule(char="-"):
    return text(char * COLS)


def code128(data, height=60, module=2):
    # ESC/POS CODE128 data must start with a code set selector; {B is set B (ASCII).
    payload = b"{B" + data.encode()
    return (
        GS + b"h" + bytes((height,))
        + GS + b"w" + bytes((module,))
        + GS + b"H" + bytes((0,))
        + GS + b"f" + bytes((0,))
        + GS + b"k" + bytes((73, len(payload))) + payload
    )


def native_qr(data, module=6, ecc=49):
    """Printer-generated QR (GS ( k). Not all MC206H firmware supports it."""
    payload = data.encode()
    store = len(payload) + 3
    return (
        GS + b"(k" + bytes((4, 0, 49, 65, 50, 0))
        + GS + b"(k" + bytes((3, 0, 49, 67, module))
        + GS + b"(k" + bytes((3, 0, 49, 69, ecc))
        + GS + b"(k" + bytes((store & 0xFF, store >> 8, 49, 80, 48)) + payload
        + GS + b"(k" + bytes((3, 0, 49, 81, 48))
    )


def status_request(kind=STATUS_PRINTER):
    return DLE + b"\x04" + bytes((kind,))


def status_byte(reply):
    """Return the first real-time status byte in ``reply``, or None.

    Status bytes always have bit 1 and bit 4 set and bits 0 and 7 clear. That
    skips unsolicited ``\xfcOK`` notifications and the MC206H ``\xfe#`` prefix.
    """
    for value in reply or b"":
        if value & 0x93 == 0x12:
            return value
    return None


def status_problem(printer_status, paper_status):
    """Describe why the printer can't print, or return None when ready."""
    if printer_status is None or paper_status is None:
        return "Printer not responding"
    if paper_status & 0x60:
        return "Printer is out of paper"
    if printer_status & 0x08:
        return "Printer is offline"
    return None


def raster(path):
    """Yield GS v 0 commands for a packed 1bpp raster file, in short bands."""
    with open(path, "rb") as source:
        header = source.read(3)
        width_bytes = header[0]
        height = header[1] | (header[2] << 8)
        row = 0
        while row < height:
            rows = min(BAND_ROWS, height - row)
            yield (
                GS + b"v0" + bytes((0, width_bytes, 0, rows & 0xFF, rows >> 8))
                + source.read(width_bytes * rows)
            )
            row += rows


def haiku_id(number):
    return "{:03d}".format(number)


def receipt(number, verses, logo=None, qr=None, date=None, clock=None, payment="CURIOSITY"):
    """Yield the byte chunks for one haiku receipt.

    ``number`` is the 1-based haiku line number; ``date``/``clock`` are
    omitted when the badge clock has not been set.
    """
    ident = haiku_id(number)
    yield INIT
    if logo:
        yield align(CENTER)
        for band in raster(logo):
            yield band
        yield feed(1)
    yield text("GitHub Universe 2026", CENTER, strong=True, double_height=True)
    yield text("Fort Mason Center", CENTER)
    yield text("2 Marina Blvd", CENTER)
    yield text("San Francisco, CA 94123", CENTER)
    yield rule()
    if date and clock:
        yield text(columns("DATE " + date, "TIME " + clock))
    yield text(columns("BADGE 2026", "REG 01"))
    yield rule()
    yield text(columns("ITEM", "QTY   AMT"), strong=True)
    yield text(columns("CODE HAIKU #" + ident, "1   $0.00"))
    yield rule()
    yield text(" YOUR HAIKU ", CENTER, strong=True, inverse=True)
    yield feed(1)
    for verse in verses:
        yield text(verse, CENTER)
    yield feed(1)
    yield rule()
    yield text(columns("SYLLABLES", "5-7-5"))
    yield text(columns("SUBTOTAL", "$0.00"))
    yield text(columns("TAX (ENTERPRISE)", "$0.00"))
    yield text(columns("TOTAL", "$0.00", COLS // 2), strong=True, double_width=True)
    yield text(columns("PAID WITH", payment))
    yield rule()
    yield align(CENTER) + code128("H" + ident)
    # Printer HRI would show the {B selector, so print the ID as text instead.
    yield text("H" + ident, CENTER)
    yield feed(1)
    yield text("BUILD FROM HERE!", CENTER, strong=True)
    yield feed(1)
    if qr:
        yield align(CENTER)
        for band in raster(qr):
            yield band
    yield text("Scan for the badge apps", CENTER)
    yield text("gh.io/badger2026", CENTER, strong=True)
    yield feed(1)
    yield rule("*")
    yield feed(4)
    yield align(LEFT)


class Printer:
    """Drip-feed chunks to a UART at roughly the line rate.

    Call ``pump(elapsed_ms)`` once per frame; it never writes more than the
    byte budget accumulated since the last call, so the UI stays responsive.
    """

    def __init__(self, uart, bytes_per_second=BYTES_PER_SECOND):
        self.uart = uart
        self.rate = bytes_per_second
        self.chunks = None
        self.pending = b""
        self.budget = 0
        self.sent = 0
        self.total = 0
        self.cancelled = False

    @property
    def busy(self):
        return self.chunks is not None or bool(self.pending)

    @property
    def progress(self):
        return min(1.0, self.sent / self.total) if self.total else 1.0

    def start(self, chunks, total):
        self.chunks = iter(chunks)
        self.pending = b""
        self.budget = CHUNK
        self.sent = 0
        self.total = total
        self.cancelled = False

    def pump(self, elapsed_ms):
        if not self.busy:
            return False
        self.budget = min(self.budget + self.rate * elapsed_ms // 1000, self.rate // 4)
        while self.budget > 0:
            if not self.pending:
                if self.chunks is None:
                    break
                try:
                    self.pending = next(self.chunks)
                except StopIteration:
                    self.chunks = None
                    break
            written = self.uart.write(self.pending[: min(self.budget, CHUNK)]) or 0
            if not written:
                break
            self.pending = self.pending[written:]
            self.budget -= written
            self.sent += written
        return self.busy

    def cancel(self):
        """Finish the command in flight, then eject what has printed."""
        if self.busy and not self.cancelled:
            self.cancelled = True
            self.chunks = iter((feed(4), align(LEFT)))
            self.total = self.sent + len(self.pending) + 5

    def drain(self, timeout_ms=3000, step_ms=20, sleep=None):
        """Cancel, then block until the in-flight command is sent (bounded)."""
        if sleep is None:
            import time
            sleep = time.sleep_ms
        self.cancel()
        waited = 0
        while self.pump(step_ms):
            if waited >= timeout_ms:
                return False
            sleep(step_ms)
            waited += step_ms
        return True
