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
ip_address = "0.0.0.0"
channel = None
security = None
last_attempt_time = None
WIFI_TIMEOUT = 15  # seconds
RETRY_DELAY = 15  # seconds

# Scroll state
scroll_y = 0
scroll_target = 0
content_height = 0
SCROLL_STEP = 10  # Pixels per button press

wlan_security_types = {
    0: "Open",
    1: "WEP",
    2: "WPA-PSK",
    3: "WPA2-PSK",
    4: "WPA/WPA2-PSK",
    5: "WPA2-Enterprise",
    6: "WPA3-PSK",
    7: "WPA2/WPA3-PSK",
    4194304: "WPA2-PSK",          # Alternative value
    4194308: "WPA2-PSK (TKIP+CCMP)",  # Common configuration
    4194310: "WPA3-PSK (SAE)"     # WPA3 with SAE
}

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
    global wlan, channel, connection_status, connecting, connection_start_time, ip_address, last_attempt_time, security
    
    if wlan is None:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
    
    # Check if we're already connected
    if wlan.isconnected():
        connection_status = "Connected"
        connecting = False
        ip_address = wlan.ifconfig()[0]
        channel = wlan.config('channel')
        security = wlan_security_types.get(wlan.config('security'), 'Unknown')
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
            ip_address = wlan.ifconfig()[0]
            channel = wlan.config('channel')
            security = wlan_security_types.get(wlan.config('security'), 'Unknown')
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
    global scroll_y, scroll_target, content_height
    
    try:
        # Calculate the maximum scroll position (content height minus visible area)
        visible_area = 80  # Space between header and footer
        max_scroll = max(0, content_height - visible_area)
        
        # Handle scrolling with button press
        if io.BUTTON_UP in io.pressed:
            scroll_target = max(0, scroll_target - SCROLL_STEP)  # Scroll up
            
        if io.BUTTON_DOWN in io.pressed:
            scroll_target = min(max_scroll, scroll_target + SCROLL_STEP)  # Scroll down
        
        # Ensure scroll target stays within bounds
        scroll_target = max(0, min(max_scroll, scroll_target))
        
        # Smooth scroll animation
        scroll_delta = scroll_target - scroll_y
        if abs(scroll_delta) > 0.1:
            movement = scroll_delta * (io.ticks_delta / 50)  # Faster animation
            scroll_y = scroll_y + movement
            # Keep scroll_y within bounds
            scroll_y = max(0, min(max_scroll, scroll_y))
        else:
            scroll_y = scroll_target
            
    except Exception as e:
        print(f"Scroll error: {e}")
        # Reset scroll state if something goes wrong
        scroll_y = 0
        scroll_target = 0
    
    # Clear screen
    screen.brush = background
    screen.draw(shapes.rectangle(0, 0, 160, 120))
    
    # Draw header (fixed position, no scroll)
    screen.font = small_font
    screen.brush = phosphor
    center_text("WiFi Settings", 2)
    
    # Draw line separator (fixed position)
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
        
        # Start scrollable content
        content_y = y
        
        # SSID
        visible_y = content_y - scroll_y  # Convert to screen space
        if visible_y >= 15 and visible_y <= 100:  # Only draw if in visible area
            screen.brush = phosphor
            screen.text("Network:", 5, visible_y)
        content_y += 10
        visible_y = content_y - scroll_y
        if visible_y >= 18 and visible_y <= 100:
            screen.brush = white
            if WIFI_SSID:
                # Truncate if too long
                ssid_display = WIFI_SSID if len(WIFI_SSID) <= 20 else WIFI_SSID[:17] + "..."
                screen.text(ssid_display, 10, visible_y)
            else:
                screen.brush = gray
                screen.text("Not set", 10, visible_y)
        content_y += 12
        
        # Password
        visible_y = content_y - scroll_y
        if visible_y >= 18 and visible_y <= 100:
            screen.brush = phosphor
            screen.text("Password:", 5, visible_y)
        content_y += 10
        visible_y = content_y - scroll_y
        if visible_y >= 18 and visible_y <= 100:
            screen.brush = white
            if WIFI_PASSWORD:
                screen.text(mask_password(WIFI_PASSWORD), 10, visible_y)
            else:
                screen.brush = gray
                screen.text("Not set", 10, visible_y)
        content_y += 12
        
        # GitHub Username
        visible_y = content_y - scroll_y
        if visible_y >= 18 and visible_y <= 100:
            screen.brush = phosphor
            screen.text("GitHub User:", 5, visible_y)
        content_y += 10
        visible_y = content_y - scroll_y
        if visible_y >= 18 and visible_y <= 100:
            screen.brush = white
            if GITHUB_USERNAME:
                screen.text(GITHUB_USERNAME, 10, visible_y)
            else:
                screen.brush = gray
                screen.text("Not set", 10, visible_y)
        content_y += 12
        
        # Connection status
        check_connection_status()
        visible_y = content_y - scroll_y
        if visible_y >= 18 and visible_y <= 100:
            screen.brush = phosphor
            screen.text("Status:", 5, visible_y)
        content_y += 10
        visible_y = content_y - scroll_y
        if visible_y >= 18 and visible_y <= 100:
            if connection_status == "Connected":
                screen.brush = green
            elif "Connecting" in connection_status:
                screen.brush = phosphor
            elif "Retry" in connection_status:
                screen.brush = gray
            else:
                screen.brush = red
            screen.text(connection_status, 10, visible_y)
        content_y += 12
        
        # IP Address
        if connection_status == "Connected":
            visible_y = content_y - scroll_y
            if visible_y >= 18 and visible_y <= 100:
                screen.brush = phosphor
                screen.text("IP Address:", 5, visible_y)
            content_y += 10
            visible_y = content_y - scroll_y
            if visible_y >= 18 and visible_y <= 100:
                if ip_address == "0.0.0.0":
                    screen.brush = gray
                else:
                    screen.brush = white
                screen.text(ip_address, 10, visible_y)
            content_y += 12

        # Channel
        if connection_status == "Connected":
            visible_y = content_y - scroll_y
            if visible_y >= 18 and visible_y <= 100:
                screen.brush = phosphor
                screen.text("Channel:", 5, visible_y)
            content_y += 10
            visible_y = content_y - scroll_y
            if visible_y >= 18 and visible_y <= 100:
                if channel is None:
                    screen.brush = gray
                    screen.text("N/A", 10, visible_y)
                else:
                    screen.brush = white
                    screen.text(str(channel), 10, visible_y)
            content_y += 12
        
        # Security
        if connection_status == "Connected":
            visible_y = content_y - scroll_y
            if visible_y >= 18 and visible_y <= 100:
                screen.brush = phosphor
                screen.text("Security:", 5, visible_y)
            content_y += 10
            visible_y = content_y - scroll_y
            if visible_y >= 18 and visible_y <= 100:
                if security is None:
                    screen.brush = gray
                    screen.text("N/A", 10, visible_y)
                else:
                    screen.brush = white
                    screen.text(str(security), 10, visible_y)
            content_y += 12

        # Update total content height
        content_height = content_y - y
        
        # Draw scroll indicators if needed
        if scroll_y > 0:
            screen.brush = brushes.color(255, 255, 255, 128)
            screen.draw(shapes.rectangle(150, 15, 10, 2))  # Up indicator
        if scroll_y < max_scroll:  # Show down indicator if more content below
            screen.brush = brushes.color(255, 255, 255, 128)
            screen.draw(shapes.rectangle(150, 103, 10, 2))  # Down indicator
        
        # Debug info
    
    # Draw bottom instructions (fixed position)
    screen.font = small_font
    screen.brush = gray
    screen.draw(shapes.rectangle(5, 103, 150, 1))
    center_text("UP/DOWN to scroll", 106)


if __name__ == "__main__":
    run(update)
