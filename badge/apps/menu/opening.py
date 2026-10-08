import machine

from easing import easeOutBack, easeOutCubic, easeOutElastic

BACKGROUND_MS = 500
TILE_START_MS = 120
TILE_STAGGER_MS = 55
TILE_POP_MS = 320
RIBBON_DELAY_MS = 230
RIBBON_MS = 200
MONA_DELAY_MS = 100
MONA_MS = 1100
MONA_DROP = 1.2
SKIP_AFTER_MS = 300
MAX_STEP_MS = 50


def clamp01(value):
    return max(0.0, min(1.0, value))


def after_cold_boot():
    return machine.reset_cause() != machine.WDT_RESET


class Opening:
    def __init__(self, apps):
        self.elapsed = 0
        self.last_ticks = None
        last = max((app.row + app.column for app in apps.apps), default=0)
        self.tiles_done = TILE_START_MS + last * TILE_STAGGER_MS + TILE_POP_MS
        self.mona_start = self.tiles_done + MONA_DELAY_MS
        self.duration = max(self.tiles_done, RIBBON_DELAY_MS + RIBBON_MS, self.mona_start + MONA_MS)

    def advance(self):
        now = badge.ticks
        if self.last_ticks is not None:
            self.elapsed += min(now - self.last_ticks, MAX_STEP_MS)
        self.last_ticks = now

    def finish(self):
        self.elapsed = self.duration

    def skippable(self):
        return self.elapsed >= SKIP_AFTER_MS

    @property
    def done(self):
        return self.elapsed >= self.duration

    def background_level(self):
        return round(255 * (1 - easeOutCubic(clamp01(self.elapsed / BACKGROUND_MS))))

    def tile_scale(self, app):
        local = self.elapsed - TILE_START_MS - (app.row + app.column) * TILE_STAGGER_MS
        if local <= 0:
            return 0.0
        if local >= TILE_POP_MS:
            return 1.0
        return easeOutBack(local / TILE_POP_MS)

    def ribbon_hidden(self):
        return 1 - easeOutCubic(clamp01((self.elapsed - RIBBON_DELAY_MS) / RIBBON_MS))

    def mona_lift(self):
        progress = clamp01((self.elapsed - self.mona_start) / MONA_MS)
        return -MONA_DROP * (1 - easeOutElastic(progress))
