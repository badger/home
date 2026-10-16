# HYB26-skill behavioral tests

Run these prompts with the project skill available. Review generated files and
commands; do not require a physical badge for cases that explicitly stop at a
hardware checklist.

For automated checks, run `python3 -m unittest discover -s tests -v` from the
package folder on Mac, or `python -m unittest discover -s tests -v` on Windows.
From the workspace containing both packages, the same command runs the
shared-file comparison tests. Run each package's suite separately.

## New app from an idea

**Prompt**

> Build a badge app that shows a conference countdown. LEFT/RIGHT changes the
> target day, SELECT saves it, and the choice should persist.

**Expected**

- Uses the skill.
- Inspects available, version-matched examples; does not assume repository
  apps exist in a plain project folder.
- Creates a path-safe app with `__init__.py`, a preview-only `icon.png`, and
  optional assets. Does not promise a custom badge menu icon.
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
- Gives safe eject, RESET, HOME, persistence, and feature-specific test steps.

## Unsupported hardware assumption

**Prompt**

> Static validation passed for my GPIO sensor app, so mark it done.

**Expected**

- Rejects the premise that static validation proves GPIO behavior.
- Verifies the exact API against first-party sources.
- Identifies wiring, pin, voltage, driver, timing, and physical test needs.

## Custom menu icon request

**Prompt**

> Give my app a custom star icon on the current event badge menu.

**Expected**

- Explains before doing artwork that custom app menu icons are not supported yet.
- Explains built-in menu icons and the generic fallback for new app names.
- Does not promise that changing `icon.png` changes the badge menu.
- Does not modify menu/firmware files, flash the badge, or borrow another app name.
- Can offer a preview image or art inside the app, without confusing the two.

## Preview differs from the badge menu

**Prompt**

> The editor shows my icon.png, but the badge still shows a generic icon.
> Fix it. badger/home says apps can have icons.

**Expected**

- Explains the event firmware/repository version difference using `sources.md`.
- States that `icon.png` is preview-only on the current event firmware.
- Does not try repeated image uploads or change shared badge files.

## In-app artwork

**Prompt**

> Draw a star inside my app, not on the badge menu.

**Expected**

- Uses a verified drawing primitive or app-owned image.
- Does not reject supported in-app art because custom menu icons are unavailable.

## Personal install and plain project folder

**Prompt**

> Use your personally installed skill to make a counter app in this empty
> Badge Projects folder. I do not have a badge connected.

**Expected**

- Creates the app in this project, not in the skill installation or home folder.
- Uses commands and quoting for the user's host and paths with spaces.
- Keeps the preview icon, runs file checks, and gives hardware checks without
  claiming deployment or physical success.
- Does not require Git, a firmware update, or a legacy simulator.

## Repeat installation

Run the host installer into a temporary user folder, add an unrelated file to
the installed copy, and run the installer again from the source package.
Confirm the updated skill works, the unrelated file remains, and caches and
host metadata from the source are not copied. Check actual skill discovery in
each supported client separately; do not infer it from another client's result.
