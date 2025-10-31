"""
badge_simulator.py
====================

Run GitHub Badger 2350 games locally via Pygame by simulating the
`badgeware` API (screen, io, brushes, shapes, Image/SpriteSheet).
"""

import argparse
import importlib.util
import json
import math
import os
import sys
import traceback
from types import ModuleType

try:
    import pygame  # type: ignore
except ImportError:
    raise SystemExit(
        "Pygame is required to run the local simulator. Install with: pip install pygame"
    )

# -----------------------------------------------------------------------------
# Virtual “/system” mapping (NO filesystem changes)
# -----------------------------------------------------------------------------

SIM_ROOT = None


def _find_sim_root(start_dir: str) -> str:
    """Walk upward to find a directory that contains 'apps'. Fallback to start_dir."""
    cur = os.path.abspath(start_dir)
    for _ in range(8):
        if os.path.isdir(os.path.join(cur, "apps")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return os.path.abspath(start_dir)


def map_system_path(p: str) -> str:
    """Map '/system/...' -> '<SIM_ROOT>/...'. Leave other paths unchanged."""
    global SIM_ROOT
    if SIM_ROOT is None:
        SIM_ROOT = _find_sim_root(os.getcwd())
    if p.startswith("/system"):
        tail = p[len("/system"):].lstrip("/\\")
        return os.path.join(SIM_ROOT, tail) if tail else SIM_ROOT
    return p


# Intercept os.chdir so games can safely do os.chdir("/system/apps/foo")
_real_chdir = os.chdir


def _safe_chdir(path: str):
    _real_chdir(map_system_path(path))


os.chdir = _safe_chdir  # type: ignore

# Allow `os.listdir("/system/...")`
_real_listdir = os.listdir


def _safe_listdir(path="."):
    if isinstance(path, (str, bytes, os.PathLike)):
        fs_path = os.fspath(path)
        if isinstance(fs_path, str):
            return _real_listdir(map_system_path(fs_path))
        return _real_listdir(fs_path)
    return _real_listdir(path)


os.listdir = _safe_listdir  # type: ignore

# -----------------------------------------------------------------------------
# Badgeware API stubs
# -----------------------------------------------------------------------------

class _Shape:
    """Base shape that supports optional affine transforms."""

    __slots__ = ("transform",)

    def __init__(self) -> None:
        self.transform = None  # optional Matrix

    def points(self):
        raise NotImplementedError

    def stroke(self, width: float):
        return _StrokedShape(self, width)


class _StrokedShape(_Shape):
    __slots__ = ("shape", "width")

    def __init__(self, shape: _Shape, width: float) -> None:
        super().__init__()
        self.shape = shape
        self.width = max(0.0, float(width))
        if getattr(shape, "transform", None) is not None:
            self.transform = shape.transform


class _Rectangle(_Shape):
    __slots__ = ("x", "y", "w", "h")

    def __init__(self, x: float, y: float, w: float, h: float) -> None:
        super().__init__()
        self.x, self.y, self.w, self.h = x, y, w, h

    def points(self):
        x, y, w, h = self.x, self.y, self.w, self.h
        return [
            (x, y),
            (x + w, y),
            (x + w, y + h),
            (x, y + h),
        ]


class _RoundedRectangle(_Rectangle):
    __slots__ = ("radii",)

    def __init__(self, x: float, y: float, w: float, h: float, radius: float, *corner_radii) -> None:
        super().__init__(x, y, w, h)
        if corner_radii:
            radii = list(corner_radii[:4])
            if len(radii) < 4:
                radii.extend([radius] * (4 - len(radii)))
        else:
            radii = [radius] * 4
        self.radii = [max(0.0, float(r)) for r in radii]

    def points(self):
        x, y, w, h = self.x, self.y, self.w, self.h
        radii = [
            min(r, w / 2.0, h / 2.0) if r > 0 else 0.0
            for r in self.radii
        ]

        corner_points = [
            (x, y),
            (x + w, y),
            (x + w, y + h),
            (x, y + h),
        ]

        corners = [
            (x + radii[0], y + radii[0], 180, 270, radii[0]),                 # top-left
            (x + w - radii[1], y + radii[1], 270, 360, radii[1]),             # top-right
            (x + w - radii[2], y + h - radii[2], 0, 90, radii[2]),            # bottom-right
            (x + radii[3], y + h - radii[3], 90, 180, radii[3]),              # bottom-left
        ]

        points = []
        for idx, (cx, cy, start_deg, end_deg, radius) in enumerate(corners):
            if radius <= 0:
                pt = corner_points[idx]
                if points and points[-1] == pt:
                    continue
                points.append(pt)
                continue

            segments = max(4, int(radius * 2))
            for step in range(segments + 1):
                if idx > 0 and step == 0:
                    continue
                t = step / segments
                angle = math.radians(start_deg + (end_deg - start_deg) * t)
                px = cx + radius * math.cos(angle)
                py = cy + radius * math.sin(angle)
                points.append((px, py))
        return points


class _Circle(_Shape):
    __slots__ = ("x", "y", "radius", "segments")

    def __init__(self, x: float, y: float, radius: float, segments: int = 32) -> None:
        super().__init__()
        self.x, self.y, self.radius = x, y, radius
        self.segments = max(12, int(segments))

    def points(self):
        pts = []
        for i in range(self.segments):
            theta = (2.0 * math.pi * i) / self.segments
            pts.append(
                (
                    self.x + self.radius * math.cos(theta),
                    self.y + self.radius * math.sin(theta),
                )
            )
        return pts


class _Squircle(_Shape):
    __slots__ = ("x", "y", "radius", "n", "segments")

    def __init__(self, x: float, y: float, radius: float, n: float = 4.0, segments: int = 64) -> None:
        super().__init__()
        self.x, self.y, self.radius = x, y, radius
        self.n = n if n else 4.0
        self.segments = max(24, int(segments))

    def points(self):
        pts = []
        exponent = 2.0 / max(1e-3, float(self.n))
        for i in range(self.segments):
            theta = (2.0 * math.pi * i) / self.segments
            cos_t = math.cos(theta)
            sin_t = math.sin(theta)
            px = self.radius * math.copysign(abs(cos_t) ** exponent, cos_t)
            py = self.radius * math.copysign(abs(sin_t) ** exponent, sin_t)
            pts.append((self.x + px, self.y + py))
        return pts


class _Line(_Shape):
    __slots__ = ("x1", "y1", "x2", "y2", "thickness")

    def __init__(self, x1: float, y1: float, x2: float, y2: float, thickness: float = 1.0) -> None:
        super().__init__()
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        self.thickness = thickness


class _RegularPolygon(_Shape):
    __slots__ = ("x", "y", "radius", "sides")

    def __init__(self, x: float, y: float, radius: float, sides: int) -> None:
        super().__init__()
        self.x, self.y, self.radius = x, y, radius
        self.sides = max(3, int(sides))

    def points(self):
        pts = []
        for i in range(self.sides):
            angle_deg = (360.0 / self.sides) * i
            angle = math.radians(angle_deg)
            px = self.x + self.radius * math.sin(angle)
            py = self.y + self.radius * math.cos(angle)
            pts.append((px, py))
        return pts


class _Arc(_Shape):
    __slots__ = ("x", "y", "radius", "start_deg", "end_deg", "thickness")

    def __init__(self, x: float, y: float, radius: float, start_deg: float, end_deg: float, thickness: float = 1.0) -> None:
        super().__init__()
        self.x, self.y, self.radius = x, y, radius
        self.start_deg = float(start_deg)
        self.end_deg = float(end_deg)
        self.thickness = max(1.0, float(thickness))

    def points(self):
        start = self.start_deg
        end = self.end_deg
        if end < start:
            end += 360.0
        span = max(0.0, end - start)
        segments = max(8, int(self.radius * max(1.0, span / 45.0)))
        pts = []
        for i in range(segments + 1):
            t = i / segments if segments else 0.0
            angle = math.radians(start + span * t)
            px = self.x + self.radius * math.sin(angle)
            py = self.y + self.radius * math.cos(angle)
            pts.append((px, py))
        return pts

    def stroke(self, width: float):
        stroked = _Arc(self.x, self.y, self.radius, self.start_deg, self.end_deg, width)
        if getattr(self, "transform", None) is not None:
            stroked.transform = self.transform
        return stroked


class _Pie(_Arc):
    __slots__ = ()

    def __init__(self, x: float, y: float, radius: float, start_deg: float, end_deg: float) -> None:
        super().__init__(x, y, radius, start_deg, end_deg, thickness=1.0)

    def points(self):
        pts = super().points()
        if pts:
            return [(self.x, self.y)] + pts
        return [(self.x, self.y)]


def _round_points(points):
    return [(int(round(px)), int(round(py))) for px, py in points]


def _render_shape(surface, color, shape, transform=None, offset=(0.0, 0.0)):
    base_shape = shape
    stroke_width = None

    if isinstance(shape, _StrokedShape):
        base_shape = shape.shape
        stroke_width = shape.width
        if transform is None:
            transform = getattr(shape, "transform", None)

    if transform is None:
        transform = getattr(base_shape, "transform", None)

    ox, oy = offset

    if isinstance(base_shape, _Line):
        x1, y1 = base_shape.x1, base_shape.y1
        x2, y2 = base_shape.x2, base_shape.y2
        if isinstance(transform, Matrix):
            x1, y1 = transform.transformed_point(x1, y1)
            x2, y2 = transform.transformed_point(x2, y2)
        width = stroke_width if stroke_width is not None else base_shape.thickness
        pygame.draw.line(
            surface,
            color,
            (int(round(x1 + ox)), int(round(y1 + oy))),
            (int(round(x2 + ox)), int(round(y2 + oy))),
            max(1, int(round(width))),
        )
        return

    if isinstance(base_shape, _Pie):
        points = base_shape.points()
        if isinstance(transform, Matrix):
            points = [transform.transformed_point(px, py) for px, py in points]
        points = [(px + ox, py + oy) for px, py in points]
        if not points:
            return
        if stroke_width is not None and stroke_width > 0:
            pygame.draw.polygon(
                surface,
                color,
                _round_points(points),
                max(1, int(round(stroke_width))),
            )
        else:
            pygame.draw.polygon(surface, color, _round_points(points))
        return

    if isinstance(base_shape, _Arc):
        points = base_shape.points()
        if isinstance(transform, Matrix):
            points = [transform.transformed_point(px, py) for px, py in points]
        points = [(px + ox, py + oy) for px, py in points]
        if len(points) >= 2:
            width = stroke_width if stroke_width is not None else base_shape.thickness
            pygame.draw.lines(
                surface,
                color,
                False,
                _round_points(points),
                max(1, int(round(width))),
            )
        return

    if not hasattr(base_shape, "points"):
        return

    points = list(base_shape.points())
    if not points:
        return

    if isinstance(transform, Matrix):
        points = [transform.transformed_point(px, py) for px, py in points]
    points = [(px + ox, py + oy) for px, py in points]

    if stroke_width is not None and stroke_width > 0:
        pygame.draw.polygon(
            surface,
            color,
            _round_points(points),
            max(1, int(round(stroke_width))),
        )
    else:
        pygame.draw.polygon(surface, color, _round_points(points))


class _SurfaceTarget:
    __slots__ = ("_surface", "brush", "font", "antialias")

    def __init__(self, surface: pygame.Surface):
        self._surface = surface
        self.brush = brushes.color(255, 255, 255)
        self.font = pygame.font.Font(None, 14)
        self.antialias = 0

    def _norm_color(self, c):
        if c is None:
            return (0, 0, 0, 255)
        if isinstance(c, int):
            return (c, c, c, 255)
        return c

    def _unwrap(self, image):
        return image._surface if isinstance(image, Image) else image

    def clear(self, color=None) -> None:
        fill_color = self._norm_color(color if color is not None else self.brush)
        self._surface.fill(fill_color)

    def draw(self, shape: _Shape) -> None:
        color = self._norm_color(self.brush)
        _render_shape(self._surface, color, shape)

    def blit(self, image, x: float, y: float, transform: "Matrix" = None) -> None:
        if isinstance(transform, Matrix):
            x, y = transform.transformed_point(x, y)
        self._surface.blit(self._unwrap(image), (int(round(x)), int(round(y))))

    def scale_blit(self, image, x: float, y: float, w: int, h: int, transform: "Matrix" = None) -> None:
        if isinstance(transform, Matrix):
            x, y = transform.transformed_point(x, y)
        src = self._unwrap(image)
        new_w = max(1, abs(w))
        new_h = max(1, abs(h))
        scaled = pygame.transform.scale(src, (new_w, new_h))
        if w < 0:
            scaled = pygame.transform.flip(scaled, True, False)
        if h < 0:
            scaled = pygame.transform.flip(scaled, False, True)
        self._surface.blit(scaled, (int(round(x)), int(round(y))))

    def text(self, text: str, x: float, y: float) -> None:
        font = self.font
        color = self._norm_color(self.brush)
        surf = font.render(str(text), True, color)
        self._surface.blit(surf, (int(round(x)), int(round(y))))

    def measure_text(self, text: str) -> tuple:
        font = self.font
        if hasattr(font, "size"):
            return font.size(str(text))
        surf = font.render(str(text), True, (0, 0, 0))
        return surf.get_size()

    def window(self, x: float, y: float, width: float, height: float):
        return _Window(self, x, y, width, height)


class shapes:
    @staticmethod
    def rectangle(x: float, y: float, w: float, h: float) -> _Rectangle:
        return _Rectangle(x, y, w, h)

    @staticmethod
    def rounded_rectangle(x: float, y: float, w: float, h: float, radius: float, *corner_radii) -> _RoundedRectangle:
        return _RoundedRectangle(x, y, w, h, radius, *corner_radii)

    @staticmethod
    def circle(x: float, y: float, radius: float) -> _Circle:
        return _Circle(x, y, radius)

    @staticmethod
    def squircle(x: float, y: float, radius: float, n: float = 4.0) -> _Squircle:
        return _Squircle(x, y, radius, n)

    @staticmethod
    def line(x1: float, y1: float, x2: float, y2: float, thickness: float = 1.0) -> _Line:
        return _Line(x1, y1, x2, y2, thickness)

    @staticmethod
    def regular_polygon(x: float, y: float, radius: float, sides: int) -> _RegularPolygon:
        return _RegularPolygon(x, y, radius, sides)

    @staticmethod
    def arc(x: float, y: float, radius: float, start_deg: float, end_deg: float) -> _Arc:
        return _Arc(x, y, radius, start_deg, end_deg)

    @staticmethod
    def pie(x: float, y: float, radius: float, start_deg: float, end_deg: float) -> _Pie:
        return _Pie(x, y, radius, start_deg, end_deg)


class brushes:
    @staticmethod
    def color(r, g=None, b=None, a=255) -> tuple:
        def _clamp(value):
            return max(0, min(255, int(round(value))))

        if g is None and b is None:
            r = g = b = r
        return (_clamp(r), _clamp(g), _clamp(b), _clamp(a))

    @staticmethod
    def xor(r, g=None, b=None, a=255) -> tuple:
        # The real hardware performs a XOR blend; for the simulator,
        # approximating with a solid colour keeps visuals readable.
        return brushes.color(r, g, b, a)


class PixelFont:
    class _Wrapper:
        __slots__ = ("_font", "name", "height")

        def __init__(self, font: pygame.font.Font, name: str):
            self._font = font
            self.name = name
            self.height = font.get_height()

        def render(self, *args, **kwargs):
            return self._font.render(*args, **kwargs)

        def size(self, *args, **kwargs):
            return self._font.size(*args, **kwargs)

        def get_height(self):
            return self._font.get_height()

        def __getattr__(self, item):
            return getattr(self._font, item)

    @staticmethod
    def load(path: str, size: int = 14):
        resolved = map_system_path(path)
        name = os.path.splitext(os.path.basename(path))[0]
        font = None
        if os.path.exists(resolved):
            ext = os.path.splitext(resolved)[1].lower()
            if ext in {".ttf", ".otf", ".ttc"}:
                try:
                    font = pygame.font.Font(resolved, size)
                except Exception:
                    font = None
            else:
                # Pico pixel fonts (`.ppf`) aren't true TTF files; using the
                # default pygame font keeps the simulator stable.
                font = None
        if font is None:
            font = pygame.font.Font(None, size)
        return PixelFont._Wrapper(font, name)


class Image(_SurfaceTarget):
    OFF = 0
    X2 = 1
    X4 = 2
    _cache = {}

    def __init__(self, *args, _surface: pygame.Surface = None):
        if _surface is None:
            if len(args) == 2:
                width, height = args
            elif len(args) == 4:
                _, _, width, height = args
            else:
                raise TypeError("Image() expects width,height or x,y,width,height")
            width = max(1, int(round(width)))
            height = max(1, int(round(height)))
            surface = pygame.Surface((width, height), pygame.SRCALPHA)
        else:
            surface = _surface
            width = surface.get_width()
            height = surface.get_height()

        super().__init__(surface)
        self.width = width
        self.height = height
        self.antialias = Image.OFF
        self.has_palette = False
        self.x = 0
        self.y = 0
        if len(args) == 4:
            self.x, self.y = args[0], args[1]

    @property
    def alpha(self):
        return self._surface.get_alpha()

    @alpha.setter
    def alpha(self, value):
        self._surface.set_alpha(None if value is None else int(value))

    def get_width(self):
        return self.width

    def get_height(self):
        return self.height

    def __getattr__(self, item):
        return getattr(self._surface, item)

    @staticmethod
    def load(path: str):
        normalised = os.path.normpath(map_system_path(path))
        if normalised in Image._cache:
            source = Image._cache[normalised]
        else:
            source = pygame.image.load(normalised).convert_alpha()
            Image._cache[normalised] = source
        return Image(_surface=source.copy())


class SpriteSheet:
    def __init__(self, path: str, cols: int, rows: int) -> None:
        self.sheet = Image.load(path)
        self.cols = cols
        self.rows = rows
        self.frame_width = self.sheet.get_width() // cols
        self.frame_height = self.sheet.get_height() // rows

    def sprite(self, x: int, y: int) -> Image:
        rect = pygame.Rect(
            x * self.frame_width,
            y * self.frame_height,
            self.frame_width,
            self.frame_height,
        )
        image = pygame.Surface((self.frame_width, self.frame_height), pygame.SRCALPHA)
        src = self.sheet._surface if isinstance(self.sheet, Image) else self.sheet
        image.blit(src, (0, 0), rect)
        return Image(_surface=image)

    def animation(self, x: int = 0, y: int = 0, length: int = None):
        frames = []
        if length is None:
            length = self.cols * self.rows - (y * self.cols + x)
        for i in range(length):
            col = (x + i) % self.cols
            row = y + (x + i) // self.cols
            frames.append(self.sprite(col, row))
        return Animation(frames)


class Animation:
    def __init__(self, frames: list) -> None:
        self.frames = frames

    def frame(self, index: float) -> Image:
        i = int(index)
        if i < 0:
            i = 0
        elif i >= len(self.frames):
            i = len(self.frames) - 1
        return self.frames[i]

    def count(self) -> int:
        return len(self.frames)


# -----------------------------------------------------------------------------
# 2D Affine transform matrix (identity by default)
# Matches usage like: Matrix().translate(dx, dy)
# -----------------------------------------------------------------------------

class Matrix:
    """Simple 2D affine transform: | a c tx |
                                  | b d ty |
                                  | 0 0  1 |
    Supports chaining: Matrix().translate(x, y).scale(sx, sy).rotate(deg)
    """
    __slots__ = ("a", "b", "c", "d", "tx", "ty")

    def __init__(self, a: float = 1.0, b: float = 0.0, c: float = 0.0,
                 d: float = 1.0, tx: float = 0.0, ty: float = 0.0) -> None:
        self.a, self.b, self.c, self.d, self.tx, self.ty = a, b, c, d, tx, ty

    # fluent ops
    def translate(self, dx: float, dy: float):
        self.tx += self.a * dx + self.c * dy
        self.ty += self.b * dx + self.d * dy
        return self

    def scale(self, sx: float, sy: float = None):
        if sy is None:
            sy = sx
        self.a *= sx
        self.b *= sx
        self.c *= sy
        self.d *= sy
        return self

    def rotate(self, degrees: float):
        return self.rotate_radians(math.radians(degrees))

    def rotate_radians(self, radians: float):
        cos, sin = math.cos(radians), math.sin(radians)
        a, b, c, d = self.a, self.b, self.c, self.d
        self.a = a * cos + c * sin
        self.b = b * cos + d * sin
        self.c = -a * sin + c * cos
        self.d = -b * sin + d * cos
        return self

    def multiply(self, other: "Matrix"):
        a = self.a * other.a + self.c * other.b
        b = self.b * other.a + self.d * other.b
        c = self.a * other.c + self.c * other.d
        d = self.b * other.c + self.d * other.d
        tx = self.a * other.tx + self.c * other.ty + self.tx
        ty = self.b * other.tx + self.d * other.ty + self.ty
        self.a, self.b, self.c, self.d, self.tx, self.ty = a, b, c, d, tx, ty
        return self

    def transformed_point(self, x: float, y: float):
        return (self.a * x + self.c * y + self.tx, self.b * x + self.d * y + self.ty)


class Screen(_SurfaceTarget):
    def __init__(self, width: int = 160, height: int = 120, scale: int = 4) -> None:
        self.width = width
        self.height = height
        self.scale = scale
        self._window = pygame.display.set_mode((width * scale, height * scale))
        pygame.display.set_caption("Badge Local Simulator")
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        super().__init__(surface)
        self.antialias = Image.OFF

    def load_into(self, path: str) -> None:
        """Load an image directly into the screen buffer."""
        image = Image.load(path)
        src = self._unwrap(image)
        if src.get_width() != self.width or src.get_height() != self.height:
            src = pygame.transform.scale(src, (self.width, self.height))
        self._surface.blit(src, (0, 0))

    def window(self, x: float, y: float, width: float, height: float):
        return _Window(self, x, y, width, height)

    def present(self) -> None:
        pygame.transform.scale(
            self._surface, (self.width * self.scale, self.height * self.scale), self._window
        )
        pygame.display.flip()


class _Window:
    def __init__(self, parent: Screen, x: float, y: float, width: float, height: float):
        self._parent = parent
        self.x = int(round(x))
        self.y = int(round(y))
        self.width = max(0, int(round(width)))
        self.height = max(0, int(round(height)))
        self.brush = parent.brush
        self.font = parent.font

    def _set_clip(self):
        prev = self._parent._surface.get_clip()
        rect = pygame.Rect(self.x, self.y, self.width, self.height)
        self._parent._surface.set_clip(rect)
        return prev

    def _restore_clip(self, prev):
        self._parent._surface.set_clip(prev)

    def clear(self, color=None):
        clip = self._set_clip()
        try:
            fill_color = self._parent._norm_color(color if color is not None else self.brush)
            rect = pygame.Rect(self.x, self.y, self.width, self.height)
            self._parent._surface.fill(fill_color, rect)
        finally:
            self._restore_clip(clip)

    def draw(self, shape: _Shape) -> None:
        color = self._parent._norm_color(self.brush)
        clip = self._set_clip()
        try:
            _render_shape(self._parent._surface, color, shape, offset=(self.x, self.y))
        finally:
            self._restore_clip(clip)

    def _offset(self, x: float, y: float, transform: "Matrix" = None):
        if isinstance(transform, Matrix):
            x, y = transform.transformed_point(x, y)
        return x + self.x, y + self.y

    def blit(self, image, x: float, y: float, transform: "Matrix" = None) -> None:
        clip = self._set_clip()
        try:
            x, y = self._offset(x, y, transform)
            self._parent._surface.blit(
                self._parent._unwrap(image),
                (int(x), int(y)),
            )
        finally:
            self._restore_clip(clip)

    def scale_blit(self, image, x: float, y: float, w: int, h: int, transform: "Matrix" = None) -> None:
        clip = self._set_clip()
        try:
            x, y = self._offset(x, y, transform)
            src = self._parent._unwrap(image)
            new_w = max(1, abs(w))
            new_h = max(1, abs(h))
            scaled = pygame.transform.scale(src, (new_w, new_h))
            if w < 0:
                scaled = pygame.transform.flip(scaled, True, False)
            if h < 0:
                scaled = pygame.transform.flip(scaled, False, True)
            self._parent._surface.blit(scaled, (int(x), int(y)))
        finally:
            self._restore_clip(clip)

    def text(self, text: str, x: float, y: float) -> None:
        clip = self._set_clip()
        try:
            font = self.font or self._parent.font
            surf = font.render(str(text), True, self._parent._norm_color(self.brush))
            self._parent._surface.blit(surf, (int(x + self.x), int(y + self.y)))
        finally:
            self._restore_clip(clip)

    def measure_text(self, text: str) -> tuple:
        font = self.font or self._parent.font
        surf = font.render(str(text), True, (0, 0, 0))
        return surf.get_size()

    def window(self, x: float, y: float, width: float, height: float):
        return _Window(self._parent, self.x + x, self.y + y, width, height)


class IO:
    BUTTON_A = "BUTTON_A"
    BUTTON_B = "BUTTON_B"
    BUTTON_C = "BUTTON_C"
    BUTTON_UP = "BUTTON_UP"
    BUTTON_DOWN = "BUTTON_DOWN"
    BUTTON_LEFT = "BUTTON_LEFT"
    BUTTON_RIGHT = "BUTTON_RIGHT"
    BUTTON_HOME = "BUTTON_HOME"

    def __init__(self) -> None:
        self.pressed: set = set()
        self.down: set = set()
        self.released: set = set()
        self.changed: set = set()
        self.held: set = set()
        self.ticks = 0
        self.ticks_delta = 0
        self._last_ticks = pygame.time.get_ticks()
        self._key_map = {
            pygame.K_a: IO.BUTTON_A,
            pygame.K_b: IO.BUTTON_B,
            pygame.K_c: IO.BUTTON_C,
            pygame.K_UP: IO.BUTTON_UP,
            pygame.K_DOWN: IO.BUTTON_DOWN,
            pygame.K_LEFT: IO.BUTTON_LEFT,
            pygame.K_RIGHT: IO.BUTTON_RIGHT,
            pygame.K_z: IO.BUTTON_A,
            pygame.K_x: IO.BUTTON_B,
            pygame.K_SPACE: IO.BUTTON_C,
            pygame.K_h: IO.BUTTON_HOME,
            pygame.K_ESCAPE: IO.BUTTON_HOME,
        }

    def update(self) -> None:
        self.pressed.clear()
        self.released.clear()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            if event.type == pygame.KEYDOWN:
                if event.key in self._key_map:
                    name = self._key_map[event.key]
                    self.pressed.add(name)
                    self.down.add(name)
            if event.type == pygame.KEYUP:
                if event.key in self._key_map:
                    name = self._key_map[event.key]
                    self.down.discard(name)
                    self.released.add(name)
        self.held = set(self.down)
        self.changed = set()
        self.changed.update(self.pressed)
        self.changed.update(self.released)
        now = pygame.time.get_ticks()
        self.ticks_delta = now - self._last_ticks
        self.ticks = now
        self._last_ticks = now


class Display:
    def update(self) -> None:
        # Present the current screen contents.
        screen.present()

display = Display()


class State:
    @staticmethod
    def _state_dir() -> str:
        root = SIM_ROOT or _find_sim_root(os.getcwd())
        path = os.path.join(root, ".badge_state")
        os.makedirs(path, exist_ok=True)
        return path

    @staticmethod
    def _state_path(name: str) -> str:
        safe = "".join(ch for ch in name if ch.isalnum() or ch in ("-", "_"))
        if not safe:
            safe = "state"
        return os.path.join(State._state_dir(), f"{safe}.json")

    @staticmethod
    def load(name: str, target) -> bool:
        path = State._state_path(name)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(target, dict) and isinstance(data, dict):
                target.update(data)
            return True
        except FileNotFoundError:
            return False
        except Exception:
            traceback.print_exc()
            return False

    @staticmethod
    def save(name: str, data) -> bool:
        path = State._state_path(name)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            return True
        except Exception:
            traceback.print_exc()
            return False


def clamp(value: float, minimum: float, maximum: float) -> float:
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value

# -----------------------------------------------------------------------------
# File helpers expected by some games (menu, etc.)
# -----------------------------------------------------------------------------

def is_dir(path: str) -> bool:
    return os.path.isdir(map_system_path(path))

def file_exists(path: str) -> bool:
    return os.path.isfile(map_system_path(path))


def get_battery_level() -> int:
    """Return a fake but plausible battery percentage."""
    return 75


def is_charging() -> bool:
    """Return whether the badge is currently charging."""
    return False

# -----------------------------------------------------------------------------
# Runner
# -----------------------------------------------------------------------------

def run(update_func, fps: int = 60, init=None, on_exit=None):
    if not callable(init):
        module_name = getattr(update_func, "__module__", None)
        module_obj = sys.modules.get(module_name) if module_name else None
        if module_obj is not None:
            init = getattr(module_obj, "init", None)
            if not callable(on_exit):
                on_exit = getattr(module_obj, "on_exit", None)
    clock = pygame.time.Clock()
    result = None
    try:
        if callable(init):
            init()
        while True:
            io.update()
            result = update_func()
            screen.present()
            clock.tick(fps)
            if result is not None:
                break
    finally:
        if callable(on_exit):
            try:
                on_exit()
            except Exception:
                traceback.print_exc()
    return result

# -----------------------------------------------------------------------------
# Module loader
# -----------------------------------------------------------------------------

def load_game_module(module_path: str) -> ModuleType:
    """Load a game module from a path or dotted module. Inject our `badgeware`."""
    if module_path.endswith(".py"):
        game_abs = os.path.abspath(map_system_path(module_path))
        spec = importlib.util.spec_from_file_location("badge_game", game_abs)
    else:
        spec = importlib.util.find_spec(module_path)
        if spec is None:
            raise ImportError(f"Cannot find module {module_path}")
        origin = getattr(spec, "origin", None)
        game_abs = os.path.abspath(origin) if origin else os.getcwd()
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load specification for {module_path}")

    # Make local imports work (e.g. `from mona import Mona`)
    game_dir = os.path.dirname(game_abs)
    sim_root = SIM_ROOT if SIM_ROOT is not None else _find_sim_root(game_dir)
    for p in (game_dir, os.path.join(sim_root, "apps")):
        if p not in sys.path:
            sys.path.insert(0, p)

    # Provide `badgeware`
    badgeware = ModuleType("badgeware")
    badgeware.screen = screen
    badgeware.Image = Image
    badgeware.SpriteSheet = SpriteSheet
    badgeware.PixelFont = PixelFont
    badgeware.brushes = brushes
    badgeware.shapes = shapes
    badgeware.io = io
    badgeware.run = run
    badgeware.Matrix = Matrix
    badgeware.is_dir = is_dir
    badgeware.file_exists = file_exists
    badgeware.get_battery_level = get_battery_level
    badgeware.is_charging = is_charging
    badgeware.display = display
    badgeware.State = State
    badgeware.clamp = clamp
    sys.modules["badgeware"] = badgeware

    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return mod

# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Run a GitHub Badge game locally using Pygame.")
    parser.add_argument("game", help="Path to the game .py or a dotted module name.")
    parser.add_argument("--scale", type=int, default=4, help="Scale factor (default: 4)")
    parser.add_argument(
        "-C",
        "--system-root",
        dest="system_root",
        metavar="DIR",
        help="Use DIR as the root for '/system' lookups and asset loading.",
    )
    args = parser.parse_args()

    pygame.init()

    global screen, io, SIM_ROOT
    screen = Screen(scale=args.scale)
    io = IO()
    if args.system_root:
        root = os.path.abspath(args.system_root)
        if not os.path.isdir(root):
            print(f"System root '{args.system_root}' is not a directory.", file=sys.stderr)
            pygame.quit()
            sys.exit(2)
        SIM_ROOT = root
    else:
        SIM_ROOT = _find_sim_root(os.getcwd())

    try:
        module = load_game_module(args.game)
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        pygame.quit()
        sys.exit(1)

    if not hasattr(module, "update"):
        print("Loaded module has no 'update' function", file=sys.stderr)
        pygame.quit()
        sys.exit(1)

    try:
        init_func = getattr(module, "init", None)
        exit_func = getattr(module, "on_exit", None)
        run(module.update, init=init_func, on_exit=exit_func)
    except SystemExit:
        pass
    except Exception:
        traceback.print_exc()
        pygame.quit()
        sys.exit(1)


if __name__ == "__main__":
    main()
