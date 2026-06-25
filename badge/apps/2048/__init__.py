# 2048 for the GitHub Universe 2025 Tufty badge
#
# Controls:
#   A    = slide left
#   B    = slide right
#   UP   = slide up
#   DOWN = slide down
#   HOME = back to launcher (handled by the system)
#
# Join matching tiles to reach the 2048 tile. Progress and best score
# are saved between sessions.

import gc
import math
import random

from badgeware import screen, io, brushes, shapes, PixelFont, Image, State, run

# ---------------- Layout ----------------
W, H = 160, 120
TILE = 26
GAP = 2
STEP = TILE + GAP            # distance between tile origins
BOARD_X, BOARD_Y = 2, 3      # top-left of the board background
OX = BOARD_X + GAP           # first tile origin x
OY = BOARD_Y + GAP           # first tile origin y
PANEL_X = 118

# Animation timing (milliseconds)
SLIDE_MS = 90
SPAWN_MS = 130
MERGE_MS = 150
TOAST_MS = 1600

# ---------------- Palette (classic 2048) ----------------
BG_PAGE = brushes.color(250, 248, 239)
BG_BOARD = brushes.color(187, 173, 160)
EMPTY = brushes.color(205, 193, 180)
PANEL_BG = brushes.color(187, 173, 160)
TEXT_DARK = brushes.color(119, 110, 101)
TEXT_LIGHT = brushes.color(249, 246, 242)
LABEL = brushes.color(238, 228, 218)
OVERLAY = brushes.color(238, 228, 218, 190)
HI_DEFAULT = brushes.color(60, 58, 50)

TILE_COLORS = {
    2: (238, 228, 218),
    4: (237, 224, 200),
    8: (242, 177, 121),
    16: (245, 149, 99),
    32: (246, 124, 95),
    64: (246, 94, 59),
    128: (237, 207, 114),
    256: (237, 204, 97),
    512: (237, 200, 80),
    1024: (237, 197, 63),
    2048: (237, 194, 46),
}
TILE_BRUSH = {v: brushes.color(*c) for v, c in TILE_COLORS.items()}

# Pre-computed cell coordinate order for each move direction. Index 0 is the
# edge a tile slides toward, so the same slide routine works for every move.
LINES = {
    "L": [[(r, c) for c in range(4)] for r in range(4)],
    "R": [[(r, 3 - c) for c in range(4)] for r in range(4)],
    "U": [[(r, c) for r in range(4)] for c in range(4)],
    "D": [[(3 - r, c) for r in range(4)] for c in range(4)],
}

# ---------------- Game state ----------------
board = [0] * 16
score = 0
best = 0
won = False
mode = "title"  # title | play | sliding | gameover

# Animation bookkeeping (not persisted)
anim = []
anim_start = 0
pending_board = None
pending_gained = 0
pending_merges = []
spawn_idx = -1
spawn_start = 0
merge_idxs = []
merge_start = 0
toast_text = ""
toast_start = 0

FONT = None


# ---------------- Persistence ----------------
def _load():
    global board, score, best, won, mode
    saved = {"board": [0] * 16, "score": 0, "best": 0, "won": False}
    try:
        State.load("2048", saved)
    except Exception:
        pass
    b = saved.get("board", [0] * 16)
    if isinstance(b, list) and len(b) == 16:
        board = [int(v) for v in b]
    score = int(saved.get("score", 0))
    best = int(saved.get("best", 0))
    won = bool(saved.get("won", False))
    if any(board):
        mode = "gameover" if not can_move(board) else "play"
    else:
        mode = "title"


def _save():
    try:
        State.save("2048", {"board": board, "score": score, "best": best, "won": won})
    except Exception:
        pass


# ---------------- Core logic ----------------
def slide_line(vals):
    """Collapse a line of four values toward index 0.

    Returns (new_vals, moves) where moves is a list of
    (from_index, to_index, merged) describing how each tile travels.
    """
    tiles = [(i, v) for i, v in enumerate(vals) if v != 0]
    new_vals = [0, 0, 0, 0]
    moves = []
    target = 0
    i = 0
    n = len(tiles)
    while i < n:
        from_i, val = tiles[i]
        if i + 1 < n and tiles[i + 1][1] == val:
            new_vals[target] = val * 2
            moves.append((from_i, target, False))
            moves.append((tiles[i + 1][0], target, True))
            target += 1
            i += 2
        else:
            new_vals[target] = val
            moves.append((from_i, target, False))
            target += 1
            i += 1
    return new_vals, moves


