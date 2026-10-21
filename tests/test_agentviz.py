"""Host checks only; no claims about native firmware, radio or touch behavior."""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools.agentviz.render_preview import APP, ROOT, load_app

sys.path.insert(0, str(APP))
import agentviz_client as client


TOKEN = "b" * 32
PERIOD = 1 << 30


def ticks_diff(a, b):
    return (a - b + PERIOD // 2) % PERIOD - PERIOD // 2


def packet(seq=0, epoch="a" * 32):
    return {"v": 1, "token": TOKEN, "epoch": epoch, "seq": seq, "state": "ok",
            "message": "", "source": "copilot-cli",
            "metrics": [3, 1, 1, 1, 3000, -1, -1],
            "events": [[0, 0, 500, 2, "User input", "user", 0, 0],
                       [1, 500, 1000, 1, "bash", "assistant", 1, 0],
                       [2, 1500, 1500, 3, "Response", "assistant", 0, 0]],
            "tools": [["bash", 1]]}


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.clock = patch.object(client, "time", SimpleNamespace(
            ticks_diff=ticks_diff, ticks_add=lambda a, b: (a + b) % PERIOD,
            ticks_ms=lambda: 100))
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def test_auth_sequence_epochs_and_exact_stale_boundary(self):
        feed = client.Feed(TOKEN)
        start = PERIOD - 100
        self.assertTrue(feed.accept(json.dumps(packet()), start))
        self.assertTrue(feed.live((start + 4999) % PERIOD))
        self.assertFalse(feed.live((start + 5000) % PERIOD))
        self.assertFalse(feed.accept(json.dumps(packet()), 10))
        self.assertEqual(feed.last_seen, start)
        self.assertTrue(feed.accept(json.dumps(packet(1)), 10))
        self.assertTrue(feed.accept(json.dumps(packet(0, "c" * 32)), 20))
        self.assertFalse(feed.accept(json.dumps(packet(99)), 30))
        self.assertEqual(feed.last_seen, 20)
        bad = packet()
        bad["token"] = "d" * 32
        with self.assertRaisesRegex(ValueError, "Unauthorized"):
            feed.accept(json.dumps(bad), 30)

    def test_rejects_bad_shapes_bounds_and_labels_without_replacing_data(self):
        feed = client.Feed(TOKEN)
        feed.accept(json.dumps(packet()), 100)
        for key, value in (
                ("events", [packet()["events"][0]] * 25), ("metrics", [0]),
                ("epoch", "x"), ("seq", -1), ("tools", [["bash", -2]]),
                ("source", "secret\nvalue"), ("state", "working"), ("v", True),
                ("metrics", [3, 1, 1, 1, 3000, -1.0, -1])):
            bad = packet(1)
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                feed.accept(json.dumps(bad), 200)
        for value in (b"x" * 4097, b"not json", b"[]"):
            with self.assertRaises(ValueError):
                feed.accept(value, 200)
        bad = packet(1)
        bad["events"][0][0] = 3
        with self.assertRaises(ValueError):
            feed.accept(json.dumps(bad), 200)
        self.assertEqual(feed.seq, 0)
        self.assertEqual(feed.last_seen, 100)

    def make_monitor(self, config):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        filename = Path(directory.name) / "config.json"
        filename.write_text(json.dumps(config))
        wlan = Mock()
        wlan.active.return_value = True
        wlan.isconnected.return_value = True
        wlan.ifconfig.return_value = ("127.0.0.1", "", "", "")
        network = SimpleNamespace(STA_IF=0, WLAN=lambda _: wlan)
        with patch.dict(sys.modules, {"network": network}):
            monitor = client.Monitor(str(filename))
        self.addCleanup(monitor.close)
        return monitor, wlan

    def test_actual_udp_reception_wifi_drop_and_rebind(self):
        reservation = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
        reservation.close()
        monitor, wlan = self.make_monitor({"token": TOKEN, "host": "127.0.0.1", "port": port})
        monitor.step(100)
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(sender.close)
        sender.sendto(json.dumps(packet()).encode(), ("127.0.0.1", port))
        monitor.step(101)
        self.assertTrue(monitor.live(101))
        self.assertEqual(monitor.feed.packet["metrics"], packet()["metrics"])
        sender.sendto(b"invalid", ("127.0.0.1", port))
        monitor.step(102)
        self.assertEqual(monitor.rejected, 1)
        self.assertEqual(monitor.feed.seq, 0)
        wlan.isconnected.return_value = False
        monitor.step(103)
        self.assertFalse(monitor.live(103))
        self.assertIsNone(monitor.listener)
        wlan.isconnected.return_value = True
        monitor.step(104)
        self.assertIsNotNone(monitor.listener)
        self.assertFalse(monitor.live(104))
        sender.sendto(json.dumps(packet(1)).encode(), ("127.0.0.1", port))
        monitor.step(105)
        self.assertTrue(monitor.live(105))
        monitor.close()
        wlan.disconnect.assert_not_called()
        wlan.active.assert_called_with(True)

    def test_config_errors_missing_config_and_wifi_retry(self):
        monitor = client.Monitor("/definitely-missing-agentviz-config.json")
        self.assertIn("Add", monitor.message)
        self.assertFalse(monitor.error)
        for config in ({}, {"token": TOKEN, "host": "bad"},
                       {"token": TOKEN, "host": "127.0.0.1", "port": 0}):
            bad, _ = self.make_monitor(config)
            self.assertTrue(bad.error)
        monitor, wlan = self.make_monitor({
            "token": TOKEN, "host": "127.0.0.1", "ssid": "synthetic", "password": "abcdefgh"})
        wlan.isconnected.return_value = False
        monitor.step(20100)
        self.assertEqual(monitor.message, "Wi-Fi unavailable; retrying")
        monitor.step(25100)
        self.assertEqual(monitor.message, "Joining Wi-Fi...")
        self.assertEqual(wlan.connect.call_count, 2)

    @unittest.skipUnless(os.environ.get("AGENTVIZ_SOURCE"), "Requires pinned AgentViz checkout")
    def test_real_node_bridge_to_production_badge_receiver(self):
        reservation = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
        reservation.close()
        monitor, _ = self.make_monitor({"token": TOKEN, "host": "127.0.0.1", "port": port})
        monitor.step(100)
        upstream = Path(os.environ["AGENTVIZ_SOURCE"])
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "host.json"
            config.write_text(json.dumps({"badge": "127.0.0.1", "port": port, "token": TOKEN}))
            result = subprocess.run([
                "node", str(ROOT / "tools/agentviz/bridge.mjs"), "--source", str(upstream),
                "--session", str(upstream / "src/__tests__/fixtures/test-multiagent.jsonl"),
                "--config", str(config), "--once",
            ], check=True, capture_output=True, text=True, timeout=30)
            self.assertNotIn(TOKEN, result.stdout + result.stderr)
        monitor.step(101)
        self.assertTrue(monitor.live(101))
        self.assertEqual(monitor.rejected, 0)
        self.assertEqual(monitor.feed.packet["source"], "copilot-cli")
        self.assertTrue(any(e[3] == 4 for e in monitor.feed.packet["events"]))
        app, _, screen = load_app(monitor)
        app.update()
        self.assertIn("LIVE FEED", screen.labels)
        self.assertEqual(app.selected, monitor.feed.packet["events"][-1][0])


class AppTests(unittest.TestCase):
    def setUp(self):
        self.monitor = Mock()
        self.monitor.feed = SimpleNamespace(packet=packet())
        self.monitor.error = False
        self.monitor.address = "127.0.0.1"
        self.monitor.message = "Local bridge connected"
        self.monitor.live.return_value = True
        self.app, self.badge, self.screen = load_app(self.monitor)

    def press(self, key, delta=0):
        self.badge.keys = {key}
        self.badge.ticks_delta = delta
        self.badge.ticks = (self.badge.ticks + delta) % PERIOD
        try:
            return self.app.update()
        finally:
            self.badge.keys.clear()

    def test_live_tracks_inspector_stats_and_disconnect_are_explicit(self):
        self.assertIsNone(self.app.update())
        self.assertEqual(self.badge.display_mode, 3)
        self.assertEqual(self.app.selected, 2)
        self.assertIn("LIVE FEED", self.screen.labels)
        self.press("LEFT")
        self.assertIn("REVIEW", self.screen.labels)
        self.assertIn("#2 bash", self.screen.labels)
        self.assertTrue(any("ERROR" in text for text in self.screen.labels))
        self.press("DOWN")
        self.assertIn("Tokens in/out: ? / ?", self.screen.labels)
        self.monitor.live.return_value = False
        self.app.update()
        self.assertIn("OFFLINE", self.screen.labels)
        self.assertNotIn("LIVE FEED", self.screen.labels)
        self.assertFalse(self.press("BACK"))

    def test_replay_is_frame_rate_independent(self):
        results = []
        for delta, frames in ((10, 160), (100, 16), (1600, 1)):
            app, badge, _ = load_app(self.monitor)
            app.update()
            badge.keys = {"SELECT"}
            app.update()
            badge.keys.clear()
            for _ in range(frames):
                badge.ticks_delta = delta
                app.update()
            results.append((app.selected, app.playing))
        self.assertEqual(results, [(2, False)] * 3)

    def test_demo_never_overrides_real_data_and_up_restores_follow(self):
        self.app.update()
        self.press("MENU", 1000)
        self.assertIn("DEMO", self.screen.labels)
        self.assertIn("SYNTHETIC - not a real session", self.screen.labels)
        self.assertEqual(self.monitor.feed.packet["epoch"], "a" * 32)
        self.press("MENU")
        self.assertIn("LIVE FEED", self.screen.labels)
        self.assertEqual(self.app.selected, 2)
        self.press("LEFT")
        self.press("UP")
        self.assertTrue(self.app.follow)
        self.assertEqual(self.app.selected, 2)

    def test_eviction_is_visible_and_epoch_changes_reset_replay(self):
        self.app.update()
        self.press("LEFT")
        new = packet(1)
        new["events"] = [new["events"][-1]]
        self.monitor.feed.packet = new
        self.app.update()
        self.assertTrue(self.app.trimmed)
        self.assertIn("Older events left the window", self.screen.labels)
        new["epoch"] = "c" * 32
        self.app.update()
        self.assertTrue(self.app.follow)
        self.assertFalse(self.app.trimmed)

    def test_waiting_source_error_and_retry_without_fake_session(self):
        self.monitor.feed = None
        self.monitor.message = "Add /agentviz_config.json"
        self.app.update()
        self.assertIn("Add /agentviz_config.json", self.screen.labels)
        self.assertIsNone(self.app.packet)
        self.press("UP")
        self.monitor.reload.assert_called_once()
        self.monitor.feed = SimpleNamespace(packet={
            **packet(), "state": "error", "message": "Invalid session", "events": []})
        self.monitor.message = "Invalid session"
        self.app.update()
        self.assertIn("SOURCE ERROR", self.screen.labels)
        self.assertIn("Invalid session", self.screen.labels)


if __name__ == "__main__":
    unittest.main()
