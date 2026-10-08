"""
Steer a snake that never stops. Eat, grow, and mind your own tail.

The snake always creeps forward and traces its own path exactly. Touching a wall
or your own body ends the run.

Controls:
* Left / Right = Steer
* Select = Start / restart
"""

import math
import micropython
import random

import hints

badge.mode(HIRES)
screen.antialias = image.X2

CX, CY = screen.width / 2, screen.height / 2

GRAY_1 = color.rgb(242, 245, 243)
GRAY_2 = color.rgb(228, 235, 230)
GRAY_4 = color.rgb(144, 150, 146)
GRAY_5 = color.rgb(35, 41, 37)
GRAY_6 = color.rgb(16, 20, 17)
GREEN_3 = color.rgb(95, 237, 131)
GREEN_4 = color.rgb(15, 191, 62)
GREEN_5 = color.rgb(8, 135, 43)

BACKGROUND = GRAY_6
PANEL = GRAY_5
TEXT = GRAY_2
DIM = GRAY_4
BRIGHT = GRAY_1
SNAKE = GREEN_3
EYE = GRAY_6

BODY = font.bacteria
TITLE = font.futile
HUGE = font.ignore

FOOD_FILL = font.food
FOOD_OUTLINE = font.food_outline
FOODS = ")*+-/279:;<>IJK"
FOOD_W = 14
FOOD_H = 16
FOOD_SCALE = 2
FOOD_BOB = 2.0
HUD_FOOD_SCALE = 1

HINT_STYLE = hints.Style(BRIGHT, DIM, BACKGROUND)
STEER_LIT = (BUTTON_LEFT, BUTTON_RIGHT)
START_LIT = (BUTTON_SELECT,)
HINT_SHAPE = STEER_LIT + START_LIT
HINT_RADIUS = 6

PLAYFIELD_DOT = color.rgb(36, 44, 39)
PLAYFIELD_ROWS = (0x80, 0x00, 0x00, 0x00, 0x08, 0x00, 0x00, 0x00)
PLAYFIELD = brush.pattern(PLAYFIELD_DOT, BACKGROUND, PLAYFIELD_ROWS)

HUD_H = 36
HUD_MARGIN = 10
METER_H = 3
METER_EMPTY = GRAY_5
METER_LAPS = (GREEN_3, GREEN_4, GREEN_5)

LEVEL_APPLES = 10
SPEED_STEP = 0.011
SPEED_MAX = 0.155

SPEED = 0.075
TURN = 0.0045
SPACING = 4.0
START_POINTS = 14
GROW_POINTS = 3
MAX_DT = 50

BODY_HALF = 2.6
HEAD_EXTRA = 2.1
WALL_MARGIN = 4
EAT_RADIUS = 15
NECK_SKIP = 8

BLOOM_ARGS = (60, 255, 7.5, 3.0)
BLOOM_PAD = 30

IMPACT_MS = 220
IMPACT_MAX = 7.0

TITLE_Y = 34
TITLE_SCALE = 3
TITLE_BOB = 4.0
PRIMER_Y = 178

GO_DIM = color.rgb(0, 0, 0, 150)
GO_HEADING_Y = 8
GO_COL_CX = (100, 220)
GO_ROW_Y = (66, 128)
GO_VALUE_DROP = 14
GO_RULE = GRAY_5
GO_RULE_TOP, GO_RULE_BOTTOM = 66, 178
GO_RULE_Y = 122
GO_RULE_LEFT, GO_RULE_RIGHT = 44, 276
GO_PROMPT_Y = 202

_sqrt = math.sqrt


