import os
import sys

APP_DIR = "/system/apps/mona_slice"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

from badgeware import State

badge.mode(HIRES | VSYNC)
screen.font = font.nope

GRID_W = 36
GRID_H = 20
CELL = 8
BOARD_X = 16
BOARD_Y = 42
BOARD_W = GRID_W * CELL
BOARD_H = GRID_H * CELL
BALL_R = 6
SPRITE_HALF = 12
GOAL = 75
MAX_MONAS = 5
CUT_SPEED = 28
CURSOR_REPEAT = 0.085

INK = color.rgb(20, 15, 41)
PANEL = color.rgb(38, 25, 67)
FIELD = color.rgb(20, 13, 37)
MINT = color.rgb(112, 255, 215)
PINK = color.rgb(255, 124, 201)
LAVENDER = color.rgb(171, 135, 255)
WHITE = color.rgb(255, 240, 255)
GOLD = color.rgb(255, 220, 112)

mona_sprites = image.load("assets/mona.png").spritesheet(7, 2)
mona_left_sprites = image.load("assets/mona_left.png").spritesheet(7, 2)
best = {"percent": 0, "level": 1}
State.load("mona_slice", best)

state = "title"
grid = []
walls = []
monas = []
level = 1
cursor_x = GRID_W // 2
cursor_y = GRID_H // 2
cut_axis = "horizontal"
cut = None
lives = 3
percent = 0
cuts = 0
repeat_timer = 0


def new_game():
    global lives, level

    lives = 3
    level = 1
    start_level(level)


def start_level(next_level):
    global state, grid, walls, monas, cursor_x, cursor_y, cut_axis, cut
    global percent, cuts, level

    level = next_level
    grid = [[False for _ in range(GRID_W)] for _ in range(GRID_H)]
    walls = [[False for _ in range(GRID_W)] for _ in range(GRID_H)]
    speed = 1 + min(level - 1, 8) * 0.1
    starts = (
        (0.43, 0.53, 49, 34),
        (0.68, 0.35, -38, 46),
        (0.30, 0.72, 54, -37),
        (0.74, 0.70, -43, -52),
        (0.49, 0.27, 61, 42),
    )
    monas = []
    for x, y, vx, vy in starts[:min(level, MAX_MONAS)]:
        monas.append({
            "x": BOARD_X + BOARD_W * x,
            "y": BOARD_Y + BOARD_H * y,
            "vx": vx * speed,
            "vy": vy * speed,
        })
    cursor_x = GRID_W // 2
    cursor_y = GRID_H // 2
    cut_axis = "horizontal"
    cut = None
    percent = 0
    cuts = 0
    state = "playing"


