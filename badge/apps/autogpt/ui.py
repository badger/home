"""AutoGPT status app UI: agent runs and AutoPilot (Otto and Expert) chats.

Controls:
* Left / Right = switch between Runs and AutoPilot
* Up / Down = choose a row (in details: previous / next)
* Select = open or close details, or retry after an error
* Back = close details
* Menu = case lights on or off
"""

import time

import missing_details
from badgeware import State

import model
import net

try:
    import secrets
except ImportError:
    secrets = None

DEFAULT_URL = "https://backend.agpt.co/api/v2"
TABS = ("runs", "autopilot")
TAB_NAMES = {"runs": "Runs", "autopilot": "AutoPilot"}
ROWS = 4
ROW_H = 30
LIST_TOP = 102
MARGIN = 10
STALE_MS = 90000

mona = missing_details.mona_sans()

BG = color.rgb(13, 17, 23)
PANEL = color.rgb(22, 27, 34)
PANEL_HI = color.rgb(33, 40, 50)
TEXT = color.rgb(230, 237, 243)
MUTED = color.rgb(139, 148, 158)
DIM = color.rgb(72, 79, 88)
BLUE = color.rgb(88, 166, 255)
PURPLE = color.rgb(163, 113, 247)
AMBER = color.rgb(240, 180, 41)
RED = color.rgb(248, 81, 73)
GREEN = color.rgb(63, 185, 80)
GREY = color.rgb(110, 118, 129)
RUN_COLORS = {"RUNNING": BLUE, "QUEUED": PURPLE, "REVIEW": AMBER, "FAILED": RED,
              "COMPLETED": GREEN, "TERMINATED": GREY, "INCOMPLETE": GREY}
CHAT_COLORS = {"needs_user": AMBER, "working": BLUE, "queued": PURPLE, "idle": GREY}
CHAT_LABELS = {"needs_user": "needs you", "working": "working", "queued": "queued", "idle": "idle"}
RUN_CHIPS = (("RUNNING", "RUNNING", BLUE), ("QUEUED", "QUEUED", PURPLE),
             ("REVIEW", "REVIEW", AMBER), ("FAILED", "FAILED 24H", RED))
CHAT_CHIPS = (("working", "WORKING", BLUE), ("queued", "QUEUED", PURPLE),
              ("needs_user", "NEEDS YOU", AMBER), ("total", "CHATS", TEXT))


def setting(name):
    return str(getattr(secrets, name, "") or "").strip()


def width_of(text, size):
    return screen.measure_text(text, font_size=size)[0]


def fit(text, size, room):
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


def ago(epoch, then):
    if not epoch or then is None:
        return ""
    text = model.age_text(epoch - then)
    return text if text == "now" else text + " ago"


