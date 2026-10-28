#!/usr/bin/env python3
"""Prepare offline slideshow photos and a launcher icon for the 2026 badge."""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


APP_DIR = Path(__file__).resolve().parents[1] / "badge" / "apps" / "linkedin_photo"


def prepare(source, output=None, crop=None):
    if output is None:
        output = APP_DIR / "assets" / (Path(source).stem + ".png")
    if Path(output).suffix.lower() != ".png":
        raise ValueError("Output must have a .png extension.")
    if Path(source).resolve() == Path(output).resolve():
        raise ValueError("Source and output must be different files.")
    with Image.open(source) as original:
        photo = ImageOps.exif_transpose(original).convert("RGBA")
        if crop is not None:
            left, top, right, bottom = crop
            if not (0 <= left < right <= photo.width and
                    0 <= top < bottom <= photo.height):
                raise ValueError("Crop must be inside the oriented source image.")
            photo = photo.crop(crop)
        background = Image.new("RGBA", photo.size, (0, 0, 0, 255))
        background.alpha_composite(photo)
        photo = ImageOps.contain(
            background.convert("RGB"), (320, 240), Image.Resampling.LANCZOS
        )
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        photo.save(output, format="PNG", optimize=True)
        return photo.size


def make_icon(output=APP_DIR / "icon.png"):
    icon = Image.new("RGB", (24, 24), (10, 102, 194))
    draw = ImageDraw.Draw(icon)
    draw.ellipse((9, 4, 15, 10), fill="white")
    draw.rounded_rectangle((5, 12, 19, 21), radius=5, fill="white")
    icon.save(output, format="PNG", optimize=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Your saved JPG or PNG")
    parser.add_argument(
        "--output", type=Path,
        help="Destination PNG (default: app assets/<source filename>.png)",
    )
    parser.add_argument(
        "--crop", type=int, nargs=4, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"),
        help="Optional crop box in pixels, after EXIF orientation correction",
    )
    args = parser.parse_args()
    output = args.output or APP_DIR / "assets" / (args.source.stem + ".png")
    size = prepare(args.source, output, args.crop)
    make_icon()
    print("Saved %s (%dx%d RGB PNG)" % (output, *size))


if __name__ == "__main__":
    main()
