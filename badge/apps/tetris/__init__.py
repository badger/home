# Classic Tetris for Tufty Badge
# Controls:
#   A = move left
#   C = move right
#   UP = rotate
#   DOWN = soft drop (faster fall)
#   B = instant drop

from badgeware import screen, io, brushes, shapes, PixelFont, State
import random

# Display settings
SCREEN_W, SCREEN_H = 160, 120
CELL_SIZE = 4
GRID_W = 10
GRID_H = 20
GRID_X = 10
GRID_Y = 10

# Colors - Classic Tetris palette
BG_COLOR = brushes.color(0, 0, 0)
GRID_COLOR = brushes.color(40, 40, 40)
TEXT_COLOR = brushes.color(255, 255, 255)

# Tetromino colors (classic)
PIECE_COLORS = [
    brushes.color(0, 255, 255),    # I - Cyan
    brushes.color(255, 255, 0),    # O - Yellow
    brushes.color(128, 0, 128),    # T - Purple
    brushes.color(0, 255, 0),      # S - Green
    brushes.color(255, 0, 0),      # Z - Red
    brushes.color(0, 0, 255),      # J - Blue
    brushes.color(255, 165, 0),    # L - Orange
]

# Tetromino shapes (standard SRS)
PIECES = [
    # I
    [[(0, 1), (1, 1), (2, 1), (3, 1)],
     [(2, 0), (2, 1), (2, 2), (2, 3)],
     [(0, 2), (1, 2), (2, 2), (3, 2)],
     [(1, 0), (1, 1), (1, 2), (1, 3)]],
    # O
    [[(1, 0), (2, 0), (1, 1), (2, 1)]] * 4,
    # T
    [[(1, 0), (0, 1), (1, 1), (2, 1)],
     [(1, 0), (1, 1), (2, 1), (1, 2)],
     [(0, 1), (1, 1), (2, 1), (1, 2)],
     [(1, 0), (0, 1), (1, 1), (1, 2)]],
    # S
    [[(1, 0), (2, 0), (0, 1), (1, 1)],
     [(1, 0), (1, 1), (2, 1), (2, 2)],
     [(1, 1), (2, 1), (0, 2), (1, 2)],
     [(0, 0), (0, 1), (1, 1), (1, 2)]],
    # Z
    [[(0, 0), (1, 0), (1, 1), (2, 1)],
     [(2, 0), (1, 1), (2, 1), (1, 2)],
     [(0, 1), (1, 1), (1, 2), (2, 2)],
     [(1, 0), (0, 1), (1, 1), (0, 2)]],
    # J
    [[(0, 0), (0, 1), (1, 1), (2, 1)],
     [(1, 0), (2, 0), (1, 1), (1, 2)],
     [(0, 1), (1, 1), (2, 1), (2, 2)],
     [(1, 0), (1, 1), (0, 2), (1, 2)]],
    # L
    [[(2, 0), (0, 1), (1, 1), (2, 1)],
     [(1, 0), (1, 1), (1, 2), (2, 2)],
     [(0, 1), (1, 1), (2, 1), (0, 2)],
     [(0, 0), (1, 0), (1, 1), (1, 2)]],
]

# Game state
game_state = {
    "mode": "title",  # title, playing, paused, gameover
    "board": None,
    "current_piece": None,
    "current_type": 0,
    "current_rot": 0,
    "piece_x": 0,
    "piece_y": 0,
    "score": 0,
    "level": 1,
    "lines": 0,
    "high_score": 0,
    "fall_timer": 0,
    "fall_speed": 800,
    "next_piece": None,
}

# Load font
try:
    screen.font = PixelFont.load("/system/assets/fonts/tiny.ppf")
except:
    try:
        screen.font = PixelFont.load("/system/assets/fonts/nope.ppf")
    except:
        pass

# Load high score
try:
    data = {}
    State.load("tetris_high_score", data)
    game_state["high_score"] = data.get("high_score", 0)
except:
    pass

def init():
    """Called when the app starts"""
    pass

def new_game():
    """Start a new game"""
    game_state["board"] = [[0 for _ in range(GRID_W)] for _ in range(GRID_H)]
    game_state["score"] = 0
    game_state["level"] = 1
    game_state["lines"] = 0
    game_state["fall_speed"] = 800
    game_state["fall_timer"] = io.ticks
    game_state["next_piece"] = random.randint(0, 6)
    spawn_piece()

def spawn_piece():
    """Spawn a new piece at the top"""
    game_state["current_type"] = game_state["next_piece"]
    game_state["next_piece"] = random.randint(0, 6)
    game_state["current_rot"] = 0
    game_state["piece_x"] = GRID_W // 2 - 2
    game_state["piece_y"] = 0

    # Check if spawn position is blocked (game over)
    if check_collision():
        game_state["mode"] = "gameover"

