"""Optional motion and white case-light feedback using firmware APIs only."""

import math

from clock import elapsed


class Feedback:
    def __init__(self, badge):
        self.badge = badge
        self.motion = callable(getattr(badge, "imu", None))
        self.lights = callable(getattr(badge, "caselights", None))
        self.previous = None
        self.gravity = None
        self.last_motion = None
        self.last_wake = None
        self.last_light = None
        self.saved_lights = None
        self.note = ""
        if self.lights:
            try:
                self.saved_lights = badge.caselights()
            except (OSError, ValueError) as exc:
                self._disable("lights", exc)
        if not self.motion:
            self.note = "Shake is unavailable on this runtime"

    def _disable(self, feature, exc):
        if feature == "lights":
            self.lights = False
        else:
            self.motion = False
        self.note = feature + " unavailable: " + str(exc)
        print("Solar Buddy: " + self.note)

    def update(self, app, now):
        if self.motion and (self.last_motion is None or elapsed(now, self.last_motion) >= 80):
            self.last_motion = now
            try:
                values = self.badge.imu()
                if len(values) != 6:
                    raise ValueError("Expected six IMU values")
                current = tuple(float(value) for value in values[:3])
                if not all(math.isfinite(value) for value in current):
                    raise ValueError("Invalid IMU sample")
                magnitude = math.sqrt(sum(value * value for value in current))
                if self.gravity is None and magnitude > 0:
                    self.gravity = magnitude
                if self.previous is not None and self.gravity:
                    delta = math.sqrt(sum((a - b) ** 2 for a, b in zip(current, self.previous)))
                    if (delta > self.gravity * 1.2 and
                            (self.last_wake is None or elapsed(now, self.last_wake) > 2000)):
                        app.wake(now)
                        self.last_wake = now
                    self.gravity = self.gravity * 0.98 + magnitude * 0.02
                self.previous = current
            except (OSError, ValueError, TypeError) as exc:
                self._disable("motion", exc)
        if self.lights:
            age = elapsed(now, app.celebration) if app.celebration is not None else -1
            brightness = 0.35 if 0 <= age < 1250 and (age // 250) % 2 == 0 else 0
            if brightness != self.last_light:
                try:
                    self.badge.caselights(brightness)
                    self.last_light = brightness
                except (OSError, ValueError) as exc:
                    self._disable("lights", exc)
        if self.note:
            app.hardware_note = self.note

    def close(self):
        if self.lights and self.saved_lights is not None:
            self.badge.caselights(*self.saved_lights)
