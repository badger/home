import math
from array import array

import ui
from app import BORDER, GAP, GRID_BOTTOM, GRID_LEFT, GRID_TOP, GRID_WIDTH, ICON_SHIFT, ROW_PITCH, TILE, TILE_FILTER, Tile, build_icon, polygon
from icons import ICONS
from silhouettes import SILHOUETTES
from badgeware import State
from easing import easeInOutCubic, easeOutBack, easeOutCubic

from aye_arr.nec.remotes.descriptor import RemoteDescriptor

TITLE = "Mona's Expedition"
LOCATIONS = (
    ("Mo's Diner", 0x11, "diner"),
    ("Under the Hood", 0x22, "frying-pan"),
    ("Creator Cabana", 0x33, "cabana"),
    ("Open Source Records", 0x44, "vinyl"),
    ("Makerspace", 0x55, "keycap"),
    ("Hack Your Badge", 0x66, "ascii-mona"),
    ("Demos & Donuts", 0x77, "ascii-donut"),
    ("Level Up Lounge", 0x88, "up-arrow"),
    ("CAB Member", 0x99, "cab"),
)
ACHIEVEMENT_NAMES = tuple(name for name, _, _ in LOCATIONS)
ACHIEVEMENT_CODES = tuple(code for _, code, _ in LOCATIONS)
ACHIEVEMENT_IMAGES = tuple(image for _, _, image in LOCATIONS)
HIDDEN_UNTIL_UNLOCKED = (8,)
TILE_COLOURS = {0: (139, 210, 231), 5: (255, 204, 255), 8: (140, 184, 56)}
IMAGE_DIR = "/system/apps/menu/awards"
IMAGE_FRACTION = 0.78
SMALL_IMAGE = 56
NEEDLE_REST = 45
NEEDLE_SHADOW = 2
SILHOUETTE_STRENGTH = 0.3
SILHOUETTE_KINDS = ("diner", "circle", "square", "circle", "keycap", "ascii-mona", "circle", "rounded", "circle")
LOCK_SIZE = 0.36
NEEDLE_SWING = 150
NEEDLE_STIFFNESS = 40
NEEDLE_DAMPING = 5
BEACON_ADDRESS = 0x45
RESET_CODE = 0xF0
POSITION = 2
DETECT_MS = 1200
WIGGLE_EVERY_MS = 1200
WIGGLE_MS = 650
WIGGLE_DEGREES = 12
WIGGLE_TURNS = 3
ECHO_SIZE = 34
ECHO_INSET = 4
ECHO_TOP_INSET = 10
ECHO_VIEW = 330
ECHO_BACK = (129, 148)
ECHO_FRONT = (193, 186)
ECHO_PARTICLES = ((266, 82, 30), (312, 196, 22), (226, 40, 18))
ECHO_BURST = (0.26, 0.7)
ECHO_PARTICLE_SPIN = 140
ECHO_STAR_RADIUS = 82
ECHO_ARC_OFFSET = (-33, -16)
ECHO_ARCS = ((113, 188, 234), (141, 201, 231))
ECHO_POP = (0.12, 0.34)
ECHO_SLOT = (0.72, 0.94)
ECHO_RADIATE = (0.3, 0.62)
ECHO_TURN = 72
ECHO_GROW = 0.12
ECHO_ARC_EDGE = 26
ECHO_ARC_CORE = 12
ECHO_STAR_EDGE = 10
ECHO_PERIOD_MS = 1800
ECHO_ARC_DELAY = 0.08
STAR_INNER = 0.48
MARQUEE_SPEED = 0.06
MARQUEE_PAUSE_MS = 900

NUMERAL_SIZE = 0.6
STRIP = TILE + GAP
OPEN_MS = 260
POP_MS = 300
STAGGER_MS = 45
SLIDE_MS = 90
NOTCH = 5
STRIP_CENTRE_Y = 110

locked_fill = color.rgb(30, 30, 36)
echo_edge = color.rgb(9, 40, 28)
echo_back = color.rgb(255, 255, 255, 184)
locked_ink = color.rgb(78, 78, 88)
shown_mark = color.rgb(95, 237, 131)

