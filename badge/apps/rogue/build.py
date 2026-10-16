import random

from items import random_item
from monsters import spawn_enemy
from world import (
    CAVE_TILES, CELL_COUNT, DIRT, H_WALL, HOLE, LADDER_UP, MAP_H, MAP_W, MAX_LAYER, OPEN_GROUND,
    PATH, ROCK, ROOM_FLOOR, ROOM_TILES, SEALED_GATE, STAIRS_DOWN, STAIRS_UP, STEPS, V_WALL,
    Area, Item, cell_index, distance, in_map, room_center,
)

SURFACE_HOLES = 4
SURFACE_HOLE_GAP = 7
CAVE_STEPS = 90
CAVE_REACH = 7
CAVE_FILL = 54
PASSAGE_CHANCE = 14
PASSAGE_REACH = 5
LINK_GAP = 5
LINK_GAP_FLOOR = 3
ANCHOR_REACH = 9
HOLE_TO_DUNGEON = 40
ROOM_REGION_W = 16
ROOM_REGION_H = 14

INWARD = {"left": (1, 0), "right": (-1, 0), "top": (0, 1), "bottom": (0, -1)}
OPPOSITE = {"left": "right", "right": "left", "top": "bottom", "bottom": "top"}


def shuffled(cells):
    pool = cells[:]
    order = []
    while pool:
        order.append(pool.pop(random.randrange(len(pool))))
    return order


def group_gap(origins, cell):
    nearest = 999
    for ox, oy in origins:
        gap = distance(cell[0], cell[1], ox, oy)
        if gap < nearest:
            nearest = gap
    return nearest


def doorway(room, target):
    x, y, w, h = room
    cx, cy = room_center(room)
    tx, ty = target
    if abs(tx - cx) > abs(ty - cy):
        step = 1 if tx > cx else -1
        door = (x + w - 1 if step > 0 else x, clamp(ty, y + 1, y + h - 2))
        return door, (door[0] + step, door[1])
    step = 1 if ty > cy else -1
    door = (clamp(tx, x + 1, x + w - 2), y + h - 1 if step > 0 else y)
    return door, (door[0], door[1] + step)


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


def offsets_near(target, low, high):
    ordered = []
    for gap in range(high - low + 1):
        for candidate in (target - gap, target + gap):
            if low <= candidate <= high and candidate not in ordered:
                ordered.append(candidate)
    return ordered


class Builder:
    def __init__(self, area, player):
        self.area = area
        self.tiles = area.tiles
        self.player = player

    def carve_room(self, room):
        x, y, w, h = room
        tiles = self.tiles
        for row in range(y, y + h):
            for col in range(x, x + w):
                if row == y or row == y + h - 1:
                    tiles[row][col] = H_WALL
                elif col == x or col == x + w - 1:
                    tiles[row][col] = V_WALL
                else:
                    tiles[row][col] = ROOM_FLOOR
        self.area.rooms.append(room)

    def intersects(self, room):
        x, y, w, h = room
        for ox, oy, ow, oh in self.area.rooms:
            if x - 1 < ox + ow and x + w + 1 > ox and y - 1 < oy + oh and y + h + 1 > oy:
                return True
        return False

    def carve_line(self, start, end):
        tiles = self.tiles
        fill = self.area.fill
        for y in range(min(start[1], end[1]), max(start[1], end[1]) + 1):
            for x in range(min(start[0], end[0]), max(start[0], end[0]) + 1):
                if tiles[y][x] == fill:
                    tiles[y][x] = PATH

    def connect_rooms(self, room_a, room_b):
        door_a, outside_a = doorway(room_a, room_center(room_b))
        door_b, outside_b = doorway(room_b, room_center(room_a))
        self.tiles[door_a[1]][door_a[0]] = ROOM_FLOOR
        self.tiles[door_b[1]][door_b[0]] = ROOM_FLOOR

        if random.randrange(2):
            corner = (outside_b[0], outside_a[1])
        else:
            corner = (outside_a[0], outside_b[1])
        self.carve_line(outside_a, corner)
        self.carve_line(corner, outside_b)

    def change_unless_blocking(self, changes, approach, before):
        tiles = self.tiles
        player = self.player
        replaced = [(x, y, tiles[y][x]) for (x, y), _tile in changes]
        for (x, y), tile in changes:
            tiles[y][x] = tile

        after = self.area.reachable(player.x, player.y)
        if after[cell_index(approach)]:
            spared = [cell_index(cell) for cell, _tile in changes]
            for index in range(CELL_COUNT):
                if before[index] and not after[index] and index not in spared:
                    break
            else:
                return

        for x, y, tile in replaced:
            tiles[y][x] = tile


