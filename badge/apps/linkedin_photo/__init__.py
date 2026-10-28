"""Rotate local photos or an optional cached batch from a configured URL."""

import gc
import os
import sys

APP_DIR = "/system/apps/linkedin_photo"
PHOTO_DIR = "assets"
SLIDE_MS = 5000
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

from remote_batch import BatchCache, BatchRefresh, read_config

badge.mode(HIRES | VSYNC)
screen.font = font.nope
screen.antialias = image.OFF
screen.fill_rule = image.EVEN_ODD

photo = None
photo_error = None
show_help = False
paused = False
elapsed_ms = 0
photo_index = 0
config_error = ""
batch_url = ""
cache = BatchCache()

try:
    batch_url = read_config()
except (OSError, ValueError) as error:
    config_error = "Invalid config.json: see USB console"
    print("linkedin_photo: config.json must contain a valid batch_url")

try:
    photo_files = sorted(
        name for name in os.listdir(PHOTO_DIR)
        if not name.startswith((".", "__")) and name.lower().endswith(".png")
    )
except OSError as error:
    if error.args[0] != 2:
        raise
    photo_files = []
    print("linkedin_photo: missing " + PHOTO_DIR)

if batch_url:
    try:
        cached_files = cache.cached(batch_url)
        if cached_files:
            photo_files = cached_files
    except (OSError, ValueError) as error:
        config_error = "Cache unavailable; using local photos"
        print("linkedin_photo: invalid or missing cached batch")


def load_photo(index):
    global photo, photo_index, photo_error, elapsed_ms

    elapsed_ms = 0
    photo = None
    gc.collect()
    if not photo_files:
        photo_error = "No photos yet"
        print("linkedin_photo: add PNGs to " + PHOTO_DIR)
        return
    photo_index = index % len(photo_files)
    name = photo_files[photo_index]
    path = name if name.startswith("/") else PHOTO_DIR + "/" + name
    photo_error = None
    try:
        photo = image.load(path)
    except (OSError, ValueError, RuntimeError, MemoryError) as error:
        photo_error = "Cannot open photo"
        print("linkedin_photo: failed to load " + path + ": " + str(error))


load_photo(0)


def validate_download(path):
    preview = image.load(path)
    if not (1 <= preview.width <= 320 and 1 <= preview.height <= 240):
        raise ValueError("Downloaded photo must fit within 320x240")
    del preview
    gc.collect()


refresh = BatchRefresh(cache, validate_download)
if batch_url:
    refresh.start(batch_url)


def on_exit():
    refresh.close()


def center_text(text, y):
    width, _ = screen.measure_text(text)
    screen.text(text, (screen.width - width) // 2, y)


def update():
    global show_help, paused, elapsed_ms, photo_files, config_error

    timer_reset = False
    if batch_url and badge.pressed(BUTTON_DOWN):
        refresh.start(batch_url)
    refresh.poll(badge.ticks_delta)
    if refresh.result is not None:
        photo_files = refresh.result
        refresh.result = None
        config_error = ""
        load_photo(0)
        timer_reset = True
    if badge.pressed(BUTTON_MENU):
        show_help = not show_help
        elapsed_ms = 0
        timer_reset = True
    if badge.pressed(BUTTON_SELECT):
        paused = not paused
        elapsed_ms = 0
        timer_reset = True
    if badge.pressed(BUTTON_BACK):
        show_help = False
        elapsed_ms = 0
        timer_reset = True

    if not show_help:
        if badge.pressed(BUTTON_LEFT):
            load_photo(photo_index - 1)
        elif badge.pressed(BUTTON_RIGHT):
            load_photo(photo_index + 1)
        elif not timer_reset and not paused and len(photo_files) > 1:
            elapsed_ms += badge.ticks_delta
            if elapsed_ms >= SLIDE_MS:
                load_photo(photo_index + 1)

    screen.pen = color.rgb(0, 0, 0)
    screen.rectangle(screen.clip)

    if photo is not None:
        scale = min(screen.width / photo.width, screen.height / photo.height)
        width = max(1, int(photo.width * scale))
        height = max(1, int(photo.height * scale))
        screen.blit(photo, rect(
            (screen.width - width) // 2,
            (screen.height - height) // 2,
            width, height,
        ))
        if paused and not show_help:
            screen.pen = color.rgb(13, 17, 23)
            screen.shape(shape.rectangle(0, screen.height - 22, screen.width, 22))
            screen.pen = color.rgb(255, 255, 255)
            center_text("Paused %d/%d" % (photo_index + 1, len(photo_files)),
                        screen.height - 19)

    if photo is None or show_help:
        screen.pen = color.rgb(13, 17, 23)
        screen.rectangle(screen.clip)
        screen.pen = color.rgb(80, 170, 255)
        center_text(photo_error or "Photo slideshow", 16)
        screen.pen = color.rgb(255, 255, 255)
        if photo_error:
            if photo_files:
                center_text("%d/%d: see USB console" %
                            (photo_index + 1, len(photo_files)), 42)
            center_text("Add PNG photos to assets/", 66)
            center_text("inside apps/linkedin_photo.", 88)
            center_text("See README for conversion.", 110)
        else:
            center_text("Auto: 5 sec / %d photos" % len(photo_files), 42)
            notice = refresh.message or config_error
            if notice:
                center_text(notice[:40], 66)
                center_text(notice[40:80], 88)
            else:
                center_text("Local photos / offline", 66)
        if batch_url:
            center_text("DOWN: refresh URL batch", 118)
        center_text("LEFT / RIGHT: browse", 140)
        center_text("SELECT: pause / resume", 162)
        center_text("MENU: help   BACK: close", 184)
        center_text("HOME: launcher", 206)

    if not show_help and (config_error or refresh.busy or refresh.failed):
        screen.pen = color.rgb(13, 17, 23)
        screen.rectangle(0, 0, screen.width, 22)
        screen.pen = color.rgb(255, 170, 80) if refresh.failed or config_error else color.rgb(80, 170, 255)
        center_text("Refresh failed - MENU for details" if refresh.failed else
                    ("Config/cache warning - MENU" if config_error else refresh.message), 3)


run(update)
