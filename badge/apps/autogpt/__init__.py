"""AutoGPT: live status of your AutoGPT agent runs from the platform's v2 API.

Needs Wi-Fi plus AUTOGPT_API_KEY (and optionally AUTOGPT_API_URL) in
secrets.py; see README.md.
"""

import os
import sys

APP_DIR = "/system/apps/autogpt"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

import ui

app = ui.App()


def update():
    app.update()


def on_exit():
    badge.caselights(0)


run(update)
