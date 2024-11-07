import badger2040
from machine import Pin
import random
import time
import io



# Initialize the display
display = badger2040.Badger2040()
display.set_update_speed(badger2040.UPDATE_TURBO)

def clear_screen():
    display.set_pen(15)
    display.clear()
    display.set_pen(0)

# Initialize buttons
button_a = Pin(badger2040.BUTTON_A, Pin.IN, Pin.PULL_DOWN)
button_b = Pin(badger2040.BUTTON_B, Pin.IN, Pin.PULL_DOWN)
button_c = Pin(badger2040.BUTTON_C, Pin.IN, Pin.PULL_DOWN)
button_up = Pin(badger2040.BUTTON_UP, Pin.IN, Pin.PULL_DOWN)
button_down = Pin(badger2040.BUTTON_DOWN, Pin.IN, Pin.PULL_DOWN)

# Display dimensions
WIDTH = 296
HEIGHT = 128

# Game dimensions - note we're rotating the display 90 degrees
# So our width is limited by the Badger's HEIGHT (128)
# And our height can use the Badger's WIDTH (296)
BOARD_WIDTH = 20
BOARD_HEIGHT = 48
BLOCK_SIZE = 6  # Each tetris block will be 6x6 pixels

# Center the board horizontally in the rotated display
# The display height (128) becomes our width after rotation
BOARD_X_OFFSET = (HEIGHT - (BOARD_WIDTH * BLOCK_SIZE)) // 2

# Give some space at the top for score
# Position board to reach bottom of screen
# Calculate space needed for board and position it to reach bottom
BOARD_Y_OFFSET = HEIGHT - (BOARD_WIDTH * BLOCK_SIZE) - 10  # 10px padding from bottom


# Tetromino shapes
TETROMINOS = [
    [[1, 1, 1, 1]],  # I
    [[1, 1], [1, 1]],  # O
    [[1, 1, 1], [0, 1, 0]],  # T
    [[1, 1, 1], [1, 0, 0]],  # L
    [[1, 1, 1], [0, 0, 1]],  # J
    [[1, 1, 0], [0, 1, 1]],  # S
    [[0, 1, 1], [1, 1, 0]]   # Z
]

