# Badger 2040: Reference

The Badger 2040 is a Raspberry Pi Pico powered E Ink badge.

This function reference should give you a basic understanding of how to programming for them in MicroPython. It is derived from the official [Badger 2040 & Badger 2040 W Reference](https://github.com/pimoroni/badger2040/blob/main/docs/reference.md)

- [Summary](#summary)
  - [Getting Started](#getting-started)
  - [Constants](#constants)
    - [Screen Size](#screen-size)
    - [E Ink Pins](#e-ink-pins)
    - [Power Pins](#power-pins)
    - [Activity LED Pin](#activity-led-pin)
- [Function Reference](#function-reference)
  - [Basic Drawing Settings](#basic-drawing-settings)
    - [Pen Colour](#pen-colour)
    - [Pen Thickness](#pen-thickness)
  - [Displaying Images](#displaying-images)
  - [Updating The Display](#updating-the-display)
    - [Update](#update)
    - [Clear](#clear)
    - [Partial Update](#partial-update)
    - [Update Speed](#update-speed)
  - [LED](#led)
  - [Buttons](#buttons)
  - [Waking From Sleep](#waking-from-sleep)
    - [Button Presses](#button-presses)
  - [Update Speed](#update-speed-1)
  - [System speed](#system-speed)

# Summary

## Getting Started

To start coding your Badger 2040, you will need to add the following lines of code to the start of your code file.

```python
import badger2040
badger = badger2040.Badger2040()
```

This will create a `Badger2040` class instance called `badger` that will be used in the rest of the examples going forward.

## Constants

Below is a list of other constants that have been made available, to help with the creation of more advanced programs.

### Screen Size

* `WIDTH` = `296`
* `HEIGHT` = `128`

### E Ink Pins

* `BUSY` = `26`

### Power Pins

* `ENABLE_3V3` = `10`

### Activity LED Pin

Badger 2040:
* `LED` = `25`

Badger 2040 W:
* `LED` = `22`

# Function Reference

## Basic Drawing Settings

Since Badger 2040 is based upon PicoGraphics you should read the [PicoGraphics function reference](https://github.com/pimoroni/pimoroni-pico/blob/main/micropython/modules/picographics/README.md) for more information about how to draw to the display.

### Pen Colour

There are 16 pen colours - or "shades of grey" - to choose, from 0 (black) to 15 (white).

Since Badger 2040 cannot display colours other than black and white, any value from 1 to 14 will apply dithering when drawn, to simulate a shade of grey.

```python
set_pen(
    colour  # int: colour from 0 to 15
)
```

### Pen Thickness

:warning: Applies to Hershey fonts only.

Thickness affects Hershey text and governs how thick the component lines should be, making it appear bolder:

```python
set_thickness(
    value  # int: thickness in pixels
)
```

## Displaying Images

Badger 2040 can display basic JPEG images. They must not be progressive. It will attempt to dither them to the black/white display.

To display a JPEG, import and set up the `jpegdec` module like so:

```python
import badger2040
import jpegdec

badger = badger2040.Badger2040()
jpeg = jpegdec.JPEG(badger.display)
```

`badger.display` points to the PicoGraphics instance that the Badger2040 class manages for you.

You can open and display a JPEG file like so:

```python
jpeg.open_file("/image.jpg")
jpeg.decode(x, y)
```

Where `x, y` is the position at which you want to display the JPEG.

## Updating The Display

### Update

Starts a full update of the screen. Will block until the update has finished.

Update takes no parameters, but the update time will vary depending on which update speed you've selected.

```python
badger.update()
```

### Clear

Before drawing again it can be useful to `clear` your display.

`clear` fills the drawing buffer with the pen colour, giving you a clean slate:

```python
badger.clear()
```

### Partial Update

Starts a partial update of the screen. Will block until the update has finished.

A partial update allows you to update a portion of the screen rather than the whole thing.

That portion *must* be a multiple of 8 pixels tall, but can be any number of pixels wide.

```python
partial_update(
    x,  # int: x coordinate of the update region
    y,  # int: y coordinate of the update region (must be a multiple of 8)
    w,  # int: width of the update region
    h   # int: height of the update region (must be a multiple of 8)
)
```

### Update Speed

Badger 2040 is capable of updating the display at multiple different speeds.

These offer a tradeoff between the quality of the final image and the speed of the update.

There are currently four constants naming the different update speeds from 0 to 3:

* `UPDATE_NORMAL` - a normal update, great for display the first screen of your application and ensuring good contrast and no ghosting
* `UPDATE_MEDIUM` - a good balance of speed and clarity, you probably want this most of the time
* `UPDATE_FAST` - a fast update, good for stepping through screens such as the pages of a book or the launcher
* `UPDATE_TURBO` - a super fast update, prone to ghosting, great for making minor changes such as moving a cursor through a menu

```python
set_update_speed(
    speed  # int: one of the update constants
)
```

## LED

The white indicator LED can be controlled, with brightness ranging from 0 (off) to 255:

```python
led(
    brightness  # int: 0 (off) to 255 (full)
)
```

## Buttons

The Badger 2040 features five buttons on its front, labelled A, B, C, ↑ (up) and ↓ (down). These can be read using the `pressed(button)` method, which accepts the button's pin number. For convenience, each button can be referred to using these constants:

* `BUTTON_A` = `12`
* `BUTTON_B` = `13`
* `BUTTON_C` = `14`
* `BUTTON_UP` = `15`
* `BUTTON_DOWN` = `11`

Additionally you can use `pressed_any()` to see if _any_ button has been pressed.

Badger 2040 has an additional "user" button (which doubles as boot select), availble as:

* `BUTTON_USER` = `23`

## Waking From Sleep

Turning off the Badger 2040 will put it into a low-power mode.

* `turn_off()` - cut system power, on USB this will block until a button or alarm state is raised

There are several ways to wake your Badger back up:

### Button Presses

When running on battery, pressing a button on Badger 2040 will power the unit on. It will automatically be latched on and `main.py` will be executed.

There are some useful functions to determine if Badger 2040 has been woken by a button, and figure out which one:

* `badger2040.woken_by_button()` - determine if any button was pressed during power-on.
* `badger2040.pressed_to_wake(button)` - determine if the given button was pressed during power-on.
* `badger2040.reset_pressed_to_wake()` - clear the wakeup GPIO state.
* `badger2040.pressed_to_wake_get_once(button)` - returns `True` if the given button was pressed to wake Badger, and then clears the state of that pin.

## Update Speed

The E Ink display on Badger 2040 supports several update speeds. These can be set using `set_update_speed(speed)` where `speed` is a value from `0` to `3`. For convenience these speeds have been given the following constants:

* `UPDATE_NORMAL` = `0`
* `UPDATE_MEDIUM` = `1`
* `UPDATE_FAST` = `2`
* `UPDATE_TURBO` = `3`

## System speed

The system clock speed of the RP2040 can be controlled, allowing power to be saved if on battery, or faster computations to be performed.  Use `badger2040.system_speed(speed)` where `speed` is one of the following constants:

* `SYSTEM_VERY_SLOW` = `0`  _4 MHz if on battery, 48 MHz if connected to USB_
* `SYSTEM_SLOW` = `1`  _12 MHz if on battery, 48 MHz if connected to USB_
* `SYSTEM_NORMAL` = `2`  _48 MHz_
* `SYSTEM_FAST` = `3`  _133 MHz_
* `SYSTEM_TURBO` = `4`  _250 MHz_

On USB, the system will not run slower than 48MHz, as that is the minimum clock speed required to keep the USB connection stable.

It is best to set the clock speed as the first thing in your program, and you must not change it after initializing any drivers for any I2C hardware connected to the Qwiic port.  To allow you to set the speed at the top of your program, this method is on the `badger2040` module, rather than the `badger` instance, although we have made sure that it is safe to call it after creating a `badger` instance.

:information_source: Note that `SYSTEM_TURBO` overclocks the RP2040 to 250MHz, and applies a small over voltage to ensure this is stable. We've found that every RP2040 we've tested is happy to run at this speed without any issues.
