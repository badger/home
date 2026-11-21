#!/usr/bin/env python3
"""Build the Traveling Creature app's Japanese font, pets and backgrounds."""

import argparse
import hashlib
from io import BytesIO
from pathlib import Path
import random
from urllib.request import urlopen
import zipfile

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "badge/apps/traveling_creature"
FONT_URL = "https://littlelimit.net/arc/k8x12/k8x12_bdf_2021-05-05.zip"
FONT_SHA256 = "305ab94915ec3c8e1ada08f493ee5bfdd21e2710a97d7c4d4272444d8e18ff40"
FONT_COLUMNS = 32
CELL_W = 8
CELL_H = 12
PET = 24

OUTLINE = (82, 58, 74)
EYE = (52, 36, 48)
WHITE = (255, 255, 255)
BLUSH = (255, 158, 178)
MOUTH = (232, 96, 110)
TEXT_TONES = {"ink": (70, 48, 62), "white": (255, 255, 255)}

SPECIES = {
    "mochi": {
        "colors": {"b": (255, 248, 242), "s": (238, 214, 220), "a": (255, 196, 210)},
        "eye": (6, 13),
        "mouth": 16,
        "art": (
            "............",
            "............",
            "............",
            "............",
            "............",
            "............",
            "...oo.......",
            "..oaao..oooo",
            "..oaabooobbb",
            ".obbbbbbbbbb",
            ".obwwbbbbbbb",
            "obbwbbbbbbbb",
            "obbbbbbbbbbb",
            "obbbbbbbbbbb",
            "obbbbbbbbbbb",
            "obbbbbbbbbbb",
            "obbppbbbbbbb",
            "obbbbbbbbbbb",
            "osbbbbbbbbbb",
            "osbbbbbbbbbb",
            ".osbbbbbbbbb",
            ".ossssbbbbbb",
            "..oossssssss",
            "....oooooooo",
        ),
    },
    "fuwa": {
        "colors": {"b": (220, 238, 255), "s": (168, 204, 244), "a": (255, 226, 120)},
        "eye": (6, 12),
        "mouth": 15,
        "art": (
            "............",
            "............",
            "...........o",
            "..........oa",
            "...........o",
            ".........ooo",
            ".......oobbb",
            "...oooobbbbb",
            "..obbbbbbbbb",
            "..obwwbbbbbb",
            ".obwbbbbbbbb",
            ".obbbbbbbbbb",
            "obbbbbbbbbbb",
            "obbbbbbbbbbb",
            "obbbbbbbbbbb",
            "obbppbbbbbbb",
            "obbbbbbbbbbb",
            "obbbbbbbbbbb",
            "osbbbbbbbbbb",
            ".osbbbbbbbbb",
            ".ossbbbbsbbb",
            "..ossoosssos",
            "...oo..ooo.o",
            "............",
        ),
    },
    "koro": {
        "colors": {
            "b": (250, 206, 146),
            "s": (222, 164, 104),
            "a": (198, 132, 86),
            "c": (255, 238, 206),
        },
        "eye": (6, 13),
        "mouth": 16,
        "art": (
            "............",
            "............",
            "............",
            ".ooo........",
            "obbbo.......",
            "obppbo......",
            "obppbooooooo",
            ".obpoaaaaaaa",
            "..oaaaaaaaaa",
            ".oaasaaaasaa",
            ".oasaaaaasaa",
            "oaasaaaaaaaa",
            "osssssssssss",
            "occccccccccc",
            "occccccccccc",
            "occccccccccc",
            "ocppcccccccc",
            "occccccccccc",
            "obcccccccccc",
            ".obbcccccccc",
            ".osbbbbbbbbb",
            "..ossssssbbb",
            "..oboooooooo",
            "...oo.......",
        ),
    },
    "peta": {
        "colors": {
            "b": (160, 224, 124),
            "s": (110, 184, 94),
            "a": (86, 156, 78),
            "c": (232, 250, 206),
        },
        "eye": (4, 9),
        "mouth": 15,
        "art": (
            "............",
            "..........oo",
            ".........oaa",
            "........oaaa",
            "........oaao",
            "..oooo...oo.",
            ".obbbbo....o",
            "obbbbbbooooo",
            "obbbbbbbbbbb",
            "obbbbbbbbbbb",
            "obbbbbbbbbbb",
            "obbbbbbbbbbb",
            ".obbbbbbbbbb",
            ".obbbbbbbbbb",
            "obbpbbbbbbbb",
            "obbbbbbbbbbb",
            "osbbbbbbbbbb",
            "obsbbccccccc",
            "oobbcccccccc",
            ".obbbccccccc",
            ".osbbbbbbccc",
            "..ossssbbbbb",
            "...oossooooo",
            "....oo......",
        ),
    },
}

