import random


MAP_W = 32
MAP_H = 32
CELL_COUNT = MAP_W * MAP_H
STEPS = ((1, 0), (-1, 0), (0, 1), (0, -1))

OPEN_GROUND = " "
ROCK = "^"
ROOM_FLOOR = "."
PATH = "#"
DIRT = ","
HOLE = "o"
STAIRS_DOWN = ">"
STAIRS_UP = "<"
LADDER_UP = "u"
SEALED_GATE = "="
H_WALL = "-"
V_WALL = "|"
PASSABLE_TILES = ".#,o><u"
CAVE_TILES = ",ou"
ROOM_TILES = ".#|-"
SIGHT_BLOCKERS = "|-^="
SURFACE_FLOOR = "."
UNDER_FLOOR = ".,#"
FLOOR_SAMPLE_TRIES = 24
MAX_LAYER = 2

HIDDEN_ROW = [False] * MAP_W
REACH_CLEAR = bytes(CELL_COUNT)
reach_flags = bytearray(CELL_COUNT)
reach_queue = [0] * CELL_COUNT


def distance(ax, ay, bx, by):
    return abs(ax - bx) + abs(ay - by)


def in_map(x, y):
    return 0 <= x < MAP_W and 0 <= y < MAP_H


def cell_index(cell):
    return cell[1] * MAP_W + cell[0]


def tile_open(tile, outdoors):
    return tile in PASSABLE_TILES or (tile == OPEN_GROUND and outdoors)


def room_center(room):
    x, y, w, h = room
    return x + w // 2, y + h // 2


def point_in_room(x, y, room):
    rx, ry, rw, rh = room
    return rx <= x < rx + rw and ry <= y < ry + rh


def hit_roll(chance):
    return random.randrange(100) < clamp(chance, 5, 95)


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


class Item:
    def __init__(self, kind, x=0, y=0, effect=None, count=0, cursed=False):
        self.kind = kind
        self.x = x
        self.y = y
        self.effect = effect
        self.count = count
        self.equipped = False
        self.cursed = cursed


