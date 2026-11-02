# Universe 2025 app contract

## The launcher owns the loop

Both `badge25/main.py` and the connected stock 2025 badge's
`/system/main.py` do this:

1. Let the menu return an app directory.
2. Add that directory to the import path and make it the current directory.
3. Import the app.
4. Call its optional `init()`.
5. Pass its `update()` to `badgeware.run()`.
6. On HOME, call its optional `on_exit()` and reset to the launcher.

Do not put an unconditional `run(update)` at the end of a 2025 app. Some
archived guidance suggests this, but it enters the loop during import, before
the launcher's call to `init()`. Follow the installed launcher instead.
Also do not assume standalone `run(update)` calls `init()` for you.

## Minimal app

This example uses only verified 2025 graphics and input tools. The font and
color brushes load once when the app is imported, so both launcher import and
direct execution work. A separate `init()` is not needed here.

```python
from badgeware import screen, PixelFont, brushes, io, run

screen.font = PixelFont.load("/system/assets/fonts/nope.ppf")
background = brushes.color(20, 24, 28)
foreground = brushes.color(255, 255, 255)
count = 0


def update():
    global count

    if io.BUTTON_B in io.pressed:
        count += 1

    screen.brush = background
    screen.clear()
    screen.brush = foreground
    screen.text("B presses: " + str(count), 8, 8)


if __name__ == "__main__":
    run(update)
```

For movement in pixels per second:

```python
if io.BUTTON_A in io.held:
    x -= speed * (io.ticks_delta / 1000)
if io.BUTTON_C in io.held:
    x += speed * (io.ticks_delta / 1000)
```

The hardware has A/B/C, UP/DOWN, and HOME inputs. Do not treat extra arrow keys
in the simulator as proof that the badge has LEFT/RIGHT buttons.

## Graphics and assets

Import `Image`, `SpriteSheet`, `shapes`, or `Matrix` from `badgeware` only when
needed. See `badge25/badgerware/` for signatures. Common calls:

```python
picture = Image.load("assets/picture.png")
sheet = SpriteSheet("assets/characters.png", 4, 2)
sprite = sheet.sprite(0, 0)
screen.blit(sprite, 10, 10)
screen.scale_blit(picture, 20, 20, 32, 32)
screen.draw(shapes.rectangle(0, 0, screen.width, screen.height))
width, height = screen.measure_text("Hello")
```

The last block illustrates signatures, not a standalone app. All drawing uses
`screen.brush`, not `screen.pen`. Paletted images reduce memory use, but the
archived Image docs warn that they cannot be drawn onto.

## Saved data

The archived docs describe writable LittleFS at `/`, separate from
`/system`. Confirm the actual directories on the connected badge. Choose a
unique app-specific save file or directory; create required parent directories
explicitly. Never overwrite another app's data or write saves into `/system`.

`badgeware.State` exists on the tested 2025 badge, but existence alone does not
confirm its argument order or file layout. Read its implementation or a
matching installed app before using it. Otherwise use ordinary JSON file I/O
in the verified writable location.

Handle missing files explicitly; report invalid data or failed saves. Do not
hide all errors with `except: pass`. Save after meaningful changes and on
exit, not on every frame.

## Differences that matter

The 2025 and 2026 badges share an RP2350 family and similar display size, but
that does not make their apps interchangeable. The 2025 software imports its
screen and input objects from `badgeware`; 2026 apps receive new graphics and
input globals from their runtime.

The connected 2025 badge's menu has a fixed list of six apps and already loads
each listed app's `icon.png`. `badge25/apps/menu/__init__.py` in this repo
instead discovers apps and provides pages. Neither is the 2026 menu.
Inspect before changing anything.
