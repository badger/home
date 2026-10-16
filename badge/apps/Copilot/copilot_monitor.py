"""Agent Buddy protocol-8 device endpoint; no desktop daemon or agent hooks."""

import binascii
import errno
import json
import os
import socket
import time


STATES = ("idle", "surprise", "working", "attention", "complete")
DISCOVER = b"ESP32_AGENT_COMPANION_DISCOVER_V1"
WOULD_BLOCK = (errno.EAGAIN,)
STALE_MS = 15000


def random_hex(size):
    return binascii.hexlify(os.urandom(size)).decode()


def valid_hex(value, length):
    return (isinstance(value, str) and len(value) == length
            and all(c in "0123456789abcdefABCDEF" for c in value))


def valid_id(value):
    return (isinstance(value, str) and 1 <= len(value) <= 16
            and all(c in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in value))


def read_json(path):
    try:
        with open(path) as source:
            return json.load(source)
    except OSError as error:
        if error.args[0] != errno.ENOENT:
            raise
        return None


class Protocol:
    def __init__(self, pairing_path="/state/copilot_pairing.json"):
        self.pairing_path = pairing_path
        saved = read_json(pairing_path)
        if saved is not None and (
                not isinstance(saved, dict) or not valid_hex(saved.get("deviceId"), 16)
                or not valid_hex(saved.get("token"), 32)):
            raise ValueError("Invalid Copilot pairing file")
        self.device_id = saved["deviceId"] if saved else random_hex(8)
        self.token = saved["token"] if saved else None
        self.boot = int(random_hex(4), 16) & 0x7fffffff
        self.state = "idle"
        self.icons = {}
        self.agents = []
        self.usage = []
        self.last_seen = None
        self.last_state = None
        self.pairing_code = None
        self.pairing_until = None
        self.pairing_attempts = 0

    def open_pairing(self, now):
        self.pairing_code = "%08d" % (int(random_hex(4), 16) % 100000000)
        self.pairing_until = time.ticks_add(now, 60000)
        self.pairing_attempts = 0

    def pairing(self, now):
        if self.pairing_code and time.ticks_diff(now, self.pairing_until) >= 0:
            self.pairing_code = None
        return self.pairing_code is not None

    def live(self, now):
        return (self.last_state is not None and self.last_seen is not None
                and time.ticks_diff(now, self.last_seen) < STALE_MS)

    def invalidate(self):
        if self.last_state is not None:
            # A new boot epoch makes the unmodified daemon resend its full state.
            self.boot = (self.boot + 1) & 0x7fffffff
        self.last_state = self.last_seen = None
        self.agents = []
        self.usage = []
        self.state = "idle"

    def expire(self, now):
        self.pairing(now)
        if self.last_seen is not None and time.ticks_diff(now, self.last_seen) >= STALE_MS:
            self.invalidate()

    def save_pairing(self, token):
        parent = self.pairing_path.rsplit("/", 1)[0]
        try:
            os.mkdir(parent)
        except OSError as error:
            if error.args[0] != errno.EEXIST:
                raise
        temporary = self.pairing_path + ".tmp"
        with open(temporary, "w") as destination:
            json.dump({"deviceId": self.device_id, "token": token}, destination)
        os.rename(temporary, self.pairing_path)

    def status(self):
        return {"deviceId": self.device_id, "boot": self.boot, "protocol": 8,
                "character": "copilot", "board": "github-universe-2026",
                "state": self.state}

    def handle(self, method, path, headers, body, now):
        if method == "POST" and path == "/pair":
            if not self.pairing(now) or self.pairing_attempts >= 5:
                return 403, {"error": "Pairing is closed; press Up on the badge"}
            self.pairing_attempts += 1
            if body != self.pairing_code.encode():
                if self.pairing_attempts >= 5:
                    self.pairing_code = None
                return 403, {"error": "Invalid or expired pairing code"}
            token = self.token or random_hex(16)
            self.save_pairing(token)
            self.token = token
            self.pairing_code = None
            return 200, {"deviceId": self.device_id, "token": token}
        if not self.token or headers.get("authorization") != "Bearer " + self.token:
            return 401, {"error": "Unauthorized"}
        if method == "GET" and path == "/status":
            self.last_seen = now
            return 200, self.status()
        if method != "POST" or path not in ("/state", "/icon", "/agents", "/usage"):
            return 404, {"error": "Unsupported badge endpoint"}
        try:
            text = body.decode("ascii").strip()
            if path == "/state":
                if text not in STATES:
                    raise ValueError("Invalid state")
                self.state = text
                self.last_state = now
            elif path == "/icon":
                self.set_icon(text)
            elif path == "/agents":
                self.set_agents(text)
            else:
                self.set_usage(text)
        except (ValueError, UnicodeError) as error:
            return 400, {"error": str(error)}
        self.last_seen = now
        return 200, {"ok": True}

    def set_icon(self, text):
        parts = text[1:].split(":") if text.startswith("%") else []
        if len(parts) != 3 or not valid_id(parts[0]) or not valid_hex(parts[1], 6):
            raise ValueError("Invalid icon packet")
        name, rgb, encoded = parts
        if len(encoded) != 96 or any(c not in
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/" for c in encoded):
            raise ValueError("Invalid icon mask")
        mask = binascii.a2b_base64(encoded)
        if len(mask) != 72:
            raise ValueError("Invalid icon mask")
        if name not in self.icons and len(self.icons) >= 8:
            raise ValueError("Icon table full")
        self.icons[name] = (tuple(int(rgb[i:i + 2], 16) for i in (0, 2, 4)), mask)

    def set_agents(self, text):
        if not text.startswith("&"):
            raise ValueError("Invalid agents packet")
        agents = []
        if text[1:]:
            for entry in text[1:].split(","):
                parts = entry.split("=")
                if (len(parts) != 2 or not valid_id(parts[0]) or parts[1] not in ("w", "a", "c")
                        or len(agents) >= 8 or any(name == parts[0] for name, _ in agents)):
                    raise ValueError("Invalid agents packet")
                agents.append((parts[0], parts[1]))
        self.agents = agents

    def set_usage(self, text):
        if not text.startswith("$"):
            raise ValueError("Invalid usage packet")
        lines = text[1:].split("|") if text[1:] else []
        if (len(lines) > 2 or any(not 1 <= len(line) <= 18 or any(c not in
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 ,.:"
                for c in line) for line in lines)):
            raise ValueError("Invalid usage text")
        self.usage = lines


class Peer:
    def __init__(self, connection, now):
        self.socket = connection
        self.socket.setblocking(False)
        self.started = now
        self.received = bytearray()
        self.output = None
        self.sent = 0
        self.header_end = None
        self.length = 0
        self.headers = {}

    def respond(self, status, value):
        body = json.dumps(value).encode()
        self.output = ("HTTP/1.1 %d %s\r\nContent-Type: application/json\r\n"
                       "Content-Length: %d\r\nConnection: close\r\n\r\n"
                       % (status, "OK" if status == 200 else "Error", len(body))).encode() + body
        self.received = bytearray()

    def step(self, protocol, now):
        if time.ticks_diff(now, self.started) >= 5000:
            return False
        try:
            if self.output is not None:
                count = self.socket.send(self.output[self.sent:])
                if not count:
                    return False
                self.sent += count
                return self.sent < len(self.output)
            data = self.socket.recv(1024)
            if not data:
                return False
            self.received.extend(data)
            if self.header_end is None:
                end = self.received.find(b"\r\n\r\n")
                if end < 0:
                    if len(self.received) > 2048:
                        self.respond(413, {"error": "Header too large"})
                    return True
                if end > 2048:
                    self.respond(413, {"error": "Header too large"})
                    return True
                try:
                    lines = bytes(self.received[:end]).decode("ascii").split("\r\n")
                    self.method, self.path, version = lines[0].split()
                    if version not in ("HTTP/1.0", "HTTP/1.1"):
                        raise ValueError("Invalid HTTP version")
                    for line in lines[1:]:
                        key, value = line.split(":", 1)
                        key = key.lower()
                        if key in self.headers:
                            raise ValueError("Duplicate HTTP header")
                        self.headers[key] = value.strip()
                    length = self.headers.get("content-length", "0")
                    if not length.isdigit() or "transfer-encoding" in self.headers:
                        raise ValueError("Expected Content-Length, not chunked data")
                    self.length = int(length)
                    if self.length > 512:
                        self.respond(413, {"error": "Body too large"})
                        return True
                except (ValueError, UnicodeError) as error:
                    self.respond(400, {"error": str(error)})
                    return True
                self.header_end = end + 4
            size = len(self.received) - self.header_end
            if size >= self.length:
                if size != self.length:
                    self.respond(400, {"error": "Unexpected trailing data"})
                else:
                    try:
                        status, value = protocol.handle(
                            self.method, self.path, self.headers,
                            bytes(self.received[self.header_end:]), now)
                    except OSError:
                        print("Copilot: could not save pairing")
                        status, value = 500, {"error": "Could not save pairing on badge"}
                    self.respond(status, value)
            return True
        except OSError as error:
            if error.args[0] in WOULD_BLOCK:
                return True
            print("Copilot: HTTP connection failed:", error.args[0])
            return False

    def close(self):
        self.socket.close()


class Server:
    def __init__(self, protocol, port=80, discovery_port=4666, host=None):
        if not isinstance(host, str) or not host or host == "0.0.0.0":
            raise ValueError("A specific network address is required")
        self.protocol = protocol
        self.discovery_port = discovery_port
        self.clients = []
        self.listener = self.udp = None
        try:
            self.listener = socket.socket()
            self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.listener.bind((host, port))
            self.listener.listen(3)
            self.listener.setblocking(False)
            self.port = port if port else self.listener.getsockname()[1]
        except OSError:
            self.close()
            raise

    def update_discovery(self, now):
        if self.protocol.pairing(now):
            if self.udp is None:
                self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                # Broadcast reception needs a wildcard bind, only during physical pairing.
                self.udp.bind(("0.0.0.0", self.discovery_port))
                self.udp.setblocking(False)
        elif self.udp is not None:
            self.udp.close()
            self.udp = None

    def step(self, now):
        self.protocol.expire(now)
        for _ in range(2):
            try:
                connection, _ = self.listener.accept()
            except OSError as error:
                if error.args[0] not in WOULD_BLOCK:
                    raise
                break
            if len(self.clients) >= 3:
                connection.close()
            else:
                try:
                    self.clients.append(Peer(connection, now))
                except OSError:
                    connection.close()
                    raise
        for client in self.clients[:]:
            if not client.step(self.protocol, now):
                client.close()
                self.clients.remove(client)
        self.update_discovery(now)
        if self.udp is None:
            return
        for _ in range(2):
            try:
                data, address = self.udp.recvfrom(64)
            except OSError as error:
                if error.args[0] not in WOULD_BLOCK:
                    raise
                break
            if data == DISCOVER:
                packet = {"service": "esp32-agent-companion", "protocol": 1,
                          "deviceId": self.protocol.device_id, "hostname": "universe-copilot",
                          "port": self.port, "boot": self.protocol.boot}
                self.udp.sendto(json.dumps(packet).encode(), address)

    def close(self):
        for client in self.clients:
            client.close()
        self.clients = []
        if self.listener:
            self.listener.close()
            self.listener = None
        if self.udp:
            self.udp.close()
            self.udp = None


class Monitor:
    def __init__(self, config_path="/copilot_config.json", pairing_path="/state/copilot_pairing.json"):
        self.config_path = config_path
        self.pairing_path = pairing_path
        self.protocol = None
        self.wlan = self.server = None
        self.was_active = self.joined = False
        self.message = "Set up Wi-Fi"
        self.address = ""
        self.error = None
        self.retry_at = self.joining_since = None
        self.reload()

    def reload(self):
        self.close()
        self.error = None
        self.address = ""
        self.protocol = None
        try:
            self.protocol = Protocol(self.pairing_path)
            config = read_json(self.config_path)
            if config is None:
                self.message = "Add /copilot_config.json"
                return
            if not isinstance(config, dict):
                raise ValueError("Invalid Copilot config")
            ssid, password = config.get("ssid"), config.get("password", "")
            if ssid is not None and (not isinstance(ssid, str) or not 1 <= len(ssid.encode()) <= 32
                                     or "\0" in ssid):
                raise ValueError("Invalid Wi-Fi network")
            if (not isinstance(password, str) or "\0" in password
                    or (password and not 8 <= len(password.encode()) <= 63)):
                raise ValueError("Invalid Wi-Fi password")
            port = config.get("port", 80)
            if type(port) is not int or not 1 <= port <= 65535:
                raise ValueError("Invalid Copilot port")
            self.config = config
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
            self.fail("Check Copilot config", error)

    def join(self):
        self.joined = True
        self.wlan.connect(self.config["ssid"], self.config.get("password", ""))
        self.joining_since = time.ticks_ms()
        self.retry_at = None
        self.message = "Joining Wi-Fi..."

    def fail(self, message, error):
        self.error = message
        self.message = message
        # Avoid logging credentials, tokens, or incoming request bodies.
        print("Copilot:", message, "-", type(error).__name__)
        if self.server:
            self.server.close()
            self.server = None
        if self.protocol:
            self.protocol.invalidate()

    def step(self, now):
        if self.protocol:
            self.protocol.expire(now)
        if not self.wlan or self.error:
            return
        try:
            if not self.wlan.isconnected():
                self.address = ""
                if self.server:
                    self.server.close()
                    self.server = None
                    self.protocol.invalidate()
                if self.joining_since is not None:
                    if time.ticks_diff(now, self.joining_since) >= 20000:
                        self.wlan.disconnect()
                        self.joining_since = None
                        self.retry_at = time.ticks_add(now, 5000)
                        self.message = "Wi-Fi unavailable; retrying"
                        print("Copilot: Wi-Fi connection timed out")
                elif self.config.get("ssid"):
                    if self.retry_at is None or time.ticks_diff(now, self.retry_at) >= 0:
                        self.join()
                else:
                    self.message = "Waiting for badge Wi-Fi"
                return
            self.joining_since = None
            address = self.wlan.ifconfig()[0]
            if self.server is not None and address != self.address:
                self.server.close()
                self.server = None
                self.protocol.invalidate()
            self.address = address
            if self.server is None:
                self.server = Server(self.protocol, self.config.get("port", 80), host=self.address)
            self.server.step(now)
            self.message = ("Live session monitor" if self.protocol.live(now) else
                            "Waiting for Agent Buddy" if self.protocol.token else "Up: pair Agent Buddy")
        except (OSError, ValueError) as error:
            self.fail("Network error; Select retries", error)

    def live(self, now):
        return bool(self.server and self.protocol and self.protocol.live(now))

    def open_pairing(self, now):
        if self.server:
            self.protocol.open_pairing(now)

    def close(self):
        if self.server:
            self.server.close()
            self.server = None
        if self.wlan:
            if self.joined:
                self.wlan.disconnect()
            if not self.was_active:
                self.wlan.active(False)
            self.wlan = None
        self.joined = False
