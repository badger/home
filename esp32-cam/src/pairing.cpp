#include "pairing.h"
#include "proximity.h"

#include <NimBLEDevice.h>
#include <Preferences.h>
#include <esp_system.h>
#include <mbedtls/aes.h>
#include <mbedtls/bignum.h>
#include <mbedtls/md.h>
#include <mbedtls/sha256.h>
#include <vector>

using Bytes = std::vector<uint8_t>;
static const char *SERVICE = "b9a10001-9c45-4ec2-867d-9ae58d13a001";
static const char *RX_UUID = "b9a10002-9c45-4ec2-867d-9ae58d13a001";
static const char *TX_UUID = "b9a10003-9c45-4ec2-867d-9ae58d13a001";
static const char *PRIME =
    "AC6BDB41324A9A9BF166DE5E1389582FAF72B6651987EE07FC3192943DB56050"
    "A37329CBB4A099ED8193E0757767A13DD52312AB4B03310DCD7F48A9DA04FD50"
    "E8083969EDB767B0CF6095179A163AB3661A05FBD5FAAAE82918A9962F0B93B8"
    "55F97993EC975EEAA80D740ADBF4FF747359D041D5C33EA71D281E446B14773B"
    "CA97B43A23FB801676BD207A436C6481F1D2B9078717461A5B9D32E688F87748"
    "544523B524B0D57D5EA77A2775D2ECFA032CFBDBF52FB3786160279004E57AE6"
    "AF874E7303CE53299CCC041C7BC308D82A5698F3A8D0C38271AE35F8E9DBFBB6"
    "94B5C803D89F7AE435DE236D525F54759B65E372FCD68EF20FA7111F9E4AFF73";

static Preferences storage;
static String identity, ssid, password, enrollmentToken;
static Bytes id, salt, bond, context, candidate, transcript;
static NimBLECharacteristic *output;
static QueueHandle_t inbox;
struct Fragment { uint16_t size; uint8_t data[20]; };
static Bytes incoming, outgoing;
static size_t expected = 0;
static bool hello = false, proofPending = false;
static bool bleSession = false, enrollmentPending = false;
static ProximityGate proximity;
static uint32_t lastSample = 0, enrollmentStart = 0;
static uint32_t lastProximityLog = 0;
static int lastRssi = 127, rssiStatus = 0;
static volatile bool disconnected = false;
static uint32_t sessionStart = 0, lastAttempt = 0;
static bool attempted = false;
static uint8_t failures = 0;
static String serialCommand;
static bool serialOverflow = false;

static Bytes bytes(const String &s) { return Bytes(s.c_str(), s.c_str() + s.length()); }
static Bytes joined(Bytes a, const Bytes &b) { a.insert(a.end(), b.begin(), b.end()); return a; }
static Bytes randomBytes(size_t size) {
    Bytes value(size);
    esp_fill_random(value.data(), size);
    return value;
}
static Bytes hash(const Bytes &data) {
    Bytes result(32);
    mbedtls_sha256_ret(data.data(), data.size(), result.data(), 0);
    return result;
}
static Bytes hmac(const Bytes &key, const Bytes &data) {
    Bytes result(32);
    mbedtls_md_hmac(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256),
                    key.data(), key.size(), data.data(), data.size(), result.data());
    return result;
}
static bool equal(const Bytes &a, const Bytes &b) {
    if (a.size() != b.size()) return false;
    uint8_t diff = 0;
    for (size_t i = 0; i < a.size(); i++) diff |= a[i] ^ b[i];
    return diff == 0;
}
static String hex(const Bytes &data) {
    const char *digits = "0123456789abcdef";
    String result;
    for (uint8_t value : data) { result += digits[value >> 4]; result += digits[value & 15]; }
    return result;
}
static void page(size_t offset) {
    if (offset >= outgoing.size()) { output->setValue(Bytes{0}.data(), 1); return; }
    Bytes value{uint8_t(offset >> 8), uint8_t(offset),
                uint8_t(outgoing.size() >> 8), uint8_t(outgoing.size())};
    size_t count = std::min(size_t(16), outgoing.size() - offset);
    value.insert(value.end(), outgoing.begin() + offset, outgoing.begin() + offset + count);
    output->setValue(value.data(), value.size());
}
static void reply(uint8_t type, const Bytes &data = {}) {
    outgoing = joined(Bytes{type}, data);
    page(0);
}
static void fail(const char *message) {
    Serial.printf("Pairing: %s\n", message);
    reply(255, bytes(message));
}
static void clearSession() {
    hello = proofPending = false;
    bleSession = enrollmentPending = false;
    enrollmentToken = "";
    candidate.clear();
    transcript.clear();
    context.clear();
    incoming.clear();
    outgoing.clear();
    expected = 0;
    page(0);
}

