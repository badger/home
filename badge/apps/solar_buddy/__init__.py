"""Universe 2026 Badgeware entry point. Desktop users run preview.py."""

import os
import sys

APP_DIRS = ("/remote/apps/solar_buddy", "/system/apps/solar_buddy",
            "/apps/solar_buddy", "/solar_buddy")
APP_DIR = next(path for path in APP_DIRS if is_dir(path))
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

from badgeware import State
from clock import ticks_ms
from config import DEVICE_SECRETS, load_secrets, load_settings
from controller import App
from hardware import Feedback
from ui import BadgePainter, UI

badge.mode(HIRES | VSYNC)
screen.font = font.sins
settings = load_settings("settings.json")
feedback = Feedback(badge)
saved = {"mode": settings["mode"], "scenario": 0, "superstar": False}
State.load("solar_buddy", saved)


def live_source():
    credentials = load_secrets(
        DEVICE_SECRETS, "No " + DEVICE_SECRETS +
        ". See README: Home Assistant credentials.")
    from ha_client import BadgeWifi, HomeAssistant
    return HomeAssistant(settings, credentials, wifi=BadgeWifi())


def save_state(value):
    try:
        State.save("solar_buddy", value)
    except OSError as exc:
        app.hardware_note = "Cannot save preferences: " + str(exc)
        print("Solar Buddy: " + app.hardware_note)


app = App(settings, live_source, saved, save_state)
ui = UI(BadgePainter(screen, shape, color))
buttons = ((BUTTON_LEFT, "left"), (BUTTON_RIGHT, "right"), (BUTTON_UP, "up"),
           (BUTTON_DOWN, "down"), (BUTTON_SELECT, "select"), (BUTTON_BACK, "back"),
           (BUTTON_MENU, "menu"))


def update():
    now = ticks_ms()
    for button, action in buttons:
        if badge.pressed(button):
            app.input(action, now)
    app.tick(now)
    feedback.update(app, now)
    ui.draw(app, now, badge.ticks_delta)


def on_exit():
    app.close()
    feedback.close()


try:
    run(update)
finally:
    on_exit()
