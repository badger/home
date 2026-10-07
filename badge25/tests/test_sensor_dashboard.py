import importlib.util
import math
import struct
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


APP = Path(__file__).resolve().parents[1] / "apps" / "sensor_dashboard"
sys.path.insert(0, str(APP))
from sensor_core import (
    SensorDashboard, compensation, crc8, decode_words, dew_point,
    encode_word, fahrenheit, sht_reading,
)
from gas_indexes import GasIndexes, index_caption


def ticks_diff(a, b):
    return (a - b + 32768) % 65536 - 32768


def ticks_add(a, b):
    return (a + b) % 65536


class FakeBus:
    def __init__(self, addresses=(0x44, 0x59)):
        self.addresses = addresses
        self.writes = []
        self.responses = []
        self.failure = None
        self.write_attempts = []
        self.write_failures = {}
        self.short_writes = {}

    def scan(self):
        return self.addresses

    def writeto(self, address, data):
        self.write_attempts.append((address, data))
        if self.failure:
            raise self.failure
        command = (address, data[:2])
        if self.write_failures.get(command, 0):
            self.write_failures[command] -= 1
            raise OSError("Injected command failure")
        if self.short_writes.get(command, 0):
            self.short_writes[command] -= 1
            return len(data) - 1
        self.writes.append((address, data))
        return len(data)

    def readfrom(self, address, size):
        if self.failure:
            raise self.failure
        return self.responses.pop(0)


def sht_response(temperature=25, humidity=50):
    return encode_word(round((temperature + 45) * 65535 / 175)) + encode_word(
        round((humidity + 6) * 65535 / 125)
    )


