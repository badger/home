"""Shared 320x240 layout for Badgeware, Tkinter, and SVG previews."""

from character import Buddy
from clock import elapsed
from controller import PAGES
from demo import SCENARIOS

BG = "#0d1117"
PANEL = "#161b22"
EDGE = "#30363d"
TEXT = "#e6edf3"
MUTED = "#8b949e"
GREEN = "#3fb950"
GOLD = "#e3b341"
BLUE = "#58a6ff"
RED = "#f85149"


def watts(value):
    return "%.0f W" % value


class BadgePainter:
    def __init__(self, screen, shape, color):
        self.screen, self.shape, self.color = screen, shape, color
        self.width, self.height = screen.width, screen.height
        self.pens = {}

    def _pen(self, value):
        if value not in self.pens:
            self.pens[value] = self.color.rgb(
                int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))
        self.screen.pen = self.pens[value]

    def clear(self, value):
        self._pen(value)
        self.screen.clear()

    def rect(self, x, y, width, height, value):
        self._pen(value)
        self.screen.shape(self.shape.rectangle(x, y, width, height))

    def line(self, x1, y1, x2, y2, value):
        self._pen(value)
        self.screen.line(x1, y1, x2, y2)

    def text(self, value, x, y, pen):
        self._pen(pen)
        self.screen.text(value, x, y)

    def measure(self, value):
        return self.screen.measure_text(value)[0]


