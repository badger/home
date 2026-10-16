"""Bounded, nonblocking camera transport and a persistent 15-photo cache."""

import errno
import json
import os
import select
import socket
import time

MAX_THUMB = 32768
MAX_PREVIEW = 65536
PHOTO_LIMIT = 15
WOULD_BLOCK = (errno.EAGAIN, errno.EINPROGRESS, errno.EALREADY)


class CameraError(Exception):
    pass


def valid_id(value):
    return (isinstance(value, str) and len(value) == 16
            and all(c in "0123456789abcdef" for c in value))


class Request:
    def __init__(self, host, port, path, method="GET", limit=MAX_PREVIEW,
                 timeout=12000):
        self.socket = socket.socket()
        self.poller = select.poll()
        self.started = time.ticks_ms()
        self.timeout = timeout
        self.limit = limit
        self.header = bytearray()
        self.body = None
        self.received = 0
        self.status = 0
        self.sent = 0
        self.wire = ("%s %s HTTP/1.0\r\nHost: %s\r\n"
                     "Connection: close\r\nContent-Length: 0\r\n\r\n"
                     % (method, path, host)).encode()
        try:
            self.socket.setblocking(False)
            self.poller.register(self.socket, select.POLLOUT)
            try:
                self.socket.connect((host, port))
            except OSError as error:
                if error.args[0] not in WOULD_BLOCK:
                    raise
        except Exception:
            self.close()
            raise

    def close(self):
        if self.socket is not None:
            self.poller.unregister(self.socket)
            self.socket.close()
            self.socket = None

    def feed(self, data):
        if self.body is None:
            self.header.extend(data)
            end = self.header.find(b"\r\n\r\n")
            if end < 0:
                if len(self.header) > 2048:
                    raise CameraError("Camera HTTP header too large")
                return
            if end > 2048:
                raise CameraError("Camera HTTP header too large")
            lines = bytes(self.header[:end]).split(b"\r\n")
            status = lines[0].split()
            if len(status) < 2 or not status[0].startswith(b"HTTP/1."):
                raise CameraError("Invalid camera HTTP response")
            self.status = int(status[1])
            headers = {}
            for line in lines[1:]:
                key, value = line.split(b":", 1)
                headers[key.lower()] = value.strip()
            if b"transfer-encoding" in headers or b"content-length" not in headers:
                raise CameraError("Camera must send Content-Length")
            length = int(headers[b"content-length"])
            if length < 0 or length > self.limit:
                raise CameraError("Camera response too large")
            self.body = bytearray(length)
            data = self.header[end + 4:]
            self.header = None
        if self.received + len(data) > len(self.body):
            raise CameraError("Camera response length mismatch")
        self.body[self.received:self.received + len(data)] = data
        self.received += len(data)

    def step(self):
        try:
            if time.ticks_diff(time.ticks_ms(), self.started) >= self.timeout:
                raise CameraError("Camera timed out")
            for _ in range(4):
                events = self.poller.poll(0)
                if not events:
                    return None
                if self.sent < len(self.wire):
                    try:
                        count = self.socket.send(self.wire[self.sent:])
                    except OSError as error:
                        if error.args[0] in WOULD_BLOCK:
                            return None
                        raise
                    if not count:
                        raise CameraError("Camera disconnected")
                    self.sent += count
                    if self.sent == len(self.wire):
                        self.poller.modify(self.socket, select.POLLIN)
                    continue
                try:
                    data = self.socket.recv(2048)
                except OSError as error:
                    if error.args[0] in WOULD_BLOCK:
                        return None
                    raise
                if not data:
                    raise CameraError("Camera response was interrupted")
                self.feed(data)
                if self.body is not None and self.received == len(self.body):
                    self.close()
                    if self.status != 200:
                        raise CameraError(bytes(self.body[:160]).decode("utf-8"))
                    return self.body
            return None
        except Exception:
            self.close()
            raise


def jpeg_dimensions(data):
    """Reject truncated/oversized images before passing them to native decoders."""
    if len(data) < 4 or data[:2] != b"\xff\xd8" or data[-2:] != b"\xff\xd9":
        raise CameraError("Incomplete JPEG")
    index = 2
    while index + 4 <= len(data):
        if data[index] != 255:
            raise CameraError("Invalid JPEG marker")
        marker = data[index + 1]
        if marker == 255:
            index += 1
            continue
        length = (data[index + 2] << 8) | data[index + 3]
        if length < 2 or index + 2 + length > len(data):
            raise CameraError("Invalid JPEG segment")
        if marker == 0xC0:
            if length < 8:
                raise CameraError("Invalid JPEG dimensions")
            height = (data[index + 5] << 8) | data[index + 6]
            width = (data[index + 7] << 8) | data[index + 8]
            if not (0 < width <= 320 and 0 < height <= 240):
                raise CameraError("Camera preview exceeds 320x240")
            return width, height
        if marker == 0xDA:
            break
        index += length + 2
    raise CameraError("Expected a baseline JPEG")


