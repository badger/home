"""Bounded, authenticated LAN snapshots from the local AgentViz bridge."""

import errno
import json
import socket
import time


MAX_PACKET = 4096
MAX_EVENTS = 24
STALE_MS = 5000
TRACKS = ("reasoning", "tool_call", "context", "output", "agent")
SOURCE_STATES = ("ok", "waiting", "error")
MESSAGES = ("", "Waiting for events", "Source unavailable", "Invalid session",
            "Session too large")


def hex_token(value):
    return (isinstance(value, str) and len(value) == 32
            and all(c in "0123456789abcdef" for c in value))


def label(value, limit):
    return (isinstance(value, str) and 1 <= len(value) <= limit
            and all(c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
                        "0123456789_. -" for c in value))


def number(value):
    return type(value) is int and 0 <= value <= 2147483647


def ipv4(value):
    if not isinstance(value, str):
        return False
    parts = value.split(".")
    return (len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)
            and value not in ("0.0.0.0", "255.255.255.255"))


def validate(packet):
    if not isinstance(packet, dict) or type(packet.get("v")) is not int or packet["v"] != 1:
        raise ValueError("Unsupported packet")
    if not hex_token(packet.get("epoch")) or not number(packet.get("seq")):
        raise ValueError("Invalid sequence")
    if packet.get("state") not in SOURCE_STATES or packet.get("message") not in MESSAGES:
        raise ValueError("Invalid source state")
    if not label(packet.get("source"), 16):
        raise ValueError("Invalid source label")
    metrics = packet.get("metrics")
    if (not isinstance(metrics, list) or len(metrics) != 7
            or not all(number(v) for v in metrics[:5])
            or not all(number(v) or (type(v) is int and v == -1) for v in metrics[5:])):
        raise ValueError("Invalid metrics")
    events = packet.get("events")
    if not isinstance(events, list) or len(events) > MAX_EVENTS:
        raise ValueError("Too many events")
    previous = -1
    for event in events:
        if (not isinstance(event, list) or len(event) != 8
                or not all(number(v) for v in event[:3])
                or type(event[3]) is not int or not 0 <= event[3] < len(TRACKS)
                or not label(event[4], 18) or not label(event[5], 12)
                or type(event[6]) is not int or event[6] not in (0, 1)
                or not number(event[7]) or event[0] <= previous
                or event[0] >= metrics[0]):
            raise ValueError("Invalid event")
        previous = event[0]
    tools = packet.get("tools")
    if (not isinstance(tools, list) or len(tools) > 4
            or any(not isinstance(t, list) or len(t) != 2
                   or not label(t[0], 18) or not number(t[1]) for t in tools)):
        raise ValueError("Invalid tool counts")
    return packet


class Feed:
    def __init__(self, token):
        self.token = token
        self.packet = None
        self.last_seen = None
        self.epoch = None
        self.seq = -1
        self.retired = []

    def accept(self, data, now):
        if len(data) > MAX_PACKET:
            raise ValueError("Packet too large")
        packet = json.loads(data)
        if not isinstance(packet, dict) or packet.get("token") != self.token:
            raise ValueError("Unauthorized packet")
        validate(packet)
        epoch, seq = packet["epoch"], packet["seq"]
        if epoch in self.retired or (epoch == self.epoch and seq <= self.seq):
            return False
        if epoch != self.epoch:
            if self.epoch is not None:
                self.retired.append(self.epoch)
                self.retired = self.retired[-4:]
            self.epoch = epoch
        self.seq = seq
        self.packet = packet
        self.last_seen = now
        return True

    def live(self, now):
        return (self.last_seen is not None
                and time.ticks_diff(now, self.last_seen) < STALE_MS)


