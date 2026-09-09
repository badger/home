import sys
import os

# Ensure we run from the app directory so relative asset paths work
sys.path.insert(0, "/system/apps/wled")
os.chdir("/system/apps/wled")

from badgeware import io, brushes, shapes, screen, PixelFont, run, State
import network
import gc

# ---------------------------------------------------------------------------
# Standardized HTTP helper
# ---------------------------------------------------------------------------
# A tiny wrapper (`rq`) mimics the minimal subset of the urequests interface
# used here (get/post + status_code/text/close) while keeping memory usage low.

from urllib.urequest import urlopen  # type: ignore  # Built-in on badge firmware; direct import keeps code simple.


class _HTTPResponse:
    """Minimal response object exposing .status_code, .text, .close().

    Text is lazily decoded to avoid allocating unless needed. If decoding fails,
    raw bytes are returned (repr-safe for small payloads)."""

    def __init__(self, raw, status=200):
        self._raw = raw
        self.status_code = getattr(raw, "status", status)
        self._text = None

    @property
    def text(self):
        if self._text is None:
            try:
                # Some MicroPython builds return bytes; decode defensively.
                data = self._raw.read()
                if isinstance(data, bytes):
                    self._text = data.decode("utf-8", "ignore")
                else:  # already str
                    self._text = data
            except Exception:
                self._text = ""
        return self._text

    def close(self):
        try:
            if hasattr(self._raw, "close"):
                self._raw.close()
        except Exception:
            # Ignore errors during cleanup; resource may already be closed or not closable.
            pass


class rq:  # Mimic minimal urequests-like interface used by this app
    @staticmethod
    def get(url):
        # MicroPython's urlopen does not support reliable timeout; requests may block.
        raw = urlopen(url)
        return _HTTPResponse(raw)

    @staticmethod
    def post(url, data=None, headers=None):
        # Encode string payload to bytes when needed.
        if isinstance(data, str):
            data_bytes = data.encode()
        else:
            data_bytes = data
        # MicroPython's urlopen accepts headers as dict (not list of tuples)
        raw = urlopen(url, data=data_bytes, headers=headers)
        return _HTTPResponse(raw)

# Load fonts - use smaller, more compact fonts
small_font = PixelFont.load("/system/assets/fonts/ark.ppf")

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
def truncate_message(msg, max_len=16):
    """Truncate a message safely for status output with ellipsis."""
    try:
        if msg and len(msg) > max_len:
            return msg[:max_len] + "..."
    except Exception:
        # Ignore errors: fallback to original message if msg is not a string or has no length.
        pass
    return msg

# Colors
white = brushes.color(235, 245, 255)
phosphor = brushes.color(211, 250, 55)
background = brushes.color(13, 17, 23)
gray = brushes.color(100, 110, 120)
green = brushes.color(46, 160, 67)
red = brushes.color(248, 81, 73)

#############################################
# Configuration & Runtime State
#############################################

# WiFi / WLED config (loaded from secrets.py)
WIFI_SSID = None
WIFI_PASSWORD = None
WLED_HOST = None   # Will be set from WLED_IP in secrets.py (direct IP only)

# Connection state
wlan = None
wifi_connected = False
wled_connected = False
last_error = None        # Last WLED error string (untruncated)
last_errno = None        # Last numeric errno captured (e.g. 110)
ticks_start = None
WIFI_TIMEOUT = 60  # seconds before we give up attempting initial WiFi connect
last_scan_tick = 0
last_connect_attempt = 0  # Timestamp (io.ticks) of last explicit wlan.connect() attempt (post-scan)

# WLED state
wled_power = False
wled_color = None            # (r,g,b)
wled_brightness = 0          # 0-255
wled_effect_id = None        # Current effect ID (if any)
wled_effect_name = None      # Friendly effect name (if known)
status_message = "Starting..."

# Fetch state management to avoid blocking every frame
state_checked = False        # True once we have successfully fetched state
last_state_attempt = 0       # ticks of last HTTP attempt
state_attempts = 0           # how many tries so far
FETCH_RETRY_INTERVAL = 2000  # ms between attempts
MAX_FETCH_ATTEMPTS = 1       # Single attempt to avoid UI freeze
in_flight = False             # True while an HTTP request is active to avoid overlap
skip_wled = False             # User can choose to skip WLED queries (Button C)