class App:
    def __init__(self):
        self.prefs = {"lights": True, "names": {}}
        State.load("autogpt", self.prefs)
        if not isinstance(self.prefs.get("lights"), bool):
            self.prefs["lights"] = True
        if not isinstance(self.prefs.get("names"), dict):
            self.prefs["names"] = {}
        self.wifi = net.WiFi()
        self.tab = "runs"
        self.rows = {"runs": [], "autopilot": []}
        self.selected = {"runs": 0, "autopilot": 0}
        self.selected_id = {"runs": None, "autopilot": None}
        self.detail = False
        self.toast = None
        self.toast_until = 0
        self.lights = 0
        self.flash_until = None
        self.saved_at = 0
        self.configure()

    def configure(self):
        self.client = None
        self.problem = None
        self.pending = None
        self.dash = model.Dashboard(self.prefs["names"])
        self.base_url = setting("AUTOGPT_API_URL") or DEFAULT_URL
        self.env = model.environment(self.base_url)
        epoch = time.time()
        if epoch > 1700000000:
            self.dash.set_clock(int(epoch), time.ticks_ms())
        self.missing = net.wifi_missing()
        if not setting("AUTOGPT_API_KEY"):
            self.missing.append("AUTOGPT_API_KEY")
        if self.missing:
            return
        try:
            self.client = net.Client(
                self.base_url,
                {"X-API-Key": setting("AUTOGPT_API_KEY"), "Accept": "application/json"},
                # Run inputs can be large; the badge's heap (in PSRAM) has room.
                timeout=20, max_bytes=128 * 1024)
        except ValueError as error:
            self.problem = "AUTOGPT_API_URL: %s" % error

    # ---- state -------------------------------------------------------------------

    def refresh_runs(self, now):
        dash = self.dash
        epoch = dash.now(now)
        rows = []
        for run in dash.runs:
            when = "queued" if run["started"] is None and run["status"] == "QUEUED" else ago(epoch, run["started"])
            details = [part for part in (when, model.duration_text(run["duration"]), model.money(run["cost"])) if part]
            rows.append({
                "id": run["id"], "item": run,
                "name": fit(dash.name_of(run), 13, 200),
                "sub": fit("  ".join(details), 10, 220),
                "label": run["status"], "tone": RUN_COLORS.get(run["status"], MUTED),
            })
        self.set_rows("runs", rows)

    def refresh_chats(self, now):
        epoch = self.dash.now(now)
        rows = []
        for chat in self.dash.sessions:
            details = [part for part in (chat["persona"], chat["source"], ago(epoch, chat["updated"])) if part]
            rows.append({
                "id": chat["id"], "item": chat,
                "name": fit(chat["title"], 13, 200),
                "sub": fit("  ".join(details), 10, 220),
                "label": CHAT_LABELS[chat["state"]], "tone": CHAT_COLORS[chat["state"]],
            })
        self.set_rows("autopilot", rows)

    def set_rows(self, tab, rows):
        self.rows[tab] = rows
        index = 0
        for position, row in enumerate(rows):
            if row["id"] == self.selected_id[tab]:
                index = position
        self.selected[tab] = index
        self.selected_id[tab] = rows[index]["id"] if rows else None
        if tab == self.tab and not rows:
            self.detail = False

    def network(self, now):
        if not self.client or not self.wifi.ready():
            return
        if self.pending is None:
            request = self.dash.next_request(now)
            if request:
                self.pending = request[0]
                self.client.start(request[1])
            return
        result = self.client.poll()
        if result is None:
            return
        key, self.pending = self.pending, None
        status, payload = result
        if self.client.date:
            self.dash.set_clock(model.http_date_to_epoch(self.client.date), now)
        self.dash.handle(key, status, payload, now)
        if self.dash.alert:
            self.dash.alert = False
            self.flash_until = time.ticks_add(now, 3000)
        if key == "recent" or key.startswith("name:"):
            self.refresh_runs(now)
        elif key == "autopilot":
            self.refresh_chats(now)
            if self.dash.autopilot is False and self.tab == "autopilot":
                self.tab, self.detail = "runs", False
        if self.dash.names_changed and time.ticks_diff(now, self.saved_at) > 10000:
            self.dash.names_changed = False
            self.saved_at = now
            self.prefs["names"] = self.dash.names
            State.save("autogpt", self.prefs)

    def say(self, message, now):
        self.toast = message
        self.toast_until = time.ticks_add(now, 1600)

    def buttons(self, now):
        rows = self.rows[self.tab]
        if badge.pressed(BUTTON_MENU):
            self.prefs["lights"] = not self.prefs["lights"]
            State.save("autogpt", self.prefs)
            self.say("Case lights " + ("on" if self.prefs["lights"] else "off"), now)
        if badge.pressed(BUTTON_SELECT):
            if self.dash.fatal or not self.dash.loaded:
                self.dash.refresh()
            elif rows:
                self.detail = not self.detail
        if badge.pressed(BUTTON_BACK):
            self.detail = False
        step = (1 if badge.pressed(BUTTON_DOWN) else 0) - (1 if badge.pressed(BUTTON_UP) else 0)
        if step and rows:
            index = (self.selected[self.tab] + step) % len(rows)
            self.selected[self.tab] = index
            self.selected_id[self.tab] = rows[index]["id"]
        if badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_RIGHT):
            if self.dash.autopilot is False:
                self.say("AutoPilot isn't available on %s yet" % self.env, now)
            else:
                self.tab = TABS[(TABS.index(self.tab) + 1) % len(TABS)]
                self.detail = False

    def case_lights(self, now):
        level = 0
        if self.prefs["lights"] and self.dash.loaded:
            chats = self.dash.chats if self.dash.autopilot else None
            level = model.lights_level(self.dash.counts, self.flash_until, now, chats)
        level = round(level, 2)
        if level != self.lights:
            self.lights = level
            badge.caselights(level)

    # ---- drawing -------------------------------------------------------------------

    def header(self, now):
        draw_text("AutoGPT", MARGIN, 5, 20, TEXT)
        if self.dash.loaded:
            draw_text(TAB_NAMES[self.tab], MARGIN + width_of("AutoGPT", 20) + 8, 13, 11, MUTED)
        dash = self.dash
        if dash.updated_at is None:
            return
        since = time.ticks_diff(now, dash.updated_at)
        problem = dash.error or since > STALE_MS
        label = "%s  %s" % (self.env, "stale" if since > STALE_MS else model.age_text(since // 1000))
        if dash.error:
            label = "%s  %s" % (self.env, dash.error)
        label = fit(label, 11, 130)
        draw_right(label, screen.width - MARGIN, 11, 11, MUTED)
        screen.pen = RED if problem else GREEN
        screen.shape(shape.circle(screen.width - MARGIN - width_of(label, 11) - 9, 17, 4))

    def chips(self):
        gap = 6
        if self.tab == "runs":
            chips, values = RUN_CHIPS, self.dash.counts
        else:
            chips, values = CHAT_CHIPS, self.dash.chats
        chip_w = (screen.width - 2 * MARGIN - gap * (len(chips) - 1)) // len(chips)
        for index, (key, label, tone) in enumerate(chips):
            x = MARGIN + index * (chip_w + gap)
            value = values.get(key)
            panel(x, 34, chip_w, 42, PANEL)
            pen = tone if value else DIM
            draw_centre("-" if value is None else str(value), x + chip_w / 2, 37, 22, pen)
            draw_centre(label, x + chip_w / 2, 62, 9, pen if value else MUTED)

    def info_line(self, now):
        dash = self.dash
        if self.tab == "autopilot":
            draw_text("Otto and Expert chats, most recent first", MARGIN, 82, 10, MUTED)
            return
        if dash.balance is not None:
            draw_text("Credits", MARGIN, 82, 10, MUTED)
            draw_text(model.money(dash.balance), MARGIN + 44, 81, 12, TEXT)
        if dash.next_schedule:
            name, when = dash.next_schedule
            epoch = dash.now(now)
            soon = model.until_text(when - epoch) if epoch else ""
            draw_right(fit("Next: %s %s" % (name, soon), 10, 170), screen.width - MARGIN, 83, 10, MUTED)

    def row_list(self):
        rows = self.rows[self.tab]
        if not rows:
            draw_centre("No runs yet" if self.tab == "runs" else "No AutoPilot chats yet",
                        screen.width / 2, 140, 16, MUTED)
            return
        selected = self.selected[self.tab]
        first = max(0, min(selected - ROWS // 2, len(rows) - ROWS))
        for slot, row in enumerate(rows[first:first + ROWS]):
            y = LIST_TOP + slot * ROW_H
            if first + slot == selected:
                panel(MARGIN - 4, y, screen.width - 2 * MARGIN + 8, ROW_H - 2, PANEL_HI, 5)
            screen.pen = row["tone"]
            screen.shape(shape.rounded_rectangle(MARGIN, y + 4, 4, ROW_H - 10, 2))
            draw_text(row["name"], MARGIN + 10, y + 3, 13, TEXT)
            draw_text(row["sub"], MARGIN + 10, y + 17, 10, MUTED)
            draw_right(row["label"], screen.width - MARGIN, y + 4, 10, row["tone"])
        if len(rows) > ROWS:
            track = ROWS * ROW_H
            knob = max(12, track * ROWS // len(rows))
            top = LIST_TOP + (track - knob) * first // (len(rows) - ROWS)
            screen.pen = DIM
            screen.rectangle(screen.width - 3, top, 2, knob)

    def footer(self, text):
        draw_centre(text, screen.width / 2, 227, 9, DIM)

    def detail_card(self, now):
        rows = self.rows[self.tab]
        row = rows[self.selected[self.tab]]
        item = row["item"]
        epoch = self.dash.now(now)
        panel(MARGIN - 4, 32, screen.width - 2 * MARGIN + 8, 188, PANEL)
        screen.pen = row["tone"]
        screen.shape(shape.rounded_rectangle(MARGIN - 4, 32, 6, 188, 3))
        draw_text(row["label"], MARGIN + 8, 38, 11, row["tone"])
        if self.tab == "runs":
            title = self.dash.name_of(item)
            started = "queued" if item["started"] is None else (ago(epoch, item["started"]) or "-")
            facts = (
                ("Started", started),
                ("Duration", model.duration_text(item["duration"]) or "-"),
                ("Cost", model.money(item["cost"]) or "-"),
                ("Steps", "-" if item["nodes"] is None else str(item["nodes"])),
                ("Version", "-" if item["version"] is None else "v%d" % item["version"]),
                ("Run", item["id"][:8]),
            )
        else:
            title = item["title"]
            facts = (
                ("With", item["persona"]),
                ("Status", item["status"] or "-"),
                ("Updated", ago(epoch, item["updated"]) or "-"),
                ("From", item["source"] or "AutoGPT"),
                ("Pinned", "yes" if item["pinned"] else "no"),
                ("Chat", item["id"][:8]),
            )
        screen.pen = TEXT
        screen.text(title, rect(MARGIN + 8, 54, screen.width - 2 * MARGIN - 12, 40), 15,
                    align=(LEFT, TOP), overflow=ELLIPSES)
        y = 98
        for name, value in facts:
            draw_text(name, MARGIN + 8, y, 10, MUTED)
            draw_text(fit(value, 11, 210), MARGIN + 76, y - 1, 11, TEXT)
            y += 17
        self.footer("%d of %d   UP/DOWN next   BACK close" % (self.selected[self.tab] + 1, len(rows)))

    def page(self, title, lines, now, spinning=False):
        draw_centre(title, screen.width / 2, 82, 18, TEXT)
        y = 112
        for line in lines:
            if width_of(line, 11) <= screen.width - 30:
                draw_centre(line, screen.width / 2, y, 11, MUTED)
                y += 17
            else:
                # Long messages, such as the saved networks Wi-Fi couldn't find, get two lines.
                screen.pen = MUTED
                screen.text(line, rect(15, y, screen.width - 30, 34), 11, align=(CENTER, TOP), overflow=ELLIPSES)
                y += 34
        if spinning:
            turned = now / 1200 * 360
            screen.pen = DIM
            screen.shape(shape.arc(screen.width / 2, 196, 11, 14, 0, 360))
            screen.pen = BLUE
            screen.shape(shape.arc(screen.width / 2, 196, 11, 14, turned, turned + 90))

    def draw(self, now):
        screen.pen = BG
        screen.clear()
        screen.font = mona
        if self.missing:
            draw_text("AutoGPT", MARGIN, 5, 20, TEXT)
            missing_details.show(self.missing)
            return
        if self.problem:
            self.page("Check secrets.py", [self.problem], now)
            return
        dash = self.dash
        self.header(now)
        if not dash.loaded:
            if not self.wifi.ready():
                self.page("Connecting to Wi-Fi", [self.wifi.status()], now, True)
            elif dash.fatal:
                self.page("AutoGPT said no", [dash.fatal, "Press SELECT to retry"], now)
            elif dash.error:
                self.page("Can't reach AutoGPT", [dash.error, "Retrying, SELECT retries now"], now, True)
            else:
                self.page("Asking AutoGPT (%s)" % self.env, [self.base_url], now, True)
            return
        if self.detail and self.rows[self.tab]:
            self.detail_card(now)
        else:
            self.chips()
            self.info_line(now)
            self.row_list()
            if dash.fatal:
                self.footer(fit(dash.fatal + "  SELECT retry", 9, 300))
            else:
                other = TAB_NAMES[TABS[(TABS.index(self.tab) + 1) % len(TABS)]]
                lights = "on" if self.prefs["lights"] else "off"
                self.footer("L/R %s   SELECT details   MENU lights %s" % (other, lights))
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
