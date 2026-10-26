# Choosing reference apps

Paths are in `badger/home` (`badge/apps/<name>`). They use the 2026 API.
Start with the smallest relevant app, then combine patterns. To see which
apps a particular badge has, list `/system/apps` over serial or run
`inventory_badge_apps.py --mount <BADGER>`.

| Need | Start from | What it shows |
|---|---|---|
| Every input API | `input_test` | Buttons, capacitive touch, `direction()`, IMU, HIRES |
| Drawing techniques | `demos` | Shapes, text, sprites, brushes, transforms |
| Small game loop | `plucky_cluck`, `flappy` | `ticks_delta` movement, sprites, collision, states |
| Grid game | `snake`, `life` | Timed steps, simple state |
| Turn-based game | `rogue` | Larger state machine |
| Drawing with tilt | `mona_paint` | IMU input, offscreen image, undo |
| Images | `gallery` | Loading and browsing PNGs |
| Saved state | `clock`, `contacts` | `State.load` / `State.save` |
| Wi-Fi and HTTP | `iss`, `badge` | Credentials, fetch, JSON, cached files |
| Qw/ST I2C sensor | `sense` | External sensor on the expansion bus |
| Badge-to-badge link | `contacts`, `pong`, `merge_conflict` | `badgeware.link` pairing and messages |
| IR | `quest` | NEC receiver and beacons |
| Case lights | `brattal`, `tomato` | `badge.caselights(...)` and cleanup |
| Settings and backlight | `settings` | `get_backlight` / `set_backlight` |
| Timers | `tomato` | Long-running countdown UI |
| Launcher | `menu` (read only) | Discovery, icons, launching apps |
| USB Disk Mode | `mass_storage` | `powman.reset_into_msc()` |

Notes:

- Link (Bluetooth) apps need two physical badges to test.
- Network apps need Wi-Fi credentials in the badge's `secrets.py` (set
  through the Settings app or by the user; never commit or print it).
- `badge25/` apps use the 2025 API. Port them with the table in
  `badge/AGENTS.md` instead of copying.
- Broad `except` blocks in examples are not a best practice; catch expected
  errors and show the user a way to recover.