# Control state
control_mode = False          # False = status view, True = control menu
control_selection = 0         # Current menu selection (0-4: Power, Color, Effect, Brightness, Back)
color_picker_active = False   # True when in color picker mode
color_index = 0               # Current color preset index
effect_picker_active = False  # True when in effect picker mode
effect_index = 0              # Current effect index
brightness_picker_active = False  # True when in brightness picker mode
brightness_value = 128        # Current brightness value (0-255)

# Color presets (common colors)
color_presets = [
    (255, 255, 255, "White"),
    (255, 0, 0, "Red"),
    (0, 255, 0, "Green"),
    (0, 0, 255, "Blue"),
    (255, 255, 0, "Yellow"),
    (0, 255, 255, "Cyan"),
    (255, 0, 255, "Magenta"),
    (255, 128, 0, "Orange"),
    (128, 0, 255, "Purple"),
    (255, 192, 203, "Pink"),
]

# Common WLED effects (ID and name)
effect_presets = [
    (0, "Solid"),
    (1, "Blink"),
    (2, "Breathe"),
    (9, "Rainbow"),
    (10, "Rainbow Cycle"),
    (11, "Scan"),
    (46, "Flow"),
    (101, "Pacifica"),
    (103, "Sunrise"),
]


def load_config():
    """Load WiFi credentials and WLED host from /secrets.py (mounted at disk root)."""
    global WIFI_SSID, WIFI_PASSWORD, WLED_HOST, status_message
    try:
        sys.path.insert(0, "/")
        try:
            from secrets import WIFI_SSID, WIFI_PASSWORD  # type: ignore
            try:
                from secrets import WLED_IP as _ip  # type: ignore
                WLED_HOST = _ip
            except ImportError:
                WLED_HOST = None
            status_message = "Config loaded" if WIFI_SSID and WIFI_PASSWORD else "No WiFi config"
        finally:
            if sys.path and sys.path[0] == "/":
                sys.path.pop(0)
    except ImportError:
        WIFI_SSID = WIFI_PASSWORD = WLED_HOST = None
        status_message = "No secrets.py"
    except Exception:
        WIFI_SSID = WIFI_PASSWORD = WLED_HOST = None
        status_message = "Config error"


def connect_wifi():
    """Attempt non-blocking WiFi connect with SSID presence scan."""
    global wlan, ticks_start, wifi_connected, status_message, last_scan_tick, last_connect_attempt

    if wifi_connected and wlan and wlan.isconnected():
        return True

    if not WIFI_SSID or not WIFI_PASSWORD:
        wifi_connected = False
        status_message = "Missing WiFi creds"
        return False

    if ticks_start is None:
        ticks_start = io.ticks

    # Lazy init interface
    if wlan is None:
        try:
            wlan = network.WLAN(network.STA_IF)
            wlan.active(True)
        except Exception:
            status_message = "WiFi init err"
            return False

    # Already connected?
    if wlan.isconnected():
        wifi_connected = True
        status_message = "WiFi OK"
        return True

    # Scan for SSID every 5s until found or timeout
    now = io.ticks
    if not wifi_connected and (now - last_scan_tick > 5000) and (now - ticks_start < WIFI_TIMEOUT * 1000):
        last_scan_tick = now
        try:
            scans = wlan.scan()
        except Exception:
            scans = []
        found = False
        for s in scans:
            ss = s[0]
            if isinstance(ss, (bytes, bytearray)):
                ss = ss.decode("utf-8", "ignore")
            if ss == WIFI_SSID:
                found = True
                break
        if not found:
            status_message = "Scanning for SSID" if (now - ticks_start) < WIFI_TIMEOUT * 1000 else status_message
        else:
            try:
                wlan.connect(WIFI_SSID, WIFI_PASSWORD)
                status_message = "Connecting WiFi..."
            except Exception:
                # Ignore connection errors; will retry in next loop iteration
                pass

    # Periodic reconnect attempts every 1.5s if not yet connected (after first scan cycle)
    if (not wifi_connected \
        and (now - ticks_start < WIFI_TIMEOUT * 1000) \
        and (now - last_connect_attempt >= 1500)):
        try:
            wlan.connect(WIFI_SSID, WIFI_PASSWORD)
            last_connect_attempt = now
            status_message = "Connecting WiFi..."
        except Exception:
            # Ignore connection errors; will retry after throttle interval until timeout
            last_connect_attempt = now  # still advance to avoid tight loop on immediate failures

    wifi_connected = wlan.isconnected()

    if wifi_connected:
        status_message = "WiFi connected"
        return True

    # Timeout?
    if io.ticks - ticks_start > WIFI_TIMEOUT * 1000:
        # Final check before declaring timeout
        if wlan.isconnected():
            wifi_connected = True
            status_message = "WiFi connected"
            return True
        status_message = f"WiFi timeout ({WIFI_SSID})"
        wifi_connected = False
        return False

    # Still trying
    elapsed = (io.ticks - ticks_start) // 1000
    status_message = f"Connecting... {elapsed}s"
    return True


