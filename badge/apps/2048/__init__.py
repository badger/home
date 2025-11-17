# 2048 Game for Tufty Badge
# Controls:
#   A = move left
#   C = move right
#   UP = move up
#   DOWN = move down
#   B = new game (when game over)

from badgeware import screen, io, brushes, shapes, PixelFont, State
import random

# Display settings
SCREEN_W, SCREEN_H = 160, 120
GRID_SIZE = 4
CELL_SIZE = 20
CELL_GAP = 2
GRID_X = 10
GRID_Y = 20

# GitHub-themed colors
BG_COLOR = brushes.color(13, 17, 23)
GRID_BG = brushes.color(22, 27, 34)
TEXT_COLOR = brushes.color(240, 246, 252)
TEXT_DARK = brushes.color(13, 17, 23)

# Tile colors (GitHub-themed gradient)
TILE_COLORS = {
    0: brushes.color(48, 54, 61),
    2: brushes.color(87, 96, 106),
    4: brushes.color(110, 118, 129),
    8: brushes.color(33, 136, 255),
    16: brushes.color(26, 127, 255),
    32: brushes.color(88, 166, 255),
    64: brushes.color(79, 192, 141),
    128: brushes.color(54, 179, 126),
    256: brushes.color(163, 113, 247),
    512: brushes.color(137, 87, 229),
    1024: brushes.color(248, 81, 73),
    2048: brushes.color(218, 54, 51),
    4096: brushes.color(255, 215, 0),
    8192: brushes.color(255, 165, 0),
}

# Default color for tiles beyond 8192
DEFAULT_TILE_COLOR = brushes.color(255, 100, 200)

# Game state
game_state = {
    "mode": "title",  # title, playing, won, gameover
    "board": None,
    "score": 0,
    "best": 0,
    "won": False,
    "move_made": False,
    "game_over": False,
}

# Load font
try:
    screen.font = PixelFont.load("/system/assets/fonts/tiny.ppf")
except:
    try:
        screen.font = PixelFont.load("/system/assets/fonts/nope.ppf")
    except:
        pass

# Load best score
try:
    data = {}
    State.load("2048_best_score", data)
    game_state["best"] = data.get("best", 0)
except:
    pass

def init():
    """Called when the app starts"""
    pass

