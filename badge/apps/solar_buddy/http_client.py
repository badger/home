"""Bounded, incremental HTTP/1.1 GETs; no threads, blocking DNS, or redirects."""

import errno
import json
import select
import socket

from clock import elapsed
from config import parse_url, validate_secrets

MAX_BODY = 16384
MAX_HEADERS = 4096
_BUSY = tuple(set(getattr(errno, name, -9999) for name in
                  ("EAGAIN", "EWOULDBLOCK", "EINPROGRESS", "EALREADY"))
              | {10035, 10036, 10037})


class Response:
    def __init__(self):
        self.headers = None
        self.pending = bytearray()
        self.body = bytearray()
        self.length = None
        self.chunked = False
        self.chunk_size = None
        self.trailers = False
        self.done = False
        self.received = 0

    def feed(self, data):
        if self.done and data:
            raise ValueError("Unexpected data after HTTP response")
        self.received += len(data)
        if self.received > MAX_BODY * 3 + MAX_HEADERS:
            raise ValueError("HTTP response exceeds the memory limit")
        self.pending.extend(data)
        if self.headers is None:
            end = self.pending.find(b"\r\n\r\n")
            if end < 0:
                if len(self.pending) > MAX_HEADERS:
                    raise ValueError("HTTP headers exceed the memory limit")
                return
            if end > MAX_HEADERS:
                raise ValueError("HTTP headers exceed the memory limit")
            lines = bytes(self.pending[:end]).decode().split("\r\n")
            del self.pending[:end + 4]
            status = lines[0].split(" ", 2)
            if len(status) < 2 or status[0] not in ("HTTP/1.0", "HTTP/1.1"):
                raise ValueError("Invalid HTTP status line")
            code = int(status[1])
            if code != 200:
                hint = {401: "check token", 403: "sensor access denied",
                        404: "check entity ID", 429: "rate limited",
                        503: "Home Assistant unavailable"}.get(code, "request failed")
                raise ValueError("HTTP %d: %s" % (code, hint))
            self.headers = {}
            for line in lines[1:]:
                name, separator, value = line.partition(":")
                if not separator:
                    raise ValueError("Malformed HTTP header")
                name, value = name.strip().lower(), value.strip()
                if name in self.headers and name in ("content-length", "transfer-encoding"):
                    raise ValueError("Duplicate HTTP framing header")
                self.headers[name] = value
            encoding = self.headers.get("content-encoding", "identity").lower()
            if encoding != "identity":
                raise ValueError("Compressed HTTP responses are not supported")
            transfer = self.headers.get("transfer-encoding", "").lower()
            if transfer not in ("", "chunked"):
                raise ValueError("Unsupported HTTP transfer encoding")
            self.chunked = transfer == "chunked"
            if "content-length" in self.headers:
                if self.chunked:
                    raise ValueError("Ambiguous HTTP response framing")
                self.length = int(self.headers["content-length"])
                if not 0 <= self.length <= MAX_BODY:
                    raise ValueError("HTTP body exceeds the memory limit")
        self._consume()

    def _consume(self):
        if not self.chunked:
            self.body.extend(self.pending)
            self.pending = bytearray()
            if len(self.body) > MAX_BODY:
                raise ValueError("HTTP body exceeds the memory limit")
            if self.length is not None:
                if len(self.body) > self.length:
                    raise ValueError("HTTP body exceeds Content-Length")
                self.done = len(self.body) == self.length
            return
        while True:
            if self.trailers:
                if self.pending[:2] == b"\r\n":
                    self.done = True
                elif b"\r\n\r\n" in self.pending:
                    self.done = True
                elif len(self.pending) > MAX_HEADERS:
                    raise ValueError("HTTP trailers exceed the memory limit")
                return
            if self.chunk_size is None:
                end = self.pending.find(b"\r\n")
                if end < 0:
                    if len(self.pending) > 128:
                        raise ValueError("Invalid HTTP chunk header")
                    return
                if end > 128:
                    raise ValueError("Invalid HTTP chunk header")
                size = bytes(self.pending[:end]).split(b";", 1)[0]
                if not size or any(ch not in b"0123456789abcdefABCDEF" for ch in size):
                    raise ValueError("Invalid HTTP chunk size")
                self.chunk_size = int(size, 16)
                del self.pending[:end + 2]
                if self.chunk_size + len(self.body) > MAX_BODY:
                    raise ValueError("HTTP body exceeds the memory limit")
                if self.chunk_size == 0:
                    self.trailers = True
                    continue
            if len(self.pending) < self.chunk_size + 2:
                return
            if self.pending[self.chunk_size:self.chunk_size + 2] != b"\r\n":
                raise ValueError("Invalid HTTP chunk terminator")
            self.body.extend(self.pending[:self.chunk_size])
            del self.pending[:self.chunk_size + 2]
            self.chunk_size = None

    def eof(self):
        if self.headers is None:
            raise ValueError("Connection closed before HTTP headers")
        if not self.chunked and self.length is None:
            self.done = True
        if not self.done:
            raise ValueError("Truncated HTTP response")

    def result(self):
        if not self.done:
            raise ValueError("HTTP response is incomplete")
        return json.loads(bytes(self.body).decode("utf-8")), self.headers


