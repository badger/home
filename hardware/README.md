# GitHub Universe 2026 badge hardware

This document is a human- and agent-readable transcription of the five-page
Pimoroni schematic generated on 3 September 2026. The original source is
retained as [`github_badge_2026_schematic.pdf`](./github_badge_2026_schematic.pdf).

Net names and component references below match the schematic. Treat the
firmware's board definitions and high-level `badge` API as authoritative when
they intentionally abstract or remap these physical signals.

For connecting to a physical badge, inspecting its filesystem, using the
MicroPython REPL, and copying apps, see
[`USB_SERIAL.md`](./USB_SERIAL.md).

## System overview

| Function | Device or circuit |
| --- | --- |
| Main MCU | RP2350B |
| External flash | Winbond W25Q128JVPIQ, 16 MB QSPI |
| PSRAM | APS6404L-3SQR-ZR, 8 MB |
| Wireless | RM2 module, separate `WL_*` control/data nets |
| Display | 320x240 LCD, 8-bit parallel data bus |
| Motion sensing | ST LSM6DS3TR-C accelerometer and gyroscope |
| Capacitive input | CAP1208, eight electrodes |
| IR receiver | VSOP38338 |
| IR transmitter | Two IR LEDs through a DMN3731U low-side MOSFET |
| Ambient light | PT19-21C/L41/TR8 phototransistor |
| Expansion | Qw/ST I2C connector |
| Case lighting | Four independently controlled white LEDs |
| Battery charging | MCP73831/2, approximately 455 mA charge current |
| Battery protection | XB6096I2S |
| Switched 3.3 V | AP22802AW5 load switch |

## Button layout

With the badge upright and the display in its normal orientation, the five
user-facing buttons are arranged as follows:

```text
                          Up (^)

                          Down (⌄)

     Left (<)       Right (>)       Select (⮐)
```

- The bottom row is **Left**, **Right**, then **Select**, from left to right.
- The right edge has **Up** above **Down**.
- Use `BUTTON_LEFT`, `BUTTON_RIGHT`, `BUTTON_SELECT`, `BUTTON_UP`, and
  `BUTTON_DOWN` in applications. These logical constants allow the firmware to
  account for display orientation instead of requiring apps to depend on raw
  switch names or GPIO numbers.

## RP2350B GPIO map

This table is the primary reference for low-level hardware work.

| GPIO | ADC | Schematic net | Connected function |
| ---: | ---: | --- | --- |
| 0 | - | `CL0` | Case LED 1 through 330 ohm resistor |
| 1 | - | `CL1` | Case LED 2 through 330 ohm resistor |
| 2 | - | `CL2` | Case LED 3 through 330 ohm resistor |
| 3 | - | `CL3` | Case LED 4 through 330 ohm resistor |
| 4 | - | `I2C_QWST_SDA` | External Qw/ST I2C data |
| 5 | - | `I2C_QWST_SCL` | External Qw/ST I2C clock |
| 6 | - | `SW_DOWN` | Physical down switch |
| 7 | - | `SW_A` | Physical A switch |
| 8 | - | `PSRAM_CS` | PSRAM chip select |
| 9 | - | `SW_B` | Physical B switch |
| 10 | - | `SW_C` | Physical C switch |
| 11 | - | `SW_UP` | Physical up switch |
| 12 | - | `VBUS_DETECT` | USB VBUS presence through a 5.1k/5.1k divider |
| 13 | - | `CAP_ALERT` | CAP1208 interrupt/alert |
| 14 | - | `RESET_SW` | Reset switch sensing; switch also feeds reset pulse circuit |
| 15 | - | `SWITCH_INT` | Diode-combined physical switch interrupt |
| 16 | - | `IR_TX` | IR transmitter MOSFET gate |
| 17 | - | `IR_RX` | IR receiver output |
| 18 | - | `I2C_INTERNAL_SDA` | Internal sensor/touch I2C data |
| 19 | - | `I2C_INTERNAL_SCL` | Internal sensor/touch I2C clock |
| 20 | - | `IMU_INT` | LSM6DS3TR-C interrupt 1 |
| 21 | - | `LCD_VSYNC` | LCD tearing-effect/vertical-sync signal |
| 22 | - | `USER_SW` | Combined USB boot/user switch |
| 23 | - | `WL_ON` | Wireless module enable |
| 24 | - | `WL_D` | Wireless module bidirectional data |
| 25 | - | `WL_CS` | Wireless module chip select |
| 26 | - | `LCD_BACKLIGHT` | AP2502 LCD backlight enable |
| 27 | - | `LCD_CS` | LCD chip select |
| 28 | - | `LCD_RS` | LCD register/data select |
| 29 | - | `WL_CLK` | Wireless module clock |
| 30 | - | `LCD_WR` | LCD write strobe |
| 31 | - | `LCD_RD` | LCD read strobe |
| 32 | - | `LCD_DB0` | LCD parallel data bit 0 |
| 33 | - | `LCD_DB1` | LCD parallel data bit 1 |
| 34 | - | `LCD_DB2` | LCD parallel data bit 2 |
| 35 | - | `LCD_DB3` | LCD parallel data bit 3 |
| 36 | - | `LCD_DB4` | LCD parallel data bit 4 |
| 37 | - | `LCD_DB5` | LCD parallel data bit 5 |
| 38 | - | `LCD_DB6` | LCD parallel data bit 6 |
| 39 | - | `LCD_DB7` | LCD parallel data bit 7 |
| 40 | ADC0 | `VBAT_SENSE` | Battery voltage through a 750k/250k divider |
| 41 | ADC1 | `SW_POWER_EN` | Active-high enable for switchable 3.3 V rail |
| 42 | ADC2 | Not connected | No connection shown |
| 43 | ADC3 | `LIGHT_SENSE` | Ambient-light phototransistor measurement |
| 44 | ADC4 | Not connected | No connection shown |
| 45 | ADC5 | Not connected | No connection shown |
| 46 | ADC6 | Not connected | No connection shown |
| 47 | ADC7 | Not connected | No connection shown |

