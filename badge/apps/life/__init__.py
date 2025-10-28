import sys
import os

from badgeware import screen, PixelFont, shapes, brushes, io, run
import random

# GitHub contribution graph colors (dark mode) - based on neighbor count
NEIGHBOR_COLORS = [
    (13, 17, 23),      # 0 neighbors - background (dead cell)
    (14, 68, 41),      # 1 neighbor - very dark green
    (0, 109, 50),      # 2 neighbors - dark green
    (25, 108, 46),     # 3 neighbors - #196c2e
    (38, 166, 65),     # 4 neighbors - medium green
    (46, 160, 67),     # 5 neighbors - #2ea043
    (57, 211, 83),     # 6 neighbors - bright green
    (86, 211, 100),    # 7 neighbors - #56d364
    (120, 255, 140),   # 8 neighbors - brightest green
]

BACKGROUND_COLOR = (13, 17, 23)  # Dark GitHub background
TEXT_COLOR = (255, 255, 255)

# Game configuration
GRID_SIZE = 4  # Size of each square (includes 1px gap)
SQUARE_SIZE = 3  # Actual drawn size (GRID_SIZE - 1 for gap)
GRID_WIDTH = 40  # 160 / 4
GRID_HEIGHT = 30  # 120 / 4

# Load font
small_font = PixelFont.load("/system/assets/fonts/nope.ppf")

class GameOfLife:
    def __init__(self):
        self.grid = [[False for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.neighbor_counts = [[0 for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.generation = 0
        self.last_update = 0
        self.update_interval = 200  # milliseconds
        self.randomize()
    
    def randomize(self):
        """Initialize grid with random cells"""
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                self.grid[y][x] = random.random() < 0.35  # 35% chance of being alive
        self.generation = 0
        self.calculate_neighbors()
    
    def count_neighbors(self, x, y):
        """Count live neighbors around cell at (x, y)"""
        count = 0
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx = (x + dx) % GRID_WIDTH  # Wrap around edges
                ny = (y + dy) % GRID_HEIGHT
                if self.grid[ny][nx]:
                    count += 1
        return count
    
    def calculate_neighbors(self):
        """Calculate neighbor counts for all cells"""
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                self.neighbor_counts[y][x] = self.count_neighbors(x, y)
    
    def update(self):
        """Apply Conway's Game of Life rules"""
        new_grid = [[False for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                neighbors = self.neighbor_counts[y][x]
                is_alive = self.grid[y][x]
                
                # Conway's rules:
                # 1. Any live cell with 2 or 3 neighbors survives
                # 2. Any dead cell with exactly 3 neighbors becomes alive
                # 3. All other cells die or stay dead
                if is_alive:
                    new_grid[y][x] = neighbors in [2, 3]
                else:
                    new_grid[y][x] = neighbors == 3
        
        self.grid = new_grid
        self.generation += 1
        self.calculate_neighbors()
    
    def draw(self):
        """Draw the grid with colors based on neighbor count"""
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                if self.grid[y][x]:
                    # Alive cells - color based on neighbor count
                    neighbors = self.neighbor_counts[y][x]
                    color = NEIGHBOR_COLORS[neighbors]
                    screen.brush = brushes.color(*color)
                    screen.draw(shapes.rectangle(x * GRID_SIZE, y * GRID_SIZE, SQUARE_SIZE, SQUARE_SIZE))

# Game state
game = GameOfLife()
show_info = False
info_timer = 0

def update():
    global show_info, info_timer
    
    # Clear screen
    screen.brush = brushes.color(*BACKGROUND_COLOR)
    screen.draw(shapes.rectangle(0, 0, 160, 120))
    
    # Handle input
    if io.BUTTON_B in io.pressed:
        game.randomize()
        show_info = True
        info_timer = io.ticks + 1000  # Show "Regenerated" for 1 second
    
    # Update game logic
    if io.ticks - game.last_update > game.update_interval:
        game.last_update = io.ticks
        game.update()
    
    # Draw the grid
    game.draw()
    
    # Show regeneration message
    if show_info and io.ticks < info_timer:
        msg = "Regenerated!"
        w, _ = screen.measure_text(msg)
        # Draw background for text
        screen.brush = brushes.color(0, 0, 0, 200)
        screen.draw(shapes.rectangle(80 - (w // 2) - 2, 55, w + 4, 10))
        # Draw text
        screen.brush = brushes.color(*TEXT_COLOR)
        screen.text(msg, 80 - (w // 2), 56)
    elif io.ticks >= info_timer:
        show_info = False

if __name__ == "__main__":
    run(update)
