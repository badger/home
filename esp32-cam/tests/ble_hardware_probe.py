"""Run on a real badge with the camera held against it; no setup-code file."""

import machine
import sys
import time

# A native BLE/display failure can also take USB down. Recover without a host.
watchdog = machine.WDT(timeout=8000)
namespace = dict(globals())
source_path = globals().get("CAMERA_APP_PATH", "/system/apps/camera/__init__.py")
sys.path.insert(0, source_path.rsplit("/", 1)[0])
with open(source_path) as file:
    exec(file.read().split("\napp = CameraApp()")[0], namespace)
CameraApp = namespace["CameraApp"]


def mark(message):
    watchdog.feed()
    with open("/ble_probe_stage.txt", "w") as file:
        file.write(message)
    print(message)


if globals().get("TRACE_BLE", False):
    from camera_ble import Provisioner

    def traced(method, label):
        def wrapper(*args, **kwargs):
            mark("before " + label)
            result = method(*args, **kwargs)
            mark("after " + label)
            return result
        return wrapper

    Provisioner.close = traced(Provisioner.close, "BLE close")
    Provisioner.completed = traced(Provisioner.completed, "BLE response")
    CameraApp.connect_wifi = traced(CameraApp.connect_wifi, "Wi-Fi connect")


def drive(app):
    start = time.ticks_ms()
    chosen = False
    previous = None
    while time.ticks_diff(time.ticks_ms(), start) < 120000:
        watchdog.feed()
        app.update()
        display.update()
        if app.mode == "ERROR":
            if app.message == globals().get("EXPECT_PAIRING_ERROR"):
                mark("PASS camera rejected enrollment: " + app.message)
                return False
            raise RuntimeError(app.message)
        if app.mode == "LIVE" and app.frame is not None:
            assert not globals().get("EXPECT_PAIRING_ERROR"), "Enrollment unexpectedly succeeded"
            mark("PASS BLE provisioning reached real Wi-Fi preview")
            return True
        p = app.provisioner
        state = (app.mode, p.state if p else None)
        if state != previous:
            print("STATE", state)
            previous = state
        if p:
            if p.state == "CHOOSE" and not chosen:
                p.choose()
                chosen = True
        elif app.mode == "WELCOME":
            app.connect()
        time.sleep_ms(10)
    raise RuntimeError("BLE hardware probe timed out")


def main():
    print("Starting camera app")
    watchdog.feed()
    app = CameraApp()
    try:
        if drive(app):
            assert app.config["pairing"] == "srp-v1"
            assert len(app.config["pair_key"]) == 64
            print("PASS pairing and camera identity persisted")
    finally:
        app.close()


try:
    main()
except Exception as error:
    mark("FAIL " + str(error))
    sys.print_exception(error)
finally:
    print("Probe finished; rebooting to standalone launcher")
    time.sleep_ms(1000)
    machine.reset()