def send_wled_command(data):
    """Send POST command to WLED API."""
    global wled_connected, status_message, last_error, last_errno, in_flight
    if in_flight:
        return False
    if not wifi_connected or not wlan or not wlan.isconnected():
        return False
    if not WLED_HOST:
        return False
    # Set in_flight only after passing all early-return preconditions.
    # This keeps the flag logic simple (no need to reset it in those paths)
    # and ensures that once marked, it is always cleared by the finally block.
    in_flight = True
    try:
        import json
        url = f"http://{WLED_HOST}/json/state"
        payload = json.dumps(data)
        headers = {"Content-Type": "application/json"}
        resp = rq.post(url, data=payload, headers=headers)
        success = resp.status_code in (200, 201)
        # Ensure we release underlying resources early.
        resp.close()
        status_message = "Command sent" if success else f"HTTP {resp.status_code}"
        return success
    except Exception as e:
        last_error = str(e)
        status_message = f"Cmd err: {truncate_message(str(e), max_len=10)}"
        return False
    finally:
        in_flight = False


def http_request(path):
    """Minimal GET helper. Returns JSON or None."""
    global wled_connected, wifi_connected, status_message, last_error, last_errno, in_flight
    if in_flight:
        return None
    if not wifi_connected or not wlan or not wlan.isconnected():
        wifi_connected = False
        return None
    if not WLED_HOST:  # no IP configured
        return None
    in_flight = True
    try:
        url = f"http://{WLED_HOST}{path}"
        resp = rq.get(url)
        if resp.status_code == 200:
            try:
                raw_text = resp.text  # Lazily decoded
                resp.close()
                import json
                data = json.loads(raw_text)
                wled_connected = True
                return data
            except Exception as e:
                resp.close()
                wled_connected = False
                status_message = f"JSON parse: {truncate_message(str(e), max_len=10)}"
                return None
        resp.close()
        wled_connected = False
        status_message = f"HTTP {resp.status_code}"
    except OSError as e:  # Capture errno for network errors
        wled_connected = False
        last_error = str(e)
        last_error_lower = last_error.lower()
        try:
            last_errno = e.errno
        except Exception:
            last_errno = None
        if last_errno == 110 or ("etimedout" in last_error_lower) or ("etimeout" in last_error_lower) or ("timed out" in last_error_lower):
            status_message = "Timeout (WLED)"
        else:
            status_message = f"Err {truncate_message(last_error)}"
    except Exception as e:
        wled_connected = False
        last_error = str(e)
        last_errno = None
        status_message = f"Err {truncate_message(last_error)}"
    finally:
        in_flight = False
    return None