class Surface(Builder):
    def build(self, attempt, entry):
        area = self.area
        tiles = self.tiles
        player = self.player
        rooms = area.rooms

        room_goal = 8 + min(6, area.level)
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
            if not self.intersects(room):
                self.carve_room(room)

        if len(rooms) < 2:
            return False

        player.x, player.y = room_center(rooms[0])
        for index in range(1, len(rooms)):
            self.connect_rooms(rooms[index - 1], rooms[index])

        self.scatter_outdoors()
        reachable = area.reachable(player.x, player.y)
        for room in rooms:
            if not reachable[cell_index(room_center(room))]:
                return False

        stairs_x, stairs_y = room_center(rooms[-1])
        tiles[stairs_y][stairs_x] = STAIRS_DOWN
        area.rebuild_floor()

        for _ in range(12 + area.level * 2):
            area.items.append(random_item(*area.random_floor(player)))

        if entry is not None:
            self.place_entry(*entry)
        if not self.place_gate():
            return False

        area.rebuild_floor()
        for _ in range(8 + area.level * 3):
            spawn_enemy(area, player, True, 7)

        area.update_visibility(player)
        return True

    def scatter_outdoors(self):
        tiles = self.tiles
        outdoor = []
        for y in range(1, MAP_H - 1):
            for x in range(1, MAP_W - 1):
                if tiles[y][x] != OPEN_GROUND:
                    continue
                outdoor.append((x, y))
                roll = random.randrange(100)
                if roll < 26:
                    tiles[y][x] = DIRT
                elif roll < 33:
                    tiles[y][x] = ROCK

        if len(outdoor) < 80:
            return

        placed = []
        for gap in range(SURFACE_HOLE_GAP, 0, -2):
            for _ in range(60):
                if len(placed) >= SURFACE_HOLES:
                    return
                x, y = random.choice(outdoor)
                if tiles[y][x] != OPEN_GROUND or group_gap(placed, (x, y)) < gap:
                    continue
                tiles[y][x] = HOLE
                placed.append((x, y))

    def place_entry(self, side, offset):
        area = self.area
        player = self.player
        reachable = area.reachable(player.x, player.y)
        dx, dy = INWARD[side]

        if side in ("left", "right"):
            x = 1 if side == "left" else MAP_W - 2
            candidates = [(x, y) for y in offsets_near(clamp(offset, 1, MAP_H - 2), 1, MAP_H - 2)]
            wall = V_WALL
        else:
            y = 1 if side == "top" else MAP_H - 2
            candidates = [(x, y) for x in offsets_near(clamp(offset, 1, MAP_W - 2), 1, MAP_W - 2)]
            wall = H_WALL

        for x, y in candidates:
            if not reachable[y * MAP_W + x] or not area.passable(x + dx, y + dy):
                continue
            player.x = x
            player.y = y
            onward = (x + dx, y + dy)
            gate = (x - dx, y - dy)
            changes = [(gate, SEALED_GATE)]
            for flank in gate_flanks(side, gate):
                if flank != (x, y) and flank != onward:
                    changes.append((flank, wall))
            self.change_unless_blocking(changes, onward, area.reachable(x, y))
            return

        for x, y in candidates:
            if reachable[y * MAP_W + x]:
                player.x = x
                player.y = y
                return

    def place_gate(self):
        area = self.area
        tiles = self.tiles
        player = self.player
        reachable = area.reachable(player.x, player.y)
        sides = ["left", "right", "top", "bottom"]

        while sides:
            side = sides.pop(random.randrange(len(sides)))
            candidates = [pair for pair in gate_positions(side)
                          if reachable[cell_index(pair[1])] and tiles[pair[0][1]][pair[0][0]] != SEALED_GATE]
            if not candidates:
                continue

            area.gate_side = side
            area.gate, approach = candidates[random.randrange(len(candidates))]
            wall = V_WALL if side in ("left", "right") else H_WALL
            flanks = [(cell, wall) for cell in gate_flanks(side, area.gate) if cell != (player.x, player.y)]
            self.change_unless_blocking(flanks, approach, reachable)

            for attempt in range(121):
                key_x, key_y = area.random_floor(player, True, 6)
                if attempt == 120 or distance(key_x, key_y, area.gate[0], area.gate[1]) > 10:
                    area.items.append(Item("key", key_x, key_y))
                    break
            return True

        return False


