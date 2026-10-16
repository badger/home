"""Check all four native graphics transforms on the physical badge framebuffer."""

import gc
import sys

sys.path.insert(0, "/system/apps/camera")
namespace = dict(globals())
with open("/system/apps/camera/__init__.py") as source:
    exec(source.read().split("\napp = CameraApp()")[0], namespace)
app = namespace["CameraApp"]()
try:
    sample = image(80, 60)
    for x, y, rgb in (
        (0, 0, (255, 0, 0)), (40, 0, (0, 255, 0)),
        (0, 30, (0, 0, 255)), (40, 30, (255, 255, 0)),
    ):
        sample.pen = color.rgb(*rgb)
        sample.rectangle(x, y, 40, 30)
    expected = (
        (0xf800, 0x07e0, 0x001f, 0xffe0),
        (0x001f, 0xf800, 0xffe0, 0x07e0),
        (0xffe0, 0x001f, 0x07e0, 0xf800),
        (0x07e0, 0xffe0, 0xf800, 0x001f),
    )
    app.mode = "FROZEN"
    app.message = "Rotation regression test"
    app.detail = ""
    for rotation in range(4):
        app.prepare_frame(sample, rotation)
        gc.collect()
        app.draw()
        display.update()
        area = app.frame_rect
        actual = []
        for x, y in ((1, 1), (3, 1), (1, 3), (3, 3)):
            px = int(area.x + area.w * x / 4)
            py = int(area.y + area.h * y / 4)
            offset = (py * screen.width + px) * 2
            actual.append(screen.raw[offset] | (screen.raw[offset + 1] << 8))
        assert tuple(actual) == expected[rotation], (rotation, actual, expected[rotation])
        print("PASS rotation", rotation * 90, "framebuffer quadrants", actual)
    print("ROTATION_HARDWARE_PROBE_PASS")
finally:
    app.close()
