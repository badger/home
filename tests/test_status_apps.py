"""Host-side checks for the AutoGPT and T3 Code status apps' non-drawing code."""

import datetime
import importlib.util
from pathlib import Path
import random
import sys
import types
import unittest

# Importing app modules must not leave __pycache__ inside badge/apps.
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1] / "badge/apps"
PERIOD = 1 << 30


class Clock:
    """MicroPython's wrapping ticks API."""

    def __init__(self, now=100):
        self.now = now

    def ticks_ms(self):
        return self.now

    def ticks_diff(self, a, b):
        return (a - b + PERIOD // 2) % PERIOD - PERIOD // 2

    def ticks_add(self, a, b):
        return (a + b) % PERIOD

    def advance(self, ms):
        self.now = self.ticks_add(self.now, ms)


class FakeAsyncFetch:
    IDLE, FETCHING, DONE, ERROR = 0, 1, 2, 3
    instances = []

    def __init__(self, host, port=None, use_tls=True, timeout=None, max_bytes=None):
        self.args = (host, port, use_tls, timeout, max_bytes)
        self.requests = []
        self.script = []
        self.http_status = None
        self.http_response_headers = {}
        self.body = memoryview(b"")
        self.resets = 0
        self.error_handler = None
        FakeAsyncFetch.instances.append(self)

    def on_error(self, handler):
        self.error_handler = handler

    def fetch(self, path, headers=None):
        self.requests.append((path, dict(headers or {})))

    def update(self):
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        if step == "pending":
            return self.FETCHING
        status, body, headers = step
        self.http_status = status
        self.http_response_headers = headers
        self.body = memoryview(body)
        if status == 200:
            return self.DONE
        assert self.error_handler and self.error_handler(self)
        return self.ERROR

    def to_json(self):
        import json
        return json.loads(bytes(self.body))

    def reset(self):
        self.resets += 1


class FakeUrl:
    """The simulator's fetch.url shim: truthy once the response arrives."""

    replies = []

    def __init__(self, url, headers=None):
        self.url = url
        self.headers = headers
        self.reply = FakeUrl.replies.pop(0)
        self.error = None
        self.checks = 0

    def __bool__(self):
        self.checks += 1
        if self.checks < 2:
            return False
        if isinstance(self.reply, str):
            self.error = self.reply
            return False
        return True

    def json(self):
        return self.reply


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fake_fetch = types.ModuleType("fetch")
fake_fetch.AsyncFetch = FakeAsyncFetch
fake_fetch.url = FakeUrl
fake_wifi = types.ModuleType("wifi")
sys.modules["fetch"] = fake_fetch
sys.modules["wifi"] = fake_wifi

net = load("status_net", ROOT / "t3code/net.py")
t3 = load("t3_model", ROOT / "t3code/model.py")
ag = load("autogpt_model", ROOT / "autogpt/model.py")


class SharedNetModuleTests(unittest.TestCase):
    def test_both_apps_ship_the_same_net_module(self):
        self.assertEqual((ROOT / "t3code/net.py").read_bytes(), (ROOT / "autogpt/net.py").read_bytes())


class SplitUrlTests(unittest.TestCase):
    def test_parses_scheme_host_port_and_prefix(self):
        self.assertEqual(net.split_url("https://backend.agpt.co/api/v2"), (True, "backend.agpt.co", 443, "/api/v2"))
        self.assertEqual(net.split_url("https://t.ts.net:10000/badge/"), (True, "t.ts.net", 10000, "/badge"))
        self.assertEqual(net.split_url("http://127.0.0.1:8791"), (False, "127.0.0.1", 8791, ""))

    def test_rejects_other_schemes_and_empty_hosts(self):
        for url in ("ftp://x", "backend.agpt.co", "https:///path"):
            with self.assertRaises(ValueError):
                net.split_url(url)


class MessageTests(unittest.TestCase):
    def test_describe_network_errors(self):
        self.assertEqual(net.describe(OSError(110, "x")), "timed out")
        self.assertEqual(net.describe(OSError(-2)), "DNS lookup failed")
        self.assertEqual(net.describe(OSError(111)), "connection refused")
        self.assertEqual(net.describe(OSError(-29312)), "TLS error -29312")
        self.assertEqual(net.describe(ValueError("Response exceeds max_bytes of 10")), "response too large")

    def test_error_message_uses_server_detail(self):
        self.assertEqual(net.error_message(403, b'{"error":{"code":"forbidden","message":"Missing READ_RUN"}}'),
                         "HTTP 403: Missing READ_RUN")
        self.assertEqual(net.error_message(401, b'{"error":"badge bridge: unauthorized"}'),
                         "HTTP 401: badge bridge: unauthorized")
        self.assertEqual(net.error_message(404, b'{"detail":"Not Found"}'), "HTTP 404: Not Found")
        self.assertEqual(net.error_message(502, b"<html>bad gateway</html>"), "HTTP 502")


class NativeClientTests(unittest.TestCase):
    def setUp(self):
        FakeAsyncFetch.instances.clear()
        net.NATIVE = True
        self.client = net.Client("https://api.example:8443/api/v2", {"X-API-Key": "k"}, timeout=7, max_bytes=999)

    def test_reuses_one_connection_and_reports_json(self):
        self.client.start("/runs?limit=1")
        request = FakeAsyncFetch.instances[0]
        self.assertEqual(request.args, ("api.example", 8443, True, 7, 999))
        request.script = ["pending", (200, b'{"total_count": 4}', {"Date": "Tue, 27 Oct 2026 02:21:52 GMT"})]
        self.assertIsNone(self.client.poll())
        self.assertEqual(self.client.poll(), (200, {"total_count": 4}))
        self.assertFalse(self.client.busy)
        self.assertEqual(self.client.date, "Tue, 27 Oct 2026 02:21:52 GMT")
        self.client.start("/credits")
        self.assertEqual(len(FakeAsyncFetch.instances), 1)
        self.assertEqual(request.requests, [("/api/v2/runs?limit=1", {"X-API-Key": "k"}), ("/api/v2/credits", {"X-API-Key": "k"})])

    def test_http_errors_become_messages(self):
        self.client.start("/runs")
        FakeAsyncFetch.instances[0].script = [(401, b'{"error":{"message":"Missing authentication."}}', {})]
        self.assertEqual(self.client.poll(), (401, "HTTP 401: Missing authentication."))

    def test_network_exceptions_reset_the_socket(self):
        self.client.start("/runs")
        request = FakeAsyncFetch.instances[0]
        request.script = [OSError(110, "No data for 7s")]
        self.assertEqual(self.client.poll(), (0, "timed out"))
        self.assertEqual(request.resets, 1)
        self.assertFalse(self.client.busy)

    def test_one_request_at_a_time(self):
        self.client.start("/a")
        with self.assertRaises(RuntimeError):
            self.client.start("/b")

    def test_running_out_of_memory_parsing_is_reported(self):
        self.client.start("/runs")
        request = FakeAsyncFetch.instances[0]
        request.script = [(200, b"{}", {})]

        def too_big():
            raise MemoryError()

        request.to_json = too_big
        self.assertEqual(self.client.poll(), (0, "response too large"))
        self.assertFalse(self.client.busy)


class ShimClientTests(unittest.TestCase):
    def setUp(self):
        net.NATIVE = False

    def tearDown(self):
        net.NATIVE = True

    def test_simulator_path(self):
        FakeUrl.replies = [{"ok": True}, "HTTP 401"]
        client = net.Client("https://bridge.example/badge", {"Authorization": "Bearer t"})
        client.start("/t3/status")
        self.assertIsNone(client.poll())
        self.assertEqual(client.poll(), (200, {"ok": True}))
        client.start("/t3/status")
        client.poll()
        self.assertEqual(client.poll(), (401, "HTTP 401"))


class PollerTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.original_time = net.time
        net.time = self.clock
        net.NATIVE = True
        FakeAsyncFetch.instances.clear()
        self.client = net.Client("https://bridge.example/badge")
        self.poller = net.Poller(self.client, "/t3/status", 5000)

    def tearDown(self):
        net.time = self.original_time

    def answer(self, *steps):
        self.assertFalse(self.poller.step(self.clock.now))  # starts the request
        FakeAsyncFetch.instances[0].script = list(steps)
        return self.poller.step(self.clock.now)

    def test_success_waits_for_the_interval(self):
        self.assertTrue(self.answer((200, b'{"v": 1}', {})))
        self.assertEqual(self.poller.data, {"v": 1})
        self.assertFalse(self.poller.due(self.clock.now))
        self.clock.advance(5000)
        self.assertTrue(self.poller.due(self.clock.now))

    def test_failures_back_off_and_rejected_tokens_pause(self):
        self.assertFalse(self.answer(OSError(110)))
        self.assertEqual(self.poller.error, "timed out")
        self.clock.advance(5000)
        self.assertFalse(self.poller.due(self.clock.now))
        self.clock.advance(5000)
        self.assertTrue(self.poller.due(self.clock.now))
        self.assertFalse(self.answer((401, b"{}", {})))
        self.assertTrue(self.poller.paused)
        self.clock.advance(600000)
        self.assertFalse(self.poller.due(self.clock.now))
        self.poller.refresh()
        self.assertTrue(self.poller.due(self.clock.now))

    def test_works_across_tick_wraparound(self):
        self.clock.now = PERIOD - 1000
        self.assertTrue(self.answer((200, b"{}", {})))
        self.clock.advance(4000)
        self.assertFalse(self.poller.due(self.clock.now))
        self.clock.advance(1000)
        self.assertTrue(self.poller.due(self.clock.now))


class FakeRoamer:
    """badge/lib's wifi_networks.Roamer, scripted one update() result at a time."""

    def __init__(self):
        self.script = []
        self.restarts = 0
        self.status = "Starting Wi-Fi"

    def update(self):
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    def restart(self):
        self.restarts += 1


def fake_wifi_networks(missing=()):
    module = types.ModuleType("wifi_networks")
    module.CONNECTING, module.CONNECTED, module.FAILED = 0, 1, 2
    module.Roamer = FakeRoamer
    module.missing = lambda: list(missing)
    return module


class WiFiTests(unittest.TestCase):
    def setUp(self):
        self.original = (net.wifi_networks, net.time)
        self.clock = Clock()
        net.time = self.clock
        net.wifi_networks = None

    def tearDown(self):
        net.wifi_networks, net.time = self.original

    def test_first_call_sets_patient_retries(self):
        calls = []
        fake_wifi.connect = lambda *args, **kwargs: calls.append(kwargs) or False
        fake_wifi.status = lambda: (1, "Connecting to home")
        link = net.WiFi()
        self.assertFalse(link.ready())
        self.assertFalse(link.ready())
        # The first call starts the attempt and pumps it once; later calls only pump.
        self.assertEqual(calls, [{"timeout": net.WIFI_TIMEOUT, "retries": net.WIFI_RETRIES}, {}, {}])
        self.assertEqual(link.status(), "Connecting to home")

    def test_roams_with_the_shared_module_when_the_badge_has_it(self):
        net.wifi_networks = fake_wifi_networks()
        fake_wifi.connect = lambda *args, **kwargs: self.fail("firmware wifi used alongside the roamer")
        link = net.WiFi()
        link.roamer.script = [0, 1]
        link.roamer.status = "Joining GitHub Guest"
        self.assertFalse(link.ready())
        self.assertEqual(link.status(), "Joining GitHub Guest")
        self.assertTrue(link.ready())

    def test_looks_again_after_every_saved_network_failed(self):
        net.wifi_networks = fake_wifi_networks()
        link = net.WiFi()
        link.roamer.script = [2] * 4
        self.assertFalse(link.ready())
        self.clock.advance(net.ROAM_RETRY_MS - 1)
        self.assertFalse(link.ready())
        self.assertEqual(link.roamer.restarts, 0)
        self.clock.advance(1)
        self.assertFalse(link.ready())
        self.assertEqual(link.roamer.restarts, 1)
        # The wait starts over after a restart.
        self.assertFalse(link.ready())
        self.assertEqual(link.roamer.restarts, 1)

    def test_a_retry_by_the_roamer_restarts_the_wait(self):
        net.wifi_networks = fake_wifi_networks()
        link = net.WiFi()
        link.roamer.script = [2, 0, 2, 2]
        self.assertFalse(link.ready())
        self.clock.advance(net.ROAM_RETRY_MS)
        self.assertFalse(link.ready())  # joining again: the failure is over
        self.assertFalse(link.ready())  # a new failure starts a new wait
        self.clock.advance(net.ROAM_RETRY_MS - 1)
        self.assertFalse(link.ready())
        self.assertEqual(link.roamer.restarts, 0)

    def test_leaves_retries_to_a_roamer_that_retries_itself(self):
        net.wifi_networks = fake_wifi_networks()
        link = net.WiFi()
        link.roamer.retry_in = 20
        link.roamer.script = [2, 2]
        self.assertFalse(link.ready())
        self.clock.advance(net.ROAM_RETRY_MS * 3)
        self.assertFalse(link.ready())
        self.assertEqual(link.roamer.restarts, 0)

    def test_falls_back_to_firmware_wifi_without_a_radio_module(self):
        net.wifi_networks = fake_wifi_networks()
        calls = []
        fake_wifi.connect = lambda *args, **kwargs: calls.append(kwargs) or True
        link = net.WiFi()
        link.roamer.script = [ImportError("no module named 'network'")]
        self.assertTrue(link.ready())
        self.assertIsNone(link.roamer)
        self.assertEqual(len(calls), 2)

    def test_missing_settings_follow_the_shared_module(self):
        net.wifi_networks = fake_wifi_networks(missing=["WIFI_SSID"])
        self.assertEqual(net.wifi_missing(), ["WIFI_SSID"])
        net.wifi_networks = fake_wifi_networks()
        self.assertEqual(net.wifi_missing(), [])


class T3ModelTests(unittest.TestCase):
    def payload(self, **overrides):
        data = {
            "ok": True,
            "counts": {"attention": 1, "working": 2, "error": 0, "done": 1, "idle": 9},
            "sources": [{"name": "mbp", "ok": True, "error": None}, {"name": "fate", "ok": True}],
            "threads": [{"id": "abc", "title": "Fix \u2603 login", "project": "home", "src": "mbp",
                         "state": "attention", "detail": "approve command", "model": "gpt", "age": 75, "msg": "hi"}],
        }
        data.update(overrides)
        return data

    def test_parses_and_sanitizes(self):
        status = t3.parse_status(self.payload())
        self.assertEqual(status["counts"]["working"], 2)
        thread = status["threads"][0]
        self.assertEqual(thread["title"], "Fix login")
        self.assertEqual(thread["age"], 75)
        self.assertEqual(t3.source_line(status), "2 hosts live")

    def test_rejects_garbage_and_defaults_unknown_states(self):
        with self.assertRaises(ValueError):
            t3.parse_status({"nope": 1})
        status = t3.parse_status(self.payload(threads=[{"state": "exploded", "age": "x"}, "junk"], counts=None))
        self.assertEqual(status["threads"][0]["state"], "idle")
        self.assertIsNone(status["threads"][0]["age"])
        self.assertEqual(status["counts"]["attention"], 0)

    def test_source_line_reports_the_first_host_down(self):
        status = t3.parse_status(self.payload(sources=[
            {"name": "mbp", "ok": True}, {"name": "fate", "ok": False, "error": "T3 offline"},
            {"name": "desktop", "ok": False}]))
        self.assertEqual(t3.source_line(status), "fate: T3 offline +1")
        self.assertEqual(t3.source_line(t3.parse_status(self.payload(sources=[{"name": "mbp", "ok": True}]))), "mbp")

    def test_age_and_selection(self):
        self.assertEqual([t3.age_text(s) for s in (None, 10, 75, 3599, 7200, 200000)],
                         ["", "now", "1m", "60m", "2h", "2d"])
        threads = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        self.assertEqual(t3.keep_selection(threads, "c", 0), 2)
        self.assertEqual(t3.keep_selection(threads[:2], "gone", 5), 1)
        self.assertEqual(t3.keep_selection([], "a", 3), 0)

    def test_host_filter_cycles_through_sources(self):
        status = t3.parse_status(self.payload(src="fate"))
        self.assertEqual(status["src"], "fate")
        self.assertIsNone(t3.parse_status(self.payload())["src"])
        self.assertEqual(t3.next_host(status, None, 1), "mbp")
        self.assertEqual(t3.next_host(status, "mbp", 1), "fate")
        self.assertIsNone(t3.next_host(status, "fate", 1))
        self.assertEqual(t3.next_host(status, None, -1), "fate")
        self.assertIsNone(t3.next_host(status, "gone", 0))
        self.assertEqual(t3.status_path(None), "/t3/status")
        self.assertEqual(t3.status_path("fate"), "/t3/status?src=fate")

    def test_lights(self):
        self.assertEqual(t3.lights_level({"attention": 0, "working": 0}, 500), 0)
        pulse = [t3.lights_level({"attention": 1}, t) for t in range(0, 1200, 50)]
        self.assertAlmostEqual(min(pulse), 0.1, places=2)
        self.assertGreater(max(pulse), 0.75)
        self.assertLess(max(t3.lights_level({"working": 3}, t) for t in range(0, 3000, 100)), 0.13)


class AutoGPTTimeTests(unittest.TestCase):
    def test_iso_parsing(self):
        self.assertEqual(ag.iso_to_epoch("1970-01-01T00:00:00Z"), 0)
        self.assertEqual(ag.iso_to_epoch("2026-10-26T18:55:33.647000Z"), 1793040933)
        self.assertEqual(ag.iso_to_epoch("2026-10-26T20:55:33+02:00"), 1793040933)
        self.assertEqual(ag.iso_to_epoch("2026-10-26T16:55:33-02:00"), 1793040933)
        for bad in (None, "", "yesterday", 5):
            self.assertIsNone(ag.iso_to_epoch(bad))

    def test_http_date(self):
        self.assertEqual(ag.http_date_to_epoch("Tue, 27 Oct 2026 02:21:52 GMT"), 1793067712)
        self.assertIsNone(ag.http_date_to_epoch("garbage"))
        self.assertIsNone(ag.http_date_to_epoch(None))

    def test_civil_conversions_match_datetime(self):
        rng = random.Random(7)
        epoch = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
        for _ in range(300):
            seconds = rng.randrange(0, 5_000_000_000)
            expected = (epoch + datetime.timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")
            self.assertEqual(ag.epoch_to_iso(seconds), expected)
            self.assertEqual(ag.iso_to_epoch(expected), seconds)

    def test_formatting(self):
        self.assertEqual([ag.duration_text(s) for s in (None, 0, 12.4, 75, 3725)], ["", "", "12s", "1m 15s", "1h 2m"])
        self.assertEqual([ag.money(c) for c in (None, 0, 432, 1234567, -5)], ["", "$0.00", "$4.32", "$12345.67", "-$0.05"])
        self.assertEqual([ag.until_text(s) for s in (None, 30, 61, 7200, 90000)], ["", "now", "in 2m", "in 2h", "in 1d"])
        self.assertEqual(ag.environment("https://backend.agpt.co/api/v2"), "prod")
        self.assertEqual(ag.environment("https://dev-server.agpt.co/api/v2"), "dev")
        self.assertEqual(ag.environment("http://127.0.0.1:8791/api/v2"), "127.0.0.1")


def run_item(run_id, graph_id, status="COMPLETED", **extra):
    item = {"id": run_id, "graph_id": graph_id, "graph_version": 3, "status": status,
            "started_at": "2026-10-26T18:00:00Z", "ended_at": "2026-10-26T18:00:12Z",
            "duration_seconds": 12.0, "cost_cents": 2, "node_exec_count": 5, "inputs": {"x": "y"}}
    item.update(extra)
    return item


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.original_time = ag.time
        ag.time = self.clock
        self.dash = ag.Dashboard({"g-known": "Known agent"})

    def tearDown(self):
        ag.time = self.original_time

    def drain(self, answers):
        """Serve every queued request from answers[key] until the cycle ends."""
        served = []
        while True:
            request = self.dash.next_request(self.clock.now)
            if request is None:
                return served
            key, path = request
            served.append(key)
            status, payload = answers(key, path)
            self.dash.handle(key, status, payload, self.clock.now)

    def test_first_cycle_without_clock_skips_failures_then_names_follow_runs(self):
        def answers(key, path):
            if key == "recent":
                return 200, {"items": [run_item("r1", "g-known"), run_item("r2", "g-new"), run_item("r3", "g-new")]}
            if key.startswith("name:"):
                return 200, {"name": "New \u00e9 agent"}
            if key == "credits":
                return 200, {"balance_cents": 432}
            if key == "schedules":
                return 200, {"items": [{"name": "Later", "next_run_time": "2026-10-28T00:00:00Z"},
                                       {"name": "Soon", "next_run_time": "2026-10-27T09:00:00Z"},
                                       {"name": "Paused", "next_run_time": None}]}
            return 200, {"items": [], "total_count": 2}

        served = self.drain(answers)
        self.assertEqual(served, ["recent", "name:g-new", "autopilot", "count:RUNNING", "count:QUEUED", "count:REVIEW",
                                  "credits", "schedules"])
        self.assertEqual(self.dash.name_of(self.dash.runs[1]), "New agent")
        self.assertEqual(self.dash.counts, {"RUNNING": 2, "QUEUED": 2, "REVIEW": 2, "FAILED": None})
        self.assertEqual(self.dash.balance, 432)
        self.assertEqual(self.dash.next_schedule, ("Soon", ag.iso_to_epoch("2026-10-27T09:00:00Z")))
        self.assertTrue(self.dash.loaded)

    def test_first_cycle_counts_failures_once_an_answer_sets_the_clock(self):
        paths = []

        def answers(key, path):
            paths.append(path)
            if key == "recent":
                # The app sets the clock from each response's Date header.
                self.dash.set_clock(ag.http_date_to_epoch("Tue, 27 Oct 2026 02:21:52 GMT"), self.clock.now)
            return 200, {"items": [], "total_count": 1}

        served = self.drain(answers)
        self.assertIn("count:FAILED", served)
        self.assertIn("/runs?statuses=FAILED&started_after=2026-10-26T02:21:52Z&limit=1", paths)
        self.assertEqual(self.dash.counts["FAILED"], 1)

    def test_later_cycles_count_recent_failures_and_raise_alerts(self):
        self.dash.set_clock(1793067712, self.clock.now)
        paths = []
        failures = iter([1, 3])

        def answers(key, path):
            paths.append(path)
            if key == "count:FAILED":
                return 200, {"items": [], "total_count": next(failures)}
            return 200, {"items": [], "total_count": 0}

        self.drain(answers)
        self.assertIn("/runs?statuses=FAILED&started_after=2026-10-26T02:21:52Z&limit=1", paths)
        self.assertFalse(self.dash.alert)
        self.assertIsNone(self.dash.next_request(self.clock.now))  # waits for the next cycle
        self.clock.advance(ag.CYCLE_MS)
        served = self.drain(answers)
        self.assertNotIn("credits", served)  # slow requests run every five minutes
        self.assertTrue(self.dash.alert)
        self.assertEqual(self.dash.counts["FAILED"], 3)

    def test_missing_permissions_hide_panels_and_bad_keys_stop(self):
        def answers(key, path):
            if key in ("credits", "schedules"):
                return 403, "HTTP 403: Missing required permission(s): READ_CREDITS"
            return 200, {"items": [], "total_count": 0}

        self.drain(answers)
        self.assertFalse(self.dash.credits_allowed)
        self.assertFalse(self.dash.schedules_allowed)
        self.assertIsNone(self.dash.fatal)

        self.clock.advance(ag.CYCLE_MS)
        self.drain(lambda key, path: (401, "HTTP 401: Missing authentication."))
        self.assertIn("API key rejected", self.dash.fatal)
        self.clock.advance(10 * ag.CYCLE_MS)
        self.assertIsNone(self.dash.next_request(self.clock.now))
        self.dash.refresh()
        self.assertIsNotNone(self.dash.next_request(self.clock.now))

    def test_404_means_wrong_api_and_names_fall_back(self):
        self.drain(lambda key, path: (404, "HTTP 404: Not Found"))
        self.assertIn("No v2 API", self.dash.fatal)
        dash = ag.Dashboard()
        dash.handle("name:abcdef123", 404, "HTTP 404", 0)
        self.assertEqual(dash.names["abcdef123"], "Agent abcdef")

    def test_transient_errors_retry_sooner_until_loaded_and_rate_limits_wait(self):
        self.dash.handle("recent", 0, "timed out", self.clock.now)
        self.assertEqual(self.dash.error, "timed out")
        self.assertEqual(self.dash.cycle_at, self.clock.ticks_add(self.clock.now, ag.RETRY_MS))
        self.dash.queue = [("count:RUNNING", "/x")]
        self.dash.handle("count:QUEUED", 429, "HTTP 429", self.clock.now)
        self.assertEqual(self.dash.queue, [])
        self.assertEqual(self.dash.cycle_at, self.clock.ticks_add(self.clock.now, 60000))

    def test_name_cache_is_bounded(self):
        dash = ag.Dashboard()
        for index in range(ag.NAME_CACHE + 10):
            dash.handle("name:g%d" % index, 200, {"name": "n%d" % index}, 0)
        self.assertEqual(len(dash.names), ag.NAME_CACHE)

    def test_lights(self):
        self.assertEqual(ag.lights_level({"REVIEW": 0, "RUNNING": 0}, None, 100), 0)
        self.assertIn(ag.lights_level({}, 3000, 100), (0.0, 0.9))
        self.assertGreater(max(ag.lights_level({"REVIEW": 1}, None, t) for t in range(0, 1200, 50)), 0.75)
        self.assertGreater(max(ag.lights_level({}, None, t, {"needs_user": 1}) for t in range(0, 1200, 50)), 0.75)
        self.assertLess(max(ag.lights_level({}, None, t, {"working": 2}) for t in range(0, 3000, 100)), 0.13)


class AutoPilotTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.original_time = ag.time
        ag.time = self.clock

    def tearDown(self):
        ag.time = self.original_time

    def test_session_states_and_personas(self):
        base = {"id": "s1", "title": "Plan \u2728 launch", "updated_at": "2026-10-26T18:55:33Z"}
        otto = ag.parse_session(dict(base, status="running", is_processing=True, expert_id=None))
        self.assertEqual((otto["state"], otto["persona"], otto["title"]), ("working", "Otto", "Plan launch"))
        self.assertEqual(otto["updated"], 1793040933)
        expert = ag.parse_session(dict(base, status="queued", is_processing=False, expert_id="e1", expert_name="Harper"))
        self.assertEqual((expert["state"], expert["persona"]), ("queued", "Harper"))
        nameless = ag.parse_session(dict(base, status="idle", is_processing=False, expert_id="e2"))
        self.assertEqual((nameless["state"], nameless["persona"]), ("idle", "Expert"))
        waiting = ag.parse_session(dict(base, status="idle", is_processing=False, needs_user=True))
        self.assertEqual(waiting["state"], "needs_user")
        untitled = ag.parse_session({"id": "s2", "is_processing": True})
        self.assertEqual((untitled["title"], untitled["state"]), ("Untitled chat", "working"))

    def test_every_cycle_polls_autopilot_and_counts_chats(self):
        dash = ag.Dashboard()
        planned = [key for key, _ in dash.plan(self.clock.now)]
        self.assertIn("autopilot", planned)
        dash.handle("autopilot", 200, {"items": [
            {"id": "a", "status": "running", "is_processing": True},
            {"id": "b", "status": "queued", "is_processing": False},
            {"id": "c", "status": "idle", "is_processing": False, "needs_user": True},
            {"id": "d", "status": "idle", "is_processing": False},
        ], "total_count": 40}, self.clock.now)
        self.assertTrue(dash.autopilot)
        self.assertEqual(dash.chats, {"working": 1, "queued": 1, "needs_user": 1, "total": 40})

    def test_missing_endpoint_hides_the_tab_and_retries_with_slow_requests(self):
        dash = ag.Dashboard()
        self.assertIn("autopilot", [key for key, _ in dash.plan(self.clock.now)])  # also schedules slow work
        dash.handle("autopilot", 404, "HTTP 404: Not Found", self.clock.now)
        self.assertIs(dash.autopilot, False)
        self.assertIsNone(dash.fatal)
        self.clock.advance(ag.CYCLE_MS)
        self.assertNotIn("autopilot", [key for key, _ in dash.plan(self.clock.now)])
        self.clock.advance(ag.SLOW_MS)
        self.assertIn("autopilot", [key for key, _ in dash.plan(self.clock.now)])
        dash.handle("autopilot", 403, "HTTP 403: Missing READ_AUTOPILOT", self.clock.now)
        self.assertIs(dash.autopilot, False)
        self.assertIsNone(dash.fatal)


if __name__ == "__main__":
    unittest.main()
