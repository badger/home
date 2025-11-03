"""
JezzBall - Classic area capturing game
Trap bouncing balls by creating dividers to claim territory
"""

from badgeware import screen, Image, PixelFont, io, brushes, shapes, run
import random
import math

# Screen dimensions
WIDTH = 160
HEIGHT = 120

# Colors
BACKGROUND = brushes.color(20, 20, 40)
WALL_COLOR = brushes.color(73, 219, 255)
DIVIDER_H_COLOR = brushes.color(255, 255, 0)
DIVIDER_V_COLOR = brushes.color(0, 255, 0)
BALL_COLORS = [
    brushes.color(255, 50, 50),
    brushes.color(255, 150, 50),
    brushes.color(50, 255, 50),
    brushes.color(150, 50, 255),
]
TEXT_COLOR = brushes.color(255, 255, 255)
CLAIMED_COLOR = brushes.color(40, 40, 80, 200)
CURSOR_COLOR = brushes.color(255, 255, 255, 150)

# Game constants
PLAY_AREA_X = 10
PLAY_AREA_Y = 20
PLAY_AREA_WIDTH = 140
PLAY_AREA_HEIGHT = 90
BALL_RADIUS = 3
BALL_SPEED = 0.8
DIVIDER_SPEED = 1.2
DIVIDER_THICKNESS = 2
GRID_SIZE = 2  # Size of grid cells for area tracking

# Game state
state = {
    "level": 1,
    "lives": 3,
    "score": 0,
    "percent_claimed": 0,
    "balls": [],
    "dividers": [],
    "divider_active": False,
    "divider_direction": "horizontal",  # or "vertical"
    "game_over": False,
    "won_level": False,
    "ready": True,  # Waiting for player to start
    "completed_dividers": [],  # List of completed dividers for collision
    "claimed_areas": [],  # List of rectangles for claimed areas
    "cursor_x": 80,  # Cursor position
    "cursor_y": 60,
}

class Ball:
    def __init__(self, x, y, vx, vy, color_index):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color_index = color_index
        self.radius = BALL_RADIUS
    
    def update(self, dt):
        """Update ball position and handle wall and divider collisions"""
        # Store old position
        old_x = self.x
        old_y = self.y
        
        # Move ball
        self.x += self.vx * dt
        self.y += self.vy * dt
        
        # Check collision with play area boundaries
        if self.x - self.radius <= PLAY_AREA_X:
            self.x = PLAY_AREA_X + self.radius
            self.vx = abs(self.vx)
        elif self.x + self.radius >= PLAY_AREA_X + PLAY_AREA_WIDTH:
            self.x = PLAY_AREA_X + PLAY_AREA_WIDTH - self.radius
            self.vx = -abs(self.vx)
        
        if self.y - self.radius <= PLAY_AREA_Y:
            self.y = PLAY_AREA_Y + self.radius
            self.vy = abs(self.vy)
        elif self.y + self.radius >= PLAY_AREA_Y + PLAY_AREA_HEIGHT:
            self.y = PLAY_AREA_Y + PLAY_AREA_HEIGHT - self.radius
            self.vy = -abs(self.vy)
        
        # Check collision with completed dividers
        for divider in state["completed_dividers"]:
            if divider.direction == "horizontal":
                # Horizontal divider - check if ball crosses it
                div_y = divider.y
                div_left = divider.x - divider.left_length
                div_right = divider.x + divider.right_length
                
                if ((old_y - self.radius < div_y < old_y + self.radius) or 
                    (self.y - self.radius < div_y < self.y + self.radius)):
                    # Ball is at divider height, check x range
                    if div_left <= self.x <= div_right:
                        # Bounce off horizontal divider
                        if self.vy > 0:
                            self.y = div_y - self.radius - 1
                        else:
                            self.y = div_y + self.radius + 1
                        self.vy = -self.vy
            else:
                # Vertical divider - check if ball crosses it
                div_x = divider.x
                div_top = divider.y - divider.top_length
                div_bottom = divider.y + divider.bottom_length
                
                if ((old_x - self.radius < div_x < old_x + self.radius) or 
                    (self.x - self.radius < div_x < self.x + self.radius)):
                    # Ball is at divider x position, check y range
                    if div_top <= self.y <= div_bottom:
                        # Bounce off vertical divider
                        if self.vx > 0:
                            self.x = div_x - self.radius - 1
                        else:
                            self.x = div_x + self.radius + 1
                        self.vx = -self.vx
    
    def draw(self):
        """Draw the ball"""
        screen.brush = BALL_COLORS[self.color_index % len(BALL_COLORS)]
        screen.draw(shapes.circle(int(self.x), int(self.y), self.radius))

