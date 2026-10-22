import random

from build import OPPOSITE, build_surface, build_underground
from content import (
    BOW_ACCURACY_BONUS, LOW_HP, MERCY_RATION_CHANCE, REST_EVERY, WANDER_CHANCE, PACK_BLOCK, PLAYER_ACCURACY, PLAYER_ATK, PLAYER_HP,
    PLAYER_SIGHT, RESPAWN_LIMIT,
)
from items import ITEMS
from rings import RINGS
from monsters import spawn_enemy
from scrolls import SCROLLS
from world import (
    HOLE, LADDER_UP, MAP_H, MAP_W, MAX_LAYER, ROCK, SEALED_GATE, STAIRS_DOWN, STAIRS_UP, Item, distance, hit_roll,
)

SEED_MASK = 0x3FFFFFFF
ESCAPE_RUIN = 9
BARRED_MESSAGES = ("The gate behind you is barred.", "Find another gate.", "A magical force blocks you.")
LOCKED_MESSAGES = ("The gate is locked.", "Maybe there's a key.")


def derive_seed(parent, index):
    value = (parent + index * 83492791) & SEED_MASK
    value = ((value ^ (value >> 15)) * 2246822519) & SEED_MASK
    value = ((value ^ (value >> 13)) * 3266489917) & SEED_MASK
    return (value ^ (value >> 16)) & SEED_MASK


class Log:
    def __init__(self):
        self.lines = []
        self.count = 0

    def say(self, message):
        self.count += 1
        self.lines.append(message)
        if len(self.lines) > 3:
            self.lines.pop(0)


class Pack:
    def __init__(self):
        self.items = []
        self.slots = PACK_BLOCK
        self.cursor = 0
        self.identified = {"identify": True}

    def find(self, kind):
        for item in self.items:
            if item.kind == kind:
                return item
        return None

    def count(self, kind):
        return sum(1 for item in self.items if item.kind == kind)

    def arrows(self):
        return sum(item.count for item in self.items if item.kind == "arrows")

    def take_arrow(self):
        item = self.find("arrows")
        item.count -= 1
        if item.count <= 0:
            self.remove(item)

    def bow(self):
        for item in self.items:
            if item.kind == "bow" and item.equipped:
                return item
        return None

    def selected(self):
        return self.items[self.cursor] if self.cursor < len(self.items) else None

    def remove(self, item):
        self.items.remove(item)
        self.cursor = min(self.cursor, max(0, len(self.items) - 1))

    def unidentified(self):
        for item in self.items:
            if item.kind in ("scroll", "ring") and item.effect not in self.identified:
                return item
        return None

    def name(self, item):
        if item.kind == "bow" and item.equipped:
            return "short bow, equipped"
        if item.kind == "scroll":
            return SCROLLS[item.effect]["name"] if item.effect in self.identified else "unidentified scroll"
        if item.kind == "arrows":
            return "arrows x" + str(item.count)
        if item.kind == "ring":
            name = RINGS[item.effect]["name"] if item.effect in self.identified else "unidentified ring"
            return name + ", worn" if item.equipped else name
        return ITEMS[item.kind]["name"]


class Player:
    def __init__(self):
        self.x = 1
        self.y = 1
        self.hp = PLAYER_HP
        self.max_hp = PLAYER_HP
        self.atk = PLAYER_ATK
        self.armor = 0
        self.gold = 0
        self.confuse = 0
        self.sleep = 0
        self.pack = Pack()

    def heal(self, amount):
        self.hp = min(self.max_hp, self.hp + amount)

    def wearing(self, effect):
        return sum(1 for item in self.pack.items if item.kind == "ring" and item.equipped and item.effect == effect)

    @property
    def attack(self):
        return max(1, self.atk + 2 * (self.wearing("strength") - self.wearing("weakness")))

    @property
    def defence(self):
        return self.armor + 2 * self.wearing("protection")

    @property
    def sight(self):
        return PLAYER_SIGHT + 3 * self.wearing("sight")

    @property
    def notice(self):
        return 2 if self.wearing("stealth") else self.sight


