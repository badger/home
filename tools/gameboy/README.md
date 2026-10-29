# Game Boy emulator core

Source for `badge/apps/game_boy/gbcore.mpy`, the native MicroPython module that
runs Game Boy games in the [Game Boy app](../../badge/apps/game_boy/).

- `peanut_gb.h` is [Peanut-GB](https://github.com/deltabeard/Peanut-GB)
  (commit `d0bcca7`, MIT licence; the licence is at the top of the file).
- `gbcore.c` wraps it for MicroPython: it loads the ROM and cartridge RAM from
  Python buffers and draws each frame straight into the badge's RGB565 screen,
  either at 1x or at 1.5x (sharp or smoothed).
- `build.py` compiles it into a `.mpy` native module for the badge's
  RP2350 (`armv7emsp`), without needing `make`.

## Building

You need:

- Arm GNU toolchain (`arm-none-eabi-gcc`), for example the
  [xPack build](https://github.com/xpack-dev-tools/arm-none-eabi-gcc-xpack/releases).
- A MicroPython checkout that matches the badge firmware. Universe 2026
  firmware uses `pimoroni/micropython` tag `bw-1.29.0-gc`; check
  `ci/micropython.sh` in `pimoroni/tufty2350` for the current tag.
- `pyelftools` (`python -m pip install pyelftools`).

```sh
git clone --depth 1 --branch bw-1.29.0-gc https://github.com/pimoroni/micropython
python -m pip install pyelftools
python tools/gameboy/build.py --mpy-dir micropython
```

Pass `--cc path/to/arm-none-eabi-gcc` if the compiler is not on `PATH`. The
script writes `badge/apps/game_boy/gbcore.mpy`.

The module only loads on firmware whose `sys.implementation._mpy` matches the
build (`.mpy` v6.3, `armv7emsp`). Check a badge with:

```sh
mpremote connect PORT exec "import sys; print(sys.implementation._mpy)"
```

It should print `7942`.

## Performance

Measured on a Universe 2026 badge (RP2350 at 230 MHz) running Pokémon Red,
the core takes about 4 to 10.5 ms per Game Boy frame depending on the scene
(the Oak introduction is the heaviest seen), so it runs at 1.6 to 4 times real
speed. `-O2` and `-O3` perform the same and `-Os` is about 9% slower.

The app keeps the game at 59.7 frames per second by running as many emulated
frames as real time requires and rendering only the last one; Peanut-GB skips
line rendering entirely for the others. With `HIRES | VSYNC` the screen updates
about 42 to 45 times a second in light scenes and 22 to 37 in heavy ones.
