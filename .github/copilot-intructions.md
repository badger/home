# Copilot Instructions for Tufty 2040 Development

This project is for developing applications on a U25 Edition GitHub hackable conference badge - an RP2350-based microprocessor running MicroPython with a 320x240 TFT color display.  The board is a custom version of the Pimoroni Tufty 2350 with added IR sensors.

## Project Structure

```
/
├── badge/                     # Badge firmware and apps (deployed to /system/ on device)
│   ├── main.py               # Main entry point and app launcher
│   ├── secrets.py            # WiFi configuration secrets
│   ├── apps/                 # Application directory
│   │   ├── badge/            # GitHub profile stats viewer
│   │   ├── flappy/           # Flappy Bird style game
│   │   ├── gallery/          # Image gallery viewer
│   │   ├── menu/             # App launcher/menu system
│   │   ├── monapet/          # Virtual pet simulator
│   │   ├── quest/            # IR beacon scavenger hunt
│   │   ├── sketch/           # Drawing app
│   │   └── startup/          # Boot animation
│   └── assets/               # Shared assets (fonts, sprites)
│       ├── fonts/            # Pixel Perfect Fonts (.ppf, .af)
│       └── mona-sprites/     # Mona character sprite sheets
└── README.md
```

## Hardware Specifications

- **Display**: 320x240 TFT LCD (but badge uses 160x120 viewport with X2 scaling for performance)
- **Screen dimensions**: WIDTH=160, HEIGHT=120 (logical pixels)
- **Processor**: RP2350 (Raspberry Pi Pico architecture)
- **Platform**: MicroPython with custom badgeware library
- **Buttons**: 
  - UP (pin 22)
  - DOWN (pin 6) 
  - A (pin 7)
  - B (pin 8)
  - C (pin 9)
  - HOME (navigation button - triggers quit_to_launcher)
- **IR Receiver**: Pin 21 (used by quest app for beacon detection)

## App Development Guidelines

### Required App Structure

Every app must be in `/system/apps/<app_name>/` (or `badge/apps/<app_name>/` in repository) with:

1. **`__init__.py`** - Main app implementation with required functions:
   ```python
   def init():      # Optional: Called when app starts (for state loading)
   def update():    # Required: Called every frame for input handling and rendering
   def on_exit():   # Optional: Called when quitting app (for state saving)
   ```

2. **`icon.png`** - App icon (used by menu launcher)
   - **Format**: 24x24 pixel color PNG file
   - **Color space**: RGB with optional transparency
   - **Location**: Must be in the app's root directory

Apps should use path manipulation to ensure correct working directory:
```python
import sys
import os

sys.path.insert(0, "/system/apps/<app_name>")
os.chdir("/system/apps/<app_name>")
```

### Core Imports and Setup

```python
from badgeware import screen, Image, PixelFont, SpriteSheet, io, brushes, shapes, run, State

# Standard color definitions (RGB values)
BACKGROUND = brushes.color(r, g, b)
FOREGROUND = brushes.color(r, g, b, alpha)  # alpha is optional
HIGHLIGHT = brushes.color(r, g, b)

# Set up font
screen.font = PixelFont.load("/system/assets/fonts/ark.ppf")

# Enable 2x antialiasing if needed
screen.antialias = Image.X2
```

### State Management Pattern

```python
# Define default state dictionary
state = {
    "key": default_value,
    "count": 0,
    # ... other state variables
}

# Load saved state (merges with defaults) in init()
def init():
    State.load("app_name", state)

# Save state when app exits
def on_exit():
    State.save("app_name", state)

# Update state based on input
def update():
    if io.BUTTON_A in io.pressed:
        state["count"] += 1
        # State will be saved on exit
```

### Button Handling Best Practices

- Use `io.pressed` to detect button press events (fires once per press)
- Use `io.held` to detect buttons being held down (continuous detection)
- Available buttons: `io.BUTTON_A`, `io.BUTTON_B`, `io.BUTTON_C`, `io.BUTTON_UP`, `io.BUTTON_DOWN`
- Check `io.pressed` set membership: `if io.BUTTON_A in io.pressed:`
- Access timing: `io.ticks` for current time, `io.ticks_delta` for frame delta

### Display and Rendering

#### Basic Display Operations
```python
def update():
    # Clear screen with background color
    screen.brush = brushes.color(0, 0, 0)
    screen.clear()
    
    # OR draw a filled rectangle
    screen.brush = brushes.color(73, 219, 255)
    screen.draw(shapes.rectangle(0, 0, 160, 120))
    
    # Set font before text operations
    screen.font = PixelFont.load("/system/assets/fonts/ark.ppf")
    
    # Draw text
    screen.brush = brushes.color(255, 255, 255)
    screen.text("Hello", x, y)
    
    # No explicit update() call needed - handled by badgeware.run()
```

#### UI Layout Patterns
- **Screen Size**: 160x120 pixels (logical resolution)
- **Title Bar**: ~18px height at top
- **Bottom Bar**: ~18px height at bottom
- **Main Content Area**: Between title and bottom bars (~84px)

#### Text Handling
```python
# Measure text for positioning
text_width, text_height = screen.measure_text("text")
x_centered = 80 - (text_width / 2)  # Center on 160px width

# Draw text at position
screen.text("text", x, y)

# Text with transparency
screen.brush = brushes.color(255, 255, 255, 150)  # 150 alpha
screen.text("semi-transparent", x, y)
```

### Image Handling

#### PNG Support
```python
# Load and display PNG image
image = Image.load("path/to/image.png")
screen.blit(image, x, y)

# Scale blit (useful for sprites)
screen.scale_blit(image, x, y, width, height)

# Set image alpha
image.alpha = 150  # 0-255
screen.blit(image, x, y)
```

