"""Watchdog-protected BLE lifecycle isolation on the real badge."""

import json
import machine
import time
import sys

watchdog = machine.WDT(timeout=8000)
variant = globals().get("BLE_VARIANT", "display")
p = None


def mark(message):
    watchdog.feed()
    with open("/ble_probe_stage.txt", "w") as file:
        file.write(message)
    print(message)

try:
    from camera_ble import Provisioner
    print("ISOLATION", variant)
    if variant == "wlan":
        import network
        wlan = network.WLAN(network.STA_IF)
        print("WLAN initially active", wlan.active())
        wlan.disconnect()
        wlan.active(False)
        print("WLAN disabled")
    if variant in ("display", "mode", "disconnect"):
        badge.mode(HIRES | VSYNC)
        screen.font = font.nope
        screen.antialias = image.OFF
    config = json.load(open("/camera_config.json"))
    p = Provisioner(config, "/camera_config.json")
    original = p.irq

    def traced(event, data):
        if event != 5:
            print("IRQ", event)
        return original(event, data)

    p.ble.irq(traced)
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < 60000:
        watchdog.feed()
        result = p.step()
        if p.state == "CHOOSE":
            p.choose()
        if variant in ("display", "disconnect"):
            screen.pen = color.black
            screen.clear()
            screen.pen = color.white
            screen.text(p.message, 5, 5)
            display.update()
        if result:
            print("PASS", variant, "credentials received")
            break
        time.sleep_ms(10)
    else:
        raise RuntimeError("Isolation timed out")
except Exception as error:
    sys.print_exception(error)
finally:
    if p:
        mark("Closing BLE")
        if variant == "disconnect" and p.conn is not None:
            print("Disconnecting peer")
            p.ble.gap_disconnect(p.conn)
            for _ in range(100):
                watchdog.feed()
                time.sleep_ms(10)
            print("Peer disconnect wait complete")
        mark("Before removing IRQ")
        p.ble.irq(lambda event, data: None)
        mark("Before BLE inactive")
        p.ble.active(False)
        mark("BLE closed")
    print("ISOLATION REBOOT")
    machine.reset()
