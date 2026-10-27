# Port of badger/home's MIT-licensed Universe 2025 Gitris game.
import os
import random

from badgeware import State

APP_DIR = "/system/apps/gitris"
os.chdir(APP_DIR)

badge.mode(HIRES | VSYNC)
W, H = screen.width, screen.height
GRID_W, GRID_H = 10, 20
CELL = (H - 40) // GRID_H
PF_X, PF_Y = 12, 10
SIDE_X = PF_X + GRID_W * CELL + 18
SIDE_W = W - SIDE_X - 12

COL_BG = color.rgb(13, 17, 23)
COL_GRID = color.rgb(48, 54, 61)
COL_TEXT = color.rgb(240, 246, 252)
COL_DIM = color.rgb(139, 148, 158)
COL_GHOST = color.rgb(80, 90, 104)
CONFLICT_COLOR = color.rgb(87, 96, 106)
COLORS = [
    color.rgb(61, 199, 98),
    color.rgb(250, 219, 94),
    color.rgb(191, 128, 255),
    color.rgb(70, 212, 143),
    color.rgb(255, 121, 135),
    color.rgb(90, 150, 255),
    color.rgb(255, 170, 108),
]

SHAPES = [
    [
        [(0, 1), (1, 1), (2, 1), (3, 1)],
        [(2, 0), (2, 1), (2, 2), (2, 3)],
        [(0, 2), (1, 2), (2, 2), (3, 2)],
        [(1, 0), (1, 1), (1, 2), (1, 3)],
    ],
    [[(1, 0), (2, 0), (1, 1), (2, 1)]] * 4,
    [
        [(1, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (2, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (1, 2)],
        [(1, 0), (0, 1), (1, 1), (1, 2)],
    ],
    [
        [(1, 0), (2, 0), (0, 1), (1, 1)],
        [(1, 0), (1, 1), (2, 1), (2, 2)],
        [(1, 1), (2, 1), (0, 2), (1, 2)],
        [(0, 0), (0, 1), (1, 1), (1, 2)],
    ],
    [
        [(0, 0), (1, 0), (1, 1), (2, 1)],
        [(2, 0), (1, 1), (2, 1), (1, 2)],
        [(0, 1), (1, 1), (1, 2), (2, 2)],
        [(1, 0), (0, 1), (1, 1), (0, 2)],
    ],
    [
        [(0, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (2, 0), (1, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (2, 2)],
        [(1, 0), (1, 1), (0, 2), (1, 2)],
    ],
    [
        [(2, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (1, 2), (2, 2)],
        [(0, 1), (1, 1), (2, 1), (0, 2)],
        [(0, 0), (1, 0), (1, 1), (1, 2)],
    ],
]

KICKS = {
    (0, 1): [(0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)],
    (1, 2): [(0, 0), (1, 0), (1, -1), (0, 2), (1, 2)],
    (2, 3): [(0, 0), (1, 0), (1, 1), (0, -2), (1, -2)],
    (3, 0): [(0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)],
}

record = {"hiscore": 0}
State.load("gitris", record)
if not isinstance(record["hiscore"], int) or record["hiscore"] < 0:
    print("Gitris: invalid saved high score; starting with zero.")
    record["hiscore"] = 0

clock_ms = 0
state = {
    "screen": "title",
    "score": 0,
    "level": 1,
    "lines": 0,
    "hiscore": record["hiscore"],
    "board": None,
    "bag": [],
    "curr": None,
    "next": None,
    "x": 3,
    "y": 0,
    "rot": 0,
    "fall_ms": 800,
    "last_fall": 0,
    "move_direction": 0,
    "next_move": 0,
    "pieces": 0,
    "conflict_every": 12,
    "save_error": False,
}
toast = {"at": 0, "text": ""}


def _new_board():
    return [[0] * GRID_W for _ in range(GRID_H)]


def _refill_bag():
    bag = list(range(len(SHAPES)))
    for i in range(len(bag) - 1, 0, -1):
        j = random.getrandbits(30) % (i + 1)
        bag[i], bag[j] = bag[j], bag[i]
    return bag


def _toast(text):
    toast["at"], toast["text"] = clock_ms, text


def _to_gameover():
    if state["score"] > state["hiscore"]:
        state["hiscore"] = state["score"]
        try:
            State.save("gitris", {"hiscore": state["hiscore"]})
            state["save_error"] = False
        except OSError as error:
            print("Gitris: high score could not be saved:", error)
            state["save_error"] = True
    state["screen"] = "gameover"


def _push_conflict_row():
    if any(state["board"][0]):
        _to_gameover()
        return False
    state["board"].pop(0)
    row = [8] * GRID_W
    row[random.getrandbits(30) % GRID_W] = 0
    state["board"].append(row)
    _toast("Merge conflict!")
    return True


def _spawn():
    if not state["bag"]:
        state["bag"] = _refill_bag()
    state["curr"] = state["bag"].pop()
    state["rot"], state["x"], state["y"] = 0, 3, 0
    if not state["bag"]:
        state["bag"] = _refill_bag()
    state["next"] = state["bag"][-1]
    state["pieces"] += 1
    cadence = state["conflict_every"]
    if state["screen"] == "play" and cadence > 0 and state["pieces"] % cadence == 0:
        if not _push_conflict_row():
            return
    if _collides(state["x"], state["y"], state["rot"]):
        _to_gameover()


def _cells_at(x, y, rotation, piece=None):
    index = state["curr"] if piece is None else piece
    for dx, dy in SHAPES[index][rotation % 4]:
        yield x + dx, y + dy


def _collides(x, y, rotation):
    for cx, cy in _cells_at(x, y, rotation):
        if cx < 0 or cx >= GRID_W or cy >= GRID_H:
            return True
        if cy >= 0 and state["board"][cy][cx]:
            return True
    return False


def _clear_lines():
    kept = [row for row in state["board"] if not all(row)]
    cleared = GRID_H - len(kept)
    if not cleared:
        return
    state["board"] = [[0] * GRID_W for _ in range(cleared)] + kept
    state["score"] += {1: 40, 2: 100, 3: 300, 4: 1200}.get(cleared, 0) * state["level"]
    state["lines"] += cleared
    state["level"] = 1 + state["lines"] // 10
    state["fall_ms"] = max(120, 800 - (state["level"] - 1) * 60)
    _toast(("Committed.", "PR ready.", "Rebase clean!", "Massive merge!")[min(cleared, 4) - 1])


def _lock_piece():
    cells = list(_cells_at(state["x"], state["y"], state["rot"]))
    if any(cy < 0 for _, cy in cells):
        _to_gameover()
        return
    for cx, cy in cells:
        state["board"][cy][cx] = state["curr"] + 1
    _clear_lines()
    _spawn()


def _move(dx, dy):
    x, y = state["x"] + dx, state["y"] + dy
    if _collides(x, y, state["rot"]):
        return False
    state["x"], state["y"] = x, y
    return True


def _rotate_cw():
    old = state["rot"]
    new = (old + 1) % 4
    for dx, dy in KICKS[(old, new)]:
        if not _collides(state["x"] + dx, state["y"] + dy, new):
            state["x"] += dx
            state["y"] += dy
            state["rot"] = new
            return True
    return False


def _hard_drop():
    while _move(0, 1):
        pass
    _lock_piece()


def _ghost_y():
    y = state["y"]
    while not _collides(state["x"], y + 1, state["rot"]):
        y += 1
    return y


def _reset_run():
    state["board"] = _new_board()
    state["bag"] = _refill_bag()
    state["score"], state["lines"], state["pieces"] = 0, 0, 0
    state["level"], state["fall_ms"] = 1, 800
    state["move_direction"] = 0
    toast["text"] = ""
    _spawn()


def _to_game():
    state["screen"] = "play"
    state["last_fall"] = clock_ms
    state["move_direction"] = 0


def _down(button):
    return badge.pressed(button) or badge.held(button)


def _handle_play():
    if badge.pressed(BUTTON_MENU) or badge.pressed(BUTTON_BACK):
        state["screen"] = "pause"
        return
    if badge.pressed(BUTTON_UP):
        _rotate_cw()

    direction = int(_down(BUTTON_RIGHT)) - int(_down(BUTTON_LEFT))
    if direction != state["move_direction"]:
        state["move_direction"] = direction
        if direction:
            _move(direction, 0)
            state["next_move"] = clock_ms + 150
    elif direction and clock_ms >= state["next_move"]:
        _move(direction, 0)
        state["next_move"] = clock_ms + 45

    if badge.pressed(BUTTON_SELECT):
        _hard_drop()
        state["last_fall"] = clock_ms
        return

    soft_drop = _down(BUTTON_DOWN)
    interval = 65 if soft_drop else state["fall_ms"]
    if badge.pressed(BUTTON_DOWN) or clock_ms - state["last_fall"] >= interval:
        if _move(0, 1):
            if soft_drop:
                state["score"] += 1
        else:
            _lock_piece()
        state["last_fall"] = clock_ms


def _fill(pen, x, y, width, height):
    screen.pen = pen
    screen.rectangle(x, y, width, height)


def _text(text, x, y, pen=COL_TEXT, typeface=None):
    screen.font = font.nope if typeface is None else typeface
    screen.pen = pen
    screen.text(str(text), x, y)


def _fit(text, width):
    screen.font = font.nope
    while text and screen.measure_text(text)[0] > width:
        text = text[:-1]
    return text


def _draw_grid():
    _fill(COL_BG, 0, 0, W, H)
    _fill(COL_GRID, PF_X - 2, PF_Y - 2, GRID_W * CELL + 4, GRID_H * CELL + 4)
    _fill(COL_BG, PF_X, PF_Y, GRID_W * CELL, GRID_H * CELL)


def _draw_cell(x, y, pen):
    if 0 <= x < GRID_W and 0 <= y < GRID_H:
        _fill(pen, PF_X + x * CELL, PF_Y + y * CELL, CELL - 1, CELL - 1)


def _draw_board():
    for y, row in enumerate(state["board"]):
        for x, value in enumerate(row):
            if value:
                _draw_cell(x, y, CONFLICT_COLOR if value == 8 else COLORS[value - 1])


def _draw_piece(y, ghost=False):
    pen = COL_GHOST if ghost else COLORS[state["curr"]]
    for x, cy in _cells_at(state["x"], y, state["rot"]):
        _draw_cell(x, cy, pen)


def _draw_sidebar():
    for label, key, y in (
        ("COMMITS", "score", 12),
        ("RELEASE", "level", 58),
        ("MERGES", "lines", 104),
        ("BEST BUILD", "hiscore", 150),
    ):
        _text(label, SIDE_X, y, COL_DIM)
        _text(state[key], SIDE_X, y + 14, typeface=font.ignore)
    _text("NEXT PATCH", SIDE_X, 194, COL_DIM)
    for x, y in SHAPES[state["next"]][0]:
        _fill(COLORS[state["next"]], SIDE_X + x * 7, 212 + y * 7, 6, 6)


def _draw_title():
    _fill(COL_BG, 0, 0, W, H)
    _text("GITRIS", 12, 14, COLORS[0], font.ignore)
    for text, y in (
        ("LEFT / RIGHT: move", 62),
        ("UP: rotate", 84),
        ("DOWN: soft drop", 106),
        ("SELECT: hard drop", 128),
        ("MENU / BACK: pause", 150),
        ("HOME: badge menu", 172),
        ("SELECT to start", 202),
        ("Best build: " + str(state["hiscore"]), 222),
    ):
        _text(text, 12, y)


def _draw_overlay(title, first, second):
    _fill(color.rgb(0, 0, 0, 220), 0, 0, W, H)
    _text(title, 12, 64, typeface=font.ignore)
    _text(first, 12, 112)
    _text(second, 12, 138)
    if state["save_error"]:
        _text("High score could not be saved.", 12, 174, COLORS[4])


def update():
    global clock_ms
    clock_ms += max(0, badge.ticks_delta)
    mode = state["screen"]
    if mode == "title":
        if badge.pressed(BUTTON_SELECT) or badge.pressed(BUTTON_UP):
            _reset_run()
            _to_game()
    elif mode == "play":
        _handle_play()
    elif mode == "pause":
        if badge.pressed(BUTTON_SELECT) or badge.pressed(BUTTON_MENU):
            _to_game()
        elif badge.pressed(BUTTON_BACK):
            state["screen"] = "title"
    elif mode == "gameover":
        if badge.pressed(BUTTON_SELECT) or badge.pressed(BUTTON_BACK):
            state["screen"] = "title"

    mode = state["screen"]
    if mode == "title":
        _draw_title()
        return
    _draw_grid()
    _draw_board()
    if mode in ("play", "pause"):
        _draw_piece(_ghost_y(), ghost=True)
        _draw_piece(state["y"])
    _draw_sidebar()
    if mode == "pause":
        _draw_overlay("Pipeline paused", "SELECT: resume", "BACK: title screen")
    elif mode == "gameover":
        _draw_overlay("Build failed", "SELECT: title screen", "HOME: badge menu")
    else:
        text = toast["text"] if clock_ms - toast["at"] < 1400 else ""
        _text(_fit(text or "MENU: pause", GRID_W * CELL), PF_X, H - 20, COL_DIM)


_reset_run()
run(update)
