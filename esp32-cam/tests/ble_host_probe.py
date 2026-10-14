"""Test the physical camera BLE protocol from a Mac when badge debugging is unavailable."""

import argparse
import asyncio
import binascii
import json
import os
from pathlib import Path
import sys
import time
import types

from bleak import BleakClient, BleakScanner
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import serial

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "badge/apps/camera"))
from camera_pairing import Pairing, CameraError

SERVICE = "b9a10001-9c45-4ec2-867d-9ae58d13a001"
RX = "b9a10002-9c45-4ec2-867d-9ae58d13a001"
TX = "b9a10003-9c45-4ec2-867d-9ae58d13a001"


def aes(key, mode, iv):
    assert mode == 2
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    return types.SimpleNamespace(decrypt=lambda data: decryptor.update(data) + decryptor.finalize())


sys.modules["cryptolib"] = types.SimpleNamespace(aes=aes)


class SerialRPC:
    """Exercise the same camera crypto handler over USB, not the BLE radio."""
    def __init__(self, port):
        self.serial = serial.Serial(port, 115200, timeout=.2)
        self.serial.dtr = False
        self.serial.rts = False
        self.packet = bytearray()
        self.response = b""
        self.offset = 0

    async def __aenter__(self):
        await asyncio.sleep(2)
        self.serial.reset_input_buffer()
        return self

    async def __aexit__(self, *args):
        self.serial.close()

    async def write_gatt_char(self, uuid, value, response):
        if value[0] == 255:
            self.offset = int.from_bytes(value[1:], "big")
            return
        offset, total = int.from_bytes(value[:2], "big"), int.from_bytes(value[2:4], "big")
        if offset == 0:
            self.packet = bytearray()
        assert offset == len(self.packet)
        self.packet.extend(value[4:])
        if len(self.packet) == total:
            self.serial.write(b"RPC " + self.packet.hex().encode() + b"\n")
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                line = self.serial.readline().strip()
                if line.startswith(b"RPC "):
                    self.response = bytes.fromhex(line[4:].decode())
                    self.offset = 0
                    return
            raise RuntimeError("Camera serial RPC timed out")

    async def read_gatt_char(self, uuid):
        return (self.offset.to_bytes(2, "big") + len(self.response).to_bytes(2, "big")
                + self.response[self.offset:self.offset + 16])


async def rpc(client, operation, data):
    packet = bytes([operation]) + data
    for offset in range(0, len(packet), 16):
        frame = offset.to_bytes(2, "big") + len(packet).to_bytes(2, "big") + packet[offset:offset + 16]
        await client.write_gatt_char(RX, frame, response=True)
    result = bytearray()
    for _ in range(1000):
        await asyncio.sleep(.04)
        page = bytes(await client.read_gatt_char(TX))
        if page == b"\x00":
            continue
        if len(page) < 5:
            raise RuntimeError("Invalid BLE response page")
        offset, length = int.from_bytes(page[:2], "big"), int.from_bytes(page[2:4], "big")
        if offset < len(result):
            continue
        assert offset == len(result) and 0 < length <= 512
        result.extend(page[4:])
        if len(result) == length:
            if result[0] == 255:
                raise CameraError(result[1:].decode())
            if result[0] != operation:
                result.clear()
                continue
            return bytes(result[1:])
        await client.write_gatt_char(RX, b"\xff" + len(result).to_bytes(2, "big"), response=True)
    raise RuntimeError("BLE RPC timed out")


async def hello(client, identity):
    nonce = os.urandom(16)
    data = await rpc(client, 1, nonce)
    assert len(data) == 39 and data[:6].hex() == identity
    return Pairing(data[:6], data[6:22], nonce, data[22:38]), bool(data[38])


async def main(args):
    setup = json.loads(args.setup.read_text())
    if args.serial_port:
        connection = SerialRPC(args.serial_port)
        print("USB protocol test: this does NOT validate the BLE radio/transport.", flush=True)
    else:
        device = await BleakScanner.find_device_by_filter(
            lambda device, adv: SERVICE in adv.service_uuids
            and adv.local_name == "BadgeCam-" + setup["camera_id"], timeout=20)
        if not device:
            raise RuntimeError("Camera BLE advertisement not found")
        print("PASS real camera BLE advertisement discovered", flush=True)
        connection = BleakClient(device, timeout=20)
    old = json.loads(args.config.read_text()) if args.config.exists() else None
    async with connection as client:
        pairing, paired = await hello(client, setup["camera_id"])
        if not paired:
            public = pairing.start("%06d" % ((int(setup["code"]) + 1) % 1000000))
            challenge = await rpc(client, 2, public)
            try:
                await rpc(client, 3, pairing.challenge(challenge))
            except CameraError as error:
                assert str(error) == "Incorrect pairing code", str(error)
                print("PASS incorrect SRP code rejected", flush=True)
            else:
                raise AssertionError("Incorrect code accepted")
            await asyncio.sleep(6)
            pairing, paired = await hello(client, setup["camera_id"])
            assert not paired
            challenge = await rpc(client, 2, pairing.start(setup["code"]))
            proof = pairing.challenge(challenge)
            config = {"pairing": "srp-v1", "camera_id": setup["camera_id"],
                      "pair_key": pairing.key.hex()}
            args.config.write_text(json.dumps(config))
            args.config.chmod(0o600)
            pairing.verify(await rpc(client, 3, proof))
            print("PASS real ESP32 SRP shared key and server proof", flush=True)
        else:
            assert old is not None, "Camera is paired but no saved test key is available"
            config = dict(old)
        proof = pairing.reconnect(bytes.fromhex(config["pair_key"]))
        encrypted = await rpc(client, 4, proof)
        config.update(pairing.credentials(encrypted))
        args.config.write_text(json.dumps(config))
        args.config.chmod(0o600)
        print("PASS authenticated encrypted Wi-Fi credentials retrieved", flush=True)
        if args.check_rekey:
            assert old and old["password"] != config["password"]
            assert old["pair_key"] == config["pair_key"]
            print("PASS camera restart rotates Wi-Fi password and preserves pairing", flush=True)
        next_pairing, paired = await hello(client, setup["camera_id"])
        assert paired
        for bad in (bytes(32), proof):
            try:
                await rpc(client, 4, bad)
            except CameraError as error:
                assert str(error) == "Unrecognised badge", str(error)
            else:
                raise AssertionError("Unauthorised/replayed proof accepted")
        print("PASS unauthorised and replayed protocol requests rejected", flush=True)
        try:
            await rpc(client, 2, pairing.start(setup["code"]))
        except CameraError as error:
            assert str(error) == "Camera already paired", str(error)
        else:
            raise AssertionError("Owned camera allowed replacement pairing")
        print("PASS owned camera rejects replacement pairing", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup", required=True, type=Path, help="Private camera ID/code JSON from USB")
    parser.add_argument("--config", required=True, type=Path, help="Private pairing output; never commit")
    parser.add_argument("--check-rekey", action="store_true")
    parser.add_argument("--serial-port", help="Validate crypto over USB instead; does not test BLE")
    asyncio.run(main(parser.parse_args()))
