import math
import os
import struct
from array import array

import ui
from gallery import GALLERY, crop, load_photo, tile_path
from icons import ICONS

TILES_PER_ROW = 4

APP_ORDER = (
    "badge",
    "contacts",
    "mona_paint",
    "flappy_mona",
    "snake",
    "mona_pet",
    "rogue",
    "life",
    "merge_conflict",
    "brattal",
    "pong",
    "iss",
    "mass_storage",
    "settings",
    "show",
)

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
ICON_FILE = "icon.png"
TILE_FILTER = image.BILINEAR
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


def load_picture(path):
    try:
        return image.load(f"{path}/{ICON_FILE}")
    except (OSError, ValueError):
        return None


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


class Tile:
    columns = 1
    rows = 1
    index = 0
    column = 0
    row = 0
    drop = 0

    def place(self):
        self.width = self.columns * TILE + (self.columns - 1) * GAP
        self.height = self.rows * TILE + (self.rows - 1) * GAP
        self.left = GRID_LEFT + self.column * (TILE + GAP)
        self.top = GRID_TOP + self.row * ROW_PITCH

    def bounds(self, scroll):
        # whole pixels, so the gaps between tiles hold while the scroll eases
        return self.left, self.top - round(scroll - self.drop), self.width, self.height

    def clip(self, left, top, width, height):
        if top + height < GRID_TOP or top > GRID_BOTTOM:
            return False
        clip_top = max(top, GRID_TOP)
        clip_bottom = min(top + height, GRID_BOTTOM)
        screen.clip = rect(left, clip_top, width, clip_bottom - clip_top)
        return True


class App(Tile):
    def __init__(self, ordinal, name, slug, path, animated=False):
        self.name = name
        self.slug = slug
        self.path = path
        self.animated = animated
        self.rgb = ui.PALETTE[ordinal % len(ui.PALETTE)]
        self.base = ui.shade(self.rgb, BASE_STRENGTH)
        self.tones = {
            "base": self.base,
            "mid": ui.shade(self.rgb, MID_STRENGTH),
            "high": ui.shade(self.rgb, HIGH_STRENGTH),
        }
        self.solid = color.rgb(*self.rgb)
        self.pattern = PATTERNS[(ordinal * 3) % len(PATTERNS)]
        self.icon_key = slug if slug in ICONS else "default"
        self.icon = build_icon(ICONS[self.icon_key])
        self.picture = None if slug in ICONS else load_picture(path)
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
        left, top, _, _ = self.bounds(scroll)
        centre_x = left + HALF
        centre_y = top + HALF
        size = TILE * scale
        left = centre_x - size / 2
        top = centre_y - size / 2
        if not self.clip(left, top, size, size):
            return

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
            antialias = screen.antialias
            screen.antialias = image.OFF
            for tone, element in self.pattern:
                element.transform = transform
                screen.pen = self.tones[tone]
                screen.shape(element)
            screen.antialias = antialias

        if self.picture is not None:
            icon_size = ICON_SIZE * scale
            icon_x = centre_x + tilt.x * ICON_SHIFT - icon_size / 2
            icon_y = centre_y + tilt.y * ICON_SHIFT - icon_size / 2
            screen.blit(self.picture, rect(0, 0, self.picture.width, self.picture.height), rect(icon_x, icon_y, icon_size, icon_size), TILE_FILTER)
            return

        icon = self.current_icon(selected)
        icon.transform = mat3().translate(
            centre_x + tilt.x * ICON_SHIFT,
            centre_y + tilt.y * ICON_SHIFT,
        ).scale(ICON_SIZE * scale)
        screen.pen = ui.white
        screen.shape(icon)


