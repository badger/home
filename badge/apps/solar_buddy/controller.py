"""Application state, navigation, freshness, and mode separation."""

from advisor import Advisor
from clock import elapsed
from demo import Demo, SCENARIOS
from energy import Mood

PAGES = ("Buddy", "Energy", "Appliances", "Settings")


class App:
    def __init__(self, settings, live_factory=None, saved=None, save=None):
        self.settings = settings
        self.live_factory = live_factory
        self.save_callback = save
        saved = saved or {}
        self.page = 0
        self.selected = 0
        self.detail = False
        self.demo_index = saved.get("scenario", 0)
        if not isinstance(self.demo_index, int) or not 0 <= self.demo_index < len(SCENARIOS):
            self.demo_index = 0
        self.superstar = saved.get("superstar") is True
        self.demo_superstar = False
        self.mood = Mood(settings)
        self.advisor = Advisor(settings)
        self.sample = None
        self.last_good = None
        self.valid = False
        self.error = ""
        self.status = "OFFLINE"
        self.source = None
        self.mode = "demo"
        self.celebration = None
        self.awake_until_start = None
        self.hardware_note = ""
        self._logged_error = None
        initial_mode = saved.get("mode", settings["mode"])
        if initial_mode not in ("demo", "live"):
            initial_mode = settings["mode"]
        self.set_mode(initial_mode, persist=False)

    def persist(self):
        if self.save_callback:
            self.save_callback({"mode": self.mode, "scenario": self.demo_index,
                                "superstar": self.superstar})

    def invalidate(self, message, status="OFFLINE"):
        self.valid = False
        self.error = message
        self.status = status
        self.advisor.invalidate()
        self.mood.update(None)
        if message != self._logged_error:
            print("Solar Buddy: " + message)
            self._logged_error = message

    def set_mode(self, mode, persist=True):
        if self.source is not None:
            self.source.close()
        self.source = None
        self.mode = mode
        self.sample = None
        self.last_good = None
        self.celebration = None
        self.valid = False
        self.error = ""
        self.advisor.invalidate()
        self.mood.update(None)
        self.status = "DEMO" if mode == "demo" else "OFFLINE"
        if mode == "demo":
            self.source = Demo(self.demo_index)
        else:
            try:
                if self.live_factory is None:
                    raise ValueError("Run the Home Assistant setup script first")
                self.source = self.live_factory()
                self.error = "Connecting to Home Assistant"
            except (OSError, ValueError, ImportError, AttributeError) as exc:
                self.invalidate("Live setup: " + str(exc))
        if persist:
            self.persist()

    def tick(self, now):
        if (self.valid and self.last_good is not None
                and elapsed(now, self.last_good) >= self.settings["stale_after_ms"]):
            self.invalidate("No fresh reading; advice paused", "STALE")
        event = self.source.tick(now) if self.source is not None else None
        if event is None:
            return
        kind, payload = event
        if kind != "reading":
            self.invalidate(payload, "STALE" if kind == "stale" or "stale" in payload.lower()
                            else "OFFLINE")
            return
        self.sample = payload
        self.last_good = now
        self.valid = True
        self.error = ""
        self._logged_error = None
        self.status = "DEMO" if self.mode == "demo" else "LIVE"
        self.mood.update(payload)
        self.advisor.update(payload, now)
        if payload["surplus_w"] > self.settings["milestone_w"]:
            earned = self.demo_superstar if self.mode == "demo" else self.superstar
            if not earned:
                self.celebration = now
                if self.mode == "demo":
                    self.demo_superstar = True
                else:
                    self.superstar = True
                    self.persist()

    def input(self, action, now):
        if action in ("left", "right"):
            self.page = (self.page + (1 if action == "right" else -1)) % len(PAGES)
            self.detail = False
        elif action == "menu":
            self.page = 3
            self.detail = False
        elif action == "back":
            if self.detail:
                self.detail = False
            else:
                self.page = 0
        elif action in ("up", "down"):
            delta = -1 if action == "up" else 1
            if self.page == 2:
                self.selected = (self.selected + delta) % len(self.advisor.items)
                self.detail = False
            elif self.mode == "demo" and self.page in (0, 1):
                self.demo_index = (self.demo_index + delta) % len(SCENARIOS)
                self.set_mode("demo")
        elif action == "select":
            if self.page == 2:
                self.detail = not self.detail
            elif self.page == 3:
                self.set_mode("live" if self.mode == "demo" else "demo")
            elif self.mode == "live":
                if self.source is None:
                    self.set_mode("live", persist=False)
                else:
                    self.source.refresh()
            else:
                self.wake(now)

    def wake(self, now):
        self.awake_until_start = now

    def is_awake(self, now):
        return self.awake_until_start is not None and elapsed(now, self.awake_until_start) < 2500

    def close(self):
        if self.source is not None:
            self.source.close()