class Number {
public:
    mbedtls_mpi value;
    Number() { mbedtls_mpi_init(&value); }
    ~Number() { mbedtls_mpi_free(&value); }
    Bytes encoded() {
        Bytes result(256);
        if (mbedtls_mpi_write_binary(&value, result.data(), result.size())) return {};
        return result;
    }
    int read(const Bytes &data) { return mbedtls_mpi_read_binary(&value, data.data(), data.size()); }
};

static bool srp(const Bytes &client) {
    Number n, g, a, b, v, k, gb, pub, u, vu, shared, tmp, x;
    Bytes secret = randomBytes(32);
    // The public, proximity-gated token supplies no password authentication.
    // SRP is retained for ephemeral key agreement and mutual key confirmation.
    Bytes xHash = hash(joined(salt, hash(bytes(identity + ":" + enrollmentToken))));
    int error = mbedtls_mpi_read_string(&n.value, 16, PRIME);
    error |= mbedtls_mpi_lset(&g.value, 2);
    error |= a.read(client);
    if (error || mbedtls_mpi_cmp_int(&a.value, 0) <= 0 ||
        mbedtls_mpi_cmp_mpi(&a.value, &n.value) >= 0) return false;
    error |= b.read(secret);
    error |= x.read(xHash);
    error |= k.read(hash(joined(n.encoded(), g.encoded())));
    error |= mbedtls_mpi_exp_mod(&v.value, &g.value, &x.value, &n.value, nullptr);
    error |= mbedtls_mpi_exp_mod(&gb.value, &g.value, &b.value, &n.value, nullptr);
    error |= mbedtls_mpi_mul_mpi(&tmp.value, &k.value, &v.value);
    error |= mbedtls_mpi_add_mpi(&tmp.value, &tmp.value, &gb.value);
    error |= mbedtls_mpi_mod_mpi(&pub.value, &tmp.value, &n.value);
    Bytes publicValue = pub.encoded();
    error |= u.read(hash(joined(client, publicValue)));
    if (error || mbedtls_mpi_cmp_int(&u.value, 0) == 0) return false;
    error |= mbedtls_mpi_exp_mod(&vu.value, &v.value, &u.value, &n.value, nullptr);
    error |= mbedtls_mpi_mul_mpi(&tmp.value, &a.value, &vu.value);
    error |= mbedtls_mpi_mod_mpi(&tmp.value, &tmp.value, &n.value);
    error |= mbedtls_mpi_exp_mod(&shared.value, &tmp.value, &b.value, &n.value, nullptr);
    if (error || mbedtls_mpi_cmp_int(&shared.value, 1) <= 0) return false;
    transcript = hash(joined(joined(joined(context, salt), client), publicValue));
    candidate = hmac(hash(shared.encoded()), joined(bytes("pair"), transcript));
    proofPending = true;
    reply(2, publicValue);
    return true;
}

static void credentials() {
    Bytes key = hmac(bond, joined(bytes("session"), context));
    Bytes enc = hmac(key, bytes("enc")), auth = hmac(key, bytes("mac"));
    Bytes plain = bytes("{\"camera_id\":\"" + identity + "\",\"ssid\":\"" + ssid +
                        "\",\"password\":\"" + password + "\"}");
    uint8_t padding = 16 - plain.size() % 16;
    plain.insert(plain.end(), padding, padding);
    Bytes iv = randomBytes(16), working = iv, cipher(plain.size());
    mbedtls_aes_context aes;
    mbedtls_aes_init(&aes);
    int error = mbedtls_aes_setkey_enc(&aes, enc.data(), 256);
    if (!error) error = mbedtls_aes_crypt_cbc(&aes, MBEDTLS_AES_ENCRYPT, plain.size(),
                                            working.data(), plain.data(), cipher.data());
    mbedtls_aes_free(&aes);
    if (error) { fail("Credential encryption failed"); return; }
    Bytes packet = joined(iv, cipher);
    reply(4, joined(packet, hmac(auth, packet)));
}

static bool enrollmentAllowed(bool viaBLE) {
    if (!bond.empty()) { fail("Camera already paired"); return false; }
    if (!viaBLE || !bleSession) { fail("Pair close to camera over BLE"); return false; }
    if (!proximity.open(millis())) { fail("Restart camera to pair nearby"); return false; }
    return true;
}

