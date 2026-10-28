"""
Guide a bee through growing hedge mazes to reach the flower.

Controls:
* Direction controls = Move
* SELECT = Show a short pollen trail, or start / continue
"""

import os
import sys

sys.path.insert(0, "/system/apps/bee_amazed")
os.chdir("/system/apps/bee_amazed")

import gc
import random
from collections import namedtuple


class GameState:
    INTRO = 1
    PLAYING = 2
    GAME_OVER = 3


state = GameState.INTRO

hedge = image.load("assets/hedge.png").spritesheet(2, 16)

# Setup for the display
small_font = font.nope
large_font = font.ziplock
screen.font = small_font
screen.antialias = image.X4

BEE_FRAMES = 4

animations = {
    "up": None,
    "down": None,
    "left": None,
    "right": None
}

for dir in animations.keys():
    animations[dir] = image.load(f"assets/bee-{dir}.png").spritesheet(BEE_FRAMES, 1)

# Colour Constants
BLACK = color.rgb(0, 0, 0)
WHITE = color.rgb(255, 255, 255)
WINDOW_COLOR = color.rgb(227, 231, 110, 125)
WALL = color.rgb(127, 125, 244)
BACKGROUND = image.load("assets/background.png")
PATH = color.rgb((227 + 60) // 2, (231 + 57) // 2, (110 + 169) // 2)
POLLEN = color.rgb(255, 210, 64)
HUD = color.rgb(24, 47, 29)


screen.pen = color.rgb(0, 0, 0)

# enable hi-res mode
badge.mode(HIRES | VSYNC)

CX, CY = screen.width / 2, screen.height / 2

# Gameplay Constants
Position = namedtuple("Position", ("x", "y"))
MIN_MAZE_WIDTH = 2
MAX_MAZE_WIDTH = 5
MIN_MAZE_HEIGHT = 2
MAX_MAZE_HEIGHT = 5
WALL_SHADOW = 1
WALL_GAP = 1
WALL_BITSHIFT = 4
TEXT_SHADOW = 2
DIFFICULT_SCALE = 0.5
N, S, E, W = 1, 2, 4, 8
HINT_STEPS = 6
HINT_MS = 2500
MOVE_DELAY_MS = 180
MOVE_REPEAT_MS = 90
HEADER_HEIGHT = 18
FOOTER_HEIGHT = 16
MIN_TILE_SIZE = 10
MOVE_DIRECTIONS = (
    (BUTTON_LEFT, -1, 0, W, E, "left"),
    (BUTTON_RIGHT, 1, 0, E, W, "right"),
    (BUTTON_UP, 0, -1, N, S, "up"),
    (BUTTON_DOWN, 0, 1, S, N, "down"),
)

# Variables
complete = False                                # Has the game been completed?
level = 0                                       # The current "level" the player is on (affects difficulty)

player = None
builder = None
hint = []
hint_remaining = 0
hints_used = 0


# Classes
class Cell:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.bottom = True
        self.right = True
        self.visited = False

    @staticmethod
    def remove_walls(current, next):
        dx, dy = current.x - next.x, current.y - next.y
        if dx == 1:
            next.right = False
        if dx == -1:
            current.right = False
        if dy == 1:
            next.bottom = False
        if dy == -1:
            current.bottom = False


class MazeBuilder:
    def __init__(self):
        self.width = 0
        self.height = 0
        self.cell_grid = []
        self.maze = []

    def build(self, width, height):
        if width <= 0:
            raise ValueError("width out of range. Expected greater than 0")

        if height <= 0:
            raise ValueError("height out of range. Expected greater than 0")

        self.width = width
        self.height = height

        # Set the starting cell to the centre
        cx = (self.width - 1) // 2
        cy = (self.height - 1) // 2

        gc.collect()

        # Create a grid of cells for building a maze
        self.cell_grid = [[Cell(x, y) for y in range(self.height)] for x in range(self.width)]
        cell_stack = []

        # Retrieve the starting cell and mark it as visited
        current = self.cell_grid[cx][cy]
        current.visited = True

        # Loop until every cell has been visited
        while True:
            next = self.choose_neighbour(current)
            # Was a valid neighbour found?
            if next is not None:
                # Move to the next cell, removing walls in the process
                next.visited = True
                cell_stack.append(current)
                Cell.remove_walls(current, next)
                current = next

            # No valid neighbour. Backtrack to a previous cell
            elif len(cell_stack) > 0:
                current = cell_stack.pop()

            # No previous cells, so exit
            else:
                break

        gc.collect()

        # Use the cell grid to create a maze grid of 0's and 1s
        self.maze = []

        row = [1]
        for _x in range(self.width):
            row.append(1)
            row.append(1)
        self.maze.append(row)

        for y in range(self.height):
            row = [1]
            for x in range(self.width):
                row.append(0)
                row.append(1 if self.cell_grid[x][y].right else 0)
            self.maze.append(row)

            row = [1]
            for x in range(self.width):
                row.append(1 if self.cell_grid[x][y].bottom else 0)
                row.append(1)
            self.maze.append(row)

        self.cell_grid.clear()
        gc.collect()

        self.grid_columns = (self.width * 2 + 1)
        self.grid_rows = (self.height * 2 + 1)

        for y in range(self.grid_rows):
            for x in range(self.grid_columns):
                current = self.maze[y][x]
                if current > 0:
                    current -= 1

                    if x < self.grid_columns - 1:
                        right = self.maze[y][x + 1]
                        if right > 0:
                            current += E << WALL_BITSHIFT
                            self.maze[y][x + 1] += W << WALL_BITSHIFT

                    if y < self.grid_rows - 1:
                        down = self.maze[y + 1][x]
                        if down > 0:
                            current += S << WALL_BITSHIFT
                            self.maze[y + 1][x] += N << WALL_BITSHIFT

                    self.maze[y][x] = current

    def choose_neighbour(self, current):
        unvisited = []
        for dx in range(-1, 2, 2):
            x = current.x + dx
            if x >= 0 and x < self.width and not self.cell_grid[x][current.y].visited:
                unvisited.append((x, current.y))

        for dy in range(-1, 2, 2):
            y = current.y + dy
            if y >= 0 and y < self.height and not self.cell_grid[current.x][y].visited:
                unvisited.append((current.x, y))

        if len(unvisited) > 0:
            x, y = random.choice(unvisited)
            return self.cell_grid[x][y]

        return None

    def maze_width(self):
        return (self.width * 2) + 1

    def maze_height(self):
        return (self.height * 2) + 1

    def pollen_trail(self, start, goal, limit=HINT_STEPS):
        """Find a few shortest-path steps without changing the player's trail."""
        columns, rows = self.grid_columns, self.grid_rows
        origin = start[1] * columns + start[0]
        target = goal[1] * columns + goal[0]
        directions = ((-1, 0), (1, 0), (0, -1), (0, 1))

        # Search back from the flower. Each byte points one step toward it;
        # unlike a dict of coordinate tuples this keeps search memory small.
        parents = bytearray(columns * rows)
        parents[target] = 5
        queue = [target]
        head = 0
        while head < len(queue) and not parents[origin]:
            cell = queue[head]
            head += 1
            x, y = cell % columns, cell // columns
            for direction, (dx, dy) in enumerate(directions):
                nx, ny = x + dx, y + dy
                if not (0 <= nx < columns and 0 <= ny < rows):
                    continue
                neighbour = ny * columns + nx
                # Low bits record where the bee has walked, not walls.
                if parents[neighbour] or self.maze[ny][nx] >> WALL_BITSHIFT:
                    continue
                parents[neighbour] = (direction ^ 1) + 1
                queue.append(neighbour)

        trail = []
        cell = origin
        while parents[cell] and cell != target and len(trail) < limit:
            dx, dy = directions[parents[cell] - 1]
            cell += dx + dy * columns
            trail.append((cell % columns, cell // columns))
        return trail

    def draw(self):
        # Draw the maze we have built. Each '1' in the array represents a wall
        for y in range(self.grid_rows):
            for x in range(self.grid_columns):
                wall = self.maze[y][x] >> WALL_BITSHIFT
                path = self.maze[y][x] & ((1 << WALL_BITSHIFT) - 1)
                # Calculate the screen coordinates
                px = (x * wall_separation) + offset_x
                py = (y * wall_separation) + offset_y

                if wall != 0:
                    sprite = (0, wall)
                else:
                    sprite = (1, path)

                screen.blit(hedge.sprite(*sprite), rect(px, py, wall_separation, wall_separation))


class Player(object):
    def __init__(self, x, y):
        self.position(x, y)

    def position(self, x, y):
        self.x = x
        self.y = y
        self.moves = 0
        self.direction = None
        self.move_wait = 0
        self.current_animation = animations["right"]

    def step(self, maze, direction):
        _button, dx, dy, leaving, entering, animation = direction
        nx, ny = self.x + dx, self.y + dy
        if not (0 <= ny < len(maze) and 0 <= nx < len(maze[ny])):
            return False
        if maze[ny][nx] >> WALL_BITSHIFT:
            return False
        maze[self.y][self.x] |= leaving
        self.x, self.y = nx, ny
        maze[ny][nx] |= entering
        self.current_animation = animations[animation]
        self.moves += 1
        return True

    def update(self, maze, target=None):
        direction = None
        for candidate in MOVE_DIRECTIONS:
            if badge.held(candidate[0]):
                direction = candidate
                break
        if direction is None:
            self.direction = None
            self.move_wait = 0
            return False

        # A tap or turn moves once immediately; holding repeats after a short
        # delay. Use elapsed time so normal frame-rate changes do not alter speed.
        if direction != self.direction:
            self.direction = direction
            self.move_wait = MOVE_DELAY_MS
            return self.step(maze, direction)

        # Resuming after a long pause must not send the bee across the maze.
        self.move_wait -= min(250, max(0, badge.ticks_delta))
        moved = False
        while self.move_wait <= 0:
            self.move_wait += MOVE_REPEAT_MS
            if not self.step(maze, direction):
                self.move_wait = MOVE_REPEAT_MS
                break
            moved = True
            if target is not None and (self.x, self.y) == target:
                break
        return moved

    def draw(self):
        image = self.current_animation.sprite(round(badge.ticks / 100) % BEE_FRAMES, 0)

        screen.blit(image, rect(self.x * wall_separation + offset_x,
                          self.y * wall_separation + offset_y,
                          wall_size, wall_size))


def build_maze():
    global wall_separation
    global wall_size
    global offset_x
    global offset_y
    global start
    global goal
    global hint, hint_remaining, hints_used

    hint = []
    hint_remaining = 0
    hints_used = 0

    difficulty = int(level * DIFFICULT_SCALE)
    width = random.randrange(MIN_MAZE_WIDTH, MAX_MAZE_WIDTH)
    height = random.randrange(MIN_MAZE_HEIGHT, MAX_MAZE_HEIGHT)
    maze_height = screen.height - HEADER_HEIGHT - FOOTER_HEIGHT
    # Keep even late-game mazes readable and bound generation / hint memory.
    max_width = max(2, (screen.width // MIN_TILE_SIZE - 1) // 2)
    max_height = max(2, (maze_height // MIN_TILE_SIZE - 1) // 2)
    builder.build(min(width + difficulty, max_width),
                  min(height + difficulty, max_height))

    wall_separation = min(maze_height // builder.grid_rows,
                          screen.width // builder.grid_columns)
    wall_size = wall_separation - WALL_GAP

    offset_x = (screen.width - (builder.grid_columns * wall_separation) + WALL_GAP) // 2
    offset_y = HEADER_HEIGHT + (maze_height - builder.grid_rows * wall_separation + WALL_GAP) // 2

    start = Position(1, builder.grid_rows - 2)
    goal = Position(builder.grid_columns - 2, 1)


# flower to mark our goal
flower = image.load("assets/flower.png")


def draw_maze():
    # Clear the screen to the background colour
    screen.blit(BACKGROUND, vec2(0, 0))

    # Draw the maze walls
    builder.draw()

    # Small pollen dots leave the hedge walls and the bee's own path visible.
    screen.pen = POLLEN
    dot = max(1, wall_size // 5)
    for x, y in hint:
        px = x * wall_separation + offset_x + (wall_size - dot) // 2
        py = y * wall_separation + offset_y + (wall_size - dot) // 2
        screen.rectangle(px, py, dot, dot)

    # Draw the goal location flower
    screen.blit(flower, rect(goal.x * wall_separation + offset_x,
                      goal.y * wall_separation + offset_y,
                      wall_size, wall_size))

    # Draw the player
    player.draw()

    draw_hud()


def count_label(count, noun):
    return "%d %s%s" % (count, noun, "" if count == 1 else "s")


def draw_hud():
    screen.pen = HUD
    screen.rectangle(0, 0, screen.width, HEADER_HEIGHT)
    screen.rectangle(0, screen.height - FOOTER_HEIGHT, screen.width, FOOTER_HEIGHT)
    screen.font = small_font
    shadow_text("LEVEL %d" % (level + 1), 6, 4)
    moves = count_label(player.moves, "move")
    width, _ = screen.measure_text(moves)
    shadow_text(moves, screen.width - width - 6, 4)
    text = "Follow the pollen!" if hint else "SELECT: pollen"
    shadow_text(text, 6, screen.height - FOOTER_HEIGHT + 3)
    count = count_label(hints_used, "hint")
    width, _ = screen.measure_text(count)
    shadow_text(count, screen.width - width - 6, screen.height - FOOTER_HEIGHT + 3)


def shadow_text(text, x, y):
    screen.pen = color.rgb(20, 40, 60, 100)
    screen.text(text, x + 1, y + 1)
    screen.pen = color.rgb(255, 255, 255)
    screen.text(text, x, y)


def center_text(text, y):
    w, _ = screen.measure_text(text)
    shadow_text(text, screen.width / 2 - (w / 2), y)


def intro():
    global state

    image = animations["down"].sprite(round(badge.ticks / 100) % BEE_FRAMES, 0)

    screen.blit(BACKGROUND, vec2(0, 0))
    screen.blit(image, rect((screen.width / 2) - 16, CY - 50, 32, 32))

    # draw title
    screen.font = large_font
    center_text("Bee a-maze'd!", CY - 10)
    screen.font = small_font
    center_text("Stuck? SELECT shows pollen", CY + 40)
    # blink button message
    if int(badge.ticks / 500) % 2:
        screen.font = small_font
        center_text("Press SELECT to start", CY + 20)

    if badge.pressed(BUTTON_SELECT):
        state = GameState.PLAYING


def draw_complete_banner(allow_continue=True):
    global level, complete

    screen.pen = WINDOW_COLOR
    screen.shape(shape.rounded_rectangle(10, CY - 34, screen.width - 20, 72, 5))

    # Draw text
    screen.font = small_font
    screen.pen = WHITE
    center_text(f"Level {level + 1} Complete!", CY - 25)
    center_text(count_label(player.moves, "move") + " / " +
                count_label(hints_used, "hint"), CY - 5)
    center_text("Press SELECT to continue", CY + 15)

    if allow_continue and badge.pressed(BUTTON_SELECT):
        complete = False
        level += 1
        build_maze()
        player.position(*start)


def init():
    global builder, player
    # Create the maze builder and build the first maze and put
    builder = MazeBuilder()
    build_maze()

    # Create the player object
    player = Player(*start)


def update():
    global complete, builder, player, level
    global hint, hint_remaining, hints_used

    if state == GameState.INTRO:
        intro()
        return

    if state == GameState.PLAYING:
        was_complete = complete

        if not complete:
            hint_remaining = max(0, hint_remaining - badge.ticks_delta)
            if hint and not hint_remaining:
                hint = []

            # Update the player's position in the maze
            if player.update(builder.maze, goal):
                hint = []
                hint_remaining = 0

            if badge.pressed(BUTTON_SELECT):
                hint = builder.pollen_trail((player.x, player.y), goal)
                hint_remaining = HINT_MS
                if hint:
                    hints_used += 1

            # Check if any player has reached the goal position
            if player.x == goal.x and player.y == goal.y:
                complete = True
                hint = []
                hint_remaining = 0

        draw_maze()
        if complete:
            draw_complete_banner(allow_continue=was_complete)


def on_exit():
    pass


init()
run(update)
