#include "../src/flash_led.h"
#include "../src/proximity.h"

#include <assert.h>
#include <vector>

static bool setupFails = false, attached = false;
static std::vector<uint32_t> writes;

void pinMode(uint8_t pin, uint8_t mode) {
    assert(pin == 4 && mode == OUTPUT);
}
void digitalWrite(uint8_t pin, uint8_t value) {
    assert(pin == 4 && value == LOW);
}
double ledcSetup(uint8_t channel, double frequency, uint8_t resolution) {
    assert(channel == 2 && frequency == 4000 && resolution == 10);
    return setupFails ? 0 : frequency;
}
void ledcAttachPin(uint8_t pin, uint8_t channel) {
    assert(pin == 4 && channel == 2);
    attached = true;
}
void ledcWrite(uint8_t channel, uint32_t duty) {
    assert(channel == 2 && duty <= 1023);
    writes.push_back(duty);
}

int main() {
    FlashLed led;
    assert(led.begin() && attached);
    assert(writes.back() == 0);
    led.update(true, 0);
    assert(writes.back() == 8);
    size_t count = writes.size();
    led.update(true, 99);
    assert(writes.size() == count);
    led.update(true, 100);
    assert(writes.back() == 0);
    led.update(true, 1999);
    assert(writes.back() == 0);
    led.update(true, 2000);
    assert(writes.back() == 8);
    led.update(false, 2050);
    assert(writes.back() == 0); // Pairing stops a pulse immediately.

    led.capture(true);
    assert(writes.back() == 1023);
    led.update(true, 4000);
    led.update(false, 4100);
    assert(writes.back() == 1023); // Capture always overrides the indicator.
    led.capture(false);
    assert(writes.back() == 0); // Off before SD writes, including failed captures.
    led.update(false, 6000);
    assert(writes.back() == 0);

    ProximityGate gate;
    gate.begin(0);
    led.update(gate.open(178000), 178000);
    assert(writes.back() == 8);
    led.update(gate.open(180000), 180000);
    assert(writes.back() == 0); // No blink at the end of the three-minute window.
    count = writes.size();
    for (uint32_t now = 180000; now < 184000; now++) led.update(false, now);
    assert(writes.size() == count); // Paired/expired idle cannot drive the LED.

    setupFails = true;
    attached = false;
    FlashLed failed;
    assert(!failed.begin() && !attached);
    failed.update(true, 0);
    failed.capture(true);
    assert(writes.size() == count);
}
