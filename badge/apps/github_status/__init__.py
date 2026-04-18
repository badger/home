import sys
import os

sys.path.insert(0, "/system/apps/github_status")
os.chdir("/system/apps/github_status")

from badgeware import io, brushes, shapes, screen, PixelFont, run
import network
from urllib.urequest import urlopen
import json
import gc

# Load fonts
small_font = PixelFont.load("/system/assets/fonts/ark.ppf")
large_font = PixelFont.load("/system/assets/fonts/absolute.ppf")

# Colors
white = brushes.color(235, 245, 255)
phosphor = brushes.color(211, 250, 55)
background = brushes.color(13, 17, 23)
gray = brushes.color(100, 110, 120)
green = brushes.color(46, 160, 67)
yellow = brushes.color(210, 153, 34)
red = brushes.color(248, 81, 73)

# GitHub Status API endpoint
STATUS_URL = "https://www.githubstatus.com/api/v2/summary.json"

# Refresh interval (10 minutes in milliseconds)
REFRESH_INTERVAL_MS = 10 * 60 * 1000

# Overall status levels
STATUS_OK = "ok"
STATUS_PARTIAL = "partial"
STATUS_DOWN = "down"

# Component statuses considered "impacted"
IMPACTED_STATUSES = (
    "degraded_performance",
    "partial_outage",
    "major_outage",
)

# State
WIFI_TIMEOUT = 60
WIFI_PASSWORD = None
WIFI_SSID = None

wlan = None
connected = False
ticks_start = None
overall_status = None
impacted_services = []
loading = False
error_message = None
last_update = None
scroll_offset = 0
last_scroll_tick = 0
SCROLL_REPEAT_MS = 180


def get_wifi_credentials():
    """Load WiFi credentials from secrets.py"""
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

    return WIFI_SSID is not None


def wlan_start():
    """Start WiFi connection"""
    global wlan, ticks_start, connected

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

        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        print("Connecting to WiFi...")

    connected = wlan.isconnected()

    if io.ticks - ticks_start < WIFI_TIMEOUT * 1000:
        if connected:
            return True
        return True  # still waiting
    elif not connected:
        return False

    return True


def classify_status(indicator, components):
    """Map the GitHub status response to one of our three display states."""
    total = len(components)
    impacted = sum(1 for c in components if c.get("status") in IMPACTED_STATUSES)
    major_outages = sum(1 for c in components if c.get("status") == "major_outage")

    # "everything is down" when the overall indicator is critical, or all
    # reported components are in a major outage.
    if indicator == "critical" or (total > 0 and major_outages == total):
        return STATUS_DOWN

    # "all good" when nothing is impacted and indicator is none
    if impacted == 0 and indicator == "none":
        return STATUS_OK

    # Otherwise - some services are impacted
    return STATUS_PARTIAL


def fetch_status():
    """Fetch GitHub status from the status API."""
    global overall_status, impacted_services, loading, error_message, last_update, scroll_offset

    loading = True
    error_message = None

    try:
        response = urlopen(STATUS_URL, headers={"User-Agent": "GitHubBadge"})
        data = b""
        chunk = bytearray(512)

        while True:
            length = response.readinto(chunk)
            if length == 0:
                break
            data += chunk[:length]

        result = json.loads(data.decode('utf-8'))

        indicator = result.get('status', {}).get('indicator', 'none')
        components = result.get('components', []) or []

        # Only show user-visible top-level components - skip groups themselves
        # and components that are part of a group (they'd duplicate the group).
        visible = [
            c for c in components
            if not c.get('group', False)
        ]

        impacted_services = [
            c.get('name', 'Unknown')
            for c in visible
            if c.get('status') in IMPACTED_STATUSES
        ]

        overall_status = classify_status(indicator, visible)
        scroll_offset = 0

        print(f"GitHub status: {overall_status} ({len(impacted_services)} impacted)")

        del response, data, chunk, result, components, visible
        gc.collect()

    except Exception as e:
        print(f"Error fetching GitHub status: {e}")
        error_message = str(e)
        overall_status = None

    loading = False
    last_update = io.ticks


def center_text(text, y):
    """Draw centered text"""
    w, _ = screen.measure_text(text)
    screen.text(text, int(80 - (w / 2)), y)


# Scroll / layout constants for the impacted services list
LIST_TOP = 42
LIST_BOTTOM = 104
LINE_HEIGHT = 10


def visible_lines():
    return (LIST_BOTTOM - LIST_TOP) // LINE_HEIGHT


def clamp_scroll():
    global scroll_offset
    max_offset = max(0, len(impacted_services) - visible_lines())
    if scroll_offset < 0:
        scroll_offset = 0
    elif scroll_offset > max_offset:
        scroll_offset = max_offset


