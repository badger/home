import os
import gc
import json
import math
import random

import fetch
import machine
import missing_details
import wifi
from badgeware import link as badgelink

try:
    import secrets
except ImportError:
    secrets = None

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

phosphor = color.rgb(211, 250, 55, 150)
white = color.rgb(235, 245, 255)
faded = color.rgb(235, 245, 255, 100)
spinner = color.rgb(211, 250, 55, 50)
black = color.rgb(0, 0, 0)

mona_sans = missing_details.mona_sans()

HANDLE_SIZE = 28
NAME_SIZE = 16
VALUE_SIZE = 28
LABEL_SIZE = 14
NUDGE_SIZE = 17
NUDGE_RECT = (176, 70, 136, 150)

CONTRIB_URL = "https://github.com/{user}.contribs"
# The refresh query busts both the proxy cache and its upstream GitHub image request.
USER_AVATAR = "https://wsrv.nl/?url=https://github.com/{user}.png%3Fbadge_refresh%3D{refresh}&w=150&output=png"
DETAILS_URL = "https://api.github.com/users/{user}"

CACHE_DIR = "/state"
USER_FILE = f"{CACHE_DIR}/badge_user.json"
CONTRIB_FILE = f"{CACHE_DIR}/badge_contribs.json"
AVATAR_FILE = f"{CACHE_DIR}/badge_avatar.png"

HEADERS = {"User-Agent": "GitHub Universe Badge 2026"}
TOKEN = str(getattr(secrets, "GITHUB_TOKEN", "") or "").strip()


def headers_for(url):
    if TOKEN and url.startswith("https://api.github.com/"):
        headers = dict(HEADERS)
        headers["Authorization"] = "Bearer " + TOKEN
        return headers
    return HEADERS

RETRY_MS = 30000

fetch.AsyncFetch.MAX_HEADER_BYTES = 8192

GRAPH_WEEKS = 53
GRAPH_DAYS = 7
TILE_SIZE = 33
TILE_STEP = 37
GRAPH_TOP = (240 - GRAPH_DAYS * TILE_STEP) // 2
PARALLAX_SHIFT = 8
AVATAR_SIZE = 150
PROFILE_AVATAR = 96

STATS_VIEW = 0
NAME_VIEW = 1
PROFILE_VIEW = 2
VIEW_COUNT = 3

TITLE_SIZE = 72
LINE_GAP = 4

try:
    os.mkdir(CACHE_DIR)
except OSError:
    pass


class Tilt:
    GRAVITY = 16384.0
    SMOOTH_MS = 120
    RECENTRE_MS = 2800

    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.rest_z = None
        self.last_ticks = None

    def update(self):
        ax, _, az = badge.imu()[:3]
        now = badge.ticks
        dt = min(now - self.last_ticks, 200) if self.last_ticks is not None else 0
        self.last_ticks = now
        smooth = 1 - math.exp(-dt / self.SMOOTH_MS)
        recentre = 1 - math.exp(-dt / self.RECENTRE_MS)
        if self.rest_z is None:
            self.rest_z = az
        self.rest_z += (az - self.rest_z) * recentre
        target_x = max(-1.0, min(1.0, -ax / self.GRAVITY * 2))
        target_y = max(-1.0, min(1.0, (az - self.rest_z) / self.GRAVITY * 2))
        self.x += (target_x - self.x) * smooth
        self.y += (target_y - self.y) * smooth


tilt = Tilt()


def fake_number():
    return random.randint(10000, 99999)


