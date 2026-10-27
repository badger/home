"""Non-blocking JSON GETs for status apps.

On the badge one fetch.AsyncFetch per host keeps its TLS connection alive
between polls, so only the first request pays for a handshake. The
simulator's fetch module only implements fetch.url(), which is used there.
"""

import json
import time

import fetch

try:
    import wifi
except ImportError:
    wifi = None

NATIVE = hasattr(fetch.AsyncFetch, "update")

# A short attempt so failures report quickly, and enough retries that the
# firmware never gives up and parks the app on its fatal error screen.
WIFI_TIMEOUT = 10
WIFI_RETRIES = 100000


def split_url(url):
    if url.startswith("https://"):
        tls, rest = True, url[8:]
    elif url.startswith("http://"):
        tls, rest = False, url[7:]
    else:
        raise ValueError("URL must start with https://")
    host_port, _, path = rest.partition("/")
    host, _, port = host_port.partition(":")
    if not host:
        raise ValueError("URL has no host")
    port = int(port) if port else (443 if tls else 80)
    return tls, host, port, ("/" + path).rstrip("/")


def describe(error):
    """A short, human-readable reason for a network exception."""
    code = error.args[0] if isinstance(error, OSError) and error.args else None
    if code in (110, 116):
        return "timed out"
    if code in (111, 104, 103):
        return "connection refused"
    if code == 113:
        return "host unreachable"
    if isinstance(code, int) and code in (-2, -3, -6, -202):
        return "DNS lookup failed"
    if isinstance(code, int) and code < -100:
        return "TLS error %d" % code
    text = str(error) or type(error).__name__
    if "max_bytes" in text:
        return "response too large"
    return text[:60]


def error_message(status, body):
    """'HTTP 403: detail' using the server's JSON error message when present."""
    detail = ""
    try:
        data = json.loads(body)
        problem = data.get("error") if isinstance(data, dict) else None
        if isinstance(problem, dict):
            detail = problem.get("message") or problem.get("code") or ""
        elif isinstance(problem, str):
            detail = problem
        elif isinstance(data, dict) and data.get("detail"):
            detail = str(data["detail"])
    except (ValueError, TypeError):
        pass
    detail = str(detail).replace("\n", " ")[:80]
    return "HTTP %d: %s" % (status, detail) if detail else "HTTP %d" % status


class WiFi:
    """Drives the firmware's Wi-Fi state machine one step per frame."""

    def __init__(self):
        self.started = False

    def ready(self):
        if wifi is None:
            return True
        if not self.started:
            self.started = True
            wifi.connect(timeout=WIFI_TIMEOUT, retries=WIFI_RETRIES)
        return bool(wifi.connect())

    def status(self):
        if wifi is None:
            return "No Wi-Fi module"
        try:
            return wifi.status()[1]
        except (OSError, KeyError, IndexError):
            return "Connecting to Wi-Fi"


class Client:
    """Runs one GET at a time against base_url.

    start(path) begins a request. poll() returns None while it is pending,
    then (status, payload): payload is parsed JSON for HTTP 200, otherwise an
    error message. A status of 0 means the request never got an HTTP answer.
    """

    def __init__(self, base_url, headers=None, timeout=15, max_bytes=32 * 1024):
        self.base_url = base_url.rstrip("/")
        self.tls, self.host, self.port, self.prefix = split_url(self.base_url)
        self.headers = dict(headers or {})
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.busy = False
        self.date = None  # the last response's Date header, when available
        self._native = None
        self._shim = None

    def start(self, path):
        if self.busy:
            raise RuntimeError("A request is already running")
        self.busy = True
        if NATIVE:
            if self._native is None:
                self._native = fetch.AsyncFetch(
                    self.host, self.port, use_tls=self.tls,
                    timeout=self.timeout, max_bytes=self.max_bytes)
                # Report HTTP errors as results instead of raising them.
                self._native.on_error(lambda _: True)
            self._native.fetch(self.prefix + path, headers=self.headers)
        else:
            self._shim = fetch.url(self.base_url + path, headers=self.headers)

    def poll(self):
        if not self.busy:
            return None
        return self._poll_native() if NATIVE else self._poll_shim()

    def cancel(self):
        if self._native is not None:
            self._native.reset()
        self._shim = None
        self.busy = False

    def _finish(self, status, payload):
        self.busy = False
        return status, payload

    def _poll_native(self):
        request = self._native
        try:
            state = request.update()
        except Exception as error:  # noqa: BLE001 - network errors surface here
            request.reset()
            return self._finish(0, describe(error))
        if state == fetch.AsyncFetch.FETCHING:
            return None
        status = request.http_status or 0
        headers = request.http_response_headers or {}
        for key in headers:
            if key.lower() == "date":
                self.date = headers[key]
        if state == fetch.AsyncFetch.DONE:
            try:
                return self._finish(status, request.to_json())
            except ValueError:
                return self._finish(0, "bad JSON from server")
        try:
            body = bytes(request.body[:512])
        except (ValueError, TypeError):
            body = b""
        return self._finish(status, error_message(status, body))

    def _poll_shim(self):
        request = self._shim
        if request:
            try:
                return self._finish(200, request.json())
            except ValueError:
                return self._finish(0, "bad JSON from server")
        problem = request.error
        if problem:
            text = str(problem)
            status = 0
            if text.startswith("HTTP "):
                digits = text[5:].split(" ")[0].rstrip(":")
                if digits.isdigit():
                    status = int(digits)
            return self._finish(status, text[:80])
        return None


class Poller:
    """Repeats one GET on an interval, backing off after failures."""

    def __init__(self, client, path, every_ms, max_backoff_ms=60000):
        self.client = client
        self.path = path
        self.every_ms = every_ms
        self.max_backoff_ms = max_backoff_ms
        self.next_at = None
        self.failures = 0
        self.data = None
        self.error = None
        self.status = None
        self.updated_at = None
        self.paused = False

    def due(self, now):
        return (not self.paused and not self.client.busy
                and (self.next_at is None or time.ticks_diff(now, self.next_at) >= 0))

    def refresh(self):
        self.paused = False
        self.next_at = None

    def step(self, now):
        """Advance the poll. Returns True on the frame new data arrives."""
        if self.due(now):
            self.client.start(self.path)
            return False
        result = self.client.poll()
        if result is None:
            return False
        self.status, payload = result
        if self.status == 200:
            self.data, self.error = payload, None
            self.updated_at = now
            self.failures = 0
            self.next_at = time.ticks_add(now, self.every_ms)
            return True
        self.error = payload
        self.failures += 1
        delay = min(self.every_ms * (2 ** min(self.failures, 4)), self.max_backoff_ms)
        if self.status in (401, 403):
            # A rejected credential will not fix itself; wait for SELECT.
            self.paused = True
        elif self.status == 429:
            delay = self.max_backoff_ms
        self.next_at = time.ticks_add(now, delay)
        return False
