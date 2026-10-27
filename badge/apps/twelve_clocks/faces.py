"""Twelve native vector renderers, adapted from CodingTrain/12oclocks (MIT)."""

import gc
import random
from math import sin, cos, pi
from clockwork import FONT, CONTOURS, History, Life, clock_text, hour12, pixels

TAU = 2 * pi


def contours(char, ax=1, ay=0, bx=0, by=1):
    return [
        [vec2(int(path[i]) * ax + int(path[i + 1]) * bx,
              int(path[i]) * ay + int(path[i + 1]) * by)
         for i in range(0, len(path), 2)]
        for path in CONTOURS[char]
    ]


def hsv(hue):
    h = (hue % 360) / 60
    x = int(255 * (1 - abs(h % 2 - 1)))
    return color.rgb(*((255, x, 0), (x, 255, 0), (0, 255, x),
                       (0, x, 255), (x, 0, 255), (255, 0, x))[int(h)])


class Face:
    def __init__(self, index):
        self.index = index
        self.w, self.h = screen.width, screen.height
        self.white = color.rgb(255, 255, 255)
        self.black = color.rgb(0, 0, 0)
        self.red = color.rgb(255, 0, 0)
        self.dot = shape.circle(0, 0, 1)
        self.glyphs = {}
        self.outlines = {}
        self.cached = None
        self.cache_key = None
        self.history = History(random.randrange(72) * 5) if index == 3 else None
        self.life = Life() if index == 5 else None
        self.draw_face = (
            self.pendulum, self.overlaid, self.double_circle, self.colour_history,
            self.rotated, self.game_of_life, self.hand, self.zoom,
            self.mini_clocks, self.grid, self.rotating_pixels, self.cube,
        )[index]

    def glyph(self, char, transform, target=None, outline=False):
        if char == " ":
            return
        bank = self.outlines if outline else self.glyphs
        if char not in bank:
            path = shape.custom(*contours(char))
            bank[char] = path.stroke(0.43) if outline else path
        path = bank[char]
        path.transform = transform
        (screen if target is None else target).shape(path)

    def number(self, text, x, y, size, angle=0, target=None, outline=False):
        for i, char in enumerate(text):
            transform = (mat3().translate(x, y).rotate(angle).scale(size, size)
                         .translate(i * 6, 0))
            self.glyph(char, transform, target, outline)

    def circle(self, x, y, radius, target=None):
        self.dot.transform = mat3().translate(x, y).scale(radius, radius)
        (screen if target is None else target).shape(self.dot)

    def clear(self, gray=0):
        screen.pen = color.rgb(gray, gray, gray)
        screen.clear()

    def draw(self, h, m, s, now, phase, blink):
        self.draw_face(h, m, s, now, phase, blink)

    def pendulum(self, h, m, s, now, phase, blink):
        self.clear()
        angle = sin(phase * TAU / 2000) * 0.5
        # Fit the fixed 5px dot alphabet and swinging bob within the small LCD.
        scale = min(self.w / 320, self.h / 240)
        length = self.h - 50 * scale
        for text, direction, shade in (
            (clock_text(h, m), 1, 255),
            ("AM" if h < 12 else "PM", -1, 128),
        ):
            a = angle * direction
            screen.pen = color.rgb(shade, shade, shade)
            start = -60 if len(text) == 5 else -15
            for x, y in pixels(text):
                px = (start + x * 5 - 10) * scale
                py = length + (y * 5 - 15) * scale
                self.circle(self.w / 2 + px * cos(a) - py * sin(a),
                            px * sin(a) + py * cos(a), 2.5 * scale)

    def overlaid(self, h, m, s, now, phase, blink):
        self.clear()
        cell = self.h / 10 if self.w / self.h > 11 / 7 else self.w / 14
        weight = 1 if cell < 15 else 2
        cx, cy = self.w / 2 + cell / 2, self.h / 2 + cell / 2
        for n, text, pen in (
            (0, str(hour12(h)), self.red),
            (1, "%02d" % m, color.rgb(255, 255, 0)),
            (2, "%02d" % s, color.rgb(0, 0, 255)),
        ):
            screen.pen = pen
            radius = (cell - weight * n * 3) / 2
            ring = shape.circle(0, 0, radius).stroke(weight)
            start = -5.5 if len(text) == 2 else -2.5
            for x, y in pixels(text):
                ring.transform = mat3().translate(cx + (start + x) * cell,
                                                 cy - int(7 * cell / 2) + y * cell)
                screen.shape(ring)

    def double_circle(self, h, m, s, now, phase, blink):
        self.clear()
        text = clock_text(h, m) + " "
        if self.cache_key != text:
            self.cached = []
            step = min(self.w, self.h) / 20
            for x, y in pixels(text):
                i = 6 - y
                char, col = text[x // 6], x % 6
                padding = 1 if col < 4 and FONT[char][y] & (16 >> (col + 1)) else 0
                # Native ring sectors replace the source's pie + masking circles.
                self.cached.append(shape.arc(0, 0, step * (i + 2) - 0.5,
                                             step * (i + 3), x * 10,
                                             (x + 1) * 10 + padding))
            self.cache_key = text
            gc.collect()
        screen.pen = self.white
        # Source multiplies its 60s angle by radial_step=10: one turn per 6s.
        for cx in (0, self.w):
            transform = mat3().translate(cx, self.h / 2).rotate(phase * 360 / 6000)
            for arc in self.cached:
                arc.transform = transform
                screen.shape(arc)

    def colour_history(self, h, m, s, now, phase, blink):
        self.clear()
        self.history.update(now)
        cell = self.w / 80
        skew = cell * 0.3
        tile = shape.custom([vec2(0, 0), vec2(cell, skew),
                             vec2(cell, cell + skew), vec2(0, cell)]).stroke(1.25)
        for epoch, hue, age in self.history.entries():
            sec = epoch % 86400
            text = clock_text(sec // 3600, sec // 60 % 60, sec % 60)
            screen.pen = self.white if age == 0 else hsv(hue)
            ox = self.w / 2 - 23.5 * cell + age * 2 * cell
            oy = self.h / 2 - 9 * cell - age * 2 * cell
            if text[0] == " ":
                oy += 0.5 * skew
            for x, y in pixels(text):
                # The source advances characters by 5.5 rather than 6 skew units.
                tile.transform = mat3().translate(ox + x * cell,
                                                 oy + y * cell + (x - x // 6 * 0.5) * skew)
                screen.shape(tile)

    def rotated(self, h, m, s, now, phase, blink):
        self.clear(150)
        for value, size, angle, pen in (
            (hour12(h), self.h / 14, hour12(h) * 30, self.black),
            (m, self.h / 14 * 0.75, m * 6 + 90, self.white),
            (s, self.h / 28, s * 6 + 90, color.rgb(231, 0, 0)),
        ):
            text = str(value)
            screen.pen = pen
            for i, char in enumerate(text):
                transform = (mat3().translate(self.w / 2, self.h / 2)
                             .rotate(angle).scale(size, size)
                             .translate((i - (len(text) - 1) / 2) * 6 - 2.5, -3.5))
                self.glyph(char, transform)

    def game_of_life(self, h, m, s, now, phase, blink):
        text = clock_text(h, m, s)
        self.life.step(text)
        self.clear(31)
        cell = min(self.w / 63, self.h / 30)
        ox, oy = (self.w - int(cell * 63)) / 2, (self.h - int(cell * 30)) / 2
        screen.pen = color.rgb(150, 150, 150)
        # The pinned p5 source draws the pre-step buffer, then yellow seeds.
        for i, alive in enumerate(self.life.back):
            if alive:
                screen.rectangle(ox + int(cell * (i % 63) + 1),
                                 oy + int(cell * (i // 63) + 1),
                                 int(cell - 2), int(cell - 2))
        screen.pen = color.rgb(255, 255, 1)
        for x, y in pixels(text):
            r = int(cell - 1) / 2
            self.circle(ox + int((x + 8) * cell) + r,
                        oy + int((y + 11) * cell) + r, r)

    def hand(self, h, m, s, now, phase, blink):
        self.clear()
        dim = min(self.w, self.h)
        angle = s * 6 - 180
        unit = dim / 100
        screen.pen = color.rgb(100, 100, 100)
        for i, char in enumerate("AM" if h < 12 else "PM"):
            self.glyph(char, mat3().translate(self.w / 2, self.h / 2)
                       .rotate(angle).translate((i * 6 - 3) * unit, 0)
                       .scale(unit, unit).translate(-2.5, -2.5))
        for i, char in enumerate(clock_text(h, m)):
            if char == ":" and not blink:
                continue
            screen.pen = self.red if char == ":" else self.white
            self.glyph(char, mat3().translate(self.w / 2, self.h / 2)
                       .rotate(angle).translate(0, dim / 4 + i * dim / 20)
                       .scale(unit * 0.75, unit * 0.75 * 0.6).translate(-2.5, -2.5))

    def zoom(self, h, m, s, now, phase, blink):
        self.clear()
        wave = sin(phase * 1.5 / 1000)
        fit = min(1, self.w / 320, self.h / 140)
        for text, size, shade, x in (
            (str(hour12(h)), (6 + wave * 4) * fit, 177.5 + wave * 77.5, self.w / 4),
            ("%02d" % m, (6 - wave * 4) * fit, 177.5 - wave * 77.5, 3 * self.w / 4),
        ):
            screen.pen = color.rgb(int(shade), int(shade), int(shade))
            start = -6 if x > self.w / 2 else 0
            for i, char in enumerate(text):
                self.glyph(char, mat3().translate(x, self.h / 2).scale(size, size)
                           .translate(start + i * 6 - 2.5, -3.5))

    def mini_clocks(self, h, m, s, now, phase, blink):
        self.clear()
        cell = self.w / 35
        size = max(2, int(cell))
        if self.cached is None:
            self.cached = image(size, size)
            self.cached.antialias = image.X2
        tile = self.cached
        tile.pen = self.black
        tile.clear()
        tile.pen = self.white
        self.circle(size / 2, size / 2, size * 0.475, tile)
        tile.pen = self.black
        for value, cycle, length in ((hour12(h), 12, 0.2), (m, 60, 0.45)):
            a = value * TAU / cycle - pi / 2
            tile.line(size / 2, size / 2, size / 2 + cos(a) * size * length,
                      size / 2 + sin(a) * size * length)
        tile.pen = self.red
        arc = shape.arc(size / 2, size / 2, size * 0.35, size * 0.45,
                        s * 6 - 95, s * 6 - 85)
        tile.shape(arc)
        for x, y in pixels(clock_text(h, m)):
            screen.blit(tile, vec2(self.w / 2 + (x - 14) * cell - size / 2,
                                   self.h / 2 + (y - 3) * cell - size / 2))

    def grid_number(self, value, size, x, y, target=None, outline=False, leading=True):
        text = "%02d" % value if leading else "%2d" % value
        for i, char in enumerate(text):
            self.glyph(char, mat3().rotate(10).translate(x, y)
                       .scale(size, size).translate(i * 6, 0), target, outline)

    def grid(self, h, m, s, now, phase, blink):
        size = self.h / 80 * 0.85
        # A single active-face bitmap replaces 120 static digit draws per tick.
        if self.cached is None:
            self.cached = image(self.w, self.h)
            self.cached.antialias = image.X2
            self.cached.fill_rule = image.EVEN_ODD
            self.cached.pen = self.black
            self.cached.clear()
            self.cached.pen = color.rgb(90, 90, 90)
            for value in range(60):
                self.grid_number(value, size, (30 + value // 10 * 17) * size,
                                 value % 10 * 8 * size, self.cached)
        screen.blit(self.cached, vec2(0, 0))
        for value, pen, outline, leading in (
            (hour12(h), self.white, False, False), (m, self.white, True, True),
        ):
            screen.pen = pen
            self.grid_number(value, size, (30 + value // 10 * 17) * size,
                             value % 10 * 8 * size, outline=outline, leading=leading)
        x = (30 + s // 10 * 17 - 5.5) * size
        y = (s % 10 * 8 - 3.5) * size
        screen.pen = color.rgb(150, 0, 0)
        self.grid_number(s, size * 2, x, y, outline=True)
        a = pi / 18
        for i, char in enumerate("%02d" % s):
            for path in CONTOURS[char]:
                for j in range(0, len(path), 2):
                    px = x + (int(path[j]) + i * 6) * size * 2
                    py = y + int(path[j + 1]) * size * 2
                    qx, qy = px - size, py + size
                    screen.line(px * cos(a) - py * sin(a), px * sin(a) + py * cos(a),
                                qx * cos(a) - qy * sin(a), qx * sin(a) + qy * cos(a))
        screen.pen = self.red
        self.grid_number(s, size * 2, x - size, y + size)

    def rotating_pixels(self, h, m, s, now, phase, blink):
        self.clear(150)
        text = clock_text(h, m, s) + (" AM" if h < 12 else " PM")
        for front in (False, True):
            for col in range(55):
                char = text[col // 5]
                a = phase * TAU / 5000 - col * 3.5 * pi / 180
                rx, ry = cos(a), -sin(a)
                if front == (ry < 0):
                    continue
                shade = int(255 * (ry + 1) / 2)
                screen.pen = color.rgb(shade, shade, shade)
                for row, bits in enumerate(FONT[char]):
                    if bits & (16 >> (col % 5)):
                        self.circle(self.w / 2 + rx * self.w * 0.35,
                                    self.h * 0.4 + ry * self.h * 0.125
                                    + row * 5 * self.h / 200, 1.5 * self.h / 200)

    def cube(self, h, m, s, now, phase, blink):
        self.clear()
        scale = min(self.w, self.h) / 200
        c = cos(pi / 6)
        axes = ((c, 0.5, -c, 0.5), (c, 0.5, 0, 6 / 7),
                (c, -0.5, 0, 6 / 7))
        if self.cached is None:
            self.cached = []
            for ax, ay, bx, by in axes:
                bank = {}
                for char in "0123456789":
                    bank[char] = shape.custom(*contours(char, ax * 7 * scale,
                                                       ay * 7 * scale,
                                                       bx * 11 * scale,
                                                       by * 11 * scale))
                self.cached.append(bank)
        left, right, up = -77 * c, 77 * c, -66
        for text, axis, ox, oy, pen in (
            ("%02d" % s, 0, 0, 0, color.rgb(200, 200, 200, 127)),
            (str(hour12(h)), 1, 0, up, color.rgb(200, 200, 200, 127)),
            ("%02d" % m, 2, left, 38.5 + up, color.rgb(200, 200, 200, 127)),
            ("%02d" % m, 2, left + right, 77 + up, color.rgb(255, 255, 255, 127)),
            (str(hour12(h)), 1, left, 38.5 + up, color.rgb(255, 255, 255, 127)),
            ("%02d" % s, 0, 0, up, color.rgb(255, 0, 0, 127)),
        ):
            screen.pen = pen
            ax, ay, bx, by = axes[axis]
            for i, char in enumerate(text):
                path = self.cached[axis][char]
                path.transform = mat3().translate(
                    self.w * 0.5 + (ox + i * 42 * ax) * scale,
                    self.h * 0.45 + (oy + i * 42 * ay) * scale)
                screen.shape(path)
