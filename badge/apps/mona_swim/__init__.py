"""Mona Swim: hold Left/Right to steer, Select to start or pause, Back to leave."""

import math
import sys

APP_DIR = "/system/apps/mona_swim"
sys.path.insert(0, APP_DIR)

from badgeware import State
from swim_game import Swim, LEFT, TOP, RIGHT, BOTTOM

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

NAVY = color.rgb(12, 34, 64)
DECK = color.rgb(255, 228, 197)
TILE = color.rgb(255, 247, 228)
GROUT = color.rgb(219, 169, 151)
WATER = color.rgb(20, 173, 202)
DEEP = color.rgb(15, 145, 184)
RIPPLE = color.rgb(89, 219, 231)
WHITE = color.rgb(255, 255, 248)
PINK = color.rgb(255, 105, 164)
PINK_DARK = color.rgb(186, 49, 108)
YELLOW = color.rgb(255, 224, 90)
SHARK = color.rgb(81, 109, 139)
SHARK_DARK = color.rgb(39, 67, 103)
SHADOW = color.rgb(8, 91, 137, 100)
DIM = color.rgb(162, 210, 222)
OVERLAY = color.rgb(7, 26, 53, 210)

sprites = image.load(APP_DIR + "/assets/mona.png").spritesheet(7, 2)
record = {"best": 0}
State.load("mona_swim", record)
game = Swim()
mode = "title"
countdown = 0
save_failed = False
record_dirty = False


def text(label, x, y, pen=WHITE, typeface=None):
    screen.font = typeface or font.nope
    screen.pen = pen
    screen.text(label, x, y)


def centred(label, y, pen=WHITE, typeface=None):
    screen.font = typeface or font.nope
    width, _ = screen.measure_text(label)
    text(label, (320 - width) / 2, y, pen, screen.font)


def ellipse(x, y, rx, ry, pen):
    screen.pen = pen
    screen.shape(shape.ellipse(x, y, rx, ry))


def polygon(points, pen):
    screen.pen = pen
    screen.shape(shape.custom([vec2(x, y) for x, y in points]))


def draw_pool():
    screen.pen = DECK
    screen.clear()
    screen.pen = GROUT
    screen.rectangle(6, 38, 308, 190)
    screen.pen = TILE
    screen.rectangle(7, 39, 306, 188)
    screen.pen = GROUT
    for x in range(8, 313, 16):
        screen.rectangle(x, 39, 1, 5)
        screen.rectangle(x, BOTTOM, 1, 5)
    for y in range(44, 222, 16):
        screen.rectangle(7, y, 5, 1)
        screen.rectangle(RIGHT, y, 5, 1)
    screen.pen = WATER
    screen.rectangle(LEFT, TOP, RIGHT - LEFT, BOTTOM - TOP)
    # The lane markings are decoration; sharks move across these same lanes.
    screen.pen = DEEP
    for y in (82, 130, 178):
        for x in range(24, 298, 20):
            screen.rectangle(x, y, 9, 1)
    screen.pen = RIPPLE
    drift = int(badge.ticks / 140) % 42
    for row in range(5):
        y = TOP + 15 + row * 34
        for column in range(7):
            x = LEFT + ((column * 42 + drift + row * 11) % 276)
            screen.rectangle(x, y, 7, 1)
            screen.rectangle(x + 7, y - 1, 4, 1)


def draw_ring(x, y, radius=5, pickup=False):
    ellipse(x, y + 2, radius + 1, radius * 0.7, SHADOW)
    ellipse(x, y, radius, radius * 0.72, YELLOW if pickup else PINK)
    ellipse(x, y, radius * 0.46, radius * 0.32, WATER)
    ellipse(x - radius * 0.55, y - 1, 1.4, 1.2, WHITE)


def draw_mona(x, y, large=False):
    scale = 2 if large else 1
    frame = sprites.sprite(int(badge.ticks / 150) % 7, 0)
    ellipse(x, y + 7 * scale, 12 * scale, 5 * scale, SHADOW)
    # Mona rides in a pink ring, with her existing badge animation above it.
    screen.blit(frame, rect(x - 12 * scale, y - 17 * scale, 24 * scale, 26 * scale))
    ellipse(x, y + 5 * scale, 12 * scale, 5 * scale, PINK_DARK)
    ellipse(x, y + 3 * scale, 12 * scale, 5 * scale, PINK)
    ellipse(x, y + 2 * scale, 6 * scale, 2 * scale, WATER)
    ellipse(x - 8 * scale, y + 2 * scale, 2 * scale, 1 * scale, WHITE)
    if not large:
        dx, dy = math.cos(game.heading), math.sin(game.heading)
        ellipse(x + dx * 15, y + dy * 15, 1.5, 1.5, WHITE)


