#!/usr/bin/env python3
"""Build the haiku printer's 1-bit raster assets and launcher icon.

The thermal printer is 384 dots wide at 203 dpi. Rasters are stored as:
  u8 width_bytes, u16 little-endian height, then rows of 1bpp pixels
  (MSB is the leftmost pixel, 1 is black), ready for ESC/POS ``GS v 0``.
"""

import argparse
from pathlib import Path
import struct

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/haiku_printer"
OUTPUT = ROOT / "badge/apps/haiku_printer"
QR_URL = "https://gh.io/badger2026"

LOGO_WIDTH = 80
# The source QR is 380 px with a 16 px border; 29 modules at 6 dots each.
QR_CROP = (16, 16, 364, 364)
QR_MODULES = 29
QR_DOTS = 6
QR_SYMBOL = QR_MODULES * QR_DOTS
QR_QUIET = 4 * QR_DOTS


def flatten(path):
    image = Image.open(path).convert("RGBA")
    white = Image.new("RGBA", image.size, (255, 255, 255, 255))
    return Image.alpha_composite(white, image).convert("L")


def threshold(image):
    return image.point(lambda value: 0 if value < 128 else 255, "1")


def build_logo():
    image = flatten(SOURCE / "github_invertocat_black.png")
    image = image.crop(Image.eval(image, lambda value: 255 - value).getbbox())
    height = round(image.height * LOGO_WIDTH / image.width)
    return threshold(image.resize((LOGO_WIDTH, height), Image.LANCZOS))


def build_qr():
    image = flatten(SOURCE / "qr_badger2026.png").crop(QR_CROP)
    symbol = threshold(image.resize((QR_SYMBOL, QR_SYMBOL), Image.LANCZOS))
    size = QR_SYMBOL + 2 * QR_QUIET
    canvas = Image.new("1", (size, size), 1)
    canvas.paste(symbol, (QR_QUIET, QR_QUIET))
    return canvas


def verify_qr(image):
    try:
        import cv2
        import numpy
    except ImportError:
        print("warning: opencv not installed; QR decode not verified")
        return
    pixels = numpy.array(image.convert("L").resize((image.width * 2, image.height * 2)))
    data, _, _ = cv2.QRCodeDetector().detectAndDecode(pixels)
    if data != QR_URL:
        raise SystemExit("QR raster decodes to {!r}, expected {!r}".format(data, QR_URL))


def pack(image):
    width_bytes = (image.width + 7) // 8
    rows = bytearray()
    for y in range(image.height):
        row = bytearray(width_bytes)
        for x in range(image.width):
            if image.getpixel((x, y)) == 0:
                row[x >> 3] |= 0x80 >> (x & 7)
        rows += row
    return struct.pack("<BH", width_bytes, image.height) + bytes(rows)


def build_icon():
    icon = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
    draw = ImageDraw.Draw(icon)
    paper = (250, 250, 245, 255)
    ink = (36, 41, 47, 255)
    draw.rectangle((5, 1, 18, 20), fill=paper, outline=ink)
    for x in range(5, 19, 3):
        draw.polygon(((x, 20), (x + 1, 22), (x + 3, 20)), fill=paper, outline=ink)
    for y, width in ((5, 9), (8, 7), (11, 9)):
        draw.line((7, y, 7 + width - 1, y), fill=ink)
    for x in range(7, 17, 2):
        draw.line((x, 14, x, 17), fill=ink)
    return icon


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preview", action="store_true", help="also write PNG previews")
    args = parser.parse_args()

    (OUTPUT / "assets").mkdir(parents=True, exist_ok=True)
    logo = build_logo()
    qr = build_qr()
    verify_qr(qr)
    for name, image in (("logo", logo), ("qr", qr)):
        data = pack(image)
        (OUTPUT / "assets" / (name + ".bin")).write_bytes(data)
        print("{}.bin {}x{} {} bytes".format(name, image.width, image.height, len(data)))
        if args.preview:
            image.save(OUTPUT / "assets" / (name + "_preview.png"))
    build_icon().save(OUTPUT / "icon.png")
    print("icon.png 24x24")


if __name__ == "__main__":
    main()
