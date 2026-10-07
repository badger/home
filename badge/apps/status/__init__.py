import sys
import os

APP_DIR = "/system/apps/status"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

import network
from urllib.urequest import urlopen
import json
import gc

small_font = font.ark
large_font = font.absolute

white = color.rgb(235, 245, 255)
phosphor = color.rgb(211, 250, 55)
background = color.rgb(13, 17, 23)
gray = color.rgb(100, 110, 120)
green = color.rgb(46, 160, 67)
yellow = color.rgb(210, 153, 34)
orange = color.rgb(219, 109, 40)
red = color.rgb(248, 81, 73)
blue = color.rgb(48, 148, 255)

SUMMARY_URL = "https://www.githubstatus.com/api/v2/summary.json"
INCIDENTS_URL = "https://www.githubstatus.com/api/v2/incidents.json"
SUMMARY_REFRESH_MS = 60 * 1000
INCIDENTS_REFRESH_MS = 10 * 60 * 1000
WIFI_TIMEOUT = 60
NTP_RETRY_MS = 10 * 60 * 1000
SERVICE_ROWS = 11
DAY = 86400
STATS_DAYS = 30
CHUNK_SIZE = 1024
CHUNKS_PER_FRAME = 4
# Must exceed the longest incident header (~600 bytes) so none is split across trims
STREAM_TAIL = 1024
INCIDENT_MARKER = b',"incident_updates"'
PAGES = ("OVERVIEW", "SERVICES", "LAST 30 DAYS", "RECENT")

# Statuspage indicator -> (label, colour)
INDICATORS = {
    "none": ("UP", green),
    "minor": ("DEGRADED", yellow),
    "major": ("PARTIAL OUTAGE", orange),
    "critical": ("DOWN", red),
}

COMPONENT_COLOURS = {
    "operational": green,
    "degraded_performance": yellow,
    "partial_outage": orange,
    "major_outage": red,
    "under_maintenance": blue,
}

IMPACT_COLOURS = {
    "none": gray,
    "minor": yellow,
    "major": orange,
    "critical": red,
}

WIFI_SSID = None
WIFI_PASSWORD = None

wlan = None
connected = False
ticks_start = None
page = 0

indicator = None
description = ""
components = []
active_incidents = []
maintenance_count = 0
error_message = None
summary_updated = None

# Each incident: (name, impact, started_ts, resolved_ts or None)
incidents = []
incidents_updated = None
incident_stream = None
stream_bytes = 0

clock_base = None
clock_ticks = 0
clock_synced = False
ntp_attempted = None


def get_wifi_credentials():
    global WIFI_SSID, WIFI_PASSWORD

    if WIFI_SSID is not None:
        return True

    sys.path.insert(0, "/")
    try:
        from secrets import WIFI_PASSWORD, WIFI_SSID
    except ImportError:
        WIFI_SSID = None
        WIFI_PASSWORD = None
    finally:
        sys.path.pop(0)

    return bool(WIFI_SSID)


def wlan_start():
    global wlan, ticks_start, connected

    if ticks_start is None:
        ticks_start = badge.ticks

    if wlan is None:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        if not wlan.isconnected():
            wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    is_up = wlan.isconnected()
    if connected and not is_up:
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        ticks_start = badge.ticks
    connected = is_up
    return connected


def days_from_civil(y, m, d):
    y -= m <= 2
    era = y // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def to_timestamp(year, month, day, hour, minute, second):
    return days_from_civil(year, month, day) * DAY + hour * 3600 + minute * 60 + second


def parse_iso(value):
    if not value:
        return None
    return to_timestamp(
        int(value[0:4]), int(value[5:7]), int(value[8:10]),
        int(value[11:13]), int(value[14:16]), int(value[17:19]),
    )


def set_clock(timestamp):
    global clock_base, clock_ticks
    clock_base = timestamp
    clock_ticks = badge.ticks


def now():
    if clock_base is None:
        return None
    return clock_base + (badge.ticks - clock_ticks) // 1000


def sync_clock():
    global clock_synced, ntp_attempted
    ntp_attempted = badge.ticks
    try:
        import ntptime
        import time
        ntptime.settime()
        set_clock(to_timestamp(*time.gmtime()[:6]))
        clock_synced = True
    except Exception as e:
        print("NTP sync failed:", e)


def read_all(response):
    data = b""
    chunk = bytearray(512)
    while True:
        length = response.readinto(chunk)
        if length == 0:
            break
        data += chunk[:length]
    return data


def fetch_summary():
    global indicator, description, components, active_incidents
    global maintenance_count, error_message, summary_updated

    try:
        response = urlopen(SUMMARY_URL, headers={"User-Agent": "GitHubBadge"})
        try:
            summary = json.loads(read_all(response).decode("utf-8"))
        finally:
            response.close()

        indicator = summary["status"]["indicator"]
        description = summary["status"]["description"]
        components = [
            (c["name"], c["status"])
            for c in summary["components"]
            if not c.get("group") and not c["name"].startswith("Visit ")
        ]
        active_incidents = [(i["name"], i["impact"]) for i in summary["incidents"]]
        maintenance_count = len(summary["scheduled_maintenances"])
        error_message = None

        if not clock_synced:
            # Fallback clock: never step backwards to an older page timestamp
            page_time = parse_iso(summary["page"]["updated_at"])
            current = now()
            if current is None or page_time > current:
                set_clock(page_time)
        del response, summary
    except Exception as e:
        print("Summary fetch failed:", e)
        indicator = None
        error_message = "Status unavailable"

    summary_updated = badge.ticks
    gc.collect()


