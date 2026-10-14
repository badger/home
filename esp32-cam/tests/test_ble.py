import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import Mock, patch

APP = Path(__file__).resolve().parents[2] / "badge/apps/camera"
sys.path.insert(0, str(APP))


class UUID:
    def __init__(self, value):
        self.value = value.value if isinstance(value, UUID) else value

    def __bytes__(self):
        return bytes.fromhex(self.value.replace("-", ""))[::-1]

    def __eq__(self, other):
        return isinstance(other, UUID) and self.value == other.value


class Radio:
    def __init__(self):
        self.enabled = False
        self.writes = []

    def active(self, value=None):
        if value is not None:
            self.enabled = value
        return self.enabled

    def irq(self, callback):
        self.callback = callback

    def gap_scan(self, *args):
        self.scan = args

    def gattc_write(self, *args):
        self.writes.append(args)


spec = importlib.util.spec_from_file_location("tested_camera_ble", APP / "camera_ble.py")
ble = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"bluetooth": types.SimpleNamespace(UUID=UUID, BLE=Radio)}):
    spec.loader.exec_module(ble)


class BLETests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = str(Path(self.directory.name) / "config.json")
        patcher = patch.object(time, "ticks_ms", return_value=100, create=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch.object(time, "ticks_diff", side_effect=lambda a, b: a - b, create=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.p = ble.Provisioner({}, self.path)
        self.addCleanup(self.p.close)

    def test_discovery_copies_and_bounds_advertisements(self):
        for index in range(30):
            addr = bytes([index]) * 6
            payload = bytes([17, 7]) + bytes(ble.SERVICE)
            self.p.irq(5, (0, addr, 0, -40, payload))
            name = b"BadgeCam-" + addr.hex().encode()
            self.p.irq(5, (0, addr, 4, -40, bytes([len(name) + 1, 9]) + name))
        self.assertEqual(len(self.p.cameras), 8)
        self.assertEqual(len(self.p.names), 16)
        self.p.irq(6, ())
        self.p.step()
        self.assertEqual(self.p.state, "CHOOSE")

    def test_malformed_advertisement_is_ignored(self):
        self.assertEqual(list(ble.fields(b"\x05\x09x")), [])
        self.p.irq(5, (0, bytes(6), 4, -40, b"\x0b\x09BadgeCam-\xff"))
        self.assertFalse(self.p.names)

    def test_callback_tuples_are_copied_before_return(self):
        for event, payload in ((10, (1, 0)), (12, (1, 0)),
                               (16, (1, 2, 0)), (17, (1, 2, 0))):
            self.p.irq(event, payload)
            queued_event, queued = self.p.events.pop()
            self.assertEqual((queued_event, queued), (event, payload))
            self.assertIsNot(queued, payload)

    def test_disconnect_address_is_copied(self):
        address = bytearray(range(6))
        payload = (1, 0, memoryview(address))
        self.p.irq(8, payload)
        address[:] = bytes(6)
        self.assertEqual(self.p.events.pop(), (8, (1, 0, bytes(range(6)))))

    def test_request_fragments_fit_default_mtu(self):
        self.p.conn, self.p.rx = 1, 2
        self.p.send(2, bytes(256))
        while self.p.offset < len(self.p.packet):
            self.p.irq(17, (1, 2, 0))
            self.p.step()
        frames = [args[2] for args in self.p.ble.writes]
        self.assertTrue(all(len(frame) <= 20 for frame in frames))
        self.assertEqual(b"".join(frame[4:] for frame in frames), b"\x02" + bytes(256))
        self.assertEqual([int.from_bytes(frame[:2], "big") for frame in frames], list(range(0, 257, 16)))

    def test_response_pages_reassemble(self):
        self.p.conn, self.p.rx = 1, 2
        self.p.response_total = None
        self.p.completed = Mock()
        payload = b"\x04" + bytes(range(50))
        for offset in range(0, len(payload), 16):
            self.p.read_data = offset.to_bytes(2, "big") + len(payload).to_bytes(2, "big") + payload[offset:offset + 16]
            self.p.response()
        self.p.completed.assert_called_once_with(payload)

    def test_response_gap_and_oversize_rejected(self):
        self.p.response_total = None
        for frame in (b"short!", b"\x00\x10\x00\x20x", b"\x00\x00\x03\x00x"):
            self.p.read_data = frame
            with self.assertRaises(ble.CameraError):
                self.p.response()

    def test_pending_setup_does_not_destroy_existing_key(self):
        self.p.config = {"pair_key": "aa" * 32}
        self.p.operation = 2
        self.p.identity = "001122334455"
        self.p.address = (0, bytes(6))
        self.p.pair = types.SimpleNamespace(key=bytes(32), challenge=lambda data: b"proof")
        self.p.send = Mock()
        self.p.completed(b"\x02challenge")
        saved = json.loads(Path(self.path).read_text())
        self.assertEqual(saved["pair_key"], "aa" * 32)
        self.assertEqual(saved["pending_pair_key"], "00" * 32)

    def test_failed_pending_key_retries_original_once(self):
        self.p.config = {"pair_key": "aa" * 32, "pending_pair_key": "bb" * 32}
        self.p.operation = 4
        self.p.pair = types.SimpleNamespace(reconnect=lambda key: key)
        self.p.send = Mock()
        self.p.completed(b"\xffUnrecognised badge")
        self.p.send.assert_called_once_with(4, bytes.fromhex("aa" * 32))
        with self.assertRaises(ble.CameraError):
            self.p.completed(b"\xffUnrecognised badge")
