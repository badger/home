"""Shared host paths and command display for the standalone skill tools."""

from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def project_root(explicit: Path | None = None) -> Path:
    if explicit is not None:
        root = explicit.expanduser().resolve()
    elif (
        SCRIPT_DIR.parent.parent.name == "skills"
        and SCRIPT_DIR.parent.parent.parent.name == ".github"
    ):
        root = SCRIPT_DIR.parents[3]
    else:
        root = Path.cwd().resolve()
        if (
            root == Path.home().resolve()
            or root == Path(root.anchor)
            or root.is_relative_to(SCRIPT_DIR.parent)
        ):
            raise ValueError(
                "Open your badge project folder first, or pass --repo-root "
                "(--apps-dir for scaffold_app.py). The skill folder and your "
                "home folder are not default app projects."
            )
    if not root.is_dir():
        raise FileNotFoundError(f"Project folder does not exist: {root}")
    return root


def find_apps_dir(mount: Path) -> Path:
    candidates = (mount / "system" / "apps", mount / "apps")
    found = [path for path in candidates if path.is_dir()]
    if len(found) == 1:
        return found[0]
    if len(found) > 1:
        raise RuntimeError(
            f"Multiple badge app directories found under {mount}. "
            "Pass --mount with the directory whose direct child is the intended "
            "apps folder (for example, BADGER/system)."
        )
    raise FileNotFoundError(
        f"{mount} does not contain a supported badge app directory. "
        "Expected system/apps or apps; verify this is the BADGER USB Disk Mode "
        "volume, not the RP2350 firmware drive."
    )


def validation_command(app_dir: Path) -> str:
    arguments = [
        sys.executable,
        str(SCRIPT_DIR / "validate_app.py"),
        str(app_dir),
    ]
    if os.name == "nt":
        return "& " + " ".join("'" + value.replace("'", "''") + "'" for value in arguments)
    return shlex.join(arguments)
