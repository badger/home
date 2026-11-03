WIDTH = 320
HEIGHT = 240
GROUND_Y = 216  # top of the lawn
SPEED = 60  # px/s that walls, fish and the lawn travel left

SKY_TOP = (46, 164, 244)
SKY_BOTTOM = (160, 234, 255)
SKY_BANDS = 12
BAND_H = HEIGHT // SKY_BANDS

far_hills = image.load("assets/far_hills.png")
hills = image.load("assets/background.png")
grass = image.load("assets/grass.png")
cloud = image.load("assets/cloud.png")


def lerp_color(a, b, t):
    return color.rgb(
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


sky = [lerp_color(SKY_TOP, SKY_BOTTOM, i / (SKY_BANDS - 1)) for i in range(SKY_BANDS)]


def overlaps(a, b):
    return (
        a[0] < b[0] + b[2]
        and b[0] < a[0] + a[2]
        and a[1] < b[1] + b[3]
        and b[1] < a[1] + a[3]
    )


def scatter(img, offset, y, period=None):
    if y >= HEIGHT or y + img.height <= 0:
        return
    period = period or img.width
    x = -(offset % period)
    while x < WIDTH:
        screen.blit(img, vec2(int(x), y))
        x += period


class World:
    def __init__(self):
        self.scroll = 0.0

    def advance(self, dt):
        self.scroll += SPEED * dt

    def draw(self, cam=0):
        cam = int(cam)
        drift = cam // 2  # clouds follow the camera at half speed

        y = 0
        for pen in sky:
            screen.pen = pen
            screen.rectangle(0, y, WIDTH, BAND_H)
            y += BAND_H

        scroll = self.scroll
        scatter(cloud, scroll * 0.10 + 90, -64 + drift, 320)
        scatter(cloud, scroll * 0.10, 28 + drift, 300)
        scatter(cloud, scroll * 0.10 + 170, 76 + drift, 340)
        scatter(far_hills, scroll * 0.04, 112 + cam)
        scatter(hills, scroll * 0.12, HEIGHT - hills.height + cam)
        scatter(grass, scroll, HEIGHT - grass.height + cam)
