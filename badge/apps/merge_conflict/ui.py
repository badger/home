BLACK = color.rgb(0, 0, 0)
GRAY_1 = color.rgb(242, 245, 243)
GRAY_2 = color.rgb(228, 235, 230)
GRAY_3 = color.rgb(182, 191, 184)
GRAY_4 = color.rgb(144, 150, 146)
GRAY_5 = color.rgb(35, 41, 37)
GRAY_6 = color.rgb(16, 20, 17)
GREEN_2 = color.rgb(140, 242, 166)
GREEN_3 = color.rgb(95, 237, 131)
GREEN_4 = color.rgb(15, 191, 62)
GREEN_5 = color.rgb(8, 135, 43)

BACKGROUND = GRAY_6
PANEL = GRAY_5
TEXT = GRAY_2
DIM = GRAY_4
BRIGHT = GRAY_1
RIVAL = GRAY_3
ACCENT = GREEN_3
GO = GREEN_4

BODY = font.bacteria
TITLE = font.futile
HUGE = font.ignore

ASSET_DIR = __file__.rsplit("/", 1)[0]

STRIP_Y = 188
STRIP_CY = 214
HINT_X = 14
MONA_SCALE = 3
MONA_MARGIN = 0
MONA_LEFT = 238

CRT_SPACING = 3
CRT_DARKNESS = 70
GLITCH_MS = 350
GLITCH_AMOUNT = 8

UPRIGHT_ROW = (BUTTON_LEFT, BUTTON_RIGHT, BUTTON_SELECT)
DPAD = ((BUTTON_UP, 0, -1), (BUTTON_LEFT, -1, 0), (BUTTON_RIGHT, 1, 0), (BUTTON_DOWN, 0, 1))
DIRECTIONS = (BUTTON_UP, BUTTON_DOWN, BUTTON_LEFT, BUTTON_RIGHT)
PAIR = (BUTTON_SELECT, BUTTON_BACK)
PAIR_SPAN = 1
DPAD_GAP = 3


def flipped():
    return bool(badge.rotate_180())


def centred(text, y, typeface, pen, scale=1):
    screen.font = typeface
    screen.pen = pen
    w, _h = screen.measure_text(text)
    x = (screen.width - w * scale) / 2
    if scale == 1:
        screen.text(text, x, y)
        return
    at = vec2(x, y)
    screen.text(text, at, transform=mat3().translate(at).scale(scale, scale).translate(vec2(-x, -y)))


def text_at(text, x, y, typeface, pen):
    screen.font = typeface
    screen.pen = pen
    screen.text(text, x, y)
    return screen.measure_text(text)[0]


def clear(pen=None):
    screen.pen = BACKGROUND if pen is None else pen
    screen.clear()


def timer_bar(now, started, duration, y=12):
    remaining = max(0, duration - (now - started))
    screen.pen = PANEL
    screen.rectangle(16, y, screen.width - 32, 8)
    screen.pen = ACCENT
    screen.rectangle(16, y, int((screen.width - 32) * remaining / duration), 8)


def as_actions(value):
    if value is None:
        return set()
    if isinstance(value, (tuple, list, set)):
        return set(value)
    return {value}


class Control:
    def __init__(self, label, upright, upside_down=-1):
        self.label = label
        self.upright = as_actions(upright)
        self.upside_down = self.upright if upside_down == -1 else as_actions(upside_down)

    def actions(self, upside_down):
        return self.upside_down if upside_down else self.upright


TILT = "tilt"


def active_controls(controls, upside_down):
    return [control for control in controls if control.actions(upside_down)]


def actions_for(controls, upside_down):
    shape = set()
    for control in controls:
        shape |= control.actions(upside_down)
    return shape


def dot(x, y, radius, filled):
    centre = vec2(x, y)
    screen.pen = BRIGHT if filled else DIM
    screen.circle(centre, radius)
    if not filled:
        screen.pen = BACKGROUND
        screen.circle(centre, max(1, radius - 2))


def spacing_for(radius):
    return radius * 2 + 6


def pad_parts(shape):
    return any(action in shape for action in DIRECTIONS), any(action in shape for action in PAIR)


def has_vertical(shape):
    return BUTTON_UP in shape or BUTTON_DOWN in shape


def dpad_offset(radius):
    return (radius * 2 + DPAD_GAP) / 1.4142