def compute_move(b, direction):
    """Return (new_board, anim_tiles, moved, gained, merges) for a direction."""
    new_board = [0] * 16
    anim_tiles = []
    merges = []
    gained = 0
    for cells in LINES[direction]:
        vals = [b[r * 4 + c] for (r, c) in cells]
        new_vals, moves = slide_line(vals)
        for idx, v in enumerate(new_vals):
            r, c = cells[idx]
            new_board[r * 4 + c] = v
        for (from_idx, to_idx, merged) in moves:
            anim_tiles.append((vals[from_idx], cells[from_idx], cells[to_idx], merged))
            if merged:
                gained += vals[from_idx] * 2
                merges.append(cells[to_idx])
    moved = new_board != b
    return new_board, anim_tiles, moved, gained, merges


def can_move(b):
    for i in range(16):
        if b[i] == 0:
            return True
        r, c = i // 4, i % 4
        if c < 3 and b[i] == b[i + 1]:
            return True
        if r < 3 and b[i] == b[i + 4]:
            return True
    return False


def spawn_tile():
    empties = [i for i in range(16) if board[i] == 0]
    if not empties:
        return -1
    i = random.choice(empties)
    board[i] = 4 if random.randint(0, 9) == 0 else 2
    return i


def new_game():
    global board, score, won, mode, spawn_idx, merge_idxs, toast_text
    board = [0] * 16
    score = 0
    won = False
    spawn_tile()
    spawn_tile()
    spawn_idx = -1
    merge_idxs = []
    toast_text = ""
    mode = "play"


def toast(text):
    global toast_text, toast_start
    toast_text = text
    toast_start = io.ticks


def do_move(direction):
    global anim, anim_start, pending_board, pending_gained, pending_merges, mode
    new_board, anim_tiles, moved, gained, merges = compute_move(board, direction)
    if not moved:
        return
    anim = anim_tiles
    anim_start = io.ticks
    pending_board = new_board
    pending_gained = gained
    pending_merges = merges
    mode = "sliding"


def commit():
    global board, score, best, won, mode
    global spawn_idx, spawn_start, merge_idxs, merge_start
    board = pending_board
    score += pending_gained
    if score > best:
        best = score
    merge_idxs = [r * 4 + c for (r, c) in pending_merges]
    merge_start = io.ticks
    if not won and any(v >= 2048 for v in board):
        won = True
        toast("2048! You win!")
    spawn_idx = spawn_tile()
    spawn_start = io.ticks
    mode = "play" if can_move(board) else "gameover"


# ---------------- Input ----------------
def handle_title():
    if (io.BUTTON_A in io.pressed or io.BUTTON_B in io.pressed or
            io.BUTTON_C in io.pressed or io.BUTTON_UP in io.pressed or
            io.BUTTON_DOWN in io.pressed):
        new_game()


def handle_play():
    if io.BUTTON_A in io.pressed:
        do_move("L")
    elif io.BUTTON_B in io.pressed:
        do_move("R")
    elif io.BUTTON_UP in io.pressed:
        do_move("U")
    elif io.BUTTON_DOWN in io.pressed:
        do_move("D")


def handle_gameover():
    if io.BUTTON_A in io.pressed:
        new_game()


# ---------------- Drawing helpers ----------------
def tile_brush(value):
    return TILE_BRUSH.get(value, HI_DEFAULT)


def text_brush(value):
    return TEXT_DARK if value <= 4 else TEXT_LIGHT


def draw_tile_px(px, py, size, value):
    screen.brush = tile_brush(value)
    radius = 3 if size >= 6 else size / 2
    screen.draw(shapes.rounded_rectangle(px, py, size, size, radius))
    if value:
        s = str(value)
        w, h = screen.measure_text(s)
        screen.brush = text_brush(value)
        screen.text(s, int(px + (size - w) / 2), int(py + (size - h) / 2))


def draw_tile_cell(r, c, value, scale=1.0):
    base_x = OX + c * STEP
    base_y = OY + r * STEP
    if scale == 1.0:
        draw_tile_px(base_x, base_y, TILE, value)
    else:
        size = TILE * scale
        cx = base_x + TILE / 2
        cy = base_y + TILE / 2
        draw_tile_px(cx - size / 2, cy - size / 2, size, value)


def draw_board_slots():
    screen.brush = BG_BOARD
    screen.draw(shapes.rounded_rectangle(BOARD_X, BOARD_Y, 4 * TILE + 5 * GAP, 4 * TILE + 5 * GAP, 4))
    screen.brush = EMPTY
    for r in range(4):
        for c in range(4):
            screen.draw(shapes.rounded_rectangle(OX + c * STEP, OY + r * STEP, TILE, TILE, 3))