class Divider:
    def __init__(self, x, y, direction):
        self.x = x
        self.y = y
        self.direction = direction  # "horizontal" or "vertical"
        self.growing = True
        self.length = 0
        self.max_length = PLAY_AREA_WIDTH if direction == "horizontal" else PLAY_AREA_HEIGHT
        self.hit = False
        self.left_complete = False  # For horizontal, left side reached edge
        self.right_complete = False  # For horizontal, right side reached edge
        self.top_complete = False  # For vertical, top reached edge
        self.bottom_complete = False  # For vertical, bottom reached edge
        self.left_length = 0  # Track left side length separately
        self.right_length = 0  # Track right side length separately
        self.top_length = 0  # Track top side length separately
        self.bottom_length = 0  # Track bottom side length separately
    
    def update(self, dt, balls):
        """Grow the divider and check for ball collisions"""
        if not self.growing:
            return
        
        self.length += DIVIDER_SPEED * dt
        
        # Track which sides have reached edges or hit other dividers with captured area behind
        if self.direction == "horizontal":
            # Calculate individual side lengths
            if not self.left_complete:
                self.left_length = min(self.length, self.x - PLAY_AREA_X)
            if not self.right_complete:
                self.right_length = min(self.length, PLAY_AREA_X + PLAY_AREA_WIDTH - self.x)
            
            # Check if reached boundaries
            self.left_complete = self.x - self.left_length <= PLAY_AREA_X
            self.right_complete = self.x + self.right_length >= PLAY_AREA_X + PLAY_AREA_WIDTH
            
            # Check if we hit a vertical divider (always stop at crossing dividers)
            if not self.left_complete or not self.right_complete:
                for other in state["completed_dividers"]:
                    if other.direction == "vertical":
                        other_x = other.x
                        # Check if this divider intersects with our horizontal line
                        other_top = other.y - other.top_length
                        other_bottom = other.y + other.bottom_length
                        
                        # Only stop if the crossing divider actually crosses our y position
                        if other_top <= self.y <= other_bottom:
                            # Check left side
                            if not self.left_complete and self.x - self.length <= other_x <= self.x:
                                self.left_complete = True
                                self.left_length = self.x - other_x
                            # Check right side
                            if not self.right_complete and self.x <= other_x <= self.x + self.length:
                                self.right_complete = True
                                self.right_length = other_x - self.x
        else:
            # Calculate individual side lengths
            if not self.top_complete:
                self.top_length = min(self.length, self.y - PLAY_AREA_Y)
            if not self.bottom_complete:
                self.bottom_length = min(self.length, PLAY_AREA_Y + PLAY_AREA_HEIGHT - self.y)
            
            # Check if reached boundaries
            self.top_complete = self.y - self.top_length <= PLAY_AREA_Y
            self.bottom_complete = self.y + self.bottom_length >= PLAY_AREA_Y + PLAY_AREA_HEIGHT
            
            # Check if we hit a horizontal divider (always stop at crossing dividers)
            if not self.top_complete or not self.bottom_complete:
                for other in state["completed_dividers"]:
                    if other.direction == "horizontal":
                        other_y = other.y
                        # Check if this divider intersects with our vertical line
                        other_left = other.x - other.left_length
                        other_right = other.x + other.right_length
                        
                        # Only stop if the crossing divider actually crosses our x position
                        if other_left <= self.x <= other_right:
                            # Check top side
                            if not self.top_complete and self.y - self.length <= other_y <= self.y:
                                self.top_complete = True
                                self.top_length = self.y - other_y
                            # Check bottom side
                            if not self.bottom_complete and self.y <= other_y <= self.y + self.length:
                                self.bottom_complete = True
                                self.bottom_length = other_y - self.y
        
        # Check if divider hit a ball (but only on sides that haven't reached edges)
        # Don't check if we're very close to completing (within 3 pixels)
        close_to_complete = False
        if self.direction == "horizontal":
            left_close = self.left_complete or (self.x - self.left_length - PLAY_AREA_X <= 3)
            right_close = self.right_complete or (PLAY_AREA_X + PLAY_AREA_WIDTH - (self.x + self.right_length) <= 3)
            close_to_complete = left_close and right_close
        else:
            top_close = self.top_complete or (self.y - self.top_length - PLAY_AREA_Y <= 3)
            bottom_close = self.bottom_complete or (PLAY_AREA_Y + PLAY_AREA_HEIGHT - (self.y + self.bottom_length) <= 3)
            close_to_complete = top_close and bottom_close
        
        if not close_to_complete:
            for ball in balls:
                if self.collides_with_ball(ball):
                    self.hit = True
                    self.growing = False
                    return
        
        # Check if divider reached the other side (both directions)
        if self.direction == "horizontal":
            if self.left_complete and self.right_complete:
                self.growing = False
        else:
            if self.top_complete and self.bottom_complete:
                self.growing = False
    
    def has_captured_area_beyond(self, x, y, direction):
        """Check if there's a captured area beyond a divider intersection"""
        # Sample a few pixels beyond the intersection point to check for captured areas
        test_offset = 10
        
        for area in state["claimed_areas"]:
            ax1, ay1 = area["x"], area["y"]
            ax2, ay2 = area["x"] + area["width"], area["y"] + area["height"]
            
            if direction == "left":
                # Check if there's captured area to the left of this x position
                test_x = x - test_offset
                if ax1 <= test_x <= ax2 and ay1 <= y <= ay2:
                    return True
            elif direction == "right":
                # Check if there's captured area to the right of this x position
                test_x = x + test_offset
                if ax1 <= test_x <= ax2 and ay1 <= y <= ay2:
                    return True
            elif direction == "top":
                # Check if there's captured area above this y position
                test_y = y - test_offset
                if ax1 <= x <= ax2 and ay1 <= test_y <= ay2:
                    return True
            elif direction == "bottom":
                # Check if there's captured area below this y position
                test_y = y + test_offset
                if ax1 <= x <= ax2 and ay1 <= test_y <= ay2:
                    return True
        
        return False
    
    def collides_with_ball(self, ball):
        """Check if divider is touching a ball on an incomplete side"""
        if self.direction == "horizontal":
            # Check if ball is near the horizontal divider line
            if abs(ball.y - self.y) < ball.radius + DIVIDER_THICKNESS:
                ball_x = ball.x
                # Only check collision on sides that haven't reached the edge
                left_side = self.x - self.left_length
                right_side = self.x + self.right_length
                
                # If left side is complete (reached edge), ignore collisions on left
                if self.left_complete and ball_x < self.x:
                    return False
                # If right side is complete (reached edge), ignore collisions on right
                if self.right_complete and ball_x > self.x:
                    return False
                
                # Check if ball is within the divider's x range
                if left_side <= ball_x <= right_side:
                    return True
        else:
            # Check if ball is near the vertical divider line
            if abs(ball.x - self.x) < ball.radius + DIVIDER_THICKNESS:
                ball_y = ball.y
                # Only check collision on sides that haven't reached the edge
                top_side = self.y - self.top_length
                bottom_side = self.y + self.bottom_length
                
                # If top side is complete (reached edge), ignore collisions on top
                if self.top_complete and ball_y < self.y:
                    return False
                # If bottom side is complete (reached edge), ignore collisions on bottom
                if self.bottom_complete and ball_y > self.y:
                    return False
                
                # Check if ball is within the divider's y range
                if top_side <= ball_y <= bottom_side:
                    return True
        return False
    
    def draw(self):
        """Draw the divider"""
        color = DIVIDER_H_COLOR if self.direction == "horizontal" else DIVIDER_V_COLOR
        screen.brush = color
        
        if self.direction == "horizontal":
            x1 = int(self.x - self.left_length)
            x2 = int(self.x + self.right_length)
            screen.draw(shapes.line(x1, int(self.y), x2, int(self.y), DIVIDER_THICKNESS))
        else:
            y1 = int(self.y - self.top_length)
            y2 = int(self.y + self.bottom_length)
            screen.draw(shapes.line(int(self.x), y1, int(self.x), y2, DIVIDER_THICKNESS))