def jpeg_rotation(data, default=0):
    """Read the non-mirrored EXIF orientations used by the companion firmware."""
    offset = 2
    while offset + 4 <= len(data):
        marker = data[offset + 1]
        length = (data[offset + 2] << 8) | data[offset + 3]
        if length < 2 or offset + length + 2 > len(data):
            break
        if marker == 0xE1 and data[offset + 4:offset + 10] == b"Exif\0\0":
            tiff = data[offset + 10:offset + length + 2]
            if len(tiff) < 8 or tiff[:2] not in (b"II", b"MM"):
                break
            order = "little" if tiff[:2] == b"II" else "big"
            start = int.from_bytes(tiff[4:8], order)
            if start + 2 > len(tiff):
                break
            count = int.from_bytes(tiff[start:start + 2], order)
            if count > 64 or start + 2 + count * 12 > len(tiff):
                break
            for index in range(count):
                entry = tiff[start + 2 + index * 12:start + 14 + index * 12]
                if (int.from_bytes(entry[:2], order) == 0x112
                        and int.from_bytes(entry[2:4], order) == 3
                        and int.from_bytes(entry[4:8], order) == 1):
                    return {1: 0, 6: 1, 3: 2, 8: 3}.get(
                        int.from_bytes(entry[8:10], order), default)
        if marker in (0xC0, 0xDA):
            break
        offset += length + 2
    return default


class PhotoStore:
    def __init__(self, directory="/state/camera"):
        self.directory = directory
        try:
            os.mkdir(directory)
        except OSError as error:
            if error.args[0] != errno.EEXIST:
                raise
        self.photos = self.scan()
        self.trim()

    def path(self, name):
        return self.directory + "/" + name

    def rotation(self):
        try:
            with open(self.path("rotation.json")) as file:
                value = json.load(file)
        except OSError as error:
            if error.args[0] == errno.ENOENT:
                return 0
            raise
        if type(value) is not int or not 0 <= value <= 3:
            raise CameraError("Invalid saved rotation")
        return value

    def set_rotation(self, value):
        if type(value) is not int or not 0 <= value <= 3:
            raise CameraError("Invalid rotation")
        with open(self.path("rotation.tmp"), "w") as file:
            json.dump(value, file)
        os.rename(self.path("rotation.tmp"), self.path("rotation.json"))

    def scan(self):
        return sorted(name for name in os.listdir(self.directory)
                      if len(name) == 29 and name[:8].isdigit()
                      and name[8] == "_" and valid_id(name[9:25])
                      and name.endswith(".jpg"))

    def trim(self):
        while len(self.photos) > PHOTO_LIMIT:
            os.remove(self.path(self.photos[0]))
            self.photos.pop(0)

    def pending(self):
        try:
            with open(self.path("pending.json")) as file:
                value = json.load(file)
        except OSError as error:
            if error.args[0] == errno.ENOENT:
                return None
            raise
        if not valid_id(value):
            raise CameraError("Invalid pending photo record")
        return value

    def begin(self, photo_id):
        if not valid_id(photo_id):
            raise CameraError("Invalid capture ID")
        with open(self.path("pending.tmp"), "w") as file:
            json.dump(photo_id, file)
        os.rename(self.path("pending.tmp"), self.path("pending.json"))

    def finish(self):
        os.remove(self.path("pending.json"))

    def add(self, photo_id, jpeg):
        if not valid_id(photo_id) or len(jpeg) > MAX_THUMB:
            raise CameraError("Invalid saved thumbnail")
        jpeg_dimensions(jpeg)
        for name in self.photos:
            if name[9:25] == photo_id:
                return name
        sequence = int(self.photos[-1][:8]) + 1 if self.photos else 1
        if sequence > 99999999:
            raise CameraError("Photo sequence exhausted")
        stat = os.statvfs(self.directory)
        if stat[0] * stat[3] < len(jpeg) + 65536:
            raise CameraError("Badge storage full; original remains on SD")
        name = "%08d_%s.jpg" % (sequence, photo_id)
        temporary = self.path("thumbnail.tmp")
        with open(temporary, "wb") as file:
            if file.write(jpeg) != len(jpeg):
                raise CameraError("Badge thumbnail write was incomplete")
        os.rename(temporary, self.path(name))
        self.photos.append(name)
        self.trim()
        return name