#### Sprite Sheets
```python
# Load animated sprite sheet
sprite = SpriteSheet("path/to/spritesheet.png", columns, rows).animation()

# Get frame for current time
frame = sprite.frame(io.ticks / 100)  # Adjust divisor for speed
screen.blit(frame, x, y)

# Or scale blit
screen.scale_blit(frame, x, y, width, height)
```

#### File System Operations
- Use relative paths from app directory or absolute paths from `/system/`
- Handle `OSError` exceptions for missing files/directories
- Skip hidden files (starting with `.`) when listing directories
- Use `badgeware.file_exists(path)` and `badgeware.is_dir(path)` for checks

### Common Patterns

#### Navigation Lists
```python
# Use modulo for wrapping navigation
current_index = (current_index + 1) % len(items)  # Next
current_index = (current_index - 1) % len(items)  # Previous
```

#### UI Toggles
```python
# Boolean state toggles
state["show_ui"] = not state["show_ui"]

# Conditional rendering
if state["show_ui"]:
    # Draw UI elements
else:
    # Hide UI elements
```

#### Error Handling
```python
try:
    # File operations
    files = os.listdir('directory')
except OSError:
    # Handle missing directory gracefully
    files = []
```

## Available Libraries

- `badgeware` - Core system functionality:
  - `screen` - Display object
  - `io` - Input handling (buttons, timing)
  - `brushes` - Color creation
  - `shapes` - Drawing primitives (rectangle, rounded_rectangle, etc.)
  - `Image` - Image loading and manipulation
  - `PixelFont` - Font loading
  - `SpriteSheet` - Sprite sheet handling
  - `State` - Persistent state management
  - `run()` - Main loop runner
  - `file_exists()`, `is_dir()` - File system helpers
- `network` - WiFi connectivity
- `urllib.urequest` - HTTP requests
- `json` - JSON parsing
- `math`, `random` - Standard math operations
- Standard MicroPython libraries (`os`, `sys`, `gc`, etc.)

## Development Tips

1. **Always test with real hardware** - MicroPython environment differs from desktop Python
2. **Memory management** - Be mindful of RAM usage; use `gc.collect()` when needed
3. **App lifecycle** - Use `init()` for setup, `update()` for main loop, `on_exit()` for cleanup
4. **User experience** - Provide clear navigation hints and error messages
5. **State persistence** - Use `State.load()` and `State.save()` for important user data
6. **File paths** - Use `/system/` prefix for absolute paths, handle missing files gracefully
7. **Performance** - Keep `update()` function efficient as it runs every frame
8. **Button handling** - Use `io.pressed` for single actions, `io.held` for continuous input
9. **Timing** - Use `io.ticks` (milliseconds) for animations and time-based logic

## Example Apps Reference

The `badge/apps/` directory contains several complete example applications:

### Badge (`badge/`)
**GitHub Stats Viewer** - Displays GitHub profile statistics including contributions graph, followers, and avatar.
- **Key features**: WiFi connectivity, HTTP API calls, JSON parsing, image downloading
- **Demonstrates**: Network operations, async data fetching, state management
- **Technologies**: `network.WLAN`, `urllib.urequest`, JSON API integration

### Flappy (`flappy/`)
**Flappy Bird Style Game** - A side-scrolling game where Mona jumps between obstacles.
- **Key features**: Game state machine, sprite animation, collision detection, scrolling backgrounds
- **Demonstrates**: Game loop structure, parallax scrolling, score tracking
- **Technologies**: `SpriteSheet`, multiple game states, physics simulation

### Gallery (`gallery/`)
**Image Gallery** - Browse through images with thumbnail navigation.
- **Key features**: Image loading, smooth scrolling, thumbnail strip, UI toggle. Great for loading and viewing user-provided images, why not show off you project or company logo.
- **Demonstrates**: File system operations, list navigation, animated transitions
- **Technologies**: `Image.load()`, `os.listdir()`, smooth interpolation

### Menu (`menu/`)
**App Launcher** - The main menu system for launching other apps.
- **Key features**: Grid-based icon navigation, dynamic app discovery, return to launcher
- **Demonstrates**: App management, animation, icon system, HOME button interrupt handling
- **Technologies**: File system scanning, modular app loading

### Monapet (`monapet/`)
**Virtual Pet** - A virtual pet care simulator.
- **Key features**: Time-based stat decay, multiple stats (happiness, hunger, cleanliness), animations
- **Demonstrates**: Real-time simulation, state persistence, animated sprites with actions
- **Technologies**: `io.ticks_delta` for time tracking, complex state management

### Quest (`quest/`)
**IR Scavenger Hunt** - Collect locations using IR beacons at the conference.
- **Key features**: IR receiver integration, quest tracking, completion animations
- **Demonstrates**: Hardware integration (IR), persistent progress tracking, visual feedback
- **Technologies**: `aye_arr.nec.NECReceiver`, IR beacon protocol, custom protocol handling

### Sketch (`sketch/`)
**Drawing App** - A simple drawing canvas with cursor control.
- **Key features**: Pixel drawing, animated UI elements, cursor tracking
- **Demonstrates**: Drawing to offscreen buffer, cursor positioning, character animation
- **Technologies**: Offscreen `Image` as canvas, real-time drawing

### Startup (`startup/`)
**Boot Animation** - Animated splash screen shown on badge startup.
- **Key features**: Frame-based animation sequence
- **Demonstrates**: Simple animation playback, intro/splash screens
- **Technologies**: Frame sequencing, timed display

Each app follows the standard structure with `__init__.py`, uses the `badgeware.run()` pattern, and demonstrates different aspects of badge development. Refer to these examples when building new apps.