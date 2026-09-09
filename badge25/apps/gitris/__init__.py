# /system/apps/tetris/__init__.py
# Gitris — GitHub-themed Tetris for Tufty-style MicroPython badge
# Controls:
#   A = move left   (auto-repeat)
#   B = move right  (auto-repeat)
#   UP = rotate CW
#   DOWN = soft drop
#   C = hard drop
#   HOME or B+C = pause (A=resume, B=title)
#
# Features:
#   - GitHub-dark palette + dev-themed labels
#   - 10x20 field (5px cells), ghost, 7-bag, next preview
#   - Scoring/levels/lines + persistent high score
#   - Toast messages for “merge” events
#   - Periodic “merge conflict” garbage row with a single gap

from badgeware import screen, io, brushes, shapes, PixelFont, State
import urandom

# ---------- Safe RNG (no randint required) ----------
def _getrandbits(n):
    # Prefer MicroPython's getrandbits; fall back to simple LCG seeded by io.ticks.
    try:
        return urandom.getrandbits(n)
    except AttributeError:
        # Very small fallback PRNG (LCG)
        s = _rng_state.get("s", (io.ticks & 0x7fffffff) ^ 0xB5297A4D)
        s = (1103515245 * s + 12345) & 0x7fffffff
        _rng_state["s"] = s
        # Return up to 24 bits from the state.
        return s & ((1 << min(n, 24)) - 1)

def _randint(a, b):
    span = (b - a + 1)
    # Use 30 random bits then mod to avoid bias for our small spans.
    r = _getrandbits(30)
    return a + (r % span)

_rng_state = {"s": (io.ticks & 0x7fffffff) ^ 0x1f123bb5}

# ---------------- Display/layout ----------------
W, H = 160, 120
CELL   = 5
GRID_W = 10
GRID_H = 20
PF_X = 6
PF_Y = 2
SIDE_X = PF_X + GRID_W*CELL + 8
SIDE_W = W - SIDE_X - 4

# ---------------- GitHub-dark palette ----------------
COL_BG    = brushes.color(13, 17, 23)       # page bg
COL_GRID  = brushes.color(48, 54, 61)       # frame
COL_TEXT  = brushes.color(240, 246, 252)    # primary text
COL_DIM   = brushes.color(139, 148, 158, 230)

# Piece colors (Primer-ish accents)
COLORS = [
    brushes.color( 61, 199,  98),  # I  green
    brushes.color(250, 219,  94),  # O  yellow
    brushes.color(191, 128, 255),  # T  purple
    brushes.color( 70, 212, 143),  # S  emerald
    brushes.color(255, 121, 135),  # Z  coral/red
    brushes.color( 90, 150, 255),  # J  blue
    brushes.color(255, 170, 108),  # L  orange
]
CONFLICT_COLOR = brushes.color(87, 96, 106) # conflict/garbage row blocks
COL_GHOST = brushes.color(240, 246, 252, 70)
COL_LOCK  = brushes.color(240, 246, 252, 24)

# ---------------- Font ----------------
def _load_font():
    for path in ("/system/assets/fonts/tiny.ppf",
                 "/system/assets/fonts/6x8.ppf",
                 "/system/assets/fonts/ark.ppf"):
        try:
            screen.font = PixelFont.load(path); return
        except Exception:
            pass
_load_font()

# ---------------- Game state ----------------
state = {
    "screen": "title",   # "title", "play", "pause", "gameover"
    "score": 0,          # COMMITS
    "level": 1,          # RELEASE
    "lines": 0,          # MERGES
    "hiscore": 0,
    "board": None,
    "bag": [],
    "curr": None,
    "next": None,
    "x": 3,
    "y": 0,
    "rot": 0,
    "fall_ms": 800,      # gravity
    "last_fall": 0,
    # movement auto-repeat (A/B)
    "das_ms": 150,       # delay before repeat
    "arr_ms": 45,        # repeat rate
    "left_hold": False,
    "right_hold": False,
    "left_since": 0,
    "right_since": 0,
    # conflict rows
    "pieces": 0,
    "conflict_every": 12,   # every N pieces, push a conflict row
}

