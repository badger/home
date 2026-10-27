"""Latest six uploads: left/right browse, select pause, up refresh."""

import gc
import os
import sys
import time
import machine

import fetch
import missing_details

APP_DIR = "/system/apps/youtube"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

from config import CHANNEL_HANDLE, CHANNEL_ID, SLIDE_MS, REFRESH_MS, RETRY_MS, MAX_RETRY_MS
from feed import read_feed, thumbnail_url, valid_id, video_url, relative_date, read_clock

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

CACHE_DIR = "/state/youtube"
FEED_FILE = CACHE_DIR + "/feed.xml"
HEADERS = {"User-Agent": "GitHub Universe Badge 2026"}
FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id=" + CHANNEL_ID
CLOCK_URL = "https://timeapi.io/api/time/current/zone?timeZone=UTC"
CLOCK_FILE = CACHE_DIR + "/clock.json"

black = color.rgb(0, 0, 0)
white = color.rgb(235, 245, 255)
qr_white = color.rgb(255, 255, 255)
muted = color.rgb(163, 182, 198)
accent = color.rgb(211, 250, 55)
panel = color.rgb(19, 26, 32)
warning = color.rgb(255, 150, 140)
typeface = missing_details.mona_sans()


def exists(path):
    try:
        os.stat(path)
        return True
    except OSError as error:
        if error.args[0] != 2:
            raise
        return False


configured = valid_id(CHANNEL_ID, 24) and CHANNEL_ID.startswith("UC")
if SLIDE_MS <= 0 or REFRESH_MS <= 0 or RETRY_MS <= 0 or MAX_RETRY_MS < RETRY_MS:
    raise ValueError("YouTube timings must be positive; max retry must be >= retry")
for directory in ("/state", CACHE_DIR):
    if not exists(directory):
        os.mkdir(directory)

videos = []
index = 0
paused = False
slide_at = badge.ticks
next_feed = 0
next_clock = 0
download = None
download_kind = None
download_id = None
download_file = None
photo = None
photo_id = None
qr = None
qr_id = None
thumb_retry = {}
retry_delays = {}
errors = {}
status = "Fetching latest videos..."
missing = missing_details.missing("WIFI_SSID")


def report(label, error, key):
    errors[key] = "%s: %s" % (label, error)
    print("YouTube:", errors[key])


try:
    if configured and exists(FEED_FILE):
        videos = read_feed(FEED_FILE, CHANNEL_ID)
        status = "Cached videos"
except (OSError, ValueError) as error:
    report("Cache", error, "cache")


def thumb_path(video_id):
    return CACHE_DIR + "/" + video_id + ".png"


def discard_temp():
    path = download_file + ".tmp"
    if exists(path):
        os.remove(path)


def prune_thumbnails():
    wanted = {video["id"] + ".png" for video in videos}
    for name in os.listdir(CACHE_DIR):
        if name.endswith(".png") and name not in wanted:
            os.remove(CACHE_DIR + "/" + name)


def begin(kind, url, path, video_id=None):
    global download, download_kind, download_file, download_id, status
    download_kind = kind
    download_file = path
    download_id = video_id
    status = "Refreshing videos..." if kind == "feed" else "Loading thumbnail..."
    if kind == "clock":
        status = "Syncing clock..."
    download = fetch.url(url, headers=HEADERS).to(path + ".tmp")


