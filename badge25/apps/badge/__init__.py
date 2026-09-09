import sys
import os

sys.path.insert(0, "/system/apps/badge")
os.chdir("/system/apps/badge")


from badgeware import io, brushes, shapes, Image, run, PixelFont, screen, Matrix, file_exists
import random
import math
import network
from urllib.urequest import urlopen
import gc
import sys
import json


phosphor = brushes.color(211, 250, 55, 150)
white = brushes.color(235, 245, 255)
faded = brushes.color(235, 245, 255, 100)
small_font = PixelFont.load("/system/assets/fonts/ark.ppf")
large_font = PixelFont.load("/system/assets/fonts/absolute.ppf")

WIFI_TIMEOUT = 60
CONTRIB_URL = "https://github.com/{user}.contribs"
USER_AVATAR = "https://wsrv.nl/?url=https://github.com/{user}.png&w=75&output=png"
DETAILS_URL = "https://api.github.com/users/{user}"

WIFI_PASSWORD = None
WIFI_SSID = None
GITHUB_TOKEN = None

wlan = None
connected = False
ticks_start = None


def message(text):
    print(text)


def get_connection_details(user):
    global WIFI_PASSWORD, WIFI_SSID, GITHUB_TOKEN, GITHUB_USERNAME

    if WIFI_SSID is not None and user.handle is not None:
        return True

    try:
        # Prefer a local 'secrets.py' placed at the badge repository root ("/badge/secrets.py")
        # Insert '/' (root of the badge filesystem) at the front of sys.path so a local
        # `secrets.py` can be imported on the device. Clean up sys.path afterwards.
        sys.path.insert(0, "/")
        try:
            from secrets import WIFI_PASSWORD, WIFI_SSID, GITHUB_USERNAME, GITHUB_TOKEN
        finally:
            # ensure we remove the path we inserted even if import fails
            try:
                sys.path.pop(0)
            except Exception:
                pass
    except ImportError as e:
        # If the user hasn't created a secrets.py file, fall back to None so
        # the rest of the app can detect missing credentials and show helpful UI.
        WIFI_PASSWORD = None
        WIFI_SSID = None
        GITHUB_USERNAME = None
        GITHUB_TOKEN = None
    except Exception as e:
        WIFI_PASSWORD = None
        WIFI_SSID = None
        GITHUB_USERNAME = None
        GITHUB_TOKEN = None

    if not WIFI_SSID:
        return False

    if not GITHUB_USERNAME:
        return False

    user.handle = GITHUB_USERNAME

    return True


def wlan_start():
    global wlan, ticks_start, connected, WIFI_PASSWORD, WIFI_SSID

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
            print("WiFi connected!")
            return True
    elif not connected:
        return False
    
    return True

def async_fetch_to_disk(url, file, force_update=False, timeout_ms=25000):
    """
    Fetch a URL to disk as a generator, yielding between chunks so callers
    can interleave UI updates. If timeout_ms is provided, abort the fetch
    after that many milliseconds have elapsed (based on io.ticks).
    """
    if not force_update and file_exists(file):
        return

    start_ticks = io.ticks
    try:
        # Prepare headers with authentication if token is available
        headers = {"User-Agent": "GitHub Universe Badge 2025"}
        if GITHUB_TOKEN and url.startswith("https://api.github.com"):
            headers["Authorization"] = f"token {GITHUB_TOKEN}"

        # Grab the data
        response = urlopen(url, headers=headers)
        data = bytearray(512)
        total = 0
        with open(file, "wb") as f:
            while True:
                # enforce timeout if requested
                if timeout_ms is not None and (io.ticks - start_ticks) > timeout_ms:
                    raise TimeoutError(f"Fetch timed out after {timeout_ms} ms")

                if (length := response.readinto(data)) == 0:
                    break
                total += length
                message(f"Fetched {total} bytes")
                f.write(data[:length])
                yield
        del data
        del response
    except Exception as e:
        # Clean up a partial file if present
        try:
            if file_exists(file):
                os.remove(file)
        except Exception:
            pass
        # Wrap timeout specifically so callers can react differently if needed
        if isinstance(e, TimeoutError):
            raise
        raise RuntimeError(f"Fetch from {url} to {file} failed. {e}") from e


def get_user_data(user, force_update=False):
    message(f"Getting user data for {user.handle}...")
    try:
        yield from async_fetch_to_disk(DETAILS_URL.format(user=user.handle), "/user_data.json", force_update)
    except Exception as e:
        # Check if it's a rate limit error
        error_msg = str(e).lower()
        if "403" in error_msg or "rate limit" in error_msg:
            message("Rate limit exceeded")
            user.name = "Rate Limited"
            user.handle = user.handle or "Unknown"
            user.followers = 0
            user.repos = 0
            return
        else:
            message(f"Failed to get user data: {e}")
            user.name = "Fetch Error"
            user.handle = user.handle or "Unknown"
            user.followers = 0
            user.repos = 0
            return
    
    try:
        r = json.loads(open("/user_data.json", "r").read())
        user.name = r.get("name", user.handle) # Fallback to handle if user does not have a name
        user.handle = r.get("login", "Unknown Handle")
        user.followers = r.get("followers", 0)
        user.repos = r.get("public_repos", 0)
        del r
        gc.collect()
    except Exception as e:
        message(f"Failed to parse user data: {e}")
        user.name = "Parse Error"
        user.followers = 0
        user.repos = 0