def init():
    """Initialize the game"""
    screen.font = PixelFont.load("/system/assets/fonts/nope.ppf")
    start_level()

def start_level():
    """Start a new level"""
    state["balls"] = []
    state["dividers"] = []
    state["completed_dividers"] = []
    # Initialize with one region covering the entire play area (unclaimed)
    state["claimed_areas"] = [{
        "x": PLAY_AREA_X,
        "y": PLAY_AREA_Y,
        "width": PLAY_AREA_WIDTH,
        "height": PLAY_AREA_HEIGHT
    }]
    state["divider_active"] = False
    state["percent_claimed"] = 0
    state["won_level"] = False
    # Only show ready screen on first level (level 1)
    state["ready"] = (state["level"] == 1)
    state["cursor_x"] = PLAY_AREA_X + PLAY_AREA_WIDTH // 2
    state["cursor_y"] = PLAY_AREA_Y + PLAY_AREA_HEIGHT // 2
    
    # Create balls (number increases with level)
    num_balls = min(2 + state["level"] - 1, 6)
    for i in range(num_balls):
        x = PLAY_AREA_X + PLAY_AREA_WIDTH / 2 + random.uniform(-20, 20)
        y = PLAY_AREA_Y + PLAY_AREA_HEIGHT / 2 + random.uniform(-20, 20)
        angle = random.uniform(0, 2 * math.pi)
        speed = BALL_SPEED
        vx = math.cos(angle) * speed
        vy = math.sin(angle) * speed
        ball = Ball(x, y, vx, vy, i)
        state["balls"].append(ball)