class Underground(Builder):
    def __init__(self, area, player, parent):
        super().__init__(area, player)
        self.parent = parent
        self.landings = []

    def build(self):
        area = self.area
        tiles = self.tiles
        player = self.player
        groups = self.anchor_groups()

        caves = []
        complexes = []
        for kind, cells in groups:
            if kind == "cave":
                for x, y in cells:
                    self.open_anchor(x, y, DIRT)
                caves.append(cells)
        for kind, cells in groups:
            if kind == "dungeon":
                self.carve_room_region(cells)
                for x, y in cells:
                    self.open_anchor(x, y, ROOM_FLOOR)
                    tiles[y][x] = STAIRS_UP
                complexes.append(cells)
        for cells in caves:
            for x, y in cells:
                self.carve_cave(x, y)

        taken = []
        for cells in caves + complexes:
            taken.extend(cells)
        for cells in caves:
            self.place_cave_links(cells, taken)
        if area.layer < MAX_LAYER:
            for cells in complexes:
                self.place_link(area.region(cells[0]), cells, taken, ROOM_FLOOR, STAIRS_DOWN, 5)
        for cells in caves:
            self.tunnel_to_rooms(cells[0])

        area.rebuild_floor()
        for _ in range(6 + area.level + area.layer * 2):
            x, y = area.random_floor(player)
            area.items.append(random_item(x, y, area.layer == MAX_LAYER))
        for _ in range(6 + area.level * 2 + area.layer * 2):
            spawn_enemy(area, player, False, 7)
        area.update_visibility(player)

    def anchor_groups(self):
        deep = self.area.layer > 1
        groups = []
        for y in range(MAP_H):
            row = self.parent.tiles[y]
            for x in range(MAP_W):
                if row[x] == HOLE:
                    kind = "dungeon" if deep and random.randrange(100) < HOLE_TO_DUNGEON else "cave"
                elif row[x] == STAIRS_DOWN:
                    kind = "dungeon"
                else:
                    continue
                for group in groups:
                    if group[0] == kind and any(distance(x, y, ax, ay) <= ANCHOR_REACH for ax, ay in group[1]):
                        group[1].append((x, y))
                        break
                else:
                    groups.append((kind, [(x, y)]))
        return groups

    def touches_rooms(self, x, y):
        tiles = self.tiles
        for dx, dy in STEPS:
            if tiles[y + dy][x + dx] in ROOM_TILES:
                return True
        return False

    def open_anchor(self, x, y, floor):
        tiles = self.tiles
        if tiles[y][x] != ROCK:
            return
        tiles[y][x] = floor
        for dx, dy in STEPS:
            nx = x + dx
            ny = y + dy
            if nx < 1 or ny < 1 or nx >= MAP_W - 1 or ny >= MAP_H - 1 or tiles[ny][nx] != ROCK:
                continue
            if floor == DIRT and self.touches_rooms(nx, ny):
                continue
            tiles[ny][nx] = floor

    def hollow(self, x, y):
        if x < 1 or y < 1 or x >= MAP_W - 1 or y >= MAP_H - 1:
            return
        if self.tiles[y][x] == ROCK and not self.touches_rooms(x, y):
            self.tiles[y][x] = DIRT

    def carve_cave(self, cx, cy):
        low_x = max(1, cx - CAVE_REACH)
        high_x = min(MAP_W - 2, cx + CAVE_REACH)
        low_y = max(1, cy - CAVE_REACH)
        high_y = min(MAP_H - 2, cy + CAVE_REACH)

        x = cx
        y = cy
        for _ in range(CAVE_STEPS):
            self.hollow(x, y)
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    if random.randrange(100) < CAVE_FILL:
                        self.hollow(x + dx, y + dy)
            dx, dy = random.choice(STEPS)
            x = clamp(x + dx, low_x, high_x)
            y = clamp(y + dy, low_y, high_y)

    def room_fits(self, room):
        if self.intersects(room):
            return False
        tiles = self.tiles
        x, y, w, h = room
        for row in range(y, y + h):
            for col in range(x, x + w):
                if tiles[row][col] != ROCK:
                    return False
        for row in range(max(1, y - 1), min(MAP_H - 1, y + h + 1)):
            for col in range(max(1, x - 1), min(MAP_W - 1, x + w + 1)):
                if tiles[row][col] in CAVE_TILES:
                    return False
        return True

    def home_room(self, x, y, low_x, low_y):
        for width, height in ((5, 4), (4, 3), (3, 3)):
            rx = clamp(x - width // 2, low_x, low_x + ROOM_REGION_W - width)
            ry = clamp(y - height // 2, low_y, low_y + ROOM_REGION_H - height)
            room = (rx, ry, width, height)
            if rx < x < rx + width - 1 and ry < y < ry + height - 1 and self.room_fits(room):
                return room
        return None

    def carve_room_region(self, cells):
        cx, cy = cells[0]
        low_x = clamp(cx - ROOM_REGION_W // 2, 1, MAP_W - ROOM_REGION_W - 1)
        low_y = clamp(cy - ROOM_REGION_H // 2, 1, MAP_H - ROOM_REGION_H - 1)
        placed = []

        for x, y in cells:
            room = self.home_room(x, y, low_x, low_y)
            if room is not None:
                self.carve_room(room)
                placed.append(room)

        for _ in range(40):
            if len(placed) >= 5:
                break
            w = random.randrange(4, 8)
            h = random.randrange(3, 6)
            x = random.randrange(low_x, low_x + ROOM_REGION_W - w)
            y = random.randrange(low_y, low_y + ROOM_REGION_H - h)
            room = (x, y, w, h)
            if self.room_fits(room):
                self.carve_room(room)
                placed.append(room)

        for index in range(1, len(placed)):
            self.connect_rooms(placed[index - 1], placed[index])

    def place_link(self, cells, origins, taken, wanted, tile, reach, floor=LINK_GAP_FLOOR):
        tiles = self.tiles
        for gap in range(LINK_GAP, floor - 1, -1):
            for cell in shuffled(cells):
                if tiles[cell[1]][cell[0]] != wanted:
                    continue
                if group_gap(taken, cell) < gap or group_gap(origins, cell) < reach:
                    continue
                tiles[cell[1]][cell[0]] = tile
                taken.append(cell)
                return cell
            reach = max(0, reach - 2)
        return None

    def place_cave_links(self, anchors, taken):
        tiles = self.tiles

        for anchor in anchors:
            region = self.area.region(anchor)
            if any(tiles[y][x] == LADDER_UP or tiles[y][x] == STAIRS_UP for x, y in region):
                continue

            index = anchor[1] * MAP_W + anchor[0]
            for landing in self.landings:
                if landing[index]:
                    break
            else:
                landing = self.parent.reachable(anchor[0], anchor[1])
                self.landings.append(landing)
            above = []
            beside = []
            for x, y in region:
                if (x, y) in taken or tiles[y][x] != DIRT:
                    continue
                if landing[y * MAP_W + x]:
                    above.append((x, y))
                elif any(in_map(x + dx, y + dy) and landing[(y + dy) * MAP_W + x + dx] for dx, dy in STEPS):
                    beside.append((x, y))

            if self.place_link(above, anchors, taken, DIRT, LADDER_UP, 6, 1) is None:
                self.place_link(beside, anchors, taken, DIRT, LADDER_UP, 0, 1)

        if self.area.layer < MAX_LAYER:
            self.place_link(self.area.region(anchors[0]), anchors, taken, DIRT, HOLE, 4)

    def passage_from(self, cell, dx, dy):
        tiles = self.tiles
        x, y = cell
        dug = []
        for _ in range(PASSAGE_REACH):
            x += dx
            y += dy
            if x < 1 or y < 1 or x >= MAP_W - 1 or y >= MAP_H - 1:
                return None
            tile = tiles[y][x]
            if tile == ROCK:
                dug.append((x, y))
                continue
            if tile in (H_WALL, V_WALL) and tiles[y + dy][x + dx] == ROOM_FLOOR and dug:
                return dug + [(x, y)]
            return None
        return None

    def tunnel_to_rooms(self, anchor):
        if random.randrange(100) >= PASSAGE_CHANCE:
            return

        tiles = self.tiles
        routes = []
        for cell in self.area.region(anchor):
            if tiles[cell[1]][cell[0]] != DIRT:
                continue
            for dx, dy in STEPS:
                route = self.passage_from(cell, dx, dy)
                if route is not None:
                    routes.append(route)

        if not routes:
            return

        route = routes[random.randrange(len(routes))]
        for x, y in route[:-1]:
            tiles[y][x] = PATH
        door_x, door_y = route[-1]
        tiles[door_y][door_x] = ROOM_FLOOR


def build_surface(seed, level, player, entry=None):
    random.seed(seed)
    attempt = 0
    while True:
        area = Area(0, level, seed)
        if Surface(area, player).build(attempt, entry):
            area.origin = entry
            return area
        attempt += 1


def build_underground(layer, seed, player, parent):
    random.seed(seed)
    area = Area(layer, parent.level, seed)
    area.origin = (player.x, player.y)
    Underground(area, player, parent).build()
    return area
