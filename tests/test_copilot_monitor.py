"""Agent Buddy wire compatibility, bounded networking, and live badge UI."""

import base64
import concurrent.futures
import json
from pathlib import Path
import socket
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import test_copilot

import copilot_monitor as monitor


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.clock = test_copilot.Clock()
        patcher = patch.object(monitor, "time", self.clock)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.path = str(Path(self.directory.name) / "pairing.json")
        self.protocol = monitor.Protocol(self.path)
        self.protocol.open_pairing(self.clock.now)
        code, paired = self.request("POST", "/pair", self.protocol.pairing_code)
        self.assertEqual(code, 200)
        self.token = paired["token"]

    def request(self, method, path, body="", authenticated=False):
        headers = {"authorization": "Bearer " + self.token} if authenticated else {}
        return self.protocol.handle(method, path, headers, body.encode(), self.clock.now)

    def test_pairing_is_physical_single_use_and_persisted(self):
        self.assertIsNone(self.protocol.pairing_code)
        self.assertEqual(self.request("POST", "/pair", "12345678")[0], 403)
        restored = monitor.Protocol(self.path)
        self.assertEqual(restored.token, self.token)
        self.assertEqual(restored.device_id, self.protocol.device_id)
        self.assertTrue(monitor.valid_hex(restored.device_id, 16))
        self.assertTrue(monitor.valid_hex(restored.token, 32))

    def test_pairing_expires_and_locks_after_five_wrong_attempts(self):
        self.protocol.open_pairing(self.clock.now)
        self.clock.advance(60000)
        self.assertEqual(self.request("POST", "/pair", self.protocol.pairing_code)[0], 403)
        self.protocol.open_pairing(self.clock.now)
        correct = self.protocol.pairing_code
        for _ in range(5):
            self.assertEqual(self.request("POST", "/pair", "incorrect")[0], 403)
        self.assertEqual(self.request("POST", "/pair", correct)[0], 403)
        self.assertIsNone(self.protocol.pairing_code)

    def test_all_session_endpoints_require_bearer_token(self):
        for method, path in (("GET", "/status"), ("POST", "/state"), ("POST", "/icon"),
                             ("POST", "/agents"), ("POST", "/usage")):
            self.assertEqual(self.request(method, path)[0], 401)
            status, _ = self.protocol.handle(method, path, {"authorization": "Bearer wrong"},
                                             b"", self.clock.now)
            self.assertEqual(status, 401)

    def test_protocol_negotiation_does_not_claim_esp32_firmware(self):
        status, value = self.request("GET", "/status", authenticated=True)
        self.assertEqual(status, 200)
        self.assertEqual(value["protocol"], 8)
        self.assertEqual(value["character"], "copilot")
        self.assertEqual(value["board"], "github-universe-2026")
        self.assertIsInstance(value["boot"], int)
        for path in ("/firmware", "/character", "/orientation"):
            self.assertEqual(self.request("POST", path, authenticated=True)[0], 404)

    def test_all_upstream_states_and_invalid_packets(self):
        for state in monitor.STATES:
            self.assertEqual(self.request("POST", "/state", state, True)[0], 200)
            self.assertEqual(self.protocol.state, state)
            self.assertTrue(self.protocol.live(self.clock.now))
        for value in ("!working", '{"state":"working"}', "busy", ""):
            self.assertEqual(self.request("POST", "/state", value, True)[0], 400)
            self.assertEqual(self.protocol.state, "complete")

    def test_exact_upstream_icon_agents_and_usage_packets(self):
        mask = bytes([128] + [0] * 71)
        packet = "%copilot:58a6ff:" + base64.b64encode(mask).decode() + "\n"
        self.assertEqual(self.request("POST", "/icon", packet, True)[0], 200)
        self.assertEqual(self.protocol.icons["copilot"], ((88, 166, 255), mask))
        self.assertEqual(self.request("POST", "/agents", "&copilot=w,claude=a\n", True)[0], 200)
        self.assertEqual(self.protocol.agents, [("copilot", "w"), ("claude", "a")])
        self.assertEqual(self.request("POST", "/usage", "$AIC: 902|Tokens: 1.2M\n", True)[0], 200)
        self.assertEqual(self.protocol.usage, ["AIC: 902", "Tokens: 1.2M"])
        for endpoint, packet, field in (("/agents", "&\n", "agents"), ("/usage", "$\n", "usage")):
            self.assertEqual(self.request("POST", endpoint, packet, True)[0], 200)
            self.assertEqual(getattr(self.protocol, field), [])

    def test_bad_packets_do_not_replace_previous_valid_data(self):
        for path, values in (
            ("/icon", ["%a:000000:====", "%a:zzzzzz:" + "A" * 96, "%A:000000:" + "A" * 96]),
            ("/agents", ["&copilot=oops", "&a=w,a=a", "&" + ",".join("a%d=w" % i for i in range(9))]),
            ("/usage", ["$" + "x" * 19, "$one|two|three", "$AIC: <script>", "$|"])):
            for packet in values:
                self.assertEqual(self.request("POST", path, packet, True)[0], 400, packet)
        for index in range(8):
            self.assertEqual(self.request("POST", "/icon", "%%a%d:000000:%s" %
                                         (index, "A" * 96), True)[0], 200)
        self.assertEqual(self.request("POST", "/icon", "%extra:000000:" + "A" * 96, True)[0], 400)

    def test_heartbeat_keeps_long_work_live_but_stale_state_clears(self):
        self.request("POST", "/state", "working", True)
        for _ in range(10):
            self.clock.advance(3000)
            self.request("GET", "/status", authenticated=True)
            self.protocol.expire(self.clock.now)
            self.assertTrue(self.protocol.live(self.clock.now))
        self.request("POST", "/agents", "&copilot=w", True)
        self.request("POST", "/usage", "$AIC: 3", True)
        boot = self.protocol.boot
        self.clock.advance(15000)
        self.protocol.expire(self.clock.now)
        self.assertFalse(self.protocol.live(self.clock.now))
        self.assertEqual(self.protocol.state, "idle")
        self.assertEqual(self.protocol.agents, [])
        self.assertEqual(self.protocol.usage, [])
        self.assertNotEqual(self.protocol.boot, boot)
        # This boot change triggers the existing daemon's complete resync.
        self.request("GET", "/status", authenticated=True)
        self.assertFalse(self.protocol.live(self.clock.now))
        self.request("POST", "/state", "working", True)
        self.assertTrue(self.protocol.live(self.clock.now))

    def test_stale_timeout_and_pairing_across_ticks_rollover(self):
        self.clock.now = test_copilot.PERIOD - 1000
        self.protocol.open_pairing(self.clock.now)
        self.request("POST", "/state", "attention", True)
        self.clock.advance(14999)
        self.protocol.expire(self.clock.now)
        self.assertTrue(self.protocol.live(self.clock.now))
        self.clock.advance(1)
        self.protocol.expire(self.clock.now)
        self.assertFalse(self.protocol.live(self.clock.now))
        self.assertTrue(self.protocol.pairing(self.clock.now))
        self.clock.advance(45000)
        self.assertFalse(self.protocol.pairing(self.clock.now))

    def test_invalid_saved_pairing_is_not_silently_replaced(self):
        Path(self.path).write_text('{"token":"invalid"}')
        with self.assertRaisesRegex(ValueError, "pairing file"):
            monitor.Protocol(self.path)


