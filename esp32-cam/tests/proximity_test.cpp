#include "../src/proximity.h"

#include <assert.h>
#include <initializer_list>

static void three(ProximityGate &gate, int rssi, uint32_t start = 200, uint16_t peer = 1) {
    gate.sample(peer, rssi, start);
    gate.sample(peer, rssi, start + 200);
    gate.sample(peer, rssi, start + 400);
}

int main() {
    ProximityGate gate;
    gate.begin(0);
    assert(!gate.near(0));
    gate.sample(1, -70, 200);
    gate.sample(1, -70, 400);
    assert(!gate.near(400));
    gate.sample(1, -70, 600);
    assert(gate.near(600));
    assert(gate.near(1200));
    assert(!gate.near(1201));

    gate.begin(0);
    three(gate, -71);
    assert(!gate.near(600));
    gate.begin(0);
    three(gate, -58);
    gate.sample(1, -75, 800);
    assert(gate.near(800)); // One low outlier must not abort a close handshake.
    gate.sample(1, -75, 1000);
    assert(gate.near(1000));
    gate.sample(1, -75, 1200);
    assert(!gate.near(1200)); // Sustained separation must still revoke admission.

    gate.begin(0);
    // Connected-peer readings observed on the physical ESP32-CAM and badge.
    uint32_t now = 0;
    for (int rssi : {-58, -50, -58, -52, -51, -56, -54, -56, -55, -56, -50, -57, -55, -53, -53}) {
        now += 200;
        gate.sample(1, rssi, now);
        if (now >= 600) assert(gate.near(now));
    }
    three(gate, -80, now + 200);
    assert(!gate.near(now + 600));

    gate.begin(0);
    three(gate, -68);
    assert(gate.near(600)); // The deliberately generous cutoff accepts nearby devices.

    gate.begin(0);
    three(gate, -30);
    gate.sample(2, -30, 800);
    assert(!gate.near(800)); // A different peer cannot inherit the samples.
    gate.sample(2, -30, 1000);
    gate.sample(2, -30, 1200);
    assert(gate.near(1200));
    gate.reset();
    assert(!gate.near(1200));

    gate.begin(0);
    gate.sample(1, -20, 200);
    gate.sample(1, -20, 210);
    gate.sample(1, -20, 220);
    assert(!gate.near(220));
    gate.sample(1, -20, 400);
    gate.sample(1, -20, 600);
    assert(gate.near(600));

    for (int invalid : {0, 127, -127}) {
        gate.begin(0);
        three(gate, -30);
        gate.sample(1, invalid, 800);
        assert(!gate.near(800));
    }
    gate.begin(0);
    three(gate, -30);
    gate.sample(UINT16_MAX, -30, 800);
    assert(!gate.near(800));

    gate.begin(0);
    gate.sample(1, -30, 200);
    gate.sample(1, -30, 400);
    gate.sample(1, -30, 1001);
    assert(!gate.near(1001)); // Stale readings cannot establish proximity.
    gate.sample(1, -30, 1201);
    gate.sample(1, -30, 1401);
    assert(gate.near(1401));

    gate.begin(0);
    three(gate, -30, 179400);
    assert(gate.near(179999));
    assert(!gate.near(180000));
    gate.reset();
    assert(!gate.open(180001)); // Disconnect does not reopen enrollment.

    gate.begin(UINT32_MAX - 300);
    gate.sample(1, -30, UINT32_MAX - 100);
    gate.sample(1, -30, 99);
    gate.sample(1, -30, 299);
    assert(gate.near(299)); // millis() rollover remains bounded.
}