def get_contrib_data(user, force_update=False):
    message(f"Getting contribution data for {user.handle}...")
    # Attempt the network fetch, but handle any network errors so the UI
    # doesn't get stuck if the endpoint is unreachable or returns invalid data.
    try:
        # 15 second timeout for contribution fetch to avoid blocking forever
        yield from async_fetch_to_disk(CONTRIB_URL.format(user=user.handle), "/contrib_data.json", force_update, timeout_ms=15000)
    except TimeoutError as e:
        message(f"Contrib fetch timed out: {e}")
        user.contribs = 0
        user.contribution_data = [[0 for _ in range(53)] for _ in range(7)]
        return
    except Exception as e:
        message(f"Failed to fetch contrib data: {e}")
        # Provide safe defaults so the rest of the UI can continue.
        user.contribs = 0
        user.contribution_data = [[0 for _ in range(53)] for _ in range(7)]
        return

    try:
        r = json.loads(open("/contrib_data.json", "r").read())
    except Exception as e:
        message(f"Failed to parse contrib JSON: {e}")
        user.contribs = 0
        user.contribution_data = [[0 for _ in range(53)] for _ in range(7)]
        return

    # Safely extract expected fields from the JSON, using defaults if missing.
    total = r.get("total_contributions")
    weeks = r.get("weeks") or []

    # Build an empty 7x53 grid and only populate up to available weeks
    max_weeks = min(len(weeks), 53)
    user.contribution_data = [[0 for _ in range(53)] for _ in range(7)]

    # Populate grid and compute total if missing or zero
    computed_total = 0
    for w in range(max_weeks):
        week = weeks[w] or {}
        days = week.get("contribution_days") or []
        for d in range(min(len(days), 7)):
            day = days[d] or {}
            # contribution level (for color) and count (for totals)
            level = day.get("level", 0)
            count = day.get("count", 0)
            # ensure level is a valid index into User.levels
            try:
                lvl_index = int(level)
                if lvl_index < 0 or lvl_index >= len(User.levels):
                    lvl_index = 0
            except Exception:
                lvl_index = 0
            user.contribution_data[d][w] = lvl_index
            computed_total += int(count)

    if total is None or total == 0:
        user.contribs = computed_total
    else:
        user.contribs = int(total)
    del r
    gc.collect()


def get_avatar(user, force_update=False):
    message(f"Getting avatar for {user.handle}...")
    avatar_path = "/avatar.png"
    try:
        yield from async_fetch_to_disk(USER_AVATAR.format(user=user.handle), avatar_path, force_update)
        # Verify file exists before loading
        if file_exists(avatar_path):
            user.avatar = Image.load(avatar_path)
        else:
            message("Avatar file not found after download")
            user.avatar = False
    except Exception as e:
        message(f"Failed to get avatar: {e}")
        # Set avatar to False (instead of None) to indicate fetch attempted but failed
        # This prevents infinite retry while allowing the default avatar to be drawn
        user.avatar = False


def fake_number():
    return random.randint(10000, 99999)


def placeholder_if_none(text):
    if text:
        return text
    old_seed = random.seed()
    random.seed(int(io.ticks / 100))
    chars = "!\"£$%^&*()_+-={}[]:@~;'#<>?,./\\|"
    text = ""
    for _ in range(20):
        text += random.choice(chars)
    random.seed(old_seed)
    return text


