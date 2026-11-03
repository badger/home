#!/usr/bin/env python3
"""Build the 320x240 artwork for Flappy Mona Redux.

The original Flappy Mona art is drawn for the 160x120 display mode. Redux runs
at the full 320x240, so each sprite is re-rendered at twice the size with the
Scale2x (EPX) pixel-art algorithm, which keeps the hand-drawn look but smooths
the stair-stepped diagonals. The fish, far hills, roller and icon are drawn here,
and the roof tower's brick strips, mossy lip, underside spikes and floor spike
are cut from the scaled wall tiles so they match the walls exactly.

Run from the repository root:

    python3 tools/build_flappy_mona_redux_assets.py
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "badge/apps/flappy_mona/assets"
APP = ROOT / "badge/apps/flappy_mona_redux"
OUTPUT = APP / "assets"

CLEAR = (0, 0, 0, 0)
WHITE = (255, 255, 255, 255)
MORTAR = (73, 36, 85, 255)  # the dark outline and mortar of the wall tiles
MOSS = (36, 146, 0, 255)
LIGHT_MOSS = (73, 182, 0, 255)
NAVY = (36, 36, 85, 255)
GOLD = (255, 182, 0, 255)
STEEL = (109, 109, 170, 255)
STEEL_DARK = (73, 73, 130, 255)
STEEL_LIGHT = (170, 170, 215, 255)


def scale2x(image, edge="transparent"):
    """Scale2x/EPX. `edge` is how pixels outside the image are read:
    "transparent" for sprites, "clamp" for the bottom of tiles, and "wrap" to
    keep horizontally repeating tiles seamless."""
    image = image.convert("RGBA")
    width, height = image.size
    source = image.load()

    def pixel(x, y):
        if edge == "wrap":
            x %= width
            y = min(max(y, 0), height - 1)
        elif edge == "clamp":
            x = min(max(x, 0), width - 1)
            y = min(max(y, 0), height - 1)
        elif not (0 <= x < width and 0 <= y < height):
            return CLEAR
        return source[x, y]

    result = Image.new("RGBA", (width * 2, height * 2), CLEAR)
    target = result.load()
    for y in range(height):
        for x in range(width):
            p = pixel(x, y)
            a, b = pixel(x, y - 1), pixel(x + 1, y)
            c, d = pixel(x - 1, y), pixel(x, y + 1)
            target[2 * x, 2 * y] = a if c == a and c != d and a != b else p
            target[2 * x + 1, 2 * y] = b if a == b and a != c and b != d else p
            target[2 * x, 2 * y + 1] = c if d == c and d != b and c != a else p
            target[2 * x + 1, 2 * y + 1] = d if b == d and b != a and d != c else p
    return result


def scale_sheet(path, columns, rows):
    """Scale each frame of a sprite sheet on its own so frames never bleed."""
    sheet = Image.open(path).convert("RGBA")
    frame_w, frame_h = sheet.width // columns, sheet.height // rows
    result = Image.new("RGBA", (sheet.width * 2, sheet.height * 2), CLEAR)
    for row in range(rows):
        for column in range(columns):
            box = (column * frame_w, row * frame_h, (column + 1) * frame_w, (row + 1) * frame_h)
            frame = scale2x(sheet.crop(box))
            result.paste(frame, (column * frame_w * 2, row * frame_h * 2))
    return result


def outline(image, colour=WHITE):
    """Add a one pixel outline around the opaque pixels of `image`."""
    width, height = image.size
    source = image.load()
    result = image.copy()
    target = result.load()
    for y in range(height):
        for x in range(width):
            if source[x, y][3]:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height and source[nx, ny][3]:
                    target[x, y] = colour
                    break
    return result


def far_hills(width=256, height=64):
    """A soft, distant ridge line that tiles horizontally."""
    image = Image.new("RGBA", (width, height), CLEAR)
    pixels = image.load()
    sky_top = (118, 206, 232, 255)
    sky_bottom = (150, 224, 240, 255)
    for x in range(width):
        t = 2 * math.pi * x / width
        ridge = 26 + 11 * math.sin(t + 0.6) + 7 * math.sin(2 * t + 2.1) + 4 * math.sin(3 * t + 4.0)
        for y in range(int(ridge), height):
            mix = (y - ridge) / max(1, height - ridge)
            pixels[x, y] = tuple(
                round(sky_top[i] + (sky_bottom[i] - sky_top[i]) * mix) for i in range(3)
            ) + (255,)
    return image


def fish_frame(tail):
    """One frame of the fish, facing left. `tail` swings the tail fin -2..2."""
    scale = 4
    size = (22 * scale, 14 * scale)
    art = Image.new("RGBA", size, CLEAR)
    draw = ImageDraw.Draw(art)

    def box(x0, y0, x1, y1):
        return (x0 * scale, y0 * scale, x1 * scale - 1, y1 * scale - 1)

    def points(*coordinates):
        return [(x * scale, y * scale) for x, y in coordinates]

    orange = (255, 150, 40, 255)
    dark = (226, 98, 28, 255)
    light = (255, 205, 96, 255)
    # Tail fin first so the body overlaps its root.
    swing = tail * 1.5
    draw.polygon(points((14, 7), (21, 3 + swing), (21, 11 + swing)), fill=dark)
    # Dorsal and belly fins.
    draw.polygon(points((8, 3.5), (11, 0.5), (13, 3.5)), fill=dark)
    draw.polygon(points((9, 10.5), (11.5, 13), (13, 10.5)), fill=dark)
    # Body, belly and highlight.
    draw.ellipse(box(1, 2, 16, 12), fill=orange)
    draw.ellipse(box(2, 7, 15, 12), fill=light)
    draw.ellipse(box(2, 2, 15, 8), fill=orange)
    # Stripes.
    for x in (8, 11):
        draw.line(points((x, 3.5), (x + 0.5, 10.5)), fill=dark, width=scale)
    # Eye.
    draw.ellipse(box(3, 4, 6, 7), fill=WHITE)
    draw.ellipse(box(3.5, 5, 5.5, 7), fill=(30, 20, 60, 255))

    # Flatten the 4x art to the 1x pixel grid, then thicken it into an outlined sprite.
    small = art.resize((22, 14), Image.NEAREST)
    pixels = small.load()
    for y in range(14):
        for x in range(22):
            r, g, b, a = pixels[x, y]
            pixels[x, y] = (r, g, b, 255 if a >= 128 else 0)
    padded = Image.new("RGBA", (24, 16), CLEAR)
    padded.paste(small, (1, 1))
    return scale2x(outline(padded))


def build_fish():
    frames = [fish_frame(tail) for tail in (-2, 0, 2, 0)]
    sheet = Image.new("RGBA", (frames[0].width * len(frames), frames[0].height), CLEAR)
    for index, frame in enumerate(frames):
        sheet.paste(frame, (index * frame.width, 0))
    return sheet


def roof_strips(brick):
    """The brick tile's three 16px courses, each cut into 24px left and right
    halves. The tile corners are cut away, so fill them with mortar to keep the
    joined strips free of pin holes."""
    strips = Image.new("RGBA", (24 * 6, 16), CLEAR)
    for course in range(3):
        for half in range(2):
            left = half * 24
            piece = brick.crop((left, course * 16, left + 24, course * 16 + 16))
            pixels = piece.load()
            for y in range(16):
                for x in range(24):
                    if not pixels[x, y][3]:
                        pixels[x, y] = MORTAR
            strips.paste(piece, ((course * 2 + half) * 24, 0))
    return strips


def roof_lip():
    """A 4px mossy cap for the top of every tread, as left and right 24px halves."""
    lip = Image.new("RGBA", (48, 4), CLEAR)
    pixels = lip.load()
    for x in range(48):
        pixels[x, 0] = MORTAR
        pixels[x, 1] = LIGHT_MOSS
        pixels[x, 2] = MOSS
        if x % 8 in (0, 1, 2, 5, 6):
            pixels[x, 3] = MOSS
    return lip


def roof_spike(cap):
    """One of the cap tile's downward spikes, flipped to stand on the roof."""
    spike = Image.new("RGBA", (16, 14), CLEAR)
    spike.paste(ImageOps.flip(cap.crop((2, 34, 16, 48))), (1, 0))
    return spike