def pad_width(dpad, pair, radius):
    spacing = spacing_for(radius)
    offset = dpad_offset(radius)
    if dpad and pair:
        return offset * 2 + spacing * (1 + PAIR_SPAN) + radius * 2
    if pair:
        return spacing * PAIR_SPAN + radius * 2
    return offset * 2 + radius * 2


def hint_width(shape, radius, upside_down=None):
    upside_down = flipped() if upside_down is None else upside_down
    spacing = spacing_for(radius)
    if upside_down:
        dpad, pair = pad_parts(shape)
        return pad_width(dpad or not pair, pair, radius)
    if has_vertical(shape):
        return spacing * 2 + radius * 2 + radius + 6 + radius * 2
    return spacing * 2 + radius * 2


def hint_height(shape, radius, upside_down=None):
    upside_down = flipped() if upside_down is None else upside_down
    spacing = spacing_for(radius)
    if not upside_down:
        return radius * 4 + 4 if has_vertical(shape) else radius * 2
    dpad, _pair = pad_parts(shape)
    return dpad_offset(radius) * 2 + radius * 2 if dpad else spacing * PAIR_SPAN + radius * 2


def draw_pair(left_x, cy, spacing, radius, lit):
    offset = spacing * PAIR_SPAN
    dot(left_x, cy + offset / 2, radius, BUTTON_SELECT in lit)
    dot(left_x + offset, cy - offset / 2, radius, BUTTON_BACK in lit)


def draw_dpad(cx, cy, radius, lit):
    offset = dpad_offset(radius)
    for action, dx, dy in DPAD:
        dot(cx + dx * offset, cy + dy * offset, radius, action in lit)


def arrow_marker(cx, cy, size, pointing_up, filled):
    screen.pen = BRIGHT if filled else DIM
    tip = cy - size if pointing_up else cy + size
    base = cy if pointing_up else cy
    screen.triangle(vec2(cx, tip), vec2(cx - size, base), vec2(cx + size, base))


def draw_hint(shape, lit, cx, cy, radius, upside_down=None):
    upside_down = flipped() if upside_down is None else upside_down
    spacing = spacing_for(radius)
    if not upside_down:
        row_x = cx
        if has_vertical(shape):
            row_x = cx - (radius + 6 + radius * 2) / 2
            marker_x = row_x + spacing + radius + 6 + radius
            arrow_marker(marker_x, cy - 2, radius, True, BUTTON_UP in lit)
            arrow_marker(marker_x, cy + 2, radius, False, BUTTON_DOWN in lit)
        for slot, action in enumerate(UPRIGHT_ROW):
            dot(row_x + (slot - 1) * spacing, cy, radius, action in lit)
        return
    dpad, pair = pad_parts(shape)
    if dpad and pair:
        offset = dpad_offset(radius)
        dpad_x = cx - pad_width(True, True, radius) / 2 + radius + offset
        draw_dpad(dpad_x, cy, radius, lit)
        draw_pair(dpad_x + offset + spacing, cy, spacing, radius, lit)
    elif pair:
        draw_pair(cx - spacing * PAIR_SPAN / 2, cy, spacing, radius, lit)
    else:
        draw_dpad(cx, cy, radius, lit)


def draw_tilt(cx, cy, size, lean=0.0):
    half = size / 2
    tilt = max(-0.6, min(0.6, lean)) * half
    screen.pen = BRIGHT
    screen.triangle(vec2(cx - half, cy + tilt), vec2(cx + half, cy - tilt), vec2(cx + half, cy - tilt + 5))
    screen.triangle(vec2(cx - half, cy + tilt), vec2(cx + half, cy - tilt + 5), vec2(cx - half, cy + tilt + 5))
    screen.pen = DIM
    screen.triangle(vec2(cx, cy + 8), vec2(cx - 8, cy + 18), vec2(cx + 8, cy + 18))


