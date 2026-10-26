"""Rules for The Octocat Trail.

Pure game logic with no badge runtime globals, so the same code runs on the
badge's MicroPython and under CPython tests. Randomness comes from an
injected Rng, ordered data lives in tuples (MicroPython dicts are unordered),
and only APIs that exist in MicroPython 1.29 are used.
"""

MASK32 = 0xFFFFFFFF


def fnv1a(text):
    """Deterministic 32-bit string hash; hash(str) differs on MicroPython."""
    value = 0x811C9DC5
    for char in str(text):
        value ^= ord(char) & 0xFF
        value = (value * 0x01000193) & MASK32
    return value


class Rng:
    """Seeded xorshift32 generator; MicroPython has no random.Random class."""

    def __init__(self, seed=1):
        self.seed(seed)

    def seed(self, value):
        self.state = (int(value) & MASK32) or 0x6D2B79F5

    def next32(self):
        x = self.state
        x ^= (x << 13) & MASK32
        x ^= x >> 17
        x ^= (x << 5) & MASK32
        self.state = x
        return x

    def random(self):
        return (self.next32() >> 8) / 16777216.0

    def randint(self, low, high):
        return low + self.next32() % (high - low + 1)

    def uniform(self, low, high):
        return low + (high - low) * self.random()

    def chance(self, probability):
        return self.random() < probability

    def choice(self, items):
        return items[self.next32() % len(items)]

    def weighted(self, pairs):
        total = 0
        for weight, _item in pairs:
            total += weight
        if total <= 0:
            return None
        pick = self.random() * total
        for weight, item in pairs:
            if pick < weight:
                return item
            pick -= weight
        return pairs[-1][1]
