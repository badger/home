import sys
import os

sys.path.insert(0, "/system/apps/clock")
os.chdir("/system/apps/clock")

from badgeware import io, brushes, shapes, screen, PixelFont, run, Image
import network
import ntptime
import time
import gc
from machine import RTC

# Load fonts
small_font = PixelFont.load("/system/assets/fonts/ark.ppf")
large_font = PixelFont.load("/system/assets/fonts/absolute.ppf")
time_font = PixelFont.load("/system/assets/fonts/nope.ppf")

# Colors
white = brushes.color(235, 245, 255)
phosphor = brushes.color(211, 250, 55)
background = brushes.color(13, 17, 23)
gray = brushes.color(100, 110, 120)
green = brushes.color(46, 160, 67)
red = brushes.color(248, 81, 73)
blue = brushes.color(73, 219, 255)

# WiFi credentials
WIFI_SSID = None
WIFI_PASSWORD = None

# Connection state
wlan = None
rtc = None
connection_status = "Not Connected"
sync_status = "Not Synced"
connecting = False
syncing = False
connection_start_time = None
last_sync_time = None
initial_sync_done = False
auto_sync_enabled = True
WIFI_TIMEOUT = 15  # seconds
SYNC_INTERVAL = 3600  # Sync every hour (3600 seconds)

# Time display state
current_time = None
current_date = None
local_time = None
timezone_offset = 0  # Offset in seconds from UTC
timezone_name = "UTC"
location_name = "Unknown"
location_detected = False

# Animation state
blink_colon = True
last_blink = 0
BLINK_INTERVAL = 500  # milliseconds


def load_wifi_credentials():
    """Load WiFi credentials from secrets.py"""
    global WIFI_SSID, WIFI_PASSWORD
    
    try:
        sys.path.insert(0, "/")
        from secrets import WIFI_SSID, WIFI_PASSWORD
        sys.path.pop(0)
        return True
    except ImportError:
        WIFI_SSID = None
        WIFI_PASSWORD = None
        return False


def init_rtc():
    """Initialize the RTC module"""
    global rtc
    try:
        rtc = RTC()
        return True
    except Exception as e:
        print(f"Error initializing RTC: {e}")
        return False


def connect_wifi():
    """Attempt to connect to WiFi"""
    global wlan, connection_status, connecting, connection_start_time
    
    if not WIFI_SSID or not WIFI_PASSWORD:
        connection_status = "No WiFi Config"
        return False
    
    if wlan is None:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
    
    if wlan.isconnected():
        connection_status = "Connected"
        connecting = False
        return True
    
    if not connecting:
        connecting = True
        connection_start_time = io.ticks
        connection_status = "Connecting..."
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        return False
    
    # Check connection progress
    elapsed = (io.ticks - connection_start_time) / 1000
    if wlan.isconnected():
        connection_status = "Connected"
        connecting = False
        return True
    elif elapsed >= WIFI_TIMEOUT:
        connection_status = "Failed"
        connecting = False
        return False
    else:
        dots = "." * ((int(io.ticks / 500) % 3) + 1)
        connection_status = f"Connecting{dots}"
        return False


def disconnect_wifi():
    """Disconnect and turn off WiFi to save power"""
    global wlan, connection_status
    try:
        if wlan:
            wlan.disconnect()
            wlan.active(False)
            connection_status = "Disconnected"
    except Exception as e:
        print(f"WiFi disconnect error: {e}")


def detect_timezone():
    """Detect timezone from IP location using ipapi.co"""
    global timezone_offset, timezone_name, location_name, location_detected
    
    # Always fetch fresh timezone data (in case user traveled or changed location)
    try:
        print("Detecting timezone from IP...")
        from urllib.urequest import urlopen
        import json
        
        # ipapi.co provides free IP geolocation with timezone info
        url = "https://ipapi.co/json/"
        
        response = urlopen(url, headers={"User-Agent": "GitHubBadge"})
        data = b""
        chunk = bytearray(512)
        
        while True:
            length = response.readinto(chunk)
            if length == 0:
                break
            data += chunk[:length]
        
        result = json.loads(data.decode('utf-8'))
        
        # Get timezone info
        timezone_name = result.get('timezone', 'UTC')
        location_name = result.get('city', 'Unknown')
        utc_offset_str = result.get('utc_offset', '+0000')
        
        # Parse UTC offset (format: +0500 or -0800)
        sign = 1 if utc_offset_str[0] == '+' else -1
        hours = int(utc_offset_str[1:3])
        minutes = int(utc_offset_str[3:5])
        timezone_offset = sign * (hours * 3600 + minutes * 60)
        
        location_detected = True
        print(f"Location: {location_name}, Timezone: {timezone_name}, Offset: {utc_offset_str}")
        
        del response, data, chunk, result
        gc.collect()
        
        return True
        
    except Exception as e:
        print(f"Error detecting timezone: {e}")
        timezone_offset = 0
        timezone_name = "UTC"
        location_name = "Unknown"
        return False