# High score load
try:
    wrap = {"hiscore": 0}
    State.load("tetris_hiscore", wrap)
    state["hiscore"] = int(wrap.get("hiscore", 0))
except Exception:
    # Ignore errors loading high score (e.g., file missing or corrupt); use default of 0.
    pass

# ---------------- Tetrominoes (SRS-ish) ----------------
I = [
    [(0,1),(1,1),(2,1),(3,1)],
    [(2,0),(2,1),(2,2),(2,3)],
    [(0,2),(1,2),(2,2),(3,2)],
    [(1,0),(1,1),(1,2),(1,3)]
]
O = [[(1,0),(2,0),(1,1),(2,1)]]*4
T = [
    [(1,0),(0,1),(1,1),(2,1)],
    [(1,0),(1,1),(2,1),(1,2)],
    [(0,1),(1,1),(2,1),(1,2)],
    [(1,0),(0,1),(1,1),(1,2)],
]
S = [
    [(1,0),(2,0),(0,1),(1,1)],
    [(1,0),(1,1),(2,1),(2,2)],
    [(1,1),(2,1),(0,2),(1,2)],
    [(0,0),(0,1),(1,1),(1,2)],
]
Z = [
    [(0,0),(1,0),(1,1),(2,1)],
    [(2,0),(1,1),(2,1),(1,2)],
    [(0,1),(1,1),(1,2),(2,2)],
    [(1,0),(0,1),(1,1),(0,2)],
]
J = [
    [(0,0),(0,1),(1,1),(2,1)],
    [(1,0),(2,0),(1,1),(1,2)],
    [(0,1),(1,1),(2,1),(2,2)],
    [(1,0),(1,1),(0,2),(1,2)],
]
L = [
    [(2,0),(0,1),(1,1),(2,1)],
    [(1,0),(1,1),(1,2),(2,2)],
    [(0,1),(1,1),(2,1),(0,2)],
    [(0,0),(1,0),(1,1),(1,2)],
]
SHAPES = [I, O, T, S, Z, J, L]

KICKS = {  # simple wall-kicks
    (0,1): [(0,0), (-1,0), (-1,-1), (0,2), (-1,2)],
    (1,0): [(0,0), (1,0),  (1,1),   (0,-2),(1,-2)],
    (1,2): [(0,0), (1,0),  (1,-1),  (0,2), (1,2)],
    (2,1): [(0,0), (-1,0), (-1,1),  (0,-2),(-1,-2)],
    (2,3): [(0,0), (1,0),  (1,1),   (0,-2),(1,-2)],
    (3,2): [(0,0), (-1,0), (-1,-1), (0,2), (-1,2)],
    (3,0): [(0,0), (1,0),  (1,-1),  (0,2), (1,2)],
    (0,3): [(0,0), (-1,0), (-1,1),  (0,-2),(-1,-2)],
}

# ---------------- Board & bag ----------------
def _new_board():
    return [[0]*GRID_W for _ in range(GRID_H)]

def _refill_bag():
    bag = list(range(len(SHAPES)))
    # Fisher–Yates shuffle using safe _randint
    for i in range(len(bag)-1, 0, -1):
        j = _randint(0, i)
        bag[i], bag[j] = bag[j], bag[i]
    return bag

def _push_conflict_row():
    gap = _randint(0, GRID_W-1)
    # Drop top row, append conflict row at bottom
    state["board"].pop(0)
    row = [8]*GRID_W  # 8 = conflict cell (special color)
    row[gap] = 0
    state["board"].append(row)
    _toast("Merge conflict! Resolve it.")

