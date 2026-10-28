"""Bounded asynchronous batch downloads with an atomic two-slot offline cache."""

import gc
import json
import os
import struct

MAX_PHOTOS = 20
MAX_PHOTO_BYTES = 128 * 1024
MAX_MANIFEST_BYTES = 8192
REQUEST_MS = 30000
BATCH_MS = 120000
CACHE_DIR = "/state/linkedin_photo"


def parse_url(url):
    if not isinstance(url, str) or len(url) > 1024:
        raise ValueError("URL must be a string of at most 1024 characters")
    if any(ord(char) <= 32 or ord(char) >= 127 for char in url) or "#" in url:
        raise ValueError("URL must be ASCII, encoded, and have no fragment")
    if url.startswith("https://"):
        secure, rest = True, url[8:]
    elif url.startswith("http://"):
        secure, rest = False, url[7:]
    else:
        raise ValueError("Use an http:// or https:// URL")
    end = len(rest)
    for separator in ("/", "?"):
        index = rest.find(separator)
        if index >= 0:
            end = min(end, index)
    authority, path = rest[:end], rest[end:] or "/"
    if path.startswith("?"):
        path = "/" + path
    if not authority or "@" in authority or "\\" in url:
        raise ValueError("URL must have a host and no embedded credentials")
    parts = authority.split(":")
    if len(parts) > 2 or not parts[0]:
        raise ValueError("Use a hostname or IPv4 address")
    port = int(parts[1]) if len(parts) == 2 else (443 if secure else 80)
    if not 1 <= port <= 65535:
        raise ValueError("Invalid URL port")
    return secure, parts[0], port, path


def manifest_urls(data):
    if not isinstance(data, dict) or not isinstance(data.get("photos"), list):
        raise ValueError('Batch JSON must contain a "photos" array')
    urls = data["photos"]
    if not 1 <= len(urls) <= MAX_PHOTOS:
        raise ValueError("Batch must contain 1 to %d photos" % MAX_PHOTOS)
    for url in urls:
        parse_url(url)
    return urls


def read_config(path="config.json"):
    try:
        with open(path) as handle:
            data = json.loads(handle.read(4097))
    except OSError as error:
        if error.args[0] == 2:
            return ""
        raise
    if not isinstance(data, dict) or not isinstance(data.get("batch_url", ""), str):
        raise ValueError("config.json batch_url must be a string")
    url = data.get("batch_url", "").strip()
    if url:
        parse_url(url)
    return url


def check_png(data):
    if len(data) < 33 or bytes(data[:8]) != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Photo response must be a PNG, not JPEG or HTML")
    if bytes(data[8:16]) != b"\x00\x00\x00\rIHDR":
        raise ValueError("Invalid PNG header")
    width, height, depth, kind, compression, filtering, interlace = struct.unpack(
        ">IIBBBBB", data[16:29]
    )
    if not (1 <= width <= 320 and 1 <= height <= 240):
        raise ValueError("Prepare PNGs within 320x240 before hosting")
    if depth != 8 or kind not in (2, 3, 6) or compression or filtering or interlace:
        raise ValueError("Use an 8-bit RGB, RGBA or indexed non-interlaced PNG")


class BatchCache:
    def __init__(self, root=CACHE_DIR):
        self.root = root
        self.slot = None

    def cached(self, url):
        try:
            with open(self.root + "/active.json") as handle:
                record = json.loads(handle.read(4097))
        except OSError as error:
            if error.args[0] == 2:
                return []
            raise
        if not isinstance(record, dict):
            raise ValueError("Invalid cached batch record")
        slot, count = record.get("slot"), record.get("count")
        if slot not in ("a", "b") or type(count) is not int or not 1 <= count <= MAX_PHOTOS:
            raise ValueError("Invalid cached batch record")
        self.slot = slot
        if record.get("url") != url:
            return []
        paths = [self.path(slot, index) for index in range(count)]
        for path in paths:
            os.stat(path)
        return paths

    def path(self, slot, index):
        return "%s/%s-%02d.png" % (self.root, slot, index)

    def begin(self):
        try:
            os.mkdir(self.root)
        except OSError as error:
            if error.args[0] != 17:
                raise
        return "b" if self.slot == "a" else "a"

    def commit(self, slot, count, url):
        temporary = self.root + "/active.json.tmp"
        with open(temporary, "w") as handle:
            json.dump({"slot": slot, "count": count, "url": url}, handle)
        os.rename(temporary, self.root + "/active.json")
        self.slot = slot
        return [self.path(slot, index) for index in range(count)]


