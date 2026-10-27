"""T3 Code: live status of your coding agent threads, via the badge bridge.

The bridge (tools/badge_bridge in this repository) follows your T3 Code
servers over Tailscale and publishes a small read-only summary through
Tailscale Funnel, so the badge only needs Wi-Fi and plain HTTPS.

Controls:
* Up / Down = choose a thread (in details: previous / next)
* Select = open or close the thread's details
* Back = close details
* Left / Right = show all hosts, or one T3 Code host at a time
* Menu = case lights on or off
"""

import os
import sys

APP_DIR = "/system/apps/t3code"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

import time

import missing_details
from badgeware import State

import model
import net

try:
    import secrets
except ImportError:
    secrets = None

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

POLL_MS = 5000
STALE_MS = 30000
ROWS = 5
ROW_H = 28
LIST_TOP = 84
MARGIN = 10

mona = missing_details.mona_sans()

BG = color.rgb(13, 17, 23)
PANEL = color.rgb(22, 27, 34)
PANEL_HI = color.rgb(33, 40, 50)
TEXT = color.rgb(230, 237, 243)
MUTED = color.rgb(139, 148, 158)
DIM = color.rgb(72, 79, 88)
STATE_COLORS = {
    "attention": color.rgb(240, 180, 41),
    "working": color.rgb(88, 166, 255),
    "error": color.rgb(248, 81, 73),
    "done": color.rgb(63, 185, 80),
    "idle": color.rgb(110, 118, 129),
}
CHIPS = ("attention", "working", "done", "error")


def setting(name):
    return str(getattr(secrets, name, "") or "").strip()


def width_of(text, size):
    return screen.measure_text(text, font_size=size)[0]


def fit(text, size, room):
    """Trim text with an ellipsis until it fits in room pixels."""
    if width_of(text, size) <= room:
        return text
    while text and width_of(text + "...", size) > room:
        text = text[:-1]
    return text.rstrip() + "..."


def draw_text(text, x, y, size, pen):
    screen.pen = pen
    screen.text(text, x, y, size)


def draw_right(text, right, y, size, pen):
    draw_text(text, right - width_of(text, size), y, size, pen)


def draw_centre(text, centre, y, size, pen):
    draw_text(text, centre - width_of(text, size) / 2, y, size, pen)


def panel(x, y, w, h, pen, radius=6):
    screen.pen = pen
    screen.shape(shape.rounded_rectangle(x, y, w, h, radius))