def failed(error):
    global download, next_feed, next_clock
    key = download_kind if download_kind in ("feed", "clock") else download_id
    delay = min(MAX_RETRY_MS, max(RETRY_MS, retry_delays.get(key, 0) * 2))
    retry_delays[key] = delay
    report({"feed": "Feed", "clock": "Clock"}.get(download_kind, "Thumbnail"), error, key)
    if download_kind == "feed":
        next_feed = badge.ticks + delay
    elif download_kind == "clock":
        next_clock = badge.ticks + delay
    else:
        thumb_retry[download_id] = badge.ticks + delay
    print("YouTube: retry %s in %d seconds" % (key, delay // 1000))
    discard_temp()
    download = None


def completed():
    global videos, index, slide_at, next_feed, photo_id, photo, status
    temp = download_file + ".tmp"
    if download_kind == "clock":
        machine.RTC().datetime(read_clock(temp))
        os.remove(temp)
        errors.pop("clock", None)
        retry_delays.pop("clock", None)
    elif download_kind == "feed":
        incoming = read_feed(temp, CHANNEL_ID)
        os.rename(temp, FEED_FILE)
        current_id = videos[index]["id"] if videos else None
        videos = incoming
        index = 0
        for position, video in enumerate(videos):
            if video["id"] == current_id:
                index = position
                break
        slide_at = badge.ticks
        next_feed = badge.ticks + REFRESH_MS
        wanted = {video["id"] for video in videos}
        for key in list(thumb_retry):
            if key not in wanted:
                thumb_retry.pop(key, None)
                retry_delays.pop(key, None)
                errors.pop(key, None)
        photo = None
        photo_id = None
        prune_thumbnails()
        errors.pop("feed", None)
        errors.pop("cache", None)
        retry_delays.pop("feed", None)
    else:
        candidate = image.load(temp)
        if candidate.width != 192 or candidate.height != 108:
            raise ValueError("Unexpected thumbnail dimensions")
        os.rename(temp, download_file)
        if videos and videos[index]["id"] == download_id:
            photo = candidate
            photo_id = download_id
        thumb_retry.pop(download_id, None)
        errors.pop(download_id, None)
        retry_delays.pop(download_id, None)
    status = "No public uploads" if not videos else "Latest uploads"
    gc.collect()


def fetch_step():
    global download
    if download is not None:
        try:
            if download:
                completed()
                download = None
            elif download.error:
                failed(download.error)
        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
            failed(error)
        return
    if missing:
        return
    try:
        if badge.ticks >= next_feed:
            begin("feed", FEED_URL, FEED_FILE)
        elif clock_needs_sync() and badge.ticks >= next_clock:
            begin("clock", CLOCK_URL, CLOCK_FILE)
        elif videos:
            # Fetch the visible slide first, then warm the other five on disk.
            for step in range(len(videos)):
                video_id = videos[(index + step) % len(videos)]["id"]
                if (badge.ticks >= thumb_retry.get(video_id, 0)
                        and not exists(thumb_path(video_id))):
                    begin("thumbnail", thumbnail_url(video_id), thumb_path(video_id), video_id)
                    break
    except (OSError, ValueError, RuntimeError) as error:
        failed(error)


def clock_needs_sync():
    today = time.localtime()
    if today[0] < 2024:
        return True
    current = "%04d-%02d-%02d" % today[:3]
    return bool(videos and videos[0]["published"][:10] > current)


def load_photo():
    global photo, photo_id
    video_id = videos[index]["id"]
    if photo_id == video_id:
        return
    photo = None
    photo_id = video_id
    path = thumb_path(video_id)
    if exists(path):
        try:
            photo = image.load(path)
        except (OSError, ValueError, RuntimeError) as error:
            report("Cached thumbnail", error, video_id)
            os.remove(path)
            thumb_retry[video_id] = badge.ticks + RETRY_MS


def fit(text, width, size):
    if screen.measure_text(text, font_size=size)[0] <= width:
        return text
    while text and screen.measure_text(text + "...", font_size=size)[0] > width:
        text = text[:-1]
    return text.rstrip() + "..."


def title_lines(title):
    lines = []
    line = ""
    for word in title.split():
        candidate = (line + " " + word).strip()
        if line and screen.measure_text(candidate, font_size=18)[0] > 304:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    if len(lines) > 2:
        lines[1] = fit(" ".join(lines[1:]), 304, 18)
    return [fit(line, 304, 18) for line in lines[:2]]


def draw_qr(video_id):
    global qr, qr_id
    if qr_id != video_id:
        qr = image.qr(video_url(video_id), image.QR_LOW, 2)
        qr_id = video_id
    # Fill the frame; retain only the quiet zone already in the generated image.
    size = 72
    screen.pen = qr_white
    screen.rectangle(240, 59, 72, 72)
    screen.blit(qr, rect(0, 0, qr.width, qr.height),
                rect(240 + (72 - size) // 2, 59 + (72 - size) // 2, size, size),
                image.NEAREST)


def views_label(views):
    if views is None:
        return "Views unavailable"
    digits = str(views)
    groups = []
    while digits:
        groups.insert(0, digits[-3:])
        digits = digits[:-3]
    return ",".join(groups) + (" view" if views == 1 else " views")


def draw():
    fault = errors.get("feed") or errors.get("cache") or errors.get("clock")
    if videos:
        fault = fault or errors.get(videos[index]["id"])
    screen.pen = black
    screen.clear()
    screen.font = typeface
    screen.pen = white
    screen.text(fit(CHANNEL_HANDLE, 304, 18), 8, 5, 18)
    if not videos:
        screen.pen = accent
        screen.text("YouTube slideshow", 8, 43, 23)
        screen.pen = warning if fault else muted
        message = fault or status
        screen.text(message, rect(8, 84, 304, 100), 17, align=(LEFT, TOP))
        screen.pen = muted
        screen.text("UP retry  |  DOWN home", 8, 213, 14)
        return

    video = videos[index]
    screen.pen = panel
    screen.rectangle(8, 32, 224, 126)
    if photo is not None:
        screen.blit(photo, rect(0, 0, photo.width, photo.height),
                    rect(8, 32, 224, 126), image.BILINEAR)
    else:
        screen.pen = muted
        label = "Thumbnail unavailable" if video["id"] in thumb_retry else "Loading thumbnail..."
        if missing:
            label = "Connect Wi-Fi\nfor thumbnails"
        screen.text(label, rect(18, 72, 204, 65), 15, align=image.CENTER)

    draw_qr(video["id"])
    screen.pen = muted
    published = relative_date(video["published"], time.localtime())
    if published == "Check badge clock":
        published = "Connect Wi-Fi for date" if missing else "Syncing date..."
        if errors.get("clock"):
            published = "Date sync failed"
    screen.text(published, 8, 161, 12)
    remaining = 294 - screen.measure_text(published, font_size=12)[0]
    label = fit(views_label(video["views"]), remaining, 12)
    screen.text(label, 312 - screen.measure_text(label, font_size=12)[0], 161, 12)
    screen.pen = white
    for row, line in enumerate(title_lines(video["title"])):
        screen.text(line, 8, 178 + row * 18, 18)

    screen.pen = warning if fault else muted
    footer = "L/R browse  SELECT " + ("play" if paused else "pause") + "  DOWN home"
    if missing:
        footer = "Cached | Wi-Fi not configured"
    elif fault:
        retry_at = next_feed if errors.get("feed") else (
            next_clock if errors.get("clock") else thumb_retry.get(video["id"], 0))
        seconds = max(0, (retry_at - badge.ticks + 999) // 1000)
        footer = fit("Retry %ds | %s" % (seconds, fault), 304, 12)
    elif download is not None:
        footer = status
    screen.text(footer, 8, 219, 12)
    width = 304 / len(videos)
    for position in range(len(videos)):
        screen.pen = panel
        screen.rectangle(8 + position * width, 236, width - 3, 3)
        if position == index:
            progress = min(1, max(0, (badge.ticks - slide_at) / SLIDE_MS))
            screen.pen = accent
            screen.rectangle(8 + position * width, 236, (width - 3) * progress, 3)


def update():
    global index, paused, slide_at, next_feed, next_clock, missing
    if badge.pressed(BUTTON_DOWN):
        reset()
        return
    if not configured:
        screen.pen = black
        screen.clear()
        screen.font = typeface
        screen.pen = accent
        screen.text("Set up YouTube", 8, 35, 24)
        screen.pen = white
        screen.text("Set CHANNEL_ID and CHANNEL_HANDLE in config.py, then reopen the app.",
                    rect(8, 80, 304, 110), 18, align=(LEFT, TOP))
        screen.pen = muted
        screen.text("DOWN home", 8, 219, 12)
        return
    now = badge.ticks
    if badge.pressed(BUTTON_UP):
        next_feed = 0
        next_clock = 0
        thumb_retry.clear()
        retry_delays.clear()
        missing = missing_details.missing("WIFI_SSID")
    if videos:
        if paused:
            slide_at = now
        if badge.pressed(BUTTON_SELECT):
            paused = not paused
            slide_at = now
        step = 0
        if badge.pressed(BUTTON_RIGHT):
            step = 1
        elif badge.pressed(BUTTON_LEFT):
            step = -1
        elif not paused and now - slide_at >= SLIDE_MS:
            step = 1
        if step:
            index = (index + step) % len(videos)
            slide_at = now
        load_photo()
    if missing and not videos:
        missing_details.show(missing, lambda: None)
        return
    draw()
    fetch_step()


run(update)
