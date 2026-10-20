import os
import sys
import time

APP_DIR = "/system/apps/haiku_printer"
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

from array import array
import random

from badgeware import State
from machine import Pin, UART

import escpos

HAIKU_FILE = "haikus.txt"
PAYMENT_FILE = "payments.txt"
LOGO = "assets/logo.bin"
QR = "assets/qr.bin"

SHUFFLE_MS = 700
SHUFFLE_STEP_MS = 70
DONE_MS = 2500
HISTORY = 10
STATUS_WAIT_MS = 200


class HaikuStore:
    """Index haikus.txt by byte offset so only one haiku is held in RAM."""

    def __init__(self, path):
        self.path = path
        self.offsets = array("I")
        self.numbers = array("H")
        offset = 0
        number = 0
        with open(path, "rb") as source:
            while True:
                line = source.readline()
                if not line:
                    break
                number += 1
                if self.parse(line):
                    self.offsets.append(offset)
                    self.numbers.append(number)
                offset += len(line)

    @staticmethod
    def parse(line):
        try:
            verses = [verse.strip() for verse in line.decode().strip().split(" / ")]
        except UnicodeError:
            return None
        if len(verses) != 3 or not all(verses):
            return None
        if any(len(verse) > escpos.COLS for verse in verses):
            return None
        return verses

    def __len__(self):
        return len(self.offsets)

    def get(self, index):
        with open(self.path, "rb") as source:
            source.seek(self.offsets[index])
            return self.numbers[index], self.parse(source.readline())


def check_printer(port):
    """Return None when ready, otherwise a short problem description."""
    while port.any():
        port.read()
    port.write(escpos.status_request(escpos.STATUS_PAPER))
    deadline = time.ticks_add(time.ticks_ms(), STATUS_WAIT_MS)
    while not port.any() and time.ticks_diff(deadline, time.ticks_ms()) > 0:
        time.sleep_ms(10)
    reply = port.read(1)
    if not reply:
        return "Printer not responding"
    if reply[0] & 0x60:
        return "Printer is out of paper"
    return None


def timestamp():
    now = time.localtime()
    if now[0] < 2025:
        return None, None
    return (
        "{:02d}/{:02d}/{:04d}".format(now[1], now[2], now[0]),
        "{:02d}:{:02d}".format(now[3], now[4]),
    )


def load_payments(path):
    try:
        with open(path) as source:
            payments = [line.strip() for line in source]
    except OSError:
        payments = []
    payments = [p for p in payments if p and len(p) <= escpos.COLS - len("PAID WITH ")]
    return payments or ["CURIOSITY"]


def receipt_size(*args):
    return sum(len(chunk) for chunk in escpos.receipt(*args))


IDLE, SHUFFLING, SHOWING, PRINTING, DONE, ERROR = range(6)

BACKGROUND = color.rgb(13, 17, 23)
CARD = color.rgb(22, 27, 34)
BORDER = color.rgb(48, 54, 61)
TEXT = color.rgb(230, 237, 243)
MUTED = color.rgb(125, 133, 144)
ACCENT = color.rgb(171, 125, 248)
GREEN = color.rgb(63, 185, 80)
RED = color.rgb(248, 81, 73)
SHADE = color.rgb(0, 0, 0, 170)

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2
mona = font.load("/system/assets/fonts/MonaSans-Medium.af")
screen.font = mona

store = HaikuStore(HAIKU_FILE)
payments = load_payments(PAYMENT_FILE)
uart = UART(1, baudrate=9600, bits=8, parity=None, stop=1, tx=Pin(4), rx=Pin(5), timeout=50)
printer = escpos.Printer(uart)

saved = {"last": -1, "printed": 0}
State.load("haiku_printer", saved)

mode = IDLE
history = []
position = -1
current = None
fitted = None
shuffle_until = 0
shuffle_next = 0
message_until = 0
error = ""


def show(index):
    global current, fitted
    current = (index,) + store.get(index)
    fitted = fit_verses(current[2])


def fit_verses(verses):
    size = 22
    while size > 12:
        if all(screen.measure_text(verse, font_size=size)[0] <= screen.width - 36 for verse in verses):
            break
        size -= 1
    return size


def pick():
    last = history[position] if history else -1
    choice = random.randrange(len(store))
    if len(store) > 1 and choice == last:
        choice = (choice + 1 + random.randrange(len(store) - 1)) % len(store)
    return choice


def remember(index):
    global position, history
    history = history[: position + 1] + [index]
    history = history[-HISTORY:]
    position = len(history) - 1


def start_shuffle():
    global mode, shuffle_until, shuffle_next
    mode = SHUFFLING
    shuffle_until = badge.ticks + SHUFFLE_MS
    shuffle_next = 0


def start_print():
    global mode, error, message_until
    problem = check_printer(uart)
    if problem:
        error = problem
        mode = ERROR
        message_until = badge.ticks + DONE_MS
        return
    _, number, verses = current
    date, clock = timestamp()
    args = (number, verses, LOGO, QR, date, clock, random.choice(payments))
    printer.start(escpos.receipt(*args), receipt_size(*args))
    mode = PRINTING