def roller_frame(step):
    """One of four turns of a steel roller drum. The four spokes repeat every
    quarter turn, so four frames close the loop."""
    scale = 8
    size = 14 * scale
    middle = size / 2
    art = Image.new("RGBA", (size, size), CLEAR)
    draw = ImageDraw.Draw(art)

    def disc(radius, fill):
        draw.ellipse(
            (middle - radius * scale, middle - radius * scale, middle + radius * scale - 1, middle + radius * scale - 1),
            fill=fill,
        )

    disc(7, STEEL_LIGHT)
    disc(5.6, STEEL)
    disc(3.4, STEEL_DARK)
    for spoke in range(4):
        angle = math.radians(step * 22.5 + spoke * 90)
        dx, dy = math.cos(angle), math.sin(angle)
        px, py = -dy, dx
        reach, half = 5.4 * scale, 0.7 * scale
        draw.polygon(
            [
                (middle + px * half, middle + py * half),
                (middle + dx * reach + px * half, middle + dy * reach + py * half),
                (middle + dx * reach - px * half, middle + dy * reach - py * half),
                (middle - px * half, middle - py * half),
            ],
            fill=NAVY,
        )
        draw.ellipse(
            (
                middle + dx * 4.6 * scale - 0.8 * scale,
                middle + dy * 4.6 * scale - 0.8 * scale,
                middle + dx * 4.6 * scale + 0.8 * scale,
                middle + dy * 4.6 * scale + 0.8 * scale,
            ),
            fill=STEEL_LIGHT,
        )
    disc(1.7, GOLD)

    small = art.resize((14, 14), Image.NEAREST)
    pixels = small.load()
    for y in range(14):
        for x in range(14):
            r, g, b, a = pixels[x, y]
            pixels[x, y] = (r, g, b, 255 if a >= 128 else 0)
    # The light stays put while the drum turns, so paint the glint last.
    for x, y in ((3, 2), (4, 1), (5, 1), (2, 3)):
        pixels[x, y] = WHITE

    padded = Image.new("RGBA", (16, 16), CLEAR)
    padded.paste(small, (1, 1))
    return scale2x(outline(padded, NAVY))


