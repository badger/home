"""
Digital Rain: falling green code with your badge details decoding on top.

Controls:
* Select = Show the next detail now
* Up / Down = Faster / slower rain

Performance notes: the framebuffer is not cleared between frames. Each rain
step draws one translucent black rectangle to fade the trails and then only
the head glyph of each column, so the per-step cost is a few dozen small
text draws regardless of trail length. Rain steps run on a fixed timer and
frames in between return immediately. All buffers are allocated once.
"""

import os
import sys
import random

import missing_details

try:
    import secrets
except ImportError:
    secrets = None

APP_DIR = "/system/apps/digital_rain"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

previous_clear = badge.default_clear

badge.mode(HIRES | VSYNC)
badge.default_clear = None

# Settings shown in order; empty values are skipped.
DETAIL_KEYS = ("CONTACT_NAME", "CONTACT_TITLE", "CONTACT_COMPANY", "GITHUB_USERNAME")
NO_DETAILS = "Add your details in Settings"

GLYPHS = tuple("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ$+-*/=<>:;!?#%&@^~|")
GLYPH_FONT = font.nope

TITLE_FONT = missing_details.mona_sans()

BLACK = color.rgb(0, 0, 0)
FADE = color.rgb(0, 0, 0, 34)
BAND_FADE = color.rgb(0, 0, 0, 160)
HEAD = color.rgb(215, 255, 220)
TRAIL = color.rgb(30, 220, 70)
MUTATE = color.rgb(20, 130, 45)
TITLE = color.rgb(170, 255, 170)
TITLE_GLOW = color.rgb(0, 255, 70, 70)
TITLE_SCRAMBLE = color.rgb(40, 200, 80)

STEP_MS_OPTIONS = (35, 45, 55, 75, 100)
MUTATIONS_PER_STEP = 3
COLUMN_PITCH = 2  # Extra pixels between rain columns.
MIN_TRAIL = 6

TITLE_SIZE = 40
TITLE_MIN_SIZE = 18
TITLE_MARGIN = 14
LINE_GAP = 4
TITLE_CENTER = 0.4  # Vertical centre of the title block, as a share of the height.

DECODE_MS = 1400
HOLD_MS = 3200
DISSOLVE_MS = 700
GAP_MS = 1300

DECODING = 0
HOLDING = 1
DISSOLVING = 2
GAP = 3


def setting(key):
    return str(getattr(secrets, key, "") or "").strip()


def load_details():
    details = []
    for key in DETAIL_KEYS:
        value = setting(key)
        if value and key == "GITHUB_USERNAME":
            value = "@" + value.lstrip("@")
        if value:
            details.append(value)
    return details or [NO_DETAILS]


screen.font = GLYPH_FONT
# measure_text returns floats; the grid needs whole pixels.
CELL_W, CELL_H = (int(v) for v in screen.measure_text("W"))
CELL_W += COLUMN_PITCH
COLS = screen.width // CELL_W
ROWS = screen.height // CELL_H + 1
X_OFFSET = (screen.width - COLS * CELL_W + COLUMN_PITCH) // 2

# Head row per column. Negative values are a countdown before the drop starts.
head = [random.randint(-ROWS, ROWS - 1) for _ in range(COLS)]
# Each column moves once every `period` steps, giving varied speeds.
period = bytearray(random.randint(1, 3) for _ in range(COLS))
wait = bytearray(COLS)
# Rows behind the head where the trail is erased outright. Alpha fading alone
# never quite reaches black, so this stops faint residue building up.
trail = bytearray(random.randint(MIN_TRAIL, ROWS) for _ in range(COLS))

step_index = 2
last_step = badge.ticks


def reset_column(column):
    # Wait a random number of moves before the next drop enters the screen.
    head[column] = -random.randint(0, ROWS)
    period[column] = random.randint(1, 3)
    trail[column] = random.randint(MIN_TRAIL, ROWS)


def clear_cell(column, row):
    screen.pen = BLACK
    screen.rectangle(X_OFFSET + column * CELL_W, row * CELL_H, CELL_W, CELL_H)


def draw_glyph(column, row, pen):
    # Clear first so glyphs never pile up on top of each other in one cell.
    clear_cell(column, row)
    screen.pen = pen
    screen.text(random.choice(GLYPHS), X_OFFSET + column * CELL_W, row * CELL_H)


def step_rain():
    screen.pen = FADE
    screen.rectangle(0, 0, screen.width, screen.height)

    screen.font = GLYPH_FONT
    for column in range(COLS):
        if wait[column]:
            wait[column] -= 1
            continue
        wait[column] = period[column] - 1

        row = head[column]
        if 0 <= row < ROWS:
            # Repaint the old head as trail, then draw the new bright head.
            draw_glyph(column, row, TRAIL)
        row += 1
        tail = row - trail[column]
        if 0 <= tail < ROWS:
            clear_cell(column, tail)
        if tail >= ROWS:
            reset_column(column)
            continue
        head[column] = row
        if 0 <= row < ROWS:
            draw_glyph(column, row, HEAD)

    # Flip a few glyphs inside live trails so the code keeps changing.
    for _ in range(MUTATIONS_PER_STEP):
        column = random.randrange(COLS)
        row = head[column] - random.randint(1, trail[column] - 1)
        if 0 <= row < ROWS:
            draw_glyph(column, row, MUTATE)


