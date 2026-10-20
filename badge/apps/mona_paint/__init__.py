"""
A Windows 98 style paint program.

Controls:
* Up / Down / Left / Right = Move the pointer
* Enter = Click, hold to drag
* Tilt = Move the pointer, Enter held keeps the tilt steady for long strokes
* Back = Undo
"""

import math
import micropython
import random

badge.mode(LORES)
previous_autorotate = badge.autorotate()
previous_antialias = screen.antialias
screen.antialias = image.OFF

import ui

TOOLS = ("pencil", "brush", "eraser", "fill", "picker", "spray", "line", "rectangle", "ellipse", "rounded")
OPTIONS = {
    "brush": (2, 4, 6),
    "eraser": (2, 4, 6),
    "spray": (4, 6, 9),
    "line": (1, 2, 3),
    "rectangle": ("outline", "filled"),
    "ellipse": ("outline", "filled"),
    "rounded": ("outline", "filled"),
}
SHAPES = ("line", "rectangle", "ellipse", "rounded")

SAVE_FILE = "/state/mona_paint_lores.rle"
OLDER_SAVES = (
    ("/state/mona_paint_2x.rle", 140, 88, 1),
    ("/state/mona_paint.rle", 280, 176, 2),
)
WHITE_INDEX = micropython.const(7)

POINTER_SLOW = 20
POINTER_FAST = 110
POINTER_RAMP_MS = 700
MAX_DT = 50
SPRAY_DOTS = 6

TILT_SMOOTH_MS = 100
TILT_DEAD_ZONE = 0.05
TILT_RECENTRE_MS = 3000
TILT_RECENTRE_LIMIT = 0.12
TILT_GAIN = 500
TILT_MAX_SPEED = 130

canvas = image(ui.PIXELS_W, ui.PIXELS_H)
canvas.antialias = image.OFF
undo_canvas = image(ui.PIXELS_W, ui.PIXELS_H)
undo_canvas.antialias = image.OFF
preview = image(ui.PIXELS_W, ui.PIXELS_H)
preview.antialias = image.OFF
ink = image(1, 1)
fill_stack = bytearray(ui.PIXELS_W * ui.PIXELS_H * 4)
palette_strip = image(len(ui.PALETTE), 1)
for index, swatch in enumerate(ui.PALETTE_PENS):
    palette_strip.pen = swatch
    palette_strip.put(index, 0)


inverse_indices = bytearray(range(len(ui.PALETTE)))
for first, second in ui.INVERT_PAIRS:
    inverse_indices[first] = second
    inverse_indices[second] = first

tool = "pencil"
previous_tool = tool
option = dict.fromkeys(OPTIONS, 0)
pen = ui.PALETTE_PENS[0]
pointer_x = ui.CANVAS_X + ui.CANVAS_W / 2
pointer_y = ui.CANVAS_Y + ui.CANVAS_H / 2
moving_since = None
gravity = None
tilt_reference = None
tilt_rotation = None
last_ticks = badge.ticks
open_menu = None
stroke = None
has_undo = False


def clear_canvas(target):
    target.pen = ui.WHITE
    target.clear()


def snapshot():
    global has_undo
    undo_canvas.blit(canvas, vec2(0, 0))
    has_undo = True


def undo():
    global canvas, undo_canvas
    if has_undo:
        canvas, undo_canvas = undo_canvas, canvas


@micropython.viper
def flood(pixels, stack, ink_pixel, width: int, height: int, start: int):
    canvas_pixels = ptr32(pixels)
    pending = ptr32(stack)
    colour = ptr32(ink_pixel)[0]
    target = canvas_pixels[start]
    if target == colour:
        return
    canvas_pixels[start] = colour
    pending[0] = start
    top = 1
    while top > 0:
        top -= 1
        index = pending[top]
        x = index % width
        if x > 0 and canvas_pixels[index - 1] == target:
            canvas_pixels[index - 1] = colour
            pending[top] = index - 1
            top += 1
        if x < width - 1 and canvas_pixels[index + 1] == target:
            canvas_pixels[index + 1] = colour
            pending[top] = index + 1
            top += 1
        if index >= width and canvas_pixels[index - width] == target:
            canvas_pixels[index - width] = colour
            pending[top] = index - width
            top += 1
        if index < width * (height - 1) and canvas_pixels[index + width] == target:
            canvas_pixels[index + width] = colour
            pending[top] = index + width
            top += 1


