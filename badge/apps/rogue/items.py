import random

from content import ARMOR_CAP, BLADE_CAP, FOOD_HEAL, RING_WEIGHT, GOLD, GRAY_1, GREEN_2, GREEN_4, POTION_HEAL_MIN, PURPLE
from rings import MAX_WORN, RING_EFFECTS, RINGS
from scrolls import SCROLL_EFFECTS, SCROLLS
from world import Item, pick_weighted


def potion_heal_max(level):
    return 11 + level


def stow(item, player, log, message):
    pack = player.pack
    if len(pack.items) >= pack.slots:
        log.say("Your pack is full.")
        return False
    pack.items.append(item)
    log.say(message)
    return True


def pocket(item, player, _area, log):
    return stow(item, player, log, ITEMS[item.kind]["pocket"])


def pick_up_gold(_item, player, area, log):
    found = random.randrange(4, 12 + area.level * 3)
    player.gold += found
    log.say("Gold +" + str(found) + ".")
    return True


def pick_up_blade(_item, player, _area, log):
    if player.atk >= BLADE_CAP:
        log.say("Your blade is as keen as it gets.")
        return False
    player.atk += 1
    log.say("Blade power rises.")
    return True


def pick_up_shield(_item, player, _area, log):
    if player.armor >= ARMOR_CAP:
        log.say("You cannot carry more shielding.")
        return False
    player.armor += 1
    log.say("Shielding improves.")
    return True


def pick_up_bow(item, player, area, log):
    if player.pack.find("bow") is None:
        return pocket(item, player, area, log)
    salvaged = random.randrange(3, 8)
    return stow(Item("arrows", count=salvaged), player, log, "You strip the bow for " + str(salvaged) + " arrows.")


def quaff(item, player, area, log):
    amount = random.randrange(POTION_HEAL_MIN, potion_heal_max(area.level) + 1)
    player.pack.remove(item)
    player.heal(amount)
    log.say("Potion heals " + str(amount) + ".")
    return True


def eat(item, player, _area, log):
    player.pack.remove(item)
    player.max_hp += 1
    player.heal(FOOD_HEAL)
    log.say("You eat a ration.")
    return True


def ready(item, _player, _area, log):
    item.equipped = not item.equipped
    log.say("You ready the bow." if item.equipped else "You stow the bow.")
    return False


def count_arrows(item, _player, _area, log):
    log.say("Arrows: " + str(item.count) + ".")
    return False


def inspect_key(_item, _player, _area, log):
    log.say("A key for a gate.")
    return False


def read(item, player, area, log):
    pack = player.pack
    if item.effect == "identify" and pack.unidentified() is None:
        log.say("Nothing else is mysterious.")
        return False
    pack.remove(item)
    pack.identified[item.effect] = True
    SCROLLS[item.effect]["read"](player, area, log)
    area.update_visibility(player)
    return True


def wear(item, player, _area, log):
    pack = player.pack
    if item.equipped:
        if item.cursed:
            log.say("The ring won't come off.")
            return False
        item.equipped = False
        log.say("You take off the ring.")
        return True
    if sum(1 for other in pack.items if other.kind == "ring" and other.equipped) >= MAX_WORN:
        log.say("You already wear two rings.")
        return False
    item.equipped = True
    pack.identified[item.effect] = True
    log.say(RINGS[item.effect]["worn"])
    log.say("It is a " + RINGS[item.effect]["name"] + ".")
    return True


ITEMS = {
    "gold": {"glyph": "$", "pen": GOLD, "name": "gold", "pick_up": pick_up_gold},
    "potion": {"char": "!", "glyph": "!", "pen": GREEN_2, "name": "healing potion", "action": "ENTER quaff", "hint": None,
               "pocket": "You pocket a potion.", "pick_up": pocket, "use": quaff},
    "scroll": {"char": "s", "glyph": "?", "pen": PURPLE, "name": "unidentified scroll", "action": "ENTER read", "hint": None,
               "pocket": "You pocket a scroll.", "pick_up": pocket, "use": read},
    "food": {"char": "%", "glyph": "%", "pen": GOLD, "name": "food ration", "action": "ENTER eat", "hint": None,
             "pocket": "You pack a ration.", "pick_up": pocket, "use": eat},
    "bow": {"char": ")", "glyph": ")", "pen": GRAY_1, "name": "short bow", "action": "ENTER equip", "hint": "shoot the nearest foe",
            "pocket": "You pocket a bow.", "pick_up": pick_up_bow, "use": ready},
    "arrows": {"char": "/", "glyph": "/", "pen": GRAY_1, "name": "arrows", "action": "ENTER ready", "hint": "ammunition",
               "pocket": "You pocket arrows.", "pick_up": pocket, "use": count_arrows},
    "key": {"char": "k", "glyph": "k", "pen": GOLD, "name": "gate key", "action": "ENTER hold", "hint": "opens the ruin gate",
            "pocket": "You found a gate key.", "pick_up": pocket, "use": inspect_key},
    "ring": {"char": "=", "glyph": "=", "pen": PURPLE, "name": "unidentified ring", "action": "ENTER wear", "hint": None,
             "pocket": "You pocket a ring.", "pick_up": pocket, "use": wear},
    "blade": {"glyph": ")", "pen": GRAY_1, "name": "blade", "pick_up": pick_up_blade},
    "shield": {"glyph": "]", "pen": GREEN_4, "name": "shield", "pick_up": pick_up_shield},
}
ITEM_WEIGHTS = (
    ("gold", 26),
    ("potion", 12),
    ("scroll", 14),
    ("food", 12),
    ("arrows", 12),
    ("bow", 8),
    ("shield", 6),
    ("blade", 6),
)
DEEP_ITEM_WEIGHTS = ITEM_WEIGHTS + (("ring", RING_WEIGHT),)


def random_item(x, y, deep=False):
    kind = pick_weighted(DEEP_ITEM_WEIGHTS if deep else ITEM_WEIGHTS)
    if kind == "scroll":
        return Item(kind, x, y, effect=random.choice(SCROLL_EFFECTS))
    if kind == "arrows":
        return Item(kind, x, y, count=random.randrange(3, 8))
    if kind == "ring":
        effect = random.choice(RING_EFFECTS)
        return Item(kind, x, y, effect=effect, cursed=RINGS[effect]["cursed"])
    return Item(kind, x, y)