class Title:
    def __init__(self):
        self.details = load_details()
        self.index = -1
        self.band = None
        self.next_detail(badge.ticks)

    def next_detail(self, now):
        if self.band:
            screen.pen = BLACK
            screen.rectangle(*self.band)
        self.index = (self.index + 1) % len(self.details)
        self.lines, self.size = layout(self.details[self.index])
        self.state = DECODING
        self.started = now

        # Work out every character's position and reveal time once per detail
        # so drawing never measures text or allocates layout data.
        screen.font = TITLE_FONT
        line_height = self.size + LINE_GAP
        block = line_height * len(self.lines) - LINE_GAP
        top = max(10, int(screen.height * TITLE_CENTER - block / 2))
        self.band = (0, top - 8, screen.width, block + 16)
        self.origins = []
        self.chars = []
        for line_index, line in enumerate(self.lines):
            width, _ = screen.measure_text(line, font_size=self.size)
            x = int(screen.width - width) // 2
            y = top + line_index * line_height
            self.origins.append((x, y))
            for i, char in enumerate(line):
                if char == " ":
                    continue
                offset = screen.measure_text(line[:i], font_size=self.size)[0] if i else 0
                reveal_at = int(DECODE_MS * (0.25 + 0.75 * random.random()))
                self.chars.append((char, x + offset, y, reveal_at))

    def update(self, now):
        elapsed = now - self.started
        limit = (DECODE_MS, HOLD_MS, DISSOLVE_MS, GAP_MS)[self.state]
        if elapsed < limit:
            return
        self.started = now
        if self.state == GAP:
            self.next_detail(now)
        else:
            self.state += 1

    def visibility(self, elapsed, reveal_at):
        """Returns 0 hidden, 1 scrambled or 2 resolved for one character."""
        if self.state == DECODING:
            if elapsed >= reveal_at:
                return 2
            return 1 if elapsed >= reveal_at // 3 else 0
        # Scale into the first three quarters so the last letters still have
        # time to scramble before the dissolve ends.
        scramble_ms = DISSOLVE_MS // 4
        out_at = reveal_at * (DISSOLVE_MS - scramble_ms) // DECODE_MS
        if elapsed < out_at:
            return 2
        return 1 if elapsed < out_at + scramble_ms else 0

    def draw(self, now):
        if self.state == GAP:
            if self.band:
                # Wipe the band once so no faded title residue is left behind.
                screen.pen = BLACK
                screen.rectangle(*self.band)
                self.band = None
            return

        # A stronger fade behind the text pushes the rain into the background.
        screen.pen = BAND_FADE
        screen.rectangle(*self.band)
        screen.font = TITLE_FONT

        if self.state == HOLDING:
            # Whole lines are much cheaper than one draw per character.
            for line, (x, y) in zip(self.lines, self.origins):
                screen.pen = TITLE_GLOW
                screen.text(line, x + 1, y + 1, self.size)
                screen.pen = TITLE
                screen.text(line, x, y, self.size)
            return

        elapsed = now - self.started
        for char, x, y, reveal_at in self.chars:
            shown = self.visibility(elapsed, reveal_at)
            if shown == 2:
                screen.pen = TITLE
                screen.text(char, x, y, self.size)
            elif shown == 1:
                screen.pen = TITLE_SCRAMBLE
                screen.text(random.choice(GLYPHS), x, y, self.size)


def layout(text):
    """Split multi-word text over two balanced lines at the largest size that fits."""
    screen.font = TITLE_FONT
    max_width = screen.width - TITLE_MARGIN * 2
    words = text.split()
    lines = [text]
    if len(words) > 1:
        best = None
        for split in range(1, len(words)):
            pair = [" ".join(words[:split]), " ".join(words[split:])]
            widest = max(screen.measure_text(part, font_size=TITLE_SIZE)[0] for part in pair)
            if best is None or widest < best[0]:
                best = (widest, pair)
        lines = best[1]
    widest = max(screen.measure_text(line, font_size=TITLE_SIZE)[0] for line in lines)
    size = min(TITLE_SIZE, TITLE_SIZE * max_width / widest)
    return lines, int(max(size, TITLE_MIN_SIZE))


title = Title()

screen.pen = BLACK
screen.rectangle(0, 0, screen.width, screen.height)


def update():
    global last_step, step_index

    if badge.pressed(BUTTON_UP):
        step_index = max(0, step_index - 1)
    if badge.pressed(BUTTON_DOWN):
        step_index = min(len(STEP_MS_OPTIONS) - 1, step_index + 1)
    if badge.pressed(BUTTON_SELECT):
        title.next_detail(badge.ticks)

    now = badge.ticks
    # Fixed-rate steps keep the work per second constant at any frame rate.
    if now - last_step < STEP_MS_OPTIONS[step_index]:
        return
    last_step = now

    title.update(now)
    step_rain()
    title.draw(now)


def on_exit():
    badge.default_clear = previous_clear


run(update)