def draw_header():
    """Draw the app header and refresh countdown."""
    screen.font = small_font
    screen.brush = phosphor
    screen.text("GITHUB STATUS", 2, 2)

    if last_update is not None:
        elapsed = io.ticks - last_update
        remaining = max(0, REFRESH_INTERVAL_MS - elapsed) // 1000
        mins = int(remaining // 60)
        secs = int(remaining % 60)
        timer_text = f"{mins}:{secs:02d}"
        screen.brush = gray
        w, _ = screen.measure_text(timer_text)
        screen.text(timer_text, 155 - w, 2)

    # separator line
    screen.brush = gray
    screen.draw(shapes.rectangle(5, 13, 150, 1))


def draw_status_dot(color_brush):
    """Draw a coloured status indicator dot."""
    screen.brush = color_brush
    screen.draw(shapes.circle(80, 32, 8))


def draw_all_good():
    draw_status_dot(green)
    screen.font = large_font
    screen.brush = white
    center_text("all good", 50)
    screen.font = small_font
    screen.brush = gray
    center_text("All systems operational", 72)


def draw_everything_down():
    draw_status_dot(red)
    screen.font = large_font
    screen.brush = red
    center_text("everything is down", 50)
    screen.font = small_font
    screen.brush = gray
    center_text("Major outage in progress", 72)


def draw_partial():
    # Coloured header band
    draw_status_dot(yellow)
    screen.font = small_font
    screen.brush = yellow
    center_text("some deprecated services", 24)

    # Service list
    clamp_scroll()

    screen.font = small_font
    if not impacted_services:
        screen.brush = gray
        center_text("(no services reported)", LIST_TOP + 10)
        return

    vis = visible_lines()
    start = scroll_offset
    end = min(len(impacted_services), start + vis)

    for i in range(start, end):
        name = impacted_services[i]
        y = LIST_TOP + (i - start) * LINE_HEIGHT

        # bullet
        screen.brush = yellow
        screen.draw(shapes.rectangle(4, y + 3, 3, 3))

        # truncate if too wide
        max_px = 140
        label = name
        w, _ = screen.measure_text(label)
        while w > max_px and len(label) > 3:
            label = label[:-1]
            w, _ = screen.measure_text(label + "...")
        if label != name:
            label = label + "..."
        screen.brush = white
        screen.text(label, 10, y)

    # Scroll indicators
    screen.brush = gray
    if start > 0:
        screen.text("^", 150, LIST_TOP)
    if end < len(impacted_services):
        screen.text("v", 150, LIST_BOTTOM - LINE_HEIGHT)


def draw_footer():
    """Draw the status bar at the bottom of the screen."""
    screen.font = small_font
    if not connected:
        screen.brush = gray
        screen.text("Connecting...", 2, 110)
        return

    screen.brush = phosphor
    screen.text("B:Refresh", 2, 110)

    if overall_status == STATUS_PARTIAL and len(impacted_services) > visible_lines():
        screen.brush = gray
        hint = "UP/DOWN:Scroll"
        w, _ = screen.measure_text(hint)
        screen.text(hint, 155 - w, 110)


def draw_error():
    screen.font = small_font
    screen.brush = red
    center_text("Status fetch failed", 40)
    screen.brush = gray
    # Wrap error message
    y = 55
    words = (error_message or "").split()
    line = ""
    for word in words:
        test = (line + " " + word) if line else word
        w, _ = screen.measure_text(test)
        if w < 140:
            line = test
        else:
            center_text(line, y)
            y += 10
            line = word
            if y > 95:
                break
    if line and y <= 95:
        center_text(line, y)


def draw_loading():
    screen.font = large_font
    screen.brush = white
    center_text("Checking", 40)
    center_text("GitHub...", 58)
    screen.font = small_font
    screen.brush = gray
    dots = "." * ((int(io.ticks / 500) % 3) + 1)
    center_text(dots, 78)


def draw_screen():
    # Background
    screen.brush = background
    screen.clear()

    draw_header()

    if loading and overall_status is None:
        draw_loading()
    elif error_message and overall_status is None:
        draw_error()
    elif overall_status == STATUS_OK:
        draw_all_good()
    elif overall_status == STATUS_DOWN:
        draw_everything_down()
    elif overall_status == STATUS_PARTIAL:
        draw_partial()
    else:
        draw_loading()

    draw_footer()


def update():
    """Main update loop."""
    global scroll_offset

    # WiFi credentials
    if not get_wifi_credentials():
        screen.brush = background
        screen.clear()
        screen.font = large_font
        screen.brush = white
        center_text("No WiFi Config", 40)
        screen.font = small_font
        screen.brush = phosphor
        center_text("Edit secrets.py", 60)
        return

    # WiFi connection
    if not connected:
        wlan_start()
        if not connected:
            screen.brush = background
            screen.clear()
            screen.font = small_font
            screen.brush = phosphor
            center_text("Connecting to WiFi", 50)
            dots = "." * ((int(io.ticks / 500) % 3) + 1)
            screen.brush = gray
            center_text(dots, 65)
            return

    # First fetch once connected
    if connected and last_update is None and not loading:
        fetch_status()

    # Manual refresh
    if io.BUTTON_B in io.pressed and not loading:
        fetch_status()

    # Auto-refresh every 10 minutes
    if last_update is not None and (io.ticks - last_update) > REFRESH_INTERVAL_MS and not loading:
        fetch_status()

    # Scrolling in the service list (only meaningful for partial outage).
    # Initial press scrolls immediately, then auto-repeats while held.
    global last_scroll_tick
    if overall_status == STATUS_PARTIAL and impacted_services:
        delta = 0
        if io.BUTTON_UP in io.pressed:
            delta = -1
        elif io.BUTTON_DOWN in io.pressed:
            delta = 1
        elif (io.ticks - last_scroll_tick) >= SCROLL_REPEAT_MS:
            if io.BUTTON_UP in io.held:
                delta = -1
            elif io.BUTTON_DOWN in io.held:
                delta = 1

        if delta != 0:
            scroll_offset += delta
            last_scroll_tick = io.ticks
            clamp_scroll()

    draw_screen()


if __name__ == "__main__":
    run(update)
