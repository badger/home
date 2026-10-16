"""Native 2026 check; mount badge/apps/Copilot as /remote before running."""

import gc
import machine
import os
import sys
import time


watchdog = machine.WDT(timeout=15000)
sys.path.insert(0, "/remote")
namespace = dict(globals())
with open("/remote/__init__.py") as source:
    exec(source.read().split("\napp = CopilotApp()")[0], namespace)


class MountedImages:
    OFF = image.OFF

    def load(self, path):
        # Native filename reads use text mode, which mpremote's host VFS cannot
        # serve for PNGs. Only the probe uses a binary buffer for mounted assets.
        with open(path, "rb") as source:
            return image.load(source.read())


namespace["image"] = MountedImages()
app = namespace["CopilotApp"]("/remote/assets", monitor=False)

try:
    from copilot_monitor import Protocol, Server
    pairing_path = "/state/copilot-monitor-probe.json"
    try:
        os.stat(pairing_path)
    except OSError as error:
        if error.args[0] != 2:
            raise
    else:
        raise RuntimeError("Monitor probe file already exists; refusing to overwrite it")
    try:
        protocol = Protocol(pairing_path)
        now = time.ticks_ms()
        protocol.open_pairing(now)
        status, pairing = protocol.handle("POST", "/pair", {}, protocol.pairing_code.encode(), now)
        assert status == 200
        headers = {"authorization": "Bearer " + pairing["token"]}
        assert Protocol(pairing_path).token == pairing["token"]
        for mode in ("working", "attention", "complete", "idle"):
            status, _ = protocol.handle("POST", "/state", headers, mode.encode(), now)
            assert status == 200 and protocol.state == mode
        for endpoint, payload in (("/icon", "%copilot:58a6ff:" + "A" * 96),
                                  ("/agents", "&copilot=w"), ("/usage", "$AIC: 1.2")):
            assert protocol.handle("POST", endpoint, headers, payload.encode(), now)[0] == 200
        assert protocol.live(now)
        server = Server(protocol, port=8086, discovery_port=4668)
        try:
            server.step(now)
        finally:
            server.close()
        protocol.expire(time.ticks_add(now, 15000))
        assert not protocol.live(time.ticks_add(now, 15000))
        class LivePreview:
            message = "Live session monitor"
            address = "192.0.2.10"

            def close(self):
                pass

        preview = LivePreview()
        preview.protocol = protocol
        protocol.icons["copilot"] = ((88, 166, 255), bytes([128] + [0] * 71))
        protocol.agents = [("copilot", "w")]
        protocol.usage = ["AIC: 1.2", "Tokens: 9K"]
        app.monitor = preview
        app.was_live = True
        app.mode = "working"
        app.draw()
        display.update()
        protocol.open_pairing(time.ticks_ms())
        app.draw()
        display.update()
        protocol.pairing_code = None
        app.monitor = False
        app.was_live = False
        app.icon_cache = {}
        print("COPILOT_MONITOR_NATIVE_PASS")
    finally:
        try:
            os.remove(pairing_path)
        except OSError as error:
            if error.args[0] != 2:
                raise
    path = "/copilot-native-probe.png"
    try:
        os.stat(path)
    except OSError as error:
        if error.args[0] != 2:
            raise
    else:
        raise RuntimeError("Probe file already exists; refusing to overwrite it")
    try:
        with open("/remote/assets/neutral.png", "rb") as source:
            data = source.read()
        with open(path, "wb") as destination:
            destination.write(data)
        del data
        started = time.ticks_ms()
        sample = image.load(path)
        assert (sample.width, sample.height) == (192, 180)
        print("PASS native filename PNG decode:", time.ticks_diff(time.ticks_ms(), started), "ms")
        del sample
    finally:
        os.remove(path)
    gc.collect()
    baseline = gc.mem_free()
    count = 0
    for track in ("neutral", "blink", "left", "right", "up", "down",
                  "surprise", "working", "attention", "complete"):
        names = ("neutral",) if track == "neutral" else (
            tuple("blink-%d" % index for index in range(1, 5)) if track == "blink" else
            tuple("%s-%02d" % (track, index) for index in range(12)))
        started = time.ticks_ms()
        for name in names:
            watchdog.feed()
            app.load_frame(name)
            assert app.error is None, (name, app.error)
            assert app.sprite.width == 192 and app.sprite.height == 180, name
            app.mode = track if track in namespace["LABELS"] else "idle"
            app.draw()
            display.update()
            assert any(screen.raw), "Blank framebuffer"
            count += 1
        gc.collect()
        print("PASS", track, len(names), "frames,", time.ticks_diff(time.ticks_ms(), started),
              "ms, free:", gc.mem_free())
    assert count == 101, count
    app.close()
    gc.collect()
    assert gc.mem_free() >= baseline - 32768, "Unexpected retained frame memory"
    print("COPILOT_NATIVE_PASS", count)
except Exception as error:
    print("COPILOT_NATIVE_FAIL", repr(error))
    raise
finally:
    app.close()
    time.sleep_ms(200)
    machine.reset()
