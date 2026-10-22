import math
import struct

import ui
from ui import ACCENT, BACKGROUND, BODY, BRIGHT, DIM, GO, HUGE, PANEL, RIVAL, TEXT, TILT, TITLE, Control, centred

HOST_WINS = 0
GUEST_WINS = 1
TIE = 2

NO_SCORE = 65535
IMU_GRAVITY = 16384.0

CONTENT_BOTTOM = ui.STRIP_Y - 4

# Thanks to nikoichu for the awesome CC0 icon collection - https://nikoichu.itch.io/pixel-icons - <3
ICON_FAMILIES = ("emoji", "cosmetics", "food", "tools_crafting", "travel", "weather", "hats")
FOODS = ")*+-/279:;<>IJK"
ODD_CATEGORIES = (
    ("emoji", "\x21\x24\x26\x2a\x2d\x2e"),
    ("food", "\x29\x32\x37\x39\x3b\x3e"),
    ("food", "\x21\x22\x23\x25\x2e\x34"),
    ("travel", "\xa7\xa8\xab\xae\xaf\x76"),
    ("cosmetics", "\x21\x23\x2c\x37\x3b\x3e"),
    ("weather", "\x26\x2a\x30\x34\x39\x3a"),
    ("hats", "\x28\x2c\x45\x4a\x4f\x50"),
    ("tools_crafting", "\x2f\x38\x42\x57\x5a\x21"),
)
ICON_W = 14
ICON_H = 16
ICON_FILL = BRIGHT
ICON_OUTLINE = BACKGROUND
ICON_TILE = PANEL
ICON_SELECT = ACCENT

DIRECTIONS = (BUTTON_UP, BUTTON_DOWN, BUTTON_LEFT, BUTTON_RIGHT)

icon_fonts = None


class Rng:
    def __init__(self, seed):
        self.state = (seed & 0xFFFFFFFF) or 1

    def next(self):
        self.state = (self.state * 1103515245 + 12345) & 0x7FFFFFFF
        return self.state

    def randrange(self, limit):
        return self.next() % limit

    def uniform(self, low, high):
        return low + (high - low) * (self.next() / 0x7FFFFFFF)


def load_icons():
    global icon_fonts
    if icon_fonts is None:
        icon_fonts = {}
        for family in ICON_FAMILIES:
            for name in (family, family + "_outline"):
                icon_fonts[name] = font.load(name)
    return icon_fonts


def draw_icon(family, char, x, y, scale, fill=ICON_FILL):
    fonts = load_icons()
    at = vec2(x, y)
    transform = mat3().translate(at).scale(scale, scale).translate(vec2(-x, -y))
    screen.font = fonts[family]
    screen.pen = fill
    screen.text(char, at, transform=transform)
    screen.font = fonts[family + "_outline"]
    screen.pen = ICON_OUTLINE
    screen.text(char, at, transform=transform)


