# The Octocat Trail venue: an original top-down tile map inspired by the public
# Fort Mason Center campus layout (three piers, Landmark Buildings A-E, the
# Firehouse, the Great Meadow and the Gatehouse). Pure Python, no badge globals.

W = 104
H = 140

WATER, LOT, GRASS, DECK, PATH, ROOF, FENCE, TREE, GANG1, GANG2, DOOR, DOCK, FLAG = range(13)

# (first column, first land row) from west to east.
SHORE = ((0, 116), (4, 66), (66, 64), (82, 52), (96, 56))
# (row, column) points of the plaza/meadow boundary: plaza west of it, meadow east.
EDGE = ((52, 96), (63, 87), (92, 72), (101, 66), (106, 59), (120, 25), (139, 25))

_grid = None


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


def build():
    g = bytearray(W * H)
    shore = [_shore(x) for x in range(W)]
    for y in range(H):
        edge = _edge16(y)
        row = y * W
        for x in range(W):
            if y >= shore[x]:
                g[row + x] = LOT if x * 16 < edge else GRASS
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
