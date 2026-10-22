import random

from content import ARMOR_BLOCK, ARMOR_DODGE, ENEMY_ACCURACY_GROWTH, ENEMY_ATK_GROWTH, ENEMY_HP_GROWTH, GOLD, GRAY_2, GREEN_3, HURT, PURPLE
from world import STEPS, distance, hit_roll, pick_weighted


def steal_gold(enemy, player, area, log):
    stolen = min(player.gold, player.gold // 3 + random.randrange(10, 30 + area.level * 3))
    player.gold -= stolen
    enemy.loot += stolen
    if stolen > 0:
        log.say(enemy.name + " steals " + str(stolen) + " gold.")
    else:
        log.say(enemy.name + " finds no gold.")
    enemy.flee(player, area)


def steal_item(enemy, player, area, log):
    pack = player.pack
    if len(pack.items) == 0:
        log.say(enemy.name + " finds nothing to take.")
        return
    item = pack.items[random.randrange(len(pack.items))]
    pack.remove(item)
    log.say(enemy.name + " steals your " + pack.name(item) + ".")
    enemy.flee(player, area)


def rust(enemy, player, _area, log):
    if player.armor <= 0:
        log.say(enemy.name + " splashes you.")
        return
    player.armor -= 1
    log.say("Your armor corrodes.")


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
          "move": "chase", "min_level": 1, "ramp": 5, "habitat": {"cave": 40, "surface": 8}},
    "g": {"name": "guard", "hp": 8, "atk": 3, "accuracy": 70, "dodge": 5, "pen": HURT,
          "move": "chase", "min_level": 2, "habitat": {"surface": 8, "pocket": 18}},
    "H": {"name": "hobgoblin", "hp": 10, "atk": 4, "accuracy": 65, "dodge": 12, "pen": HURT,
          "move": "chase", "min_level": 2, "habitat": {"pocket": 25, "cave": 10}},
    "F": {"name": "floating eye", "hp": 6, "atk": 0, "accuracy": 0, "dodge": 0, "pen": GREEN_3,
          "move": "still", "paralyse": 3, "min_level": 3, "habitat": {"cave": 14, "pocket": 8}},
    "L": {"name": "leprechaun", "hp": 6, "atk": 0, "accuracy": 50, "dodge": 3, "pen": GOLD,
          "move": "chase", "on_hit": steal_gold, "min_level": 3, "habitat": {"cave": 12, "pocket": 8}},
    "Z": {"name": "zombie", "hp": 14, "atk": 5, "accuracy": 60, "dodge": 3, "pen": HURT,
          "move": "slow", "min_level": 4, "habitat": {"pocket": 18, "cave": 18}},
    "A": {"name": "aquator", "hp": 10, "atk": 0, "accuracy": 60, "dodge": 21, "pen": PURPLE,
          "move": "chase", "on_hit": rust, "min_level": 5, "habitat": {"pocket": 10, "cave": 8}},
    "N": {"name": "nymph", "hp": 6, "atk": 0, "accuracy": 50, "dodge": 0, "pen": PURPLE,
          "move": "chase", "on_hit": steal_item, "min_level": 6, "habitat": {"pocket": 10, "cave": 6}},
    "T": {"name": "troll", "hp": 24, "atk": 7, "accuracy": 70, "dodge": 15, "pen": HURT,
          "move": "chase", "regen": 1, "min_level": 8, "habitat": {"pocket": 10, "cave": 8}},
}


class Enemy:
    def __init__(self, char, x, y, level):
        kind = ENEMY_KINDS[char]
        self.char = char
        self.kind = kind
        self.name = kind["name"]
        self.x = x
        self.y = y
        growth = level - 1
        self.hp = kind["hp"] + growth * ENEMY_HP_GROWTH // 2
        self.max_hp = self.hp
        self.atk = kind["atk"] + growth * ENEMY_ATK_GROWTH // 3 if kind["atk"] > 0 else 0
        self.accuracy = kind["accuracy"] + growth * ENEMY_ACCURACY_GROWTH
        self.held = 0
        self.scared = 0
        self.confused = 0
        self.skip = 0
        self.loot = 0
        self.awake = False

    def flee(self, player, area):
        self.x, self.y = area.random_floor(player, False, 8)
        self.awake = False

    def toward(self, player):
        if abs(player.x - self.x) > abs(player.y - self.y):
            return (1 if player.x > self.x else -1), 0
        return 0, (1 if player.y > self.y else -1)

    def act(self, player, area, log):
        kind = self.kind
        move = kind["move"]

        regen = kind.get("regen", 0)
        if regen > 0 and self.hp < self.max_hp:
            self.hp = min(self.max_hp, self.hp + regen)

        if self.held > 0:
            self.held -= 1
            return
        if self.skip > 0:
            self.skip -= 1
            return
        if move == "still":
            return

        if self.confused > 0:
            self.confused -= 1
        elif self.scared > 0:
            self.scared -= 1

        if move == "slow":
            self.skip = 1

        for _ in range(2 if move == "fast" else 1):
            if not self.move(player, area, log):
                return

    def move(self, player, area, log):
        dx = 0
        dy = 0
        if self.confused > 0 or self.kind["move"] == "erratic":
            dx, dy = random.choice(STEPS)
        elif self.scared > 0:
            dx, dy = self.toward(player)
            dx, dy = -dx, -dy
        elif self.awake or distance(self.x, self.y, player.x, player.y) <= player.notice:
            self.awake = True
            dx, dy = self.toward(player)
        elif random.randrange(3) == 0:
            dx, dy = random.choice(STEPS)

        if dx == 0 and dy == 0:
            return True

        x = self.x + dx
        y = self.y + dy
        if x == player.x and y == player.y:
            self.strike(player, area, log)
            return False
        if area.passable(x, y) and area.enemy_at(x, y) is None:
            self.x = x
            self.y = y
        return True

    def strike(self, player, area, log):
        if not hit_roll(self.accuracy - player.defence * ARMOR_DODGE):
            log.say(self.name + " misses.")
            return

        on_hit = self.kind.get("on_hit")
        if on_hit is not None:
            on_hit(self, player, area, log)
            return

        if self.atk <= 0:
            log.say(self.name + " lunges at you.")
            return

        damage = max(1, random.randrange(1, self.atk + 1) - player.defence // ARMOR_BLOCK)
        player.hp -= damage
        log.say(self.name + " hits for " + str(damage) + ".")


def spawn_enemy(area, player, avoid_start, min_distance):
    x, y = area.random_floor(player, avoid_start, min_distance)
    habitat = area.habitat(x, y)
    table = []
    for char in ENEMY_KINDS:
        kind = ENEMY_KINDS[char]
        ramp = kind.get("ramp", 1)
        weight = kind["habitat"].get(habitat, 0) * min(area.level, ramp) // ramp
        if weight > 0 and area.level >= kind["min_level"]:
            table.append((char, weight))
    char = pick_weighted(table)
    if char is not None:
        area.enemies.append(Enemy(char, x, y, area.level))
