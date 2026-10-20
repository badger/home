from easing import easeOutCubic

GALLERY_DIR = "/system/apps/menu/photos"
TILE_DIR = GALLERY_DIR + "/tiles"

GALLERY = (
    ("mona-quilt", 2, 1, 7, (185, 100, 0.55)),
    ("ducky-quilt", 2, 2, 10, (235, 142, 0.76)),
    ("mona-ducky-blue", 2, 1, 13, (160, 148, 0.5)),
    ("mona-centered", 2, 2, 14, (160, 138, 0.66)),
    ("ducky-profile", 2, 2, 17, (200, 92, 1.0)),
)

SHIFT = 6
OPEN_MS = 280
PREFETCH_MS = 250


full_buffer = None
full_name = None


def tile_path(name):
    return f"{TILE_DIR}/{name}.png"


def load_photo(name):
    try:
        return image.load(tile_path(name))
    except OSError:
        return None


def load_full(name):
    global full_buffer, full_name
    if full_name == name:
        return full_buffer
    if full_buffer is None:
        full_buffer = image(screen.width, screen.height)
    full_name = None
    try:
        full_buffer.load_into(f"{GALLERY_DIR}/{name}.png")
    except OSError:
        return None
    full_name = name
    return full_buffer


def prefetch(name, selected_at):
    if full_name != name and badge.ticks - selected_at >= PREFETCH_MS:
        load_full(name)


def crop(photo, width, height, tilt, frame=None):
    centre_x, centre_y, zoom = frame if frame else (photo.width / 2, photo.height / 2, 1.0)
    scale = max(zoom, (width + SHIFT * 2) / photo.width, (height + SHIFT * 2) / photo.height)
    crop_width = width / scale
    crop_height = height / scale
    margin = SHIFT / scale
    x = min(max(centre_x - crop_width / 2, margin), photo.width - margin - crop_width)
    y = min(max(centre_y - crop_height / 2, margin), photo.height - margin - crop_height)
    return rect(x + tilt.x * margin, y + tilt.y * margin, crop_width, crop_height)


def mix(start, end, amount):
    return start + (end - start) * amount


class Viewer:
    def __init__(self, photo, scroll, tilt):
        self.photo = photo
        self.start = photo.bounds(scroll)
        full = load_full(photo.slug)
        if full is None:
            photo.load()
        self.image = full if full is not None else photo.image
        self.source = crop(self.image, self.start[2], self.start[3], tilt, photo.frame if full is not None else None)
        self.opened_at = None
        self.waited = False
        self.closing_at = None

    def close(self):
        if self.closing_at is None:
            self.closing_at = badge.ticks - round(OPEN_MS * (1 - self.progress()))

    def progress(self):
        if self.closing_at is not None:
            return max(0.0, 1 - (badge.ticks - self.closing_at) / OPEN_MS)
        if self.opened_at is None:
            return 0.0
        return min(1.0, (badge.ticks - self.opened_at) / OPEN_MS)

    @property
    def done(self):
        return self.closing_at is not None and self.progress() <= 0

    @property
    def covering(self):
        return self.closing_at is None and self.progress() >= 1

    def target(self):
        amount = easeOutCubic(self.progress())
        left, top, width, height = self.start
        return rect(
            mix(left, 0, amount),
            mix(top, 0, amount),
            mix(width, screen.width, amount),
            mix(height, screen.height, amount),
        )

    def draw(self):
        if self.opened_at is None and self.closing_at is None:
            if self.waited:
                self.opened_at = badge.ticks
            self.waited = True
        amount = easeOutCubic(self.progress())
        photo = self.image
        source = self.source
        target = self.target()
        area = rect(
            mix(source.x, 0, amount),
            mix(source.y, 0, amount),
            mix(source.w, photo.width, amount),
            mix(source.h, photo.height, amount),
        )
        screen.clip = rect(0, 0, screen.width, screen.height)
        screen.blit(photo, area, target, image.NEAREST)
