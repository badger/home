"""Minimal real-badge BLE scan, before attempting the full camera app."""

import bluetooth
import time

print("BLE probe: before activation")
ble = bluetooth.BLE()
ble.active(True)
print("BLE probe: activated")
seen = 0
finished = False


def event(kind, data):
    global seen, finished
    if kind == 5:
        seen += 1
    elif kind == 6:
        finished = True


try:
    ble.irq(event)
    print("BLE probe: before scan")
    ble.gap_scan(5000, 100000, 30000, True)
    start = time.ticks_ms()
    while not finished and time.ticks_diff(time.ticks_ms(), start) < 10000:
        time.sleep_ms(10)
    assert finished, "BLE scan did not finish"
    print("PASS BLE scan completed; advertisements:", seen)
finally:
    ble.irq(None)
    ble.active(False)
