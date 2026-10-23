---
name: hyb26-skill
description: Build, debug, validate, and deploy GitHub Universe 2026 badge apps. Covers the 2026 firmware API, mpremote and the MicroPython REPL, forcing USB Disk Mode, safe app copying, custom menu icons, the badger.github.io simulator, and physical badge testing.
compatibility: Requires Python 3.10+ for bundled tools. Talking to a badge needs mpremote and a data-capable USB-C cable. Works on macOS, Linux, and Windows.
license: MIT
metadata:
  summary: Turn an app idea into a tested Universe 2026 badge app.
  status: active
---

# HYB26-skill

Help the user build an app for the GitHub Universe 2026 badge and get it
running on their own badge. Use plain language. A physical badge is always the
preferred test target; the browser simulator is a convenience, not proof.

## Sources of truth

Work in this order and say when sources disagree:

1. The user's connected badge (read its files over USB serial or USB Disk Mode).
2. `badger/home`: `badge/AGENTS.md`, `hardware/USB_SERIAL.md`,
   `hardware/README.md`, and the reference apps in `badge/apps/`.
3. The `badger/badger.github.io` simulator and docs (`/editor`, `/apps`).

Never use `badge25/` (Universe 2025) APIs in a 2026 app. When working inside a
`badger/home` checkout, read `badge/AGENTS.md` before changing an app. Details:
[references/sources.md](references/sources.md).

## Tools

Set `scripts` to this skill's `scripts` folder, then run tools from the user's
badge project folder (a plain folder works; Git is optional).

macOS / Linux (Terminal):

```bash
scripts=".github/skills/hyb26-skill/scripts"          # inside a repository
scripts="$HOME/.copilot/skills/hyb26-skill/scripts"   # personal install
python3 "$scripts/scaffold_app.py" my_app --title "My App" --description "My App shows a friendly greeting."
python3 "$scripts/validate_app.py" badge/apps/my_app
python3 "$scripts/badge_serial.py" info
python3 "$scripts/badge_serial.py" disk-mode
python3 "$scripts/patch_menu_icons.py"
python3 "$scripts/deploy_app.py" badge/apps/my_app
python3 "$scripts/deploy_app.py" badge/apps/my_app --write
python3 "$scripts/badge_serial.py" eject
```

Windows (PowerShell):

```powershell
$scripts = ".github\skills\hyb26-skill\scripts"            # inside a repository
$scripts = "$HOME\.copilot\skills\hyb26-skill\scripts"     # personal install
python "$scripts\scaffold_app.py" my_app --title "My App" --description "My App shows a friendly greeting."
python "$scripts\validate_app.py" badge\apps\my_app
python "$scripts\badge_serial.py" info
python "$scripts\badge_serial.py" disk-mode
python "$scripts\patch_menu_icons.py"
python "$scripts\deploy_app.py" badge\apps\my_app
python "$scripts\deploy_app.py" badge\apps\my_app --write
python "$scripts\badge_serial.py" eject
```

`deploy_app.py` and `patch_menu_icons.py` preview by default; add `--write`
only after reviewing the output. `deploy_app.py --replace` updates an existing
app and keeps a backup in `.badge-app-backups`. Use `--repo-root` (or
`--apps-dir` for scaffolding) to choose a project explicitly. Never use the
skill folder itself as the app project.

## Set up the computer

1. Python 3.10+.
2. `python3 -m pip install mpremote` (Windows: `python -m pip install mpremote`).
   Use a virtual environment if the system Python refuses packages.
3. Connect the badge with a data-capable USB-C cable and run `mpremote devs`.
   The badge is USB `2e8a:1101` ("GitHub Badger 2350 MicroPython" on stock
   firmware, "Pimoroni Tufty 2350 MicroPython" on some builds;
   `/dev/cu.usbmodem*` on macOS, `/dev/ttyACM*` on Linux, `COMn` on Windows).
   `badge_serial.py port` picks it out for you.

Full serial guide: [references/usb-serial.md](references/usb-serial.md).

## Talk to the badge (REPL)

```bash
mpremote connect PORT repl                       # interactive; Ctrl-] exits
mpremote connect PORT exec "import os; print(os.listdir('/system/apps'))"
mpremote connect PORT run probe.py               # run a local script once
mpremote connect PORT fs ls :/system/apps        # remote paths start with ':'
mpremote connect PORT reset
```

- Only one program can own the serial port. Never run serial commands in
  parallel; close Thonny, Web Serial tabs, `screen`, and other `mpremote`s.
- Connecting interrupts the running app and normally soft-resets it.
- `/system` (apps) is read-only over serial (`EROFS`); `/state` and `/` are
  writable. Install apps through USB Disk Mode.
- `mpremote mount badge` exposes a local `badge/` folder at `/remote` for quick
  render tests; PNG streaming through the mount is unreliable.

## Get into USB Disk Mode

Any of these makes the BADGER volume appear:

- From the computer: `badge_serial.py disk-mode`, or
  `mpremote connect PORT exec "import powman; powman.reset_into_msc()"`.
- On the badge: open the **Mass Storage** app.
- Quickly double-tap RESET.

