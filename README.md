# GitHub Universe Badge

This repository now targets the **GitHub Universe 2026 badge**. The current
badge filesystem lives in [`badge/`](./badge/) and is intended to be copied to
the badge's `/system` partition.

The Universe 2025 sources remain available in [`badge25/`](./badge25/) for
people using the previous Tufty 2350 badge. The original 2025 documentation is
preserved at [`badge25/README.md`](./badge25/README.md).

## Repository layout

| Path | Purpose |
| --- | --- |
| [`badge/`](./badge/) | Universe 2026 `/system` files and apps |
| [`badge25/`](./badge25/) | Archived Universe 2025 files, docs, simulator, and apps |
| [`hardware/`](./hardware/) | Universe 2026 schematic and hardware/GPIO reference |
| [`eink/`](./eink/) | Earlier e-ink badge resources |
| [`ir-beacon/`](./ir-beacon/) | IR beacon utilities and protocol experiments |

The legacy simulator and Badgeware API documentation are under `badge25/`.
They do not model the 2026 graphics and input APIs.

## Universe 2026 badge

The 2026 badge uses an RP2350B, a 320x240 LCD, an 8 MB PSRAM, a 16 MB flash
device, a wireless module, an LSM6DS3TR-C IMU, a CAP1208 capacitive touch
controller, IR transmit and receive hardware, a light sensor, four case LEDs,
and a Qw/ST I2C connector.

The firmware automatically handles screen orientation and exposes logical
input actions. Apps should use `BUTTON_UP`, `BUTTON_DOWN`, `BUTTON_LEFT`,
`BUTTON_RIGHT`, `BUTTON_SELECT`, `BUTTON_BACK`, `BUTTON_MENU`, and
`BUTTON_HOME` with `badge.pressed()`, `badge.held()`, and `badge.released()`.
Do not hard-code a physical control based on which end of the badge is
currently uppermost.

See the complete [Universe 2026 hardware reference](./hardware/README.md) for
the RP2350 GPIO map and onboard peripheral connections. See the
[USB serial and MicroPython REPL guide](./hardware/USB_SERIAL.md) to inspect a
connected badge and copy files or apps.

## Creating a 2026 app

Apps are directories under `badge/apps/`:

```text
badge/apps/my_app/
├── __init__.py
├── icon.png
└── assets/
```

`icon.png` should be a 24x24 PNG. A minimal application is:

```python
import os
import sys

APP_DIR = "/system/apps/my_app"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

screen.font = font.nope


def update():
    screen.pen = color.rgb(20, 24, 28)
    screen.rectangle(screen.clip)

    screen.pen = color.rgb(255, 255, 255)
    screen.text("Hello Universe!", 10, 10)

    if badge.pressed(BUTTON_SELECT):
        print("Selected")


run(update)
```

The runtime supplies commonly used graphics and badge objects as globals,
including `badge`, `screen`, `image`, `font`, `color`, `shape`, `brush`,
`vec2`, `rect`, `mat3`, `run`, button constants, mode constants, and filesystem
helpers. Inspect the apps in [`badge/apps/`](./badge/apps/) for working
patterns.

### Input and orientation

```python
if badge.pressed(BUTTON_SELECT):
    activate()

if badge.held(BUTTON_LEFT):
    x -= speed * (badge.ticks_delta / 1000)

if badge.released(BUTTON_BACK):
    close_panel()

if badge.touched(BUTTON_MENU):
    show_touch_feedback()

direction = badge.direction()
upside_down = badge.upside_down()
```

Use `badge.ticks_delta` for frame-rate-independent animation and movement.
Use `screen.width` and `screen.height` instead of assuming a resolution.
The default logical mode used by most included apps is 160x120; apps that need
the full display can request `badge.mode(HIRES | VSYNC)`, which provides a
320x240 drawing surface.

### Graphics

```python
sprite = image.load("assets/sprite.png")
sheet = image.load("assets/characters.png").spritesheet(7, 2)

screen.pen = color.rgb(73, 219, 255)
screen.shape(shape.rectangle(0, 0, screen.width, screen.height))
screen.blit(sprite, vec2(10, 10))
screen.blit(sheet.sprite(0, 0), rect(40, 20, 32, 32))
```

Set `screen.pen` before drawing. Fonts are available through the `font`
namespace, for example `font.nope`, `font.sins`, `font.ark`, and
`font.ziplock`.

### Persistent state

```python
from badgeware import State

state = {"highscore": 0}
State.load("my_app", state)

# Save after a meaningful state change.
State.save("my_app", state)
```

Persistent state is stored outside `/system`; do not commit runtime state or
real Wi-Fi credentials.

## Installing files on a badge

Copy the contents of `badge/` to `/system/` on the Universe 2026 badge. To
install a single app, copy its complete directory to
`/system/apps/<app_name>/`. The menu discovers directories containing
`__init__.py` or `__init__.mpy`.

The normal MicroPython REPL mounts `/system` read-only. Use USB mass-storage
mode for persistent deployment; `mpremote mount badge` is useful for transient
hardware tests without copying. See
[`hardware/USB_SERIAL.md`](./hardware/USB_SERIAL.md) for the tested workflow.

The Wi-Fi template is [`badge/secrets.py`](./badge/secrets.py). Keep committed
values empty and configure credentials only on the device.

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md). New development should target the
2026 runtime under `badge/`; only compatibility fixes for the older hardware
should be made under `badge25/`.
