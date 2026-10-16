import json
import os

from build import build_surface, build_underground
from game import Game, Log, Pack, Player
from monsters import Enemy
from world import MAP_W, Item

SAVE_PATH = "/state/rogue_save.json"
SAVE_TEMP = SAVE_PATH + ".tmp"
VERSION = 2

PLAYER_FIELDS = ("x", "y", "hp", "max_hp", "atk", "armor", "gold", "confuse", "sleep")
ENEMY_FIELDS = ("hp", "max_hp", "atk", "held", "scared", "confused", "skip", "loot", "awake")
GAME_FIELDS = ("kills", "turns", "items_found", "items_used", "gold_found", "seen_cells", "open_cells")


def pack_item(item):
    return [item.kind, item.x, item.y, item.effect, item.count, item.equipped, item.cursed]


def unpack_item(data):
    item = Item(data[0], data[1], data[2], data[3], data[4], data[6])
    item.equipped = data[5]
    return item


def encode_row(row):
    value = 0
    for x in range(MAP_W):
        if row[x]:
            value |= 1 << x
    return "%08x" % value


def decode_row(text):
    value = int(text, 16)
    return [(value >> x) & 1 == 1 for x in range(MAP_W)]


def pack_area(area):
    return {
        "layer": area.layer,
        "level": area.level,
        "seed": area.seed,
        "origin": area.origin,
        "explored": [encode_row(row) for row in area.explored],
        "items": [pack_item(item) for item in area.items],
        "enemies": [[enemy.char, enemy.x, enemy.y] + [getattr(enemy, name) for name in ENEMY_FIELDS] for enemy in area.enemies],
        "gate_unlocked": area.gate_unlocked,
    }


def unpack_area(data, parent):
    origin = data["origin"]
    if data["layer"] == 0:
        area = build_surface(data["seed"], data["level"], Player(), tuple(origin) if origin is not None else None)
    else:
        arrival = Player()
        arrival.x, arrival.y = origin
        area = build_underground(data["layer"], data["seed"], arrival, parent)
    area.explored = [decode_row(row) for row in data["explored"]]
    area.items = [unpack_item(item) for item in data["items"]]
    area.enemies = []
    for entry in data["enemies"]:
        enemy = Enemy(entry[0], entry[1], entry[2], area.level)
        for index, name in enumerate(ENEMY_FIELDS):
            setattr(enemy, name, entry[3 + index])
        area.enemies.append(enemy)
    area.gate_unlocked = data["gate_unlocked"]
    return area


def save_game(game):
    areas = list(game.layers.values())
    if game.area not in areas:
        areas.append(game.area)
    areas.sort(key=lambda area: area.layer)
    pack = game.player.pack
    data = {
        "version": VERSION,
        "seed": game.seed,
        "game": [getattr(game, name) for name in GAME_FIELDS],
        "log": game.log.lines,
        "player": [getattr(game.player, name) for name in PLAYER_FIELDS],
        "pack": {"items": [pack_item(item) for item in pack.items], "slots": pack.slots, "cursor": pack.cursor,
                 "identified": list(pack.identified)},
        "layer": game.area.layer,
        "areas": [pack_area(area) for area in areas],
    }
    try:
        with open(SAVE_TEMP, "w") as file:
            json.dump(data, file)
        os.rename(SAVE_TEMP, SAVE_PATH)
    except OSError:
        pass


def load_game():
    try:
        with open(SAVE_PATH) as file:
            data = json.load(file)
    except (OSError, ValueError):
        return None
    if data.get("version") != VERSION:
        return None

    try:
        areas = []
        for entry in data["areas"]:
            areas.append(unpack_area(entry, areas[-1] if areas else None))
        current = [area for area in areas if area.layer == data["layer"]][0]
        game = Game(data["seed"], current)
        for index, name in enumerate(GAME_FIELDS):
            setattr(game, name, data["game"][index])
        game.layers = {area.layer: area for area in areas if area is not current}

        game.log = Log()
        for line in data["log"]:
            game.log.say(line)

        game.player = Player()
        for index, name in enumerate(PLAYER_FIELDS):
            setattr(game.player, name, data["player"][index])
        pack = Pack()
        pack.items = [unpack_item(item) for item in data["pack"]["items"]]
        pack.slots = data["pack"]["slots"]
        pack.cursor = data["pack"]["cursor"]
        pack.identified = dict.fromkeys(data["pack"]["identified"], True)
        game.player.pack = pack
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        return None
    current.update_visibility(game.player)
    return game


def has_save():
    try:
        os.stat(SAVE_PATH)
        return True
    except OSError:
        return False


def delete_save():
    try:
        os.remove(SAVE_PATH)
    except OSError:
        pass
