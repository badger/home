"""Run after restarting the camera; verify installed launcher path and rekeying."""

import json
import machine
import sys
import time

watchdog = machine.WDT(timeout=8000)
with open("/camera_config.json") as file:
    before = json.load(file)
real_run = run
namespace = dict(globals())
start = time.ticks_ms()
live_since = None
frames = 0
previous = None


def bounded_run(update):
    def tick():
        global live_since, frames, previous
        watchdog.feed()
        result = update()
        app = namespace["app"]
        if app.mode == "ERROR":
            raise RuntimeError(app.message)
        if app.mode == "LIVE" and app.frame is not None:
            if live_since is None:
                live_since = time.ticks_ms()
            if app.frame is not previous:
                frames += 1
                previous = app.frame
            if time.ticks_diff(time.ticks_ms(), live_since) >= 10000:
                return False
        if time.ticks_diff(time.ticks_ms(), start) > 60000:
            raise RuntimeError("Installed app reconnect timed out")
        return result
    real_run(tick)


namespace["run"] = bounded_run
sys.path.insert(0, "/system/apps/camera")
try:
    with open("/system/apps/camera/__init__.py") as file:
        exec(file.read(), namespace)
    with open("/camera_config.json") as file:
        after = json.load(file)
    assert before["pair_key"] == after["pair_key"]
    assert before["camera_id"] == after["camera_id"]
    assert before["password"] != after["password"]
    assert frames >= 10
    print("PASS installed launcher app reconnected after camera restart")
    print("PASS fresh Wi-Fi password; same saved pairing; frames", frames)
    print("BLE_RECONNECT_PROBE_PASS")
finally:
    watchdog.feed()