@micropython.native
def build_ribbon(head, path, buf, body_half, head_extra):
    n = len(path) + 1
    total = n + n
    for i in range(n):
        if i == 0:
            cur = head
            a = head
        else:
            cur = path[i - 1]
            a = head if i == 1 else path[i - 2]
        b = path[i] if i < n - 1 else cur

        cx = cur.x
        cy = cur.y
        tx = a.x - b.x
        ty = a.y - b.y
        length = _sqrt(tx * tx + ty * ty)
        if length > 0.0:
            nx = -ty / length
            ny = tx / length
        else:
            nx = 0.0
            ny = 0.0

        nose = (i + 0.3) * 0.5
        if nose > 1.0:
            nose = 1.0
        tail = (n - 1 - i) * 0.25 + 0.25
        if tail > 1.0:
            tail = 1.0
        d = i - 3
        if d < 0:
            d = -d
        bulge = 1.0 - d / 3.0
        if bulge < 0.0:
            bulge = 0.0
        m = nose if nose < tail else tail
        half = (body_half + head_extra * bulge) * m

        ox = nx * half
        oy = ny * half
        lp = buf[i]
        lp.x = cx + ox
        lp.y = cy + oy
        rp = buf[total - 1 - i]
        rp.x = cx - ox
        rp.y = cy - oy


def draw_food(char, cx, cy, scale):
    x = cx - FOOD_W * scale / 2
    y = cy - FOOD_H * scale / 2
    at = vec2(x, y)
    transform = mat3().translate(at).scale(scale, scale).translate(vec2(-x, -y))
    screen.font = FOOD_FILL
    screen.pen = BRIGHT
    screen.text(char, at, transform=transform)
    screen.font = FOOD_OUTLINE
    screen.pen = BACKGROUND
    screen.text(char, at, transform=transform)


def text_width(text, typeface, scale=1):
    screen.font = typeface
    return screen.measure_text(text)[0] * scale


def write(text, x, y, typeface, pen, scale=1):
    screen.font = typeface
    screen.pen = pen
    if scale == 1:
        screen.text(text, x, y)
        return
    at = vec2(x, y)
    screen.text(text, at, transform=mat3().translate(at).scale(scale, scale).translate(vec2(-x, -y)))


def centred(text, y, typeface, pen, cx=CX, scale=1):
    write(text, cx - text_width(text, typeface, scale) / 2, y, typeface, pen, scale)


class Snake:
    def __init__(self):
        self.reset()

    def reset(self):
        self.heading = -math.pi / 2
        self.head = vec2(CX, CY + 40)
        self.target_points = START_POINTS
        self.buffer = []
        dx = -math.cos(self.heading) * SPACING
        dy = -math.sin(self.heading) * SPACING
        self.path = [vec2(self.head.x + dx * i, self.head.y + dy * i) for i in range(1, self.target_points + 1)]

    def update(self, dt):
        turn = TURN * (speed() / SPEED)
        if badge.held(BUTTON_LEFT):
            self.heading -= turn * dt
        if badge.held(BUTTON_RIGHT):
            self.heading += turn * dt

        step = speed() * dt
        self.head = vec2(self.head.x + math.cos(self.heading) * step, self.head.y + math.sin(self.heading) * step)

        front = self.path[0]
        if (self.head.x - front.x) ** 2 + (self.head.y - front.y) ** 2 >= SPACING * SPACING:
            self.path.insert(0, vec2(self.head.x, self.head.y))

        while len(self.path) > self.target_points:
            self.path.pop()

    def grow(self):
        self.target_points += GROW_POINTS

    def wander(self, dt):
        dx, dy = math.cos(self.heading), math.sin(self.heading)
        ax = self.head.x + dx * 46
        ay = self.head.y + dy * 46
        margin = WALL_MARGIN + 34
        if ax < margin or ax > screen.width - margin or ay < margin or ay > screen.height - margin:
            cross = dx * (CY - self.head.y) - dy * (CX - self.head.x)
            rate = TURN * dt * 1.6
            self.heading += rate if cross > 0 else -rate
        else:
            self.heading += math.sin(badge.ticks / 800.0) * TURN * dt * 0.25

    def glow(self):
        x0 = x1 = self.head.x
        y0 = y1 = self.head.y
        for point in self.path:
            if point.x < x0:
                x0 = point.x
            elif point.x > x1:
                x1 = point.x
            if point.y < y0:
                y0 = point.y
            elif point.y > y1:
                y1 = point.y

        x0 = max(0, int(x0) - BLOOM_PAD)
        y0 = max(0, int(y0) - BLOOM_PAD)
        x1 = min(screen.width, int(x1) + BLOOM_PAD)
        y1 = min(screen.height, int(y1) + BLOOM_PAD)
        if x1 > x0 and y1 > y0:
            screen.window(rect(x0, y0, x1 - x0, y1 - y0)).bloom(*BLOOM_ARGS)

    def hit_wall(self):
        return (self.head.x < WALL_MARGIN or self.head.x > screen.width - WALL_MARGIN
                or self.head.y < HUD_H + WALL_MARGIN or self.head.y > screen.height - WALL_MARGIN)

    def hit_self(self):
        limit = (BODY_HALF * 2) ** 2
        for point in self.path[NECK_SKIP:]:
            if (self.head.x - point.x) ** 2 + (self.head.y - point.y) ** 2 < limit:
                return True
        return False

    def draw(self):
        n = len(self.path) + 1
        if n < 2:
            return

        total = n + n
        buffer = self.buffer
        while len(buffer) < total:
            buffer.append(vec2(0.0, 0.0))
        if len(buffer) > total:
            del buffer[total:]

        build_ribbon(self.head, self.path, buffer, BODY_HALF, HEAD_EXTRA)

        screen.pen = SNAKE
        screen.shape(shape.custom(buffer))

        self.draw_head(self.head, self.path[0])

    def draw_head(self, nose, behind):
        dx, dy = nose.x - behind.x, nose.y - behind.y
        length = math.sqrt(dx * dx + dy * dy)
        if length == 0:
            return
        dx, dy = dx / length, dy / length
        nx, ny = -dy, dx

        ex = nose.x - dx * 3.0
        ey = nose.y - dy * 3.0
        screen.pen = EYE
        for side in (-1, 1):
            screen.shape(shape.circle(ex + nx * 1.9 * side, ey + ny * 1.9 * side, 1.2))


