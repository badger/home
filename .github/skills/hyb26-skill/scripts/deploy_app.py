#!/usr/bin/env python3
"""Safely copy one badge app to a mounted BADGER volume."""

from __future__ import annotations

import argparse
import getpass
import importlib.util
import os
import shutil
import string
import sys
from datetime import datetime
from pathlib import Path

from skill_paths import find_apps_dir, project_root

SCRIPT_DIR = Path(__file__).resolve().parent
EXCLUDED_NAMES = {"__pycache__", ".DS_Store", "secrets.py"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".mpy"}


def load_validator():
    spec = importlib.util.spec_from_file_location(
        "badge_app_validator", SCRIPT_DIR / "validate_app.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load validate_app.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def windows_volume_label(path: Path) -> str | None:
    if os.name != "nt":
        return None
    try:
        import ctypes

        label = ctypes.create_unicode_buffer(261)
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            str(path), label, len(label), None, None, None, None, 0
        )
        return label.value if ok else None
    except (AttributeError, OSError):
        return None


def candidate_mounts() -> list[Path]:
    user = getpass.getuser()
    candidates = [
        Path("/Volumes/BADGER"),
        Path("/media") / user / "BADGER",
        Path("/run/media") / user / "BADGER",
        Path("/mnt/BADGER"),
    ]
    if os.name == "nt":
        for letter in string.ascii_uppercase[3:]:
            root = Path(f"{letter}:\\")
            if root.exists() and windows_volume_label(root) == "BADGER":
                candidates.append(root)
    return candidates


def find_mount(explicit: Path | None) -> Path:
    if explicit is not None:
        mount = explicit.expanduser().resolve()
        if not mount.is_dir():
            raise FileNotFoundError(f"Badge mount does not exist: {mount}")
        return mount

    found = [path.resolve() for path in candidate_mounts() if path.is_dir()]
    if not found:
        raise FileNotFoundError(
            "No mounted BADGER volume found. Put the badge in USB Disk Mode or "
            "pass --mount /path/to/BADGER."
        )
    if len(found) > 1:
        joined = ", ".join(str(path) for path in found)
        raise RuntimeError(f"Multiple BADGER volumes found ({joined}); pass --mount.")
    return found[0]


def should_copy(path: Path) -> bool:
    return (
        not path.name.startswith(".")
        and path.name.casefold() not in {name.casefold() for name in EXCLUDED_NAMES}
        and path.suffix.casefold() not in EXCLUDED_SUFFIXES
    )


def included(relative: Path) -> bool:
    return not any(
        part.startswith(".") or part == "__pycache__" for part in relative.parts
    ) and should_copy(relative)


def copy_app(source: Path, destination: Path) -> None:
    for item in source.rglob("*"):
        relative = item.relative_to(source)
        if item.is_symlink() or not included(relative):
            continue
        target = destination / relative
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif item.is_file() and should_copy(item):
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def deploy(
    app_dir: Path,
    mount: Path,
    write: bool,
    replace: bool,
    repo_root: Path,
) -> Path:
    validator = load_validator()
    if app_dir.name in validator.RESERVED_APPS:
        raise RuntimeError(
            f"Refusing to deploy reserved system app '{app_dir.name}'. Update "
            "launcher/startup code through a reviewed firmware workflow instead."
        )
    validation_issues = validator.validate_app(app_dir, repo_root, "hardware")
    warnings = [issue for issue in validation_issues if issue.severity == "WARNING"]
    errors = [issue for issue in validation_issues if issue.severity == "ERROR"]
    for warning in warnings:
        print(warning.render(repo_root))
    if errors:
        rendered = "\n".join(issue.render(repo_root) for issue in errors)
        raise RuntimeError(f"Hardware validation failed:\n{rendered}")

    apps_dir = find_apps_dir(mount)

    destination = apps_dir / app_dir.name
    if destination.exists() and not replace:
        raise FileExistsError(
            f"{destination} already exists. Re-run with --replace to keep a backup "
            "and install the new version."
        )

    copied = [
        path
        for path in app_dir.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and included(path.relative_to(app_dir))
    ]
    print(f"{'Would deploy' if not write else 'Deploying'} {app_dir.name} to {destination}")
    for path in copied:
        print(f"  {path.relative_to(app_dir)}")
    if not write:
        print("Dry run only. Re-run with --write to copy files.")
        return destination

    staging_root = mount / ".badge-app-staging"
    backup_root = mount / ".badge-app-backups"
    staging = staging_root / app_dir.name
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    backup = None
    try:
        copy_app(app_dir, staging)
        if destination.exists():
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            backup_root.mkdir(exist_ok=True)
            backup = backup_root / f"{app_dir.name}-{timestamp}"
            destination.rename(backup)
            print(f"Backed up existing app to {backup}")
        staging.rename(destination)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        if backup is not None and backup.exists() and not destination.exists():
            backup.rename(destination)
        raise
    finally:
        if staging_root.exists() and not any(staging_root.iterdir()):
            staging_root.rmdir()

    print("Deployment complete. Eject with `badge_serial.py eject`; reset the badge if it does not restart.")
    return destination


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", help="App name or path")
    parser.add_argument("--mount", type=Path, help="Mounted BADGER volume")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Perform the copy (the default is a dry run)",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace an existing app after preserving it as a timestamped backup",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        help="Project root (default: current project)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        repo_root = project_root(args.repo_root)
        validator = load_validator()
        app_dir = validator.resolve_app(args.app, repo_root)
        mount = find_mount(args.mount)
        deploy(app_dir, mount, args.write, args.replace, repo_root)
    except (RuntimeError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
