import hints
from badgeware import get_backlight, set_backlight

try:
    import secrets
except ImportError:
    secrets = None

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

SECRETS_FILE = "/secrets.py"

FIELDS = (
    ("WIFI_SSID", "WiFi Network", False),
    ("WIFI_PASSWORD", "WiFi Password", True),
    ("GITHUB_USERNAME", "GitHub Username", False),
    ("CONTACT_NAME", "Contact Name", False),
    ("CONTACT_LINKEDIN", "LinkedIn Profile", False),
)

PALETTE = [
    (88, 58, 247),
    (22, 143, 251),
    (15, 191, 62),
    (247, 54, 120),
]

BASE_STRENGTH = 0.22
MID_STRENGTH = 0.42

white = color.rgb(255, 255, 255)
black = color.rgb(0, 0, 0)
dim_white = color.rgb(255, 255, 255, 140)
faint_white = color.rgb(255, 255, 255, 60)

status_font = font.salty
caption_font = font.corset
value_font = font.ziplock
field_font = font.sins
title_font = font.ignore
key_font = font.yesterday

OS_NAME = "MonaOS 4.0"
STATUS_HEIGHT = 21
RIBBON_TOP = 198
TITLE_X = 8
TITLE_Y = 202
MARGIN = 4
WIDTH = 320

ROW_HEIGHT = 40
ROW_GAP = 3
ROW_PITCH = ROW_HEIGHT + ROW_GAP
VISIBLE_ROWS = 4

FIELD_TOP = STATUS_HEIGHT + 2
FIELD_HEIGHT = 30
FIELD_SCALE = 2

KEY_GAP = 3
KEY_HEIGHT = 25
KEY_TOP = FIELD_TOP + FIELD_HEIGHT + 6
KEY_UNIT = (WIDTH - MARGIN * 2 - KEY_GAP * 9) // 10

HINT_STYLE = hints.Style(white, dim_white, black)
HINT_SHAPE = (BUTTON_LEFT, BUTTON_SELECT)
HINT_RADIUS = 4

LETTER_ROWS = ("1234567890", "qwertyuiop", "asdfghjkl", "zxcvbnm")
SYMBOL_ROWS = ("!@#$%^&*()", "-_=+[]{}\\|", ";:'\",./?~", "<>`")

SHIFT_OFF = 0
SHIFT_ONCE = 1
SHIFT_LOCK = 2

SAVED_MS = 1500
LOCK_WIDTH = 10
LOCK_HEIGHT = 8
BACKLIGHT_STEP = 10
BAR_WIDTH = 160
BAR_HEIGHT = 8


def shade(rgb, strength):
    return color.rgb(*(round(channel * strength) for channel in rgb))


def load_values():
    return {key: str(getattr(secrets, key, "") or "") for key, _, _ in FIELDS}


def is_locked(key):
    return secrets is not None and secrets.locked(key)


def save_value(key, value):
    if secrets is not None:
        secrets.save({key: value})
        return
    with open(SECRETS_FILE, "a") as f:
        f.write(f"{key} = {value!r}\n")


def draw_lock(right, top, pen):
    left = right - LOCK_WIDTH
    screen.pen = pen
    screen.rectangle(left, top + 5, LOCK_WIDTH, LOCK_HEIGHT)
    screen.rectangle(left + 2, top, 2, 6)
    screen.rectangle(left + LOCK_WIDTH - 4, top, 2, 6)
    screen.rectangle(left + 2, top, LOCK_WIDTH - 4, 2)


def draw_battery(right, top):
    if badge.is_charging():
        level = (badge.ticks / 20) % 100
    else:
        level = badge.battery_level()
    width, height = 22, 11
    left = right - width - 2
    screen.pen = white
    screen.rectangle(left, top, width, height)
    screen.rectangle(left + width, top + 4, 2, 3)
    screen.pen = black
    screen.rectangle(left + 1, top + 1, width - 2, height - 2)
    screen.pen = white
    screen.rectangle(left + 2, top + 2, round((width - 4) * level / 100), height - 4)


def draw_status():
    screen.font = status_font
    screen.pen = white
    screen.text(OS_NAME, TITLE_X, 3)
    draw_battery(WIDTH - TITLE_X, 5)


def draw_ribbon(title):
    screen.font = title_font
    screen.pen = white
    screen.text(title.lower(), TITLE_X, TITLE_Y)


def draw_hint(label, lit, right):
    screen.font = caption_font
    label_width, _ = screen.measure_text(label)
    dots_width = hints.hint_width(HINT_SHAPE, HINT_RADIUS)
    left = right - label_width - 6 - dots_width
    hints.draw_hint(HINT_STYLE, HINT_SHAPE, lit, left + dots_width / 2, 219, HINT_RADIUS)
    screen.pen = dim_white
    screen.text(label, left + dots_width + 6, 213)
    return left - 12


