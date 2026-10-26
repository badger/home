# The Octocat Trail venue: an original top-down tile map inspired by the public
# Fort Mason Center campus layout (three piers, Landmark Buildings A-E, the
# Firehouse, the Great Meadow and the Gatehouse). Pure Python, no badge globals.

W = 104
H = 140
STEPS_PER_TILE = 8

WATER, LOT, GRASS, DECK, PATH, ROOF, FENCE, TREE, GANG1, GANG2, DOOR, DOCK, FLAG = range(13)
WALK = bytes((0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1))
END = 12

# (first column, first land row) from west to east.
SHORE = ((0, 116), (4, 66), (66, 64), (82, 52), (96, 56))
# (row, column) points of the plaza/meadow boundary: plaza west of it, meadow east.
EDGE = ((52, 96), (63, 87), (92, 72), (101, 66), (106, 59), (120, 25), (139, 25))

PIERS = ((5, 16, 13, 65), (34, 1, 45, 65), (66, 1, 80, 63))
SHEDS = ((7, 18, 11, 62), (36, 3, 43, 61), (68, 3, 78, 59))
BUILDINGS = (
    ("A", 6, 72, 11, 113),
    ("B", 15, 72, 22, 95),
    ("C", 25, 72, 32, 95),
    ("D", 46, 72, 53, 95),
    ("E", 56, 72, 63, 95),
    ("", 85, 53, 91, 57),
    ("", 5, 135, 11, 138),
)

# (name, short name, kind, door x, door y). Order is the stop index.
STOPS = (
    ("The Gatehouse (git init)", "Gatehouse", "store", 8, 135),
    ("The GitHub Shop", "GitHub Shop", "store", 11, 100),
    ("Open Source Zone", "OSS Zone", "sight", 18, 95),
    ("GitHub Central", "GH Central", "sight", 28, 95),
    ("Expert Center", "Experts", "sight", 49, 95),
    ("Career Corner", "Careers", "sight", 59, 95),
    ("The Firehouse (Hotfix HQ)", "Firehouse", "heal", 88, 57),
    ("Great Meadow (Recess)", "Meadow", "meadow", 72, 126),
    ("Merge Conflict River", "Merge River", "river", 14, 32),
    ("Gateway Pavilion Makerspace", "Makerspace", "store", 39, 61),
    ("Cowell Theater", "Cowell", "sight", 39, 3),
    ("DNS Propagation Rapids", "DNS Rapids", "river", 46, 36),
    ("Festival Pavilion: GitHub Universe Mainstage", "Mainstage", "end", 73, 59),
)
START = (8, 135)

PATHS = (
    ((61, 105), (70, 110), (77, 102), (88, 85), (95, 78), (103, 71)),
    ((70, 110), (76, 117), (83, 128), (84, 139)),
    ((61, 131), (73, 128), (83, 128), (90, 131), (94, 137), (96, 139)),
    ((103, 120), (96, 125), (83, 128)),
)
TREES = (
    (88, 64), (91, 67), (88, 67), (94, 69), (98, 63), (97, 66), (100, 60), (102, 64),
    (94, 80), (97, 78), (96, 85), (92, 87), (95, 91), (90, 93), (87, 97), (84, 100),
    (81, 103), (84, 105), (79, 106), (89, 102), (96, 97), (99, 95),
    (2, 117), (3, 120), (1, 123), (21, 139), (24, 138), (30, 137),
    (44, 131), (40, 126), (90, 120), (101, 108), (63, 118),
)

_grid = None
_stops = None


def _shore(x):
    first = 0
    for x0, row in SHORE:
        if x >= x0:
            first = row
    return first


def _edge16(y):
    if y <= EDGE[0][0]:
        return EDGE[0][1] * 16
    for i in range(1, len(EDGE)):
        y1, x1 = EDGE[i]
        if y <= y1:
            y0, x0 = EDGE[i - 1]
            return x0 * 16 + ((x1 - x0) * 16 * (y - y0)) // (y1 - y0)
    return EDGE[-1][1] * 16


def _fill(g, x0, y0, x1, y1, code):
    for y in range(y0, y1 + 1):
        row = y * W
        for x in range(x0, x1 + 1):
            g[row + x] = code


def _line(g, a, b, code):
    x, y = a
    x1, y1 = b
    while True:
        i = y * W + x
        if g[i] in (LOT, GRASS):
            g[i] = code
        if x == x1 and y == y1:
            return
        dx = x1 - x
        dy = y1 - y
        if abs(dx) * abs(b[1] - a[1]) >= abs(dy) * abs(b[0] - a[0]) and dx:
            x += 1 if dx > 0 else -1
        else:
            y += 1 if dy > 0 else -1


def build():
    g = bytearray(W * H)
    shore = [_shore(x) for x in range(W)]
    for y in range(H):
        edge = _edge16(y)
        row = y * W
        for x in range(W):
            if y >= shore[x]:
                g[row + x] = LOT if x * 16 < edge else GRASS
    for x0, y0, x1, y1 in PIERS:
        _fill(g, x0, y0, x1, y1, DECK)
    for x0, y0, x1, y1 in SHEDS:
        _fill(g, x0, y0, x1, y1, ROOF)
    for building in BUILDINGS:
        _fill(g, building[1], building[2], building[3], building[4], ROOF)
    for points in PATHS:
        for k in range(1, len(points)):
            _line(g, points[k - 1], points[k], PATH)
    for x, y in TREES:
        i = y * W + x
        if g[i] in (LOT, GRASS):
            g[i] = TREE
    for stop in STOPS:
        if stop[2] != "river":
            g[stop[4] * W + stop[3]] = FLAG if stop[2] == "meadow" else DOOR
    return g


def grid():
    global _grid
    if _grid is None:
        _grid = build()
    return _grid


def terrain(x, y):
    if x < 0 or y < 0 or x >= W or y >= H:
        return WATER
    return grid()[y * W + x]


def passable(code, deployed=0):
    if WALK[code]:
        return True
    return False


def walkable(x, y, deployed=0):
    if x < 0 or y < 0 or x >= W or y >= H:
        return False
    return passable(grid()[y * W + x], deployed)


def stop_at(x, y):
    global _stops
    if _stops is None:
        _stops = {}
        for i in range(len(STOPS)):
            _stops[STOPS[i][4] * W + STOPS[i][3]] = i
    if x < 0 or y < 0 or x >= W or y >= H:
        return -1
    return _stops.get(y * W + x, -1)
