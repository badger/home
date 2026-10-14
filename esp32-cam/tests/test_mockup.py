"""Optional CAD checks: install mockup-requirements.txt to run these tests."""

from collections import Counter
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest


@unittest.skipUnless(importlib.util.find_spec("manifold3d"), "Install mockup-requirements.txt")
class MockupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "esp32-cam-mockup.py"
        spec = importlib.util.spec_from_file_location("camera_mockup", path)
        cls.model = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.model)
        cls.solid = cls.model.build()

    def test_envelope_in_millimetres(self):
        for actual, expected in zip(self.solid.bounding_box(), (-3, 0, 0, 41.5, 27, 23.5)):
            self.assertAlmostEqual(actual, expected, places=5)
        self.assertEqual(len(self.solid.decompose()), 1)

    def test_connector_and_features_on_correct_ends(self):
        parts = self.model.components()
        self.assertAlmostEqual(parts["USB-C socket"].bounding_box()[3], 41.5)
        self.assertAlmostEqual(parts["inserted microSD"].bounding_box()[0], -3.0)
        lens = parts["camera lens"].bounding_box()
        self.assertAlmostEqual((lens[0] + lens[3]) / 2, 9.9)
        self.assertAlmostEqual((lens[1] + lens[4]) / 2, 13.6)
        led = parts["flash LED"].bounding_box()
        self.assertAlmostEqual((led[0] + led[3]) / 2, 30.4)
        self.assertAlmostEqual((led[1] + led[4]) / 2, 24.7)

    def test_export_is_watertight_and_matches_checked_in_stl(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mockup.stl"
            self.model.write_stl(self.solid, path)
            data = path.read_bytes()
        checked_in = Path(self.model.__file__).with_suffix(".stl")
        self.assertEqual(data, checked_in.read_bytes())
        count = struct.unpack_from("<I", data, 80)[0]
        self.assertEqual(len(data), 84 + 50 * count)
        edges = Counter()
        directed = Counter()
        volume = 0.0
        for offset in range(84, len(data), 50):
            values = struct.unpack_from("<12fH", data, offset)
            a, b, c = (tuple(values[i:i + 3]) for i in (3, 6, 9))
            for start, end in ((a, b), (b, c), (c, a)):
                edges[tuple(sorted((start, end)))] += 1
                directed[(start, end)] += 1
            volume += (a[0] * (b[1] * c[2] - b[2] * c[1])
                       + a[1] * (b[2] * c[0] - b[0] * c[2])
                       + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6
        self.assertTrue(edges)
        self.assertTrue(all(count == 2 for count in edges.values()))
        self.assertTrue(all(count == directed[(end, start)] for (start, end), count in directed.items()))
        self.assertGreater(volume, 0)