class UI:
    def __init__(self, painter):
        self.p = painter
        self.buddy = Buddy()

    def fit(self, value, width):
        if self.p.measure(value) <= width:
            return value
        while value and self.p.measure(value + "...") > width:
            value = value[:-1]
        return value + "..."

    def text(self, value, x, y, pen=TEXT, width=None):
        width = self.p.width - x - 10 if width is None else width
        self.p.text(self.fit(value, width), x, y, pen)

    def right(self, value, y, pen=TEXT):
        self.p.text(value, self.p.width - 12 - self.p.measure(value), y, pen)

    def center(self, value, y, pen=TEXT):
        value = self.fit(value, self.p.width - 24)
        self.p.text(value, (self.p.width - self.p.measure(value)) / 2, y, pen)

    def wrap(self, value, y, lines=3, pen=RED):
        wrapped, current = [], ""
        for word in value.split():
            candidate = current + (" " if current else "") + word
            if self.p.measure(candidate) > self.p.width - 24 and current:
                wrapped.append(current)
                current = word
            else:
                current = candidate
        if current:
            wrapped.append(current)
        if len(wrapped) > lines:
            wrapped = wrapped[:lines - 1] + [" ".join(wrapped[lines - 1:])]
        for index, line in enumerate(wrapped):
            self.text(line, 12, y + index * 14, pen)

    def draw(self, app, now, delta_ms):
        self.buddy.advance(delta_ms)
        p = self.p
        p.clear(BG)
        p.rect(0, 0, p.width, 29, PANEL)
        self.text("SOLAR BUDDY" if app.page == 0 else PAGES[app.page].upper(), 12, 10,
                  TEXT, p.width - 155)
        status = app.status
        if app.mode == "demo" and status != "DEMO":
            status = "DEMO/" + status
        self.right(status, 10, GOLD if app.mode == "demo" else GREEN if app.valid else RED)
        if app.page == 0:
            self.dashboard(app, now)
        elif app.page == 1:
            self.energy(app, now)
        elif app.page == 2:
            self.appliances(app, now)
        else:
            self.settings(app, now)
        p.line(10, p.height - 21, p.width - 10, p.height - 21, EDGE)
        hint = "L/R screens"
        if app.page == 2:
            hint += " | U/D choose | SEL details"
        elif app.page == 3:
            hint += " | SEL switch demo/live"
        elif app.mode == "demo":
            hint += " | U/D scenario | SEL wake"
        else:
            hint += " | SEL retry | MENU setup"
        self.text(hint, 10, p.height - 14, MUTED)

    def dashboard(self, app, now):
        self.buddy.draw(self.p, self.p.width / 2, 77, app.mood.state, app.is_awake(now))
        messages = {"excited": "PLENTY OF SUNSHINE!", "happy": "SOME SOLAR TO SPARE",
                    "neutral": "A LITTLE SOLAR AVAILABLE", "sleepy": "USING GRID POWER",
                    "offline": "WHERE DID MY SUNSHINE GO?"}
        message = messages[app.mood.state]
        if app.valid and app.sample["surplus_w"] < 100 and app.mood.state == "neutral":
            message = "LITTLE OR NO SOLAR TO SPARE"
        self.center(message, 122, GOLD if app.valid else MUTED)
        self.metric("Solar production", app, "solar_w", 145, GOLD)
        self.metric("Home consumption", app, "house_w", 163, TEXT)
        key = "import_w" if app.valid and app.sample["import_w"] > 0 else "export_w"
        self.metric("Grid import" if key == "import_w" else "Grid export",
                    app, key, 181, RED if key == "import_w" else GREEN)
        self.p.rect(10, 199, self.p.width - 20, 17, PANEL)
        if not app.valid:
            advice = app.error or "Waiting for a fresh reading"
        else:
            ready = [item["name"] for index, item in enumerate(app.advisor.items)
                     if app.advisor.statuses[index] == "READY"]
            advice = ready[0] + ": READY" if ready else "Appliances: wait for stable surplus"
        self.text(advice, 16, 203, GREEN if "READY" in advice else MUTED,
                  self.p.width - 32)

    def metric(self, label, app, key, y, pen):
        self.text(label, 14, y, MUTED, self.p.width - 115)
        self.right(watts(app.sample[key]) if app.valid else "--", y, pen)

    def energy(self, app, now):
        for label, key, y, pen in (
                ("Solar production", "solar_w", 44, GOLD),
                ("Grid import", "import_w", 66, RED),
                ("Grid export / surplus", "export_w", 88, GREEN),
                ("House consumption", "house_w", 110, TEXT)):
            self.metric(label, app, key, y, pen)
        self.text("Home = solar + import - export", 12, 141, BLUE)
        if app.last_good is not None:
            self.text("Last good sample: %ds ago" % (elapsed(now, app.last_good) // 1000),
                      12, 160, MUTED)
        if app.mode == "demo":
            scenario = app.source.active_name if app.source else SCENARIOS[app.demo_index]
            self.text("SIMULATED: " + scenario, 12, 179, GOLD)
        else:
            self.text("Live REST data | no battery assumed", 12, 179, MUTED)
        if not app.valid:
            self.text(app.error, 12, 199, RED)
        else:
            self.text("Read-only advice. No appliance control.", 12, 199, MUTED)

    def appliances(self, app, now):
        if app.detail:
            item = app.advisor.items[app.selected]
            self.text(item["name"], 12, 44, BLUE)
            for label, value, y in (
                    ("Estimated load", watts(item["watts"]), 71),
                    ("Available export", watts(app.sample["surplus_w"]) if app.valid else "--", 93),
                    ("Safety reserve", watts(app.settings["reserve_w"]), 115),
                    ("Status", app.advisor.statuses[app.selected], 137)):
                self.text(label, 12, y, MUTED, self.p.width - 110)
                self.right(value, y, GREEN if value == "READY" else TEXT)
            remaining = app.advisor.remaining_s(app.selected, now)
            note = ("Need more surplus" if remaining is None else
                    "Stable evidence: %ds remaining" % remaining if remaining else
                    "Waiting for next sample" if app.advisor.statuses[app.selected] != "READY"
                    else "Stable surplus observed")
            self.text(note if app.valid else "Need fresh sensor readings", 12, 164, GOLD)
            self.text("One appliance at a time; loads vary.", 12, 189, MUTED)
            self.text("Not a solar-only cycle guarantee.", 12, 204, MUTED)
            return
        first = (app.selected // 4) * 4
        for row, index in enumerate(range(first, min(first + 4, len(app.advisor.items)))):
            item = app.advisor.items[index]
            y = 41 + row * 37
            self.p.rect(10, y, self.p.width - 20, 31, "#1c2d3f" if index == app.selected else PANEL)
            self.text(item["name"], 17, y + 5, TEXT, self.p.width - 116)
            status = app.advisor.statuses[index]
            self.right(status, y + 5, GREEN if status == "READY" else GOLD if status == "WAIT" else MUTED)
            self.text(watts(item["watts"]) + " estimated", 17, y + 18, MUTED)
        self.text("Each READY is an individual recommendation.", 12, 193, MUTED)
        self.text("Recheck after starting any appliance.", 12, 207, MUTED)

    def settings(self, app, now):
        self.text("Mode: " + ("SIMULATED - no Wi-Fi" if app.mode == "demo" else "LIVE - read only"),
                  12, 42, GOLD if app.mode == "demo" else GREEN)
        self.text("Polling: %ds | stale after: %ds" % (
            app.settings["poll_interval_ms"] // 1000, app.settings["stale_after_ms"] // 1000),
                  12, 62, MUTED)
        self.text("READY needs %ds + %.0f W reserve" % (
            app.settings["stability_ms"] // 1000, app.settings["reserve_w"]), 12, 82, MUTED)
        self.text("Sensor report limit: %ds" % app.settings["sensor_max_age_s"], 12, 102, MUTED)
        earned = app.demo_superstar if app.mode == "demo" else app.superstar
        self.text("Solar Superstar: " + ("earned" if earned else "> %.0f W export" %
                                       app.settings["milestone_w"]), 12, 122,
                  GOLD if earned else MUTED)
        if app.mode == "demo":
            self.text("Scenario: " + SCENARIOS[app.demo_index], 12, 142, BLUE)
        else:
            self.text("Credentials kept outside the app folder", 12, 142, BLUE)
        note = app.error or app.hardware_note
        if note:
            self.wrap(note, 165, lines=3, pen=RED if app.error else MUTED)
        else:
            self.text("SELECT toggles live/demo.", 12, 170, TEXT)
            self.text("HOME returns to the badge launcher.", 12, 191, MUTED)
