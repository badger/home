# HYB26-skill behavioral tests

Run these prompts with the project skill available. Review generated files and
commands; do not require a physical badge for cases that explicitly stop at a
hardware checklist.

For automated checks, run `python3 -m unittest discover -s tests -v` from the
skill folder (`python` on Windows).

## New app from an idea

**Prompt**

> Build a badge app that shows a conference countdown. LEFT/RIGHT changes the
> target day, SELECT saves it, and the choice should persist.

**Expected**

- Uses the skill.
- Inspects available, version-matched examples; does not assume repository
  apps exist in a plain project folder.
- Creates a path-safe app with `__init__.py`, `icon.png`, a `README.md` whose
  first sentence describes the app, and optional assets.
- Uses a 160x120 layout, U26 runtime globals, logical controls, `State`,
  module-level `run(update)`, and no desktop dependencies.
- Runs the validator and provides a physical-badge test command/checklist.

## Existing game improvement

**Prompt**

> Add a pause screen and saved high score to badge/apps/snake, then test it on
> the physical badge.

**Expected**

- Preserves the existing game loop and controls.
- Uses non-blocking state transitions and `State`.
- Runs focused validation and a physical-badge test.

## Hardware-only BLE app

**Prompt**

> Create a badge-to-badge voting app over Bluetooth.

**Expected**

- Uses current Contacts/Pong and their `badgeware.link` implementation as
  references, not legacy raw-BLE code without translation.
- Keeps IRQ work minimal and queues data for the main loop.
- Covers advertising, scanning, connect/disconnect, bounded packets, retry,
  cleanup, and `on_exit()`.
- Produces a concrete two-badge hardware test checklist.

## Wi-Fi app without credentials

**Prompt**

> Build a badge app that displays a JSON status endpoint but still does
> something useful offline.

**Expected**

- Uses root `secrets.py` without embedding or copying credentials.
- Implements timeout, failure, cached/offline, and incremental fetch behavior.
- Avoids loading an unbounded response into SRAM.
- Tests first-run behavior on the physical badge.

## Physical deployment

**Prompt**

> Put badge/apps/my-app on my connected badge.

**Expected**

- Confirms BADGER USB Disk Mode with either `apps` or `system/apps`; does not
  copy to RP2350 or silently choose between two app trees.
- Runs hardware-target validation.
- Runs deployment as a dry run first.
- Copies only `my-app`, never `secrets.py`.
- Requires explicit replacement and preserves a backup outside `system/apps`.
- Enters USB Disk Mode from the computer when the badge is on the menu.
- Verifies the newly created `icon.png` is installed, checks custom menu icon
  support, applies the menu patch when needed, and visually confirms the app
  tile shows that icon instead of the default icon after restart.
- Gives safe eject (`badge_serial.py eject`), HOME, persistence, and
  feature-specific test steps.

## Unsupported hardware assumption

**Prompt**

> Static validation passed for my GPIO sensor app, so mark it done.

**Expected**

- Rejects the premise that static validation proves GPIO behavior.
- Verifies the exact API against first-party sources.
- Identifies wiring, pin, voltage, driver, timing, and physical test needs.

## Custom menu icon request

**Prompt**

> Give my app a custom star icon in the badge menu.

**Expected**

- Creates a square `icon.png` (48x48 ideal, 24x24 minimum) in the app folder.
- Explains that apps named like built-in apps keep the built-in icon.
- Checks whether the badge menu loads `icon.png` (`badge_serial.py info` or
  `ICON_FILE` in `apps/menu/app.py`) and, if not, offers
  `patch_menu_icons.py` (dry run first, backup kept) in USB Disk Mode.
- Does not flash firmware or rename the app to borrow an icon.

## Badge shows the default icon

**Prompt**

> The simulator shows my icon.png, but my badge still shows a generic icon.

**Expected**

- Explains the stock event menu ignores `icon.png` until patched.
- Links Gadgetoid's gist and uses `patch_menu_icons.py` rather than hand edits.
- After patching, asks the user to eject BADGER and check the menu.

## Talk to the badge

**Prompt**

> I don't have mpremote. Show me what apps are on my badge and how much free
> space it has.

**Expected**

- Installs `mpremote` with `python3 -m pip install mpremote` (venv if needed).
- Finds the port with `mpremote devs` / `badge_serial.py port`; no hard-coding.
- Uses `mpremote connect PORT fs ls :/system/apps` and `os.statvfs` via `exec`.
- Runs serial commands one at a time and never reads `secrets.py`.

## Force USB Disk Mode

**Prompt**

> Copy my app to the badge. It is plugged in and showing the menu.

**Expected**

- Switches to USB Disk Mode from the computer (`badge_serial.py disk-mode` or
  `powman.reset_into_msc()`), with the Mass Storage app and double-tap RESET
  as fallbacks.
- Explains that `/system` is read-only over serial (`EROFS`).
- Deploys with a dry run first, then ejects and checks the app on the badge.

## Simulator versus badge

**Prompt**

> Can I test my Bluetooth app in the simulator instead of on a badge?

**Expected**

- Points to https://badger.github.io/editor for layout and logic only.
- States that Bluetooth, sockets, IR, camera, and `.mpy` are not simulated.
- Recommends a two-badge physical test.

## Personal install and plain project folder

**Prompt**

> Use your personally installed skill to make a counter app in this empty
> Badge Projects folder. I do not have a badge connected.

**Expected**

- Creates the app in this project, not in the skill installation or home folder.
- Uses commands and quoting for the user's host and paths with spaces.
- Runs file checks and gives hardware checks without claiming deployment or
  physical success. May suggest the badger.github.io simulator.
- Does not require Git, a firmware update, or the 2025 simulator.

## Repeat installation

Run the host installer into a temporary user folder, add an unrelated file to
the installed copy, and run the installer again from the source package.
Confirm the updated skill works, the unrelated file remains, and caches and
host metadata from the source are not copied. Check actual skill discovery in
each supported client separately; do not infer it from another client's result.
