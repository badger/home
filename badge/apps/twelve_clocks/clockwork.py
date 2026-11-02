"""Shared font and bounded clock state; no display or network dependencies."""

from math import pi
import micropython

NAMES = (
    "Pendulum", "Overlaid circles", "Double circle", "Colour history",
    "Rotated numbers", "Game of Life", "Time as a hand", "Zoom and fade",
    "Clocks as pixels", "Rotated grid", "Rotating pixels", "Cube",
)
PERIODS = (2000, 0, 6000, 0, 0, 0, 0, 2000 * pi / 1.5, 0, 0, 5000, 0)

# Original CodingTrain font, packed as seven five-bit rows per character.
FONT = {
    "0": bytes((14, 17, 17, 17, 17, 17, 14)),
    "1": bytes((2, 6, 2, 2, 2, 2, 2)),
    "2": bytes((14, 17, 1, 2, 4, 8, 31)),
    "3": bytes((14, 17, 1, 6, 1, 17, 14)),
    "4": bytes((2, 6, 10, 18, 31, 2, 2)),
    "5": bytes((31, 16, 30, 1, 1, 17, 14)),
    "6": bytes((14, 16, 30, 17, 17, 17, 14)),
    "7": bytes((31, 1, 1, 2, 4, 4, 4)),
    "8": bytes((14, 17, 17, 14, 17, 17, 14)),
    "9": bytes((14, 17, 17, 17, 15, 1, 14)),
    "A": bytes((14, 17, 17, 31, 17, 17, 17)),
    "M": bytes((17, 27, 21, 17, 17, 17, 17)),
    "P": bytes((30, 17, 17, 30, 16, 16, 16)),
    ":": bytes((0, 4, 0, 0, 0, 4, 0)),
    " ": bytes(7),
}

# Original font_shapes.js contours: consecutive decimal x,y pairs (0..7).
# Keeping the disjoint polygons preserves the grid's outlines and cube alpha.
CONTOURS = {
    "0": ("10404111", "01111606", "41515646", "16464717"),
    "1": ("3040473732222131",),
    "2": ("10404111", "01111202", "41515343", "33434434",
          "24343525", "1525265657070616"),
    "3": ("10404111", "01111202", "41515343", "23434424",
          "44545646", "05151606", "16464717"),
    "4": ("304044545545473735050313143432222131", "12222313"),
    "5": ("0050511112424303", "43535646", "05151606", "16464717"),
    "6": ("10404111", "0111124243131606", "43535646", "16464717"),
    "7": ("005053434101", "33434434", "24343727"),
    "8": ("10404111", "01111303", "41515343", "13434414",
          "04141606", "44545646", "16464717"),
    "9": ("10404111", "01111404", "4151564645151444", "16464717"),
    "A": ("10404111", "011113434151574744141707"),
    "P": ("00404111134344141707", "41515343"),
    "M": ("0010112122121707", "4050574742323141", "22323323"),
    ":": ("21313222", "25353626"),
    " ": (),
}


def hour12(hour):
    return hour % 12 or 12


def clock_text(hour, minute, second=None):
    text = "%2d:%02d" % (hour12(hour), minute)
    return text if second is None else text + ":%02d" % second


def pixels(text):
    for i, char in enumerate(text):
        for y, row in enumerate(FONT[char]):
            for x in range(5):
                if row & (16 >> x):
                    yield i * 6 + x, y


def selected_index(value):
    # bool is an int subclass, but not a valid persisted selection.
    return value if type(value) is int and 0 <= value < 12 else 0


class Timing:
    """Per-face phase and work cadence, independent of render callback rate."""

    def __init__(self, index):
        self.index = index
        self.phase = 0
        self.wait = 0
        self.last_key = None

    def advance(self, delta, second, blink, force=False):
        period = PERIODS[self.index]
        if period:
            self.phase = (self.phase + max(0, delta)) % period
        interval = 50 if self.index == 5 else 1000 / 15
        self.wait += max(0, delta)
        key = (second, blink) if self.index == 6 else second
        animated = self.index in (0, 2, 5, 7, 10)
        due = (force or self.last_key is None or (animated and self.wait >= interval)
               or (self.index != 5 and self.last_key != key))
        if due:
            self.wait = 0
            self.last_key = key
        return due


class History:
    """Reconstruct at most 25 seconds, even after backward RTC corrections."""

    def __init__(self, hue):
        self.hue = hue
        self.last = None
        self.count = 0

    def update(self, now):
        if self.last is None:
            self.count = 1
        elif now != self.last:
            delta = now - self.last
            self.count = min(25, self.count + delta) if delta > 0 else 25
            self.hue = (self.hue + 5 * delta) % 360
        self.last = now

    def entries(self):
        for age in range(self.count - 1, -1, -1):
            yield self.last - age, (self.hue - age * 5) % 360, age


class Life:
    COLS = 63
    ROWS = 30

    def __init__(self):
        self.front = bytearray(63 * 30)
        self.back = bytearray(63 * 30)

    def seed(self, text, value):
        for x, y in pixels(text):
            self.front[(y + 11) * 63 + x + 8] = value

    def step(self, text):
        self.seed(text, 1)
        life_step(self.front, self.back)
        self.front, self.back = self.back, self.front
        self.seed(text, 0)


@micropython.viper
def life_step(source, target):
    """Finite boundaries, not the wrapping board of the badge's Life app."""
    src = ptr8(source)
    dst = ptr8(target)
    for y in range(30):
        for x in range(63):
            index = y * 63 + x
            count = 0
            if y > 0:
                count += src[index - 63]
                if x > 0:
                    count += src[index - 64]
                if x < 62:
                    count += src[index - 62]
            if x > 0:
                count += src[index - 1]
            if x < 62:
                count += src[index + 1]
            if y < 29:
                count += src[index + 63]
                if x > 0:
                    count += src[index + 62]
                if x < 62:
                    count += src[index + 64]
            dst[index] = 1 if count == 3 or (count == 2 and src[index]) else 0
