"""Tests for the Taste Stamp & Creative 8-Ball app in badge/apps/taste_stamp.

The app's modules are loaded under unique taste_stamp_* names and are never
registered in sys.modules, so these tests can share a process with other
apps' tests that vendor helpers with generic names.
"""

import ast
import math
import struct
import types
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "badge" / "apps" / "taste_stamp"


def load(path, name):
    # Executes a source file as a fresh module without touching sys.modules.
    module = types.ModuleType(name)
    module.__file__ = str(path)
    code = compile(Path(path).read_text(encoding="utf-8"), str(path), "exec")
    exec(code, module.__dict__)
    return module


V = load(APP / "verdicts.py", "taste_stamp_verdicts")
README_CHECK = load(ROOT / ".github" / "scripts" / "validate_app_readmes.py", "taste_stamp_validate_app_readmes")


def luminance(c):
    def channel(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(v) for v in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


class VerdictsTests(unittest.TestCase):
    def test_verdicts_follow_the_spec_order(self):
        self.assertEqual(V.VERDICTS, (
            "SHIP IT",
            "CERTIFIED BANGER",
            "NEEDS MORE TEETH",
            "KILL THE FLUFF",
            "TOO SAFE",
            "WHERE IS THE TENSION?",
            "MAKE THE DEV THE HERO",
        ))

    def test_ordered_collections_are_tuples(self):
        for value in (V.VERDICTS, V.INKS, V.FOOTERS):
            self.assertIsInstance(value, tuple)

    def test_every_verdict_has_an_ink_and_a_footer(self):
        self.assertEqual(len(V.INKS), len(V.VERDICTS))
        self.assertEqual(V.FOOTERS, ("APPROVED",) * 2 + ("REVISE",) * 5)
        self.assertEqual(V.STAMP_HEADER, "CREATIVE DIRECTOR")
        for ink in V.INKS:
            self.assertEqual(len(ink), 3)
            for v in ink:
                self.assertIsInstance(v, int)
                self.assertTrue(0 <= v <= 255)

    def test_inks_read_on_paper_and_differ(self):
        paper = (241, 236, 224)
        k = 225 / 255.0
        for ink in V.INKS:
            blended = tuple(round(i * k + p * (1 - k)) for i, p in zip(ink, paper))
            self.assertGreaterEqual(contrast(blended, paper), 3.0, ink)
        for i, a in enumerate(V.INKS):
            for b in V.INKS[i + 1:]:
                self.assertGreaterEqual(math.dist(a, b), 40, (a, b))


def read_png(path):
    data = Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    chunks = []
    pos = 8
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        (crc,) = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])
        chunks.append((kind, body, crc == zlib.crc32(kind + body) & 0xFFFFFFFF))
        pos += 12 + length
    return chunks


def png_pixels(chunks):
    width, height, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", chunks[0][1])
    bpp = {6: 4, 2: 3, 4: 2, 0: 1}[ctype]
    raw = zlib.decompress(b"".join(body for kind, body, _ in chunks if kind == b"IDAT"))
    stride = width * bpp
    rows = []
    prev = bytearray(stride)
    pos = 0
    for _ in range(height):
        kind = raw[pos]
        line = bytearray(raw[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if kind == 1:
                line[x] = (line[x] + a) & 0xFF
            elif kind == 2:
                line[x] = (line[x] + b) & 0xFF
            elif kind == 3:
                line[x] = (line[x] + (a + b) // 2) & 0xFF
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 0xFF
        rows.append([tuple(line[i:i + bpp]) for i in range(0, stride, bpp)])
        prev = line
    return rows


class IconTests(unittest.TestCase):
    def test_icon_is_a_valid_24px_rgba_png(self):
        chunks = read_png(APP / "icon.png")
        self.assertEqual(chunks[0][0], b"IHDR")
        self.assertEqual(chunks[-1][0], b"IEND")
        self.assertTrue(all(ok for _, _, ok in chunks))
        width, height, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", chunks[0][1])
        self.assertEqual((width, height, depth, ctype, interlace), (24, 24, 8, 6, 0))

    def test_icon_has_a_drawn_mark(self):
        rows = png_pixels(read_png(APP / "icon.png"))
        self.assertEqual(len(rows), 24)
        alphas = [p[3] for row in rows for p in row]
        self.assertGreaterEqual(alphas.count(255), 48)
        self.assertGreaterEqual(alphas.count(0), 24 * 24 * 2 // 5)

    def test_icon_is_white_like_the_menu_icons(self):
        rows = png_pixels(read_png(APP / "icon.png"))
        # Transparent pixels are white too, so the menu's bilinear blit has no dark fringe.
        self.assertEqual({p[:3] for row in rows for p in row}, {(255, 255, 255)})

    def test_icon_is_legible_on_every_menu_tile(self):
        # The menu blits icon.png over a palette colour (full when selected, 22% otherwise).
        tree = ast.parse((ROOT / "badge/apps/menu/src/ui.py").read_text(encoding="utf-8"))
        palette = [ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                   and any(getattr(t, "id", None) == "PALETTE" for t in node.targets)][0]
        self.assertGreaterEqual(len(palette), 8)
        for rgb in palette:
            for strength in (1.0, 0.22):
                tile = tuple(round(c * strength) for c in rgb)
                self.assertGreaterEqual(contrast((255, 255, 255), tile), 2.0, tile)


class ReadmeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (APP / "README.md").read_text(encoding="utf-8")

    def test_repository_readme_check_passes(self):
        self.assertIsNone(README_CHECK.check_app(APP))

    def test_first_paragraph_is_the_one_sentence_description(self):
        lines = self.text.splitlines()
        self.assertEqual(lines[0], "# Taste Stamp")
        i = 1
        while not lines[i].strip():
            i += 1
        paragraph = []
        while i < len(lines) and lines[i].strip():
            paragraph.append(lines[i].strip())
            i += 1
        self.assertEqual(" ".join(paragraph), (
            "Flip or karate-chop your badge to slam Creative Director verdicts, shake the "
            "Creative 8-Ball for a Studio creative direction, and beam either one to nearby "
            "badges over IR."
        ))


if __name__ == "__main__":
    unittest.main()
