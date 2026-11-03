"""Advice is based on a continuous series of fresh samples, never a UI timer."""

from clock import elapsed


class Advisor:
    def __init__(self, settings):
        self.settings = settings
        self.items = settings["appliances"]
        self.max_gap_ms = settings["poll_interval_ms"] + 3 * settings["request_timeout_ms"] + 1000
        self.invalidate()

    def invalidate(self):
        self.since = [None] * len(self.items)
        self.statuses = ["UNKNOWN"] * len(self.items)
        self.last_sample = None

    def update(self, sample, now):
        if sample is None:
            self.invalidate()
            return
        if self.last_sample is not None:
            gap = elapsed(now, self.last_sample)
            if gap <= 0:
                return
            if gap > self.max_gap_ms:
                self.invalidate()
        self.last_sample = now
        usable = sample["surplus_w"] - self.settings["reserve_w"]
        importing = sample["import_w"] > self.settings["import_threshold_w"]
        for index, item in enumerate(self.items):
            if importing or usable < item["watts"]:
                self.since[index] = None
                self.statuses[index] = "WAIT"
            elif self.since[index] is None:
                self.since[index] = now
                self.statuses[index] = "WAIT"
            elif elapsed(now, self.since[index]) >= self.settings["stability_ms"]:
                self.statuses[index] = "READY"

    def remaining_s(self, index, now):
        if self.since[index] is None:
            return None
        left = self.settings["stability_ms"] - elapsed(now, self.since[index])
        return max(0, (left + 999) // 1000)