def draw_tile(left, top, width, height, rgb, selected):
    if selected:
        screen.pen = white
        screen.rectangle(left, top, width, height)
        screen.pen = color.rgb(*rgb)
        screen.rectangle(left + 2, top + 2, width - 4, height - 4)
    else:
        screen.pen = shade(rgb, BASE_STRENGTH)
        screen.rectangle(left, top, width, height)


def fit_tail(text, width, scale):
    while text and screen.measure_text(text, font_size=scale)[0] > width:
        text = text[1:]
    return text


class SettingsList:
    BACKLIGHT_ROW = len(FIELDS)
    ROWS = len(FIELDS) + 1

    def __init__(self, values):
        self.values = values
        self.index = 0
        self.top_row = 0
        self.saved_at = None
        self.backlight = get_backlight()

    def edited(self, key, value):
        self.values[key] = value
        save_value(key, value)
        self.saved_at = badge.ticks

    def update(self):
        if badge.pressed(BUTTON_DOWN):
            self.index = (self.index + 1) % self.ROWS
        if badge.pressed(BUTTON_UP):
            self.index = (self.index - 1) % self.ROWS
        self.top_row = max(min(self.top_row, self.index), self.index - VISIBLE_ROWS + 1)
        if self.index == self.BACKLIGHT_ROW:
            step = (1 if badge.pressed(BUTTON_RIGHT) else 0) - (1 if badge.pressed(BUTTON_LEFT) else 0)
            if step:
                self.backlight = set_backlight(self.backlight + step * BACKLIGHT_STEP, save=True)
        if badge.pressed(BUTTON_BACK):
            reset()
        if badge.pressed(BUTTON_SELECT) and self.index < len(FIELDS):
            key, label, _ = FIELDS[self.index]
            if not is_locked(key):
                return Editor(self, key, label, self.values[key])
        return self

    def draw(self):
        for slot in range(VISIBLE_ROWS):
            row = self.top_row + slot
            if row >= self.ROWS:
                break
            top = FIELD_TOP + slot * ROW_PITCH
            rgb = PALETTE[row % len(PALETTE)]
            selected = row == self.index
            draw_tile(MARGIN, top, WIDTH - MARGIN * 2, ROW_HEIGHT, rgb, selected)

            if row == self.BACKLIGHT_ROW:
                self.draw_backlight(top, selected)
                continue

            key, label, secret = FIELDS[row]
            value = self.values[key]
            shown = "*" * len(value) if secret else value
            screen.font = caption_font
            screen.pen = white if selected else dim_white
            screen.text(label, MARGIN + 10, top + 2)
            screen.font = value_font
            screen.pen = white if value else faint_white
            screen.text(fit_tail(shown or "not set", WIDTH - 48, 1), MARGIN + 10, top + 16)
            if is_locked(key):
                draw_lock(WIDTH - MARGIN - 10, top + 14, white if selected else dim_white)

        self.draw_scrollbar()
        draw_ribbon("settings")
        if self.index == self.BACKLIGHT_ROW:
            draw_hint("adjust", (BUTTON_LEFT, BUTTON_RIGHT), WIDTH - TITLE_X)
            return
        key = FIELDS[self.index][0]
        if self.recently_saved():
            action = "saved!"
        elif is_locked(key):
            action = "locked"
        else:
            action = "edit"
        draw_hint(action, (BUTTON_SELECT,), WIDTH - TITLE_X)

    def draw_scrollbar(self):
        if self.ROWS <= VISIBLE_ROWS:
            return
        track_top = FIELD_TOP
        track_height = VISIBLE_ROWS * ROW_PITCH - ROW_GAP
        thumb_height = track_height * VISIBLE_ROWS // self.ROWS
        thumb_top = track_top + (track_height - thumb_height) * self.top_row // (self.ROWS - VISIBLE_ROWS)
        screen.pen = faint_white
        screen.rectangle(WIDTH - 2, track_top, 2, track_height)
        screen.pen = dim_white
        screen.rectangle(WIDTH - 2, thumb_top, 2, thumb_height)

    def draw_backlight(self, top, selected):
        screen.font = caption_font
        screen.pen = white if selected else dim_white
        screen.text("Backlight", MARGIN + 10, top + 2)
        bar_left = MARGIN + 10
        bar_top = top + 24
        screen.pen = faint_white
        screen.rectangle(bar_left, bar_top, BAR_WIDTH, BAR_HEIGHT)
        screen.pen = white
        screen.rectangle(bar_left, bar_top, round(BAR_WIDTH * self.backlight / 100), BAR_HEIGHT)
        screen.font = value_font
        screen.text(f"{self.backlight}%", bar_left + BAR_WIDTH + 10, top + 16)

    def recently_saved(self):
        return self.saved_at is not None and badge.ticks - self.saved_at < SAVED_MS