def is_point_in_claimed_area(x, y):
    """Check if a point is in a TRULY CLAIMED area (no balls can reach it)"""
    # Since claimed_areas now tracks UNCLAIMED regions (where balls are),
    # we need to check if point is NOT in any ball region
    for area in state["claimed_areas"]:
        if (area["x"] < x < area["x"] + area["width"] and
            area["y"] < y < area["y"] + area["height"]):
            # Point is in a ball region - check if balls are actually there
            has_ball = False
            for ball in state["balls"]:
                if (area["x"] < ball.x < area["x"] + area["width"] and
                    area["y"] < ball.y < area["y"] + area["height"]):
                    has_ball = True
                    break
            
            # If no balls in this region, it's claimed - don't allow divider
            if not has_ball:
                return True
            # If balls are here, it's unclaimed - allow divider
            return False
    
    # Point is not in any tracked region, so it's claimed by default
    return True

def is_point_on_divider(x, y):
    """Check if a point is on top of an existing divider"""
    threshold = 5  # Distance threshold
    for divider in state["completed_dividers"]:
        if divider.direction == "horizontal":
            # Check if point is near this horizontal divider
            if abs(y - divider.y) < threshold:
                # Check if point is within the divider's x range
                x1 = max(PLAY_AREA_X, divider.x - divider.length)
                x2 = min(PLAY_AREA_X + PLAY_AREA_WIDTH, divider.x + divider.length)
                if x1 <= x <= x2:
                    return True
        else:
            # Check if point is near this vertical divider
            if abs(x - divider.x) < threshold:
                # Check if point is within the divider's y range
                y1 = max(PLAY_AREA_Y, divider.y - divider.length)
                y2 = min(PLAY_AREA_Y + PLAY_AREA_HEIGHT, divider.y + divider.length)
                if y1 <= y <= y2:
                    return True
    return False

def create_divider():
    """Create a new divider at cursor position"""
    if state["divider_active"] or state["game_over"] or state["won_level"]:
        return
    
    # Don't allow divider creation in claimed areas
    if is_point_in_claimed_area(state["cursor_x"], state["cursor_y"]):
        return
    
    # Don't allow divider creation on top of existing dividers
    if is_point_on_divider(state["cursor_x"], state["cursor_y"]):
        return
    
    # Start divider at cursor position
    x = state["cursor_x"]
    y = state["cursor_y"]
    
    divider = Divider(x, y, state["divider_direction"])
    state["dividers"].append(divider)
    state["divider_active"] = True

