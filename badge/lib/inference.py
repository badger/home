"""A shared inference engine for badge apps.

It asks an OpenAI-compatible chat completions gateway (CLIProxyAPI, the badge
bridge in front of it, or any other compatible server) a question without
stalling the frame loop:

    import sys
    if "/system/lib" not in sys.path:
        sys.path.append("/system/lib")
    import inference

    engine = inference.from_secrets()       # or inference.Engine(url, key, model)
    engine.ask("Summarise this in one line: ...")

    def update():
        state = engine.update()             # once a frame
        if state == inference.DONE:
            screen.text(engine.answer, 10, 10)
        elif state == inference.FAILED:
            screen.text(engine.error, 10, 10)

On the badge the request runs over the firmware's fetch.AsyncFetch, a little
each frame, and the connection is reused between questions. Where that is
missing (the simulators) it falls back to a blocking requests.post, sent on the
frame after ask() so a waiting screen can be drawn first.

See badge/lib/README.md for the secrets.py settings and the full API.
"""

import errno
import json
import time

try:
    import fetch
except ImportError:
    fetch = None

__version__ = "1.0.0"

DEFAULT_MODEL = "claude-opus-5-5"

SYSTEM_PROMPT = (
    "You are the voice of a GitHub Universe conference badge with a small "
    "screen. Answer in plain text of at most 60 words. Do not use markdown, "
    "lists, emoji or code blocks."
)

IDLE = 0
BUSY = 1
DONE = 2
FAILED = 3

# Punctuation models like that the badge fonts cannot draw
_FOLD = {
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u2032": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u2033": '"',
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-",
    "\u2014": "-", "\u2212": "-", "\u2022": "-", "\u00b7": "-",
    "\u2026": "...", "\u2192": "->", "\u00d7": "x", "\t": " ",
    "\u00a0": " ", "\u2009": " ", "\u202f": " ",
    "\u00df": "ss", "\u00e6": "ae", "\u00c6": "AE",
}
_ACCENTED = "ÀÁÂÃÄÅàáâãäåÇçÈÉÊËèéêëÌÍÎÏìíîïÑñÒÓÔÕÖØòóôõöøÙÚÛÜùúûüÝýÿ"
_UNACCENTED = "AAAAAAaaaaaaCcEEEEeeeeIIIIiiiiNnOOOOOOooooooUUUUuuuuYyy"


def plain(text):
    """Fold text into what the badge fonts can draw, and drop markdown."""
    kept = []
    for ch in text:
        if " " <= ch <= "~" or ch == "\n":
            kept.append(ch)
        elif ch in _FOLD:
            kept.append(_FOLD[ch])
        else:
            at = _ACCENTED.find(ch)
            if at >= 0:
                kept.append(_UNACCENTED[at])
    text = "".join(kept)
    for mark in ("**", "__", "`"):
        text = text.replace(mark, "")

    lines = []
    for line in text.split("\n"):
        line = line.strip()
        while line.startswith("#"):
            line = line[1:].lstrip()
        if line.startswith("* "):
            line = "- " + line[2:]
        # at most one blank line in a row
        if line or (lines and lines[-1]):
            lines.append(line)
    return "\n".join(lines).strip()


def endpoint(url, name="The gateway URL"):
    """Split a gateway URL into (tls, host, port, path) for chat completions.

    Takes the gateway's base URL, its /v1 URL, or the full chat completions URL.
    name is what error messages call the URL, such as a secrets.py setting.
    """
    url = url.strip()
    if url.startswith("https://"):
        tls, rest = True, url[8:]
    elif url.startswith("http://"):
        tls, rest = False, url[7:]
    else:
        raise ValueError("%s must start with https:// or http://" % name)

    host_port, _, path = rest.partition("/")
    host, _, port = host_port.partition(":")
    if not host:
        raise ValueError("%s has no host name" % name)
    try:
        port = int(port) if port else (443 if tls else 80)
    except ValueError:
        raise ValueError("%s has a bad port number" % name) from None

    path = "/" + path.strip("/")
    if not path.endswith("/chat/completions"):
        if not path.endswith("/v1"):
            path = path.rstrip("/") + "/v1"
        path += "/chat/completions"
    return tls, host, port, path


def _clip(text, length):
    return text if len(text) <= length else text[: length - 3].rstrip() + "..."