class NetworkTests(unittest.TestCase):
    def setUp(self):
        ProtocolTests.setUp(self)
        self.server = monitor.Server(self.protocol, port=0, discovery_port=0, host="127.0.0.1")
        self.addCleanup(self.server.close)

    request = ProtocolTests.request

    def complete(self, request):
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(request)
            deadline = time.monotonic() + 3
            while not future.done() and time.monotonic() < deadline:
                self.server.step(self.clock.now)
                time.sleep(0.001)
            return future.result(timeout=1)

    def exchange(self, method, path, body="", auth=True):
        def request():
            headers = {"Authorization": "Bearer " + self.token} if auth else {}
            request = Request("http://127.0.0.1:%d%s" % (self.server.port, path),
                              data=body.encode() if method == "POST" else None,
                              headers=headers, method=method)
            try:
                response = urlopen(request, timeout=2)
            except HTTPError as error:
                response = error
            with response:
                return response.status, json.loads(response.read())

        return self.complete(request)

    def test_real_http_supports_the_daemon_request_sequence(self):
        status, value = self.exchange("GET", "/status")
        self.assertEqual((status, value["deviceId"]), (200, self.protocol.device_id))
        self.assertEqual(self.exchange("POST", "/state", "working")[0], 200)
        self.assertEqual(self.exchange("POST", "/icon", "%copilot:58a6ff:" + "A" * 96 + "\n")[0], 200)
        self.assertEqual(self.exchange("POST", "/agents", "&copilot=w\n")[0], 200)
        self.assertEqual(self.exchange("POST", "/usage", "$AIC: 1.2\n")[0], 200)
        self.assertEqual(self.exchange("POST", "/state", "attention")[0], 200)
        self.assertEqual(self.exchange("POST", "/state", "complete")[0], 200)
        self.assertEqual(self.exchange("POST", "/state", "idle")[0], 200)
        self.assertEqual(self.exchange("GET", "/status", auth=False)[0], 401)

    def test_real_udp_discovery_uses_upstream_service_and_version(self):
        self.protocol.open_pairing(self.clock.now)
        self.server.step(self.clock.now)
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(udp.close)
        udp.settimeout(1)
        def request():
            udp.sendto(monitor.DISCOVER, ("127.0.0.1", self.server.udp.getsockname()[1]))
            return json.loads(udp.recv(512))

        value = self.complete(request)
        self.assertEqual(value["service"], "esp32-agent-companion")
        self.assertEqual(value["protocol"], 1)
        self.assertEqual(value["deviceId"], self.protocol.device_id)
        self.assertEqual(value["port"], self.server.port)

    def test_http_listener_requires_a_specific_interface(self):
        self.assertEqual(self.server.listener.getsockname()[0], "127.0.0.1")
        for host in (None, "", "0.0.0.0"):
            with self.subTest(host=host), patch.object(monitor.socket, "socket") as factory:
                with self.assertRaisesRegex(ValueError, "specific network address"):
                    monitor.Server(self.protocol, host=host)
                factory.assert_not_called()

    def test_discovery_socket_exists_only_during_the_pairing_window(self):
        self.assertIsNone(self.server.udp)
        self.protocol.open_pairing(self.clock.now)
        self.server.step(self.clock.now)
        udp = self.server.udp
        self.assertEqual(udp.getsockname()[0], "0.0.0.0")
        self.clock.advance(59999)
        self.server.step(self.clock.now)
        self.assertIs(self.server.udp, udp)
        self.clock.advance(1)
        self.server.step(self.clock.now)
        self.assertIsNone(self.server.udp)
        self.assertEqual(udp.fileno(), -1)
        self.assertEqual(self.exchange("GET", "/status")[0], 200)
        self.protocol.open_pairing(self.clock.now)
        self.server.step(self.clock.now)
        udp = self.server.udp
        self.protocol.pairing_code = None
        self.server.step(self.clock.now)
        self.assertIsNone(self.server.udp)
        self.assertEqual(udp.fileno(), -1)

    def test_pairing_success_and_lockout_close_discovery_without_closing_http(self):
        for success in (True, False):
            with self.subTest(success=success):
                self.protocol.open_pairing(self.clock.now)
                self.server.step(self.clock.now)
                udp = self.server.udp
                code = self.protocol.pairing_code
                for _ in range(1 if success else 5):
                    self.assertEqual(self.exchange("POST", "/pair",
                                                  code if success else "incorrect", auth=False)[0],
                                     200 if success else 403)
                self.assertIsNone(self.server.udp)
                self.assertEqual(udp.fileno(), -1)
                self.assertEqual(self.exchange("GET", "/status")[0], 200)

    def test_discovery_closes_at_expiry_across_ticks_rollover(self):
        self.clock.now = test_copilot.PERIOD - 1000
        self.protocol.open_pairing(self.clock.now)
        self.server.step(self.clock.now)
        udp = self.server.udp
        self.clock.advance(60000)
        self.server.step(self.clock.now)
        self.assertIsNone(self.server.udp)
        self.assertEqual(udp.fileno(), -1)

    def test_fragmented_http_and_partial_responses(self):
        first = b"POST /state HTTP/1.1\r\nAuthorization: Bearer " + self.token.encode()
        chunks = [first, b"\r\nContent-Length: 7\r\n\r\nwor", b"king"]
        connection = Mock()
        connection.recv.side_effect = chunks
        connection.send.side_effect = lambda value: min(7, len(value))
        peer = monitor.Peer(connection, self.clock.now)
        for _ in chunks:
            self.assertTrue(peer.step(self.protocol, self.clock.now))
        self.assertEqual(self.protocol.state, "working")
        while peer.step(self.protocol, self.clock.now):
            pass
        self.assertEqual(peer.sent, len(peer.output))

    def test_bounded_http_rejects_oversized_chunked_and_duplicate_headers(self):
        for request, status in (
            (b"POST /state HTTP/1.1\r\nContent-Length: 513\r\n\r\n", 413),
            (b"POST /state HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\n", 400),
            (b"POST /state HTTP/1.1\r\nContent-Length: 0\r\nContent-Length: 0\r\n\r\n", 400),
            (b"POST /state HTTP/1.1\r\nContent-Length: -1\r\n\r\n", 400),
            (b"GET /status HTTP/1.1\r\n" + b"x" * 2048, 413),
        ):
            connection = Mock()
            connection.recv.return_value = request
            peer = monitor.Peer(connection, self.clock.now)
            peer.step(self.protocol, self.clock.now)
            self.assertTrue(peer.output.startswith(("HTTP/1.1 %d " % status).encode()))

    def test_client_timeout_and_client_count_are_bounded(self):
        clients = []
        for _ in range(6):
            client = socket.create_connection(("127.0.0.1", self.server.port), timeout=1)
            self.addCleanup(client.close)
            clients.append(client)
            self.server.step(self.clock.now)
        self.assertLessEqual(len(self.server.clients), 3)
        self.clock.advance(5000)
        self.server.step(self.clock.now)
        self.assertEqual(self.server.clients, [])


