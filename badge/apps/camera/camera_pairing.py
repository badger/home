"""Proximity TOFU key agreement and authenticated remembered-camera sessions."""

import binascii
import hashlib
import json
import os

from camera_core import CameraError

N = int(
    "AC6BDB41324A9A9BF166DE5E1389582FAF72B6651987EE07FC3192943DB56050"
    "A37329CBB4A099ED8193E0757767A13DD52312AB4B03310DCD7F48A9DA04FD50"
    "E8083969EDB767B0CF6095179A163AB3661A05FBD5FAAAE82918A9962F0B93B8"
    "55F97993EC975EEAA80D740ADBF4FF747359D041D5C33EA71D281E446B14773B"
    "CA97B43A23FB801676BD207A436C6481F1D2B9078717461A5B9D32E688F87748"
    "544523B524B0D57D5EA77A2775D2ECFA032CFBDBF52FB3786160279004E57AE6"
    "AF874E7303CE53299CCC041C7BC308D82A5698F3A8D0C38271AE35F8E9DBFBB6"
    "94B5C803D89F7AE435DE236D525F54759B65E372FCD68EF20FA7111F9E4AFF73", 16)
G = 2
SIZE = 256


def digest(data):
    return hashlib.sha256(data).digest()


def mac(key, data):
    if len(key) > 64:
        key = digest(key)
    key = key + bytes(64 - len(key))
    return digest(bytes(x ^ 0x5c for x in key)
                  + digest(bytes(x ^ 0x36 for x in key) + data))


def equal(left, right):
    if len(left) != len(right):
        return False
    mismatch = 0
    for a, b in zip(left, right):
        mismatch |= a ^ b
    return mismatch == 0


def pad(value):
    return value.to_bytes(SIZE, "big")


class Pairing:
    def __init__(self, camera_id, salt, client_nonce, server_nonce):
        if len(camera_id) != 6 or len(salt) != 16 or len(client_nonce) != 16 or len(server_nonce) != 16:
            raise CameraError("Invalid pairing hello")
        self.identity = binascii.hexlify(camera_id)
        self.salt = salt
        self.context = b"BadgeCam-v1" + camera_id + client_nonce + server_nonce
        self.key = None
        self.transcript = None

    def nearby(self, token):
        if (len(token) != 64
                or any(c not in b"0123456789abcdef" for c in token)):
            raise CameraError("Invalid proximity pairing token")
        return self.exchange(token)

    def exchange(self, token):
        self.secret = int.from_bytes(os.urandom(32), "big")
        self.public = pad(pow(G, self.secret, N))
        self.x = int.from_bytes(digest(self.salt + digest(self.identity + b":" + token)), "big")
        return self.public

    def challenge(self, public):
        if len(public) != SIZE:
            raise CameraError("Invalid SRP challenge")
        peer = int.from_bytes(public, "big")
        if not 0 < peer < N:
            raise CameraError("Invalid SRP public value")
        multiplier = int.from_bytes(digest(pad(N) + pad(G)), "big")
        scramble = int.from_bytes(digest(self.public + public), "big")
        if not scramble:
            raise CameraError("Invalid SRP scramble")
        base = (peer - multiplier * pow(G, self.x, N)) % N
        shared = pow(base, self.secret + scramble * self.x, N)
        if shared in (0, 1):
            raise CameraError("Invalid SRP shared value")
        self.transcript = digest(self.context + self.salt + self.public + public)
        self.key = mac(digest(pad(shared)), b"pair" + self.transcript)
        self.secret = self.x = None
        return mac(self.key, b"client" + self.transcript)

    def verify(self, proof):
        if not equal(proof, mac(self.key, b"server" + self.transcript)):
            raise CameraError("Camera pairing proof failed")
        return self.key

    def reconnect(self, key):
        self.key = key
        return mac(key, b"resume" + self.context)

    def credentials(self, packet):
        import cryptolib
        if self.key is None or len(packet) < 64 or (len(packet) - 48) % 16:
            raise CameraError("Invalid encrypted credentials")
        session_key = mac(self.key, b"session" + self.context)
        authentication = mac(session_key, b"mac")
        if not equal(mac(authentication, packet[:-32]), packet[-32:]):
            raise CameraError("Camera credential authentication failed")
        plain = cryptolib.aes(mac(session_key, b"enc"), 2, packet[:16]).decrypt(packet[16:-32])
        padding = plain[-1]
        if not 1 <= padding <= 16 or plain[-padding:] != bytes([padding]) * padding:
            raise CameraError("Invalid camera credential padding")
        config = json.loads(plain[:-padding])
        identity = self.identity.decode()
        if (config.get("camera_id") != identity or config.get("ssid") != "BadgeCam-" + identity
                or not isinstance(config.get("password"), str)
                or len(config["password"]) != 48
                or any(c not in "0123456789abcdef" for c in config["password"])):
            raise CameraError("Unexpected camera credentials")
        config["host"] = "192.168.4.1"
        config["port"] = 80
        return config


def save_config(path, value):
    temporary = path + ".tmp"
    with open(temporary, "w") as file:
        json.dump(value, file)
    os.rename(temporary, path)
