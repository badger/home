# Choosing repository examples

Use the smallest relevant examples first, then combine patterns.
The paths below refer to `badger/badgerfactory`, not necessarily the user's
project. Prefer the current target's examples in `device-app-inventory.md`.

| Need | Best starting point | What it demonstrates |
|---|---|---|
| Minimal screen | `badge/apps/hello` | Basic font, clear, measure, centered text |
| Launcher integration | Target badge `apps/menu` and `main.py` | Discovery, built-in icon mapping, app switching, HOME; read only |
| Button-driven game | `badge/apps/snake` | Grid state, pressed controls, timed updates |
| Physics/collision game | `badge/apps/flappy` | State machine, sprites, delta time, collision, parallax |
| More complex game | `badge/apps/commits` | Intro/play/win/game-over, continuous controls, many objects |
| Offscreen drawing | `badge/apps/sketch` | Writable `Image`, clipping/window concepts, held controls |
| Images and browsing | `badge/apps/gallery` | Directory listing, thumbnails, smooth transitions |
| Persistent simulation | `badge/apps/monapet` | Saved state and cleanup patterns; translate its legacy API |
| Battery display | `badge/apps/vault`, `badge/apps/menu/ui.py` | Battery level and charging status |
| Wi-Fi/API basics | `badge/apps/badge` | Credentials, WLAN, streamed download, JSON, cached files |
| Robust network UI | `badge/apps/contributions` | Cached content, background refresh, multiple views |
| Long-running network display | `badge/apps/marquee` | Incremental backend, NTP/timezone, settings, LEDs, charging |
| IR receive | `badge/apps/quest` | NEC receiver, descriptor, persistent completion |
| BLE peripheral/browser | `badge/apps/contacts` and `contacts-editor` | GATT service, Web Bluetooth, chunked JSON, persistent data |
| BLE peer game | `badge/apps/pong` | Advertising, scanning, connection, notifications, cleanup |
| Startup/frame animation | `badge/apps/startup` | `screen.load_into`, frame sequence, explicit display update |

## Pattern selection

- Start with `hello` for a static informational app.
- Start with `snake` or `flappy` for games; do not copy a large app when a small loop suffices.
- Start with `monapet` for saved preferences or progression.
- Start with `badge` for a single network request and `marquee` for resilient repeated background data.
- Start with `contacts` only for BLE peripheral/Web Bluetooth behavior.
- Start with `pong` for direct badge-to-badge BLE behavior.
- Start with `quest` for IR.

## Important differences

- Many apps in `badger/badgerfactory` use the legacy 2025 API. Use them as examples of
  behavior or game structure, but translate their imports, graphics, controls,
  timing, and lifecycle to the U26 API in `badgeware-api.md`.
- BLE apps require a physical two-badge test.
- Marquee's LED writes require physical badge verification.
- New U26 apps call `run(update)` at module level without a `__main__` guard.
- Custom app menu icons are not supported yet on current event firmware.
  `icon.png` is an optional 24x24 preview image, not a menu icon upload.
  Do not change the menu or rename an app to borrow a built-in icon.
- Existing broad exception handling is not automatically a best practice. Catch expected failures narrowly and give the user a visible recovery path.