def _spawn():
    if not state["bag"]:
        state["bag"] = _refill_bag()
    idx = state["bag"].pop()
    state["curr"] = idx
    state["rot"]  = 0
    state["x"]    = 3
    state["y"]    = 0
    if not state["bag"]:
        state["bag"] = _refill_bag()
    state["next"] = state["bag"][-1]
    # conflict cadence
    state["pieces"] += 1
    if state["screen"] == "play" and state["conflict_every"] > 0:
        if state["pieces"] % state["conflict_every"] == 0:
            _push_conflict_row()
    # top-out?
    if _collides(state["x"], state["y"], state["rot"]):
        _to_gameover()

# ---------------- Core helpers ----------------
def _cells_at(x, y, rot, shape_idx=None):
    s = SHAPES[state["curr"] if shape_idx is None else shape_idx][rot % 4]
    for dx, dy in s:
        yield x + dx, y + dy

def _collides(nx, ny, nrot):
    for cx, cy in _cells_at(nx, ny, nrot):
        if cx < 0 or cx >= GRID_W or cy >= GRID_H:
            return True
        if cy >= 0:
            v = state["board"][cy][cx]
            if v: return True
    return False

def _lock_piece():
    for cx, cy in _cells_at(state["x"], state["y"], state["rot"]):
        if 0 <= cy < GRID_H and 0 <= cx < GRID_W:
            state["board"][cy][cx] = state["curr"] + 1
    _clear_lines()
    _spawn()

def _announce_merge(cleared):
    if cleared == 1: msg = "Committed."
    elif cleared == 2: msg = "PR ready."
    elif cleared == 3: msg = "Rebase clean!"
    else: msg = "Massive merge! ✅"
    _toast(msg)

def _clear_lines():
    rows = state["board"]
    kept = [r for r in rows if not all(r)]  # any zero keeps the row
    cleared = GRID_H - len(kept)
    if cleared:
        # add empty rows up top
        for _ in range(cleared):
            kept.insert(0, [0]*GRID_W)
        state["board"] = kept
        # scoring
        scores = {1:40, 2:100, 3:300, 4:1200}
        state["score"] += scores.get(cleared, 0) * state["level"]
        state["lines"] += cleared
        _announce_merge(cleared)
        # level up every 10 lines
        new_level = 1 + state["lines"] // 10
        if new_level != state["level"]:
            state["level"] = new_level
            state["fall_ms"] = max(120, 800 - (state["level"]-1)*60)

def _move(dx, dy):
    nx, ny = state["x"] + dx, state["y"] + dy
    if not _collides(nx, ny, state["rot"]):
        state["x"], state["y"] = nx, ny
        return True
    return False

def _rotate_cw():
    old = state["rot"]; new = (old + 1) % 4
    if (old, new) in KICKS:
        for kx, ky in KICKS[(old, new)]:
            if not _collides(state["x"] + kx, state["y"] + ky, new):
                state["x"] += kx; state["y"] += ky; state["rot"] = new; return True
    if not _collides(state["x"], state["y"], new):
        state["rot"] = new; return True
    return False

def _hard_drop():
    while _move(0, 1):
        pass
    _lock_piece()

def _ghost_y():
    gx, gy, gr = state["x"], state["y"], state["rot"]
    while not _collides(gx, gy+1, gr):
        gy += 1
    return gy

def _reset_run():
    state["board"] = _new_board()
    state["bag"] = _refill_bag()
    state["score"] = 0
    state["level"] = 1
    state["lines"] = 0
    state["fall_ms"] = 800
    state["left_hold"] = False
    state["right_hold"] = False
    state["pieces"] = 0
    _spawn()

def _to_title(): state["screen"] = "title"
def _to_game():  state["screen"] = "play";  state["last_fall"] = io.ticks
def _to_pause(): state["screen"] = "pause"

def _to_gameover():
    if state["score"] > state["hiscore"]:
        state["hiscore"] = state["score"]
        try: State.save("tetris_hiscore", {"hiscore": state["hiscore"]})
        except Exception:
            # Ignore errors saving high score (e.g., file system full or read-only).
            pass
    state["screen"] = "gameover"