GPIO8 is used for `PSRAM_CS`. The schematic notes that the RP2350 PSRAM chip
select could instead use GPIO0, GPIO8, GPIO19, or GPIO47, but those alternatives
do not describe this assembled board.

## Dedicated RP2350 connections

| RP2350 signal | Net or destination |
| --- | --- |
| `QSPI_SD0..3` | Shared data bus to flash and PSRAM |
| `QSPI_SCLK` | Shared QSPI clock to flash and PSRAM |
| `QSPI_CS` | W25Q128 flash chip select |
| `USB_DP`, `USB_DM` | USB-C D+ and D- through 27 ohm series resistors |
| `SWDIO`, `SWCLK` | Three-pin debug connector with ground |
| `RUN` | Reset pulse generator and reset circuitry |
| `XIN`, `XOUT` | External crystal network |

## I2C buses

The board has two distinct I2C buses. Do not place an external device on the
internal bus unless you specifically intend to share it with onboard devices.

| Bus | GPIO | Pull-ups | Devices |
| --- | --- | --- | --- |
| Qw/ST | SDA GPIO4, SCL GPIO5 | 10k to `3V3_SW` | External Qw/ST connector |
| Internal | SDA GPIO18, SCL GPIO19 | 10k to `3V3_SW` | LSM6DS3TR-C and CAP1208 |

### Installed-device address map

| Bus | 7-bit address | Device | Data available to applications |
| --- | ---: | --- | --- |
| Internal | `0x28` | CAP1208 capacitive touch controller | Eight touch channels, mapped by firmware to logical buttons and a direction vector |
| Internal | `0x6A` | LSM6DS3TR-C IMU | Three-axis acceleration, three-axis angular velocity, and orientation derived by firmware |
| Qw/ST | None pre-installed | User-supplied device | Depends on the attached Qw/ST hardware |

The schematic fixes the IMU address by grounding `SDO/SA0`. The CAP1208 has a
fixed 7-bit I2C/SMBus address of `0x28`; the board does not show any address
selection pins.

The Python source does not expose an internal-bus number or construct an I2C
object for these installed devices. Instead, it accesses them through
`badge.imu()`, `badge.touched()`, `badge.direction()`, and the logical button
event APIs. By contrast, `apps/sense/__init__.py` constructs `machine.I2C()` to
talk to optional sensors on the external Qw/ST connector. Do not assume that a
default `machine.I2C()` object refers to the internal bus.

### LSM6DS3TR-C IMU

- Supply: `3V3_SW`.
- I2C: `I2C_INTERNAL_SDA` and `I2C_INTERNAL_SCL`.
- `SDO/SA0` is tied low, selecting I2C address **0x6A**.
- `INT1` is connected to GPIO20 as `IMU_INT`.
- The fitted part is **LSM6DS3TR-C**, explicitly noted as different from
  LSM6DS3TR.
- Firmware uses the IMU to report orientation through
  `badge.upside_down()` and to provide six-axis readings through `badge.imu()`.

#### Data exposed by the 2026 firmware

The input test app unpacks the IMU result as:

```python
ax, ay, az, gx, gy, gz = badge.imu()
```

The six values are integer-like values in this order:

| Index | Name | Meaning |
| ---: | --- | --- |
| 0 | `ax` | Acceleration on the X axis |
| 1 | `ay` | Acceleration on the Y axis |
| 2 | `az` | Acceleration on the Z axis |
| 3 | `gx` | Angular velocity around the X axis |
| 4 | `gy` | Angular velocity around the Y axis |
| 5 | `gz` | Angular velocity around the Z axis |

The available Python source prints the acceleration values with integer
formatting but does not establish whether the six results are raw signed
16-bit register values, scaled physical units, or a firmware-specific fixed
point format. It also does not reveal the configured accelerometer full-scale
range, gyroscope full-scale range, output data rate, filters, or interrupt
thresholds. Apps should therefore treat the values as relative motion data
unless the firmware implementation documents units elsewhere.

The firmware derives a higher-level orientation result from the IMU:

```python
is_inverted = badge.upside_down()  # bool
```

`badge.upside_down()` returns a boolean used by the firmware's automatic
orientation handling. The source does not define its thresholds, filtering,
update rate, or exact relationship to the raw acceleration values.

#### Raw device data

At the device level, the LSM6DS3TR-C provides:

- Three little-endian signed 16-bit accelerometer samples.
- Three little-endian signed 16-bit gyroscope samples.
- A signed temperature sample.
- Status, FIFO, tap, motion, orientation, and interrupt registers.

The actual scale of acceleration and angular-velocity samples depends on the
firmware's full-scale configuration. The schematic connects only `INT1` to
`IMU_INT`; `INT2` is not connected to the RP2350.

### CAP1208 capacitive touch controller

- Supply: `3V3_SW`.
- I2C: internal bus on GPIO18/19.
- 7-bit I2C address: **0x28**.
- Alert: `CAP_ALERT` on GPIO13.
- Eight sensing channels are routed as `CAP1` through `CAP8`.
- Application code should use the logical button constants and
  `badge.touched()`, `badge.pressed()`, `badge.held()`, or `badge.released()`
  rather than assuming a fixed channel-to-action mapping.

#### Data exposed by the 2026 firmware

The input test app shows eight touch-backed logical actions:

| Touch position | Logical action |
| --- | --- |
| Direction pad up | `BUTTON_UP` |
| Direction pad down | `BUTTON_DOWN` |
| Direction pad left | `BUTTON_LEFT` |
| Direction pad right | `BUTTON_RIGHT` |
| Select pad | `BUTTON_SELECT` |
| Back pad | `BUTTON_BACK` |
| Menu pad | `BUTTON_MENU` |
| Home pad | `BUTTON_HOME` |

The source does not identify which physical `CAP1` through `CAP8` net maps to
each logical action. Firmware orientation handling may also change the logical
meaning of directional pads, so applications must not depend on CAP channel
numbers.

Application-level access is:

```python
touching = badge.touched(BUTTON_SELECT)  # current touch state, bool
pressed = badge.pressed(BUTTON_SELECT)   # newly active this poll/frame
held = badge.held(BUTTON_SELECT)         # remains active
released = badge.released(BUTTON_SELECT) # newly inactive
```

Calling `badge.pressed()`, `badge.held()`, or `badge.released()` without an
argument returns a collection of active logical actions. These event
collections combine the firmware's logical input sources; the app source does
not guarantee that every returned action originated from the CAP1208 rather
than a physical switch.

The touch direction pad is also represented as a vector:

```python
move = badge.direction()
x = move.x
y = move.y
magnitude = move.length()
angle = move.angle()
```

This is a processed firmware result, not raw CAP1208 measurement data. The
source does not specify whether diagonals are produced by simultaneous
channels, interpolation, or another algorithm. `apps/input_test/` treats it as
a normalized two-dimensional direction and converts its angle to a
compass-like heading.

#### Raw device data

The CAP1208 itself reports:

- An eight-bit sensor-input status mask, one bit per capacitive channel.
- Signed per-channel delta counts representing change from the calibrated
  baseline.
- Per-channel threshold and enable configuration.
- General touch, repeat, multi-touch, recalibration, sensitivity, and noise
  status/configuration.
- An interrupt condition signalled on the active `CAP_ALERT` connection.

The 2026 Python source does not expose raw delta counts, baselines, thresholds,
noise flags, sensitivity settings, repeat timing, or the controller's
configuration registers. Use `badge.touched()` and the logical event APIs
unless developing firmware or a board diagnostic.

### External Qw/ST bus

No device is shown as permanently installed on the Qw/ST bus. The `sense` app
demonstrates optional external devices by creating one default `machine.I2C()`
object for each driver:

```python
motion_sensor = LSM6DS3(I2C(), mode=NORMAL_MODE_104HZ)
temperature_sensor = BreakoutBME280(I2C())
light_sensor = BreakoutLTR559(I2C())
```

