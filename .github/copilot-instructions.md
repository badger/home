## Copilot instructions for the Badger repository

This file is a compact, practical guide for AI coding agents to be productive in this repo.
Keep changes minimal and always prefer working on app entrypoints under `/system/apps/`.

### Big picture (what runs where)
- Runtime: MicroPython (RP2350) with a custom "badgeware" library (MicroPython 1.24+ expected).
- Launcher: `badge/main.py` (the device `main.py` copies `/system/main.py` on first run) boots a startup cinematic, then the `menu` app and finally the selected app.
- Apps live in `/system/apps/<app_name>/` and must expose an `update()` function. `init()` and `on_exit()` are optional.
- Logical framebuffer: 160×120 (pixel-doubled to 320×240 on the physical display). Use this coordinate space for layout.

### App structure & conventions (concrete)
- Required files: `/system/apps/<app>/__init__.py` (entrypoint) and `icon.png` (24×24). `assets/` is optional.
- At app launch the app's `assets/` path is automatically inserted into `sys.path` — load assets with relative paths like `"assets/sprite.png"` or `/system/assets/...`.
- At the end of `__init__.py` call `run(update)` to start the per-frame loop (see `badge/main.py`).

Example minimal `__init__.py` snippet:

```python
screen.font = PixelFont.load("nope.ppf")
def update():
    screen.brush = brushes.color(0,0,0); screen.clear()
    screen.text("hi", 10, 10)

run(update)
```

### Key APIs & runtime patterns to reference
- `badgeware.screen` — primary Image (width=160, height=120). Use `screen.brush`, `screen.clear()`, `screen.text()` and `screen.blit()`.
- `badgeware.io` — input and timing. Use `io.pressed`, `io.held`, `io.released`, `io.ticks`, `io.ticks_delta`.
- Drawing: `brushes`, `shapes`, `Matrix`, `SpriteSheet`, `PixelFont` — these are the idiomatic building blocks (see `badge/AGENTS.md` and `README.md`).
- Avoid CPU-heavy Python features; prefer frame-friendly incremental updates and rely on `io.ticks_delta` for time-based motion.

### Developer workflows and device tips (explicit)
- Edit live on the device: plug in USB-C, double-tap RESET to mount the FAT32 `/system` volume named `BADGER`.
- Flash firmware: drop a `.uf2` on the `RP2350` drive (follow steps in `README.md` / releases).
- Secrets: `badge/secrets.py` contains WiFi/GitHub defaults — do not commit personal secrets. Prefer editing on-device or use environment-controlled workflows.

### Project-specific conventions
- Coordinate space uses logical 160×120; many helper functions and examples assume that.
- Fonts are pixel-font `.ppf` files under `/system/assets/fonts/` — prefer `PixelFont.load("nope.ppf")` for compatibility.
- `assets/` are bundled per-app; sprite sheets live in `/system/assets/mona-sprites/` in this repo.
- Many example apps set `screen.antialias = Image.X2` or `Image.X4` when drawing vector shapes — mimic that when you need smoothing.

### Integrations & external APIs
- Network (WiFi) and Bluetooth should use MicroPython's `network` and `bluetooth` libs; the device includes those in firmware — see `README.md` links.
- IR, LED zones, and power management are available via badge-specific modules (see `badge/AGENTS.md` for pin constants and `powman` usage).

### Guidance for automated edits (Do / Don't)
- DO: update or add small app `__init__.py` files, add assets under an app's `assets/` directory, and update icons.
- DO: use `io.ticks`/`io.ticks_delta` for timing and keep per-frame workloads small.
- DO NOT: add heavyweight CPython-only dependencies or assume full stdlib availability — test on-device.
- DO NOT: commit personal credentials from `badge/secrets.py`.

### Primary references
- `badge/AGENTS.md` — canonical, detailed guidance and examples for LLMs and developers (use liberally).
- `badge/main.py` and `/system/main.py` — shows the launcher/app lifecycle and `run()` usage.
- `README.md` (repo root and `eink/README.md`) — device-flash and editing workflows.

### CI quick checks
- This repo includes a lightweight quick-checks script at `scripts/quick_checks.py` and a GitHub Action that runs it on PRs.
- The action will post a comment on the PR with the script output when checks fail. Use this script locally to catch structural issues before opening a PR.

If any of these sections are unclear or you want more examples (e.g., animation timing, SpriteSheet usage, or file I/O patterns), tell me which area to expand and I will iterate.

If any of these sections are unclear or you want more examples (e.g., animation timing, SpriteSheet usage, or file I/O patterns), tell me which area to expand and I will iterate.
