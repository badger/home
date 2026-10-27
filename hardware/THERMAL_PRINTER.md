# Thermal receipt printer on the Qw/ST port

This guide covers driving an **MC206H** embedded 58 mm thermal printer (ESC/POS,
TTL serial, 9600 8N1 by default) from the Universe 2026 badge. It also applies
to most other ESC/POS panel printers with a TTL serial input.
[`badge/apps/haiku_printer/`](../badge/apps/haiku_printer/) is the reference app.

## Wiring

The Qw/ST connector carries GPIO4 (`I2C_QWST_SDA`) and GPIO5 (`I2C_QWST_SCL`).
On the RP2350 these pins can also act as **UART1 TX (GPIO4)** and **UART1 RX
(GPIO5)**. The on-board 10k pull-ups are harmless because UART idles high.

| Qw/ST wire | Badge signal | Printer TTL pin |
| --- | --- | --- |
| Black | GND | GND (required common ground) |
| Red | 3V3_SW | **Not connected** |
| Blue | GPIO4, UART1 TX | Printer RX |
| Yellow | GPIO5, UART1 RX | Printer TX (optional, for status) |

- Power the printer from its **own supply** (5–9 V, at least 2 A peak). The
  badge cannot power a thermal head.
- The badge sends 3.3 V logic, which the MC206H accepts.
- The printer's TX may idle at **5 V**, and RP2350 GPIOs must never see more
  than 3.3 V. Measure it before connecting. If it is above 3.3 V, use a level
  shifter or a low-impedance divider (for example 1k/2k). You can also leave
  it disconnected and give up status reads.

```python
from machine import UART, Pin

uart = UART(1, baudrate=9600, bits=8, parity=None, stop=1,
            tx=Pin(4), rx=Pin(5), timeout=50)
uart.write(b"\x1b@Hello from the badge\n\n\n")
uart.deinit()  # always release the pins when the app exits
```

While an app owns the UART, the Qw/ST port is not available for I2C sensors.

### Quick check

1. Hold FEED while powering the printer on. It prints a self-test page; check
   that it shows `EPSON (ESC/POS)`, 9600 baud and TTL.
2. Run `python -m mpremote connect <port> run tests/thermal_printer_probe.py`.
   It prints a status line, text styles, a column ruler, barcodes and a
   native QR test.
3. A status byte of `0x12` to `DLE EOT 1` (`10 04 01`) means online and idle.
   The tested MC206H prefixes this reply with `fe 23`, so read the last byte. No
   reply means TX/RX are swapped or printer TX isn't connected.

## Flow control: do not send at full line rate

The MC206H has no hardware handshake on its TTL header and only a small
receive buffer. If a full receipt is streamed at the 9600 baud line rate
(about 960 B/s), the printer **silently drops data**. The receipt then stops
partway, often after a raster image, while the badge reports success.

Pace writes to about **750 B/s** in small chunks (900 B/s overflowed; 750 B/s is
tested with back-to-back receipts). Also check how many bytes
each `uart.write()` call actually accepted.
`escpos.Printer` in the haiku app does this in a frame-friendly way: it sends
`BYTES_PER_SECOND` worth of data per second spread across `update()` calls. A
~7.5 KB receipt with logo and QR therefore takes about 11 s.

## Capabilities

The paper is 58 mm wide with **384 printable dots** (48 bytes) at 203 dpi
(8 dots/mm). There is no cutter; feed about 4 lines, then tear.

### Text

| Feature | Command | Notes |
| --- | --- | --- |
| Initialise | `ESC @` (1B 40) | Start every job with this |
| Justify | `ESC a n` | 0 left, 1 centre, 2 right |
| Bold | `ESC E n` | |
| Underline | `ESC - n` | 1- or 2-dot |
| Size | `GS ! n` | `0x10` double width, `0x01` double height |
| Font | `ESC M n` | Font A 12×24 = **32 columns**; Font B 9×17 = 42 columns |
| Reverse | `GS B n` | White on black |
| Feed | `ESC d n` | Feed n lines |
| Heat | `ESC 7 n1 n2 n3` | Darkness vs. speed tuning |

Use ASCII only. Code-page support varies, so avoid smart quotes and emoji.

### Raster images

`GS v 0 m xL xH yL yH data` prints a 1-bit image (MSB = leftmost pixel,
1 = black), up to 48 bytes wide. Send tall images in bands of 24 rows.
Pre-render images on the host: `tools/build_haiku_printer_assets.py` produces
`.bin` files with a 3-byte header (`u8` width in bytes, `u16` LE height)
followed by the rows.

### Barcodes

Set up with `GS h n` (height), `GS w n` (module width 2–6), `GS H n`
(human-readable text position) and `GS f n` (text font). Then print with
`GS k m n data`. The usual set is UPC-A, UPC-E, EAN-13, EAN-8, CODE39, ITF,
CODABAR, CODE93 and **CODE128**. CODE128 (`m = 73`, data prefixed with `{B`)
handles arbitrary ASCII; the probe prints a sample of each.

### QR codes

- **Raster (recommended):** pre-render the QR on the host and print it with
  `GS v 0`. It works on every ESC/POS printer and can carry a branded logo.
  The haiku receipt uses a version 3 QR at 6 dots/module plus a 4-module quiet
  zone (222×222 px, about 6.2 KB). At 3 dots/module it was too small for phones
  to scan reliably.
- **Native:** `GS ( k` (model 2, module size, error correction, store, print)
  needs far fewer bytes, but many low-cost clones don't implement it. The
  probe prints one so you can check yours. `escpos.native_qr()` builds the
  command.

### Status

`DLE EOT n` (`10 04 n`) is answered in real time with one status byte. Use
n=1 for printer, 2 for offline, 3 for error and 4 for paper. For n=4, bits
5–6 set means paper out. The firmware may also send unsolicited `\xfcOK`
messages; discard them before reading a status reply.
