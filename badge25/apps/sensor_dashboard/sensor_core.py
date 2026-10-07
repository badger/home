import math


def crc8(data):
    value = 0xFF
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = ((value << 1) ^ 0x31) & 0xFF if value & 0x80 else (value << 1) & 0xFF
    return value


def decode_words(data, count):
    if len(data) != count * 3:
        raise ValueError("Short sensor response")
    words = []
    for offset in range(0, len(data), 3):
        if crc8(data[offset:offset + 2]) != data[offset + 2]:
            raise ValueError("Sensor CRC failed")
        words.append((data[offset] << 8) | data[offset + 1])
    return words


def encode_word(value):
    data = bytes((value >> 8, value & 0xFF))
    return data + bytes((crc8(data),))


def sht_reading(data):
    temperature, humidity = decode_words(data, 2)
    return -45 + 175 * temperature / 65535, max(0, min(100, -6 + 125 * humidity / 65535))


def compensation(temperature, humidity):
    rh = round(max(0, min(100, humidity)) * 65535 / 100)
    temp = round((max(-45, min(130, temperature)) + 45) * 65535 / 175)
    return encode_word(rh) + encode_word(temp)


def fahrenheit(celsius):
    return celsius * 9 / 5 + 32


def dew_point(temperature, humidity):
    if humidity <= 0:
        return None
    gamma = math.log(humidity / 100) + 17.62 * temperature / (243.12 + temperature)
    return 243.12 * gamma / (17.62 - gamma)


class SensorDashboard:
    SHT_ADDRESS = 0x44
    SGP_ADDRESS = 0x59
    SAMPLE_MS = 1000
    CONDITION_MS = 9000

    def __init__(self, bus, now, ticks_diff, ticks_add, indexes=None):
        self.bus = bus
        self.diff = ticks_diff
        self.add = ticks_add
        self.indexes = indexes
        self.next_sample = now
        self.deadline = now
        self.phase = "idle"
        self.condition_started = None
        self.conditioned = False
        self.conditioning_expired = False
        self.temperature = None
        self.humidity = None
        self.voc = None
        self.nox = None
        self.sht_status = "Starting"
        self.sgp_status = "Starting"
        addresses = bus.scan()
        self.has_sht = self.SHT_ADDRESS in addresses
        self.has_sgp = self.SGP_ADDRESS in addresses
        if not self.has_sht:
            self.sht_status = "Missing 0x44"
        if not self.has_sgp:
            self.sgp_status = "Missing 0x59"

    def _error(self, sensor, error):
        status = "I2C error"
        if isinstance(error, ValueError):
            status = "CRC error" if "CRC" in str(error) else "Data error"
        print("Sensor dashboard: %s: %s" % (sensor, error))
        if self.indexes is not None:
            self.indexes.reset()
        if sensor == "SHT41":
            self.temperature = None
            self.humidity = None
            self.sht_status = status
        else:
            self.voc = None
            self.nox = None
            self.sgp_status = status

    def _write_gas(self, data):
        if self.bus.writeto(self.SGP_ADDRESS, data) != len(data):
            raise OSError("Short SGP41 command write")

    def _gas_command(self, now):
        if not self.has_sgp:
            self.phase = "idle"
            return
        if self.temperature is None:
            self.voc = None
            self.nox = None
            self.sgp_status = "Needs SHT41"
            self.close()
            self.phase = "idle"
            return
        if self.condition_started is None:
            self.condition_started = now
        age = self.diff(now, self.condition_started)
        if not self.conditioned and age >= self.CONDITION_MS:
            self.conditioning_expired = True
        conditioning = not self.conditioned and not self.conditioning_expired
        command = b"\x26\x12" if conditioning else b"\x26\x19"
        arguments = b"\x80\x00\xa2\x66\x66\x93" if conditioning else compensation(
            self.temperature, self.humidity
        )
        try:
            self._write_gas(command + arguments)
        except OSError as error:
            self._error("SGP41", error)
            self.phase = "idle"
            if not conditioning and not self.conditioned:
                self.close()
            return
        if not conditioning:
            self.conditioned = True
        self.phase = "conditioning" if conditioning else "gas"
        self.sgp_status = "Conditioning" if conditioning else "Measuring"
        self.deadline = self.add(now, 50)

    def update(self, now):
        # Latch the cutoff across errors and tick wrap until transition or shutdown succeeds.
        if not self.conditioned and self.condition_started is not None:
            if self.conditioning_expired or self.diff(now, self.condition_started) >= self.CONDITION_MS:
                self.conditioning_expired = True
                if self.temperature is not None:
                    self._gas_command(now)
                    return
                if not self.close() and self.phase == "idle":
                    self.next_sample = now
        if self.phase == "idle":
            if self.diff(now, self.next_sample) < 0:
                return
            self.next_sample = self.add(self.next_sample, self.SAMPLE_MS)
            if self.diff(now, self.next_sample) >= 0:
                self.next_sample = self.add(now, self.SAMPLE_MS)
            if not self.has_sht:
                self.sgp_status = "Needs SHT41" if self.has_sgp else self.sgp_status
                return
            try:
                self.bus.writeto(self.SHT_ADDRESS, b"\xfd")
            except OSError as error:
                self._error("SHT41", error)
                self._gas_command(now)
                return
            self.phase = "sht"
            self.deadline = self.add(now, 10)
            return
        if self.diff(now, self.deadline) < 0:
            return
        if self.phase == "sht":
            try:
                self.temperature, self.humidity = sht_reading(
                    self.bus.readfrom(self.SHT_ADDRESS, 6)
                )
                self.sht_status = "OK"
            except (OSError, ValueError) as error:
                self._error("SHT41", error)
            self._gas_command(now)
        else:
            conditioning = self.phase == "conditioning"
            try:
                values = decode_words(
                    self.bus.readfrom(self.SGP_ADDRESS, 3 if conditioning else 6),
                    1 if conditioning else 2,
                )
                self.voc = values[0]
                self.nox = None if conditioning else values[1]
                self.sgp_status = "Conditioning" if conditioning else "OK"
                if not conditioning and self.indexes is not None:
                    self.indexes.process(self.voc, self.nox, now)
            except (OSError, ValueError) as error:
                self._error("SGP41", error)
            self.phase = "idle"

    def close(self):
        if self.has_sgp:
            try:
                self._write_gas(b"\x36\x15")
            except OSError as error:
                self._error("SGP41", error)
                return False
        self.condition_started = None
        self.conditioned = False
        self.conditioning_expired = False
        return True
