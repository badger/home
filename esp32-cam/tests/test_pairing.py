import hashlib
import hmac
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from srptools import SRPContext

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "badge/apps/camera"))
import camera_pairing as pairing


class PairingTests(unittest.TestCase):
    def setUp(self):
        self.client = pairing.Pairing(bytes(range(6)), bytes(range(16)),
                                      bytes(range(16, 32)), bytes(range(32, 48)))

    def test_hmac_matches_standard_library(self):
        for key in (b"", bytes(32), bytes(range(100))):
            self.assertEqual(pairing.mac(key, b"message"),
                             hmac.digest(key, b"message", "sha256"))

    def test_srp_shared_key_matches_independent_library(self):
        token = b"ab" * 32
        context = SRPContext(self.client.identity.decode(), token.decode(),
                             prime=format(pairing.N, "x"), generator="2",
                             hash_func=hashlib.sha256)
        # srptools serialises integers minimally; use a non-zero-leading salt here.
        self.client.salt = bytes(range(1, 17))
        public = self.client.nearby(token)
        private = 123456789012345678901234567890123456789
        x = context.get_common_password_hash(int.from_bytes(self.client.salt, "big"))
        verifier = context.get_common_password_verifier(x)
        server_public = context.get_server_public(verifier, private)
        scramble = context.get_common_secret(server_public, int.from_bytes(public, "big"))
        shared = context.get_server_premaster_secret(verifier, private, int.from_bytes(public, "big"), scramble)
        proof = self.client.challenge(pairing.pad(server_public))
        expected = pairing.mac(pairing.digest(pairing.pad(shared)), b"pair" + self.client.transcript)
        self.assertEqual(self.client.key, expected)
        self.assertEqual(proof, pairing.mac(expected, b"client" + self.client.transcript))
        self.assertEqual(self.client.verify(pairing.mac(expected, b"server" + self.client.transcript)), expected)
        with self.assertRaisesRegex(pairing.CameraError, "proof"):
            self.client.verify(bytes(32))

    def test_srp_rejects_invalid_public_values(self):
        self.client.nearby(b"ab" * 32)
        for value in (b"short", bytes(256), pairing.pad(pairing.N)):
            with self.assertRaises(pairing.CameraError):
                self.client.challenge(value)

    def test_mismatched_tokens_cannot_confirm_pairing(self):
        self.client.salt = bytes(range(1, 17))
        context = SRPContext(self.client.identity.decode(), "ab" * 32,
                             prime=format(pairing.N, "x"), generator="2",
                             hash_func=hashlib.sha256)
        public = self.client.nearby(b"cd" * 32)
        private = 123456789012345678901234567890123456789
        x = context.get_common_password_hash(int.from_bytes(self.client.salt, "big"))
        verifier = context.get_common_password_verifier(x)
        server_public = context.get_server_public(verifier, private)
        scramble = context.get_common_secret(server_public, int.from_bytes(public, "big"))
        shared = context.get_server_premaster_secret(
            verifier, private, int.from_bytes(public, "big"), scramble)
        proof = self.client.challenge(pairing.pad(server_public))
        key = pairing.mac(pairing.digest(pairing.pad(shared)), b"pair" + self.client.transcript)
        self.assertNotEqual(proof, pairing.mac(key, b"client" + self.client.transcript))
        with self.assertRaisesRegex(pairing.CameraError, "proof"):
            self.client.verify(pairing.mac(key, b"server" + self.client.transcript))

    def test_token_validation(self):
        for token in (b"", b"ab" * 31, b"ab" * 33, b"AB" * 32, b"z" * 64, b"123456"):
            with self.assertRaises(pairing.CameraError):
                self.client.nearby(token)

    def test_fresh_sessions_and_tokens_produce_different_keys(self):
        clients = [pairing.Pairing(bytes(range(6)), bytes(range(16)),
                                  bytes([index]) * 16, bytes(range(32, 48)))
                   for index in range(3)]
        keys = []
        for index, client in enumerate(clients):
            client.nearby(bytes([97 + index]) * 64)
            client.challenge(pairing.pad(pow(2, 1234567, pairing.N)))
            keys.append(client.key)
        self.assertEqual(len(set(keys)), 3)

    def test_resume_is_bound_to_both_nonces_and_camera(self):
        key = bytes(range(32))
        first = self.client.reconnect(key)
        for args in ((bytes(6), self.client.salt, bytes(range(16, 32)), bytes(range(32, 48))),
                     (bytes(range(6)), self.client.salt, bytes(16), bytes(range(32, 48))),
                     (bytes(range(6)), self.client.salt, bytes(range(16, 32)), bytes(16))):
            other = pairing.Pairing(*args)
            self.assertNotEqual(first, other.reconnect(key))

    def encrypted_config(self, **changes):
        self.client.reconnect(bytes(range(32)))
        key = pairing.mac(self.client.key, b"session" + self.client.context)
        config = {"camera_id": self.client.identity.decode(),
                  "ssid": "BadgeCam-" + self.client.identity.decode(), "password": "ab" * 24}
        config.update(changes)
        plain = json.dumps(config).encode()
        n = 16 - len(plain) % 16
        plain += bytes([n]) * n
        iv = bytes(range(16))
        encryptor = Cipher(algorithms.AES(pairing.mac(key, b"enc")), modes.CBC(iv)).encryptor()
        packet = iv + encryptor.update(plain) + encryptor.finalize()
        return packet + pairing.mac(pairing.mac(key, b"mac"), packet)

    def decode(self, packet):
        def aes(key, mode, iv):
            self.assertEqual(mode, 2)
            decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
            return types.SimpleNamespace(decrypt=lambda data: decryptor.update(data) + decryptor.finalize())
        with patch.dict(sys.modules, {"cryptolib": types.SimpleNamespace(aes=aes)}):
            return self.client.credentials(packet)

    def test_authenticated_credentials(self):
        packet = self.encrypted_config()
        self.assertEqual(self.decode(packet)["password"], "ab" * 24)
        for index in (0, 16, len(packet) - 1):
            corrupt = bytearray(packet)
            corrupt[index] ^= 1
            with self.assertRaisesRegex(pairing.CameraError, "authentication"):
                self.decode(bytes(corrupt))

    def test_credentials_reject_wrong_identity_and_password(self):
        for changes in ({"camera_id": "other"}, {"ssid": "other"}, {"password": "short"}):
            with self.assertRaisesRegex(pairing.CameraError, "Unexpected"):
                self.decode(self.encrypted_config(**changes))

    def test_config_persists_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "config.json")
            pairing.save_config(path, {"camera_id": "test"})
            pairing.save_config(path, {"camera_id": "replacement"})
            self.assertEqual(json.loads(Path(path).read_text()), {"camera_id": "replacement"})
            self.assertFalse(Path(path + ".tmp").exists())