KORO_BALL = (
    "............",
    "............",
    "............",
    "............",
    "............",
    ".......ooooo",
    ".....ooaaaaa",
    "....oaaasaaa",
    "...oaasaaasa",
    "..oaasaaasaa",
    "..oasaaasaaa",
    ".oaasaaasaaa",
    ".oasaaasaaaa",
    ".oasaaasaaaa",
    ".oasaaasaaaa",
    ".oaasaaasaaa",
    "..oasaaasaaa",
    "..oaasaaasaa",
    "...oaasaaasa",
    "....osssssss",
    ".....oosssss",
    ".......ooooo",
    "............",
    "............",
)

EGG = {
    "colors": {
        "b": (255, 246, 224),
        "s": (240, 214, 182),
        "a": (255, 184, 130),
        "c": (124, 200, 232),
    },
    "art": (
        "............",
        "............",
        "............",
        "..........oo",
        "........ooob",
        ".......obbbb",
        "......obwbbb",
        ".....obwbbbb",
        ".....obbbbbb",
        "....obbbbbbb",
        "....obbbbbbb",
        "...obbbbbbbb",
        "...obbbbbbbb",
        "...obbbbbbbb",
        "...obbbbbbbb",
        "...obbbbbbbb",
        "...osbbbbbbb",
        "...osbbbbbbb",
        "...ossbbbbbb",
        "....osssbbbb",
        ".....osssssb",
        "......oossss",
        "........oooo",
        "............",
    ),
    "spots": {
        "a": ((9, 6), (10, 6), (9, 7), (10, 7), (11, 7), (6, 15), (7, 15), (7, 16),
              (13, 18), (14, 18), (14, 19)),
        "c": ((16, 12), (17, 12), (16, 13), (17, 13), (18, 13), (17, 14)),
    },
    "cracks": (
        ((9, 10), (10, 11), (11, 10), (12, 9), (13, 10), (14, 11)),
        ((7, 10), (8, 9), (9, 10), (10, 11), (11, 10), (12, 9), (13, 10), (14, 11),
         (15, 10), (16, 9)),
        ((7, 10), (8, 9), (9, 10), (10, 11), (11, 10), (12, 9), (13, 10), (14, 11),
         (15, 10), (16, 9), (10, 12), (14, 12), (12, 8)),
    ),
}

ITEMS = {
    "star": (
        "...o....",
        "..oyo...",
        "ooyyyoo.",
        "oyyyyyo.",
        ".oyyyo..",
        ".oyoyo..",
        ".oo.oo..",
        "........",
    ),
    "flower": (
        "..oo....",
        ".opop...",
        "opoyopo.",
        ".opyyo..",
        "opoyopo.",
        ".opop...",
        "..oo....",
        "........",
    ),
    "bag": (
        "..ooo...",
        ".o...o..",
        "oooooooo",
        "orrrrrro",
        "orryyrro",
        "orrrrrro",
        "oooooooo",
        "........",
    ),
    "crown": (
        "........",
        "o..o..o.",
        "oyoyoyo.",
        "oyyyyyo.",
        "oyryryo.",
        "oyyyyyo.",
        "ooooooo.",
        "........",
    ),
    "heart": (
        "........",
        ".pp.pp..",
        "pwppppp.",
        "ppppppp.",
        ".ppppp..",
        "..ppp...",
        "...p....",
        "........",
    ),
    "sparkle": (
        "...y....",
        "...y....",
        "..yyy...",
        "yyywyyy.",
        "..yyy...",
        "...y....",
        "...y....",
        "........",
    ),
    "note": (
        "...ooo..",
        "...o.o..",
        "...o.o..",
        "...o.o..",
        ".ooo.o..",
        "oooo....",
        ".oo.....",
        "........",
    ),
    "swirl": (
        "........",
        ".oooo...",
        "o....o..",
        "o.oo.o..",
        "o.o..o..",
        "o..oo...",
        ".o......",
        "........",
    ),
}
ITEM_COLORS = {
    "o": OUTLINE,
    "y": (255, 214, 72),
    "p": (255, 128, 160),
    "r": (226, 92, 84),
    "w": WHITE,
}