def calculate_overlap_with_claimed(area):
    """Calculate how much of an area overlaps with already claimed areas"""
    if not state["claimed_areas"]:
        return 0
    
    new_x1 = area["x"]
    new_y1 = area["y"]
    new_x2 = area["x"] + area["width"]
    new_y2 = area["y"] + area["height"]
    
    total_overlap = 0
    for claimed in state["claimed_areas"]:
        c_x1 = claimed["x"]
        c_y1 = claimed["y"]
        c_x2 = claimed["x"] + claimed["width"]
        c_y2 = claimed["y"] + claimed["height"]
        
        # Calculate intersection
        overlap_x1 = max(new_x1, c_x1)
        overlap_y1 = max(new_y1, c_y1)
        overlap_x2 = min(new_x2, c_x2)
        overlap_y2 = min(new_y2, c_y2)
        
        if overlap_x1 < overlap_x2 and overlap_y1 < overlap_y2:
            overlap_area = (overlap_x2 - overlap_x1) * (overlap_y2 - overlap_y1)
            total_overlap += overlap_area
    
    return total_overlap

def split_area_by_divider(divider):
    """Split existing ball regions by this divider"""
    new_regions = []
    
    # For each existing region, check if this divider splits it
    for region in state["claimed_areas"]:
        if divider.direction == "horizontal":
            # Horizontal divider
            div_left = divider.x - divider.left_length
            div_right = divider.x + divider.right_length
            div_y = divider.y
            
            # Check if divider crosses this region
            if (div_left < region["x"] + region["width"] and 
                div_right > region["x"] and
                region["y"] < div_y < region["y"] + region["height"]):
                # Split the region into above and below
                above = {
                    "x": region["x"],
                    "y": region["y"],
                    "width": region["width"],
                    "height": div_y - region["y"]
                }
                below = {
                    "x": region["x"],
                    "y": div_y,
                    "width": region["width"],
                    "height": region["y"] + region["height"] - div_y
                }
                
                if above["height"] > 0:
                    new_regions.append(above)
                if below["height"] > 0:
                    new_regions.append(below)
            else:
                # Divider doesn't split this region, keep it
                new_regions.append(region)
        
        else:  # vertical
            # Vertical divider
            div_top = divider.y - divider.top_length
            div_bottom = divider.y + divider.bottom_length
            div_x = divider.x
            
            # Check if divider crosses this region
            if (div_top < region["y"] + region["height"] and 
                div_bottom > region["y"] and
                region["x"] < div_x < region["x"] + region["width"]):
                # Split the region into left and right
                left = {
                    "x": region["x"],
                    "y": region["y"],
                    "width": div_x - region["x"],
                    "height": region["height"]
                }
                right = {
                    "x": div_x,
                    "y": region["y"],
                    "width": region["x"] + region["width"] - div_x,
                    "height": region["height"]
                }
                
                if left["width"] > 0:
                    new_regions.append(left)
                if right["width"] > 0:
                    new_regions.append(right)
            else:
                # Divider doesn't split this region, keep it
                new_regions.append(region)
    
    state["claimed_areas"] = new_regions

def calculate_claimed_area():
    """Calculate percentage - regions with balls are UNCLAIMED"""
    total_area = PLAY_AREA_WIDTH * PLAY_AREA_HEIGHT
    
    # Sum up regions that have balls (unclaimed)
    unclaimed = 0
    for area in state["claimed_areas"]:
        # Check if any ball is in this area
        has_ball = False
        for ball in state["balls"]:
            if (area["x"] < ball.x < area["x"] + area["width"] and
                area["y"] < ball.y < area["y"] + area["height"]):
                has_ball = True
                break
        
        if has_ball:
            unclaimed += area["width"] * area["height"]
    
    # Percentage claimed is 100% minus unclaimed percentage
    state["percent_claimed"] = int(((total_area - unclaimed) / total_area) * 100)
    
    # Check if level is won (75% claimed)
    if state["percent_claimed"] >= 75:
        state["won_level"] = True
        state["score"] += 100 * state["level"]
        state["level"] += 1

