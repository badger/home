# Motion detectors for Taste Stamp: flip, karate chop and shake.
#
# badge.imu() units are undocumented, and the Badge Simulator reports gravity
# with the opposite y sign to the hardware, so nothing here trusts a fixed
# axis or scale:
#
# - Flips come from badge.upside_down(), which the firmware already debounces
#   for its own display rotation.
# - Chops compare the size of the acceleration with a running estimate of
#   gravity, so any direction works.
# - Shakes count direction reversals of the acceleration around its slow
#   average, so turning the badge over once never counts as shaking.
#
# Times are integer milliseconds from badge.ticks, thresholds are integer
# percentages of gravity, and smoothing uses exp(-dt / tau), so behaviour
# does not depend on the frame rate.

import math


def magnitude(x, y, z):
    return math.sqrt(x * x + y * y + z * z)


def blend(dt, tau):
    # Fraction of the remaining gap an exponential average closes in dt ms.
    if dt <= 0:
        return 0.0
    return 1.0 - math.exp(-dt / tau)


class FlipDetector:
    # Reports each change of orientation, in either direction, once it has
    # held for SETTLE_MS.

    SETTLE_MS = 120
    COOLDOWN_MS = 600

    def __init__(self, upside_down=False):
        self.state = bool(upside_down)
        self.pending_since = None
        self.last_flip = None

    def update(self, upside_down, now):
        upside_down = bool(upside_down)
        if upside_down == self.state:
            self.pending_since = None
            return False
        if self.pending_since is None:
            self.pending_since = now
        if now - self.pending_since < self.SETTLE_MS:
            return False
        self.state = upside_down
        self.pending_since = None
        if self.last_flip is not None and now - self.last_flip < self.COOLDOWN_MS:
            return False
        self.last_flip = now
        return True


class ChopDetector:
    # A karate chop is a hard spike in the size of the acceleration, or a
    # smaller spike while the gyro shows a fast swing. After firing it waits
    # for QUIET_MS of calm before it can fire again.

    FIRE_PCT = 90
    SPIN_FIRE_PCT = 60
    SPIN = 12000
    CALM_PCT = 15
    QUIET_PCT = 30
    QUIET_MS = 120
    COOLDOWN_MS = 650
    GRAVITY_TAU = 500.0
    DRIFT_TAU = 4000.0
    SPIN_TAU = 150.0

    def __init__(self):
        self.gravity = 0.0
        self.spin = 0.0
        self.jolt = 0
        # Start disarmed so the first reading can't fire before a baseline.
        self.armed = False
        self.quiet_since = None
        self.last_chop = None

    def update(self, imu, dt, now):
        mag = magnitude(imu[0], imu[1], imu[2])
        if mag <= 0.0:
            return False
        if self.gravity <= 0.0:
            self.gravity = mag
        jolt = int(abs(mag - self.gravity) * 100.0 / self.gravity)
        self.jolt = jolt
        # Learn gravity quickly while calm and slowly otherwise, so a bad
        # first reading still converges but a chop barely moves it.
        tau = self.GRAVITY_TAU if jolt < self.CALM_PCT else self.DRIFT_TAU
        self.gravity += (mag - self.gravity) * blend(dt, tau)
        spin = magnitude(imu[3], imu[4], imu[5])
        self.spin = max(spin, self.spin * (1.0 - blend(dt, self.SPIN_TAU)))
        if not self.armed:
            if jolt < self.QUIET_PCT:
                if self.quiet_since is None:
                    self.quiet_since = now
                if now - self.quiet_since >= self.QUIET_MS:
                    self.armed = True
            else:
                self.quiet_since = None
            return False
        if jolt >= self.FIRE_PCT or (jolt >= self.SPIN_FIRE_PCT and self.spin >= self.SPIN):
            self.armed = False
            self.quiet_since = None
            if self.last_chop is None or now - self.last_chop >= self.COOLDOWN_MS:
                self.last_chop = now
                return True
        return False


class ShakeDetector:
    # Shaking swings the acceleration back and forth around its slow
    # average. A swing past STRONG_PCT of gravity that points away from the
    # previous swing is a reversal. REVERSALS of them within WINDOW_MS start a
    # shake, which ends once no reversal has come for HOLD_MS.

    SLOW_TAU = 250.0
    STRONG_PCT = 35
    OPPOSITE = -0.3
    REVERSALS = 2
    WINDOW_MS = 800
    HOLD_MS = 450

    def __init__(self):
        self.slow = None
        self.direction = None
        self.times = []
        self.shaking = False
        self.reversed = False

    def update(self, imu, dt, now):
        ax = imu[0]
        ay = imu[1]
        az = imu[2]
        self.reversed = False
        slow = self.slow
        if slow is None:
            if magnitude(ax, ay, az) > 0.0:
                self.slow = [ax, ay, az]
            return False
        dx = ax - slow[0]
        dy = ay - slow[1]
        dz = az - slow[2]
        ref = magnitude(slow[0], slow[1], slow[2])
        k = blend(dt, self.SLOW_TAU)
        slow[0] += dx * k
        slow[1] += dy * k
        slow[2] += dz * k
        dev = magnitude(dx, dy, dz)
        if ref > 0.0 and dev * 100.0 >= self.STRONG_PCT * ref:
            ux = dx / dev
            uy = dy / dev
            uz = dz / dev
            last = self.direction
            if last is not None and ux * last[0] + uy * last[1] + uz * last[2] < self.OPPOSITE:
                self.times.append(now)
                self.reversed = True
            self.direction = (ux, uy, uz)
        times = self.times
        while times and now - times[0] > self.WINDOW_MS:
            times.pop(0)
        if self.shaking:
            if not times or now - times[-1] > self.HOLD_MS:
                self.shaking = False
                # Forget this shake's reversals, or the ones still inside
                # WINDOW_MS would start it again on the next frame.
                self.times = []
        elif len(times) >= self.REVERSALS:
            self.shaking = True
        return self.shaking