class User:
    levels = [
        brushes.color(21 / 2,  27 / 2,  35 / 2),
        brushes.color(3 / 2,  58 / 2,  22 / 2),
        brushes.color(25 / 2, 108 / 2,  46 / 2),
        brushes.color(46 / 2, 160 / 2,  67 / 2),
        brushes.color(86 / 2, 211 / 2, 100 / 2),
    ]

    def __init__(self):
        self.handle = None
        self.update()

    def update(self, force_update=False):
        self.name = None
        self.followers = None
        self.contribs = None
        self.contribution_data = None
        self.repos = None
        self.avatar = None
        self._task = None
        self._force_update = force_update

    def draw_stat(self, title, value, x, y):
        # value may be 0; treat None as missing
        screen.brush = white if value is not None else faded
        screen.font = large_font
        screen.text(str(value) if value is not None else str(fake_number()), x, y)
        screen.font = small_font
        screen.brush = phosphor
        screen.text(title, x - 1, y + 13)

    def draw(self, connected):
        # draw contribution graph background
        size = 15
        graph_width = 53 * (size + 2)
        xo = int(-math.sin(io.ticks / 5000) *
                 ((graph_width - 160) / 2)) + ((graph_width - 160) / 2)

        screen.font = small_font
        rect = shapes.rounded_rectangle(0, 0, size, size, 2)
        for y in range(7):
            for x in range(53):
                if self.contribution_data:
                    level = self.contribution_data[y][x]
                    screen.brush = User.levels[level]
                else:
                    screen.brush = User.levels[1]
                pos = (x * (size + 2) - xo, y * (size + 2) + 1)
                if pos[0] + size < 0 or pos[0] > 160:
                    # skip tiles that aren't in view
                    continue
                rect.transform = Matrix().translate(*pos)
                screen.draw(rect)

        # draw handle
        screen.font = large_font
        handle = self.handle

        # use the handle area to show loading progress if not everything is ready
        # Use explicit None checks so legitimate zero values (e.g. 0 contribs)
        # don't prevent later tasks (like fetching an avatar) from running.
        # avatar can be None (not fetched), False (fetch failed), or an Image object
        if ((self.handle is None) or (self.avatar is None) or (self.contribs is None)) and connected:
            if not self.name:
                handle = "fetching user data..."
                if not self._task:
                    self._task = get_user_data(self, self._force_update)
            elif self.contribs is None:
                handle = "fetching contribs..."
                if not self._task:
                    self._task = get_contrib_data(self, self._force_update)
            else:
                handle = "fetching avatar..."
                if not self._task:
                    self._task = get_avatar(self, self._force_update)

            try:
                next(self._task)
            except StopIteration:
                self._task = None
            except:
                self._task = None
                handle = "fetch error"

        if not connected:
            handle = "connecting..."

        w, _ = screen.measure_text(handle)
        screen.brush = white
        screen.text(handle, 80 - (w / 2), 2)

        # draw name
        screen.font = small_font
        screen.brush = phosphor
        name = placeholder_if_none(self.name)
        w, _ = screen.measure_text(name)
        screen.text(name, 80 - (w / 2), 16)

        # draw statistics
        self.draw_stat("followers", self.followers, 88, 33)
        self.draw_stat("contribs", self.contribs, 88, 62)
        self.draw_stat("repos", self.repos, 88, 91)

        # draw avatar imagee
        if not self.avatar:
            drawDefaultAvatar()
        else:
            try:
                screen.blit(self.avatar, 5, 37)
            except Exception as e:
                drawDefaultAvatar()

def drawDefaultAvatar():
    # create a spinning loading animation while we wait for the avatar to load
    screen.brush = phosphor
    squircle = shapes.squircle(0, 0, 10, 5)
    screen.brush = brushes.color(211, 250, 55, 50)
    for i in range(4):
        mul = math.sin(io.ticks / 1000) * 14000
        squircle.transform = Matrix().translate(42, 75).rotate(
            (io.ticks + i * mul) / 40).scale(1 + i / 1.3)
        screen.draw(squircle)

user = User()
connected = file_exists("/contrib_data.json") and file_exists("/user_data.json") and file_exists("/avatar.png")
force_update = False


def center_text(text, y):
  w, h = screen.measure_text(text)
  screen.text(text, 80 - (w / 2), y)


def wrap_text(text, x, y):
  lines = text.splitlines()
  for line in lines:
    _, h = screen.measure_text(line)
    screen.text(line, x, y)
    y += h * 0.8


# tell the user where to fill in their details
def no_secrets_error():
  screen.font = large_font
  screen.brush = white
  center_text("Missing Details!", 5)

  screen.text("1:", 10, 23)
  screen.text("2:", 10, 55)
  screen.text("3:", 10, 87)

  screen.brush = phosphor
  screen.font = small_font
  wrap_text("""Put your badge into\ndisk mode (tap\nRESET twice)""", 30, 24)

  wrap_text("""Edit 'secrets.py' to\nset WiFi details and\nGitHub username.""", 30, 56)

  wrap_text("""Reload to see your\nsweet sweet stats!""", 30, 88)


# tell the user that the connection failed :-(
def connection_error():
  screen.font = large_font
  screen.brush = white
  center_text("Connection Failed!", 5)

  screen.text("1:", 10, 63)
  screen.text("2:", 10, 95)

  screen.brush = phosphor
  screen.font = small_font
  wrap_text("""Could not connect\nto the WiFi network.\n\n:-(""", 16, 20)

  wrap_text("""Edit 'secrets.py' to\nset WiFi details and\nGitHub username.""", 30, 65)

  wrap_text("""Reload to see your\nsweet sweet stats!""", 30, 96)


def update():
    global connected, force_update

    screen.brush = brushes.color(0, 0, 0)
    screen.draw(shapes.rectangle(0, 0, 160, 120))

    force_update = False

    if io.BUTTON_A in io.held and io.BUTTON_C in io.held:
        connected = False
        user.update(True)

    if get_connection_details(user):
        if wlan_start():
            user.draw(connected)
        else:  # Connection Failed
            connection_error()
    else:      # Get Details Failed
        no_secrets_error()


if __name__ == "__main__":
    run(update)