# --- Streaming JSON fetch to avoid full allocation issues ---
def fetch_wled_json(timeout=2, max_bytes=8192):
    """Stream /json manually to avoid urequests full-buffer allocation.
    Returns a dict or None. Extracts only the 'state' object for parsing.
    """
    global last_error, last_errno, wled_connected, status_message, in_flight
    if in_flight:
        return None
    if not wifi_connected or not WLED_HOST:
        return None
    in_flight = True
    s = None
    try:
        import socket
        s = socket.socket()
        s.settimeout(timeout)
        s.connect((WLED_HOST, 80))
        try:
            # Minimal GET
            req = b"GET /json HTTP/1.0\r\nHost: " + WLED_HOST.encode() + b"\r\nConnection: close\r\n\r\n"
            s.send(req)
            # Read headers first
            raw = b""
            header_end = -1
            while True:
                chunk = s.recv(256)
                if not chunk:
                    break
                raw += chunk
                header_end = raw.find(b"\r\n\r\n")
                if header_end != -1 or len(raw) > max_bytes:
                    break
            # If header_end remains -1 we treat entire raw buffer as body below; additional reads occur in body loop.
            body = raw[header_end+4:] if header_end != -1 else raw
            # Continue reading body
            while len(body) < max_bytes:
                try:
                    chunk = s.recv(512)
                except Exception:
                    break
                if not chunk:
                    break
                body += chunk
            wled_connected = True
            # Find '"state":' token and attempt to isolate braces
            state_idx = body.find(b'"state"')
            if state_idx == -1:
                # Try full JSON parse as fallback (may be big)
                import json
                try:
                    return json.loads(body.decode('utf-8', 'ignore'))
                except Exception as e:
                    last_error = str(e)
                    status_message = "JSON full fail"
                    return None
            brace_start = body.find(b'{', state_idx)
            if brace_start == -1:
                status_message = "No state brace"
                return None
            depth = 0
            end_pos = -1
            for i in range(brace_start, len(body)):
                b = body[i:i+1]
                if b == b'{':
                    depth += 1
                elif b == b'}':
                    depth -= 1
                    if depth == 0:
                        end_pos = i
                        break
            if end_pos == -1:
                status_message = "State brace unterminated"
                return None
            state_slice = body[brace_start:end_pos+1]
            import json
            try:
                state_obj = json.loads(state_slice.decode('utf-8','ignore'))
            except Exception as e:
                last_error = truncate_message(str(e), max_len=10)
                status_message = "State parse err"
                return None
            return {"state": state_obj}
        finally:
            try:
                if s:
                    s.close()
            except Exception:
                # Ignore errors during socket close; cleanup failures are non-critical
                pass
    except OSError as e:
        try:
            last_errno = e.errno
        except Exception:
            last_errno = None
        last_error = str(e)
        status_message = "Stream timeout" if last_errno == 110 else "Stream err"
    except Exception as e:
        last_error = str(e)
        status_message = "Stream fail"
    finally:
        in_flight = False
    return None


def get_wled_state():
    """Fetch state using streaming method first, fallback to standard request."""
    global wled_power, wled_color, wled_brightness, status_message, state_checked, in_flight, skip_wled
    global wled_effect_id, wled_effect_name
    if skip_wled:
        return False
    if in_flight:
        return False
    # Attempt streaming fetch to reduce memory pressure
    result = fetch_wled_json(timeout=2)
    if not result:
        # Fallback to regular request (may fail with parse error 110 previously)
        result = http_request("/json", timeout=2)
    if not result:
        return False
    try:
        # Combined result may return full json; state under key
        state_data = result.get("state") or result
        
        # Check if we got valid state data
        if "on" not in state_data and "bri" not in state_data:
            status_message = f"No state in response"
            return False
        
        wled_power = state_data.get("on", False)
        wled_brightness = state_data.get("bri", 0)
        wled_effect_id = None
        wled_effect_name = None
        
        # Get segment info
        seg = state_data.get("seg") or []
        if seg and isinstance(seg, list) and len(seg) > 0:
            first = seg[0] or {}
            
            # Check if using an effect (fx > 0 means effect is active)
            fx = first.get("fx", 0)

            # Note: WLED effect ID 0 is "Solid", which is technically an effect per the API.
            # This code intentionally treats only fx > 0 as effects, showing color info for fx == 0 ("Solid").
            if fx > 0:
                # Effect is active - don't show col, show effect info instead
                wled_color = None  # Signal effect mode
                wled_effect_id = fx
                # Lookup effect name from presets
                name = None
                try:
                    for _id, _name in effect_presets:
                        if _id == fx:
                            name = _name
                            break
                except Exception:
                    name = None
                if name:
                    wled_effect_name = name
                    status_message = name
                else:
                    status_message = f"Effect {fx}"
            else:
                # Solid color mode - extract color
                col = first.get("col") or []
                if col and isinstance(col, list) and len(col) > 0 and len(col[0]) >= 3:
                    c0 = col[0]
                    wled_color = (int(c0[0]), int(c0[1]), int(c0[2]))
                else:
                    wled_color = None
        else:
            wled_color = None
        
        if not wled_effect_name and "Effect" not in status_message:
            status_message = "State OK"
        state_checked = True
        gc.collect()
        return True
    except Exception as e:
        status_message = f"Parse: {truncate_message(str(e), max_len=10)}"
        return False


def center_text(text, y):
    w, _ = screen.measure_text(text)
    screen.text(text, 80 - (w / 2), y)