def get_piece_cells():
    """Get current piece cell positions"""
    piece = PIECES[game_state["current_type"]][game_state["current_rot"]]
    return [(game_state["piece_x"] + dx, game_state["piece_y"] + dy) for dx, dy in piece]

def check_collision(offset_x=0, offset_y=0, new_rot=None):
    """Check if piece collides with board or boundaries"""
    rot = new_rot if new_rot is not None else game_state["current_rot"]
    piece = PIECES[game_state["current_type"]][rot]

    for dx, dy in piece:
        x = game_state["piece_x"] + dx + offset_x
        y = game_state["piece_y"] + dy + offset_y

        # Check boundaries
        if x < 0 or x >= GRID_W or y >= GRID_H:
            return True

        # Check board collision (only if y >= 0)
        if y >= 0 and game_state["board"][y][x] != 0:
            return True

    return False

def lock_piece():
    """Lock the current piece to the board"""
    for x, y in get_piece_cells():
        if 0 <= y < GRID_H and 0 <= x < GRID_W:
            game_state["board"][y][x] = game_state["current_type"] + 1

    clear_lines()
    spawn_piece()

def clear_lines():
    """Clear completed lines and update score"""
    lines_cleared = 0
    y = GRID_H - 1

    while y >= 0:
        if all(cell != 0 for cell in game_state["board"][y]):
            # Remove this line
            game_state["board"].pop(y)
            # Add empty line at top
            game_state["board"].insert(0, [0 for _ in range(GRID_W)])
            lines_cleared += 1
        else:
            y -= 1

    if lines_cleared > 0:
        # Update lines and score
        game_state["lines"] += lines_cleared

        # Score based on lines cleared (classic Tetris scoring)
        line_scores = [0, 40, 100, 300, 1200]
        game_state["score"] += line_scores[min(lines_cleared, 4)] * game_state["level"]

        # Update high score
        if game_state["score"] > game_state["high_score"]:
            game_state["high_score"] = game_state["score"]
            try:
                State.save("tetris_high_score", {"high_score": game_state["high_score"]})
            except:
                pass

        # Level up every 10 lines
        new_level = 1 + game_state["lines"] // 10
        if new_level != game_state["level"]:
            game_state["level"] = new_level
            # Increase speed (cap at 100ms)
            game_state["fall_speed"] = max(100, 800 - (game_state["level"] - 1) * 70)

def move_piece(dx, dy):
    """Try to move the piece"""
    if not check_collision(dx, dy):
        game_state["piece_x"] += dx
        game_state["piece_y"] += dy
        return True
    return False

def rotate_piece():
    """Try to rotate the piece"""
    new_rot = (game_state["current_rot"] + 1) % len(PIECES[game_state["current_type"]])

    # Try rotation without wall kick
    if not check_collision(0, 0, new_rot):
        game_state["current_rot"] = new_rot
        return True

    # Try simple wall kicks
    for kick_x in [-1, 1, -2, 2]:
        if not check_collision(kick_x, 0, new_rot):
            game_state["piece_x"] += kick_x
            game_state["current_rot"] = new_rot
            return True

    return False

def instant_drop():
    """Drop piece instantly to bottom"""
    while move_piece(0, 1):
        game_state["score"] += 2  # Bonus points for hard drop
    lock_piece()
    game_state["fall_timer"] = io.ticks

def draw_cell(x, y, color):
    """Draw a single cell"""
    px = GRID_X + x * CELL_SIZE
    py = GRID_Y + y * CELL_SIZE
    screen.brush = color
    screen.draw(shapes.rectangle(px, py, CELL_SIZE - 1, CELL_SIZE - 1))

def draw_board():
    """Draw the game board"""
    # Draw border
    screen.brush = GRID_COLOR
    border_w = GRID_W * CELL_SIZE + 2
    border_h = GRID_H * CELL_SIZE + 2
    screen.draw(shapes.rectangle(GRID_X - 1, GRID_Y - 1, border_w, border_h))

    # Draw locked pieces
    for y in range(GRID_H):
        for x in range(GRID_W):
            if game_state["board"][y][x] != 0:
                piece_type = game_state["board"][y][x] - 1
                draw_cell(x, y, PIECE_COLORS[piece_type])

def draw_current_piece():
    """Draw the current falling piece"""
    color = PIECE_COLORS[game_state["current_type"]]
    for x, y in get_piece_cells():
        if y >= 0:  # Don't draw cells above the board
            draw_cell(x, y, color)

