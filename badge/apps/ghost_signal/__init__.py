import math
import os
import random
import sys


APP_DIRS = (
    "/system/apps/ghost_signal",
    "/apps/ghost_signal",
    "/ghost_signal",
)

APP_DIR = APP_DIRS[0]
for app_dir in APP_DIRS:
    try:
        os.stat(app_dir)
        APP_DIR = app_dir
        break
    except OSError:
        pass

os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2


class GameState:
    INTRO = 1
    PLAYING = 2
    COMPLETE = 3


def resolve_button(*names):
    for name in names:
        try:
            return eval(name)
        except NameError:
            pass
    return None


BUTTON_MOVE_LEFT = resolve_button("BUTTON_A", "BUTTON_LEFT")
BUTTON_MOVE_RIGHT = resolve_button("BUTTON_C", "BUTTON_SELECT")
BUTTON_ACTION = resolve_button("BUTTON_B", "BUTTON_RIGHT")

WIDTH = screen.width
HEIGHT = screen.height
CX = WIDTH / 2
CY = HEIGHT / 2
FIELD_X = 0
FIELD_Y = 26
FIELD_W = WIDTH
FIELD_H = HEIGHT - 56
START_X = 2
END_X = WIDTH - 2

BACKGROUND = color.rgb(16, 20, 17)
PANEL = color.rgb(10, 36, 27)
GRID_MAJOR = color.rgb(8, 135, 43, 92)
GRID_MINOR = color.rgb(35, 41, 37, 180)
TARGET = color.rgb(15, 191, 62)
TARGET_GLOW = color.rgb(15, 191, 62, 58)
SIGNAL = color.rgb(191, 255, 209)
SIGNAL_HOT = color.rgb(242, 245, 243)
TRACE_OK = color.rgb(140, 242, 166, 128)
TRACE_MID = color.rgb(95, 237, 131, 94)
TRACE_BAD = color.rgb(182, 191, 184, 72)
TEXT = color.rgb(242, 245, 243)
MUTED = color.rgb(182, 191, 184)
SHADOW = color.rgb(0, 0, 0, 120)

small_font = font.sins
large_font = font.curse

state = GameState.INTRO
level = 1
signal_x = START_X
signal_y = CY
signal_vy = 0.0
score_total = 0.0
score_samples = 0
last_score = 0
energy = 100
pulse_until = 0
last_action_ticks = 0
target_points = []
trail = []
stars = []
scope_background = None
wave_phase = 0.0
wave_amp_1 = 44
wave_amp_2 = 16
wave_freq_1 = 2.0
wave_freq_2 = 5.0


def held(button):
    return button is not None and badge.held(button)


def pressed(button):
    return button is not None and badge.pressed(button)


def action_ready(delay=260):
    return badge.ticks - last_action_ticks > delay and pressed(BUTTON_ACTION)


def clamp(value, low, high):
    return min(high, max(low, value))


def mix(start, end, amount):
    return start + (end - start) * amount


def center_text(text, y):
    w, _ = screen.measure_text(text)
    screen.text(text, (WIDTH - w) / 2, y)


def target_y_at(x):
    progress = clamp((x - FIELD_X) / FIELD_W, 0, 1)
    primary = math.sin((progress * math.pi * wave_freq_1) + wave_phase) * wave_amp_1
    secondary = math.sin((progress * math.pi * wave_freq_2) + wave_phase * 0.63) * wave_amp_2
    return clamp(CY + primary + secondary, FIELD_Y + 15, FIELD_Y + FIELD_H - 15)


def accuracy_at(x, y):
    error = abs(y - target_y_at(x))
    return clamp(1 - (error / 56), 0, 1)


def make_wave():
    global target_points, wave_phase, wave_amp_1, wave_amp_2, wave_freq_1, wave_freq_2

    random.seed(level * 131)
    wave_phase = random.randrange(628) / 100
    wave_amp_1 = 34 + min(24, level * 3) + random.randrange(10)
    wave_amp_2 = 10 + random.randrange(16)
    wave_freq_1 = 1.6 + random.randrange(5) * 0.35
    wave_freq_2 = 3.4 + random.randrange(7) * 0.42
    target_points = []
    for index in range(81):
        x = FIELD_X + (FIELD_W * index / 80)
        target_points.append((x, target_y_at(x)))

    build_scope_background()


def reset_game():
    global state, signal_x, signal_y, signal_vy, score_total, score_samples
    global energy, pulse_until, last_action_ticks, trail

    make_wave()
    signal_x = START_X
    signal_y = target_y_at(START_X)
    signal_vy = 0.0
    score_total = 0.0
    score_samples = 0
    energy = 100
    pulse_until = 0
    last_action_ticks = badge.ticks
    trail = []
    state = GameState.PLAYING


def init():
    global stars

    random.seed(11)
    stars = []
    for _ in range(42):
        stars.append((random.randrange(WIDTH), random.randrange(HEIGHT), 24 + random.randrange(86)))
    make_wave()


