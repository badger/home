"""AgentViz tracks and recent-event replay for the Universe 2026 badge."""

import os
import sys

APP_DIR = "/system/apps/agentviz"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

from agentviz_client import Monitor


TRACK_NAMES = ("THINK", "TOOLS", "CONTEXT", "OUTPUT", "AGENTS")
PALETTE = ((148, 163, 184), (59, 158, 255), (167, 139, 250), (16, 217, 122),
           (6, 182, 212))
DEMO_EVENTS = (
    [0, 0, 800, 2, "User input", "user", 0, 0],
    [1, 800, 1200, 0, "Reasoning", "assistant", 0, 0],
    [2, 2000, 2500, 1, "task", "explore", 0, 0],
    [3, 2200, 300, 4, "Agent started", "explore", 0, 0],
    [4, 3000, 2500, 1, "task", "code-review", 0, 0],
    [5, 3500, 600, 2, "Tool result", "explore", 0, 0],
    [6, 4300, 900, 1, "bash", "code-review", 1, 0],
    [7, 5500, 700, 0, "Reasoning", "assistant", 0, 0],
    [8, 6200, 1200, 1, "edit", "assistant", 0, 0],
    [9, 7500, 1400, 1, "bash", "assistant", 0, 0],
    [10, 8900, 700, 3, "Response", "assistant", 0, 0],
)


