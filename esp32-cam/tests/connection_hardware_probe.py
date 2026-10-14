"""Measure cached startup, photo resume, and BLE recovery on the physical badge."""

import json
import machine
import os
import sys
import time

sys.path.insert(0, "/system/apps/camera")
import camera_ble

watchdog = machine.WDT(timeout=8000)
scenario = globals().get("CONNECTION_SCENARIO", "cached")
counts = {"ble": 0, "scan": 0, "wifi": 0}
real_provisioner = camera_ble.Provisioner


class CountedProvisioner(real_provisioner):
    def __init__(self, *args):
        counts["ble"] += 1
        super().__init__(*args)

    def scan(self):
        counts["scan"] += 1
        return super().scan()

    def step(self):
        if globals().get("TRACE_CONNECTION"):
            for event, data in self.events:
                if event in (7, 8, 9, 10, 11, 12):
                    print("BLE_EVENT", event, data)
        return super().step()


camera_ble.Provisioner = CountedProvisioner
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
CameraApp = namespace["CameraApp"]
real_connect = CameraApp.connect_wifi


def counted_connect(self, *args, **kwargs):
    counts["wifi"] += 1
    return real_connect(self, *args, **kwargs)


CameraApp.connect_wifi = counted_connect
test_config = "/camera-speed-config.json"
with open("/camera_config.json") as file:
    before = json.load(file)
config_path = "/camera_config.json"
if scenario == "address":
    config = dict(before)
    config["ble_addr"] = "000000000001"
    config.pop("password", None)
    with open(test_config, "w") as file:
        json.dump(config, file)
    config_path = test_config
app = None


def tick():
    watchdog.feed()
    app.update()
    display.update()
    if app.mode == "ERROR":
        raise RuntimeError(app.message)
    time.sleep_ms(5)


def wait(predicate, timeout=40000):
    started = time.ticks_ms()
    while not predicate():
        tick()
        if time.ticks_diff(time.ticks_ms(), started) > timeout:
            raise RuntimeError("Connection probe timeout")
    return time.ticks_diff(time.ticks_ms(), started)


def press(key):
    buttons.keys = (key,)
    try:
        tick()
    finally:
        buttons.keys = ()


try:
    start = time.ticks_ms()
    app = CameraApp(config_path=config_path)
    wait(lambda: app.mode == "LIVE" and app.frame is not None)
    print("STARTUP_MS", time.ticks_diff(time.ticks_ms(), start), "COUNTS", counts)
    if scenario == "cached":
        assert counts == {"ble": 0, "scan": 0, "wifi": 1}, counts
        for index in range(2):
            press(BUTTON_SELECT)
            wait(lambda: app.mode == "FROZEN")
            start = time.ticks_ms()
            press(BUTTON_SELECT)
            wait(lambda: app.mode == "LIVE" and app.frame is not None)
            elapsed = time.ticks_diff(time.ticks_ms(), start)
            print("PHOTO_RESUME_MS", elapsed)
            assert elapsed < 2000
            assert counts == {"ble": 0, "scan": 0, "wifi": 1}, counts
        press(BUTTON_UP)
        assert app.mode == "GALLERY"
        press(BUTTON_SELECT)
        wait(lambda: app.mode == "LIVE" and app.frame is not None)
        assert counts == {"ble": 0, "scan": 0, "wifi": 1}, counts
        print("PASS photo and gallery resume reuse existing Wi-Fi")
    elif scenario == "reboot":
        assert counts == {"ble": 1, "scan": 0, "wifi": 2}, counts
        assert app.config["pair_key"] == before["pair_key"]
        assert app.config["password"] != before["password"]
        print("PASS stale Wi-Fi falls back to direct BLE and refreshes password")
    elif scenario == "address":
        assert counts == {"ble": 1, "scan": 1, "wifi": 1}, counts
        assert app.config["ble_addr"] != "000000000001"
        assert app.config["pair_key"] == before["pair_key"]
        print("PASS stale BLE address falls back to matching camera discovery")
    else:
        raise ValueError("Unknown scenario")
    print("CONNECTION_HARDWARE_PROBE_PASS", scenario)
finally:
    if app:
        app.close()
    if scenario == "address":
        os.remove(test_config)
    camera_ble.Provisioner = real_provisioner