static void process(const Bytes &request, bool viaBLE = false) {
    if (request.empty()) { fail("Empty command"); return; }
    uint8_t command = request[0];
    Bytes data(request.begin() + 1, request.end());
    if (command == 1 && data.size() == 16) {
        clearSession();
        Bytes nonce = randomBytes(16);
        context = joined(joined(joined(bytes("BadgeCam-v1"), id), data), nonce);
        sessionStart = millis();
        hello = true;
        bleSession = viaBLE;
        reply(1, joined(joined(joined(id, salt), nonce), Bytes{uint8_t(2 | !bond.empty())}));
    } else if (!hello || millis() - sessionStart > 180000) {
        fail("Pairing session expired");
    } else if (command == 5 && data.empty()) {
        if (!enrollmentAllowed(viaBLE)) return;
        if (enrollmentPending || !enrollmentToken.isEmpty()) {
            fail("Pairing already started"); return;
        }
        enrollmentPending = true;
        enrollmentStart = millis();
        lastProximityLog = 0;
    } else if (command == 2 && data.size() == 256) {
        if (!enrollmentAllowed(viaBLE)) return;
        if (enrollmentToken.isEmpty()) { fail("Start proximity pairing first"); return; }
        if (!proximity.near(millis())) { fail("Hold badge against camera; retry"); return; }
        if (failures >= 5 || (attempted && millis() - lastAttempt < 5000)) {
            fail("Pairing rate limited; restart camera"); return;
        }
        attempted = true;
        lastAttempt = millis();
        failures++;
        proofPending = false;
        if (!srp(data)) fail("Invalid pairing exchange");
    } else if (command == 3 && data.size() == 32 && proofPending && bond.empty()) {
        proofPending = false;
        if (!enrollmentAllowed(viaBLE)) return;
        if (!proximity.near(millis())) { fail("Hold badge against camera; retry"); return; }
        if (!equal(data, hmac(candidate, joined(bytes("client"), transcript)))) {
            candidate.clear();
            fail("Pairing confirmation failed"); return;
        }
        if (storage.putBytes("bond", candidate.data(), candidate.size()) != candidate.size()) {
            fail("Cannot persist pairing"); return;
        }
        bond = candidate;
        candidate.clear();
        enrollmentToken = "";
        reply(3, hmac(bond, joined(bytes("server"), transcript)));
        Serial.println("Pairing established; credentials are not logged.");
    } else if (command == 4 && data.size() == 32 && !bond.empty()) {
        if (!equal(data, hmac(bond, joined(bytes("resume"), context)))) {
            fail("Unrecognised badge"); return;
        }
        credentials();
    } else {
        fail("Unexpected pairing command");
    }
}

class Receiver : public NimBLECharacteristicCallbacks {
    void onWrite(NimBLECharacteristic *characteristic) override {
        std::string value = characteristic->getValue();
        Fragment fragment{};
        if (value.size() <= 20 && !value.empty()) {
            fragment.size = value.size();
            memcpy(fragment.data, value.data(), value.size());
        }
        if (xQueueSend(inbox, &fragment, 0) != pdTRUE) {
            Serial.println("BLE request queue overflow");
            disconnected = true;
        }
    }
};
class Connections : public NimBLEServerCallbacks {
    void onDisconnect(NimBLEServer *) override { disconnected = true; }
};

bool setupPairing(bool) {
    if (!storage.begin("badge-camera", false)) return false;
    id.resize(6);
    esp_read_mac(id.data(), ESP_MAC_WIFI_STA);
    identity = hex(id);
    ssid = "BadgeCam-" + identity;
    password = hex(randomBytes(24));
    salt.resize(16);
    if (!storage.isKey("salt")) {
        salt = randomBytes(16);
        if (storage.putBytes("salt", salt.data(), salt.size()) != salt.size()) return false;
    } else if (storage.getBytes("salt", salt.data(), salt.size()) != salt.size()) return false;
    size_t length = storage.isKey("bond") ? storage.getBytesLength("bond") : 0;
    if (length) {
        if (length != 32) return false;
        bond.resize(32);
        if (storage.getBytes("bond", bond.data(), bond.size()) != bond.size()) return false;
    }
    proximity.begin(millis());
    inbox = xQueueCreate(40, sizeof(Fragment));
    if (!inbox) return false;
    NimBLEDevice::init(ssid.c_str());
    NimBLEServer *server = NimBLEDevice::createServer();
    server->setCallbacks(new Connections());
    NimBLEService *service = server->createService(SERVICE);
    auto *input = service->createCharacteristic(RX_UUID, NIMBLE_PROPERTY::WRITE);
    input->setCallbacks(new Receiver());
    output = service->createCharacteristic(TX_UUID, NIMBLE_PROPERTY::READ);
    page(0);
    service->start();
    auto *advertising = NimBLEDevice::getAdvertising();
    advertising->addServiceUUID(SERVICE);
    advertising->setScanResponse(true);
    advertising->start();
    return true;
}