def mirror(rows):
    full = []
    for row in rows:
        row = row[:12].ljust(12, ".")
        full.append(row + row[::-1])
    if len(full) != PET:
        raise ValueError("Pet art must have %d rows" % PET)
    return full


def paint(image, origin, rows, colors):
    ox, oy = origin
    for y, row in enumerate(rows):
        for x, key in enumerate(row):
            if key == ".":
                continue
            colour = colors.get(key)
            if colour is None:
                raise ValueError("Unknown colour key %r" % key)
            image.putpixel((ox + x, oy + y), colour + (255,))


def put(image, origin, points, colour):
    ox, oy = origin
    for x, y in points:
        image.putpixel((ox + x, oy + y), colour + (255,))


def face(image, origin, eye, mouth_y, expression, skin):
    ex, ey = eye
    for left in (ex, PET - 2 - ex):
        if expression == "normal":
            put(image, origin, [(left + dx, ey + dy) for dx in (0, 1) for dy in range(3)], EYE)
            put(image, origin, [(left, ey)], WHITE)
        elif expression == "blink":
            put(image, origin, [(left - 1, ey + 1), (left + 2, ey + 1), (left, ey + 2), (left + 1, ey + 2)], EYE)
        elif expression == "happy":
            put(image, origin, [(left - 1, ey + 2), (left + 2, ey + 2), (left, ey + 1), (left + 1, ey + 1)], EYE)
        elif expression == "dizzy":
            put(
                image,
                origin,
                [(left - 1, ey), (left + 2, ey), (left, ey + 1), (left + 1, ey + 1),
                 (left, ey + 2), (left + 1, ey + 2), (left - 1, ey + 3), (left + 2, ey + 3)],
                EYE,
            )
    if expression in ("normal", "blink"):
        put(image, origin, [(10, mouth_y), (13, mouth_y), (11, mouth_y + 1), (12, mouth_y + 1)], EYE)
    elif expression == "happy":
        put(image, origin, [(10, mouth_y), (11, mouth_y), (12, mouth_y), (13, mouth_y),
                            (10, mouth_y + 1), (13, mouth_y + 1), (11, mouth_y + 2), (12, mouth_y + 2)], EYE)
        put(image, origin, [(11, mouth_y + 1), (12, mouth_y + 1)], MOUTH)
    elif expression == "dizzy":
        put(image, origin, [(11, mouth_y), (12, mouth_y), (10, mouth_y + 1), (13, mouth_y + 1),
                            (11, mouth_y + 2), (12, mouth_y + 2)], EYE)


def build_pets():
    expressions = ("normal", "blink", "happy", "dizzy")
    sheet = Image.new("RGBA", (PET * len(expressions), PET * 5), (0, 0, 0, 0))
    for row, (name, data) in enumerate(SPECIES.items()):
        colors = {"o": OUTLINE, "w": WHITE, "p": BLUSH}
        colors.update(data["colors"])
        art = mirror(data["art"])
        for column, expression in enumerate(expressions):
            origin = (column * PET, row * PET)
            if name == "koro" and expression == "dizzy":
                paint(sheet, origin, mirror(KORO_BALL), colors)
                continue
            paint(sheet, origin, art, colors)
            face(sheet, origin, data["eye"], data["mouth"], expression, colors["b"])
    colors = {"o": OUTLINE, "w": WHITE}
    colors.update(EGG["colors"])
    egg = mirror(EGG["art"])
    for column in range(len(expressions)):
        origin = (column * PET, 4 * PET)
        paint(sheet, origin, egg, colors)
        for key, points in EGG["spots"].items():
            put(sheet, origin, points, colors[key])
        if column:
            put(sheet, origin, EGG["cracks"][column - 1], OUTLINE)
    return sheet


def build_items():
    sheet = Image.new("RGBA", (8 * len(ITEMS), 8), (0, 0, 0, 0))
    for index, rows in enumerate(ITEMS.values()):
        paint(sheet, (index * 8, 0), rows, ITEM_COLORS)
    return sheet


def vertical(draw, top, bottom, start, end, steps=6):
    height = bottom - top
    for step in range(steps):
        t = step / max(1, steps - 1)
        colour = tuple(round(a + (b - a) * t) for a, b in zip(start, end))
        y0 = top + height * step // steps
        y1 = top + height * (step + 1) // steps
        draw.rectangle((0, y0, 159, y1), fill=colour)


