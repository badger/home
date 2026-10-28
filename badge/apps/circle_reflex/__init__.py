"""Time your taps to the spinning needle and clear all 50 targets."""

import math
import os
import random
import sys


APP_DIR = "/system/apps/circle_reflex"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

screen.font = font.sins
screen.antialias = image.X2

BACKGROUND = color.rgb(13, 17, 23)
RING = color.rgb(72, 83, 96)
DIM = color.rgb(139, 148, 158)
TEXT = color.rgb(240, 246, 252)
NEEDLE = color.rgb(255, 190, 62)
TARGET = color.rgb(87, 242, 165)

STARTING_TARGETS = 50
STARTING_SPEED = 1.7
SPEED_STEP = 0.07
MAX_SPEED = 5.2
HIT_TOLERANCE = 0.18
MAX_FRAME_MS = 50
MIN_TARGET_GAP = 0.55
FIRST_TARGET_MIN_GAP = math.pi / 2
TARGET_RADIUS = 5
NEEDLE_TIP_RADIUS = 2

cx = screen.width / 2
cy = screen.height / 2
radius = min(screen.width, screen.height) * 0.34
needle_angle = -math.pi / 2
direction = 1
speed = STARTING_SPEED
remaining = STARTING_TARGETS
target_angle = 0
state = "playing"


def wrap_angle(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


def crossed_target(previous_angle, current_angle):
    travelled = direction * wrap_angle(current_angle - previous_angle)
    clear_angle = 2 * math.asin((TARGET_RADIUS + NEEDLE_TIP_RADIUS) / (2 * radius))
    far_edge = target_angle + direction * clear_angle
    distance = direction * wrap_angle(far_edge - previous_angle) % (2 * math.pi)
    return 0 <= distance <= travelled


def new_target(previous_target, minimum_gap=MIN_TARGET_GAP):
    global target_angle
    distance = minimum_gap + random.random() * (math.pi - minimum_gap)
    target_angle = wrap_angle(previous_target + direction * distance)


def restart():
    global needle_angle, direction, speed, remaining, state
    needle_angle = -math.pi / 2
    direction = 1
    speed = STARTING_SPEED
    remaining = STARTING_TARGETS
    state = "playing"
    new_target(needle_angle, FIRST_TARGET_MIN_GAP)


def centred(text, x, y, pen, typeface):
    screen.font = typeface
    width, height = screen.measure_text(text)
    screen.pen = pen
    screen.text(text, x - width / 2, y - height / 2)


def draw_game():
    screen.pen = BACKGROUND
    screen.rectangle(screen.clip)

    screen.pen = RING
    screen.circle(vec2(cx, cy), radius + 2)
    screen.pen = BACKGROUND
    screen.circle(vec2(cx, cy), radius - 1)

    target_x = cx + math.cos(target_angle) * radius
    target_y = cy + math.sin(target_angle) * radius
    screen.pen = TARGET
    screen.circle(vec2(target_x, target_y), TARGET_RADIUS)
    screen.pen = BACKGROUND
    screen.circle(vec2(target_x, target_y), 2)

    tip_x = cx + math.cos(needle_angle) * radius
    tip_y = cy + math.sin(needle_angle) * radius
    screen.pen = NEEDLE
    screen.line(vec2(cx, cy), vec2(tip_x, tip_y))
    screen.circle(vec2(tip_x, tip_y), NEEDLE_TIP_RADIUS)

    screen.pen = RING
    screen.circle(vec2(cx, cy), 21)
    screen.pen = BACKGROUND
    screen.circle(vec2(cx, cy), 18)

    centred("ARROW AT TARGET", cx, 7, DIM, font.sins)
    centred("%02d" % remaining, cx, cy - 6, TEXT, font.futile)
    centred("LEFT", cx, cy + 14, DIM, font.sins)
    centred("SPEED %.1f" % speed, cx, screen.height - 7, DIM, font.sins)

    if state != "playing":
        screen.pen = BACKGROUND
        screen.rectangle(0, cy - 31, screen.width, 62)
        if state == "won":
            centred("PERFECT!", cx, cy - 20, TARGET, font.futile)
        else:
            centred("GREAT RUN!", cx, cy - 20, TARGET, font.futile)
        centred("%02d LEFT" % remaining, cx, cy - 1, TEXT, font.futile)
        centred("%02d TARGETS HIT" % (STARTING_TARGETS - remaining), cx, cy + 16, DIM, font.sins)
        centred("SELECT TO PLAY AGAIN", cx, cy + 28, TEXT, font.sins)


def update():
    global needle_angle, direction, speed, remaining, state

    if state != "playing":
        if badge.pressed(BUTTON_SELECT):
            restart()
    else:
        dt = min(badge.ticks_delta, MAX_FRAME_MS) / 1000
        previous_angle = needle_angle
        needle_angle = wrap_angle(needle_angle + direction * speed * dt)

        if (badge.pressed(BUTTON_UP) or badge.pressed(BUTTON_DOWN)
                or badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_RIGHT)):
            error = abs(wrap_angle(needle_angle - target_angle))
            if error <= HIT_TOLERANCE:
                remaining -= 1
                direction = -direction
                speed = min(MAX_SPEED, speed + SPEED_STEP)
                if remaining == 0:
                    state = "won"
                else:
                    new_target(target_angle)
            else:
                state = "missed"
        elif crossed_target(previous_angle, needle_angle):
            state = "missed"

    draw_game()


new_target(needle_angle, FIRST_TARGET_MIN_GAP)
run(update)
