"""A cached, remotely editable personal card."""

import json
import os
import sys

APP_DIR = "/system/apps/live_card"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

from card import DEFAULT, THEMES, validate_page, encode_cursor, wrap
from badgeware import State
import fetch
import wifi

try:
    import secrets
except ImportError:
    secrets = None

badge.mode(HIRES | VSYNC)
screen.font = font.load("/system/assets/fonts/MonaSans-Medium.af")

DEFAULT_URL = "https://github-badge.exe.xyz/api/history"
URL = str(getattr(secrets, "LIVE_CARD_HISTORY_URL", DEFAULT_URL) or "").strip()
TOKEN = str(getattr(secrets, "LIVE_CARD_READ_TOKEN", "") or "").strip()
ALLOW_HTTP = getattr(secrets, "LIVE_CARD_ALLOW_HTTP", False) is True
CONFIGURED = bool(URL)
VALID_URL = URL.startswith("https://") or (ALLOW_HTTP and URL.startswith("http://"))
DOWNLOAD = "/state/live_card_download.json"
REFRESH_MS = 15000
WHITE = color.rgb(240, 246, 252)
MUTED = color.rgb(164, 175, 189)
BACKGROUND = color.rgb(13, 17, 23)

card = dict(DEFAULT)
saved = {"page": None}
State.load("live_card_history", saved)
page = {"messages": [], "next_cursor": None}
status = "Setup needed - see README"
if saved["page"] is not None:
    try:
        page = validate_page(saved["page"])
        status = "Cached history"
    except ValueError:
        print("Live Card: invalid cached card")
        status = "Invalid cache - showing demo"

request = None
page_cursors = [None]
page_number = 0
selected = 0
target_page = 0
target_cursor = None
loading_page = False
next_refresh = 0
scroll = 0
title_lines = []
message_lines = []
visible_rows = 1
message_y = 0


def layout():
    global card, title_lines, message_lines, message_y, visible_rows, scroll
    card = page["messages"][selected] if page["messages"] else dict(DEFAULT, title="No messages yet", message="Publish a message on the website.")
    title_lines = wrap(card["title"], screen.width - 24,
                       lambda text: screen.measure_text(text, font_size=22)[0])
    message_lines = wrap(card["message"], screen.width - 24,
                         lambda text: screen.measure_text(text, font_size=18)[0])
    message_y = 59 + len(title_lines) * 25
    visible_rows = max(1, (screen.height - 44 - message_y) // 22)
    scroll = 0


def fail(message):
    global request, status, next_refresh, loading_page
    print("Live Card: " + message)
    status = message
    request = None
    loading_page = False
    next_refresh = badge.ticks + REFRESH_MS


def sync():
    global request, status, next_refresh, page, selected, page_number, loading_page
    global target_page, target_cursor, page_cursors
    if not CONFIGURED:
        status = "Setup needed - see README"
        return
    if not VALID_URL:
        status = "Setup error: HTTPS required"
        return
    if request is not None:
        if request.error:
            fail("Sync failed - will retry")
        elif request:
            request = None
            next_refresh = badge.ticks + REFRESH_MS
            try:
                if os.stat(DOWNLOAD)[6] > 12288:
                    raise ValueError("History response is too large")
                with open(DOWNLOAD) as file:
                    updated = validate_page(json.load(file))
                if updated["next_cursor"] is not None and (
                        updated["next_cursor"] == target_cursor
                        or updated["next_cursor"] in page_cursors[:target_page + 1]):
                    raise ValueError("History cursor repeats")
            except (OSError, ValueError):
                fail("Invalid response - kept card")
                return
            if target_page == 0:
                try:
                    State.save("live_card_history", {"page": updated})
                except OSError:
                    fail("Cache save failed - kept card")
                    return
            old_id = card.get("id")
            old_page = page_number
            page = updated
            page_number = target_page
            if loading_page:
                if target_page == 0:
                    page_cursors = [None]
                elif target_page == len(page_cursors):
                    page_cursors.append(target_cursor)
                selected = max(0, len(page["messages"]) - 1) if target_page < old_page else 0
            else:
                selected = next((index for index, item in enumerate(page["messages"])
                                 if item["id"] == old_id), 0)
            loading_page = False
            layout()
            status = "Synced"
        return
    if badge.ticks < next_refresh:
        return
    if not loading_page:
        if page_number != 0:
            return
        target_page = 0
        target_cursor = None
    if not wifi.is_connected():
        status = "Connecting to Wi-Fi..."
        wifi.connect()
        if wifi.failure():
            status = "Wi-Fi unavailable - will retry"
        return
    try:
        headers = {}
        if TOKEN:
            headers["Authorization"] = "Bearer " + TOKEN
        url = URL
        if target_cursor is not None:
            url += ("&" if "?" in url else "?") + "cursor=" + encode_cursor(target_cursor)
        request = fetch.url(url, headers=headers).to(DOWNLOAD)
        status = "Syncing..."
    except (OSError, ValueError):
        fail("Could not start sync")


def draw():
    screen.pen = BACKGROUND
    screen.rectangle(screen.clip)
    screen.pen = color.rgb(*THEMES[card["theme"]])
    screen.rectangle(0, 0, screen.width, 4)
    screen.text("KD's GitHub Badge", 12, 14, 12)
    if page["messages"]:
        name = "From: " + card["name"]
        while screen.measure_text(name, font_size=12)[0] > screen.width - 24:
            name = name[:-1]
        screen.text(name, 12, 34, 12)
    for index, line in enumerate(title_lines):
        screen.text(line, 12, 56 + index * 25, 22)
    screen.pen = WHITE
    for index, line in enumerate(message_lines[scroll:scroll + visible_rows]):
        screen.text(line, 12, message_y + index * 22, 18)
    screen.pen = MUTED
    status_width, _ = screen.measure_text(status, font_size=12)
    screen.text(status, screen.width - status_width - 12, screen.height - 35, 12)
    hint = "UP/DOWN: MESSAGES   ENTER: LATEST"
    if len(message_lines) > visible_rows:
        hint = "UP/DOWN: MESSAGES   LEFT/RIGHT: TEXT"
    hint_width, _ = screen.measure_text(hint, font_size=10)
    screen.text(hint, screen.width - hint_width - 12, screen.height - 17, 10)


def update():
    global next_refresh, scroll, selected, target_cursor, target_page, loading_page
    if badge.pressed(BUTTON_SELECT) and request is None:
        target_page = 0
        target_cursor = None
        loading_page = True
        next_refresh = 0
    elif request is None and not loading_page:
        if badge.pressed(BUTTON_DOWN):
            if selected + 1 < len(page["messages"]):
                selected += 1
                layout()
            elif page["next_cursor"] is not None:
                target_page = page_number + 1
                target_cursor = page["next_cursor"]
                loading_page = True
                next_refresh = 0
        elif badge.pressed(BUTTON_UP):
            if selected > 0:
                selected -= 1
                layout()
            elif page_number > 0:
                target_page = page_number - 1
                target_cursor = page_cursors[target_page]
                loading_page = True
                next_refresh = 0
    if badge.pressed(BUTTON_RIGHT):
        scroll = min(max(0, len(message_lines) - visible_rows), scroll + 1)
    elif badge.pressed(BUTTON_LEFT):
        scroll = max(0, scroll - 1)
    sync()
    draw()


layout()
run(update)
