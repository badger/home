#pragma once

#include <stdint.h>

class ProximityGate {
public:
    static constexpr uint32_t WINDOW_MS = 180000;
    static constexpr uint32_t SAMPLE_MS = 200;
    static constexpr int MIN_RSSI = -70;

    void begin(uint32_t now) { started = now; reset(); }
    void reset() { count = next = 0; peer = UINT16_MAX; }
    bool open(uint32_t now) const { return uint32_t(now - started) < WINDOW_MS; }
    void sample(uint16_t handle, int rssi, uint32_t now) {
        if (handle != peer || uint32_t(now - last) > 600) count = next = 0;
        peer = handle;
        if (rssi <= -127 || rssi >= 0 || handle == UINT16_MAX) {
            count = next = 0;
            last = now;
        } else if (!count || uint32_t(now - last) >= SAMPLE_MS) {
            readings[next] = rssi;
            next = (next + 1) % 5;
            if (count < 5) count++;
            last = now;
        }
    }
    bool near(uint32_t now) const {
        if (!open(now) || count < 3 || uint32_t(now - last) > 600) return false;
        int sorted[5];
        for (uint8_t i = 0; i < count; i++) {
            sorted[i] = readings[i];
            for (uint8_t j = i; j > 0 && sorted[j] < sorted[j - 1]; j--) {
                int value = sorted[j];
                sorted[j] = sorted[j - 1];
                sorted[j - 1] = value;
            }
        }
        return sorted[(count - 1) / 2] >= MIN_RSSI;
    }

private:
    uint32_t started = 0, last = 0;
    uint16_t peer = UINT16_MAX;
    uint8_t count = 0, next = 0;
    int readings[5] = {};
};
