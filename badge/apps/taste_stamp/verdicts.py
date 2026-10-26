# Verdicts for Taste Stamp. MicroPython dicts are unordered, so every
# ordered collection here is a tuple.

VERDICTS = (
    "SHIP IT",
    "CERTIFIED BANGER",
    "NEEDS MORE TEETH",
    "KILL THE FLUFF",
    "TOO SAFE",
    "WHERE IS THE TENSION?",
    "MAKE THE DEV THE HERO",
)

# Primer light-theme ink colours, one per verdict, readable on cream paper.
INKS = (
    (26, 127, 55),
    (191, 57, 137),
    (188, 76, 0),
    (207, 34, 46),
    (154, 103, 0),
    (9, 105, 218),
    (130, 80, 223),
)

# Small print stamped under each verdict.
FOOTERS = (
    "APPROVED",
    "APPROVED",
    "REVISE",
    "REVISE",
    "REVISE",
    "REVISE",
    "REVISE",
)

STAMP_HEADER = "CREATIVE DIRECTOR"


class Rng:
    # xorshift32. MicroPython has no random.Random and seeds differently from
    # CPython, so seeded behaviour (and the tests) use this instead.

    def __init__(self, seed=0x2545F491):
        seed = int(seed) & 0xFFFFFFFF
        self.state = seed or 0x2545F491

    def next_u32(self):
        x = self.state
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        self.state = x
        return x

    def random(self):
        # 24 bits so the result stays below 1.0 in single-precision floats.
        return (self.next_u32() >> 8) / 16777216.0

    def randint(self, low, high):
        return low + self.next_u32() % (high - low + 1)

    def uniform(self, low, high):
        return low + (high - low) * self.random()
