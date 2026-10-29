"""Persistent agenda and cooperative overlays for every runtime run() loop."""

import builtins
import json
import time
import utc_clock

KEY = "universe_agenda"
IMPORT_PATH = "/system/apps/universe_agenda/agenda.json"
LEADS = (5, 10, 15, 30)
MAX_EVENTS = 128
installed = False
service = None
_background = None
_covered = None


def text(value, name, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError("Invalid " + name)
    return value.replace("\n", " ").replace("\r", " ").strip()


def validate_events(events):
    if not isinstance(events, list) or len(events) > MAX_EVENTS:
        raise ValueError("Agenda must contain at most 128 sessions")
    result = []
    ids = set()
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("Invalid session")
        location = event.get("location", "See Universe portal")
        if location == "":
            location = "See Universe portal"
        entry = {
            "id": text(event.get("id"), "session ID", 128),
            "title": text(event.get("title"), "session title", 160),
            "start": event.get("start"),
            "end": event.get("end"),
            "location": text(location, "location", 120),
        }
        start = utc_clock.parse_utc(entry["start"])
        end = utc_clock.parse_utc(entry["end"])
        if end <= start or entry["id"] in ids:
            raise ValueError("Duplicate session or invalid session duration")
        ids.add(entry["id"])
        result.append(entry)
    return sorted(result, key=lambda event: event["start"])


class Agenda:
    def __init__(self):
        self.state = {
            "source": "", "events": [], "seen": [],
            "lead_minutes": 10, "enabled": True,
        }
        self.events = []
        self.error = ""
        self.current = None
        self.remaining = 0
        self.last_check = None
        self.clock_ready = False
        try:
            loaded = utc_clock.load_state(KEY, dict(self.state))
            events = validate_events(loaded["events"])
            if (type(loaded["lead_minutes"]) is not int
                    or loaded["lead_minutes"] not in LEADS
                    or type(loaded["enabled"]) is not bool
                    or not isinstance(loaded["seen"], list)
                    or len(loaded["seen"]) > MAX_EVENTS
                    or any(not isinstance(key, str) for key in loaded["seen"])
                    or not isinstance(loaded["source"], str)):
                raise ValueError("Invalid reminder settings")
            self.state = loaded
            self.events = events
            self.clock_ready = utc_clock.ready()
        except (OSError, ValueError, TypeError) as error:
            self.fail(error)

    def fail(self, error):
        self.error = str(error)
        print("Universe agenda: " + self.error)

    def save(self, changes):
        updated = dict(self.state)
        updated.update(changes)
        utc_clock.save_state(KEY, updated)
        self.state = updated

    def import_agenda(self, path=IMPORT_PATH):
        with open(path) as handle:
            raw = handle.read(65537)
        if len(raw) > 65536:
            raise ValueError("Agenda file exceeds 64 KiB")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Invalid agenda file")
        source = text(data.get("source"), "agenda source", 160)
        events = validate_events(data.get("events"))
        active = {event["id"] + "|" + event["start"] for event in events}
        seen = [key for key in self.state["seen"] if key in active]
        self.save({"source": source, "events": events, "seen": seen})
        self.events = events
        self.current = None
        self.error = ""

    def tick(self, elapsed_ms):
        if self.error:
            return
        if not self.state["enabled"]:
            self.current = None
            self.remaining = 0
        self.remaining = max(0, self.remaining - max(0, elapsed_ms))
        if not self.remaining:
            self.current = None
        now = time.time()
        if self.last_check == now:
            return
        self.last_check = now
        try:
            self.clock_ready = utc_clock.ready()
        except (OSError, ValueError) as error:
            self.fail(error)
            return
        if not self.clock_ready or not self.state["enabled"] or self.current:
            return
        lead = self.state["lead_minutes"] * 60
        seen = self.state["seen"]
        for event in self.events:
            start = utc_clock.parse_utc(event["start"])
            key = event["id"] + "|" + event["start"]
            if start - lead <= now < start and key not in seen:
                try:
                    self.save({"seen": seen + [key]})
                except (OSError, ValueError) as error:
                    self.fail(error)
                    return
                self.current = event
                self.remaining = 12000
                return


def fit(surface, value, width):
    if surface.measure_text(value)[0] <= width:
        return value
    while value and surface.measure_text(value + "...")[0] > width:
        value = value[:-1]
    return value + "..."


def draw_mona(surface, x, y):
    surface.pen = color.rgb(190, 133, 255)
    surface.shape(shape.circle(x, y, 10))
    surface.shape(shape.rectangle(x - 9, y - 11, 6, 8))
    surface.shape(shape.rectangle(x + 3, y - 11, 6, 8))
    surface.pen = color.rgb(255, 236, 220)
    surface.shape(shape.circle(x, y + 2, 7))
    surface.pen = color.rgb(13, 17, 23)
    surface.shape(shape.circle(x - 3, y + 1, 1.5))
    surface.shape(shape.circle(x + 3, y + 1, 1.5))
    surface.line(x - 2, y + 5, x + 2, y + 5)


def overlay():
    global _background, _covered
    service.tick(badge.ticks_delta)
    if not service.current:
        return
    event = service.current
    x, y, width, height = 3, screen.height - 42, screen.width - 6, 39
    if _background is None or (_background.width, _background.height) != (width, height):
        _background = image(width, height)
    _background.blit(screen, rect(x, y, width, height), rect(0, 0, width, height))
    _covered = (screen.width, screen.height, x, y, width, height)
    window = screen.window(x, y, width, height)
    window.pen = color.rgb(35, 18, 59)
    window.rectangle(window.clip)
    draw_mona(window, 14, 18)
    window.font = font.ark
    window.pen = color.rgb(211, 250, 55)
    seconds_left = utc_clock.parse_utc(event["start"]) - time.time()
    minutes = max(1, int((seconds_left + 59) // 60))
    window.text("Starting now" if seconds_left <= 0 else "Universe in %dm" % minutes, 29, 2)
    window.pen = color.rgb(255, 255, 255)
    window.text(fit(window, event["title"], window.width - 32), 29, 14)
    window.text(fit(window, event["location"], window.width - 32), 29, 26)


def restore_overlay():
    global _covered
    if _covered is None:
        return
    sw, sh, x, y, width, height = _covered
    if (screen.width, screen.height) == (sw, sh):
        screen.window(x, y, width, height).blit(_background, vec2(0, 0))
    _covered = None


def install():
    global installed, service
    if installed:
        return
    service = Agenda()
    original_run = run

    class AgendaRun(original_run):
        def __call__(self, update):
            def with_reminder():
                # Incremental renderers must not retain the last banner's pixels.
                restore_overlay()
                result = update()
                if result is None:
                    overlay()
                return result
            return super().__call__(with_reminder)

    builtins.run = AgendaRun
    installed = True
