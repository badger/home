"""Wi-Fi camera for the October 2026 Badgeware firmware."""

import binascii
import json
import network
import os
import time

from camera_core import CameraError, MAX_THUMB, PhotoStore, Request, jpeg_dimensions, jpeg_rotation

badge.mode(HIRES | VSYNC)
screen.font = font.nope
screen.antialias = image.OFF


class CameraApp:
    def __init__(self, config_path="/camera_config.json", cache_path="/state/camera"):
        self.request = None
        self.operation = None
        self.mode = "CONNECTING"
        self.frame = None
        self.frame_brush = None
        self.frame_rect = None
        self.rotation = 0
        self.frame_rotation = 0
        self.message = "Connecting to camera..."
        self.detail = ""
        self.store = None
        self.config = None
        self.pending = None
        self.gallery_index = 0
        self.next_preview = 0
        self.connecting_since = None
        self.wlan = network.WLAN(network.STA_IF)
        self.was_active = self.wlan.active()
        try:
            self.store = PhotoStore(cache_path)
            self.rotation = self.store.rotation()
            self.pending = self.store.pending()
            with open(config_path) as file:
                self.config = json.load(file)
            if not isinstance(self.config.get("ssid"), str) or not self.config["ssid"]:
                raise CameraError("Missing camera SSID")
            if not isinstance(self.config.get("password"), str):
                raise CameraError("Missing camera password")
            # This private AP protocol uses an IPv4 literal: never block on DNS.
            host = self.config.get("host", "192.168.4.1")
            parts = host.split(".")
            if len(parts) != 4 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
                raise CameraError("Camera host must be an IPv4 address")
            self.config["host"] = host
            self.config["port"] = int(self.config.get("port", 80))
            if not 1 <= self.config["port"] <= 65535:
                raise CameraError("Invalid camera port")
            if self.pending:
                self.error("Unfinished photo", "Select retries safely")
            else:
                self.connect()
        except (OSError, ValueError, CameraError) as error:
            self.error("Camera setup needed", str(error))

    def cancel_request(self):
        if self.request:
            self.request.close()
            self.request = None

    def error(self, message, detail="Select to retry"):
        self.cancel_request()
        self.mode = "ERROR"
        self.message = message
        self.detail = detail
        print("Camera:", message, detail)

    def connect(self):
        if not self.config:
            self.error("Install camera_config.json", "See esp32-cam/README.md")
            return
        self.mode = "CONNECTING"
        self.message = "Connecting to camera..."
        self.detail = "Camera needs separate USB power"
        self.wlan.active(True)
        self.wlan.disconnect()
        self.wlan.connect(self.config["ssid"], self.config["password"])
        self.connecting_since = time.ticks_ms()

    def start_request(self, operation, path, method="GET", limit=65536):
        self.operation = operation
        self.request = Request(self.config["host"], self.config["port"], path,
                               method, limit, 30000 if operation == "capture" else 12000)

    def take_photo(self):
        if not self.pending:
            photo_id = binascii.hexlify(os.urandom(8)).decode()
            self.store.begin(photo_id)
            self.pending = photo_id
        self.mode = "CAPTURING"
        self.message = "Saving 1600x1200 to SD..."
        self.detail = "Keep camera powered"
        self.start_request("capture", "/capture?id=" + self.pending
                           + "&rotation=" + str(self.rotation * 90), "POST", 2048)

    def set_frame(self, data, saved=False):
        jpeg_dimensions(data)
        frame = image.load(data, 320, 240)
        rotation = jpeg_rotation(data, self.rotation) if saved else self.rotation
        self.prepare_frame(frame, rotation)

    def prepare_frame(self, frame, rotation):
        width, height = frame.width, frame.height
        rotated_width, rotated_height = (height, width) if rotation % 2 else (width, height)
        scale = min(320 / rotated_width, 195 / rotated_height)
        transform = (mat3().translate(160, 119.5).scale(scale, scale)
                     .rotate(rotation * 90).translate(-width / 2, -height / 2))
        frame_brush = brush.image(frame, transform)
        width, height = int(rotated_width * scale), int(rotated_height * scale)
        frame_rect = rect((320 - width) // 2, 22 + (195 - height) // 2, width, height)
        self.frame, self.frame_rotation = frame, rotation
        self.frame_brush, self.frame_rect = frame_brush, frame_rect

    def rotate(self, step):
        rotation = (self.frame_rotation + step) % 4
        self.store.set_rotation(rotation)
        self.rotation = self.frame_rotation = rotation
        if self.frame is not None:
            self.prepare_frame(self.frame, rotation)

    def show_gallery(self, step):
        if not self.store or not self.store.photos:
            self.detail = "No saved photos on badge"
            return
        self.cancel_request()
        if self.mode == "GALLERY":
            self.gallery_index = (self.gallery_index + step) % len(self.store.photos)
        else:
            self.gallery_index = len(self.store.photos) - 1
        name = self.store.photos[self.gallery_index]
        with open(self.store.path(name), "rb") as file:
            data = file.read(MAX_THUMB + 1)
        if len(data) > MAX_THUMB:
            raise CameraError("Saved thumbnail too large")
        self.set_frame(data, saved=True)
        self.mode = "GALLERY"
        self.message = "Photo %d / %d" % (self.gallery_index + 1, len(self.store.photos))
        self.detail = "Up/down: browse   Select: camera"

    def received(self, data):
        operation = self.operation
        self.request = None
        if operation == "status":
            status = json.loads(data)
            if status.get("protocol") != 1:
                raise CameraError("Incompatible camera firmware")
            if not status.get("camera"):
                raise CameraError(status.get("error") or "Camera sensor not detected")
            if self.pending:
                self.take_photo()
            else:
                self.mode = "LIVE"
                self.message = "LIVE"
                self.detail = "Select: photo   Up/down: gallery"
                if not status.get("sd"):
                    self.detail = "SD missing - preview only"
        elif operation == "preview":
            self.set_frame(data)
            self.next_preview = time.ticks_ms() + 100
        elif operation == "capture":
            result = json.loads(data)
            if (result.get("id") != self.pending or result.get("saved") is not True
                    or result.get("width") != 1600 or result.get("height") != 1200):
                raise CameraError("Camera did not confirm full-resolution save")
            self.message = "Saved on SD; loading photo..."
            self.start_request("thumbnail", "/thumbnail?id=" + self.pending, limit=MAX_THUMB)
        elif operation == "thumbnail":
            self.set_frame(data, saved=True)
            self.store.add(self.pending, data)
            self.store.finish()
            self.pending = None
            self.mode = "FROZEN"
            self.message = "SAVED 1600x1200 on SD"
            self.detail = "Select: camera   Up/down: gallery"

    def update(self):
        try:
            if badge.pressed(BUTTON_BACK):
                return False
            if self.mode != "CAPTURING":
                if self.mode in ("LIVE", "FROZEN", "GALLERY") and badge.pressed(BUTTON_LEFT):
                    self.rotate(-1)
                elif self.mode in ("LIVE", "FROZEN", "GALLERY") and badge.pressed(BUTTON_RIGHT):
                    self.rotate(1)
                elif badge.pressed(BUTTON_UP):
                    self.show_gallery(-1)
                elif badge.pressed(BUTTON_DOWN):
                    self.show_gallery(1)
                elif badge.pressed(BUTTON_SELECT):
                    if self.mode == "LIVE":
                        self.cancel_request()
                        self.take_photo()
                    elif self.mode in ("FROZEN", "GALLERY", "ERROR"):
                        self.frame = None
                        self.connect()
            if self.mode == "CONNECTING" and self.request is None:
                if self.wlan.isconnected():
                    self.start_request("status", "/status", limit=2048)
                elif time.ticks_diff(time.ticks_ms(), self.connecting_since) > 15000:
                    self.error("Camera Wi-Fi not found", "Power camera; Select retries")
            if self.request:
                data = self.request.step()
                if data is not None:
                    self.received(data)
            if self.mode == "LIVE" and self.request is None:
                if time.ticks_diff(time.ticks_ms(), self.next_preview) >= 0:
                    self.start_request("preview", "/preview")
        except (OSError, ValueError, KeyError, TypeError, MemoryError, CameraError) as error:
            self.error(str(error), "Select retries same photo" if self.pending else "Select to reconnect")
        self.draw()

    def draw(self):
        screen.pen = color.black
        screen.clear()
        if self.frame is not None:
            screen.pen = self.frame_brush
            screen.rectangle(self.frame_rect)
        screen.pen = color.rgb(0, 0, 0, 190)
        screen.rectangle(0, 0, 320, 22)
        screen.rectangle(0, 217, 320, 23)
        screen.pen = color.white
        screen.font = font.nope
        screen.text(self.message[:46], 5, 5)
        screen.text(self.detail[:48], 5, 224)
        if self.mode in ("CONNECTING", "ERROR", "CAPTURING"):
            screen.pen = color.rgb(0, 0, 0, 220)
            screen.rectangle(8, 75, 304, 80)
            screen.pen = color.white
            words = self.message.split()
            line = ""
            y = 90
            for word in words:
                candidate = (line + " " + word).strip()
                if screen.measure_text(candidate)[0] > 288 and line:
                    screen.text(line, 16, y)
                    y += 16
                    line = word
                else:
                    line = candidate
            screen.text(line, 16, y)

    def close(self):
        self.cancel_request()
        self.wlan.disconnect()
        if not self.was_active:
            self.wlan.active(False)


app = CameraApp()
try:
    run(app.update)
finally:
    app.close()
