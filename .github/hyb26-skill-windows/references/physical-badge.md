# Physical badge workflow

Use the host commands and safe-eject steps in `SKILL.md`. Source versions and
current event firmware differences are recorded in [sources.md](sources.md).

## USB Disk Mode and copying

1. Connect a data-capable USB-C cable.
2. Quickly press RESET twice. Wait for USB Disk Mode and the BADGER volume.
3. Identify the actual mount/drive letter. RP2350 is for firmware, not apps.
4. Confirm BADGER contains `apps` or `system/apps`.
5. Run hardware-target validation, then preview the selected app deployment.
6. Review the destination and file list before using `--write`.

If both app trees exist, stop and choose the intended tree explicitly. Pass
`--mount` with the folder whose direct child is the intended `apps` folder,
for example `BADGER/system` for the nested tree. Do not guess between them.

For an intended update, `--replace` preserves the previous directory under
`.badge-app-backups` at the selected mount, outside the app discovery tree.
Files are staged before replacement. Do not claim this is a power-loss-proof
transaction; keep the cable connected throughout copying.

The tool copies only the chosen app and excludes credentials, hidden files,
bytecode, and caches. It refuses reserved `menu` and `startup` app names.
Do not replace shared apps, edit menu icons, or change system files as part of
an ordinary app deployment.

## Reboot and test

1. Safely eject BADGER through the host's file manager and wait for completion.
2. Press RESET once.
3. Open the app and exercise all screens, controls, and failure states.
4. Press HOME, reopen the app, and confirm cleanup and saved state.
5. Reset and repeat relevant initialization and persistence checks.

Missing credentials should produce useful offline behavior or a clear error.
Configure credentials only through a separate, intentional device setup step.
Never print, commit, inventory, or deploy the root `secrets.py`.

## Feature-specific checks

- Wi-Fi: missing credentials, unreachable network, timeout, retry, bounded data,
  cache reuse, and responsive controls.
- Bluetooth: real peers, discovery, connection, exchange, disconnect,
  reconnect, missing peer, and cleanup. Use two badges for badge-to-badge apps.
- IR: verified pins/protocol, duplicate and missed events, range and orientation.
- Lights/battery: supported brightness range, plugged/unplugged behavior,
  cleanup, and safe power use.
- State: first run, wrong value types, corrupt data, failed save, reopen, reset.
- Graphics/memory: cold start, busiest screen, display modes, long-running use.
- Expansion: correct voltage, bus, pins, and supported driver.

File validation and desktop previews cannot replace these checks.

## Troubleshooting

- App missing: confirm its entry file under the selected USB app tree. Device
  runtime paths use `/system/apps/<name>`, even when USB shows `BADGER/apps`.
- Wrong menu icon: custom app menu icons are not supported yet on current
  event firmware. The menu uses built-in icons and a generic fallback.
  `icon.png` is preview-only; replacing it cannot change the menu.
- Missing art inside the app: check exact case, app-relative paths, and assets.
- HOME unresponsive: remove blocking work and keep `on_exit()` short.
- File checks pass but the app fails: inspect logs and matching firmware APIs.
  Keep diagnostics concise; never print credentials or personal payloads.

## Firmware recovery boundary

Do not flash firmware to solve an app or icon request. If recovery is needed,
stop ordinary deployment and identify the exact hardware and intended U26
firmware with event staff or matching official instructions first. A release
called "latest" in an older repository can be for a different badge.
Flashing and system/menu changes require a separate approved workflow.