class Game:
    def __init__(self, seed, area=None):
        self.seed = seed & SEED_MASK
        self.player = Player()
        self.log = Log()
        self.kills = 0
        self.turns = 0
        self.items_found = 0
        self.items_used = 0
        self.gold_found = 0
        self.escaped = False
        self.seen_cells = 0
        self.open_cells = 0
        self.layers = {}
        self.area = area
        if area is None:
            self.area = build_surface(derive_seed(self.seed, 1), 1, self.player)
            self.log.say("You wake in a dark ruin.")

    @property
    def level(self):
        return self.area.level

    @property
    def layer(self):
        return self.area.layer

    @property
    def dead(self):
        return self.player.hp <= 0

    def ruin_exploration(self):
        areas = list(self.layers.values())
        if self.area not in areas:
            areas.append(self.area)
        seen = 0
        total = 0
        for area in areas:
            area_seen, area_total = area.exploration()
            seen += area_seen
            total += area_total
        return seen, total

    def explored_percent(self):
        seen, total = self.ruin_exploration()
        seen += self.seen_cells
        total += self.open_cells
        return seen * 100 // total if total else 0

    def score(self):
        return self.gold_found + self.kills * 10 + (self.items_found + self.items_used) * 5 + self.explored_percent() * 5

    def next_ruin(self):
        area = self.area
        side = area.gate_side
        offset = area.gate[1] if side in ("left", "right") else area.gate[0]
        level = area.level + 1
        seen, total = self.ruin_exploration()
        self.seen_cells += seen
        self.open_cells += total
        self.layers = {}
        self.area = build_surface(derive_seed(self.seed, level), level, self.player, (OPPOSITE[side], offset))
        if level == ESCAPE_RUIN:
            self.log.say("You enter the last ruin. Its gate leads out.")
        else:
            self.log.say("You enter ruin " + str(level) + " of " + str(ESCAPE_RUIN) + ".")
        self.player.heal(4)

    def enter_layer(self, layer):
        here = self.area
        self.layers[here.layer] = here

        area = self.layers.get(layer)
        if area is None:
            seed = derive_seed(derive_seed(self.seed, here.level), layer)
            self.area = build_underground(layer, seed, self.player, here)
            return

        self.area = area
        budget = self.population(area) - len(area.enemies)
        for _ in range(min(RESPAWN_LIMIT, budget)):
            spawn_enemy(area, self.player, False, 7)
        area.update_visibility(self.player)

    def take_turn(self, dx, dy):
        acted = self.step(dx, dy) if dx != 0 or dy != 0 else self.act()
        if acted:
            self.end_turn()
        else:
            self.area.update_visibility(self.player)

    def population(self, area):
        return 8 + area.level * 3 if area.outdoors else 6 + area.level * 2

    def end_turn(self):
        self.turns += 1
        player = self.player
        area = self.area
        if random.randrange(WANDER_CHANCE) == 0 and len(area.enemies) < self.population(area):
            spawn_enemy(area, player, False, 10)
        for item in player.pack.items:
            if item.kind == "ring" and item.equipped and "turn" in RINGS[item.effect]:
                RINGS[item.effect]["turn"](player, area, self.log, self.turns)
        if player.hp > 0:
            for enemy in area.enemies:
                enemy.act(player, area, self.log)
                if player.hp <= 0:
                    self.log.say("You die on level " + str(area.level) + ".")
                    break
        area.update_visibility(player)

    def sleep_turn(self):
        self.player.sleep -= 1
        self.log.say("You sleep.")
        self.end_turn()

    def step(self, dx, dy):
        player = self.player
        area = self.area
        log = self.log
        x = player.x + dx
        y = player.y + dy

        enemy = area.enemy_at(x, y)
        if enemy is not None:
            self.attack(enemy)
            return True
        if area.gate is not None and (x, y) == area.gate:
            return self.unlock_gate()
        if not area.passable(x, y):
            if x < 0 or y < 0 or x >= MAP_W or y >= MAP_H:
                log.say("The world ends here.")
            elif area.tiles[y][x] == SEALED_GATE:
                log.say(random.choice(BARRED_MESSAGES))
            elif area.tiles[y][x] == ROCK:
                log.say("Shrubs block the way." if area.outdoors else "Solid rock blocks the way.")
            else:
                log.say("Stone blocks the way.")
            return False

        player.x = x
        player.y = y
        if area.tiles[y][x] == HOLE:
            player.hp -= 2
            if player.hp <= 0:
                log.say("You fall into the dark.")
            elif area.layer >= MAX_LAYER:
                log.say("The hole is choked with rubble.")
            else:
                self.enter_layer(area.layer + 1)
                log.say("You fall through into the dark.")
            return True

        item = area.item_at(x, y)
        gold = player.gold
        if item is not None and ITEMS[item.kind]["pick_up"](item, player, area, log):
            self.gold_found += player.gold - gold
            if item.kind != "gold":
                self.items_found += 1
            area.items.remove(item)
        return True

    def act(self):
        player = self.player
        area = self.area
        log = self.log
        here = area.tiles[player.y][player.x]

        if here == STAIRS_UP or here == LADDER_UP:
            self.enter_layer(area.layer - 1)
            log.say("You climb up into daylight." if self.layer == 0 else "You climb up a level.")
            return False
        if here == STAIRS_DOWN:
            self.enter_layer(area.layer + 1)
            log.say("You reach the deepest ruins." if self.layer >= MAX_LAYER else "You take the stairs down.")
            return False
        if area.gate is not None and distance(player.x, player.y, area.gate[0], area.gate[1]) == 1:
            return self.unlock_gate()
        if self.shoot():
            return True

        if self.turns % REST_EVERY == 0:
            player.heal(1)
        log.say("You wait and listen.")
        return True

    def unlock_gate(self):
        area = self.area
        pack = self.player.pack
        if not area.gate_unlocked:
            key = pack.find("key")
            if key is None:
                self.log.say(random.choice(LOCKED_MESSAGES))
                return False
            pack.remove(key)
            area.gate_unlocked = True
            self.log.say("You unlock the gate.")
            return True

        if area.level >= ESCAPE_RUIN:
            self.escaped = True
            self.log.say("You escape the ruins.")
            return False
        self.log.say("The gate opens.")
        self.next_ruin()
        return False

    def attack(self, enemy):
        player = self.player
        log = self.log
        if player.confuse > 0:
            player.confuse = 0
            enemy.confused = 6
            log.say(enemy.name + " stares wildly.")
            return

        if not hit_roll(PLAYER_ACCURACY + self.level - enemy.kind["dodge"]):
            log.say("You miss " + enemy.name + ".")
            return

        damage = random.randrange(1, player.attack + 1)
        enemy.hp -= damage
        log.say("You hit " + enemy.name + " for " + str(damage) + ".")
        if enemy.hp <= 0:
            self.kill(enemy)
            return

        paralyse = enemy.kind.get("paralyse", 0)
        if paralyse > 0:
            player.sleep = max(player.sleep, paralyse)
            log.say(enemy.name + " holds you rigid.")

    def shoot(self):
        player = self.player
        pack = player.pack
        area = self.area
        if pack.bow() is None or pack.arrows() <= 0:
            return False

        target = None
        nearest = 999
        for enemy in area.enemies:
            if area.visible[enemy.y][enemy.x]:
                gap = distance(enemy.x, enemy.y, player.x, player.y)
                if gap < nearest:
                    target = enemy
                    nearest = gap
        if target is None:
            return False

        pack.take_arrow()
        target.skip += 1
        if not hit_roll(PLAYER_ACCURACY + self.level - target.kind["dodge"] + BOW_ACCURACY_BONUS):
            self.log.say("Your arrow misses " + target.name + ".")
            return True

        damage = random.randrange(2, player.attack + 2)
        target.hp -= damage
        self.log.say("Arrow hits " + target.name + " for " + str(damage) + ".")
        if target.hp <= 0:
            self.kill(target)
        return True

    def kill(self, enemy):
        player = self.player
        area = self.area
        log = self.log
        self.kills += 1
        area.enemies.remove(enemy)
        reward = random.randrange(1, 5 + area.level)
        player.gold += reward
        self.gold_found += reward
        log.say(enemy.name + " falls.")

        if (player.hp <= LOW_HP and player.pack.find("food") is None
                and random.randrange(100) < MERCY_RATION_CHANCE and area.item_at(enemy.x, enemy.y) is None):
            area.items.append(Item("food", enemy.x, enemy.y))
            log.say("It was carrying a ration.")

        if enemy.loot > 0:
            player.gold += enemy.loot
            log.say("You recover " + str(enemy.loot) + " gold.")

    def use_selected(self):
        item = self.player.pack.selected()
        if item is None or not ITEMS[item.kind]["use"](item, self.player, self.area, self.log):
            return False
        self.items_used += 1
        return True

    def drop_selected(self):
        player = self.player
        pack = player.pack
        item = pack.selected()
        if item is None:
            return False
        if item.equipped and item.cursed:
            self.log.say("The ring won't come off.")
            return False
        if self.area.item_at(player.x, player.y) is not None:
            self.log.say("No room to drop it.")
            return False

        self.log.say("Dropped " + pack.name(item) + ".")
        pack.remove(item)
        item.x = player.x
        item.y = player.y
        item.equipped = False
        self.area.items.append(item)
        return True
