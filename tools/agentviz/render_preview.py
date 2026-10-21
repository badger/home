"""Host drawing harness, not a firmware simulator or hardware verification."""

import argparse
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "badge/apps/agentviz"


class HostScreen:
    width = 320
    height = 240

    def __init__(self):
        self.canvas = Image.new("RGB", (self.width, self.height))
        self.draw = ImageDraw.Draw(self.canvas)
        self.host_font = ImageFont.load_default(size=11)
        self.pen = (255, 255, 255)
        self.labels = []

    def clear(self):
        self.draw.rectangle((0, 0, self.width, self.height), fill=self.pen)
        self.labels.clear()

    def shape(self, rectangle):
        x, y, w, h = rectangle
        self.draw.rectangle((x, y, x + w - 1, y + h - 1), fill=self.pen)

    def measure_text(self, text):
        return (int(self.draw.textlength(text, font=self.host_font)), 12)

    def text(self, text, x, y):
        self.labels.append(text)
        self.draw.text((int(x), int(y)), text, font=self.host_font, fill=self.pen)


class HostBadge:
    def __init__(self):
        self.ticks = 0
        self.ticks_delta = 0
        self.keys = set()

    def mode(self, mode):
        self.display_mode = mode

    def pressed(self, key):
        return key in self.keys


class HostMonitor:
    feed = None
    error = False
    address = ""
    message = "Add /agentviz_config.json"

    def step(self, now):
        pass

    def live(self, now):
        return False

    def reload(self):
        pass


def load_app(monitor=None):
    badge, screen = HostBadge(), HostScreen()
    namespace = {
        "badge": badge, "screen": screen, "color": SimpleNamespace(rgb=lambda *rgb: rgb),
        "shape": SimpleNamespace(rectangle=lambda *r: r),
        "font": SimpleNamespace(nope=None), "image": SimpleNamespace(OFF=0),
        "HIRES": 1, "VSYNC": 2,
    }
    for name in ("BACK", "LEFT", "RIGHT", "UP", "DOWN", "SELECT", "MENU"):
        namespace["BUTTON_" + name] = name
    # Execute the real app logic, excluding only its device path/bootstrap.
    code = (APP / "__init__.py").read_text().split("from agentviz_client import Monitor\n")[1]
    code = code.split("\napp = AgentVizApp()")[0]
    exec(compile(code, str(APP / "__init__.py"), "exec"), namespace)
    app = namespace["AgentVizApp"](monitor=monitor or HostMonitor())
    return app, badge, screen


def render_preview(destination):
    app, badge, screen = load_app()
    tiles = []
    app.update()
    tiles.append(screen.canvas.copy())
    badge.keys = {"MENU"}
    app.update()
    badge.keys.clear()
    badge.ticks = badge.ticks_delta = 10000
    app.update()
    tiles.append(screen.canvas.copy())
    badge.ticks_delta = 0
    badge.keys = {"LEFT"}
    app.update()
    badge.keys = {"DOWN"}
    app.update()
    tiles.append(screen.canvas.copy())
    canvas = Image.new("RGB", (960, 272), (25, 25, 33))
    for i, tile in enumerate(tiles):
        canvas.paste(tile, (i * 320, 0))
    ImageDraw.Draw(canvas).text((8, 248),
        "HOST-GENERATED DRAWING PREVIEW / synthetic data / substitute font / NOT hardware verification",
        font=ImageFont.load_default(size=13), fill="white")
    canvas.save(destination)


def render_icon(destination):
    icon = Image.new("RGB", (24, 24), (0, 0, 0))
    draw = ImageDraw.Draw(icon)
    colors = ((148, 163, 184), (59, 158, 255), (167, 139, 250), (16, 217, 122))
    for i, rgb in enumerate(colors):
        y = 3 + 5 * i
        draw.rectangle((2, y, 21, y + 2), fill=(26, 26, 36))
        x = 3 + (i * 7) % 11
        draw.rectangle((x, y, min(21, x + 7), y + 2), fill=rgb)
    draw.line((13, 1, 13, 22), fill=(240, 240, 242))
    icon.save(destination, optimize=True)


if __name__ == "__main__":
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--preview", type=Path)
    args.add_argument("--icon", type=Path)
    options = args.parse_args()
    if options.preview:
        render_preview(options.preview)
    if options.icon:
        render_icon(options.icon)
