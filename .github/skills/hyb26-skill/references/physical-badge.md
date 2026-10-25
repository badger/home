# Physical badge workflow

A real badge is always the preferred test. Commands and serial details are in
[usb-serial.md](usb-serial.md).

## Deploy

1. Connect a data-capable USB-C cable. Check `mpremote devs` shows `2e8a:1101`.
2. Validate: `validate_app.py badge/apps/<name>`.
3. Enter USB Disk Mode: `badge_serial.py disk-mode`, the Mass Storage app, or a
   quick double-tap of RESET. Wait for the BADGER volume.
4. Confirm BADGER contains `apps` (or `system/apps`). `RP2350` is the firmware
   bootloader drive; never copy apps there.
5. Preview, then copy: `deploy_app.py badge/apps/<name>`, then `--write`.
   Add `--replace` to update an existing app (backup kept in
   `BADGER/.badge-app-backups`).
6. Verify the app icon before ejecting:
   - Confirm the installed app directory contains the newly created
     `icon.png`, and that it is square.
   - Run `badge_serial.py info` or check for `ICON_FILE` in the installed
     menu. If custom icons are unsupported, preview and then apply
     `patch_menu_icons.py` once per badge ([menu-icons.md](menu-icons.md)).
7. Eject: `badge_serial.py eject` (flushes, ejects, and waits for the badge
   to restart). The badge restarts into the menu; press RESET if it does not.
8. Open the app tile and visually confirm that the newly created icon is
   displayed instead of the default icon. A valid PNG or a successful copy is
   not enough to claim that the badge displays it.

If both `apps` and `system/apps` exist, pass `--mount` pointing at the folder
whose direct child is the intended `apps`. Keep the cable connected while
copying. The deploy tool copies one app, skips hidden files, caches, bytecode,
and `secrets.py`, and refuses `menu` and `startup`.

## Test on the badge

1. Open the app from the menu and exercise every screen, control, and error
   state.
2. Press HOME, reopen, and confirm cleanup and saved state.
3. Reset and repeat persistence checks.
4. For crashes, attach with `mpremote connect PORT resume repl`, open the app,
   and read the traceback. Use `exec`/`eval` to probe APIs and memory
   (`import gc; gc.collect(); print(gc.mem_free())`).
5. For quick iterations without reinstalling, `mpremote connect PORT mount
   badge` exposes the local `badge/` folder at `/remote` (asset streaming is
   unreliable; do the final test from USB Disk Mode).

## Feature checks

- Wi-Fi: missing credentials, no network, timeout, retry, bounded data, cache.
- Badge link / Bluetooth: two badges, pairing, exchange, disconnect, retry.
- IR: duplicates, misses, range, orientation.
- Lights and battery: brightness, on battery and USB, cleanup on exit.
- State: first run, wrong types, corrupt data, reopen, reset.
- Graphics and memory: cold start, busiest screen, display modes, long runs.
- Expansion: voltage, bus, pins, driver.

## Troubleshooting

- App missing from menu: check `/system/apps/<name>/__init__.py` exists
  (`mpremote connect PORT fs ls :/system/apps/<name>`), then reset.
- Default icon instead of the app's icon: built-in apps keep their own icon;
  check the installed PNG, confirm menu support, apply the menu patch if
  needed, restart, and visually check the tile again.
- `OSError: 30` / `EROFS` copying over serial: `/system` is read-only there;
  use USB Disk Mode.
- Port busy: close Thonny, Web Serial tabs, `screen`, and other `mpremote`s.
- HOME unresponsive: remove blocking work from `update()` and `on_exit()`.

Never print, commit, or deploy `secrets.py`. Do not flash firmware as part of
an app task; firmware recovery is a separate, deliberate step.
