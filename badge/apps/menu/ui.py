import math
import random


black = color.rgb(0, 0, 0)
background = color.rgb(60, 15, 10)
phosphor = color.rgb(246, 135, 4)
terminal_text = color.rgb(123, 72, 2)
terminal_fade = color.rgb(60, 15, 10, 150)


def draw_background():
    # draw over the corners in black ready for the rounded rectangle that makes
    # up most of the background
    screen.pen = black
    screen.rectangle(0, 0, 10, 10)
    screen.rectangle(150, 0, 10, 10)
    screen.rectangle(0, 110, 10, 10)
    screen.rectangle(150, 110, 10, 10)

    # draw the faux crt shape background area
    screen.pen = background
    screen.shape(shape.rounded_rectangle(0, 0, 160, 120, 8))

    # draw the scrolling terminal effects
    draw_terminal()


class Terminal:
    lines = []
    max_lines = 25
    line_added_at = None
    lines_added = 0
    speed = 250

    def update():
        if badge.ticks - Terminal.line_added_at > Terminal.speed:
            Terminal.add_line()

    def add_line():
        Terminal.lines.append(random.randint(20, 140))
        Terminal.line_added_at = badge.ticks
        Terminal.lines_added += 1
        if len(Terminal.lines) > Terminal.max_lines:
            Terminal.lines = Terminal.lines[len(Terminal.lines) - Terminal.max_lines:]


# pre populate the terminal
for _ in range(25):
    Terminal.add_line()


# the terminal effect creates a rolling window of text that is infinitely
# populated with new lines
def draw_terminal():
    screen.pen = terminal_text

    # update the fake terminal
    Terminal.update()

    for i in range(21):
        # work out the position of screen that this line will be rendered
        y = 20 + i * 5
        yo = ((badge.ticks - Terminal.line_added_at) / Terminal.speed) * 5
        y = int(y - yo)

        # force the random seed so that word widths will always be consistent for
        # each line...
        random.seed(i + Terminal.lines_added)
        cx = 0
        while cx < Terminal.lines[i]:
            # pick a random word width
            w = random.randint(3, 10)
            # draw the "greeked" word
            screen.rectangle(cx + 5, y, w, 2)
            # rect.transform = mat3().translate(cx + 5, y).scale(w, 2)
            # screen.shape(rect)
            # add a space
            cx += w + 2

    # draw the terminal fade at top
    screen.pen = terminal_fade
    screen.rectangle(0, 13, 160, 5)
    screen.rectangle(0, 13, 160, 3)


def draw_header():
    # create animated header text
    dots = "." * int(math.sin(badge.ticks / 250) * 2 + 2)
    label = f"BadgeOS{dots}"
    pos = (5, 2)

    # draw the OS title
    screen.pen = phosphor
    screen.text(label, *pos)

    # draw the battery indicator
    if badge.is_charging():
        battery_level = (badge.ticks / 20) % 100
    else:
        battery_level = badge.battery_level()
    pos = (137, 4)
    size = (16, 8)
    screen.pen = phosphor
    screen.shape(shape.rectangle(*pos, *size))
    screen.shape(shape.rectangle(pos[0] + size[0], pos[1] + 2, 1, 4))
    screen.pen = background
    screen.shape(shape.rectangle(pos[0] + 1, pos[1] + 1, size[0] - 2, size[1] - 2))

    # draw the battery fill level
    width = ((size[0] - 4) / 100) * battery_level
    screen.pen = phosphor
    screen.shape(shape.rectangle(pos[0] + 2, pos[1] + 2, width, size[1] - 4))
