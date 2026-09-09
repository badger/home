# A little library of methods to display text on the screen in mildly fancy ways.

black = color.rgb(0, 0, 0)
white = color.rgb(235, 245, 255)
small_font = font.ark
large_font = font.absolute


def center_text(text, y):
    # Centre text on screen

    w, h = screen.measure_text(text)
    screen.text(text, (screen.width / 2) - (w / 2), y)


def wrap_text(text, x, y):
    # Wrap text across multiple lines

    lines = text.splitlines()
    for line in lines:
        _, h = screen.measure_text(line)
        screen.text(line, x, y)
        y += h * 0.8


def stretch_text(text, x, y, distance, current_brush):
    # Stretch text across a given distance

    screen.pen = current_brush
    text_dims = screen.measure_text(text)
    width = text_dims[0]
    height = text_dims[1]

    # Calculate how much space should go between each letter
    totalspace = distance - width
    spacing = totalspace / (len(text) - 1)

    # Draw each character leaving that space between each one
    for i in text:
        screen.text(i, x, y)
        x += screen.measure_text(i)[0] + spacing
    return height


def user_message(header, lines):
    # A simple message screen with a heading and up to six lines of text.

    if not isinstance(lines, list):
        raise TypeError("lines must be provided in a list.")

    screen.pen = brush.pattern(color.rgb(0, 0, 0), color.rgb(20, 20, 20), 20)
    screen.clear()
    screen.font = large_font
    screen.pen = white
    center_text(header, 5)

    screen.font = small_font
    line_spacing = 8
    ty = 20

    for line in lines:
        center_text(line, ty)
        ty += line_spacing


def bullet_list(header, bullet_points):
    # A simple message screen with three bullet points.

    if not isinstance(bullet_points, list):
        raise TypeError("bullet points must be provided in a list.")

    screen.pen = brush.pattern(color.rgb(0, 0, 0), color.rgb(20, 20, 20), 20)
    screen.clear()
    screen.font = large_font
    screen.pen = white
    center_text(header, 5)

    ty = 23
    line_spacing = 30

    for i, b in enumerate(bullet_points):
        num = i + 1
        screen.font = large_font
        screen.text(f"{num}:", 10, ty)
        screen.font = small_font
        wrap_text(b, 30, ty + 1)
        ty += line_spacing
