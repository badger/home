# Original pixel art for The Octocat Trail, drawn for this app in the spirit
# of 1980s 8-bit educational games. Nothing here is traced or sampled from any
# commercial game. Sprites are rows of palette letters; "." is transparent.
# Pure Python: no badge globals, so the tests can import it.

BLACK, WHITE, GREEN, VIOLET, ORANGE, BLUE, NAVY, GREY, DKGREEN = range(9)
YELLOW, PINK, PURPLE, MAGENTA, AQUA, BROWN, LTBLUE, GOLD, PLUM = range(9, 18)

PALETTE = (
    (0, 0, 0),
    (255, 255, 255),
    (20, 245, 60),
    (255, 68, 253),
    (255, 106, 60),
    (20, 207, 253),
    (60, 50, 160),
    (156, 156, 156),
    (0, 150, 70),
    (255, 221, 0),
    (255, 170, 200),
    (120, 70, 230),
    (227, 30, 96),
    (114, 255, 208),
    (150, 90, 40),
    (190, 200, 255),
    (215, 150, 0),
    (70, 40, 140),
)
LETTERS = "KWGVOBNgDYPMRAbLym"


def green_rgb(rgb):
    """One colour as seen on a green phosphor monitor."""
    r, g, b = rgb
    if r == 0 and g == 0 and b == 0:
        return (0, 0, 0)
    lum = (r * 30 + g * 59 + b * 11) // 100
    level = 60 + lum * 195 // 255
    return (level // 6, level, level // 4)


def palette(green=False):
    if not green:
        return PALETTE
    return tuple(green_rgb(rgb) for rgb in PALETTE)


# ----- the party --------------------------------------------------------------
# The GitHub Ducky pulls the wagon. Two waddle frames, facing right.
DUCK = (
    (
        "......YYY...",
        ".....YYYYY..",
        ".....YYKYY..",
        ".....YYKYYOO",
        "Y....YYYYOO.",
        "YY....YYY...",
        "YYYYYYYYYY..",
        "YYyyyYYYYYY.",
        ".YYyyyYYYYY.",
        "..YYYYYYYY..",
        "...O...O....",
    ),
    (
        "............",
        "......YYY...",
        ".....YYYYY..",
        ".....YYKYY..",
        "Y....YYKYYOO",
        "YY...YYYYOO.",
        "YYY...YYY...",
        "YYYYYYYYYYY.",
        ".YYyyyyYYYY.",
        "..YYYYYYYY..",
        "....O.O.....",
    ),
)

# Covered wagon with Mona riding up front, facing right. Wheels are separate.
WAGON = (
    "...WWWWWWWW.......",
    "..WWLWWLWWWW......",
    ".WWWLWWLWWWW.M...M",
    ".WWWLWWLWWWW.MMMMM",
    ".WWWLWWLWWWW.PKPKP",
    ".WWWLWWLWWWW.PPPPP",
    "bbbbbbbbbbbbbbMMMb",
    "bOOOOOOOOOOOOOOOOb",
    "bbbbbbbbbbbbbbbbbb",
)
WHEEL = (
    (
        ".WWW.",
        "W.W.W",
        "WWWWW",
        "W.W.W",
        ".WWW.",
    ),
    (
        ".WWW.",
        "WW.WW",
        "W.W.W",
        "WW.WW",
        ".WWW.",
    ),
)
ROPE = ("bb",)

TOKEN_W = 32
TOKEN_H = 12


def token_parts(frame):
    """(sprite rows, x, y) parts of the wagon party, facing right."""
    frame &= 1
    return (
        (WAGON, 0, 0),
        (WHEEL[frame], 2, 7),
        (WHEEL[frame], 12, 7),
        (ROPE, 18, 8),
        (DUCK[frame], 20, 1),
    )


# Mona on foot for the hunt and the title screen. Two tentacle frames.
MONA = (
    (
        ".M........M.",
        ".MM......MM.",
        ".MMMMMMMMMM.",
        "MMMMMMMMMMMM",
        "MMPPPPPPPPMM",
        "MPWKPPPPWKPM",
        "MPKKPPPPKKPM",
        "MPPPPPPPPPPM",
        ".MPPPRRPPPM.",
        "..MMMMMMMM..",
        ".MMMMMMMMMM.",
        ".M.M.MM.M.M.",
        "M..M.MM.M..M",
    ),
    (
        ".M........M.",
        ".MM......MM.",
        ".MMMMMMMMMM.",
        "MMMMMMMMMMMM",
        "MMPPPPPPPPMM",
        "MPWKPPPPWKPM",
        "MPKKPPPPKKPM",
        "MPPPPPPPPPPM",
        ".MPPPRRPPPM.",
        "..MMMMMMMM..",
        ".MMMMMMMMMM.",
        ".MM.M..M.MM.",
        ".M..M..M..M.",
    ),
)

# ----- the hunt ------------------------------------------------------------
BUG = (
    (
        ".W.....W.",
        "..W.R.W..",
        "W..RRR..W",
        ".WRRKRRW.",
        "...RKR...",
        ".WRRKRRW.",
        "W..RRR..W",
    ),
    (
        ".W.....W.",
        "..W.R.W..",
        ".W.RRR.W.",
        "W.RRKRR.W",
        "...RKR...",
        "W.RRKRR.W",
        ".W.RRR.W.",
    ),
)
SLOP = (
    (
        "......AAAAA....V.",
        "....AAAAAAAAA.VVV",
        "...AAAAAAAAAAA.V.",
        "..AAAWKAAAAWKAA..",
        "..AAAKKAAAAKKAA..",
        ".AAAAAAAAAAAAAAA.",
        ".AAAAAKKKKKAAAAA.",
        "AAAAAAAAAAAAAAAAA",
        "AAAAAAAAAAAAAAAAA",
        ".AAAAAAAAAAAAAAA.",
        ".AA.AAAAA.AAAA.A.",
        ".A...AAA...AA....",
        ".....A...........",
    ),
    (
        ".................",
        ".....AAAAAAA..V..",
        "...AAAAAAAAAAVVV.",
        "..AAAWKAAAAWKAV..",
        ".AAAAKKAAAAKKAAA.",
        ".AAAAAAAAAAAAAAA.",
        "AAAAAAKKKKKAAAAAA",
        "AAAAAAAAAAAAAAAAA",
        "AAAAAAAAAAAAAAAAA",
        ".AAAAAAAAAAAAAAA.",
        "..AAAA.AAAAA.AA..",
        "...AA...AAA...A..",
        ".........A.......",
    ),
)
STAMP = (
    "GGGGG",
    "GWGWG",
    "GGWGG",
    "GWGWG",
    "GGGGG",
)

# ----- scenery --------------------------------------------------------------
TREE = (
    "..DDDD..",
    ".DGGDDD.",
    "DGGDDDDD",
    "DGDDDDDD",
    ".DDDDDD.",
    "..DDDD..",
    "...bb...",
    "...bb...",
)
FLAG = (
    "VV...",
    "VVVV.",
    "VVVVV",
    "VVV..",
    "W....",
    "W....",
    "W....",
    "W....",
)
FIRE = (
    (
        "....R....",
        "...ROR...",
        "..ROYOR..",
        "..OYYYO..",
        ".ROYWYOR.",
        ".OYYWYYO.",
        "bbOYYYObb",
        ".bbbbbbb.",
        "bb.....bb",
    ),
    (
        "...R.....",
        "...RO..R.",
        "..ROYOR..",
        ".ROYYYO..",
        ".OYYWYOR.",
        ".OYWWYYO.",
        "bbOYYYObb",
        ".bbbbbbb.",
        "bb.....bb",
    ),
)

_cache = {}


def compile_rows(rows):
    """Turn sprite rows into (width, height, runs) with runs (x, y, n, slot)
    grouped by colour so the renderer changes pens as rarely as possible."""
    width = 0
    runs = []
    for y in range(len(rows)):
        row = rows[y]
        if len(row) > width:
            width = len(row)
        x = 0
        n = len(row)
        while x < n:
            ch = row[x]
            if ch == ".":
                x += 1
                continue
            start = x
            while x < n and row[x] == ch:
                x += 1
            slot = LETTERS.find(ch)
            if slot < 0:
                raise ValueError("bad sprite letter %s" % ch)
            runs.append((start, y, x - start, slot))
    # Unique keys (sprites stay under 64x64), so the badge's unstable sort is still deterministic.
    runs.sort(key=lambda run: run[3] * 4096 + run[1] * 64 + run[0])
    return width, len(rows), tuple(runs)


def mirror_runs(width, runs):
    return tuple((width - x - n, y, n, slot) for x, y, n, slot in runs)


def sprite(rows, mirror=False):
    """Cached (width, height, runs) for sprite rows, optionally mirrored."""
    key = (id(rows), bool(mirror))
    hit = _cache.get(key)
    if hit is not None:
        return hit
    width, height, runs = compile_rows(rows)
    if mirror:
        runs = mirror_runs(width, runs)
    hit = (width, height, runs)
    _cache[key] = hit
    return hit


def size(rows):
    hit = sprite(rows)
    return hit[0], hit[1]
