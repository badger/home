# AGENTS.md - Badge App Development Guide for LLMs

This document provides comprehensive context for developing applications for the GitHub Universe 2025 Tufty Badge.

## Hardware Overview

The GitHub Universe 2025 badge is a custom Pimoroni Tufty 2350 device with the following specifications:

- **Processor**: RP2350 Dual-core ARM Cortex-M33 @ 200MHz
- **Memory**: 512kB SRAM, 16MB QSPI XiP flash
- **Display**: 320x240 full colour IPS (pixel-doubled to 160x120 logical pixels for performance)
- **Screen Dimensions**: WIDTH=160, HEIGHT=120 (all app coordinates use these logical pixels)
- **Runtime**: MicroPython v1.14-5485 with custom badgeware library
- **Connectivity**: 2.4GHz WiFi and Bluetooth 5
- **Battery**: 1000mAh rechargeable lithium polymer (up to 8 hours runtime)
- **Buttons**: 
  - **Front**: UP, DOWN, A, B, C
  - **Back**: HOME (returns to launcher menu)
  - **Hardware**: RESET, BOOTSEL
- **IR**: Receiver (pin 21) and transmitter for beacon hunting and remote control
- **LEDs**: 4-zone backlight (TOP_LEFT, TOP_RIGHT, BOTTOM_LEFT, BOTTOM_RIGHT)
- **Ports**: USB-C (charging/programming), Qw/ST connector, SWD debug
- **GPIO**: 4 additional GPIO pins + power available through solder pads

## App Structure and Lifecycle

### Directory Layout
```
/system/apps/<app_name>/
    __init__.py         # Required - contains init(), update(), on_exit()
    icon.png            # Required - 24x24 PNG icon for launcher
    assets/             # Optional - images, fonts, data files
        *.png           # Images (PNG format, true color or paletted)
        *.ppf           # Pixel fonts (if not using system fonts)
        *.json          # Data files
```

### Required Functions

#### `update()` - Main Loop (REQUIRED)
Called every frame by the main loop. This is where all app logic, input handling, and rendering happens.

```python
def update():
    # 1. Handle input
    if io.BUTTON_A in io.pressed:
        # Button A was just pressed
        pass
    
    if io.BUTTON_B in io.held:
        # Button B is being held down
        pass
    
    # 2. Update game state/logic
    # Use io.ticks for milliseconds since boot
    # Use io.ticks_delta for frame delta time
    
    # 3. Clear screen
    screen.brush = brushes.color(0, 0, 0)
    screen.clear()
    
    # 4. Draw everything
    screen.brush = brushes.color(255, 255, 255)
    screen.text("Hello", 10, 10)
    
    # No explicit display update needed - handled automatically
```

#### `init()` - Initialization (OPTIONAL)
Called once when the app starts. Use for loading resources, setting up state, etc.

```python
def init():
    global game_state, sprite_sheet, font
    
    # Load resources
    sprite_sheet = SpriteSheet("/system/apps/myapp/assets/sprites.png", 4, 2)
    font = PixelFont.load("/system/assets/fonts/nope.ppf")
    
    # Initialize state
    game_state = {
        "score": 0,
        "level": 1,
        "player_x": 80,
        "player_y": 60
    }
    
    # Set up screen
    screen.font = font
    screen.antialias = Image.X2
```

#### `on_exit()` - Cleanup (OPTIONAL)
Called when the user presses HOME or the app terminates. Use for saving state, cleanup, etc.

```python
def on_exit():
    # Save state to file
    try:
        with open("/myapp_save.json", "w") as f:
            json.dump(game_state, f)
    except:
        pass  # Handle gracefully
```

### Starting the App
At the bottom of `__init__.py`, call `run()` with your update function:

```python
run(update)
```

## badgeware API Reference

### Core Modules

#### `screen` - Main Display (160x120 Image object)
The primary drawing surface. All rendering happens on this object.

**Properties:**
- `screen.width` - Always 160
- `screen.height` - Always 120
- `screen.brush` - Current brush (color) for drawing
- `screen.font` - Current font for text rendering
- `screen.antialias` - Antialiasing mode (Image.OFF, Image.X2, Image.X4)
- `screen.alpha` - Global alpha transparency (0-255)

**Methods:**
```python
# Clear screen with current brush color (fastest)
screen.clear()

# Draw shapes (requires screen.brush to be set)
screen.draw(shape)  # shape from shapes module

# Draw text at position
screen.text("Hello", x, y)

# Measure text size
width = screen.measure_text("Hello")

# Blit (copy) image at position
screen.blit(image, x, y)

# Scale blit (resize while blitting, negative dims flip)
screen.scale_blit(image, x, y, width, height)
```

#### `io` - Input and Timing
Handles button state and timing.

