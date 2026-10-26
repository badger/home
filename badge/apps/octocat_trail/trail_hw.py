"""Guarded hardware adapters for The Octocat Trail.

Every sensor, light and IR call is wrapped so the app degrades instead of
crashing in the Badge Simulator, which has no IR, a static IMU and a
constant light sensor. Nothing here touches the display.
"""

LIGHT_ADC_PIN = 43


class Sensors:
    """IMU and ambient light, with fallbacks for missing hardware."""

    def __init__(self, device):
        self.device = device
        self.imu_ok = True
        self.light_source = None
        self.adc = None
        self.light_failed = False

    def imu(self):
        """(ax, ay, az) or None when there is no IMU."""
        if not self.imu_ok:
            return None
        try:
            values = self.device.imu()
            return (float(values[0]), float(values[1]), float(values[2]))
        except Exception:
            self.imu_ok = False
            return None

    def light(self):
        """Raw 16-bit ambient light from GPIO43/ADC3, or None."""
        if self.light_failed:
            return None
        if self.light_source != "adc":
            try:
                value = int(self.device.light_level())
                self.light_source = "badge"
                return value
            except Exception:
                if self.light_source == "badge":
                    return None
        try:
            if self.adc is None:
                import machine
                self.adc = machine.ADC(LIGHT_ADC_PIN)
            value = int(self.adc.read_u16())
            self.light_source = "adc"
            return value
        except Exception:
            self.light_failed = True
            return None