class HttpClient:
    def __init__(self, credentials, timeout_ms):
        validate_secrets(credentials)
        self.scheme, self.host, self.port, self.prefix, self.authority = parse_url(
            credentials["base_url"])
        self.ip = credentials.get("connect_ip", self.host)
        self.token = credentials["token"]
        self.timeout_ms = timeout_ms
        self.sock = None
        self.phase = None
        self.tls = None
        self.ssl_module = None
        if self.scheme == "https":
            import ssl
            self.ssl_module = ssl
            self.tls = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            self.tls.verify_mode = ssl.CERT_REQUIRED
            ca_file = credentials.get("ca_file")
            if ca_file:
                self.tls.load_verify_locations(cafile=ca_file)
            elif hasattr(self.tls, "load_default_certs"):
                self.tls.load_default_certs()
            else:
                raise ValueError("HTTPS on the badge requires ca_file and a correct RTC")

    def start(self, path, now):
        if self.sock is not None:
            raise RuntimeError("An HTTP request is already in progress")
        self.started = now
        self.response = Response()
        self.sent = 0
        self.request = (
            "GET %s%s HTTP/1.1\r\nHost: %s\r\nAuthorization: Bearer %s\r\n"
            "Accept: application/json\r\nAccept-Encoding: identity\r\n"
            "Connection: close\r\nUser-Agent: SolarBuddy/1.0\r\n\r\n"
            % (self.prefix, path, self.authority, self.token)).encode()
        address = socket.getaddrinfo(self.ip, self.port, socket.AF_INET, socket.SOCK_STREAM)[0]
        self.sock = socket.socket(address[0], address[1], address[2])
        try:
            self.sock.setblocking(False)
            try:
                self.sock.connect(address[-1])
            except OSError as exc:
                if not self._busy(exc):
                    raise
            self.phase = "connect"
        except OSError:
            self.close()
            raise

    def _busy(self, exc):
        if self.ssl_module is not None:
            for name in ("SSLWantReadError", "SSLWantWriteError"):
                cls = getattr(self.ssl_module, name, None)
                if cls is not None and isinstance(exc, cls):
                    return True
        return bool(exc.args) and exc.args[0] in _BUSY

    def _writable(self):
        if hasattr(select, "poll"):
            poller = select.poll()
            poller.register(self.sock, select.POLLOUT)
            return bool(poller.poll(0))
        _readable, writable, errors = select.select([], [self.sock], [self.sock], 0)
        return bool(writable or errors)

    def step(self, now):
        if self.sock is None:
            return None
        if elapsed(now, self.started) >= self.timeout_ms:
            self.close()
            raise OSError("Home Assistant request timed out")
        try:
            if self.phase == "connect":
                if not self._writable():
                    return None
                if hasattr(socket, "SO_ERROR") and hasattr(self.sock, "getsockopt"):
                    error = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                    if error:
                        raise OSError(error, "Connection failed")
                if self.tls is not None:
                    self.sock = self.tls.wrap_socket(
                        self.sock, server_hostname=self.host, do_handshake_on_connect=False)
                    self.sock.setblocking(False)
                self.phase = "send"
                return None
            if self.phase == "send":
                part = memoryview(self.request)[self.sent:self.sent + 1024]
                count = self.sock.write(part) if self.tls else self.sock.send(part)
                if count is None:
                    return None
                if count == 0:
                    raise OSError("Connection closed while sending the request")
                self.sent += count
                if self.sent == len(self.request):
                    self.phase = "read"
                    self.request = b""
                return None
            data = self.sock.read(1024) if self.tls else self.sock.recv(1024)
            if data is None:
                return None
            if data:
                self.response.feed(data)
            else:
                self.response.eof()
            if self.response.done:
                result = self.response.result()
                self.close()
                return result
        except OSError as exc:
            if self._busy(exc):
                return None
            self.close()
            raise
        except (ValueError, TypeError):
            self.close()
            raise
        return None

    def close(self):
        sock, self.sock = self.sock, None
        self.phase = None
        self.request = b""
        if sock is not None:
            sock.close()
