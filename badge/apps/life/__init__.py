from badgeware import screen, PixelFont, shapes, brushes, io, run, Matrix
import random


# Multiple color palettes for neighbor count
NEIGHBOR_PALETTES = {
    "github_dark": [
        (13, 17, 23),      # 0 neighbors - background (dead cell)
        (14, 68, 41),      # 1 neighbor - very dark green
        (0, 109, 50),      # 2 neighbors - dark green
        (25, 108, 46),     # 3 neighbors - #196c2e
        (38, 166, 65),     # 4 neighbors - medium green
        (46, 160, 67),     # 5 neighbors - #2ea043
        (57, 211, 83),     # 6 neighbors - bright green
        (86, 211, 100),    # 7 neighbors - #56d364
        (120, 255, 140),   # 8 neighbors - brightest green
    ],
    "github_light": [
        (255, 255, 255),   # 0 neighbors - background (dead cell)
        (198, 228, 139),   # 1 neighbor - very light green
        (123, 201, 111),   # 2 neighbors - light green
        (35, 154, 59),     # 3 neighbors - medium green
        (25, 97, 39),      # 4 neighbors - dark green
        (15, 70, 30),      # 5 neighbors - darker green
        (0, 109, 50),      # 6 neighbors - even darker
        (14, 68, 41),      # 7 neighbors - very dark
        (13, 17, 23),      # 8 neighbors - darkest
    ],
    "github_blue": [
        (13, 17, 23),      # 0 neighbors - background (dead cell)
        (20, 30, 60),      # 1 neighbor - very dark blue
        (30, 50, 100),     # 2 neighbors - dark blue
        (40, 70, 140),     # 3 neighbors - medium dark blue
        (60, 100, 180),    # 4 neighbors - medium blue
        (80, 130, 220),    # 5 neighbors - lighter blue
        (110, 160, 255),   # 6 neighbors - bright blue
        (150, 190, 255),   # 7 neighbors - lighter bright blue
        (200, 220, 255),   # 8 neighbors - lightest blue
    ],
    "classic": [
        (0, 0, 0),         # 0 neighbors - black
        (50, 50, 200),     # 1 neighbor - blue
        (50, 200, 50),     # 2 neighbors - green
        (200, 200, 50),    # 3 neighbors - yellow
        (200, 50, 50),     # 4 neighbors - red
        (200, 50, 200),    # 5 neighbors - magenta
        (50, 200, 200),    # 6 neighbors - cyan
        (150, 150, 150),   # 7 neighbors - gray
        (255, 255, 255),   # 8 neighbors - white
    ],
    "pastel": [
        (245, 245, 245),   # 0 neighbors - pastel gray
        (255, 179, 186),   # 1 neighbor - pastel pink
        (255, 223, 186),   # 2 neighbors - pastel orange
        (255, 255, 186),   # 3 neighbors - pastel yellow
        (186, 255, 201),   # 4 neighbors - pastel green
        (186, 225, 255),   # 5 neighbors - pastel blue
        (201, 186, 255),   # 6 neighbors - pastel purple
        (255, 186, 255),   # 7 neighbors - pastel magenta
        (220, 220, 220),   # 8 neighbors - pastel light gray
    ],
    "black_white": [
        (0, 0, 0),         # 0 neighbors - black
        (32, 32, 32),      # 1 neighbor - very dark gray
        (64, 64, 64),      # 2 neighbors - dark gray
        (96, 96, 96),      # 3 neighbors - gray
        (128, 128, 128),   # 4 neighbors - medium gray
        (160, 160, 160),   # 5 neighbors - light gray
        (192, 192, 192),   # 6 neighbors - lighter gray
        (224, 224, 224),   # 7 neighbors - very light gray
        (255, 255, 255),   # 8 neighbors - white
    ],
}

# Select active palette
ACTIVE_PALETTE = "github_dark"
def set_palette(name):
    global ACTIVE_PALETTE, NEIGHBOR_COLORS, NEIGHBOR_BRUSHES, BACKGROUND_COLOR, BACKGROUND_BRUSH
    if name in NEIGHBOR_PALETTES:
        ACTIVE_PALETTE = name
        NEIGHBOR_COLORS = NEIGHBOR_PALETTES[ACTIVE_PALETTE]
        NEIGHBOR_BRUSHES = [brushes.color(*color) for color in NEIGHBOR_COLORS]
        BACKGROUND_COLOR = NEIGHBOR_COLORS[0]
        BACKGROUND_BRUSH = brushes.color(*BACKGROUND_COLOR)
    else:
        raise ValueError(f"Palette '{name}' not found.")

