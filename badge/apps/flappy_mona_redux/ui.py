from world import WIDTH

typeface = font.load("/system/assets/fonts/DynaPuff-Medium.af")

WHITE = color.rgb(255, 255, 255)
GOLD = color.rgb(255, 214, 80)
NAVY = color.rgb(22, 44, 96)
SHADOW = color.rgb(16, 36, 64, 150)
PANEL = color.rgb(16, 36, 64, 120)
DIM = color.rgb(16, 36, 64, 150)


def text_mode():
    screen.font = typeface
    screen.fill_rule = image.EVEN_ODD
    screen.antialias = image.X2


def pixel_mode():
    screen.antialias = image.OFF


def measure(text, size):
    return screen.measure_text(text, font_size=size)


def shadow_text(text, x, y, size, pen=WHITE):
    screen.pen = SHADOW
    screen.text(text, x + 2, y + 2, size)
    screen.pen = pen
    screen.text(text, x, y, size)


def outlined_text(text, x, y, size, fill, edge=NAVY, thickness=2):
    screen.pen = edge
    for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1), (0, 2), (0, -1)):
        screen.text(text, x + dx * thickness, y + dy * thickness, size)
    screen.pen = fill
    screen.text(text, x, y, size)


def centered(text, y, size, pen=WHITE, outline=None):
    width, _ = measure(text, size)
    x = (WIDTH - width) / 2
    if outline is None:
        shadow_text(text, x, y, size, pen)
    else:
        outlined_text(text, x, y, size, pen, outline)


def panel(x, y, w, h, radius=8, pen=PANEL):
    screen.pen = pen
    screen.shape(shape.rounded_rectangle(x, y, w, h, radius))
