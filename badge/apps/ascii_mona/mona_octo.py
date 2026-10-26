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


def check_header(head):
    return len(head) >= 6 and head[0:4] == b"OCTO" and head[4] == P.VERSION and head[5] == P.Q
