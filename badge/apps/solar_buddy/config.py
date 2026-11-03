"""Non-secret settings and validation shared by the badge and host tools."""

import json
import math

DEVICE_SECRETS = "/state/solar_buddy_secrets.json"
# ENOENT is 2 on the badge and CPython; the canvas's WebAssembly runtime reports 44.
MISSING_FILE_ERRNOS = (2, 44)


def defaults():
    return {
        "mode": "demo",
        "poll_interval_ms": 10000,
        "request_timeout_ms": 4000,
        "stale_after_ms": 45000,
        "sensor_max_age_s": 180,
        "stability_ms": 30000,
        "reserve_w": 100,
        "happy_w": 800,
        "excited_w": 2000,
        "mood_hysteresis_w": 100,
        "import_threshold_w": 25,
        "milestone_w": 4000,
        "appliances": [
            {"name": "Dishwasher", "watts": 1500},
            {"name": "Washing machine", "watts": 2000},
            {"name": "EV charging", "watts": 2300},
            {"name": "Small appliance", "watts": 500},
        ],
    }


def number(value, label, minimum=0, maximum=1000000):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(label + " must be a number")
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(label + " is outside its allowed range")
    return value


def read_json(path, optional=False):
    try:
        with open(path, "r") as handle:
            result = json.load(handle)
    except OSError as exc:
        if optional and exc.args and exc.args[0] in MISSING_FILE_ERRNOS:
            return None
        raise
    if not isinstance(result, dict):
        raise ValueError("Configuration must be a JSON object")
    return result


def load_settings(path=None):
    settings = defaults()
    if path:
        supplied = read_json(path, optional=True)
        if supplied is not None:
            for key, value in supplied.items():
                if key not in settings:
                    raise ValueError("Unknown setting: " + key)
                settings[key] = value
    return validate_settings(settings)


def validate_settings(settings):
    if settings["mode"] not in ("demo", "live"):
        raise ValueError("mode must be demo or live")
    for key in ("poll_interval_ms", "request_timeout_ms", "stale_after_ms",
                "sensor_max_age_s", "stability_ms"):
        number(settings[key], key, 1, 3600000)
        if int(settings[key]) != settings[key]:
            raise ValueError(key + " must be a whole number")
    if settings["poll_interval_ms"] < 1000:
        raise ValueError("poll_interval_ms must be at least 1000")
    if settings["request_timeout_ms"] < 100:
        raise ValueError("request_timeout_ms must be at least 100")
    cycle_budget = settings["poll_interval_ms"] + 3 * settings["request_timeout_ms"]
    if settings["stale_after_ms"] <= cycle_budget:
        raise ValueError("stale_after_ms must exceed poll interval + 3 timeouts")
    for key in ("reserve_w", "happy_w", "excited_w", "mood_hysteresis_w",
                "import_threshold_w", "milestone_w"):
        number(settings[key], key)
    if not 0 < settings["happy_w"] < settings["excited_w"]:
        raise ValueError("Mood thresholds must satisfy 0 < happy_w < excited_w")
    if settings["mood_hysteresis_w"] >= min(
            settings["happy_w"], settings["excited_w"] - settings["happy_w"]):
        raise ValueError("mood_hysteresis_w is too large for the thresholds")
    appliances = settings["appliances"]
    if not isinstance(appliances, list) or not 1 <= len(appliances) <= 12:
        raise ValueError("Configure between 1 and 12 appliances")
    names = []
    for appliance in appliances:
        if not isinstance(appliance, dict) or set(appliance) != {"name", "watts"}:
            raise ValueError("Each appliance needs only name and watts")
        name = appliance["name"]
        if (not isinstance(name, str) or not 1 <= len(name) <= 24
                or not all(32 <= ord(ch) < 127 for ch in name) or not name.strip()):
            raise ValueError("Appliance names must be 1-24 printable ASCII characters")
        if name in names:
            raise ValueError("Appliance names must be unique")
        names.append(name)
        number(appliance["watts"], "Appliance watts", 1)
    return settings