def placeholder_if_none(text):
    if text:
        return text
    random.seed(badge.ticks // 100)
    chars = "!\"£$%^&*()_+-={}[]:@~;'#<>?,./\\|"
    return "".join(random.choice(chars) for _ in range(20))


class Download:
    def __init__(self, url, file, force_update):
        self.file = file
        self.temp_file = file + ".tmp"
        self.request = None
        if force_update or not file_exists(file):
            self.request = fetch.url(url, headers=headers_for(url)).to(self.temp_file)

    def ready(self):
        if self.request is None:
            return True
        if self.request:
            os.rename(self.temp_file, self.file)
            self.request = None
            return True
        return False

    @property
    def state(self):
        if self.request is None:
            return None
        return self.request.state

    @property
    def error(self):
        if self.request is None:
            return None
        return self.request.error


class User:
    levels = [
        color.rgb(10, 13, 17),
        color.rgb(1, 29, 11),
        color.rgb(12, 54, 23),
        color.rgb(23, 80, 33),
        color.rgb(43, 105, 50),
    ]

    SPIN_MS = 1000
    SPIN_TURNS = 2
    AVATAR_ACTIONS = ("flip", "clockwise", "pulse")
    ROTATE_MS = 1200
    PULSE_MS = 1800
    STATS = (("Followers", "followers"), ("Contribs", "contribs"),
             ("Repos", "repos"), ("Best Day", "best_day"), ("Yrs on GH", "years"))
    VISIBLE_STATS = 3

    def __init__(self, handle):
        self.handle = handle
        self.stats_offset = 0
        self.spin_start = None
        self.avatar_action = "flip"
        self.tile = shape.rounded_rectangle(0, 0, TILE_SIZE, TILE_SIZE, 4)
        self.update()

    def update(self, force_update=False):
        self.name = None
        self.followers = None
        self.contribs = None
        self.contribution_data = None
        self.repos = None
        self.created_at = None
        self.company = None
        self.best_day = None
        self.years = None
        self.avatar = None
        self._download = None
        self._force_update = force_update
        self._error = None
        self._retry_at = 0
        self.missing = []

    def load_user_data(self):
        with open(USER_FILE, "r") as f:
            data = json.load(f)
        if data["login"].lower() != self.handle.lower():
            self.update(True)
            return
        self.name = data["name"] or data["login"]
        self.handle = data["login"]
        self.followers = data["followers"]
        self.repos = data["public_repos"]
        self.created_at = data.get("created_at")
        self.company = data.get("company")
        del data
        gc.collect()

    def load_contrib_data(self):
        with open(CONTRIB_FILE, "r") as f:
            data = json.load(f)
        self.contribs = data["total_contributions"]
        self.contribution_data = [[0 for _ in range(GRAPH_WEEKS)] for _ in range(GRAPH_DAYS)]
        best_day = 0
        for week_index, week in enumerate(data["weeks"][:GRAPH_WEEKS]):
            for day, contribution in enumerate(week["contribution_days"][:GRAPH_DAYS]):
                self.contribution_data[day][week_index] = contribution["level"]
                best_day = max(best_day, int(contribution.get("count", 0)))
        self.best_day = best_day
        # Use the downloaded history's end date; the badge clock may be unset.
        try:
            self.years = account_years(self.created_at, data.get("to"))
        except (TypeError, ValueError) as e:
            print(f"Badge: could not calculate years on GitHub: {e}")
        del data
        gc.collect()

    def load_avatar(self):
        self.avatar = image.load(AVATAR_FILE)

    def next_download(self):
        if self.name is None:
            return "fetching user data...", DETAILS_URL, USER_FILE, self.load_user_data
        if self.contribs is None:
            return "fetching contribs...", CONTRIB_URL, CONTRIB_FILE, self.load_contrib_data
        if self.avatar is None:
            return "fetching avatar...", USER_AVATAR, AVATAR_FILE, self.load_avatar
        return None

    def fail(self, error):
        print(f"Badge: {error}")
        self._error = error
        self._retry_at = badge.ticks + RETRY_MS
        self._download = None

    def fetch_step(self):
        if self._error:
            if badge.ticks < self._retry_at:
                return "fetch failed, retrying..."
            self._error = None

        pending = self.next_download()
        if pending is None:
            return None

        label, url, file, load = pending

        if self._download is None or self._download.file != file:
            if self._force_update or not file_exists(file):
                self.missing = missing_details.missing("WIFI_SSID")
                if self.missing:
                    return label
            url = url.format(user=self.handle, refresh=random.getrandbits(32))
            self._download = Download(url, file, self._force_update)

        if self._download.ready():
            self._download = None
            try:
                load()
            except (OSError, ValueError, KeyError) as e:
                os.remove(file)
                self.fail(e)
            return label

        if self._download.error:
            self.fail(self._download.error)
            return label

        return self._download.state if self._download.state not in ("Idle", "Fetching") else label

    @property
    def loaded(self):
        return self.name is not None

    @property
    def failed(self):
        return self._error is not None

    def draw_stat(self, title, value, x, y):
        screen.font = mona_sans
        screen.pen = white if value else faded
        if value is not None:
            text = str(value)
        elif self.failed:
            text = "-"
        else:
            text = str(fake_number())
        screen.text(text, x, y, VALUE_SIZE)
        screen.pen = phosphor
        screen.text(title, x, y + VALUE_SIZE + 2, LABEL_SIZE)

    def draw_graph(self):
        graph_width = GRAPH_WEEKS * TILE_STEP
        travel = (graph_width - screen.width) / 2
        offset_x = int(-math.sin(badge.ticks / 5000) * travel + travel + tilt.x * PARALLAX_SHIFT)
        offset_y = GRAPH_TOP - int(tilt.y * PARALLAX_SHIFT)

        for y in range(GRAPH_DAYS):
            for x in range(GRAPH_WEEKS):
                pos_x = x * TILE_STEP - offset_x
                if pos_x + TILE_SIZE < 0 or pos_x > screen.width:
                    continue
                level = self.contribution_data[y][x] if self.contribution_data else 1
                screen.pen = User.levels[level]
                self.tile.transform = mat3().translate(pos_x, y * TILE_STEP + offset_y)
                screen.shape(self.tile)

    def animate_avatar(self):
        self.avatar_action = random.choice(User.AVATAR_ACTIONS)
        self.spin_start = badge.ticks

    def avatar_progress(self):
        if self.spin_start is None:
            return 1
        duration = (User.ROTATE_MS if self.avatar_action == "clockwise" else
                    User.PULSE_MS if self.avatar_action == "pulse" else User.SPIN_MS)
        progress = (badge.ticks - self.spin_start) / duration
        if progress >= 1:
            self.spin_start = None
            return 1
        return progress

    def avatar_spin_scale(self, progress):
        # Horizontal scale for a coin-flip spin, matching the menu icon effect.
        eased = 1 - (1 - progress) ** 2
        return math.cos(eased * User.SPIN_TURNS * 2 * math.pi)

    def draw_avatar(self, x, y, size):
        if not self.avatar:
            self.draw_spinner(x + size / 2, y + size / 2, size / AVATAR_SIZE)
            return

        progress = self.avatar_progress()
        if self.avatar_action == "clockwise" and progress < 1:
            self.draw_rotated_avatar(x, y, size, progress * 360)
            return
        width = height = size
        if progress < 1:
            if self.avatar_action == "pulse":
                width = height = size * (0.6 + 0.4 * math.cos(progress * 6 * math.pi))
            else:
                width = size * abs(self.avatar_spin_scale(progress))
        if width >= 1:
            screen.blit(self.avatar, rect(x + (size - width) / 2, y + (size - height) / 2, width, height))

    def draw_rotated_avatar(self, x, y, size, angle):
        # Shrink while turning so the rotated square stays inside the avatar area.
        radians = math.radians(angle)
        scale = size / self.avatar.width / (abs(math.cos(radians)) + abs(math.sin(radians)))
        half = self.avatar.width / 2
        outline = shape.rectangle(0, 0, self.avatar.width, self.avatar.height)
        outline.transform = mat3().translate(x + size / 2, y + size / 2).rotate(angle).scale(scale, scale).translate(-half, -half)
        screen.pen = brush.image(self.avatar, mat3())
        screen.shape(outline)

    def draw_spinner(self, cx, cy, scale):
        squircle = shape.squircle(0, 0, 20, 5)
        screen.pen = spinner
        for i in range(4):
            mul = math.sin(badge.ticks / 1000) * 14000
            squircle.transform = mat3().translate(cx, cy).rotate((badge.ticks + i * mul) / 40).scale((1 + i / 1.3) * scale)
            screen.shape(squircle)

    def display_handle(self):
        return "@" + self.handle if self.handle else ""

    def display_company(self):
        return (self.company or "").strip()

    def draw(self, status, view=STATS_VIEW):
        self.draw_graph()
        screen.font = mona_sans
        if view == NAME_VIEW:
            self.draw_name_view(status)
        elif view == PROFILE_VIEW:
            self.draw_profile_view(status)
        else:
            self.draw_stats_view(status)

    def draw_stats_view(self, status):
        screen.pen = white
        center_text(status or self.display_handle(), 4, HANDLE_SIZE)

        screen.pen = phosphor
        center_text(placeholder_if_none(self.name), 36, NAME_SIZE)

        for row, (title, field) in enumerate(self.STATS[self.stats_offset:self.stats_offset + self.VISIBLE_STATS]):
            self.draw_stat(title, getattr(self, field), 176, 66 + row * 58)

        screen.pen = phosphor
        if self.stats_offset > 0:
            screen.text("^", screen.width - 12, 56, LABEL_SIZE)
        if self.stats_offset + self.VISIBLE_STATS < len(self.STATS):
            screen.text("v", screen.width - 12, screen.height - 18, LABEL_SIZE)

        self.draw_avatar(10, 74, AVATAR_SIZE)

    def scroll_stats(self, direction):
        self.stats_offset = max(0, min(len(self.STATS) - self.VISIBLE_STATS,
                                       self.stats_offset + direction))

    def draw_name_view(self, status):
        # The username fills the width, with the full name below it.
        lines = [(self.display_handle(), TITLE_SIZE, white),
                 (placeholder_if_none(self.name), HANDLE_SIZE, phosphor)]
        top = 32 if status else 0
        draw_lines(lines, None, top + (screen.height - top) / 2, screen.width - 8)
        if status:
            screen.pen = white
            center_text(status, 4, NAME_SIZE)

    def draw_profile_view(self, status):
        # Name and company sit beside the avatar; the username fills the space below.
        self.draw_avatar(8, 8, PROFILE_AVATAR)
        lines = [(placeholder_if_none(self.name), HANDLE_SIZE, phosphor)]
        company = self.display_company()
        if company:
            lines.append((company, NAME_SIZE, faded))
        left = 8 + PROFILE_AVATAR + 10
        draw_lines(lines, left, 56, screen.width - left - 6)
        draw_lines([(self.display_handle(), TITLE_SIZE, white)], None, 152, screen.width - 8)
        if status:
            screen.pen = white
            center_text(status, 208, NAME_SIZE)


def account_years(created_at, as_of):
    created = tuple(int(part) for part in created_at[:10].split("-"))
    current = tuple(int(part) for part in as_of[:10].split("-"))
    if len(created) != 3 or len(current) != 3 or current < created:
        raise ValueError("Invalid account or contribution date")
    return current[0] - created[0] - (current[1:] < created[1:])


def fit_text(text, max_width, size):
    """Shrink the text size until it fits max_width; return the size and width."""
    w, _ = screen.measure_text(text, font_size=size)
    if w > max_width:
        size = size * max_width / w
        w = max_width
    return size, w


def draw_lines(lines, x, centre_y, max_width):
    """Draw (text, size, pen) lines as a block centred on centre_y.

    Lines are centred horizontally when x is None, otherwise left-aligned at x.
    """
    fitted = [(text,) + fit_text(text, max_width, size) + (pen,) for text, size, pen in lines]
    y = centre_y - (sum(line[1] for line in fitted) + LINE_GAP * (len(fitted) - 1)) / 2
    for text, size, w, pen in fitted:
        screen.pen = pen
        screen.text(text, screen.width / 2 - w / 2 if x is None else x, y, size)
        y += size + LINE_GAP


def center_text(text, y, size):
    w, _ = screen.measure_text(text, font_size=size)
    if w > screen.width - 16:
        size = size * (screen.width - 16) / w
        w = screen.width - 16
    screen.text(text, screen.width / 2 - w / 2, y, size)


def setting(key):
    return str(getattr(secrets, key, "") or "").strip()


def linkedin_label(url):
    if not url:
        return ""
    path = url.split("://")[-1]
    if path.startswith("www."):
        path = path[4:]
    return path.rstrip("/")


handle = setting("GITHUB_USERNAME")
contact_name = setting("CONTACT_NAME")
linkedin = linkedin_label(setting("CONTACT_LINKEDIN"))
user = User(handle)
view = STATS_VIEW
badge_id = bytes(machine.unique_id())[:badgelink.ID_LEN]


def draw_simple(status):
    user.draw_graph()
    screen.font = mona_sans
    screen.pen = white
    center_text(contact_name or handle or linkedin, 4, HANDLE_SIZE)
    details = []
    if handle and contact_name:
        details.append("@" + handle)
    if linkedin and (contact_name or handle):
        details.append(linkedin)
    screen.pen = phosphor
    for index, line in enumerate(details):
        center_text(line, 36 + index * 18, NAME_SIZE)
    badgelink.draw_identicon(screen, badge_id, 10, 74, AVATAR_SIZE)

    if not handle:
        nudge = "Add your GitHub username in Settings or visit Hack Your Badge to show your stats"
    elif user.failed and wifi.failure():
        nudge = "Couldn't connect to WiFi. Visit the Hack Your Badge station to get your GitHub stats"
    elif user.missing or user.failed:
        nudge = "Visit the Hack Your Badge station to get your GitHub stats"
    else:
        nudge = status or "connecting to GitHub..."
    screen.pen = white
    screen.text(nudge, rect(*NUDGE_RECT), NUDGE_SIZE, align=(LEFT, TOP))


def update():
    global view
    tilt.update()

    screen.pen = black
    screen.clear()

    if not handle and not contact_name and not linkedin:
        missing_details.show([], user.draw_graph, ("your name, GitHub username,", "and LinkedIn stub"))
        return

    both_held = badge.held(BUTTON_LEFT) and badge.held(BUTTON_RIGHT)
    if handle and both_held and (badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_RIGHT)):
        user.update(True)

    status = user.fetch_step() if handle else None
    if user.loaded:
        if not both_held:
            if badge.pressed(BUTTON_LEFT):
                view = (view - 1) % VIEW_COUNT
            if badge.pressed(BUTTON_RIGHT):
                view = (view + 1) % VIEW_COUNT
        if view == STATS_VIEW:
            if badge.pressed(BUTTON_UP):
                user.scroll_stats(-1)
            if badge.pressed(BUTTON_DOWN):
                user.scroll_stats(1)
        if badge.pressed(BUTTON_SELECT):
            user.animate_avatar()
        user.draw(status, view)
    else:
        draw_simple(status)


run(update)
