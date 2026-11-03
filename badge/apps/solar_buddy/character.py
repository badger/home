"""Small vector/pixel character: no sprite downloads or large assets."""

import math


class Buddy:
    def __init__(self):
        self.phase = 0.0
        self.blink_ms = 900.0

    def advance(self, delta_ms):
        self.phase = (self.phase + max(0, delta_ms) / 1000.0) % (2 * math.pi * 100)
        self.blink_ms = (self.blink_ms + max(0, delta_ms)) % 4200

    def draw(self, painter, x, y, mood, awake=False):
        p = painter
        accent = {"excited": "#f2cc60", "happy": "#e3b341", "neutral": "#c9a64d",
                  "sleepy": "#7891b0", "offline": "#8b949e"}[mood]
        speed = 5 if mood == "excited" else 2
        bob = math.sin(self.phase * speed) * (4 if mood == "excited" else 2)
        y += bob
        p.rect(x - 24, y + 34 - bob, 48, 3, "#21262d")
        rays = ((-34, -22, 7, 7), (-5, -38, 10, 9), (27, -22, 7, 7),
                (-42, -4, 9, 8), (33, -4, 9, 8),
                (-34, 20, 7, 7), (-5, 29, 10, 7), (27, 20, 7, 7))
        for rx, ry, w, h in rays:
            p.rect(x + rx, y + ry, w, h, accent)
        p.rect(x - 22, y - 28, 44, 56, accent)
        p.rect(x - 28, y - 22, 56, 44, accent)
        p.rect(x - 20, y - 24, 40, 4, "#ffe8a3" if mood != "offline" else "#b1bac4")
        p.rect(x - 27, y + 12, 4, 10, "#26303c")
        p.rect(x + 23, y + 12, 4, 10, "#26303c")
        ink = "#0d1117"
        closed = self.blink_ms < 130 or (mood == "sleepy" and not awake)
        for eye_x in (x - 11, x + 11):
            if mood == "offline":
                p.line(eye_x - 3, y - 7, eye_x + 3, y - 1, ink)
                p.line(eye_x - 3, y - 1, eye_x + 3, y - 7, ink)
            elif closed:
                p.rect(eye_x - 4, y - 3, 8, 2, ink)
            else:
                p.rect(eye_x - 3, y - 8, 6, 9, ink)
                p.rect(eye_x - 2, y - 7, 2, 3, "#ffffff")
        if mood in ("excited", "happy") or awake:
            p.rect(x - 9, y + 8, 3, 4, ink)
            p.rect(x + 6, y + 8, 3, 4, ink)
            p.rect(x - 6, y + 12, 12, 3, ink)
            if mood == "excited":
                p.rect(x - 5, y + 9, 10, 3, ink)
        elif mood == "sleepy":
            p.rect(x - 3, y + 9, 6, 5, ink)
            if not awake:
                p.text("z Z", x + 45, y - 25, "#8b949e")
        elif mood == "offline":
            p.rect(x - 7, y + 12, 14, 2, ink)
            p.text("?", x + 44, y - 28, "#f85149")
        else:
            p.rect(x - 7, y + 10, 14, 2, ink)
        if mood == "excited":
            for dx, dy in ((-59, -17), (56, 16)):
                p.line(x + dx - 3, y + dy, x + dx + 3, y + dy, "#f2cc60")
                p.line(x + dx, y + dy - 3, x + dx, y + dy + 3, "#f2cc60")
