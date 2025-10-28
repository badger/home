import sys
import os

from badgeware import screen, PixelFont, shapes, brushes, io, run
import random

# GitHub contribution graph colors (dark mode)
COMMIT_COLORS = [
    (25, 108, 46),    # #196c2e - dark green
    (46, 160, 67),    # #2ea043 - medium green
    (86, 211, 100),   # #56d364 - bright green
]

PADDLE_COLOR = (86, 211, 100)  # #56d364 - bright green
BALL_COLOR = (163, 113, 247)   # #a371f7 - purple (GitHub purple accent)
BACKGROUND_COLOR = (13, 17, 23)  # Dark GitHub background

# Game configuration
SQUARE_SIZE = 6  # Size of each square
SQUARE_GAP = 1   # Gap between squares
UNIT = SQUARE_SIZE + SQUARE_GAP  # Total unit size (7 pixels)

# Screen dimensions
SCREEN_WIDTH = 160
SCREEN_HEIGHT = 120

# Brick configuration
BRICK_COLS = 22  # Fill screen width (160 / 7 ≈ 22)
BRICK_ROWS = 5
BRICK_WIDTH = SQUARE_SIZE
BRICK_HEIGHT = SQUARE_SIZE
BRICK_OFFSET_X = 1
BRICK_OFFSET_Y = 17

# Paddle configuration
PADDLE_SEGMENTS = 7  # Number of squares in paddle
PADDLE_Y = 110
PADDLE_SPEED = 3

# Ball configuration
BALL_SIZE = SQUARE_SIZE
BALL_SPEED = 2

# Load font
small_font = PixelFont.load("/system/assets/fonts/nope.ppf")

class GameState:
    INTRO = 1
    PLAYING = 2
    GAME_OVER = 3
    WIN = 4

class Brick:
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.color = color
        self.alive = True
    
    def draw(self):
        if self.alive:
            screen.brush = brushes.color(*self.color)
            screen.draw(shapes.rectangle(self.x, self.y, BRICK_WIDTH, BRICK_HEIGHT))
    
    def get_bounds(self):
        return (self.x, self.y, self.x + BRICK_WIDTH, self.y + BRICK_HEIGHT)