class Tetris:
    def __init__(self):
        # Initialize board with rotated dimensions
        self.board = [[0] * BOARD_WIDTH for _ in range(BOARD_HEIGHT)]
        self.score = 0
        self.game_over = True
        self.current_piece = None
        self.current_x = 0
        self.current_y = 0
        
    def new_game(self):
        self.board = [[0] * BOARD_WIDTH for _ in range(BOARD_HEIGHT)]
        self.score = 0
        self.game_over = False
        self.spawn_piece()
        
    def spawn_piece(self):
        self.current_piece = random.choice(TETROMINOS)
        # Start from left side (was top)
        self.current_x = 0
        # Center vertically (was horizontally)
        self.current_y = BOARD_WIDTH // 2 - len(self.current_piece[0]) // 2
        
        if not self.is_valid_move(self.current_x, self.current_y, self.current_piece):
            self.game_over = True
            
    def rotate_piece(self, clockwise=True):
        if not self.current_piece:
            return
            
        rows = len(self.current_piece)
        cols = len(self.current_piece[0])
        
        rotated = [[0] * rows for _ in range(cols)]
        
        if clockwise:
            for r in range(rows):
                for c in range(cols):
                    rotated[c][rows-1-r] = self.current_piece[r][c]
        else:
            for r in range(rows):
                for c in range(cols):
                    rotated[cols-1-c][r] = self.current_piece[r][c]
                    
        if self.is_valid_move(self.current_x, self.current_y, rotated):
            self.current_piece = rotated
            
    def is_valid_move(self, x, y, piece):
        for row in range(len(piece)):
            for col in range(len(piece[0])):
                if piece[row][col]:
                    board_x = x + col
                    board_y = y + row
                    
                    if (board_x < 0 or board_x >= BOARD_HEIGHT or  # Changed WIDTH to HEIGHT
                        board_y < 0 or board_y >= BOARD_WIDTH or   # Changed HEIGHT to WIDTH
                        self.board[board_x][board_y]):             # Swapped x/y
                        return False
        return True
        
    def move(self, dx, dy):
        if not self.current_piece:
            return
            
        new_x = self.current_x + dx
        new_y = self.current_y + dy
        
        if self.is_valid_move(new_x, new_y, self.current_piece):
            self.current_x = new_x
            self.current_y = new_y
            return True
        return False
        
    def merge_piece(self):
        for row in range(len(self.current_piece)):
            for col in range(len(self.current_piece[0])):
                if self.current_piece[row][col]:
                    self.board[self.current_x + col][self.current_y + row] = 1  # Swapped x/y
                    
    def clear_lines(self):
        lines_cleared = 0
        x = BOARD_HEIGHT - 1  # Changed from y to x since we're moving rightward
        while x >= 0:
            if all(self.board[x]):
                lines_cleared += 1
                # Move all columns right-to-left
                for move_x in range(x, 0, -1):
                    self.board[move_x] = self.board[move_x - 1][:]
                self.board[0] = [0] * BOARD_WIDTH
            else:
                x -= 1
        self.score += lines_cleared * 100
        
    def draw(self):
        clear_screen()
        display.clear()
        
        # Draw board frame - note the swapped dimensions
        display.set_pen(15)
        display.rectangle(
            BOARD_X_OFFSET - 2,
            BOARD_Y_OFFSET - 2,
            BOARD_HEIGHT * BLOCK_SIZE + 4,  # Width is now height
            BOARD_WIDTH * BLOCK_SIZE + 4    # Height is now width
        )
        
        # Draw board contents - with rotated coordinates
        display.set_pen(0)
        for x in range(BOARD_HEIGHT):  # Outer loop is now x
            for y in range(BOARD_WIDTH):  # Inner loop is now y
                if self.board[x][y]:
                    display.rectangle(
                        BOARD_X_OFFSET + x * BLOCK_SIZE,
                        BOARD_Y_OFFSET + y * BLOCK_SIZE,
                        BLOCK_SIZE - 1,
                        BLOCK_SIZE - 1
                    )
                    
        # Draw current piece - also with rotated coordinates
        if self.current_piece:
            for row in range(len(self.current_piece)):
                for col in range(len(self.current_piece[0])):
                    if self.current_piece[row][col]:
                        display.rectangle(
                            BOARD_X_OFFSET + (self.current_x + col) * BLOCK_SIZE,
                            BOARD_Y_OFFSET + (self.current_y + row) * BLOCK_SIZE,
                            BLOCK_SIZE - 1,
                            BLOCK_SIZE - 1
                        )

        display.set_pen(15)  # White text
        score_text = f"Score: {self.score}"
        # Position score at top right of board
        display.text(score_text, 
                    BOARD_X_OFFSET + BOARD_HEIGHT * BLOCK_SIZE + 15,  # Move right of board
                    BOARD_Y_OFFSET + BOARD_WIDTH * BLOCK_SIZE - 10,   # Near top of board
                    angle=270)  # Rotate text 270 degrees (same as 90 degrees counterclockwise)
        
        
        if self.game_over:
            # Center the game over text
            display.text("Game Over!", BOARD_X_OFFSET + (BOARD_HEIGHT * BLOCK_SIZE) // 2 - 30, 
                        BOARD_Y_OFFSET + (BOARD_WIDTH * BLOCK_SIZE) // 2)
            display.text("Press A to exit", BOARD_X_OFFSET + (BOARD_HEIGHT * BLOCK_SIZE) // 2 - 30, 
                        BOARD_Y_OFFSET + (BOARD_WIDTH * BLOCK_SIZE) // 2 + 15)
            
        display.update()
        

def start_text():
    clear_screen()
    display.set_update_speed(badger2040.UPDATE_NORMAL)
    
    display.set_pen(0)
    display.set_thickness(2)
    
    # Title - moved up slightly
    display.text("TETRIS", WIDTH//2 - 40, 10, 2)
    display.set_thickness(1)
    
    # Better separated columns
    left_x = 30
    right_x = WIDTH//2 + 30
    y = 40  # Start content lower
    
    display.text("Rotate 90°!", left_x, y)
    display.text(f"High Score: {high_score}", right_x-25, y)
    
    # Controls with more vertical spacing
    y += 20  # Increased spacing
    y += 20
    display.text("UP:R | DN:L | B:CW | C:CCW", left_x, y)
    y += 20
    display.text("UP:Start | A: QUIT", left_x, y)
    
    display.update()


def game_loop():
    display.set_update_speed(badger2040.UPDATE_TURBO)
    game = Tetris()
    game.new_game()
    last_drop = time.ticks_ms()
    drop_delay = 200  # Time in ms between piece drops
    
    while not game.game_over:
        current_time = time.ticks_ms()
        
        # Handle input
        if button_up.value():
            game.move(0, -1)
            time.sleep(0.1)
        if button_down.value():
            game.move(0, 1)
            time.sleep(0.1)
        if button_c.value():
            game.rotate_piece(clockwise=True)
            time.sleep(0.2)
        if button_b.value():
            game.rotate_piece(clockwise=False)
            time.sleep(0.2)
        if button_a.value():
            game.game_over = True
            time.sleep(0.2)
            
        # Handle automatic dropping
        if time.ticks_diff(current_time, last_drop) > drop_delay:
            if not game.move(1, 0):
                game.merge_piece()
                game.clear_lines()
                game.spawn_piece()
            last_drop = current_time
            
        game.draw()
    
    return game.score

def main():
    global high_score
    
    # Initialize high score
    high_score = 0
    high_score_path = "tetris_high_score.txt"
    
    try:
        with io.open(high_score_path, "r") as f:
            high_score = int(f.read().strip())
    except (OSError, ValueError):
        # If file doesn't exist or contains invalid data
        high_score = 0
    clear_screen()
    start_text()
    while True:
        if button_up.value():
            score = game_loop()
            if score is not None and score > high_score:
                high_score = score
                print("Saving new high score: " + str(high_score))
                with io.open(high_score_path, "w") as f:
                    f.write(str(score))
            start_text()
        elif button_a.value():
            clear_screen()
            display.set_update_speed(badger2040.UPDATE_FAST)
            display.update()
            start_text()
            # badger2040.turn_off()
        time.sleep(0.1)  # Debounce


main()
