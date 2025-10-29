import sys
import os

sys.path.insert(0, "/system/apps/pacman")
os.chdir("/system/apps/pacman")

from badgeware import screen, brushes, shapes, io, run, PixelFont
import random

# Game constants
SCREEN_WIDTH = 160
SCREEN_HEIGHT = 120
CELL_SIZE = 8
GRID_WIDTH = SCREEN_WIDTH // CELL_SIZE  # 20
GRID_HEIGHT = SCREEN_HEIGHT // CELL_SIZE  # 15

# Colors
BLACK = brushes.color(0, 0, 0)
YELLOW = brushes.color(255, 255, 0)
WHITE = brushes.color(255, 255, 255)
BLUE = brushes.color(33, 33, 255)
RED = brushes.color(255, 0, 0)
PINK = brushes.color(255, 184, 255)
CYAN = brushes.color(0, 255, 255)
ORANGE = brushes.color(255, 184, 82)
WALL_COLOR = brushes.color(33, 33, 255)

# Load fonts
try:
    small_font = PixelFont.load("/system/assets/fonts/ark.ppf")
    large_font = PixelFont.load("/system/assets/fonts/absolute.ppf")
except:
    small_font = None
    large_font = None

# Simple maze layout (0 = path with dot, 1 = wall, 2 = path no dot, 3 = power pellet)
maze = [
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
    [1,0,0,0,0,0,0,0,0,1,1,0,0,0,0,0,0,0,0,1],
    [1,3,1,1,0,1,1,1,0,1,1,0,1,1,1,0,1,1,3,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
    [1,0,1,1,0,1,0,1,1,1,1,1,1,0,1,0,1,1,0,1],
    [1,0,0,0,0,1,0,0,0,1,1,0,0,0,1,0,0,0,0,1],
    [1,1,1,1,0,1,1,1,2,1,1,2,1,1,1,0,1,1,1,1],
    [1,1,1,1,0,1,2,2,2,2,2,2,2,2,1,0,1,1,1,1],
    [1,1,1,1,0,1,2,1,1,2,2,1,1,2,1,0,1,1,1,1],
    [0,0,0,0,0,0,2,1,2,2,2,2,1,2,0,0,0,0,0,0],
    [1,1,1,1,0,1,2,1,1,1,1,1,1,2,1,0,1,1,1,1],
    [1,1,1,1,0,1,2,2,2,2,2,2,2,2,1,0,1,1,1,1],
    [1,0,0,0,0,0,0,0,0,1,1,0,0,0,0,0,0,0,0,1],
    [1,3,1,1,0,1,1,1,0,1,1,0,1,1,1,0,1,1,3,1],
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
]

class Pacman:
    def __init__(self, maze_state=None):
        # Find a safe starting position away from ghosts
        if maze_state:
            # Find all valid starting positions (not walls, in corners preferably)
            safe_positions = [
                (1, 1), (1, 3), (1, 12), (1, 13),
                (18, 1), (18, 3), (18, 12), (18, 13)
            ]
            # Pick a random safe position
            self.x, self.y = random.choice(safe_positions)
        else:
            self.x = 1
            self.y = 1
        self.dir = 0  # 0=right, 1=down, 2=left, 3=up
        self.next_dir = 0
        self.move_counter = 0
        self.move_speed = 3  # move every N frames
        self.mouth_open = True
        self.mouth_timer = 0

    def update(self, maze_state):
        self.mouth_timer += 1
        if self.mouth_timer > 5:
            self.mouth_open = not self.mouth_open
            self.mouth_timer = 0

        self.move_counter += 1
        if self.move_counter >= self.move_speed:
            self.move_counter = 0

            # Try to turn if next_dir is different
            if self.next_dir != self.dir:
                if self.can_move(self.next_dir, maze_state):
                    self.dir = self.next_dir

            # Move in current direction
            if self.can_move(self.dir, maze_state):
                if self.dir == 0:  # right
                    self.x += 1
                elif self.dir == 1:  # down
                    self.y += 1
                elif self.dir == 2:  # left
                    self.x -= 1
                elif self.dir == 3:  # up
                    self.y -= 1

            # Wrap around edges
            if self.x < 0:
                self.x = GRID_WIDTH - 1
            elif self.x >= GRID_WIDTH:
                self.x = 0

    def can_move(self, direction, maze_state):
        new_x, new_y = self.x, self.y
        if direction == 0:  # right
            new_x += 1
        elif direction == 1:  # down
            new_y += 1
        elif direction == 2:  # left
            new_x -= 1
        elif direction == 3:  # up
            new_y -= 1

        # Wrap around
        if new_x < 0:
            new_x = GRID_WIDTH - 1
        elif new_x >= GRID_WIDTH:
            new_x = 0

        if new_y < 0 or new_y >= GRID_HEIGHT:
            return False

        return maze_state[new_y][new_x] != 1

    def draw(self):
        cx = self.x * CELL_SIZE + CELL_SIZE // 2
        cy = self.y * CELL_SIZE + CELL_SIZE // 2
        radius = CELL_SIZE // 2 - 1

        screen.brush = YELLOW

        if self.mouth_open:
            # Draw pac-man with mouth open (approximate with circle)
            screen.draw(shapes.circle(cx, cy, radius))

            # Draw mouth gap (black triangle-ish area)
            screen.brush = BLACK
            mouth_size = 2
            if self.dir == 0:  # right
                screen.draw(shapes.line(cx, cy, cx + radius, cy - mouth_size, 1))
                screen.draw(shapes.line(cx, cy, cx + radius, cy + mouth_size, 1))
            elif self.dir == 2:  # left
                screen.draw(shapes.line(cx, cy, cx - radius, cy - mouth_size, 1))
                screen.draw(shapes.line(cx, cy, cx - radius, cy + mouth_size, 1))
            elif self.dir == 3:  # up
                screen.draw(shapes.line(cx, cy, cx - mouth_size, cy - radius, 1))
                screen.draw(shapes.line(cx, cy, cx + mouth_size, cy - radius, 1))
            elif self.dir == 1:  # down
                screen.draw(shapes.line(cx, cy, cx - mouth_size, cy + radius, 1))
                screen.draw(shapes.line(cx, cy, cx + mouth_size, cy + radius, 1))
        else:
            # Mouth closed - just a circle
            screen.draw(shapes.circle(cx, cy, radius))

class Ghost:
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.color = color
        self.dir = random.randint(0, 3)
        self.move_counter = 0
        self.move_speed = 4

    def update(self, maze_state, pacman):
        self.move_counter += 1
        if self.move_counter >= self.move_speed:
            self.move_counter = 0

            # Simple AI: randomly try to move toward pacman
            possible_dirs = []
            for d in range(4):
                if self.can_move(d, maze_state):
                    possible_dirs.append(d)

            if possible_dirs:
                # 70% chance to move toward pacman, 30% random
                if random.random() < 0.7:
                    # Choose direction that gets closer to pacman
                    best_dir = self.dir
                    best_dist = 999
                    for d in possible_dirs:
                        new_x, new_y = self.x, self.y
                        if d == 0:
                            new_x += 1
                        elif d == 1:
                            new_y += 1
                        elif d == 2:
                            new_x -= 1
                        elif d == 3:
                            new_y -= 1

                        dist = abs(new_x - pacman.x) + abs(new_y - pacman.y)
                        if dist < best_dist:
                            best_dist = dist
                            best_dir = d
                    self.dir = best_dir
                else:
                    self.dir = random.choice(possible_dirs)

            # Move
            if self.can_move(self.dir, maze_state):
                if self.dir == 0:
                    self.x += 1
                elif self.dir == 1:
                    self.y += 1
                elif self.dir == 2:
                    self.x -= 1
                elif self.dir == 3:
                    self.y -= 1

    def can_move(self, direction, maze_state):
        new_x, new_y = self.x, self.y
        if direction == 0:
            new_x += 1
        elif direction == 1:
            new_y += 1
        elif direction == 2:
            new_x -= 1
        elif direction == 3:
            new_y -= 1

        if new_x < 0 or new_x >= GRID_WIDTH or new_y < 0 or new_y >= GRID_HEIGHT:
            return False

        return maze_state[new_y][new_x] != 1

    def draw(self):
        cx = self.x * CELL_SIZE + CELL_SIZE // 2
        cy = self.y * CELL_SIZE + CELL_SIZE // 2
        radius = CELL_SIZE // 2 - 1

        screen.brush = self.color
        # Draw circle for ghost body
        screen.draw(shapes.circle(cx, cy - 1, radius))
        # Draw rectangle for bottom half
        screen.draw(shapes.rectangle(cx - radius, cy - 1, radius * 2, radius + 1))

        # Draw eyes
        screen.brush = WHITE
        screen.draw(shapes.rectangle(cx - 2, cy - 2, 2, 2))
        screen.draw(shapes.rectangle(cx + 1, cy - 2, 2, 2))

class GameState:
    PLAYING = 1
    GAME_OVER = 2
    WIN = 3

# Initialize game
maze_state = [row[:] for row in maze]  # Copy maze
pacman = Pacman(maze_state)
ghosts = [
    Ghost(8, 7, RED),
    Ghost(10, 7, PINK),
    Ghost(11, 7, CYAN),
]
score = 0
state = GameState.PLAYING
total_dots = sum(row.count(0) + row.count(3) for row in maze_state)

def draw_maze():
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            cell = maze_state[y][x]
            px = x * CELL_SIZE
            py = y * CELL_SIZE

            if cell == 1:  # wall
                screen.brush = WALL_COLOR
                screen.draw(shapes.rectangle(px, py, CELL_SIZE, CELL_SIZE))
            elif cell == 0:  # dot
                screen.brush = WHITE
                screen.draw(shapes.circle(px + CELL_SIZE // 2, py + CELL_SIZE // 2, 1))
            elif cell == 3:  # power pellet
                screen.brush = WHITE
                screen.draw(shapes.circle(px + CELL_SIZE // 2, py + CELL_SIZE // 2, 2))

def check_collision():
    for ghost in ghosts:
        if pacman.x == ghost.x and pacman.y == ghost.y:
            return True
    return False

def update():
    global score, state, maze_state

    # Handle input
    if io.BUTTON_C in io.pressed or io.BUTTON_C in io.held:
        pacman.next_dir = 0  # right
    if io.BUTTON_A in io.pressed or io.BUTTON_A in io.held:
        pacman.next_dir = 2  # left
    if io.BUTTON_UP in io.pressed or io.BUTTON_UP in io.held:
        pacman.next_dir = 3  # up
    if io.BUTTON_DOWN in io.pressed or io.BUTTON_DOWN in io.held:
        pacman.next_dir = 1  # down

    if state == GameState.PLAYING:
        # Update game
        pacman.update(maze_state)

        for ghost in ghosts:
            ghost.update(maze_state, pacman)

        # Check dot collection
        cell = maze_state[pacman.y][pacman.x]
        if cell == 0:
            score += 10
            maze_state[pacman.y][pacman.x] = 2
        elif cell == 3:
            score += 50
            maze_state[pacman.y][pacman.x] = 2

        # Check collision
        if check_collision():
            state = GameState.GAME_OVER

        # Check win condition
        remaining_dots = sum(row.count(0) + row.count(3) for row in maze_state)
        if remaining_dots == 0:
            state = GameState.WIN

    elif state == GameState.GAME_OVER or state == GameState.WIN:
        if io.BUTTON_B in io.pressed:
            # Restart game
            maze_state = [row[:] for row in maze]
            pacman.__init__(maze_state)
            for i, ghost in enumerate(ghosts):
                ghost.__init__(8 + i, 7, [RED, PINK, CYAN][i])
            score = 0
            state = GameState.PLAYING

    # Draw everything
    screen.brush = BLACK
    screen.draw(shapes.rectangle(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))

    draw_maze()

    for ghost in ghosts:
        ghost.draw()

    pacman.draw()

    # Draw score at top
    if small_font:
        screen.font = small_font
        screen.brush = WHITE
        screen.text(f"Score: {score}", 2, 2)

    # Draw game over / win screen
    if state == GameState.GAME_OVER:
        if large_font:
            screen.font = large_font
            screen.brush = RED
            text = "GAME OVER"
            w, _ = screen.measure_text(text)
            screen.text(text, SCREEN_WIDTH // 2 - w // 2, 50)

        if small_font:
            screen.font = small_font
            screen.brush = WHITE
            text = "Press B to retry"
            w, _ = screen.measure_text(text)
            screen.text(text, SCREEN_WIDTH // 2 - w // 2, 70)

    elif state == GameState.WIN:
        if large_font:
            screen.font = large_font
            screen.brush = YELLOW
            text = "YOU WIN!"
            w, _ = screen.measure_text(text)
            screen.text(text, SCREEN_WIDTH // 2 - w // 2, 50)

        if small_font:
            screen.font = small_font
            screen.brush = WHITE
            text = "Press B to play again"
            w, _ = screen.measure_text(text)
            screen.text(text, SCREEN_WIDTH // 2 - w // 2, 70)

if __name__ == "__main__":
    run(update)