**Button Constants:**
- `io.BUTTON_A`, `io.BUTTON_B`, `io.BUTTON_C`
- `io.BUTTON_UP`, `io.BUTTON_DOWN`
- `io.BUTTON_HOME`

**Button State Sets:**
```python
# Buttons just pressed this frame (single fire)
if io.BUTTON_A in io.pressed:
    # Triggered once per press
    
# Buttons currently held down
if io.BUTTON_B in io.held:
    # Triggered every frame while held
    
# Buttons just released this frame
if io.BUTTON_C in io.released:
    # Triggered once on release
    
# Buttons that changed state this frame
if io.BUTTON_UP in io.changed:
    # Triggered on press or release
```

**Timing:**
```python
# Milliseconds since boot
current_time = io.ticks

# Milliseconds since last frame
delta = io.ticks_delta

# Frame-independent movement example
speed = 50  # pixels per second
x += speed * (io.ticks_delta / 1000)

# Animation timing
angle = (io.ticks / 1000) * 360  # Full rotation per second
```

**LED Control:**
```python
# LED position constants
io.LED_TOP_LEFT, io.LED_TOP_RIGHT
io.LED_BOTTOM_LEFT, io.LED_BOTTOM_RIGHT

# Set LED brightness (0-255)
io.led[io.LED_TOP_LEFT] = 128
```

#### `brushes` - Color Creation
Create color brushes for drawing.

```python
# Create color (RGB)
red = brushes.color(255, 0, 0)

# With alpha transparency (0=transparent, 255=opaque)
semi_transparent = brushes.color(255, 0, 0, 128)

# Set as current brush
screen.brush = brushes.color(100, 200, 50)
```

#### `shapes` - Drawing Primitives
All shapes return shape objects that can be drawn with `screen.draw()`.

```python
# Rectangle (x, y, width, height)
rect = shapes.rectangle(10, 10, 50, 30)

# Rounded rectangle (x, y, width, height, corner_radius)
rounded = shapes.rounded_rectangle(10, 10, 50, 30, 5)

# Circle (x, y, radius)
circle = shapes.circle(80, 60, 20)

# Arc (x, y, radius, from_degrees, to_degrees)
arc = shapes.arc(80, 60, 30, 0, 180)

# Pie slice (x, y, radius, from_degrees, to_degrees)
pie = shapes.pie(80, 60, 30, 45, 135)

# Line (x1, y1, x2, y2, thickness)
line = shapes.line(10, 10, 150, 110, 3)

# Regular polygon (x, y, radius, sides)
hexagon = shapes.regular_polygon(80, 60, 30, 6)

# Squircle (x, y, radius, n=4)
squircle = shapes.squircle(80, 60, 30, 4)

# Stroke (outline) a shape
outline = shapes.circle(80, 60, 30).stroke(3)  # 3px outline width
```

**Drawing:**
```python
screen.brush = brushes.color(255, 0, 0)
screen.draw(shapes.circle(80, 60, 20))
```

#### `Matrix` - Transformations
Transform shapes with translation, rotation, and scaling.

```python
from badgeware import Matrix

# Create transformation
transform = Matrix()

# Translate (move)
transform = transform.translate(x, y)

# Scale (resize, can be negative to flip)
transform = transform.scale(x_scale, y_scale)

# Rotate (degrees)
transform = transform.rotate(degrees)

# Rotate (radians)
transform = transform.rotate_radians(radians)

# Combine transformations (chaining)
transform = Matrix().translate(80, 60).scale(2, 2).rotate(45)

# Apply to shape
rect = shapes.rectangle(-10, -10, 20, 20)
rect.transform = Matrix().translate(80, 60).rotate(io.ticks / 10)
screen.draw(rect)
```

#### `Image` - Image Loading and Manipulation
Load and work with PNG images.

```python
# Load PNG image (supports true color RGBA and paletted)
image = Image.load("/system/apps/myapp/assets/sprite.png")

# Properties
width = image.width
height = image.height

# Set transparency for entire image
image.alpha = 128  # 0-255

# Set antialiasing
image.antialias = Image.X2  # Image.OFF, Image.X2, Image.X4

# Set current brush/font for drawing ON the image
image.brush = brushes.color(255, 0, 0)
image.font = my_font

# Draw on image (same methods as screen)
image.draw(shapes.circle(10, 10, 5))
image.text("Hi", 0, 0)

# Create window (clipped subsection)
sub_image = image.window(x, y, width, height)

# Display on screen
screen.blit(image, x, y)
screen.scale_blit(image, x, y, new_width, new_height)
```

#### `PixelFont` - Font Loading and Text
Load pixel fonts for text rendering.

