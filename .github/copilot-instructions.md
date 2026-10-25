# Copilot instructions for GitHub Universe badge development

The repository targets the **GitHub Universe 2026 badge** by default.

- Work in `badge/` for current firmware and applications.
- Read `badge/AGENTS.md` before changing a 2026 app.
- Read `hardware/README.md` before using raw GPIO, I2C, ADC, IR, power,
  wireless, display, touch, switch, or interrupt hardware.
- Read `hardware/USB_SERIAL.md` before communicating with a connected badge or
  modifying its filesystem.
- `badge25/` is the preserved Universe 2025 source tree. Read
  `badge25/AGENTS.md` only when intentionally maintaining that badge.
- `badge25/simulator/` and `badge25/badgerware/` document the legacy 2025
  runtime and must not be treated as authoritative for 2026 apps.

## Universe 2026 essentials

- The RP2350B firmware supplies `badge`, `screen`, `image`, `font`, `color`,
  `shape`, `brush`, `vec2`, `rect`, `mat3`, `run`, button constants, display
  mode constants, and filesystem helpers as globals.
- Prefer orientation-aware logical actions such as `BUTTON_SELECT`,
  `BUTTON_LEFT`, and `BUTTON_RIGHT`.
- Read input with `badge.pressed()`, `badge.held()`, `badge.released()`, and
  `badge.touched()`.
- Use `badge.ticks` and `badge.ticks_delta`; movement must be frame-rate
  independent.
- Draw with `screen.pen`, `color.rgb()`, `screen.shape()`, and
  `screen.blit()`.
- Load sprites with `image.load(path).spritesheet(columns, rows)`.
- Use `screen.width` and `screen.height`; HIRES mode is 320x240 and the common
  logical mode is 160x120.
- Keep `badge/secrets.py` empty in source control.
- New apps need `badge/apps/<name>/__init__.py`, a 24x24 `icon.png`, and a
  `README.md` whose first paragraph is a one-sentence description of the app
  (followed by usage and any hardware or network requirements). The
  `Validate app READMEs` check fails pull requests without one.
- Use `mpremote devs` to discover a connected badge, then explicit
  `mpremote connect <port> ...` commands. Never run concurrent serial commands:
  only one process can own the USB serial port.
- Remote filesystem paths in `mpremote fs` commands begin with `:`. The normal
  REPL mounts `/system` read-only; use a host mount for transient tests or USB
  mass-storage mode to deploy under `/system/apps/`. Inspect state under
  `:/state/`, and reset after copying so the normal startup path is exercised.

## Testing apps in the Badge Simulator canvas

This repository ships a **Badge Simulator** canvas in
`.github/extensions/badge-simulator/` (see its `README.md`). When creating,
changing or testing an app, open it beside the conversation with
`open_canvas` using `canvasId: "badge-simulator"` and
`input: { "app": "<folder under badge/apps>" }`.

- It reruns the app automatically whenever files in `badge/apps/<app>` change,
  so save edits and check the result without reopening it.
- Use `invoke_canvas_action` to verify behavior: `get_output` returns console
  output and tracebacks, `screenshot` returns a PNG path to view, `press`
  presses a badge button (`up`, `down`, `left`, `right`, `select`, `home`,
  `back`, `menu`), `load_app` switches apps and `reload` reruns.
- The canvas **Deploy** button sends a request to install the app on the
  connected badge. Handle it by following `hardware/USB_SERIAL.md`
  ("Installing an app", including "Menu icon patch"): always use USB
  mass-storage mode for `/system/apps/<app>`, apply the patched menu `app.py`
  when the badge's menu lacks it, and run one `mpremote` command at a time.
- The simulator approximates the firmware; still test on real hardware.

When porting a 2025 app, preserve behavior and assets but explicitly translate
the graphics, input, timing, orientation, lifecycle, and state APIs. Use
`badge/apps/input_test/`, `badge/apps/demos/` and `badge/apps/flappy_mona/` as primary references.
