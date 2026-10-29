"""Generate the original Mona/calendar icon using only Python's standard library."""

from pathlib import Path
import struct
import zlib


def icon_bytes():
    size = 48
    pixels = [[(13, 17, 23) for _ in range(size)] for _ in range(size)]

    def rectangle(x, y, width, height, ink):
        for row in range(y, y + height):
            for column in range(x, x + width):
                pixels[row][column] = ink

    def circle(x, y, radius, ink):
        for row in range(size):
            for column in range(size):
                if (column - x) ** 2 + (row - y) ** 2 <= radius ** 2:
                    pixels[row][column] = ink

    purple = (190, 133, 255)
    white = (255, 236, 220)
    dark = (13, 17, 23)
    green = (211, 250, 55)
    rectangle(7, 18, 34, 24, purple)
    rectangle(10, 23, 28, 16, white)
    rectangle(13, 14, 3, 8, green)
    rectangle(32, 14, 3, 8, green)
    circle(24, 16, 11, purple)
    rectangle(14, 3, 6, 12, purple)
    rectangle(28, 3, 6, 12, purple)
    circle(24, 18, 8, white)
    circle(21, 17, 2, dark)
    circle(27, 17, 2, dark)
    rectangle(22, 22, 5, 1, dark)
    rectangle(16, 31, 4, 4, purple)
    rectangle(23, 31, 4, 4, purple)
    rectangle(30, 31, 4, 4, purple)

    def chunk(kind, data):
        payload = kind + data
        return (struct.pack(">I", len(data)) + payload
                + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF))

    raw = b"".join(b"\0" + bytes(channel for pixel in row for channel in pixel)
                   for row in pixels)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    target = root / "badge" / "apps" / "universe_agenda" / "icon.png"
    target.write_bytes(icon_bytes())
    print(target)
