"""Badge-side model for the T3 Code status app; no drawing, testable off-device."""

import math

STATES = ("attention", "working", "error", "done", "idle")
LABELS = {
    "attention": "NEEDS YOU",
    "working": "WORKING",
    "error": "ERROR",
    "done": "DONE",
    "idle": "IDLE",
}


def clean(text, limit):
    """Printable ASCII only (the badge fonts have no other glyphs), collapsed and capped."""
    text = "".join(c if 32 <= ord(c) < 127 else " " for c in str(text or ""))
    return " ".join(text.split())[:limit]


def age_text(seconds):
    if not isinstance(seconds, int) or seconds < 0:
        return ""
    if seconds < 45:
        return "now"
    if seconds < 3600:
        return "%dm" % max(1, (seconds + 30) // 60)
    if seconds < 86400:
        return "%dh" % (seconds // 3600)
    return "%dd" % (seconds // 86400)


def parse_status(data):
    """Validate the bridge's /t3/status payload into a predictable shape."""
    if not isinstance(data, dict) or not isinstance(data.get("threads"), list):
        raise ValueError("unexpected status from bridge")
    counts = data.get("counts") if isinstance(data.get("counts"), dict) else {}
    result = {
        "ok": bool(data.get("ok")),
        "src": clean(data.get("src"), 16) or None,
        "counts": {},
        "sources": [],
        "threads": [],
    }
    for state in STATES:
        value = counts.get(state)
        result["counts"][state] = value if isinstance(value, int) and value > 0 else 0
    for source in data.get("sources") or []:
        if isinstance(source, dict):
            result["sources"].append({
                "name": clean(source.get("name"), 16),
                "ok": bool(source.get("ok")),
                "error": clean(source.get("error"), 40),
            })
    for thread in data["threads"]:
        if not isinstance(thread, dict):
            continue
        state = thread.get("state")
        age = thread.get("age")
        result["threads"].append({
            "id": clean(thread.get("id"), 16),
            "title": clean(thread.get("title"), 60) or "Untitled thread",
            "project": clean(thread.get("project"), 24),
            "src": clean(thread.get("src"), 16),
            "state": state if state in STATES else "idle",
            "detail": clean(thread.get("detail"), 32),
            "model": clean(thread.get("model"), 32),
            "age": age if isinstance(age, int) else None,
            "msg": clean(thread.get("msg"), 160),
        })
    return result


def source_line(status):
    """Which T3 Code hosts are live, for the header."""
    if not status or not status["sources"]:
        return "no T3 hosts"
    down = [source for source in status["sources"] if not source["ok"]]
    if not down:
        names = [source["name"] for source in status["sources"]]
        return names[0] if len(names) == 1 else "%d hosts live" % len(names)
    first = down[0]
    more = " +%d" % (len(down) - 1) if len(down) > 1 else ""
    return "%s: %s%s" % (first["name"], first["error"] or "offline", more)


def next_host(status, current, step):
    """Cycle the host filter: all hosts (None), then each source in order."""
    choices = [None] + [source["name"] for source in (status or {}).get("sources", [])]
    position = choices.index(current) if current in choices else 0
    return choices[(position + step) % len(choices)]


def status_path(host):
    return "/t3/status" + ("?src=" + host if host else "")


def keep_selection(threads, selected_id, index):
    """Follow the selected thread across refreshes, else keep the position."""
    for position, thread in enumerate(threads):
        if thread["id"] == selected_id:
            return position
    if not threads:
        return 0
    return max(0, min(index, len(threads) - 1))


def lights_level(counts, ticks):
    """Case light brightness: a strong pulse when a thread needs you, a slow
    breath while agents work, otherwise off."""
    if counts.get("attention"):
        period, low, high = 1200, 0.1, 0.8
    elif counts.get("working"):
        period, low, high = 3000, 0.02, 0.12
    else:
        return 0
    phase = (ticks % period) / period
    return low + (high - low) * (0.5 - 0.5 * math.cos(2 * math.pi * phase))