def draw_icon_tile(family, char, x, y, w, h, scale, selected=False, fill=ICON_FILL, tile=ICON_TILE):
    if selected:
        screen.pen = ICON_SELECT
        screen.rectangle(x - 3, y - 3, w + 6, h + 6)
    screen.pen = tile
    screen.rectangle(x, y, w, h)
    draw_icon(family, char, x + (w - ICON_W * scale) // 2, y + (h - ICON_H * scale) // 2, scale, fill)


REVEAL_TILE = 32
REVEAL_GAP = 10
REVEAL_RING = 3
REVEAL_SCALE = 2
NO_PICK = 255


def pick_of(detail):
    return detail[0] if detail else NO_PICK


def draw_legend(y, has_rival):
    labels = (("you", BRIGHT), ("them", RIVAL)) if has_rival else (("you", BRIGHT),)
    screen.font = BODY
    widths = [screen.measure_text(label)[0] for label, _pen in labels]
    x = (screen.width - sum(widths) - 16 * (len(labels) - 1)) / 2
    for (label, pen), width in zip(labels, widths):
        ui.text_at(label, x, y, BODY, pen)
        x += width + 16


def draw_grid_reveal(tiles, columns, answer, mine, theirs, top):
    rows = len(tiles) // columns
    pitch = REVEAL_TILE + REVEAL_GAP
    left = (screen.width - (pitch * columns - REVEAL_GAP)) // 2
    mine_pick = pick_of(mine)
    their_pick = pick_of(theirs) if theirs is not None else NO_PICK
    for index, (family, char) in enumerate(tiles):
        x = left + (index % columns) * pitch
        y = top + (index // columns) * pitch
        ring = REVEAL_RING
        if index == their_pick:
            screen.pen = RIVAL
            screen.rectangle(x - ring * 2, y - ring * 2, REVEAL_TILE + ring * 4, REVEAL_TILE + ring * 4)
            screen.pen = BACKGROUND
            screen.rectangle(x - ring, y - ring, REVEAL_TILE + ring * 2, REVEAL_TILE + ring * 2)
        if index == mine_pick:
            screen.pen = BRIGHT
            screen.rectangle(x - ring, y - ring, REVEAL_TILE + ring * 2, REVEAL_TILE + ring * 2)
        draw_icon_tile(family, char, x, y, REVEAL_TILE, REVEAL_TILE, REVEAL_SCALE, tile=ACCENT if index == answer else ICON_TILE)
    draw_legend(top + rows * pitch + 4, theirs is not None)


def move_cursor(cursor, columns, count, _upside_down):
    rows = count // columns
    column, row = cursor % columns, cursor // columns
    if badge.pressed(BUTTON_LEFT):
        column = max(0, column - 1)
    if badge.pressed(BUTTON_RIGHT):
        column = min(columns - 1, column + 1)
    if badge.pressed(BUTTON_UP):
        row = max(0, row - 1)
    if badge.pressed(BUTTON_DOWN):
        row = min(rows - 1, row + 1)
    return row * columns + column


def read_lean(level_x, level_y, upside_down):
    reading = badge.imu()
    lean_x = reading[0] / IMU_GRAVITY - level_x
    lean_y = reading[1] / IMU_GRAVITY - level_y
    if upside_down:
        return -lean_x, -lean_y
    return lean_x, lean_y


def compare_lower(host, guest):
    if host == guest:
        return TIE
    return HOST_WINS if host < guest else GUEST_WINS


def compare_higher(host, guest):
    if host == guest:
        return TIE
    return HOST_WINS if host > guest else GUEST_WINS


GRID_CONTROLS = (
    Control("move", DIRECTIONS),
    Control("pick", BUTTON_SELECT),
)

CHOICE_CONTROLS = (
    Control("", BUTTON_LEFT, BUTTON_LEFT),
    Control("", BUTTON_RIGHT, BUTTON_UP),
    Control("", BUTTON_SELECT, BUTTON_RIGHT),
)


class Microgame:
    NAME = ""
    HINT = ""
    CONTROLS = ()
    TILT_TEXT = "tilt your badge"
    SHOW_HINT = True
    HOLD_MS = 1000
    REVEAL = False

    def __init__(self, seed, me, rival):
        self.rng = Rng(seed)
        self.me = me
        self.rival = rival
        self.done = False
        self.score = NO_SCORE
        self.rival_live = None
        self.oops_pending = False
        self.upside_down = ui.flipped()

    def start(self, now):
        self.started = now
        self.upside_down = ui.flipped()

    def actions(self, index):
        return self.CONTROLS[index].actions(self.upside_down)

    def pressed(self, index):
        return any(badge.pressed(action) for action in self.actions(index))

    def held(self, index):
        return any(badge.held(action) for action in self.actions(index))

    def shape(self):
        return ui.actions_for(self.CONTROLS, self.upside_down)

    def oops(self):
        self.oops_pending = True

    def hides_mona(self):
        return False

    def detail(self):
        return b""

    def draw_reveal(self, mine, theirs, top):
        pass

    def finish(self, score):
        self.done = True
        self.score = min(NO_SCORE - 1, max(0, int(score)))

    @staticmethod
    def compare(host, guest):
        return compare_lower(host, guest)

    def describe(self, score):
        return "%d" % score

    def draw_choices(self, labels, lit, top=44, box_w=80, box_h=80, pitch=100, draw_label=None, hint_gap=(20, 32)):
        left = (screen.width - (pitch * 2 + box_w)) // 2
        shape = self.shape()
        for index in range(3):
            x = left + index * pitch
            screen.pen = ACCENT if index == lit else PANEL
            screen.rectangle(x, top, box_w, box_h)
            if draw_label is not None:
                draw_label(index, x, top, box_w, box_h)
            else:
                screen.font = HUGE
                w, h = screen.measure_text(labels[index])
                screen.pen = BACKGROUND if index == lit else BRIGHT
                screen.text(labels[index], x + (box_w - w) / 2, top + (box_h - h) / 2)
            ui.draw_hint(shape, self.actions(index), x + box_w // 2, top + box_h + hint_gap[1 if self.upside_down else 0], 6, self.upside_down)


FADE = color.rgb(35, 41, 37, 190)
LIGHT_RED = "\xa3"
LIGHT_GREEN = "\xa2"
LAMP_X = 7.75
LAMP_Y = (2.75, 7.9, 13.0)
LAMP_RADIUS = 1.7


def draw_traffic_light(x, y, scale, green):
    draw_icon("travel", LIGHT_GREEN if green else LIGHT_RED, x, y, scale)
    if green:
        screen.pen = GO
        screen.circle(vec2(x + LAMP_X * scale, y + LAMP_Y[2] * scale), LAMP_RADIUS * scale)


class QuickDraw(Microgame):
    NAME = "QUICK DRAW"
    HINT = "go on green"
    CONTROLS = (Control("go", BUTTON_SELECT),)
    TIMEOUT_MS = 1500
    FOUL = 9000
    REVEAL_MS = 900
    FLASH_MS = 140
    HOLD_MS = 300
    CAR = "\xab"
    LIGHT_SCALE = 4
    LIGHT_X = 132
    LIGHT_Y = 14
    ROAD_Y = 124
    ROAD_H = 46
    CAR_SCALE = 3
    CAR_X = 20
    LINE_X = 70
    LAUNCH = 900.0
    LURCH = 34

    def start(self, now):
        super().start(now)
        load_icons()
        self.go_at = now + int(self.rng.uniform(1500, 4000))
        self.pressed_at = None
        self.result = None

    def update(self, now):
        if self.pressed_at is not None:
            if now - self.pressed_at >= self.REVEAL_MS:
                self.finish(self.result)
            return
        if self.pressed(0):
            self.pressed_at = now
            if now < self.go_at:
                self.oops()
                self.result = self.FOUL
            else:
                self.result = now - self.go_at
        elif now >= self.go_at + self.TIMEOUT_MS:
            self.pressed_at = now
            self.result = self.TIMEOUT_MS

    def lights(self, now):
        return 0.6 if now >= self.go_at and not self.done else 0.0

    def car_x(self, now):
        if self.pressed_at is None:
            return self.CAR_X
        seconds = (now - self.pressed_at) / 1000
        if self.result == self.FOUL:
            return self.CAR_X + min(1.0, seconds * 6) * self.LURCH
        if self.result >= self.TIMEOUT_MS:
            return self.CAR_X
        return self.CAR_X + self.LAUNCH * seconds * seconds

    def draw_road(self):
        screen.pen = PANEL
        screen.rectangle(0, self.ROAD_Y, screen.width, self.ROAD_H)
        screen.pen = BACKGROUND
        for x in range(4, screen.width, 20):
            screen.rectangle(x, self.ROAD_Y + self.ROAD_H - 7, 10, 3)
        screen.pen = BRIGHT
        screen.rectangle(self.LINE_X, self.ROAD_Y, 3, self.ROAD_H)

    def draw(self, now):
        green = now >= self.go_at and self.result != self.FOUL
        flashing = green and now - self.go_at < self.FLASH_MS
        ui.clear(GO if flashing else BACKGROUND)
        self.draw_road()
        draw_traffic_light(self.LIGHT_X, self.LIGHT_Y, self.LIGHT_SCALE, green)
        idle = 0 if green or self.pressed_at is not None else (now // 60) % 2
        car_y = self.ROAD_Y + self.ROAD_H - ICON_H * self.CAR_SCALE - 6 - idle
        draw_icon("travel", self.CAR, int(self.car_x(now)), car_y, self.CAR_SCALE)
        if self.result == self.FOUL:
            centred("jumped the light!", 90, TITLE, BRIGHT)
        elif self.result is not None and self.result < self.TIMEOUT_MS:
            centred("%d ms" % self.result, 90, TITLE, ACCENT)
        elif self.result is not None:
            centred("too slow", 90, TITLE, DIM)
        elif green:
            centred("GO!", 90, TITLE, BACKGROUND if flashing else ACCENT)
        else:
            centred("wait for green...", 90, BODY, DIM)

    def describe(self, score):
        return "too early" if score >= self.FOUL else "%d ms" % score


VEHICLE_SETS = (
    ("road", "\xab\xa9\xb0"),
    ("water", "\x6d\x72\x6f\x76"),
)


class MashRace(Microgame):
    NAME = "MASH"
    HINT = "mash for 5 seconds"
    CONTROLS = (Control("mash", BUTTON_SELECT),)
    DURATION_MS = 5000
    TRACK_PRESSES = 30
    START_X = 16
    FINISH_X = 292
    LANE_H = 44
    LANE_Y = (40, 108)
    SCALE = 2
    DASH = 10

    def start(self, now):
        super().start(now)
        load_icons()
        self.count = 0
        kind, vehicles = VEHICLE_SETS[self.rng.randrange(len(VEHICLE_SETS))]
        self.water = kind == "water"
        first = self.rng.randrange(len(vehicles))
        second = (first + 1 + self.rng.randrange(len(vehicles) - 1)) % len(vehicles)
        low, high = vehicles[first], vehicles[second]
        self.mine, self.theirs = (low, high) if self.me <= self.rival else (high, low)

    def update(self, now):
        if self.pressed(0):
            self.count += 1
        if now - self.started >= self.DURATION_MS:
            self.finish(self.count)

    def live(self):
        return self.count

    def draw_lane(self, y, vehicle, count, label, pen):
        screen.pen = PANEL
        screen.rectangle(0, y, screen.width, self.LANE_H)
        screen.pen = BACKGROUND
        if self.water:
            for x in range(4, screen.width, self.DASH * 2):
                screen.rectangle(x, y + self.LANE_H - 8, self.DASH, 2)
                screen.rectangle(x + self.DASH, y + self.LANE_H - 5, self.DASH, 2)
        else:
            for x in range(4, screen.width, self.DASH * 2):
                screen.rectangle(x, y + self.LANE_H - 6, self.DASH, 3)
        vehicle_w = ICON_W * self.SCALE
        progress = 0.0 if count is None else min(1.0, count / self.TRACK_PRESSES)
        x = self.START_X + progress * (self.FINISH_X - self.START_X - vehicle_w)
        draw_icon("travel", vehicle, int(x), y + (self.LANE_H - ICON_H * self.SCALE) // 2 - 2, self.SCALE, pen)
        text = "%s %s" % (label, "-" if count is None else count)
        ui.text_at(text, self.START_X, y + self.LANE_H + 3, BODY, pen)

    def draw_finish(self):
        top = self.LANE_Y[0]
        bottom = self.LANE_Y[1] + self.LANE_H
        square = 4
        for row, y in enumerate(range(top, bottom, square)):
            for column in range(2):
                screen.pen = BRIGHT if (row + column) % 2 else BACKGROUND
                screen.rectangle(self.FINISH_X + column * square, y, square, min(square, bottom - y))

    def draw(self, now):
        ui.clear()
        ui.timer_bar(now, self.started, self.DURATION_MS)
        self.draw_lane(self.LANE_Y[0], self.mine, self.count, "you", BRIGHT)
        self.draw_lane(self.LANE_Y[1], self.theirs, self.rival_live, "them", RIVAL)
        self.draw_finish()

    @staticmethod
    def compare(host, guest):
        return compare_higher(host, guest)

    def describe(self, score):
        return "%d presses" % score


BLACK_HOLE = ui.BLACK


class TiltHole(Microgame):
    NAME = "TILT"
    HINT = "roll the ball into the hole"
    CONTROLS = TILT
    TIMEOUT_MS = 9000
    ACCEL = 900.0
    FRICTION = 1.5
    BALL = 9
    HOLE = 14
    PULL_RADIUS = 36
    PULL = 500.0
    FIELD_TOP = 24
    START_INSET = 36
    HOLE_INSET = 40
    HOLE_SPREAD = 50
    WALL_W = 12
    GAP = 44
    GAP_MARGIN = 0
    BOUNCE = 0.5
    SUBSTEPS = 2

    def start(self, now):
        super().start(now)
        middle = (self.FIELD_TOP + CONTENT_BOTTOM) / 2
        left_to_right = self.rng.randrange(2) == 0
        self.x = self.START_INSET if left_to_right else screen.width - self.START_INSET
        self.y = middle
        self.vx = 0.0
        self.vy = 0.0
        self.hx = screen.width - self.HOLE_INSET if left_to_right else self.HOLE_INSET
        self.hy = middle + self.rng.uniform(-self.HOLE_SPREAD, self.HOLE_SPREAD)
        gap_top = self.FIELD_TOP + self.GAP_MARGIN if self.rng.randrange(2) else CONTENT_BOTTOM - self.GAP_MARGIN - self.GAP
        wall_x = screen.width // 2 - self.WALL_W // 2
        self.walls = [
            (wall_x, self.FIELD_TOP, self.WALL_W, gap_top - self.FIELD_TOP),
            (wall_x, gap_top + self.GAP, self.WALL_W, CONTENT_BOTTOM - gap_top - self.GAP),
        ]
        self.walls = [wall for wall in self.walls if wall[3] > 0]
        reading = badge.imu()
        self.level_x = reading[0] / IMU_GRAVITY
        self.level_y = reading[1] / IMU_GRAVITY
        self.last = now

    def push_out(self, wall):
        wx, wy, ww, wh = wall
        nearest_x = max(wx, min(self.x, wx + ww))
        nearest_y = max(wy, min(self.y, wy + wh))
        dx = self.x - nearest_x
        dy = self.y - nearest_y
        distance_squared = dx * dx + dy * dy
        if distance_squared >= self.BALL * self.BALL:
            return
        if distance_squared == 0:
            if abs(self.x - (wx + ww / 2)) * wh > abs(self.y - (wy + wh / 2)) * ww:
                dx, dy = (1.0 if self.x > wx + ww / 2 else -1.0), 0.0
            else:
                dx, dy = 0.0, (1.0 if self.y > wy + wh / 2 else -1.0)
            distance = 0.0
            nearest_x, nearest_y = self.x, self.y
        else:
            distance = math.sqrt(distance_squared)
            dx, dy = dx / distance, dy / distance
        self.x = nearest_x + dx * self.BALL if distance else self.x + dx * self.BALL
        self.y = nearest_y + dy * self.BALL if distance else self.y + dy * self.BALL
        along = self.vx * dx + self.vy * dy
        if along < 0:
            self.vx -= (1 + self.BOUNCE) * along * dx
            self.vy -= (1 + self.BOUNCE) * along * dy

    def update(self, now):
        seconds = min(0.05, (now - self.last) / 1000)
        self.last = now
        lean_x, lean_y = read_lean(self.level_x, self.level_y, self.upside_down)
        self.vx += lean_x * self.ACCEL * seconds
        self.vy += lean_y * self.ACCEL * seconds
        to_x = self.hx - self.x
        to_y = self.hy - self.y
        distance = math.sqrt(to_x * to_x + to_y * to_y)
        if 0 < distance < self.PULL_RADIUS:
            pull = self.PULL * (1.0 - distance / self.PULL_RADIUS) * seconds / distance
            self.vx += to_x * pull
            self.vy += to_y * pull
        drag = max(0.0, 1.0 - self.FRICTION * seconds)
        self.vx *= drag
        self.vy *= drag
        step = seconds / self.SUBSTEPS
        for _ in range(self.SUBSTEPS):
            from_x, from_y = self.x, self.y
            self.x += self.vx * step
            self.y += self.vy * step
            if self.x < self.BALL or self.x > screen.width - self.BALL:
                self.vx = -self.vx * self.BOUNCE
                self.x = min(screen.width - self.BALL, max(self.BALL, self.x))
            if self.y < self.BALL + self.FIELD_TOP or self.y > CONTENT_BOTTOM - self.BALL:
                self.vy = -self.vy * self.BOUNCE
                self.y = min(CONTENT_BOTTOM - self.BALL, max(self.BALL + self.FIELD_TOP, self.y))
            for wall in self.walls:
                self.push_out(wall)
            if self.passes_hole(from_x, from_y, self.x, self.y):
                self.x, self.y = self.hx, self.hy
                self.finish(now - self.started)
                return
        if now - self.started >= self.TIMEOUT_MS:
            self.finish(self.TIMEOUT_MS)

    def passes_hole(self, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        length_squared = dx * dx + dy * dy
        along = 0.0 if length_squared == 0 else max(0.0, min(1.0, ((self.hx - x1) * dx + (self.hy - y1) * dy) / length_squared))
        nearest_x = x1 + dx * along - self.hx
        nearest_y = y1 + dy * along - self.hy
        return nearest_x * nearest_x + nearest_y * nearest_y < (self.HOLE - 3) ** 2

    def draw(self, now):
        ui.clear()
        ui.timer_bar(now, self.started, self.TIMEOUT_MS)
        screen.pen = DIM
        for wx, wy, ww, wh in self.walls:
            screen.rectangle(wx, wy, ww, wh)
        screen.pen = ACCENT
        screen.circle(vec2(self.hx, self.hy), self.HOLE + 4)
        screen.pen = BLACK_HOLE
        screen.circle(vec2(self.hx, self.hy), self.HOLE)
        screen.pen = BRIGHT
        screen.circle(vec2(self.x, self.y), self.BALL)

    def describe(self, score):
        return "missed" if score >= self.TIMEOUT_MS else "%.1f s" % (score / 1000)


class FindFood(Microgame):
    NAME = "FIND THE FOOD"
    HINT = "spot the dish shown"
    CONTROLS = GRID_CONTROLS
    TIMEOUT_MS = 8000
    PENALTY_MS = 1500
    TILE = 54
    GAP = 4
    SCALE = 3
    TARGET_SCALE = 4

    def start(self, now):
        super().start(now)
        load_icons()
        pool = list(FOODS)
        picks = []
        while len(picks) < 9:
            picks.append(pool.pop(self.rng.randrange(len(pool))))
        self.tiles = picks
        self.target = self.rng.randrange(9)
        self.food = picks[self.target]
        self.cursor = 4
        self.penalty = 0
        self.flash_until = 0

    def update(self, now):
        self.cursor = move_cursor(self.cursor, 3, 9, self.upside_down)
        if self.pressed(1):
            if self.cursor == self.target:
                self.finish(now - self.started + self.penalty)
                return
            self.penalty += self.PENALTY_MS
            self.flash_until = now + 300
            self.oops()
        if now - self.started + self.penalty >= self.TIMEOUT_MS:
            self.finish(self.TIMEOUT_MS)

    def draw(self, now):
        ui.clear(PANEL if now < self.flash_until else BACKGROUND)
        span = 3 * self.TILE + 2 * self.GAP
        left = screen.width - span - 10
        top = (CONTENT_BOTTOM - span) // 2 + 2
        ui.text_at("find", 14, top, BODY, DIM)
        draw_icon_tile("food", self.food, 14, top + 26, ICON_W * self.TARGET_SCALE + 16, ICON_H * self.TARGET_SCALE + 12, self.TARGET_SCALE)
        for index, food in enumerate(self.tiles):
            x = left + (index % 3) * (self.TILE + self.GAP)
            y = top + (index // 3) * (self.TILE + self.GAP)
            draw_icon_tile("food", food, x, y, self.TILE, self.TILE, self.SCALE, index == self.cursor)

    REVEAL = True

    def detail(self):
        return bytes((self.cursor,))

    def draw_reveal(self, mine, theirs, top):
        draw_grid_reveal([("food", food) for food in self.tiles], 3, self.target, mine, theirs, top)

    def describe(self, score):
        return "missed" if score >= self.TIMEOUT_MS else "%.1f s" % (score / 1000)


class RockPaperScissors(Microgame):
    NAME = "ROCK PAPER SCISSORS"
    HINT = "pick before zero"
    CONTROLS = (
        Control("rock", BUTTON_LEFT, BUTTON_LEFT),
        Control("paper", BUTTON_RIGHT, BUTTON_UP),
        Control("scissors", BUTTON_SELECT, BUTTON_RIGHT),
    )
    SHOW_HINT = False
    COUNT_MS = 2400
    CHOICES = ("rock", "paper", "scissors")
    ICONS = (("emoji", "0"), ("emoji", "6"), ("cosmetics", ">"))
    NONE = 3
    SCALE = 4

    def start(self, now):
        super().start(now)
        self.choice = self.NONE
        load_icons()

    def update(self, now):
        for choice in range(3):
            if self.pressed(choice):
                self.choice = choice
        if now - self.started >= self.COUNT_MS:
            self.finish(self.choice)

    def draw_label(self, index, x, top, box_w, box_h):
        family, char = self.ICONS[index]
        draw_icon_tile(family, char, x, top, box_w, box_h, self.SCALE, tile=ACCENT if index == self.choice else ICON_TILE)

    def draw(self, now):
        ui.clear()
        step = self.COUNT_MS // 3
        remaining = max(0, self.COUNT_MS - (now - self.started))
        centred("%d" % max(1, (remaining + step - 1) // step), 8, HUGE, ACCENT)
        self.draw_choices(None, self.choice, draw_label=self.draw_label)

    @staticmethod
    def compare(host, guest):
        none = RockPaperScissors.NONE
        if host == guest:
            return TIE
        if guest == none:
            return HOST_WINS
        if host == none:
            return GUEST_WINS
        return HOST_WINS if (host - guest) % 3 == 1 else GUEST_WINS

    REVEAL = True
    REVEAL_BOX = 76

    def detail(self):
        return bytes((self.choice,))

    def draw_pick(self, pick, x, y, label, pen, winner):
        box = self.REVEAL_BOX
        if pick < self.NONE:
            family, char = self.ICONS[pick]
            draw_icon_tile(family, char, x, y, box, box, self.SCALE, winner)
        else:
            if winner:
                screen.pen = ACCENT
                screen.rectangle(x - 3, y - 3, box + 6, box + 6)
            screen.pen = PANEL
            screen.rectangle(x, y, box, box)
            screen.font = HUGE
            w, h = screen.measure_text("?")
            ui.text_at("?", x + (box - w) / 2, y + (box - h) / 2, HUGE, DIM)
        screen.font = BODY
        w, _h = screen.measure_text(label)
        ui.text_at(label, x + (box - w) / 2, y + box + 8, BODY, pen)

    def draw_reveal(self, mine, theirs, top):
        mine_pick = pick_of(mine) if mine else self.NONE
        if theirs is None:
            self.draw_pick(mine_pick, (screen.width - self.REVEAL_BOX) // 2, top + 10, "you", BRIGHT, False)
            return
        their_pick = pick_of(theirs)
        outcome = self.compare(mine_pick, their_pick)
        self.draw_pick(mine_pick, 40, top + 10, "you", BRIGHT, outcome == HOST_WINS)
        self.draw_pick(their_pick, screen.width - 40 - self.REVEAL_BOX, top + 10, "them", RIVAL, outcome == GUEST_WINS)
        centred("vs", top + 10 + self.REVEAL_BOX // 2 - 10, TITLE, DIM)

    def describe(self, score):
        return "nothing" if score >= self.NONE else self.CHOICES[score]


class StopClock(Microgame):
    NAME = "STOP THE CLOCK"
    HINT = "count in your head"
    CONTROLS = (Control("stop", BUTTON_SELECT),)
    TARGET_MS = 5000
    VISIBLE_MS = 1000
    GRACE_MS = 3000
    REVEAL_MS = 1500
    PERFECT_MS = 20
    HOLD_MS = 300
    CX = 160
    CY = 98
    OUTER = 56
    INNER = 43
    LABEL_GAP = 6

    def start(self, now):
        super().start(now)
        self.stopped_at = None
        self.stopped_elapsed = None

    def update(self, now):
        if self.stopped_at is not None:
            if now - self.stopped_at >= self.REVEAL_MS:
                if self.stopped_elapsed is None:
                    self.finish(self.GRACE_MS)
                else:
                    self.finish(abs(self.stopped_elapsed - self.TARGET_MS))
            return
        elapsed = now - self.started
        if self.pressed(0):
            self.stopped_at = now
            self.stopped_elapsed = elapsed
        elif elapsed > self.TARGET_MS + self.GRACE_MS:
            self.stopped_at = now
            self.oops()

    def ring(self, from_fraction, to_fraction, pen):
        if to_fraction <= from_fraction:
            return
        screen.pen = pen
        screen.shape(shape.arc(vec2(self.CX, self.CY), self.INNER, self.OUTER, from_fraction * 360, to_fraction * 360))

    def draw(self, now):
        ui.clear()
        counting = self.stopped_at is None and now - self.started < self.VISIBLE_MS
        centred("count in your head" if counting else "stop at exactly 5s", 16, TITLE, TEXT)
        self.ring(0.0, 1.0, PANEL)
        if self.stopped_at is None:
            elapsed = now - self.started
            if elapsed < self.VISIBLE_MS:
                self.ring(0.0, elapsed / self.TARGET_MS, ACCENT)
                shown = "%.2f" % (elapsed / 1000)
            else:
                shown = None
            label = None
        elif self.stopped_elapsed is None:
            self.ring(0.0, 1.0, DIM)
            shown = None
            label = "too late"
        else:
            fraction = self.stopped_elapsed / self.TARGET_MS
            self.ring(0.0, min(1.0, fraction), ACCENT)
            self.ring(0.0, min(1.0, fraction - 1.0), BRIGHT)
            shown = "%.2f" % (self.stopped_elapsed / 1000)
            off = self.stopped_elapsed - self.TARGET_MS
            if abs(off) < self.PERFECT_MS:
                label = "perfect!"
            else:
                label = "%.2fs %s" % (abs(off) / 1000, "over" if off > 0 else "under")
        screen.pen = BRIGHT
        screen.rectangle(self.CX - 1, self.CY - self.OUTER - 4, 3, self.OUTER - self.INNER + 8)
        if shown is not None:
            screen.font = TITLE
            w, h = screen.measure_text(shown)
            ui.text_at(shown, self.CX - w / 2, self.CY - h / 2, TITLE, BRIGHT)
        if label is not None:
            centred(label, self.CY + self.OUTER + self.LABEL_GAP, BODY, ACCENT)

    REVEAL = True
    NO_STOP = 0xFFFF
    REVEAL_CY = 104
    REVEAL_INNER = 32
    REVEAL_OUTER = 42
    REVEAL_RIVAL_OUTER = 50
    REVEAL_LABEL_GAP = 12

    def detail(self):
        return struct.pack("<H", self.NO_STOP if self.stopped_elapsed is None else min(self.NO_STOP - 1, self.stopped_elapsed))

    def stop_of(self, detail):
        if not detail or len(detail) < 2:
            return None
        value = struct.unpack("<H", detail[:2])[0]
        return None if value == self.NO_STOP else value

    def arc(self, inner, outer, fraction, pen):
        if fraction <= 0:
            return
        centre = vec2(self.CX, self.REVEAL_CY)
        screen.pen = pen
        screen.shape(shape.arc(centre, inner, outer, 0, min(1.0, fraction) * 360))
        if fraction > 1.0:
            screen.pen = BRIGHT
            screen.shape(shape.arc(centre, inner, outer, 0, min(1.0, fraction - 1.0) * 360))

    def stop_label(self, stop):
        return "too late" if stop is None else "%.2fs" % (stop / 1000)

    def side_label(self, lines, pen, right):
        screen.font = BODY
        for number, text in enumerate(lines):
            w, h = screen.measure_text(text)
            x = self.CX + self.REVEAL_RIVAL_OUTER + self.REVEAL_LABEL_GAP if right else self.CX - self.REVEAL_RIVAL_OUTER - self.REVEAL_LABEL_GAP - w
            ui.text_at(text, x, self.REVEAL_CY - h + number * h, BODY, pen)

    def draw_reveal(self, mine, theirs, top):
        mine_stop = self.stop_of(mine)
        their_stop = self.stop_of(theirs) if theirs is not None else None
        centre = vec2(self.CX, self.REVEAL_CY)
        screen.pen = PANEL
        screen.shape(shape.arc(centre, self.REVEAL_INNER, self.REVEAL_OUTER, 0, 360))
        if mine_stop is not None:
            self.arc(self.REVEAL_INNER, self.REVEAL_OUTER, mine_stop / self.TARGET_MS, ACCENT)
        if theirs is not None:
            screen.pen = PANEL
            screen.shape(shape.arc(centre, self.REVEAL_OUTER + 2, self.REVEAL_RIVAL_OUTER, 0, 360))
            if their_stop is not None:
                self.arc(self.REVEAL_OUTER + 2, self.REVEAL_RIVAL_OUTER, their_stop / self.TARGET_MS, RIVAL)
        screen.pen = BRIGHT
        screen.rectangle(self.CX - 1, self.REVEAL_CY - self.REVEAL_RIVAL_OUTER - 4, 3, self.REVEAL_RIVAL_OUTER - self.REVEAL_INNER + 8)
        self.side_label(("you", self.stop_label(mine_stop)), BRIGHT, False)
        if theirs is not None:
            self.side_label(("them", self.stop_label(their_stop)), RIVAL, True)

    def describe(self, score):
        return "missed" if score >= self.GRACE_MS else "%.2fs off" % (score / 1000)


class Simon(Microgame):
    NAME = "SIMON"
    HINT = "repeat the pattern"
    CONTROLS = CHOICE_CONTROLS
    SHOW_HINT = False
    LENGTH = 4
    STEP_MS = 600
    HOLD_MS = 500
    POP_MS = 220
    RETRY_MS = 900
    TIMEOUT_MS = 6000
    MISS = 9000
    SLOT_PITCH = 76
    SLOT_Y = 104
    TITLE_Y = 28
    TURN_HINT_Y = 164
    RADIUS = 7

    def start(self, now):
        super().start(now)
        self.sequence = [self.rng.randrange(3) for _ in range(self.LENGTH)]
        self.input_at = now + self.LENGTH * self.STEP_MS + self.HOLD_MS
        self.entered = []
        self.second_chance = True
        self.retry_until = 0
        self.wrong = None

    def update(self, now):
        if now < self.input_at:
            return
        pressed = [symbol for symbol in range(3) if self.pressed(symbol)]
        if pressed:
            expected = self.sequence[len(self.entered)]
            symbol = expected if expected in pressed else pressed[0]
            if symbol != expected:
                self.oops()
                if not self.entered and self.second_chance:
                    self.second_chance = False
                    self.retry_until = now + self.RETRY_MS
                    return
                self.wrong = symbol
                self.finish(self.MISS)
                return
            self.entered.append(symbol)
            if len(self.entered) == self.LENGTH:
                self.finish(now - self.input_at)
                return
        if now - self.input_at > self.TIMEOUT_MS:
            self.finish(self.MISS)

    def draw_slot(self, index, symbol, scale):
        cx = screen.width / 2 + (index - (self.LENGTH - 1) / 2) * self.SLOT_PITCH
        screen.pen = PANEL
        screen.rectangle(cx - 34, self.SLOT_Y - 36, 68, 72)
        if symbol is None:
            ui.text_at("?", cx - 6, self.SLOT_Y - 12, TITLE, DIM)
            return
        radius = max(2, int(self.RADIUS * scale))
        ui.draw_hint(self.shape(), self.actions(symbol), cx, self.SLOT_Y, radius, self.upside_down)

    def draw(self, now):
        ui.clear()
        watching = now < self.input_at
        if watching:
            centred("watch", self.TITLE_Y, TITLE, DIM)
        elif now < self.retry_until:
            centred("try again", self.TITLE_Y, TITLE, BRIGHT)
        else:
            centred("your turn", self.TITLE_Y, TITLE, ACCENT)
        for index in range(self.LENGTH):
            if watching:
                appear = self.started + index * self.STEP_MS
                if now < appear:
                    self.draw_slot(index, None, 1)
                    continue
                age = now - appear
                pop = 1.0 + 0.6 * max(0.0, 1.0 - age / self.POP_MS) if age < self.POP_MS * 2 else 1.0
                self.draw_slot(index, self.sequence[index], pop)
            elif index < len(self.entered):
                self.draw_slot(index, self.entered[index], 1)
            else:
                self.draw_slot(index, None, 1)
        if not watching:
            ui.draw_hint(self.shape(), set(), screen.width / 2, self.TURN_HINT_Y, 8, self.upside_down)

    REVEAL = True
    WRONG_FLAG = 0x80
    REVEAL_PITCH = 54
    REVEAL_SHIFT = 42
    REVEAL_ROW = 44
    REVEAL_LABEL_X = 10

    def detail(self):
        data = bytes(self.entered)
        if self.wrong is not None:
            data += bytes((self.WRONG_FLAG | self.wrong,))
        return data

    def draw_reveal_row(self, label, pen, symbols, wrong, y):
        ui.text_at(label, self.REVEAL_LABEL_X, y - 10, BODY, pen)
        shape = self.shape()
        for index in range(self.LENGTH):
            cx = screen.width / 2 + self.REVEAL_SHIFT + (index - (self.LENGTH - 1) / 2) * self.REVEAL_PITCH
            screen.pen = PANEL
            screen.rectangle(int(cx - 24), y - 18, 48, 36)
            if index < len(symbols):
                ui.draw_hint(shape, self.actions(symbols[index]), cx, y, 4, self.upside_down)
            elif index == len(symbols) and wrong is not None:
                ui.draw_hint(shape, self.actions(wrong), cx, y, 4, self.upside_down)
                screen.pen = FADE
                screen.rectangle(int(cx - 24), y - 18, 48, 36)

    def split_detail(self, detail):
        symbols = [value for value in detail if value < self.WRONG_FLAG]
        wrong = [value & 0x7F for value in detail if value >= self.WRONG_FLAG]
        return symbols, wrong[0] if wrong else None

    def draw_reveal(self, mine, theirs, top):
        self.draw_reveal_row("simon", ACCENT, self.sequence, None, top + 22)
        symbols, wrong = self.split_detail(mine or b"")
        self.draw_reveal_row("you", BRIGHT, symbols, wrong, top + 22 + self.REVEAL_ROW)
        if theirs is not None:
            symbols, wrong = self.split_detail(theirs)
            self.draw_reveal_row("them", RIVAL, symbols, wrong, top + 22 + self.REVEAL_ROW * 2)

    def describe(self, score):
        return "missed" if score >= self.MISS else "%.1f s" % (score / 1000)


ARROW_DIRECTIONS = ((1, 0), (-1, 0), (0, 1), (0, -1))


class ArrowRush(Microgame):
    NAME = "ARROW RUSH"
    HINT = "tilt into the arrow"
    CONTROLS = TILT
    DURATION_MS = 7000
    WINDOW_MS = 1800
    ARROWS = 60
    TILT_ON = 0.22
    CENTRE_RADIUS = 22
    CENTRE_HOLD_MS = 150
    POP_MS = 250
    STAGE_ARROW = 0
    STAGE_CENTRE = 1
    SMOOTH = 0.35
    SIZE = 20
    TRAVEL_X = 100
    TRAVEL_Y = 48
    CX = 160
    CY = 104
    WINDOW_Y = 180

    def start(self, now):
        super().start(now)
        self.arrows = [self.rng.randrange(len(ARROW_DIRECTIONS)) for _ in range(self.ARROWS)]
        self.index = 0
        self.correct = 0
        self.lean_x = 0.0
        self.lean_y = 0.0
        self.flash_until = 0
        self.pop_at = None
        self.pop_kind = None
        self.pop_direction = ARROW_DIRECTIONS[0]
        self.stage = self.STAGE_ARROW
        self.centre_since = None
        reading = badge.imu()
        self.level_x = reading[0] / IMU_GRAVITY
        self.level_y = reading[1] / IMU_GRAVITY
        self.shown_at = now

    def target(self):
        return ARROW_DIRECTIONS[self.arrows[self.index]]

    def reach(self):
        return (max(-1.0, min(1.0, self.lean_x / self.TILT_ON)),
                max(-1.0, min(1.0, self.lean_y / self.TILT_ON)))

    def marker(self):
        reach_x, reach_y = self.reach()
        return self.CX + reach_x * self.TRAVEL_X, self.CY + reach_y * self.TRAVEL_Y

    def pointing(self):
        if abs(self.lean_x) >= abs(self.lean_y):
            return (1 if self.lean_x > 0 else -1, 0), abs(self.lean_x)
        return (0, 1 if self.lean_y > 0 else -1), abs(self.lean_y)

    def in_zone(self):
        direction, amount = self.pointing()
        return direction if amount >= self.TILT_ON else None

    def centred(self):
        x, y = self.marker()
        return (x - self.CX) ** 2 + (y - self.CY) ** 2 < self.CENTRE_RADIUS ** 2

    def relevel(self):
        sign = -1 if self.upside_down else 1
        self.level_x += self.lean_x * sign
        self.level_y += self.lean_y * sign
        self.lean_x = 0.0
        self.lean_y = 0.0

    def pop(self, kind, now):
        self.pop_kind = kind
        self.pop_at = now
        self.pop_direction = self.target()

    def update(self, now):
        lean_x, lean_y = read_lean(self.level_x, self.level_y, self.upside_down)
        self.lean_x += (lean_x - self.lean_x) * self.SMOOTH
        self.lean_y += (lean_y - self.lean_y) * self.SMOOTH
        if now - self.started >= self.DURATION_MS:
            self.finish(self.correct)
            return
        if self.pop_at is not None:
            if now - self.pop_at < self.POP_MS:
                return
            self.pop_at = None
            if self.pop_kind == self.STAGE_ARROW:
                self.index = (self.index + 1) % self.ARROWS
                self.stage = self.STAGE_CENTRE
            else:
                self.stage = self.STAGE_ARROW
            self.shown_at = now
        if self.stage == self.STAGE_CENTRE:
            if not self.centred():
                self.centre_since = None
            elif self.centre_since is None:
                self.centre_since = now
            elif now - self.centre_since >= self.CENTRE_HOLD_MS:
                self.centre_since = None
                self.relevel()
                self.pop(self.STAGE_CENTRE, now)
            return
        if self.in_zone() == self.target():
            self.correct += 1
            self.pop(self.STAGE_ARROW, now)
        elif now - self.shown_at > self.WINDOW_MS:
            self.flash_until = now + 200
            self.oops()
            self.index = (self.index + 1) % self.ARROWS
            self.stage = self.STAGE_CENTRE
            self.shown_at = now

    def spot(self, direction):
        return self.CX + direction[0] * self.TRAVEL_X, self.CY + direction[1] * self.TRAVEL_Y

    def arrow(self, x, y, direction, size, pen):
        dx, dy = direction
        side_x, side_y = -dy, dx
        screen.pen = pen
        screen.triangle(
            vec2(x + dx * size, y + dy * size),
            vec2(x - dx * size / 2 + side_x * size * 0.8, y - dy * size / 2 + side_y * size * 0.8),
            vec2(x - dx * size / 2 - side_x * size * 0.8, y - dy * size / 2 - side_y * size * 0.8),
        )

    def outline(self, x, y, direction, size, pen):
        self.arrow(x, y, direction, size, pen)
        self.arrow(x, y, direction, size - 6, BACKGROUND)

    def ring(self, radius, pen):
        centre = vec2(self.CX, self.CY)
        screen.pen = pen
        screen.circle(centre, radius)
        screen.pen = BACKGROUND
        screen.circle(centre, radius - 4)

    def draw_marker(self):
        x, y = self.marker()
        direction, amount = self.pointing()
        if amount < self.TILT_ON * 0.3:
            screen.pen = BRIGHT
            screen.circle(vec2(x, y), 7)
        else:
            pen = ACCENT if self.stage == self.STAGE_ARROW and direction == self.target() else BRIGHT
            self.arrow(x, y, direction, self.SIZE - 6, pen)

    def draw(self, now):
        ui.clear(PANEL if now < self.flash_until else BACKGROUND)
        ui.timer_bar(now, self.started, self.DURATION_MS)
        ui.text_at("%d" % self.correct, 14, 28, TITLE, DIM)
        screen.pen = PANEL
        screen.rectangle(self.CX - self.TRAVEL_X, self.CY - 1, self.TRAVEL_X * 2, 3)
        screen.rectangle(self.CX - 1, self.CY - self.TRAVEL_Y, 3, self.TRAVEL_Y * 2)

        if self.pop_at is not None:
            progress = min(1.0, (now - self.pop_at) / self.POP_MS)
            grow = 1.0 + 0.5 * (1.0 - progress)
            if self.pop_kind == self.STAGE_ARROW:
                x, y = self.spot(self.pop_direction)
                self.arrow(x, y, self.pop_direction, self.SIZE * grow, ACCENT)
            else:
                self.ring(int(self.CENTRE_RADIUS * grow), ACCENT)
            self.draw_marker()
            return

        if self.stage == self.STAGE_CENTRE:
            self.ring(self.CENTRE_RADIUS, BRIGHT)
            self.draw_marker()
            return

        target = self.target()
        x, y = self.spot(target)
        self.outline(x, y, target, self.SIZE, BRIGHT)
        self.draw_marker()

        remaining = max(0, self.WINDOW_MS - (now - self.shown_at))
        screen.pen = PANEL
        screen.rectangle(80, self.WINDOW_Y, 160, 4)
        screen.pen = BRIGHT
        screen.rectangle(80, self.WINDOW_Y, int(160 * remaining / self.WINDOW_MS), 4)

    @staticmethod
    def compare(host, guest):
        return compare_higher(host, guest)

    def describe(self, score):
        return "%d arrows" % score


class CountDots(Microgame):
    NAME = "COUNT THEM"
    HINT = "count the dots, fast"
    CONTROLS = CHOICE_CONTROLS
    SHOW_HINT = False
    TIMEOUT_MS = 7000
    MISS = 9999
    MIN_DOTS = 4
    MAX_DOTS = 9
    DOT = 8
    SPACING = 30
    FIELD_X = 20
    FIELD_Y = 8
    FIELD_W = 280
    FIELD_H = 104
    CHOICE_Y = 124
    CHOICE_W = 64
    CHOICE_H = 42
    CHOICE_PITCH = 88

    def start(self, now):
        super().start(now)
        self.count = self.MIN_DOTS + self.rng.randrange(self.MAX_DOTS - self.MIN_DOTS + 1)
        margin = self.DOT + 6
        self.dots = []
        while len(self.dots) < self.count:
            x = self.FIELD_X + margin + self.rng.randrange(self.FIELD_W - margin * 2)
            y = self.FIELD_Y + margin + self.rng.randrange(self.FIELD_H - margin * 2)
            if all((x - ox) ** 2 + (y - oy) ** 2 > self.SPACING ** 2 for ox, oy in self.dots):
                self.dots.append((x, y))
        decoys = [self.count + offset for offset in (-2, -1, 1, 2) if self.count + offset >= 1]
        first = decoys.pop(self.rng.randrange(len(decoys)))
        second = decoys.pop(self.rng.randrange(len(decoys)))
        options = [self.count, first, second]
        self.options = []
        while options:
            self.options.append(options.pop(self.rng.randrange(len(options))))
        self.picked = None

    def update(self, now):
        elapsed = now - self.started
        for choice in range(3):
            if self.pressed(choice):
                self.picked = choice
                if self.options[choice] == self.count:
                    self.finish(elapsed)
                else:
                    self.oops()
                    self.finish(self.MISS)
                return
        if elapsed > self.TIMEOUT_MS:
            self.finish(self.MISS)

    def draw(self, now):
        ui.clear()
        screen.pen = PANEL
        screen.rectangle(self.FIELD_X, self.FIELD_Y, self.FIELD_W, self.FIELD_H)
        screen.pen = BRIGHT
        for x, y in self.dots:
            screen.circle(vec2(x, y), self.DOT)
        self.draw_choices(["%d" % option for option in self.options], self.picked,
                          top=self.CHOICE_Y, box_w=self.CHOICE_W, box_h=self.CHOICE_H, pitch=self.CHOICE_PITCH, hint_gap=(12, 22))

    REVEAL = True

    def detail(self):
        return bytes((NO_PICK if self.picked is None else self.options[self.picked],))

    def draw_reveal(self, mine, theirs, top):
        centred("there were %d dots" % self.count, top + 4, BODY, TEXT)
        box_w, box_h, pitch = self.CHOICE_W, self.CHOICE_H, self.CHOICE_PITCH
        left = (screen.width - (pitch * 2 + box_w)) // 2
        box_y = top + 40
        mine_value = pick_of(mine)
        their_value = pick_of(theirs) if theirs is not None else NO_PICK
        for index, option in enumerate(sorted(self.options)):
            x = left + index * pitch
            right = option == self.count
            screen.pen = ACCENT if right else PANEL
            screen.rectangle(x, box_y, box_w, box_h)
            screen.font = HUGE
            w, h = screen.measure_text("%d" % option)
            ui.text_at("%d" % option, x + (box_w - w) / 2, box_y + (box_h - h) / 2, HUGE, BACKGROUND if right else BRIGHT)
            tag_y = box_y + box_h + 6
            for value, label, pen in ((mine_value, "you", BRIGHT), (their_value, "them", RIVAL)):
                if value == option:
                    screen.font = BODY
                    w, _h = screen.measure_text(label)
                    ui.text_at(label, x + (box_w - w) / 2, tag_y, BODY, pen)
                    tag_y += 20

    def describe(self, score):
        return "wrong" if score >= self.MISS else "%.1f s" % (score / 1000)


class OddOneOut(Microgame):
    NAME = "ODD ONE OUT"
    HINT = "find the imposter"
    CONTROLS = GRID_CONTROLS
    TIMEOUT_MS = 8000
    PENALTY_MS = 1500
    COLUMNS = 4
    ROWS = 3
    TILE = 52
    GAP = 6
    SCALE = 3

    def start(self, now):
        super().start(now)
        load_icons()
        count = len(ODD_CATEGORIES)
        common = self.rng.randrange(count)
        other = (common + 1 + self.rng.randrange(count - 1)) % count
        family, chars = ODD_CATEGORIES[common]
        tiles = self.COLUMNS * self.ROWS
        self.tiles = [(family, chars[self.rng.randrange(len(chars))]) for _ in range(tiles)]
        self.odd = self.rng.randrange(tiles)
        odd_family, odd_chars = ODD_CATEGORIES[other]
        self.tiles[self.odd] = (odd_family, odd_chars[self.rng.randrange(len(odd_chars))])
        self.cursor = 0
        self.penalty = 0
        self.flash_until = 0

    def update(self, now):
        self.cursor = move_cursor(self.cursor, self.COLUMNS, self.COLUMNS * self.ROWS, self.upside_down)
        if self.pressed(1):
            if self.cursor == self.odd:
                self.finish(now - self.started + self.penalty)
                return
            self.penalty += self.PENALTY_MS
            self.flash_until = now + 300
            self.oops()
        if now - self.started + self.penalty >= self.TIMEOUT_MS:
            self.finish(self.TIMEOUT_MS)

    def draw(self, now):
        ui.clear(PANEL if now < self.flash_until else BACKGROUND)
        pitch = self.TILE + self.GAP
        left = (screen.width - (pitch * self.COLUMNS - self.GAP)) // 2
        top = (CONTENT_BOTTOM - (pitch * self.ROWS - self.GAP)) // 2
        for index in range(self.COLUMNS * self.ROWS):
            x = left + (index % self.COLUMNS) * pitch
            y = top + (index // self.COLUMNS) * pitch
            family, char = self.tiles[index]
            draw_icon_tile(family, char, x, y, self.TILE, self.TILE, self.SCALE, index == self.cursor)

    REVEAL = True

    def detail(self):
        return bytes((self.cursor,))

    def draw_reveal(self, mine, theirs, top):
        draw_grid_reveal(self.tiles, self.COLUMNS, self.odd, mine, theirs, top)

    def describe(self, score):
        return "missed" if score >= self.TIMEOUT_MS else "%.1f s" % (score / 1000)


class Balance(Microgame):
    NAME = "BALANCE"
    HINT = "stay in the ring"
    CONTROLS = TILT
    DURATION_MS = 7000
    GUSTS = 2
    GUST_RAMP_MS = 700
    GUST = 180.0
    ACCEL = 900.0
    FRICTION = 1.5
    BALL = 9
    RING = 40
    STREAKS = 26

    def start(self, now):
        super().start(now)
        self.cx = screen.width / 2
        self.cy = CONTENT_BOTTOM / 2 + 12
        self.x, self.y = self.cx, self.cy
        self.vx = 0.0
        self.vy = 0.0
        first = self.rng.uniform(0, math.pi * 2)
        self.gusts = [first, first + self.rng.uniform(math.pi / 2, math.pi * 3 / 2)]
        self.streaks = [(self.rng.randrange(screen.width), self.rng.randrange(CONTENT_BOTTOM)) for _ in range(self.STREAKS)]
        reading = badge.imu()
        self.level_x = reading[0] / IMU_GRAVITY
        self.level_y = reading[1] / IMU_GRAVITY
        self.inside_ms = 0
        self.last = now

    def wind(self, now):
        elapsed = now - self.started
        span = self.DURATION_MS // self.GUSTS
        index = min(self.GUSTS - 1, elapsed // span)
        into = elapsed - index * span
        envelope = max(0.0, min(1.0, into / self.GUST_RAMP_MS, (span - into) / self.GUST_RAMP_MS))
        angle = self.gusts[index]
        return math.cos(angle) * envelope, math.sin(angle) * envelope, envelope

    def update(self, now):
        dt = min(50, now - self.last)
        seconds = dt / 1000
        self.last = now
        lean_x, lean_y = read_lean(self.level_x, self.level_y, self.upside_down)
        wind_x, wind_y, _strength = self.wind(now)
        self.vx += (lean_x * self.ACCEL + wind_x * self.GUST) * seconds
        self.vy += (lean_y * self.ACCEL + wind_y * self.GUST) * seconds
        drag = max(0.0, 1.0 - self.FRICTION * seconds)
        self.vx *= drag
        self.vy *= drag
        self.x += self.vx * seconds
        self.y += self.vy * seconds
        if self.x < self.BALL or self.x > screen.width - self.BALL:
            self.vx = -self.vx * 0.5
            self.x = min(screen.width - self.BALL, max(self.BALL, self.x))
        if self.y < self.BALL + 24 or self.y > CONTENT_BOTTOM - self.BALL:
            self.vy = -self.vy * 0.5
            self.y = min(CONTENT_BOTTOM - self.BALL, max(self.BALL + 24, self.y))
        if (self.x - self.cx) ** 2 + (self.y - self.cy) ** 2 < (self.RING - self.BALL) ** 2:
            self.inside_ms += dt
        if now - self.started >= self.DURATION_MS:
            self.finish(self.inside_ms)

    def draw(self, now):
        ui.clear()
        wind_x, wind_y, strength = self.wind(now)
        if strength > 0.1:
            screen.pen = DIM if strength > 0.5 else PANEL
            travel = (now - self.started) * 0.35
            length = 44 * strength
            for sx, sy in self.streaks:
                x = (sx + wind_x * travel) % screen.width
                y = 24 + (sy + wind_y * travel) % (CONTENT_BOTTOM - 24)
                screen.line(vec2(x, y), vec2(x - wind_x * length, y - wind_y * length))
                screen.line(vec2(x, y + 1), vec2(x - wind_x * length, y + 1 - wind_y * length))
        ui.timer_bar(now, self.started, self.DURATION_MS)
        centred("%.1f s" % (self.inside_ms / 1000), 26, BODY, DIM)
        if strength > 0.1:
            ax, ay = screen.width - 40, 60
            reach = 26 * strength
            tip = vec2(ax + wind_x * reach, ay + wind_y * reach)
            screen.pen = TEXT
            screen.line(vec2(ax - wind_x * reach, ay - wind_y * reach), tip)
            side_x, side_y = -wind_y, wind_x
            screen.triangle(tip, vec2(tip.x - wind_x * 10 + side_x * 6, tip.y - wind_y * 10 + side_y * 6), vec2(tip.x - wind_x * 10 - side_x * 6, tip.y - wind_y * 10 - side_y * 6))
        screen.pen = ACCENT
        screen.circle(vec2(self.cx, self.cy), self.RING + 3)
        screen.pen = BACKGROUND
        screen.circle(vec2(self.cx, self.cy), self.RING)
        screen.pen = BRIGHT
        screen.circle(vec2(self.x, self.y), self.BALL)

    @staticmethod
    def compare(host, guest):
        return compare_higher(host, guest)

    def describe(self, score):
        return "%.1f s in" % (score / 1000)


UP = "up"
DOWN = "down"
LEFT = "left"
RIGHT = "right"
OPPOSITE_SIDE = {UP: DOWN, DOWN: UP, LEFT: RIGHT, RIGHT: LEFT}

PIPES = (
    ("\u00c2", {LEFT, RIGHT}, (0, 0)),
    ("\u00c6", {UP, DOWN}, (0, 0)),
    ("\u00bc", {RIGHT, DOWN}, (2, 2)),
    ("\u00bd", {LEFT, DOWN}, (-2, 2)),
    ("\u00be", {UP, LEFT}, (-2, -2)),
    ("\u00bf", {UP, RIGHT}, (2, -2)),
    ("\u00c0", {UP, DOWN, LEFT, RIGHT}, (0, 0)),
)


def pipe_for(sides):
    for index, (_char, connects, _offset) in enumerate(PIPES):
        if connects == sides:
            return index
    return 0


class FixPipe(Microgame):
    NAME = "FIX THE PIPE"
    HINT = "pick the missing piece"
    CONTROLS = CHOICE_CONTROLS
    SHOW_HINT = False
    DURATION_MS = 8000
    FLOW_MS = 260
    COLUMNS = 8
    ROWS = 3
    SCALE = 2
    PITCH_X = ICON_W * SCALE
    PITCH_Y = ICON_H * SCALE
    PLATE_MARGIN = 3
    BOX_W = 56
    BUTTON_X = (80, 160, 240)
    BOARD_Y = 44
    COUNT_Y = 150
    BOX_Y = 190
    BOX_H = 42
    FLIPPED_BOARD_Y = 26
    FLIPPED_BOX_Y = 126
    FLIPPED_BOX_H = 38
    FLIPPED_BOX_PITCH = 72
    FLIPPED_OPTIONS_WIDTH = 238
    FLIPPED_COUNT_X = 278
    FLIPPED_COUNT_Y = 132
    FLIPPED_HINT_GAP = 13
    FLIPPED_HINT_RADIUS = 4

    def start(self, now):
        super().start(now)
        load_icons()
        self.fixed = 0
        self.flash_until = 0
        self.flow_until = 0
        self.board_x = (screen.width - self.COLUMNS * self.PITCH_X) // 2
        self.board_y = self.FLIPPED_BOARD_Y if self.upside_down else self.BOARD_Y
        self.new_puzzle()

    def hides_mona(self):
        return not self.upside_down

    def new_puzzle(self):
        row = self.rng.randrange(self.ROWS)
        cells = []
        entry = LEFT
        column = 0
        while column < self.COLUMNS:
            moves = [RIGHT]
            if cells and cells[-1][3] == RIGHT or not cells:
                if row > 0:
                    moves.append(UP)
                if row < self.ROWS - 1:
                    moves.append(DOWN)
            exit_side = RIGHT if column == self.COLUMNS - 1 else moves[self.rng.randrange(len(moves))]
            cells.append((column, row, entry, exit_side))
            if exit_side == RIGHT:
                column += 1
            else:
                row += -1 if exit_side == UP else 1
            entry = OPPOSITE_SIDE[exit_side]
        self.cells = [(column, row, pipe_for({entry, exit_side})) for column, row, entry, exit_side in cells]
        self.gap = 1 + self.rng.randrange(len(self.cells) - 2)
        answer = self.cells[self.gap][2]
        needed = PIPES[answer][1]
        near = [index for index, (_char, sides, _offset) in enumerate(PIPES) if index != answer and sides & needed]
        options = [answer]
        while len(options) < 3:
            options.append(near.pop(self.rng.randrange(len(near))))
        self.options = []
        while options:
            self.options.append(options.pop(self.rng.randrange(len(options))))

    def update(self, now):
        if self.flow_until:
            if now < self.flow_until:
                return
            self.flow_until = 0
            self.new_puzzle()
        for choice in range(3):
            if not self.pressed(choice):
                continue
            if self.options[choice] == self.cells[self.gap][2]:
                self.fixed += 1
                self.flow_until = now + self.FLOW_MS
            else:
                self.fixed = max(0, self.fixed - 1)
                self.flash_until = now + 250
                self.oops()
                self.new_puzzle()
            return
        if now - self.started >= self.DURATION_MS:
            self.finish(self.fixed)

    def draw_pipe(self, index, x, y, fill=BRIGHT):
        offset_x, offset_y = PIPES[index][2]
        draw_icon("tools_crafting", PIPES[index][0], x + offset_x * self.SCALE, y + offset_y * self.SCALE, self.SCALE, fill)

    def draw_board(self, now):
        flowing = now < self.flow_until
        pen = ACCENT if flowing else BRIGHT
        screen.pen = ICON_TILE
        screen.rectangle(0, self.board_y - self.PLATE_MARGIN, screen.width, self.ROWS * self.PITCH_Y + self.PLATE_MARGIN * 2)
        straight = pipe_for({LEFT, RIGHT})
        entry_row = self.cells[0][1]
        exit_row = self.cells[-1][1]
        column = -1
        while self.board_x + column * self.PITCH_X + self.PITCH_X > 0:
            self.draw_pipe(straight, self.board_x + column * self.PITCH_X, self.board_y + entry_row * self.PITCH_Y, pen)
            column -= 1
        column = self.COLUMNS
        while self.board_x + column * self.PITCH_X < screen.width:
            self.draw_pipe(straight, self.board_x + column * self.PITCH_X, self.board_y + exit_row * self.PITCH_Y, pen)
            column += 1
        for position, (column, row, index) in enumerate(self.cells):
            x = self.board_x + column * self.PITCH_X
            y = self.board_y + row * self.PITCH_Y
            if position == self.gap and not flowing:
                if int(now / 250) % 2:
                    screen.pen = ACCENT
                    screen.rectangle(x + 1, y + 1, self.PITCH_X - 2, self.PITCH_Y - 2)
                    screen.pen = ICON_TILE
                    screen.rectangle(x + 3, y + 3, self.PITCH_X - 6, self.PITCH_Y - 6)
                continue
            self.draw_pipe(index, x, y, pen)

    def draw_options_over_buttons(self):
        for slot, index in enumerate(self.options):
            x = self.BUTTON_X[slot] - self.BOX_W // 2
            draw_icon_tile("tools_crafting", PIPES[index][0], x, self.BOX_Y, self.BOX_W, self.BOX_H, self.SCALE)

    def draw_options_with_hints(self):
        left = (self.FLIPPED_OPTIONS_WIDTH - (self.FLIPPED_BOX_PITCH * 2 + self.BOX_W)) // 2
        shape = self.shape()
        for slot, index in enumerate(self.options):
            x = left + slot * self.FLIPPED_BOX_PITCH
            draw_icon_tile("tools_crafting", PIPES[index][0], x, self.FLIPPED_BOX_Y, self.BOX_W, self.FLIPPED_BOX_H, self.SCALE)
            cy = self.FLIPPED_BOX_Y + self.FLIPPED_BOX_H + self.FLIPPED_HINT_GAP
            ui.draw_hint(shape, self.actions(slot), x + self.BOX_W // 2, cy, self.FLIPPED_HINT_RADIUS, self.upside_down)

    def draw(self, now):
        ui.clear(PANEL if now < self.flash_until else BACKGROUND)
        ui.timer_bar(now, self.started, self.DURATION_MS)
        self.draw_board(now)
        count = "%d fixed" % self.fixed
        if self.upside_down:
            screen.font = BODY
            w, _h = screen.measure_text(count)
            ui.text_at(count, self.FLIPPED_COUNT_X - w / 2, self.FLIPPED_COUNT_Y, BODY, DIM)
            self.draw_options_with_hints()
        else:
            centred(count, self.COUNT_Y, BODY, DIM)
            self.draw_options_over_buttons()

    @staticmethod
    def compare(host, guest):
        return compare_higher(host, guest)

    def describe(self, score):
        return "%d fixed" % score


class TapTempo(Microgame):
    NAME = "TAP TEMPO"
    HINT = "keep the beat going"
    CONTROLS = (Control("tap any", (BUTTON_LEFT, BUTTON_RIGHT, BUTTON_SELECT), DIRECTIONS + (BUTTON_SELECT, BUTTON_BACK)),)
    DEMO_BEATS = 4
    TAPS = 6
    LEAD_MS = 600
    LANE_Y = 104
    LANE_H = 44
    DRUM_X = 62
    DRUM_RADIUS = 20
    NOTE_RADIUS = 10
    TRAVEL_MS = 1400
    FADE_X = 170
    STRIKE_MS = 130
    FLASH_MS = 110
    GRADE_MS = 450
    GRADES = ((60, "great"), (120, "good"))
    BATON_W = 5
    BATON_LIFT = 22

    def start(self, now):
        super().start(now)
        self.beat = int(self.rng.uniform(450, 700))
        self.first = now + self.LEAD_MS
        self.errors = []
        self.tapped_at = None

    def expected(self, tap):
        return self.first + (self.DEMO_BEATS + tap) * self.beat

    def update(self, now):
        if self.pressed(0) and now >= self.expected(0) - self.beat // 2:
            error = min(self.beat, abs(now - self.expected(len(self.errors))))
            if error > self.beat // 3:
                self.oops()
            self.errors.append(error)
            self.tapped_at = now
            if len(self.errors) == self.TAPS:
                self.finish(sum(self.errors) // self.TAPS)
                return
        if now > self.expected(self.TAPS - 1) + self.beat:
            missing = self.TAPS - len(self.errors)
            self.finish((sum(self.errors) + missing * self.beat) // self.TAPS)

    def last_hit(self, now):
        hits = [self.first + beat * self.beat for beat in range(self.DEMO_BEATS) if self.first + beat * self.beat <= now]
        if self.tapped_at is not None:
            hits.append(self.tapped_at)
        return max(hits) if hits else None

    def note_x(self, at, now):
        return self.DRUM_X + (at - now) / self.TRAVEL_MS * (screen.width + self.NOTE_RADIUS - self.DRUM_X)

    def draw_baton(self, base_x, base_y, tip_x, tip_y):
        screen.pen = TEXT
        screen.shape(shape.line(vec2(base_x, base_y), vec2(tip_x, tip_y), self.BATON_W))
        screen.pen = BRIGHT
        screen.circle(vec2(tip_x, tip_y), self.BATON_W)

    def draw(self, now):
        ui.clear()
        demo = now < self.expected(0) - self.beat // 2
        centred("watch the beat" if demo else "keep it going", 16, TITLE, DIM if demo else ACCENT)
        top = self.LANE_Y - self.LANE_H // 2
        screen.pen = PANEL
        screen.rectangle(0, top, screen.width, self.LANE_H)

        for beat in range(self.DEMO_BEATS):
            at = self.first + beat * self.beat
            x = self.note_x(at, now)
            if self.DRUM_X <= x <= screen.width + self.NOTE_RADIUS:
                screen.pen = BRIGHT
                screen.circle(vec2(x, self.LANE_Y), self.NOTE_RADIUS)
        for tap in range(len(self.errors), self.TAPS):
            x = self.note_x(self.expected(tap), now)
            if self.FADE_X <= x <= screen.width + self.NOTE_RADIUS:
                screen.pen = DIM
                screen.circle(vec2(x, self.LANE_Y), self.NOTE_RADIUS)
                screen.pen = PANEL
                screen.circle(vec2(x, self.LANE_Y), self.NOTE_RADIUS - 3)

        hit = self.last_hit(now)
        since = None if hit is None else now - hit
        striking = since is not None and since < self.STRIKE_MS
        flashing = since is not None and since < self.FLASH_MS
        centre = vec2(self.DRUM_X, self.LANE_Y)
        screen.pen = BRIGHT
        screen.circle(centre, self.DRUM_RADIUS + 4)
        screen.pen = ACCENT if flashing else BACKGROUND
        screen.circle(centre, self.DRUM_RADIUS)
        lift = 0 if striking else self.BATON_LIFT
        self.draw_baton(self.DRUM_X - 36, top - 34 - lift // 2, self.DRUM_X - 9, top + 2 - lift)
        self.draw_baton(self.DRUM_X + 36, top - 34 - lift // 2, self.DRUM_X + 9, top + 2 - lift)

        if self.tapped_at is not None and now - self.tapped_at < self.GRADE_MS and self.errors:
            error = self.errors[-1]
            label = "ok"
            for limit, name in self.GRADES:
                if error < limit:
                    label = name
                    break
            screen.font = BODY
            w, _h = screen.measure_text(label)
            rise = (now - self.tapped_at) // 30
            ui.text_at(label, self.DRUM_X - w / 2, top + self.LANE_H + 6 - rise, BODY, ACCENT if label != "ok" else TEXT)

        for index in range(self.TAPS):
            ui.dot(screen.width / 2 + 40 + (index - 2.5) * 22, 166, 6, index < len(self.errors))

    def describe(self, score):
        return "%d ms off" % score


class Bowling(Microgame):
    NAME = "BOWLING"
    HINT = "bowl a strike"
    CONTROLS = (Control("bowl", BUTTON_SELECT),)
    WAIT_MS = 6000
    SIM_MS = 1600
    SHOW_MS = 900
    HOLD_MS = 300
    STEP_MS = 8
    LANE_X = 110
    LANE_W = 100
    LANE_TOP = 12
    LANE_BOTTOM = CONTENT_BOTTOM - 4
    BALL = 7
    PIN = 5
    PIN_ROWS = (4, 3, 2, 1)
    PIN_TOP = 26
    PIN_PITCH_X = 16
    PIN_PITCH_Y = 13
    BALL_SPEED = 330.0
    BALL_MASS = 3.0
    PIN_MASS = 1.0
    RESTITUTION = 0.8
    WALL_BOUNCE = 0.6
    RESTING = 1.0
    FRICTION = 2.2
    KNOCKED = 4.0
    TILT_PULL = 320.0
    AMPLITUDE = 26
    MAX_ANGLE = 0.2
    GUIDE = 34

    def start(self, now):
        super().start(now)
        self.position_period = self.rng.uniform(1100, 1700)
        self.angle_period = self.rng.uniform(900, 1500)
        self.position_phase = self.rng.uniform(0, math.pi * 2)
        self.angle_phase = self.rng.uniform(0, math.pi * 2)
        self.centre = self.LANE_X + self.LANE_W / 2
        self.pins = []
        for row, count in enumerate(self.PIN_ROWS):
            y = self.PIN_TOP + row * self.PIN_PITCH_Y
            for index in range(count):
                x = self.centre + (index - (count - 1) / 2) * self.PIN_PITCH_X
                self.pins.append([x, y, 0.0, 0.0, x, y])
        self.ball_start_y = self.LANE_BOTTOM - self.BALL - 4
        reading = badge.imu()
        self.level_x = reading[0] / IMU_GRAVITY
        self.level_y = reading[1] / IMU_GRAVITY
        self.lean = 0.0
        self.thrown_at = None
        self.simulated = 0
        self.ball = None

    def aim(self, now):
        elapsed = now - self.started
        x = self.centre + self.AMPLITUDE * math.sin(2 * math.pi * elapsed / self.position_period + self.position_phase)
        angle = self.MAX_ANGLE * math.sin(2 * math.pi * elapsed / self.angle_period + self.angle_phase)
        return x, angle

    def knocked(self):
        count = 0
        for x, y, _vx, _vy, home_x, home_y in self.pins:
            if (x - home_x) ** 2 + (y - home_y) ** 2 > self.KNOCKED ** 2:
                count += 1
        return count

    def collide(self, a, b, mass_a, mass_b, reach):
        dx = b[0] - a[0]
        dy = b[1] - a[1]
        distance_squared = dx * dx + dy * dy
        if distance_squared >= reach * reach or distance_squared == 0:
            return
        distance = math.sqrt(distance_squared)
        nx, ny = dx / distance, dy / distance
        overlap = reach - distance
        total = mass_a + mass_b
        a[0] -= nx * overlap * mass_b / total
        a[1] -= ny * overlap * mass_b / total
        b[0] += nx * overlap * mass_a / total
        b[1] += ny * overlap * mass_a / total
        closing = (a[2] - b[2]) * nx + (a[3] - b[3]) * ny
        if closing <= 0:
            return
        impulse = (1 + self.RESTITUTION) * closing / total
        a[2] -= impulse * mass_b * nx
        a[3] -= impulse * mass_b * ny
        b[2] += impulse * mass_a * nx
        b[3] += impulse * mass_a * ny

    def bounce(self, body, radius):
        left = self.LANE_X + radius
        right = self.LANE_X + self.LANE_W - radius
        if body[0] < left:
            body[0] = left
            body[2] = abs(body[2]) * self.WALL_BOUNCE
        elif body[0] > right:
            body[0] = right
            body[2] = -abs(body[2]) * self.WALL_BOUNCE

    def step(self):
        seconds = self.STEP_MS / 1000
        ball = self.ball
        ball[2] += self.lean * self.TILT_PULL * seconds
        ball[0] += ball[2] * seconds
        ball[1] += ball[3] * seconds
        self.bounce(ball, self.BALL)
        drag = max(0.0, 1.0 - self.FRICTION * seconds)
        for pin in self.pins:
            pin[0] += pin[2] * seconds
            pin[1] += pin[3] * seconds
            pin[2] *= drag
            pin[3] *= drag
            self.bounce(pin, self.PIN)
        reach = self.BALL + self.PIN
        for pin in self.pins:
            if abs(pin[0] - ball[0]) < reach and abs(pin[1] - ball[1]) < reach:
                self.collide(ball, pin, self.BALL_MASS, self.PIN_MASS, reach)
        reach = self.PIN * 2
        moving = [pin[2] * pin[2] + pin[3] * pin[3] > self.RESTING for pin in self.pins]
        count = len(self.pins)
        for index in range(count):
            pin = self.pins[index]
            for other_index in range(index + 1, count):
                if not (moving[index] or moving[other_index]):
                    continue
                other = self.pins[other_index]
                if abs(pin[0] - other[0]) < reach and abs(pin[1] - other[1]) < reach:
                    self.collide(pin, other, self.PIN_MASS, self.PIN_MASS, reach)

    def update(self, now):
        if self.thrown_at is None:
            if self.pressed(0):
                self.thrown_at = now
                x, angle = self.aim(now)
                self.ball = [x, self.ball_start_y, self.BALL_SPEED * math.sin(angle), -self.BALL_SPEED * math.cos(angle)]
            elif now - self.started > self.WAIT_MS:
                self.finish(0)
            return
        self.lean = read_lean(self.level_x, self.level_y, self.upside_down)[0]
        target = min(self.SIM_MS, now - self.thrown_at) // self.STEP_MS
        while self.simulated < target:
            self.step()
            self.simulated += 1
        if now - self.thrown_at >= self.SIM_MS + self.SHOW_MS:
            count = self.knocked()
            if count == 0:
                self.oops()
            self.finish(count)

    def draw(self, now):
        ui.clear()
        screen.pen = PANEL
        screen.rectangle(self.LANE_X, self.LANE_TOP, self.LANE_W, self.LANE_BOTTOM - self.LANE_TOP)
        screen.pen = DIM
        screen.rectangle(self.LANE_X - 6, self.LANE_TOP, 4, self.LANE_BOTTOM - self.LANE_TOP)
        screen.rectangle(self.LANE_X + self.LANE_W + 2, self.LANE_TOP, 4, self.LANE_BOTTOM - self.LANE_TOP)
        for x, y, _vx, _vy, home_x, home_y in self.pins:
            fallen = (x - home_x) ** 2 + (y - home_y) ** 2 > self.KNOCKED ** 2
            screen.pen = DIM if fallen else BRIGHT
            screen.circle(vec2(x, y), 3 if fallen else self.PIN)
        if self.thrown_at is None:
            x, angle = self.aim(now)
            y = self.ball_start_y
            screen.pen = DIM
            screen.line(vec2(x, y), vec2(x + math.sin(angle) * self.GUIDE, y - math.cos(angle) * self.GUIDE))
            screen.pen = ACCENT
            screen.circle(vec2(x, y), self.BALL)
            return
        ball_x, ball_y = self.ball[0], self.ball[1]
        if ball_y > self.LANE_TOP - self.BALL:
            screen.pen = ACCENT
            screen.circle(vec2(ball_x, ball_y), self.BALL)
        if now - self.thrown_at >= self.SIM_MS:
            count = self.knocked()
            label = "STRIKE!" if count == len(self.pins) else "miss" if count == 0 else "%d pins" % count
            screen.font = TITLE
            w, _h = screen.measure_text(label)
            ui.text_at(label, (self.LANE_X - w) / 2 if w < self.LANE_X - 8 else 4, 90, TITLE, ACCENT if count else DIM)

    @staticmethod
    def compare(host, guest):
        return compare_higher(host, guest)

    def describe(self, score):
        return "strike" if score == 10 else "%d pins" % score


GAMES = (
    QuickDraw, MashRace, TiltHole, FindFood, RockPaperScissors,
    StopClock, Simon, ArrowRush, CountDots, OddOneOut, Balance, FixPipe, TapTempo, Bowling,
)
