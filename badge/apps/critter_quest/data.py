import random

# name: (type, power, accuracy, effect)
MOVES = {
    "TACKLE": ("NORMAL", 35, 95, None),
    "SCRATCH": ("NORMAL", 40, 100, None),
    "PECK": ("AIR", 35, 100, None),
    "GUST": ("AIR", 40, 100, None),
    "ZAP": ("ELECTRIC", 40, 100, None),
    "BOLT RUSH": ("ELECTRIC", 65, 95, None),
    "QUICK DASH": ("NORMAL", 45, 100, None),
    "VINE LASH": ("GRASS", 40, 100, None),
    "SEED BURST": ("GRASS", 60, 95, None),
    "SPLASH JET": ("WATER", 40, 100, None),
    "TIDE CRASH": ("WATER", 60, 95, None),
    "CINDER": ("FIRE", 40, 100, None),
    "FLARE DIVE": ("FIRE", 60, 95, None),
    "PEBBLE TOSS": ("ROCK", 40, 95, None),
    "BOULDER": ("ROCK", 60, 90, None),
    "GROWL": ("NORMAL", 0, 100, ("atk", -1)),
    "SCOWL": ("NORMAL", 0, 100, ("def", -1)),
    "HUNKER": ("ROCK", 0, 100, ("def", 1)),
}

# name: (type, hp, atk, def, spd, exp, [(level, move), ...])
SPECIES = {
    "VOLTPUP": ("ELECTRIC", 40, 55, 35, 90, 80,
                [(1, "TACKLE"), (1, "GROWL"), (4, "ZAP"), (9, "QUICK DASH"), (13, "BOLT RUSH")]),
    "LEAFLING": ("GRASS", 45, 48, 50, 40, 60,
                 [(1, "TACKLE"), (1, "GROWL"), (4, "VINE LASH"), (11, "SEED BURST")]),
    "PUDDLEFIN": ("WATER", 45, 48, 48, 55, 64,
                  [(1, "TACKLE"), (3, "SPLASH JET"), (6, "SCOWL"), (12, "TIDE CRASH")]),
    "EMBERBAT": ("FIRE", 40, 58, 35, 70, 70,
                 [(1, "SCRATCH"), (3, "CINDER"), (7, "SCOWL"), (12, "FLARE DIVE")]),
    "PEBBLET": ("ROCK", 50, 55, 70, 25, 66,
                [(1, "TACKLE"), (1, "HUNKER"), (4, "PEBBLE TOSS"), (12, "BOULDER")]),
    "FLUFFWING": ("AIR", 40, 45, 40, 65, 55,
                  [(1, "PECK"), (1, "GROWL"), (5, "GUST"), (10, "QUICK DASH")]),
}

# attacker type -> {defender type: multiplier}
TYPE_CHART = {
    "NORMAL": {"ROCK": 0.5},
    "ELECTRIC": {"WATER": 2, "AIR": 2, "GRASS": 0.5, "ROCK": 0.5, "ELECTRIC": 0.5},
    "GRASS": {"WATER": 2, "ROCK": 2, "FIRE": 0.5, "GRASS": 0.5, "AIR": 0.5},
    "WATER": {"FIRE": 2, "ROCK": 2, "GRASS": 0.5, "WATER": 0.5},
    "FIRE": {"GRASS": 2, "WATER": 0.5, "ROCK": 0.5, "FIRE": 0.5},
    "ROCK": {"FIRE": 2, "AIR": 2},
    "AIR": {"GRASS": 2, "ELECTRIC": 0.5, "ROCK": 0.5},
}


def effectiveness(move_type, target_type):
    return TYPE_CHART.get(move_type, {}).get(target_type, 1)


def xp_for(level):
    return level * level * level * 4 // 5


def max_hp(c):
    return (2 * SPECIES[c["sp"]][1] * c["lv"]) // 100 + c["lv"] + 10


def stat(c, index):
    # index: 2 = atk, 3 = def, 4 = spd
    return (2 * SPECIES[c["sp"]][index] * c["lv"]) // 100 + 5


def moves_at(species, level):
    return [m for (lv, m) in SPECIES[species][6] if lv <= level][-4:]


def new_critter(species, level):
    c = {"sp": species, "lv": level, "xp": xp_for(level), "moves": moves_at(species, level)}
    c["hp"] = max_hp(c)
    return c


# ---------------------------------------------------------------- world map
#  . grass   , tall grass   : path   * flowers   ~ water   T tree   F fence
#  R roof    W wall   w window   D home door   C clinic door   + clinic sign
#  S sign
MAP = [
    "TTTTTTTTTTTTTTTTTTTTTTTTTTTTTT",
    "T............................T",
    "T..RRRR......RRRRR...*****...T",
    "T..RRRR......RRRRR...*****...T",
    "T..WwwW......WW+WW...........T",
    "T..WDwW......WWCWW...........T",
    "T...:..........:.............T",
    "T...::::::::::::::::::::.....T",
    "T.S....................:.....T",
    "TFFFFF.................:.....T",
    "T~~~~.......,,,,,,,,...:.....T",
    "T~~~~~......,,,,,,,,...:.....T",
    "T~~~~~......,,,,,,,,...:..TT.T",
    "T~~~~.......,,,,,,,,...:..TT.T",
    "T...........,,,,,,,,...:.....T",
    "T***........S..........:.....T",
    "T..............:::::::::.....T",
    "T..............:.............T",
    "T,,,,,,,,,,,,,.:.,,,,,,,,,,,,T",
    "T,,,,,,,,,,,,,.:.,,,,,,,,,,,,T",
    "T,,,,,,,,,,,,,.:.,,,,,,,,,,,,T",
    "T.......TT.....:.....TT......T",
    "T..............S.............T",
    "TTTTTTTTTTTTTTTTTTTTTTTTTTTTTT",
]
MAP_W = len(MAP[0])
MAP_H = len(MAP)

WALKABLE = ".,:*"

START = (4, 6)
NPC_POS = (27, 8)

SIGNS = {
    (2, 8): "AMBERVALE TOWN\nA quiet town under a golden sky.",
    (12, 15): "ROUTE 1\nWild critters live in the tall grass!",
    (15, 22): "ROUTE 2\nThe path ahead is still being built. Check back soon!",
}


def tile(x, y):
    if 0 <= y < MAP_H and 0 <= x < MAP_W:
        return MAP[y][x]
    return "T"


def encounter(y):
    # North meadow is gentle; the southern fields are wilder.
    if y < 16:
        table = (("LEAFLING", 2, 4), ("FLUFFWING", 2, 4), ("PEBBLET", 3, 4), ("PUDDLEFIN", 3, 4))
    else:
        table = (("EMBERBAT", 4, 7), ("PEBBLET", 5, 7), ("PUDDLEFIN", 4, 6), ("LEAFLING", 5, 7))
    sp, lo, hi = table[random.randint(0, len(table) - 1)]
    return new_critter(sp, random.randint(lo, hi))