def demo_packet(elapsed):
    count = min(len(DEMO_EVENTS), 1 + int(elapsed % 13000) // 900)
    events = DEMO_EVENTS[:count]
    tools = {}
    for event in events:
        if event[3] == 1:
            tools[event[4]] = tools.get(event[4], 0) + 1
    return {"epoch": "demo", "state": "ok", "source": "synthetic",
            "events": events, "tools": sorted(tools.items(), key=lambda t: -t[1])[:4],
            "metrics": [count, 1, sum(e[3] == 1 for e in events),
                        sum(e[6] for e in events), events[-1][1] + events[-1][2], -1, -1]}


def duration(ms):
    if ms < 1000:
        return "%dms" % ms
    if ms < 60000:
        return "%.1fs" % (ms / 1000)
    return "%dm%02ds" % (ms // 60000, ms // 1000 % 60)


class AgentVizApp:
    def __init__(self, monitor=None):
        badge.mode(HIRES | VSYNC)
        screen.font = font.nope
        screen.antialias = image.OFF
        self.monitor = Monitor() if monitor is None else monitor
        self.colors = [color.rgb(*rgb) for rgb in PALETTE]
        self.bg = color.rgb(0, 0, 0)
        self.panel = color.rgb(15, 15, 22)
        self.white = color.rgb(240, 240, 242)
        self.muted = color.rgb(161, 161, 172)
        self.red = color.rgb(244, 63, 94)
        self.accent = color.rgb(100, 117, 232)
        self.demo = self.stats = self.playing = False
        self.follow = True
        self.elapsed = self.play_ms = 0
        self.selected = None
        self.epoch = None
        self.packet = None
        self.trimmed = False

    def text(self, text, x, y, pen=None):
        screen.pen = self.white if pen is None else pen
        screen.text(text, x, y)

    def box(self, x, y, width, height, pen):
        screen.pen = pen
        screen.shape(shape.rectangle(int(x), int(y), max(1, int(width)), max(1, int(height))))

    def fit(self, text, width):
        while text and screen.measure_text(text)[0] > width:
            text = text[:-1]
        return text

    def select_packet(self, packet):
        self.packet = packet
        if packet is None or not packet["events"]:
            return
        events = packet["events"]
        if packet["epoch"] != self.epoch:
            self.epoch = packet["epoch"]
            self.follow = True
            self.playing = False
        if self.follow:
            self.selected = events[-1][0]
            self.trimmed = False
        elif not any(e[0] == self.selected for e in events):
            self.selected = events[0][0]
            self.trimmed = True

    def step_event(self, direction):
        events = self.packet["events"] if self.packet else []
        if not events:
            return
        index = next((i for i, e in enumerate(events) if e[0] == self.selected), 0)
        index = max(0, min(len(events) - 1, index + direction))
        self.selected = events[index][0]
        self.follow = self.playing = False
        self.play_ms = 0

    def draw_tracks(self, events, selected):
        width = screen.width
        left, right = 61, width - 10
        start = min(e[1] for e in events)
        end = max(e[1] + max(1, e[2]) for e in events)
        span = max(1000, end - start)
        self.text(duration(start), left, 67, self.muted)
        end_text = duration(end)
        self.text(end_text, right - screen.measure_text(end_text)[0], 67, self.muted)
        for track, name in enumerate(TRACK_NAMES):
            y = 86 + track * 19
            self.text(name, 6, y + 3, self.colors[track])
            self.box(left, y, right - left, 17, self.panel)
        # Small offsets expose overlapping events within a semantic track.
        for event in events:
            index, t, ms, track, _, _, error, _ = event
            x = left + (t - start) * (right - left - 2) / span
            bar = min(right - x, max(3, ms * (right - left - 2) / span))
            y = 86 + track * 19 + (index % 3) * 3
            self.box(x, y + 2, bar, 7, self.red if error else self.colors[track])
        x = left + (selected[1] - start) * (right - left - 2) / span
        self.box(x, 85, 1, 96, self.white)
        self.text("#%d %s" % (selected[0] + 1, selected[4]), 7, 186,
                  self.red if selected[6] else self.white)
        detail = "%s / ~%s%s" % (selected[5], duration(selected[2]),
                                " / ERROR" if selected[6] else "")
        self.text(self.fit(detail, width - 14), 7, 201, self.muted)

    def draw_stats(self, packet):
        metrics = packet["metrics"]
        labels = ("Events", "Turns", "Tool calls", "Errors")
        for i, name in enumerate(labels):
            y = 70 + i * 19
            self.text(name, 9, y, self.muted)
            self.text(str(metrics[i]), screen.width // 2, y,
                      self.red if i == 3 and metrics[i] else self.white)
        usage = "Tokens in/out: %s / %s" % tuple(
            "?" if n == -1 else str(n) for n in metrics[5:])
        self.text(self.fit(usage, screen.width - 18), 9, 150, self.muted)
        self.text("Session span: " + duration(metrics[4]), 9, 168, self.muted)
        for i, (name, count) in enumerate(packet["tools"][:2]):
            self.text("%s  %d calls" % (name, count), 9, 187 + 15 * i,
                      self.colors[1])

    def draw(self, live):
        width, height = screen.width, screen.height
        screen.pen = self.bg
        screen.clear()
        self.text("AGENTVIZ", 7, 6)
        status = ("DEMO" if self.demo else "OFFLINE" if not live else
                  "SOURCE ERROR" if self.packet and self.packet["state"] == "error" else
                  "WAITING" if self.packet and self.packet["state"] == "waiting" else
                  "LIVE FEED" if self.follow else "REPLAY" if self.playing else "REVIEW")
        self.text(status, width - screen.measure_text(status)[0] - 7, 6,
                  self.red if status in ("OFFLINE", "SOURCE ERROR") else self.accent)
        self.box(6, 24, width - 12, 1, self.accent)
        packet = self.packet
        if not packet or not packet["events"]:
            self.text("Session tracks, in your pocket.", 8, 47, self.muted)
            message = "Synthetic demo" if self.demo else self.monitor.message
            self.text(self.fit(message, width - 16), 8, 86)
            if self.monitor.address and not self.demo:
                self.text(self.monitor.address + " UDP", 8, 110, self.muted)
            self.text("Run the local AgentViz bridge.", 8, 146, self.muted)
            self.text("Up: retry   Menu: demo", 8, 170, self.muted)
        else:
            source = "SYNTHETIC - not a real session" if self.demo else packet["source"]
            self.text("Older events left the window" if self.trimmed else source,
                      7, 29, self.red if self.trimmed else self.muted)
            m = packet["metrics"]
            summary = "%d events   %d tools   %d errors" % (m[0], m[2], m[3])
            self.text(self.fit(summary, width - 14), 7, 48)
            if self.stats:
                self.draw_stats(packet)
            else:
                selected = next((e for e in packet["events"] if e[0] == self.selected),
                                packet["events"][-1])
                self.draw_tracks(packet["events"], selected)
        self.text("< > step  Select play  Up follow", 6, height - 24, self.muted)
        self.text("Down view  Menu demo  Back exit", 6, height - 11, self.muted)

    def update(self):
        now = badge.ticks
        delta = max(0, badge.ticks_delta)
        self.elapsed += delta
        if badge.pressed(BUTTON_BACK):
            return False
        self.monitor.step(now)
        if badge.pressed(BUTTON_MENU):
            self.demo = not self.demo
            self.elapsed = 0
            self.epoch = None
        packet = (demo_packet(self.elapsed) if self.demo else
                  self.monitor.feed.packet if self.monitor.feed else None)
        self.select_packet(packet)
        if badge.pressed(BUTTON_UP):
            self.follow, self.playing, self.trimmed = True, False, False
            if not self.demo and (self.monitor.error or self.monitor.feed is None
                                  or not self.monitor.live(now)):
                self.monitor.reload()
            self.select_packet(packet)
        if badge.pressed(BUTTON_DOWN):
            self.stats = not self.stats
        if badge.pressed(BUTTON_LEFT):
            self.step_event(-1)
        if badge.pressed(BUTTON_RIGHT):
            self.step_event(1)
        if badge.pressed(BUTTON_SELECT) and packet and packet["events"]:
            self.follow = False
            self.playing = not self.playing
            self.play_ms = 0
            if self.playing and self.selected == packet["events"][-1][0]:
                self.selected = packet["events"][0][0]
        if self.playing and packet and packet["events"]:
            events = packet["events"]
            index = next((i for i, e in enumerate(events) if e[0] == self.selected), 0)
            self.play_ms += delta
            while index < len(events) - 1:
                gap = max(150, min(2000, events[index + 1][1] - events[index][1]))
                if self.play_ms < gap:
                    break
                self.play_ms -= gap
                index += 1
            self.selected = events[index][0]
            if index == len(events) - 1:
                self.playing = False
        self.draw(self.monitor.live(now))


app = AgentVizApp()
try:
    run(app.update)
finally:
    app.monitor.close()
