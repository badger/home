import time
import random
import sys
from badgeware import screen, PixelFont, shapes, brushes, io, run, Matrix

try:
    import network
    import ntptime
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

# NTP sync state
_ntp_synced = False
_ntp_sync_attempt = 0
_last_sync_attempt = 0
SYNC_RETRY_INTERVAL = 5 * 1000  # Retry NTP sync every 5 seconds (in milliseconds) when failed

# Network connection state
WIFI_TIMEOUT = 60
WIFI_PASSWORD = None
WIFI_SSID = None
wlan = None
connected = False
ticks_start = None

def get_connection_details():
    """Get WiFi credentials from secrets.py"""
    global WIFI_PASSWORD, WIFI_SSID

    if WIFI_SSID is not None:
        return True

    try:
        sys.path.insert(0, "/")
        from secrets import WIFI_PASSWORD, WIFI_SSID
        sys.path.pop(0)
    except ImportError:
        WIFI_PASSWORD = None
        WIFI_SSID = None

    if not WIFI_SSID:
        return False

    return True

def wlan_start():
    """Initialize and connect to WiFi network"""
    global wlan, ticks_start, connected, WIFI_PASSWORD, WIFI_SSID

    if not NETWORK_AVAILABLE:
        return False

    if ticks_start is None:
        ticks_start = io.ticks

    if connected:
        return True

    if wlan is None:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)

        if wlan.isconnected():
            connected = True
            return True

    # attempt to find the SSID by scanning; some APs may be hidden intermittently
    try:
        ssid_found = False
        try:
            scans = wlan.scan()
        except Exception:
            scans = []

        for s in scans:
            # s[0] is SSID (bytes or str)
            ss = s[0]
            if isinstance(ss, (bytes, bytearray)):
                try:
                    ss = ss.decode("utf-8", "ignore")
                except Exception:
                    ss = str(ss)
            if ss == WIFI_SSID:
                ssid_found = True
                break

        if not ssid_found:
            # not found yet; if still within timeout, keep trying on subsequent calls
            if io.ticks - ticks_start < WIFI_TIMEOUT * 1000:
                # return True to indicate we're still attempting to connect (in-progress)
                return True
            else:
                # timed out
                return False

        # SSID is visible; attempt to connect (or re-attempt)
        try:
            wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        except Exception:
            # connection initiation failed; we'll retry while still within timeout
            if io.ticks - ticks_start < WIFI_TIMEOUT * 1000:
                return True
            return False

        # update connected state
        connected = wlan.isconnected()

        # if connected, return True; otherwise indicate in-progress until timeout
        if connected:
            return True
        if io.ticks - ticks_start < WIFI_TIMEOUT * 1000:
            return True
        return False
    except Exception as e:
        # on unexpected errors, don't crash the UI; report and return False
        try:
            print("wlan_start error:", e)
        except Exception:
            # Ignore errors in error reporting to avoid crashing the UI
            pass
        return False

def sync_time_via_ntp():
    """
    Sync system time using NTP
    Returns True if sync was successful, False otherwise
    """
    global _ntp_synced, _ntp_sync_attempt, _last_sync_attempt
    
    if not NETWORK_AVAILABLE:
        return False
    
    if not connected:
        return False
    
    # If already synced, don't sync again
    if _ntp_synced:
        return True
    
    # Check if we should retry
    current_ticks = io.ticks
    if _ntp_sync_attempt > 0:
        if current_ticks - _last_sync_attempt < SYNC_RETRY_INTERVAL:
            return False  # Still waiting to retry
    
    # Update last sync attempt timestamp
    _last_sync_attempt = current_ticks
    _ntp_sync_attempt += 1
    
    try:
        # Sync time via NTP
        ntptime.settime()
        _ntp_synced = True
        print("NTP time sync successful")
        return True
    except Exception as e:
        print(f"NTP sync failed (attempt {_ntp_sync_attempt}): {e}")
        return False

def get_current_date():
    """
    Get current date from system time (after NTP sync)
    Returns (year, month, day) tuple or None if time is not synced
    """
    if not _ntp_synced:
        return None
    
    try:
        # Get current time from system
        # time.localtime() returns: (year, month, day, hour, minute, second, weekday, yearday)
        current_time = time.localtime()
        year = current_time[0]
        month = current_time[1]
        day = current_time[2]
        
        # Sanity check: if year is unreasonable, NTP didn't actually work
        # Valid range: 2025-2100 (the badge was created in 2025)
        if year < 2025 or year > 2100:
            return None
        
        return (year, month, day)
    except Exception as e:
        print(f"Failed to get current date from system time: {e}")
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
    # Get current date from NTP-synced system time
    current_date = get_current_date()
    
    if current_date:
        # Use synced time
        year, month, day = current_date
        return format_date(year, month, day)
    
    # Return "thinking..." if we don't have a synced time yet
    return "thinking..."

def get_days_until_christmas():
    """
    Calculate days until next Christmas (Dec 25)
    Returns None if date cannot be determined from NTP-synced time
    """
    # Get current date from NTP-synced system time
    current_date = get_current_date()
    
    if not current_date:
        # Cannot calculate without valid synced date
        return None
    
    current_year, current_month, current_day = current_date
    
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
    global connected
    
    # Clear screen with dark blue background
    screen.brush = BG_BRUSH
    screen.clear()
    
    # Update and draw snowflakes (backdrop)
    for snowflake in snowflakes:
        snowflake.update()
        snowflake.draw()
    
    # Try to get connection details and start WLAN if network is available
    if NETWORK_AVAILABLE:
        if get_connection_details():
            wlan_start()
            # Once connected, attempt NTP sync
            if connected:
                sync_time_via_ntp()
    
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
        # Still fetching date - show appropriate message
        screen.font = small_font
        if not NETWORK_AVAILABLE:
            message = "network unavailable"
        elif not get_connection_details():
            message = "no wifi config"
        elif not connected:
            message = "connecting..."
        else:
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
