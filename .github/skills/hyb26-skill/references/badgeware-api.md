# U26 runtime and Badgeware API

Sources: `badger/home` `badge/AGENTS.md` and `badge/apps/`; see
[sources.md](sources.md). Confirm version-specific APIs on the badge's REPL
(`mpremote connect PORT exec "print(dir(badge))"`) before relying on them.

## Runtime globals

The U26 runtime supplies common graphics and badge APIs as globals. New apps
normally import only `State` from `badgeware` when they need saved data:

```python
from badgeware import State
```

Other imports used by `badger/home` apps include `badgeware.link` in Contacts
and Pong, and `get_backlight`/`set_backlight` in Settings. They are
firmware-specific helpers; inspect the matching implementation before using
them. The validator recognizing a name does not prove its signature.

Common runtime globals include `badge`, `screen`, `image`, `font`, `color`,
`shape`, `brush`, `vec2`, `rect`, `mat3`, `run`, button constants, display mode
constants, and filesystem helpers. Do not use the legacy 2025 imports such as
`io`, `PixelFont`, `Image`, `brushes`, or `shapes` for new U26 apps.

## App setup and frame loop

Set the app directory before importing local modules or loading app-relative
assets. Start the app loop at module level:

```python
import os
import sys

APP_DIR = "/system/apps/my_app"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

def update():
    screen.pen = color.rgb(20, 24, 28)
    screen.rectangle(screen.clip)

run(update)
```

Do not guard `run(update)` with `if __name__ == "__main__"`; the firmware loads
the app through `launch()`.

## Input and timing

Use the orientation-aware logical actions. Firmware maps physical buttons and
capacitive controls to the same actions:

```python
if badge.pressed(BUTTON_SELECT):
    activate()

if badge.held(BUTTON_LEFT):
    x -= speed * (badge.ticks_delta / 1000)

if badge.released(BUTTON_BACK):
    close_panel()

if badge.touched(BUTTON_MENU):
    show_touch_feedback()
```

Actions are `BUTTON_UP`, `BUTTON_DOWN`, `BUTTON_LEFT`, `BUTTON_RIGHT`,
`BUTTON_SELECT`, `BUTTON_BACK`, `BUTTON_MENU`, and `BUTTON_HOME`. HOME is
launcher-owned. For diagnostics, `badge.pressed()`, `badge.held()`, and
`badge.released()` return sets of current actions. `badge.direction()` returns
a direction vector; `badge.upside_down()` reports physical orientation.

- `badge.ticks`: milliseconds since boot.
- `badge.ticks_delta`: milliseconds since the prior frame.
- `badge.imu()` returns raw accelerometer and gyroscope values as
  `(ax, ay, az, gx, gy, gz)`. The current badge examples scale the
  accelerometer values by `16384` to estimate Gs. Use short samples, filtering,
  thresholds, and cooldowns for motion gestures; do not treat one raw sample as
  a reliable gesture.

Use `badge.ticks_delta` for frame-rate-independent movement and animation.

## Screen, drawing, images, and fonts

Most apps use a 160x120 logical drawing surface. Use `screen.width`,
`screen.height`, and `screen.clip` rather than assuming fixed dimensions.
Apps that need the full display can request `badge.mode(HIRES | VSYNC)`.

```python
screen.pen = color.rgb(255, 255, 255)
screen.shape(shape.rounded_rectangle(8, 8, 80, 24, 4))
screen.text("Hello", 12, 12)

picture = image.load("assets/picture.png")
screen.blit(picture, vec2(10, 10))

sheet = image.load("assets/characters.png").spritesheet(7, 2)
screen.blit(sheet.sprite(0, 0), rect(40, 20, 32, 32))
```

Built-in fonts are available through `font`, for example `font.nope`,
`font.sins`, `font.ark`, and `font.ziplock`. Set `screen.font` before drawing
text and use `screen.measure_text(text)` for layout. Load static assets once;
keep their size and lifetime within the badge's memory limits.

## Persistent state and files

`State` is imported from `badgeware`. The checked implementation stores data
under `/state`, outside `/system`:

```python
state = {"highscore": 0}
State.load("my_app", state)

# Save after a meaningful state change.
State.save("my_app", state)
```

Use app-relative paths for app-owned assets and `/system/...` for deployed
system files. Never store credentials in an app or its saved state.

`State.load` can restore values with unexpected types. Validate loaded values
before using them. Test missing/corrupt state and failed saves on the target.

## Hardware-specific APIs

Use regular MicroPython imports for supported modules. Hardware APIs for the
IMU, IR, wireless, GPIO, LEDs, and expansion hardware can depend on firmware
and board wiring. Check current `badger/home` source and examples before using
them. Static validation does not provide the U26 runtime; verify behavior on the
physical badge.

App patterns in `badger/home` include `wifi` with `fetch.url(...).to(...)`
(`apps/iss`, `apps/badge`), `badgeware.link` for badge-to-badge interaction
(`apps/contacts`, `apps/pong`), and `badge.caselights(...)` with cleanup
(`apps/brattal`). Read those apps for exact usage and never block the frame
loop. To list the apps on a connected badge, run
`python3 scripts/inventory_badge_apps.py --mount /Volumes/BADGER`.
