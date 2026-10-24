#!/usr/bin/env python3
"""Generate the original pixel art used by the Super Mona badge app.

Tiles and enemies are drawn here from ASCII sprites and simple shapes; the
player sheet is derived from the repository's flappy_mona Mona frames. Run from the repository root:

    python tools/build_super_mona_assets.py
"""

from pathlib import Path

from PIL import Image, ImageDraw


APP = Path(__file__).resolve().parents[1] / "badge/apps/super_mona"
ASSETS = APP / "assets"

PALETTE = {
    ".": (0, 0, 0, 0),
    "k": (16, 16, 24, 255),
    "d": (52, 48, 72, 255),
    "D": (88, 80, 116, 255),
    "p": (124, 92, 220, 255),
    "f": (255, 206, 170, 255),
    "w": (255, 255, 255, 255),
    "r": (228, 52, 52, 255),
    "R": (140, 24, 32, 255),
    "o": (248, 152, 40, 255),
    "y": (252, 216, 64, 255),
    "Y": (255, 244, 160, 255),
    "g": (64, 176, 64, 255),
    "G": (24, 112, 40, 255),
    "l": (148, 228, 96, 255),
    "n": (176, 104, 48, 255),
    "N": (112, 60, 24, 255),
    "m": (232, 160, 96, 255),
    "b": (196, 84, 32, 255),
    "B": (90, 30, 10, 255),
    "s": (196, 196, 208, 255),
    "S": (112, 112, 128, 255),
    "u": (64, 120, 220, 255),
    "U": (24, 52, 140, 255),
    "q": (168, 216, 255, 255),
}

# Tile sheet indices (16 columns x 4 rows of 8x8 cells). Keep in sync with
# badge/apps/super_mona/game.py.
TILE_ART = {
    1: """
llllllll
gglggglg
GgGGgGGg
nNnnnnNn
nnnmnnnn
nNnnnNnn
nnnnnnnn
nNnnmnnN
""",
    2: """
nnnnnNnn
nmnnnnnn
nnnNnnnm
nnnnnnnn
Nnnnmnnn
nnnnnnNn
nnmnnnnn
nnnnNnnn
""",
    3: """
bbbbbbbB
bbbbbbbB
BBBBBBBB
bbbBbbbb
bbbBbbbb
BBBBBBBB
bbbbbbbB
BBBBBBBB
""",
    4: """
Nyyyyyyn
yoowwoon
yowoowon
yoooowon
yooowoon
yooooooN
yooowoon
nNNNNNNN
""",
    5: """
NnnnnnnN
nmmmmmmN
nmNmmNmN
nmmmmmmN
nmmmmmmN
nmNmmNmN
nmmmmmmN
NNNNNNNN
""",
    6: """
mmmmmmmN
mnnnnnNN
mnnnnnNN
mnnnnnNN
mnnnnnNN
mnnnnnNN
mNNNNNNN
NNNNNNNN
""",
    7: """
kkkkkkkk
klggggGG
klggggGG
klggggGG
kkkkkkkk
.klgggGG
.klgggGG
.klgggGG
""",
    8: """
kkkkkkkk
GgggGGGk
GgggGGGk
GgggGGGk
kkkkkkkk
GgggGGk.
GgggGGk.
GgggGGk.
""",
    9: "\n".join([".klgggGG"] * 8),
    10: "\n".join(["GgggGGk."] * 8),
    11: "\n".join(["...sS..."] * 8),
    12: """
........
..GGGG..
.GlggGG.
.GggggG.
.GggggG.
..GGGG..
...sS...
...sS...
""",
    13: """
SSSSSSSS
ssssssss
sSssSssS
SSSSSSSS
.S..S..S
.S..S..S
S.S.S.S.
........
""",
    14: """
qUUUUUUU
UuuuuuuU
UuUuuuuU
UuuuuUuU
UuuuuuuU
UuuUuuuU
UuuuuuuU
UUUUUUUU
""",
    15: """
uuuuuuuU
uuuuuuuU
UUUUUUUU
uuuUuuuu
uuuUuuuu
UUUUUUUU
uuuuuuuU
UUUUUUUU
""",
}

