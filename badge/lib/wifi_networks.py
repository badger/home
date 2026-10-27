"""Saved Wi-Fi networks for badge apps: keep several, join whichever is around.

The firmware's wifi module joins one network, WIFI_SSID and WIFI_PASSWORD in
secrets.py, and every app uses it. This module adds more saved networks,
WIFI_NETWORKS = {"name": "password", ...} in secrets.py, and moves between
them:

    import sys
    if "/system/lib" not in sys.path:
        sys.path.append("/system/lib")
    import wifi_networks

    roamer = wifi_networks.Roamer()

    def update():
        if roamer.update() == wifi_networks.CONNECTED:   # once a frame
            ...                                          # use the network
        else:
            screen.text(roamer.status, 10, 10)

A Roamer tries the active network (WIFI_SSID) first. If it can't join that,
it scans and tries the saved networks that are in range, strongest first,
giving each a second attempt, since a weak signal often fails once. Names
match whatever case the network broadcasts. The network that works becomes
the active one in secrets.py, so the next app, which only knows WIFI_SSID,
joins it too. The network you were on stays saved.

See badge/lib/README.md for the settings.
"""

import os
import time

__version__ = "1.1.0"

SECRETS_FILE = "/secrets.py"            # the badge's own settings, which the Settings app writes
SYSTEM_SECRETS_FILE = "/system/secrets.py"

CONNECTING = 0
CONNECTED = 1
FAILED = 2

TRY_SECONDS = 15                        # how long one join attempt gets before the next is tried
DHCP_SECONDS = 10                       # more time when it has joined and is waiting for an address
ATTEMPTS = 2                            # joins per network: a weak signal often fails just once
SCANS = 2

# network.WLAN.status() link states
_BAD_PASSWORD = -3
_NOT_FOUND = -2
_JOIN_FAILED = -1
_NO_ADDRESS = 2
_LINK_UP = 3


def _secrets():
    try:
        import secrets
        return secrets
    except ImportError:
        return None


def _wlan(activate=False):
    import network
    wlan = network.WLAN(network.STA_IF)
    if activate and not wlan.active():
        wlan.active(True)
    return wlan


def _pairs(value):
    """WIFI_NETWORKS as [(ssid, password)], from a dict or a list of pairs."""
    if isinstance(value, dict):
        value = value.items()
    pairs = []
    for entry in value or ():
        try:
            ssid, password = entry
        except (TypeError, ValueError):
            continue
        pairs.append((str(ssid or "").strip(), str(password or "")))
    return [pair for pair in pairs if pair[0]]


def _same(a, b):
    return a.lower() == b.lower()


def active():
    """The network every app joins: WIFI_SSID, or ""."""
    s = _secrets()
    return str(getattr(s, "WIFI_SSID", "") or "").strip() if s else ""


def saved():
    """Every saved network as [(ssid, password)], the active one first."""
    s = _secrets()
    if s is None:
        return []
    found = []
    for ssid, password in [(active(), str(getattr(s, "WIFI_PASSWORD", "") or ""))] + _pairs(getattr(s, "WIFI_NETWORKS", None)):
        if ssid and not any(_same(ssid, known) for known, _ in found):
            found.append((ssid, password))
    return found


def missing():
    """secrets.py names to ask for with missing_details.show(), or []."""
    return [] if saved() else ["WIFI_SSID"]


def scan():
    """Visible networks as {ssid: rssi}. Blocks for about a second; {} if it can't."""
    try:
        results = _wlan(True).scan()
    except Exception:  # noqa: BLE001 - no radio, a simulator, or the radio is busy
        return {}
    seen = {}
    for entry in results:
        try:
            ssid = entry[0]
            ssid = str(ssid, "utf-8") if isinstance(ssid, (bytes, bytearray)) else str(ssid)
            rssi = int(entry[3])
        except (IndexError, TypeError, ValueError, UnicodeError):
            continue
        if ssid and rssi > seen.get(ssid, -1000):
            seen[ssid] = rssi
    return seen