def build_roller():
    frames = [roller_frame(step) for step in range(4)]
    sheet = Image.new("RGBA", (frames[0].width * len(frames), frames[0].height), CLEAR)
    for index, frame in enumerate(frames):
        sheet.paste(frame, (index * frame.width, 0))
    return sheet


def build_icon(fish):
    """The 24x24 menu icon the launcher expects: the original Mona with a fish."""
    icon = Image.new("RGBA", (24, 24), CLEAR)
    icon.alpha_composite(Image.open(SOURCE / "mona.png").crop((0, 0, 24, 24)), (0, -1))
    small = fish.crop((0, 0, 48, 32)).resize((16, 10), Image.BOX)
    pixels = small.load()
    for y in range(small.height):
        for x in range(small.width):
            r, g, b, a = pixels[x, y]
            pixels[x, y] = (r, g, b, 255 if a >= 128 else 0)
    icon.alpha_composite(small, (8, 14))
    return icon


def save(image, name):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT / name, optimize=True)
    print(f"{name}: {image.width}x{image.height}")


def main():
    mona = scale_sheet(SOURCE / "mona.png", 7, 2)
    fish = build_fish()
    obstacles = scale_sheet(SOURCE / "obstacles.png", 2, 1)
    brick, cap = obstacles.crop((0, 0, 48, 48)), obstacles.crop((48, 0, 96, 48))
    save(mona, "mona.png")
    save(obstacles, "obstacles.png")
    save(scale2x(Image.open(SOURCE / "cloud.png"), "clamp"), "cloud.png")
    save(scale2x(Image.open(SOURCE / "background.png"), "wrap"), "background.png")
    save(scale2x(Image.open(SOURCE / "grass.png"), "wrap"), "grass.png")
    save(far_hills(), "far_hills.png")
    save(fish, "fish.png")
    save(roof_strips(brick), "roof.png")
    save(roof_lip(), "roof_lip.png")
    save(cap.crop((0, 28, 48, 48)), "roof_under.png")
    save(roof_spike(cap), "spike.png")
    save(build_roller(), "roller.png")
    icon = build_icon(fish)
    icon.save(APP / "icon.png", optimize=True)
    print(f"icon.png: {icon.width}x{icon.height}")


if __name__ == "__main__":
    main()
