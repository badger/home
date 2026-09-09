import json
import os
import sys

APP_DIRS = ("/remote/apps/badge", "/system/apps/badge", "/apps/badge", "/badge")
APP_DIR = next(path for path in APP_DIRS if is_dir(path))
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

import requests
import secrets
import wifi

screen.antialias = image.X2
small_font = font.sins
large_font = font.nope

USERNAME = getattr(secrets, "GITHUB_USERNAME", "")
TOKEN = getattr(secrets, "GITHUB_TOKEN", "")
CACHE_FILE = "/state/github-badge.json"
AVATAR_FILE = "/state/github-badge-avatar.png"

BACKGROUND = color.rgb(13, 17, 23)
FOREGROUND = color.rgb(240, 246, 252)
MUTED = color.rgb(139, 148, 158)
GREEN = color.rgb(46, 160, 67)
BLUE = color.rgb(88, 166, 255)
RED = color.rgb(248, 81, 73)

profile = None
contributions = None
avatar = None
status = "Loading cache..."
refresh_requested = True


def headers():
    result = {"User-Agent": "GitHub-Universe-Badge"}
    if TOKEN:
        result["Authorization"] = "Bearer " + TOKEN
    return result


def request_json(url):
    response = requests.get(url, headers=headers())
    try:
        return response.json()
    finally:
        response.close()


def download(url, path):
    response = requests.get(url, headers=headers())
    try:
        with open(path, "wb") as destination:
            destination.write(response.content)
    finally:
        response.close()


def load_cache():
    global profile, contributions, avatar, status, refresh_requested
    try:
        with open(CACHE_FILE, "r") as cached:
            data = json.load(cached)
        profile = data.get("profile")
        contributions = data.get("contributions")
        if file_exists(AVATAR_FILE):
            avatar = image.load(AVATAR_FILE)
        status = "SELECT to refresh"
        refresh_requested = False
    except (OSError, ValueError):
        status = "No cached GitHub data"


def save_cache():
    with open(CACHE_FILE, "w") as cached:
        json.dump({"profile": profile, "contributions": contributions}, cached)


def refresh():
    global profile, contributions, avatar, status

    if not USERNAME:
        status = "Set GITHUB_USERNAME in secrets.py"
        return
    if not wifi.connect():
        status = "Connecting to Wi-Fi..."
        return

    status = "Downloading profile..."
    profile = request_json("https://api.github.com/users/" + USERNAME)

    status = "Downloading contributions..."
    contributions = request_json("https://github.com/%s.contribs" % USERNAME)

    avatar_url = profile.get("avatar_url")
    if avatar_url:
        status = "Downloading avatar..."
        download("https://wsrv.nl/?url=%s&w=96&h=96&output=png" % avatar_url, AVATAR_FILE)
        avatar = image.load(AVATAR_FILE)

    save_cache()
    status = "Updated - SELECT to refresh"


def contribution_count():
    if isinstance(contributions, dict):
        for key in ("total_contributions", "total", "totalContributions", "contributions"):
            value = contributions.get(key)
            if isinstance(value, int):
                return value
    if isinstance(contributions, list):
        return sum(item.get("count", 0) for item in contributions if isinstance(item, dict))
    return None


def draw_contributions():
    if not isinstance(contributions, dict):
        return
    weeks = contributions.get("weeks") or []
    colors = (
        color.rgb(22, 27, 34),
        color.rgb(14, 68, 41),
        color.rgb(0, 109, 50),
        color.rgb(38, 166, 65),
        color.rgb(57, 211, 83),
    )
    offset = int((badge.ticks / 150) % max(1, len(weeks)))
    for x in range(53):
        week = weeks[(x + offset) % len(weeks)] if weeks else {}
        days = week.get("contribution_days") or []
        for y in range(min(7, len(days))):
            level = clamp(int(days[y].get("level", 0)), 0, 4)
            screen.pen = colors[level]
            screen.shape(shape.rectangle(x * 3 + 1, y * 3 + 1, 2, 2))


def center_text(text, y):
    width, _ = screen.measure_text(text)
    screen.text(text, (screen.width - width) / 2, y)


def draw():
    screen.pen = BACKGROUND
    screen.clear()
    draw_contributions()

    if profile is None:
        screen.font = large_font
        screen.pen = FOREGROUND
        center_text("GITHUB BADGE", 28)
        screen.font = small_font
        screen.pen = MUTED
        center_text(status, 58)
        center_text("Configure badge/secrets.py", 75)
        return

    if avatar:
        screen.blit(avatar, rect(8, 8, 48, 48))

    screen.font = large_font
    screen.pen = FOREGROUND
    screen.text(profile.get("name") or profile.get("login") or USERNAME, 62, 9)
    screen.font = small_font
    screen.pen = BLUE
    screen.text("@" + profile.get("login", USERNAME), 62, 27)
    screen.pen = MUTED
    screen.text((profile.get("company") or "")[:20], 62, 42)

    screen.pen = color.rgb(22, 27, 34)
    screen.shape(shape.rounded_rectangle(7, 62, 146, 39, 5))
    screen.pen = FOREGROUND
    screen.text("REPOS", 15, 69)
    screen.text("FOLLOWERS", 58, 69)
    screen.text("CONTRIBS", 111, 69)
    screen.font = large_font
    screen.pen = GREEN
    screen.text(str(profile.get("public_repos", 0)), 15, 84)
    screen.pen = BLUE
    screen.text(str(profile.get("followers", 0)), 65, 84)
    screen.pen = RED
    count = contribution_count()
    screen.text("-" if count is None else str(count), 116, 84)

    screen.font = small_font
    screen.pen = MUTED
    screen.text(status, 8, 107)


def update():
    global refresh_requested, status

    if badge.pressed(BUTTON_SELECT):
        refresh_requested = True

    if refresh_requested:
        refresh_requested = False
        try:
            refresh()
        except (OSError, ValueError, KeyError) as error:
            status = "Update failed: %s" % error

    draw()


load_cache()
run(update)
