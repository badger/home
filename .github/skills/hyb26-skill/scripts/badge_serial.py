"""Find a connected badge over USB serial and run common mpremote tasks.

Subcommands:
  port       Print the badge's serial port.
  info       Print firmware, app list, and whether the menu loads icon.png.
  repl       Open the interactive MicroPython REPL (Ctrl-] exits).
  disk-mode  Reboot the badge into USB Disk Mode and wait for BADGER.
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Sequence


BADGE_USB_ID = "2e8a:1101"
INSTALL_HINT = (
    "mpremote is not installed. Install it with "
    "`python3 -m pip install mpremote` (Windows: `python -m pip install mpremote`), "
    "using a virtual environment if the system Python refuses packages."
)

INFO_CODE = """\
import os, sys
print('firmware:', sys.implementation)
print('machine:', os.uname().machine)
print('apps:', ' '.join(sorted(os.listdir('/system/apps'))))
try:
    src = open('/system/apps/menu/app.py').read()
    print('menu icon.png support:', 'yes' if 'ICON_FILE' in src else 'no (run patch_menu_icons.py)')
except OSError:
    print('menu icon.png support: unknown (no readable /system/apps/menu/app.py)')
"""

DISK_MODE_CODE = """\
import powman
if hasattr(powman, 'reset_into_msc'):
    print('HYB26:MSC')
    powman.reset_into_msc()
else:
    print('HYB26:NO_MSC')
"""

Runner = Callable[..., subprocess.CompletedProcess]


class SerialError(RuntimeError):
    pass


def mpremote_command() -> list[str]:
    found = shutil.which("mpremote")
    if found:
        return [found]
    if importlib.util.find_spec("mpremote") is not None:
        return [sys.executable, "-m", "mpremote"]
    raise SerialError(INSTALL_HINT)


def parse_devs(output: str) -> list[str]:
    ports = []
    for line in output.splitlines():
        fields = line.split()
        if len(fields) > 2 and BADGE_USB_ID in fields[1:]:
            ports.append(fields[0])
    return ports


def find_port(mpremote: Sequence[str], run: Runner = subprocess.run) -> str:
    result = run([*mpremote, "devs"], capture_output=True, text=True, timeout=30)
    ports = parse_devs(result.stdout)
    if not ports:
        raise SerialError(
            f"No badge ({BADGE_USB_ID}) found by `mpremote devs`. Use a data-capable "
            "USB-C cable, make sure the badge is running (not in USB Disk Mode), "
            "and close other serial programs."
        )
    if len(ports) > 1:
        raise SerialError(
            f"Multiple badges found ({', '.join(ports)}); pass --port to choose one."
        )
    return ports[0]


def wait_for_mount(timeout: float, candidates: Callable[[], list[Path]]) -> Path | None:
    deadline = time.monotonic() + timeout
    while True:
        found = [path for path in candidates() if path.is_dir()]
        if found:
            return found[0]
        if time.monotonic() >= deadline:
            return None
        time.sleep(1)


def default_candidates() -> list[Path]:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from deploy_app import candidate_mounts

    return candidate_mounts()


def disk_mode(
    mpremote: Sequence[str],
    port: str,
    wait: float,
    run: Runner = subprocess.run,
    candidates: Callable[[], list[Path]] = default_candidates,
) -> Path | None:
    try:
        result = run(
            [*mpremote, "connect", port, "exec", DISK_MODE_CODE],
            capture_output=True,
            text=True,
            timeout=20,
        )
        output = (result.stdout or "") + (result.stderr or "")
    except subprocess.TimeoutExpired:
        output = ""
    if "HYB26:NO_MSC" in output:
        raise SerialError(
            "This firmware has no powman.reset_into_msc(). Double-tap RESET "
            "to enter USB Disk Mode instead."
        )
    return wait_for_mount(wait, candidates)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("command", choices=("port", "info", "repl", "disk-mode"))
    parser.add_argument("--port", help="Serial port; defaults to `mpremote devs` lookup")
    parser.add_argument(
        "--wait", type=float, default=30, help="Seconds to wait for BADGER (disk-mode)"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        mpremote = mpremote_command()
        port = args.port or find_port(mpremote)
        if args.command == "port":
            print(port)
            return 0
        if args.command == "info":
            return subprocess.run(
                [*mpremote, "connect", port, "exec", INFO_CODE], timeout=60
            ).returncode
        if args.command == "repl":
            return subprocess.run([*mpremote, "connect", port, "repl"]).returncode
        print(f"Asking the badge on {port} to reboot into USB Disk Mode...")
        mount = disk_mode(mpremote, port, args.wait)
    except (SerialError, OSError, subprocess.SubprocessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if mount is None:
        print(
            "BADGER did not appear. Check the badge screen, or double-tap RESET. "
            "If the volume uses another path, pass it to deploy_app.py with --mount.",
            file=sys.stderr,
        )
        return 1
    print(f"BADGER is mounted at {mount}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