# Mob sheet: 8 columns x 2 rows of 8x8 cells. Keep in sync with game.py/render.py.
MOB_ART = [
    # Row 0: bug walk1, bug walk2, bug squashed, shellbot walk1, shellbot walk2,
    # shell, shell (wiggle), power chip
    """
.k....k.
..k..k..
.rrrrrr.
rrwrrwrr
rrkrrkrr
rrrrrrrr
.RkRRkR.
k.k..k.k
""",
    """
.k....k.
..k..k..
.rrrrrr.
rrwrrwrr
rrkrrkrr
rrrrrrrr
.RkRRkR.
.k.kk.k.
""",
    """
........
........
........
........
........
.rrrrrr.
rkrrrrkr
.k.kk.k.
""",
    """
.....ss.
....swsS
...sssS.
.GgGgs..
GgGgGg..
GGGGGGs.
.s...s..
ss..ss..
""",
    """
.....ss.
....swsS
...sssS.
.GgGgs..
GgGgGg..
GGGGGGs.
..s..s..
..ss.ss.
""",
    """
........
..GGGG..
.GgGgGG.
GgGgGgGG
GGGGGGGG
ssssssss
.ssssss.
........
""",
    """
........
........
..GGGG..
.GgGgGG.
GgGgGgGG
GGGGGGGG
ssssssss
.s.ss.s.
""",
    """
.s.s.s..
skkkkkks
.kpqqpk.
skqwwqks
.kqwwqk.
skpqqpks
.kkkkkk.
.s.s.s..
""",
    # Row 1: star f0, f1, f2, 1-up heart, sparkle, debris, flag, empty
    """
...yy...
...yy...
yyyYYyyy
.yYYYYy.
..yYYy..
.yyyyyy.
.yy..yy.
y......y
""",
    """
...yy...
...yy...
..yYYy..
..yYYy..
..yYYy..
..yyyy..
..y..y..
..y..y..
""",
    """
...yy...
...yy...
...yy...
...Yy...
...Yy...
...yy...
...yy...
...yy...
""",
    """
.gg.gg..
glgggggk
glgggggk
gggggggk
.gggggk.
..gggk..
...gk...
........
""",
    """
...w....
.w.q.w..
..qwq...
wqwYwqw.
..qwq...
.w.q.w..
...w....
........
""",
    """
........
..bb....
.bbBb...
.bBBb...
..bb....
........
........
........
""",
    """
.......w
.....www
...wwpww
.wwwppww
...wwpww
.....www
.......w
........
""",
    """
........
........
........
........
........
........
........
........
""",
]


def art(text):
    rows = [row for row in text.strip("\n").splitlines()]
    return rows


def paint(img, rows, ox, oy):
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch not in PALETTE:
                raise ValueError("unknown palette key %r" % ch)
            if ch != ".":
                img.putpixel((ox + x, oy + y), PALETTE[ch])


def check(rows, width, height, name):
    if len(rows) != height or any(len(row) != width for row in rows):
        raise ValueError("%s must be %dx%d: %r" % (name, width, height, rows))


