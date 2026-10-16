# U26 app structure and lifecycle

Sources and firmware differences: [sources.md](sources.md). Use the inspected
event firmware for menu behavior, not the older menu in `badger/home`.

## Directory contract

```text
badge/apps/<app-name>/
├── __init__.py
├── icon.png
└── assets/
```

- `__init__.py` is required. The menu discovers directories that contain it or
  `__init__.mpy`.
- `icon.png` is an optional 24x24 preview image. Custom app menu icons are not
  supported yet on current event firmware. Changing this file does not change
  the badge menu, which uses a built-in icon map and a generic fallback.
- Do not change menu/firmware files or borrow an existing app name to work
  around this limit. Images drawn inside an app remain supported.
- `assets/` is optional and may contain PNGs, PPF fonts, JSON, or other app data.
- App names should be lowercase path-safe identifiers. Menu label formatting
  depends on firmware; the inspected event menu capitalizes underscore-separated
  words. Set the requested display title inside the app.
- Do not deploy over `menu` or `startup`. Hidden-app rules such as `vault`
  belong to particular older menus, not the general U26 app contract.

## Lifecycle

The firmware launches an app module with `launch()`. Set the app directory
before importing local modules or opening relative asset paths. Define
`update()` and start the frame loop with a module-level `run(update)` call:

```python
import os
import sys

APP_DIR = "/system/apps/my_app"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

def update():
    draw()

run(update)
```

Do not put `run(update)` behind an `if __name__ == "__main__"` guard. The
firmware loads the app module through `launch()`, so the app must start its
frame loop while that module runs. Define `on_exit()` at module level when
hardware or other resources need cleanup. Ordinary apps should not call
`launch()` themselves; return an app path from `update()` only when acting as a
launcher.

`update()` may return a `/system/apps/<name>` path to launch another app. Normal apps should usually return `None`.

## Paths and imports

- Repository `badge/` maps to `/system/` on the device.
- Use `/system/apps/<app>/...` and `/system/assets/...` for deployed absolute paths.
- Relative paths resolve from the app directory after launch and work well for app-owned assets.
- Local modules such as `ui.py` or `player.py` may be imported by module name.
- Avoid host-specific paths.

## Persistent data

Persistent state is outside `/system`; `/system` is the mass-storage application
tree. The checked `State` implementation uses `/state/<app>.json`. Do not
assume state files are visible on the BADGER USB drive.

Load saved state during module setup:

```python
from badgeware import State

state = {"score": 0}
State.load("my_app", state)

def on_exit():
    State.save("my_app", state)
```

Or write a uniquely named root file such as `/my_app.json`. Supply defaults, validate loaded values, and tolerate missing data. Do not store credentials in app state.

## Frame loop rules

- Use `badge.pressed(action)` for one-shot actions and `badge.held(action)` for
  continuous actions.
- Use `badge.released(action)` or `badge.touched(action)` when those transitions
  matter.
- Use `badge.ticks` or `badge.ticks_delta` for timing.
- Use timestamps/state machines instead of long sleeps or blocking loops.
- Render a complete coherent frame on every update unless intentionally
  retaining an offscreen image.
- Bound lists, queues, particles, cached responses, and histories.
- Keep network and BLE work incremental so input and HOME remain responsive.

U26 input names are logical and remain consistent when firmware changes screen
orientation: UP, DOWN, LEFT, RIGHT, SELECT, BACK, MENU, and HOME. The launcher
owns HOME. Do not use the old A/B/C control names in new U26 apps.

## Launcher compatibility

- The launcher owns HOME and starts apps through `launch()`.
- Shared module state may remain between apps; avoid relying on another app's
  imported module state.
