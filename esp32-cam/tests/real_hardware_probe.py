"""Exercise the physical camera and installed badge app over their private Wi-Fi."""

import binascii
import gc
import json
import sys
import time

sys.path.insert(0, "/system/apps/camera")
from camera_core import Request, jpeg_rotation

real_badge = badge
watchdog = globals().get("CAMERA_WATCHDOG")


class Buttons:
    keys = ()

    def mode(self, value):
        return real_badge.mode(value)

    def pressed(self, key):
        return key in self.keys


buttons = Buttons()
namespace = dict(globals())
namespace["badge"] = buttons
with open("/system/apps/camera/__init__.py") as source:
    exec(source.read().split("\napp = CameraApp()")[0], namespace)
app = namespace["CameraApp"]()


def tick():
    if watchdog:
        watchdog.feed()
    app.update()
    display.update()
    time.sleep_ms(5)


def wait_for(predicate, label, timeout=40000):
    start = time.ticks_ms()
    while not predicate():
        tick()
        if app.mode == "ERROR":
            raise RuntimeError(label + ": " + app.message)
        if time.ticks_diff(time.ticks_ms(), start) > timeout:
            raise RuntimeError("Timeout " + label)
    print("PASS", label)


def press(key):
    buttons.keys = (key,)
    tick()
    buttons.keys = ()


def fetch(path, method="GET", limit=2 * 1024 * 1024):
    request = Request(app.config["host"], app.config["port"], path, method, limit, 30000)
    while True:
        if watchdog:
            watchdog.feed()
        data = request.step()
        if data is not None:
            return data
        time.sleep_ms(5)


def dimensions(data):
    assert data[:2] == b"\xff\xd8" and data[-2:] == b"\xff\xd9"
    offset = 2
    while offset + 9 < len(data):
        assert data[offset] == 255
        marker = data[offset + 1]
        length = (data[offset + 2] << 8) | data[offset + 3]
        if marker == 192:
            return ((data[offset + 7] << 8) | data[offset + 8],
                    (data[offset + 5] << 8) | data[offset + 6])
        offset += length + 2
    raise AssertionError("No JPEG dimensions")


try:
    wait_for(lambda: app.mode == "LIVE" and app.frame is not None, "real Wi-Fi live view")
    previous = app.frame
    frames = 0
    start = time.ticks_ms()
    gc.collect()
    initial_memory = gc.mem_free()
    while time.ticks_diff(time.ticks_ms(), start) < 30000:
        tick()
        if app.mode == "ERROR":
            raise RuntimeError(app.message)
        if app.frame is not previous:
            previous = app.frame
            frames += 1
    gc.collect()
    print("LIVE", frames, "frames in 30 seconds; free memory", initial_memory, gc.mem_free())
    assert frames >= 10
    for index in range(2):
        press(BUTTON_SELECT)
        wait_for(lambda: app.mode == "FROZEN", "real SD capture %d" % (index + 1))
        name = app.store.photos[-1]
        photo_id = name[9:25]
        full = fetch("/photo?id=" + photo_id)
        assert dimensions(full) == (1600, 1200)
        assert jpeg_rotation(full, -1) == app.rotation
        checksum = binascii.crc32(full)
        length = len(full)
        del full
        confirmation = json.loads(fetch("/capture?id=" + photo_id, "POST", 2048))
        assert confirmation["id"] == photo_id and confirmation["saved"]
        repeated = fetch("/photo?id=" + photo_id)
        assert len(repeated) == length and binascii.crc32(repeated) == checksum
        del repeated
        thumb = fetch("/thumbnail?id=" + photo_id, limit=32768)
        assert dimensions(thumb) == (200, 150)
        assert jpeg_rotation(thumb, -1) == app.rotation
        with open(app.store.path(name), "rb") as file:
            assert file.read() == thumb
        frozen = bytes(app.frame.raw)
        for _ in range(50):
            tick()
        assert frozen == app.frame.raw
        print("SAVED", photo_id, "JPEG_BYTES", length, "CRC32", checksum,
              "THUMB_BYTES", len(thumb))
        print("PASS exact saved thumbnail cached, freeze stable, retry idempotent")
        del frozen, thumb
        if index == 0:
            press(BUTTON_SELECT)
            wait_for(lambda: app.mode == "LIVE" and app.frame is not None, "real preview resumes")
    press(BUTTON_UP)
    assert app.mode == "GALLERY"
    newest = app.gallery_index
    press(BUTTON_UP)
    assert app.gallery_index == (newest - 1) % len(app.store.photos)
    print("PASS real-photo gallery")
    print("REAL_HARDWARE_PROBE_PASS")
finally:
    app.close()
