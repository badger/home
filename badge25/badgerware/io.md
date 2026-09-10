# `io` - access to hardware features

This module exposes helpful information about the state of the badge hardware including the buttons and clock.

## Timing

`io.ticks`\
The number of ticks (milliseconds) since the badge was powered on when `update()` was called.

`io.ticks_delta`\
The number of ticks (milliseconds) since the previous time `update()` was called. Useful for timing animations where the framerate isn't completely stable.

## Reading button state

There are two main ways to handle button input.
- For things like menu navigation, you usually want to respond only when a button is first pressed.
- For games or continuous actions, you often want something to happen as long as the button is held down.

The API lets you check the state of each button — whether it has been `pressed`, `released`, `held`, or `changed` during the current frame.

```python
from badgeware import io

def update():
  # true only when button A is newly pressed this frame
  if io.BUTTON_A in io.pressed:
    ...

  # true continuously while button B is being held
  if io.BUTTON_B in io.held:
    ...

  # true only if button C has been released this frame
  if io.BUTTON_C in io.released:
    ...

  # true only if button UP has changed state this frame
  if io.BUTTON_UP in io.changed:
    ...
```

`io.pressed`\
A list of buttons that were just pressed during the current frame — that is, buttons that were not pressed in the previous frame.

To check which buttons are currently being held down, use `io.held` instead.

`io.released`\
A list of buttons that were just released during the current frame — that is, buttons that were pressed in the previous frame.

To check which buttons are currently being held down, use `io.held` instead.

`io.held`\
A list of all buttons that are currently held down.

`io.changed`\
A list of all buttons whose state changed during the previous frame.

## Backlight LEDs

> TODO

## Battery status

> TODO

## Constants

`io.BUTTON_HOME`\
`io.BUTTON_A`\
`io.BUTTON_B`\
`io.BUTTON_C`\
`io.BUTTON_UP`\
`io.BUTTON_DOWN`

Identifiers for each of the software useable buttons.

`io.LED_TOP_LEFT`\
`io.LED_TOP_RIGHT`\
`io.LED_BOTTOM_RIGHT`\
`io.LED_BOTTOM_LEFT`

Identifiers for each of backlight LEDs.