# Copilot Instructions for Universe 2025 Tufty Badge Development

This project is for developing applications on the GitHub Universe 2025 hackable conference badge - a custom Pimoroni Tufty 2350 edition. It's an RP2350-based device running MicroPython with a 320x240 TFT color display (pixel-doubled to 160x120 for performance) and custom IR sensors.

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

- **Processor**: RP2350 Dual-core ARM Cortex-M33 @ 200MHz
- **Memory**: 512kB SRAM, 16MB QSPI XiP flash
- **Display**: 320x240 full colour IPS display (pixel doubled to 160x120 for performance)
- **Screen dimensions**: WIDTH=160, HEIGHT=120 (logical pixels)
- **Connectivity**: 2.4GHz WiFi and Bluetooth 5
- **Battery**: 1000mAh rechargeable (up to 8 hours runtime)
- **Platform**: MicroPython with custom badgeware library
- **Buttons**: 
  - UP, DOWN, A, B, C (front-facing buttons)
  - HOME (back button - triggers quit_to_launcher to return to menu)
  - RESET, BOOTSEL (hardware buttons)
- **IR**: Receiver and transmitter for beacon hunting and remote control
- **Ports**: USB-C (charging/programming), Qw/ST, SWD
- **GPIO**: 4 GPIO pins + power through-hole solder pads
- **LEDs**: 4-zone backlight (TOP_LEFT, TOP_RIGHT, BOTTOM_LEFT, BOTTOM_RIGHT)
- **Case**: Durable polycarbonate with lanyard fixings
- **Runtime**: MicroPython v1.14-5485 with custom badgeware library and built-in modules (see below)

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

### Built-in Modules ###
The following built in modules are available to the MicroPython code running on the device:

array, binascii, builtins, cmath, collections, errno, gc, hashlib, heapq, io, json, machine, math, micropython, network, os, platform, random, re,select, socket, ssl, struct, sys,time, uctypes, rp2, bluetooth, cryptolib, deflate, framebuf, vfs, lwip, ntptime, mip, badgeware,picovector, pimoroni, pimoroni_i2c, qrcode, st7789, powman, board, boot, datetime, ezwifi, pcf85063a, qwstpad, cppmem, adcfft, aioble, asyncio, uasyncio, requests, urequests, urllib, webrepl, websocket, umqtt, ulab, aye_arr, breakout_as7262, breakout_as7343, breakout_bh1745, breakout_bme280, breakout_bme68x, breakout_bme69x, breakout_bmp280, breakout_dotmatrix, breakout_encoder, breakout_encoder_wheel, breakout_icp10125, breakout_ioexpander, breakout_ltr559, breakout_matrix11x7, breakout_mics6814, breakout_msa301, breakout_paa5100, breakout_pmw3901, breakout_potentiometer, breakout_rgbmatrix5x5, breakout_rtc, breakout_scd41, breakout_sgp30, breakout_trackball, breakout_vl53l5cx

### Core Imports and Setup

```python
from badgeware import screen, Image, PixelFont, SpriteSheet, io, brushes, shapes, run, Matrix

# Standard color definitions (RGB values)
BACKGROUND = brushes.color(r, g, b)
FOREGROUND = brushes.color(r, g, b, alpha)  # alpha is optional (0-255)
HIGHLIGHT = brushes.color(r, g, b)

# Set up font - loads from /system/assets/fonts/
screen.font = PixelFont.load("/system/assets/fonts/nope.ppf")

# Enable antialiasing for smooth vector graphics
screen.antialias = Image.X2  # or Image.X4 for higher quality, Image.OFF to disable
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
- Use `io.released` to detect when a button is released
- Use `io.changed` to detect any state change
- Available buttons: `io.BUTTON_A`, `io.BUTTON_B`, `io.BUTTON_C`, `io.BUTTON_UP`, `io.BUTTON_DOWN`, `io.BUTTON_HOME`
- Check button state with set membership: `if io.BUTTON_A in io.pressed:`
- Access timing: `io.ticks` for milliseconds since boot, `io.ticks_delta` for frame delta time

### Display and Rendering

#### Basic Display Operations
```python
def update():
    # Clear screen with background color (fastest method)
    screen.brush = brushes.color(0, 0, 0)
    screen.clear()
    
    # OR draw a filled rectangle over entire screen
    screen.brush = brushes.color(73, 219, 255)
    screen.draw(shapes.rectangle(0, 0, 160, 120))
    
    # Draw shapes using current brush
    screen.brush = brushes.color(255, 0, 0)
    screen.draw(shapes.circle(80, 60, 20))
    
    # Draw text (set font first)
    screen.font = PixelFont.load("/system/assets/fonts/nope.ppf")
    screen.brush = brushes.color(255, 255, 255)
    screen.text("Hello Badge!", 10, 10)
    
    # No explicit display update needed - handled by badgeware.run()
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

### Image and Sprite Handling

#### Loading and Displaying Images
```python
# Load PNG image (supports true color RGBA and paletted)
image = Image.load("/system/apps/myapp/assets/sprite.png")

# Blit image at position
screen.blit(image, x, y)

# Scale blit to specific dimensions (negative dims flip image)
screen.scale_blit(image, x, y, width, height)

# Set transparency
image.alpha = 150  # 0-255, affects entire image
screen.blit(image, x, y)

# Create image window (subsection for clipping)
window = image.window(x, y, width, height)
```