def _problem(status, reply, raw, engine):
    """Turn a gateway's error reply into a short message for the screen."""
    detail = ""
    if isinstance(reply, dict):
        error = reply.get("error", reply.get("message", ""))
        if isinstance(error, dict):
            detail = str(error.get("message") or error.get("code") or error.get("type") or "")
        else:
            detail = str(error)
    elif raw:
        try:
            detail = bytes(raw[:200]).decode()
        except UnicodeError:
            detail = ""
    detail = plain(detail)

    if status in (401, 403):
        hint = "The gateway refused the key. Check %s." % engine.key_name
    elif status == 404:
        hint = "There is no chat endpoint at %s." % engine.url_name
    elif status == 429:
        hint = "The gateway is out of quota for now. Try another model."
    elif status == 400 and "model" in detail.lower():
        hint = "This key cannot use %s." % engine.model
    elif status and status >= 500:
        hint = "The gateway ran into a problem."
    else:
        hint = "The gateway turned the question down."

    message = "%s (HTTP %s)" % (hint, status)
    if detail:
        message += "\n" + _clip(detail, 160)
    return message


def _async_capable():
    # The simulators stand in a constants-only AsyncFetch, without fetch()
    return fetch is not None and hasattr(getattr(fetch, "AsyncFetch", None), "fetch")


class ConfigError(ValueError):
    """secrets.py has no usable gateway settings."""


def _setting(name):
    try:
        import secrets
    except ImportError:
        return ""
    return str(getattr(secrets, name, "") or "").strip()


def settings():
    """Where to send questions, from secrets.py: (url, key, url_name, key_name).

    GATEWAY_URL and GATEWAY_KEY come first. Without them, a badge set up for the
    badge bridge (BADGE_BRIDGE_URL and BADGE_BRIDGE_TOKEN) uses the bridge's
    /gateway route, so one bridge configuration serves every app. The key always
    comes from the same pair as the URL, so a bridge token is never sent to a
    different gateway.
    """
    url = _setting("GATEWAY_URL")
    if url:
        return url, _setting("GATEWAY_KEY"), "GATEWAY_URL", "GATEWAY_KEY"
    bridge = _setting("BADGE_BRIDGE_URL")
    if bridge:
        return bridge.rstrip("/") + "/gateway", _setting("BADGE_BRIDGE_TOKEN"), "BADGE_BRIDGE_URL", "BADGE_BRIDGE_TOKEN"
    raise ConfigError("Set GATEWAY_URL (or BADGE_BRIDGE_URL) in secrets.py")


def missing():
    """secrets.py names to ask for with missing_details.show(), or []."""
    return [] if _setting("GATEWAY_URL") or _setting("BADGE_BRIDGE_URL") else ["GATEWAY_URL"]


def models():
    """The models listed in GATEWAY_MODEL (comma-separated), or [DEFAULT_MODEL]."""
    return [name.strip() for name in _setting("GATEWAY_MODEL").split(",") if name.strip()] or [DEFAULT_MODEL]


def from_secrets(model=None, **options):
    """An Engine set up from secrets.py. Raises ConfigError when it can't be.

    model defaults to the first of models(); options go to Engine (system,
    max_tokens, timeout).
    """
    url, key, url_name, key_name = settings()
    try:
        endpoint(url, url_name)
    except ValueError as reason:
        raise ConfigError(str(reason)) from None
    engine = Engine(url, key, model or models()[0], **options)
    engine.url_name, engine.key_name = url_name, key_name
    return engine