class Beacon(RemoteDescriptor):
    NAME = "AchievementBeacon"
    ADDRESS = BEACON_ADDRESS
    BUTTON_CODES = {number + 1: code for number, code in enumerate(ACHIEVEMENT_CODES)}
    BUTTON_CODES["reset"] = RESET_CODE


class Achievements:
    def __init__(self):
        data = {"unlocked": [], "shown": None}
        if not State.load("achievements", data):
            if file_exists("/state/awards.json"):
                State.load("awards", data)
                State.delete("awards")
            elif file_exists("/state/quest.json"):
                quest = {"completed": []}
                State.load("quest", quest)
                data["unlocked"] = [number - 1 for number in quest["completed"] if 1 <= number <= len(ACHIEVEMENT_CODES)]
                if data["unlocked"]:
                    data["shown"] = data["unlocked"][-1]
            State.save("achievements", data)
        self.unlocked = {index for index in data["unlocked"] if 0 <= index < len(ACHIEVEMENT_CODES)}
        self.shown = data["shown"] if data["shown"] in self.unlocked else None
        self.pending = None
        self.beacon = None
        self.detected = None
        self.detected_at = 0
        self.detected_since = 0

    def __len__(self):
        return len(ACHIEVEMENT_CODES)

    def visible(self):
        return [index for index in range(len(ACHIEVEMENT_CODES)) if index not in HIDDEN_UNTIL_UNLOCKED or index in self.unlocked]

    def save(self):
        State.save("achievements", {"unlocked": sorted(self.unlocked), "shown": self.shown})

    def show(self, index):
        if index in self.unlocked and index != self.shown:
            self.shown = index
            self.save()

    def received(self, key):
        if key == "reset":
            self.reset()
            return
        if key - 1 in self.unlocked:
            self.detect(key - 1)
        else:
            self.unlock(key)

    def detect(self, index):
        now = badge.ticks
        if self.detecting() != index:
            self.detected_since = now
        self.detected = index
        self.detected_at = now

    def detecting(self):
        if self.detected is not None and badge.ticks - self.detected_at < DETECT_MS:
            return self.detected
        return None

    def reset(self):
        self.unlocked = set()
        self.shown = None
        self.pending = None
        self.save()

    def unlock(self, number):
        index = number - 1
        if 0 <= index < len(ACHIEVEMENT_CODES) and index not in self.unlocked:
            self.unlocked.add(index)
            if self.shown is None:
                self.shown = index
            self.save()
            self.pending = index

    def listen(self):
        from badgeware.ir import ir
        self.beacon = ir.bind(Beacon())
        self.beacon.on_known = self.received

    def close(self):
        if self.beacon is None:
            return
        from badgeware.ir import ir
        ir.close()
        self.beacon = None


award_images = {}


def award_image(index, size):
    slug = ACHIEVEMENT_IMAGES[index] if index is not None else None
    if slug is None:
        return None
    suffix = "-small" if size <= SMALL_IMAGE else ""
    return load_award(slug + suffix)


def preload_images(achievements):
    for key in ("compass", "compass-needle", "compass-shadow"):
        load_award(key)
    if achievements.shown is not None:
        award_image(achievements.shown, TILE * 2)
    for index in achievements.unlocked:
        award_image(index, SMALL_IMAGE)


def load_award(key):
    if key not in award_images:
        try:
            award_images[key] = image.load(f"{IMAGE_DIR}/{key}.png")
        except OSError:
            award_images[key] = None
    return award_images[key]


def draw_award_image(picture, x, y, size, angle):
    if angle:
        scale = size / picture.width
        transform = mat3().translate(x, y).rotate(angle).scale(scale, scale).translate(-picture.width / 2, -picture.height / 2)
        outline = shape.rectangle(0, 0, picture.width, picture.height)
        outline.transform = transform
        screen.pen = brush.image(picture, mat3(), TILE_FILTER)
        screen.shape(outline)
    else:
        screen.blit(picture, rect(x - size / 2, y - size / 2, size, size), TILE_FILTER)


lock_shape = None


def clamp01(value):
    return max(0.0, min(1.0, value))


