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
USER_AVATAR = "https://wsrv.nl/?url=https://github.com/{user}.png&w=150&output=png"
DETAILS_URL = "https://api.github.com/users/{user}"

CACHE_DIR = "/state"
USER_FILE = f"{CACHE_DIR}/badge_user.json"
CONTRIB_FILE = f"{CACHE_DIR}/badge_contribs.json"
AVATAR_FILE = f"{CACHE_DIR}/badge_avatar.png"

HEADERS = {"User-Agent": "GitHub Universe Badge 2026"}

RETRY_MS = 30000

fetch.AsyncFetch.MAX_HEADER_BYTES = 8192

GRAPH_WEEKS = 53
GRAPH_DAYS = 7
TILE_SIZE = 33
TILE_STEP = 37
GRAPH_TOP = (240 - GRAPH_DAYS * TILE_STEP) // 2
PARALLAX_SHIFT = 8
AVATAR_SIZE = 150

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
            self.request = fetch.url(url, headers=HEADERS).to(self.temp_file)

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

    def __init__(self, handle):
        self.handle = handle
        self.tile = shape.rounded_rectangle(0, 0, TILE_SIZE, TILE_SIZE, 4)
        self.update()

    def update(self, force_update=False):
        self.name = None
        self.followers = None
        self.contribs = None
        self.contribution_data = None
        self.repos = None
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
        del data
        gc.collect()

    def load_contrib_data(self):
        with open(CONTRIB_FILE, "r") as f:
            data = json.load(f)
        self.contribs = data["total_contributions"]
        self.contribution_data = [[0 for _ in range(GRAPH_WEEKS)] for _ in range(GRAPH_DAYS)]
        for week_index, week in enumerate(data["weeks"][:GRAPH_WEEKS]):
            for day, contribution in enumerate(week["contribution_days"][:GRAPH_DAYS]):
                self.contribution_data[day][week_index] = contribution["level"]
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
            self._download = Download(url.format(user=self.handle), file, self._force_update)

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

    def draw_avatar(self):
        if self.avatar:
            screen.blit(self.avatar, rect(10, 74, AVATAR_SIZE, AVATAR_SIZE))
            return

        squircle = shape.squircle(0, 0, 20, 5)
        screen.pen = spinner
        for i in range(4):
            mul = math.sin(badge.ticks / 1000) * 14000
            squircle.transform = mat3().translate(85, 149).rotate((badge.ticks + i * mul) / 40).scale(1 + i / 1.3)
            screen.shape(squircle)

    def draw(self, status):
        self.draw_graph()

        screen.font = mona_sans
        screen.pen = white
        center_text(status or self.handle, 4, HANDLE_SIZE)

        screen.pen = phosphor
        center_text(placeholder_if_none(self.name), 36, NAME_SIZE)

        self.draw_stat("followers", self.followers, 176, 66)
        self.draw_stat("contribs", self.contribs, 176, 124)
        self.draw_stat("repos", self.repos, 176, 182)

        self.draw_avatar()


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
        user.draw(status)
    else:
        draw_simple(status)


run(update)
