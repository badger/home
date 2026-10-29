"""Shared UTC clock contract for the clock and Universe reminders."""

import json
import time
import errno
from badgeware import State

_synced = None


def load_state(key, defaults):
    try:
        with open("/state/" + key + ".json") as handle:
            data = json.load(handle)
    except OSError as error:
        if error.args[0] == errno.ENOENT:
            return defaults
        raise
    if not isinstance(data, dict):
        raise ValueError(key + ": expected an object")
    defaults.update(data)
    return defaults


def save_state(key, data):
    # Firmware State.save can swallow write errors; verify before claiming success.
    State.save(key, data)
    with open("/state/" + key + ".json") as handle:
        if json.load(handle) != data:
            raise OSError(key + ": state did not save")


def ready():
    global _synced
    if _synced is None:
        state = load_state("utc_clock", {"synced": False})
        if type(state["synced"]) is not bool:
            raise ValueError("Invalid UTC clock state")
        _synced = state["synced"]
    return _synced and time.gmtime()[0] >= 2026


def sync():
    global _synced
    import ntptime

    _synced = False
    ntptime.settime()
    if time.gmtime()[0] < 2026:
        raise ValueError("NTP returned an invalid date")
    try:
        helper = rtc
    except NameError:
        helper = None
    if helper is not None:
        helper.localtime_to_rtc()
    else:
        print("UTC clock: internal RTC only; no firmware RTC helper")
    save_state("utc_clock", {"synced": True})
    _synced = True


def seconds(year, month, day, hour=0, minute=0, second=0):
    tail = (0, 0, 0)[:len(time.gmtime(0)) - 6]
    return time.mktime((year, month, day, hour, minute, second) + tail)


def parse_utc(value):
    if (not isinstance(value, str) or len(value) != 20
            or value[4] != "-" or value[7] != "-" or value[10] != "T"
            or value[13] != ":" or value[16] != ":" or value[19] != "Z"):
        raise ValueError("Use UTC dates: YYYY-MM-DDTHH:MM:SSZ")
    parts = tuple(value[a:b] for a, b in
                  ((0, 4), (5, 7), (8, 10), (11, 13), (14, 16), (17, 19)))
    if any(not "0" <= character <= "9" for part in parts for character in part):
        raise ValueError("Invalid agenda date")
    fields = tuple(int(part) for part in parts)
    if (not 2026 <= fields[0] <= 2099 or not 1 <= fields[1] <= 12
            or not 1 <= fields[2] <= 31 or not 0 <= fields[3] <= 23
            or not 0 <= fields[4] <= 59 or not 0 <= fields[5] <= 59):
        raise ValueError("Invalid agenda date")
    stamp = seconds(*fields)
    if time.gmtime(stamp)[:6] != fields:
        raise ValueError("Invalid agenda date")
    return stamp


def pacific_time(stamp=None):
    """Current US Pacific rules; never change the underlying RTC."""
    stamp = time.time() if stamp is None else stamp
    year = time.gmtime(stamp)[0]
    march_first = time.gmtime(seconds(year, 3, 1))[6]
    november_first = time.gmtime(seconds(year, 11, 1))[6]
    march_sunday = 1 + (6 - march_first) % 7 + 7
    november_sunday = 1 + (6 - november_first) % 7
    start = seconds(year, 3, march_sunday, 10)
    end = seconds(year, 11, november_sunday, 9)
    offset = -7 if start <= stamp < end else -8
    return time.gmtime(stamp + offset * 3600)