def build_scope_background():
    global scope_background

    scope_background = image(WIDTH, HEIGHT)
    scope_background.antialias = image.X2
    scope_background.pen = BACKGROUND
    scope_background.clear()

    for x, y, alpha in stars:
        scope_background.pen = color.rgb(95, 237, 131, alpha)
        scope_background.put(x, y)

    scope_background.pen = PANEL
    scope_background.rectangle(FIELD_X, FIELD_Y, FIELD_W, FIELD_H)

    for x in range(0, WIDTH + 1, 16):
        scope_background.pen = GRID_MAJOR if x % 64 == 0 else GRID_MINOR
        scope_background.line(x, FIELD_Y, x, FIELD_Y + FIELD_H)
    for y in range(int(FIELD_Y), int(FIELD_Y + FIELD_H) + 1, 16):
        scope_background.pen = GRID_MAJOR if (y - FIELD_Y) % 64 == 0 else GRID_MINOR
        scope_background.line(0, y, WIDTH, y)

    if len(target_points) < 2:
        return

    scope_background.pen = TARGET_GLOW
    for index in range(len(target_points) - 1):
        x1, y1 = target_points[index]
        x2, y2 = target_points[index + 1]
        scope_background.shape(shape.line(x1, y1, x2, y2, 6))

    scope_background.pen = TARGET
    for index in range(len(target_points) - 1):
        x1, y1 = target_points[index]
        x2, y2 = target_points[index + 1]
        scope_background.shape(shape.line(x1, y1, x2, y2, 2))

    scope_background.pen = color.rgb(8, 135, 43, 150)
    scope_background.line(0, CY, WIDTH, CY)
    scope_background.pen = TARGET
    scope_background.rectangle(END_X - 2, FIELD_Y, 4, FIELD_H)
    scope_background.crt(4, 22, 0.35)


def draw_background():
    if scope_background is None:
        build_scope_background()
    screen.blit(scope_background, vec2(0, 0))


def draw_hud():
    score = int((score_total / max(1, score_samples)) * 100)

    screen.font = small_font
    screen.pen = MUTED
    screen.text("A/C phase", 8, 5)
    screen.text("UP/DOWN trace", WIDTH - 120, 5)

    screen.pen = color.rgb(35, 41, 37)
    screen.shape(shape.rounded_rectangle(8, HEIGHT - 17, 82, 8, 3))
    screen.pen = color.rgb(140, 242, 166)
    screen.shape(shape.rounded_rectangle(9, HEIGHT - 16, energy * 0.8, 6, 2))

    screen.pen = TEXT
    screen.text("SYNC " + str(score) + "%", 100, HEIGHT - 19)
    screen.text("L" + str(level), WIDTH - 34, HEIGHT - 19)


def trace_color(quality):
    if quality > 0.72:
        return TRACE_OK
    if quality > 0.38:
        return TRACE_MID
    return TRACE_BAD


def add_trace(quality):
    trail.append((signal_x, signal_y, quality))
    if len(trail) > 58:
        trail.pop(0)


def draw_trace():
    count = len(trail)
    if count == 0:
        return

    for index, point in enumerate(trail):
        x, y, quality = point
        radius = 1.6 + (index / count) * 3.2
        screen.pen = trace_color(quality)
        screen.circle(vec2(x, y), radius)


def draw_signal():
    pulsing = badge.ticks < pulse_until
    radius = 8 if pulsing else 6
    target_y = target_y_at(signal_x)

    screen.pen = color.rgb(191, 255, 209, 84)
    screen.line(signal_x, signal_y, signal_x, target_y)

    if pulsing:
        screen.pen = color.rgb(242, 245, 243, 72)
        screen.circle(vec2(signal_x, signal_y), 27)

    screen.pen = SIGNAL_HOT if pulsing else SIGNAL
    screen.circle(vec2(signal_x, signal_y), radius)


def intro():
    draw_background()
    screen.font = large_font
    screen.pen = SHADOW
    center_text("GHOST SIGNAL", 72)
    screen.pen = TEXT
    center_text("GHOST SIGNAL", 70)

    screen.font = small_font
    screen.pen = MUTED
    center_text("trace the carrier", 116)
    center_text("A/C phase, UP/DOWN amplitude", 134)

    if int(badge.ticks / 500) % 2:
        screen.pen = SIGNAL
        center_text("B to trigger", 166)

    if action_ready():
        reset_game()


def play():
    global state, level, signal_x, signal_y, signal_vy, score_total, score_samples
    global energy, pulse_until, last_action_ticks, last_score

    dt = badge.ticks_delta / 16.6
    if dt <= 0:
        dt = 1
    dt = min(2.5, dt)

    sweep = 0.82 + min(0.35, level * 0.025)
    if held(BUTTON_MOVE_LEFT):
        sweep -= 0.42
    if held(BUTTON_MOVE_RIGHT):
        sweep += 0.42
    if badge.ticks < pulse_until:
        sweep *= 0.45

    if held(BUTTON_UP):
        signal_vy -= 0.028 * dt
    if held(BUTTON_DOWN):
        signal_vy += 0.028 * dt

    if action_ready() and energy >= 28:
        target_y = target_y_at(signal_x)
        signal_y = mix(signal_y, target_y, 0.36)
        signal_vy *= 0.38
        energy -= 28
        pulse_until = badge.ticks + 720
        last_action_ticks = badge.ticks

    signal_vy *= 0.972
    signal_vy = clamp(signal_vy, -1.18, 1.18)
    signal_x += sweep * dt
    signal_y += signal_vy * dt
    signal_y = clamp(signal_y, FIELD_Y + 10, FIELD_Y + FIELD_H - 10)
    energy = min(100, energy + 0.055 * dt)

    quality = accuracy_at(signal_x, signal_y)
    score_total += quality
    score_samples += 1
    add_trace(quality)

    if signal_x >= END_X:
        last_score = int((score_total / max(1, score_samples)) * 100)
        state = GameState.COMPLETE
        level += 1

    draw_background()
    draw_trace()
    draw_signal()
    draw_hud()


def complete():
    draw_background()
    draw_trace()
    screen.font = large_font
    screen.pen = TEXT
    center_text("SYNC " + str(last_score) + "%", 78)
    screen.font = small_font
    screen.pen = SIGNAL
    center_text("B for next sweep", 134)

    if action_ready():
        reset_game()


def update():
    if state == GameState.INTRO:
        intro()
    elif state == GameState.PLAYING:
        play()
    elif state == GameState.COMPLETE:
        complete()


def on_exit():
    pass


init()
run(update)