class Engine:
    """Asks one chat completions gateway, one question at a time."""

    # max_tokens leaves room for the tokens a model like Opus spends before
    # it answers; 200 cut its 60-word answers short
    def __init__(self, url, key="", model=DEFAULT_MODEL, system=SYSTEM_PROMPT,
                 max_tokens=400, timeout=45):
        self.tls, self.host, self.port, self.path = endpoint(url)
        self.url = "%s://%s:%d%s" % ("https" if self.tls else "http", self.host, self.port, self.path)
        self.key = (key or "").strip()
        self.model = model or DEFAULT_MODEL
        self.system = system
        self.max_tokens = max_tokens
        self.timeout = timeout          # seconds without data before giving up
        self.url_name = "the gateway URL"   # what error hints call the settings
        self.key_name = "the gateway key"

        self.state = IDLE
        self.answer = None              # the last answer, as plain text
        self.error = None               # or why there isn't one
        self.truncated = False          # the answer hit max_tokens
        self.elapsed = 0                # ms the last request took

        self._started = 0
        self._client = None             # fetch.AsyncFetch, kept so its connection is reused
        self._body = None               # a request waiting for the blocking fallback
        self._armed = False

    @property
    def busy(self):
        return self.state == BUSY

    def ask(self, prompt, history=None):
        """Start asking. history is a list of earlier {"role", "content"} messages."""
        self.cancel()

        messages = [{"role": "system", "content": self.system}] if self.system else []
        messages.extend(history or ())
        messages.append({"role": "user", "content": prompt})
        body = json.dumps({
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "stream": False,
        }).encode()

        self.state = BUSY
        self.answer = self.error = None
        self.truncated = False
        self._started = time.ticks_ms()

        if _async_capable():
            if self._client is None:
                try:
                    client = fetch.AsyncFetch(self.host, self.port, use_tls=self.tls, timeout=self.timeout)
                except TypeError:
                    # firmware from before AsyncFetch took a timeout
                    client = fetch.AsyncFetch(self.host, self.port, use_tls=self.tls)
                # keep error replies instead of raising, so their reason can be shown
                client.on_error(lambda _fetch: True)
                self._client = client
            self._client.fetch(self.path, headers=self._headers(), data=body, method="POST")
        else:
            self._body = body
            self._armed = False

    def update(self):
        """Move the request along. Call once a frame; returns the state."""
        if self.state == BUSY:
            if self._body is None:
                self._pump()
            elif self._armed:
                self._send_blocking()
            else:
                self._armed = True
        return self.state

    def cancel(self):
        """Drop a request in flight. The answer to it is never shown."""
        if self.state == BUSY:
            if self._client is not None:
                self._client.reset()
            self.state = IDLE
        self._body = None

    def _headers(self):
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.key:
            headers["Authorization"] = "Bearer " + self.key
        return headers

    def _pump(self):
        client = self._client
        try:
            status = client.update()
        except Exception as error:  # noqa: BLE001 - network faults surface from update()
            phase = getattr(client, "_phase", None)
            client.reset()
            self._fail(self._explain(error, phase))
            return

        if status in (fetch.AsyncFetch.DONE, fetch.AsyncFetch.ERROR):
            self._finish(client.http_status, bytes(client.body))

    def _send_blocking(self):
        body, self._body = self._body, None
        try:
            import requests
            response = requests.post(self.url, data=body, headers=self._headers(), timeout=self.timeout)
        except Exception as error:  # noqa: BLE001 - anything here means no answer
            self._fail(self._explain(error, None))
            return
        try:
            self._finish(response.status_code, response.content)
        finally:
            response.close()

    def _finish(self, status, raw):
        try:
            reply = json.loads(raw)
        except (ValueError, TypeError):
            reply = None

        if status != 200:
            self._fail(_problem(status, reply, raw, self))
            return

        try:
            choice = reply["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError):
            self._fail("The gateway sent a reply the badge could not read.")
            return

        # some providers answer in parts
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))

        answer = plain(content or "")
        if not answer:
            if choice.get("finish_reason") == "length":
                # thinking models can spend the whole allowance before answering
                self._fail("The model used up its %d tokens before it answered. Try again." % self.max_tokens)
            else:
                self._fail("The model sent back an empty answer.")
            return

        self.answer = answer
        self.truncated = choice.get("finish_reason") == "length"
        self.elapsed = time.ticks_diff(time.ticks_ms(), self._started)
        self.state = DONE

    def _fail(self, message):
        self.error = message
        self.elapsed = time.ticks_diff(time.ticks_ms(), self._started)
        self.state = FAILED

    def _explain(self, error, phase):
        code = error.args[0] if getattr(error, "args", None) else None
        if phase == "dns" or (phase is None and isinstance(code, int) and -10 <= code < 0):
            return "Cannot look up %s from this network." % self.host
        if code == errno.ETIMEDOUT or "timed out" in str(error).lower():
            return "No answer from the gateway in %d seconds." % self.timeout
        if isinstance(error, OSError):
            if isinstance(code, int) and code < -1000:
                return "The secure connection to %s failed (TLS %d)." % (self.host, code)
            return "Cannot reach %s:%d (%s)." % (self.host, self.port, error)
        return "%s: %s" % (type(error).__name__, error)