def draw_next_piece():
    """Draw the next piece preview"""
    screen.brush = TEXT_COLOR
    screen.text("NEXT", GRID_X + GRID_W * CELL_SIZE + 8, GRID_Y)

    # Draw next piece (smaller)
    next_piece = PIECES[game_state["next_piece"]][0]
    base_x = GRID_X + GRID_W * CELL_SIZE + 8
    base_y = GRID_Y + 12

    color = PIECE_COLORS[game_state["next_piece"]]
    for dx, dy in next_piece:
        px = base_x + dx * 3
        py = base_y + dy * 3
        screen.brush = color
        screen.draw(shapes.rectangle(px, py, 2, 2))

def draw_stats():
    """Draw score and stats"""
    x = GRID_X + GRID_W * CELL_SIZE + 8
    y = GRID_Y + 40

    screen.brush = TEXT_COLOR
    screen.text("SCORE", x, y)
    screen.text(str(game_state["score"]), x, y + 10)

    screen.text("LEVEL", x, y + 25)
    screen.text(str(game_state["level"]), x, y + 35)

    screen.text("LINES", x, y + 50)
    screen.text(str(game_state["lines"]), x, y + 60)

    screen.text("HIGH", x, y + 75)
    screen.text(str(game_state["high_score"]), x, y + 85)

def draw_title():
    """Draw title screen"""
    screen.brush = TEXT_COLOR
    screen.text("TETRIS", 60, 30)
    screen.text("A/C: Move", 50, 50)
    screen.text("UP: Rotate", 50, 60)
    screen.text("DOWN: Drop", 50, 70)
    screen.text("B: Instant", 50, 80)

    if io.ticks % 1000 < 500:
        screen.text("Press A", 60, 100)

def draw_gameover():
    """Draw game over screen"""
    draw_board()
    draw_current_piece()
    draw_stats()

    # Overlay
    screen.brush = brushes.color(0, 0, 0, 180)
    screen.draw(shapes.rectangle(GRID_X, GRID_Y + 30, GRID_W * CELL_SIZE, 30))

    screen.brush = TEXT_COLOR
    screen.text("GAME OVER", GRID_X + 4, GRID_Y + 38)
    screen.text("Press A", GRID_X + 8, GRID_Y + 50)

def update_title():
    """Update title screen"""
    if io.BUTTON_A in io.pressed:
        new_game()
        game_state["mode"] = "playing"

def update_playing():
    """Update playing state"""
    # Check for pause
    if hasattr(io, "BUTTON_HOME") and io.BUTTON_HOME in io.pressed:
        game_state["mode"] = "paused"
        return

    # Handle input
    if io.BUTTON_A in io.pressed:
        move_piece(-1, 0)

    if io.BUTTON_C in io.pressed:
        move_piece(1, 0)

    if io.BUTTON_UP in io.pressed:
        rotate_piece()

    if io.BUTTON_DOWN in io.pressed:
        if move_piece(0, 1):
            game_state["score"] += 1  # Bonus for soft drop
            game_state["fall_timer"] = io.ticks

    if io.BUTTON_B in io.pressed:
        instant_drop()

    # Auto-fall based on speed
    if io.ticks - game_state["fall_timer"] >= game_state["fall_speed"]:
        if not move_piece(0, 1):
            lock_piece()
        game_state["fall_timer"] = io.ticks

def update_paused():
    """Update paused state"""
    if io.BUTTON_A in io.pressed:
        game_state["mode"] = "playing"
    elif io.BUTTON_B in io.pressed:
        game_state["mode"] = "title"

def update_gameover():
    """Update game over state"""
    if io.BUTTON_A in io.pressed:
        game_state["mode"] = "title"

def update():
    """Main update function called every frame"""
    # Clear screen
    screen.brush = BG_COLOR
    screen.clear()

    # Update based on mode
    if game_state["mode"] == "title":
        update_title()
        draw_title()

    elif game_state["mode"] == "playing":
        update_playing()
        draw_board()
        draw_current_piece()
        draw_next_piece()
        draw_stats()

    elif game_state["mode"] == "paused":
        update_paused()
        draw_board()
        draw_current_piece()
        draw_stats()

        # Pause overlay
        screen.brush = brushes.color(0, 0, 0, 180)
        screen.draw(shapes.rectangle(GRID_X, GRID_Y + 30, GRID_W * CELL_SIZE, 30))
        screen.brush = TEXT_COLOR
        screen.text("PAUSED", GRID_X + 8, GRID_Y + 38)
        screen.text("A:Resume B:Quit", GRID_X + 2, GRID_Y + 50)

    elif game_state["mode"] == "gameover":
        update_gameover()
        draw_gameover()

def on_exit():
    """Called when exiting the app"""
    pass