class LiveUITests(unittest.TestCase):
    def setUp(self):
        test_copilot.CopilotTests.setUp(self)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        patcher = patch.object(monitor, "time", self.clock)
        patcher.start()
        self.addCleanup(patcher.stop)
        protocol = monitor.Protocol(str(Path(self.directory.name) / "pairing.json"))
        self.live_monitor = types.SimpleNamespace(
            protocol=protocol, error=None, message="Waiting for Agent Buddy",
            address="192.0.2.10", server=True, close=Mock(), reload=Mock(), step=Mock(),
            live=lambda now: protocol.live(now), open_pairing=lambda now: protocol.open_pairing(now))
        self.app = self.namespace["CopilotApp"](monitor=self.live_monitor)

    press = test_copilot.CopilotTests.press
    labels = test_copilot.CopilotTests.labels

    def state(self, value):
        protocol = self.live_monitor.protocol
        protocol.state = value
        protocol.last_seen = protocol.last_state = self.clock.now
        self.app.update()

    def test_remote_state_controls_animation_and_repeated_heartbeat_does_not_restart_it(self):
        self.state("working")
        self.assertEqual(self.app.mode, "working")
        self.clock.advance(800)
        self.app.update()
        self.assertEqual(self.app.sprite_name, "working-10")
        self.state("attention")
        self.assertEqual(self.app.mode, "attention")
        self.press("RIGHT")
        self.assertEqual(self.app.mode, "attention")
        self.state("complete")
        self.clock.advance(6000)
        self.app.update()
        self.assertEqual(self.app.mode, "complete")

    def test_disconnect_never_leaves_fake_work_or_usage(self):
        self.state("working")
        self.live_monitor.protocol.usage = ["AIC: 3"]
        self.clock.advance(15000)
        self.app.update()
        self.assertFalse(self.app.was_live)
        self.assertEqual(self.app.mode, "idle")
        self.assertNotIn("AIC: 3", self.labels())

    def test_demo_is_explicit_and_returns_to_current_remote_state(self):
        self.state("attention")
        self.press("DOWN")
        self.assertTrue(self.app.demo)
        self.assertIn("DEMO - not session status", self.labels())
        self.state("working")
        self.assertNotEqual(self.app.mode, "working")
        self.press("DOWN")
        self.assertFalse(self.app.demo)
        self.assertEqual(self.app.mode, "working")

    def test_pairing_ui_and_cancel(self):
        self.screen.measure_text.side_effect = lambda text, size=1: (len(text) * 7 * size, 13 * size)
        self.press("UP")
        self.assertIn(self.live_monitor.protocol.pairing_code, self.labels())
        self.assertIn("192.0.2.10", self.labels())
        self.press("UP")
        self.assertIsNone(self.live_monitor.protocol.pairing_code)

    def test_entering_demo_closes_pairing_and_select_reloads_config(self):
        self.screen.measure_text.side_effect = lambda text, size=1: (len(text) * 7 * size, 13 * size)
        self.press("UP")
        self.press("DOWN")
        self.assertIsNone(self.live_monitor.protocol.pairing_code)
        self.assertTrue(self.app.demo)
        self.press("SELECT")
        self.live_monitor.reload.assert_called_once()

    def test_live_usage_agent_mask_rendering_and_cleanup(self):
        protocol = self.live_monitor.protocol
        protocol.agents = [("copilot", "w")]
        protocol.icons["copilot"] = ((88, 166, 255), bytes([128] + [0] * 71))
        protocol.usage = ["AIC: 1.2", "Tokens: 9K"]
        self.state("working")
        self.assertIn("AIC: 1.2", self.labels())
        self.assertIn("Tokens: 9K", self.labels())
        self.assertIn("copilot", self.labels())
        self.screen.rectangle.assert_any_call(16, 64, 1, 1)
        self.assertEqual(len(self.app.icon_cache), 1)
        self.app.close()
        self.live_monitor.close.assert_called_once()
        self.assertEqual(self.app.icon_cache, {})


class WifiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.clock = test_copilot.Clock()
        p = patch.object(monitor, "time", self.clock)
        p.start()
        self.addCleanup(p.stop)
        self.wlan = Mock()
        self.wlan.active.return_value = False
        self.wlan.isconnected.return_value = False
        p = patch.dict(sys.modules, {"network": types.SimpleNamespace(
            WLAN=lambda interface: self.wlan, STA_IF=0)})
        p.start()
        self.addCleanup(p.stop)

    def create(self, config=None):
        if config is not None:
            (self.root / "config.json").write_text(json.dumps(config))
        value = monitor.Monitor(str(self.root / "config.json"), str(self.root / "pairing.json"))
        self.addCleanup(value.close)
        return value

    def test_missing_config_does_not_start_network(self):
        client = self.create()
        self.assertIsNone(client.wlan)
        self.wlan.active.assert_not_called()
        self.assertIn("config.json", client.message)

    def test_invalid_config_is_visible_without_disclosing_credentials(self):
        for config in ([], {"ssid": 42}, {"port": 0}, {"port": True}, {"password": 42}):
            client = self.create(config)
            self.assertEqual(client.error, "Check Copilot config")
            self.assertIsNone(client.wlan)

    def test_join_timeout_retries_without_blocking(self):
        client = self.create({"ssid": "example", "password": "not-a-real-password"})
        self.wlan.connect.assert_called_once()
        self.clock.advance(20000)
        client.step(self.clock.now)
        self.assertEqual(client.message, "Wi-Fi unavailable; retrying")
        self.clock.advance(4999)
        client.step(self.clock.now)
        self.assertEqual(self.wlan.connect.call_count, 1)
        self.clock.advance(1)
        client.step(self.clock.now)
        self.assertEqual(self.wlan.connect.call_count, 2)

    def test_reuses_existing_wifi_and_preserves_it_on_exit(self):
        self.wlan.active.return_value = True
        self.wlan.isconnected.return_value = True
        self.wlan.ifconfig.return_value = ("192.0.2.10", "", "", "")
        with patch.object(monitor, "Server") as server:
            client = self.create({})
            client.step(self.clock.now)
            self.assertTrue(client.server)
            server.assert_called_once_with(client.protocol, 80, host="192.0.2.10")
            client.close()
        self.wlan.disconnect.assert_not_called()
        self.wlan.active.assert_any_call(True)
        self.assertNotIn((False,), [call.args for call in self.wlan.active.call_args_list])

    def test_address_change_rebinds_http_and_requests_full_resync(self):
        self.wlan.active.return_value = True
        self.wlan.isconnected.return_value = True
        self.wlan.ifconfig.return_value = ("192.0.2.10", "", "", "")
        with patch.object(monitor, "Server") as factory:
            client = self.create({})
            client.step(self.clock.now)
            old = client.server
            client.protocol.state = "working"
            client.protocol.last_state = client.protocol.last_seen = self.clock.now
            boot = client.protocol.boot
            self.wlan.ifconfig.return_value = ("192.0.2.11", "", "", "")
            client.step(self.clock.now)
            old.close.assert_called_once()
            self.assertEqual(factory.call_count, 2)
            factory.assert_called_with(client.protocol, 80, host="192.0.2.11")
            self.assertEqual(client.protocol.state, "idle")
            self.assertNotEqual(client.protocol.boot, boot)

    def test_invalid_wifi_address_is_reported_without_falling_back_to_all_interfaces(self):
        self.wlan.isconnected.return_value = True
        self.wlan.ifconfig.return_value = ("0.0.0.0", "", "", "")
        with patch.object(monitor.socket, "socket") as factory:
            client = self.create({})
            client.step(self.clock.now)
            factory.assert_not_called()
        self.assertIsNone(client.server)
        self.assertEqual(client.error, "Network error; Select retries")

    def test_disconnect_closes_sockets_and_reconnect_requests_full_resync(self):
        self.wlan.active.return_value = True
        self.wlan.isconnected.return_value = True
        self.wlan.ifconfig.return_value = ("192.0.2.10", "", "", "")
        with patch.object(monitor, "Server") as factory:
            client = self.create({})
            client.step(self.clock.now)
            old = client.server
            client.protocol.last_state = client.protocol.last_seen = self.clock.now
            client.protocol.state = "working"
            boot = client.protocol.boot
            self.wlan.isconnected.return_value = False
            client.step(self.clock.now)
            old.close.assert_called_once()
            self.assertIsNone(client.server)
            self.assertFalse(client.live(self.clock.now))
            self.assertNotEqual(client.protocol.boot, boot)
            self.wlan.isconnected.return_value = True
            client.step(self.clock.now)
            self.assertEqual(factory.call_count, 2)
            self.assertIsNotNone(client.server)


if __name__ == "__main__":
    unittest.main()
