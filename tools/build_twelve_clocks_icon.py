"""Build the 24x24 launcher icon without Pillow or other host dependencies."""

import ast
import math
from pathlib import Path
import struct
import zlib

APP = Path(__file__).resolve().parents[1] / "badge/apps/twelve_clocks"


def build():
    rows = {}
    tree = ast.parse((APP / "clockwork.py").read_text())
    for item in tree.body:
        if isinstance(item, ast.Assign) and item.targets[0].id == "FONT":
            for key, value in zip(item.value.keys, item.value.values):
                if key.value in ("1", "2"):
                    rows[key.value] = ast.literal_eval(value.args[0])
    rgb = bytearray(24 * 24 * 3)

    def pixel(x, y, pen):
        if 0 <= x < 24 and 0 <= y < 24:
            offset = (y * 24 + x) * 3
            rgb[offset:offset + 3] = bytes(pen)

    for i in range(12):
        a = i * math.tau / 12
        pixel(round(11.5 + math.sin(a) * 10),
              round(11.5 - math.cos(a) * 10), (255, 0, 0) if i == 0 else (150, 150, 150))
    for i, char in enumerate("12"):
        for y, row in enumerate(rows[char]):
            for x in range(5):
                if row & (16 >> x):
                    pixel(6 + i * 6 + x, 8 + y, (255, 255, 255))

    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data)))

    raw = b"".join(b"\0" + rgb[y * 72:(y + 1) * 72] for y in range(24))
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">2I5B", 24, 24, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    (APP / "icon.png").write_bytes(png)
    print("Wrote icon.png (%d bytes)" % len(png))


if __name__ == "__main__":
    build()
