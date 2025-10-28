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

# Pre-create brushes for performance
NEIGHBOR_BRUSHES = [brushes.color(*color) for color in NEIGHBOR_COLORS]
BACKGROUND_BRUSH = brushes.color(*BACKGROUND_COLOR)
TEXT_BRUSH = brushes.color(*TEXT_COLOR)
INFO_BG_BRUSH = brushes.color(0, 0, 0, 200)

# Game configuration
GRID_SIZE = 4  # Size of each square (includes 1px gap)
SQUARE_SIZE = 3  # Actual drawn size (GRID_SIZE - 1 for gap)
GRID_WIDTH = 40  # 160 / 4
GRID_HEIGHT = 30  # 120 / 4

# Load font
small_font = PixelFont.load("/system/assets/fonts/nope.ppf")

# Pre-create shape for cells (reused for all cells)
cell_rect = shapes.rectangle(0, 0, SQUARE_SIZE, SQUARE_SIZE)

class GameOfLife:
    def __init__(self):
        self.grid = [[False for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.next_grid = [[False for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
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
    
    def update(self):
        """Apply Conway's Game of Life rules"""
        # First pass: count neighbors and apply rules
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                # Count neighbors inline
                count = 0
                y_prev = (y - 1) % GRID_HEIGHT
                y_next = (y + 1) % GRID_HEIGHT
                x_prev = (x - 1) % GRID_WIDTH
                x_next = (x + 1) % GRID_WIDTH
                
                # Unrolled loop for speed (avoid nested loops)
                if self.grid[y_prev][x_prev]: count += 1
                if self.grid[y_prev][x]: count += 1
                if self.grid[y_prev][x_next]: count += 1
                if self.grid[y][x_prev]: count += 1
                if self.grid[y][x_next]: count += 1
                if self.grid[y_next][x_prev]: count += 1
                if self.grid[y_next][x]: count += 1
                if self.grid[y_next][x_next]: count += 1
                
                # Apply Conway's rules
                is_alive = self.grid[y][x]
                
                # Optimized rules check
                if is_alive:
                    self.next_grid[y][x] = (count == 2 or count == 3)
                else:
                    self.next_grid[y][x] = (count == 3)
        
        # Swap grids (avoid allocation)
        self.grid, self.next_grid = self.next_grid, self.grid
        self.generation += 1
        
        # Second pass: calculate neighbor counts for the NEW grid state (for coloring)
        for y in range(GRID_HEIGHT):
            y_prev = (y - 1) % GRID_HEIGHT
            y_next = (y + 1) % GRID_HEIGHT
            for x in range(GRID_WIDTH):
                x_prev = (x - 1) % GRID_WIDTH
                x_next = (x + 1) % GRID_WIDTH
                
                count = 0
                if self.grid[y_prev][x_prev]: count += 1
                if self.grid[y_prev][x]: count += 1
                if self.grid[y_prev][x_next]: count += 1
                if self.grid[y][x_prev]: count += 1
                if self.grid[y][x_next]: count += 1
                if self.grid[y_next][x_prev]: count += 1
                if self.grid[y_next][x]: count += 1
                if self.grid[y_next][x_next]: count += 1
                
                self.neighbor_counts[y][x] = count
    
    def calculate_neighbors(self):
        """Calculate neighbor counts for all cells (used only on init)"""
        for y in range(GRID_HEIGHT):
            y_prev = (y - 1) % GRID_HEIGHT
            y_next = (y + 1) % GRID_HEIGHT
            for x in range(GRID_WIDTH):
                x_prev = (x - 1) % GRID_WIDTH
                x_next = (x + 1) % GRID_WIDTH
                
                count = 0
                if self.grid[y_prev][x_prev]: count += 1
                if self.grid[y_prev][x]: count += 1
                if self.grid[y_prev][x_next]: count += 1
                if self.grid[y][x_prev]: count += 1
                if self.grid[y][x_next]: count += 1
                if self.grid[y_next][x_prev]: count += 1
                if self.grid[y_next][x]: count += 1
                if self.grid[y_next][x_next]: count += 1
                
                self.neighbor_counts[y][x] = count
    
    def draw(self):
        """Draw the grid with colors based on neighbor count"""
        # Use pre-created shape and brushes for performance
        from badgeware import Matrix
        for y in range(GRID_HEIGHT):
            py = y * GRID_SIZE
            for x in range(GRID_WIDTH):
                if self.grid[y][x]:
                    # Alive cells - color based on neighbor count
                    neighbors = self.neighbor_counts[y][x]
                    screen.brush = NEIGHBOR_BRUSHES[neighbors]
                    cell_rect.transform = Matrix().translate(x * GRID_SIZE, py)
                    screen.draw(cell_rect)

# Game state
game = GameOfLife()
show_info = False
info_timer = 0

def update():
    global show_info, info_timer
    
    # Clear screen with pre-created brush
    screen.brush = BACKGROUND_BRUSH
    screen.clear()
    
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
        screen.brush = INFO_BG_BRUSH
        screen.draw(shapes.rectangle(80 - (w // 2) - 2, 55, w + 4, 10))
        # Draw text
        screen.brush = TEXT_BRUSH
        screen.text(msg, 80 - (w // 2), 56)
    elif io.ticks >= info_timer:
        show_info = False

if __name__ == "__main__":
    run(update)
