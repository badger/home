# U26 app structure and lifecycle

Source: `badger/home` `badge/AGENTS.md`. See [sources.md](sources.md).

## Directory contract

```text
badge/apps/<app-name>/
├── __init__.py
├── icon.png
├── README.md
└── assets/
```

- `__init__.py` is required. The menu discovers directories that contain it or
  `__init__.mpy`.
- `icon.png`: square PNG, 24x24 minimum, 48x48 looks sharpest. The menu
  falls back to its default icon without one. Stock event firmware needs the
  menu icon patch to show it; see [menu-icons.md](menu-icons.md).
- `README.md` is required in `badger/home`. Its first paragraph after the
  title is one plain sentence (10-200 characters, ending in `.`, `!`, or `?`)
  describing the app. Follow it with usage and any hardware, Wi-Fi, or
  `secrets.py` requirements. Check with
  `python .github/scripts/validate_app_readmes.py badge/apps`.
- `assets/` is optional and may contain PNGs, PPF fonts, JSON, or other app data.
- App names should be lowercase path-safe identifiers. The menu capitalizes
  underscore-separated words for its label. Set the display title in the app.
- Do not deploy over `menu` or `startup`.

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
