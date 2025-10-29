from badgeware import screen, Image, PixelFont, brushes, shapes, io, run
import random

# Constants
WIDTH = 160
HEIGHT = 120
GROUND_Y = 90
PLAYER_X = 30
SCROLL_SPEED = 2
OBSTACLE_SPAWN_MIN = 70
OBSTACLE_SPAWN_MAX = 120
OBSTACLE_REMOVAL_THRESHOLD = -50  # X position at which off-screen obstacles are removed
AIR_GAP = 8  # Vertical gap above ground that the branch bottom sits at (duck to clear)
GRASS_PATTERN_WIDTH = 8  # Width of the repeating grass pattern

# Collision box adjustments for forgiving gameplay
COLLISION_MARGIN = 2  # Pixels reduced from each side of collision boxes
COLLISION_Y_MARGIN = 2  # Y-offset for standing player collision box
DUCKING_Y_OFFSET = 10  # Y-offset for ducking player collision box
DUCKING_SPRITE_Y_OFFSET = 8  # Y-offset for rendering ducking sprite (visual position)
PLAYER_COLLISION_WIDTH = 16 - (COLLISION_MARGIN * 2)  # Player collision box width (12)
PLAYER_COLLISION_HEIGHT = 16 - (COLLISION_MARGIN * 2)  # Standing player collision box height (12)
PLAYER_DUCKING_COLLISION_HEIGHT = 8 - (COLLISION_MARGIN * 2)  # Ducking player collision box height (4)

# Jungle theme colors
SKY_COLOR = brushes.color(135, 206, 235)  # Sky blue
GROUND_COLOR = brushes.color(34, 139, 34)  # Forest green
GRASS_COLOR = brushes.color(50, 205, 50)   # Lime green
TEXT_COLOR = brushes.color(255, 255, 255)  # White
GAMEOVER_BG = brushes.color(0, 0, 0, 200)  # Semi-transparent black

# Set up font
screen.font = PixelFont.load("/system/assets/fonts/ark.ppf")

# Load sprites
player_img = Image.load("/system/apps/jungle/sprites/player.png")
log_img = Image.load("/system/apps/jungle/sprites/log.png")
creature_img = Image.load("/system/apps/jungle/sprites/creature.png")
branch_img = Image.load("/system/apps/jungle/sprites/branch.png")

# Game state
state = {
    "game_state": "playing",  # "playing" or "gameover"
    "score": 0,
    "player_y": GROUND_Y - 16,  # Player standing on ground
    "player_vel_y": 0,
    "is_jumping": False,
    "is_ducking": False,
    "obstacles": [],
    "next_spawn": OBSTACLE_SPAWN_MIN,
    "scroll_offset": 0
}

# Obstacle types: (image, type, ground_height)
# type: "ground" (jump over) or "air" (duck under)
# ground_height: for ground obstacles, this should equal sprite height so bottom rests at GROUND_Y
#   (calculation: y_pos = GROUND_Y - ground_height, so bottom = y_pos + height = GROUND_Y)
# Coordinate system: y = top of sprite. Collision boxes use margins and offsets.
# Air obstacles: branch placed with bottom at GROUND_Y - AIR_GAP (90 - 8 = 82)
# Standing player: player_y = 74 (sprite top), collision box top = 74 + COLLISION_Y_MARGIN = 76,
#   collision box height = 12, so collision box bottom = 88 (HITS branch at 82)
# Ducking player: player_y = 74 (sprite top), collision box top = 74 + DUCKING_Y_OFFSET = 84,
#   collision box height = 4, so collision box bottom = 88 (CLEARS branch at 82)
OBSTACLE_TYPES = [
    (log_img, "ground", 12),
    (creature_img, "ground", 12),
    (branch_img, "air", 0)  # ground_height not used for air obstacles
]

def reset_game():
    """Reset game to initial state"""
    state["game_state"] = "playing"
    state["score"] = 0
    state["player_y"] = GROUND_Y - 16
    state["player_vel_y"] = 0
    state["is_jumping"] = False
    state["is_ducking"] = False
    state["obstacles"] = []
    state["next_spawn"] = OBSTACLE_SPAWN_MIN
    state["scroll_offset"] = 0

def spawn_obstacle():
    """Spawn a new obstacle, ensuring it's passable"""
    # Pick random obstacle type
    img, obs_type, ground_height = random.choice(OBSTACLE_TYPES)

    # Check if last obstacle was an air obstacle
    last_was_air = False
    if state["obstacles"]:
        last_obs = state["obstacles"][-1]
        if last_obs.get("type") == "air":
            last_was_air = True

    # Ensure we don't spawn two air obstacles in a row (would be impossible)
    if last_was_air and obs_type == "air":
        # Force ground obstacle instead
        ground_obstacles = [(img, t, h) for img, t, h in OBSTACLE_TYPES if t == "ground"]
        img, obs_type, ground_height = random.choice(ground_obstacles)

    # Compute spawn Y: ground obstacles rest on ground; air obstacles have fixed bottom at GROUND_Y - AIR_GAP
    if obs_type == "air":
        y_pos = GROUND_Y - AIR_GAP - img.height
    else:
        y_pos = GROUND_Y - ground_height

    obstacle = {
        "x": WIDTH,
        "y": y_pos,
        "img": img,
        "type": obs_type,
        "scored": False
    }
    state["obstacles"].append(obstacle)
    state["next_spawn"] = random.randint(OBSTACLE_SPAWN_MIN, OBSTACLE_SPAWN_MAX)

