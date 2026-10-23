#!/usr/bin/env python3
"""List readable app evidence on a mounted BADGER volume."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from skill_paths import find_apps_dir

EXCLUDED_NAMES = {"__pycache__", ".DS_Store", "secrets.py"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".mpy"}


def readable_files(app_dir: Path) -> list[Path]:
    files = []
    for path in sorted(app_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.is_symlink() or any(
            part.startswith(".") or part in EXCLUDED_NAMES
            for part in path.relative_to(app_dir).parts
        ):
            continue
        if path.name in EXCLUDED_NAMES or path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        if path.suffix.lower() in {".py", ".png", ".jpg", ".jpeg", ".json"}:
            files.append(path.relative_to(app_dir))
    return files


def render_inventory(apps_dir: Path) -> str:
    lines = [
        "# BADGER app source inventory",
        "",
        f"Source: `{apps_dir}`",
        "",
        "| App | Readable files |",
        "|---|---|",
    ]
    for app_dir in sorted(path for path in apps_dir.iterdir() if path.is_dir()):
        if app_dir.is_symlink() or app_dir.name.startswith(".") or app_dir.name in EXCLUDED_NAMES:
            continue
        files = readable_files(app_dir)
        names = ", ".join(f"`{path.as_posix()}`" for path in files) or "*(none)*"
        lines.append(f"| `{app_dir.name}` | {names} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mount", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        inventory = render_inventory(find_apps_dir(args.mount.expanduser().resolve()))
        if args.output:
            args.output.write_text(inventory, encoding="utf-8")
        else:
            print(inventory, end="")
    except (OSError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
