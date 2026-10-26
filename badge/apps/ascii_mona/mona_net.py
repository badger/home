"""Optional public-profile lookup on api.github.com to tune a Mona.

The firmware's async fetch downloads the profile while frames keep running,
the way the Badge app does. Where there is no fetch module, a blocking
requests.get runs instead, after the ISS app's wifi.connect() polling. Only
public fields are kept, and a GITHUB_TOKEN from secrets is sent to
api.github.com and nowhere else.
"""

import json
import os

import mona_dna

API = "https://api.github.com/users/"
USER_AGENT = "GitHub Universe Badge 2026"
STATE_DIR = "/state"
TEMP = "/state/ascii_mona_profile.tmp"
KEEP = (
    "login", "name", "bio", "company", "location", "type", "created_at",
    "public_repos", "public_gists", "followers", "following", "site_admin",
)
TEXT_LIMIT = 160
WIFI_TIMEOUT = 10
WIFI_RETRIES = 100000
REQUEST_TIMEOUT = 10
GIVE_UP_MS = 30000

IDLE = 0
CONNECTING = 1
FETCHING = 2


def load_module(name):
    """A firmware module, or None where this runtime lacks it."""
    try:
        if name == "fetch":
            import fetch as module
        elif name == "requests":
            import requests as module
        elif name == "wifi":
            import wifi as module
        elif name == "missing_details":
            import missing_details as module
        elif name == "secrets":
            import secrets as module
        else:
            return None
    except Exception:
        return None
    return module


def token(load=load_module):
    secrets = load("secrets")
    try:
        return str(getattr(secrets, "GITHUB_TOKEN", "") or "").strip()
    except Exception:
        return ""


def headers_for(url, secret=""):
    headers = {"User-Agent": USER_AGENT}
    if secret and url.startswith("https://api.github.com/"):
        headers["Authorization"] = "Bearer " + secret
    return headers


def slim(data):
    """The public profile fields ASCII Mona uses, or None if it isn't one."""
    if not isinstance(data, dict):
        return None
    login = data.get("login")
    if not isinstance(login, str) or not mona_dna.valid_handle(login):
        return None
    out = {}
    for key in KEEP:
        value = data.get(key)
        if isinstance(value, (bool, int)):
            out[key] = value
        elif isinstance(value, str):
            out[key] = mona_dna.clean_text(value, TEXT_LIMIT)
    return out


def reason(data, code=0):
    """A short, drawable reason a lookup failed."""
    if code == 404:
        return "no such GitHub user"
    message = data.get("message") if isinstance(data, dict) else None
    if isinstance(message, str) and message:
        low = message.lower()
        if "rate limit" in low:
            return "GitHub rate limit, try later"
        if "not found" in low:
            return "no such GitHub user"
        return mona_dna.clean_text(message, 40)
    if code == 403 or code == 429:
        return "GitHub rate limit, try later"
    if code and code != 200:
        return "GitHub said %d" % code
    if not isinstance(data, dict):
        return "bad reply from GitHub"
    return "no such GitHub user"


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


class Lookup:
    """One profile lookup at a time, advanced a step per frame."""

    def __init__(self, load=None):
        self.load = load or load_module
        self.state = IDLE
        self.handle = ""
        self.request = None
        self.requests = None
        self.wifi = None
        self.started = 0
        self.painted = False
        self.status = ""

    @property
    def busy(self):
        return self.state != IDLE

    def cancel(self):
        self.state = IDLE
        self.request = None
        self.painted = False

    def _fail(self, why):
        self.cancel()
        self.status = why
        return ("failed", why)

    def _missing_wifi(self):
        details = self.load("missing_details")
        if details is None:
            return False
        try:
            return bool(details.missing("WIFI_SSID"))
        except Exception:
            return False

    def _connected(self):
        try:
            return bool(self.wifi.is_connected())
        except Exception:
            return False

    def start(self, handle, now):
        """Begin a lookup; returns ("failed", reason) straight away or None."""
        self.cancel()
        handle = mona_dna.clean_handle(handle)
        if not handle:
            return self._fail("no handle to look up")
        self.handle = handle
        self.started = now
        self.status = "asking GitHub..."
        url = API + handle
        fetch = self.load("fetch")
        if fetch is not None:
            if self._missing_wifi():
                return self._fail("add Wi-Fi in Settings")
            try:
                os.mkdir(STATE_DIR)
            except OSError:
                pass
            try:
                fetch.AsyncFetch.MAX_HEADER_BYTES = 8192
            except Exception:
                pass
            try:
                self.request = fetch.url(url, headers=headers_for(url, token(self.load))).to(TEMP)
            except Exception as err:
                return self._fail("fetch failed: %s" % err)
            self.state = FETCHING
            return None
        self.requests = self.load("requests")
        if self.requests is None:
            return self._fail("no network on this badge")
        self.wifi = self.load("wifi")
        if self.wifi is not None and not self._connected():
            if self._missing_wifi():
                return self._fail("add Wi-Fi in Settings")
            try:
                self.wifi.connect(timeout=WIFI_TIMEOUT, retries=WIFI_RETRIES)
            except Exception as err:
                return self._fail("Wi-Fi: %s" % err)
            self.state = CONNECTING
            self.status = "connecting to Wi-Fi..."
            return None
        self.state = FETCHING
        return None

    def update(self, now):
        """Advance; returns ("profile", dict) or ("failed", reason) once."""
        if self.state == IDLE:
            return None
        if now - self.started > GIVE_UP_MS:
            return self._fail("GitHub timed out")
        try:
            if self.state == CONNECTING:
                return self._connecting()
            if self.request is not None:
                return self._poll()
            return self._get()
        except Exception as err:
            return self._fail(mona_dna.clean_text("lookup failed: %s" % err, 40))

    def _connecting(self):
        saying = ""
        try:
            code, saying = self.wifi.status()
            if code >= 0:
                saying = ""
        except Exception:
            saying = ""
        if self.wifi.connect():
            self.state = FETCHING
            self.status = "asking GitHub..."
            return None
        if saying:
            self.status = mona_dna.clean_text("Wi-Fi: %s" % saying, 40)
        return None

    def _poll(self):
        request = self.request
        if request:
            self.request = None
            data = None
            try:
                with open(TEMP) as file:
                    data = json.load(file)
            except (OSError, ValueError):
                data = None
            _remove(TEMP)
            return self._finish(data, 0)
        error = getattr(request, "error", None)
        if error:
            return self._fail(mona_dna.clean_text(str(error), 40) or "fetch failed")
        state = getattr(request, "state", None)
        if isinstance(state, str) and state not in ("Idle", "Fetching"):
            self.status = mona_dna.clean_text(state, 40)
        return None

    def _get(self):
        if not self.painted:
            # a blocking request stalls the frame, so paint the status first
            self.painted = True
            return None
        url = API + self.handle
        response = self.requests.get(url, headers=headers_for(url, token(self.load)), timeout=REQUEST_TIMEOUT)
        code = 0
        data = None
        try:
            code = response.status_code
            try:
                data = response.json()
            except Exception:
                data = None
        finally:
            try:
                response.close()
            except Exception:
                pass
        if code != 200:
            return self._fail(reason(data, code))
        return self._finish(data, code)

    def _finish(self, data, code):
        profile = slim(data)
        if profile is None:
            return self._fail(reason(data, code))
        self.cancel()
        self.status = ""
        return ("profile", profile)