def draw_control_menu():
    """Draw control menu interface."""
    screen.font = small_font
    screen.brush = phosphor
    center_text("WLED Control", 5)
    
    screen.brush = gray
    screen.draw(shapes.rectangle(5, 16, 150, 1))
    
    menu_items = ["Power Toggle", "Set Color", "Set Effect", "Set Brightness", "Back"]
    start_y = 25
    
    for i, item in enumerate(menu_items):
        y = start_y + (i * 13)
        if i == control_selection:
            screen.brush = phosphor
            screen.text(">", 10, y)
        else:
            screen.brush = white
        screen.text(item, 20, y)
    
    screen.font = small_font
    screen.brush = gray
    screen.text("A: Select  UP/DOWN: Nav", 5, 110)


def draw_color_picker():
    """Draw color picker interface."""
    screen.font = small_font
    screen.brush = phosphor
    center_text("Choose Color", 5)
    
    screen.brush = gray
    screen.draw(shapes.rectangle(5, 16, 150, 1))
    
    # Show current color
    r, g, b, name = color_presets[color_index]
    screen.brush = white
    center_text(name, 30)
    
    # Color swatch
    sw = brushes.color(r, g, b)
    screen.brush = sw
    screen.draw(shapes.rectangle(50, 45, 60, 30))
    screen.brush = white
    screen.draw(shapes.rectangle(49, 44, 62, 1))
    screen.draw(shapes.rectangle(49, 75, 62, 1))
    screen.draw(shapes.rectangle(49, 44, 1, 32))
    screen.draw(shapes.rectangle(110, 44, 1, 32))
    
    screen.brush = gray
    center_text(f"RGB {r},{g},{b}", 85)
    center_text(f"{color_index + 1}/{len(color_presets)}", 95)
    
    screen.text("A: Apply  UP/DOWN: Nav", 5, 110)


def draw_effect_picker():
    """Draw effect picker interface."""
    screen.font = small_font
    screen.brush = phosphor
    center_text("Choose Effect", 5)
    
    screen.brush = gray
    screen.draw(shapes.rectangle(5, 16, 150, 1))
    
    # Show current effect
    fx_id, fx_name = effect_presets[effect_index]
    screen.brush = white
    center_text(fx_name, 40)
    
    screen.brush = gray
    center_text(f"Effect ID: {fx_id}", 60)
    center_text(f"{effect_index + 1}/{len(effect_presets)}", 75)
    
    screen.text("A: Apply  UP/DOWN: Nav", 5, 110)


def draw_brightness_picker():
    """Draw brightness picker interface."""
    screen.font = small_font
    screen.brush = phosphor
    center_text("Set Brightness", 5)
    
    screen.brush = gray
    screen.draw(shapes.rectangle(5, 16, 150, 1))
    
    # Show current brightness
    pct = int((brightness_value / 255) * 100)
    screen.brush = white
    center_text(f"{pct}%", 35)
    
    # Draw brightness bar
    bar_x = 30
    bar_y = 55
    bar_w = 100
    bar_h = 15
    
    # Background bar
    screen.brush = gray
    screen.draw(shapes.rectangle(bar_x, bar_y, bar_w, bar_h))
    
    # Filled portion based on brightness
    filled_w = int((brightness_value / 255) * bar_w)
    screen.brush = phosphor
    screen.draw(shapes.rectangle(bar_x, bar_y, filled_w, bar_h))
    
    # Border
    screen.brush = white
    screen.draw(shapes.rectangle(bar_x - 1, bar_y - 1, bar_w + 2, 1))
    screen.draw(shapes.rectangle(bar_x - 1, bar_y + bar_h, bar_w + 2, 1))
    screen.draw(shapes.rectangle(bar_x - 1, bar_y - 1, 1, bar_h + 2))
    screen.draw(shapes.rectangle(bar_x + bar_w, bar_y - 1, 1, bar_h + 2))
    
    screen.brush = gray
    center_text(f"Value: {brightness_value}/255", 85)
    
    screen.text("A: Apply  UP/DOWN: Adjust", 5, 110)


