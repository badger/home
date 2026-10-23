"""Thermal printer probe for the Universe 2026 badge Qw/ST port.

Run with: python -m mpremote connect <port> run tests/thermal_printer_probe.py

Prints a status line, text styles, a column ruler, each standard ESC/POS
barcode type and a native QR code. See hardware/THERMAL_PRINTER.md.
"""

import time

from machine import Pin, UART

ESC = b"\x1b"
GS = b"\x1d"
BYTES_PER_SECOND = 750
CHUNK = 32

BARCODES = (
    ("UPC-A", 65, b"01234567890"),
    ("UPC-E", 66, b"0123456"),
    ("EAN-13", 67, b"012345678901"),
    ("EAN-8", 68, b"0123456"),
    ("CODE39", 69, b"BADGE-26"),
    ("ITF", 70, b"12345678"),
    ("CODABAR", 71, b"A40156B"),
    ("CODE93", 72, b"BADGE26"),
    ("CODE128", 73, b"{BBadge 2026"),
)

uart = UART(1, baudrate=9600, bits=8, parity=None, stop=1, tx=Pin(4), rx=Pin(5), timeout=50)


def send(data):
    # The printer silently drops data sent at the full 9600 baud line rate.
    view = memoryview(data)
    while view:
        written = uart.write(view[:CHUNK]) or 0
        view = view[written:]
        time.sleep_ms(written * 1000 // BYTES_PER_SECOND)


def status(kind):
    # Let any unsolicited "\xfcOK" message finish arriving before discarding it.
    time.sleep_ms(100)
    while uart.any():
        uart.read()
    uart.write(b"\x10\x04" + bytes((kind,)))
    deadline = time.ticks_add(time.ticks_ms(), 200)
    while not uart.any() and time.ticks_diff(deadline, time.ticks_ms()) > 0:
        time.sleep_ms(10)
    time.sleep_ms(50)
    reply = uart.read()
    # Some MC206H firmware prefixes DLE EOT 1 with b"\xfe#"; the last byte is the status.
    return "--" if not reply else "0x{:02x}".format(reply[-1])


def line(text=""):
    send(text.encode() + b"\n")


try:
    replies = [status(kind) for kind in (1, 2, 3, 4)]
    print("DLE EOT 1-4:", " ".join(replies))
    if replies[0] == "--":
        print("No status reply: check GND, swap TX/RX, or printer TX is not connected.")

    send(ESC + b"@" + ESC + b"a\x01")
    line("BADGE PRINTER PROBE")
    line("Status " + " ".join(replies))
    send(ESC + b"a\x00")
    line("12345678901234567890123456789012")
    send(ESC + b"E\x01")
    line("Bold")
    send(ESC + b"E\x00" + ESC + b"-\x01")
    line("Underline")
    send(ESC + b"-\x00" + GS + b"B\x01")
    line(" Reverse ")
    send(GS + b"B\x00" + GS + b"!\x11")
    line("Double")
    send(GS + b"!\x00" + ESC + b"M\x01")
    line("Font B: 42 columns per line......")
    send(ESC + b"M\x00" + ESC + b"a\x01")

    send(GS + b"h\x50" + GS + b"w\x02" + GS + b"H\x02" + GS + b"f\x00")
    for name, kind, data in BARCODES:
        line(name)
        send(GS + b"k" + bytes((kind, len(data))) + data)
        line()

    line("Native QR")
    qr = b"https://gh.io/badger2026"
    store = len(qr) + 3
    send(
        GS + b"(k" + bytes((4, 0, 49, 65, 50, 0))
        + GS + b"(k" + bytes((3, 0, 49, 67, 6))
        + GS + b"(k" + bytes((3, 0, 49, 69, 49))
        + GS + b"(k" + bytes((store & 0xFF, store >> 8, 49, 80, 48)) + qr
        + GS + b"(k" + bytes((3, 0, 49, 81, 48))
    )
    send(ESC + b"d\x04")
    print("Probe sent.")
finally:
    uart.deinit()
