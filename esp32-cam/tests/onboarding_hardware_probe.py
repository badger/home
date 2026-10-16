"""Check first-use UI and Select discovery without changing the real pairing."""

import bluetooth
import machine
import os
import sys
import time

sys.path.insert(0, "/system/apps/camera")
watchdog = machine.WDT(timeout=8000)
real_badge = badge


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

app = None
try:
    assert "camera-onboarding-test.json" not in os.listdir("/"), "Disposable test path is occupied"
    before = bluetooth.BLE().active()
    app = namespace["CameraApp"](config_path="/camera-onboarding-test.json")
    assert app.mode == "WELCOME", app.message
    assert app.message == "Connect new camera"
    for _ in range(10):
        watchdog.feed()
        app.update()
        display.update()
        time.sleep_ms(10)
    assert app.mode == "WELCOME" and app.provisioner is None
    assert bluetooth.BLE().active() == before
    print("PASS first use renders Connect new camera without activating Bluetooth")
    buttons.keys = (BUTTON_SELECT,)
    app.update()
    buttons.keys = ()
    display.update()
    assert app.mode == "PAIRING", app.message
    assert app.provisioner.state == "SCANNING"
    print("PASS Select starts BLE discovery")
    assert "camera-onboarding-test.json" not in os.listdir("/")
    print("ONBOARDING_HARDWARE_PROBE_PASS; real pairing unchanged")
finally:
    if app:
        app.close()
    time.sleep_ms(500)
    machine.reset()
