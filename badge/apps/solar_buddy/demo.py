"""Deterministic, explicitly simulated scenarios that never use the network."""

import math

from clock import elapsed
from energy import reading

SCENARIOS = ("Automatic", "Sunny", "Solar peak", "Cloudy", "Busy home",
             "Night", "No network", "Missing sensor", "Stale sensor")


class Demo:
    def __init__(self, scenario=0):
        self.scenario = scenario % len(SCENARIOS)
        self.last = None
        self.started = None
        self.active_name = SCENARIOS[self.scenario]

    def tick(self, now):
        if self.last is not None and elapsed(now, self.last) < 1000:
            return None
        if self.started is None:
            self.started = now
        self.last = now
        age = elapsed(now, self.started)
        index = self.scenario
        if index == 0:
            sequence = (1, 2, 3, 4, 5, 6, 1)
            index = sequence[(age // 45000) % len(sequence)]
        self.active_name = SCENARIOS[index]
        if index == 6:
            return "error", "Demo: Home Assistant connection lost"
        if index == 7:
            return "error", "Demo: a configured sensor is unavailable"
        if index == 8:
            return "stale", "Demo: sensor report is stale"
        solar, home = {1: (3400, 2200), 2: (6500, 1500), 3: (1100, 700),
                       4: (1200, 4000), 5: (0, 420)}[index]
        if solar:
            solar += math.sin(age / 6000) * 70
        home += math.sin(age / 8500) * 25
        difference = solar - home
        return "reading", reading(solar, max(0, -difference), max(0, difference))

    def close(self):
        return
