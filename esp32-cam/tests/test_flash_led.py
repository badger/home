"""Exercise the firmware's LED controller against recorded Arduino PWM calls."""

from pathlib import Path
import subprocess
import tempfile
import unittest


class FlashLedTests(unittest.TestCase):
    def test_pwm_indicator_capture_priority_and_timeout(self):
        tests = Path(__file__).parent
        with tempfile.TemporaryDirectory() as directory:
            binary = str(Path(directory) / "flash-led-test")
            subprocess.run(["c++", "-std=c++11", "-Wall", "-Wextra", "-Werror",
                            "-I", str(tests / "stubs"),
                            str(tests / "flash_led_test.cpp"), "-o", binary],
                           check=True, capture_output=True)
            subprocess.run([binary], check=True, capture_output=True)