def wiggle(age):
    local = age % WIGGLE_EVERY_MS
    if local >= WIGGLE_MS:
        return 0.0
    progress = local / WIGGLE_MS
    return WIGGLE_DEGREES * math.sin(progress * WIGGLE_TURNS * 2 * math.pi) * (1 - progress)


def build_star():
    points = []
    for step in range(10):
        angle = step * math.pi / 5
        radius = 1.0 if step % 2 == 0 else STAR_INNER
        points.extend((radius * math.sin(angle), -radius * math.cos(angle)))
    return shape.custom(array("f", points))


star_shape = None


def draw_star(x, y, radius, angle, fill, outline):
    global star_shape
    if star_shape is None:
        star_shape = build_star()
    star_shape.transform = mat3().translate(x, y).rotate(angle).scale(radius + outline)
    screen.pen = echo_edge
    screen.shape(star_shape)
    star_shape.transform = mat3().translate(x, y).rotate(angle).scale(radius)
    screen.pen = fill
    screen.shape(star_shape)


def draw_echo(right, top, scale):
    unit = ECHO_SIZE * scale / ECHO_VIEW
    left = right - ECHO_SIZE * scale
    phase = (badge.ticks % ECHO_PERIOD_MS) / ECHO_PERIOD_MS
    pop_out = clamp01((phase - ECHO_POP[0]) / (ECHO_POP[1] - ECHO_POP[0]))
    slot_in = clamp01((phase - ECHO_SLOT[0]) / (ECHO_SLOT[1] - ECHO_SLOT[0]))
    travel = easeOutBack(pop_out) * (1 - easeInOutCubic(slot_in))
    spin = ECHO_TURN * easeInOutCubic(clamp01((phase - ECHO_POP[0]) / (ECHO_SLOT[1] - ECHO_POP[0])))

    back_x, back_y = ECHO_BACK
    out_x, out_y = ECHO_FRONT
    front_x = back_x + (out_x - back_x) * travel
    front_y = back_y + (out_y - back_y) * travel

    for index, (radius, start, end) in enumerate(ECHO_ARCS):
        local = clamp01((phase - ECHO_RADIATE[0] - index * ECHO_ARC_DELAY) / (ECHO_RADIATE[1] - ECHO_RADIATE[0]))
        alpha = round(255 * math.sin(math.pi * local))
        if alpha <= 0:
            continue
        x = left + (front_x + ECHO_ARC_OFFSET[0]) * unit
        y = top + (front_y + ECHO_ARC_OFFSET[1]) * unit
        edge = ECHO_ARC_EDGE * unit / 2
        core = ECHO_ARC_CORE * unit / 2
        screen.pen = color.rgb(9, 40, 28, alpha)
        screen.shape(shape.arc(x, y, radius * unit - edge, radius * unit + edge, start, end))
        screen.pen = color.rgb(255, 255, 255, alpha)
        screen.shape(shape.arc(x, y, radius * unit - core, radius * unit + core, start, end))

    edge = ECHO_STAR_EDGE * unit
    draw_star(left + back_x * unit, top + back_y * unit, ECHO_STAR_RADIUS * unit, 0, echo_back, edge)
    burst = clamp01((phase - ECHO_BURST[0]) / (ECHO_BURST[1] - ECHO_BURST[0]))
    if 0 < burst < 1:
        flight = easeOutCubic(burst)
        size = 1 - burst
        for target_x, target_y, radius in ECHO_PARTICLES:
            x = out_x + (target_x - out_x) * flight
            y = out_y + (target_y - out_y) * flight
            draw_star(left + x * unit, top + y * unit, radius * size * unit, burst * ECHO_PARTICLE_SPIN, ui.white, edge * 0.7 * size)
    grow = 1 + ECHO_GROW * math.sin(math.pi * travel) if travel > 0 else 1
    draw_star(left + front_x * unit, top + front_y * unit, ECHO_STAR_RADIUS * unit * grow, spin, ui.white, edge)


def draw_marquee(text, started):
    screen.font = ui.title_font
    screen.pen = ui.white
    width, _ = screen.measure_text(text)
    elapsed = max(0, badge.ticks - started - MARQUEE_PAUSE_MS)
    shift = elapsed * MARQUEE_SPEED
    if shift <= width + ui.TITLE_X:
        x = ui.TITLE_X - shift
    else:
        x = screen.width - (shift - width - ui.TITLE_X) % (screen.width + width)
    screen.clip = rect(0, ui.RIBBON_TOP, screen.width, screen.height - ui.RIBBON_TOP)
    screen.text(text, round(x), ui.TITLE_Y)
    screen.clip = rect(0, 0, screen.width, screen.height)