def update():
    """Main update function called every frame"""
    # Clear screen
    screen.brush = BACKGROUND
    screen.clear()
    
    # Handle input
    if state["ready"]:
        # Waiting for player to start - any button starts
        if io.BUTTON_A in io.pressed or io.BUTTON_B in io.pressed or io.BUTTON_C in io.pressed:
            state["ready"] = False
    elif not state["game_over"]:
        # Move cursor when not actively drawing
        if not state["divider_active"] and not state["won_level"]:
            move_speed = 2
            if io.BUTTON_UP in io.held:
                state["cursor_y"] = max(PLAY_AREA_Y + 5, state["cursor_y"] - move_speed)
            if io.BUTTON_DOWN in io.held:
                state["cursor_y"] = min(PLAY_AREA_Y + PLAY_AREA_HEIGHT - 5, state["cursor_y"] + move_speed)
            # A = left, C = right
            if io.BUTTON_A in io.held:
                state["cursor_x"] = max(PLAY_AREA_X + 5, state["cursor_x"] - move_speed)
            if io.BUTTON_C in io.held:
                state["cursor_x"] = min(PLAY_AREA_X + PLAY_AREA_WIDTH - 5, state["cursor_x"] + move_speed)
        
        # Toggle divider direction with B
        if io.BUTTON_B in io.pressed and not state["divider_active"] and not state["won_level"]:
            state["divider_direction"] = "vertical" if state["divider_direction"] == "horizontal" else "horizontal"
        
        # Create divider with A+C simultaneously
        if not state["divider_active"] and not state["won_level"]:
            if (io.BUTTON_A in io.held and io.BUTTON_C in io.held):
                create_divider()
        
        if io.BUTTON_B in io.pressed and state["won_level"]:
            # Start next level
            start_level()
    
    # Restart game on game over (allow any button)
    if state["game_over"]:
        if io.BUTTON_A in io.pressed or io.BUTTON_B in io.pressed or io.BUTTON_C in io.pressed:
            state["level"] = 1
            state["lives"] = 3
            state["score"] = 0
            state["game_over"] = False
            start_level()
    
    # Update game objects
    if not state["game_over"] and not state["won_level"]:
        dt = min(io.ticks_delta / 10, 5)  # Cap delta for stability
        
        # Update balls (even in ready state so they bounce)
        for ball in state["balls"]:
            ball.update(dt)
        
        # Update dividers (only if not in ready state)
        if not state["ready"]:
            for divider in state["dividers"][:]:  # Use slice to avoid modification during iteration
                if divider.growing:
                    divider.update(dt, state["balls"])
                    if divider.hit:
                        # Ball hit the divider - remove it immediately
                        state["dividers"].remove(divider)
                        state["lives"] -= 1
                        if state["lives"] <= 0:
                            state["game_over"] = True
                        state["divider_active"] = False
                elif not divider.growing:
                    # Divider completed successfully
                    state["dividers"].remove(divider)
                    state["completed_dividers"].append(divider)
                    split_area_by_divider(divider)
                    state["divider_active"] = False
            
            # Calculate claimed area percentage
            calculate_claimed_area()

    # Draw play area background (claimed by default)
    screen.brush = CLAIMED_COLOR
    screen.draw(shapes.rectangle(PLAY_AREA_X, PLAY_AREA_Y, PLAY_AREA_WIDTH, PLAY_AREA_HEIGHT))
    
    # Draw unclaimed regions (where balls can be) with darker color
    for area in state["claimed_areas"]:
        # Check if any ball is in this area
        has_ball = False
        for ball in state["balls"]:
            if (area["x"] < ball.x < area["x"] + area["width"] and
                area["y"] < ball.y < area["y"] + area["height"]):
                has_ball = True
                break
        
        # Only draw unclaimed regions (with balls)
        if has_ball:
            screen.brush = BACKGROUND
            screen.draw(shapes.rectangle(int(area["x"]), int(area["y"]), int(area["width"]), int(area["height"])))
    
    # Draw play area border
    screen.brush = WALL_COLOR
    screen.draw(shapes.rectangle(PLAY_AREA_X - 2, PLAY_AREA_Y - 2, PLAY_AREA_WIDTH + 4, PLAY_AREA_HEIGHT + 4).stroke(2))
    
    # Draw completed dividers
    for divider in state["completed_dividers"]:
        divider.draw()
    
    # Draw growing dividers
    for divider in state["dividers"]:
        divider.draw()
    
    # Draw balls
    for ball in state["balls"]:
        ball.draw()
    
    # Draw divider indicator (cursor) at cursor position
    if not state["ready"] and not state["divider_active"] and not state["game_over"] and not state["won_level"]:
        screen.brush = CURSOR_COLOR
        cursor_x = int(state["cursor_x"])
        cursor_y = int(state["cursor_y"])
        
        if state["divider_direction"] == "horizontal":
            # Show horizontal line indicator
            screen.draw(shapes.line(PLAY_AREA_X, cursor_y, PLAY_AREA_X + PLAY_AREA_WIDTH, cursor_y, 1))
            # Draw crosshair
            screen.draw(shapes.line(cursor_x - 3, cursor_y, cursor_x + 3, cursor_y, 2))
            screen.draw(shapes.line(cursor_x, cursor_y - 3, cursor_x, cursor_y + 3, 2))
        else:
            # Show vertical line indicator
            screen.draw(shapes.line(cursor_x, PLAY_AREA_Y, cursor_x, PLAY_AREA_Y + PLAY_AREA_HEIGHT, 1))
            # Draw crosshair
            screen.draw(shapes.line(cursor_x - 3, cursor_y, cursor_x + 3, cursor_y, 2))
            screen.draw(shapes.line(cursor_x, cursor_y - 3, cursor_x, cursor_y + 3, 2))
    
    # Draw HUD
    draw_hud()

