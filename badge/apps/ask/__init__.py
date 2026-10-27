"""
Ask your own AI gateway a question and read the answer on the badge.

The badge has no keyboard, so you pick one of a few ready-made prompts. It goes
to an OpenAI-compatible chat completions gateway, such as CLIProxyAPI, and the
answer comes back as plain text. The gateway details come from secrets.py.

Controls:
* Up and down = Choose a prompt, or scroll an answer
* Left and right = Switch model, when GATEWAY_MODEL lists more than one
* Select = Ask, or ask again
* Back = Cancel, or go back to the prompts
"""

import math
import os
import sys

APP_DIR = "/system/apps/ask"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

import missing_details  # noqa: E402

import gateway  # noqa: E402

try:
    import secrets
except ImportError:
    secrets = None

MISSING = missing_details.missing("WIFI_SSID", "GATEWAY_URL")
if not MISSING:
    import wifi

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

WIDTH, HEIGHT = screen.width, screen.height

PROMPTS = (
    ("Icebreaker", "Give me one fun, original icebreaker question to ask someone I just met at GitHub Universe."),
    ("Git tip", "Share one lesser-known but genuinely useful git command, with a one-line example."),
    ("Haiku", "Write a haiku about shipping code at a developer conference. Put each line on its own line."),
    ("Fortune cookie", "Write a one-line developer fortune cookie."),
    ("Explain it", "Pick a random computer science idea and explain it to a five year old in two sentences."),
    ("Hot take", "Give me one playful, harmless hot take about software development."),
    ("Pep talk", "Give me a short, upbeat pep talk before I walk into my next conference session."),
)

# a short timeout so failures report quickly; retries set high enough that
# wifi's own error card never appears and the connecting page keeps reporting
WIFI_TIMEOUT = 10
WIFI_RETRIES = 100000

REPEAT_DELAY = 350          # ms a held button waits before repeating
REPEAT_EVERY = 90           # ms between repeats

background = color.rgb(13, 17, 23)
panel = color.rgb(22, 27, 34)
edge = color.rgb(48, 54, 61)
ink = color.rgb(230, 237, 243)
muted = color.rgb(139, 148, 158)
accent = color.rgb(163, 113, 247)
accent_soft = color.rgb(163, 113, 247, 56)
accent_faint = color.rgb(163, 113, 247, 40)
warning = color.rgb(248, 81, 73)

typeface = missing_details.mona_sans()
TITLE_SIZE = 18
ROW_SIZE = 16
BODY_SIZE = 15
SMALL_SIZE = 12
LINE_H = 20                 # body line spacing

HEADER_H = 30
FOOTER_H = 22
ROW_H = 24
LIST_TOP = HEADER_H + 8
BODY_X = 14
BODY_W = WIDTH - 2 * BODY_X - 6
BODY_TOP = HEADER_H + 10
BODY_ROWS = (HEIGHT - FOOTER_H - BODY_TOP - 4) // LINE_H

LIST, CONNECTING, THINKING, ANSWER, FAILED = range(5)


def setting(name):
    return str(getattr(secrets, name, "") or "").strip()


MODELS = [name.strip() for name in setting("GATEWAY_MODEL").split(",") if name.strip()]
MODELS = MODELS or [gateway.DEFAULT_MODEL]

client = None
problem = None              # what is wrong with secrets.py, if anything
if not MISSING:
    try:
        client = gateway.Gateway(setting("GATEWAY_URL"), setting("GATEWAY_KEY"), MODELS[0])
    except ValueError as reason:
        problem = "%s\n\nFix it in secrets.py on the badge, then open Ask again." % reason
    else:
        # start the radio now so it has associated by the first question
        wifi.connect(timeout=WIFI_TIMEOUT, retries=WIFI_RETRIES)

mode = FAILED if problem else LIST
selected = 0
model_index = 0
lines = []                  # the answer or the error, wrapped to the screen
top = 0                     # first answer line on screen
question = []               # the prompt, wrapped, while waiting
asked_at = 0
repeat_at = 0


def wrap(words, width, size):
    """Break text into lines no wider than width at this size."""
    screen.font = typeface
    out = []
    for paragraph in words.split("\n"):
        line = ""
        for word in paragraph.split(" "):
            if not word:
                continue
            trial = line + " " + word if line else word
            if screen.measure_text(trial, font_size=size)[0] <= width:
                line = trial
                continue
            if line:
                out.append(line)
            # a word wider than the whole line is cut where it has to be
            while len(word) > 1 and screen.measure_text(word, font_size=size)[0] > width:
                cut = len(word) - 1
                while cut > 1 and screen.measure_text(word[:cut], font_size=size)[0] > width:
                    cut -= 1
                out.append(word[:cut])
                word = word[cut:]
            line = word
        out.append(line)
    return out