def cloud(draw, x, y, scale=1):
    for dx, dy, r in ((0, 4, 6), (8, 0, 8), (17, 4, 6), (8, 6, 7)):
        r *= scale
        cx = x + dx * scale
        cy = y + dy * scale
        draw.ellipse((cx - r, cy - r // 2, cx + r, cy + r // 2 + 2), fill=(255, 255, 255))


def tufts(draw, rng, top, bottom, colour, count):
    for _ in range(count):
        x = rng.randrange(0, 160)
        y = rng.randrange(top, bottom)
        draw.point((x, y), fill=colour)
        draw.point((x + 1, y - 1), fill=colour)
        draw.point((x - 1, y - 1), fill=colour)


def flower(draw, x, y, petal, centre=(255, 222, 90)):
    draw.point((x, y - 1), fill=petal)
    draw.point((x - 1, y), fill=petal)
    draw.point((x + 1, y), fill=petal)
    draw.point((x, y + 1), fill=petal)
    draw.point((x, y), fill=centre)


def background_house():
    image = Image.new("RGB", (160, 120), (252, 232, 214))
    draw = ImageDraw.Draw(image)
    for y in range(0, 84, 10):
        for x in range((y // 10) % 2 * 6, 160, 12):
            draw.rectangle((x, y + 4, x + 1, y + 5), fill=(246, 214, 200))
    draw.rectangle((0, 78, 159, 83), fill=(236, 196, 166))
    draw.line((0, 78, 159, 78), fill=(214, 168, 136))
    draw.rectangle((0, 84, 159, 119), fill=(216, 166, 118))
    for row, y in enumerate(range(84, 120, 6)):
        draw.line((0, y, 159, y), fill=(190, 140, 96))
        for x in range((row % 2) * 20, 160, 40):
            draw.line((x, y, x, y + 5), fill=(190, 140, 96))
    draw.rectangle((14, 20, 56, 60), fill=(150, 110, 92))
    draw.rectangle((16, 22, 54, 58), fill=(176, 222, 250))
    cloud(draw, 20, 32)
    draw.rectangle((34, 22, 35, 58), fill=(255, 250, 240))
    draw.rectangle((16, 39, 54, 40), fill=(255, 250, 240))
    for x0, x1 in ((8, 18), (52, 62)):
        draw.rectangle((x0, 16, x1, 64), fill=(255, 176, 190))
        for x in range(x0 + 2, x1, 4):
            draw.line((x, 16, x, 64), fill=(244, 150, 170))
    draw.rectangle((6, 14, 64, 16), fill=(160, 116, 96))
    draw.rectangle((108, 22, 140, 46), fill=(150, 110, 92))
    draw.rectangle((110, 24, 138, 44), fill=(255, 248, 230))
    for x, y, c in ((118, 32, (255, 140, 160)), (126, 36, (140, 200, 240)), (132, 30, (255, 210, 90))):
        draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=c)
    draw.ellipse((28, 94, 132, 110), fill=(240, 150, 150))
    draw.ellipse((32, 96, 128, 108), fill=(255, 196, 184))
    draw.polygon(((136, 82), (152, 82), (149, 98), (139, 98)), fill=(214, 120, 84))
    draw.rectangle((135, 80, 153, 83), fill=(190, 98, 70))
    for dx, dy in ((-4, -10), (4, -12), (0, -16), (-6, -4), (6, -6)):
        draw.ellipse((144 + dx - 4, 80 + dy - 3, 144 + dx + 4, 80 + dy + 3), fill=(110, 186, 104))
    return image


def background_meadow():
    image = Image.new("RGB", (160, 120))
    draw = ImageDraw.Draw(image)
    vertical(draw, 0, 72, (138, 202, 250), (214, 240, 255))
    draw.ellipse((128, 6, 150, 28), fill=(255, 238, 150))
    draw.ellipse((131, 9, 147, 25), fill=(255, 222, 96))
    cloud(draw, 8, 22)
    cloud(draw, 70, 12, 1)
    cloud(draw, 104, 40)
    draw.ellipse((-40, 56, 90, 110), fill=(166, 220, 150))
    draw.ellipse((60, 60, 210, 112), fill=(150, 210, 138))
    draw.rectangle((0, 84, 159, 119), fill=(128, 204, 104))
    draw.ellipse((-20, 78, 180, 96), fill=(128, 204, 104))
    rng = random.Random(7)
    tufts(draw, rng, 86, 120, (98, 178, 86), 70)
    for _ in range(16):
        flower(draw, rng.randrange(4, 156), rng.randrange(90, 118),
               rng.choice(((255, 255, 255), (255, 170, 200), (255, 226, 110))))
    return image


def background_desert():
    image = Image.new("RGB", (160, 120))
    draw = ImageDraw.Draw(image)
    vertical(draw, 0, 76, (150, 206, 240), (255, 232, 190))
    draw.ellipse((112, 8, 146, 42), fill=(255, 240, 180))
    draw.ellipse((118, 14, 140, 36), fill=(255, 210, 100))
    draw.polygon(((92, 70), (114, 46), (136, 70)), fill=(226, 184, 128))
    draw.polygon(((114, 46), (136, 70), (120, 70)), fill=(206, 160, 108))
    draw.ellipse((-30, 62, 100, 100), fill=(240, 202, 142))
    draw.ellipse((70, 66, 200, 104), fill=(232, 190, 126))
    draw.rectangle((0, 86, 159, 119), fill=(248, 216, 156))
    draw.ellipse((-20, 80, 180, 96), fill=(248, 216, 156))
    for y in range(92, 120, 6):
        for x in range((y // 6 % 2) * 8, 160, 18):
            draw.arc((x, y, x + 12, y + 4), 200, 340, fill=(226, 186, 124))
    green, dark = (112, 180, 112), (70, 124, 82)
    draw.rounded_rectangle((18, 52, 27, 98), 4, fill=green, outline=dark)
    draw.rounded_rectangle((8, 62, 15, 80), 3, fill=green, outline=dark)
    draw.rectangle((12, 76, 20, 81), fill=green)
    draw.rounded_rectangle((30, 58, 37, 74), 3, fill=green, outline=dark)
    draw.rectangle((25, 70, 33, 75), fill=green)
    for x, y in ((22, 60), (22, 72), (22, 86), (11, 68), (33, 64)):
        draw.point((x, y), fill=(240, 250, 220))
    draw.ellipse((40, 94, 56, 104), fill=(196, 160, 120))
    draw.ellipse((140, 100, 152, 108), fill=(196, 160, 120))
    return image


def background_garden():
    image = Image.new("RGB", (160, 120))
    draw = ImageDraw.Draw(image)
    vertical(draw, 0, 60, (160, 216, 250), (220, 242, 252))
    cloud(draw, 92, 12)
    for x in range(-6, 170, 18):
        draw.ellipse((x, 28, x + 26, 62), fill=(92, 168, 96))
        draw.ellipse((x + 4, 32, x + 16, 44), fill=(120, 190, 112))
    draw.rectangle((0, 50, 159, 86), fill=(92, 168, 96))
    for x in range(2, 160, 12):
        draw.polygon(((x, 52), (x + 4, 46), (x + 8, 52), (x + 8, 86), (x, 86)), fill=(252, 250, 242))
        draw.line((x + 8, 52, x + 8, 86), fill=(206, 200, 190))
    draw.rectangle((0, 60, 159, 63), fill=(236, 232, 222))
    draw.rectangle((0, 76, 159, 79), fill=(236, 232, 222))
    draw.rectangle((0, 84, 159, 119), fill=(136, 206, 112))
    rng = random.Random(11)
    tufts(draw, rng, 88, 120, (104, 180, 90), 60)
    for x in (8, 22, 136, 150):
        draw.line((x, 72, x, 88), fill=(76, 150, 76))
        draw.ellipse((x - 3, 66, x + 3, 73), fill=(255, 120, 140) if x % 4 else (255, 206, 80))
        draw.rectangle((x - 3, 66, x - 2, 67), fill=(255, 250, 240))
        draw.ellipse((x + 1, 78, x + 5, 82), fill=(96, 176, 86))
    for x, y in ((50, 104), (80, 112), (112, 104)):
        draw.ellipse((x - 9, y - 3, x + 9, y + 3), fill=(206, 204, 196))
        draw.ellipse((x - 7, y - 3, x + 7, y + 1), fill=(226, 224, 216))
    return image


def background_title():
    image = Image.new("RGB", (160, 120))
    draw = ImageDraw.Draw(image)
    vertical(draw, 0, 120, (255, 220, 232), (206, 214, 255), steps=8)
    rng = random.Random(3)
    for _ in range(22):
        x, y = rng.randrange(4, 156), rng.randrange(4, 80)
        draw.point((x, y), fill=WHITE)
        if rng.random() < 0.4:
            draw.point((x - 1, y), fill=WHITE)
            draw.point((x + 1, y), fill=WHITE)
            draw.point((x, y - 1), fill=WHITE)
            draw.point((x, y + 1), fill=WHITE)
    draw.ellipse((-30, 92, 190, 170), fill=(150, 214, 140))
    draw.ellipse((-20, 96, 180, 160), fill=(168, 226, 150))
    for _ in range(12):
        flower(draw, rng.randrange(8, 152), rng.randrange(102, 118),
               rng.choice(((255, 255, 255), (255, 170, 200), (255, 226, 110))))
    return image


def paletted(image, colours=48):
    return image.convert("RGB").quantize(colours, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)


def load_font(path=None):
    if path is None:
        with urlopen(FONT_URL, timeout=60) as response:
            data = response.read()
        digest = hashlib.sha256(data).hexdigest()
        if digest != FONT_SHA256:
            raise ValueError("Unexpected k8x12 archive checksum: " + digest)
        with zipfile.ZipFile(BytesIO(data)) as archive:
            text = archive.read("k8x12.bdf").decode("latin-1")
    else:
        text = Path(path).read_text("latin-1")
    glyphs = {}
    lines = iter(text.splitlines())
    for line in lines:
        if not line.startswith("STARTCHAR"):
            continue
        code = width = None
        bbx = None
        for line in lines:
            if line.startswith("ENCODING"):
                code = int(line.split()[1])
            elif line.startswith("DWIDTH"):
                width = int(line.split()[1])
            elif line.startswith("BBX"):
                bbx = tuple(int(value) for value in line.split()[1:])
            elif line == "BITMAP":
                rows = []
                for line in lines:
                    if line == "ENDCHAR":
                        break
                    rows.append(int(line, 16))
                glyphs[code] = (width, bbx, rows)
                break
    return glyphs


def used_characters():
    source = (APP / "__init__.py").read_text("utf-8")
    chars = {chr(code) for code in range(32, 127)}
    # Owner names arrive from other badges, so always include every kana.
    chars.update(chr(code) for code in range(0x3041, 0x3094))
    chars.update(chr(code) for code in range(0x30A1, 0x30F7))
    chars.update("ー・")
    chars.update(char for char in source if ord(char) > 127)
    chars.discard("\n")
    return sorted(chars, key=ord)


def build_font(glyphs):
    chars = used_characters()
    missing = [char for char in chars if ord(char) not in glyphs]
    if missing:
        raise ValueError("k8x12 lacks: " + "".join(missing))
    rows = (len(chars) + FONT_COLUMNS - 1) // FONT_COLUMNS
    sheets = {}
    for tone, colour in TEXT_TONES.items():
        sheet = Image.new("RGBA", (FONT_COLUMNS * CELL_W, rows * CELL_H), (0, 0, 0, 0))
        for index, char in enumerate(chars):
            _, (width, height, xoff, yoff), bitmap = glyphs[ord(char)]
            ox = (index % FONT_COLUMNS) * CELL_W + xoff
            oy = (index // FONT_COLUMNS) * CELL_H + (10 - height - yoff)
            bytes_wide = (width + 7) // 8
            for y, bits in enumerate(bitmap):
                for x in range(width):
                    if bits & (1 << (bytes_wide * 8 - 1 - x)):
                        sheet.putpixel((ox + x, oy + y), colour + (255,))
        sheets[tone] = sheet
    return chars, rows, sheets


def write(output, font_path=None):
    assets = output / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    chars, rows, sheets = build_font(load_font(font_path))
    for tone, sheet in sheets.items():
        sheet.save(assets / ("font_%s.png" % tone), optimize=True)
    (assets / "font.txt").write_text("%d\n%s" % (rows, "".join(chars)), "utf-8")
    build_pets().save(assets / "pets.png", optimize=True)
    build_items().save(assets / "items.png", optimize=True)
    for name, painter in (
        ("house", background_house),
        ("meadow", background_meadow),
        ("desert", background_desert),
        ("garden", background_garden),
        ("title", background_title),
    ):
        paletted(painter()).save(assets / ("bg_%s.png" % name), optimize=True)
    pets = build_pets()
    icon = Image.new("RGBA", (PET, PET), (255, 226, 236, 255))
    icon.alpha_composite(pets.crop((0, 0, PET, PET)), (0, 1))
    icon.convert("RGB").save(output / "icon.png", optimize=True)
    print("Wrote %d glyphs and art to %s" % (len(chars), assets))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=APP)
    parser.add_argument("--font", help="Use a local k8x12.bdf instead of downloading it")
    args = parser.parse_args()
    write(args.output, args.font)


if __name__ == "__main__":
    main()