def in_range(visible=None):
    """Saved networks that are visible, strongest first, as [(ssid, password, rssi)].

    ssid is spelled the way the network broadcasts it, so a network saved as
    "Github Guest" joins "GitHub Guest".
    """
    visible = scan() if visible is None else visible
    by_name = {}
    for name, rssi in visible.items():
        key = name.lower()
        if key not in by_name or rssi > by_name[key][1]:
            by_name[key] = (name, rssi)
    found = []
    for ssid, password in saved():
        hit = by_name.get(ssid.lower())
        if hit:
            found.append((hit[0], password, hit[1]))
    found.sort(key=lambda item: -item[2])
    return found


def _read(path):
    try:
        with open(path) as handle:
            return handle.read()
    except OSError:
        return None


def _assigned(line):
    """The name a simple `NAME = value` line sets, or None."""
    text = line.strip()
    if not text or text[0] == "#" or "=" not in text:
        return None
    name = text.split("=", 1)[0].strip()
    if name and all(c == "_" or c.isalpha() or c.isdigit() for c in name):
        return name
    return None


def _loads_to(text, values):
    scope = {}
    try:
        exec(text, scope)
    except Exception:  # noqa: BLE001 - anything that stops it loading
        return False
    return all(scope.get(name) == value for name, value in values.items())


def save_settings(values, path=None):
    """Set secrets.py values, keeping everything else in the file.

    Rewrites the badge's own /secrets.py, starting from /system/secrets.py when
    there isn't one yet (it would hide that file), and only after checking the
    result still loads with the new values. Also updates the loaded secrets
    module, so the running app sees the change.
    """
    path = path or SECRETS_FILE
    old = _read(path)
    if old is None:
        old = _read(SYSTEM_SECRETS_FILE) or ""
    added = "\n".join("%s = %r" % (name, values[name]) for name in sorted(values)) + "\n"
    kept = [line for line in old.split("\n") if _assigned(line) not in values]
    text = None
    # replace the old lines; if that would break a multi-line value, append instead
    for candidate in ("\n".join(kept).rstrip("\n") + "\n" + added, old.rstrip("\n") + "\n" + added):
        if _loads_to(candidate, values):
            text = candidate.lstrip("\n")
            break
    if text is None:
        raise ValueError("secrets.py would not load with these values, so it was left alone")

    temp = path + ".tmp"
    with open(temp, "w") as handle:
        handle.write(text)
    try:
        os.rename(temp, path)
    except OSError:
        os.remove(path)
        os.rename(temp, path)

    s = _secrets()
    if s is not None:
        for name, value in values.items():
            try:
                setattr(s, name, value)
            except (AttributeError, TypeError):
                pass


def remember(ssid, password):
    """Save a network and make it the active one. Returns True if anything changed."""
    networks = {}
    for name, secret in saved():
        if not _same(name, ssid):
            networks[name] = secret
    networks[ssid] = password
    s = _secrets()
    current = (active(), str(getattr(s, "WIFI_PASSWORD", "") or "") if s else "")
    stored = dict(_pairs(getattr(s, "WIFI_NETWORKS", None) if s else None))
    if current == (ssid, password) and stored == networks:
        return False
    save_settings({"WIFI_SSID": ssid, "WIFI_PASSWORD": password, "WIFI_NETWORKS": networks})
    return True


def current():
    """The network the radio is on, or None."""
    try:
        wlan = _wlan()
        if wlan.isconnected():
            return str(wlan.config("ssid") or "") or None
    except Exception:  # noqa: BLE001 - no radio, or no ssid to report
        pass
    return None


