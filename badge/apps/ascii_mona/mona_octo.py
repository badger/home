"""The real MyOctocat art.

The part library is GitHub's own MyOctocat builder
(https://myoctocat.com/build-your-octocat/). The ascii_mona bake tool turned
its SVG parts into octocat.bin, and mona_parts indexes that file. Octocat art
(c) GitHub.
"""

import mona_parts as P


EYES = 0
MOUTHS = 1
HAIR = 2
HEADGEAR = 3
TOPS = 4
BOTTOMS = 5
FOOTWEAR = 6
PROPS = 7
EYEWEAR = 8
FACEHAIR = 9
MISC = 10
PICKS = 10  # categories with one pick each; MISC takes a tuple

CUSTOM = 0xFF
ORIGINAL = 1
MASKED = 2


def count(cat):
    return len(P.PARTS[cat])


def part_name(cat, index):
    parts = P.PARTS[cat]
    if index is None or index < 0 or index >= len(parts):
        return "None"
    return parts[index][0]


def find_part(cat, name):
    """Index of the part called name in a category, or -1."""
    parts = P.PARTS[cat]
    for i in range(len(parts)):
        if parts[i][0] == name:
            return i
    return -1


def colours(body, face, eye, hair, facehair):
    """0xRRGGBB for each paint role, in mona_parts.ROLES order."""
    b = P.BODY[body % len(P.BODY)]
    f = P.FACE[face % len(P.FACE)]
    return (
        b[0], b[1], b[2], f[0], f[1],
        P.EYE[eye % len(P.EYE)],
        P.HAIR[hair % len(P.HAIR)],
        P.FACEHAIR[facehair % len(P.FACEHAIR)],
    )


def layers(data):
    """Yield (role, rgb, alpha, variant, contours) for one block.

    role indexes mona_parts.ROLES, or is CUSTOM with rgb set. Each contour is
    bytes of little-endian int16 (x, y) pairs in SVG units * mona_parts.Q.
    """
    count = data[0] | (data[1] << 8)
    pos = 2
    for _ in range(count):
        role = data[pos]
        pos += 1
        rgb = 0
        if role == CUSTOM:
            rgb = (data[pos] << 16) | (data[pos + 1] << 8) | data[pos + 2]
            pos += 3
        alpha = data[pos]
        variant = data[pos + 1]
        contours = data[pos + 2] | (data[pos + 3] << 8)
        pos += 4
        out = []
        for _ in range(contours):
            n = (data[pos] | (data[pos + 1] << 8)) * 4
            pos += 2
            out.append(data[pos:pos + n])
            pos += n
        yield role, rgb, alpha, variant, out


def check_header(head):
    return len(head) >= 6 and head[0:4] == b"OCTO" and head[4] == P.VERSION and head[5] == P.Q