class Area:
    def __init__(self, layer, level, seed):
        self.layer = layer
        self.level = level
        self.seed = seed
        self.outdoors = layer == 0
        self.fill = OPEN_GROUND if self.outdoors else ROCK
        self.floor_tiles = SURFACE_FLOOR if self.outdoors else UNDER_FLOOR
        self.tiles = [[self.fill] * MAP_W for _ in range(MAP_H)]
        self.explored = [[False] * MAP_W for _ in range(MAP_H)]
        self.visible = [[False] * MAP_W for _ in range(MAP_H)]
        self.rooms = []
        self.items = []
        self.enemies = []
        self.floor = []
        self.gate = None
        self.gate_side = None
        self.gate_unlocked = False
        self.origin = None

    def passable(self, x, y):
        return in_map(x, y) and tile_open(self.tiles[y][x], self.outdoors)

    def enemy_at(self, x, y):
        for enemy in self.enemies:
            if enemy.x == x and enemy.y == y:
                return enemy
        return None

    def item_at(self, x, y):
        for item in self.items:
            if item.x == x and item.y == y:
                return item
        return None

    def habitat(self, x, y):
        if self.outdoors:
            return "surface"
        return "cave" if self.tiles[y][x] in CAVE_TILES else "pocket"

    def nearby_enemies(self, x, y, radius):
        return [enemy for enemy in self.enemies if distance(enemy.x, enemy.y, x, y) <= radius]

    def exploration(self):
        seen = 0
        total = 0
        for y in range(MAP_H):
            tiles = self.tiles[y]
            explored = self.explored[y]
            for x in range(MAP_W):
                if tile_open(tiles[x], self.outdoors):
                    total += 1
                    if explored[x]:
                        seen += 1
        return seen, total

    def reveal(self, kind):
        found = False
        for item in self.items:
            if item.kind == kind:
                self.explored[item.y][item.x] = True
                found = True
        return found

    def reachable(self, x, y):
        flags = reach_flags
        queue = reach_queue
        tiles = self.tiles
        outdoors = self.outdoors
        flags[:] = REACH_CLEAR

        index = y * MAP_W + x
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
                if not in_map(nx, ny):
                    continue
                step = ny * MAP_W + nx
                if flags[step]:
                    continue
                if tile_open(tiles[ny][nx], outdoors):
                    flags[step] = 1
                    queue[tail] = step
                    tail += 1

        return bytes(flags)

    def region(self, cell):
        reachable = self.reachable(cell[0], cell[1])
        return [(index % MAP_W, index // MAP_W) for index in range(CELL_COUNT) if reachable[index]]

    def rebuild_floor(self):
        wanted = self.floor_tiles
        self.floor = [(x, y) for y in range(1, MAP_H - 1) for x in range(1, MAP_W - 1) if self.tiles[y][x] in wanted]

    def free(self, x, y, player):
        if self.tiles[y][x] not in self.floor_tiles or (x == player.x and y == player.y):
            return False
        return self.enemy_at(x, y) is None and self.item_at(x, y) is None

    def suits(self, x, y, player, avoid_start, min_distance):
        if avoid_start and self.rooms and point_in_room(x, y, self.rooms[0]):
            return False
        return not min_distance or distance(x, y, player.x, player.y) >= min_distance

    def random_floor(self, player, avoid_start=False, min_distance=0):
        floor = self.floor
        for _ in range(FLOOR_SAMPLE_TRIES):
            if len(floor) == 0:
                break
            x, y = floor[random.randrange(len(floor))]
            if self.free(x, y, player) and self.suits(x, y, player, avoid_start, min_distance):
                return x, y
        return self.scan_floor(player, avoid_start, min_distance)

    def scan_floor(self, player, avoid_start, min_distance):
        candidates = [(x, y) for y in range(1, MAP_H - 1) for x in range(1, MAP_W - 1) if self.free(x, y, player)]
        while len(candidates) > 0:
            x, y = candidates.pop(random.randrange(len(candidates)))
            if self.suits(x, y, player, avoid_start, min_distance):
                return x, y

        if avoid_start or min_distance:
            return self.scan_floor(player, False, 0)
        return player.x, player.y

    def blocks_sight(self, x, y):
        return not in_map(x, y) or self.tiles[y][x] in SIGHT_BLOCKERS

    def line_of_sight(self, x1, y1, x2, y2):
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
            if (x != x1 or y != y1) and self.blocks_sight(x, y):
                return False
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy

    def update_visibility(self, player):
        visible = self.visible
        explored = self.explored
        for row in visible:
            row[:] = HIDDEN_ROW

        for room in self.rooms:
            if point_in_room(player.x, player.y, room):
                break
        else:
            room = None

        if room is not None:
            rx, ry, rw, rh = room
            for y in range(ry, ry + rh):
                for x in range(rx, rx + rw):
                    visible[y][x] = True
                    explored[y][x] = True
                    if self.tiles[y][x] != ROOM_FLOOR or (rx < x < rx + rw - 1 and ry < y < ry + rh - 1):
                        continue
                    for dx, dy in STEPS:
                        nx = x + dx
                        ny = y + dy
                        if not in_map(nx, ny) or point_in_room(nx, ny, room):
                            continue
                        if self.passable(nx, ny) or self.enemy_at(nx, ny) is not None:
                            visible[ny][nx] = True
                            explored[ny][nx] = True
            return

        sight = player.sight
        for y in range(max(0, player.y - sight), min(MAP_H, player.y + sight + 1)):
            for x in range(max(0, player.x - sight), min(MAP_W, player.x + sight + 1)):
                if distance(player.x, player.y, x, y) <= sight and self.line_of_sight(player.x, player.y, x, y):
                    visible[y][x] = True
                    explored[y][x] = True
