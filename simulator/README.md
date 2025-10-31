# Badge Simulator

`badge_simulator.py` lets you run badge apps locally by reproducing the `badgeware`
API on top of Pygame. Use it to iterate quickly or to smoke-test changes before
shipping them to the hardware badge.

## Prerequisites
- Python 3.10 or newer (3.11 is what we use for local testing).
- Pygame (`pip install pygame`).

## Quick Start

```bash
python simulator/badge_simulator.py -C badge badge/apps/flappy/__init__.py
```

- `--scale` enlarges the 160×120 framebuffer so the window is easier to see
  (default is 4).
- `-C DIR` forces the simulator to treat `DIR` as `/system`, useful when apps
  live outside the repo or you want to point at generated assets.
- The simulator automatically makes `/system/...` imports and file operations
  point at the repository tree so you can run unmodified badge apps.

## Controls
- `A` / `Z` → Button A
- `B` / `X` → Button B
- `C` / `Space` → Button C
- Arrow keys → D-pad
- `H` / `Esc` → Home / exit back to menu
- Close the window or press `Ctrl+C` in the terminal to stop the simulator.
