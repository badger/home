from content import ARMOR_CAP, PACK_BLOCK, PACK_MAX_SLOTS
from monsters import spawn_enemy
from world import MAP_W


def read_identify(player, _area, log):
    log.say("This scroll is an identify scroll.")
    item = player.pack.unidentified()
    player.pack.identified[item.effect] = True
    log.say("Now known: " + player.pack.name(item) + ".")


def read_enchant_armor(player, _area, log):
    player.armor = min(ARMOR_CAP + 2, player.armor + 1)
    log.say("Your armor glows faintly for a moment.")


def read_enchant_weapon(player, _area, log):
    player.atk += 1
    log.say("Your weapon glows blue for a moment.")


def read_mapping(_player, area, log):
    for row in area.explored:
        row[:] = [True] * MAP_W
    log.say("Oh, now this scroll has a map on it.")


def read_teleport(player, area, _log):
    player.x, player.y = area.random_floor(player, False, 0)


def read_gold_detection(_player, area, _log):
    area.reveal("gold")


def read_remove_curse(player, _area, log):
    for item in player.pack.items:
        item.cursed = False
    log.say("You feel as if somebody is watching over you.")


def read_carry(player, _area, log):
    pack = player.pack
    if pack.slots < PACK_MAX_SLOTS:
        pack.slots = min(PACK_MAX_SLOTS, pack.slots + PACK_BLOCK)
        log.say("Your pack feels roomier.")
    else:
        log.say("Your pack cannot hold more.")


def read_hold_monster(player, area, log):
    for enemy in area.nearby_enemies(player.x, player.y, 6):
        enemy.held = 5
    log.say("The monsters around you stop moving.")


def read_scare_monster(player, area, log):
    for enemy in area.nearby_enemies(player.x, player.y, 9):
        enemy.scared = 8
    log.say("You hear maniacal laughter in the distance")


def read_food_detection(_player, area, log):
    if area.reveal("food"):
        log.say("Your nose tingles as you sense food.")
    else:
        log.say("Your nose tingles briefly.")


def read_monster_confusion(player, _area, log):
    player.confuse = 1
    log.say("Your hands begin to glow red")


def read_sleep(player, _area, log):
    player.sleep = 4
    log.say("You fall asleep")


def read_create_monster(player, area, log):
    spawn_enemy(area, player, False, 5)
    log.say("You hear a faint cry of anguish")


def read_aggravate(_player, area, log):
    for enemy in area.enemies:
        enemy.awake = True
    log.say("You hear a high pitched humming noise")


def read_blank(_player, _area, log):
    log.say("This scroll seems to be blank.")


SCROLLS = {
    "identify": {"name": "scroll of identify", "char": "i", "hint": "names one carried item", "read": read_identify},
    "enchant_armor": {"name": "scroll of enchant armor", "char": "a", "hint": "+1 armor", "read": read_enchant_armor},
    "enchant_weapon": {"name": "scroll of enchant weapon", "char": "w", "hint": "+1 attack", "read": read_enchant_weapon},
    "mapping": {"name": "scroll of magic mapping", "char": "m", "hint": "reveals the level", "read": read_mapping},
    "teleport": {"name": "scroll of teleportation", "char": "t", "hint": "moves you elsewhere", "read": read_teleport},
    "gold_detection": {"name": "scroll of gold detection", "char": "g", "hint": "reveals gold", "read": read_gold_detection},
    "remove_curse": {"name": "scroll of remove curse", "char": "c", "hint": "lifts curses", "read": read_remove_curse},
    "carry": {"name": "scroll of carry", "char": "p", "hint": "+9 pack slots", "read": read_carry},
    "hold_monster": {"name": "scroll of hold monster", "char": "h", "hint": "freezes nearby foes", "read": read_hold_monster},
    "scare_monster": {"name": "scroll of scare monster", "char": "f", "hint": "routs nearby foes", "read": read_scare_monster},
    "food_detection": {"name": "scroll of food detection", "char": "d", "hint": "reveals food", "read": read_food_detection},
    "monster_confusion": {"name": "scroll of monster confusion", "char": "r", "hint": "confuses your next hit", "read": read_monster_confusion},
    "sleep": {"name": "scroll of sleep", "char": "z", "hint": "puts you to sleep", "read": read_sleep},
    "create_monster": {"name": "scroll of create monster", "char": "n", "hint": "summons a foe", "read": read_create_monster},
    "aggravate": {"name": "scroll of aggravate monsters", "char": "u", "hint": "wakes every foe", "read": read_aggravate},
    "blank": {"name": "blank paper", "char": "b", "hint": "nothing at all", "read": read_blank},
}
SCROLL_EFFECTS = tuple(SCROLLS.keys())
