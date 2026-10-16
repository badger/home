# U26 physical badge constraints

Sources: pinned U26 `badger/home/hardware/README.md` and the schematic, listed
in [sources.md](sources.md). Firmware behavior must match the target badge.

## Core specifications

- RP2350B with 16 MB flash and 8 MB PSRAM.
- 320x240 full-color display. Most apps use the 160x120 logical display; U26
  apps can request 320x240 mode.
- Wireless module, rechargeable battery, case lighting, light sensor, USB-C,
  SWD, and Qw/ST expansion connector.
- Five front buttons plus eight capacitive controls. Use logical actions:
  UP, DOWN, LEFT, RIGHT, SELECT, BACK, MENU, and HOME.
- Onboard LSM6DS3TR-C accelerometer and gyroscope.
- IR transmitter on GPIO16 and IR receiver on GPIO17. GPIO21 is LCD VSYNC.
- U26 firmware runs MicroPython and supplies its graphics and input APIs as
  runtime globals.

The 2026 badge is a custom Tufty 2350 derivative. Do not assume stock Tufty
wiring for the custom controls, sensors, or IR hardware.

## Design implications

- Use the usual 160x120 logical coordinates unless the app requests high
  resolution. Use `screen.width` and `screen.height` for layout.
- Available app memory depends on firmware, drivers, framebuffers, PSRAM use,
  and loaded assets. Measure on the badge instead of assuming all memory is
  available to an app.
- Keep the per-frame `update()` path short. Desktop performance does not predict RP2350 MicroPython performance.
- Prefer paletted PNGs. Badgeware documentation says they use roughly one quarter of the memory of true-color images.
- Prefer sprite sheets over many separately loaded images.
- Load large or optional assets on demand and release references before `gc.collect()`.
- Use `badge.ticks_delta` for movement that should remain stable when frames
  are delayed.
- Do not take over HOME in normal apps; the launcher owns it.
- Treat Wi-Fi, BLE, IR, LEDs, GPIO, Qw/ST accessories, battery, and charging
  as real hardware behavior requiring on-device testing.

## Hardware-only validation checklist

- Buttons are comfortable with the physical layout and do not require impossible simultaneous presses.
- Text is readable at actual 57.6x43.2 mm display size.
- No clipping appears in either orientation or display mode used by the app.
- First launch fits in memory and repeated navigation does not leak.
- App exits through HOME and `on_exit()` completes promptly.
- Saved state survives reset and handles missing/corrupt data.
- Network failure and absent credentials remain usable or show an actionable error.
- BLE discovery, connection, MTU/chunking, disconnect, and retry behavior work between real peers.
- IR receive/transmit uses the correct pin/protocol and tolerates duplicate or missing events.
- LEDs and battery/charging state behave safely on battery power.
- Any expansion hardware uses the correct voltage, pins, and supported driver.

## Upstream verification

For details not represented in this repository, inspect current files in:

- `badger/home` U26 `badge/` and `hardware/` sources.
- Matching event firmware modules and installed apps.
- `pimoroni/tufty2350` and `pimoroni/badgeware-docs` for shared platform details.

The archived `badger/home/badge25/` APIs and stock Tufty wiring are not the
custom U26 hardware contract.

Verify exact signatures in source or first-party examples before generating hardware code.