def stepped(button):
    """True when the button is pressed, then again every so often while held."""
    global repeat_at
    if badge.pressed(button):
        repeat_at = badge.ticks + REPEAT_DELAY
        return True
    if badge.held(button) and badge.ticks >= repeat_at:
        repeat_at = badge.ticks + REPEAT_EVERY
        return True
    return False


def model_label():
    name = MODELS[model_index]
    return "< %s >" % name if len(MODELS) > 1 else name


def draw_header(title):
    screen.pen = panel
    screen.rectangle(0, 0, WIDTH, HEADER_H)
    screen.pen = edge
    screen.rectangle(0, HEADER_H, WIDTH, 1)

    screen.pen = accent
    screen.shape(shape.star(16, HEADER_H / 2, 4, 2.5, 8))

    screen.font = typeface
    screen.pen = ink
    screen.text(title, 30, 5, TITLE_SIZE)

    label = model_label()
    width, _ = screen.measure_text(label, font_size=SMALL_SIZE)
    screen.pen = muted
    screen.text(label, WIDTH - 12 - width, 9, SMALL_SIZE)


def draw_footer(left, right=""):
    y = HEIGHT - FOOTER_H
    screen.pen = panel
    screen.rectangle(0, y, WIDTH, FOOTER_H)
    screen.pen = edge
    screen.rectangle(0, y, WIDTH, 1)

    screen.font = typeface
    screen.pen = muted
    screen.text(left, 12, y + 4, SMALL_SIZE)
    if right:
        width, _ = screen.measure_text(right, font_size=SMALL_SIZE)
        screen.text(right, WIDTH - 12 - width, y + 4, SMALL_SIZE)


def draw_list():
    screen.pen = background
    screen.rectangle(0, 0, WIDTH, HEIGHT)
    draw_header("Ask")

    screen.font = typeface
    for index, (title, _) in enumerate(PROMPTS):
        y = LIST_TOP + index * ROW_H
        if index == selected:
            screen.pen = accent_soft
            screen.shape(shape.rounded_rectangle(8, y, WIDTH - 16, ROW_H - 3, 6))
            screen.pen = accent
            screen.shape(shape.rounded_rectangle(8, y, 4, ROW_H - 3, 2))
            screen.pen = ink
        else:
            screen.pen = muted
        screen.text(title, 22, y + 2, ROW_SIZE)

    draw_footer("SELECT ask", "LEFT/RIGHT model" if len(MODELS) > 1 else "")


def draw_waiting(heading, saying):
    """The question, a spinner and a line about what is happening."""
    screen.pen = background
    screen.rectangle(0, 0, WIDTH, HEIGHT)
    draw_header(PROMPTS[selected][0])

    screen.font = typeface
    screen.pen = muted
    for row, line in enumerate(question[:3]):
        screen.text(line, BODY_X, BODY_TOP + row * 17, SMALL_SIZE)

    cx, cy = WIDTH / 2, 142
    turned = badge.ticks / 1100 * 360
    screen.pen = accent_faint
    screen.shape(shape.arc(cx, cy, 24, 28, 0, 360))
    screen.pen = accent
    screen.shape(shape.arc(cx, cy, 24, 28, turned, turned + 90))
    pulse = 11 + 2.5 * math.sin(badge.ticks / 160)
    screen.shape(shape.star(cx, cy, 4, pulse * 0.3, pulse))

    screen.pen = ink
    width, _ = screen.measure_text(heading, font_size=BODY_SIZE)
    screen.text(heading, (WIDTH - width) / 2, 182, BODY_SIZE)
    screen.pen = muted
    width, _ = screen.measure_text(saying, font_size=SMALL_SIZE)
    screen.text(saying, (WIDTH - width) / 2, 202, SMALL_SIZE)

    draw_footer("BACK cancel")