def hill(img):
    # 3x2 tiles at indices 16..21.
    layer = Image.new("RGBA", (24, 16), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.ellipse((0, 1, 23, 30), fill=PALETTE["G"])
    draw.ellipse((1, 2, 22, 30), fill=PALETTE["g"])
    draw.ellipse((8, 4, 11, 7), fill=PALETTE["G"])
    draw.ellipse((14, 7, 16, 9), fill=PALETTE["G"])
    draw.point((6, 9), fill=PALETTE["l"])
    draw.point((5, 10), fill=PALETTE["l"])
    for i in range(6):
        tile = layer.crop(((i % 3) * 8, (i // 3) * 8, (i % 3) * 8 + 8, (i // 3) * 8 + 8))
        place_tile(img, 16 + i, tile)


def bush(img):
    layer = Image.new("RGBA", (24, 8), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for cx, r in ((4, 4), (11, 5), (19, 4)):
        draw.ellipse((cx - r, 8 - r * 2 + 1, cx + r, 8 + r), fill=PALETTE["G"])
    for cx, r in ((4, 3), (11, 4), (19, 3)):
        draw.ellipse((cx - r, 8 - r * 2 + 1, cx + r, 8 + r), fill=PALETTE["l"])
        draw.ellipse((cx - r + 1, 8 - r * 2 + 3, cx + r, 8 + r), fill=PALETTE["g"])
    for i in range(3):
        place_tile(img, 22 + i, layer.crop((i * 8, 0, i * 8 + 8, 8)))


def cloud(img):
    layer = Image.new("RGBA", (24, 16), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for box in ((1, 6, 11, 15), (6, 1, 18, 13), (13, 5, 23, 15)):
        draw.ellipse(box, fill=PALETTE["q"])
    for box in ((1, 5, 11, 13), (6, 0, 18, 11), (13, 4, 23, 13)):
        draw.ellipse(box, fill=PALETTE["w"])
    for i in range(6):
        tile = layer.crop(((i % 3) * 8, (i // 3) * 8, (i % 3) * 8 + 8, (i // 3) * 8 + 8))
        place_tile(img, 25 + i, tile)


def castle(img):
    # 5x5 tiles at indices 31..55.
    layer = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    brick, mortar = PALETTE["b"], PALETTE["B"]

    def wall(x0, y0, x1, y1):
        draw.rectangle((x0, y0, x1, y1), fill=brick)
        for y in range(y0, y1 + 1, 4):
            draw.line((x0, y, x1, y), fill=mortar)
            offset = 0 if (y // 4) % 2 else 4
            for x in range(x0 + offset, x1 + 1, 8):
                draw.line((x, y, x, min(y + 3, y1)), fill=mortar)

    wall(0, 20, 39, 39)
    wall(8, 6, 31, 19)
    for x in (0, 8, 16, 24, 32):
        draw.rectangle((x + 4, 16, x + 7, 19), fill=(0, 0, 0, 0))
    for x in (8, 16, 24):
        draw.rectangle((x + 4, 2, x + 7, 5), fill=brick)
        draw.rectangle((x, 6, x + 3, 9), fill=brick)
    draw.rectangle((12, 9, 15, 15), fill=PALETTE["k"])
    draw.rectangle((24, 9, 27, 15), fill=PALETTE["k"])
    draw.rectangle((16, 28, 23, 39), fill=PALETTE["k"])
    draw.ellipse((16, 24, 23, 31), fill=PALETTE["k"])
    # Octocat banner over the gate.
    draw.rectangle((18, 2, 19, 5), fill=PALETTE["S"])
    draw.polygon(((20, 0), (26, 1), (20, 3)), fill=PALETTE["p"])
    for i in range(25):
        tile = layer.crop(((i % 5) * 8, (i // 5) * 8, (i % 5) * 8 + 8, (i // 5) * 8 + 8))
        place_tile(img, 31 + i, tile)


def place_tile(sheet, index, tile):
    sheet.alpha_composite(tile, ((index % 16) * 8, (index // 16) * 8))


def build_tiles():
    sheet = Image.new("RGBA", (128, 32), (0, 0, 0, 0))
    for index, text in TILE_ART.items():
        rows = art(text)
        check(rows, 8, 8, "tile %d" % index)
        paint(sheet, rows, (index % 16) * 8, (index // 16) * 8)
    hill(sheet)
    bush(sheet)
    cloud(sheet)
    castle(sheet)
    return sheet


FLAPPY_MONA = APP.parent / "flappy_mona/assets/mona.png"
# Player sheet columns, chosen from the 24x24 flappy_mona frames.
PLAYER_FRAMES = (2, 0, 3, 4, 1, 6, 7, 5)  # stand walk1 walk2 jump skid crouch dead climb
LUNA_COLOURS = {
    (109, 36, 170): (40, 160, 72),
    (36, 0, 170): (0, 92, 48),
    (73, 36, 85): (20, 64, 40),
}


def recolour(img, mapping):
    out = img.copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if a and (r, g, b) in mapping:
                px[x, y] = mapping[(r, g, b)] + (a,)
    return out


def build_players():
    """Mona and Luna, 16x16 cells: rows small/big Mona, small/big Luna."""
    src = Image.open(FLAPPY_MONA).convert("RGBA")
    sheet = Image.new("RGBA", (128, 64), (0, 0, 0, 0))
    for hero, colours in enumerate((None, LUNA_COLOURS)):
        for col, frame in enumerate(PLAYER_FRAMES):
            x, y = (frame % 7) * 24, (frame // 7) * 24
            cell = src.crop((x, y, x + 24, y + 24))
            if colours and frame != 7:
                cell = recolour(cell, colours)
            sheet.alpha_composite(cell.resize((12, 12), Image.NEAREST),
                                  (col * 16 + 2, hero * 32 + 4))
            sheet.alpha_composite(cell.resize((16, 16), Image.NEAREST),
                                  (col * 16, hero * 32 + 16))
    return sheet

def build_mobs():
    sheet = Image.new("RGBA", (64, 16), (0, 0, 0, 0))
    for index, text in enumerate(MOB_ART):
        rows = art(text)
        check(rows, 8, 8, "mob %d" % index)
        paint(sheet, rows, (index % 8) * 8, (index // 8) * 8)
    return sheet


def build_icon(players, tiles, mobs):
    scene = Image.new("RGBA", (24, 24), (92, 148, 252, 255))
    for x in range(0, 24, 8):
        scene.alpha_composite(tiles.crop((8, 0, 16, 4)), (x, 20))
    scene.alpha_composite(tiles.crop((32, 0, 40, 8)), (14, 1))
    scene.alpha_composite(players.crop((48, 16, 64, 32)), (1, 3))
    return scene

def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    tiles = build_tiles()
    players = build_players()
    mobs = build_mobs()
    tiles.save(ASSETS / "tiles.png", optimize=True)
    players.save(ASSETS / "players.png", optimize=True)
    mobs.save(ASSETS / "mobs.png", optimize=True)
    build_icon(players, tiles, mobs).save(APP / "icon.png", optimize=True)
    print("wrote", ASSETS)


if __name__ == "__main__":
    main()