```python
# Load font from system or app assets
font = PixelFont.load("/system/assets/fonts/nope.ppf")
screen.font = font

# Properties
height = font.height
name = font.name

# Measure text
width = screen.measure_text("Hello Badge!")

# Draw text
screen.brush = brushes.color(255, 255, 255)
screen.text("Hello Badge!", x, y)
```

**Available System Fonts** (in `/system/assets/fonts/`):
- `nope.ppf` - Clean, readable default
- `ark.ppf` - Pixel art style
- `compass.ppf` - Bold and chunky
- `kobold.ppf` - Fantasy themed
- `troll.ppf` - Large and bold
- Plus 30+ more - see PixelFont.md for full list

#### `SpriteSheet` - Sprite Animation
Load and animate sprite sheets.

```python
# Load sprite sheet (image_path, columns, rows)
sprite_sheet = SpriteSheet("/system/assets/mona-sprites/mona-default.png", 7, 1)

# Get single sprite
sprite = sprite_sheet.sprite(column, row)
screen.blit(sprite, x, y)

# Create animation
animation = sprite_sheet.animation()

# Get frame based on time (auto-loops)
frame = animation.frame(io.ticks / 100)  # Adjust divisor for speed
screen.blit(frame, x, y)

# Scale blit (can flip with negative dims)
screen.scale_blit(frame, x, y, 32, 32)
```

#### `run()` - Main Loop
Starts the main loop that calls your update function every frame.

```python
# At end of __init__.py
run(update)
```

### Built-in Modules ###
The following built in modules are available to the MicroPython code running on the device:

array, binascii, builtins, cmath, collections, errno, gc, hashlib, heapq, io, json, machine, math, micropython, network, os, platform, random, re,select, socket, ssl, struct, sys,time, uctypes, rp2, bluetooth, cryptolib, deflate, framebuf, vfs, lwip, ntptime, mip, badgeware,picovector, pimoroni, pimoroni_i2c, qrcode, st7789, powman, board, boot, datetime, ezwifi, pcf85063a, qwstpad, cppmem, adcfft, aioble, asyncio, uasyncio, requests, urequests, urllib, webrepl, websocket, umqtt, ulab, aye_arr, breakout_as7262, breakout_as7343, breakout_bh1745, breakout_bme280, breakout_bme68x, breakout_bme69x, breakout_bmp280, breakout_dotmatrix, breakout_encoder, breakout_encoder_wheel, breakout_icp10125, breakout_ioexpander, breakout_ltr559, breakout_matrix11x7, breakout_mics6814, breakout_msa301, breakout_paa5100, breakout_pmw3901, breakout_potentiometer, breakout_rgbmatrix5x5, breakout_rtc, breakout_scd41, breakout_sgp30, breakout_trackball, breakout_vl53l5cx

### File System Helpers

```python
from badgeware import file_exists, is_dir

# Check if file exists
if file_exists("/myapp_save.json"):
    # Load save file

# Check if directory
if is_dir("/system/apps/myapp/assets"):
    # List assets
```

### Battery Status

```python
from badgeware import get_battery_level, is_charging

# Get battery percentage (0-100)
level = get_battery_level()

# Check if charging
charging = is_charging()
```

## Common Patterns and Examples

### Basic App Template
```python
from badgeware import screen, io, brushes, shapes, run, PixelFont

# Global state
game_state = {"score": 0}

def init():
    global game_state
    screen.font = PixelFont.load("/system/assets/fonts/nope.ppf")
    screen.antialias = Image.X2
    game_state = {"score": 0}

def update():
    # Input
    if io.BUTTON_A in io.pressed:
        game_state["score"] += 1
    
    # Clear
    screen.brush = brushes.color(0, 0, 0)
    screen.clear()
    
    # Draw
    screen.brush = brushes.color(255, 255, 255)
    screen.text(f"Score: {game_state['score']}", 10, 10)

def on_exit():
    # Save state if needed
    pass

run(update)
```

### Button Navigation
```python
menu_items = ["Play", "Settings", "Quit"]
selected = 0

def update():
    global selected
    
    # Navigation with wrapping
    if io.BUTTON_UP in io.pressed:
        selected = (selected - 1) % len(menu_items)
    if io.BUTTON_DOWN in io.pressed:
        selected = (selected + 1) % len(menu_items)
    
    # Selection
    if io.BUTTON_A in io.pressed:
        handle_selection(menu_items[selected])
    
    # Draw menu
    for i, item in enumerate(menu_items):
        color = (255, 255, 0) if i == selected else (255, 255, 255)
        screen.brush = brushes.color(*color)
        screen.text(item, 10, 10 + i * 15)
```

### Sprite Animation
```python
from badgeware import SpriteSheet

sprite_sheet = None
animation = None

def init():
    global sprite_sheet, animation
    sprite_sheet = SpriteSheet("/system/assets/mona-sprites/mona-default.png", 7, 1)
    animation = sprite_sheet.animation()

def update():
    # Get frame based on time (100ms per frame)
    frame = animation.frame(io.ticks / 100)
    
    # Draw at position
    screen.blit(frame, 64, 44)
```

