"""Read-only Home Assistant polling, with independent Wi-Fi recovery."""

import sys

from clock import elapsed
from energy import check_freshness, decode_report, reading

if sys.platform == "webassembly":
    from browser_http import HttpClient
else:
    from http_client import HttpClient


class BadgeWifi:
    def __init__(self):
        import network
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        self.started = None
        self.ssid = None
        self.password = None
        if not self.wlan.isconnected():
            self._credentials()

    def _credentials(self):
        import secrets
        self.ssid = getattr(secrets, "WIFI_SSID", "")
        self.password = getattr(secrets, "WIFI_PASSWORD", "")
        if not self.ssid:
            raise ValueError("Configure WIFI_SSID in the badge's existing secrets.py")

    def tick(self, now):
        if self.wlan.isconnected():
            self.started = None
            return None
        if self.ssid is None:
            self._credentials()
        if self.started is None or elapsed(now, self.started) >= 15000:
            if self.started is not None:
                self.wlan.disconnect()
            self.wlan.connect(self.ssid, self.password)
            self.started = now
        status = self.wlan.status()
        if status < 0:
            return "Wi-Fi failed (status %d); retrying" % status
        return "Connecting to Wi-Fi"


class HomeAssistant:
    def __init__(self, settings, credentials, wifi=None, http=None):
        self.settings = settings
        self.credentials = credentials
        self.wifi = wifi
        self.http = http or HttpClient(credentials, settings["request_timeout_ms"])
        self.entities = [credentials["entities"][key] for key in ("solar", "import", "export")]
        self.last_attempt = None
        self.delay = 0
        self.failures = 0
        self.reports = []
        self.active = False
        self.last_wifi_error = None

    def _fail(self, message):
        self.http.close()
        self.active = False
        self.reports = []
        self.failures = min(self.failures + 1, 5)
        self.delay = min(60000, self.settings["poll_interval_ms"] * (2 ** (self.failures - 1)))
        return "error", message

    def tick(self, now):
        try:
            if self.wifi is not None:
                problem = self.wifi.tick(now)
                if problem:
                    self.http.close()
                    self.active = False
                    self.reports = []
                    self.last_attempt = None
                    if problem != self.last_wifi_error:
                        self.last_wifi_error = problem
                        return "error", problem
                    return None
                self.last_wifi_error = None
            if not self.active:
                if (self.last_attempt is not None
                        and elapsed(now, self.last_attempt) < self.delay):
                    return None
                self.last_attempt = now
                self.reports = []
                self.http.start("/api/states/" + self.entities[0], now)
                self.active = True
                return None
            response = self.http.step(now)
            if response is None:
                return None
            payload, headers = response
            entity = self.entities[len(self.reports)]
            self.reports.append(decode_report(payload, entity, headers))
            check_freshness(self.entities, [age for _watts, age in self.reports],
                            self.settings["sensor_max_age_s"])
            if len(self.reports) < 3:
                self.http.start("/api/states/" + self.entities[len(self.reports)], now)
                return None
            sample = reading(*[watts for watts, _age in self.reports])
            self.active = False
            self.failures = 0
            self.delay = self.settings["poll_interval_ms"]
            self.last_attempt = now
            return "reading", sample
        except (OSError, ValueError, TypeError, KeyError) as exc:
            message = str(exc).replace(self.credentials["token"], "[redacted]")
            return self._fail(message)

    def refresh(self):
        self.close()
        self.last_attempt = None

    def close(self):
        self.http.close()
        self.active = False
        self.reports = []
