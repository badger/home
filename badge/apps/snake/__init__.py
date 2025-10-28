import sys
import os

from badgeware import screen, PixelFont, shapes, brushes, io, run
import random

# GitHub contribution graph colors (dark mode)
COMMIT_COLORS = [
    (25, 108, 46),    # #196c2e
    (46, 160, 67),    # #2ea043
    (86, 211, 100),   # #56d364
]

SNAKE_COLOR = (86, 211, 100)  # #56d364 - bright green
BACKGROUND_COLOR = (13, 17, 23)  # Dark GitHub background

# Game configuration
GRID_SIZE = 4  # Size of each square (includes 1px gap)
SQUARE_SIZE = 3  # Actual drawn size (GRID_SIZE - 1 for gap)
GRID_WIDTH = 40  # 160 / 4
GRID_HEIGHT = 30  # 120 / 4

# Load font
small_font = PixelFont.load("/system/assets/fonts/nope.ppf")

class GameState:
    INTRO = 1
    PLAYING = 2
    GAME_OVER = 3

class Snake:
    def __init__(self):
        self.reset()
    
    def reset(self):
        # Start in the middle
        start_x = GRID_WIDTH // 2
        start_y = GRID_HEIGHT // 2
        self.segments = [(start_x, start_y), (start_x - 1, start_y), (start_x - 2, start_y)]
        self.direction = (1, 0)  # Moving right
        self.next_direction = (1, 0)
        self.grow_pending = 0
    
    def set_direction(self, dx, dy):
        # Prevent reversing direction
        current_dx, current_dy = self.direction
        if (dx, dy) != (-current_dx, -current_dy):
            self.next_direction = (dx, dy)
    
    def update(self):
        self.direction = self.next_direction
        
        # Calculate new head position
        head_x, head_y = self.segments[0]
        dx, dy = self.direction
        new_head = ((head_x + dx) % GRID_WIDTH, (head_y + dy) % GRID_HEIGHT)
        
        # Check self collision
        if new_head in self.segments:
            return False
        
        # Add new head
        self.segments.insert(0, new_head)
        
        # Remove tail unless growing
        if self.grow_pending > 0:
            self.grow_pending -= 1
        else:
            self.segments.pop()
        
        return True
    
    def grow(self):
        self.grow_pending += 1
    
    def draw(self):
        screen.brush = brushes.color(*SNAKE_COLOR)
        for x, y in self.segments:
            screen.draw(shapes.rectangle(x * GRID_SIZE, y * GRID_SIZE, SQUARE_SIZE, SQUARE_SIZE))

class Commit:
    def __init__(self):
        self.respawn()
    
    def respawn(self):
        self.x = random.randint(0, GRID_WIDTH - 1)
        self.y = random.randint(0, GRID_HEIGHT - 1)
        self.color = random.choice(COMMIT_COLORS)
    
    def draw(self):
        screen.brush = brushes.color(*self.color)
        screen.draw(shapes.rectangle(self.x * GRID_SIZE, self.y * GRID_SIZE, SQUARE_SIZE, SQUARE_SIZE))

# Game state
state = GameState.INTRO
snake = Snake()
commit = Commit()
score = 0
last_update = 0
update_interval = 150  # milliseconds

def update():
    global state, score, last_update
    
    # Clear screen
    screen.brush = brushes.color(*BACKGROUND_COLOR)
    screen.draw(shapes.rectangle(0, 0, 160, 120))
    
    if state == GameState.INTRO:
        intro()
    elif state == GameState.PLAYING:
        play()
    elif state == GameState.GAME_OVER:
        game_over()

def intro():
    global state, snake, commit, score
    
    # Draw title
    screen.font = small_font
    screen.brush = brushes.color(255, 255, 255)
    
    title = "SNAKE"
    w, _ = screen.measure_text(title)
    screen.text(title, 80 - (w // 2), 30)
    
    subtitle = "Merge the commits!"
    w, _ = screen.measure_text(subtitle)
    screen.text(subtitle, 80 - (w // 2), 45)
    
    # Blink start message
    if int(io.ticks / 500) % 2:
        msg = "Press A to start"
        w, _ = screen.measure_text(msg)
        screen.text(msg, 80 - (w // 2), 70)
    
    # Draw some sample commits
    for i in range(3):
        x = 50 + i * 20
        color = COMMIT_COLORS[i]
        screen.brush = brushes.color(*color)
        screen.draw(shapes.rectangle(x, 90, SQUARE_SIZE, SQUARE_SIZE))
    
    if io.BUTTON_A in io.pressed:
        state = GameState.PLAYING
        snake.reset()
        commit.respawn()
        score = 0

def play():
    global state, score, last_update
    
    # Handle input
    if io.BUTTON_A in io.pressed:
        snake.set_direction(-1, 0)  # Left
    elif io.BUTTON_C in io.pressed:
        snake.set_direction(1, 0)   # Right
    elif io.BUTTON_UP in io.pressed:
        snake.set_direction(0, -1)  # Up
    elif io.BUTTON_DOWN in io.pressed:
        snake.set_direction(0, 1)   # Down
    
    # Update game logic
    if io.ticks - last_update > update_interval:
        last_update = io.ticks
        
        # Update snake position
        if not snake.update():
            state = GameState.GAME_OVER
            return
        
        # Check if snake ate the commit
        head = snake.segments[0]
        if head[0] == commit.x and head[1] == commit.y:
            score += 1
            snake.grow()
            commit.respawn()
            # Make sure commit doesn't spawn on snake
            while (commit.x, commit.y) in snake.segments:
                commit.respawn()
    
    # Draw everything
    commit.draw()
    snake.draw()
    
def game_over():
    global state
    
    # Draw game over screen
    screen.font = small_font
    screen.brush = brushes.color(255, 255, 255)
    
    title = "GAME OVER!"
    w, _ = screen.measure_text(title)
    screen.text(title, 80 - (w // 2), 30)
    
    score_text = f"Commits merged: {score}"
    w, _ = screen.measure_text(score_text)
    screen.text(score_text, 80 - (w // 2), 50)
    
    # Blink restart message
    if int(io.ticks / 500) % 2:
        msg = "Press A to restart"
        w, _ = screen.measure_text(msg)
        screen.text(msg, 80 - (w // 2), 70)
    
    if io.BUTTON_A in io.pressed:
        state = GameState.INTRO

if __name__ == "__main__":
    run(update)
