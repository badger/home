"""Execute the firmware's actual signal-strength gate on the host."""

from pathlib import Path
import subprocess
import tempfile
import unittest


class ProximityTests(unittest.TestCase):
    def test_firmware_proximity_threshold_dwell_freshness_peer_and_window(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = str(Path(directory) / "proximity-test")
            source = Path(__file__).with_name("proximity_test.cpp")
            subprocess.run(["c++", "-std=c++11", "-Wall", "-Wextra", "-Werror",
                            str(source), "-o", binary], check=True, capture_output=True)
            subprocess.run([binary], check=True, capture_output=True)