### Collision Detection
```python
def rect_collision(x1, y1, w1, h1, x2, y2, w2, h2):
    return (x1 < x2 + w2 and
            x1 + w1 > x2 and
            y1 < y2 + h2 and
            y1 + h1 > y2)

def circle_collision(x1, y1, r1, x2, y2, r2):
    dx = x2 - x1
    dy = y2 - y1
    distance = (dx * dx + dy * dy) ** 0.5
    return distance < (r1 + r2)
```

### Persistent State
```python
import json
from badgeware import file_exists

save_file = "/myapp_save.json"

def init():
    global game_state
    if file_exists(save_file):
        try:
            with open(save_file, "r") as f:
                game_state = json.load(f)
        except:
            game_state = {"high_score": 0}
    else:
        game_state = {"high_score": 0}

def on_exit():
    try:
        with open(save_file, "w") as f:
            json.dump(game_state, f)
    except:
        pass  # Fail gracefully
```

### Smooth Movement
```python
# Frame-rate independent movement
player_x = 80
player_y = 60
speed = 50  # pixels per second

def update():
    global player_x, player_y
    
    # Movement based on frame delta
    if io.BUTTON_UP in io.held:
        player_y -= speed * (io.ticks_delta / 1000)
    if io.BUTTON_DOWN in io.held:
        player_y += speed * (io.ticks_delta / 1000)
    
    # Clamp to screen bounds
    player_y = max(0, min(player_y, 120))
```

### Rotating Shape
```python
def update():
    # Clear
    screen.brush = brushes.color(0, 0, 0)
    screen.clear()
    
    # Create shape centered at origin
    rect = shapes.rectangle(-20, -10, 40, 20)
    
    # Transform: move to screen center, rotate based on time
    rect.transform = Matrix().translate(80, 60).rotate(io.ticks / 10)
    
    # Draw
    screen.brush = brushes.color(255, 0, 0)
    screen.draw(rect)
```

## Performance Best Practices

1. **Pre-create Objects** - Create brushes, shapes, fonts in `init()`, not in `update()`
2. **Minimize Allocations** - Avoid creating new objects every frame
3. **Use Paletted Images** - Smaller file size and memory usage
4. **Call gc.collect()** - Before loading large resources or major state changes
5. **Profile Critical Paths** - Use `io.ticks_delta` to measure frame time
6. **Batch Drawing** - Group similar drawing operations together
7. **Optimize Loops** - Unroll small loops, use list comprehensions wisely
8. **Cache Calculations** - Don't recalculate static values every frame

## Common Pitfalls

1. **Not Setting screen.font** - Always set font before calling `screen.text()`
2. **Not Setting screen.brush** - Always set brush before drawing shapes/clearing
3. **Forgetting to Clear** - Call `screen.clear()` every frame or redraw everything
4. **Using Desktop Python Features** - MicroPython subset (no `random.choices()`, limited stdlib)
5. **Absolute Paths** - Use `/system/` prefix or relative paths from app directory
6. **Not Handling Errors** - Wrap file operations in try/except
7. **Memory Leaks** - Don't create new objects in tight loops
8. **Coordinate System** - Remember screen is 160x120 logical pixels, not 320x240

## Reference Apps in This Project

Study these apps for working examples:

- **`/badge/apps/snake/`** - Classic Snake game with score tracking
- **`/badge/apps/life/`** - Conway's Game of Life with pattern injection
- **`/badge/apps/flappy/`** - Flappy Bird clone with sprite animation
- **`/badge/apps/monapet/`** - Virtual pet with state management
- **`/badge/apps/sketch/`** - Drawing app with button controls
- **`/badge/apps/quest/`** - IR beacon hunting game
- **`/badge/apps/menu/`** - Launcher menu with icon grid

## Additional Resources

- **README.md** - Comprehensive badge documentation and examples
- **badgeware/*.md** - Detailed API documentation for each module

## Development Workflow

1. **Create App Directory** - `./apps/<name>/`
2. **Create icon.png** - 24x24 PNG icon
3. **Create __init__.py** - With `init()`, `update()`, `on_exit()`, `run(update)`
4. **Add Assets** - Images, fonts, data in `assets/` subdirectory
5. **Test on Hardware** - MicroPython differs from desktop Python
6. **Handle Errors** - Wrap I/O operations, handle missing files gracefully
7. **Optimize** - Profile with `io.ticks_delta`, reduce allocations
8. **Document** - Add comments for complex logic

---

This document should provide you with everything needed to create badge apps. When in doubt, check the badgeware documentation in this repository or examine existing apps for patterns.
