import math


def chevron(cx, cy, s):
  # a sharp down-pointing V; the apex makes the line join obvious
  return [
    vec2(cx - s, cy - s * 0.7),
    vec2(cx, cy + s * 0.7),
    vec2(cx + s, cy - s * 0.7),
  ]


def update():
  screen.antialias = image.X4
  # stroke ribbons rely on even-odd to leave the band hollow
  screen.fill_rule = image.EVEN_ODD

  w = screen.width
  h = screen.height
  col = w / 4
  s = w * 0.06

  # animate the thickness so you can watch the miter grow while round/bevel stay
  # bounded, and the caps extend
  thick = (math.sin(badge.ticks / 600) + 1) * (w * 0.022) + 6

  joins = [("miter", shape.JOIN_MITER), ("round", shape.JOIN_ROUND), ("bevel", shape.JOIN_BEVEL)]
  caps = [("butt", shape.CAP_BUTT), ("round", shape.CAP_ROUND), ("square", shape.CAP_SQUARE)]

  jy = h * 0.30
  cy = h * 0.72

  # top row: same chevron, three line joins (open stroke, centred)
  for i, (name, join) in enumerate(joins):
    cx = col * (i + 1)
    outline = shape.custom(chevron(cx, jy, s)).stroke(thick, shape.ALIGN_CENTER | shape.PATH_OPEN | join)
    screen.pen = color.rgb(120, 200, 255)
    screen.shape(outline)
    screen.pen = color.rgb(255, 255, 255)
    screen.text(name, cx - 16, jy + s + 10)

  # bottom row: same segment, three line caps
  for i, (name, cap) in enumerate(caps):
    cx = col * (i + 1)
    seg = [vec2(cx - s, cy), vec2(cx + s, cy)]
    outline = shape.custom(seg).stroke(thick, shape.ALIGN_CENTER | shape.PATH_OPEN | cap)
    screen.pen = color.rgb(120, 200, 255)
    screen.shape(outline)
    screen.pen = color.rgb(255, 255, 255)
    screen.text(name, cx - 16, cy + 16)

  # restore the default so the setting doesn't leak into other demos
  screen.fill_rule = image.EVEN_ODD
