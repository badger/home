import time
import random
from badgeware import screen, PixelFont, shapes, brushes, io, run, Matrix

# Christmas colors
BG_COLOR = (10, 20, 40)  # Dark blue night sky
TEXT_COLOR = (255, 255, 255)  # White text
SNOWFLAKE_COLOR = (240, 248, 255)  # Light snow color

# Pre-create brushes for performance
BG_BRUSH = brushes.color(*BG_COLOR)
TEXT_BRUSH = brushes.color(*TEXT_COLOR)
SNOWFLAKE_BRUSH = brushes.color(*SNOWFLAKE_COLOR)

# Load font
large_font = PixelFont.load("/system/assets/fonts/ziplock.ppf")
small_font = PixelFont.load("/system/assets/fonts/nope.ppf")

class Snowflake:
    """A single falling snowflake"""
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset snowflake to top of screen with random properties"""
        self.x = random.randint(0, 160)
        self.y = random.randint(-20, 0)  # Start slightly above screen
        self.size = random.randint(1, 2)  # Small snowflakes
        self.speed = random.uniform(0.3, 0.8)  # Gentle fall speed
        self.drift = random.uniform(-0.2, 0.2)  # Slight horizontal drift
    
    def update(self):
        """Update snowflake position"""
        self.y += self.speed
        self.x += self.drift
        
        # Reset if fallen off screen
        if self.y > 120:
            self.reset()
        
        # Wrap horizontally
        if self.x < 0:
            self.x = 160
        elif self.x > 160:
            self.x = 0
    
    def draw(self):
        """Draw the snowflake"""
        screen.brush = SNOWFLAKE_BRUSH
        screen.draw(shapes.circle(int(self.x), int(self.y), self.size))

# Create snowflakes
snowflakes = [Snowflake() for _ in range(15)]

# Base days in each month (non-leap year)
BASE_DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

def get_days_until_christmas():
    """Calculate days until next Christmas (Dec 25)"""
    now = time.localtime()
    current_year = now[0]
    current_month = now[1]
    current_day = now[2]
    
    # Determine which Christmas to count down to
    christmas_year = current_year
    if current_month == 12 and current_day > 25:
        # After Christmas, count to next year
        christmas_year += 1
    
    # Helper function to get days in month for a specific year
    def get_days_in_month(year):
        days = BASE_DAYS_IN_MONTH.copy()
        is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
        if is_leap:
            days[1] = 29
        return days
    
    # Calculate day of year for current date
    current_days_in_month = get_days_in_month(current_year)
    current_day_of_year = sum(current_days_in_month[:current_month-1]) + current_day
    
    # Calculate day of year for Christmas
    if christmas_year == current_year:
        # Christmas this year
        christmas_day_of_year = sum(current_days_in_month[:11]) + 25  # December 25
        days_left = christmas_day_of_year - current_day_of_year
    else:
        # Christmas next year
        days_left_this_year = sum(current_days_in_month) - current_day_of_year
        # Calculate days from Jan 1 to Christmas in next year
        next_year_days = get_days_in_month(christmas_year)
        days_jan1_to_christmas = sum(next_year_days[:11]) + 25  # Jan 1 to Dec 25
        days_left = days_left_this_year + days_jan1_to_christmas
    
    return max(0, days_left)

def update():
    # Clear screen with dark blue background
    screen.brush = BG_BRUSH
    screen.clear()
    
    # Update and draw snowflakes (backdrop)
    for snowflake in snowflakes:
        snowflake.update()
        snowflake.draw()
    
    # Calculate days until Christmas
    days = get_days_until_christmas()
    
    # Draw countdown
    screen.font = large_font
    screen.brush = TEXT_BRUSH
    
    # Main number (at top)
    days_text = str(days)
    w, h = screen.measure_text(days_text)
    screen.text(days_text, 80 - (w // 2), 30)
    
    # Labels
    screen.font = small_font
    label = "days until"
    w, _ = screen.measure_text(label)
    screen.text(label, 80 - (w // 2), 60)
    
    label2 = "Christmas"
    w, _ = screen.measure_text(label2)
    screen.text(label2, 80 - (w // 2), 75)

if __name__ == "__main__":
    run(update)
