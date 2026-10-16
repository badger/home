"""
A single player game demo. Navigate a set of mazes from the start (red) to the goal (green).
Mazes get bigger / harder with each increase in level.

Controls:
* U = Move Forward
* D = Move Backward
* C = Move Right
* A = Move left
* B = Continue (once the current level is complete)
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

# Variables
complete = False                                # Has the game been completed?
level = 0                                       # The current "level" the player is on (affects difficulty)

player = None
builder = None


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
        self.x = x
        self.y = y
        self.last_move = badge.ticks

        self.current_animation = animations["right"]

    def position(self, x, y):
        self.x = x
        self.y = y

    def update(self, maze):

        if badge.ticks - self.last_move > 20:
            if badge.held(BUTTON_LEFT) and maze[self.y][self.x - 1] < (1 << WALL_BITSHIFT):
                maze[self.y][self.x] |= W
                self.x -= 1
                maze[self.y][self.x] |= E
                self.current_animation = animations["left"]
                self.last_move = badge.ticks

            elif badge.held(BUTTON_RIGHT) and maze[self.y][self.x + 1] < (1 << WALL_BITSHIFT):
                maze[self.y][self.x] |= E
                self.x += 1
                maze[self.y][self.x] |= W
                self.current_animation = animations["right"]
                self.last_move = badge.ticks

            elif badge.held(BUTTON_UP) and maze[self.y - 1][self.x] < (1 << WALL_BITSHIFT):
                maze[self.y][self.x] |= N
                self.y -= 1
                maze[self.y][self.x] |= S
                self.current_animation = animations["up"]
                self.last_move = badge.ticks

            elif badge.held(BUTTON_DOWN) and maze[self.y + 1][self.x] < (1 << WALL_BITSHIFT):
                maze[self.y][self.x] |= S
                self.y += 1
                maze[self.y][self.x] |= N
                self.current_animation = animations["down"]
                self.last_move = badge.ticks

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

    difficulty = int(level * DIFFICULT_SCALE)
    width = random.randrange(MIN_MAZE_WIDTH, MAX_MAZE_WIDTH)
    height = random.randrange(MIN_MAZE_HEIGHT, MAX_MAZE_HEIGHT)
    builder.build(width + difficulty, height + difficulty)

    wall_separation = min(screen.height // builder.grid_rows,
                          screen.width // builder.grid_columns)
    wall_size = wall_separation - WALL_GAP

    offset_x = (screen.width - (builder.grid_columns * wall_separation) + WALL_GAP) // 2
    offset_y = (screen.height - (builder.grid_rows * wall_separation) + WALL_GAP) // 2

    start = Position(1, builder.grid_rows - 2)
    goal = Position(builder.grid_columns - 2, 1)


# flower to mark our goal
flower = image.load("assets/flower.png")


def draw_maze():
    # Clear the screen to the background colour
    screen.blit(BACKGROUND, vec2(0, 0))

    # Draw the maze walls
    builder.draw()

    # Draw the goal location flower
    screen.blit(flower, rect(goal.x * wall_separation + offset_x,
                      goal.y * wall_separation + offset_y,
                      wall_size, wall_size))

    # Draw the player
    player.draw()


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
    # blink button message
    if int(badge.ticks / 500) % 2:
        screen.font = small_font
        center_text("Press SELECT to start", CY + 20)

    if badge.pressed(BUTTON_SELECT):
        state = GameState.PLAYING


def draw_complete_banner():
    global level, complete

    screen.pen = WINDOW_COLOR
    screen.shape(shape.rounded_rectangle(10, CY - 24, screen.width - 20, 50, 5))

    # Draw text
    screen.font = small_font
    screen.pen = WHITE
    center_text(f"Level {level + 1} Complete!", CY - 15)
    center_text("Press SELECT to continue", CY + 5)

    if badge.pressed(BUTTON_SELECT):
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

    if state == GameState.INTRO:
        intro()

    if state == GameState.PLAYING:

        draw_maze()

        if not complete:
            # Update the player's position in the maze
            player.update(builder.maze)

            # Check if any player has reached the goal position
            if player.x == goal.x and player.y == goal.y:
                complete = True

        if complete:
            draw_complete_banner()


def on_exit():
    pass


init()
run(update)
