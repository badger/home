# Universe 2026 badge app development

This directory is the deployable `/system` tree for the GitHub Universe 2026
badge. New apps and ports must target the 2026 firmware API. Do not copy 2025
Badgeware patterns from `badge25/` without translating them.

Read [`../hardware/README.md`](../hardware/README.md) before accessing raw GPIO,
I2C, ADC, IR, display, power, wireless, or interrupt hardware.
Read [`../hardware/USB_SERIAL.md`](../hardware/USB_SERIAL.md) before connecting
to a physical badge or copying files over USB.

## Directory and app structure

```text
badge/
├── main.py
├── secrets.py
├── assets/
└── apps/
    └── my_app/
        ├── __init__.py
        ├── icon.png
        └── assets/
```

An app directory is discovered when it contains `__init__.py` or
`__init__.mpy`. Include a 24x24 `icon.png`; the menu falls back to its default
icon when one is absent, but new apps should provide one.

Use an explicit application directory so local modules and relative assets
resolve correctly:

```python
import os
import sys

APP_DIR = "/system/apps/my_app"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)
```

## Runtime-provided globals

The launcher/runtime provides the common badge and graphics API as globals.
Existing apps rely on:

- `badge`: input, timing, orientation, IMU, battery, mode, and status APIs.
- `screen`: drawing surface.
- `image`: image constants and `image.load()`.
- `font`: built-in font namespace.
- `color`: colors and `color.rgb()`.
- `shape`: vector shape constructors.
- `brush`: gradients, patterns, and other brushes.
- `vec2`, `rect`, `mat3`: geometry and transforms.
- `run`: frame-loop runner.
- `file_exists`, `is_dir`, `launch`, `reset`: filesystem and lifecycle helpers.
- `BUTTON_*`, `HIRES`, `VSYNC`: input and display-mode constants.

Import standard MicroPython modules normally. `State` is currently imported
from `badgeware`:

```python
from badgeware import State
```

Follow current apps rather than the legacy `from badgeware import screen,
Image, PixelFont, io, brushes, shapes` API used in `badge25/`.

## Lifecycle

Define an `update()` function and pass it to `run()`:

```python
def update():
    draw()


run(update)
```

An update callback may return a path when it acts as a launcher. The menu uses
`on_exit = run(update).result` so `main.py` can launch the selected app.
Ordinary apps normally call `run(update)` directly.

Avoid doing expensive work or allocating large objects every frame. Load
images, sprite sheets, fonts, brushes, and static shapes at module scope or in
one-time setup.

## Input and automatic orientation

Use logical actions, not physical GPIO names:

```python
if badge.pressed(BUTTON_SELECT):
    confirm()

if badge.held(BUTTON_LEFT):
    x -= speed * (badge.ticks_delta / 1000)

if badge.released(BUTTON_BACK):
    cancel()

if badge.touched(BUTTON_MENU):
    highlight_menu()
```

Available logical actions include:

```text
BUTTON_UP
BUTTON_DOWN
BUTTON_LEFT
BUTTON_RIGHT
BUTTON_SELECT
BUTTON_BACK
BUTTON_MENU
BUTTON_HOME
```

The firmware uses the IMU and touch controller to keep the display and logical
controls consistent when the badge is inverted. Do not swap controls based on
physical A/B/C placement. Use `badge.upside_down()` only when the app genuinely
needs to know the physical orientation.

Additional input APIs demonstrated by `apps/input_test/`:

```python
pressed_now = badge.pressed()       # set of actions
held_now = badge.held()             # set of actions
released_now = badge.released()     # set of actions
move = badge.direction()            # normalized vec2-like direction
touching = badge.touched(action)
ax, ay, az, gx, gy, gz = badge.imu()
```

Use the per-action form (`badge.pressed(BUTTON_SELECT)`) for normal app logic.
Use set-returning forms for diagnostics or multi-action processing.

## Timing

- `badge.ticks`: milliseconds since boot.
- `badge.ticks_delta`: milliseconds since the previous frame.

Movement and animation must be frame-rate independent:

```python
position += pixels_per_second * (badge.ticks_delta / 1000)
```

Do not move by a fixed number of pixels per update. Display modes and firmware
changes can alter frame rate.

## Display and graphics

Most apps use a 160x120 logical drawing surface. Apps can request full
resolution:

```python
badge.mode(HIRES | VSYNC)
```

HIRES provides 320x240. Always prefer `screen.width`, `screen.height`, and
`screen.clip` over fixed dimensions.

### Drawing

```python
screen.pen = color.rgb(20, 24, 28)
screen.rectangle(screen.clip)

screen.pen = color.rgb(255, 255, 255)
screen.shape(shape.rounded_rectangle(8, 8, 80, 24, 4))
screen.line(0, 0, screen.width - 1, screen.height - 1)
screen.text("Hello", 12, 12)
```

Set `screen.pen` before drawing. `badge.default_clear` can set the automatic
frame clear color.

### Fonts

Use built-in fonts through the `font` namespace:

```python
screen.font = font.nope
screen.font = font.sins
screen.font = font.ark
screen.font = font.ziplock
```

Use `width, height = screen.measure_text(text)` for alignment.

### Images and sprites

```python
picture = image.load("assets/picture.png")
sheet = image.load("assets/characters.png").spritesheet(7, 2)

screen.blit(picture, vec2(10, 10))
screen.blit(sheet.sprite(column, row), rect(x, y, width, height))
```

A negative `rect` width or height flips a blit. Use paletted or otherwise
optimized PNGs where practical because RAM remains constrained.

### Transforms and antialiasing

```python
screen.antialias = image.X2
tile.transform = mat3().translate(x, y).scale(scale_x, scale_y)
```

Available antialiasing modes demonstrated in the tree include `image.OFF`,
`image.X2`, and `image.X4`.

## State and files

```python
from badgeware import State

state = {"score": 0}
State.load("my_app", state)
State.save("my_app", state)
```

Use a unique state key. Save only after meaningful changes, not every frame.
Wrap direct file operations in `try`/`except OSError` when absence is expected.
Do not commit generated state or real values in `secrets.py`.

## Hardware rules

The complete physical map is in [`../hardware/README.md`](../hardware/README.md).
Important application-facing facts:

- GPIO4/5 are the Qw/ST expansion I2C bus.
- GPIO18/19 are the internal I2C bus shared by the IMU and CAP1208.
- GPIO16/17 are IR transmit/receive.
- GPIO40/ADC0 measures battery voltage through a 4:1 divider.
- GPIO43/ADC3 measures ambient light.
- GPIO41 controls switchable 3.3 V and is not a general-purpose ADC input.
- GPIO0..3 drive case LEDs.
- LCD, PSRAM, flash, wireless, switch, and interrupt GPIOs are committed.

Prefer firmware APIs and `machine.Pin.board` aliases. Never use numeric GPIOs
without checking the hardware reference and existing firmware behavior.

## Working with a connected badge

The badge exposes a MicroPython USB serial interface. Use `mpremote` and follow
[`../hardware/USB_SERIAL.md`](../hardware/USB_SERIAL.md).

Discover the port instead of hard-coding it:

```bash
mpremote devs
PORT=/dev/cu.usbmodem2101  # example only
```

The tested device identifies as USB `2e8a:1101`, product
`Pimoroni Tufty 2350 MicroPython`.

Common commands:

```bash
mpremote connect "$PORT" fs ls :/system/apps
mpremote connect "$PORT" exec "import os; print(os.listdir('/state'))"
mpremote connect "$PORT" reset
```

Only one process can own the port. Never run serial operations in parallel.
Close Thonny, Web Serial pages, `screen`, and other `mpremote` processes first.
Connecting can interrupt the running app and `mpremote` normally soft-resets
when entering raw REPL, so reset and test the normal startup path after
deploying.

Remote filesystem paths use a leading `:` in `mpremote fs` commands. The normal
REPL runtime mounts `/system` read-only on the tested firmware, so `mpremote fs
cp ... :/system/...` fails with `EROFS`. Use `mpremote mount badge` for a quick
hardware render test, or put the badge into USB mass-storage mode before
replacing files in `/system`. App state belongs under `/state`, which remains
writable. See the USB serial guide for the tested details.

## Reference apps

Use these current 2026 examples:

| App | Pattern |
| --- | --- |
| `apps/input_test/` | Capacitive input, physical input, direction, IMU, HIRES |
| `apps/menu/` | Launcher return values, pagination, transforms |
| `apps/plucky_cluck/` | Frame-rate-independent game loop and sprites |
| `apps/flappy/` | Ported 2025 game using the 2026 API |
| `apps/gallery/` | Image loading and navigation |
| `apps/sense/` | External Qw/ST I2C sensor use |
| `apps/demos/` | Graphics, brush, text, and transform techniques |

## Porting from Universe 2025

Translate these common API changes:

| Universe 2025 | Universe 2026 |
| --- | --- |
| `io.BUTTON_A in io.pressed` | `badge.pressed(BUTTON_SELECT)` or another logical action |
| `io.ticks` | `badge.ticks` |
| `io.ticks_delta` | `badge.ticks_delta` |
| `screen.brush = brushes.color(...)` | `screen.pen = color.rgb(...)` |
| `screen.draw(shapes.rectangle(...))` | `screen.shape(shape.rectangle(...))` |
| `Image.load(...)` | `image.load(...)` |
| `SpriteSheet(path, columns, rows)` | `image.load(path).spritesheet(columns, rows)` |
| `PixelFont.load(...)` | `font.<name>` |
| `screen.blit(sprite, x, y)` | `screen.blit(sprite, vec2(x, y))` |
| `screen.scale_blit(...)` | `screen.blit(sprite, rect(x, y, width, height))` |

Also replace per-frame movement with `badge.ticks_delta`-based movement, use
logical orientation-aware controls, and verify layout in both orientations.
