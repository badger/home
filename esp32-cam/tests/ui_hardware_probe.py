"""Check native UI rendering and one real SD capture; preserves pairing/cache."""

import machine
import sys
import time

sys.path.insert(0, "/system/apps/camera")
watchdog = machine.WDT(timeout=8000)
real_badge = badge
real_screen = screen
labels = []


class Buttons:
    keys = ()

    def mode(self, value):
        return real_badge.mode(value)

    def pressed(self, key):
        return key in self.keys


class Screen:
    def __getattr__(self, name):
        return getattr(real_screen, name)

    def __setattr__(self, name, value):
        setattr(real_screen, name, value)

    def text(self, label, *args, **kwargs):
        labels.append(label)
        return real_screen.text(label, *args, **kwargs)


buttons = Buttons()
namespace = dict(globals())
namespace["badge"] = buttons
namespace["screen"] = Screen()
with open("/system/apps/camera/__init__.py") as file:
    exec(file.read().split("\napp = CameraApp()")[0], namespace)
app = namespace["CameraApp"]()
display_only = globals().get("UI_DISPLAY_ONLY", False)
if display_only:
    print("DISPLAY ONLY: native UI check, not a camera/SD capture test")
    app.cancel_request()
    if app.provisioner:
        app.provisioner.close()
        app.provisioner = None
    app.mode = "LIVE"
    app.message = app.detail = ""
    class DisplayStore:
        def begin(self, photo_id):
            pass

        def finish(self):
            pass

    app.store = DisplayStore()
    app.pending = None
    app.cached_wifi = app.resume_pending = False
    class DisplayRequest:
        def __init__(self, *args):
            pass

        def close(self):
            pass

        def step(self):
            return None

    namespace["Request"] = DisplayRequest
    app.next_preview = time.ticks_ms() + 60000
    sample = image(320, 240)
    sample.pen = color.rgb(50, 80, 120)
    sample.clear()
    app.prepare_frame(sample, app.rotation)


def tick():
    watchdog.feed()
    labels.clear()
    app.update()
    display.update()
    if app.mode == "ERROR":
        raise RuntimeError(app.message + ": " + app.detail)
    time.sleep_ms(10)


def wait(predicate):
    start = time.ticks_ms()
    while not predicate():
        tick()
        if time.ticks_diff(time.ticks_ms(), start) > 45000:
            raise RuntimeError("UI probe timed out")


def press(key):
    buttons.keys = (key,)
    try:
        tick()
    finally:
        buttons.keys = ()


try:
    wait(lambda: app.mode == "LIVE" and app.frame is not None)
    tick()
    assert not labels, labels
    print("PASS clean live view")
    app.mode = "CONNECTING"
    app.draw()
    assert labels.count("Connecting to") == 1
    assert labels.count("your camera...") == 1
    app.mode = "LIVE"
    tick()
    started = time.ticks_ms()
    press(BUTTON_SELECT)
    assert app.mode == "COUNTDOWN"
    numbers = set()
    while app.mode == "COUNTDOWN":
        numbers.update(label for label in labels if label in ("3", "2", "1"))
        tick()
    assert numbers == {"3", "2", "1"}, numbers
    assert time.ticks_diff(time.ticks_ms(), started) >= 3000
    assert app.mode == "CAPTURING"
    assert all(value == 255 for value in real_screen.raw), "Shutter framebuffer not white"
    assert not labels
    print("PASS animated 3-2-1 and white native shutter frame")
    if display_only:
        app.cancel_request()
        # No HTTP request was progressed and no real photograph was requested.
        app.store.finish()
        app.pending = None
        app.mode = "FROZEN"
        app.message = "Photo 1 / 1"
        app.detail = ""
        labels.clear()
        app.draw()
        assert labels == ["Photo 1 / 1"]
        assert app.menu_mona is not None, "Expected the launcher's native 3D Mona"
        print("PASS actual menu 3D Mona and clean review rendering")
        print("CAMERA_UI_DISPLAY_PROBE_PASS")
    else:
        wait(lambda: app.mode == "FROZEN")
        assert labels == [app.message], labels
        assert app.message.startswith("Photo ")
        assert not app.detail
        print("PASS saved photo review without control hints")
        press(BUTTON_UP)
        assert app.mode == "GALLERY"
        assert labels == [app.message], labels
        press(BUTTON_SELECT)
        wait(lambda: app.mode == "LIVE" and app.frame is not None)
        tick()
        assert not labels
        print("CAMERA_UI_HARDWARE_PROBE_PASS")
finally:
    app.close()
