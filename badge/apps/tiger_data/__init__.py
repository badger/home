"""Tiger Data: an office tiger. Select: tantrum. Right: idea. Back: launcher."""

import gc

APP_DIR = "/system/apps/tiger_data"
FRAME_COUNT = 156
FPS = 12
CYCLE_MS = 13000
TANTRUM_MS = 4400
IDEA_MS = 10000

badge.mode(HIRES | VSYNC)
previous_clear = badge.default_clear
badge.default_clear = None
screen.antialias = image.OFF

BACKGROUND = color.rgb(16, 29, 39)
DIM = color.rgb(164, 183, 187)
YELLOW = color.rgb(245, 255, 128)
phase_ms = 0
frame_index = -1
picture = None
failed = False


def draw_footer():
    screen.pen = BACKGROUND
    screen.rectangle(0, 222, 320, 18)
    screen.font = font.nope
    screen.pen = DIM
    screen.text("SELECT tantrum", 5, 226)
    screen.text("RIGHT idea", 145, 226)
    screen.text("BACK exit", 250, 226)


def update():
    global phase_ms, frame_index, picture, failed
    if badge.pressed(BUTTON_BACK):
        return False
    # Delta time is bounded to avoid skipping the raised-paw and slam poses
    # after a slow storage read. The app keeps only one decoded frame in RAM.
    if badge.pressed(BUTTON_SELECT):
        phase_ms = TANTRUM_MS
    elif badge.pressed(BUTTON_RIGHT):
        phase_ms = IDEA_MS
    else:
        phase_ms = (phase_ms + min(max(badge.ticks_delta, 0), 125)) % CYCLE_MS
    target = min(FRAME_COUNT - 1, phase_ms * FPS // 1000)
    if target != frame_index and not failed:
        picture = None
        gc.collect()
        try:
            picture = image.load(APP_DIR + "/assets/frames/%03d.png" % target)
            frame_index = target
        except (OSError, MemoryError):
            failed = True
    screen.pen = BACKGROUND
    screen.clear()
    if picture is not None:
        screen.blit(picture, vec2(0, 5))
    elif failed:
        screen.font = font.nope
        screen.pen = YELLOW
        screen.text("Tiger Data frames unavailable", 25, 100)
        screen.pen = DIM
        screen.text("Copy the complete tiger_data folder", 15, 119)
    draw_footer()


def on_exit():
    global picture
    picture = None
    badge.default_clear = previous_clear
    screen.antialias = image.OFF
    gc.collect()


run(update)
