"""Small, hardware-independent turn-based battle rules."""

import random


CREATURES = (
    ("Draceon", ("ELECTRIC", "DRAGON"), 100, (255, 205, 75)),
    ("Ethereon", ("WATER", "GHOST"), 110, (99, 215, 223)),
    ("Zephyreon", ("PSYCHIC", "FLYING"), 120, (192, 154, 244)),
)
ELEMENT_MOVES = (
    ("Spark Lance", "Dragon Rush"),
    ("Tide Pulse", "Haunt"),
    ("Mind Wave", "Sky Dive"),
)
MOVES = ("Quick Hit", None, None, "Mend")
# Only types present in this roster are needed; unlisted matchups are neutral.
TYPE_CHART = {
    "ELECTRIC": (("WATER", "FLYING"), ("ELECTRIC", "DRAGON")),
    "DRAGON": (("DRAGON",), ()),
    "WATER": ((), ("WATER", "DRAGON")),
    "GHOST": (("GHOST", "PSYCHIC"), ()),
    "PSYCHIC": ((), ("PSYCHIC",)),
    "FLYING": ((), ("ELECTRIC",)),
}


def move_name(creature, move):
    return ELEMENT_MOVES[creature][move - 1] if move in (1, 2) else MOVES[move]


def effectiveness(attack_type, defender):
    strong, resisted = TYPE_CHART[attack_type]
    multiplier = 1
    for element in CREATURES[defender][1]:
        if element in strong:
            multiplier *= 2
        elif element in resisted:
            multiplier *= 0.5
    return multiplier


class Rng:
    """Xorshift32, so two badges given the same seed roll identical numbers."""

    def __init__(self, seed):
        self.state = (seed & 0xFFFFFFFF) or 1

    def randint(self, low, high):
        x = self.state
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        self.state = x
        return low + x % (high - low + 1)


def first_actor(moves, coin):
    """Mend has priority; otherwise the coin (0 or 1) picks who acts first."""
    if moves[0] == 3 and moves[1] != 3:
        return 0
    if moves[1] == 3 and moves[0] != 3:
        return 1
    return coin & 1


class Battle:
    def __init__(self, creature, opponent, rng=None):
        self.creatures = (creature, opponent)
        self.hp = [CREATURES[creature][2], CREATURES[opponent][2]]
        self.mends = [2, 2]
        self.rng = rng if rng is not None else random

    def winner(self):
        if self.hp[0] == 0:
            return 1
        if self.hp[1] == 0:
            return 0
        return None

    def available(self, actor, move):
        return move in (0, 1, 2) or (move == 3 and self.mends[actor] > 0)

    def enemy_move(self):
        if self.hp[1] < CREATURES[self.creatures[1]][2] // 2 and self.mends[1]:
            return 3
        return self.rng.randint(0, 2)

    def act(self, actor, move):
        if actor not in (0, 1) or move not in (0, 1, 2, 3):
            raise ValueError("Invalid actor or move")
        if self.winner() is not None:
            raise ValueError("The battle has ended")
        if not self.available(actor, move):
            raise ValueError("No mends remaining")

        creature = self.creatures[actor]
        name = CREATURES[creature][0]
        title = name + " used " + move_name(creature, move) + "!"
        target = 1 - actor
        if move == 3:
            self.mends[actor] -= 1
            before = self.hp[actor]
            self.hp[actor] = min(CREATURES[creature][2], before + 28)
            return (title, "Recovered %d HP." % (self.hp[actor] - before), actor, "heal")

        if move == 2 and self.rng.randint(1, 100) > 75:
            return (title, "Missed! This move has 75% accuracy.", target, "miss")

        damage = (15, 19, 28)[move] + self.rng.randint(-2, 2)
        detail = ""
        if move in (1, 2):
            attack_type = CREATURES[creature][1][move - 1]
            multiplier = effectiveness(attack_type, self.creatures[target])
            damage = max(1, int(damage * multiplier))
            if multiplier > 1:
                detail = " Strong hit!"
            elif multiplier < 1:
                detail = " Resisted."
        damage = min(self.hp[target], damage)
        self.hp[target] -= damage
        return (title, "-%d HP.%s" % (damage, detail), target, "hit")

    def turn(self, first, moves):
        """Apply both actors' moves; return (actor, event, hp after) per action."""
        events = []
        for actor in (first, 1 - first):
            if self.winner() is not None:
                break
            event = self.act(actor, moves[actor])
            events.append((actor, event, tuple(self.hp)))
        return events