class SensorTests(unittest.TestCase):
    def conditioning_dashboard(self, now=0):
        bus = FakeBus()
        model = SensorDashboard(bus, now, ticks_diff, ticks_add)
        model.temperature, model.humidity = 25, 50
        model.next_sample = ticks_add(now, 20000)
        model._gas_command(now)
        return bus, model

    def test_crc_and_word_encoding(self):
        self.assertEqual(crc8(b"\xbe\xef"), 0x92)
        self.assertEqual(encode_word(0x8000), b"\x80\x00\xa2")
        self.assertEqual(encode_word(0x6666), b"\x66\x66\x93")
        self.assertEqual(decode_words(encode_word(12345), 1), [12345])
        with self.assertRaisesRegex(ValueError, "CRC"):
            decode_words(b"\xbe\xef\x00", 1)
        with self.assertRaisesRegex(ValueError, "Short"):
            decode_words(b"\xbe", 1)

    def test_sht_units_and_dew_point(self):
        temperature, humidity = sht_reading(sht_response())
        self.assertAlmostEqual(temperature, 25, places=2)
        self.assertAlmostEqual(humidity, 50, places=2)
        self.assertEqual(fahrenheit(0), 32)
        self.assertEqual(fahrenheit(100), 212)
        self.assertAlmostEqual(dew_point(25, 50), 13.85, places=2)
        self.assertAlmostEqual(dew_point(25, 100), 25, places=5)
        self.assertIsNone(dew_point(25, 0))
        self.assertTrue(math.isfinite(dew_point(-20, 30)))

    def test_humidity_clamping(self):
        self.assertEqual(sht_reading(encode_word(0) + encode_word(0))[1], 0)
        self.assertEqual(sht_reading(encode_word(65535) + encode_word(65535))[1], 100)
        self.assertEqual(decode_words(compensation(25, 50), 2), [32768, 26214])

    def test_nonblocking_waits_conditioning_and_compensation(self):
        bus = FakeBus()
        model = SensorDashboard(bus, 0, ticks_diff, ticks_add)
        bus.responses = [sht_response(), encode_word(22000)]
        model.update(0)
        self.assertEqual(bus.writes, [(0x44, b"\xfd")])
        model.update(9)
        self.assertIsNone(model.temperature)
        model.update(10)
        self.assertEqual(bus.writes[-1], (0x59, b"\x26\x12\x80\x00\xa2\x66\x66\x93"))
        model.update(59)
        self.assertIsNone(model.voc)
        model.update(60)
        self.assertEqual(model.voc, 22000)
        self.assertIsNone(model.nox)
        self.assertEqual(model.sgp_status, "Conditioning")
        model.update(9010)
        self.assertEqual(bus.writes[-1][1][:2], b"\x26\x19")
        self.assertEqual(
            bus.writes[-1][1][2:], compensation(model.temperature, model.humidity)
        )
        bus.responses = [encode_word(21000) + encode_word(17000)]
        model.update(9060)
        self.assertEqual(model.voc, 21000)
        self.assertEqual(model.nox, 17000)
        self.assertEqual(model.sgp_status, "OK")

    def test_conditioning_cutoff_even_with_pending_conversion(self):
        bus = FakeBus()
        model = SensorDashboard(bus, 0, ticks_diff, ticks_add)
        bus.responses = [sht_response()]
        model.update(0)
        model.update(10)
        model.update(9010)
        self.assertEqual(bus.writes[-1][1][:2], b"\x26\x19")

    def test_missing_sensor_does_not_produce_fake_values(self):
        model = SensorDashboard(FakeBus(()), 0, ticks_diff, ticks_add)
        model.update(0)
        self.assertEqual(model.sht_status, "Missing 0x44")
        self.assertEqual(model.sgp_status, "Missing 0x59")
        self.assertIsNone(model.temperature)
        self.assertIsNone(model.voc)

    def test_missing_sht_blocks_gas(self):
        bus = FakeBus((0x59,))
        model = SensorDashboard(bus, 0, ticks_diff, ticks_add)
        model.update(0)
        self.assertEqual(model.sgp_status, "Needs SHT41")
        self.assertFalse(bus.writes)

    def test_crc_failure_clears_values_and_stops_heater(self):
        bus = FakeBus()
        model = SensorDashboard(bus, 0, ticks_diff, ticks_add)
        model.temperature, model.humidity = 25, 50
        model.voc, model.nox = 22000, 18000
        bus.responses = [b"\x00" * 6]
        model.update(0)
        with patch("builtins.print"):
            model.update(10)
        self.assertIsNone(model.temperature)
        self.assertIsNone(model.humidity)
        self.assertIsNone(model.voc)
        self.assertIsNone(model.nox)
        self.assertEqual(model.sht_status, "CRC error")
        self.assertEqual(bus.writes[-1], (0x59, b"\x36\x15"))

    def test_i2c_failure_is_visible(self):
        bus = FakeBus()
        bus.failure = OSError("No response")
        model = SensorDashboard(bus, 0, ticks_diff, ticks_add)
        with patch("builtins.print"):
            model.update(0)
        self.assertEqual(model.sht_status, "I2C error")
        self.assertIsNone(model.temperature)

    def test_clock_wraparound_and_close(self):
        bus = FakeBus()
        model = SensorDashboard(bus, 65530, ticks_diff, ticks_add)
        bus.responses = [sht_response()]
        model.update(65530)
        model.update(3)
        self.assertIsNone(model.temperature)
        model.update(4)
        self.assertIsNotNone(model.temperature)
        model.close()
        self.assertEqual(bus.writes[-1], (0x59, b"\x36\x15"))

    def test_completed_conditioning_does_not_restart_after_timer_half_wrap(self):
        bus = FakeBus()
        model = SensorDashboard(bus, 0, ticks_diff, ticks_add)
        model.temperature, model.humidity = 25, 50
        model.condition_started = 0
        model._gas_command(9000)
        self.assertTrue(model.conditioned)
        model._gas_command(40000)
        self.assertEqual(bus.writes[-1][1][:2], b"\x26\x19")
        model.close()
        self.assertFalse(model.conditioned)

    def test_failed_transition_and_shutdown_retry_before_next_sample(self):
        bus, model = self.conditioning_dashboard()
        bus.write_failures[(0x59, b"\x26\x19")] = 1
        bus.write_failures[(0x59, b"\x36\x15")] = 1
        with patch("builtins.print") as logged:
            model.update(9000)
        self.assertTrue(logged.called)
        self.assertFalse(model.conditioned)
        self.assertEqual(model.condition_started, 0)
        self.assertEqual(model.phase, "idle")
        self.assertEqual(
            [data[:2] for _, data in bus.write_attempts[-2:]],
            [b"\x26\x19", b"\x36\x15"],
        )
        self.assertLess(ticks_diff(9010, model.next_sample), 0)
        model.update(9010)
        self.assertEqual(bus.writes[-1][1][:2], b"\x26\x19")
        self.assertTrue(model.conditioned)
        self.assertLess(ticks_diff(9010, model.condition_started), 10000)

    def test_failed_transition_can_stop_heater_instead(self):
        bus, model = self.conditioning_dashboard()
        bus.write_failures[(0x59, b"\x26\x19")] = 1
        with patch("builtins.print"):
            model.update(9000)
        self.assertEqual(bus.writes[-1], (0x59, b"\x36\x15"))
        self.assertIsNone(model.condition_started)
        self.assertFalse(model.conditioned)
        self.assertEqual(model.sgp_status, "I2C error")

    def test_conditioning_read_error_does_not_disable_deadline(self):
        bus, model = self.conditioning_dashboard()
        bus.responses = [b"\x00" * 3]
        with patch("builtins.print"):
            model.update(50)
        self.assertEqual(model.sgp_status, "CRC error")
        self.assertEqual(model.phase, "idle")
        model.update(9000)
        self.assertEqual(bus.writes[-1][1][:2], b"\x26\x19")
        self.assertTrue(model.conditioned)

    def test_conditioning_write_error_keeps_the_original_deadline(self):
        bus, model = self.conditioning_dashboard()
        bus.write_failures[(0x59, b"\x26\x12")] = 1
        with patch("builtins.print"):
            model._gas_command(8000)
        self.assertEqual(model.condition_started, 0)
        self.assertEqual(model.sgp_status, "I2C error")
        self.assertEqual(model.phase, "idle")
        model.update(9000)
        self.assertEqual(bus.writes[-1][1][:2], b"\x26\x19")
        self.assertTrue(model.conditioned)

    def test_failed_shutdown_does_not_restart_window_after_sht_recovery(self):
        bus, model = self.conditioning_dashboard()
        bus.responses = [encode_word(22000)]
        model.update(50)
        model.next_sample = 3000
        bus.responses = [b"\x00" * 6]
        bus.write_failures[(0x59, b"\x36\x15")] = 1
        model.update(3000)
        with patch("builtins.print"):
            model.update(3010)
        self.assertEqual(model.sht_status, "CRC error")
        self.assertEqual(model.sgp_status, "I2C error")
        self.assertEqual(model.condition_started, 0)
        self.assertFalse(model.conditioned)
        bus.responses = [sht_response()]
        model.update(4000)
        model.update(4010)
        self.assertEqual(model.condition_started, 0)
        model.update(9000)
        self.assertEqual(bus.writes[-1][1][:2], b"\x26\x19")
        self.assertTrue(model.conditioned)

    def test_deadline_shutdown_retries_do_not_starve_sht_recovery(self):
        bus, model = self.conditioning_dashboard()
        bus.responses = [encode_word(22000)]
        model.update(50)
        model.next_sample = 8000
        bus.responses = [b"\x00" * 6]
        bus.write_failures[(0x59, b"\x36\x15")] = 3
        model.update(8000)
        with patch("builtins.print"):
            model.update(8010)
        self.assertIsNone(model.temperature)
        self.assertEqual(model.condition_started, 0)
        model.next_sample = 20000
        bus.responses = [sht_response()]
        with patch("builtins.print"):
            model.update(9000)
        self.assertEqual(model.phase, "sht")
        self.assertEqual(bus.writes[-1], (0x44, b"\xfd"))
        with patch("builtins.print"):
            model.update(9010)
        self.assertTrue(model.conditioned)
        self.assertEqual(model.condition_started, 0)
        self.assertEqual(bus.writes[-1][1][:2], b"\x26\x19")
        self.assertLess(ticks_diff(9010, model.condition_started), 10000)

    def test_failed_shutdown_preserves_window_across_tick_wrap(self):
        start = 65000
        bus, model = self.conditioning_dashboard(start)
        bus.write_failures[(0x59, b"\x36\x15")] = 1
        with patch("builtins.print"):
            self.assertFalse(model.close())
        self.assertEqual(model.condition_started, start)
        model._gas_command(ticks_add(start, 4000))
        self.assertEqual(model.condition_started, start)
        model.update(ticks_add(start, 9000))
        self.assertEqual(bus.writes[-1][1][:2], b"\x26\x19")
        self.assertTrue(model.conditioned)

    def test_short_transition_ack_does_not_complete_conditioning(self):
        bus, model = self.conditioning_dashboard()
        bus.short_writes[(0x59, b"\x26\x19")] = 1
        bus.write_failures[(0x59, b"\x36\x15")] = 1
        with patch("builtins.print"):
            model.update(9000)
        self.assertFalse(model.conditioned)
        self.assertEqual(model.condition_started, 0)
        self.assertEqual(model.sgp_status, "I2C error")
        model.update(9010)
        self.assertTrue(model.conditioned)
        self.assertEqual(bus.writes[-1][1][:2], b"\x26\x19")

    def test_short_shutdown_ack_keeps_conditioning_state(self):
        bus, model = self.conditioning_dashboard()
        bus.short_writes[(0x59, b"\x36\x15")] = 1
        with patch("builtins.print"):
            self.assertFalse(model.close())
        self.assertEqual(model.condition_started, 0)
        self.assertFalse(model.conditioned)
        self.assertTrue(model.close())
        self.assertIsNone(model.condition_started)

    def test_failed_shutdown_keeps_completed_latch(self):
        bus, model = self.conditioning_dashboard()
        model.update(9000)
        self.assertTrue(model.conditioned)
        bus.write_failures[(0x59, b"\x36\x15")] = 1
        with patch("builtins.print"):
            self.assertFalse(model.close())
        self.assertTrue(model.conditioned)
        self.assertEqual(model.condition_started, 0)
        model._gas_command(40000)
        self.assertEqual(bus.writes[-1][1][:2], b"\x26\x19")

    def test_conditioning_deadline_preempts_pending_sht_conversion(self):
        bus, model = self.conditioning_dashboard()
        model.phase = "sht"
        model.deadline = 9010
        model.update(9000)
        self.assertEqual(bus.writes[-1][1][:2], b"\x26\x19")
        self.assertTrue(model.conditioned)

    def test_successful_shutdown_allows_a_new_conditioning_window(self):
        bus, model = self.conditioning_dashboard()
        model.update(9000)
        self.assertTrue(model.conditioning_expired)
        self.assertTrue(model.close())
        self.assertIsNone(model.condition_started)
        self.assertFalse(model.conditioned)
        self.assertFalse(model.conditioning_expired)
        model._gas_command(13000)
        self.assertEqual(model.condition_started, 13000)
        self.assertEqual(bus.writes[-1][1][:2], b"\x26\x12")
        model.update(22000)
        self.assertEqual(bus.writes[-1][1][:2], b"\x26\x19")

    def test_failed_deadline_transition_does_not_restart_after_half_wrap(self):
        bus, model = self.conditioning_dashboard()
        bus.write_failures[(0x59, b"\x26\x19")] = 1
        bus.write_failures[(0x59, b"\x36\x15")] = 1
        with patch("builtins.print"):
            model.update(9000)
        self.assertFalse(model.conditioned)
        self.assertTrue(model.conditioning_expired)
        model.update(40000)
        self.assertEqual(bus.writes[-1][1][:2], b"\x26\x19")
        self.assertTrue(model.conditioned)


