# Example Apps

This directory contains example apps that demonstrate how to interact with the `badger2040` library & picographics API.

Note that while each example app is in its own directory, all of the files for each app will need to be copied directly into the `/examples/` directory to correctly show up as an app in the launcher menu.

## Badge++
Just like the badge app that came with your Badger 2350, but with a few extra features to make sure your badge is truly one of a kind.

Installation instructions:
1. Run the accompanying `profile_pic_download.py` script to generate a few images to try out on your badge.
2. Copy the resulting images to the `/badges/` directory on your badge.
3. Copy the `badge++.py` and `icon-badge++.jpg` files to the `/example/` directory on your badge just like any other app.

How to customize your badge:
- A/B: Cycle back and forth through the font options.
- UP/DOWN: Cycle back and forth through the images in the `/badges/` directory.

Find the combination that looks best to you!

_Note:_ To run this app on the Universe 2023 badge, the `BACK_COMPAT_MODE` constant must be set to `True`. Any PNG images in the `/badges/` directory will be ignored.

## Copilot
Have some time before your next session? Read this guide to help you get the most out of GitHub Copilot.

How to use:
- A: Change font size
- B: Change font
- UP/DOWN: Scroll text

## Dino
Forked from [niutech/dino-badger2040](https://github.com/niutech/dino-badger2040). This is the Dino Game from Google Chrome coded in MicroPython and ported to [Pimoroni Badger 2040](https://shop.pimoroni.com/products/badger-2040) e-ink device based on [RP2040](https://www.raspberrypi.com/products/rp2040/) MCU. It is based on [dino-game-micropython](https://github.com/danielkurek/dino-game-micropython) by Daniel Kurek. [Demo video](https://twitter.com/niu_tech/status/1598804559270486033).

## Hello
There's nothing like a classic. This app will display "Hello Universe!" on the screen.

## Life
The Game of Life by @link- forked from [glich-stream/gol-badger-2350](https://github.com/glich-stream/gol-badger-2350)

How to play:
- A: Reset the grid (press and HOLD for 2s)
- B: Pause/Resume the simulation (press and HOLD for 2s)
- UP: Increase the refresh rate (press and HOLD for 2s)
- DOWN: Decrease the refresh rate (press and HOLD for 2s)

## Wordle
Forked from [makew0rld/wordle-badger2040](https://github.com/makew0rld/wordle-badger2040) and lightly updated to run on the latest version of the picographics library.

How to play:
1. Use the *B* and *C* buttons to cycle through the alphabet.
2. Use the arrow buttons to move between squares.
3. Press the *A* button to submit a word.

# Other Credits
- @martinwoodward & @ashleymcnamara - inception, hardware, inspiration
- @peckjon & @tbries - tutorials, integration
- @alliekpeck - testing