class Paddle:
    def __init__(self):
        self.x = SCREEN_WIDTH // 2 - (PADDLE_SEGMENTS * UNIT) // 2
        self.y = PADDLE_Y
    
    def find_target_brick(self, bricks):
        """Find the brightest green brick (target) for optimized play."""
        brightest_green = COMMIT_COLORS[-1]  # (86, 211, 100) - brightest green
        green_bricks = [b for b in bricks if b.alive and b.color == brightest_green]
        
        if green_bricks:
            # Return leftmost bright green brick (systematic approach)
            return min(green_bricks, key=lambda b: (b.x, b.y))
        
        # No bright green bricks, target any alive brick
        alive_bricks = [b for b in bricks if b.alive]
        if alive_bricks:
            return min(alive_bricks, key=lambda b: (b.x, b.y))
        
        return None
    
    def update(self, ball=None, auto_play=False, bricks=None):
        # Check for manual input - returns True if player is taking control
        manual_input = io.BUTTON_A in io.held or io.BUTTON_C in io.held
        
        if auto_play and ball and ball.active and ball.vy > 0 and not manual_input:
            # AI: Only move when ball is heading down
            paddle_left = self.x
            paddle_right = self.x + (PADDLE_SEGMENTS * UNIT) - SQUARE_GAP
            ball_center = ball.x + BALL_SIZE // 2
            
            # Find target brick (brightest green)
            target_brick = self.find_target_brick(bricks) if bricks else None
            
            if target_brick:
                # Calculate desired paddle position to deflect ball toward target
                target_x = target_brick.x + BRICK_WIDTH // 2
                
                # Estimate where ball will be when it reaches paddle height
                # Simple prediction: if ball continues on current trajectory
                if ball.vy != 0:
                    time_to_paddle = (self.y - ball.y) / abs(ball.vy)
                    predicted_ball_x = ball.x + (ball.vx * time_to_paddle)
                else:
                    predicted_ball_x = ball.x
                
                # Calculate paddle position that would deflect ball toward target
                # When ball hits paddle, we want to aim it at the target
                paddle_center = (paddle_left + paddle_right) // 2
                
                # If ball is heading down, position to intercept and angle toward target
                desired_offset = 0
                if predicted_ball_x < target_x:
                    # Want ball to go right after bounce, so hit with left side of paddle
                    desired_offset = -UNIT
                elif predicted_ball_x > target_x:
                    # Want ball to go left after bounce, so hit with right side of paddle
                    desired_offset = UNIT
                
                desired_paddle_x = predicted_ball_x - (PADDLE_SEGMENTS * UNIT) // 2 + desired_offset
                
                # Move toward desired position
                if self.x < desired_paddle_x:
                    self.x += min(PADDLE_SPEED, desired_paddle_x - self.x)
                elif self.x > desired_paddle_x:
                    self.x -= min(PADDLE_SPEED, self.x - desired_paddle_x)
            else:
                # No target brick, just intercept the ball
                if ball_center < paddle_left:
                    move_needed = paddle_left - ball_center
                    self.x -= min(PADDLE_SPEED, move_needed)
                elif ball_center > paddle_right:
                    move_needed = ball_center - paddle_right
                    self.x += min(PADDLE_SPEED, move_needed)
        else:
            # Manual control
            if io.BUTTON_A in io.held:
                self.x -= PADDLE_SPEED
            if io.BUTTON_C in io.held:
                self.x += PADDLE_SPEED
        
        # Keep paddle on screen
        self.x = max(0, min(self.x, SCREEN_WIDTH - (PADDLE_SEGMENTS * UNIT)))
        
        return manual_input
    
    def draw(self):
        screen.brush = brushes.color(*PADDLE_COLOR)
        for i in range(PADDLE_SEGMENTS):
            x = self.x + (i * UNIT)
            screen.draw(shapes.rectangle(x, self.y, SQUARE_SIZE, SQUARE_SIZE))
    
    def get_bounds(self):
        return (self.x, self.y, self.x + (PADDLE_SEGMENTS * UNIT) - SQUARE_GAP, self.y + SQUARE_SIZE)