class Screen:
    width = 160
    height = 120

    def __init__(self):
        self.drawn = []
        self.clipped = []
        self.bounds = []

    def clear(self):
        self.drawn = []
        self.clipped = []
        self.bounds = []

    def measure_text(self, text):
        height = getattr(getattr(self, "font", None), "height", 8)
        return len(text) * (4 if height == 5 else 6), height

    def text(self, text, x, y):
        self.drawn.append((text, x, y))
        self.bounds.append((x, y, *self.measure_text(text)))

    def draw(self, shape):
        pass

    def window(self, x, y, width, height):
        parent = self

        class Window:
            def text(self, text, offset_x, offset_y):
                parent.clipped.append((text, offset_x, offset_y, x, y, width, height))

            def scale_blit(self, image, offset_x, offset_y, scaled_width, scaled_height):
                parent.clipped.append((image.drawn[-1][0], offset_x, offset_y, x, y, width, height))

        return Window()

    def scale_blit(self, image, x, y, width, height):
        self.drawn.append((image.drawn[-1][0], x, y))
        self.bounds.append((x, y, width, height))


class IndexTests(unittest.TestCase):
    def test_processing_cadence_warmup_and_gap_reset(self):
        native = SimpleNamespace(reset=lambda: None, process=lambda voc, nox: (0, 0))
        indexes = GasIndexes(native, ticks_diff)
        indexes.process(22000, 18000, 0)
        self.assertIsNone(indexes.voc)
        self.assertIsNone(indexes.nox)
        native.process = lambda voc, nox: (123, 4)
        indexes.process(22000, 18000, 1000)
        self.assertEqual((indexes.voc, indexes.nox), (123, 4))
        self.assertEqual(indexes.samples, 2)
        indexes.process(22000, 18000, 1100)
        self.assertEqual(indexes.samples, 2)
        with patch("builtins.print"):
            indexes.process(22000, 18000, 3000)
        self.assertEqual(indexes.samples, 1)

    def test_captions_compare_to_documented_baselines(self):
        self.assertEqual(index_caption(None, 100), "Warming up")
        self.assertEqual(index_caption(80, 100), "Below usual")
        self.assertEqual(index_caption(100, 100), "Usual")
        self.assertEqual(index_caption(140, 100), "Above usual")
        self.assertEqual(index_caption(1, 1), "Background")
        self.assertEqual(index_caption(2, 1), "Above usual")