silhouette_shapes = {}


def silhouette_shape(kind):
    if kind not in silhouette_shapes:
        if kind == "circle":
            outline = shape.circle(0, 0, 0.5)
        elif kind == "square":
            outline = shape.rectangle(-0.5, -0.5, 1, 1)
        elif kind == "rounded":
            outline = shape.rounded_rectangle(-0.5, -0.5, 1, 1, 0.15)
        else:
            outline = build_icon((SILHOUETTES[kind],))
        silhouette_shapes[kind] = outline
    return silhouette_shapes[kind]


def location_rgb(index):
    return ui.PALETTE[index % len(ui.PALETTE)]


def tile_fill(index, unlocked):
    rgb = TILE_COLOURS.get(index) if unlocked else None
    return color.rgb(*rgb) if rgb else ui.shade(location_rgb(index), 0.42)


def draw_locked(index, x, y, size):
    global lock_shape
    if index is not None:
        outline = silhouette_shape(SILHOUETTE_KINDS[index])
        outline.transform = mat3().translate(x, y).scale(size * IMAGE_FRACTION)
        screen.pen = ui.shade(location_rgb(index), SILHOUETTE_STRENGTH)
        screen.shape(outline)
    if lock_shape is None:
        lock_shape = build_icon(ICONS["lock"])
    lock_shape.transform = mat3().translate(x, y).scale(size * LOCK_SIZE)
    screen.pen = ui.white
    screen.shape(lock_shape)


def draw_achievement(index, unlocked, left, top, size, tilt, selected, scale=1.0, angle=0.0):
    if index is not None:
        rgb = location_rgb(index)
        fill = tile_fill(index, unlocked)
        glow = ui.shade(rgb, 0.62)
        ink = ui.white
    else:
        fill = glow = locked_fill
        ink = locked_ink

    if selected:
        border = BORDER * scale
        screen.pen = ui.white
        screen.rectangle(left, top, size, size)
        screen.pen = fill
        screen.rectangle(left + border, top + border, size - border * 2, size - border * 2)
    else:
        screen.pen = fill
        screen.rectangle(left, top, size, size)

    centre_x = left + size / 2
    centre_y = top + size / 2
    shift = ICON_SHIFT * size / TILE
    picture_size = size * IMAGE_FRACTION
    if not unlocked and index is not None:
        draw_locked(index, centre_x + tilt.x * shift, centre_y + tilt.y * shift, size)
        return
    picture = award_image(index, picture_size) if unlocked else None
    if picture is not None:
        draw_award_image(picture, centre_x + tilt.x * shift, centre_y + tilt.y * shift, picture_size, angle)
        return

    if unlocked:
        screen.pen = glow
        screen.shape(shape.circle(centre_x - tilt.x * ICON_SHIFT * 2, centre_y - tilt.y * ICON_SHIFT * 2, size * 0.36))

    label = str(index + 1) if index is not None else "?"
    screen.font = ui.title_font
    screen.pen = ink
    _, base_height = screen.measure_text(label)
    text_scale = max(1, round(size * NUMERAL_SIZE / base_height))
    width, height = screen.measure_text(label, font_size=text_scale)
    x = centre_x + tilt.x * shift
    y = centre_y + tilt.y * shift
    if angle:
        transform = mat3().translate(x, y).rotate(angle).translate(-width / 2, -height / 2)
        screen.text(label, 0, 0, text_scale, transform=transform)
    else:
        screen.text(label, round(x - width / 2), round(y - height / 2), text_scale)


needle_layers = None


def build_needle_layers(needle):
    outline = shape.rectangle(0, 0, needle.width, needle.height)
    shadow = load_award("compass-shadow")
    layers = [(brush.image(needle, mat3(), image.NEAREST), 0)]
    if shadow is not None:
        layers.insert(0, (brush.image(shadow, mat3(), image.NEAREST), NEEDLE_SHADOW))
    return outline, layers


