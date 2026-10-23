# Haiku Printer (2026 firmware only)

Print a random code haiku as a GitHub Universe receipt on a thermal printer connected to the badge.

Pick one of 256 code haiku at random, then print it as a GitHub Universe 2026
store-style receipt on a thermal printer wired to the badge's Qw/ST (Stemma QT)
port. Each receipt has the GitHub logo, the event header, the haiku, some joke
line items, a barcode and a QR code linking to <https://gh.io/badger2026>.

## Controls

| Button | Action |
| --- | --- |
| SELECT | Pick a haiku, or print the one shown |
| UP / DOWN / LEFT / RIGHT / BACK | Shuffle to another haiku |
| BACK (while printing) | Stop printing and feed the paper |

A receipt takes about 11 seconds to print.

## Shopping list

| Part | 🇺🇸 US | 🇬🇧 UK |
| --- | --- | --- |
| Thermal printer (MC206H, 58 mm, TTL) | [Amazon US](https://amzn.to/4ys3te5) | [Amazon UK](https://link.amazon/B0eN5xHCi) |
| 5 V power supply | [Amazon US](https://amzn.to/4k3zeX5) | [Amazon UK](https://link.amazon/B07AnEg4o) |
| Pelican 1150 case | [Amazon US](https://amzn.to/4z11w9x) | [Amazon UK](https://link.amazon/B0j9OYGPV) |
| Panel-mount DC connector | [Amazon US](https://amzn.to/4i9eIBM) | [Amazon UK](https://link.amazon/B04crlTq9) |
| JST connectors (Qw/ST / Stemma QT leads) | [Amazon US](https://amzn.to/4ivEl12) | [Amazon UK](https://link.amazon/B02s5CaJu) |

## Wiring

The badge's Qw/ST port is a 4-pin JST SH (1.0 mm pitch) connector. Its two
signal pins can act as a UART, so the app uses them as a serial link to the
printer's TTL input (9600 baud, 8N1, ESC/POS command mode).

```text
 Badge Qw/ST (JST SH)                 Printer TTL header
 ────────────────────                 ──────────────────
 Black  GND ───────────────────────── GND
 Red    3V3 ──────── (not connected)
 Blue   GPIO4 / UART TX ───────────── RX
 Yellow GPIO5 / UART RX ───────────── TX
```

| Qw/ST wire | Badge signal | Printer TTL pin |
| --- | --- | --- |
| Black | GND | GND |
| Red | 3.3 V | **Leave unconnected** |
| Blue | GPIO4 (UART1 TX) | RX |
| Yellow | GPIO5 (UART1 RX) | TX |

1. Use a JST SH 4-pin pigtail lead and plug it into the badge's Qw/ST port.
   Check the wire colours against the table above. Some leads use different
   colours, so follow the pin order if yours do.
2. Connect GND, TX and RX to the printer's TTL header, using the labels printed
   next to its pins. Always connect GND, because the badge and printer must
   share a common ground.
3. Cut back or insulate the red 3.3 V wire. The badge cannot power the printer.
4. Power the printer from the 5 V supply through the panel-mount DC connector,
   wired to the printer's power input. Check the polarity before switching on.
   A thermal print head draws several amps when printing, so use a supply rated
   for at least 2 A.

If nothing prints, the TX/RX wires are probably swapped; swap blue and yellow.
The printer's TX line is only needed for the paper and online status check. If
the printer drives its TX at 5 V, add a level shifter or a 1k/2k divider on the
yellow wire, because the badge's pins are 3.3 V only.

To check the printer itself, hold FEED while powering it on. It prints a
self-test page, which should show `EPSON (ESC/POS)`, 9600 baud and TTL.

## Case

The printer, power connector and wiring fit inside a Pelican 1150 case. 3d Print printer's panel mount and drill a hole for the DC connector.

## Files

| File | Purpose |
| --- | --- |
| `__init__.py` | Badge app: UI, haiku picker and print progress |
| `escpos.py` | ESC/POS receipt builder and paced UART sender |
| `haikus.txt` | One haiku per line as `verse / verse / verse`, max 32 characters per verse |
| `payments.txt` | Joke "PAID WITH" options, one per line |
| `assets/logo.bin`, `assets/qr.bin` | Pre-rendered 1-bit raster images |
| `launcher_icon.py` | Vector launcher icon contours (MDI `receipt-send`, Apache-2.0) |

Lines in `haikus.txt` that break the format are skipped. Rebuild the raster
assets with `python tools/build_haiku_printer_assets.py` (add `--preview` to
also write PNG previews).

See [`hardware/THERMAL_PRINTER.md`](../../../hardware/THERMAL_PRINTER.md) for
the printer's ESC/POS capabilities, flow control and status codes.
