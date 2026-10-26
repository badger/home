# Original pixel art for The Octocat Trail, drawn for this app in the spirit
# of 1980s 8-bit educational games. Nothing here is traced or sampled from any
# commercial game. Sprites are rows of palette letters; "." is transparent.
# Pure Python: no badge globals, so the tests can import it.

BLACK, WHITE, GREEN, VIOLET, ORANGE, BLUE, NAVY, GREY, DKGREEN = range(9)
YELLOW, PINK, PURPLE, MAGENTA, AQUA, BROWN, LTBLUE, GOLD, PLUM = range(9, 18)

PALETTE = (
    (0, 0, 0),
    (255, 255, 255),
    (20, 245, 60),
    (255, 68, 253),
    (255, 106, 60),
    (20, 207, 253),
    (60, 50, 160),
    (156, 156, 156),
    (0, 150, 70),
    (255, 221, 0),
    (255, 170, 200),
    (120, 70, 230),
    (227, 30, 96),
    (114, 255, 208),
    (150, 90, 40),
    (190, 200, 255),
    (215, 150, 0),
    (70, 40, 140),
)
LETTERS = "KWGVOBNgDYPMRAbLym"


def green_rgb(rgb):
    """One colour as seen on a green phosphor monitor."""
    r, g, b = rgb
    if r == 0 and g == 0 and b == 0:
        return (0, 0, 0)
    lum = (r * 30 + g * 59 + b * 11) // 100
    level = 60 + lum * 195 // 255
    return (level // 6, level, level // 4)


def palette(green=False):
    if not green:
        return PALETTE
    return tuple(green_rgb(rgb) for rgb in PALETTE)
