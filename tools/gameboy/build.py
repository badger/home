#!/usr/bin/env python3
"""Build gbcore.mpy, the native Game Boy emulator core for the badge.

Requirements:
  * arm-none-eabi-gcc on PATH (or pass --cc)
  * a MicroPython checkout that matches the badge firmware
    (pimoroni/micropython tag bw-1.29.0-gc for the Universe 2026 firmware)
  * pyelftools (python -m pip install pyelftools)

Example:
  python tools/gameboy/build.py --mpy-dir ../micropython
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
MODULE = "gbcore"
ARCH = "armv7emsp"
DEFAULT_OUTPUT = REPO / "badge" / "apps" / "game_boy" / f"{MODULE}.mpy"

ARCH_FLAGS = [
    "-mthumb",
    "-mcpu=cortex-m4",
    "-mfpu=fpv4-sp-d16",
    "-mfloat-abi=hard",
]


def run(cmd):
    print(" ".join(str(part) for part in cmd))
    subprocess.run([str(part) for part in cmd], check=True)


def find_cc(explicit):
    candidates = [explicit, os.environ.get("ARM_GCC"), shutil.which("arm-none-eabi-gcc")]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return Path(candidate)
    sys.exit("arm-none-eabi-gcc not found; install it or pass --cc")


def find_mpy_dir(explicit):
    candidate = explicit or os.environ.get("MPY_DIR")
    if not candidate:
        sys.exit("pass --mpy-dir (or set MPY_DIR) to a MicroPython checkout")
    path = Path(candidate).resolve()
    if not (path / "py" / "dynruntime.h").exists() or not (path / "tools" / "mpy_ld.py").exists():
        sys.exit(f"{path} does not look like a MicroPython checkout")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mpy-dir", help="MicroPython source checkout (default: $MPY_DIR)")
    parser.add_argument("--cc", help="path to arm-none-eabi-gcc")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="where to write gbcore.mpy")
    parser.add_argument("--opt", default="-O2", help="optimisation flag, written as --opt=-Os (default: -O2)")
    args = parser.parse_args()

    cc = find_cc(args.cc)
    mpy_dir = find_mpy_dir(args.mpy_dir)
    mpy_ld = mpy_dir / "tools" / "mpy_ld.py"

    build = HERE / "build"
    build.mkdir(exist_ok=True)
    source = HERE / f"{MODULE}.c"
    config_h = build / f"{MODULE}.config.h"
    obj = build / f"{MODULE}.o"
    linked = build / f"{MODULE}.mpy"

    run([sys.executable, mpy_ld, "--arch", ARCH, "--preprocess", "-o", config_h, source])

    cflags = [
        f"-I{HERE}",
        f"-I{mpy_dir}",
        "-std=gnu11",
        args.opt,
        "-Wall",
        "-Wno-deprecated-declarations",
        "-DNDEBUG",
        "-DNO_QSTR",
        "-DMICROPY_ENABLE_DYNRUNTIME",
        f"-DMP_CONFIGFILE=<{config_h.as_posix()}>",
        "-fpic",
        "-fno-common",
        "-U_FORTIFY_SOURCE",
        *ARCH_FLAGS,
        "-DMICROPY_FLOAT_IMPL=MICROPY_FLOAT_IMPL_FLOAT",
    ]
    run([cc, *cflags, "-o", obj, "-c", source])

    run([sys.executable, mpy_ld, "--arch", ARCH, "--qstrs", config_h, f"--source-name={MODULE}.mpy", "-o", linked, obj])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(linked, args.output)
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