class AppTests(unittest.TestCase):
    def load_app(self):
        self.screen = Screen()
        self.io = SimpleNamespace(BUTTON_A="A", BUTTON_C="C", pressed=set())
        self.bus = FakeBus()
        badgeware = ModuleType("badgeware")
        badgeware.screen = self.screen
        badgeware.io = self.io
        badgeware.brushes = SimpleNamespace(color=lambda *rgb: rgb)
        badgeware.shapes = SimpleNamespace(rounded_rectangle=lambda *args: args)
        badgeware.PixelFont = SimpleNamespace(
            load=lambda path: SimpleNamespace(height=5 if path.endswith("tiny.ppf") else 8)
        )
        machine = ModuleType("machine")
        machine.I2C = lambda *args, **kwargs: self.bus
        machine.Pin = SimpleNamespace(board=SimpleNamespace(I2C_SDA=4, I2C_SCL=5))
        clock = ModuleType("time")
        clock.ticks_ms = lambda: 0
        clock.ticks_diff = ticks_diff
        clock.ticks_add = ticks_add
        native = ModuleType("_gas_index")
        native.reset = lambda: None
        native.process = lambda voc, nox: (100, 1)
        spec = importlib.util.spec_from_file_location("test_sensor_app", APP / "__init__.py")
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {
            "badgeware": badgeware, "machine": machine, "time": clock,
            "_gas_index": native,
        }):
            spec.loader.exec_module(module)
            module.init()
        return module

    def test_default_metric_a_metric_c_imperial_and_frame_bounds(self):
        module = self.load_app()
        self.assertFalse(module.imperial)
        module.dashboard.temperature, module.dashboard.humidity = 25, 50
        module.dashboard.next_sample = 1000
        module.update()
        self.assertIn("25.0 C", [item[0] for item in self.screen.drawn])
        self.assertIn("Temp", [item[0] for item in self.screen.drawn])
        self.assertIn("A=Met C=Imp", [item[0] for item in self.screen.drawn])
        self.assertFalse(any(text.startswith(("SHT:", "SGP:")) for text, _, _ in self.screen.drawn))
        self.io.pressed = {"C"}
        module.update()
        self.assertTrue(module.imperial)
        self.assertIn("77.0 F", [item[0] for item in self.screen.drawn])
        self.io.pressed = {"A"}
        module.update()
        self.assertFalse(module.imperial)
        for x, y, width, height in self.screen.bounds:
            self.assertGreaterEqual(x, 0)
            self.assertLessEqual(x + width, 160)
            self.assertGreaterEqual(y, 0)
            self.assertLessEqual(y + height, 120)
        module.on_exit()
        self.assertEqual(self.bus.writes[-1], (0x59, b"\x36\x15"))

    def test_gas_index_values_and_error_captions(self):
        module = self.load_app()
        module.dashboard.next_sample = 1000
        module.dashboard.indexes.voc = 127
        module.dashboard.indexes.nox = 2
        module.update()
        displayed = [item[0] for item in self.screen.drawn]
        self.assertIn("127", displayed)
        self.assertIn("2", displayed)
        self.assertNotIn("VOC raw", displayed)
        module.dashboard.sgp_status = "CRC error"
        module.dashboard.indexes.reset()
        module.update()
        self.assertIn("CRC error", [item[0] for item in self.screen.clipped])

    def test_header_fits_wider_hardware_font_without_truncating_title(self):
        module = self.load_app()
        module.dashboard.next_sample = 1000
        self.screen.measure_text = lambda text: (len(text) * 8, 8)
        module.update()
        title = next(item for item in self.screen.drawn if item[0] == "SENSORS")
        hint = next(item for item in self.screen.drawn if item[0] == "A=Met C=Imp")
        self.assertGreaterEqual(hint[1] - (title[1] + self.screen.measure_text(title[0])[0]), 6)
        self.assertEqual(hint[1] + self.screen.measure_text(hint[0])[0], 155)

    def test_long_captions_scroll_in_separate_clipped_windows(self):
        module = self.load_app()
        self.screen.measure_text = lambda text: (len(text) * 7, 5)
        clock = [0]
        module.time.ticks_ms = lambda: clock[0]
        module.scrolling_caption("Below usual", 4, module.muted)
        module.scrolling_caption("Background", 82, module.muted)
        self.assertEqual(self.screen.clipped[0], ("Below usual", 0, 0, 9, 98, 64, 8))
        self.assertEqual(self.screen.clipped[1], ("Background", 0, 0, 87, 98, 64, 8))
        clock[0] = 1500
        module.scrolling_caption("Below usual", 4, module.muted)
        self.assertEqual(self.screen.clipped[-1][1], -6)
        clock[0] = 2500
        module.scrolling_caption("Below usual", 4, module.muted)
        self.assertEqual(self.screen.clipped[-1][1], -13)
        module.scrolling_caption("Above usual", 4, module.muted)
        self.assertEqual(self.screen.clipped[-1][1], 0)
        self.assertEqual(module.caption_states[82][0], "Background")

    def test_caption_pause_return_and_short_text(self):
        module = self.load_app()
        self.assertEqual(module.caption_offset(77, 999), 0)
        self.assertEqual(module.caption_offset(77, 1500), 6)
        self.assertEqual(module.caption_offset(77, 2500), 13)
        self.assertEqual(module.caption_offset(77, 3584), 7)
        self.assertEqual(module.caption_offset(77, 4168), 0)
        self.assertEqual(module.caption_offset(63, 1500), 0)

    def test_caption_timing_handles_tick_wrap(self):
        module = self.load_app()
        self.screen.measure_text = lambda text: (88, 8)
        clock = [65000]
        module.time.ticks_ms = lambda: clock[0]
        module.scrolling_caption("Below usual", 4, module.muted)
        clock[0] = ticks_add(65000, 1500)
        module.scrolling_caption("Below usual", 4, module.muted)
        self.assertEqual(self.screen.clipped[-1][1], -6)

    def test_caption_and_footer_use_compact_font_without_image_constructor(self):
        module = self.load_app()
        module.scrolling_caption("Below usual", 4, module.muted)
        self.assertEqual(module.caption_windows[4].font.height, 5)
        module.dashboard.next_sample = 1000
        module.update()
        self.assertEqual(self.screen.font.height, 5)
        self.assertFalse(hasattr(module, "Image"))
        footer = next(bound for text, bound in zip(self.screen.drawn, self.screen.bounds)
                      if text[0] == "RELATIVE INDEX, NOT PPM")
        self.assertEqual(footer[3], 5)

    def test_caption_offset_handles_float_font_measurements(self):
        module = self.load_app()
        self.assertEqual(module.caption_offset(77.0, 1500), 6)
        self.assertIsInstance(module.caption_offset(77.0, 2500), int)

    def test_compact_font_binary_layout(self):
        data = (APP / "tiny.ppf").read_bytes()
        self.assertEqual(data[:4], b"ppf!")
        flags, count, width, height = struct.unpack(">HIHH", data[4:14])
        self.assertEqual((flags, count, width, height), (0, 95, 4, 5))
        self.assertEqual(len(data), 46 + count * (6 + height))
        table = [struct.unpack(">IH", data[46 + i * 6:52 + i * 6]) for i in range(count)]
        self.assertEqual([entry[0] for entry in table], list(range(32, 127)))
        self.assertTrue(all(entry[1] <= width for entry in table))


if __name__ == "__main__":
    unittest.main()
