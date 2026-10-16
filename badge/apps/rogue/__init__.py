import machine
import os
import random
import sys


APP_DIRS = (
    "/system/apps/rogue",
    "/apps/rogue",
    "/rogue",
)

APP_DIR = APP_DIRS[0]
for app_dir in APP_DIRS:
    try:
        os.stat(app_dir)
        APP_DIR = app_dir
        break
    except OSError:
        pass

os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

badge.mode(HIRES | VSYNC)
badge.default_clear = None
screen.antialias = image.OFF
screen.font = font.sins

small_font = font.sins
large_font = font.curse


class GameState:
    INTRO = 1
    PLAYING = 2
    DEAD = 3


def resolve_button(*names):
    for name in names:
        try:
            return eval(name)
        except NameError:
            pass
    return None


BUTTON_MOVE_LEFT = resolve_button("BUTTON_A", "BUTTON_LEFT")
BUTTON_MOVE_RIGHT = resolve_button("BUTTON_C", "BUTTON_SELECT")
BUTTON_ACTION = resolve_button("BUTTON_B", "BUTTON_RIGHT")
BUTTON_COMMAND = resolve_button("BUTTON_HOME")

WIDTH = screen.width
HEIGHT = screen.height
MAP_W = 32
MAP_H = 32
CELL_W = 10
CELL_H = 10
MAP_Y = 25
VIEW_SCALE = 2
VIEW_W = 16
VIEW_H = 8
MAP_STRIP_W = VIEW_W * CELL_W * VIEW_SCALE
MAP_STRIP_H = VIEW_H * CELL_H * VIEW_SCALE
LOG_Y = MAP_Y + MAP_STRIP_H + 3
map_view = image(VIEW_W * CELL_W, VIEW_H * CELL_H)
map_view.antialias = image.OFF
map_view.font = small_font
LOG_W = WIDTH - 8
minimap_view = image(MAP_W, MAP_H)
minimap_view.antialias = image.OFF
banner_view = image(WIDTH // 2, 26)
banner_view.antialias = image.OFF

BLACK = color.rgb(0, 0, 0)
GRAY_1 = color.rgb(242, 245, 243)
GRAY_2 = color.rgb(228, 235, 230)
GRAY_3 = color.rgb(182, 191, 184)
GRAY_4 = color.rgb(144, 150, 146)
GRAY_5 = color.rgb(35, 41, 37)
GRAY_6 = color.rgb(16, 20, 17)
GREEN_1 = color.rgb(191, 255, 209)
GREEN_2 = color.rgb(140, 242, 166)
GREEN_3 = color.rgb(95, 237, 131)
GREEN_4 = color.rgb(15, 191, 62)
GREEN_5 = color.rgb(8, 135, 43)

# Take some artistic liberty with GREEN_5, making outdoors less bright
GREEN_5_GRASS = color.rgb(8, 135, 43).darken(75)
GREEN_5_SHRUB = color.rgb(8, 135, 43).darken(25)

MINIMAP_ROOM = color.rgb(144, 150, 146).darken(45)
MINIMAP_PATH = color.rgb(144, 150, 146).darken(65)

GREEN_6 = color.rgb(10, 36, 27)
GOLD = color.rgb(235, 210, 120)
HURT = color.rgb(230, 96, 88)
PURPLE = color.rgb(190, 155, 235)
ROOM_BRUSH = brush.pattern(GRAY_6, BLACK, 10)
PATH_BRUSH = brush.pattern(GREEN_6, GRAY_6, 8)
WALL_BRUSH = brush.pattern(GRAY_5, GRAY_6, 11)
DIRT_BRUSH = brush.pattern(GREEN_6, GRAY_6, 9)
GRASS_BRUSH = brush.pattern(GREEN_6, GREEN_5_GRASS, 32)
SHRUB_BRUSH = brush.pattern(GREEN_6, GREEN_5_SHRUB, 16)
HOLE_BRUSH = brush.pattern(GRAY_6, GREEN_6, 19)
SHADOW_BRUSH = color.rgb(0, 0, 0, 150)
UP_STAIR_BRUSH = brush.pattern(GRAY_5, GRAY_6, 7)
DOWN_STAIR_BRUSH = brush.pattern(GRAY_5, GRAY_6, 26)
LADDER_BRUSH = brush.pattern(GRAY_4, GRAY_6, 24)
GATE_BRUSH = brush.pattern(GRAY_6, GOLD, 4)
CAVE_WALL_BRUSH = brush.pattern(GRAY_5, GRAY_6, 16)


PATTERN_SIZE = 8
PATTERN_MASK = PATTERN_SIZE - 1
PHASE_X = [(x * CELL_W) & PATTERN_MASK for x in range(PATTERN_SIZE)]
PHASE_Y = [(y * CELL_H) & PATTERN_MASK for y in range(PATTERN_SIZE)]


def tile_patch(pen):
    scratch = image(CELL_W + PATTERN_SIZE, CELL_H + PATTERN_SIZE)
    scratch.antialias = image.OFF
    scratch.pen = pen
    scratch.rectangle(0, 0, scratch.width, scratch.height)

    made = {}
    patch = []
    for y in range(PATTERN_SIZE):
        for x in range(PATTERN_SIZE):
            phase = PHASE_Y[y] * PATTERN_SIZE + PHASE_X[x]
            tile = made.get(phase)
            if tile is None:
                tile = image(CELL_W, CELL_H)
                tile.antialias = image.OFF
                tile.blit(scratch, vec2(-PHASE_X[x], -PHASE_Y[y]))
                made[phase] = tile
            patch.append(tile)
    return patch


ROOM_PATCH = tile_patch(ROOM_BRUSH)
PATH_PATCH = tile_patch(PATH_BRUSH)
WALL_PATCH = tile_patch(WALL_BRUSH)
DIRT_PATCH = tile_patch(DIRT_BRUSH)
GRASS_PATCH = tile_patch(GRASS_BRUSH)
SHRUB_PATCH = tile_patch(SHRUB_BRUSH)
HOLE_PATCH = tile_patch(HOLE_BRUSH)
UP_STAIR_PATCH = tile_patch(UP_STAIR_BRUSH)
DOWN_STAIR_PATCH = tile_patch(DOWN_STAIR_BRUSH)
LADDER_PATCH = tile_patch(LADDER_BRUSH)
GATE_PATCH = tile_patch(GATE_BRUSH)
CAVE_WALL_PATCH = tile_patch(CAVE_WALL_BRUSH)
GLYPH_LIFT = 2

state = GameState.INTRO
level = 1
kills = 0
turns = 0
items_found = 0
needs_draw = True
command_open = False
command_open_ticks = 0
menu_tab = "pack"
pack_cursor = 0
message_log = []
dungeon = []
explored = []
visible = []
rooms = []
items = []
pack = []
identified_scrolls = {"identify": True}
enemies = []
gate = None
gate_side = None
gate_unlocked = False
layer = 0
ruin = 1
layer_cache = {}
run_seed = 0
area_seed = 0
surface_seed = 0
fill_tile = " "
floor_list = []
entry_side = None
entry_offset = None
player = {
    "x": 1,
    "y": 1,
    "hp": 18,
    "max_hp": 18,
    "atk": 4,
    "armor": 0,
    "gold": 0,
    "sight": 8,
    "confuse": 0,
    "sleep": 0,
    "weapon_cursed": False,
    "armor_cursed": False,
    "pack_slots": 9,
}

SCROLLS = {
    "identify": {"name": "scroll of identify", "char": "i", "hint": "names one carried item"},
    "enchant_armor": {"name": "scroll of enchant armor", "char": "a", "hint": "+1 armor"},
    "enchant_weapon": {"name": "scroll of enchant weapon", "char": "w", "hint": "+1 attack"},
    "mapping": {"name": "scroll of magic mapping", "char": "m", "hint": "reveals the level"},
    "teleport": {"name": "scroll of teleportation", "char": "t", "hint": "moves you elsewhere"},
    "gold_detection": {"name": "scroll of gold detection", "char": "g", "hint": "reveals gold"},
    "remove_curse": {"name": "scroll of remove curse", "char": "c", "hint": "lifts curses"},
    "carry": {"name": "scroll of carry", "char": "p", "hint": "+9 pack slots"},
    "hold_monster": {"name": "scroll of hold monster", "char": "h", "hint": "freezes nearby foes"},
    "scare_monster": {"name": "scroll of scare monster", "char": "f", "hint": "routs nearby foes"},
    "food_detection": {"name": "scroll of food detection", "char": "d", "hint": "reveals food"},
    "monster_confusion": {"name": "scroll of monster confusion", "char": "r", "hint": "confuses your next hit"},
    "sleep": {"name": "scroll of sleep", "char": "z", "hint": "puts you to sleep"},
    "create_monster": {"name": "scroll of create monster", "char": "n", "hint": "summons a foe"},
    "aggravate": {"name": "scroll of aggravate monsters", "char": "u", "hint": "wakes every foe"},
    "blank": {"name": "blank paper", "char": "b", "hint": "nothing at all"},
}
SCROLL_EFFECTS = tuple(SCROLLS.keys())
ITEM_DEFS = {
    "gold": {"char": "$", "glyph": "$", "pen": GOLD, "name": "gold", "action": "B use", "hint": "coin"},
    "potion": {"char": "!", "glyph": "!", "pen": GREEN_2, "name": "healing potion", "action": "B quaff", "hint": None},
    "scroll": {"char": "s", "glyph": "?", "pen": PURPLE, "name": "unidentified scroll", "action": "B read", "hint": None},
    "food": {"char": "%", "glyph": "%", "pen": GOLD, "name": "food ration", "action": "B eat", "hint": None},
    "bow": {"char": ")", "glyph": ")", "pen": GRAY_1, "name": "short bow", "action": "B equip", "hint": "shoot the nearest foe"},
    "arrows": {"char": "/", "glyph": "/", "pen": GRAY_1, "name": "arrows", "action": "B ready", "hint": "ammunition"},
    "key": {"char": "k", "glyph": "k", "pen": GOLD, "name": "gate key", "action": "B hold", "hint": "opens the ruin gate"},
    "blade": {"char": ")", "glyph": ")", "pen": GRAY_1, "name": "blade", "action": "B use", "hint": "+1 attack"},
    "shield": {"char": "]", "glyph": "]", "pen": GREEN_4, "name": "shield", "action": "B use", "hint": "+1 armor"},
}
UNKNOWN_ITEM_DEF = {"char": "?", "glyph": "]", "pen": GREEN_4, "name": "strange item", "action": "B use", "hint": "who knows"}
ITEM_WEIGHTS = (
    ("gold", 26),
    ("potion", 16),
    ("scroll", 14),
    ("food", 12),
    ("arrows", 12),
    ("bow", 8),
    ("shield", 6),
    ("blade", 6),
)
POTION_HEAL_MIN = 6
FOOD_HEAL = 3
ARMOR_CAP = 5
RESPAWN_LIMIT = 2

ENEMY_KINDS = {
    "r": {"name": "rat", "hp": 4, "atk": 1, "accuracy": 45, "dodge": 5, "pen": GRAY_2,
          "move": "chase", "min_level": 1, "habitat": {"surface": 45, "pocket": 12}},
    "b": {"name": "bat", "hp": 5, "atk": 2, "accuracy": 40, "dodge": 18, "pen": GRAY_2,
          "move": "erratic", "min_level": 1, "habitat": {"pocket": 30, "cave": 45}},
    "E": {"name": "emu", "hp": 5, "atk": 2, "accuracy": 60, "dodge": 6, "pen": GRAY_2,
          "move": "chase", "min_level": 1, "habitat": {"surface": 25}},
    "K": {"name": "kestrel", "hp": 4, "atk": 2, "accuracy": 50, "dodge": 6, "pen": GRAY_2,
          "move": "fast", "min_level": 1, "habitat": {"surface": 18, "pocket": 8}},
    "s": {"name": "slime", "hp": 10, "atk": 2, "accuracy": 55, "dodge": 0, "pen": GREEN_3,
          "move": "chase", "min_level": 1, "habitat": {"cave": 40, "surface": 8}},
    "g": {"name": "guard", "hp": 8, "atk": 3, "accuracy": 70, "dodge": 5, "pen": HURT,
          "move": "chase", "min_level": 2, "habitat": {"surface": 8, "pocket": 18}},
    "H": {"name": "hobgoblin", "hp": 8, "atk": 4, "accuracy": 65, "dodge": 12, "pen": HURT,
          "move": "chase", "min_level": 2, "habitat": {"pocket": 25, "cave": 10}},
    "F": {"name": "floating eye", "hp": 6, "atk": 0, "accuracy": 0, "dodge": 0, "pen": GREEN_3,
          "move": "still", "paralyse": 3, "min_level": 3, "habitat": {"cave": 14, "pocket": 8}},
    "L": {"name": "leprechaun", "hp": 6, "atk": 0, "accuracy": 50, "dodge": 3, "pen": GOLD,
          "move": "chase", "on_hit": "steal_gold", "min_level": 3, "habitat": {"cave": 12, "pocket": 8}},
    "Z": {"name": "zombie", "hp": 14, "atk": 4, "accuracy": 60, "dodge": 3, "pen": HURT,
          "move": "slow", "min_level": 4, "habitat": {"pocket": 18, "cave": 18}},
    "A": {"name": "aquator", "hp": 10, "atk": 0, "accuracy": 60, "dodge": 21, "pen": PURPLE,
          "move": "chase", "on_hit": "rust", "min_level": 5, "habitat": {"pocket": 10, "cave": 8}},
    "N": {"name": "nymph", "hp": 6, "atk": 0, "accuracy": 50, "dodge": 0, "pen": PURPLE,
          "move": "chase", "on_hit": "steal_item", "min_level": 6, "habitat": {"pocket": 10, "cave": 6}},
    "T": {"name": "troll", "hp": 18, "atk": 5, "accuracy": 70, "dodge": 15, "pen": HURT,
          "move": "chase", "regen": 1, "min_level": 8, "habitat": {"pocket": 10, "cave": 8}},
}
PLAYER_ACCURACY = 78
BOW_ACCURACY_BONUS = 10
STEPS = ((1, 0), (-1, 0), (0, 1), (0, -1))
SURFACE_FLOOR = "."
UNDER_FLOOR = ".,#"
PASSABLE_TILES = ".#,o><u"
OPEN_GROUND = " "
ROCK = "^"
SEALED_GATE = "="
CAVE_FLOOR = ","
HOLE = "o"
STAIRS_DOWN = ">"
STAIRS_UP = "<"
LADDER_UP = "u"
CAVE_TILES = ",ou"
ROOM_TILES = ".#|-"
SIGHT_BLOCKERS = "|-^="
FLOOR_SAMPLE_TRIES = 24
SEED_MASK = 0x3FFFFFFF
SURFACE_HOLES = 4
SURFACE_HOLE_GAP = 7
MAX_LAYER = 2
CAVE_STEPS = 90
CAVE_REACH = 7
CAVE_FILL = 54
CAVE_DIRT_SHARE = 62
PASSAGE_CHANCE = 14
PASSAGE_REACH = 5
LINK_GAP = 5
LINK_GAP_FLOOR = 3
ANCHOR_REACH = 9
HOLE_TO_DUNGEON = 40
ROOM_REGION_W = 16
ROOM_REGION_H = 14
HIDDEN_ROW = [False] * MAP_W
CELL_COUNT = MAP_W * MAP_H
REACH_CLEAR = bytes(CELL_COUNT)
reach_flags = bytearray(CELL_COUNT)
reach_queue = [0] * CELL_COUNT

PACK_BLOCK = 9
PACK_BLOCKS = 3
PACK_MAX_SLOTS = PACK_BLOCK * PACK_BLOCKS
PACK_COLS = PACK_BLOCK
PACK_ROWS = PACK_BLOCKS
PACK_SLOT = 30
PACK_BOX = 26
PACK_GRID_W = PACK_COLS * PACK_SLOT - (PACK_SLOT - PACK_BOX)
PACK_GRID_H = PACK_ROWS * PACK_SLOT - (PACK_SLOT - PACK_BOX)
PACK_PANEL_Y = MAP_Y - 4
PACK_PANEL_H = MAP_STRIP_H + 6
PACK_GRID_X = (WIDTH - PACK_GRID_W) // 2
PACK_GRID_Y = PACK_PANEL_Y + 24
PACK_TITLE_Y = PACK_PANEL_Y + 4
PACK_NAME_Y = PACK_GRID_Y + PACK_GRID_H + 8
PACK_EFFECT_Y = PACK_NAME_Y + 15
PACK_HINT_Y = PACK_EFFECT_Y + 15
PACK_BACKDROP = color.rgb(0, 0, 0, 205)
PACK_LOCKED = color.rgb(144, 150, 146).darken(50)
DEAD_TITLE_Y = PACK_PANEL_Y + 35
DEAD_HINT_Y = PACK_PANEL_Y + 101
MENU_TABS = (("pack", "PACK"), ("map", "MAP"))
MENU_TAB_GAP = 24
MENU_TAB_RULE = 14
MENU_PANEL_Y = 0
MENU_PANEL_H = HEIGHT
MENU_MAP_SCALE = 6
MENU_MAP_W = MAP_W * MENU_MAP_SCALE
MENU_MAP_H = MAP_H * MENU_MAP_SCALE
MENU_MAP_X = 2
MENU_MAP_Y = MENU_PANEL_Y + MENU_PANEL_H - MENU_MAP_H - 2
MENU_STAT_X = MENU_MAP_X + MENU_MAP_W + 10
MENU_STAT_W = WIDTH - MENU_STAT_X - 4
MENU_STAT_PITCH = 16


def mark_dirty():
    global needs_draw
    needs_draw = True


def held(button):
    return button is not None and badge.held(button)


def pressed(button):
    return button is not None and badge.pressed(button)


def say(message):
    message_log.append(message)
    while len(message_log) > 3:
        message_log.pop(0)


def pack_count(kind):
    count = 0
    for item in pack:
        if item["kind"] == kind:
            count += 1
    return count


def arrow_count():
    count = 0
    for item in pack:
        if item["kind"] == "arrows":
            count += item.get("count", 1)
    return count


def consume_arrow():
    for item in pack:
        if item["kind"] != "arrows":
            continue
        count = item.get("count", 1) - 1
        if count <= 0:
            pack.remove(item)
        else:
            item["count"] = count
        return True
    return False


def add_pack_item(item):
    if len(pack) >= player["pack_slots"]:
        say("Your pack is full.")
        return False
    pack.append(item)
    return True


def selected_pack_item():
    if pack_cursor < len(pack):
        return pack[pack_cursor]
    return None


def clamp(value, low, high):
    return min(high, max(low, value))


def room_center(room):
    x, y, w, h = room
    return x + w // 2, y + h // 2


def point_in_room(x, y, room):
    rx, ry, rw, rh = room
    return x >= rx and y >= ry and x < rx + rw and y < ry + rh


def current_room():
    for room in rooms:
        if point_in_room(player["x"], player["y"], room):
            return room
    return None


def carve_room(room):
    x, y, w, h = room
    for row in range(y, y + h):
        for col in range(x, x + w):
            if row == y or row == y + h - 1 or col == x or col == x + w - 1:
                dungeon[row][col] = "-" if row == y or row == y + h - 1 else "|"
            else:
                dungeon[row][col] = "."


def carve_hline(x1, x2, y):
    start = min(x1, x2)
    end = max(x1, x2)
    for x in range(start, end + 1):
        carve_path(x, y)


def carve_vline(y1, y2, x):
    start = min(y1, y2)
    end = max(y1, y2)
    for y in range(start, end + 1):
        carve_path(x, y)


def doorway_towards(room, target):
    x, y, w, h = room
    cx, cy = room_center(room)
    tx, ty = target

    if abs(tx - cx) > abs(ty - cy):
        door_x = x + w - 1 if tx > cx else x
        door_y = clamp(ty, y + 1, y + h - 2)
    else:
        door_x = clamp(tx, x + 1, x + w - 2)
        door_y = y + h - 1 if ty > cy else y
    return door_x, door_y


def outside_door(room, door):
    x, y, w, h = room
    door_x, door_y = door
    if door_x == x:
        return door_x - 1, door_y
    if door_x == x + w - 1:
        return door_x + 1, door_y
    if door_y == y:
        return door_x, door_y - 1
    return door_x, door_y + 1


def connect_rooms(room_a, room_b):
    center_a = room_center(room_a)
    center_b = room_center(room_b)
    door_a = doorway_towards(room_a, center_b)
    door_b = doorway_towards(room_b, center_a)
    outside_a = outside_door(room_a, door_a)
    outside_b = outside_door(room_b, door_b)

    dungeon[door_a[1]][door_a[0]] = "."
    dungeon[door_b[1]][door_b[0]] = "."

    if random.randrange(2):
        carve_hline(outside_a[0], outside_b[0], outside_a[1])
        carve_vline(outside_a[1], outside_b[1], outside_b[0])
    else:
        carve_vline(outside_a[1], outside_b[1], outside_a[0])
        carve_hline(outside_a[0], outside_b[0], outside_b[1])

    return True


def cell_index(cell):
    return cell[1] * MAP_W + cell[0]


def derive_seed(parent, x, y, extra):
    value = (parent + x * 73856093 + y * 19349663 + extra * 83492791) & SEED_MASK
    value = ((value ^ (value >> 15)) * 2246822519) & SEED_MASK
    value = ((value ^ (value >> 13)) * 3266489917) & SEED_MASK
    return (value ^ (value >> 16)) & SEED_MASK


def surface_seed_for(index):
    return derive_seed(run_seed, 0, 0, index)


def layer_seed(index):
    return derive_seed(surface_seed, 0, 0, index)


def habitat_at(x, y):
    if outdoors():
        return "surface"
    return "cave" if dungeon[y][x] in CAVE_TILES else "pocket"


def link_anchors(grid, deep):
    anchors = []
    for y in range(MAP_H):
        row = grid[y]
        for x in range(MAP_W):
            if row[x] == HOLE:
                sink = deep and random.randrange(100) < HOLE_TO_DUNGEON
                anchors.append((x, y, "dungeon" if sink else "cave"))
            elif row[x] == STAIRS_DOWN:
                anchors.append((x, y, "dungeon"))
    return anchors


def region_cells(start):
    reachable = reachable_cells(start)
    cells = []
    for index in range(CELL_COUNT):
        if reachable[index]:
            cells.append((index % MAP_W, index // MAP_W))
    return cells


def anchor_groups(anchors):
    groups = []
    for x, y, kind in anchors:
        for group in groups:
            if group[0] != kind:
                continue
            if any(abs(x - ax) + abs(y - ay) <= ANCHOR_REACH for ax, ay in group[1]):
                group[1].append((x, y))
                break
        else:
            groups.append((kind, [(x, y)]))
    return groups


def open_anchor(x, y, floor):
    if dungeon[y][x] != ROCK:
        return
    dungeon[y][x] = floor
    for dx, dy in STEPS:
        nx = x + dx
        ny = y + dy
        if nx < 1 or ny < 1 or nx >= MAP_W - 1 or ny >= MAP_H - 1:
            continue
        if dungeon[ny][nx] != ROCK:
            continue
        if floor == CAVE_FLOOR and touches_rooms(nx, ny):
            continue
        dungeon[ny][nx] = floor


def carve_cave_region(cx, cy):
    low_x = max(1, cx - CAVE_REACH)
    high_x = min(MAP_W - 2, cx + CAVE_REACH)
    low_y = max(1, cy - CAVE_REACH)
    high_y = min(MAP_H - 2, cy + CAVE_REACH)

    x = cx
    y = cy
    for _ in range(CAVE_STEPS):
        hollow(x, y)
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                if random.randrange(100) < CAVE_FILL:
                    hollow(x + dx, y + dy)
        dx, dy = random.choice(STEPS)
        x = clamp(x + dx, low_x, high_x)
        y = clamp(y + dy, low_y, high_y)


def touches_rooms(x, y):
    for dx, dy in STEPS:
        if dungeon[y + dy][x + dx] in ROOM_TILES:
            return True
    return False


def hollow(x, y):
    if x < 1 or y < 1 or x >= MAP_W - 1 or y >= MAP_H - 1:
        return
    if dungeon[y][x] != ROCK:
        return
    if touches_rooms(x, y):
        return
    dungeon[y][x] = CAVE_FLOOR


def clear_of_caves(room):
    x, y, w, h = room
    for row in range(max(1, y - 1), min(MAP_H - 1, y + h + 1)):
        for col in range(max(1, x - 1), min(MAP_W - 1, x + w + 1)):
            if dungeon[row][col] in CAVE_TILES:
                return False
    return True


def all_rock(room):
    x, y, w, h = room
    for row in range(y, y + h):
        for col in range(x, x + w):
            if dungeon[row][col] != ROCK:
                return False
    return True


def room_holds(room, x, y):
    rx, ry, rw, rh = room
    return x > rx and y > ry and x < rx + rw - 1 and y < ry + rh - 1


def home_room(x, y, low_x, low_y):
    for width, height in ((5, 4), (4, 3), (3, 3)):
        room = (clamp(x - width // 2, low_x, low_x + ROOM_REGION_W - width),
                clamp(y - height // 2, low_y, low_y + ROOM_REGION_H - height), width, height)
        if not room_holds(room, x, y) or intersects(room) or not all_rock(room):
            continue
        if not clear_of_caves(room):
            continue
        return room
    return None


def carve_room_region(cells):
    cx, cy = cells[0]
    low_x = clamp(cx - ROOM_REGION_W // 2, 1, MAP_W - ROOM_REGION_W - 1)
    low_y = clamp(cy - ROOM_REGION_H // 2, 1, MAP_H - ROOM_REGION_H - 1)
    placed = []

    for x, y in cells:
        room = home_room(x, y, low_x, low_y)
        if room is None:
            continue
        carve_room(room)
        rooms.append(room)
        placed.append(room)

    for _ in range(40):
        if len(placed) >= 5:
            break
        w = random.randrange(4, 8)
        h = random.randrange(3, 6)
        x = random.randrange(low_x, low_x + ROOM_REGION_W - w)
        y = random.randrange(low_y, low_y + ROOM_REGION_H - h)
        room = (x, y, w, h)
        if intersects(room) or not all_rock(room) or not clear_of_caves(room):
            continue
        carve_room(room)
        rooms.append(room)
        placed.append(room)

    for index in range(1, len(placed)):
        connect_rooms(placed[index - 1], placed[index])

    return placed


def reachable_cells(start):
    flags = reach_flags
    queue = reach_queue
    flags[:] = REACH_CLEAR
    outside = outdoors()

    index = cell_index(start)
    flags[index] = 1
    queue[0] = index
    head = 0
    tail = 1

    while head < tail:
        index = queue[head]
        head += 1
        x = index % MAP_W
        y = index // MAP_W

        for dx, dy in STEPS:
            nx = x + dx
            ny = y + dy
            if nx < 0 or ny < 0 or nx >= MAP_W or ny >= MAP_H:
                continue
            step = ny * MAP_W + nx
            if flags[step]:
                continue
            if tile_open(dungeon[ny][nx], outside):
                flags[step] = 1
                queue[tail] = step
                tail += 1

    return bytes(flags)


def dungeon_connected():
    visited = reachable_cells((player["x"], player["y"]))

    for room in rooms:
        if not visited[cell_index(room_center(room))]:
            return False
    return True


def scatter_outdoors():
    outdoor = []
    for y in range(1, MAP_H - 1):
        for x in range(1, MAP_W - 1):
            if dungeon[y][x] != " ":
                continue
            outdoor.append((x, y))
            roll = random.randrange(100)
            if roll < 26:
                dungeon[y][x] = ","
            elif roll < 33:
                dungeon[y][x] = "^"

    if len(outdoor) < 80:
        return

    placed = []
    for gap in range(SURFACE_HOLE_GAP, 0, -2):
        for _ in range(60):
            if len(placed) >= SURFACE_HOLES:
                return
            x, y = random.choice(outdoor)
            if dungeon[y][x] != " " or group_gap(placed, (x, y)) < gap:
                continue
            dungeon[y][x] = "o"
            placed.append((x, y))


def blocked_message(x, y):
    if x < 0 or y < 0 or x >= MAP_W or y >= MAP_H:
        return "The world ends here."
    if dungeon[y][x] == SEALED_GATE:
        return "The gate behind you is barred."
    if dungeon[y][x] == ROCK:
        return "Shrubs block the way." if outdoors() else "Solid rock blocks the way."
    return "Stone blocks the way."


def carve_path(x, y):
    if dungeon[y][x] == fill_tile:
        dungeon[y][x] = "#"


def intersects(room):
    x, y, w, h = room
    for other in rooms:
        ox, oy, ow, oh = other
        if x - 1 < ox + ow and x + w + 1 > ox and y - 1 < oy + oh and y + h + 1 > oy:
            return True
    return False


def rebuild_floor_list():
    global floor_list

    wanted = SURFACE_FLOOR if outdoors() else UNDER_FLOOR
    cells = []
    for y in range(1, MAP_H - 1):
        for x in range(1, MAP_W - 1):
            if dungeon[y][x] in wanted:
                cells.append((x, y))
    floor_list = cells


def random_floor(avoid_start=False, min_player_distance=0):
    wanted = SURFACE_FLOOR if outdoors() else UNDER_FLOOR

    for _ in range(FLOOR_SAMPLE_TRIES):
        if len(floor_list) == 0:
            break
        x, y = floor_list[random.randrange(len(floor_list))]
        if dungeon[y][x] not in wanted or (x, y) == (player["x"], player["y"]):
            continue
        if enemy_at(x, y) is not None or item_at(x, y) is not None:
            continue
        if avoid_start and rooms and point_in_room(x, y, rooms[0]):
            continue
        if min_player_distance and abs(x - player["x"]) + abs(y - player["y"]) < min_player_distance:
            continue
        return x, y

    return scan_floor(avoid_start, min_player_distance)


def scan_floor(avoid_start, min_player_distance):
    wanted = SURFACE_FLOOR if outdoors() else UNDER_FLOOR
    candidates = []
    for y in range(1, MAP_H - 1):
        for x in range(1, MAP_W - 1):
            if dungeon[y][x] not in wanted or (x, y) == (player["x"], player["y"]):
                continue
            if enemy_at(x, y) is not None or item_at(x, y) is not None:
                continue
            candidates.append((x, y))

    while len(candidates) > 0:
        index = random.randrange(len(candidates))
        x, y = candidates.pop(index)
        if avoid_start and rooms and point_in_room(x, y, rooms[0]):
            continue
        if min_player_distance and abs(x - player["x"]) + abs(y - player["y"]) < min_player_distance:
            continue
        return x, y

    if avoid_start or min_player_distance:
        return scan_floor(False, 0)
    return player["x"], player["y"]


def enemy_at(x, y):
    for enemy in enemies:
        if enemy["hp"] > 0 and enemy["x"] == x and enemy["y"] == y:
            return enemy
    return None


def item_at(x, y):
    for item in items:
        if item["x"] == x and item["y"] == y:
            return item
    return None


def pack_item(kind):
    for item in pack:
        if item["kind"] == kind:
            return item
    return None


def equipped_bow():
    for item in pack:
        if item["kind"] == "bow" and item.get("equipped"):
            return item
    return None


def enemy_kind(enemy):
    return ENEMY_KINDS[enemy["ch"]]


def enemy_name(enemy):
    return ENEMY_KINDS[enemy["ch"]]["name"]


def make_enemy(x, y, char):
    definition = ENEMY_KINDS[char]
    hp = definition["hp"] + level
    return {
        "x": x,
        "y": y,
        "ch": char,
        "hp": hp,
        "max_hp": hp,
        "atk": (definition["atk"] + level // 2) if definition["atk"] > 0 else 0,
        "held": 0,
        "scared": 0,
        "confused": 0,
        "skip": 0,
        "loot": 0,
        "awake": False,
    }


def spawn_weights(kind):
    table = []
    for char in ENEMY_KINDS:
        definition = ENEMY_KINDS[char]
        weight = definition["habitat"].get(kind, 0)
        if weight > 0 and level >= definition["min_level"]:
            table.append((char, weight))
    return table


def pick_weighted(table):
    total = 0
    for _choice, weight in table:
        total += weight
    if total == 0:
        return None

    roll = random.randrange(total)
    for choice, weight in table:
        roll -= weight
        if roll < 0:
            return choice
    return table[0][0]


def random_enemy_char(kind):
    return pick_weighted(spawn_weights(kind))


def make_item(x, y):
    kind = pick_weighted(ITEM_WEIGHTS)
    item = {"x": x, "y": y, "kind": kind}
    if kind == "scroll":
        item["effect"] = random.choice(SCROLL_EFFECTS)
    elif kind == "arrows":
        item["count"] = random.randrange(3, 8)
    return item


def capture_area():
    return {
        "dungeon": [row[:] for row in dungeon],
        "explored": [row[:] for row in explored],
        "visible": [row[:] for row in visible],
        "rooms": rooms[:],
        "items": [item.copy() for item in items],
        "enemies": [enemy.copy() for enemy in enemies if enemy["hp"] > 0],
        "gate": gate,
        "gate_side": gate_side,
        "gate_unlocked": gate_unlocked,
        "seed": area_seed,
    }


def restore_area(snapshot):
    global dungeon, explored, visible, rooms, items, enemies, gate, gate_side, gate_unlocked
    global area_seed, fill_tile

    dungeon = [row[:] for row in snapshot["dungeon"]]
    explored = [row[:] for row in snapshot["explored"]]
    visible = [row[:] for row in snapshot["visible"]]
    rooms = snapshot["rooms"][:]
    items = [item.copy() for item in snapshot["items"]]
    enemies = [enemy.copy() for enemy in snapshot["enemies"]]
    gate = snapshot["gate"]
    gate_side = snapshot["gate_side"]
    gate_unlocked = snapshot["gate_unlocked"]
    area_seed = snapshot["seed"]
    fill_tile = OPEN_GROUND if outdoors() else ROCK


def gate_positions(side):
    if side == "left":
        return [((0, y), (1, y)) for y in range(3, MAP_H - 3)]
    if side == "right":
        return [((MAP_W - 1, y), (MAP_W - 2, y)) for y in range(3, MAP_H - 3)]
    if side == "top":
        return [((x, 0), (x, 1)) for x in range(3, MAP_W - 3)]
    return [((x, MAP_H - 1), (x, MAP_H - 2)) for x in range(3, MAP_W - 3)]


def gate_flanks(side, cell):
    x, y = cell
    if side in ("left", "right"):
        inner = 1 if side == "left" else MAP_W - 2
        return ((x, y - 1), (x, y + 1), (inner, y - 1), (inner, y + 1))
    inner = 1 if side == "top" else MAP_H - 2
    return ((x - 1, y), (x + 1, y), (x - 1, inner), (x + 1, inner))


def flank_gate(approach, reachable):
    flanks = [cell for cell in gate_flanks(gate_side, gate) if cell != (player["x"], player["y"])]
    replaced = [(x, y, dungeon[y][x]) for x, y in flanks]
    wall = "|" if gate_side in ("left", "right") else "-"

    for x, y in flanks:
        dungeon[y][x] = wall

    if flanks_kept_map_open(approach, reachable, flanks):
        return

    for x, y, tile in replaced:
        dungeon[y][x] = tile


def flanks_kept_map_open(approach, reachable, flanks):
    still_reachable = reachable_cells((player["x"], player["y"]))
    if not still_reachable[cell_index(approach)]:
        return False

    spared = [cell_index(cell) for cell in flanks]
    for index in range(CELL_COUNT):
        if reachable[index] and not still_reachable[index] and index not in spared:
            return False
    return True


def place_gate_key():
    for _ in range(120):
        key_x, key_y = random_floor(True, 6)
        if abs(key_x - gate[0]) + abs(key_y - gate[1]) > 10:
            items.append({"x": key_x, "y": key_y, "kind": "key"})
            return
    key_x, key_y = random_floor(True, 6)
    items.append({"x": key_x, "y": key_y, "kind": "key"})


def place_surface_goal():
    global gate, gate_side

    reachable = reachable_cells((player["x"], player["y"]))
    sides = ["left", "right", "top", "bottom"]

    while sides:
        side = sides.pop(random.randrange(len(sides)))
        candidates = [pair for pair in gate_positions(side)
                      if reachable[cell_index(pair[1])] and dungeon[pair[0][1]][pair[0][0]] != SEALED_GATE]
        if not candidates:
            continue
        gate_side = side
        gate, approach = candidates[random.randrange(len(candidates))]
        flank_gate(approach, reachable)
        place_gate_key()
        return True

    return False


def opposite_side(side):
    if side == "left":
        return "right"
    if side == "right":
        return "left"
    if side == "top":
        return "bottom"
    return "top"


def offsets_near(target, low, high):
    ordered = []
    for distance in range(high - low + 1):
        for candidate in (target - distance, target + distance):
            if candidate >= low and candidate <= high and candidate not in ordered:
                ordered.append(candidate)
    return ordered


def inward_step(side):
    if side == "left":
        return 1, 0
    if side == "right":
        return -1, 0
    if side == "top":
        return 0, 1
    return 0, -1


def entry_candidates(side):
    if side in ("left", "right"):
        x = 1 if side == "left" else MAP_W - 2
        return [(x, y) for y in offsets_near(clamp(entry_offset, 1, MAP_H - 2), 1, MAP_H - 2)]
    y = 1 if side == "top" else MAP_H - 2
    return [(x, y) for x in offsets_near(clamp(entry_offset, 1, MAP_W - 2), 1, MAP_W - 2)]


def seal_entry_gate(x, y):
    dx, dy = inward_step(entry_side)
    onward = (x + dx, y + dy)
    cell = (x - dx, y - dy)
    wall = "|" if entry_side in ("left", "right") else "-"

    changes = [(cell, SEALED_GATE)]
    for flank in gate_flanks(entry_side, cell):
        if flank != (x, y) and flank != onward:
            changes.append((flank, wall))

    before = reachable_cells((player["x"], player["y"]))
    replaced = [(fx, fy, dungeon[fy][fx]) for (fx, fy), _tile in changes]
    for (fx, fy), tile in changes:
        dungeon[fy][fx] = tile

    if flanks_kept_map_open(onward, before, [pair[0] for pair in changes]):
        return

    for fx, fy, tile in replaced:
        dungeon[fy][fx] = tile


def place_entry():
    if entry_side is None:
        return

    reachable = reachable_cells((player["x"], player["y"]))
    dx, dy = inward_step(entry_side)
    candidates = entry_candidates(entry_side)

    for x, y in candidates:
        if not reachable[y * MAP_W + x] or not passable(x + dx, y + dy):
            continue
        player["x"] = x
        player["y"] = y
        seal_entry_gate(x, y)
        return

    for x, y in candidates:
        if reachable[y * MAP_W + x]:
            player["x"] = x
            player["y"] = y
            return


def blank_area(fill):
    global dungeon, explored, visible, rooms, items, enemies, fill_tile

    fill_tile = fill
    dungeon = [[fill for _ in range(MAP_W)] for _ in range(MAP_H)]
    explored = [[False for _ in range(MAP_W)] for _ in range(MAP_H)]
    visible = [[False for _ in range(MAP_W)] for _ in range(MAP_H)]
    rooms = []
    items = []
    enemies = []


def build_layer(index, seed, arrive_x, arrive_y, parent):
    global area_seed, gate, gate_side, gate_unlocked

    area_seed = seed
    random.seed(seed)
    blank_area(ROCK)
    gate = None
    gate_side = None
    gate_unlocked = False

    groups = anchor_groups(link_anchors(parent, index > 1))
    caves = []
    complexes = []
    for kind, cells in groups:
        if kind != "cave":
            continue
        for x, y in cells:
            open_anchor(x, y, CAVE_FLOOR)
        caves.append(cells)
    for kind, cells in groups:
        if kind != "dungeon":
            continue
        carve_room_region(cells)
        for x, y in cells:
            open_anchor(x, y, ".")
            dungeon[y][x] = STAIRS_UP
        complexes.append(cells)
    for kind, cells in groups:
        if kind != "cave":
            continue
        for x, y in cells:
            carve_cave_region(x, y)

    player["x"] = arrive_x
    player["y"] = arrive_y
    rebuild_floor_list()

    taken = []
    for cells in caves + complexes:
        taken.extend(cells)
    for cells in caves:
        place_cave_links(cells, taken, index, parent)
    for cells in complexes:
        place_complex_links(cells, taken, index)
    for cells in caves:
        link_cave_to_complex(cells[0])

    rebuild_floor_list()
    for _ in range(6 + level + index * 2):
        items.append(make_item(*random_floor()))
    populate_layer(index)
    update_visibility()


def place_link(cells, origins, taken, wanted, tile, reach, floor=LINK_GAP_FLOOR):
    for gap in range(LINK_GAP, floor - 1, -1):
        for cell in shuffled(cells):
            if dungeon[cell[1]][cell[0]] != wanted:
                continue
            if group_gap(taken, cell) < gap or group_gap(origins, cell) < reach:
                continue
            dungeon[cell[1]][cell[0]] = tile
            return cell
        reach = max(0, reach - 2)
    return None


def group_gap(origins, cell):
    nearest = 999
    for ox, oy in origins:
        gap = abs(cell[0] - ox) + abs(cell[1] - oy)
        if gap < nearest:
            nearest = gap
    return nearest


def open_beside(grid, cell, outside):
    x, y = cell
    for dx, dy in STEPS:
        nx = x + dx
        ny = y + dy
        if 0 <= nx < MAP_W and 0 <= ny < MAP_H and tile_open(grid[ny][nx], outside):
            return True
    return False


def cave_ladder_candidates(region, taken, parent, parent_outside):
    above = []
    beside = []
    for cell in region:
        if cell in taken or dungeon[cell[1]][cell[0]] != CAVE_FLOOR:
            continue
        if tile_open(parent[cell[1]][cell[0]], parent_outside):
            above.append(cell)
        elif open_beside(parent, cell, parent_outside):
            beside.append(cell)
    return above, beside


def place_cave_links(anchors, taken, index, parent):
    parent_outside = index == 1
    for anchor in anchors:
        region = region_cells(anchor)
        if any(dungeon[y][x] == LADDER_UP or dungeon[y][x] == STAIRS_UP for x, y in region):
            continue
        above, beside = cave_ladder_candidates(region, taken, parent, parent_outside)
        ladder = place_link(above, anchors, taken, CAVE_FLOOR, LADDER_UP, 6, 1)
        if ladder is None:
            ladder = place_link(beside, anchors, taken, CAVE_FLOOR, LADDER_UP, 0, 1)
        if ladder is not None:
            taken.append(ladder)

    if index >= MAX_LAYER:
        return
    hole = place_link(region_cells(anchors[0]), anchors, taken, CAVE_FLOOR, HOLE, 4)
    if hole is not None:
        taken.append(hole)


def place_complex_links(anchors, taken, index):
    if index >= MAX_LAYER:
        return
    stairs = place_link(region_cells(anchors[0]), anchors, taken, ".", STAIRS_DOWN, 5)
    if stairs is not None:
        taken.append(stairs)


def passage_from(cell, dx, dy):
    x, y = cell
    dug = []
    for _ in range(PASSAGE_REACH):
        x += dx
        y += dy
        if x < 1 or y < 1 or x >= MAP_W - 1 or y >= MAP_H - 1:
            return None
        tile = dungeon[y][x]
        if tile == ROCK:
            dug.append((x, y))
            continue
        if tile in "|-" and dungeon[y + dy][x + dx] == "." and dug:
            return dug + [(x, y)]
        return None
    return None


def link_cave_to_complex(anchor):
    if random.randrange(100) >= PASSAGE_CHANCE:
        return None

    routes = []
    for cell in region_cells(anchor):
        if dungeon[cell[1]][cell[0]] != CAVE_FLOOR:
            continue
        for dx, dy in STEPS:
            route = passage_from(cell, dx, dy)
            if route is not None:
                routes.append(route)

    if not routes:
        return None

    route = routes[random.randrange(len(routes))]
    for x, y in route[:-1]:
        dungeon[y][x] = "#"
    door_x, door_y = route[-1]
    dungeon[door_y][door_x] = "."
    return route


def populate_layer(index):
    budget = 6 + level * 2 + index * 2
    for _ in range(budget):
        x, y = random_floor(False, 7)
        char = random_enemy_char(habitat_at(x, y))
        if char is not None:
            enemies.append(make_enemy(x, y, char))


def shuffled(cells):
    pool = cells[:]
    order = []
    while pool:
        order.append(pool.pop(random.randrange(len(pool))))
    return order


def build_surface(attempt=0, seed=None):
    global gate, gate_side, gate_unlocked, area_seed

    if seed is not None:
        area_seed = seed
        random.seed(seed)

    blank_area(OPEN_GROUND)
    gate = None
    gate_side = None
    gate_unlocked = False

    room_goal = 8 + min(6, level)
    if attempt > 3:
        room_goal = 7
    if attempt > 7:
        room_goal = 4
    tries = 0

    while len(rooms) < room_goal and tries < 200:
        tries += 1
        w = random.randrange(4, 9)
        h = random.randrange(3, 7)
        x = random.randrange(1, MAP_W - w - 1)
        y = random.randrange(1, MAP_H - h - 1)
        room = (x, y, w, h)
        if intersects(room):
            continue
        carve_room(room)
        rooms.append(room)

    if len(rooms) < 2:
        build_surface(attempt + 1)
        return

    player["x"], player["y"] = room_center(rooms[0])

    for index in range(1, len(rooms)):
        connect_rooms(rooms[index - 1], rooms[index])

    scatter_outdoors()
    if not dungeon_connected():
        build_surface(attempt + 1)
        return

    stairs_x, stairs_y = room_center(rooms[-1])
    dungeon[stairs_y][stairs_x] = STAIRS_DOWN
    rebuild_floor_list()

    for _ in range(12 + level * 2):
        items.append(make_item(*random_floor()))

    place_entry()
    if not place_surface_goal():
        build_surface(attempt + 1)
        return

    rebuild_floor_list()
    for _ in range(8 + level * 3):
        x, y = random_floor(True, 7)
        char = random_enemy_char("surface")
        if char is not None:
            enemies.append(make_enemy(x, y, char))

    update_visibility()


def new_game():
    global state, level, kills, turns, items_found, command_open, pack, identified_scrolls, pack_cursor
    global ruin, layer, layer_cache
    global run_seed, surface_seed

    run_seed = badge.ticks & SEED_MASK
    random.seed(run_seed)
    level = 1
    ruin = 1
    kills = 0
    turns = 0
    items_found = 0
    command_open = False
    layer = 0
    layer_cache = {}
    player["hp"] = player["max_hp"]
    player["atk"] = 4
    player["armor"] = 0
    player["gold"] = 0
    player["confuse"] = 0
    player["sleep"] = 0
    player["weapon_cursed"] = False
    player["armor_cursed"] = False
    player["pack_slots"] = PACK_BLOCK
    pack = []
    identified_scrolls = {"identify": True}
    pack_cursor = 0
    message_log.clear()
    surface_seed = surface_seed_for(ruin)
    build_surface(seed=surface_seed)
    say("You wake in a dark ruin.")
    state = GameState.PLAYING
    mark_dirty()


def next_level():
    global level, layer, ruin, entry_side, entry_offset, layer_cache, surface_seed

    exit_side = gate_side
    exit_offset = gate[1] if gate_side in ("left", "right") else gate[0]
    ruin += 1
    level += 1
    layer = 0
    layer_cache = {}
    entry_side = opposite_side(exit_side)
    entry_offset = exit_offset
    surface_seed = surface_seed_for(ruin)
    build_surface(seed=surface_seed)
    entry_side = None
    entry_offset = None
    say("You enter ruin " + str(ruin) + ".")
    player["hp"] = min(player["max_hp"], player["hp"] + 4)
    mark_dirty()


def outdoors():
    return layer == 0


def tile_open(tile, outside):
    return tile in PASSABLE_TILES or (tile == OPEN_GROUND and outside)


def passable(x, y):
    if x < 0 or y < 0 or x >= MAP_W or y >= MAP_H:
        return False
    return tile_open(dungeon[y][x], outdoors())


def blocks_sight(x, y):
    return x < 0 or y < 0 or x >= MAP_W or y >= MAP_H or dungeon[y][x] in SIGHT_BLOCKERS


def has_los(x1, y1, x2, y2):
    dx = abs(x2 - x1)
    dy = -abs(y2 - y1)
    sx = 1 if x1 < x2 else -1
    sy = 1 if y1 < y2 else -1
    err = dx + dy
    x = x1
    y = y1

    while True:
        if x == x2 and y == y2:
            return True
        if (x != x1 or y != y1) and blocks_sight(x, y):
            return x == x2 and y == y2
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy


def update_visibility():
    for row in visible:
        row[:] = HIDDEN_ROW

    room = current_room()
    if room is not None:
        rx, ry, rw, rh = room
        for y in range(ry, ry + rh):
            for x in range(rx, rx + rw):
                visible[y][x] = True
                explored[y][x] = True
                if dungeon[y][x] == "." and (x == rx or x == rx + rw - 1 or y == ry or y == ry + rh - 1):
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx = x + dx
                        ny = y + dy
                        if nx < 0 or ny < 0 or nx >= MAP_W or ny >= MAP_H or point_in_room(nx, ny, room):
                            continue
                        if passable(nx, ny) or enemy_at(nx, ny) is not None:
                            visible[ny][nx] = True
                            explored[ny][nx] = True
        return

    sight = player["sight"]
    for y in range(max(0, player["y"] - sight), min(MAP_H, player["y"] + sight + 1)):
        for x in range(max(0, player["x"] - sight), min(MAP_W, player["x"] + sight + 1)):
            if abs(player["x"] - x) + abs(player["y"] - y) <= sight and has_los(player["x"], player["y"], x, y):
                visible[y][x] = True
                explored[y][x] = True


def hit_roll(chance):
    return random.randrange(100) < clamp(chance, 5, 95)


def player_hit_chance(enemy):
    return PLAYER_ACCURACY + level - enemy_kind(enemy)["dodge"]


def enemy_hit_chance(enemy):
    return enemy_kind(enemy)["accuracy"] - player["armor"] * 4


def kill_enemy(enemy):
    global kills

    kills += 1
    player["gold"] += random.randrange(1, 5 + level)
    say(enemy_name(enemy) + " falls.")

    if enemy["loot"] > 0:
        player["gold"] += enemy["loot"]
        say("You recover " + str(enemy["loot"]) + " gold.")
        enemy["loot"] = 0


def attack(enemy):
    if player["confuse"] > 0:
        player["confuse"] = 0
        enemy["confused"] = 6
        say(enemy_name(enemy) + " stares wildly.")
        return

    if not hit_roll(player_hit_chance(enemy)):
        say("You miss " + enemy_name(enemy) + ".")
        return

    damage = random.randrange(1, player["atk"] + 1)
    enemy["hp"] -= damage
    say("You hit " + enemy_name(enemy) + " for " + str(damage) + ".")
    if enemy["hp"] <= 0:
        kill_enemy(enemy)
        return

    paralyse = enemy_kind(enemy).get("paralyse", 0)
    if paralyse > 0:
        player["sleep"] = max(player["sleep"], paralyse)
        say(enemy_name(enemy) + " holds you rigid.")


def nearest_visible_enemy():
    closest = None
    closest_distance = 999
    for enemy in enemies:
        if enemy["hp"] <= 0 or not visible[enemy["y"]][enemy["x"]]:
            continue
        gap = abs(enemy["x"] - player["x"]) + abs(enemy["y"] - player["y"])
        if gap < closest_distance:
            closest = enemy
            closest_distance = gap
    return closest


def shoot_bow():
    if equipped_bow() is None or arrow_count() <= 0:
        return False
    enemy = nearest_visible_enemy()
    if enemy is None:
        return False

    consume_arrow()
    enemy["skip"] += 1

    if not hit_roll(player_hit_chance(enemy) + BOW_ACCURACY_BONUS):
        say("Your arrow misses " + enemy_name(enemy) + ".")
        return True

    damage = random.randrange(2, player["atk"] + 2)
    enemy["hp"] -= damage
    say("Arrow hits " + enemy_name(enemy) + " for " + str(damage) + ".")
    if enemy["hp"] <= 0:
        kill_enemy(enemy)
    return True


def use_item(item):
    global items_found

    kind = item["kind"]
    if kind == "gold":
        found = random.randrange(4, 12 + level * 3)
        player["gold"] += found
        say("Gold +" + str(found) + ".")
    elif kind == "potion":
        if add_pack_item({"kind": "potion"}):
            say("You pocket a potion.")
        else:
            return
    elif kind == "scroll":
        effect = item.get("effect", random.choice(SCROLL_EFFECTS))
        if add_pack_item({"kind": "scroll", "effect": effect}):
            say("You pocket a scroll.")
        else:
            return
    elif kind == "blade":
        player["atk"] += 1
        say("Blade power rises.")
    elif kind == "shield":
        if player["armor"] >= ARMOR_CAP:
            say("You cannot carry more shielding.")
            return
        player["armor"] += 1
        say("Shielding improves.")
    elif kind == "food":
        if add_pack_item({"kind": "food"}):
            say("You pack a ration.")
        else:
            return
    elif kind == "bow":
        if pack_item("bow") is not None:
            salvaged = random.randrange(3, 8)
            if add_pack_item({"kind": "arrows", "count": salvaged}):
                say("You strip the bow for " + str(salvaged) + " arrows.")
            else:
                return
        elif add_pack_item({"kind": "bow"}):
            say("You pocket a bow.")
        else:
            return
    elif kind == "arrows":
        count = item.get("count", random.randrange(3, 8))
        if add_pack_item({"kind": "arrows", "count": count}):
            say("You pocket arrows.")
        else:
            return
    elif kind == "key":
        if add_pack_item({"kind": "key"}):
            say("You found a gate key.")
        else:
            return
    if kind != "gold":
        items_found += 1
    items.remove(item)


def step_player(dx, dy):
    x = player["x"] + dx
    y = player["y"] + dy
    enemy = enemy_at(x, y)
    if enemy is not None:
        attack(enemy)
        return True
    if gate is not None and (x, y) == gate:
        return unlock_gate()
    if not passable(x, y):
        say(blocked_message(x, y))
        return False
    player["x"] = x
    player["y"] = y
    if dungeon[y][x] == HOLE:
        fall_through_hole()
        return True
    item = item_at(x, y)
    if item is not None:
        use_item(item)
    return True


def action():
    here = dungeon[player["y"]][player["x"]]
    if here == STAIRS_UP or here == LADDER_UP:
        return ascend()
    if here == STAIRS_DOWN:
        return descend()

    if near_gate():
        return unlock_gate()

    if shoot_bow():
        return True

    player["hp"] = min(player["max_hp"], player["hp"] + 1)
    say("You wait and listen.")
    return True


def near_gate():
    return gate is not None and abs(player["x"] - gate[0]) + abs(player["y"] - gate[1]) == 1


def unlock_gate():
    global gate_unlocked

    if not outdoors() or gate is None:
        return False

    if not gate_unlocked:
        key = pack_item("key")
        if key is None:
            say("The gate is locked.")
            return False
        pack.remove(key)
        gate_unlocked = True
        say("You unlock the gate.")
        return True

    say("The gate opens.")
    next_level()
    return False


def respawn_enemies():
    living = 0
    for enemy in enemies:
        if enemy["hp"] > 0:
            living += 1
    budget = (8 + level * 3 if outdoors() else 6 + level * 2) - living
    if budget <= 0:
        return
    for _ in range(min(RESPAWN_LIMIT, budget)):
        x, y = random_floor(False, 7)
        char = random_enemy_char(habitat_at(x, y))
        if char is not None:
            enemies.append(make_enemy(x, y, char))


def enter_layer(index, arrive_x, arrive_y):
    global layer

    parent = dungeon
    layer_cache[layer] = capture_area()
    layer = index

    snapshot = layer_cache.get(index)
    if snapshot is None:
        build_layer(index, layer_seed(index), arrive_x, arrive_y, parent)
        mark_dirty()
        return

    restore_area(snapshot)
    player["x"] = arrive_x
    player["y"] = arrive_y
    rebuild_floor_list()
    respawn_enemies()
    update_visibility()
    mark_dirty()


def descend():
    if layer >= MAX_LAYER:
        return False
    enter_layer(layer + 1, player["x"], player["y"])
    if layer >= MAX_LAYER:
        say("You reach the deepest ruins.")
    else:
        say("You take the stairs down.")
    return False


def ascend():
    if layer <= 0:
        return False
    enter_layer(layer - 1, player["x"], player["y"])
    if layer == 0:
        say("You climb up into daylight.")
    else:
        say("You climb up a level.")
    return False


def fall_through_hole():
    global state

    player["hp"] -= 2
    if player["hp"] <= 0:
        state = GameState.DEAD
        say("You fall into the dark.")
        return
    if layer >= MAX_LAYER:
        say("The hole is choked with rubble.")
        return
    enter_layer(layer + 1, player["x"], player["y"])
    say("You fall through into the dark.")


def item_char(item):
    if item["kind"] == "scroll":
        effect = item["effect"]
        return SCROLLS[effect]["char"] if effect in identified_scrolls else "s"
    return ITEM_DEFS.get(item["kind"], UNKNOWN_ITEM_DEF)["char"]


def item_name(item):
    if item["kind"] == "bow" and item.get("equipped"):
        return "short bow, equipped"
    if item["kind"] == "scroll":
        effect = item["effect"]
        return SCROLLS[effect]["name"] if effect in identified_scrolls else "unidentified scroll"
    if item["kind"] == "arrows":
        return "arrows x" + str(item.get("count", 1))
    return ITEM_DEFS.get(item["kind"], UNKNOWN_ITEM_DEF)["name"]


def item_action(item):
    if item["kind"] == "bow":
        return "B stow" if item.get("equipped") else "B equip"
    return ITEM_DEFS.get(item["kind"], UNKNOWN_ITEM_DEF)["action"]


def potion_heal_max():
    return 11 + level


def item_effect(item):
    kind = item["kind"]
    if kind == "potion":
        return "heals " + str(POTION_HEAL_MIN) + "-" + str(potion_heal_max())
    if kind == "food":
        return "+1 max HP, heals " + str(FOOD_HEAL)
    if kind == "scroll":
        effect = item["effect"]
        return SCROLLS[effect]["hint"] if effect in identified_scrolls else "effect unknown"
    if kind == "arrows":
        return "ammunition, " + str(arrow_count()) + " held"
    if kind == "bow":
        if item.get("equipped"):
            return "B shoots the nearest foe"
        return "equip it to shoot arrows"
    return ITEM_DEFS.get(item["kind"], UNKNOWN_ITEM_DEF)["hint"]


def heal_preview():
    if not command_open or menu_tab != "pack":
        return 0
    item = selected_pack_item()
    if item is None:
        return 0
    if item["kind"] == "potion":
        return min(potion_heal_max(), player["max_hp"] - player["hp"])
    if item["kind"] == "food":
        return min(FOOD_HEAL, player["max_hp"] + 1 - player["hp"])
    return 0


def item_glyph(item):
    definition = ITEM_DEFS.get(item["kind"], UNKNOWN_ITEM_DEF)
    return definition["glyph"], definition["pen"]


def unidentified_pack_scroll():
    for item in pack:
        if item["kind"] == "scroll" and item["effect"] not in identified_scrolls:
            return item
    return None


def identify_pack_item():
    item = unidentified_pack_scroll()
    if item is None:
        say("Nothing else is mysterious.")
        return
    identified_scrolls[item["effect"]] = True
    say("Now known: " + SCROLLS[item["effect"]]["name"] + ".")


def dropped_item(item):
    floor_item = {"x": player["x"], "y": player["y"], "kind": item["kind"]}
    if item["kind"] == "scroll":
        floor_item["effect"] = item["effect"]
    elif item["kind"] == "arrows":
        floor_item["count"] = item.get("count", 5)
    return floor_item


def drop_pack_item():
    global pack_cursor

    item = selected_pack_item()
    if item is None:
        close_command_menu()
        return False
    if item_at(player["x"], player["y"]) is not None:
        say("No room to drop it.")
        return False

    items.append(dropped_item(item))
    pack.pop(pack_cursor)
    pack_cursor = min(pack_cursor, max(0, len(pack) - 1))
    say("Dropped " + item_name(item) + ".")
    return True


def use_pack_item():
    global pack_cursor

    item = selected_pack_item()
    if item is None:
        say("Your pack is empty.")
        return False
    pack.pop(pack_cursor)

    if item["kind"] == "potion":
        heal = random.randrange(POTION_HEAL_MIN, potion_heal_max() + 1)
        player["hp"] = min(player["max_hp"], player["hp"] + heal)
        say("Potion heals " + str(heal) + ".")
        return True
    if item["kind"] == "food":
        player["max_hp"] += 1
        player["hp"] = min(player["max_hp"], player["hp"] + FOOD_HEAL)
        say("You eat a ration.")
        return True
    if item["kind"] == "bow":
        pack.insert(pack_cursor, item)
        if item.get("equipped"):
            item["equipped"] = False
            say("You stow the bow.")
        else:
            item["equipped"] = True
            say("You ready the bow.")
        return False
    if item["kind"] == "arrows":
        pack.insert(pack_cursor, item)
        say("Arrows: " + str(item.get("count", 1)) + ".")
        return False
    if item["kind"] == "key":
        pack.insert(pack_cursor, item)
        say("A key for a gate.")
        return False
    if item["kind"] == "scroll":
        effect = item["effect"]
        if effect == "identify" and unidentified_pack_scroll() is None:
            pack.insert(pack_cursor, item)
            say("Nothing else is mysterious.")
            return False
        identified_scrolls[effect] = True
        apply_scroll_effect(effect)
        if effect == "identify":
            identify_pack_item()
        pack_cursor = min(pack_cursor, max(0, len(pack) - 1))
        return True

    say("Nothing happens.")
    return False


def reveal_items(kind):
    found = False
    for item in items:
        if item["kind"] == kind:
            explored[item["y"]][item["x"]] = True
            found = True
    return found


def nearby_enemies(radius=6):
    found = []
    for enemy in enemies:
        if enemy["hp"] > 0 and abs(enemy["x"] - player["x"]) + abs(enemy["y"] - player["y"]) <= radius:
            found.append(enemy)
    return found


def scroll_identify():
    say("This scroll is an identify scroll.")


def scroll_enchant_armor():
    player["armor"] = min(ARMOR_CAP + 2, player["armor"] + 1)
    player["armor_cursed"] = False
    say("Your armor glows faintly for a moment.")


def scroll_enchant_weapon():
    player["atk"] += 1
    player["weapon_cursed"] = False
    say("Your weapon glows blue for a moment.")


def scroll_mapping():
    for y in range(MAP_H):
        for x in range(MAP_W):
            if dungeon[y][x] != " " or outdoors():
                explored[y][x] = True
    say("Oh, now this scroll has a map on it.")


def scroll_teleport():
    x, y = random_floor(False, 0)
    player["x"] = x
    player["y"] = y


def scroll_gold_detection():
    reveal_items("gold")


def scroll_remove_curse():
    player["weapon_cursed"] = False
    player["armor_cursed"] = False
    say("You feel as if somebody is watching over you.")


def scroll_carry():
    if player["pack_slots"] < PACK_MAX_SLOTS:
        player["pack_slots"] = min(PACK_MAX_SLOTS, player["pack_slots"] + PACK_BLOCK)
        say("Your pack feels roomier.")
    else:
        say("Your pack cannot hold more.")


def scroll_hold_monster():
    for enemy in nearby_enemies():
        enemy["held"] = 5
    say("The monsters around you stop moving.")


def scroll_scare_monster():
    for enemy in nearby_enemies(9):
        enemy["scared"] = 8
    say("You hear maniacal laughter in the distance")


def scroll_food_detection():
    if reveal_items("food"):
        say("Your nose tingles as you sense food.")
    else:
        say("Your nose tingles briefly.")


def scroll_monster_confusion():
    player["confuse"] = 1
    say("Your hands begin to glow red")


def scroll_sleep():
    player["sleep"] = 4
    say("You fall asleep")


def scroll_create_monster():
    x, y = random_floor(False, 5)
    char = random_enemy_char(habitat_at(x, y))
    if char is not None:
        enemies.append(make_enemy(x, y, char))
    say("You hear a faint cry of anguish")


def scroll_aggravate():
    for enemy in enemies:
        enemy["awake"] = True
    say("You hear a high pitched humming noise")


def scroll_blank():
    say("This scroll seems to be blank.")


SCROLL_HANDLERS = {
    "identify": scroll_identify,
    "enchant_armor": scroll_enchant_armor,
    "enchant_weapon": scroll_enchant_weapon,
    "mapping": scroll_mapping,
    "teleport": scroll_teleport,
    "gold_detection": scroll_gold_detection,
    "remove_curse": scroll_remove_curse,
    "carry": scroll_carry,
    "hold_monster": scroll_hold_monster,
    "scare_monster": scroll_scare_monster,
    "food_detection": scroll_food_detection,
    "monster_confusion": scroll_monster_confusion,
    "sleep": scroll_sleep,
    "create_monster": scroll_create_monster,
    "aggravate": scroll_aggravate,
    "blank": scroll_blank,
}


def apply_scroll_effect(effect):
    SCROLL_HANDLERS.get(effect, scroll_blank)()
    update_visibility()


def distance_to_player(enemy):
    return abs(enemy["x"] - player["x"]) + abs(enemy["y"] - player["y"])


def flee_by_teleport(enemy):
    enemy["x"], enemy["y"] = random_floor(False, 8)
    enemy["awake"] = False


def steal_gold(enemy):
    stolen = min(player["gold"], player["gold"] // 3 + random.randrange(10, 30 + level * 3))
    player["gold"] -= stolen
    enemy["loot"] += stolen
    if stolen > 0:
        say(enemy_name(enemy) + " steals " + str(stolen) + " gold.")
    else:
        say(enemy_name(enemy) + " finds no gold.")
    flee_by_teleport(enemy)


def steal_item(enemy):
    global pack_cursor

    if len(pack) == 0:
        say(enemy_name(enemy) + " finds nothing to take.")
        return
    item = pack.pop(random.randrange(len(pack)))
    pack_cursor = min(pack_cursor, max(0, len(pack) - 1))
    say(enemy_name(enemy) + " steals your " + item_name(item) + ".")
    flee_by_teleport(enemy)


def rust_armor(enemy):
    if player["armor"] <= 0:
        say(enemy_name(enemy) + " splashes you.")
        return
    player["armor"] -= 1
    player["armor_cursed"] = False
    say("Your armor corrodes.")


def strike_player(enemy):
    if not hit_roll(enemy_hit_chance(enemy)):
        say(enemy_name(enemy) + " misses.")
        return

    on_hit = enemy_kind(enemy).get("on_hit")
    if on_hit == "steal_gold":
        steal_gold(enemy)
        return
    if on_hit == "steal_item":
        steal_item(enemy)
        return
    if on_hit == "rust":
        rust_armor(enemy)
        return

    if enemy["atk"] <= 0:
        say(enemy_name(enemy) + " lunges at you.")
        return

    damage = max(1, random.randrange(1, enemy["atk"] + 1) - player["armor"])
    player["hp"] -= damage
    say(enemy_name(enemy) + " hits for " + str(damage) + ".")


def step_towards_player(enemy):
    if abs(player["x"] - enemy["x"]) > abs(player["y"] - enemy["y"]):
        return (1 if player["x"] > enemy["x"] else -1), 0
    return 0, (1 if player["y"] > enemy["y"] else -1)


def step_away_from_player(enemy):
    if abs(player["x"] - enemy["x"]) > abs(player["y"] - enemy["y"]):
        return (-1 if player["x"] > enemy["x"] else 1), 0
    return 0, (-1 if player["y"] > enemy["y"] else 1)


def enemy_move(enemy, move):
    dx = 0
    dy = 0
    if enemy["confused"] > 0 or move == "erratic":
        dx, dy = random.choice(STEPS)
    elif enemy["scared"] > 0:
        dx, dy = step_away_from_player(enemy)
    elif distance_to_player(enemy) <= player["sight"] or enemy["awake"]:
        enemy["awake"] = True
        dx, dy = step_towards_player(enemy)
    elif random.randrange(3) == 0:
        dx, dy = random.choice(STEPS)

    if dx == 0 and dy == 0:
        return True

    x = enemy["x"] + dx
    y = enemy["y"] + dy
    if x == player["x"] and y == player["y"]:
        strike_player(enemy)
        return False
    if passable(x, y) and enemy_at(x, y) is None:
        enemy["x"] = x
        enemy["y"] = y
    return True


def enemy_step(enemy):
    definition = enemy_kind(enemy)
    move = definition["move"]

    regen = definition.get("regen", 0)
    if regen > 0 and enemy["hp"] < enemy["max_hp"]:
        enemy["hp"] = min(enemy["max_hp"], enemy["hp"] + regen)

    if enemy["held"] > 0:
        enemy["held"] -= 1
        return
    if enemy["skip"] > 0:
        enemy["skip"] -= 1
        return
    if move == "still":
        return

    if enemy["confused"] > 0:
        enemy["confused"] -= 1
    elif enemy["scared"] > 0:
        enemy["scared"] -= 1

    if move == "slow":
        enemy["skip"] = 1

    for _ in range(2 if move == "fast" else 1):
        if not enemy_move(enemy, move):
            return


def enemies_take_turn():
    global state

    for enemy in enemies:
        if enemy["hp"] > 0:
            enemy_step(enemy)
        if player["hp"] <= 0:
            state = GameState.DEAD
            say("You die on level " + str(level) + ".")
            return


def take_turn(dx, dy):
    global turns

    acted = step_player(dx, dy) if dx != 0 or dy != 0 else action()
    if acted:
        turns += 1
        enemies_take_turn()
    update_visibility()
    mark_dirty()


def glyph_at(x, y):
    if not explored[y][x]:
        return " ", GRAY_6
    is_visible = visible[y][x]
    if x == player["x"] and y == player["y"]:
        return "@", GREEN_1
    if is_visible:
        enemy = enemy_at(x, y)
        if enemy is not None:
            return enemy["ch"], enemy_kind(enemy)["pen"]
        item = item_at(x, y)
        if item is not None:
            return item_glyph(item)
    if gate is not None and (x, y) == gate:
        return " ", GOLD if is_visible else GRAY_4
    return " ", GRAY_6


def cave_floor_is_dirt(x, y):
    return ((x * 73856093) ^ (y * 19349663)) % 100 < CAVE_DIRT_SHARE


def cell_patch(x, y):
    tile = dungeon[y][x]
    if gate is not None and (x, y) == gate:
        return GATE_PATCH
    if tile == LADDER_UP:
        return LADDER_PATCH
    if tile == STAIRS_UP:
        return UP_STAIR_PATCH
    if tile == STAIRS_DOWN:
        return DOWN_STAIR_PATCH
    if tile == ".":
        return ROOM_PATCH
    if tile == "#":
        return PATH_PATCH
    if tile == CAVE_FLOOR:
        return DIRT_PATCH if outdoors() or cave_floor_is_dirt(x, y) else PATH_PATCH
    if tile == ROCK:
        return SHRUB_PATCH if outdoors() else CAVE_WALL_PATCH
    if tile == HOLE:
        return HOLE_PATCH
    if tile == SEALED_GATE:
        return GATE_PATCH
    if tile == OPEN_GROUND:
        return GRASS_PATCH if outdoors() else None
    return WALL_PATCH


def draw_cell_background(target, x, y, px, py):
    if not explored[y][x]:
        return

    patch = cell_patch(x, y)
    if patch is None:
        return
    target.blit(patch[(y & PATTERN_MASK) * PATTERN_SIZE + (x & PATTERN_MASK)], vec2(px, py))
    if not visible[y][x]:
        target.pen = SHADOW_BRUSH
        target.rectangle(px, py, CELL_W, CELL_H)


def view_origin():
    x = clamp(player["x"] - VIEW_W // 2, 0, MAP_W - VIEW_W)
    y = clamp(player["y"] - VIEW_H // 2, 0, MAP_H - VIEW_H)
    return x, y


def draw_map_pixel_double():
    vx, vy = view_origin()
    map_view.font = small_font
    map_view.pen = BLACK
    map_view.clear()

    for row in range(VIEW_H):
        y = vy + row
        for col in range(VIEW_W):
            x = vx + col
            px = col * CELL_W
            py = row * CELL_H
            draw_cell_background(map_view, x, y, px, py)
            glyph, pen = glyph_at(x, y)
            map_view.pen = pen
            map_view.text(glyph, px + 2, py - GLYPH_LIFT)

    screen.blit(map_view, rect(0, MAP_Y, MAP_STRIP_W, MAP_STRIP_H))


def minimap_pen(x, y):
    if x == player["x"] and y == player["y"]:
        return GREEN_1
    if not explored[y][x]:
        return None
    if visible[y][x] and enemy_at(x, y) is not None:
        return HURT
    if gate is not None and (x, y) == gate:
        return GOLD

    tile = dungeon[y][x]
    if tile == SEALED_GATE:
        return GOLD
    if tile == LADDER_UP:
        return GOLD
    if tile in (STAIRS_UP, STAIRS_DOWN):
        return GREEN_2
    if tile == HOLE:
        return GREEN_4
    if tile == ".":
        return MINIMAP_ROOM
    if tile == "#":
        return MINIMAP_PATH
    if tile == CAVE_FLOOR:
        return GREEN_5_GRASS if outdoors() else MINIMAP_PATH
    if tile == ROCK:
        return GREEN_5_SHRUB if outdoors() else GRAY_6
    if tile == " ":
        return GREEN_6 if outdoors() else None
    return GRAY_6


def explored_percent():
    seen = 0
    for row in explored:
        for cell in row:
            if cell:
                seen += 1
    return seen * 100 // (MAP_W * MAP_H)


def menu_stats():
    return (
        ("explored", str(explored_percent()) + "%"),
        ("kills", str(kills)),
        ("items", str(items_found)),
        ("gold", str(player["gold"])),
        ("turns", str(turns)),
        ("layer", "surface" if outdoors() else str(layer)),
        ("seed", "%08x" % area_seed),
    )


def draw_menu_stats():
    y = PACK_GRID_Y
    for label, value in menu_stats():
        draw_text(label, MENU_STAT_X, y, GRAY_4)
        value_width, _ = screen.measure_text(value)
        draw_text(value, MENU_STAT_X + MENU_STAT_W - value_width, y, GREEN_2)
        y += MENU_STAT_PITCH


def draw_menu_minimap():
    minimap_view.pen = BLACK
    minimap_view.clear()

    for y in range(MAP_H):
        for x in range(MAP_W):
            pen = minimap_pen(x, y)
            if pen is None:
                continue
            minimap_view.pen = pen
            minimap_view.put(x, y)

    screen.pen = GREEN_6
    screen.shape(shape.rectangle(MENU_MAP_X - 1, MENU_MAP_Y - 1, MENU_MAP_W + 2, MENU_MAP_H + 2).stroke(1))
    screen.blit(minimap_view, rect(MENU_MAP_X, MENU_MAP_Y, MENU_MAP_W, MENU_MAP_H))


def draw_text(text, x, y, pen):
    screen.pen = pen
    screen.text(text, x, y)


def draw_clipped(text, x, y, width, pen):
    screen.pen = pen
    screen.text(text, rect(x, y, width, 14), overflow=ELLIPSES)


def draw_message(text, y, pen):
    draw_clipped(text, 4, y, LOG_W, pen)


def draw_centered(text, y, pen):
    w, _ = screen.measure_text(text)
    draw_text(text, (WIDTH - w) / 2, y, pen)


def draw_intro():
    screen.pen = BLACK
    screen.clear()
    screen.font = large_font
    draw_centered("ROGUE", 54, GREEN_1)
    screen.font = small_font
    draw_centered("A/C move left/right", 95, GRAY_3)
    draw_centered("UP/DOWN move vertically", 112, GRAY_3)
    draw_centered("B waits, descends, restarts", 129, GRAY_3)
    draw_centered("Find stairs. Take powerups. Survive.", 154, GREEN_3)
    if int(badge.ticks / 500) % 2:
        draw_centered("Press B", 188, GREEN_1)


def draw_game():
    screen.pen = BLACK
    screen.clear()
    screen.font = small_font

    hp_text = "HP " + str(player["hp"]) + "/" + str(player["max_hp"])
    draw_text(hp_text, 4, 4, GREEN_1 if player["hp"] > 5 else HURT)
    heal = heal_preview()
    if heal > 0:
        draw_text("+" + str(heal), 6 + screen.measure_text(hp_text)[0], 4, GREEN_3)
    draw_text("D" + str(level), 75, 4, GRAY_2)
    draw_text("ATK " + str(player["atk"]), 112, 4, GRAY_3)
    draw_text("ARM " + str(player["armor"]), 168, 4, GRAY_3)
    draw_text("!" + str(pack_count("potion")), 238, 4, GREEN_2)
    draw_text("?" + str(pack_count("scroll")), 270, 4, PURPLE)
    draw_text("/" + str(arrow_count()), 300, 4, GRAY_2)

    screen.pen = BLACK
    screen.rectangle(0, MAP_Y - 4, WIDTH, MAP_STRIP_H + 6)

    draw_map_pixel_double()

    for index, message in enumerate(message_log):
        draw_message(message, LOG_Y + index * 12, GRAY_2 if index == len(message_log) - 1 else GRAY_4)

    if command_open:
        draw_command_menu()


def pack_slot_origin(slot):
    return PACK_GRID_X + (slot % PACK_COLS) * PACK_SLOT, PACK_GRID_Y + (slot // PACK_COLS) * PACK_SLOT


def draw_pack_slot(slot):
    x, y = pack_slot_origin(slot)

    if slot >= player["pack_slots"]:
        screen.pen = PACK_LOCKED
        screen.shape(shape.rectangle(x, y, PACK_BOX, PACK_BOX).stroke(1))
        return

    selected = slot == pack_cursor
    screen.pen = GREEN_6 if selected else GRAY_6
    screen.rectangle(x, y, PACK_BOX, PACK_BOX)
    screen.pen = GREEN_2 if selected else GRAY_4
    screen.shape(shape.rectangle(x, y, PACK_BOX, PACK_BOX).stroke(2 if selected else 1))

    if slot >= len(pack):
        return

    glyph = item_char(pack[slot])
    glyph_w, glyph_h = screen.measure_text(glyph)
    if pack[slot].get("equipped"):
        screen.pen = GOLD
    else:
        screen.pen = GREEN_1 if selected else GRAY_1
    screen.text(glyph, x + (PACK_BOX - glyph_w) / 2, y + (PACK_BOX - glyph_h) / 2)


def draw_menu_tabs():
    widths = []
    total = MENU_TAB_GAP * (len(MENU_TABS) - 1)
    for _key, label in MENU_TABS:
        width, _ = screen.measure_text(label)
        widths.append(width)
        total += width

    x = (WIDTH - total) / 2
    for index, (key, label) in enumerate(MENU_TABS):
        selected = key == menu_tab
        draw_text(label, x, PACK_TITLE_Y, GREEN_1 if selected else GRAY_4)
        if selected:
            screen.pen = GREEN_2
            screen.rectangle(x, PACK_TITLE_Y + MENU_TAB_RULE, widths[index], 1)
        x += widths[index] + MENU_TAB_GAP

    close_width, _ = screen.measure_text("HOME close")
    draw_text("HOME close", WIDTH - close_width - 6, PACK_TITLE_Y, GRAY_5)
    draw_text("DOWN pack" if menu_tab == "map" else "UP map", 6, PACK_TITLE_Y, GRAY_5)


def draw_command_menu():
    top = MENU_PANEL_Y if menu_tab == "map" else PACK_PANEL_Y
    height = MENU_PANEL_H if menu_tab == "map" else PACK_PANEL_H
    screen.pen = PACK_BACKDROP
    screen.rectangle(0, top, WIDTH, height)
    screen.pen = GREEN_6
    screen.shape(shape.rectangle(1, top + 1, WIDTH - 2, height - 2).stroke(1))

    draw_menu_tabs()

    if menu_tab == "map":
        draw_menu_minimap()
        draw_menu_stats()
        return

    for slot in range(PACK_MAX_SLOTS):
        draw_pack_slot(slot)

    item = selected_pack_item()
    if item is None:
        draw_centered("Pack is empty" if len(pack) == 0 else "Empty slot", PACK_NAME_Y, GRAY_3)
        return

    draw_centered(item_name(item), PACK_NAME_Y, GRAY_1)
    effect = item_effect(item)
    if effect:
        draw_centered(effect, PACK_EFFECT_Y, GREEN_2)
    draw_centered(item_action(item) + "   A+C drop", PACK_HINT_Y, GREEN_3)


def draw_doubled(text, chosen_font, y, pen):
    banner_view.font = chosen_font
    banner_view.pen = BLACK
    banner_view.clear()
    width, _height = banner_view.measure_text(text)
    banner_view.pen = pen
    banner_view.text(text, (banner_view.width - width) / 2, 0)
    screen.blit(banner_view, rect(0, y, banner_view.width * 2, banner_view.height * 2))


def draw_dead():
    draw_game()
    screen.pen = BLACK
    screen.rectangle(0, PACK_PANEL_Y, WIDTH, PACK_PANEL_H)

    draw_doubled("YOU DIED", large_font, DEAD_TITLE_Y, HURT)
    draw_doubled("B to explore again", small_font, DEAD_HINT_Y, GREEN_1)

    screen.pen = HURT
    screen.shape(shape.rectangle(1, PACK_PANEL_Y + 1, WIDTH - 2, PACK_PANEL_H - 2).stroke(1))
    screen.font = small_font


def redraw():
    if state == GameState.INTRO:
        draw_intro()
    elif state == GameState.PLAYING:
        draw_game()
    elif state == GameState.DEAD:
        draw_dead()


def toggle_command_menu():
    global command_open, command_open_ticks, needs_draw, menu_tab

    if state != GameState.PLAYING or badge.ticks - command_open_ticks < 180:
        return
    command_open = not command_open
    command_open_ticks = badge.ticks
    if command_open:
        menu_tab = "pack"
    needs_draw = True


def home_pressed(_pin):
    toggle_command_menu()


def close_command_menu():
    global command_open

    command_open = False
    mark_dirty()


def command_input():
    global pack_cursor, turns, menu_tab

    if pressed(BUTTON_COMMAND):
        toggle_command_menu()
        return
    if menu_tab == "map":
        if pressed(BUTTON_DOWN) or pressed(BUTTON_ACTION):
            menu_tab = "pack"
            mark_dirty()
        return
    if held(BUTTON_MOVE_LEFT) and held(BUTTON_MOVE_RIGHT):
        acted = drop_pack_item()
        close_command_menu()
        if acted:
            turns += 1
            enemies_take_turn()
            update_visibility()
        return
    if pressed(BUTTON_MOVE_LEFT):
        pack_cursor = max(0, pack_cursor - 1)
        mark_dirty()
        return
    if pressed(BUTTON_MOVE_RIGHT):
        pack_cursor = min(player["pack_slots"] - 1, pack_cursor + 1)
        mark_dirty()
        return
    if pressed(BUTTON_UP):
        if pack_cursor < PACK_COLS:
            menu_tab = "map"
        else:
            pack_cursor -= PACK_COLS
        mark_dirty()
        return
    if pressed(BUTTON_DOWN):
        pack_cursor = min(player["pack_slots"] - 1, pack_cursor + PACK_COLS)
        mark_dirty()
        return
    if pressed(BUTTON_ACTION):
        if selected_pack_item() is None:
            close_command_menu()
            return
        acted = use_pack_item()
        close_command_menu()
        if acted:
            turns += 1
            enemies_take_turn()
            update_visibility()
        mark_dirty()


def any_control_pressed():
    return pressed(BUTTON_MOVE_LEFT) or pressed(BUTTON_MOVE_RIGHT) or pressed(BUTTON_UP) or pressed(BUTTON_DOWN) or pressed(BUTTON_ACTION) or pressed(BUTTON_COMMAND)


def sleep_turn():
    global turns

    if player["sleep"] <= 0 or not any_control_pressed():
        return False
    player["sleep"] -= 1
    turns += 1
    say("You sleep.")
    enemies_take_turn()
    update_visibility()
    mark_dirty()
    return True


def update():
    global needs_draw

    acted = False
    if state == GameState.INTRO:
        if pressed(BUTTON_ACTION):
            new_game()
        elif int(badge.ticks / 500) != int((badge.ticks - badge.ticks_delta) / 500):
            mark_dirty()
    elif state == GameState.PLAYING:
        if sleep_turn():
            acted = True
        elif command_open:
            command_input()
        elif pressed(BUTTON_COMMAND):
            toggle_command_menu()
        elif pressed(BUTTON_MOVE_LEFT):
            take_turn(-1, 0)
            acted = True
        elif pressed(BUTTON_MOVE_RIGHT):
            take_turn(1, 0)
            acted = True
        elif pressed(BUTTON_UP):
            take_turn(0, -1)
            acted = True
        elif pressed(BUTTON_DOWN):
            take_turn(0, 1)
            acted = True
        elif pressed(BUTTON_ACTION):
            take_turn(0, 0)
            acted = True
    elif state == GameState.DEAD and pressed(BUTTON_ACTION):
        new_game()
        acted = True

    if needs_draw or acted:
        redraw()
        needs_draw = False


def on_exit():
    badge.default_clear = BLACK


machine.Pin.board.BUTTON_HOME.irq(trigger=machine.Pin.IRQ_FALLING, handler=home_pressed)
mark_dirty()
run(update)