def finish_print():
    global mode, message_until
    saved["last"] = current[0]
    saved["printed"] += 1
    State.save("haiku_printer", saved)
    mode = DONE
    message_until = badge.ticks + DONE_MS


SHUFFLE_BUTTONS = (BUTTON_UP, BUTTON_DOWN, BUTTON_LEFT, BUTTON_RIGHT, BUTTON_BACK)


def shuffle_pressed():
    return any(badge.pressed(button) for button in SHUFFLE_BUTTONS)


def handle_input():
    global mode
    if mode == IDLE:
        if (badge.pressed(BUTTON_SELECT) or shuffle_pressed()) and len(store):
            start_shuffle()
    elif mode == SHOWING:
        if badge.pressed(BUTTON_SELECT):
            start_print()
        elif shuffle_pressed():
            start_shuffle()
    elif mode == PRINTING:
        if badge.pressed(BUTTON_BACK):
            printer.cancel()
    elif mode in (DONE, ERROR):
        if badge.pressed(BUTTON_SELECT) or badge.pressed(BUTTON_BACK):
            mode = SHOWING


def advance():
    global mode, shuffle_next
    if mode == SHUFFLING:
        if badge.ticks >= shuffle_until:
            remember(pick())
            show(history[position])
            mode = SHOWING
        elif badge.ticks >= shuffle_next:
            show(random.randrange(len(store)))
            shuffle_next = badge.ticks + SHUFFLE_STEP_MS
    elif mode == PRINTING:
        if not printer.pump(badge.ticks_delta):
            finish_print()
    elif mode in (DONE, ERROR) and badge.ticks >= message_until:
        mode = SHOWING


def label(text, y, size=14, pen=MUTED, x=None):
    width = screen.measure_text(text, font_size=size)[0]
    screen.pen = pen
    screen.text(text, (screen.width - width) / 2 if x is None else x, y, font_size=size)


def draw_header():
    screen.pen = TEXT
    screen.text("Haiku Printer", 12, 8, font_size=16)
    count = "{} printed".format(saved["printed"])
    width = screen.measure_text(count, font_size=12)[0]
    screen.pen = MUTED
    screen.text(count, screen.width - width - 12, 11, font_size=12)


def draw_card():
    top = 38
    height = 152
    screen.pen = CARD
    screen.shape(shape.rounded_rectangle(8, top, screen.width - 16, height, 8))
    screen.pen = BORDER
    screen.shape(shape.rounded_rectangle(8, top, screen.width - 16, height, 8).stroke(1))
    if current is None:
        label("{} code haiku await".format(len(store)), top + 48, 20, TEXT)
        label("Press SELECT to pick one", top + 82, 14)
        return
    label("#" + escpos.haiku_id(current[1]), top + 12, 14, ACCENT)
    line_height = fitted + 10
    y = top + 44 + (88 - line_height * 3) / 2
    for verse in current[2]:
        label(verse, y, fitted, MUTED if mode == SHUFFLING else TEXT)
        y += line_height


def draw_footer():
    hints = {
        IDLE: "SELECT pick",
        SHUFFLING: "Shuffling...",
        SHOWING: "SELECT print, ^ shuffle",
        PRINTING: "BACK stop",
        DONE: "",
        ERROR: "",
    }
    label(hints[mode], screen.height - 26, 12)


def draw_dialog(title, detail, pen, progress=None):
    screen.pen = SHADE
    screen.rectangle(0, 0, screen.width, screen.height)
    screen.pen = CARD
    screen.shape(shape.rounded_rectangle(30, 70, screen.width - 60, 100, 8))
    screen.pen = pen
    screen.shape(shape.rounded_rectangle(30, 70, screen.width - 60, 100, 8).stroke(2))
    label(title, 86, 20, TEXT)
    label(detail, 118, 13)
    if progress is not None:
        screen.pen = BORDER
        screen.shape(shape.rounded_rectangle(50, 144, screen.width - 100, 10, 5))
        screen.pen = pen
        screen.shape(shape.rounded_rectangle(50, 144, max(10, (screen.width - 100) * progress), 10, 5))


def draw():
    screen.pen = BACKGROUND
    screen.clear()
    draw_header()
    draw_card()
    draw_footer()
    if mode == PRINTING:
        draw_dialog("Printing...", "{}%".format(int(printer.progress * 100)), GREEN, printer.progress)
    elif mode == DONE:
        draw_dialog("Printed!", "Tear the receipt off gently", GREEN)
    elif mode == ERROR:
        draw_dialog("Can't print", error, RED)


def update():
    handle_input()
    advance()
    draw()


def on_exit():
    uart.deinit()


if len(store) and 0 <= saved["last"] < len(store):
    remember(saved["last"])
    show(saved["last"])
    mode = SHOWING

run(update)
