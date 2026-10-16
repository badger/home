import math


def backdrop():
  # colourful spinning blobs for the effect to chew on
  for i in range(8):
    a = i / 8 * 2 * math.pi + badge.ticks / 1400
    screen.pen = color.hsv(i * 32, 200, 230)
    x = screen.width * 0.5 + math.cos(a) * screen.width * 0.26
    y = screen.height * 0.5 + math.sin(a) * screen.height * 0.26
    screen.shape(shape.circle(x, y, screen.width * 0.14))


def update():
  screen.antialias = image.X4
  backdrop()

  # frosted-glass window; radius pulses 1..10 (box blur is O(r^2) per pixel, so
  # this gets heavy at the top end)
  radius = int((math.sin(badge.ticks / 900) + 1) * 4.5) + 1
  cx = screen.width * 0.5 + math.sin(badge.ticks / 1100) * screen.width * 0.18
  cy = screen.height * 0.5
  r = screen.width * 0.2

  screen.pen = brush.blur(radius)
  screen.shape(shape.circle(cx, cy, r))

  # outline the blurred region
  screen.pen = color.rgb(255, 255, 255)
  screen.shape(shape.circle(cx, cy, r).stroke(2))
  screen.text(f"blur {radius}", 5, screen.height - 12)
