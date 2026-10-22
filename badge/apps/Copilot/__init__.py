"""Copilot Agent Buddy session monitor for October 2026 Badgeware."""

import gc
import random
import time

from copilot_monitor import Monitor


FRAME_MS = 80
FRAME_COUNT = 12
SLEEP_MS = 120000
MODES = ("idle", "working", "attention", "complete")
DEMO = (("surprise", 960), ("working", 6000), ("attention", 5000),
        ("complete", 4000), ("idle", 5000))
LOOKS = ("left", "right", "up", "down")
BLINK = (1, 2, 3, 4, 3, 2, 1)
LABELS = {
    "idle": "Your Agent Buddy",
    "working": "Working",
    "attention": "Needs attention",
    "complete": "Complete!",
    "surprise": "Hello, Universe!",
    "sleep": "Z z z",
}


class CopilotApp:
    def __init__(self, asset_path="/system/apps/Copilot/assets", monitor=None):
        badge.mode(HIRES | VSYNC)
        screen.font = font.nope
        screen.antialias = image.OFF
        self.asset_path = asset_path
        self.background = color.rgb(0, 0, 0)
        self.foreground = color.rgb(240, 246, 252)
        self.muted = color.rgb(139, 148, 158)
        self.accent = color.rgb(128, 170, 255)
        self.role_colors = {"w": color.rgb(88, 166, 255), "a": color.rgb(255, 193, 7),
                            "c": color.rgb(63, 185, 80)}
        self.frame_rect = rect(64, 22, 192, 180)
        self.sprite = None
        self.sprite_name = None
        self.error = None
        self.monitor = Monitor() if monitor is None else monitor
        self.remote_mode = None
        self.was_live = False
        self.icon_cache = {}
        self.demo = False
        self.demo_index = 0
        self.last_input = time.ticks_ms()
        self.set_mode("idle", self.last_input)

    def set_mode(self, mode, now):
        self.mode = mode
        self.mode_since = now
        self.look = None
        self.blink_since = None
        self.next_look = time.ticks_add(now, random.randint(2500, 5000))
        self.next_blink = time.ticks_add(now, random.randint(1800, 3500))

    def start_demo(self, now):
        self.demo = True
        self.demo_index = 0
        self.set_mode(DEMO[0][0], now)

    def handle_buttons(self, now):
        if badge.pressed(BUTTON_BACK):
            return False
        left = badge.pressed(BUTTON_LEFT)
        right = badge.pressed(BUTTON_RIGHT)
        up = badge.pressed(BUTTON_UP)
        down = badge.pressed(BUTTON_DOWN)
        select = badge.pressed(BUTTON_SELECT)
        if not (left or right or up or down or select):
            return True
        self.last_input = now
        if self.error:
            if select:
                self.error = None
                self.sprite_name = None
            return True
        if self.monitor:
            if up:
                if self.monitor.protocol and self.monitor.protocol.pairing(now):
                    self.monitor.protocol.pairing_code = None
                else:
                    self.demo = False
                    self.remote_mode = None
                    self.monitor.open_pairing(now)
            elif down:
                if self.monitor.protocol:
                    self.monitor.protocol.pairing_code = None
                if self.demo:
                    self.demo = False
                    self.remote_mode = None
                    self.set_mode("idle", now)
                else:
                    self.start_demo(now)
            elif select:
                self.monitor.reload()
            elif self.demo and (left or right):
                index = MODES.index(self.mode) if self.mode in MODES else 0
                self.set_mode(MODES[(index + (1 if right else -1)) % len(MODES)], now)
            return True
        if select:
            if self.mode == "sleep":
                self.demo = False
                self.set_mode("idle", now)
            elif self.demo:
                self.demo = False
                self.set_mode("idle", now)
            else:
                self.start_demo(now)
        else:
            self.demo = False
            if up:
                self.set_mode("surprise", now)
            elif down:
                self.set_mode("idle" if self.mode == "sleep" else "sleep", now)
            else:
                index = MODES.index(self.mode) if self.mode in MODES else 0
                self.set_mode(MODES[(index + (1 if right else -1)) % len(MODES)], now)
        return True

    def animate(self, now):
        elapsed = time.ticks_diff(now, self.mode_since)
        if self.demo:
            if elapsed >= DEMO[self.demo_index][1]:
                self.demo_index = (self.demo_index + 1) % len(DEMO)
                self.set_mode(DEMO[self.demo_index][0], now)
        elif self.mode == "surprise" and elapsed >= FRAME_MS * FRAME_COUNT:
            self.set_mode("idle", now)
        elif self.mode == "complete" and elapsed >= 5000 and not self.was_live:
            self.set_mode("idle", now)
        elif self.mode == "idle" and time.ticks_diff(now, self.last_input) >= SLEEP_MS:
            self.set_mode("sleep", now)

        elapsed = max(0, time.ticks_diff(now, self.mode_since))
        if self.mode == "sleep":
            return "blink-4"
        if self.mode != "idle":
            if self.mode == "surprise":
                index = min(FRAME_COUNT - 1, elapsed // FRAME_MS)
            else:
                # Play the turn out and back so looping never snaps to neutral.
                step = (elapsed // FRAME_MS) % (FRAME_COUNT * 2 - 2)
                index = step if step < FRAME_COUNT else FRAME_COUNT * 2 - 2 - step
            return "%s-%02d" % (self.mode, index)

        if self.look is not None:
            step = time.ticks_diff(now, self.look_since) // FRAME_MS
            if step < FRAME_COUNT * 2 - 1:
                index = step if step < FRAME_COUNT else FRAME_COUNT * 2 - 2 - step
                return "%s-%02d" % (self.look, index)
            self.look = None
            self.next_look = time.ticks_add(now, random.randint(2500, 5000))
        if self.blink_since is not None:
            step = time.ticks_diff(now, self.blink_since) // 45
            if step < len(BLINK):
                return "blink-%d" % BLINK[step]
            self.blink_since = None
            self.next_blink = time.ticks_add(now, random.randint(1800, 3500))
        if time.ticks_diff(now, self.next_blink) >= 0:
            self.blink_since = now
            return "blink-1"
        if time.ticks_diff(now, self.next_look) >= 0:
            self.look = LOOKS[random.randint(0, len(LOOKS) - 1)]
            self.look_since = now
            return self.look + "-00"
        return "neutral"

    def load_frame(self, name):
        if name == self.sprite_name:
            return
        # Drop the previous decoded frame before loading another, not afterwards.
        self.sprite = None
        gc.collect()
        try:
            self.sprite = image.load(self.asset_path + "/" + name + ".png")
        except (OSError, ValueError, RuntimeError) as error:
            self.error = "Missing or invalid artwork"
            print("Copilot: cannot load", name, "-", error)
            return
        self.sprite_name = name

    def center_text(self, text, y):
        width, _ = screen.measure_text(text)
        screen.text(text, (320 - width) // 2, y)

    def draw(self):
        screen.pen = self.background
        screen.clear()
        screen.font = font.nope
        screen.pen = self.accent
        self.center_text("GitHub Copilot", 7)
        if self.error:
            screen.pen = self.foreground
            self.center_text(self.error, 88)
            screen.pen = self.muted
            self.center_text("Copy the complete assets folder", 113)
            self.center_text("Select: retry   Back: exit", 154)
            return
        now = time.ticks_ms()
        if self.monitor and self.monitor.protocol and self.monitor.protocol.pairing(now):
            screen.pen = self.foreground
            self.center_text("Pair with Agent Buddy", 63)
            code = self.monitor.protocol.pairing_code
            width, _ = screen.measure_text(code, 2)
            screen.text(code, (320 - width) // 2, 100, 2)
            screen.pen = self.muted
            self.center_text(self.monitor.address, 151)
            self.center_text("Code expires in 60 seconds", 177)
            self.center_text("Up: cancel   Back: exit", 220)
            return
        if self.sprite is not None:
            screen.blit(self.sprite, self.frame_rect)
        screen.pen = self.foreground
        self.center_text(LABELS[self.mode], 194)
        screen.pen = self.muted
        if self.monitor:
            if self.demo:
                self.center_text("DEMO - not session status", 25)
                self.center_text("Down: live   < > Mood", 220)
            else:
                self.center_text(self.monitor.message, 25)
                if self.was_live:
                    self.draw_agents()
                    screen.pen = self.muted
                    for index, line in enumerate(self.monitor.protocol.usage):
                        self.center_text(line, 213 + 14 * index)
                else:
                    if self.monitor.address:
                        self.center_text(self.monitor.address, 213)
                    self.center_text("Up: pair   Down: demo   Select: retry", 227)
        elif self.mode == "sleep":
            self.center_text("Down / Select: wake   Back: exit", 220)
        elif self.demo:
            self.center_text("Offline demo   Select: stop", 220)
        else:
            self.center_text("< > Mood   Up: hi   Down: nap", 213)
            self.center_text("Select: demo   Back: exit", 227)

    def draw_agents(self):
        protocol = self.monitor.protocol
        positions = ((16, 64), (280, 64), (16, 120), (280, 120))
        for (name, role), (x, y) in zip(protocol.agents, positions):
            definition = protocol.icons.get(name)
            if definition:
                cached = self.icon_cache.get(name)
                if cached is None or cached[0] != definition:
                    rgb, mask = definition
                    spans = []
                    for row in range(24):
                        start = None
                        for column in range(25):
                            bit = row * 24 + column
                            filled = column < 24 and mask[bit // 8] & (128 >> (bit % 8))
                            if filled and start is None:
                                start = column
                            elif not filled and start is not None:
                                spans.append((start, row, column - start, 1))
                                start = None
                    cached = (definition, color.rgb(*rgb), spans)
                    self.icon_cache[name] = cached
                screen.pen = cached[1]
                for sx, sy, width, height in cached[2]:
                    screen.rectangle(x + sx, y + sy, width, height)
            screen.pen = self.role_colors[role]
            screen.rectangle(x, y + 26, 24, 3)
            screen.pen = self.muted
            label = name
            while screen.measure_text(label)[0] > 56:
                label = label[:-1]
            width, _ = screen.measure_text(label)
            screen.text(label, x + (24 - width) // 2, y + 32)
        self.icon_cache = {name: self.icon_cache[name] for name, _ in protocol.agents[:4]
                           if name in self.icon_cache}

    def update(self):
        now = time.ticks_ms()
        if self.monitor:
            self.monitor.step(now)
        if not self.handle_buttons(now):
            return False
        if self.monitor:
            live = self.monitor.live(now)
            if not self.demo:
                remote = self.monitor.protocol.state if live else "idle"
                if remote != self.remote_mode or live != self.was_live:
                    self.set_mode(remote, now)
                    self.remote_mode = remote
                    self.last_input = now
            self.was_live = live and not self.demo
        if not self.error:
            self.load_frame(self.animate(now))
        self.draw()

    def close(self):
        if self.monitor:
            self.monitor.close()
        self.sprite = None
        self.icon_cache = {}
        gc.collect()


app = CopilotApp()
try:
    run(app.update)
finally:
    app.close()