def draw_ui():
    screen.font = small_font
    screen.brush = phosphor
    center_text("WLED Status", 5)

    screen.brush = gray
    screen.draw(shapes.rectangle(5, 16, 150, 1))

    screen.brush = white
    center_text(status_message, 25)

    if not WIFI_SSID or not WIFI_PASSWORD:
        screen.brush = gray
        center_text("Missing WiFi creds", 50)
        return
    if not WLED_HOST:
        screen.brush = gray
        center_text("No WLED_IP set", 50)
        return

    if wifi_connected and state_checked and wled_connected:
        # Power / Effect / Color status
        screen.brush = green if wled_power else red
        center_text("ON" if wled_power else "OFF", 40)
        if wled_power:
            if wled_color:
                # Solid color mode
                screen.brush = white
                center_text(f"RGB {wled_color[0]},{wled_color[1]},{wled_color[2]}", 53)
                pct = int((wled_brightness / 255) * 100)
                center_text(f"Brightness {pct}%", 66)
                # Swatch
                sw = brushes.color(wled_color[0], wled_color[1], wled_color[2])
                screen.brush = sw
                screen.draw(shapes.rectangle(60, 79, 40, 15))
                screen.brush = white
                screen.draw(shapes.rectangle(59, 78, 42, 1))
                screen.draw(shapes.rectangle(59, 94, 42, 1))
                screen.draw(shapes.rectangle(59, 78, 1, 17))
                screen.draw(shapes.rectangle(100, 78, 1, 17))
            else:
                # Effect mode - show name only once (top line already shows status_message set to name)
                screen.brush = phosphor
                if wled_effect_name and wled_effect_name != status_message:
                    center_text(wled_effect_name, 53)
                elif not wled_effect_name and "Effect" in status_message:
                    center_text(status_message, 53)
                # Brightness line
                pct = int((wled_brightness / 255) * 100)
                screen.brush = white
                center_text(f"Brightness {pct}%", 66)
    else:
        # Show contextual waiting text
        screen.font = small_font
        screen.brush = gray
        if not wifi_connected:
            center_text(f"Connecting {WIFI_SSID or '?'}...", 50)
            if ticks_start:
                center_text(f"t={(io.ticks - ticks_start)//1000}s", 63)
        elif state_attempts >= MAX_FETCH_ATTEMPTS and not state_checked:
            center_text("WLED unreachable", 43)
            center_text(WLED_HOST or "", 56)
            if last_errno is not None:
                screen.brush = red
                center_text(f"errno {last_errno}", 69)
            screen.brush = gray
            center_text("Press B to retry", 82)
        else:
            if skip_wled:
                center_text("WLED skipped", 50)
            else:
                center_text("Fetching state...", 50)
                if WLED_HOST:
                    center_text(WLED_HOST, 63)

    # Footer hints
    screen.font = small_font
    screen.brush = gray
    if wifi_connected and wled_connected:
        screen.text("A: Control  B: Refresh", 5, 110)
    else:
        screen.text("B: Refresh  C: Skip", 5, 110)