void pollPairing() {
    if (!inbox) return;
    if (disconnected) {
        disconnected = false;
        xQueueReset(inbox);
        clearSession();
        proximity.reset();
        NimBLEDevice::startAdvertising();
    }
    uint32_t now = millis();
    if (uint32_t(now - lastSample) >= ProximityGate::SAMPLE_MS) {
        lastSample = now;
        auto *server = NimBLEDevice::getServer();
        int8_t rssi = 127;
        if (server->getConnectedCount() == 1) {
            uint16_t handle = server->getPeerInfo(size_t(0)).getConnHandle();
            rssiStatus = ble_gap_conn_rssi(handle, &rssi);
            lastRssi = rssi;
            if (rssiStatus == 0) proximity.sample(handle, rssi, now);
            else proximity.reset();
        } else {
            proximity.reset();
        }
    }
    if (enrollmentPending) {
        if (uint32_t(now - lastProximityLog) >= 1000) {
            lastProximityLog = now;
            Serial.printf("Pairing proximity: RSSI=%d dBm read_status=%d cutoff=%d near=%u\n",
                          lastRssi, rssiStatus, ProximityGate::MIN_RSSI, unsigned(proximity.near(now)));
        }
        if (!proximity.open(now) || uint32_t(now - enrollmentStart) > 15000) {
            enrollmentPending = false;
            fail(proximity.open(now) ? "Hold badge against camera; retry" : "Restart camera to pair nearby");
        } else if (proximity.near(now)) {
            enrollmentPending = false;
            enrollmentToken = hex(randomBytes(32));
            reply(5, bytes(enrollmentToken));
        }
    }
    while (Serial.available()) {
        char c = Serial.read();
        if (c == '\n' || c == '\r') {
            if (serialOverflow) {
                Serial.println("Serial command too long");
            } else if (serialCommand == "UNPAIR") {
                if (!storage.clear()) { Serial.println("Cannot clear pairing"); return; }
                Serial.println("Pairing cleared; restarting. SD photos are unchanged.");
                Serial.flush();
                ESP.restart();
            } else if (serialCommand.startsWith("RPC ")) {
                if (NimBLEDevice::getServer()->getConnectedCount()) {
                    Serial.println("Serial RPC unavailable during BLE connection");
                } else {
                    Bytes command;
                    String text = serialCommand.substring(4);
                    bool valid = text.length() > 0 && text.length() % 2 == 0;
                    for (size_t i = 0; valid && i < text.length(); i += 2) {
                        char pair[3] = {text[i], text[i + 1], 0};
                        char *end;
                        long value = strtol(pair, &end, 16);
                        valid = end == pair + 2 && isxdigit(pair[0]) && isxdigit(pair[1]);
                        command.push_back(uint8_t(value));
                    }
                    if (valid) process(command);
                    else fail("Invalid serial RPC");
                    Serial.printf("RPC %s\n", hex(outgoing).c_str());
                }
            }
            serialCommand = "";
            serialOverflow = false;
        } else if (serialCommand.length() < 1028) {
            serialCommand += c;
        } else {
            serialOverflow = true;
        }
    }
    Fragment fragment;
    if (xQueueReceive(inbox, &fragment, 0) != pdTRUE) return;
    const uint8_t *p = fragment.data;
    if (fragment.size == 3 && p[0] == 255) {
        page((size_t(p[1]) << 8) | p[2]);
        return;
    }
    if (fragment.size < 5) { fail("Invalid BLE fragment"); return; }
    size_t offset = (size_t(p[0]) << 8) | p[1];
    size_t total = (size_t(p[2]) << 8) | p[3];
    if (offset == 0) {
        incoming.clear();
        outgoing.clear();
        expected = total;
        page(0);
    }
    if (total < 1 || total > 512 || total != expected || offset != incoming.size() ||
        offset + fragment.size - 4 > total) { fail("Invalid BLE sequence"); return; }
    incoming.insert(incoming.end(), p + 4, p + fragment.size);
    if (incoming.size() == expected) {
        Bytes command = incoming;
        incoming.clear();
        process(command, true);
    }
}

bool cameraPairingOpen() { return inbox && bond.empty() && proximity.open(millis()); }
String cameraIdentity() { return identity; }
String cameraSSID() { return ssid; }
String cameraPassword() { return password; }