def blocked_at(x, y):
    gx = int((x - BOARD_X) // CELL)
    gy = int((y - BOARD_Y) // CELL)
    if gx < 0 or gx >= GRID_W or gy < 0 or gy >= GRID_H:
        return True
    return grid[gy][gx]


def update_ball(mona, dt):
    next_x = mona["x"] + mona["vx"] * dt
    min_x = BOARD_X + SPRITE_HALF
    max_x = BOARD_X + BOARD_W - SPRITE_HALF
    if next_x < min_x:
        mona["x"] = min_x
        mona["vx"] = abs(mona["vx"])
    elif next_x > max_x:
        mona["x"] = max_x
        mona["vx"] = -abs(mona["vx"])
    elif blocked_at(next_x + (BALL_R if mona["vx"] > 0 else -BALL_R), mona["y"]):
        mona["vx"] = -mona["vx"]
    else:
        mona["x"] = next_x

    next_y = mona["y"] + mona["vy"] * dt
    min_y = BOARD_Y + SPRITE_HALF
    max_y = BOARD_Y + BOARD_H - SPRITE_HALF
    if next_y < min_y:
        mona["y"] = min_y
        mona["vy"] = abs(mona["vy"])
    elif next_y > max_y:
        mona["y"] = max_y
        mona["vy"] = -abs(mona["vy"])
    elif blocked_at(mona["x"], next_y + (BALL_R if mona["vy"] > 0 else -BALL_R)):
        mona["vy"] = -mona["vy"]
    else:
        mona["y"] = next_y


def move_cursor():
    global cursor_x, cursor_y, repeat_timer

    direction = None
    if badge.held(BUTTON_LEFT):
        direction = (-1, 0)
    elif badge.held(BUTTON_RIGHT):
        direction = (1, 0)
    elif badge.held(BUTTON_UP):
        direction = (0, -1)
    elif badge.held(BUTTON_DOWN):
        direction = (0, 1)

    if direction is None:
        repeat_timer = 0
        return

    repeat_timer -= badge.ticks_delta / 1000
    if repeat_timer > 0:
        return

    repeat_timer = CURSOR_REPEAT
    cursor_x = max(0, min(GRID_W - 1, cursor_x + direction[0]))
    cursor_y = max(0, min(GRID_H - 1, cursor_y + direction[1]))


def cell_blocked(x, y):
    return grid[y][x] or walls[y][x]


def cut_extent(dx, dy):
    # Pass through captured cells until open space is reached, then stop at the next blocker.
    seen_open = not cell_blocked(cursor_x, cursor_y)
    step = 1
    while True:
        x = cursor_x + dx * step
        y = cursor_y + dy * step
        if x < 0 or x >= GRID_W or y < 0 or y >= GRID_H:
            return step - 0.5 if seen_open else 0
        if cell_blocked(x, y):
            if seen_open:
                return step - 0.5
        else:
            seen_open = True
        step += 1


def start_cut():
    global cut

    if cut_axis == "horizontal":
        negative = cut_extent(-1, 0)
        positive = cut_extent(1, 0)
    else:
        negative = cut_extent(0, -1)
        positive = cut_extent(0, 1)
    if negative <= 0 and positive <= 0:
        return
    cut = {
        "axis": cut_axis,
        "negative": negative,
        "positive": positive,
        "negative_length": 0,
        "positive_length": 0,
    }


def cut_hits_mona(negative_length, positive_length, mona):
    center_x = BOARD_X + cursor_x * CELL + CELL / 2
    center_y = BOARD_Y + cursor_y * CELL + CELL / 2
    if cut["axis"] == "horizontal":
        along = mona["x"] - center_x
        return (
            abs(mona["y"] - center_y) <= BALL_R + 2
            and -negative_length * CELL - BALL_R <= along <= positive_length * CELL + BALL_R
        )
    along = mona["y"] - center_y
    return (
        abs(mona["x"] - center_x) <= BALL_R + 2
        and -negative_length * CELL - BALL_R <= along <= positive_length * CELL + BALL_R
    )


def fill_regions():
    global percent

    visited = [[False for _ in range(GRID_W)] for _ in range(GRID_H)]
    queue = []
    for mona in monas:
        start_x = max(0, min(GRID_W - 1, int((mona["x"] - BOARD_X) // CELL)))
        start_y = max(0, min(GRID_H - 1, int((mona["y"] - BOARD_Y) // CELL)))
        if not grid[start_y][start_x] and not walls[start_y][start_x] and not visited[start_y][start_x]:
            queue.append(start_y * GRID_W + start_x)
            visited[start_y][start_x] = True

    index = 0
    while index < len(queue):
        cell = queue[index]
        index += 1
        x = cell % GRID_W
        y = cell // GRID_W
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if (
                0 <= nx < GRID_W
                and 0 <= ny < GRID_H
                and not grid[ny][nx]
                and not walls[ny][nx]
                and not visited[ny][nx]
            ):
                visited[ny][nx] = True
                queue.append(ny * GRID_W + nx)

    filled = 0
    for y in range(GRID_H):
        for x in range(GRID_W):
            if not visited[y][x] and not walls[y][x]:
                grid[y][x] = True
            if grid[y][x] or walls[y][x]:
                filled += 1
    percent = int(filled * 100 / (GRID_W * GRID_H))


def finish_cut():
    global cut, cuts, state, best

    negative_cells = int(cut["negative"])
    positive_cells = int(cut["positive"])
    if cut["axis"] == "horizontal":
        for x in range(cursor_x - negative_cells, cursor_x + positive_cells + 1):
            walls[cursor_y][x] = True
            grid[cursor_y][x] = True
    else:
        for y in range(cursor_y - negative_cells, cursor_y + positive_cells + 1):
            walls[y][cursor_x] = True
            grid[y][cursor_x] = True
    cut = None
    cuts += 1
    fill_regions()
    if percent >= GOAL:
        state = "level_clear"
        if level > best["level"]:
            best["level"] = level
            State.save("mona_slice", best)


def update_cut(dt):
    global cut, lives, state

    cut["negative_length"] = min(
        cut["negative"],
        cut["negative_length"] + CUT_SPEED * dt,
    )
    cut["positive_length"] = min(
        cut["positive"],
        cut["positive_length"] + CUT_SPEED * dt,
    )
    for mona in monas:
        if cut_hits_mona(cut["negative_length"], cut["positive_length"], mona):
            cut = None
            lives -= 1
            if lives <= 0:
                state = "lost"
            return
    if (
        cut["negative_length"] >= cut["negative"]
        and cut["positive_length"] >= cut["positive"]
    ):
        finish_cut()


def draw_board():
    screen.pen = PANEL
    screen.shape(shape.rounded_rectangle(BOARD_X - 3, BOARD_Y - 3, BOARD_W + 6, BOARD_H + 6, 5))
    screen.pen = FIELD
    screen.shape(shape.rectangle(BOARD_X, BOARD_Y, BOARD_W, BOARD_H))

    for y in range(GRID_H):
        for x in range(GRID_W):
            if grid[y][x]:
                screen.pen = LAVENDER if (x + y) % 4 else PINK
                screen.shape(shape.rectangle(BOARD_X + x * CELL, BOARD_Y + y * CELL, CELL, CELL))

    if cut is not None:
        center_x = BOARD_X + cursor_x * CELL + CELL / 2
        center_y = BOARD_Y + cursor_y * CELL + CELL / 2
        negative_distance = cut["negative_length"] * CELL
        positive_distance = cut["positive_length"] * CELL
        screen.pen = MINT
        if cut["axis"] == "horizontal":
            screen.line(
                center_x - negative_distance,
                center_y,
                center_x + positive_distance,
                center_y,
            )
        else:
            screen.line(
                center_x,
                center_y - negative_distance,
                center_x,
                center_y + positive_distance,
            )
    else:
        x = BOARD_X + cursor_x * CELL
        y = BOARD_Y + cursor_y * CELL
        center_x = x + CELL / 2
        center_y = y + CELL / 2
        screen.pen = GOLD
        screen.shape(shape.rectangle(x + 1, y + 1, CELL - 2, CELL - 2))
        screen.pen = FIELD
        screen.shape(shape.rectangle(x + 3, y + 3, CELL - 6, CELL - 6))
        screen.pen = MINT
        if cut_axis == "horizontal":
            screen.line(center_x - 10, center_y, center_x - 4, center_y)
            screen.line(center_x + 4, center_y, center_x + 10, center_y)
        else:
            screen.line(center_x, center_y - 10, center_x, center_y - 4)
            screen.line(center_x, center_y + 4, center_x, center_y + 10)
        screen.pen = GOLD
        screen.shape(shape.rectangle(center_x - 3, center_y - 3, 6, 6))
        screen.pen = FIELD
        screen.shape(shape.rectangle(center_x - 1, center_y - 1, 2, 2))

    for index, mona in enumerate(monas):
        frame = int(badge.ticks / 115 + index * 2) % 7
        sprites = mona_left_sprites if mona["vx"] < 0 else mona_sprites
        sprite = sprites.sprite(frame, 0)
        screen.blit(sprite, vec2(mona["x"] - SPRITE_HALF, mona["y"] - SPRITE_HALF))


def draw_hud():
    screen.pen = WHITE
    screen.text("MONA SLICE", 16, 8)
    screen.pen = MINT
    screen.text("LV %d  %d%%/%d%%" % (level, percent, GOAL), 166, 8)
    screen.pen = PINK
    screen.text("PAWS %d" % lives, 272, 8)

    screen.pen = PANEL
    screen.shape(shape.rounded_rectangle(16, 210, 288, 9, 4))
    if percent:
        screen.pen = MINT
        screen.shape(shape.rounded_rectangle(16, 210, max(2, int(288 * percent / 100)), 9, 4))
    screen.pen = WHITE
    if cut is None:
        screen.text("ARROWS MOVE   SELECT CUT   BACK: %s" % cut_axis.upper(), 16, 224)
    else:
        screen.text("MONA IS ON THE MOVE!", 16, 224)


def draw_title():
    screen.pen = INK
    screen.shape(shape.rectangle(0, 0, screen.width, screen.height))
    screen.pen = LAVENDER
    screen.shape(shape.circle(160, 74, 40))
    frame = int(badge.ticks / 115) % 7
    screen.blit(mona_sprites.sprite(frame, 0), vec2(148, 62))
    centered_text("MONA SLICE", 19, WHITE)
    centered_text("Snip the space. Keep Mona safe!", 122, MINT)
    centered_text("Carve off empty corners to claim them.", 146, WHITE)
    centered_text("Reach 75% before your paws run out.", 164, WHITE)
    if int(badge.ticks / 500) % 2:
        centered_text("PRESS SELECT TO PLAY", 194, GOLD)


def centered_text(text, y, pen):
    width, _ = screen.measure_text(text)
    screen.pen = pen
    screen.text(text, (screen.width - width) / 2, y)


def draw_end():
    screen.pen = INK
    screen.shape(shape.rectangle(0, 0, screen.width, screen.height))
    cleared = state == "level_clear"
    centered_text("LEVEL CLEARED!" if cleared else "OH NO, MONA!", 64, MINT if cleared else PINK)
    centered_text("Level %d   Territory: %d%%" % (level, percent), 105, WHITE)
    centered_text("Monas: %d   Best level: %d" % (len(monas), best["level"]), 128, WHITE)
    if int(badge.ticks / 500) % 2:
        prompt = "SELECT: NEXT LEVEL" if cleared else "SELECT: TRY AGAIN"
        centered_text(prompt, 171, GOLD)


def update():
    global cut_axis

    dt = min(0.05, max(0, badge.ticks_delta / 1000))
    if state == "title":
        draw_title()
        if badge.pressed(BUTTON_SELECT):
            new_game()
        return

    if state == "playing":
        if cut is None:
            move_cursor()
            if badge.pressed(BUTTON_BACK):
                cut_axis = "vertical" if cut_axis == "horizontal" else "horizontal"
            if badge.pressed(BUTTON_SELECT):
                start_cut()
        for mona in monas:
            update_ball(mona, dt)
        if cut is not None:
            update_cut(dt)
        draw_board()
        draw_hud()
        return

    draw_end()
    if badge.pressed(BUTTON_SELECT) and state == "level_clear":
        start_level(level + 1)
    elif badge.pressed(BUTTON_SELECT):
        new_game()


run(update)
