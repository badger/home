#pragma once

#include <Arduino.h>

class FlashLed {
public:
    static constexpr uint8_t PIN = 4;
    // Channel 2 uses timer 1, separate from the camera's channel 0 / timer 0 XCLK.
    static constexpr uint8_t CHANNEL = 2;
    static constexpr uint32_t FULL_DUTY = 1023;
    static constexpr uint32_t DIM_DUTY = 8;
    static constexpr uint32_t PERIOD_MS = 2000;
    static constexpr uint32_t PULSE_MS = 100;

    bool begin() {
        pinMode(PIN, OUTPUT);
        digitalWrite(PIN, LOW);
        if (ledcSetup(CHANNEL, 4000, 10) == 0) return false;
        ledcAttachPin(PIN, CHANNEL);
        ready = true;
        write(0);
        return true;
    }

    void capture(bool active) {
        capturing = active;
        write(active ? FULL_DUTY : 0);
    }

    void update(bool pairingOpen, uint32_t now) {
        write(capturing ? FULL_DUTY :
              pairingOpen && now % PERIOD_MS < PULSE_MS ? DIM_DUTY : 0);
    }

private:
    bool ready = false, capturing = false;
    uint32_t current = UINT32_MAX;

    void write(uint32_t duty) {
        if (ready && duty != current) {
            ledcWrite(CHANNEL, duty);
            current = duty;
        }
    }
};
