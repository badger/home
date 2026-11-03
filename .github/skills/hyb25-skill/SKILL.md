---
name: hyb25-skill
description: Build, debug, and deploy GitHub Universe 2025 Tufty badge apps. Identify the older Badgeware firmware, use its A/B/C buttons and graphics API, test with the archived Pygame simulator, and install safely through USB Disk Mode. Do not use this skill for Universe 2026 apps.
compatibility: Physical badge access requires mpremote and a data-capable USB-C cable. The optional repository simulator requires Python 3.10+ and Pygame. USB workflows support macOS, Linux, and Windows.
license: MIT
metadata:
  summary: Build apps for the Universe 2025 badge without mixing in 2026 APIs.
  status: active
---

# HYB25-skill

Help the user build and test apps for the GitHub Universe 2025 badge. Use plain
language. Keep the 2025 and 2026 software separate. A simulator can help with
layout, but only a real badge can confirm hardware behavior.

## Identify the badge first

1. Run `mpremote devs`. Select the badge explicitly for every serial command.
   Never run serial commands in parallel.
2. The tested 2025 badge identifies as USB `2e8a:0005`, product
   `GitHub Badger MicroPython`. The tested 2026 firmware uses `2e8a:1101`.
   Names and IDs are clues, not sufficient proof of app compatibility.
3. Read the firmware and available tools before writing anything:

   ```bash
   mpremote connect PORT resume exec "import sys; print(sys.version)"
   mpremote connect PORT resume exec "import badgeware; print(dir(badgeware)); print(badgeware.screen.width, badgeware.screen.height); print(dir(badgeware.io))"
   ```

4. The tested 2025 firmware reports
   `MicroPython v1.14-5485.gddae88e91.dirty on 2025-10-20`. It provides
   `badgeware.screen`, `PixelFont`, `Image`, `brushes`, `shapes`, and
   `io.BUTTON_A/B/C/UP/DOWN/HOME`, with a 160x120 drawing surface.
   Do not require that exact build string on other badges.
5. If results are missing, mixed, or inconsistent, stop before deployment and
   ask which firmware the user intends to use. Do not flash to resolve a
   detection problem.

`mpremote` may interrupt the running app. `resume` skips its initial soft reset;
it does not allow the app to keep running during a command. Reset afterwards
to restore normal startup. See [USB and recovery](references/usb.md), including
the older firmware's import and raw-REPL issues.

## Sources of truth

Use the connected badge first, then these files in a `badger/home` checkout:

- `badge25/AGENTS.md` and `badge25/README.md` for archived guidance.
- `badge25/main.py` for the real app startup sequence.
- `badge25/badgerware/` for input, images, fonts, brushes, and shapes.
- `badge25/apps/menu/`, `snake/`, and `flappy/` for examples.
- `badge25/simulator/README.md` for the optional 2025 simulator.

Read `badge25/AGENTS.md` before changing a 2025 app. Treat old examples as
evidence to check, not as instructions to copy without review. If the badge
and repo differ, explain the difference and follow the installed firmware.
If these repo files are unavailable, ask for a checkout or inspect the
badge's matching files; do not substitute the 2026 tree.

Do not use `badge/`, the 2026 Badge Simulator canvas, or
`hyb26-skill/scripts/` to generate, validate, patch, or deploy 2025 apps.
The 2026 menu patch and firmware are not 2025 updates.

## Plan the app

Agree on screens, controls, assets, saved data, and any network or accessory
needs. Ask only about choices that materially affect the behavior.

Prefer the existing app structure and standard `mpremote` tools over new
helpers. Do not change firmware or replace the launcher as part of an ordinary
app task. A stock menu change needs its own explanation, backup, and approval.

## Build

Use `badge25/apps/<lowercase_name>/` in this repository, or an app folder in
the user's own project. Never put app files inside the skill folder.

Each app needs:

- `__init__.py` with `update()` and optional `init()` and `on_exit()`.
- A 24x24 PNG `icon.png` for the 2025 menu.
- `README.md`: begin with a one-sentence description, then explain controls,
  requirements, and how to test.
- Optional app-local `assets/`.

The installed launcher imports the app, calls `init()`, then runs `update()`.
**Do not call `run(update)` unconditionally at module level.** That is a 2026
pattern and bypasses the 2025 launcher's initialization. For direct execution,
use `if __name__ == "__main__": run(update)`. See the complete
[app contract and starter](references/app-contract.md).

Use explicit imports from `badgeware`:

- Input: `io.BUTTON_B in io.pressed`, not `badge.pressed(BUTTON_SELECT)`.
- Timing: `io.ticks` and `io.ticks_delta`; use elapsed time for movement.
- Colors: `screen.brush = brushes.color(r, g, b)`.
- Shapes: `screen.draw(shapes.rectangle(x, y, width, height))`.
- Fonts: `PixelFont.load("/system/assets/fonts/nope.ppf")`.
- Images: `Image.load(path)` and `screen.blit(picture, x, y)`.
- Scaling: `screen.scale_blit(picture, x, y, width, height)`.
- Text size: `width, height = screen.measure_text(text)`.

Use `screen.width` and `screen.height`. Keep HOME for the launcher. Default
menu controls are A/C for previous/next, UP/DOWN for rows, and B to select.
Do not assume the 2026 touch controls, automatic orientation, HIRES mode,
IMU, pin map, `screen.pen`, or runtime-provided graphics globals exist.

Load assets once, prefer paletted PNGs, and keep frame work short. Use
app-relative assets because the launcher changes to the app directory.
Check the installed fonts rather than assuming a font is present.

For saved data, use a unique location in writable storage, as described in
the app contract. Do not assume a 2026 `State` signature or `/state` layout.
Never read out, commit, or deploy filled `secrets.py` files.

The 2026 `hardware/README.md` is not a 2025 pin map. Before raw GPIO, IR,
I2C, ADC, power, or display work, verify a 2025 hardware source and matching
firmware driver or board aliases. Do not infer wiring from the chip name.

## Test and install

1. Check syntax without running the app on the host. Check imports, lifecycle,
   icon dimensions, assets, secrets exclusions, and controls against this
   skill. Desktop syntax checks do not prove MicroPython compatibility.
2. Optionally run the archived simulator from the app directory:

   ```bash
   (cd badge25/apps/my_app && python3 ../../simulator/badge_simulator.py -C ../.. .)
   ```

   It requires Pygame. Keys A/Z, B/X, C/Space, Up/Down, and H/Esc simulate
   controls; H/Esc returns to the menu. Network and IR behavior is simulated,
   not hardware validation. See `badge25/simulator/README.md`.
3. Follow [USB installation](references/usb.md). Inspect the installed menu
   before copying. The stock 2025 menu has six hard-coded apps; copying a new
   folder alone does not add a visible tile. The repo's archived menu differs.
4. Copy only the requested app, preserving existing files and secrets.
   Back up an existing app before replacing it. Flush and eject, wait for
   serial to return, and reset into the normal launcher.
5. On the badge, check the app's tile and icon, launch, all controls, HOME,
   reopen, reset, saved data, and relevant failure cases. Ask the user to
   confirm visual or physical checks that cannot be observed remotely.

Never describe a successful copy as a successful on-badge test. Report what
was actually checked and what remains unverified. If no badge is available,
give a specific hardware checklist instead.