class Monitor:
    def __init__(self, config_path="/agentviz_config.json"):
        self.config_path = config_path
        self.wlan = self.listener = self.feed = None
        self.owned_wifi = self.was_active = False
        self.address = ""
        self.message = ""
        self.error = False
        self.joining = self.retry = None
        self.rejected = 0
        self.reload()

    def reload(self):
        self.close()
        self.error = False
        self.feed = None
        self.address = ""
        self.joining = self.retry = None
        try:
            try:
                with open(self.config_path) as source:
                    config = json.load(source)
            except OSError as error:
                if error.args[0] != errno.ENOENT:
                    raise
                self.message = "Add /agentviz_config.json"
                return
            if not isinstance(config, dict) or not hex_token(config.get("token")):
                raise ValueError("Expected a 32-character lowercase hex token")
            if not ipv4(config.get("host")):
                raise ValueError("Expected the bridge computer IPv4 address")
            port = config.get("port", 9138)
            if type(port) is not int or not 1 <= port <= 65535:
                raise ValueError("Invalid UDP port")
            ssid, password = config.get("ssid"), config.get("password", "")
            if ssid is not None and (not isinstance(ssid, str)
                                     or not 1 <= len(ssid.encode()) <= 32 or "\0" in ssid):
                raise ValueError("Invalid SSID")
            if (not isinstance(password, str) or "\0" in password
                    or (password and not 8 <= len(password.encode()) <= 63)):
                raise ValueError("Invalid Wi-Fi password")
            self.config = config
            self.feed = Feed(config["token"])
            import network
            self.wlan = network.WLAN(network.STA_IF)
            self.was_active = self.wlan.active()
            self.wlan.active(True)
            if ssid:
                self.wlan.disconnect()
                self.join()
            else:
                self.message = "Waiting for badge Wi-Fi"
        except (OSError, ValueError) as error:
            self.fail("Check AgentViz config", error)

    def join(self):
        self.owned_wifi = True
        self.wlan.connect(self.config["ssid"], self.config.get("password", ""))
        self.joining = time.ticks_ms()
        self.retry = None
        self.message = "Joining Wi-Fi..."

    def fail(self, message, error):
        self.error = True
        self.message = message
        # Do not log config values, raw packets, or tokens.
        print("AgentViz:", message, "-", type(error).__name__)
        self.disconnect()

    def disconnect(self):
        if self.listener is not None:
            self.listener.close()
            self.listener = None
        if self.feed:
            self.feed.last_seen = None
        self.address = ""

    def step(self, now):
        if self.wlan is None or self.error:
            return
        try:
            if not self.wlan.isconnected():
                self.disconnect()
                if self.joining is not None:
                    if time.ticks_diff(now, self.joining) >= 20000:
                        self.wlan.disconnect()
                        self.joining = None
                        self.retry = time.ticks_add(now, 5000)
                        self.message = "Wi-Fi unavailable; retrying"
                        print("AgentViz: Wi-Fi connection timed out")
                elif self.config.get("ssid"):
                    if self.retry is None or time.ticks_diff(now, self.retry) >= 0:
                        self.join()
                else:
                    self.message = "Waiting for badge Wi-Fi"
                return
            self.joining = None
            address = self.wlan.ifconfig()[0]
            if address != self.address:
                self.disconnect()
                self.listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.listener.bind((address, self.config.get("port", 9138)))
                self.listener.setblocking(False)
                self.address = address
            for _ in range(2):
                try:
                    data, peer = self.listener.recvfrom(MAX_PACKET + 1)
                except OSError as error:
                    if error.args[0] == errno.EAGAIN:
                        break
                    raise
                if peer[0] != self.config["host"]:
                    continue
                try:
                    self.feed.accept(data, now)
                except (ValueError, UnicodeError):
                    self.rejected += 1
                    if self.rejected == 1:
                        print("AgentViz: rejected invalid or unauthorized update")
            if self.live(now):
                packet = self.feed.packet
                self.message = ("Local bridge connected" if packet["state"] == "ok"
                                else packet["message"])
            else:
                self.message = ("Bridge disconnected" if self.feed.packet is not None
                                else "Waiting for local bridge")
        except OSError as error:
            self.fail("Network error; Up retries", error)

    def live(self, now):
        return bool(self.listener is not None and self.feed and self.feed.live(now))

    def close(self):
        self.disconnect()
        if self.wlan is not None:
            if self.owned_wifi:
                self.wlan.disconnect()
            if not self.was_active:
                self.wlan.active(False)
            self.wlan = None
        self.owned_wifi = False
