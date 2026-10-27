"""Badge-side model for the AutoGPT status app: what to ask the v2 API and what
the answers mean. No drawing, so it is testable off-device."""

import math
import time

COUNTED = ("RUNNING", "QUEUED", "REVIEW", "FAILED")
CYCLE_MS = 30000
SLOW_MS = 300000
RETRY_MS = 10000
RECENT_RUNS = 6
NAME_CACHE = 48
DAY = 86400


# ---- time (no datetime on the badge) ----------------------------------------------

def days_from_civil(year, month, day):
    if month <= 2:
        year -= 1
    era = (year if year >= 0 else year - 399) // 400
    yoe = year - era * 400
    doy = (153 * (month + (-3 if month > 2 else 9)) + 2) // 5 + day - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def civil_from_days(days):
    days += 719468
    era = (days if days >= 0 else days - 146096) // 146097
    doe = days - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    day = doy - (153 * mp + 2) // 5 + 1
    month = mp + (3 if mp < 10 else -9)
    return yoe + era * 400 + (1 if month <= 2 else 0), month, day


def iso_to_epoch(text):
    """'2026-10-26T18:55:33.647000Z' -> seconds since 1970 UTC, or None."""
    if not isinstance(text, str) or len(text) < 19:
        return None
    try:
        seconds = (days_from_civil(int(text[0:4]), int(text[5:7]), int(text[8:10])) * DAY
                   + int(text[11:13]) * 3600 + int(text[14:16]) * 60 + int(text[17:19]))
        tail = text[19:]
        for sign in ("+", "-"):
            if sign in tail:
                offset = tail[tail.index(sign) + 1:]
                minutes = int(offset[0:2]) * 60 + int(offset[3:5])
                seconds += -minutes * 60 if sign == "+" else minutes * 60
                break
        return seconds
    except (ValueError, IndexError):
        return None


MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def http_date_to_epoch(text):
    """'Tue, 27 Oct 2026 02:21:52 GMT' -> seconds since 1970 UTC, or None."""
    try:
        _, day, month, year, clock, _ = text.split(" ")
        hours, minutes, secs = clock.split(":")
        return (days_from_civil(int(year), MONTHS.index(month) + 1, int(day)) * DAY
                + int(hours) * 3600 + int(minutes) * 60 + int(secs))
    except (AttributeError, ValueError):
        return None


