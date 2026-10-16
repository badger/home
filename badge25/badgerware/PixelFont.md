# `PixelFont` - load

This class provides functions for loading pixel fonts, which can then be used to render text onto images.

Text is drawn using the currently selected brush, allowing for alpha blending and other visual effects.

PicoGraphics includes thirty high-quality, licensed pixel fonts created by [somepx](https://somepx.itch.io), giving you plenty of options to add style and character to your applications.

```python
# example of how to draw text onto the screen

import math
from badgeware import screen, PixelFont

screen.font = PixelFont.load("nope.ppf")

def update():
  screen.brush = brushes.color(20, 40, 60)
  screen.clear()

  # draw the message at random locations with alpha blending
  screen.brush(0, 255, 0, 100)
  for i in range(10):
    x = math.randint(0, 160)
    y = math.randint(0, 120)

    screen.text("badgeware!", x, y)
```

## Measuring text

When outputting text you often want to align it or word wrap it. This requires the ability to measure a piece of text so that you can adjust its position before drawing it to the screen.

```python
# example of centering text using the measure_text method

from badgeware import screen, PixelFont

screen.font = PixelFont.load("nope.ppf")

def update():
  screen.brush = brushes.color(20, 40, 60)
  screen.clear()

  # center the text on screen
  message = "this is my message"
  w, h = screen.measure_text(message)
  screen.brush(0, 255, 0)
  screen.text(message, 80 - (w / 2), 60 - (h / 2))
```

## Static methods

`PixelFont.load(path)`\
Creates and returns a new `PixelFont` object representing the specified font.

## Properties

`height`\
The height, in pixels, of the fonts glyph bounding box.

`name`\
The name of the pixel font.

## Included fonts

**absolute**: bold, boxy, 10px tall\
![absolute](fonts/absolute.png)

**ark**: tiny, smallcaps, 6px tall\
![ark](fonts/ark.png)

**awesome**: cheerful, wholesome, monospace, 9px tall\
![awesome](fonts/awesome.png)

**bacteria**: rational, wide, monospace, 12px tall\
![bacteria](fonts/bacteria.png)

**compass**: classic, fantasy, 9px tall\
![compass](fonts/compass.png)

**corset**: elegant, cozy, 8px tall\
![corset](fonts/corset.png)

**curse**: comic, horror, smallcaps, 12px tall\
![curse](fonts/curse.png)

**desert**: tiny, drowsy, sunny, 6px tall\
![desert](fonts/desert.png)

**fear**: smallcaps, horror, 11px tall\
![fear](fonts/fear.png)

**futile**: big, bold, unique, 14px tall\
![futile](fonts/futile.png)

**holotype**: distinctive, premium, 9px tall\
![holotype](fonts/holotype.png)

**hungry**: playful, unique, monospace, 7px tall\
![hungry](fonts/hungry.png)

**ignore**: colossal, super-readable, intrepid, 17px tall\
![ignore](fonts/ignore.png)

**kobold**: classic, tiny, fantasy, 7px tall\
![kobold](fonts/kobold.png)

**lookout**: adventurous, piratesque, fantasy, 7px tall\
![lookout](fonts/lookout.png)

**loser**: slanted, smallcaps, monospace, 7px tall\
![loser](fonts/loser.png)

**manticore**: strong, metal, horror, 14px tall\
![manticore](fonts/manticore.png)

**match**: classic, joyful, 7px tall\
![match](fonts/match.png)

**memo**: wacky, distinctive, 9px tall\
![memo](fonts/memo.png)

**more**: chunky, huge, comic, 15px tall\
![more](fonts/more.png)

**nope**: clear, readable, 8px tall\
![nope](fonts/nope.png)

**outflank**: fantasy, arcane, 9px tall\
![outflank](fonts/outflank.png)

**saga**: medieval, fantasy, legendary, 8px tall\
![saga](fonts/saga.png)

**salty**: thick, all-purpose, 9px tall\
![salty](fonts/salty.png)

**sins**: tiny, classic, stylish, 7px tall\
![sins](fonts/sins.png)

**smart**: classic, chunky, smallcaps, 9px tall\
![smart](fonts/smart.png)

**teatime**: classic, readable, monospace, 7px tall\
![teatime](fonts/teatime.png)

**torch**: fiery, pocket-sized, fantasy, 6px tall\
![torch](fonts/torch.png)

**troll**: fantasy, ornate, 12px tall\
![troll](fonts/troll.png)

**unfair**: wide, retro, eccentric, 8px tall\
![unfair](fonts/unfair.png)

**vest**: elegant, classic, serif, 9px tall\
![vest](fonts/vest.png)

**winds**: tiny, extra-spaced, easy to read, 7px tall\
![winds](fonts/winds.png)

**yesterday**: bold, readable, distinctive, 10px tall\
![yesterday](fonts/yesterday.png)

**yolk**: classic, fantasy, 9px tall\
![yolk](fonts/yolk.png)

**ziplock**: round, cheerful, comic, 13px tall\
![ziplock](fonts/ziplock.png)

> todo: include font sampler image