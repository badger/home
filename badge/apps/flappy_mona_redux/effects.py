import math
import random

import ui
from world import WIDTH

MAX_SPARKLES = 48
POPUP_SECONDS = 1.2
POPUP_SIZE = 20
POPUP_TOP = 36  # keeps the popup clear of the score panel when she is near the top
PALETTE = ((255, 214, 80), (255, 244, 170), (255, 160, 50), (255, 255, 255))

sparkles = []  # [x, y, vx, vy, age, life, size, colour index]
popup = None  # [text, x, y, age]


def clear():
    global popup
    del sparkles[:]
    popup = None


def burst(x, y, count=18):
    for _ in range(count):
        if len(sparkles) >= MAX_SPARKLES:
            return
        angle = random.random() * 6.283
        speed = 40 + random.random() * 90
        sparkles.append(
            [
                x,
                y,
                math.cos(angle) * speed,
                math.sin(angle) * speed,
                0.0,
                0.5 + random.random() * 0.4,
                2 + random.randint(0, 2),
                random.randint(0, len(PALETTE) - 1),
            ]
        )


def trail(x, y):
    if len(sparkles) >= MAX_SPARKLES:
        return
    sparkles.append(
        [
            x + random.randint(-6, 6),
            y + random.randint(-16, 16),
            -50 - random.random() * 30,
            random.randint(-14, 14),
            0.0,
            0.35 + random.random() * 0.25,
            2,
            random.randint(0, len(PALETTE) - 1),
        ]
    )


def show_popup(text, x, y):
    global popup
    popup = [text, x, y, 0.0]


def update(dt):
    global popup
    alive = []
    for s in sparkles:
        s[4] += dt
        if s[4] < s[5]:
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[3] += 60 * dt
            alive.append(s)
    sparkles[:] = alive

    if popup is not None:
        popup[3] += dt
        popup[2] -= 24 * dt
        if popup[3] > POPUP_SECONDS:
            popup = None


def draw(cam=0):
    for s in sparkles:
        r, g, b = PALETTE[s[7]]
        screen.pen = color.rgb(r, g, b, int(255 * (1 - s[4] / s[5])))
        screen.rectangle(int(s[0]), int(s[1]) + cam, s[6], s[6])

    if popup is not None:
        text, x, y, age = popup
        alpha = int(255 * min(1.0, (POPUP_SECONDS - age) / 0.4))
        ui.text_mode()
        width, _ = ui.measure(text, POPUP_SIZE)
        left = max(8, min(WIDTH - 8 - width, x - width / 2))
        y = max(POPUP_TOP, y)
        ui.outlined_text(text, left, y, POPUP_SIZE, color.rgb(255, 214, 80, alpha), color.rgb(22, 44, 96, alpha), 1)
        ui.pixel_mode()
