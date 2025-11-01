# Badge Simulator

`badge_simulator.py` lets you run badge apps locally by reproducing the `badgeware`
API on top of Pygame. Use it to iterate quickly or to smoke-test changes before
shipping them to the hardware badge.

## Prerequisites
- Python 3.10 or newer (3.13 recommended).
- Pygame (`pip install pygame`).

## Setup

### Option 1: Virtual Environment (Recommended)

Create and activate a virtual environment to isolate dependencies:

```bash
# Create virtual environment
python3 -m venv .venv

# Activate it (macOS/Linux)
source .venv/bin/activate

# Activate it (Windows)
.venv\Scripts\activate

# Install pygame
pip install pygame
```

Once activated, your shell prompt will show `(.venv)` and you can use `python` directly:

```bash
python simulator/badge_simulator.py -C badge badge/apps/flappy/__init__.py
```

To deactivate the virtual environment when done:

```bash
deactivate
```

### Option 2: System Python

If you prefer not to use a virtual environment:

```bash
pip3 install pygame
python3 simulator/badge_simulator.py -C badge badge/apps/flappy/__init__.py
```

**Note:** If you have multiple Python versions installed, ensure pygame is installed for the version you're using to run the simulator.

## Quick Start

```bash
python simulator/badge_simulator.py -C badge badge/apps/flappy/__init__.py
```

## Command Line Options

- `--scale` enlarges the 160×120 framebuffer so the window is easier to see
  (default is 4).
- `-C DIR` forces the simulator to treat `DIR` as `/system`, useful when apps
  live outside the repo or you want to point at generated assets.
- `--screenshots DIR` specifies a directory to save screenshots when you press F12.
  Screenshots are saved at native badge resolution (160×120) in PNG format.
- The simulator automatically makes `/system/...` imports and file operations
  point at the repository tree so you can run unmodified badge apps.

## Controls
- `A` / `Z` → Button A
- `B` / `X` → Button B
- `C` / `Space` → Button C
- Arrow keys → D-pad
- `H` / `Esc` → Home / exit back to menu
- `F12` → Take screenshot (when --screenshots is configured)
- Close the window or press `Ctrl+C` in the terminal to stop the simulator.

## Examples

Run the menu app:
```bash
python simulator/badge_simulator.py -C badge badge/apps/menu/__init__.py
```

Run Flappy Bird with screenshots enabled:
```bash
python simulator/badge_simulator.py -C badge --screenshots ./screenshots badge/apps/flappy/__init__.py
```

Run at 2x scale for a smaller window:
```bash
python simulator/badge_simulator.py -C badge --scale 2 badge/apps/life/__init__.py
```
