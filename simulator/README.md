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

## IR Beacon Simulation

Apps that use IR receiver/transmitter functionality (like the Quest scavenger hunt) work in the simulator through mock `aye_arr` modules:

- **`aye_arr.nec.NECReceiver`**: Simulates IR receiver for detecting beacons
- **Number keys (1-9)**: Press to simulate detecting IR beacons
- The simulator prints messages when beacons are "detected"

To test IR apps:
1. Run the Quest app: `python3 simulator/badge_simulator.py badge/apps/quest`
2. Press number keys 1-9 to simulate finding different beacons
3. Each number corresponds to a different quest location
4. Rate limited to once per second to prevent accidental double-triggers

Example:
```bash
python3 simulator/badge_simulator.py badge/apps/quest
# Press '1' to simulate finding beacon 1, '2' for beacon 2, etc.
```

## Command Line Options

- `--scale` enlarges the 160×120 framebuffer so the window is easier to see
  (default is 4).
- `-C DIR` forces the simulator to treat `DIR` as `/system`. By default, the simulator
  uses `badge/` relative to the simulator directory. Override this when apps
  live outside the repo or you want to point at generated assets.
- `--screenshots DIR` specifies a directory to save screenshots when you press F12.
  Screenshots are saved at native badge resolution (160×120) in PNG format.
- `--clean` removes all temporary files (cached downloads, saved state) before starting.
  Useful for forcing apps to re-fetch data or testing the initial load experience.
- `--perf` shows live performance metrics (FPS, CPU, and memory usage) in the terminal.
  Requires `psutil` to be installed (`pip install psutil`). Metrics update every 0.5 seconds.
  **Badge profiling**: Shows app memory usage relative to the badge's 512KB SRAM limit with warnings
  when memory usage is high or exceeds the badge's capacity.
- The simulator automatically makes `/system/...` imports and file operations
  point at the repository tree so you can run unmodified badge apps.

## App Launching

The simulator now supports apps launching other apps, just like on the hardware badge:

- When you run the menu app and select another app, it automatically loads
- Press the **Home button (H or Esc)** to return to the menu from any app
- Apps can return a path to another app (e.g., `return "/system/apps/flappy"`)
- The simulator will clean up the previous app's modules and load the new one

This means you can test the full badge experience, starting from the menu and navigating
between apps without restarting the simulator. Press H or Esc at any time to go back to the menu!

## Controls
- `A` / `Z` → Button A
- `B` / `X` → Button B
- `C` / `Space` → Button C
- Arrow keys → D-pad
- **`H` / `Esc` → Home (return to menu)**
- `1-9` → Simulate IR beacons (Quest app)
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

Clean cached files and start fresh:
```bash
python3 simulator/badge_simulator.py badge/apps/badge --clean
```

This removes temporary files including downloaded avatars, API responses, and saved app state.

Show performance metrics in the terminal:
```bash
python3 simulator/badge_simulator.py badge/apps/flappy --perf
```

This displays live FPS, CPU usage, and memory usage while the app runs. Requires `psutil` (`pip install psutil`).

Run the menu and navigate to other apps:
```bash
python3 simulator/badge_simulator.py badge/apps/menu
```

The simulator will automatically load apps you select from the menu, just like the real badge.

## Simulator Accuracy & Badge Profiling

### How Accurate is the Simulator?

The simulator aims to provide a faithful reproduction of the badge's behavior, but there are important differences:

**What's Accurate:**
- ✅ Display resolution (160x120 pixels)
- ✅ Button mappings and input handling
- ✅ Frame rate (60 FPS)
- ✅ Drawing API (shapes, text, images, sprites)
- ✅ App structure and lifecycle (init, update, on_exit)
- ✅ App launching and navigation
- ✅ State persistence between sessions
- ✅ Network/WiFi simulation (using your computer's network)
- ✅ IR beacon simulation (via number keys)

**What's Different:**
- ❌ **Memory**: Desktop Python uses ~100-200x more memory than MicroPython
- ❌ **CPU Speed**: Desktop is much faster than RP2350 @ 200MHz
- ⚠️ **Memory Management**: Python's garbage collector vs MicroPython's simpler model
- ⚠️ **Module Import Speed**: Faster on desktop
- ⚠️ **Image Loading**: Desktop has more RAM for caching

### Badge Memory Profiling

Use `--perf` to profile your app's **asset memory usage** and **performance** relative to the badge:

```bash
python3 simulator/badge_simulator.py badge/apps/myapp --perf
```

**Understanding the output:**
```
[Perf] FPS: 60.0 Frame: 16.5ms ✓ | Badge~ 42.1KB ✓ | Imgs:7( 14.4KB) Fonts:1
              ^^^        ^^^^^                ^^^^       ^^^   ^^^^^^    ^^^^
             Frame      Frame                Badge      Count  Largest  Fonts
             rate       time                 memory            image
```

**Performance metrics:**
- **FPS**: Frames per second (target: 60)
- **Frame**: Time per frame in milliseconds (target: < 16.67ms for 60 FPS)
  - `✓` Fast (< 16.67ms) - Will run smoothly on badge
  - `⚡` Over budget (16.67-25ms) - May drop frames on badge
  - `⚠️  Slow!` Too slow (> 25ms) - Will definitely lag on badge

**Memory metrics:**
- **Badge~XXX KB**: Estimated memory usage on the badge based on loaded assets
- **Imgs:N(XXX KB)**: Number of images loaded and size of the largest one
- **Fonts:N**: Number of fonts loaded

**Memory indicators:**
- `✓` Safe (< 200KB)
- `⚡ Med` Medium usage (200-300KB)
- `⚡ High` High usage (300-400KB) 
- `⚠️  OVER LIMIT!` Exceeds 400KB (may fail on badge)

**How it works:**
The profiler tracks every image and font loaded via `Image.load()` and `PixelFont.load()`, then estimates MicroPython memory:
- **Images**: ~2 bytes/pixel (RGB565 format typical on badge)
- **Fonts**: ~20KB each (rough average)
- **Asset counter resets** when switching apps or pressing Home

**What to look for:**
1. **Frame time > 16.67ms** = Badge will drop frames (optimize your update() function)
2. **Total memory > 400KB** = Likely to fail on badge (reduce assets)
3. **Largest image > 150KB** = Consider splitting or reducing image size
4. **Many images** = Consider using sprite sheets instead of individual files
5. **FPS dropping over time** = Performance degradation (check for inefficient loops)

**Why frame time matters more than CPU%:**
- Your desktop CPU is 10-100x faster than the badge's RP2350
- CPU% doesn't translate between different processors
- **Frame time is universal**: If it takes > 16.67ms, the badge can't maintain 60 FPS
- The badge's MicroPython is also slower than desktop Python, so add a safety margin

**Important notes:**
1. **Asset-based estimation**: Counts actual images/fonts, not Python interpreter overhead
2. **Conservative estimate**: Uses 2 bytes/pixel; paletted images use less (1 byte)
3. **Doesn't track everything**: Code, variables, and buffers add overhead too
4. **Always test on hardware**: This is an estimate to catch obvious problems early

**Best practices for badge memory:**
- Use sprite sheets (one large image) instead of many small images
- Use paletted PNGs when possible (especially for pixel art)
- Unload images when switching screens (`del image` and rely on cache)
- Keep individual images < 100KB when possible
- Load assets on-demand, not all at startup
- Watch the "Imgs" count - if it keeps growing, you have a leak

**Example workflow:**
```bash
# Profile your app
python3 simulator/badge_simulator.py badge/apps/myapp --perf

# Navigate around (press H to go home and back)
# Watch the Badge~XXX KB value - should stay stable or decrease

# If you see ⚠️  OVER LIMIT!:
# 1. Check the "Imgs" count - are you loading too many?
# 2. Check largest image size - can you optimize it?
# 3. Use sprite sheets to combine small images
# 4. Convert to paletted PNG if it's pixel art
```