def parse_incident(header):
    data = json.loads(header.decode("utf-8"))
    return (
        data["name"],
        data["impact"],
        parse_iso(data["started_at"] or data["created_at"]),
        parse_iso(data["resolved_at"]),
    )


def stream_incidents():
    # The feed is ~280KB, so scan it in chunks and keep only each incident's header fields
    global incidents, incidents_updated, stream_bytes

    stream_bytes = 0
    found = []
    response = urlopen(INCIDENTS_URL, headers={"User-Agent": "GitHubBadge"})
    chunk = bytearray(CHUNK_SIZE)
    buf = b""
    done = False

    try:
        while not done:
            for _ in range(CHUNKS_PER_FRAME):
                length = response.readinto(chunk)
                if length == 0:
                    done = True
                    break
                stream_bytes += length
                buf += bytes(chunk[:length])

                while True:
                    marker = buf.find(INCIDENT_MARKER)
                    if marker < 0:
                        break
                    start = buf.rfind(b'{"id":"', 0, marker)
                    if start >= 0:
                        found.append(parse_incident(buf[start:marker] + b"}"))
                    buf = buf[marker + len(INCIDENT_MARKER):]
                buf = buf[-STREAM_TAIL:]
            yield
    finally:
        response.close()

    incidents = found
    incidents_updated = badge.ticks
    gc.collect()


def step_incident_stream():
    global incident_stream, incidents_updated
    try:
        next(incident_stream)
    except StopIteration:
        incident_stream = None
    except Exception as e:
        print("Incident fetch failed:", e)
        incident_stream = None
        incidents_updated = badge.ticks


def incident_duration(incident, current):
    _, _, started, resolved = incident
    end = resolved if resolved is not None else current
    return max(0, end - started)


def incident_stats(current):
    cutoff_30 = current - STATS_DAYS * DAY
    cutoff_7 = current - 7 * DAY
    recent = [i for i in incidents if i[2] >= cutoff_30]
    durations = [incident_duration(i, current) for i in recent]
    resolved = [incident_duration(i, current) for i in recent if i[3] is not None]
    return {
        "count_30": len(recent),
        "count_7": len([i for i in recent if i[2] >= cutoff_7]),
        "serious": len([i for i in recent if i[1] in ("major", "critical")]),
        "disrupted": sum(durations),
        "longest": max(durations) if durations else 0,
        "average": sum(resolved) // len(resolved) if resolved else 0,
        "covered_days": (current - incidents[-1][2]) // DAY if incidents else 0,
    }


def format_duration(seconds):
    # Fallback clock can lag behind incident timestamps
    minutes = max(0, seconds) // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h{minutes % 60:02d}m"
    return f"{hours // 24}d {hours % 24}h"


def format_ago(seconds):
    if seconds < 60:
        return "just now"
    return f"{format_duration(seconds)} ago"


def clear():
    screen.pen = background
    screen.rectangle(0, 0, screen.width, screen.height)


def center_text(text, y):
    w, _ = screen.measure_text(text)
    screen.text(text, (screen.width - w) / 2, y)


def right_text(text, y):
    w, _ = screen.measure_text(text)
    screen.text(text, screen.width - 4 - w, y)


def fit_text(text, max_width):
    if screen.measure_text(text)[0] <= max_width:
        return text
    while text and screen.measure_text(text + "..")[0] > max_width:
        text = text[:-1]
    return text + ".."


def draw_dot(x, y, colour):
    screen.pen = colour
    screen.shape(shape.circle(x, y, 2))


def draw_stat(label, value, y):
    screen.pen = gray
    screen.text(label, 4, y)
    screen.pen = white
    right_text(value, y)


def draw_loading(y):
    screen.font = small_font
    screen.pen = gray
    dots = "." * ((int(badge.ticks / 500) % 3) + 1)
    if incident_stream is not None:
        center_text(f"Reading history {stream_bytes // 1024}KB{dots}", y)
    else:
        center_text(f"Please wait{dots}", y)