def draw_hud():
    """Draw the heads-up display"""
    screen.brush = TEXT_COLOR
    
    # Top bar - add score
    screen.text(f"L{state['level']}", 5, 2)
    screen.text(f"Lives:{state['lives']}", 40, 2)
    screen.text(f"{state['percent_claimed']}%", 95, 2)
    screen.text(f"{state['score']}", 130, 2)
    
    # Ready screen with controls
    if state["ready"]:
        screen.brush = brushes.color(255, 255, 0)
        text = "JEZZBALL"
        w, h = screen.measure_text(text)
        screen.text(text, 80 - w // 2, 35)
        
        screen.brush = TEXT_COLOR
        text = "A/C - Move left/right"
        w, h = screen.measure_text(text)
        screen.text(text, 80 - w // 2, 52)
        
        text = "Up/Down - Move up/down"
        w, h = screen.measure_text(text)
        screen.text(text, 80 - w // 2, 62)
        
        text = "B - Switch direction"
        w, h = screen.measure_text(text)
        screen.text(text, 80 - w // 2, 72)
        
        text = "A+C - Draw divider"
        w, h = screen.measure_text(text)
        screen.text(text, 80 - w // 2, 82)
        
        screen.brush = brushes.color(0, 255, 0)
        text = "Press any button"
        w, h = screen.measure_text(text)
        screen.text(text, 80 - w // 2, 95)
    
    # Game over message
    if state["game_over"]:
        screen.brush = brushes.color(255, 0, 0)
        text = "GAME OVER"
        w, h = screen.measure_text(text)
        screen.text(text, 80 - w // 2, 50)
        
        screen.brush = TEXT_COLOR
        text = f"Score: {state['score']}"
        w, h = screen.measure_text(text)
        screen.text(text, 80 - w // 2, 65)
        
        text = "Press any button"
        w, h = screen.measure_text(text)
        screen.text(text, 80 - w // 2, 80)
    
    # Level complete message
    if state["won_level"]:
        screen.brush = brushes.color(0, 255, 0)
        text = "LEVEL COMPLETE!"
        w, h = screen.measure_text(text)
        screen.text(text, 80 - w // 2, 50)
        
        screen.brush = TEXT_COLOR
        text = f"Score: {state['score']}"
        w, h = screen.measure_text(text)
        screen.text(text, 80 - w // 2, 65)
        
        text = "[B] Next Level"
        w, h = screen.measure_text(text)
        screen.text(text, 80 - w // 2, 80)
