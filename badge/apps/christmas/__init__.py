import time
import random
from badgeware import screen, PixelFont, shapes, brushes, io, run, Matrix

try:
    from urllib.urequest import urlopen
    import json
    NETWORK_AVAILABLE = True
except ImportError:
    NETWORK_AVAILABLE = False

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

# Month names (short format)
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Cache for fetched time data
_cached_time = None
_last_fetch_attempt = 0
_fetch_success = False
FETCH_INTERVAL = 60 * 60 * 1000  # Try to fetch once per hour (in milliseconds) when successful
RETRY_INTERVAL = 5 * 1000  # Retry every 5 seconds (in milliseconds) when failed

def fetch_current_date():
    """
    Fetch current date from worldtimeapi.org
    Returns (year, month, day) tuple or None if fetch fails
    """
    global _cached_time, _last_fetch_attempt, _fetch_success
    
    if not NETWORK_AVAILABLE:
        return None
    
    # Return cached time if still valid
    current_ticks = io.ticks
    if _cached_time and _fetch_success and (current_ticks - _last_fetch_attempt < FETCH_INTERVAL):
        return _cached_time
    
    # Check if we should retry (use shorter interval when failed)
    if not _fetch_success and _last_fetch_attempt > 0:
        if current_ticks - _last_fetch_attempt < RETRY_INTERVAL:
            return None  # Return None to indicate we're still waiting to retry
    
    # Update last fetch attempt timestamp before trying
    _last_fetch_attempt = current_ticks
    
    # Attempt to fetch current date from the API
    try:
        # Use worldtimeapi.org - a free API that doesn't require authentication
        # Reduced timeout to 3 seconds to keep badge responsive
        response = urlopen("https://worldtimeapi.org/api/timezone/Etc/UTC", timeout=3)
        try:
            data = response.read()
            time_data = json.loads(data)
            # datetime format: "2025-10-30T01:23:45.123456+00:00"
            datetime_str = time_data.get("datetime", "")
            
            if datetime_str:
                # Parse the date part (YYYY-MM-DD) with validation
                try:
                    if "T" not in datetime_str:
                        raise ValueError("datetime string missing 'T' separator")
                    date_part = datetime_str.split("T")[0]
                    parts = date_part.split("-")
                    if len(parts) != 3:
                        raise ValueError("date part does not have three components")
                    year, month, day = parts
                    _cached_time = (int(year), int(month), int(day))
                    _fetch_success = True
                    return _cached_time
                except (ValueError, TypeError) as parse_err:
                    print(f"Failed to parse date from API response: {parse_err}")
                    _fetch_success = False
        finally:
            response.close()
    except Exception as e:
        # Network request failed, will retry on next attempt
        print(f"Failed to fetch time from internet: {e}")
        _fetch_success = False
    
    return None

def format_date(year, month, day):
    """
    Format date as DD MMM YYYY (e.g., 30 Oct 2025)
    """
    month_name = MONTH_NAMES[month - 1] if 1 <= month <= 12 else "???"
    return f"{day:02d} {month_name} {year}"

def get_current_date_string():
    """
    Get current date formatted as DD MMM YYYY
    Returns formatted string or "thinking..." if date cannot be determined
    """
    # Try to fetch current date from internet
    fetched_date = fetch_current_date()
    
    if fetched_date:
        # Use internet time
        year, month, day = fetched_date
        return format_date(year, month, day)
    
    # Return "thinking..." if we don't have a date yet (no fallback to local time)
    return "thinking..."

def get_days_until_christmas():
    """
    Calculate days until next Christmas (Dec 25)
    Returns None if date cannot be determined from network
    """
    # Try to fetch current date from internet
    fetched_date = fetch_current_date()
    
    if not fetched_date:
        # Cannot calculate without valid date from network
        return None
    
    current_year, current_month, current_day = fetched_date
    
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
    
    screen.font = large_font
    screen.brush = TEXT_BRUSH
    
    if days is not None:
        # We have a valid date - show countdown
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
    else:
        # Still fetching date - show "thinking..."
        screen.font = small_font
        message = "thinking..."
        w, _ = screen.measure_text(message)
        screen.text(message, 80 - (w // 2), 55)
    
    # Display today's date at the bottom (only if we have a real date, not "thinking...")
    date_string = get_current_date_string()
    if date_string and date_string != "thinking...":
        screen.font = small_font
        w, _ = screen.measure_text(date_string)
        screen.text(date_string, 80 - (w // 2), 105)

if __name__ == "__main__":
    run(update)
