"""Bounded BLE discovery/RPC, with persistent application-level pairing."""

import binascii
import bluetooth
import os
import time

from camera_core import CameraError
from camera_pairing import Pairing, save_config

SERVICE = bluetooth.UUID("b9a10001-9c45-4ec2-867d-9ae58d13a001")
RX = bluetooth.UUID("b9a10002-9c45-4ec2-867d-9ae58d13a001")
TX = bluetooth.UUID("b9a10003-9c45-4ec2-867d-9ae58d13a001")


def fields(payload):
    offset = 0
    while offset < len(payload):
        length = payload[offset]
        if not length or offset + length >= len(payload):
            return
        yield payload[offset + 1], payload[offset + 2:offset + length + 1]
        offset += length + 1


class Provisioner:
    def __init__(self, config, config_path):
        self.config = config
        self.path = config_path
        self.state = "SCANNING"
        self.message = "Looking for BLE cameras..."
        self.cameras = []
        self.names = {}
        self.choice = 0
        self.conn = None
        self.service = None
        self.rx = self.tx = None
        self.events = []
        self.error = None
        self.packet = None
        self.result = None
        self.read_data = b""
        self.received = bytearray()
        self.awaiting = None
        self.next_read = None
        self.tried_original = False
        self.direct = False
        self.started = time.ticks_ms()
        self.ble = bluetooth.BLE()
        self.owned = False
        if self.ble.active():
            raise CameraError("Bluetooth already in use")
        self.ble.active(True)
        self.owned = True
        try:
            self.ble.irq(self.irq)
            address = config.get("ble_addr")
            if (isinstance(address, str) and len(address) == 12
                    and all(c in "0123456789abcdef" for c in address)
                    and config.get("ble_addr_type") in (0, 1)):
                self.address = (config["ble_addr_type"], binascii.unhexlify(address))
                self.state = "DIRECT"
                self.direct = True
                self.message = "Reconnecting to paired camera..."
                try:
                    self.ble.gap_connect(self.address[0], self.address[1], 3000)
                except OSError as error:
                    self.scan_fallback(str(error))
            else:
                self.scan()
        except Exception:
            self.close()
            raise

    def scan(self):
        self.direct = False
        self.state = "SCANNING"
        self.message = "Looking for BLE cameras..."
        self.started = time.ticks_ms()
        self.ble.gap_scan(5000, 100000, 30000, True)

    def scan_fallback(self, reason):
        print("Camera: direct BLE connection failed; scanning:", reason)
        # Stop any outstanding direct connection before starting discovery.
        self.ble.irq(None)
        self.ble.active(False)
        self.events.clear()
        self.conn = None
        self.service = None
        self.rx = self.tx = None
        self.ble.active(True)
        self.ble.irq(self.irq)
        self.scan()

    def irq(self, event, data):
        if event == 5:
            addr_type, addr, _, rssi, advertisement = data
            key = (addr_type, bytes(addr))
            service = False
            for kind, value in fields(bytes(advertisement)):
                if (kind in (8, 9) and len(value) == 21 and value.startswith(b"BadgeCam-")
                        and all(c in b"0123456789abcdef" for c in value[9:])
                        and (key in self.names or len(self.names) < 16)):
                    self.names[key] = value.decode()
                if kind in (6, 7) and bytes(SERVICE) in value:
                    service = True
            if service and all(item[:2] != key for item in self.cameras) and len(self.cameras) < 8:
                self.cameras.append((key[0], key[1], rssi))
            return
        if len(self.events) >= 32:
            self.error = "BLE event overflow"
            return
        if event in (7, 8):
            data = (data[0], data[1], bytes(data[2]))
        elif event in (9, 11):
            data = tuple(data[:-1]) + (bluetooth.UUID(data[-1]),)
        elif event == 15:
            data = (data[0], data[1], bytes(data[2]))
        elif event == 6:
            data = ()
        elif event in (10, 12):
            data = (data[0], data[1])
        elif event in (16, 17):
            data = (data[0], data[1], data[2])
        else:
            return
        # Synchronous MicroPython frees the callback tuple on return, including
        # numeric-only events. Never queue that tuple or tuple(data) (an alias).
        self.events.append((event, data))

    def choose(self):
        if self.state != "CHOOSE" or not self.cameras:
            return
        addr_type, address, _ = self.cameras[self.choice]
        self.address = (addr_type, address)
        self.state = "WORKING"
        self.message = "Connecting over BLE..."
        self.started = time.ticks_ms()
        self.ble.gap_connect(addr_type, address, 10000)

    def camera_name(self):
        if not self.cameras:
            return "No camera"
        item = self.cameras[self.choice]
        return self.names.get(item[:2], "Camera " + binascii.hexlify(item[1]).decode())

    def send(self, operation, data):
        self.operation = operation
        self.packet = bytes([operation]) + data
        self.offset = 0
        self.received = bytearray()
        self.response_total = None
        self.next_read = None
        self.started = time.ticks_ms()
        self.write_next()

    def write_next(self):
        end = min(self.offset + 16, len(self.packet))
        frame = (self.offset.to_bytes(2, "big") + len(self.packet).to_bytes(2, "big")
                 + self.packet[self.offset:end])
        self.offset = end
        self.awaiting = "write"
        self.ble.gattc_write(self.conn, self.rx, frame, 1)

    def read(self):
        self.read_data = b""
        self.awaiting = "read"
        self.next_read = None
        self.ble.gattc_read(self.conn, self.tx)

    def response(self):
        data = self.read_data
        if data == b"\x00":
            self.next_read = time.ticks_ms() + 40
            return
        if len(data) < 5 or len(data) > 20:
            raise CameraError("Invalid BLE response")
        offset, total = int.from_bytes(data[:2], "big"), int.from_bytes(data[2:4], "big")
        # A page request is queued on the camera; its previous page may still be visible.
        if offset < len(self.received):
            self.next_read = time.ticks_ms() + 40
            return
        if (offset != len(self.received) or not 1 <= total <= 512
                or (self.response_total is not None and total != self.response_total)
                or offset + len(data) - 4 > total):
            raise CameraError("Invalid BLE response sequence")
        self.response_total = total
        self.received.extend(data[4:])
        if len(self.received) == total:
            self.completed(bytes(self.received))
        else:
            self.awaiting = "page"
            self.ble.gattc_write(self.conn, self.rx,
                                 b"\xff" + len(self.received).to_bytes(2, "big"), 1)

    def completed(self, response):
        operation, data = response[0], response[1:]
        if operation == 255:
            if (self.operation == 4 and data == b"Unrecognised badge"
                    and self.config.get("pending_pair_key") and self.config.get("pair_key")
                    and not self.tried_original):
                self.tried_original = True
                print("Camera: retrying saved relationship after interrupted pairing")
                self.send(4, self.pair.reconnect(binascii.unhexlify(self.config["pair_key"])))
                return
            raise CameraError(data.decode())
        if operation != self.operation:
            # The command's final fragment may not have reached the camera loop yet.
            self.received = bytearray()
            self.response_total = None
            self.next_read = time.ticks_ms() + 40
            return
        if operation == 1:
            if len(data) != 39:
                raise CameraError("Invalid BLE camera hello")
            self.pair = Pairing(data[:6], data[6:22], self.nonce, data[22:38])
            identity = self.pair.identity.decode()
            if self.config.get("camera_id") and self.config["camera_id"] != identity:
                raise CameraError("Wrong camera identity")
            self.identity = identity
            if data[38] & 1:
                key = self.config.get("pending_pair_key") or self.config.get("pair_key")
                if not isinstance(key, str) or len(key) != 64:
                    raise CameraError("Camera paired elsewhere; reset pairing")
                self.send(4, self.pair.reconnect(binascii.unhexlify(key)))
            elif data[38] & 2:
                self.state = "NEARBY"
                self.message = "Hold badge against camera..."
                self.send(5, b"")
            else:
                raise CameraError("Update camera firmware for code-free pairing")
        elif operation == 5:
            self.state = "WORKING"
            self.message = "Making camera friends..."
            self.send(2, self.pair.nearby(data))
        elif operation == 2:
            proof = self.pair.challenge(data)
            # Persist before the camera commits, so a lost reply is recoverable.
            self.config = dict(self.config)
            self.config.update({
                "pairing": "srp-v1", "camera_id": self.identity,
                "ble_addr_type": self.address[0],
                "ble_addr": binascii.hexlify(self.address[1]).decode(),
                "pending_pair_key": binascii.hexlify(self.pair.key).decode(),
            })
            save_config(self.path, self.config)
            self.send(3, proof)
        elif operation == 3:
            self.pair.verify(data)
            self.send(4, self.pair.reconnect(self.pair.key))
        elif operation == 4:
            self.config.update(self.pair.credentials(data))
            self.config["pair_key"] = binascii.hexlify(self.pair.key).decode()
            self.config.pop("pending_pair_key", None)
            self.config["ble_addr_type"] = self.address[0]
            self.config["ble_addr"] = binascii.hexlify(self.address[1]).decode()
            save_config(self.path, self.config)
            self.result = self.config
            self.state = "READY"

    def step(self):
        if self.error:
            raise CameraError(self.error)
        while self.events:
            event, data = self.events.pop(0)
            if event == 6 and self.state == "SCANNING":
                known = self.config.get("ble_addr")
                identity = self.config.get("camera_id")
                if known or identity:
                    for index, item in enumerate(self.cameras):
                        if ((binascii.hexlify(item[1]).decode() == known
                             and item[0] == self.config.get("ble_addr_type"))
                                or (identity and self.names.get(item[:2]) == "BadgeCam-" + identity)):
                            self.choice = index
                            self.state = "CHOOSE"
                            self.choose()
                            break
                    else:
                        raise CameraError("Paired camera not found")
                elif self.cameras:
                    self.state = "CHOOSE"
                    self.message = "Select a camera"
                else:
                    raise CameraError("No BLE cameras; power camera")
            elif event == 7:
                self.conn = data[0]
                self.state = "WORKING"
                self.started = time.ticks_ms()
                self.ble.gattc_discover_services(self.conn, SERVICE)
            elif event == 8 and self.state != "READY":
                if self.direct:
                    self.scan_fallback("Camera did not accept connection")
                else:
                    raise CameraError("Camera BLE disconnected")
            elif event == 9:
                if data[3] == SERVICE:
                    self.service = data[1:3]
                else:
                    print("Camera: unexpected BLE service", data[3])
            elif event == 10:
                if data[1] or self.service is None:
                    print("Camera: BLE discovery failed; status", data[1], "handles", self.service)
                    if self.direct:
                        self.scan_fallback("Camera BLE service unavailable")
                        continue
                    raise CameraError("Camera BLE service unavailable")
                self.ble.gattc_discover_characteristics(self.conn, *self.service)
            elif event == 11:
                if data[4] == RX:
                    self.rx = data[2]
                elif data[4] == TX:
                    self.tx = data[2]
            elif event == 12:
                if data[1] or self.rx is None or self.tx is None:
                    if self.direct:
                        self.scan_fallback("Camera BLE characteristics unavailable")
                        continue
                    raise CameraError("Camera BLE characteristics unavailable")
                self.direct = False
                self.nonce = os.urandom(16)
                self.send(1, self.nonce)
            elif event == 17:
                if data[2]:
                    raise CameraError("Camera BLE write failed")
                previous, self.awaiting = self.awaiting, None
                if previous == "write" and self.offset < len(self.packet):
                    self.write_next()
                else:
                    self.next_read = time.ticks_ms() + 30
            elif event == 15:
                self.read_data += data[2]
                if len(self.read_data) > 20:
                    raise CameraError("Camera BLE page too large")
            elif event == 16:
                self.awaiting = None
                if data[2]:
                    raise CameraError("Camera BLE read failed")
                self.response()
        if self.next_read is not None and time.ticks_diff(time.ticks_ms(), self.next_read) >= 0:
            self.read()
        if self.state == "DIRECT" and time.ticks_diff(time.ticks_ms(), self.started) > 3500:
            self.scan_fallback("Direct connection timed out")
        if self.state == "SCANNING" and time.ticks_diff(time.ticks_ms(), self.started) > 7000:
            raise CameraError("Camera BLE scan timed out")
        if self.state in ("WORKING", "NEARBY") and time.ticks_diff(time.ticks_ms(), self.started) > 30000:
            raise CameraError("Camera BLE timed out")
        return self.result

    def close(self):
        if self.owned:
            self.ble.irq(None)
            self.ble.active(False)
            self.owned = False
