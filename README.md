# Universe 2025 (Tufty) Badge

For GitHub Universe 2025 we have partnered with our friends at Pimoroni to create the Tufty Edition of our hackable conference badge.  This is a custom version of the 
[Pimoroni Tufty 2350](https://shop.pimoroni.com/) badge, with a custom PCB, added IR
sensors and pre-loaded with some fun apps.  The source code for the custom apps is 
available [here](./badgerware/).

These apps are designed to be run on the base MonaOS MicroPython firmware pre-installed on your badge.

## Table of Contents
- [Universe 2025 (Tufty) Badge](#universe-2025-tufty-badge)
  - [Table of Contents](#table-of-contents)
  - [Introduction](#introduction)
  - [Getting started](#getting-started)
    - [Creating your own apps](#creating-your-own-apps)
    - [Testing apps with the simulator](#testing-apps-with-the-simulator)
    - [Editing code on the badge](#editing-code-on-the-badge)
    - [Flashing your Badge](#flashing-your-badge)
    - [Writing to files from application code](#writing-to-files-from-application-code)
  - [Reading button state](#reading-button-state)
  - [Working with the screen](#working-with-the-screen)
    - [Drawing shapes](#drawing-shapes)
    - [Blitting images and sprites](#blitting-images-and-sprites)
    - [Drawing text](#drawing-text)
  - [Wireless networking and Bluetooth](#wireless-networking-and-bluetooth)
  - [Built-in Modules](#built-in-modules)
  - [Contributing](#contributing)

## Introduction

Your badge this year is based on Pimoroni's upcoming "Tufty" Badgeware product. It's the fourth, most ambitious, and best, digital badge that we've developed for GitHub Universe so far!

On the board we've packed in a bunch of great features:

- RP2350 Dual-core ARM Cortex-M33 @ 200MHz
- 512kB SRAM
- 16MB QSPI XiP flash
- 320x240 full colour IPS display (currently pixel doubled to 160x120)
- 2.4GHz WiFi and Bluetooth 5
- 1000mAh chargeable battery (up to 8 hours runtime)
- Qw/ST and SWD ports for accessories and debugging
- 4 GPIO pins + power through-hole solder pads for additional hardware hacking
- IR receiver and transmitter for beacon hunting and remote control
- Five front facing buttons
- Battery voltage monitoring and charge status
- USB-C port for charging and programming
- RESET / BOOTSEL buttons
- 4-zone LED backlight
- Durable polycarbonate case with lanyard fixings

We hope you really love tinkering with it during, and after, the event. Tag the Pimoroni team on [BlueSky](https://bsky.app/profile/pimoroni.com) and show them what you're up to!

> This documentation is an early draft and both it and the API are subject to change! We're putting together a new build with more features and some performance enhancements which we'll share soon!

## Getting started

The board is pre-loaded with a special build of MicroPython that includes drivers for all of the built-in hardware.

We've also included a small suite of example applications to demonstrate how different features of the badge work. Feel free to poke around in the code and experiment!

For an overview of how to put the badge into different modes checkout https://badger.github.io/get-started/.

### Creating your own apps
The structure for apps is as follows. They live in the `/system/apps` directory.

```
/system
  /apps
    /my_application
      icon.png
      __init__.py
      /assets
        ...
```

Each application has a minimal structure:

- `icon.png` contains the icon for your app, it should be a 24x24 PNG image.
- `__init__.py` the entry point for your application, this is where `update()` will be implemented.
- `assets/` a directory to contain any assets your app uses, this is automatically added to the system path when your app launches.

Your app should implement an `update()` function within `__init__.py` which will automatically be called every frame to give it a chance to update its state and render new output to the screen.

You'll have to [update the menu app](https://badger.github.io/hack/menu-pagination/) on your device to see your app, the version of the pre-flashed firmware only supports six icons - have fun expanding it!

An app is launched by `main.py`, which handles the intro cinematic, menu and launching your app. It'll call your `init()` and `update()` methods, and call `on_exit()` when you press the `HOME` button to leave your app.

### Testing apps with the simulator

The badge simulator lets you test your apps on your computer before deploying them to the hardware. This is much faster for development and debugging.

**Prerequisites:**
- Python 3.10 or newer (3.13 recommended)
- Pygame (`pip install pygame`)

**Basic usage:**
```bash
python simulator/badge_simulator.py -C badge badge/apps/your_app/__init__.py
```

**Controls:**
- `A` / `Z` → Button A
- `B` / `X` → Button B  
- `C` / `Space` → Button C
- Arrow keys → D-pad
- `H` / `Esc` → Home / exit
- `F12` → Take screenshot (when --screenshots is configured)

**Taking screenshots:**
```bash
python simulator/badge_simulator.py -C badge --screenshots ./screenshots badge/apps/your_app/__init__.py
```

Screenshots are saved at native badge resolution (160×120) in PNG format, perfect for documentation and pull requests.

For more details and advanced options, see the [simulator documentation](./simulator/README.md).

```python
# example __init__.py for an application

# select a font to use
screen.font = PixelFont.load("nope.ppf")

# called once when your app launches
def init():
  pass

# called every frame, do all your stuff here!
def update():
  # clear the framebuffer
  screen.brush = brushes.color(20, 40, 60)
  screen.clear()

  # calculate and draw an animated sine wave
  y = (math.sin(io.ticks / 100) * 20) + 80
  screen.brush = brushes.color(0, 255, 0)
  for x in range(160):
    screen.draw(shapes.rectangle(x, y, 1, 1))

  # write a message
  screen.brush = brushes.color(255, 255, 255)
  screen.text("hello badge!", 10, 10)

# called before returning to the menu to allow you to save state
def on_exit():
  pass
```

### Editing code on the badge

The easiest way to edit the code on the device is to put it into mass storage mode:

- Connect your badge up to your computer via a USB-C cable
- Press the RESET button twice
- The USB Disk Mode screen will appear
- The badge should appear as a disk named "BADGER" on your computer

In this mode you can see the contents of the FAT32 `/system/` mount. This is where all application code should live.

### Flashing your Badge
When your badge arrives, it will be pre-loaded with a factory default Micropython image that will have a custom image of Micropython with our apps pre-installed and a 'MonaOS' app launcher.

If you want to reset your badge back to factory conditions, you will need to flash the latest Micropython
firmware that we have. You can find the latest firmware image in the
[Releases](https://github.com/badger/home/releases)

1. Download the latest `.uf2` firmware file from the [releases page](https://github.com/badger/home/releases).
2. Connect your badge to your computer via USB.
3. On the back of the badge, press and hold the `Home` button. While holding down `Home`, press and release the `Reset` button. Then release the `Home` button.
4. Your badge should then appear as a USB drive named `RP2350`.
5. Drag and drop the `.uf2` file onto the `RP2350` drive.
6. The badge will automatically reboot and run the new firmware.

### Writing to files from application code

The badge has a writeable LittleFS partition located at `/` which is intended for applications to store state information and cache any data they may need to hold on to across resets.

You can use normal Python style file access from your code:

```python
with open("/storage/myfile.txt", "w") as out:
  out.write("this is some text i want to keep\n")
```

## Reading button state

The `io` module also exposes helpful information about the state of the buttons on your badge. [Click here for full documentation of the `io` module](./badgerware/io.md).

Each button is represented by a constant (for example, `io.BUTTON_A`). The API lets you check whether a button has been pressed, released, held, or if its state has changed during the current frame.

The following example draws a small white circle in the centre of the screen and allows the user to move it using the buttons:

```python
import math
from badgeware import screen, shapes, brushes, io

# start the cursor in the middle of the screen
x, y = 80, 60

# clamp a value to within an upper and lower bound
def clamp(value, lower, upper):
  return math.max(lower, math.min(upper, value))

# called automatically every frame
def update():
  global x, y

  # clear the screen
  screen.brush = brushes.color(20, 40, 60)
  screen.draw(shapes.rectangle(0, 0, 160, 120))

  # move cursor based on button states
  if io.BUTTON_A    in io.held: x -= 1  # left
  if io.BUTTON_C    in io.held: x += 1  # right
  if io.BUTTON_UP   in io.held: y -= 1  # up
  if io.BUTTON_DOWN in io.held: y += 1  # down

  # clamp position to screen bounds
  x = clamp(x, 0, 160)
  y = clamp(y, 0, 120)

  # draw the cursor
  screen.brush = brushes.color(255, 255, 255)
  screen.draw(shapes.circle(x, y, 5))
```

## Working with the screen

The framebuffer is a 160 × 120 true colour `Image` named `screen`. [Click here for full documentation of the `Image` class](./badgerware/Image.md).

Your application can draw to the screen during the update() function.
After your code finishes executing, the badge automatically pixel-doubles the framebuffer to fit the display.

The screen supports drawing vector shapes, blitting other images, and rendering text using pixel fonts.

### Drawing shapes

The `shapes` module provides ways to create primitive shapes which can then be drawn onto images. [Click here for full documentation of the `shapes` module](./badgerware/shapes.md).

Currently supported shapes are rectangles, circles, arcs, pies, lines, rounded rectangles, regular polygons, and squircles.

Shapes are drawn using the currently assigned brush. [Click here for full documentation of the `brushes` module](./badgerware/brushes.md).

```python
# example of drawing a circle in the center of the screen

from badgeware import screen, brushes, shapes

# enable antialiasing for lush smooth edges
screen.antialias = Image.X4

def update():
  # clear the background
  screen.brush = brushes.color(20, 40, 60)
  screen.clear()

  # draw the circle
  screen.brush = brushes.color(0, 255, 0)
  screen.draw(shapes.circle(80, 60, 20))
```

Shapes can also be given a transformation matrix to adjust their scale, rotation, and skew - this is very useful for creating smooth animations. [Click here for full documentation of the `Matrix` class](Matrix.md).

```python
# example of animating a rotating rectangle

from badgeware import screen, brushes, shapes

# enable antialiasing for lush smooth edges
screen.antialias = Image.X4

def update():
  # clear the background
  screen.brush = brushes.color(20, 40, 60)
  screen.clear()

  # transform and draw the rectangle
  screen.brush = brushes.color(0, 255, 0)
  rectangle = shapes.rectangle(-1, -1, 2, 2)
  rectangle.transform = Matrix().translate(80, 60).scale(20, 20).rotate(io.ticks / 100)
  screen.draw(rectangle)
```

### Blitting images and sprites

The `Image` class can load images from files on the filesystem which can then be blitted onto the screen. [Click here for full documentation of the `Image` class](./badgerware/Image.md).

```python
# example of loading a sprite and blitting it to the screen
from badgeware import screen, brushes, Image
from lib import SpriteSheet

# load an image as a sprite sheet specifying the number of rows and columns
mona = SpriteSheet(f"assets/mona-sprites/mona-default.png", 7, 1)

def update():
  # clear the background
  screen.brush = brushes.color(20, 40, 60)
  screen.clear()

  # blit the sprite at 0, 0 in the spritesheet to the screen
  screen.blit(mona.sprite(0, 0), 10, 10)

  # scale blit the sprite at 3, 0 in the spritesheet to the screen
  screen.scale_blit(mona.sprite(0, 0), 50, 50, 30, 30)
```

### Drawing text

The `PixelFont` class provides functions for loading pixel fonts, which can then be used to render text onto images. [Click here for full documentation of the `PixelFont` class](./badgerware/PixelFont.md).

There are thirty licensed pixel fonts included.

```python
# example of drawing text to the screen

from badgeware import screen, PixelFont

screen.font = PixelFont.load("nope.ppf")

def update():
  screen.brush = brushes.color(20, 40, 60)
  screen.clear()

  message = "this font rocks"
  screen.brush(255, 255, 255)
  screen.text(message, 10, 10)
```

## Wireless networking and Bluetooth

You can use the existing MicroPython functionality for wireless networking and bluetooth functionality.

- Wireless networking: https://docs.micropython.org/en/latest/rp2/quickref.html#wlan
- Bluetooth: https://docs.micropython.org/en/latest/library/bluetooth.html#module-bluetooth

## Built-in Modules ##
The following built in modules are available to the MicroPython code running on the device:

array, binascii, builtins, cmath, collections, errno, gc, hashlib, heapq, io, json, machine, math, micropython, network, os, platform, random, re,select, socket, ssl, struct, sys,time, uctypes, rp2, bluetooth, cryptolib, deflate, framebuf, vfs, lwip, ntptime, mip, badgeware,picovector, pimoroni, pimoroni_i2c, qrcode, st7789, powman, board, boot, datetime, ezwifi, pcf85063a, qwstpad, cppmem, adcfft, aioble, asyncio, uasyncio, requests, urequests, urllib, webrepl, websocket, umqtt, ulab, aye_arr, breakout_as7262, breakout_as7343, breakout_bh1745, breakout_bme280, breakout_bme68x, breakout_bme69x, breakout_bmp280, breakout_dotmatrix, breakout_encoder, breakout_encoder_wheel, breakout_icp10125, breakout_ioexpander, breakout_ltr559, breakout_matrix11x7, breakout_mics6814, breakout_msa301, breakout_paa5100, breakout_pmw3901, breakout_potentiometer, breakout_rgbmatrix5x5, breakout_rtc, breakout_scd41, breakout_sgp30, breakout_trackball, breakout_vl53l5cx

## Contributing

We welcome contributions! If you've created a new app or improved an existing one, please consider submitting a pull request.

See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines on how to contribute to this project.