Those LSM6DS3, BME280, and LTR559 devices are part of an optional Multi Sensor
Stick, not pre-installed badge hardware. The app handles `OSError` by telling
the user to connect the stick. Their addresses therefore depend on the
attached breakout and are not part of the badge's installed-device address
map.

## Physical controls

The physical switch nets are `SW_UP`, `SW_DOWN`, `SW_A`, `SW_B`, and `SW_C`.
BAT54AW dual diodes combine them onto `SWITCH_INT` so the MCU can wake or react
through one interrupt while still reading individual switch GPIOs.

The reset switch drives `RESET_SW` and a 74LVC1G57 pulse-generator circuit
connected to `RUN`. The USB boot/user switch is exposed to GPIO22 as
`USER_SW`.

The 2026 firmware also exposes orientation-aware logical actions:

```text
BUTTON_UP, BUTTON_DOWN, BUTTON_LEFT, BUTTON_RIGHT,
BUTTON_SELECT, BUTTON_BACK, BUTTON_MENU, BUTTON_HOME
```

These logical actions include capacitive controls and should be preferred by
apps over raw GPIO access.

## LCD

The LCD uses an 8-bit parallel interface.

| Function | GPIO |
| --- | ---: |
| Data `DB0..DB7` | 32..39 |
| Read strobe | 31 |
| Write strobe | 30 |
| Register select | 28 |
| Chip select | 27 |
| VSYNC/tearing effect | 21 |
| Backlight enable | 26 |

The LCD connector's reset is handled by an RC network rather than an RP2350
GPIO. The AP2502 backlight driver sinks current for four parallel white LEDs
and is enabled by `LCD_BACKLIGHT`.

Most apps use a 160x120 logical framebuffer. `badge.mode(HIRES | VSYNC)`
selects the full 320x240 surface. Always use `screen.width` and
`screen.height` where possible.

## IR

- GPIO16 `IR_TX` drives a DMN3731U N-channel MOSFET.
- The MOSFET switches two series IR LEDs, each with a 47 ohm resistor.
- GPIO17 `IR_RX` receives the output of a VSOP38338 demodulating IR receiver.
- The receiver is powered from `3V3_SW` and includes local decoupling.

## Analog sensing and power control

### Battery voltage

`VBAT_SENSE` reaches GPIO40/ADC0 through a 750k high-side and 250k low-side
divider, so the ADC sees one quarter of the battery voltage:

```text
VBAT = ADC_voltage * 4
```

Account for ADC reference tolerance and divider tolerance when converting this
to a percentage.

### Ambient light

The PT19-21C/L41/TR8 phototransistor is connected between `3V3_SW` and
`LIGHT_SENSE`; a 1k resistor pulls `LIGHT_SENSE` to ground. Read it on
GPIO43/ADC3.

### Power rails

- VBUS is preferred when present; otherwise the system uses the LiPo battery.
- The RT9080-33GJ5 LDO creates always-on 3.3 V.
- GPIO41 `SW_POWER_EN` enables the AP22802AW5 load switch that creates
  `3V3_SW` for switchable peripherals.
- GPIO12 `VBUS_DETECT` reads half of USB VBUS through equal 5.1k resistors.
- `CHARGE_STAT` from the MCP73831/2 also connects to the wireless module.
- The charger programming resistor is 2.2k, documented as approximately
  455 mA charge current.

## Wireless module

The RM2 wireless module is powered from `VDDBAT` and has a 1.8-3.3 V I/O
supply. Its MCU-facing nets are:

| Net | GPIO | Purpose |
| --- | ---: | --- |
| `WL_ON` | 23 | Enable/control |
| `WL_D` | 24 | Data |
| `WL_CS` | 25 | Chip select |
| `WL_CLK` | 29 | Clock |

The module also receives `CHARGE_STAT`. Use the firmware networking APIs rather
than driving these signals directly from application code.

## Lighting and expansion

`CL0` through `CL3` on GPIO0 through GPIO3 each drive a white case LED through
a 330 ohm resistor. The Qw/ST connector exposes `3V3_SW`, ground, and the
GPIO4/5 I2C bus.

## Safe low-level development

- Prefer the `badge` API and `machine.Pin.board` aliases when available.
- Do not reconfigure LCD, flash, PSRAM, wireless, internal I2C, power-control,
  or interrupt GPIOs from an app.
- Qw/ST GPIO4/5 are the intended user expansion bus.
- The ADC-capable GPIOs are not all free: GPIO40, GPIO41, and GPIO43 are
  committed to battery sense, power enable, and light sense.
- Never expose an RP2350 GPIO to 5 V. The MCU I/O rail is 3.3 V.
