"""Instantaneous power, source freshness, and hysteretic moods; no hardware imports."""

import math

UNIT_FACTORS = {"W": 1.0, "kW": 1000.0, "MW": 1000000.0}


def to_watts(state, unit):
    if unit not in UNIT_FACTORS:
        raise ValueError("Expected instantaneous W, kW, or MW; never Wh or kWh")
    if isinstance(state, bool) or state is None:
        raise ValueError("Power sensor is not numeric")
    try:
        value = float(state) * UNIT_FACTORS[unit]
    except (ValueError, TypeError):
        raise ValueError("Power sensor is unknown, unavailable, or non-numeric")
    if not math.isfinite(value) or value < 0:
        raise ValueError("Power sensor must be finite and nonnegative")
    return value


def reading(solar_w, import_w, export_w):
    values = [to_watts(value, "W") for value in (solar_w, import_w, export_w)]
    solar_w, import_w, export_w = values
    house_w = solar_w + import_w - export_w
    if house_w < 0:
        raise ValueError("Inconsistent sensors: export exceeds solar plus import")
    return {"solar_w": solar_w, "import_w": import_w, "export_w": export_w,
            "house_w": house_w, "surplus_w": export_w}


def _leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _unix(year, month, day, hour, minute, second):
    if not 1970 <= year <= 2199 or not 1 <= month <= 12:
        raise ValueError("Invalid timestamp date")
    lengths = (31, 29 if _leap(year) else 28, 31, 30, 31, 30,
               31, 31, 30, 31, 30, 31)
    if (not 1 <= day <= lengths[month - 1] or not 0 <= hour <= 23
            or not 0 <= minute <= 59 or not 0 <= second <= 59):
        raise ValueError("Invalid timestamp component")
    days = sum(366 if _leap(y) else 365 for y in range(1970, year))
    days += sum(lengths[:month - 1]) + day - 1
    return ((days * 24 + hour) * 60 + minute) * 60 + second


def iso_timestamp(value):
    if not isinstance(value, str) or len(value) < 20:
        raise ValueError("Missing or invalid sensor timestamp")
    try:
        if (value[4] != "-" or value[7] != "-" or value[10] != "T"
                or value[13] != ":" or value[16] != ":"):
            raise ValueError("Invalid ISO timestamp")
        result = _unix(int(value[:4]), int(value[5:7]), int(value[8:10]),
                       int(value[11:13]), int(value[14:16]), int(value[17:19]))
        tail = value[19:]
        if tail.startswith("."):
            index = 1
            while index < len(tail) and "0" <= tail[index] <= "9":
                index += 1
            if index == 1:
                raise ValueError("Invalid timestamp fraction")
            tail = tail[index:]
        if tail == "Z":
            return result
        if len(tail) != 6 or tail[0] not in "+-" or tail[3] != ":":
            raise ValueError("Timestamp must include a timezone")
        hours, minutes = int(tail[1:3]), int(tail[4:6])
        if not 0 <= hours <= 23 or not 0 <= minutes <= 59:
            raise ValueError("Invalid timestamp timezone")
        offset = (hours * 60 + minutes) * 60
        return result - offset if tail[0] == "+" else result + offset
    except (ValueError, IndexError):
        raise ValueError("Invalid sensor timestamp")


def http_timestamp(value):
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    try:
        fields = value.split()
        if len(fields) != 6 or fields[-1] != "GMT":
            raise ValueError("Invalid Date header")
        hour, minute, second = [int(x) for x in fields[4].split(":")]
        return _unix(int(fields[3]), months.index(fields[2]) + 1,
                     int(fields[1]), hour, minute, second)
    except (AttributeError, ValueError, IndexError):
        raise ValueError("Missing or invalid HTTP Date; cannot verify sensor freshness")


def decode_report(payload, entity, headers):
    """Return (watts, seconds since the sensor's last report) for a valid power sensor."""
    if not isinstance(payload, dict) or payload.get("entity_id") != entity:
        raise ValueError("Home Assistant returned the wrong sensor")
    attrs = payload.get("attributes")
    if not isinstance(attrs, dict):
        raise ValueError(entity + ": missing attributes")
    device_class = attrs.get("device_class")
    if device_class not in (None, "power"):
        raise ValueError(entity + ": device_class is not power")
    value = to_watts(payload.get("state"), attrs.get("unit_of_measurement"))
    reported = payload.get("last_reported") or payload.get("last_updated")
    age = http_timestamp(headers.get("date")) - iso_timestamp(reported)
    if age < -30:
        raise ValueError(entity + ": timestamp is ahead of the server clock")
    return value, age


def check_freshness(entities, ages, max_age_s):
    """Judge report ages for solar, grid import, grid export; a leading subset is allowed.

    Integrations such as DSMR only write a meter direction when its value changes, so
    the direction that is not flowing (usually 0 W) can stay unreported for hours while
    the other updates every second. The two grid directions therefore share one
    deadline: a recent report from either proves the meter is alive.
    """
    if ages[0] > max_age_s:
        raise ValueError(entities[0] + ": stale sensor report")
    if len(ages) > 2 and min(ages[1], ages[2]) > max_age_s:
        raise ValueError(entities[1] + " and " + entities[2] + ": stale sensor reports")


class Mood:
    def __init__(self, settings):
        self.settings = settings
        self.state = "offline"

    def update(self, sample):
        if sample is None:
            self.state = "offline"
            return self.state
        cfg = self.settings
        if sample["import_w"] > cfg["import_threshold_w"]:
            self.state = "sleepy"
            return self.state
        if self.state == "sleepy" and sample["import_w"] > 0:
            return self.state
        surplus = sample["surplus_w"]
        happy, excited, band = cfg["happy_w"], cfg["excited_w"], cfg["mood_hysteresis_w"]
        if self.state in ("offline", "sleepy"):
            self.state = ("excited" if surplus >= excited else
                          "happy" if surplus >= happy else "neutral")
        elif self.state == "excited":
            if surplus < happy - band:
                self.state = "neutral"
            elif surplus < excited - band:
                self.state = "happy"
        elif self.state == "happy":
            if surplus >= excited + band:
                self.state = "excited"
            elif surplus < happy - band:
                self.state = "neutral"
        elif surplus >= excited + band:
            self.state = "excited"
        elif surplus >= happy + band:
            self.state = "happy"
        return self.state