@micropython.viper
def remap(pixels, total: int, colours, count: int, mapping):
    canvas_pixels = ptr32(pixels)
    palette = ptr32(colours)
    table = ptr8(mapping)
    last = canvas_pixels[0] ^ 1
    result = 0
    for i in range(total):
        value = canvas_pixels[i]
        if value != last:
            last = value
            index = int(WHITE_INDEX)
            for candidate in range(count):
                if palette[candidate] == value:
                    index = candidate
                    break
            result = palette[table[index]]
        canvas_pixels[i] = result


@micropython.viper
def encode(pixels, total: int, colours, count: int, out) -> int:
    canvas_pixels = ptr32(pixels)
    palette = ptr32(colours)
    data = ptr8(out)
    written = 0
    run_value = canvas_pixels[0] ^ 1
    run_index = 0
    run = 0
    for i in range(total):
        value = canvas_pixels[i]
        if value == run_value and run < 255:
            run += 1
            continue
        index = int(WHITE_INDEX)
        for candidate in range(count):
            if palette[candidate] == value:
                index = candidate
                break
        if run > 0:
            data[written] = run
            data[written + 1] = run_index
            written += 2
        run_value = value
        run_index = index
        run = 1
    data[written] = run
    data[written + 1] = run_index
    return written + 2


@micropython.viper
def decode(source, length: int, colours, count: int, pixels, total: int) -> int:
    data = ptr8(source)
    palette = ptr32(colours)
    canvas_pixels = ptr32(pixels)
    filled = 0
    for i in range(0, length, 2):
        run = data[i]
        index = data[i + 1]
        if index >= count or filled + run > total:
            return 0
        colour = palette[index]
        for _ in range(run):
            canvas_pixels[filled] = colour
            filled += 1
    return filled


def invert():
    remap(canvas.raw, ui.PIXELS_W * ui.PIXELS_H, palette_strip.raw, len(ui.PALETTE), inverse_indices)


def save():
    out = bytearray(ui.PIXELS_W * ui.PIXELS_H * 2)
    length = encode(canvas.raw, ui.PIXELS_W * ui.PIXELS_H, palette_strip.raw, len(ui.PALETTE), out)
    try:
        with open(SAVE_FILE, "wb") as f:
            f.write(memoryview(out)[:length])
    except OSError:
        pass


def nearest(rgb, palette):
    distances = [sum((rgb[channel] - other[channel]) ** 2 for channel in range(3)) for other in palette]
    return distances.index(min(distances))


