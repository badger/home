import os
import sys

APP_DIRS = ("/remote/apps/startup", "/system/apps/startup", "/apps/startup", "/startup")
APP_DIR = next(path for path in APP_DIRS if is_dir(path))
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

INTRO_END = 113
FINAL_FRAME = 159
INTRO_DURATION = 3000
OUTRO_DURATION = 750

started_at = badge.ticks
outro_started_at = None


def draw_frame(frame):
    screen.load_into("frames/intro_%05d.png" % frame)


def update():
    global outro_started_at

    elapsed = badge.ticks - started_at
    if elapsed < INTRO_DURATION:
        draw_frame(min(int((elapsed / INTRO_DURATION) * INTRO_END), INTRO_END))
        return

    if outro_started_at is None:
        draw_frame(INTRO_END)
        if badge.pressed() or badge.touched():
            outro_started_at = badge.ticks
        return

    outro_elapsed = badge.ticks - outro_started_at
    if outro_elapsed >= OUTRO_DURATION:
        return True

    progress = outro_elapsed / OUTRO_DURATION
    frame = INTRO_END + int(progress * (FINAL_FRAME - INTRO_END))
    draw_frame(min(frame, FINAL_FRAME))
    screen.pen = color.rgb(0, 0, 0, int(progress * 255))
    screen.shape(shape.rectangle(0, 0, screen.width, screen.height))


run(update)