def draw_compass(left, top, size, tilt, selected, scale, needle_angle):
    global needle_layers
    base = load_award("compass")
    needle = load_award("compass-needle")
    if base is None or needle is None:
        draw_achievement(None, False, left, top, size, tilt, selected, scale)
        return
    if selected:
        border = BORDER * scale
        screen.pen = ui.white
        screen.rectangle(left, top, size, size)
        screen.pen = locked_fill
        screen.rectangle(left + border, top + border, size - border * 2, size - border * 2)
    else:
        screen.pen = locked_fill
        screen.rectangle(left, top, size, size)
    shift = ICON_SHIFT * size / TILE
    picture_size = size * IMAGE_FRACTION
    pixel = picture_size / base.width
    picture_left = left + (size - picture_size) / 2 + tilt.x * shift
    picture_top = top + (size - picture_size) / 2 + tilt.y * shift
    screen.blit(base, rect(picture_left, picture_top, picture_size, picture_size), TILE_FILTER)
    centre_x = picture_left + picture_size / 2
    centre_y = picture_top + picture_size / 2
    if needle_layers is None:
        needle_layers = build_needle_layers(needle)
    outline, layers = needle_layers
    # the needle images have transparent borders, so the outline's edges need no antialiasing
    antialias = screen.antialias
    screen.antialias = image.OFF
    for layer, offset in layers:
        offset *= pixel
        outline.transform = mat3().translate(centre_x + offset, centre_y + offset).rotate(NEEDLE_REST + needle_angle).scale(pixel, pixel).translate(-needle.width / 2, -needle.height / 2)
        screen.pen = layer
        screen.shape(outline)
    screen.antialias = antialias


class AchievementsTile(Tile):
    columns = 2
    rows = 2

    def __init__(self, achievements):
        self.achievements = achievements
        self.name = TITLE
        self.slug = "achievements"
        self.path = None
        self.needle_angle = 0.0
        self.needle_speed = 0.0
        self.needle_ticks = None
        self.count = (None, "")

    def swing_needle(self, tilt):
        now = badge.ticks
        dt = min(now - self.needle_ticks, 100) / 1000 if self.needle_ticks is not None else 0
        self.needle_ticks = now
        target = tilt.x * NEEDLE_SWING
        self.needle_speed += ((target - self.needle_angle) * NEEDLE_STIFFNESS - self.needle_speed * NEEDLE_DAMPING) * dt
        self.needle_angle += self.needle_speed * dt

    def draw(self, scroll, tilt, selected, scale=1.0):
        if scale <= 0:
            return
        left, top, width, height = self.bounds(scroll)
        centre_x = left + width / 2
        centre_y = top + height / 2
        size = width * scale
        left = centre_x - size / 2
        top = centre_y - size / 2
        if not self.clip(left, top, size, size):
            return

        achievements = self.achievements
        shown = achievements.shown
        if shown is None:
            self.swing_needle(tilt)
            draw_compass(left, top, size, tilt, selected, scale, self.needle_angle)
        else:
            draw_achievement(shown, True, left, top, size, tilt, selected, scale)

        if achievements.detecting() is not None:
            draw_echo(left + size - ECHO_INSET * scale, top + ECHO_TOP_INSET * scale, scale)

        unlocked, count = self.count
        if unlocked != len(achievements.unlocked):
            unlocked = len(achievements.unlocked)
            count = f"{unlocked} / {len(achievements.visible())}"
            self.count = (unlocked, count)
        screen.font = ui.status_font
        screen.pen = ui.dim_white
        screen.text(count, left + 8 * scale, top + size - 22 * scale)


