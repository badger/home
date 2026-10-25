# Custom menu icons

## How the menu chooses an icon

`badge/apps/menu/app.py` in `badger/home`:

- Apps whose folder name is in the menu's built-in `ICONS` table (for example
  `gallery`, `flappy`, `settings`) always use the built-in vector icon.
- Every other app loads `<app>/icon.png` (`ICON_FILE`) and draws it at
  48x48 in its tile. Missing or unreadable files fall back to the default icon.

So ship an `icon.png` that is square, at least 24x24, and ideally 48x48.
Keep it small (a paletted PNG is best). New app names get their own icon;
do not rename an app to borrow a built-in one.

## Badges whose menu ignores icon.png

The stock event firmware menu only uses the built-in `ICONS` table (confirmed
on a stock badge in October 2026).
[Gadgetoid's patch](https://gist.github.com/Gadgetoid/f72b85e6efe603bd02b2b730bbc40356)
adds the PNG loading shown above. `badger/home` already includes it.

Check the badge:

```bash
python3 scripts/badge_serial.py info          # "menu icon.png support: yes/no"
mpremote connect PORT exec "print('ICON_FILE' in open('/system/apps/menu/app.py').read())"
```

or search `BADGER/apps/menu/app.py` (or `BADGER/system/apps/menu/app.py`) for
`ICON_FILE`.

## Applying the patch

1. Put the badge in USB Disk Mode (see [usb-serial.md](usb-serial.md)).
2. Preview, then write:

   ```bash
   python3 scripts/patch_menu_icons.py
   python3 scripts/patch_menu_icons.py --write
   ```

   BADGER is found automatically; pass `--mount /path/to/BADGER` (Windows:
   `--mount E:\`) if it is somewhere else.
3. Eject BADGER (`badge_serial.py eject`). The badge restarts into the patched menu (press RESET if not).

The tool only edits `apps/menu/app.py`, is safe to rerun (it detects an
already patched menu), saves the original to
`BADGER/.badge-app-backups/menu-app.py-<timestamp>`, and refuses to touch a
menu whose code does not match the expected anchors. In that case, compare the
file with the gist by hand or copy `badge/apps/menu/app.py` from a
`badger/home` checkout that matches the badge firmware. Do not touch the
menu's `.mpy` files.

To patch a local file instead of a badge: `--file path/to/app.py --write`.
To undo: copy the backup over `apps/menu/app.py`.
