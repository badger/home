from badgeware import screen, PixelFont, shapes, brushes, io, run, Matrix
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

# Interesting Life patterns (name, pattern as list of (x, y) offsets)
PATTERNS = {
    # Spaceships (moving patterns)
    'glider': [(1, 0), (2, 1), (0, 2), (1, 2), (2, 2)],
    'lwss': [(1, 0), (4, 0), (0, 1), (0, 2), (4, 2), (0, 3), (1, 3), (2, 3), (3, 3)],  # Lightweight spaceship
    
    # Oscillators
    'blinker': [(0, 1), (1, 1), (2, 1)],
    'toad': [(1, 0), (2, 0), (3, 0), (0, 1), (1, 1), (2, 1)],
    'beacon': [(0, 0), (1, 0), (0, 1), (3, 2), (2, 3), (3, 3)],
    'pulsar': [  # Period-3 oscillator
        (2, 0), (3, 0), (4, 0), (8, 0), (9, 0), (10, 0),
        (0, 2), (5, 2), (7, 2), (12, 2),
        (0, 3), (5, 3), (7, 3), (12, 3),
        (0, 4), (5, 4), (7, 4), (12, 4),
        (2, 5), (3, 5), (4, 5), (8, 5), (9, 5), (10, 5),
        (2, 7), (3, 7), (4, 7), (8, 7), (9, 7), (10, 7),
        (0, 8), (5, 8), (7, 8), (12, 8),
        (0, 9), (5, 9), (7, 9), (12, 9),
        (0, 10), (5, 10), (7, 10), (12, 10),
        (2, 12), (3, 12), (4, 12), (8, 12), (9, 12), (10, 12),
    ],
    
    # Small interesting patterns
    'r_pentomino': [(1, 0), (2, 0), (0, 1), (1, 1), (1, 2)],  # Creates chaos for ~1000 gens
    'acorn': [(1, 0), (3, 1), (0, 2), (1, 2), (4, 2), (5, 2), (6, 2)],  # Takes 5206 generations to stabilize
}

class GameOfLife:
    def __init__(self):
        self.grid = [[False for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.next_grid = [[False for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.neighbor_counts = [[0 for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.generation = 0
        self.last_update = 0
        self.update_interval = 200  # milliseconds
        self.history = []  # Store recent grid states for pattern detection
        self.history_size = 10  # Check last 10 states
        self.stagnant_count = 0  # How many generations have been static/oscillating
        self.randomize()
    
    def randomize(self):
        """Initialize grid with random cells"""
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                self.grid[y][x] = random.random() < 0.35  # 35% chance of being alive
        self.generation = 0
        self.history = []
        self.stagnant_count = 0
        self.calculate_neighbors()
    
    def count_neighbors(self, x, y):
        """Count alive neighbors for a given cell position"""
        y_prev = (y - 1) % GRID_HEIGHT
        y_next = (y + 1) % GRID_HEIGHT
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
        
        return count
    
    def get_grid_hash(self):
        """Create a hashable representation of current grid state"""
        return tuple(tuple(row) for row in self.grid)
    
    def is_stagnant(self):
        """Check if grid is static or oscillating"""
        current = self.get_grid_hash()
        
        # Check if current state matches any recent state
        for old_state in self.history:
            if current == old_state:
                return True
        return False
    
    def inject_pattern(self, pattern_name):
        """Inject an interesting pattern at a random location"""
        pattern = PATTERNS[pattern_name]
        
        # Find pattern bounds
        max_x = max(p[0] for p in pattern)
        max_y = max(p[1] for p in pattern)
        
        # Choose random position with padding
        start_x = random.randint(2, GRID_WIDTH - max_x - 3)
        start_y = random.randint(2, GRID_HEIGHT - max_y - 3)
        
        # Place pattern
        for dx, dy in pattern:
            x = (start_x + dx) % GRID_WIDTH
            y = (start_y + dy) % GRID_HEIGHT
            self.grid[y][x] = True
        
        # Reset stagnancy tracking
        self.history = []
        self.stagnant_count = 0
        self.calculate_neighbors()
    
    def update(self):
        """Apply Conway's Game of Life rules"""
        # First pass: count neighbors and apply rules
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                # Count neighbors using helper method
                count = self.count_neighbors(x, y)
                
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
        
        # Check for stagnation and inject patterns if needed
        if self.is_stagnant():
            self.stagnant_count += 1
            if self.stagnant_count >= 5:  # If stagnant for 5+ generations
                # Choose a random interesting pattern with weights
                # More likely to pick gliders, spaceships, and interesting patterns
                pattern_pool = [
                    'glider', 'glider', 'glider',  # 3x weight
                    'lwss', 'lwss', 'lwss',  # 3x weight
                    'blinker',
                    'toad',
                    'beacon',
                    'pulsar', 'pulsar',  # 2x weight
                    'r_pentomino', 'r_pentomino',  # 2x weight
                    'acorn'
                ]
                pattern = random.choice(pattern_pool)
                self.inject_pattern(pattern)
        else:
            self.stagnant_count = 0
        
        # Update history for pattern detection
        self.history.append(self.get_grid_hash())
        if len(self.history) > self.history_size:
            self.history.pop(0)
        
        # Second pass: calculate neighbor counts for the NEW grid state (for coloring)
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                self.neighbor_counts[y][x] = self.count_neighbors(x, y)
    
    def calculate_neighbors(self):
        """Calculate neighbor counts for all cells (used only on init)"""
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                self.neighbor_counts[y][x] = self.count_neighbors(x, y)
    
    def draw(self):
        """Draw the grid with colors based on neighbor count"""
        # Use pre-created shape and brushes for performance
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