def draw_controls_hint(controls, now=0):
    if controls == TILT:
        draw_tilt(HINT_X + 24, STRIP_CY - 4, 44, 0.4 * ((now // 600) % 2 * 2 - 1))
        return
    upside_down = flipped()
    shape = actions_for(controls, upside_down)
    radius = 6
    cx = HINT_X + hint_width(shape, radius, upside_down) / 2
    draw_hint(shape, shape, cx, STRIP_CY, radius, upside_down)


def draw_primer(controls, top, now=0, tilt_text="tilt your badge"):
    if controls == TILT:
        draw_tilt(screen.width / 2, top + 20, 70, 0.4 * ((now // 600) % 2 * 2 - 1))
        centred(tilt_text, top + 44, BODY, TEXT)
        return
    upside_down = flipped()
    shape = actions_for(controls, upside_down)
    shown = active_controls(controls, upside_down)
    radius = 7
    slot = screen.width / max(1, len(shown))
    for index, control in enumerate(shown):
        cx = slot * index + slot / 2
        draw_hint(shape, control.actions(upside_down), cx, top + 20, radius, upside_down)
        if control.label:
            screen.font = BODY
            w, _h = screen.measure_text(control.label)
            text_at(control.label, cx - w / 2, top + 20 + hint_height(shape, radius, upside_down) / 2 + 6, BODY, TEXT)


class Mona:
    ANIMATIONS = {
        "default": 11,
        "eating": 12,
        "dance": 6,
        "heart": 14,
        "code": 4,
        "notify": 11,
        "dead": 7,
    }
    FRAME_MS = 100
    ONCE_MS = 1200

    def __init__(self):
        self.sheets = {}
        self.sizes = {}
        for name, frames in self.ANIMATIONS.items():
            sheet_image = image.load("%s/mona-%s.png" % (ASSET_DIR, name))
            self.sizes[name] = (sheet_image.width // frames, sheet_image.height)
            self.sheets[name] = sheet_image
        self.mood = "default"
        self.action = None
        self.action_until = 0
        self.action_started = 0

    def set_mood(self, mood):
        self.mood = mood

    def react(self, name, now, duration=ONCE_MS):
        self.action = name
        self.action_started = now
        self.action_until = now + duration

    def draw(self, now):
        if self.action is not None and now < self.action_until:
            name = self.action
            frame = (now - self.action_started) // self.FRAME_MS
        else:
            self.action = None
            name = self.mood
            frame = now // self.FRAME_MS
        frames = self.ANIMATIONS[name]
        w, h = self.sizes[name]
        scaled_w, scaled_h = w * MONA_SCALE, h * MONA_SCALE
        x = screen.width - scaled_w - MONA_MARGIN
        y = screen.height - scaled_h - MONA_MARGIN
        screen.blit(self.sheets[name], rect((frame % frames) * w, 0, w, h), rect(x, y, scaled_w, scaled_h))


class Effects:
    def __init__(self):
        self.glitch_until = 0

    def oops(self, now, duration=GLITCH_MS):
        self.glitch_until = max(self.glitch_until, now + duration)

    def apply(self, now):
        if now < self.glitch_until:
            screen.glitch(GLITCH_AMOUNT)
        screen.crt(CRT_SPACING, CRT_DARKNESS)


class Splash:
    COLUMNS = 10
    ROWS = 7
    PITCH = 32
    GAP = 9
    CORNER = 4
    BLANK_MS = 250
    FILL_MS = 600
    SMASH_MS = 160
    SHAKE_MS = 260
    SHAKE = 6
    WORDS = (("MERGE", 100), ("CONFLICT", 500))
    HOLD_MS = 1650
    FONT = font.manticore
    SCALE = 4
    SMASH_SCALE = 2.2
    LINE_GAP = 6
    LEVELS = (PANEL, GREEN_5, GREEN_4, GREEN_3, GREEN_2)

    def __init__(self, rng):
        self.started = None
        count = self.COLUMNS * self.ROWS
        self.levels = [rng.randrange(len(self.LEVELS)) for _ in range(count)]
        order = list(range(count))
        for index in range(count - 1, 0, -1):
            swap = rng.randrange(index + 1)
            order[index], order[swap] = order[swap], order[index]
        self.reveal = [0] * count
        self.position = [0] * count
        for position, cell in enumerate(order):
            self.reveal[cell] = self.BLANK_MS + self.FILL_MS * position // count
            self.position[cell] = position
        self.loaded = 0.0
        self.filled_at = None
        self.shake_x = [rng.randrange(self.SHAKE * 2 + 1) - self.SHAKE for _ in range(16)]
        self.shake_y = [rng.randrange(self.SHAKE * 2 + 1) - self.SHAKE for _ in range(16)]
        self.smashed = set()
        self.rendered = {}
        self.cells = None
        self.graph = None
        self.drawn = set()

    def start(self, now):
        self.started = now

    def update(self, now, loaded):
        self.loaded = loaded
        if self.filled_at is None and loaded >= 1.0 and now - self.started >= self.BLANK_MS + self.FILL_MS:
            self.filled_at = now

    def word_elapsed(self, now):
        return None if self.filled_at is None else now - self.filled_at

    def done(self, now):
        since = self.word_elapsed(now)
        return since is not None and since >= self.HOLD_MS

    def smashes(self, now):
        since = self.word_elapsed(now)
        if since is None:
            return []
        fresh = [word for word, at in self.WORDS if since >= at + self.SMASH_MS and word not in self.smashed]
        self.smashed.update(fresh)
        return fresh

    def shake(self, since):
        if since is None:
            return 0, 0
        for index, (_word, at) in enumerate(self.WORDS):
            since_smash = since - at - self.SMASH_MS
            if 0 <= since_smash < self.SHAKE_MS:
                strength = 1.0 - since_smash / self.SHAKE_MS
                frame = (since_smash // 40 + index * 5) % len(self.shake_x)
                return int(self.shake_x[frame] * strength), int(self.shake_y[frame] * strength)
        return 0, 0

    def cell_images(self):
        if self.cells is None:
            size = self.PITCH - self.GAP
            self.cells = []
            for pen in self.LEVELS:
                cell = image(size, size)
                cell.antialias = image.X4
                cell.pen = color.rgb(0, 0, 0, 0)
                cell.clear()
                cell.pen = pen
                cell.shape(shape.rounded_rectangle(0, 0, size, size, self.CORNER, self.CORNER, self.CORNER, self.CORNER))
                self.cells.append(cell)
        return self.cells

    def draw_graph(self, elapsed, dx, dy):
        cells = self.cell_images()
        if self.graph is None:
            self.graph = image(screen.width, screen.height)
            self.graph.pen = BACKGROUND
            self.graph.clear()
        pitch = self.PITCH
        left = (screen.width - pitch * self.COLUMNS + self.GAP) // 2
        top = (screen.height - pitch * self.ROWS + self.GAP) // 2
        visible = int(self.loaded * len(self.levels))
        for index, level in enumerate(self.levels):
            if index in self.drawn or elapsed < self.reveal[index] or self.position[index] >= visible:
                continue
            self.drawn.add(index)
            column = index % self.COLUMNS
            row = index // self.COLUMNS
            self.graph.blit(cells[level], vec2(left + column * pitch, top + row * pitch))
        screen.blit(self.graph, vec2(dx, dy))

    def render_word(self, word):
        screen.font = self.FONT
        w, h = screen.measure_text(word)
        w, h = int(w) + 2, int(h) + 2
        target = image(w, h)
        target.antialias = image.OFF
        target.pen = color.rgb(0, 0, 0, 0)
        target.clear()
        target.font = self.FONT
        target.pen = BACKGROUND
        for ox in (0, 1, 2):
            for oy in (0, 1, 2):
                target.text(word, ox, oy)
        target.pen = BRIGHT
        target.text(word, 1, 1)
        return target

    def draw_word(self, word, cy, scale, dx, dy):
        rendered = self.rendered.get(word)
        if rendered is None:
            rendered = self.rendered[word] = self.render_word(word)
        w, h = rendered.width, rendered.height
        scaled_w, scaled_h = int(w * scale), int(h * scale)
        x = int(screen.width / 2 - scaled_w / 2) + dx
        y = int(cy - scaled_h / 2) + dy
        screen.blit(rendered, rect(0, 0, w, h), rect(x, y, scaled_w, scaled_h))

    def draw(self, now):
        elapsed = now - self.started
        since = self.word_elapsed(now)
        clear()
        dx, dy = self.shake(since)
        self.draw_graph(elapsed, dx, dy)
        if since is None:
            return
        screen.font = self.FONT
        _w, h = screen.measure_text("MERGE")
        line = h * self.SCALE + self.LINE_GAP
        top = screen.height / 2 - line / 2
        for index, (word, at) in enumerate(self.WORDS):
            since_word = since - at
            if since_word < 0:
                continue
            progress = min(1.0, since_word / self.SMASH_MS)
            scale = self.SCALE * (1.0 + (self.SMASH_SCALE - 1.0) * (1.0 - progress) ** 2)
            self.draw_word(word, top + index * line, scale, dx, dy)
