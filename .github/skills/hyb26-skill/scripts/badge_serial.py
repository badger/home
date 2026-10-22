"""Find a connected badge over USB serial and run common mpremote tasks.

Subcommands:
  port       Print the badge's serial port.
  info       Print firmware, app list, and whether the menu loads icon.png.
  repl       Open the interactive MicroPython REPL (Ctrl-] exits).
  disk-mode  Reboot the badge into USB Disk Mode and wait for BADGER.
  eject      Flush and eject BADGER, then wait for the badge to restart.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
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


# The badge reboots as soon as it receives the eject request, so the final
# eject IOCTL can fail because the device has already gone. Windows Explorer
# reports this as "An error occurred while ejecting"; the data is already safe.
WINDOWS_GONE_ERRORS = {2, 3, 21, 433, 1167}


def eject_windows(mount: Path) -> None:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = (
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    )
    kernel32.DeviceIoControl.argtypes = (
        wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
    )
    invalid = wintypes.HANDLE(-1).value
    drive = mount.drive.rstrip("\\")
    if not drive:
        raise SerialError(f"{mount} is not a drive letter; eject it from Explorer.")
    handle = kernel32.CreateFileW(
        f"\\\\.\\{drive}", 0xC0000000, 0x3, None, 3, 0, None  # RW, share RW, OPEN_EXISTING
    )
    if handle in (None, invalid):
        raise SerialError(f"Could not open {drive} (error {ctypes.get_last_error()}).")
    returned = wintypes.DWORD()

    def ioctl(code: int) -> int:
        ok = kernel32.DeviceIoControl(handle, code, None, 0, None, 0, ctypes.byref(returned), None)
        return 0 if ok else ctypes.get_last_error()

    try:
        kernel32.FlushFileBuffers(handle)
        for _ in range(10):
            error = ioctl(0x00090018)  # FSCTL_LOCK_VOLUME
            if error == 0:
                break
            time.sleep(0.5)
        else:
            raise SerialError(
                f"{drive} is in use (error {error}). Close Explorer windows, editors, "
                "or terminals open on BADGER and try again."
            )
        error = ioctl(0x00090020)  # FSCTL_DISMOUNT_VOLUME
        if error and error not in WINDOWS_GONE_ERRORS:
            raise SerialError(f"Could not dismount {drive} (error {error}).")
        error = ioctl(0x002D4808)  # IOCTL_STORAGE_EJECT_MEDIA
        if error and error not in WINDOWS_GONE_ERRORS:
            raise SerialError(f"Could not eject {drive} (error {error}).")
    finally:
        kernel32.CloseHandle(handle)


def eject_posix(mount: Path, run: Runner = subprocess.run) -> None:
    if sys.platform == "darwin":
        command = ["diskutil", "eject", str(mount)]
    elif shutil.which("udisksctl") and shutil.which("findmnt"):
        source = run(
            ["findmnt", "-n", "-o", "SOURCE", "--target", str(mount)],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        command = ["udisksctl", "unmount", "-b", source] if source else ["umount", str(mount)]
    else:
        command = ["umount", str(mount)]
    if hasattr(os, "sync"):
        os.sync()
    result = run(command, capture_output=True, text=True, timeout=60)
    if result.returncode != 0 and mount.is_dir():
        detail = (result.stderr or result.stdout or "").strip()
        raise SerialError(f"`{' '.join(command)}` failed: {detail}")


def wait_until_gone(mount: Path, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while mount.is_dir():
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.5)
    return True


def eject(mount_arg: Path | None, wait: float) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from deploy_app import find_mount

    mount = find_mount(mount_arg)
    print(f"Ejecting BADGER at {mount}...")
    if os.name == "nt":
        eject_windows(mount)
    else:
        eject_posix(mount)
    if not wait_until_gone(mount, wait):
        print(
            f"{mount} is still mounted. Eject it from your file manager, "
            "then press RESET if the badge does not restart.",
            file=sys.stderr,
        )
        return 1
    print("BADGER ejected safely.")
    try:
        mpremote = mpremote_command()
    except SerialError:
        print("The badge should restart into the menu; press RESET if it does not.")
        return 0
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        try:
            print(f"Badge restarted on {find_port(mpremote)}.")
            return 0
        except (SerialError, OSError, subprocess.SubprocessError):
            time.sleep(1)
    print("The badge has not reappeared over USB serial yet; press RESET if the screen is blank.")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("command", choices=("port", "info", "repl", "disk-mode", "eject"))
    parser.add_argument("--port", help="Serial port; defaults to `mpremote devs` lookup")
    parser.add_argument(
        "--mount", type=Path, help="BADGER volume to eject; defaults to auto-detect"
    )
    parser.add_argument(
        "--wait", type=float, default=30,
        help="Seconds to wait for BADGER to appear (disk-mode) or disappear (eject)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "eject":
        try:
            return eject(args.mount, args.wait)
        except (SerialError, OSError, RuntimeError, subprocess.SubprocessError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
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
