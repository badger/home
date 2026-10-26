# Motion detectors for Taste Stamp, starting with the flip.
#
# Flips come from badge.upside_down(), which the firmware already debounces
# for its own display rotation. Times are integer milliseconds from
# badge.ticks, so behaviour does not depend on the frame rate.


class FlipDetector:
    # Reports each change of orientation, in either direction, once it has
    # held for SETTLE_MS.

    SETTLE_MS = 120
    COOLDOWN_MS = 600

    def __init__(self, upside_down=False):
        self.state = bool(upside_down)
        self.pending_since = None
        self.last_flip = None

    def update(self, upside_down, now):
        upside_down = bool(upside_down)
        if upside_down == self.state:
            self.pending_since = None
            return False
        if self.pending_since is None:
            self.pending_since = now
        if now - self.pending_since < self.SETTLE_MS:
            return False
        self.state = upside_down
        self.pending_since = None
        if self.last_flip is not None and now - self.last_flip < self.COOLDOWN_MS:
            return False
        self.last_flip = now
        return True