class Picker:
    def __init__(self, achievements, tile, index):
        self.achievements = achievements
        self.tile = tile
        self.slots = achievements.visible()
        self.slot = self.slots.index(index) if index in self.slots else 0
        self.index = self.slots[self.slot]
        self.changed_at = badge.ticks
        self.opened_at = badge.ticks
        self.closing_at = None
        self.offset = self.target_offset()
        self.last_ticks = None

    def progress(self):
        if self.closing_at is not None:
            return max(0.0, 1 - (badge.ticks - self.closing_at) / OPEN_MS)
        return min(1.0, (badge.ticks - self.opened_at) / OPEN_MS)

    @property
    def is_open(self):
        return self.closing_at is None

    @property
    def done(self):
        return self.closing_at is not None and self.progress() <= 0

    def close(self):
        if self.closing_at is None:
            self.closing_at = badge.ticks - round(OPEN_MS * (1 - self.progress()))

    def height(self):
        return STRIP * easeOutCubic(self.progress())

    def move(self, step):
        slot = max(0, min(len(self.slots) - 1, self.slot + step))
        if slot != self.slot:
            self.slot = slot
            self.index = self.slots[slot]
            self.changed_at = badge.ticks

    def choose(self):
        if self.index not in self.achievements.unlocked:
            return False
        self.achievements.show(self.index)
        return True

    def title(self):
        return ACHIEVEMENT_NAMES[self.index]

    def message(self):
        detected = self.achievements.detecting()
        if detected is None:
            return None
        return ui.lowercase(ACHIEVEMENT_NAMES[detected] + ": Already Unlocked"), max(self.achievements.detected_since, self.opened_at)

    def target_offset(self):
        width = len(self.slots) * STRIP - GAP
        left = self.slot * STRIP
        return max(0, min(left - (GRID_WIDTH - TILE) / 2, width - GRID_WIDTH))

    def strip_top(self, scroll):
        _, top, _, height = self.tile.bounds(scroll)
        return top + height + GAP

    def focus_scroll(self):
        tile = self.tile
        return GRID_TOP + (tile.row + tile.rows) * ROW_PITCH + TILE / 2 - STRIP_CENTRE_Y

    def item_centre(self, scroll):
        x = GRID_LEFT + self.slot * STRIP - self.target_offset() + TILE / 2
        return x, self.strip_top(scroll) + TILE / 2

    def draw(self, scroll, tilt):
        now = badge.ticks
        dt = min(now - self.last_ticks, 200) if self.last_ticks is not None else 0
        self.last_ticks = now
        target = self.target_offset()
        self.offset += (target - self.offset) * (1 - math.exp(-dt / SLIDE_MS))

        shown = self.height() - GAP
        if shown <= 0:
            return
        top = self.strip_top(scroll)
        clip_top = max(top, GRID_TOP)
        clip_bottom = min(top + shown, GRID_BOTTOM)
        if clip_bottom <= clip_top:
            return

        tile_left, _, tile_width, _ = self.tile.bounds(scroll)
        notch_x = tile_left + tile_width / 2
        screen.clip = rect(0, max(top - GAP, GRID_TOP), screen.width, clip_bottom - max(top - GAP, GRID_TOP))
        screen.pen = ui.white
        screen.shape(polygon(notch_x - NOTCH, top, notch_x + NOTCH, top, notch_x, top - GAP))

        screen.clip = rect(GRID_LEFT, clip_top, GRID_WIDTH, clip_bottom - clip_top)
        centre_y = top + TILE / 2
        detected = self.achievements.detecting()
        for slot, index in enumerate(self.slots):
            left = GRID_LEFT + slot * STRIP - self.offset
            if left + TILE < GRID_LEFT or left > GRID_LEFT + GRID_WIDTH:
                continue
            scale = self.item_scale(slot)
            if scale <= 0:
                continue
            size = TILE * scale
            item_left = left + (TILE - size) / 2
            item_top = centre_y - size / 2
            unlocked = index in self.achievements.unlocked
            angle = wiggle(now - self.achievements.detected_since) if index == detected else 0.0
            draw_achievement(index, unlocked, item_left, item_top, size, tilt, index == self.index, scale, angle)
            if index == self.achievements.shown:
                screen.pen = shown_mark
                screen.shape(shape.circle(item_left + size - 9 * scale, item_top + 9 * scale, 4 * scale))

    def item_scale(self, slot):
        if self.closing_at is not None:
            return easeOutCubic(max(0.0, min(1.0, self.progress() * 1.6 - 0.6)))
        local = (badge.ticks - self.opened_at - abs(slot - self.slot) * STAGGER_MS) / POP_MS
        if local <= 0:
            return 0.0
        if local >= 1:
            return 1.0
        return easeOutBack(local)