def epoch_to_iso(seconds):
    days, rest = divmod(int(seconds), DAY)
    year, month, day = civil_from_days(days)
    return "%04d-%02d-%02dT%02d:%02d:%02dZ" % (year, month, day, rest // 3600, rest // 60 % 60, rest % 60)


# ---- formatting --------------------------------------------------------------------

def clean(text, limit):
    text = "".join(c if 32 <= ord(c) < 127 else " " for c in str(text or ""))
    return " ".join(text.split())[:limit]


def age_text(seconds):
    if seconds is None:
        return ""
    seconds = max(0, int(seconds))
    if seconds < 45:
        return "now"
    if seconds < 3600:
        return "%dm" % max(1, (seconds + 30) // 60)
    if seconds < DAY:
        return "%dh" % (seconds // 3600)
    return "%dd" % (seconds // DAY)


def until_text(seconds):
    if seconds is None:
        return ""
    if seconds < 60:
        return "now"
    if seconds < 3600:
        return "in %dm" % ((seconds + 59) // 60)
    if seconds < DAY:
        return "in %dh" % (seconds // 3600)
    return "in %dd" % (seconds // DAY)


def duration_text(seconds):
    if not isinstance(seconds, (int, float)) or seconds <= 0:
        return ""
    seconds = int(seconds + 0.5)
    if seconds < 60:
        return "%ds" % seconds
    if seconds < 3600:
        return "%dm %ds" % (seconds // 60, seconds % 60)
    return "%dh %dm" % (seconds // 3600, seconds // 60 % 60)


def money(cents):
    if not isinstance(cents, int):
        return ""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return "%s$%d.%02d" % (sign, cents // 100, cents % 100)


def environment(base_url):
    """A short label for which AutoGPT the badge is talking to."""
    host = base_url.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]
    if host == "backend.agpt.co":
        return "prod"
    if host.startswith("dev-"):
        return "dev"
    return host[:20]


def lights_level(counts, flash_until, ticks, chats=None):
    """Pulse while something waits on you, blink after a new failure, breathe while working."""
    chats = chats or {}
    if flash_until is not None and time.ticks_diff(flash_until, ticks) > 0:
        return 0.9 if (ticks // 150) % 2 == 0 else 0.0
    if counts.get("REVIEW") or chats.get("needs_user"):
        period, low, high = 1200, 0.1, 0.8
    elif counts.get("RUNNING") or chats.get("working"):
        period, low, high = 3000, 0.02, 0.12
    else:
        return 0
    phase = (ticks % period) / period
    return low + (high - low) * (0.5 - 0.5 * math.cos(2 * math.pi * phase))


# ---- the dashboard -----------------------------------------------------------------

def parse_run(item):
    duration = item.get("duration_seconds")
    cost = item.get("cost_cents")
    nodes = item.get("node_exec_count")
    status = item.get("status")
    return {
        "id": clean(item.get("id"), 40),
        "graph_id": clean(item.get("graph_id"), 40),
        "version": item.get("graph_version") if isinstance(item.get("graph_version"), int) else None,
        "status": status if isinstance(status, str) else "?",
        "started": iso_to_epoch(item.get("started_at")),
        "ended": iso_to_epoch(item.get("ended_at")),
        "duration": duration if isinstance(duration, (int, float)) else None,
        "cost": cost if isinstance(cost, int) else None,
        "nodes": nodes if isinstance(nodes, int) else None,
    }


AUTOPILOT_SESSIONS = 6


def parse_session(item):
    """One AutoPilot chat from GET /autopilot/sessions."""
    status = item.get("status")
    processing = item.get("is_processing") is True
    if not isinstance(status, str):
        status = "running" if processing else "idle"
    if item.get("needs_user") is True:
        state = "needs_user"
    elif processing or status in ("running", "queued"):
        state = "working" if processing or status == "running" else "queued"
    else:
        state = "idle"
    expert = clean(item.get("expert_name"), 24)
    return {
        "id": clean(item.get("id"), 40),
        "title": clean(item.get("title"), 60) or "Untitled chat",
        "state": state,
        "status": clean(status, 12),
        "persona": expert or ("Expert" if item.get("expert_id") else "Otto"),
        "source": clean(item.get("source_platform"), 16),
        "pinned": item.get("is_pinned") is True,
        "updated": iso_to_epoch(item.get("updated_at")),
    }


class Dashboard:
    """Decides which v2 request to make next and folds each answer into state.

    The app calls next_request(ticks) when the network is idle and handle()
    with each result, so one TLS connection carries every request in turn.
    """

    def __init__(self, names=None):
        self.counts = dict((status, None) for status in COUNTED)
        self.runs = []
        self.balance = None
        self.credits_allowed = True
        self.schedules_allowed = True
        self.next_schedule = None
        # AutoPilot (Otto and Expert chats); None until the API answers, False
        # while this server or key can't list them.
        self.autopilot = None
        self.sessions = []
        self.chats = {"working": 0, "queued": 0, "needs_user": 0, "total": None}
        self.names = dict(names or {})
        self.names_changed = False
        self.queue = []
        self.fatal = None
        self.error = None
        self.cycle_at = None
        self.slow_at = None
        self.updated_at = None
        self.clock = None  # (epoch seconds, ticks) from the server's Date header
        self.alert = False  # set when the failure count rises
        self.loaded = False

    # time -------------------------------------------------------------------------

    def set_clock(self, epoch, ticks):
        if epoch:
            self.clock = (epoch, ticks)

    def now(self, ticks):
        if self.clock is None:
            return None
        epoch, at = self.clock
        return epoch + time.ticks_diff(ticks, at) // 1000

    # scheduling ---------------------------------------------------------------------

    def refresh(self):
        self.fatal = None
        self.cycle_at = None
        self.slow_at = None

    def plan(self, ticks):
        work = [("recent", "/runs?limit=%d" % RECENT_RUNS)]
        slow = self.slow_at is None or time.ticks_diff(ticks, self.slow_at) >= 0
        # Unavailable AutoPilot listings are retried with the slow requests, so
        # the panel appears on its own once the server supports it.
        if self.autopilot is not False or slow:
            work.append(("autopilot", "/autopilot/sessions?limit=%d" % AUTOPILOT_SESSIONS))
        for status in ("RUNNING", "QUEUED", "REVIEW"):
            work.append(("count:" + status, "/runs?statuses=%s&limit=1" % status))
        # Counting the last day's failures needs the time, which the badge
        # learns from the first answer, so this path is filled in when sent.
        work.append(("count:FAILED", None))
        if slow:
            if self.credits_allowed:
                work.append(("credits", "/credits"))
            if self.schedules_allowed:
                work.append(("schedules", "/schedules?limit=5"))
            self.slow_at = time.ticks_add(ticks, SLOW_MS)
        return work

    def next_request(self, ticks):
        if self.fatal:
            return None
        while True:
            if not self.queue:
                if self.cycle_at is not None and time.ticks_diff(ticks, self.cycle_at) < 0:
                    return None
                self.queue = self.plan(ticks)
                self.cycle_at = time.ticks_add(ticks, CYCLE_MS)
            key, path = self.queue.pop(0)
            if path is None:
                now = self.now(ticks)
                if not now:
                    continue  # still no clock: skip it this cycle
                path = "/runs?statuses=FAILED&started_after=%s&limit=1" % epoch_to_iso(now - DAY)
            return key, path

    # answers ----------------------------------------------------------------------

    def handle(self, key, status, payload, ticks):
        if status == 200 and isinstance(payload, dict):
            self.error = None
            self.updated_at = ticks
            self.loaded = True
            self._apply(key, payload)
            return
        if key.startswith("name:"):
            graph_id = key[5:]
            self._remember(graph_id, "Agent " + graph_id[:6])
            return
        if key == "autopilot" and status in (403, 404):
            # Older servers lack the endpoint (404); older keys lack the scope (403).
            self.autopilot = False
            self.sessions = []
            return
        if key in ("credits", "schedules") and status == 403:
            # The key lacks READ_CREDITS / READ_SCHEDULE; hide that panel.
            if key == "credits":
                self.credits_allowed = False
            else:
                self.schedules_allowed = False
            return
        message = payload if isinstance(payload, str) else "HTTP %d" % status
        if status == 401:
            self.fatal = "API key rejected. Check AUTOGPT_API_KEY."
        elif status == 403:
            self.fatal = "Key lacks a permission: " + message
        elif status == 404 and (key == "recent" or key.startswith("count:")):
            self.fatal = "No v2 API here (404). Check AUTOGPT_API_URL."
        else:
            self.error = message
            if status == 429:
                self.queue = []
                self.cycle_at = time.ticks_add(ticks, 60000)
            elif not self.loaded:
                self.cycle_at = time.ticks_add(ticks, RETRY_MS)
        if self.fatal:
            self.queue = []

    def _apply(self, key, payload):
        if key.startswith("count:"):
            status = key[6:]
            total = payload.get("total_count")
            if isinstance(total, int):
                if status == "FAILED" and self.counts["FAILED"] is not None and total > self.counts["FAILED"]:
                    self.alert = True
                self.counts[status] = total
        elif key == "recent":
            items = payload.get("items") if isinstance(payload.get("items"), list) else []
            self.runs = [parse_run(item) for item in items[:RECENT_RUNS] if isinstance(item, dict)]
            wanted = []
            for run in self.runs:
                graph_id = run["graph_id"]
                if graph_id and graph_id not in self.names and graph_id not in wanted:
                    wanted.append(graph_id)
            # Look names up straight after the run list, ahead of the counts.
            self.queue = [("name:" + graph_id, "/graphs/%s/library-agent" % graph_id) for graph_id in wanted] + self.queue
        elif key.startswith("name:"):
            self._remember(key[5:], clean(payload.get("name"), 40) or "Agent " + key[5:11])
        elif key == "autopilot":
            items = payload.get("items") if isinstance(payload.get("items"), list) else []
            self.sessions = [parse_session(item) for item in items[:AUTOPILOT_SESSIONS] if isinstance(item, dict)]
            self.autopilot = True
            chats = {"working": 0, "queued": 0, "needs_user": 0, "total": None}
            for session in self.sessions:
                if session["state"] != "idle":
                    chats[session["state"]] += 1
            total = payload.get("total_count")
            chats["total"] = total if isinstance(total, int) else len(self.sessions)
            self.chats = chats
        elif key == "credits":
            balance = payload.get("balance_cents")
            self.balance = balance if isinstance(balance, int) else None
        elif key == "schedules":
            soonest = None
            for item in payload.get("items") or []:
                when = iso_to_epoch(item.get("next_run_time")) if isinstance(item, dict) else None
                if when and (soonest is None or when < soonest[1]):
                    soonest = (clean(item.get("name"), 40) or "Schedule", when)
            self.next_schedule = soonest

    def _remember(self, graph_id, name):
        if len(self.names) >= NAME_CACHE and graph_id not in self.names:
            self.names.pop(next(iter(self.names)))
        self.names[graph_id] = name
        self.names_changed = True

    def name_of(self, run):
        return self.names.get(run["graph_id"]) or "Agent " + run["graph_id"][:6]