def draw_overview():
    if indicator in INDICATORS:
        label, colour = INDICATORS[indicator]
    elif error_message:
        label, colour = "UNKNOWN", gray
    else:
        screen.font = large_font
        screen.pen = white
        center_text("Checking", 45)
        draw_loading(65)
        return

    screen.pen = colour
    screen.shape(shape.circle(screen.width / 2, 32, 16))

    screen.font = large_font
    screen.pen = white
    center_text(label, 52)

    screen.font = small_font
    screen.pen = gray
    center_text(fit_text(error_message or description, 150), 68)

    current = now()
    if active_incidents:
        name, impact = active_incidents[0]
        screen.pen = IMPACT_COLOURS.get(impact, orange)
        center_text(f"{len(active_incidents)} active incident(s)", 80)
        center_text(fit_text(name, 150), 90)
    elif incidents and current is not None:
        latest = incidents[0]
        since = current - (latest[3] or current)
        screen.pen = white
        center_text(f"Incident-free for {format_duration(since)}", 80)
        screen.pen = gray
        center_text(f"Last: {format_ago(current - latest[2])}", 90)
    elif incident_stream is not None:
        draw_loading(84)

    if maintenance_count:
        screen.pen = blue
        center_text(f"{maintenance_count} maintenance scheduled", 99)


def draw_services():
    if not components:
        draw_loading(50)
        return

    screen.font = small_font
    shown = components
    if len(components) > SERVICE_ROWS:
        shown = components[:SERVICE_ROWS - 1]
    y = 15
    for name, status in shown:
        colour = COMPONENT_COLOURS.get(status, gray)
        draw_dot(8, y + 3, colour)
        screen.pen = white if status == "operational" else colour
        screen.text(fit_text(name, 140), 14, y)
        y += 8

    hidden = components[len(shown):]
    if hidden:
        screen.pen = gray
        if any(status != "operational" for _, status in hidden):
            screen.pen = orange
        screen.text(f"+{len(hidden)} more", 14, y)


def draw_stats():
    current = now()
    if not incidents or current is None:
        draw_loading(50)
        return

    stats = incident_stats(current)
    screen.font = small_font
    draw_stat("Incidents", str(stats["count_30"]), 16)
    draw_stat("Last 7 days", str(stats["count_7"]), 26)
    draw_stat("Major/critical", str(stats["serious"]), 36)
    draw_stat("Time disrupted", format_duration(stats["disrupted"]), 46)
    draw_stat("Longest", format_duration(stats["longest"]), 56)
    draw_stat("Avg to resolve", format_duration(stats["average"]), 66)

    # The API only returns the last 50 incidents
    if stats["covered_days"] < STATS_DAYS:
        screen.pen = gray
        center_text(f"Feed covers only {stats['covered_days']}d", 84)


def draw_recent():
    current = now()
    if not incidents or current is None:
        draw_loading(50)
        return

    screen.font = small_font
    y = 15
    for incident in incidents[:4]:
        name, impact, started, resolved = incident
        draw_dot(6, y + 3, IMPACT_COLOURS.get(impact, gray))
        screen.pen = white
        screen.text(fit_text(name, 146), 12, y)

        screen.pen = gray
        state = "ongoing" if resolved is None else format_duration(incident_duration(incident, current))
        screen.text(fit_text(f"{format_ago(current - started)} - {state} - {impact}", 146), 12, y + 8)
        y += 22


def draw_screen():
    clear()

    screen.font = small_font
    screen.pen = phosphor
    screen.text(f"GITHUB {PAGES[page]}", 2, 2)
    screen.pen = gray
    right_text(f"{page + 1}/{len(PAGES)}", 2)

    if connected:
        [draw_overview, draw_services, draw_stats, draw_recent][page]()
    else:
        draw_loading(55)

    screen.font = small_font
    if connected:
        screen.pen = phosphor
        screen.text("UP/DN:Page SEL:Refresh", 2, 110)
        if summary_updated is not None:
            remaining = max(0, SUMMARY_REFRESH_MS - (badge.ticks - summary_updated)) // 1000
            screen.pen = gray
            right_text(f"{remaining}s", 110)
    else:
        screen.pen = gray
        screen.text("Connecting...", 2, 110)


def draw_message(title, subtitle):
    clear()
    screen.font = large_font
    screen.pen = white
    center_text(title, 40)
    screen.font = small_font
    screen.pen = phosphor
    center_text(subtitle, 60)


def is_stale(updated, interval):
    return updated is None or badge.ticks - updated > interval


def update():
    global page, incident_stream

    if badge.pressed(BUTTON_UP):
        page = (page - 1) % len(PAGES)
    if badge.pressed(BUTTON_DOWN):
        page = (page + 1) % len(PAGES)

    if not get_wifi_credentials():
        draw_message("No WiFi Config", "Edit secrets.py")
        return

    if not wlan_start():
        if badge.ticks - ticks_start >= WIFI_TIMEOUT * 1000:
            draw_message("Connection Failed", "Check WiFi settings")
        else:
            draw_screen()
        return

    refresh = badge.pressed(BUTTON_SELECT)

    if not clock_synced and is_stale(ntp_attempted, NTP_RETRY_MS):
        sync_clock()

    if refresh or is_stale(summary_updated, SUMMARY_REFRESH_MS):
        draw_screen()
        fetch_summary()

    if incident_stream is None and (refresh or is_stale(incidents_updated, INCIDENTS_REFRESH_MS)):
        incident_stream = stream_incidents()
    if incident_stream is not None:
        step_incident_stream()

    draw_screen()


if __name__ == "__main__":
    run(update)
