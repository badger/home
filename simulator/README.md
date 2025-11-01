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
python simulator/badge_simulator.py badge/apps/flappy
```

To deactivate the virtual environment when done:

```bash
deactivate
```

### Option 2: System Python

If you prefer not to use a virtual environment:

```bash
pip3 install pygame
python3 simulator/badge_simulator.py badge/apps/flappy
```

**Note:** If you have multiple Python versions installed, ensure pygame is installed for the version you're using to run the simulator.

## Quick Start

```bash
python3 simulator/badge_simulator.py badge/apps/flappy
```

The simulator automatically:
- Uses `badge/` as the default system root (no need for `-C badge`)
- Looks for `__init__.py` when you specify a directory
- Sets the window title and icon based on the app
- Cleans up `__pycache__` directories when you exit
- Provides mock `network` and `urllib.urequest` modules for WiFi-enabled apps

## Network Simulation

Apps that use WiFi (like the badge stats viewer) work in the simulator through mock network modules:

- **`network.WLAN`**: Simulates WiFi connectivity, accepting any SSID/password
- **`urllib.urequest.urlopen`**: Proxies HTTP requests through your computer's network
- Connection simulation includes a realistic 1.5 second delay
- All network requests use your local machine's internet connection

To test WiFi apps:
1. Create a `badge/secrets.py` file with your WiFi credentials and GitHub username
2. Run the app - the simulator will mock the WiFi connection and fetch real data
3. The app behaves identically to the hardware badge, but uses your computer's network

Example `badge/secrets.py`:
```python
WIFI_SSID = "YourNetworkName"
WIFI_PASSWORD = "YourPassword"
GITHUB_USERNAME = "yourusername"
```

## Command Line Options

- `--scale` enlarges the 160×120 framebuffer so the window is easier to see
  (default is 4).
- `-C DIR` forces the simulator to treat `DIR` as `/system`. By default, the simulator
  uses `badge/` relative to the simulator directory. Override this when apps
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
python3 simulator/badge_simulator.py badge/apps/menu
```

Run Flappy Bird with screenshots enabled:
```bash
python3 simulator/badge_simulator.py badge/apps/flappy --screenshots ./screenshots
```

Run at 2x scale for a smaller window:
```bash
python3 simulator/badge_simulator.py badge/apps/life --scale 2
```

Run a specific file directly (also works):
```bash
python3 simulator/badge_simulator.py badge/apps/gallery/__init__.py
```

Use a custom system root:
```bash
python3 simulator/badge_simulator.py -C /path/to/custom/badge badge/apps/quest
```