def check_collision():
    """Check if player collides with any obstacle"""
    # Reduced collision box for more forgiving gameplay
    # Calculate Y position based on ducking state
    if state["is_ducking"]:
        collision_y = state["player_y"] + DUCKING_Y_OFFSET
        collision_h = PLAYER_DUCKING_COLLISION_HEIGHT
    else:
        collision_y = state["player_y"] + COLLISION_Y_MARGIN
        collision_h = PLAYER_COLLISION_HEIGHT

    player_rect = {
        "x": PLAYER_X + COLLISION_MARGIN,
        "y": collision_y,
        "w": PLAYER_COLLISION_WIDTH,
        "h": collision_h
    }

    for obs in state["obstacles"]:
        obs_w = obs["img"].width
        obs_h = obs["img"].height

        # Reduced obstacle collision box
        obs_rect = {
            "x": obs["x"] + COLLISION_MARGIN,
            "y": obs["y"] + COLLISION_MARGIN,
            "w": obs_w - (COLLISION_MARGIN * 2),
            "h": obs_h - (COLLISION_MARGIN * 2)
        }

        # Check rectangle collision
        if (player_rect["x"] < obs_rect["x"] + obs_rect["w"] and
            player_rect["x"] + player_rect["w"] > obs_rect["x"] and
            player_rect["y"] < obs_rect["y"] + obs_rect["h"] and
            player_rect["y"] + player_rect["h"] > obs_rect["y"]):
            return True

    return False

def update():
    if state["game_state"] == "playing":
        # Handle jumping
        if io.BUTTON_UP in io.pressed and not state["is_jumping"]:
            state["is_jumping"] = True
            state["player_vel_y"] = -4.5

        # Handle ducking
        if io.BUTTON_DOWN in io.held and not state["is_jumping"]:
            state["is_ducking"] = True
        else:
            state["is_ducking"] = False

        # Apply gravity
        if state["is_jumping"]:
            state["player_vel_y"] += 0.3
            state["player_y"] += state["player_vel_y"]

            # Check if landed
            if state["player_y"] >= GROUND_Y - 16:
                state["player_y"] = GROUND_Y - 16
                state["is_jumping"] = False
                state["player_vel_y"] = 0

        # Update obstacles
        state["scroll_offset"] += SCROLL_SPEED
        state["next_spawn"] -= SCROLL_SPEED

        # Spawn new obstacle if needed
        if state["next_spawn"] <= 0:
            spawn_obstacle()

        # Move obstacles and check scoring
        for obs in state["obstacles"]:
            obs["x"] -= SCROLL_SPEED

            # Score point when obstacle passes player
            if not obs["scored"] and obs["x"] + obs["img"].width < PLAYER_X:
                obs["scored"] = True
                state["score"] += 1

        # Remove off-screen obstacles
        state["obstacles"] = [obs for obs in state["obstacles"] if obs["x"] > OBSTACLE_REMOVAL_THRESHOLD]

        # Check collision
        if check_collision():
            state["game_state"] = "gameover"

        # Draw game
        draw_game()

    elif state["game_state"] == "gameover":
        # Draw game over screen
        draw_game()
        draw_gameover()

        # Press A to restart
        if io.BUTTON_A in io.pressed:
            reset_game()

def draw_game():
    # Draw sky
    screen.brush = SKY_COLOR
    screen.clear()

    # Draw ground
    screen.brush = GROUND_COLOR
    screen.draw(shapes.rectangle(0, GROUND_Y, WIDTH, HEIGHT - GROUND_Y))

    # Draw grass pattern on ground
    screen.brush = GRASS_COLOR
    offset = state["scroll_offset"] % GRASS_PATTERN_WIDTH
    for i in range(0, WIDTH, GRASS_PATTERN_WIDTH):
        screen.draw(shapes.rectangle(i - offset, GROUND_Y, 4, 2))

    # Draw obstacles
    for obs in state["obstacles"]:
        x_pos = int(obs["x"])
        y_pos = int(obs["y"])
        # Ensure coordinates are integers to prevent rendering artifacts
        screen.blit(obs["img"], x_pos, y_pos)

    # Draw player
    player_y = int(state["player_y"])
    if state["is_ducking"]:
        # Draw ducking (squashed sprite)
        # DUCKING_SPRITE_Y_OFFSET (8) positions the squashed sprite (16px->8px) visually on ground.
        # DUCKING_Y_OFFSET (10) positions collision box top for reduced hit area during ducking.
        screen.scale_blit(player_img, PLAYER_X, int(player_y + DUCKING_SPRITE_Y_OFFSET), 16, 8)
    else:
        screen.blit(player_img, PLAYER_X, player_y)

    # Draw score
    screen.brush = TEXT_COLOR
    screen.text(f"Score: {state['score']}", 5, 5)

def draw_gameover():
    # Semi-transparent overlay
    screen.brush = GAMEOVER_BG
    screen.draw(shapes.rectangle(20, 35, 120, 50))

    # Game over text
    screen.brush = TEXT_COLOR
    screen.text("GAME OVER!", 45, 45)
    screen.text(f"Score: {state['score']}", 52, 60)
    screen.text("Press A to restart", 25, 75)

if __name__ == "__main__":
    run(update)