# ---------------- Toast (tiny overlay) ----------------
_toast_msg = {"t":0, "txt":""}
def _toast(s):
    _toast_msg["t"] = io.ticks
    _toast_msg["txt"] = s

def _draw_toast():
    if not _toast_msg["txt"]:
        return
    if io.ticks - _toast_msg["t"] > 1400:
        _toast_msg["txt"] = ""
        return
    screen.brush = brushes.color(0,0,0,160)
    screen.draw(shapes.rectangle(PF_X, PF_Y+38, GRID_W*CELL, 14))
    screen.brush = COL_TEXT
    screen.text(_toast_msg["txt"], PF_X+6, PF_Y+40)

# ---------------- Input helpers ----------------
def _pressed(btn): return btn in io.pressed
def _pause_pressed():
    return (hasattr(io, "BUTTON_HOME") and _pressed(io.BUTTON_HOME)) or (_pressed(io.BUTTON_B) and _pressed(io.BUTTON_C))

# ---------------- Input handlers ----------------
def _handle_title():
    # Any of these starts a new run
    if _pressed(io.BUTTON_A) or _pressed(io.BUTTON_B) or _pressed(io.BUTTON_C) or _pressed(io.BUTTON_DOWN) or _pressed(io.BUTTON_UP):
        _reset_run(); _to_game()

def _handle_pause():
    # A = resume, B = title
    if _pressed(io.BUTTON_A): _to_game()
    elif _pressed(io.BUTTON_B): _to_title()

def _handle_gameover():
    if _pressed(io.BUTTON_A) or _pressed(io.BUTTON_B) or _pressed(io.BUTTON_C):
        _to_title()

def _handle_play():
    now = io.ticks

    # Pause via HOME or B+C
    if _pause_pressed(): _to_pause(); return

    # Rotation
    if _pressed(io.BUTTON_UP): _rotate_cw()

    # Movement (A = left, B = right) with DAS/ARR
    if _pressed(io.BUTTON_A):
        if not state["left_hold"]:
            _move(-1,0); state["left_hold"] = True; state["left_since"] = now
        else:
            if now - state["left_since"] > state["das_ms"]:
                if ((now - state["left_since"]) % state["arr_ms"]) < 15:
                    _move(-1,0)
    else:
        state["left_hold"] = False

    if _pressed(io.BUTTON_B):
        if not state["right_hold"]:
            _move(1,0); state["right_hold"] = True; state["right_since"] = now
        else:
            if now - state["right_since"] > state["das_ms"]:
                if ((now - state["right_since"]) % state["arr_ms"]) < 15:
                    _move(1,0)
    else:
        state["right_hold"] = False

    # Soft drop
    if _pressed(io.BUTTON_DOWN):
        if _move(0,1): state["score"] += 1
        state["last_fall"] = now

    # Hard drop
    if _pressed(io.BUTTON_C):
        _hard_drop(); state["last_fall"] = now; return

    # Gravity
    if now - state["last_fall"] >= state["fall_ms"]:
        if not _move(0,1): _lock_piece()
        state["last_fall"] = now

# ---------------- Drawing ----------------
def _draw_cell(px, py, color, alpha_outline=False):
    screen.brush = color
    screen.draw(shapes.rectangle(px, py, CELL, CELL))
    if alpha_outline:
        screen.brush = COL_LOCK
        screen.draw(shapes.rectangle(px, py, CELL, CELL))

def _draw_grid():
    screen.brush = COL_BG; screen.clear()
    screen.brush = COL_GRID
    screen.draw(shapes.rectangle(PF_X-1, PF_Y-1, GRID_W*CELL+2, GRID_H*CELL+2))

def _draw_board():
    for y in range(GRID_H):
        row = state["board"][y]
        for x in range(GRID_W):
            v = row[x]
            if v:
                if v == 8:  # conflict cell
                    color = CONFLICT_COLOR
                else:
                    color = COLORS[v-1]
                _draw_cell(PF_X + x*CELL, PF_Y + y*CELL, color)

