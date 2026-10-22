import random

MAX_WORN = 2


def regenerate(player, _area, _log, turns):
    if turns % 3 == 0:
        player.heal(1)


def blink(player, area, log, _turns):
    if random.randrange(20) == 0:
        player.x, player.y = area.random_floor(player, False, 0)
        log.say("You blink elsewhere.")


def aggravate(_player, area, _log, _turns):
    for enemy in area.enemies:
        enemy.awake = True


RINGS = {
    "protection": {"name": "ring of protection", "hint": "+2 armor", "worn": "You feel protected.", "cursed": False},
    "strength": {"name": "ring of strength", "hint": "+2 attack", "worn": "You feel stronger.", "cursed": False},
    "regeneration": {"name": "ring of regeneration", "hint": "heals over time", "worn": "Your wounds begin to knit.",
                     "cursed": False, "turn": regenerate},
    "sight": {"name": "ring of sight", "hint": "+3 sight", "worn": "Your eyes sharpen.", "cursed": False},
    "stealth": {"name": "ring of stealth", "hint": "foes notice you late", "worn": "Your steps fall silent.", "cursed": False},
    "weakness": {"name": "ring of weakness", "hint": "-2 attack", "worn": "You feel weaker.", "cursed": True},
    "teleportation": {"name": "ring of teleportation", "hint": "moves you at random", "worn": "You feel unsteady.",
                      "cursed": True, "turn": blink},
    "aggravation": {"name": "ring of aggravation", "hint": "wakes every foe", "worn": "You hear a distant howl.",
                    "cursed": True, "turn": aggravate},
}
RING_EFFECTS = tuple(RINGS.keys())