class Ball:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.x = SCREEN_WIDTH // 2
        self.y = SCREEN_HEIGHT // 2
        self.vx = BALL_SPEED if random.random() > 0.5 else -BALL_SPEED
        self.vy = -BALL_SPEED
        self.active = False
    
    def update(self, paddle, bricks, auto_play=False):
        if not self.active:
            # Ball follows paddle until launched
            paddle_bounds = paddle.get_bounds()
            self.x = (paddle_bounds[0] + paddle_bounds[2]) // 2
            self.y = paddle.y - BALL_SIZE - 2
            
            if io.BUTTON_UP in io.pressed or io.BUTTON_B in io.pressed:
                self.active = True
                self.vy = -BALL_SPEED
            return True
        
        # Move ball
        self.x += self.vx
        self.y += self.vy
        
        # Wall collisions (left, right, top)
        if self.x <= 0 or self.x >= SCREEN_WIDTH - BALL_SIZE:
            self.vx = -self.vx
            self.x = max(0, min(self.x, SCREEN_WIDTH - BALL_SIZE))
        
        # Top collision - bounce at brick level if all bricks cleared
        bricks_remaining = any(brick.alive for brick in bricks)
        ceiling = 0 if bricks_remaining else BRICK_OFFSET_Y
        
        if self.y <= ceiling:
            self.vy = -self.vy
            self.y = ceiling
        
        # Bottom wall - lose life
        if self.y >= SCREEN_HEIGHT:
            return False
        
        # Paddle collision
        paddle_bounds = paddle.get_bounds()
        if (self.y + BALL_SIZE >= paddle_bounds[1] and 
            self.y <= paddle_bounds[3] and
            self.x + BALL_SIZE >= paddle_bounds[0] and
            self.x <= paddle_bounds[2]):
            
            if self.vy > 0:  # Only bounce if moving downward
                self.vy = -self.vy
                self.y = paddle_bounds[1] - BALL_SIZE
                
                # Add some angle based on where ball hits paddle
                paddle_center = (paddle_bounds[0] + paddle_bounds[2]) // 2
                ball_center = self.x + BALL_SIZE // 2
                offset = (ball_center - paddle_center) / ((paddle_bounds[2] - paddle_bounds[0]) // 2)
                self.vx = int(offset * BALL_SPEED * 1.5)
                
                # In auto mode, ensure ball doesn't go straight up
                if auto_play and abs(self.vx) < 1:
                    self.vx = BALL_SPEED if ball_center > paddle_center else -BALL_SPEED
        
        # Brick collisions
        for brick in bricks:
            if not brick.alive:
                continue
            
            brick_bounds = brick.get_bounds()
            if (self.x + BALL_SIZE >= brick_bounds[0] and
                self.x <= brick_bounds[2] and
                self.y + BALL_SIZE >= brick_bounds[1] and
                self.y <= brick_bounds[3]):
                
                brick.alive = False
                
                # Determine bounce direction
                ball_center_x = self.x + BALL_SIZE // 2
                ball_center_y = self.y + BALL_SIZE // 2
                brick_center_x = (brick_bounds[0] + brick_bounds[2]) // 2
                brick_center_y = (brick_bounds[1] + brick_bounds[3]) // 2
                
                dx = abs(ball_center_x - brick_center_x)
                dy = abs(ball_center_y - brick_center_y)
                
                if dx > dy:
                    self.vx = -self.vx
                else:
                    self.vy = -self.vy
                
                return True
        
        return True
    
    def draw(self):
        screen.brush = brushes.color(*BALL_COLOR)
        screen.draw(shapes.rectangle(int(self.x), int(self.y), BALL_SIZE, BALL_SIZE))

# Initialize game objects
bricks = []
paddle = Paddle()
ball = Ball()
state = GameState.INTRO
lives = 3
score = 0
auto_play = False

def create_bricks():
    global bricks
    bricks = []
    for row in range(BRICK_ROWS):
        for col in range(BRICK_COLS):
            x = BRICK_OFFSET_X + (col * UNIT)
            y = BRICK_OFFSET_Y + (row * UNIT)
            color = random.choice(COMMIT_COLORS)
            bricks.append(Brick(x, y, color))

def update():
    global state, lives, score
    
    # Clear screen
    screen.brush = brushes.color(*BACKGROUND_COLOR)
    screen.draw(shapes.rectangle(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))
    
    if state == GameState.INTRO:
        intro()
    elif state == GameState.PLAYING:
        play()
    elif state == GameState.GAME_OVER:
        game_over()
    elif state == GameState.WIN:
        win_screen()

def intro():
    global state, lives, score
    
    # Draw title
    screen.font = small_font
    screen.brush = brushes.color(255, 255, 255)
    
    title = "COMMITS"
    w, _ = screen.measure_text(title)
    screen.text(title, 80 - (w // 2), 25)
    
    subtitle = "Break the commits!"
    w, _ = screen.measure_text(subtitle)
    screen.text(subtitle, 80 - (w // 2), 40)
    
    # Controls
    controls = "A/C: Move"
    w, _ = screen.measure_text(controls)
    screen.text(controls, 80 - (w // 2), 55)
    
    controls2 = "B: Launch"
    w, _ = screen.measure_text(controls2)
    screen.text(controls2, 80 - (w // 2), 65)
    
    controls3 = "DOWN: Auto-play"
    w, _ = screen.measure_text(controls3)
    screen.text(controls3, 80 - (w // 2), 75)
    
    # Blink start message
    if int(io.ticks / 500) % 2:
        msg = "Press B to start"
        w, _ = screen.measure_text(msg)
        screen.text(msg, 80 - (w // 2), 90)
    
    # Draw sample bricks
    for i in range(3):
        x = 50 + i * 20
        color = COMMIT_COLORS[i]
        screen.brush = brushes.color(*color)
        screen.draw(shapes.rectangle(x, 105, SQUARE_SIZE, SQUARE_SIZE))
    
    if io.BUTTON_UP in io.pressed or io.BUTTON_B in io.pressed:
        state = GameState.PLAYING
        lives = 3
        score = 0
        auto_play = False
        create_bricks()
        paddle = Paddle()
        ball.reset()

def play():
    global state, lives, score, auto_play, paddle, ball
    
    # Toggle auto-play mode with DOWN button
    if io.BUTTON_DOWN in io.pressed:
        auto_play = not auto_play
    
    # Update game objects - check if manual input cancels auto mode
    manual_input = paddle.update(ball, auto_play, bricks)
    if manual_input and auto_play:
        auto_play = False
    
    if not ball.update(paddle, bricks, auto_play):
        if auto_play:
            # Auto mode: restart without losing a life
            score = 0
            create_bricks()
            paddle = Paddle()
            ball = Ball()
        else:
            # Manual mode: lose a life
            lives -= 1
            if lives <= 0:
                state = GameState.GAME_OVER
            else:
                ball.reset()
    
    # Check for win
    if all(not brick.alive for brick in bricks):
        if auto_play:
            # Auto-restart: reset game with auto mode still enabled
            score = 0
            create_bricks()
            paddle = Paddle()
            ball = Ball()
            # auto_play remains True
        else:
            state = GameState.WIN
    
    # Count score
    score = sum(1 for brick in bricks if not brick.alive)
    
    # Draw game objects
    for brick in bricks:
        brick.draw()
    
    paddle.draw()
    ball.draw()
    
    # Draw UI
    screen.font = small_font
    screen.brush = brushes.color(255, 255, 255)
    screen.text(f"Lives: {lives}", 2, 2)
    
    score_text = f"Score: {score}"
    w, _ = screen.measure_text(score_text)
    screen.text(score_text, SCREEN_WIDTH - w - 2, 2)
    
    # Show green 'A' when in auto-play mode
    if auto_play:
        auto_text = "A"
        w, _ = screen.measure_text(auto_text)
        screen.brush = brushes.color(*PADDLE_COLOR)
        screen.text(auto_text, 80 - (w // 2), 2)

def game_over():
    global state
    
    # Draw game over screen
    screen.font = small_font
    screen.brush = brushes.color(255, 255, 255)
    
    title = "GAME OVER!"
    w, _ = screen.measure_text(title)
    screen.text(title, 80 - (w // 2), 40)
    
    score_text = f"Commits: {score}"
    w, _ = screen.measure_text(score_text)
    screen.text(score_text, 80 - (w // 2), 55)
    
    # Blink restart message
    if int(io.ticks / 500) % 2:
        msg = "Press B to restart"
        w, _ = screen.measure_text(msg)
        screen.text(msg, 80 - (w // 2), 75)
    
    if io.BUTTON_UP in io.pressed or io.BUTTON_B in io.pressed:
        state = GameState.INTRO

def win_screen():
    global state
    
    # Draw win screen
    screen.font = small_font
    screen.brush = brushes.color(255, 255, 255)
    
    title = "YOU WIN!"
    w, _ = screen.measure_text(title)
    screen.text(title, 80 - (w // 2), 40)
    
    score_text = "All commits broken!"
    w, _ = screen.measure_text(score_text)
    screen.text(score_text, 80 - (w // 2), 55)
    
    # Blink restart message
    if int(io.ticks / 500) % 2:
        msg = "Press B to restart"
        w, _ = screen.measure_text(msg)
        screen.text(msg, 80 - (w // 2), 75)
    
    if io.BUTTON_UP in io.pressed or io.BUTTON_B in io.pressed:
        state = GameState.INTRO

if __name__ == "__main__":
    run(update)