The repo's `badge/apps/mass_storage/__init__.py` reboots cleanly into disk mode
with `powman.reset_into_msc()` (stock event firmware ships the same app). If a
badge's Mass Storage app hangs or does not switch, double-tap RESET and copy the
repo version over
`apps/mass_storage/` (`deploy_app.py badge/apps/mass_storage --write --replace`
from a `badger/home` checkout). If `powman.reset_into_msc` is missing, the
firmware is too old for remote switching; use the double-tap.

`BADGER/apps` (or `BADGER/system/apps` on some firmware) is `/system/apps` on
the device. Never copy apps to the `RP2350` drive; that is the firmware
bootloader. Eject with `badge_serial.py eject`, which flushes, ejects, and
waits for the badge to come back. Windows Explorer's "error occurred while
ejecting" message is harmless: the badge reboots as soon as it gets the eject
request. If ejecting by hand, wait for BADGER to disappear; the badge normally
restarts into the menu by itself (press RESET if it does not).

## Custom menu icons

Each app should ship an `icon.png` (24x24 minimum, 48x48 square looks
sharpest). The menu in `badger/home` loads it for apps without a built-in icon,
but the stock event firmware menu ignores `icon.png`. Check with
`badge_serial.py info` (or look for `ICON_FILE` in `apps/menu/app.py`). If it
is missing, put the badge in USB Disk Mode and run `patch_menu_icons.py`, which
applies [Gadgetoid's menu icon patch](https://gist.github.com/Gadgetoid/f72b85e6efe603bd02b2b730bbc40356)
with a backup. Details: [references/menu-icons.md](references/menu-icons.md).

For every physical deployment, verify the icon end to end. Before copying,
confirm the app's `icon.png` is the newly created app icon, is square, and is
at least 24x24. After copying, confirm that same file exists in the installed
app directory on BADGER. Check that the installed menu supports custom icons;
if it does not, preview and apply `patch_menu_icons.py` before ejecting. After
the badge restarts, open the menu and visually confirm that the app tile shows
the app's icon instead of the default icon. Do not claim the icon works from
file checks alone.

## Design and build

Reduce the request to screens/states, controls, assets, saved data, timing,
memory, and acceptance checks. Ask only about assumptions that would change
the behavior substantially. Then:

1. Create `badge/apps/<name>/` with `__init__.py`, `icon.png`, and `README.md`
   (`scaffold_app.py` does this). Use lowercase path-safe names.
2. The README's first paragraph after the title is one 10-200 character
   sentence describing the app, followed by usage and any hardware, Wi-Fi, or
   `secrets.py` needs. `badger/home` pull requests fail without it.
3. Use the runtime globals (`badge`, `screen`, `image`, `font`, `color`,
   `shape`, `brush`, `vec2`, `rect`, `mat3`, `run`, `BUTTON_*`, `HIRES`).
   Do not `import badge`. Import `State` from `badgeware` for saved data.
4. Define `update()` and call `run(update)` at module level (no `__main__`
   guard). Keep frames short; move with `badge.ticks_delta`.
5. Use logical buttons (`BUTTON_UP/DOWN/LEFT/RIGHT/SELECT/BACK/MENU`) via
   `badge.pressed/held/released/touched`. HOME belongs to the launcher.
6. Use `screen.width`/`screen.height` (160x120 default, 320x240 with
   `badge.mode(HIRES | VSYNC)`).
7. Keep assets app-relative after `os.chdir("/system/apps/<name>")`. Load
   images once; prefer paletted PNGs and sprite sheets.
8. Read `hardware/README.md` before raw GPIO, I2C, ADC, IR, or power work.
9. Never put credentials in an app; never deploy or commit a filled
   `secrets.py`. Do not modify unrelated apps or system files.

References: [app-contract.md](references/app-contract.md),
[badgeware-api.md](references/badgeware-api.md),
[patterns.md](references/patterns.md), [examples.md](references/examples.md),
[capabilities.md](references/capabilities.md), [hardware.md](references/hardware.md).

## Test

1. `validate_app.py` (static checks only; `--target emulator` adds simulator
   warnings).
2. Optional quick look in the simulator at https://badger.github.io/editor
   ([references/simulator.md](references/simulator.md)). It cannot run
   sockets/Bluetooth/IR/camera or `.mpy` files and does not prove hardware
   behavior.
3. Deploy to the physical badge through USB Disk Mode, reset, and exercise
   every screen, control, HOME/re-open, saved state, and failure case
   ([references/physical-badge.md](references/physical-badge.md)).
   Include the end-to-end icon check: verify the installed app icon, verify
   menu support or apply the menu patch, and visually confirm the tile after
   restart.
4. To debug crashes, attach without resetting (`mpremote connect PORT resume
   repl`), open the app on the badge, and read the printed traceback. Probe
   APIs interactively with `exec`/`eval`.

## Definition of done

Report which checks actually ran: static validation, simulator, deployment,
and on-badge feature checks. If no badge was available, give a concrete
hardware checklist and say physical verification is still outstanding. Never
call an app hardware-verified because static checks passed.