NEIGHBOR_COLORS = NEIGHBOR_PALETTES[ACTIVE_PALETTE]

# Always use the first color of the active palette as background
BACKGROUND_COLOR = NEIGHBOR_COLORS[0]
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

# Probability of injecting static life patterns when stagnant
STATIC_LIFE_PROBABILITY = 0.4

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

# Static life patterns (static, don't change)
STATIC_LIFE = {
    'block': [(0, 0), (1, 0), (0, 1), (1, 1)],
    'beehive': [(1, 0), (2, 0), (0, 1), (3, 1), (1, 2), (2, 2)],
    'loaf': [(1, 0), (2, 0), (0, 1), (3, 1), (1, 2), (3, 2), (2, 3)],
    'boat': [(0, 0), (1, 0), (0, 1), (2, 1), (1, 2)],
    'tub': [(1, 0), (0, 1), (2, 1), (1, 2)],
    'ship': [(0, 0), (1, 0), (0, 1), (2, 1), (1, 2), (2, 2)],
    'barge': [(1, 0), (2, 0), (0, 1), (3, 1), (0, 2), (3, 2), (1, 3), (2, 3)],
}

class GameOfLife:
    def __init__(self):
        self.grid = [[False for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.next_grid = [[False for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.neighbor_counts = [[0 for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.generation = 0
        self.last_update = 0
        self.update_interval = 100  # milliseconds
        self.history = []  # Store recent grid states for pattern detection
        self.history_size = 10  # Check last 10 states
        self.stagnant_count = 0  # How many generations have been static/oscillating
        self.last_regen = 0  # Track time of last full regeneration
        self.regen_interval = 600000  # 10 minutes in milliseconds
        self.randomize()
    
    def randomize(self):
        """Initialize grid with random cells"""
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                self.grid[y][x] = random.random() < 0.35  # 35% chance of being alive
        self.generation = 0
        self.history = []
        self.stagnant_count = 0
        self.last_regen = io.ticks
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
        # Check if it's a static life or regular pattern
        if pattern_name in STATIC_LIFE:
            pattern = STATIC_LIFE[pattern_name]
        else:
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
                # 40% chance to add static life patterns, 60% chance for moving patterns
                if random.random() < STATIC_LIFE_PROBABILITY:
                    # Add 1-3 static life patterns to create obstacles/targets
                    num_static_lifes = random.randint(1, 3)
                    static_life_names = list(STATIC_LIFE.keys())
                    for _ in range(num_static_lifes):
                        pattern = random.choice(static_life_names)
                        self.inject_pattern(pattern)
                
                # Add a moving or oscillating pattern
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
info_message = ""

def update():
    global show_info, info_timer, info_message
    
    # Clear screen with pre-created brush
    screen.brush = BACKGROUND_BRUSH
    screen.clear()
    

    # Handle input
    if io.BUTTON_B in io.pressed:
        game.randomize()
        show_info = True
        info_message = "Regenerated!"
        info_timer = io.ticks + 1000  # Show "Regenerated" for 1 second    
    if io.BUTTON_C in io.pressed:
        # Cycle palette
        palette_names = list(NEIGHBOR_PALETTES.keys())
        current_index = palette_names.index(ACTIVE_PALETTE)
        next_index = (current_index + 1) % len(palette_names)
        set_palette(palette_names[next_index])
        show_info = True
        info_message = f"Palette: {palette_names[next_index]}"
        info_timer = io.ticks + 1000  # Show palette name for 1 second
    # Check for auto-regeneration every 10 minutes
    if io.ticks - game.last_regen > game.regen_interval:
        game.randomize()
        # Don't show message for automatic regeneration
    
    # Update game logic
    if io.ticks - game.last_update > game.update_interval:
        game.last_update = io.ticks
        game.update()
    
    # Draw the grid
    game.draw()
    
    # Show info message
    if show_info and io.ticks < info_timer:
        w, _ = screen.measure_text(info_message)
        # Draw background for text
        screen.brush = INFO_BG_BRUSH
        screen.draw(shapes.rectangle(80 - (w // 2) - 2, 55, w + 4, 10))
        # Draw text
        screen.brush = TEXT_BRUSH
        screen.text(info_message, 80 - (w // 2), 56)
    elif io.ticks >= info_timer:
        show_info = False

if __name__ == "__main__":
    run(update)
