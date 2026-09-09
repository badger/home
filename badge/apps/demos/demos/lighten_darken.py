import math


def backdrop():
  # colourful spinning blobs for the effect to chew on
  for i in range(8):
    a = i / 8 * 2 * math.pi + badge.ticks / 1400
    screen.pen = color.hsv(i * 32, 200, 200)
    x = screen.width * 0.5 + math.cos(a) * screen.width * 0.26
    y = screen.height * 0.5 + math.sin(a) * screen.height * 0.26
    screen.shape(shape.circle(x, y, screen.width * 0.14))


def effect_window(cx, cy, r, b, label):
  screen.pen = b
  screen.shape(shape.circle(cx, cy, r))

  # white outline around the region
  screen.pen = color.rgb(255, 255, 255)
  screen.shape(shape.circle(cx, cy, r).stroke(2))
  screen.text(label, cx - 28, cy + r + 12)


def update():
  screen.antialias = image.X4
  backdrop()

  amount = int((math.sin(badge.ticks / 700) + 1) * 60) + 20  # 20..140
  r = screen.width * 0.17
  cy = screen.height * 0.5

  effect_window(screen.width * 0.3, cy, r, brush.lighten(amount), "lighten %d" % amount)
  effect_window(screen.width * 0.7, cy, r, brush.darken(amount), "darken %d" % amount)