def sync_time():
    """Sync time from NTP server and update RTC"""
    global sync_status, syncing, last_sync_time, rtc, initial_sync_done
    
    if not wlan or not wlan.isconnected():
        sync_status = "WiFi Not Connected"
        return False
    
    if not rtc:
        if not init_rtc():
            sync_status = "RTC Error"
            return False
    
    try:
        syncing = True
        sync_status = "Syncing..."
        
        # Detect timezone first (if not already detected)
        if not location_detected:
            detect_timezone()
        
        # Set NTP server (default is pool.ntp.org)
        ntptime.settime()
        
        # Get the time from NTP (UTC)
        # NTP sets the system time automatically
        # machine.RTC.datetime is already updated by ntptime.settime()
        # No need to manually set RTC
        
        last_sync_time = io.ticks
        sync_status = "Synced"
        syncing = False
        initial_sync_done = True
        
        # Disconnect WiFi after successful sync to save power
        disconnect_wifi()
        
        return True
        
    except Exception as e:
        print(f"NTP sync error: {e}")
        sync_status = f"Sync Failed"
        syncing = False
        return False


def update_time_display():
    """Update the time and date strings from RTC"""
    global current_time, current_date, local_time, rtc
    
    if not rtc:
        if not init_rtc():
            current_time = "--:--:--"
            current_date = "-- --- ----"
            local_time = "--:--:--"
            return
    
    try:
        # machine.RTC returns: (year, month, day, weekday, hour, minute, second, subseconds)
        dt = rtc.datetime()
        
        # Format UTC time as HH:MM:SS
        current_time = f"{dt[4]:02d}:{dt[5]:02d}:{dt[6]:02d}"
        
        # Calculate local time by applying timezone offset
        total_seconds = dt[4] * 3600 + dt[5] * 60 + dt[6] + timezone_offset
        
        # Handle day overflow/underflow
        days_offset = 0
        if total_seconds < 0:
            days_offset = -1
            total_seconds += 86400
        elif total_seconds >= 86400:
            days_offset = 1
            total_seconds -= 86400
        
        local_hour = (total_seconds // 3600) % 24
        local_minute = (total_seconds % 3600) // 60
        local_second = total_seconds % 60
        
        local_time = f"{local_hour:02d}:{local_minute:02d}:{local_second:02d}"
        
        # Format date (using UTC date, could adjust for timezone if needed)
        weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        
        weekday_name = weekdays[dt[3]] if 0 <= dt[3] < 7 else "---"
        month_name = months[dt[1] - 1] if 1 <= dt[1] <= 12 else "---"
        
        current_date = f"{weekday_name} {dt[2]:02d} {month_name} {dt[0]}"
        
    except Exception as e:
        print(f"Error reading RTC: {e}")
        current_time = "--:--:--"
        current_date = "-- --- ----"
        local_time = "--:--:--"


def center_text(text, y):
    """Draw centered text at specified y position"""
    w, _ = screen.measure_text(text)
    screen.text(text, 80 - (w / 2), y)


def init():
    """Initialize the clock app"""
    global auto_sync_enabled
    load_wifi_credentials()
    init_rtc()
    # Start initial WiFi connection and sync on app start
    auto_sync_enabled = True


def update():
    """Main update loop for clock display"""
    global blink_colon, last_blink, last_sync_time, initial_sync_done, auto_sync_enabled
    
    # Clear screen
    screen.brush = background
    screen.draw(shapes.rectangle(0, 0, 160, 120))
    
    # Draw header
    screen.font = small_font
    screen.brush = phosphor
    center_text("Clock", 2)
    
    # Draw line separator
    screen.brush = gray
    screen.draw(shapes.rectangle(5, 13, 150, 1))
    
    # Update time from RTC
    update_time_display()
    
    # Handle button presses
    if io.BUTTON_A in io.pressed:
        # Manual sync - connect WiFi
        if load_wifi_credentials():
            connect_wifi()
    
    if io.BUTTON_B in io.pressed:
        # Sync time if connected
        if wlan and wlan.isconnected():
            sync_time()
    
    # Auto-sync logic
    if auto_sync_enabled:
        # Initial sync on startup
        if not initial_sync_done and not connecting and not syncing:
            if load_wifi_credentials():
                if WIFI_SSID and WIFI_PASSWORD:
                    connect_wifi()
        
        # Hourly auto-sync
        if initial_sync_done and last_sync_time:
            elapsed_since_sync = (io.ticks - last_sync_time) / 1000
            if elapsed_since_sync >= SYNC_INTERVAL:
                # Time to sync again - reconnect WiFi
                if not connecting and not syncing:
                    if load_wifi_credentials():
                        if WIFI_SSID and WIFI_PASSWORD:
                            connect_wifi()
    
    # Update WiFi connection and auto-sync when connected
    if connecting:
        if connect_wifi():
            # Successfully connected, now sync
            if auto_sync_enabled and not syncing:
                sync_time()
    
    # Blink colon animation
    if io.ticks - last_blink > BLINK_INTERVAL:
        blink_colon = not blink_colon
        last_blink = io.ticks
    
    # Display LOCAL time with large font (primary display)
    screen.font = time_font
    screen.brush = white
    
    if local_time:
        # Split time into parts for blinking colon
        parts = local_time.split(":")
        if len(parts) == 3:
            hours = parts[0]
            mins = parts[1]
            secs = parts[2]
            
            # Measure and calculate positions
            h_w, _ = screen.measure_text(hours)
            m_w, _ = screen.measure_text(mins)
            s_w, _ = screen.measure_text(secs)
            colon_w, _ = screen.measure_text(":")
            
            total_w = h_w + colon_w + m_w + colon_w + s_w
            x = 80 - (total_w / 2)
            y = 30
            
            # Draw hours
            screen.text(hours, x, y)
            x += h_w
            
            # Draw first colon (blinking)
            if blink_colon:
                screen.brush = blue
            else:
                screen.brush = gray
            screen.text(":", x, y)
            x += colon_w
            
            # Draw minutes
            screen.brush = white
            screen.text(mins, x, y)
            x += m_w
            
            # Draw second colon (blinking)
            if blink_colon:
                screen.brush = blue
            else:
                screen.brush = gray
            screen.text(":", x, y)
            x += colon_w
            
            # Draw seconds
            screen.brush = white
            screen.text(secs, x, y)
    
    # Display timezone and location
    screen.font = small_font
    screen.brush = phosphor
    if location_detected:
        # Show location and timezone
        tz_display = f"{location_name} ({timezone_name})"
        center_text(tz_display, 50)
    else:
        center_text("UTC (detecting...)", 50)
    
    # Display date
    screen.brush = gray
    if current_date:
        center_text(current_date, 62)
    
    # Draw status section
    y = 75
    
    # Sync status
    screen.brush = gray
    screen.text("Last sync:", 5, y)
    if sync_status == "Synced":
        screen.brush = green
        # Show time since last sync
        if last_sync_time:
            elapsed = int((io.ticks - last_sync_time) / 1000)
            if elapsed < 60:
                sync_text = f"{elapsed}s ago"
            elif elapsed < 3600:
                sync_text = f"{elapsed // 60}m ago"
            else:
                sync_text = f"{elapsed // 3600}h ago"
            screen.text(sync_text, 75, y)
        else:
            screen.text("Synced", 75, y)
    elif syncing:
        screen.brush = blue
        screen.text("Syncing...", 75, y)
    elif connecting:
        screen.brush = blue
        dots = "." * ((int(io.ticks / 500) % 3) + 1)
        screen.text(f"WiFi{dots}", 75, y)
    elif not initial_sync_done:
        screen.brush = phosphor
        screen.text("Pending", 75, y)
    else:
        screen.brush = red
        screen.text(sync_status[:15], 75, y)
    
    y += 12
    
    # Next sync countdown (if synced)
    if initial_sync_done and last_sync_time and auto_sync_enabled:
        screen.brush = gray
        screen.text("Next sync:", 5, y)
        elapsed = int((io.ticks - last_sync_time) / 1000)
        remaining = SYNC_INTERVAL - elapsed
        if remaining > 0:
            if remaining < 60:
                next_text = f"{remaining}s"
            elif remaining < 3600:
                next_text = f"{remaining // 60}m"
            else:
                next_text = f"{remaining // 3600}h {(remaining % 3600) // 60}m"
            screen.brush = phosphor
            screen.text(next_text, 75, y)
        else:
            screen.brush = blue
            screen.text("Now", 75, y)
    
    # Draw bottom instructions
    screen.font = small_font
    screen.brush = gray
    screen.draw(shapes.rectangle(5, 103, 150, 1))
    center_text("A:Manual Sync", 106)


if __name__ == "__main__":
    run(update)
