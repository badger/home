import math
import os
import struct
from array import array

import ui
from icons import ICONS

TILES_PER_ROW = 4

APP_ORDER = ("merge_conflict", "mona_pet", "rogue", "iss", "snake")

GAP = 4
GRID_WIDTH = 312
TILE = (GRID_WIDTH - (TILES_PER_ROW - 1) * GAP) // TILES_PER_ROW
GRID_LEFT = (320 - (TILES_PER_ROW * TILE + (TILES_PER_ROW - 1) * GAP)) // 2
GRID_TOP = ui.STATUS_HEIGHT + 2
GRID_BOTTOM = ui.RIBBON_TOP
ROW_PITCH = TILE + GAP
VISIBLE_ROWS = max(1, (GRID_BOTTOM - GRID_TOP + GAP) // ROW_PITCH)

DESIGN_TILE = 75
DESIGN_SCALE = TILE / DESIGN_TILE
ICON_SIZE = 48 * DESIGN_SCALE
BORDER = 2
BACKGROUND_SHIFT = 6
ICON_SHIFT = 3
SCROLL_MS = 90

BASE_STRENGTH = 0.22
MID_STRENGTH = 0.42
HIGH_STRENGTH = 0.62

HALF = TILE / 2
DESIGN_HALF = DESIGN_TILE / 2

ANIMATION_DIR = "/system/apps/menu/anim"
ANIMATION_MAGIC = b"BWIC"
ANIMATION_VERSION = 3


def polygon(*values):
    return shape.custom(array("f", values))


def build_patterns():
    return [
        [
            ("mid", shape.circle(18, 20, 36)),
            ("base", shape.circle(18, 20, 22)),
            ("high", shape.circle(18, 20, 10)),
        ],
        [
            ("mid", polygon(-60, 10, 10, -60, 34, -60, -60, 34)),
            ("high", polygon(-20, 60, 60, -20, 60, -6, -6, 60)),
        ],
        [
            ("mid", polygon(-DESIGN_HALF - 8, DESIGN_HALF + 8, DESIGN_HALF + 8, DESIGN_HALF + 8, DESIGN_HALF + 8, -DESIGN_HALF - 8)),
            ("high", shape.circle(-16, -16, 8)),
        ],
        [
            ("mid", shape.circle(-DESIGN_HALF, DESIGN_HALF, 52)),
            ("base", shape.circle(-DESIGN_HALF, DESIGN_HALF, 40)),
            ("mid", shape.circle(-DESIGN_HALF, DESIGN_HALF, 28)),
            ("base", shape.circle(-DESIGN_HALF, DESIGN_HALF, 16)),
        ],
        [
            ("mid", shape.regular_polygon(16, 16, 42, 4)),
            ("high", shape.regular_polygon(16, 16, 18, 4)),
        ],
        [
            ("mid", shape.circle(0, DESIGN_HALF + 6, 32)),
            ("high", shape.circle(22, -20, 9)),
        ],
        [
            ("mid", shape.rectangle(-DESIGN_HALF - 8, -DESIGN_HALF - 8, 26, DESIGN_TILE + 16)),
            ("high", shape.rectangle(-DESIGN_HALF + 22, -DESIGN_HALF - 8, 8, DESIGN_TILE + 16)),
        ],
    ]


PATTERNS = build_patterns()


def build_icon(contours):
    return shape.custom(*(array("f", values) for values in contours))


def animated_slugs():
    try:
        return {name[:-4] for name in os.listdir(ANIMATION_DIR) if name.endswith(".bin")}
    except OSError:
        return set()


class Animation:
    def __init__(self, file, fps, offsets):
        self.file = file
        self.fps = fps
        self.offsets = offsets
        self.shapes = [None] * len(offsets)

    def frame(self, index):
        index = min(len(self.shapes) - 1, index)
        if self.shapes[index] is None:
            file = self.file
            file.seek(self.offsets[index])
            contours = []
            for _ in range(file.read(1)[0]):
                points = struct.unpack("<H", file.read(2))[0]
                contours.append(array("f", file.read(points * 8)))
            self.shapes[index] = shape.custom(*contours)
        return self.shapes[index]


def load_animation(slug):
    try:
        file = open(f"{ANIMATION_DIR}/{slug}.bin", "rb")
    except OSError:
        return None
    header = file.read(9)
    if header[:4] != ANIMATION_MAGIC:
        file.close()
        return None
    version, fps, count = struct.unpack_from("<HBH", header, 4)
    if version != ANIMATION_VERSION:
        file.close()
        return None
    offsets = struct.unpack(f"<{count}I", file.read(4 * count))
    return Animation(file, fps, offsets)


class App:
    def __init__(self, index, name, slug, path, animated=False):
        self.index = index
        self.name = name
        self.slug = slug
        self.path = path
        self.animated = animated
        self.column = index % TILES_PER_ROW
        self.row = index // TILES_PER_ROW
        self.rgb = ui.PALETTE[index % len(ui.PALETTE)]
        self.base = ui.shade(self.rgb, BASE_STRENGTH)
        self.tones = {
            "base": self.base,
            "mid": ui.shade(self.rgb, MID_STRENGTH),
            "high": ui.shade(self.rgb, HIGH_STRENGTH),
        }
        self.solid = color.rgb(*self.rgb)
        self.pattern = PATTERNS[(index * 3) % len(PATTERNS)]
        self.icon_key = slug if slug in ICONS else "default"
        self.icon = build_icon(ICONS[self.icon_key])
        self.animation = None
        self.was_selected = False
        self.selected_at = 0

    def current_icon(self, selected):
        if not self.animated:
            return self.icon
        if selected and not self.was_selected:
            if self.animation is None:
                self.animation = load_animation(self.icon_key)
                if self.animation is None:
                    self.animated = False
                    return self.icon
            self.selected_at = badge.ticks
        self.was_selected = selected
        if not selected:
            return self.icon
        animation = self.animation
        return animation.frame((badge.ticks - self.selected_at) * animation.fps // 1000)

    def draw(self, scroll, tilt, selected, scale=1.0):
        if scale <= 0:
            return
        centre_x = GRID_LEFT + self.column * (TILE + GAP) + HALF
        centre_y = GRID_TOP + self.row * ROW_PITCH - scroll + HALF
        size = TILE * scale
        left = centre_x - size / 2
        top = centre_y - size / 2
        if top + size < GRID_TOP or top > GRID_BOTTOM:
            return

        clip_top = max(top, GRID_TOP)
        clip_bottom = min(top + size, GRID_BOTTOM)
        screen.clip = rect(left, clip_top, size, clip_bottom - clip_top)

        if selected:
            border = BORDER * scale
            screen.pen = ui.white
            screen.rectangle(left, top, size, size)
            screen.pen = self.solid
            screen.rectangle(left + border, top + border, size - border * 2, size - border * 2)
        else:
            screen.pen = self.base
            screen.rectangle(left, top, size, size)
            transform = mat3().translate(
                centre_x - tilt.x * BACKGROUND_SHIFT,
                centre_y - tilt.y * BACKGROUND_SHIFT,
            ).scale(scale * DESIGN_SCALE)
            for tone, element in self.pattern:
                element.transform = transform
                screen.pen = self.tones[tone]
                screen.shape(element)

        icon = self.current_icon(selected)
        icon.transform = mat3().translate(
            centre_x + tilt.x * ICON_SHIFT,
            centre_y + tilt.y * ICON_SHIFT,
        ).scale(ICON_SIZE * scale)
        screen.pen = ui.white
        screen.shape(icon)


class Apps:
    def __init__(self, root):
        self.apps = []
        self.active_index = 0
        self.changed_at = 0
        self.scroll = 0.0
        self.target = 0
        self.last_ticks = None

        def capitalize(word):
            if len(word) <= 1:
                return word
            return word[0].upper() + word[1:]

        def order(slug):
            return (APP_ORDER.index(slug) if slug in APP_ORDER else len(APP_ORDER), slug)

        animated = animated_slugs()
        folders = [entry[0] for entry in os.ilistdir(root) if entry[1] == 0x4000]
        for slug in sorted(folders, key=order):
            path = f"{root}/{slug}"
            if slug == "menu":
                continue
            if not (file_exists(f"{path}/__init__.py") or file_exists(f"{path}/__init__.mpy")):
                continue
            name = " ".join([capitalize(word) for word in slug.split("_")])
            icon_key = slug if slug in ICONS else "default"
            self.apps.append(App(len(self.apps), name, slug, path, icon_key in animated))

    @property
    def active(self):
        return self.apps[self.active_index]

    def move(self, step):
        index = max(0, min(len(self.apps) - 1, self.active_index + step))
        if index != self.active_index:
            self.active_index = index
            self.changed_at = badge.ticks

    def active_centre(self):
        app = self.active
        x = GRID_LEFT + app.column * (TILE + GAP) + HALF
        y = GRID_TOP + app.row * ROW_PITCH - self.target + HALF
        return x, y

    def update_scroll(self):
        row = self.active.row
        lowest = (row - VISIBLE_ROWS + 1) * ROW_PITCH
        self.target = max(0, min(max(self.target, lowest), row * ROW_PITCH))
        target = self.target

        now = badge.ticks
        dt = min(now - self.last_ticks, 200) if self.last_ticks is not None else 0
        self.last_ticks = now
        self.scroll += (target - self.scroll) * (1 - math.exp(-dt / SCROLL_MS))
        if abs(target - self.scroll) < 0.5:
            self.scroll = target

    def draw(self, tilt, opening=None):
        self.update_scroll()
        for app in self.apps:
            scale = opening.tile_scale(app) if opening else 1.0
            app.draw(self.scroll, tilt, app.index == self.active_index, scale)
        screen.clip = rect(0, 0, screen.width, screen.height)

    def __len__(self):
        return len(self.apps)