class App:
    def __init__(self):
        self.prefs = {"lights": True}
        State.load("t3code", self.prefs)
        if not isinstance(self.prefs.get("lights"), bool):
            self.prefs["lights"] = True
        self.wifi = net.WiFi()
        self.status = None
        self.rows = []
        self.selected = 0
        self.selected_id = None
        self.detail = False
        self.host = None  # None shows every T3 Code host
        self.toast = None
        self.toast_until = 0
        self.lights = 0
        self.configure()

    def configure(self):
        self.poller = None
        self.problem = None
        self.missing = list(missing_details.missing("WIFI_SSID"))
        self.missing += [name for name in ("BADGE_BRIDGE_URL", "BADGE_BRIDGE_TOKEN") if not setting(name)]
        if self.missing:
            return
        try:
            client = net.Client(
                setting("BADGE_BRIDGE_URL"),
                {"Authorization": "Bearer " + setting("BADGE_BRIDGE_TOKEN"), "Accept": "application/json"},
                timeout=15, max_bytes=16 * 1024)
        except ValueError as error:
            self.problem = "BADGE_BRIDGE_URL: %s" % error
            return
        self.poller = net.Poller(client, model.status_path(self.host), POLL_MS)

    # ---- state -------------------------------------------------------------------

    def refresh_rows(self):
        """Pre-fit row text once per update instead of measuring every frame."""
        self.rows = []
        for thread in self.status["threads"]:
            detail = thread["detail"] or model.LABELS[thread["state"]].lower()
            sub = " / ".join(part for part in (thread["src"], thread["project"]) if part)
            self.rows.append({
                "thread": thread,
                "title": fit(thread["title"], 13, 196),
                "detail": fit(detail, 10, 92),
                "sub": fit(sub, 10, 220),
                "age": model.age_text(thread["age"]),
            })
        threads = self.status["threads"]
        self.selected = model.keep_selection(threads, self.selected_id, self.selected)
        self.selected_id = threads[self.selected]["id"] if threads else None
        if not threads:
            self.detail = False

    def network(self, now):
        if not self.poller or not self.wifi.ready():
            return
        if self.poller.step(now):
            try:
                status = model.parse_status(self.poller.data)
            except ValueError as error:
                self.poller.error = str(error)
                return
            if status["src"] != self.host:
                return  # an answer for the previous host filter
            self.status = status
            self.refresh_rows()

    def say(self, message, now):
        self.toast = message
        self.toast_until = time.ticks_add(now, 1600)

    def buttons(self, now):
        count = len(self.rows)
        if badge.pressed(BUTTON_MENU):
            self.prefs["lights"] = not self.prefs["lights"]
            State.save("t3code", self.prefs)
            self.say("Case lights " + ("on" if self.prefs["lights"] else "off"), now)
        if badge.pressed(BUTTON_SELECT):
            if self.poller and (self.poller.paused or not self.status):
                self.poller.refresh()
            elif count:
                self.detail = not self.detail
        if badge.pressed(BUTTON_BACK):
            self.detail = False
        step = (1 if badge.pressed(BUTTON_DOWN) else 0) - (1 if badge.pressed(BUTTON_UP) else 0)
        if step and count:
            self.selected = (self.selected + step) % count
            self.selected_id = self.rows[self.selected]["thread"]["id"]
        turn = (1 if badge.pressed(BUTTON_RIGHT) else 0) - (1 if badge.pressed(BUTTON_LEFT) else 0)
        if turn and not self.detail and self.status and self.poller:
            self.host = model.next_host(self.status, self.host, turn)
            self.poller.client.cancel()
            self.poller.path = model.status_path(self.host)
            self.poller.refresh()
            self.selected, self.selected_id = 0, None
            self.say(self.host or "All hosts", now)

    def case_lights(self, now):
        level = 0
        if self.prefs["lights"] and self.status:
            level = model.lights_level(self.status["counts"], now)
        level = round(level, 2)
        if level != self.lights:
            self.lights = level
            badge.caselights(level)

    # ---- drawing -------------------------------------------------------------------

    def header(self, now):
        draw_text("T3 Code", MARGIN, 5, 20, TEXT)
        if self.status:
            draw_text(fit(self.host or "all hosts", 11, 80), MARGIN + width_of("T3 Code", 20) + 8, 13, 11, MUTED)
        poller = self.poller
        if poller and poller.updated_at is not None and self.status:
            since = time.ticks_diff(now, poller.updated_at)
            stale = since > STALE_MS or poller.error
            dot = STATE_COLORS["error" if stale else "done"]
            if not self.status["ok"]:
                dot = STATE_COLORS["error"]
            label = model.source_line(self.status)
            if stale:
                label = "stale " + model.age_text(since // 1000)
            label = fit(label, 11, 120)
            draw_right(label, screen.width - MARGIN, 11, 11, MUTED)
            screen.pen = dot
            screen.shape(shape.circle(screen.width - MARGIN - width_of(label, 11) - 9, 17, 4))

    def chips(self):
        gap = 6
        chip_w = (screen.width - 2 * MARGIN - gap * (len(CHIPS) - 1)) // len(CHIPS)
        for index, state in enumerate(CHIPS):
            x = MARGIN + index * (chip_w + gap)
            value = self.status["counts"][state]
            panel(x, 34, chip_w, 42, PANEL)
            pen = STATE_COLORS[state] if value else DIM
            draw_centre(str(value), x + chip_w / 2, 37, 22, pen)
            draw_centre(model.LABELS[state], x + chip_w / 2, 62, 9, pen if value else MUTED)

    def thread_list(self):
        if not self.rows:
            draw_centre("All quiet", screen.width / 2, 128, 18, MUTED)
            draw_centre("No T3 Code threads need you right now.", screen.width / 2, 154, 11, DIM)
            return
        first = max(0, min(self.selected - ROWS // 2, len(self.rows) - ROWS))
        for slot, row in enumerate(self.rows[first:first + ROWS]):
            index = first + slot
            y = LIST_TOP + slot * ROW_H
            state = row["thread"]["state"]
            if index == self.selected:
                panel(MARGIN - 4, y, screen.width - 2 * MARGIN + 8, ROW_H - 2, PANEL_HI, 5)
            screen.pen = STATE_COLORS[state]
            screen.shape(shape.rounded_rectangle(MARGIN, y + 4, 4, ROW_H - 10, 2))
            draw_text(row["title"], MARGIN + 10, y + 2, 13, TEXT)
            draw_text(row["sub"], MARGIN + 10, y + 15, 10, MUTED)
            right = screen.width - MARGIN
            draw_right(row["detail"], right, y + 3, 10, STATE_COLORS[state])
            draw_right(row["age"], right, y + 15, 10, MUTED)
        if len(self.rows) > ROWS:
            track = ROWS * ROW_H
            knob = max(12, track * ROWS // len(self.rows))
            top = LIST_TOP + (track - knob) * first // (len(self.rows) - ROWS)
            screen.pen = DIM
            screen.rectangle(screen.width - 3, top, 2, knob)

    def footer(self, text):
        draw_centre(text, screen.width / 2, 227, 9, DIM)

    def detail_card(self):
        row = self.rows[self.selected]
        thread = row["thread"]
        tone = STATE_COLORS[thread["state"]]
        panel(MARGIN - 4, 32, screen.width - 2 * MARGIN + 8, 188, PANEL)
        screen.pen = tone
        screen.shape(shape.rounded_rectangle(MARGIN - 4, 32, 6, 188, 3))
        label = model.LABELS[thread["state"]]
        if thread["detail"]:
            label += "  " + thread["detail"]
        draw_text(fit(label, 11, 250), MARGIN + 8, 38, 11, tone)
        draw_right(model.age_text(thread["age"]), screen.width - MARGIN, 38, 11, MUTED)
        screen.pen = TEXT
        screen.text(thread["title"], rect(MARGIN + 8, 54, screen.width - 2 * MARGIN - 12, 40), 15,
                    align=(LEFT, TOP), overflow=ELLIPSES)
        y = 98
        for name, value in (("Project", thread["project"]), ("Model", thread["model"]), ("Host", thread["src"])):
            if value:
                draw_text(name, MARGIN + 8, y, 10, MUTED)
                draw_text(fit(value, 11, 220), MARGIN + 70, y - 1, 11, TEXT)
                y += 16
        if thread["msg"]:
            screen.pen = MUTED
            screen.text('"' + thread["msg"] + '"', rect(MARGIN + 8, y + 4, screen.width - 2 * MARGIN - 12, 214 - y), 11,
                        align=(LEFT, TOP), overflow=ELLIPSES)
        self.footer("%d of %d   UP/DOWN next   BACK close" % (self.selected + 1, len(self.rows)))

    def page(self, title, lines, now, spinning=False):
        draw_centre(title, screen.width / 2, 82, 18, TEXT)
        y = 112
        for line in lines:
            draw_centre(fit(line, 11, screen.width - 30), screen.width / 2, y, 11, MUTED)
            y += 17
        if spinning:
            turned = now / 1200 * 360
            screen.pen = DIM
            screen.shape(shape.arc(screen.width / 2, 196, 11, 14, 0, 360))
            screen.pen = STATE_COLORS["working"]
            screen.shape(shape.arc(screen.width / 2, 196, 11, 14, turned, turned + 90))

    def draw(self, now):
        screen.pen = BG
        screen.clear()
        screen.font = mona
        if self.missing:
            draw_text("T3 Code", MARGIN, 5, 20, TEXT)
            missing_details.show(self.missing)
            return
        if self.problem:
            self.page("Check secrets.py", [self.problem], now)
            return
        self.header(now)
        poller = self.poller
        if self.status is None:
            if not self.wifi.ready():
                self.page("Connecting to Wi-Fi", [self.wifi.status()], now, True)
            elif poller.paused:
                self.page("Bridge refused the token", [poller.error or "", "Check BADGE_BRIDGE_TOKEN, then press SELECT"], now)
            elif poller.error:
                self.page("Can't reach the bridge", [poller.error, "Retrying automatically, SELECT retries now"], now, True)
            else:
                self.page("Asking the bridge", [setting("BADGE_BRIDGE_URL")], now, True)
            return
        if self.detail and self.rows:
            self.detail_card()
        else:
            self.chips()
            self.thread_list()
            lights = "on" if self.prefs["lights"] else "off"
            if poller.paused:
                self.footer("Token refused   SELECT retry")
            elif poller.error:
                self.footer(fit(poller.error, 9, 300))
            else:
                self.footer("L/R host   SELECT details   MENU lights %s" % lights)
        if self.toast and time.ticks_diff(self.toast_until, now) > 0:
            w = width_of(self.toast, 12) + 24
            panel((screen.width - w) / 2, 196, w, 24, PANEL_HI, 12)
            draw_centre(self.toast, screen.width / 2, 201, 12, TEXT)

    def update(self):
        now = time.ticks_ms()
        self.network(now)
        self.buttons(now)
        self.case_lights(now)
        self.draw(now)


app = App()


def update():
    app.update()


def on_exit():
    badge.caselights(0)


run(update)
