# Verdicts and Creative 8-Ball prompts. MicroPython dicts are unordered, so
# every ordered collection here is a tuple and the IR beam sends indexes into
# these tuples. Append new entries at the end so older badges stay compatible.

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

# One prompt per icosahedron face: the Creative 8-Ball is a d20.
PROMPTS = (
    "WHAT'S THE ONE THING?",
    "CUT IT IN HALF",
    "SHOW THE CODE",
    "EARN THE FIRST 3 SECONDS",
    "KILL YOUR DARLINGS",
    "SAY IT LIKE A DEV WOULD",
    "MORE CONTRAST, LESS GRADIENT",
    "NAME THE ENEMY",
    "MAKE IT WEIRDER",
    "ONE IDEA PER FRAME",
    "TRUST THE WHITESPACE",
    "WRITE THE HEADLINE FIRST",
    "STEAL FROM THE TERMINAL",
    "PUT A HUMAN IN IT",
    "GO BOLDER, THEN EDIT",
    "WOULD A DEV SCREENSHOT THIS?",
    "LOSE THE STOCK PHOTO",
    "FEWER WORDS, SHARPER VERBS",
    "SHIP THE ROUGH CUT",
    "WHAT WOULD MONA DO?",
)


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


class ShuffleBag:
    # Deals every index once in a random order before any repeats, and never
    # deals the same index twice in a row across refills.

    def __init__(self, count, rng):
        self.count = count
        self.rng = rng
        self.pool = []
        self.last = None

    def next(self):
        if not self.pool:
            pool = list(range(self.count))
            for i in range(len(pool) - 1, 0, -1):
                j = self.rng.randint(0, i)
                pool[i], pool[j] = pool[j], pool[i]
            if self.count > 1 and pool[-1] == self.last:
                pool[0], pool[-1] = pool[-1], pool[0]
            self.pool = pool
        self.last = self.pool.pop()
        return self.last
