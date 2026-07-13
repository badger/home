import sys
import os

sys.path.insert(0, "/system/apps/fireplace")
os.chdir("/system/apps/fireplace")

from badgeware import screen, io, run, brushes, PixelFont, shapes

FRAME_COUNT       = 20
DEFAULT_DURATION  = 100   # ms per frame
MIN_DURATION      = 50
MAX_DURATION      = 1000
SPEED_STEP        = 50
LABEL_TIMEOUT     = 1500  # ms to show the label after a speed change

_current_frame    = 0
_last_tick        = None
_frame_duration   = DEFAULT_DURATION
_label_until      = 0     # ticks timestamp until which to show the label
_needs_redraw     = True  # reload frame when it advances or label expires

_font             = None
_label_brush      = None
_bg_brush         = None


def init():
    global _font, _label_brush, _bg_brush
    _font        = PixelFont.load("/system/assets/fonts/nope.ppf")
    screen.font  = _font
    _label_brush = brushes.color(255, 255, 255, 200)
    _bg_brush    = brushes.color(0, 0, 0, 150)


def update():
    global _current_frame, _last_tick, _frame_duration, _label_until, _needs_redraw

    if _last_tick is None:
        _last_tick = io.ticks

    # Speed up
    if io.BUTTON_UP in io.pressed:
        _frame_duration = max(MIN_DURATION, _frame_duration - SPEED_STEP)
        _label_until = io.ticks + LABEL_TIMEOUT

    # Slow down
    if io.BUTTON_DOWN in io.pressed:
        _frame_duration = min(MAX_DURATION, _frame_duration + SPEED_STEP)
        _label_until = io.ticks + LABEL_TIMEOUT

    # Any of A, B, C resets to default
    if io.BUTTON_A in io.pressed or io.BUTTON_B in io.pressed or io.BUTTON_C in io.pressed:
        _frame_duration = DEFAULT_DURATION
        _label_until = io.ticks + LABEL_TIMEOUT

    # Advance frame
    if io.ticks - _last_tick >= _frame_duration:
        _current_frame = (_current_frame + 1) % FRAME_COUNT
        _last_tick = io.ticks
        _needs_redraw = True

    showing_label = io.ticks < _label_until

    # Only reload the PNG when the frame changed or the label just cleared
    if _needs_redraw:
        screen.load_into(f"frames/frame_{_current_frame:04d}.png")
        _needs_redraw = showing_label  # stay dirty while label is visible

    # Show speed label if recently changed
    if showing_label:
        label = f"{_frame_duration}ms/frame"
        w, h = screen.measure_text(label)
        pad = 4
        x = (screen.width - w) // 2
        y = screen.height - h - pad * 2
        screen.brush = _bg_brush
        screen.draw(shapes.rectangle(x - pad, y - pad, w + pad * 2, h + pad * 2))
        screen.brush = _label_brush
        screen.text(label, x, y)


if __name__ == "__main__":
    run(update, init=init)
