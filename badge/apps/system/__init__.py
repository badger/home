import sys
import os

sys.path.insert(0, "/system/apps/system")
os.chdir("/system/apps/system")

from badgeware import io, brushes, shapes, screen, PixelFont, run, State
from badgeware import get_battery_level, is_charging
import time

# machine exists on the badge but not in the desktop simulator.
try:
    import machine
except ImportError:
    machine = None

# network/ntptime exist on the badge but not in the desktop simulator.
try:
    import network
    import ntptime
    NET_AVAILABLE = True
except ImportError:
    NET_AVAILABLE = False

# Battery-backed hardware RTC (PCF85063A on I2C GPIO4/5). Absent in the sim.
try:
    import board
    from pimoroni_i2c import PimoroniI2C
    from pcf85063a import PCF85063A
    HW_RTC_AVAILABLE = True
except ImportError:
    HW_RTC_AVAILABLE = False

# Fonts
small_font = PixelFont.load("/system/assets/fonts/ark.ppf")
large_font = PixelFont.load("/system/assets/fonts/absolute.ppf")

# Colors
white = brushes.color(235, 245, 255)
phosphor = brushes.color(211, 250, 55)
background = brushes.color(13, 17, 23)
gray = brushes.color(100, 110, 120)
green = brushes.color(46, 160, 67)
red = brushes.color(248, 81, 73)

# Timezone offset from UTC in hours. Change it live with the UP / DOWN buttons;
# the choice is saved automatically and restored on the next boot. The RTCs
# always hold UTC - this offset is applied only for display.
#
# Persistence uses badgeware.State (the same store every other app uses), which
# writes to a writable location off-device (/state/system.json on hardware,
# .badge_state/system.json in the simulator). The app's own folder lives under
# the read-only /system filesystem and can't be written to at runtime.
DEFAULT_TZ_OFFSET = 2
TZ_MIN = -12
TZ_MAX = 14
config = {"tz_offset": DEFAULT_TZ_OFFSET}


def load_config():
    """Restore persisted settings. A missing file just leaves the defaults."""
    try:
        State.load("system", config)
    except Exception:
        pass


def save_config():
    """Persist settings so the timezone survives a reboot."""
    try:
        State.save("system", config)
    except Exception:
        pass


def tz_label():
    """Human-readable current offset, e.g. 'UTC+02:00' or 'UTC-05:00'."""
    return "UTC%+03d:00" % config["tz_offset"]

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# State
WIFI_SSID = None
WIFI_PASSWORD = None
wlan = None
_hw_rtc = None
time_valid = False    # do we have a real time to display?
ntp_synced = False    # has an NTP sync completed at least once?
source = "--"         # where the shown time came from: "RTC" or "NTP"
status = "Starting..."   # short network/sync status line
hw_status = ""        # hardware RTC write result: "RTC set" / "RTC err"


def load_credentials():
    """Load WiFi credentials from secrets.py once."""
    global WIFI_SSID, WIFI_PASSWORD
    if WIFI_SSID is not None:
        return True
    try:
        sys.path.insert(0, "/")
        from secrets import WIFI_SSID as S, WIFI_PASSWORD as P
        sys.path.pop(0)
        WIFI_SSID, WIFI_PASSWORD = S, P
    except ImportError:
        WIFI_SSID, WIFI_PASSWORD = None, None
    return WIFI_SSID is not None


def get_hw_rtc():
    """Lazily build the PCF85063A driver on I2C (GPIO4/5). None if unavailable."""
    global _hw_rtc
    if not HW_RTC_AVAILABLE:
        return None
    if _hw_rtc is None:
        try:
            i2c = PimoroniI2C(sda=board.I2C_SDA, scl=board.I2C_SCL)
            _hw_rtc = PCF85063A(i2c)
        except Exception:
            _hw_rtc = None
    return _hw_rtc


def restore_from_hw_rtc():
    """Seed the internal RTC from the battery-backed RTC so the clock is
    correct immediately at boot, even with no WiFi/NTP."""
    global time_valid, source, status
    rtc = get_hw_rtc()
    if rtc is None:
        return
    try:
        # PCF85063A: (year, month, day, hour, minute, second, weekday)
        y, mo, d, hh, mm, ss, wday = rtc.datetime()
        if y >= 2024:  # a sane year => it was set before, trust it
            # machine.RTC wants (year, month, day, weekday, h, m, s, subsec)
            machine.RTC().datetime((y, mo, d, wday, hh, mm, ss, 0))
            time_valid = True
            source = "RTC"
            status = "From RTC"
    except Exception:
        pass


def set_hw_rtc_from_utc():
    """Write the current internal (UTC) time into the battery-backed RTC."""
    global hw_status
    rtc = get_hw_rtc()
    if rtc is None:
        hw_status = "no RTC"
        return
    try:
        t = time.localtime()  # internal RTC holds UTC after ntptime.settime()
        # PCF85063A: (year, month, day, hour, minute, second, weekday)
        rtc.datetime((t[0], t[1], t[2], t[3], t[4], t[5], t[6]))
        hw_status = "RTC set"
    except Exception:
        hw_status = "RTC err"


