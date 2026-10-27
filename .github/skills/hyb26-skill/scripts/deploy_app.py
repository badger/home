#!/usr/bin/env python3
"""Safely copy one badge app, and the shared badge/lib modules it imports, to a
mounted BADGER volume."""

from __future__ import annotations

import argparse
import ast
import filecmp
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


def imported_modules(path: Path) -> set[str]:
    """Top-level module names a Python file or package folder imports."""
    sources = [path] if path.is_file() else [
        source for source in path.rglob("*.py") if included(source.relative_to(path))
    ]
    names: set[str] = set()
    for source in sources:
        try:
            tree = ast.parse(source.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue  # validate_app reports these
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                names.add(node.module.split(".")[0])
    return names


def shared_libs(app_dir: Path, repo_root: Path) -> list[Path]:
    """badge/lib modules (files or packages) the app needs, including theirs."""
    lib_root = repo_root / "badge" / "lib"
    if not lib_root.is_dir():
        return []
    local = {path.stem for path in app_dir.glob("*.py")}
    local.update(path.name for path in app_dir.iterdir() if path.is_dir())

    def find(name: str) -> Path | None:
        module, package = lib_root / f"{name}.py", lib_root / name
        if module.is_file():
            return module
        if package.is_dir() and (package / "__init__.py").is_file():
            return package
        return None

    found: dict[str, Path] = {}
    pending = sorted(imported_modules(app_dir) - local)
    while pending:
        name = pending.pop()
        lib = None if name in found else find(name)
        if lib is not None:
            found[name] = lib
            pending.extend(sorted(imported_modules(lib) - found.keys()))
    return [found[name] for name in sorted(found)]


def same_content(source: Path, target: Path) -> bool:
    if source.is_file():
        return target.is_file() and filecmp.cmp(source, target, shallow=False)
    if not target.is_dir():
        return False
    files = [path for path in source.rglob("*") if path.is_file() and included(path.relative_to(source))]
    copied = [path for path in target.rglob("*") if path.is_file()]
    return len(files) == len(copied) and all(
        same_content(path, target / path.relative_to(source)) for path in files
    )


def install_shared_libs(libs: list[Path], lib_dir: Path, backup_root: Path) -> None:
    """Copy each shared module into lib_dir, keeping a backup of any it changes."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    for lib in libs:
        target = lib_dir / lib.name
        if same_content(lib, target):
            print(f"Shared {lib.name} is already up to date")
            continue
        lib_dir.mkdir(parents=True, exist_ok=True)
        staging = lib_dir / f".{lib.name}.staging"
        if staging.is_dir():
            shutil.rmtree(staging)
        elif staging.exists():
            staging.unlink()
        if lib.is_file():
            shutil.copy2(lib, staging)
        else:
            copy_app(lib, staging)
        if target.exists():
            backup_root.mkdir(exist_ok=True)
            backup = backup_root / f"lib-{lib.name}-{timestamp}"
            target.rename(backup)
            print(f"Backed up existing shared {lib.name} to {backup}")
        staging.rename(target)
        print(f"Installed shared {lib.name} to {target}")


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
    libs = shared_libs(app_dir, repo_root)
    lib_dir = apps_dir.parent / "lib"
    print(f"{'Would deploy' if not write else 'Deploying'} {app_dir.name} to {destination}")
    for path in copied:
        print(f"  {path.relative_to(app_dir)}")
    for lib in libs:
        print(f"  shared: badge/lib/{lib.name} -> {lib_dir / lib.name}")
    if not write:
        print("Dry run only. Re-run with --write to copy files.")
        return destination

    staging_root = mount / ".badge-app-staging"
    backup_root = mount / ".badge-app-backups"
    # shared modules first, so the app never lands without what it imports
    install_shared_libs(libs, lib_dir, backup_root)
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