def draw_shark(shark):
    x, y, direction = shark.x, shark.y, shark.direction
    warning = shark.warning > 0
    if warning and (badge.ticks // 140) % 2:
        ellipse(x, y, 24, 13, RIPPLE)
        return
    ellipse(x, y + 5, 20, 7, SHADOW)

    def body(points, pen):
        polygon([(x + px * direction, y + py) for px, py in points], pen)

    body(((-12, 0), (-24, -9), (-22, 0), (-24, 9)), SHARK_DARK)
    ellipse(x, y, 17, 7, SHARK)
    body(((-6, -4), (1, -17), (7, -3)), SHARK_DARK)
    body(((-3, 3), (3, 12), (8, 3)), SHARK_DARK)
    ellipse(x + 7 * direction, y - 2, 2, 2, WHITE)
    ellipse(x + 8 * direction, y - 2, 1, 1, NAVY)
    body(((9, 3), (15, 1), (13, 5)), WHITE)
    if warning:
        text("!", x - 2, y - 27, YELLOW, font.futile)


def draw_swimmers():
    # Rings follow the exact path, like a snake's body.
    for i in range(len(game.path) - 1, 2, -3):
        x, y = game.path[i]
        draw_ring(x, y)
    if game.floatie is not None:
        x, y = game.floatie
        draw_ring(x, y, 8, True)
        if game.splash > 0:
            ellipse(game.head[0], game.head[1], 17, 9, RIPPLE)
    for shark in game.sharks:
        draw_shark(shark)
    draw_mona(*game.head)


def draw_hud():
    screen.pen = NAVY
    screen.rectangle(0, 0, 320, 34)
    text("MONA SWIM", 10, 6, WHITE, font.futile)
    text("FLOATIES %02d" % game.score, 151, 5, YELLOW)
    text("BEST %02d" % record["best"], 151, 19, DIM)
    text("LAP %d" % game.level, 259, 5)
    text("%02d:%02d" % (game.elapsed // 60000, game.elapsed // 1000 % 60), 259, 19, DIM)
    warning = mode == "play" and any(s.warning > 0 for s in game.sharks)
    centred("SHARK INCOMING! Watch the flashing fins" if warning
            else "L / R steer   SELECT pause   BACK exit", 227, NAVY)


def panel(top, height):
    screen.pen = OVERLAY
    screen.rectangle(22, top, 276, height)
    screen.pen = PINK
    screen.rectangle(22, top, 276, 2)


def start():
    global mode, countdown
    game.reset()
    countdown = 2400
    mode = "countdown"


def save_best():
    global save_failed, record_dirty
    if game.score > record["best"]:
        record["best"] = game.score
        record_dirty = True
    if record_dirty:
        try:
            State.save("mona_swim", record)
            save_failed = False
            record_dirty = False
        except OSError:
            save_failed = True


def update():
    global mode, countdown
    dt = min(max(badge.ticks_delta, 0), 80)
    if badge.pressed(BUTTON_BACK):
        save_best()
        return False
    if mode == "title":
        if badge.pressed(BUTTON_SELECT):
            start()
    elif mode == "countdown":
        countdown -= dt
        if countdown <= 0:
            mode = "play"
    elif mode == "play":
        if badge.pressed(BUTTON_SELECT):
            mode = "pause"
        else:
            steering = int(bool(badge.held(BUTTON_RIGHT))) - int(bool(badge.held(BUTTON_LEFT)))
            game.step(dt, steering)
            if game.dead:
                save_best()
                mode = "over"
    elif mode == "pause":
        if badge.pressed(BUTTON_SELECT):
            # A short ready cue avoids an accidental collision on resuming.
            countdown = 1200
            mode = "countdown"
    elif mode == "over" and badge.pressed(BUTTON_SELECT):
        start()

    draw_pool()
    draw_swimmers()
    draw_hud()

    if mode == "title":
        panel(56, 151)
        centred("MONA SWIM", 62, YELLOW, font.ignore)
        draw_mona(160, 126, True)
        centred("Collect yellow floaties. Grow your train.", 153)
        centred("Dodge sharks, edges and your own tail.", 167)
        centred("LEFT / RIGHT steer   SELECT dive in", 189, YELLOW)
    elif mode == "countdown":
        panel(94, 64)
        centred("READY TO MAKE WAVES?", 105, YELLOW)
        centred(str(max(1, (countdown + 799) // 800)), 124, WHITE, font.ignore)
    elif mode == "pause":
        panel(90, 77)
        centred("POOL BREAK", 101, YELLOW, font.ignore)
        centred("SELECT swim on   BACK exit", 142)
    elif mode == "over":
        panel(65, 140)
        centred("POOL'S CLOSED", 77, YELLOW, font.ignore)
        centred(game.reason, 111)
        centred("FLOATIES %d     BEST %d" % (game.score, record["best"]), 136, PINK, font.futile)
        centred("Best kept this session (save failed)" if save_failed else "One more lap?", 161, DIM)
        centred("SELECT try again   BACK exit", 184, YELLOW)


def on_exit():
    save_best()


run(update)