def update():
    # Declare all globals we mutate to avoid UnboundLocalError
    global wifi_connected, state_checked, last_state_attempt, state_attempts, status_message
    global skip_wled, in_flight
    global control_mode, control_selection, color_picker_active, color_index
    global effect_picker_active, effect_index, wled_power, wled_color, wled_brightness
    global brightness_picker_active, brightness_value
    global ticks_start, WIFI_SSID, WIFI_PASSWORD, WLED_HOST

    # Clear background
    screen.brush = background
    screen.draw(shapes.rectangle(0, 0, 160, 120))

    # Step 1: Ensure config loaded (first frame only)
    if ticks_start is None and WIFI_SSID is None and WIFI_PASSWORD is None and WLED_HOST is None:
        load_config()

    # Step 2: WiFi connect (non-blocking)
    connect_wifi()

    # Handle different modes
    if color_picker_active:
        # Color picker mode
        if io.BUTTON_A in io.pressed:
            # Apply selected color
            r, g, b, name = color_presets[color_index]
            if send_wled_command({"on": True, "seg": [{"col": [[r, g, b]], "fx": 0}]}):
                wled_color = (r, g, b)
                wled_power = True
                state_checked = False  # Refresh state
            color_picker_active = False
            control_mode = True
        elif io.BUTTON_UP in io.pressed:
            color_index = (color_index - 1) % len(color_presets)
        elif io.BUTTON_DOWN in io.pressed:
            color_index = (color_index + 1) % len(color_presets)
        draw_color_picker()
        return
    
    if effect_picker_active:
        # Effect picker mode
        if io.BUTTON_A in io.pressed:
            # Apply selected effect
            fx_id, fx_name = effect_presets[effect_index]
            if send_wled_command({"on": True, "seg": [{"fx": fx_id}]}):
                wled_power = True
                state_checked = False  # Refresh state
            effect_picker_active = False
            control_mode = True
        elif io.BUTTON_UP in io.pressed:
            effect_index = (effect_index - 1) % len(effect_presets)
        elif io.BUTTON_DOWN in io.pressed:
            effect_index = (effect_index + 1) % len(effect_presets)
        draw_effect_picker()
        return
    
    if brightness_picker_active:
        # Brightness picker mode
        if io.BUTTON_A in io.pressed:
            # Apply brightness - use top-level 'bri' (segment 'bri' does not persist global brightness)
            if send_wled_command({"on": True, "bri": brightness_value}):
                wled_brightness = brightness_value
                wled_power = True
                state_checked = False  # Refresh state
            brightness_picker_active = False
            control_mode = True
        elif io.BUTTON_UP in io.pressed:
            # Increase brightness by 15 (about 6%)
            brightness_value = min(255, brightness_value + 15)
        elif io.BUTTON_DOWN in io.pressed:
            # Decrease brightness by 15 (about 6%)
            brightness_value = max(1, brightness_value - 15)
        draw_brightness_picker()
        return
    
    if control_mode:
        # Control menu mode
        if io.BUTTON_A in io.pressed:
            if control_selection == 0:
                # Toggle power
                new_power = not wled_power
                if send_wled_command({"on": new_power}):
                    wled_power = new_power
                    state_checked = False  # Refresh state
            elif control_selection == 1:
                # Enter color picker
                color_picker_active = True
                control_mode = False
            elif control_selection == 2:
                # Enter effect picker
                effect_picker_active = True
                control_mode = False
            elif control_selection == 3:
                # Enter brightness picker
                brightness_value = wled_brightness if wled_brightness > 0 else 128
                brightness_picker_active = True
                control_mode = False
            elif control_selection == 4:
                # Back to status view
                control_mode = False
                state_checked = False  # Refresh state
                state_attempts = 0
        elif io.BUTTON_UP in io.pressed:
            control_selection = (control_selection - 1) % 5
        elif io.BUTTON_DOWN in io.pressed:
            control_selection = (control_selection + 1) % 5
        draw_control_menu()
        return
    
    # Status view mode
    # Step 3: Attempt WLED state fetch with throttling
    now = io.ticks
    if (not state_checked and state_attempts < MAX_FETCH_ATTEMPTS and wifi_connected and WLED_HOST and not skip_wled):
        if now - last_state_attempt > FETCH_RETRY_INTERVAL:
            last_state_attempt = now
            state_attempts += 1
            get_wled_state()
            # If failed, status_message already updated; we leave state_checked False

    # Button A: Enter control mode
    if io.BUTTON_A in io.pressed and wifi_connected and wled_connected:
        control_mode = True
        control_selection = 0

    # Manual refresh (Button B)
    if io.BUTTON_B in io.pressed:
        # Reset fetch cycle
        state_checked = False
        state_attempts = 0
        last_state_attempt = 0
        skip_wled = False
        status_message = "Refreshing..."
        if wifi_connected and WLED_HOST:
            # Immediate attempt (do not wait for interval)
            get_wled_state()

    # Button C: Skip WLED queries entirely
    if io.BUTTON_C in io.pressed:
        skip_wled = True
        status_message = "WLED skipped"

    # Draw UI last
    draw_ui()


def init():
    """Load persisted UI selection and control values."""
    global color_index, effect_index, brightness_value, control_selection
    state = {
        "color_index": color_index,
        "effect_index": effect_index,
        "brightness_value": brightness_value,
        "control_selection": control_selection,
    }
    if State.load("wled", state):
        color_index = state.get("color_index", color_index)
        effect_index = state.get("effect_index", effect_index)
        brightness_value = state.get("brightness_value", brightness_value)
        control_selection = state.get("control_selection", control_selection)
    del state


def on_exit():
    """Persist relevant UI/control selections for next launch."""
    State.save("wled", {
        "color_index": color_index,
        "effect_index": effect_index,
        "brightness_value": brightness_value,
        "control_selection": control_selection,
    })


if __name__ == "__main__":
    run(update, init=init, on_exit=on_exit)