def draw_lines(rows, first, pen):
    screen.font = typeface
    screen.pen = pen
    for row, line in enumerate(rows[first:first + BODY_ROWS]):
        screen.text(line, BODY_X, BODY_TOP + row * LINE_H, BODY_SIZE)

    # a scroll bar when there is more than fits
    if len(rows) > BODY_ROWS:
        track = BODY_ROWS * LINE_H
        x = WIDTH - 8
        screen.pen = edge
        screen.rectangle(x, BODY_TOP, 3, track)
        size = max(12, track * BODY_ROWS / len(rows))
        offset = (track - size) * first / (len(rows) - BODY_ROWS)
        screen.pen = accent
        screen.rectangle(x, int(BODY_TOP + offset), 3, int(size))


def draw_answer():
    screen.pen = background
    screen.rectangle(0, 0, WIDTH, HEIGHT)
    draw_header(PROMPTS[selected][0])
    draw_lines(lines, top, ink)
    took = "%.1fs" % (client.elapsed / 1000)
    draw_footer(took + (", cut short" if client.truncated else ""), "SELECT again   BACK prompts")


def draw_failed():
    screen.pen = background
    screen.rectangle(0, 0, WIDTH, HEIGHT)
    draw_header(PROMPTS[selected][0] if client else "Ask")
    screen.font = typeface
    screen.pen = warning
    screen.text("No answer" if client else "Check secrets.py", BODY_X, BODY_TOP, TITLE_SIZE)
    screen.pen = ink
    for row, line in enumerate(lines[:BODY_ROWS - 1]):
        screen.text(line, BODY_X, BODY_TOP + 28 + row * LINE_H, BODY_SIZE)
    if client:
        draw_footer("SELECT try again", "BACK prompts")
    else:
        draw_footer("HOME menu")


def ask():
    """Send the selected prompt, once there is a network to send it on."""
    global mode, question
    client.model = MODELS[model_index]
    question = wrap(PROMPTS[selected][1], BODY_W, SMALL_SIZE)
    if wifi.is_connected():
        send()
    else:
        mode = CONNECTING


def send():
    global mode, asked_at
    asked_at = badge.ticks
    client.ask(PROMPTS[selected][1])
    mode = THINKING


def answered():
    global mode, lines, top
    top = 0
    if client.state == gateway.DONE:
        lines = wrap(client.answer, BODY_W, BODY_SIZE)
        if client.truncated:
            lines[-1] += "..."
        mode = ANSWER
    else:
        lines = wrap(client.error or "Something went wrong.", BODY_W, BODY_SIZE)
        mode = FAILED


def update():
    global mode, selected, model_index, top

    if MISSING:
        missing_details.show(MISSING, draw_list)
        return

    if mode == LIST:
        if stepped(BUTTON_UP):
            selected = (selected - 1) % len(PROMPTS)
        if stepped(BUTTON_DOWN):
            selected = (selected + 1) % len(PROMPTS)
        if badge.pressed(BUTTON_LEFT):
            model_index = (model_index - 1) % len(MODELS)
        if badge.pressed(BUTTON_RIGHT):
            model_index = (model_index + 1) % len(MODELS)
        if badge.pressed(BUTTON_SELECT):
            ask()

    elif mode == CONNECTING:
        if badge.pressed(BUTTON_BACK):
            mode = LIST
        elif wifi.connect():
            send()

    elif mode == THINKING:
        if badge.pressed(BUTTON_BACK):
            client.cancel()
            mode = LIST
        elif client.update() != gateway.BUSY:
            answered()

    elif mode == ANSWER:
        if stepped(BUTTON_UP):
            top = max(0, top - 1)
        if stepped(BUTTON_DOWN):
            top = min(max(0, len(lines) - BODY_ROWS), top + 1)
        if badge.pressed(BUTTON_SELECT):
            ask()
        if badge.pressed(BUTTON_BACK):
            mode = LIST

    elif mode == FAILED and client:
        if badge.pressed(BUTTON_SELECT):
            ask()
        if badge.pressed(BUTTON_BACK):
            mode = LIST

    if mode == LIST:
        draw_list()
    elif mode == CONNECTING:
        try:
            saying = wifi.status()[1]
        except (KeyError, IndexError):
            saying = "Joining the network"
        draw_waiting("Connecting to Wi-Fi...", saying)
    elif mode == THINKING:
        draw_waiting("Thinking...", "%s, %.1fs" % (client.model, (badge.ticks - asked_at) / 1000))
    elif mode == ANSWER:
        draw_answer()
    else:
        draw_failed()


if problem:
    lines = wrap(problem, BODY_W, BODY_SIZE)

run(update)