class Photo(Tile):
    def __init__(self, name, columns, rows, frame=None):
        self.name = name.replace("-", " ")
        self.slug = name
        self.path = None
        self.columns = columns
        self.rows = rows
        self.frame = frame
        self.image = None

    def load(self):
        if self.image is None:
            self.image = load_photo(self.slug)
        return self.image is not None

    def draw(self, scroll, tilt, selected, scale=1.0):
        if scale <= 0:
            return
        _, top, _, height = self.bounds(scroll)
        if top + height < GRID_TOP or top > GRID_BOTTOM or not self.load():
            return
        left, top, width, height = self.bounds(scroll)
        centre_x = left + width / 2
        centre_y = top + height / 2
        width *= scale
        height *= scale
        left = centre_x - width / 2
        top = centre_y - height / 2
        if not self.clip(left, top, width, height):
            return

        source = crop(self.image, width / scale, height / scale, tilt)
        screen.blit(self.image, source, rect(left, top, width, height), TILE_FILTER)
        if selected:
            border = BORDER * scale
            screen.pen = ui.white
            screen.rectangle(left, top, width, border)
            screen.rectangle(left, top + height - border, width, border)
            screen.rectangle(left, top + border, border, height - border * 2)
            screen.rectangle(left + width - border, top + border, border, height - border * 2)


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
        tiles = []
        for slug in sorted(folders, key=order):
            path = f"{root}/{slug}"
            if slug == "menu":
                continue
            if not (file_exists(f"{path}/__init__.py") or file_exists(f"{path}/__init__.mpy")):
                continue
            name = " ".join([capitalize(word) for word in slug.split("_")])
            icon_key = slug if slug in ICONS else "default"
            tiles.append(App(len(tiles), name, slug, path, icon_key in animated))

        from achievements import POSITION, Achievements, AchievementsTile
        self.achievements = Achievements()
        self.achievements_tile = AchievementsTile(self.achievements)
        self.picker = None
        tiles.insert(min(POSITION, len(tiles)), self.achievements_tile)

        for name, columns, rows, position, frame in GALLERY:
            if file_exists(tile_path(name)):
                tiles.insert(min(position, len(tiles)), Photo(name, columns, rows, frame))

        self.apps = self.pack(tiles)
        boundary = self.achievements_tile.row + self.achievements_tile.rows
        # (tile, first row, row after its last, below the picker) for the draw loop
        self.layout = [(tile, tile.row, tile.row + tile.rows, tile.row >= boundary) for tile in self.apps]
        self.want_column = 0
        self.want_row = 0
        self.photos = [tile for tile in self.apps if isinstance(tile, Photo)]
        for photo in self.photos:
            if photo.row <= VISIBLE_ROWS:
                photo.load()

    def preload_images(self):
        for photo in self.photos:
            photo.load()
        from achievements import preload_images
        preload_images(self.achievements)

    def load_photos(self, idle):
        top_row = int(self.scroll // ROW_PITCH) - 1
        bottom_row = top_row + VISIBLE_ROWS + 2
        for photo in self.photos:
            if photo.image is None and (idle or (photo.row <= bottom_row and photo.row + photo.rows > top_row)):
                photo.load()
                return

    @staticmethod
    def pack(tiles):
        taken = set()
        for tile in tiles:
            row = 0
            placed = False
            while not placed:
                for column in range(TILES_PER_ROW - tile.columns + 1):
                    cells = [(column + x, row + y) for x in range(tile.columns) for y in range(tile.rows)]
                    if not any(cell in taken for cell in cells):
                        tile.column = column
                        tile.row = row
                        taken.update(cells)
                        placed = True
                        break
                row += 1
        tiles.sort(key=lambda tile: (tile.row, tile.column))
        for index, tile in enumerate(tiles):
            tile.index = index
            tile.place()
        return tiles

    @property
    def active(self):
        return self.apps[self.active_index]

    def select(self, index):
        if index != self.active_index:
            self.active_index = index
            self.changed_at = badge.ticks

    def move(self, step):
        active = self.active
        row = self.want_row if active.row <= self.want_row < active.row + active.rows else active.row
        column = active.column + active.columns if step > 0 else active.column - 1
        beside = self.tile_at(column, row) if 0 <= column < TILES_PER_ROW else None
        if beside is not None:
            self.select(beside.index)
            self.want_row = row
        else:
            self.select(max(0, min(len(self.apps) - 1, self.active_index + step)))
            self.want_row = self.active.row
        self.want_column = self.active.column

    def tile_at(self, column, row):
        for tile in self.apps:
            if tile.column <= column < tile.column + tile.columns and tile.row <= row < tile.row + tile.rows:
                return tile
        return None

    def move_vertical(self, direction):
        active = self.active
        row = active.row - 1 if direction < 0 else active.row + active.rows
        last_row = max(tile.row + tile.rows for tile in self.apps)
        while 0 <= row < last_row:
            for offset in range(TILES_PER_ROW):
                for column in (self.want_column - offset, self.want_column + offset):
                    if 0 <= column < TILES_PER_ROW:
                        tile = self.tile_at(column, row)
                        if tile is not None:
                            self.select(tile.index)
                            self.want_row = row
                            return
            row += direction

    def open_picker(self, index=None):
        from achievements import Picker
        achievements = self.achievements
        if index is None:
            index = achievements.detecting()
        if index is None:
            index = achievements.shown if achievements.shown is not None else 0
        self.select(self.achievements_tile.index)
        self.picker = Picker(achievements, self.achievements_tile, index)

    def update_picker(self):
        if self.picker is not None and self.picker.done:
            self.picker = None

    def active_centre(self):
        if self.picker is not None and self.picker.is_open:
            return self.picker.item_centre(self.target)
        left, top, width, height = self.active.bounds(self.target)
        return left + width / 2, top + height / 2

    def update_scroll(self):
        row = self.active.row
        lowest = (row + self.active.rows - VISIBLE_ROWS) * ROW_PITCH
        highest = row * ROW_PITCH
        if self.picker is not None and self.picker.is_open:
            self.target = max(0, self.picker.focus_scroll())
        else:
            self.target = max(0, min(max(self.target, lowest), highest))
        target = self.target

        now = badge.ticks
        dt = min(now - self.last_ticks, 200) if self.last_ticks is not None else 0
        self.last_ticks = now
        if self.scroll == target:
            return
        self.scroll += (target - self.scroll) * (1 - math.exp(-dt / SCROLL_MS))
        if abs(target - self.scroll) < 0.5:
            self.scroll = target

    def draw(self, tilt, opening=None, covered=None):
        self.update_picker()
        self.update_scroll()
        picker = self.picker
        drop = picker.height() if picker is not None else 0
        selected = self.active_index if picker is None or not picker.is_open else None
        scroll = self.scroll
        # rows in view, with a GAP of slack for the opening's overshoot
        first_row = (scroll - GAP) / ROW_PITCH
        last_row = (scroll + GRID_BOTTOM - GRID_TOP + GAP) / ROW_PITCH
        dropped_first = first_row - drop / ROW_PITCH
        dropped_last = last_row - drop / ROW_PITCH
        for app, row, end, dropped in self.layout:
            if dropped:
                app.drop = drop
                if end < dropped_first or row > dropped_last:
                    continue
            else:
                app.drop = 0
                if end < first_row or row > last_row:
                    continue
            if covered is not None:
                left, top, width, height = app.bounds(self.scroll)
                if covered.x <= left and covered.y <= top and left + width <= covered.x + covered.w and top + height <= covered.y + covered.h:
                    continue
            scale = opening.tile_scale(app) if opening else 1.0
            app.draw(self.scroll, tilt, app.index == selected, scale)
        if picker is not None:
            picker.draw(self.scroll, tilt)
        screen.clip = rect(0, 0, screen.width, screen.height)

    def __len__(self):
        return len(self.apps)


shared_apps = {}


def shared(root):
    if root not in shared_apps:
        shared_apps[root] = Apps(root)
    return shared_apps[root]