def load_older(path, width, height, shrink):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return False
    old_palette = ui.LEGACY_PALETTE if shrink > 1 else ui.PALETTE
    colours = old_palette + ui.PALETTE
    strip = image(len(colours), 1)
    for index, rgb in enumerate(colours):
        strip.pen = color.rgb(*rgb)
        strip.put(index, 0)
    older = image(width, height)
    older.antialias = image.OFF
    total = width * height
    if decode(data, len(data), strip.raw, len(old_palette), older.raw, total) != total:
        return False
    mapping = bytes(len(old_palette) + nearest(rgb, ui.PALETTE) for rgb in old_palette)
    remap(older.raw, total, strip.raw, len(old_palette), mapping)
    shown_w, shown_h = width // shrink, height // shrink
    canvas.blit(older, rect((ui.PIXELS_W - shown_w) // 2, (ui.PIXELS_H - shown_h) // 2, shown_w, shown_h))
    save()
    return True


def load():
    try:
        with open(SAVE_FILE, "rb") as f:
            data = f.read()
    except OSError:
        for path, width, height, shrink in OLDER_SAVES:
            if load_older(path, width, height, shrink):
                return
        return
    total = ui.PIXELS_W * ui.PIXELS_H
    if decode(data, len(data), palette_strip.raw, len(ui.PALETTE), canvas.raw, total) != total:
        clear_canvas(canvas)


def fill(x, y):
    ink.pen = pen
    ink.clear()
    flood(canvas.raw, fill_stack, ink.raw, ui.PIXELS_W, ui.PIXELS_H, y * ui.PIXELS_W + x)


def size():
    return OPTIONS[tool][option[tool]]


def paint_segment(x0, y0, x1, y1):
    if tool == "pencil":
        canvas.pen = pen
        canvas.line(x0, y0, x1, y1)
    elif tool == "brush":
        canvas.pen = pen
        radius = size() / 2
        canvas.shape(shape.line(x0, y0, x1, y1, size()))
        canvas.circle(vec2(x0, y0), radius)
        canvas.circle(vec2(x1, y1), radius)
    elif tool == "eraser":
        canvas.pen = ui.WHITE
        half = size() // 2
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        for step in range(steps + 1):
            x = x0 + (x1 - x0) * step // steps
            y = y0 + (y1 - y0) * step // steps
            canvas.rectangle(x - half, y - half, size(), size())


def spray(x, y):
    canvas.pen = pen
    radius = size()
    for _ in range(SPRAY_DOTS):
        angle = random.random() * math.pi * 2
        distance = random.random() * radius
        canvas.put(int(x + math.cos(angle) * distance), int(y + math.sin(angle) * distance))


def draw_shape(target, x0, y0, x1, y1):
    target.pen = pen
    if tool == "line":
        if size() == 1:
            target.line(x0, y0, x1, y1)
        else:
            target.shape(shape.line(x0, y0, x1, y1, size()))
        return
    left, top = min(x0, x1), min(y0, y1)
    width, height = abs(x1 - x0) + 1, abs(y1 - y0) + 1
    filled = size() == "filled"
    if tool == "rectangle":
        if filled:
            target.rectangle(left, top, width, height)
        else:
            target.rectangle(left, top, width, 1)
            target.rectangle(left, top + height - 1, width, 1)
            target.rectangle(left, top, 1, height)
            target.rectangle(left + width - 1, top, 1, height)
        return
    if tool == "ellipse":
        draw_ellipse(target, left, top, left + width - 1, top + height - 1, filled)
        return
    outline = shape.rounded_rectangle(left, top, width, height, min(6, width / 2, height / 2))
    target.shape(outline if filled else outline.stroke(1))


def ellipse_row(target, left, right, y, filled):
    if filled:
        target.rectangle(left, y, right - left + 1, 1)
    else:
        target.put(left, y)
        target.put(right, y)


def draw_ellipse(target, left, top, right, bottom, filled):
    a = right - left
    b = bottom - top
    odd = b & 1
    dx = 4 * (1 - a) * b * b
    dy = 4 * (odd + 1) * a * a
    error = dx + dy + odd * a * a
    top += (b + 1) // 2
    bottom = top - odd
    a_step = 8 * a * a
    b_step = 8 * b * b
    while left <= right:
        ellipse_row(target, left, right, top, filled)
        ellipse_row(target, left, right, bottom, filled)
        twice = 2 * error
        if twice <= dy:
            top += 1
            bottom -= 1
            dy += a_step
            error += dy
        if twice >= dx or 2 * error > dy:
            left += 1
            right -= 1
            dx += b_step
            error += dx
    while top - bottom < b:
        ellipse_row(target, left - 1, right + 1, top, filled)
        ellipse_row(target, left - 1, right + 1, bottom, filled)
        top += 1
        bottom -= 1


def canvas_point():
    x = (int(pointer_x) - ui.CANVAS_X) // ui.PIXEL
    y = (int(pointer_y) - ui.CANVAS_Y) // ui.PIXEL
    return x, y


def on_canvas():
    x, y = canvas_point()
    return 0 <= x < ui.PIXELS_W and 0 <= y < ui.PIXELS_H


def choose_tool(name):
    global tool, previous_tool
    if name != "picker":
        previous_tool = name
    tool = name


def menu_action(item):
    if item == "New" or item == "Clear Image":
        snapshot()
        clear_canvas(canvas)
    elif item == "Save":
        save()
    elif item == "Exit":
        on_exit()
        reset()
    elif item == "Undo":
        undo()
    elif item == "Invert Colors":
        snapshot()
        invert()


def click_menus(x, y):
    global open_menu
    if open_menu is not None:
        for title, items, title_x, _width in ui.menu_titles():
            if title == open_menu:
                for item, item_x, item_y, item_w in ui.menu_items(title_x, items):
                    if ui.inside(x, y, (item_x, item_y, item_w, ui.MENU_H)):
                        open_menu = None
                        menu_action(item)
                        return True
        open_menu = None
        return True
    for title, _items, title_x, width in ui.menu_titles():
        if ui.inside(x, y, (title_x, ui.MENU_Y, width, ui.MENU_H)):
            open_menu = title
            return True
    return False


def click(x, y):
    global pen, stroke
    if click_menus(x, y):
        return
    if ui.inside(x, y, ui.CLOSE):
        menu_action("Exit")
        return
    for index, name in enumerate(TOOLS):
        if ui.inside(x, y, ui.tool_rect(index)):
            choose_tool(name)
            return
    if tool in OPTIONS:
        for index in range(len(OPTIONS[tool])):
            if ui.inside(x, y, ui.option_rect(index)):
                option[tool] = index
                return
    for index, swatch in enumerate(ui.PALETTE_PENS):
        if ui.inside(x, y, ui.palette_rect(index)):
            pen = swatch
            return
    if not on_canvas():
        return
    cx, cy = canvas_point()
    if tool == "picker":
        pen = canvas.get(cx, cy)
        choose_tool(previous_tool)
        return
    snapshot()
    if tool == "fill":
        fill(cx, cy)
        return
    stroke = (cx, cy, cx, cy)
    if tool in SHAPES:
        return
    if tool == "spray":
        spray(cx, cy)
    else:
        paint_segment(cx, cy, cx, cy)


def drag():
    global stroke
    cx, cy = canvas_point()
    start_x, start_y, last_x, last_y = stroke
    if tool == "spray":
        spray(cx, cy)
    elif tool not in SHAPES and (cx, cy) != (last_x, last_y):
        paint_segment(last_x, last_y, cx, cy)
    stroke = (start_x, start_y, cx, cy)


def release():
    global stroke
    if tool in SHAPES:
        start_x, start_y, _last_x, _last_y = stroke
        cx, cy = canvas_point()
        draw_shape(canvas, start_x, start_y, cx, cy)
    stroke = None


def read_tilt(dt):
    global gravity
    reading = badge.imu()[:3]
    if not any(reading):
        return None
    if gravity is None:
        gravity = list(reading)
    else:
        k = min(1.0, dt / TILT_SMOOTH_MS)
        for axis in range(3):
            gravity[axis] += (reading[axis] - gravity[axis]) * k
    gx, gy, gz = gravity
    length = math.sqrt(gx * gx + gy * gy + gz * gz) or 1.0
    return math.asin(max(-1.0, min(1.0, gx / length))), math.atan2(gz, gy)


def wrap(angle):
    return (angle + math.pi) % (2 * math.pi) - math.pi


def dead_zone(lean):
    if lean > TILT_DEAD_ZONE:
        return lean - TILT_DEAD_ZONE
    if lean < -TILT_DEAD_ZONE:
        return lean + TILT_DEAD_ZONE
    return 0.0


def tilt_speed(lean):
    return max(-TILT_MAX_SPEED, min(TILT_MAX_SPEED, dead_zone(lean) * TILT_GAIN))


def tilt_pointer(dt):
    global pointer_x, pointer_y, tilt_reference, tilt_rotation
    badge.autorotate(previous_autorotate and not badge.held(BUTTON_SELECT))
    lean = read_tilt(dt)
    if lean is None:
        return
    side, fore = lean
    if badge.rotate_180() != tilt_rotation:
        tilt_rotation = badge.rotate_180()
        tilt_reference = None
    if tilt_reference is None:
        tilt_reference = (side, fore)
    lean_x = side - tilt_reference[0]
    lean_y = wrap(fore - tilt_reference[1])
    if not badge.held(BUTTON_SELECT) and max(abs(lean_x), abs(lean_y)) < TILT_RECENTRE_LIMIT:
        k = 1 - math.exp(-dt / TILT_RECENTRE_MS)
        tilt_reference = (tilt_reference[0] + lean_x * k, wrap(tilt_reference[1] + lean_y * k))
    if badge.rotate_180():
        lean_x, lean_y = -lean_x, -lean_y
    pointer_x = max(0, min(screen.width - 1, pointer_x + tilt_speed(lean_x) * dt / 1000))
    pointer_y = max(0, min(screen.height - 1, pointer_y + tilt_speed(lean_y) * dt / 1000))


def move_pointer(dt):
    global pointer_x, pointer_y, moving_since
    dx = int(badge.held(BUTTON_RIGHT)) - int(badge.held(BUTTON_LEFT))
    dy = int(badge.held(BUTTON_DOWN)) - int(badge.held(BUTTON_UP))
    if not dx and not dy:
        moving_since = None
        return
    if moving_since is None:
        moving_since = badge.ticks
        pointer_x += dx
        pointer_y += dy
    else:
        ramp = min(1, (badge.ticks - moving_since) / POINTER_RAMP_MS)
        speed = POINTER_SLOW + (POINTER_FAST - POINTER_SLOW) * ramp * ramp
        pointer_x += dx * speed * dt / 1000
        pointer_y += dy * speed * dt / 1000
    pointer_x = max(0, min(screen.width - 1, pointer_x))
    pointer_y = max(0, min(screen.height - 1, pointer_y))


def update():
    global last_ticks

    dt = min(badge.ticks - last_ticks, MAX_DT)
    last_ticks = badge.ticks
    move_pointer(dt)
    tilt_pointer(dt)

    if badge.pressed(BUTTON_SELECT):
        click(int(pointer_x), int(pointer_y))
    elif stroke is not None and badge.held(BUTTON_SELECT):
        drag()
    if stroke is not None and badge.released(BUTTON_SELECT):
        release()
    if badge.pressed(BUTTON_BACK) and stroke is None:
        undo()

    ui.draw_title()
    ui.draw_menu_bar(open_menu)
    ui.draw_toolbox(TOOLS, tool, OPTIONS.get(tool, ()), option.get(tool))
    if stroke is not None and tool in SHAPES:
        start_x, start_y, _last_x, _last_y = stroke
        cx, cy = canvas_point()
        preview.blit(canvas, vec2(0, 0))
        draw_shape(preview, start_x, start_y, cx, cy)
        ui.draw_workspace(preview)
    else:
        ui.draw_workspace(canvas)
    ui.draw_palette(pen)
    ui.draw_menu(open_menu, pointer_x, pointer_y)
    ui.draw_pointer(pointer_x, pointer_y)


def on_exit():
    save()
    screen.antialias = previous_antialias
    badge.autorotate(previous_autorotate)


clear_canvas(canvas)
clear_canvas(undo_canvas)
load()
run(update)