def draw_panel():
    screen.brush = TEXT_DARK
    screen.text("2048", PANEL_X + 6, 4)
    _draw_stat("SCORE", score, 20)
    _draw_stat("BEST", best, 50)


def _draw_stat(label, value, y):
    screen.brush = PANEL_BG
    screen.draw(shapes.rounded_rectangle(PANEL_X, y, 40, 24, 3))
    screen.brush = LABEL
    w, _ = screen.measure_text(label)
    screen.text(label, PANEL_X + int((40 - w) / 2), y + 3)
    s = str(value)
    w, _ = screen.measure_text(s)
    screen.brush = TEXT_LIGHT
    screen.text(s, PANEL_X + int((40 - w) / 2), y + 12)


def draw_toast():
    if not toast_text:
        return
    if io.ticks - toast_start > TOAST_MS:
        return
    w, h = screen.measure_text(toast_text)
    bx = BOARD_X + (4 * TILE + 5 * GAP - w - 10) / 2
    screen.brush = brushes.color(0, 0, 0, 170)
    screen.draw(shapes.rounded_rectangle(bx, 50, w + 10, h + 8, 3))
    screen.brush = TEXT_LIGHT
    screen.text(toast_text, int(bx + 5), 54)


# ---------------- Screens ----------------
def draw_play():
    draw_board_slots()
    now = io.ticks
    for i in range(16):
        v = board[i]
        if v == 0:
            continue
        r, c = i // 4, i % 4
        scale = 1.0
        if i == spawn_idx and now - spawn_start < SPAWN_MS:
            t = (now - spawn_start) / SPAWN_MS
            scale = 0.2 + 0.8 * (1 - (1 - t) * (1 - t))
        elif i in merge_idxs and now - merge_start < MERGE_MS:
            t = (now - merge_start) / MERGE_MS
            scale = 1.0 + 0.12 * math.sin(math.pi * t)
        draw_tile_cell(r, c, v, scale)
    draw_panel()
    draw_toast()


def draw_sliding():
    draw_board_slots()
    t = (io.ticks - anim_start) / SLIDE_MS
    if t > 1:
        t = 1
    e = 1 - (1 - t) * (1 - t)
    for (value, (fr, fc), (tr, tc), _merged) in anim:
        fx = OX + fc * STEP
        fy = OY + fr * STEP
        tx = OX + tc * STEP
        ty = OY + tr * STEP
        draw_tile_px(fx + (tx - fx) * e, fy + (ty - fy) * e, TILE, value)
    draw_panel()


def draw_title():
    draw_board_slots()
    draw_tile_cell(1, 1, 2)
    draw_tile_cell(1, 2, 4)
    draw_tile_cell(2, 1, 8)
    draw_tile_cell(2, 2, 16)
    screen.brush = TEXT_DARK
    screen.text("2048", PANEL_X + 6, 6)
    screen.text("A left", PANEL_X, 24)
    screen.text("B right", PANEL_X, 34)
    screen.text("UP", PANEL_X, 48)
    screen.text("DOWN", PANEL_X, 58)
    if int(io.ticks / 500) % 2:
        screen.brush = TEXT_LIGHT
        screen.text("Press", PANEL_X, 84)
        screen.text("any key", PANEL_X, 94)


def draw_gameover():
    draw_play()
    screen.brush = OVERLAY
    screen.draw(shapes.rounded_rectangle(BOARD_X, BOARD_Y, 4 * TILE + 5 * GAP, 4 * TILE + 5 * GAP, 4))
    screen.brush = TEXT_DARK
    _centered_board_text("Game", 38)
    _centered_board_text("Over", 52)
    if int(io.ticks / 500) % 2:
        _centered_board_text("A: retry", 74)


def _centered_board_text(text, y):
    w, _ = screen.measure_text(text)
    bw = 4 * TILE + 5 * GAP
    screen.text(text, int(BOARD_X + (bw - w) / 2), y)


# ---------------- Lifecycle ----------------
def init():
    global FONT
    gc.collect()
    FONT = PixelFont.load("/system/assets/fonts/nope.ppf")
    screen.font = FONT
    screen.antialias = Image.X2
    _load()


def update():
    if mode == "title":
        handle_title()
    elif mode == "play":
        handle_play()
    elif mode == "sliding":
        if io.ticks - anim_start >= SLIDE_MS:
            commit()
    elif mode == "gameover":
        handle_gameover()

    screen.brush = BG_PAGE
    screen.clear()

    if mode == "title":
        draw_title()
    elif mode == "sliding":
        draw_sliding()
    elif mode == "gameover":
        draw_gameover()
    else:
        draw_play()


def on_exit():
    _save()


if __name__ == "__main__":
    init()
    run(update)
