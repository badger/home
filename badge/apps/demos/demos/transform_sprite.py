import math

skull = image.load("/system/assets/skull.png")

def magic_sprite(src, pos, scale=1, angle=0):
  w, h = src.width, src.height
  t = mat3().translate(*pos).scale(scale, scale).rotate(angle).translate(-w / 2, -h)
  screen.pen = brush.image(src)
  rect = shape.rectangle(0, 0, w, h)
  rect.transform = t
  screen.shape(rect)


def update():
  scale = (math.sin(badge.ticks / 1000) + 1.0) * 3 + 1
  angle = math.cos(badge.ticks / 500) * 100
  magic_sprite(skull, (80, 60), scale, angle)