def new_game():
    """Start a new game"""
    game_state["board"] = [[0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
    game_state["score"] = 0
    game_state["won"] = False
    game_state["game_over"] = False
    game_state["move_made"] = False

    # Add two initial tiles
    add_random_tile()
    add_random_tile()

def add_random_tile():
    """Add a random tile (2 or 4) to an empty cell"""
    empty_cells = []
    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            if game_state["board"][row][col] == 0:
                empty_cells.append((row, col))

    if empty_cells:
        row, col = random.choice(empty_cells)
        # 90% chance of 2, 10% chance of 4
        game_state["board"][row][col] = 2 if random.random() < 0.9 else 4

def compress(row):
    """Remove zeros from row and shift left"""
    new_row = [i for i in row if i != 0]
    new_row += [0] * (GRID_SIZE - len(new_row))
    return new_row

def merge(row):
    """Merge adjacent equal tiles"""
    for i in range(GRID_SIZE - 1):
        if row[i] != 0 and row[i] == row[i + 1]:
            row[i] *= 2
            row[i + 1] = 0
            game_state["score"] += row[i]

            # Check for win condition
            if row[i] == 2048 and not game_state["won"]:
                game_state["won"] = True
    return row

def move_left():
    """Move all tiles left"""
    moved = False
    for i in range(GRID_SIZE):
        original = game_state["board"][i][:]
        game_state["board"][i] = compress(game_state["board"][i])
        game_state["board"][i] = merge(game_state["board"][i])
        game_state["board"][i] = compress(game_state["board"][i])
        if original != game_state["board"][i]:
            moved = True
    return moved

def move_right():
    """Move all tiles right"""
    moved = False
    for i in range(GRID_SIZE):
        original = game_state["board"][i][:]
        game_state["board"][i] = game_state["board"][i][::-1]
        game_state["board"][i] = compress(game_state["board"][i])
        game_state["board"][i] = merge(game_state["board"][i])
        game_state["board"][i] = compress(game_state["board"][i])
        game_state["board"][i] = game_state["board"][i][::-1]
        if original != game_state["board"][i]:
            moved = True
    return moved

def transpose():
    """Transpose the board"""
    game_state["board"] = [[game_state["board"][j][i] for j in range(GRID_SIZE)]
                           for i in range(GRID_SIZE)]

def move_up():
    """Move all tiles up"""
    transpose()
    moved = move_left()
    transpose()
    return moved

def move_down():
    """Move all tiles down"""
    transpose()
    moved = move_right()
    transpose()
    return moved

def can_move():
    """Check if any moves are possible"""
    # Check for empty cells
    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            if game_state["board"][row][col] == 0:
                return True

    # Check for possible merges horizontally
    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE - 1):
            if game_state["board"][row][col] == game_state["board"][row][col + 1]:
                return True

    # Check for possible merges vertically
    for row in range(GRID_SIZE - 1):
        for col in range(GRID_SIZE):
            if game_state["board"][row][col] == game_state["board"][row + 1][col]:
                return True

    return False

def get_tile_color(value):
    """Get color for a tile value"""
    return TILE_COLORS.get(value, DEFAULT_TILE_COLOR)

def draw_tile(row, col, value):
    """Draw a single tile"""
    x = GRID_X + col * (CELL_SIZE + CELL_GAP)
    y = GRID_Y + row * (CELL_SIZE + CELL_GAP)

    # Draw tile background
    color = get_tile_color(value)
    screen.brush = color
    screen.draw(shapes.rectangle(x, y, CELL_SIZE, CELL_SIZE))

    # Draw value if not empty
    if value > 0:
        text = str(value)
        # Use smaller font size calculation for larger numbers
        if value >= 1024:
            text = str(value // 1024) + "k"

        # Center the text
        w, h = screen.measure_text(text)
        text_x = x + (CELL_SIZE - w) // 2
        text_y = y + (CELL_SIZE - h) // 2

        # Choose text color based on tile value
        if value <= 4:
            screen.brush = TEXT_COLOR
        else:
            screen.brush = TEXT_DARK if value <= 16 else TEXT_COLOR

        screen.text(text, text_x, text_y)

def draw_board():
    """Draw the game board"""
    # Draw background
    bg_width = GRID_SIZE * (CELL_SIZE + CELL_GAP) - CELL_GAP
    bg_height = GRID_SIZE * (CELL_SIZE + CELL_GAP) - CELL_GAP
    screen.brush = GRID_BG
    screen.draw(shapes.rectangle(GRID_X - 2, GRID_Y - 2, bg_width + 4, bg_height + 4))

    # Draw tiles
    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            draw_tile(row, col, game_state["board"][row][col])

def draw_header():
    """Draw score header"""
    screen.brush = TEXT_COLOR
    screen.text("2048", 10, 4)

    # Score
    score_text = "Score: " + str(game_state["score"])
    screen.text(score_text, 50, 4)

    # Best
    best_text = "Best: " + str(game_state["best"])
    screen.text(best_text, 108, 4)

def draw_title():
    """Draw title screen"""
    screen.brush = TEXT_COLOR
    screen.text("2048", 65, 25)

    screen.text("Join tiles to", 45, 45)
    screen.text("get to 2048!", 45, 55)

    screen.text("A/C: Left/Right", 35, 75)
    screen.text("UP/DOWN: Move", 35, 85)

    if io.ticks % 1000 < 500:
        screen.text("Press A to start", 32, 105)

def draw_game_over():
    """Draw game over overlay"""
    # Semi-transparent overlay
    overlay_x = GRID_X + 5
    overlay_y = GRID_Y + 25
    overlay_w = GRID_SIZE * (CELL_SIZE + CELL_GAP) - 10
    overlay_h = 30

    screen.brush = brushes.color(0, 0, 0, 200)
    screen.draw(shapes.rectangle(overlay_x, overlay_y, overlay_w, overlay_h))

    screen.brush = TEXT_COLOR
    screen.text("Game Over!", overlay_x + 8, overlay_y + 5)
    screen.text("Press B", overlay_x + 14, overlay_y + 18)

def draw_won():
    """Draw you won overlay"""
    # Semi-transparent overlay
    overlay_x = GRID_X + 5
    overlay_y = GRID_Y + 25
    overlay_w = GRID_SIZE * (CELL_SIZE + CELL_GAP) - 10
    overlay_h = 30

    screen.brush = brushes.color(0, 100, 0, 200)
    screen.draw(shapes.rectangle(overlay_x, overlay_y, overlay_w, overlay_h))

    screen.brush = TEXT_COLOR
    screen.text("You Win!", overlay_x + 15, overlay_y + 5)
    screen.text("Keep going!", overlay_x + 8, overlay_y + 18)

def update_title():
    """Update title screen"""
    if io.BUTTON_A in io.pressed:
        new_game()
        game_state["mode"] = "playing"

def update_playing():
    """Update playing state"""
    moved = False

    # Handle input
    if io.BUTTON_A in io.pressed:
        moved = move_left()
    elif io.BUTTON_C in io.pressed:
        moved = move_right()
    elif io.BUTTON_UP in io.pressed:
        moved = move_up()
    elif io.BUTTON_DOWN in io.pressed:
        moved = move_down()

    # Add new tile if move was made
    if moved:
        add_random_tile()

        # Update best score
        if game_state["score"] > game_state["best"]:
            game_state["best"] = game_state["score"]
            try:
                State.save("2048_best_score", {"best": game_state["best"]})
            except:
                pass

        # Check for game over
        if not can_move():
            game_state["game_over"] = True

    # Check for new game on game over
    if game_state["game_over"] and io.BUTTON_B in io.pressed:
        new_game()

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
        draw_header()
        draw_board()

        # Draw overlays
        if game_state["won"] and not game_state["game_over"]:
            draw_won()

        if game_state["game_over"]:
            draw_game_over()

def on_exit():
    """Called when exiting the app"""
    pass