class Roamer:
    """Joins the best saved network, a step each frame. See the module docstring."""

    def __init__(self, try_seconds=TRY_SECONDS, remember=True):
        self.try_ms = int(try_seconds * 1000)
        self.remember = remember    # make the network that works the active one
        self.restart()

    def restart(self, only=None):
        """Start over. With only, join that saved network and no other."""
        self.only = only
        self.state = CONNECTING
        self.status = "Starting Wi-Fi"
        self.ssid = None            # the network being tried, then the one joined
        self.problems = []          # (ssid, reason) for each network that didn't work
        self._password = None
        self._queue = None
        self._attempts = {}         # lower-case ssid -> joins started
        self._scans = 0
        self._in_range = None       # saved networks the last scan found
        self._began = 0

    @property
    def connected(self):
        return self.state == CONNECTED

    def update(self):
        """Move along. Call once a frame; returns CONNECTING, CONNECTED or FAILED."""
        try:
            if self.state == CONNECTING:
                self._step()
            elif self.state == CONNECTED and not _wlan().isconnected():
                self.restart()      # the network went away: find another
        except OSError as error:  # MicroPython raises OSError for radio faults
            self._fail("The Wi-Fi radio ran into a problem: %s" % error)
        return self.state

    def _step(self):
        wlan = _wlan(True)
        if self._queue is None:
            if self.only is None and wlan.isconnected():
                # still on a network from an earlier app
                self._joined(current(), None)
                return
            if self.only is None:
                self._queue = saved()[:1]   # the active network, without scanning
            else:
                self._queue = []            # look for the chosen one, for its spelling
            self._next(wlan)
            return

        # read the state once: a join can finish between two reads
        code = wlan.status()
        if code == _LINK_UP or wlan.isconnected():
            self._joined(self.ssid, self._password)
            return
        waited = time.ticks_diff(time.ticks_ms(), self._began)
        if code == _BAD_PASSWORD and waited > 2000:
            self._give_up(wlan, "wrong password")
        elif code in (_NOT_FOUND, _JOIN_FAILED) and waited > 5000:
            self._give_up(wlan, "not found" if code == _NOT_FOUND else "could not join")
        elif code == _NO_ADDRESS and waited > self.try_ms + DHCP_SECONDS * 1000:
            self._give_up(wlan, "no address")
        elif code != _NO_ADDRESS and waited > self.try_ms:
            self._give_up(wlan, "no answer")

    def _give_up(self, wlan, reason):
        self.problems = [p for p in self.problems if not _same(p[0], self.ssid)] + [(self.ssid, reason)]
        self._next(wlan)

    def _worth_trying(self, ssid):
        if self._attempts.get(ssid.lower(), 0) >= ATTEMPTS:
            return False
        return not any(_same(ssid, failed) and reason == "wrong password" for failed, reason in self.problems)

    def _next(self, wlan):
        while True:
            while self._queue:
                ssid, password = self._queue.pop(0)
                if not self._worth_trying(ssid):
                    continue
                self._attempts[ssid.lower()] = self._attempts.get(ssid.lower(), 0) + 1
                self.ssid, self._password = ssid, password
                self.status = "Joining %s" % ssid
                self._began = time.ticks_ms()
                try:
                    wlan.disconnect()
                except OSError:
                    pass
                wlan.connect(ssid, password)
                return
            if self._scans >= SCANS:
                self._fail(self._summary())
                return
            self._scan(wlan)

    def _scan(self, wlan):
        self._scans += 1
        self.status = "Looking for your networks"
        try:
            wlan.disconnect()       # a join in progress stops the scan
        except OSError:
            pass
        visible = scan()
        found = in_range(visible)
        if self.only is not None:
            ranked = [(s, p, r) for s, p, r in found if _same(s, self.only)]
            ranked = ranked or [(s, p, -1000) for s, p in saved() if _same(s, self.only)]
        elif visible:
            self._in_range = found
            ranked = found
        else:
            # couldn't scan: try each saved network in turn
            ranked = [(s, p, -index) for index, (s, p) in enumerate(saved())]
        # networks not tried yet before second attempts, then the strongest
        ranked.sort(key=lambda item: (self._attempts.get(item[0].lower(), 0), -item[2]))
        self._queue = [(s, p) for s, p, _ in ranked]

    def _summary(self):
        names = [ssid for ssid, _ in saved()]
        if not names:
            return "No Wi-Fi network is saved. Set WIFI_SSID and WIFI_PASSWORD in secrets.py."
        tried = ", ".join("%s (%s)" % problem for problem in self.problems)
        if self._in_range is not None and not self._in_range:
            if tried:
                return "Could not join %s, and no other saved network is in range." % tried
            return "None of your saved networks is in range: %s." % ", ".join(names)
        if tried:
            return "Could not join %s." % tried
        return "Could not join a saved network."

    def _joined(self, ssid, password):
        self.state = CONNECTED
        self.ssid = ssid
        self.status = "Connected to %s" % (ssid or "Wi-Fi")
        if ssid:
            self.problems = [p for p in self.problems if not _same(p[0], ssid)]
        if self.remember and ssid and password is not None:
            try:
                remember(ssid, password)
            except (OSError, ValueError):
                pass                # joined anyway, just not remembered for next time

    def _fail(self, message):
        self.state = FAILED
        self.status = message