#### Sprite Sheets and Animation
```python
# Load sprite sheet (specify columns and rows)
sprite_sheet = SpriteSheet("/system/assets/mona-sprites/mona-default.png", 7, 1)

# Create animation from sheet
animation = sprite_sheet.animation()

# Get current frame based on time
frame = animation.frame(io.ticks / 100)  # Adjust divisor for animation speed
screen.blit(frame, x, y)

# Or get specific sprite from sheet
sprite = sprite_sheet.sprite(column, row)
screen.scale_blit(sprite, x, y, width, height)
```

#### File System Operations
- Use relative paths from app directory or absolute paths from `/system/`
- Handle `OSError` exceptions for missing files/directories
- Skip hidden files (starting with `.`) when listing directories
- Use `badgeware.file_exists(path)` and `badgeware.is_dir(path)` for checks

### Shape Transformations

Shapes can be transformed using Matrix operations for animations and effects:

```python
from badgeware import shapes, Matrix

# Create a shape
rect = shapes.rectangle(-10, -10, 20, 20)

# Apply transformations (chaining supported)
rect.transform = Matrix().translate(80, 60).scale(2, 2).rotate(io.ticks / 100)

# Draw transformed shape
screen.brush = brushes.color(255, 0, 0)
screen.draw(rect)

# Create stroked (outline) shapes
circle_outline = shapes.circle(80, 60, 30).stroke(3)  # 3px width outline
```

### Common Patterns

#### Navigation Lists
```python
# Use modulo for wrapping navigation
current_index = (current_index + 1) % len(items)  # Next
current_index = (current_index - 1) % len(items)  # Previous

# Clamp values to ranges
x = max(0, min(x, 160))  # Clamp x to screen width
```

#### Animation Timing
```python
# Smooth animations using ticks
angle = (io.ticks / 1000) * 360  # Full rotation per second
offset = math.sin(io.ticks / 500) * 20  # Oscillate ±20 pixels

# Frame-rate independent movement
velocity_x = 50  # pixels per second
x += velocity_x * (io.ticks_delta / 1000)
```

#### Error Handling
```python
try:
    # File operations
    files = os.listdir('/system/apps/myapp/assets')
except OSError:
    # Handle missing directory gracefully
    files = []

# Check before loading
if file_exists("/system/apps/myapp/data.json"):
    with open("/system/apps/myapp/data.json", "r") as f:
        data = json.load(f)
```

## Available Libraries and Modules

### badgeware - Core System Library
- `screen` - Main display framebuffer (160x120 Image object)
- `io` - Input handling (buttons, timing with ticks/ticks_delta)
- `brushes.color(r, g, b, alpha=255)` - Create color brushes for drawing
- `shapes` - Drawing primitives:
  - `rectangle(x, y, w, h)` - Rectangles
  - `rounded_rectangle(x, y, w, h, r)` - Rounded corners
  - `circle(x, y, r)` - Circles
  - `arc(x, y, r, from_deg, to_deg)` - Arcs
  - `pie(x, y, r, from_deg, to_deg)` - Pie slices
  - `line(x1, y1, x2, y2, thickness)` - Lines
  - `regular_polygon(x, y, r, sides)` - Polygons
  - `squircle(x, y, r, n=4)` - Squircles
- `Image` - Image loading, manipulation, and drawing surface
- `PixelFont` - Pixel font loading and text rendering
- `SpriteSheet` - Sprite sheet handling with animation support
- `Matrix` - Transformation matrices (translate, rotate, scale)
- `run(update_func)` - Main loop runner that calls update_func every frame
- `file_exists(path)`, `is_dir(path)` - File system helpers
- `get_battery_level()`, `is_charging()` - Battery status

### Standard MicroPython Libraries
- `network` - WiFi connectivity (network.WLAN)
- `urllib.urequest` - HTTP requests
- `json` - JSON parsing and serialization
- `math`, `random` - Mathematical operations
- `os`, `sys`, `gc` - System utilities
- `time` - Time and sleep functions
- `bluetooth` - Bluetooth functionality

## Development Tips and Best Practices

1. **App Structure** - Every app must have `__init__.py` with `update()` function; `init()` and `on_exit()` are optional
2. **Icon Required** - Apps need a 24x24 PNG `icon.png` to appear in the menu launcher
3. **Memory Management** - Limited RAM; use paletted images when possible, call `gc.collect()` for large operations
4. **Performance** - `update()` runs every frame; keep it efficient, avoid heavy computations
5. **File Paths** - Use `/system/` for absolute paths; assets in app directory are auto-pathed
6. **Button Handling** - Use `io.pressed` for single actions, `io.held` for continuous movement
7. **Screen Clearing** - Use `screen.clear()` with brush color, not drawing full-screen rectangles
8. **Antialiasing** - Enable `screen.antialias = Image.X2` or `Image.X4` for smooth vector graphics
9. **Text Rendering** - Always set `screen.font` before calling `screen.text()`
10. **Transformations** - Use `Matrix()` chaining for efficient shape transformations
11. **State Management** - Store persistent data in `/` LittleFS partition, not `/system/`
12. **Error Handling** - Always wrap file operations in try/except for missing files/directories
13. **Timing** - Use `io.ticks` (milliseconds) for animations; `io.ticks_delta` for frame-independent movement
14. **HOME Button** - Automatically handled by main.py; calls `on_exit()` before returning to menu
15. **Testing** - Test on real hardware; MicroPython differs from desktop Python

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