class BatchRefresh:
    def __init__(self, cache, validate_image):
        self.cache = cache
        self.validate_image = validate_image
        self.busy = False
        self.message = ""
        self.failed = False
        self.request = None
        self.result = None

    def fail(self, message):
        if self.request is not None:
            self.request.reset()
            self.request = None
        self.busy = False
        self.failed = True
        self.message = message
        print("linkedin_photo refresh: " + message)

    def start(self, url):
        if self.busy:
            return
        self.result = None
        self.failed = False
        self.url = url
        self.total_ms = 0
        self.request_ms = 0
        self.urls = None
        self.index = 0
        self.message = "Connecting Wi-Fi..."
        try:
            parse_url(url)
            import secrets
            if not getattr(secrets, "WIFI_SSID", ""):
                raise ValueError("Set Wi-Fi in badge Settings first")
            import wifi
            import fetch
            fetch_class = getattr(fetch, "AsyncFetch", None)
            if not all(callable(getattr(fetch_class, name, None))
                       for name in ("update", "reset", "fetch", "on_error", "to_json")):
                raise RuntimeError("Download API unavailable in this runtime")
            self.wifi = wifi
            self.fetch = fetch
            if not wifi.is_connected():
                # Reset exhausted retry state left by another app before connecting.
                wifi.disconnect()
            self.slot = self.cache.begin()
            self.busy = True
        except (ImportError, OSError, ValueError, RuntimeError) as error:
            self.fail(str(error))

    def begin_request(self, url, limit):
        secure, host, port, path = parse_url(url)
        self.request = self.fetch.AsyncFetch(
            host, port, use_tls=secure, max_bytes=limit, timeout=10,
            step_bytes=4096,
        )
        self.request.on_error(lambda request: True)
        self.request.fetch(path, headers={"User-Agent": "BadgePhoto/1"})
        self.request_ms = 0

    def poll(self, delta_ms):
        if not self.busy:
            return
        self.total_ms += delta_ms
        self.request_ms += delta_ms
        if self.total_ms > BATCH_MS or self.request_ms > REQUEST_MS:
            self.fail("Refresh timed out; keeping current photos")
            return
        try:
            if self.request is None:
                # Large retry count prevents wifi's fatal full-screen error handler.
                if not self.wifi.connect(timeout=10, retries=100000):
                    return
                if self.urls is None:
                    self.message = "Fetching batch list..."
                    self.begin_request(self.url, MAX_MANIFEST_BYTES)
                else:
                    self.message = "Fetching photo %d/%d" % (self.index + 1, len(self.urls))
                    self.begin_request(self.urls[self.index], MAX_PHOTO_BYTES)
            self.request.update()
            if self.request.status == self.fetch.AsyncFetch.ERROR:
                raise ValueError("Server returned HTTP %s" % self.request.http_status)
            if not self.request.done:
                return
            if self.urls is None:
                self.urls = manifest_urls(self.request.to_json())
            else:
                data = self.request.body
                check_png(data)
                path = self.cache.path(self.slot, self.index)
                with open(path, "wb") as handle:
                    handle.write(data)
                del data
                self.request.reset()
                self.request = None
                gc.collect()
                self.validate_image(path)
                self.index += 1
                if self.index == len(self.urls):
                    self.result = self.cache.commit(self.slot, self.index, self.url)
                    self.busy = False
                    self.message = "Batch ready: %d photos" % self.index
                    return
            if self.request is not None:
                self.request.reset()
                self.request = None
            self.request_ms = 0
        except (OSError, ValueError, RuntimeError, MemoryError, TypeError) as error:
            # URLs can contain private query parameters; do not print transport exceptions.
            if self.request is not None and not isinstance(error, (ValueError, MemoryError)):
                self.fail("Download failed; keeping current photos")
            else:
                self.fail(str(error) if isinstance(error, ValueError) else
                          "Cache/image error; keeping current photos")

    def close(self):
        if self.request is not None:
            self.request.reset()
            self.request = None
        self.busy = False