class Food:
    def __init__(self):
        self.position = vec2(CX, CY)
        self.index = -1
        self.respawn(None)

    def respawn(self, snake):
        margin = WALL_MARGIN + FOOD_H * FOOD_SCALE // 2
        x0, x1 = margin, screen.width - margin
        y0, y1 = HUD_H + margin, screen.height - margin
        self.index = (self.index + 1) % len(FOODS)
        self.char = FOODS[self.index]
        for _ in range(30):
            candidate = vec2(random.randint(x0, x1), random.randint(y0, y1))
            if snake is None:
                self.position = candidate
                return
            dx = candidate.x - snake.head.x
            dy = candidate.y - snake.head.y
            if dx * dx + dy * dy > 60 * 60:
                self.position = candidate
                return
        self.position = candidate

    def draw(self):
        bob = round(math.sin(badge.ticks / 300.0) * FOOD_BOB)
        draw_food(self.char, self.position.x, self.position.y + bob, FOOD_SCALE)


run_started = None
run_ended = None
impact_at = None


def draw_impact():
    if impact_at is None:
        return
    age = badge.ticks - impact_at
    if 0 <= age < IMPACT_MS:
        screen.chromatic(IMPACT_MAX * (1.0 - age / IMPACT_MS))


def elapsed():
    if run_started is None:
        return "00:00"
    end = badge.ticks if run_ended is None else run_ended
    t = (end - run_started) // 1000
    return "%02d:%02d" % (t // 60 % 100, t % 60)


def level():
    return score // LEVEL_APPLES + 1


def speed():
    return min(SPEED_MAX, SPEED + (level() - 1) * SPEED_STEP)


def draw_top_bar():
    screen.pen = PANEL
    screen.rectangle(0, 0, screen.width, HUD_H)

    write("level", HUD_MARGIN, 4, BODY, DIM)
    write("%02d" % level(), HUD_MARGIN, 15, TITLE, TEXT)

    count = "x%02d" % score
    icon_w = FOOD_W * HUD_FOOD_SCALE
    group = icon_w + 6 + max(text_width(count, TITLE), text_width("eaten", BODY))
    gx = CX - group / 2
    draw_food(food.char, gx + icon_w / 2, HUD_H / 2 - 2, HUD_FOOD_SCALE)
    write("eaten", gx + icon_w + 6, 4, BODY, DIM)
    write(count, gx + icon_w + 6, 15, TITLE, TEXT)

    stamp = elapsed()
    right = screen.width - HUD_MARGIN
    write("time", right - text_width("time", BODY), 4, BODY, DIM)
    write(stamp, right - text_width(stamp, TITLE), 15, TITLE, TEXT)

    done = (score % LEVEL_APPLES) / LEVEL_APPLES
    screen.pen = METER_EMPTY
    screen.rectangle(0, HUD_H - METER_H, screen.width, METER_H)
    screen.pen = METER_LAPS[(level() - 1) % len(METER_LAPS)]
    screen.rectangle(0, HUD_H - METER_H, screen.width * done, METER_H)


def draw_hint_with_label(label, lit, cx, cy):
    hints.draw_hint(HINT_STYLE, HINT_SHAPE, lit, cx, cy, HINT_RADIUS)
    centred(label, cy + hints.hint_height(HINT_SHAPE, HINT_RADIUS) / 2 + 6, BODY, TEXT, cx)


def draw_primer(y):
    draw_hint_with_label("steer", STEER_LIT, CX - 70, y)
    draw_hint_with_label("start", START_LIT, CX + 70, y)


def draw_title():
    bob = math.sin(badge.ticks / 520.0) * TITLE_BOB
    centred("snake", TITLE_Y + bob, HUGE, SNAKE, scale=TITLE_SCALE)


snake = Snake()
food = Food()
score = 0


def ground(top):
    screen.pen = BACKGROUND
    screen.clear()
    screen.pen = PLAYFIELD
    screen.rectangle(0, top, screen.width, screen.height - top)


def draw_figures():
    screen.pen = GO_DIM
    screen.rectangle(0, 0, screen.width, screen.height)

    centred("game over", GO_HEADING_Y, HUGE, SNAKE, scale=2)

    screen.pen = GO_RULE
    screen.rectangle(CX, GO_RULE_TOP, 1, GO_RULE_BOTTOM - GO_RULE_TOP)
    screen.rectangle(GO_RULE_LEFT, GO_RULE_Y, GO_RULE_RIGHT - GO_RULE_LEFT, 1)

    figures = (
        ("level", "%02d" % level()),
        ("eaten", "%02d" % score),
        ("length", "%d" % (len(snake.path) + 1)),
        ("time", elapsed()),
    )
    for index, (label, value) in enumerate(figures):
        cx = GO_COL_CX[index % 2]
        y = GO_ROW_Y[index // 2]
        centred(label, y, BODY, DIM, cx)
        centred(value, y + GO_VALUE_DROP, TITLE, TEXT, cx, scale=2)

    draw_hint_with_label("again", START_LIT, CX, GO_PROMPT_Y)


def titles():
    snake.reset()

    while True:
        ground(0)
        step = min(badge.ticks_delta, MAX_DT)
        snake.wander(step)
        snake.update(step)
        snake.draw()
        snake.glow()

        draw_title()
        draw_primer(PRIMER_Y)
        badge.update()

        if badge.pressed(BUTTON_SELECT):
            return


def play():
    global score, run_started, run_ended, impact_at

    snake.reset()
    food.respawn(snake)
    score = 0
    run_started, run_ended, impact_at = badge.ticks, None, None

    while True:
        ground(HUD_H)
        snake.update(min(badge.ticks_delta, MAX_DT))

        dx = snake.head.x - food.position.x
        dy = snake.head.y - food.position.y
        if dx * dx + dy * dy < EAT_RADIUS * EAT_RADIUS:
            snake.grow()
            score += 1
            food.respawn(snake)
            impact_at = badge.ticks

        snake.draw()
        snake.glow()
        food.draw()
        draw_top_bar()
        draw_impact()
        badge.update()

        if snake.hit_wall() or snake.hit_self():
            run_ended = badge.ticks
            return


def game_over():
    while True:
        ground(0)
        snake.draw()
        snake.glow()
        food.draw()
        draw_figures()
        draw_impact()
        badge.update()

        if badge.pressed(BUTTON_SELECT):
            return


while True:
    titles()
    play()
    game_over()
