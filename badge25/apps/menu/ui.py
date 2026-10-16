import math
import random
from badgeware import brushes, shapes, io, screen, Matrix, get_battery_level, is_charging

black = brushes.color(0, 0, 0)
background = brushes.color(35, 41, 37)
phosphor = brushes.color(211, 250, 55)
terminal_text = brushes.color(60, 71, 16)
terminal_fade = brushes.color(35, 41, 37, 150)


def draw_background():
    # draw over the corners in black ready for the rounded rectangle that makes
    # up most of the background
    screen.brush = black
    screen.draw(shapes.rectangle(0, 0, 10, 10))
    screen.draw(shapes.rectangle(150, 0, 10, 10))
    screen.draw(shapes.rectangle(0, 110, 10, 10))
    screen.draw(shapes.rectangle(150, 110, 10, 10))

    # draw the faux crt shape background area
    screen.brush = background
    screen.draw(shapes.rounded_rectangle(0, 0, 160, 120, 8))

    # draw the scrolling terminal effects
    draw_terminal()


class Terminal:
    lines = []
    max_lines = 25
    line_added_at = None
    lines_added = 0
    speed = 250

    def update():
        if io.ticks - Terminal.line_added_at > Terminal.speed:
            Terminal.add_line()

    def add_line():
        Terminal.lines.append(random.randint(20, 100))
        Terminal.line_added_at = io.ticks
        Terminal.lines_added += 1
        if len(Terminal.lines) > Terminal.max_lines:
            Terminal.lines = Terminal.lines[len(Terminal.lines) - Terminal.max_lines :]


# pre populate the terminal
for _ in range(25):
    Terminal.add_line()


# the terminal effect creates a rolling window of text that is infinitely
# populated with new lines
def draw_terminal():
    screen.brush = terminal_text

    # update the fake terminal
    Terminal.update()

    # draw the terminal lines
    rect = shapes.rectangle(0, 0, 1, 1)
    for i in range(21):
        # work out the position of screen that this line will be rendered
        y = 20 + i * 5
        yo = ((io.ticks - Terminal.line_added_at) / Terminal.speed) * 5
        y = int(y - yo)

        # force the random seed so that word widths will always be consistent for
        # each line...
        random.seed(i + Terminal.lines_added)
        cx = 0
        while cx < Terminal.lines[i]:
            # pick a random word width
            w = random.randint(3, 10)
            # draw the "greeked" word
            rect.transform = Matrix().translate(cx + 5, y).scale(w, 2)
            screen.draw(rect)
            # add a space
            cx += w + 2

    # draw the terminal fade at top
    screen.brush = terminal_fade
    screen.draw(shapes.rectangle(0, 15, 160, 5))
    screen.draw(shapes.rectangle(0, 15, 160, 3))


def draw_header():
    # create animated header text
    dots = "." * int(math.sin(io.ticks / 250) * 2 + 2)
    label = f"Mona-OS v4.03{dots}"
    pos = (5, 2)

    # draw the OS title
    screen.brush = phosphor
    screen.text(label, *pos)

    # draw the battery indicator
    if is_charging():
        battery_level = (io.ticks / 20) % 100
    else:
        battery_level = get_battery_level()
    pos = (137, 4)
    size = (16, 8)
    screen.brush = phosphor
    screen.draw(shapes.rectangle(*pos, *size))
    screen.draw(shapes.rectangle(pos[0] + size[0], pos[1] + 2, 1, 4))
    screen.brush = background
    screen.draw(shapes.rectangle(pos[0] + 1, pos[1] + 1, size[0] - 2, size[1] - 2))

    # draw the battery fill level
    width = ((size[0] - 4) / 100) * battery_level
    screen.brush = phosphor
    screen.draw(shapes.rectangle(pos[0] + 2, pos[1] + 2, width, size[1] - 4))