def have_ip():
    """True only when we actually hold an IP. isconnected() lies on CYW43."""
    return wlan is not None and wlan.ifconfig()[0] != "0.0.0.0"


def tick_network():
    """Bring WiFi up and sync time over NTP (once). On success also writes the
    battery-backed hardware RTC. Non-blocking-ish."""
    global wlan, ntp_synced, time_valid, source, status

    if ntp_synced:
        return

    if not NET_AVAILABLE:
        status = "No network (sim)"
        return

    if not load_credentials():
        status = "No WiFi config"
        return

    if wlan is None:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        if not have_ip():
            wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        status = "Connecting..."
        return

    if not have_ip():
        status = "Connecting..."
        return

    # We have an IP - try a single NTP sync (brief blocking call).
    status = "Syncing time..."
    try:
        ntptime.settime()        # internal RTC <- UTC
        set_hw_rtc_from_utc()    # battery-backed RTC <- UTC
        ntp_synced = True
        time_valid = True
        source = "NTP"
        status = "Synced"
    except Exception:
        status = "Sync failed"


def init():
    # Restore the saved timezone, then show the battery-backed time straight
    # away, before networking.
    load_config()
    restore_from_hw_rtc()


def center_text(text, y):
    w, _ = screen.measure_text(text)
    screen.text(text, 80 - (w / 2), y)


def draw_battery(x, y, level, charging):
    """Small battery glyph at (x, y), 26x12, filled by level %."""
    # body outline
    screen.brush = gray
    screen.draw(shapes.rectangle(x, y, 24, 12).stroke(1))
    # positive terminal
    screen.draw(shapes.rectangle(x + 24, y + 3, 2, 6))
    # fill
    fill_w = int(20 * max(0, min(100, level)) / 100)
    if charging:
        screen.brush = green
    elif level <= 20:
        screen.brush = red
    else:
        screen.brush = phosphor
    if fill_w > 0:
        screen.draw(shapes.rectangle(x + 2, y + 2, fill_w, 8))


def update():
    tick_network()

    # Manual re-sync with button A: re-runs NTP and re-writes the hardware RTC.
    if io.BUTTON_A in io.pressed:
        global ntp_synced, hw_status
        ntp_synced = False
        hw_status = ""

    # Adjust the timezone with UP / DOWN and save the change immediately.
    if io.BUTTON_UP in io.pressed and config["tz_offset"] < TZ_MAX:
        config["tz_offset"] += 1
        save_config()
    if io.BUTTON_DOWN in io.pressed and config["tz_offset"] > TZ_MIN:
        config["tz_offset"] -= 1
        save_config()

    # Background
    screen.brush = background
    screen.draw(shapes.rectangle(0, 0, 160, 120))

    # Header
    screen.font = small_font
    screen.brush = phosphor
    center_text("System", 3)
    screen.brush = gray
    screen.draw(shapes.rectangle(5, 13, 150, 1))

    # Local time = RTC (UTC) + offset
    t = time.localtime(time.time() + config["tz_offset"] * 3600)
    weekday = WEEKDAYS[t[6]]
    date_str = "%s %02d %s %d" % (weekday, t[2], MONTHS[t[1] - 1], t[0])
    time_str = "%02d:%02d:%02d" % (t[3], t[4], t[5])

    if not time_valid:
        # No reliable time yet - show status instead of a bogus clock.
        screen.font = small_font
        screen.brush = gray
        center_text(status, 38)
        center_text("waiting for time...", 50)
    else:
        # Big clock
        screen.font = large_font
        screen.brush = white
        center_text(time_str, 24)
        # Date
        screen.font = small_font
        screen.brush = gray
        center_text(date_str, 48)
        # Time source + hardware-RTC status (verifiable on screen)
        if ntp_synced:
            line = "via NTP - " + (hw_status or "RTC set")
        else:
            line = "via RTC - " + status
        center_text(line, 70)

    # Current timezone (the value the UP / DOWN buttons change).
    screen.font = small_font
    screen.brush = phosphor
    center_text(tz_label(), 60)

    # Charging / battery row
    level = get_battery_level()
    charging = is_charging()

    screen.font = small_font
    draw_battery(22, 82, level, charging)
    screen.brush = white
    screen.text("%d%%" % level, 54, 84)

    if charging:
        screen.brush = green
        screen.text("Charging", 85, 84)
    else:
        screen.brush = gray
        screen.text("On battery", 85, 84)

    # Footer
    screen.brush = gray
    screen.draw(shapes.rectangle(5, 104, 150, 1))
    screen.font = small_font
    center_text("A: sync    UP/DOWN: zone", 107)


if __name__ == "__main__":
    run(update)
