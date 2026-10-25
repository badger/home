# USB serial, mpremote, and USB Disk Mode

Condensed from `badger/home` `hardware/USB_SERIAL.md`; read that file for the
tested details.

## Install mpremote

```bash
python3 -m pip install mpremote        # macOS / Linux
python -m pip install mpremote         # Windows
```

If pip refuses (externally managed Python), use a virtual environment
(`python3 -m venv .venv && . .venv/bin/activate`) or `pipx install mpremote`.

## Find the badge

```bash
mpremote devs
```

Pick the line with `2e8a:1101` (stock firmware: `GitHub Badger 2350
MicroPython`; some builds: `Pimoroni Tufty 2350 MicroPython`), not Bluetooth or
debug-console ports. `python3 scripts/badge_serial.py port` does this. The
port name can change after reconnecting, so do not hard-code it. A badge in
USB Disk Mode has no serial port.

## REPL and one-off commands

| Task | Command |
| --- | --- |
| Interactive REPL (Ctrl-] exits, Ctrl-C stops a running app) | `mpremote connect PORT repl` |
| Attach without the initial soft reset | `mpremote connect PORT resume repl` |
| Run statements | `mpremote connect PORT exec "import os; print(os.listdir('/state'))"` |
| Evaluate an expression | `mpremote connect PORT eval "1 + 1"` |
| Run a local script on the badge | `mpremote connect PORT run probe.py` |
| List / read files | `mpremote connect PORT fs ls :/system/apps`, `fs cat :/path` |
| Copy to writable storage | `mpremote connect PORT fs cp file :/file` |
| Free space | `mpremote connect PORT exec "import os; print(os.statvfs('/'))"` |
| Reboot normally | `mpremote connect PORT reset` |
| Firmware, apps, icon support | `python3 scripts/badge_serial.py info` |

Rules:

- One process owns the port. Never run serial commands in parallel.
- Connecting stops the running app; reset afterwards to test normal startup.
- `/system` is read-only in the normal runtime (`OSError: 30`/`EROFS`). `/` and
  `/state` (~1 MiB) are writable. App state lives in `/state`.
- Never send raw binary into the friendly REPL; use `fs cp` or raw REPL.
- Quick render tests without installing: `mpremote connect PORT mount badge`
  exposes the local `badge/` folder at `/remote`. Asset-heavy apps may fail
  because PNG streaming through the mount is unreliable.

## Force USB Disk Mode

USB Disk Mode exposes `/system` as the `BADGER` volume so apps can be
installed. Options:

1. `python3 scripts/badge_serial.py disk-mode` (waits for BADGER).
2. `mpremote connect PORT exec "import powman; powman.reset_into_msc()"`.
   The connection drops as the badge reboots; that is expected. BADGER
   appears a few seconds later.
3. Open the **Mass Storage** app on the badge.
4. Quickly double-tap RESET.

Options 1-3 set the same persistent double-tap flag and reboot into USB
storage (`badger/home`'s `badge/main.py` checks `powman.WAKE_DOUBLETAP` and
imports `_msc`; stock firmware handles it the same way at boot).

Stock event firmware already ships this behavior. If a badge's Mass Storage app
runs USB storage inline instead (it hangs or
the volume misbehaves), update it to the `badger/home` version, which calls
`powman.reset_into_msc()`. Double-tap RESET, then from a `badger/home`
checkout run `deploy_app.py badge/apps/mass_storage --write --replace`.
If `powman` lacks `reset_into_msc`, the firmware is too old for options 1-3.

## Copy and eject

- Volume root contains `apps/` (or `system/apps/`): that is `/system/apps`.
- `deploy_app.py` previews and copies one app, excluding hidden files,
  caches, bytecode, and `secrets.py`.
- Do not use the `RP2350` drive; it is the firmware bootloader.
- Eject with `badge_serial.py eject` (or Finder, `diskutil eject /Volumes/BADGER`,
  Linux `udisksctl unmount`, or Windows "Eject") and wait for the volume to
  disappear. The badge restarts into the menu by itself; press RESET if not.
- Windows Explorer often reports "An error occurred while ejecting 'BADGER'".
  The badge reboots the instant it receives the eject request, so Windows loses
  the device before the request completes. Files are already flushed and the
  message is harmless; `badge_serial.py eject` avoids it.
- Confirm: `mpremote connect PORT fs ls :/system/apps/<name>`.