def _draw_piece(x, y, rot, idx, ghost=False):
    col = COL_GHOST if ghost else COLORS[idx]
    for cx, cy in SHAPES[idx][rot]:
        px = PF_X + (x+cx)*CELL
        py = PF_Y + (y+cy)*CELL
        _draw_cell(px, py, col, alpha_outline=ghost)

def _draw_sidebar():
    screen.brush = COL_TEXT
    screen.text("COMMITS", SIDE_X, 4);      screen.text(str(state["score"]), SIDE_X, 15)
    screen.text("RELEASE", SIDE_X, 30);     screen.text(str(state["level"]), SIDE_X, 41)
    screen.text("MERGES",  SIDE_X, 56);     screen.text(str(state["lines"]), SIDE_X, 67)
    screen.text("BEST BUILD",  SIDE_X, 82); screen.text(str(state["hiscore"]), SIDE_X, 93)
    screen.text("NEXT PATCH",  SIDE_X, 108-26)
    nx = state["next"]
    if nx is not None:
        ox = SIDE_X + 2; oy = 108 - 16
        for cx, cy in SHAPES[nx][0]:
            px = ox + cx*3; py = oy + cy*3
            screen.brush = COLORS[nx]
            screen.draw(shapes.rectangle(px, py, 3, 3))

def _draw_title():
    _draw_grid(); _draw_board()
    screen.brush = COL_DIM;  screen.text("GITRIS", PF_X + 6, 10)
    screen.brush = COL_TEXT
    screen.text("UP=Rotate  A/B=Move", PF_X + 6, 26)
    screen.text("DOWN=Soft  C=Hard", PF_X + 6, 38)
    screen.text("HOME or B+C = Pause", PF_X + 6, 50)
    screen.text("Press any to start", PF_X + 6, 70)
    screen.text("Best Build:", PF_X + 6, 86); screen.text(str(state["hiscore"]), PF_X + 6, 98)

def _draw_pause():
    _draw_grid(); _draw_board()
    # show current + ghost
    if state["curr"] is not None:
        gy = _ghost_y(); _draw_piece(state["x"], gy, state["rot"], state["curr"], ghost=True)
        _draw_piece(state["x"], state["y"], state["rot"], state["curr"])
    _draw_sidebar()
    # overlay
    screen.brush = brushes.color(0,0,0,180)
    screen.draw(shapes.rectangle(0, 0, W, H))
    screen.brush = COL_TEXT
    screen.text("Pipeline Paused", PF_X + 6, 46)
    screen.text("A: Resume   B: Title", PF_X + 6, 60)

def _draw_gameover():
    _draw_grid(); _draw_board(); _draw_sidebar()
    screen.brush = brushes.color(0,0,0,200)
    screen.draw(shapes.rectangle(0, 0, W, H))
    screen.brush = COL_TEXT
    screen.text("Build Failed", PF_X + 16, 46)
    screen.text("A/B/C: Title", PF_X + 16, 60)

def update():
    # logic
    if state["screen"] == "title": _handle_title()
    elif state["screen"] == "play": _handle_play()
    elif state["screen"] == "pause": _handle_pause()
    elif state["screen"] == "gameover": _handle_gameover()

    # draw
    if state["screen"] == "title":
        _draw_title(); return

    if state["screen"] == "play":
        _draw_grid(); _draw_board()
        gy = _ghost_y()
        _draw_piece(state["x"], gy, state["rot"], state["curr"], ghost=True)
        _draw_piece(state["x"], state["y"], state["rot"], state["curr"])
        _draw_sidebar()
        _draw_toast()
        return

    if state["screen"] == "pause":
        _draw_pause(); return

    if state["screen"] == "gameover":
        _draw_gameover(); return

# Initialize a fresh board so title renders
if state["board"] is None:
    state["board"] = _new_board()
    _reset_run(); _to_title()
