"""Simple DVD-logo-style bouncing demo app for the badge.

This app draws a small rectangle with the label "DVD" that bounces around the
160x120 logical framebuffer and changes color on collisions.

No external assets required — keep per-frame work minimal.
"""
import random
from badge import screen, brushes, shapes, io, PixelFont

# App configuration
WIDTH = screen.width
HEIGHT = screen.height
LOGO_W = 28
LOGO_H = 12

# state
_x = 10
_y = 10
_vx = 60  # pixels per second
_vy = 40
_color = brushes.color(255, 0, 0)

try:
    screen.font = PixelFont.load("nope.ppf")
except Exception:
    # fallback: some firmwares may not support font loading here
    pass

def _rand_color():
    return brushes.color(random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))

def init():
    global _x, _y, _vx, _vy, _color
    _x = (WIDTH - LOGO_W) // 2
    _y = (HEIGHT - LOGO_H) // 2
    _vx = 60
    _vy = 40
    _color = _rand_color()

def update():
    global _x, _y, _vx, _vy, _color

    # frame time in seconds
    dt = io.ticks_delta / 1000.0

    # update position
    _x += _vx * dt
    _y += _vy * dt

    bounced = False
    # collision with left/right
    if _x <= 0:
        _x = 0
        _vx = abs(_vx)
        bounced = True
    elif _x + LOGO_W >= WIDTH:
        _x = WIDTH - LOGO_W
        _vx = -abs(_vx)
        bounced = True

    # collision with top/bottom
    if _y <= 0:
        _y = 0
        _vy = abs(_vy)
        bounced = True
    elif _y + LOGO_H >= HEIGHT:
        _y = HEIGHT - LOGO_H
        _vy = -abs(_vy)
        bounced = True

    if bounced:
        _color = _rand_color()

    # draw
    screen.brush = brushes.color(0, 0, 0)
    screen.clear()

    # draw logo background rectangle with a small outline
    screen.brush = brushes.color(0, 0, 0)
    screen.draw(shapes.rectangle(0, 0, WIDTH, HEIGHT))

    screen.brush = _color
    screen.draw(shapes.rounded_rectangle(int(_x), int(_y), LOGO_W, LOGO_H, 3))

    # draw the DVD label in contrasting color
    inv = brushes.color(255 - (_color.r if hasattr(_color, 'r') else 0), 255, 255)
    # simple heuristic: white text
    screen.brush = brushes.color(255, 255, 255)
    # center text inside the logo box (rough placement)
    tx = int(_x + 4)
    ty = int(_y + 2)
    try:
        screen.text("DVD", tx, ty)
    except Exception:
        # some images may not support text; ignore
        pass

def on_exit():
    # nothing to clean up
    pass

# Start the app loop
run(update)