class Key:
    def __init__(self, label, action, units):
        self.label = label
        self.action = action
        self.units = units
        self.left = 0
        self.top = 0
        self.width = 0

    @property
    def centre(self):
        return self.left + self.width / 2


class Editor:
    def __init__(self, settings, key, label, value):
        self.settings = settings
        self.key = key
        self.label = label
        self.value = value
        self.shift = SHIFT_OFF
        self.symbols = False
        self.row = 1
        self.column = 0
        self.rows = []
        self.build()

    def build(self):
        source = SYMBOL_ROWS if self.symbols else LETTER_ROWS
        upper = self.shift != SHIFT_OFF and not self.symbols
        rows = []
        for index, characters in enumerate(source):
            keys = [Key(c.upper() if upper else c, c.upper() if upper else c, 1) for c in characters]
            if index == 3:
                if not self.symbols:
                    shift_label = ("shift", "Shift", "SHIFT")[self.shift]
                    keys.insert(0, Key(shift_label, "shift", 1.5))
                keys.append(Key("del", "delete", 1.5))
            rows.append(keys)
        rows.append([
            Key("abc" if self.symbols else "#+=", "symbols", 2),
            Key("space", " ", 5),
            Key("done", "done", 3),
        ])

        for index, keys in enumerate(rows):
            for key in keys:
                key.width = int(key.units * KEY_UNIT + (key.units - 1) * KEY_GAP)
            width = sum(key.width for key in keys) + KEY_GAP * (len(keys) - 1)
            x = (WIDTH - width) // 2
            for key in keys:
                key.left = x
                key.top = KEY_TOP + index * (KEY_HEIGHT + KEY_GAP)
                x += key.width + KEY_GAP

        self.rows = rows
        self.column = min(self.column, len(rows[self.row]) - 1)

    @property
    def selected(self):
        return self.rows[self.row][self.column]

    def move_row(self, step):
        centre = self.selected.centre
        self.row = (self.row + step) % len(self.rows)
        keys = self.rows[self.row]
        self.column = min(range(len(keys)), key=lambda index: abs(keys[index].centre - centre))

    def press(self, key):
        if key.action == "shift":
            self.shift = (self.shift + 1) % 3
            self.build()
        elif key.action == "symbols":
            self.symbols = not self.symbols
            self.build()
        elif key.action == "delete":
            self.value = self.value[:-1]
        elif key.action == "done":
            self.settings.edited(self.key, self.value)
            return self.settings
        else:
            self.value += key.action
            if self.shift == SHIFT_ONCE:
                self.shift = SHIFT_OFF
                self.build()
        return self

    def update(self):
        if badge.pressed(BUTTON_RIGHT):
            self.column = (self.column + 1) % len(self.rows[self.row])
        if badge.pressed(BUTTON_LEFT):
            self.column = (self.column - 1) % len(self.rows[self.row])
        if badge.pressed(BUTTON_DOWN):
            self.move_row(1)
        if badge.pressed(BUTTON_UP):
            self.move_row(-1)
        if badge.pressed(BUTTON_BACK):
            self.value = self.value[:-1]
        if badge.pressed(BUTTON_SELECT):
            return self.press(self.selected)
        return self

    def draw(self):
        screen.pen = shade(PALETTE[0], BASE_STRENGTH)
        screen.rectangle(MARGIN, FIELD_TOP, WIDTH - MARGIN * 2, FIELD_HEIGHT)

        screen.font = field_font
        shown = fit_tail(self.value, WIDTH - MARGIN * 2 - 24, FIELD_SCALE)
        screen.pen = white
        screen.text(shown, MARGIN + 8, FIELD_TOP + 3, FIELD_SCALE)
        if (badge.ticks // 500) % 2 == 0:
            cursor_x = MARGIN + 8 + screen.measure_text(shown, font_size=FIELD_SCALE)[0] + 2
            screen.rectangle(cursor_x, FIELD_TOP + 5, 2, FIELD_HEIGHT - 10)

        for row_index, keys in enumerate(self.rows):
            for column_index, key in enumerate(keys):
                selected = row_index == self.row and column_index == self.column
                rgb = PALETTE[row_index % len(PALETTE)]
                draw_tile(key.left, key.top, key.width, KEY_HEIGHT, rgb, selected)
                if not selected and key.action == "shift" and self.shift != SHIFT_OFF:
                    screen.pen = shade(rgb, MID_STRENGTH)
                    screen.rectangle(key.left, key.top, key.width, KEY_HEIGHT)
                screen.font = key_font
                width, _ = screen.measure_text(key.label)
                screen.pen = white
                screen.text(key.label, key.left + (key.width - width) // 2, key.top + 4)

        draw_ribbon(self.label)
        draw_hint("type", (BUTTON_SELECT,), WIDTH - TITLE_X)


screen_state = SettingsList(load_values())


def update():
    global screen_state
    screen_state = screen_state.update()
    screen.pen = black
    screen.clear()
    draw_status()
    screen_state.draw()


run(update)
