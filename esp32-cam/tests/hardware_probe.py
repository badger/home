"""Run with mpremote on a 2026 badge against tests/mock_camera.py.

Requires app files and a private test Wi-Fi config in /camera-test/.
Only /state/camera-test is used for synthetic photos; production photos stay intact.
"""

import gc
import json
import sys
import time

sys.path.insert(0, "/camera-test")
from camera_core import Request
from camera_core import CameraError

real_badge = badge


class Buttons:
    def __init__(self):
        self.keys = ()

    def mode(self, mode):
        return real_badge.mode(mode)

    def pressed(self, key):
        return key in self.keys


buttons = Buttons()
namespace = dict(globals())
namespace["badge"] = buttons
with open("/camera-test/__init__.py") as source:
    exec(source.read().split("\napp = CameraApp()")[0], namespace)

if globals().get("CAMERA_OFFLINE_TEST", False):
    print("OFFLINE SYNTHETIC MODE: display/storage/input test, NOT a Wi-Fi or sensor test")

    class TestWLAN:
        def active(self, value=None):
            return True

        def disconnect(self):
            pass

        def connect(self, ssid, password):
            pass

        def isconnected(self):
            return True

    class TestNetwork:
        STA_IF = 0

        @staticmethod
        def WLAN(interface):
            return TestWLAN()

    class TestRequest:
        captures = set()
        previews = 0
        fail_capture = False

        def __init__(self, host, port, path, method="GET", limit=65536, timeout=12000):
            self.path = path

        def close(self):
            pass

        def step(self):
            cls = type(self)
            if self.path == "/status":
                result = {"protocol": 1, "camera": True, "sd": True}
            elif self.path == "/stats":
                result = {"captures": len(cls.captures), "previews": cls.previews}
            elif self.path.startswith("/test/fail"):
                cls.fail_capture = self.path.endswith("=1")
                result = {"ok": True}
            elif self.path.startswith("/capture"):
                if cls.fail_capture:
                    raise CameraError("SD card unavailable")
                photo_id = self.path.split("=", 1)[1].split("&", 1)[0]
                cls.captures.add(photo_id)
                result = {"id": photo_id, "saved": True, "width": 1600, "height": 1200}
            else:
                filename = "live.jpg" if self.path == "/preview" else "saved.jpg"
                if filename == "live.jpg":
                    cls.previews += 1
                with open("/camera-test/" + filename, "rb") as file:
                    return bytearray(file.read())
            return bytearray(json.dumps(result).encode())

    namespace["network"] = TestNetwork
    namespace["Request"] = TestRequest
    Request = TestRequest

app = namespace["CameraApp"]("/camera-test/config.json", "/state/camera-test")


def tick():
    app.update()
    display.update()
    time.sleep_ms(10)


def press(key):
    buttons.keys = (key,)
    tick()
    buttons.keys = ()


def wait_for(predicate, label, timeout=35000):
    started = time.ticks_ms()
    while not predicate():
        tick()
        if app.mode == "ERROR":
            raise RuntimeError(label + ": " + app.message)
        if time.ticks_diff(time.ticks_ms(), started) > timeout:
            raise RuntimeError("Timeout: " + label)
    print("PASS", label)


def control(path, method="POST"):
    request = Request(app.config["host"], app.config["port"], path, method, 2048)
    while True:
        data = request.step()
        if data is not None:
            return json.loads(data)
        time.sleep_ms(5)


try:
    wait_for(lambda: app.mode == "LIVE" and app.frame is not None, "live JPEG on badge")
    live_pixel = bytes(app.frame.raw[:4])
    gc.collect()
    before = gc.mem_free()
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < 10000:
        tick()
    gc.collect()
    print("LIVE_MEMORY", before, gc.mem_free())
    before_stats = control("/stats", "GET")
    for index in range(17):
        press(BUTTON_SELECT)
        wait_for(lambda: app.mode == "FROZEN", "capture %d saved and frozen" % (index + 1))
        assert app.pending is None
        assert app.frame.width == 200 and app.frame.height == 150
        assert bytes(app.frame.raw[:4]) != live_pixel, "Frozen image must be the saved shot"
        frozen = bytes(app.frame.raw)
        for _ in range(5):
            tick()
        assert frozen == app.frame.raw, "Frozen frame changed"
        if index != 16:
            press(BUTTON_SELECT)
            wait_for(lambda: app.mode == "LIVE" and app.frame is not None, "resume preview")
    assert len(app.store.photos) == 15
    reloaded = namespace["PhotoStore"]("/state/camera-test")
    assert reloaded.photos == app.store.photos
    print("PASS exactly 15 persistent previews after 17 shots")
    press(BUTTON_UP)
    assert app.mode == "GALLERY"
    newest = app.gallery_index
    press(BUTTON_UP)
    assert app.gallery_index == newest - 1
    press(BUTTON_DOWN)
    assert app.gallery_index == newest
    print("PASS gallery up/down navigation")
    press(BUTTON_SELECT)
    wait_for(lambda: app.mode == "LIVE" and app.frame is not None, "gallery select resumes camera")
    control("/test/fail?enabled=1")
    press(BUTTON_SELECT)
    started = time.ticks_ms()
    while app.mode != "ERROR":
        tick()
        assert time.ticks_diff(time.ticks_ms(), started) < 10000
    assert app.pending
    pending = app.pending
    assert app.store.pending() == pending
    print("PASS SD failure visible and pending ID persisted")
    control("/test/fail?enabled=0")
    press(BUTTON_SELECT)
    wait_for(lambda: app.mode == "FROZEN", "retry succeeds without changing capture ID")
    assert app.store.photos[-1][9:25] == pending
    after_stats = control("/stats", "GET")
    assert after_stats["captures"] - before_stats["captures"] == 18
    print("PASS one saved photo per successful shutter")
    print("STATS", after_stats)
    print("HARDWARE_PROBE_PASS")
finally:
    app.close()
