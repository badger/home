# U26 capability guide

Classify the request before choosing code. Every feature needs source evidence
and an acceptance check. Follow [sources.md](sources.md) for source order.

| Capability | Evidence to inspect | What still needs a real badge |
|---|---|---|
| Buttons and controls | `badge.pressed`, `held`, `released`, logical constants | Orientation, hold timing, HOME |
| Timing and animation | `badge.ticks`, `badge.ticks_delta`, short updates | Frame rate, long-run stability |
| Motion and tilt | `badge.imu`, `direction`, orientation helpers | Filtering, thresholds, false triggers |
| Saved state | `State.load`, `State.save`, value validation | Reset/reopen persistence and failed saves |
| Images and sprites | `image.load`, app assets, `screen.blit` | Drawing result, decode time, memory |
| Display modes | `badge.mode`, dimensions, LORES/HIRES | Actual layout, rotation, frame time |
| Wi-Fi and network | `wifi`, `fetch`, matching cache patterns | Timeout, retry, missing credentials |
| Bluetooth and badge link | `badgeware.link`, current Contacts/Pong | Real peers, reconnect, cleanup |
| IR | U26 schematic and a matching driver/protocol example | GPIO16 TX/GPIO17 RX, range, duplicates |
| Lights and battery | Current Settings, Brattal, and battery helpers | Brightness, power, charging, cleanup |
| Storage | Small `/state` data; app-relative read assets | Capacity, corruption, reset behavior |
| Expansion hardware | U26 schematic and supported device driver | Voltage, bus, pins, timing |
| Menu icon | App `icon.png`, [menu-icons.md](menu-icons.md) | Menu shows it (stock firmware needs the patch) |
| Simulator fit | [simulator.md](simulator.md) | Anything using sockets, Bluetooth, IR, camera, `.mpy` |

The validator checks Python syntax, selected imports, callback structure,
literal image paths, and PNG integrity. It does not resolve every runtime name,
prove non-blocking behavior, validate a protocol, measure real memory, or test
layout. Its image-memory warnings are estimates, not firmware limits.

List each requested feature, pick the smallest verified pattern, and state
which checks are static, physical, or uncertain. Do not infer support from an
app name alone.
