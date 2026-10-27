from art import PENS

FONT = font.nope
screen.font = FONT
_, LINE_H = screen.measure_text("Ag")
LINE_H = int(LINE_H) + 2
TEXT_W = 144


def pen(shade):
    screen.pen = PENS[shade]


def fill(x, y, w, h, shade):
    screen.pen = PENS[shade]
    screen.rectangle(x, y, w, h)


def text(s, x, y, shade=3):
    screen.pen = PENS[shade]
    screen.text(s, x, y)


def text_w(s):
    return screen.measure_text(s)[0]


def box(x, y, w, h):
    # Double-ruled frame like a classic handheld RPG text window.
    fill(x, y, w, h, 3)
    fill(x + 1, y + 1, w - 2, h - 2, 0)
    fill(x + 2, y + 2, w - 4, 1, 3)
    fill(x + 2, y + h - 3, w - 4, 1, 3)
    fill(x + 2, y + 2, 1, h - 4, 3)
    fill(x + w - 3, y + 2, 1, h - 4, 3)


def cursor(x, y):
    for i in range(4):
        fill(x + i, y + i, 1, 7 - 2 * i, 3)


def more_arrow(x, y):
    if (badge.ticks // 400) % 2:
        for i in range(4):
            fill(x + i, y + i, 7 - 2 * i, 1, 3)


def hp_bar(x, y, w, hp, max_hp):
    text("HP", x - 13, y - 3)
    fill(x, y, w, 4, 3)
    fill(x + 1, y + 1, w - 2, 2, 0)
    if max_hp > 0 and hp > 0:
        filled = max(1, int((w - 2) * hp / max_hp))
        fill(x + 1, y + 1, filled, 2, 2 if hp * 5 > max_hp else 3)


def wrap(message, width=TEXT_W):
    lines = []
    for para in message.split("\n"):
        line = ""
        for word in para.split(" "):
            trial = word if not line else line + " " + word
            if line and text_w(trial) > width:
                lines.append(line)
                line = word
            else:
                line = trial
        lines.append(line)
    return lines


def pages(message):
    lines = wrap(message)
    return [lines[i:i + 2] for i in range(0, len(lines), 2)]


class Dialog:
    """A queue of messages typed into the bottom text box.

    Items are strings (shown one two-line page at a time) or callables, which
    run when they reach the front of the queue.
    """

    CHARS_PER_MS = 0.05

    def __init__(self):
        self.queue = []
        self.page = None
        self.shown = 0.0
        self.total = 0

    def active(self):
        return self.page is not None or bool(self.queue)

    def say(self, *items):
        self.queue.extend(items)
        if self.page is None:
            self._next()

    def clear(self):
        self.queue = []
        self.page = None

    def _next(self):
        self.page = None
        while self.queue:
            item = self.queue.pop(0)
            if callable(item):
                item()
                continue
            if isinstance(item, list):
                self._show(item)
                return
            split = pages(item)
            self.queue = split[1:] + self.queue
            self._show(split[0])
            return

    def _show(self, lines):
        if isinstance(lines, str):
            lines = [lines]
        self.page = lines
        self.shown = 0.0
        self.total = sum(len(line) for line in lines)

    def typed(self):
        return self.page is not None and self.shown >= self.total

    def update(self, can_advance=True):
        if self.page is None:
            if self.queue:
                self._next()
            return
        self.shown = min(self.total, self.shown + badge.ticks_delta * self.CHARS_PER_MS)
        if badge.pressed(BUTTON_SELECT) or badge.pressed(BUTTON_BACK):
            if not self.typed():
                self.shown = self.total
            elif can_advance:
                self._next()

    def draw(self):
        if self.page is None:
            return
        box(0, 120 - 38, 160, 38)
        left = int(self.shown)
        for i, line in enumerate(self.page):
            if left <= 0:
                break
            text(line[:left], 8, 88 + i * LINE_H)
            left -= len(line)
        if self.typed() and self.queue:
            more_arrow(146, 110)
