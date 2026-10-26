# U26 physical badge constraints

Source: `badger/home` `hardware/README.md` and its schematic. Read them before
raw GPIO, I2C, ADC, IR, power, or wireless work.

## Core specifications

- RP2350B with 16 MB flash and 8 MB PSRAM.
- 320x240 colour display; most apps draw at 160x120, `badge.mode(HIRES | VSYNC)`
  gives 320x240.
- Wireless module (Wi-Fi and Bluetooth), rechargeable battery, four case
  LEDs (GPIO0..3), light sensor (GPIO43/ADC3), battery sense (GPIO40/ADC0),
  USB-C, SWD, and a Qw/ST connector (I2C on GPIO4/5).
- Five front buttons plus eight capacitive controls (CAP1208 on internal I2C
  GPIO18/19, shared with the IMU). Use logical actions only.
- LSM6DS3TR-C accelerometer and gyroscope.
- IR transmitter on GPIO16 and receiver on GPIO17.
- GPIO41 switches 3.3 V; it is not an ADC input. LCD, PSRAM, flash, and
  wireless pins are committed.

The badge is a custom Tufty 2350 derivative. Do not assume stock Tufty wiring.
Prefer firmware APIs and `machine.Pin.board` aliases over numeric GPIOs.

## Design implications

- Measure memory on the badge (`gc.mem_free()` over the REPL); do not assume
  all RAM is available to an app.
- Keep `update()` short. Desktop and simulator speed do not predict RP2350
  MicroPython speed.
- Prefer paletted PNGs and sprite sheets; load assets once.
- Use `badge.ticks_delta` for movement.
- Do not take over HOME; the launcher owns it.
- Wi-Fi, Bluetooth, IR, LEDs, GPIO, Qw/ST devices, battery, and charging need
  on-device testing.

## Hardware-only checklist

- Controls are comfortable and work in both orientations.
- Text is readable on the real 2.8" screen.
- First launch fits in memory; repeated launches do not leak.
- HOME exits promptly and `on_exit()` finishes quickly.
- Saved state survives reset and tolerates missing or corrupt data.
- Missing Wi-Fi credentials or network failures give a usable message.
- Link apps work between two real badges, including disconnect and retry.
- IR handles duplicates and missed events at real range.
- LEDs and power use behave on battery.
- Expansion hardware uses the right voltage, bus, and driver.

Shared platform details: `pimoroni/tufty2350` and `pimoroni/badgeware-docs`.
They do not describe the 2026 badge's custom wiring.
