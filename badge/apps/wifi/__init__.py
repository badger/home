import sys
import os

sys.path.insert(0, "/system/apps/wifi")
os.chdir("/system/apps/wifi")

from badgeware import io, brushes, shapes, screen, PixelFont, run, Matrix
import network

# Load fonts
small_font = PixelFont.load("/system/assets/fonts/ark.ppf")
large_font = PixelFont.load("/system/assets/fonts/absolute.ppf")

# Colors
white = brushes.color(235, 245, 255)
phosphor = brushes.color(211, 250, 55)
background = brushes.color(13, 17, 23)
gray = brushes.color(100, 110, 120)
green = brushes.color(46, 160, 67)
red = brushes.color(248, 81, 73)

# WiFi credentials from secrets.py
WIFI_SSID = None
WIFI_PASSWORD = None
GITHUB_USERNAME = None

# Connection state
wlan = None
connection_status = "Not Connected"
connecting = False
connection_start_time = None
last_attempt_time = None
WIFI_TIMEOUT = 15  # seconds
RETRY_DELAY = 15  # seconds


def load_wifi_credentials():
    """Load WiFi credentials from secrets.py"""
    global WIFI_SSID, WIFI_PASSWORD, GITHUB_USERNAME
    
    try:
        sys.path.insert(0, "/")
        from secrets import WIFI_SSID, WIFI_PASSWORD, GITHUB_USERNAME
        sys.path.pop(0)
        return True
    except ImportError:
        WIFI_SSID = None
        WIFI_PASSWORD = None
        GITHUB_USERNAME = None
        return False


def check_connection_status():
    """Check if currently connected to WiFi and manage connection attempts"""
    global wlan, connection_status, connecting, connection_start_time, last_attempt_time
    
    if wlan is None:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
    
    # Check if we're already connected
    if wlan.isconnected():
        connection_status = "Connected"
        connecting = False
        return True
    
    # If not connecting yet, start connection
    if not connecting and WIFI_SSID and WIFI_PASSWORD:
        # Check if we should retry (after failed attempt)
        if last_attempt_time:
            elapsed_since_last = (io.ticks - last_attempt_time) / 1000
            if elapsed_since_last < RETRY_DELAY:
                # Still waiting for retry
                remaining = int(RETRY_DELAY - elapsed_since_last)
                connection_status = f"Retry in {remaining}s"
                return False
        
        # Start connection attempt
        connecting = True
        connection_start_time = io.ticks
        connection_status = "Connecting..."
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        print(f"Attempting to connect to {WIFI_SSID}...")
        return False
    
    # If we're in the process of connecting
    if connecting:
        elapsed = (io.ticks - connection_start_time) / 1000
        
        # Check if connected
        if wlan.isconnected():
            connection_status = "Connected"
            connecting = False
            print("WiFi connected successfully!")
            return True
        
        # Check if timeout
        if elapsed >= WIFI_TIMEOUT:
            connection_status = "Connection failed"
            connecting = False
            last_attempt_time = io.ticks
            print("WiFi connection timeout")
            return False
        
        # Still connecting
        dots = "." * ((int(io.ticks / 500) % 3) + 1)
        connection_status = f"Connecting{dots}"
        return False
    
    return False


def center_text(text, y):
    """Draw centered text at specified y position"""
    w, _ = screen.measure_text(text)
    screen.text(text, 80 - (w / 2), y)


def wrap_text(text, x, y, max_width):
    """Wrap text to fit within max_width"""
    words = text.split()
    lines = []
    current_line = ""
    
    for word in words:
        test_line = current_line + (" " if current_line else "") + word
        w, _ = screen.measure_text(test_line)
        
        if w <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    
    if current_line:
        lines.append(current_line)
    
    # Draw lines
    for line in lines:
        screen.text(line, x, y)
        y += 10
    
    return y


def mask_password(password):
    """Mask password for display (show first 2 and last 2 chars)"""
    if not password:
        return "None"
    if len(password) <= 4:
        return "*" * len(password)
    return password[:2] + ("*" * (len(password) - 4)) + password[-2:]


def update():
    """Main update loop for WiFi info display"""
    # Clear screen
    screen.brush = background
    screen.draw(shapes.rectangle(0, 0, 160, 120))
    
    # Draw header
    screen.font = small_font
    screen.brush = phosphor
    center_text("WiFi Settings", 2)
    
    # Draw line separator
    screen.brush = gray
    screen.draw(shapes.rectangle(5, 13, 150, 1))
    
    # Load credentials
    has_credentials = load_wifi_credentials()
    
    if not has_credentials:
        # No secrets.py found
        screen.font = small_font
        screen.brush = white
        center_text("No Configuration", 25)
        
        screen.brush = gray
        y = wrap_text("Edit 'secrets.py' in disk mode to set WiFi credentials.", 10, 45, 140)
        
    else:
        # Display WiFi info
        screen.font = small_font
        y = 18
        
        # SSID
        screen.brush = phosphor
        screen.text("Network:", 5, y)
        screen.brush = white
        y += 10
        if WIFI_SSID:
            # Truncate if too long
            ssid_display = WIFI_SSID if len(WIFI_SSID) <= 20 else WIFI_SSID[:17] + "..."
            screen.text(ssid_display, 10, y)
        else:
            screen.brush = gray
            screen.text("Not set", 10, y)
        y += 12
        
        # Password
        screen.brush = phosphor
        screen.text("Password:", 5, y)
        screen.brush = white
        y += 10
        if WIFI_PASSWORD:
            screen.text(mask_password(WIFI_PASSWORD), 10, y)
        else:
            screen.brush = gray
            screen.text("Not set", 10, y)
        y += 12
        
        # GitHub Username
        screen.brush = phosphor
        screen.text("GitHub User:", 5, y)
        screen.brush = white
        y += 10
        if GITHUB_USERNAME:
            screen.text(GITHUB_USERNAME, 10, y)
        else:
            screen.brush = gray
            screen.text("Not set", 10, y)
        y += 15
        
        # Connection status
        check_connection_status()
        screen.brush = phosphor
        screen.text("Status:", 5, y)
        y += 10
        if connection_status == "Connected":
            screen.brush = green
        elif "Connecting" in connection_status:
            screen.brush = phosphor
        elif "Retry" in connection_status:
            screen.brush = gray
        else:
            screen.brush = red
        screen.text(connection_status, 10, y)
    
    # Draw bottom instructions
    screen.font = small_font
    screen.brush = gray
    screen.draw(shapes.rectangle(5, 103, 150, 1))
    center_text("Edit via USB mode", 106)


if __name__ == "__main__":
    run(update)
