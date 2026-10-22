"""MDI camera contours for the 2026 vector-icon launcher (Apache-2.0).

Coordinates are centred and normalized to the launcher's unit-sized icons.
See assets/NOTICE.txt and assets/LICENSE-MDI.txt.
"""

import math


def arc(cx, cy, radius, start, end, steps):
    return [(cx + radius * math.cos(math.radians(start + (end - start) * i / steps)),
             cy + radius * math.sin(math.radians(start + (end - start) * i / steps)))
            for i in range(steps + 1)]


def contour(points):
    return tuple(value for x, y in points for value in ((x - 12) / 24, (y - 12) / 24))


CONTOURS = (
    contour([(4, 4), (7, 4), (9, 2), (15, 2), (17, 4), (20, 4)]
            + arc(20, 6, 2, -90, 0, 8)
            + [(22, 18)] + arc(20, 18, 2, 0, 90, 8)
            + [(4, 20)] + arc(4, 18, 2, 90, 180, 8)
            + [(2, 6)] + arc(4, 6, 2, 180, 270, 8)),
    contour(arc(12, 12, 5, 0, -360, 64)),
    contour(arc(12, 12, 3, 0, 360, 48)),
)
