# Installed U26 app evidence

This is a pattern guide from readable event-badge source, not a universal
installed-app list or a complete API definition. See [sources.md](sources.md)
for versions and evidence. Use the host-specific inventory command in
`SKILL.md` to list files on another BADGER volume.

| App on the inspected badge | Useful evidence | Important caution |
|---|---|---|
| `badge` | IMU tilt smoothing, `wifi`, `fetch.url(...).to(...)`, cache, images | Inspect helper modules and bound downloads |
| `flappy_mona` | Intro/play/game-over, sprites, saved score | Verify imports and paths before reuse |
| `life` | Press/hold/release timing, HIRES, bounded buffers | Uses MicroPython-specific performance features |
| `mona_paint` | Filtered tilt, LORES, image buffers, `/state` files | Check memory and restore orientation on exit |
| `settings` | Forms, `get_backlight`/`set_backlight`, display modes | Settings are system-owned; inspect rather than replace |
| `brattal` | Autorotation, `badge.caselights`, cleanup | Real light/power behavior needs a badge |
| `mona_pet` | Multiple modules, assets, saved progression | Inspect each helper and state format |
| `snake` | HIRES steering, elapsed time, bounded geometry | Not the legacy grid Snake example |
| `iss` | Wi-Fi state machine, requests, map rendering, cache | Do not assume a request is non-blocking |
| `contacts` / `pong` | `badgeware.link`, saved data, peer interaction | Not the legacy raw-BLE/browser contract; test with real peers |
| `menu` | Discovery, built-in icon mapping, generic fallback | Read only; no supported custom menu icon upload |

## Evidence rules

- Prefer readable `.py` source over compiled `.mpy`.
- Read only app source and necessary public assets. Do not copy credentials,
  contact payloads, or saved user data into a skill.
- Inspect a helper's implementation before reusing its calls.
- For an unknown API, verify matching firmware source or state what is unknown.
- Keep the generated inventory as a snapshot. A filename alone does not prove
  the app's behavior or firmware compatibility.

## Menu icons

The inspected menu imports `ICONS` and selects by app folder name, falling
back to `default`. The readable generated map is `apps/menu/src/icons.py`.
It does not read app-local `icon.png`. Custom app menu icons are not supported
yet on this event firmware; keep the PNG only as an optional preview image.
Do not modify firmware/menu files or borrow an existing folder name to bypass
this limit. In-app artwork remains a separate feature.