def is_ipv4(value):
    if not isinstance(value, str):
        return False
    pieces = value.split(".")
    return (len(pieces) == 4 and all(
        p and all("0" <= ch <= "9" for ch in p) and len(p) <= 3
        and 0 <= int(p) <= 255 and (p == "0" or not p.startswith("0"))
        for p in pieces))


def parse_url(value):
    if not isinstance(value, str) or not value:
        raise ValueError("Set the Home Assistant base_url")
    if any(ord(ch) <= 32 or ord(ch) >= 127 for ch in value):
        raise ValueError("base_url must contain only printable ASCII without spaces")
    if any(ch in value for ch in "@?#\\[]"):
        raise ValueError("base_url cannot contain credentials, query, fragment, or IPv6")
    parts = value.rstrip("/").split("://")
    if len(parts) != 2 or parts[0] not in ("http", "https"):
        raise ValueError("base_url must begin with http:// or https://")
    scheme, rest = parts
    authority, separator, path = rest.partition("/")
    pieces = authority.split(":")
    if len(pieces) > 2:
        raise ValueError("Only IPv4 addresses and DNS hostnames are supported")
    host = pieces[0]
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-."
    if not host or any(ch not in allowed for ch in host):
        raise ValueError("Invalid Home Assistant hostname")
    port = 443 if scheme == "https" else 80
    if len(pieces) == 2:
        if not pieces[1] or not all("0" <= ch <= "9" for ch in pieces[1]):
            raise ValueError("Invalid Home Assistant port")
        port = int(pieces[1])
        number(port, "Home Assistant port", 1, 65535)
    return scheme, host, port, "/" + path if separator else "", authority


def validate_entity(value):
    allowed = "abcdefghijklmnopqrstuvwxyz0123456789_"
    if (not isinstance(value, str) or not value.startswith("sensor.")
            or not value[7:] or any(ch not in allowed for ch in value[7:])):
        raise ValueError("Select an actual sensor entity ID from Home Assistant")
    return value


def validate_token(token):
    if (not isinstance(token, str) or not 1 <= len(token) <= 4096
            or any(not 32 < ord(ch) < 127 for ch in token)):
        raise ValueError("Set a nonempty Home Assistant token without whitespace")
    return token


def validate_secrets(secrets):
    if not isinstance(secrets, dict):
        raise ValueError("Run configure_home_assistant.py first")
    allowed = {"base_url", "token", "connect_ip", "entities", "allow_insecure_http",
               "ca_file"}
    if set(secrets) - allowed:
        raise ValueError("Unknown field in Home Assistant configuration")
    scheme, host, _port, _prefix, _authority = parse_url(secrets.get("base_url"))
    validate_token(secrets.get("token"))
    ip = secrets.get("connect_ip", host)
    if not is_ipv4(ip):
        raise ValueError("Set connect_ip to a numeric IPv4 address to avoid blocking DNS")
    if scheme == "http" and secrets.get("allow_insecure_http") is not True:
        raise ValueError("HTTP exposes the token; explicitly allow it on a trusted LAN")
    entities = secrets.get("entities")
    if not isinstance(entities, dict) or set(entities) != {"solar", "import", "export"}:
        raise ValueError("Configure solar, import, and export entity IDs")
    values = [validate_entity(entities[key]) for key in ("solar", "import", "export")]
    if len(set(values)) != 3:
        raise ValueError("Solar, import, and export must be three different power sensors")
    ca_file = secrets.get("ca_file")
    if ca_file is not None and (not isinstance(ca_file, str) or not ca_file):
        raise ValueError("ca_file must be a certificate file path")
    return secrets


def load_secrets(path, missing="Run configure_home_assistant.py first"):
    secrets = read_json(path, optional=True)
    if secrets is None:
        raise ValueError(missing)
    return validate_secrets(secrets)
