#!/usr/bin/env python3
"""Let the badge menu show an app's own icon.png.

Applies the menu change from
https://gist.github.com/Gadgetoid/f72b85e6efe603bd02b2b730bbc40356 to
``apps/menu/app.py`` on a BADGER volume in USB Disk Mode. Apps whose folder
name has a built-in menu icon keep it; other apps show their ``icon.png``.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

from skill_paths import find_apps_dir

GIST_URL = "https://gist.github.com/Gadgetoid/f72b85e6efe603bd02b2b730bbc40356"
MARKERS = ('ICON_FILE = "icon.png"', "def load_picture(path):", "self.picture")

LOAD_PICTURE = '''def load_picture(path):
    try:
        return image.load(f"{path}/{ICON_FILE}")
    except (OSError, ValueError):
        return None


'''

BLIT_PICTURE = '''if self.picture is not None:
    icon_size = ICON_SIZE * scale
    icon_x = centre_x + tilt.x * ICON_SHIFT - icon_size / 2
    icon_y = centre_y + tilt.y * ICON_SHIFT - icon_size / 2
    screen.blit(self.picture, rect(0, 0, self.picture.width, self.picture.height), rect(icon_x, icon_y, icon_size, icon_size), TILE_FILTER)
    return

'''


class PatchError(ValueError):
    pass


def is_patched(text: str) -> bool:
    return all(marker in text for marker in MARKERS)


def _single(pattern: str, text: str, description: str) -> re.Match[str]:
    matches = list(re.finditer(pattern, text, re.MULTILINE))
    if len(matches) != 1:
        raise PatchError(
            f"Expected one {description} in menu/app.py, found {len(matches)}. "
            f"This menu differs from the one the patch targets; compare it "
            f"with {GIST_URL} and apply the change by hand."
        )
    return matches[0]


def patch_text(text: str) -> str:
    if is_patched(text):
        return text
    if any(marker in text for marker in MARKERS):
        raise PatchError(
            "menu/app.py is partially patched. Restore a backup or compare it "
            f"with {GIST_URL} by hand."
        )
    newline = "\r\n" if "\r\n" in text else "\n"
    text = text.replace("\r\n", "\n")

    for name in ("ICON_SIZE", "TILE_FILTER"):
        _single(rf"^{name} = ", text, f"{name} constant")
    _single(r"^class App\(", text, "App class")

    anchor = _single(r"^ICON_SHIFT = .*\n", text, "ICON_SHIFT constant")
    text = text[: anchor.end()] + 'ICON_FILE = "icon.png"\n' + text[anchor.end():]

    anchor = _single(r"^def load_animation\(", text, "load_animation function")
    text = text[: anchor.start()] + LOAD_PICTURE + text[anchor.start():]

    anchor = _single(
        r"^( +)self\.icon = build_icon\(ICONS\[self\.icon_key\]\)\n",
        text,
        "built-in icon assignment",
    )
    init = text.rfind("def __init__(", 0, anchor.start())
    if init < 0 or not re.match(r"def __init__\([^)]*\bpath\b", text[init:]):
        raise PatchError(
            "App.__init__ does not receive the app path. Compare menu/app.py "
            f"with {GIST_URL} and apply the change by hand."
        )
    indent = anchor.group(1)
    line = f"{indent}self.picture = None if slug in ICONS else load_picture(path)\n"
    text = text[: anchor.end()] + line + text[anchor.end():]

    anchor = _single(
        r"^( +)icon = self\.current_icon\(selected\)\n", text, "icon draw call"
    )
    indent = anchor.group(1)
    block = "".join(
        f"{indent}{row}\n" if row else "\n"
        for row in BLIT_PICTURE.rstrip("\n").split("\n")
    ) + "\n"
    text = text[: anchor.start()] + block + text[anchor.start():]

    return text.replace("\n", newline)


def find_menu(mount: Path) -> Path:
    menu = find_apps_dir(mount) / "menu" / "app.py"
    if not menu.is_file():
        raise FileNotFoundError(
            f"{menu} not found. The menu may be compiled (app.mpy) on this "
            "firmware; update the firmware or apply the gist to its source."
        )
    return menu


def apply(menu: Path, write: bool, backup_root: Path) -> str:
    original = menu.read_bytes().decode("utf-8")
    if is_patched(original):
        print(f"{menu} already shows app icon.png files. Nothing to do.")
        return "patched"
    updated = patch_text(original)
    if not write:
        print(f"Would patch {menu} so apps without a built-in icon show icon.png.")
        print("Dry run only. Re-run with --write to change the badge menu.")
        return "dry-run"

    backup_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = backup_root / f"menu-app.py-{timestamp}"
    shutil.copy2(menu, backup)
    temporary = menu.with_name(".app.py.patching")
    temporary.write_bytes(updated.encode("utf-8"))
    os.replace(temporary, menu)
    print(f"Patched {menu}. Original saved to {backup}.")
    return "written"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group()
    target.add_argument(
        "--mount", type=Path, help="Mounted BADGER volume (found automatically if omitted)"
    )
    target.add_argument(
        "--file",
        type=Path,
        help="A local copy of menu/app.py (for example one fetched with mpremote)",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Change the file (the default is a dry run)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.file is not None:
            menu = args.file.expanduser().resolve()
            apply(menu, args.write, menu.parent)
            return 0
        from deploy_app import find_mount

        mount = find_mount(args.mount)
        menu = find_menu(mount)
        if apply(menu, args.write, mount / ".badge-app-backups") == "written":
            print("Eject with `badge_serial.py eject`; reset the badge if it does not restart.")
    except (OSError, RuntimeError, UnicodeDecodeError, PatchError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
