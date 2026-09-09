import math

# A unit 5-point star traced as a single self-intersecting path (a pentagram,
# the {5/2} star polygon): each edge skips a point, so the centre pentagon is
# enclosed twice. It winds to 2 there -> a hole under the even-odd rule, but
# filled under the nonzero rule.
PENTAGRAM = [
  vec2(math.cos(math.radians(-90 + k * 144)), math.sin(math.radians(-90 + k * 144)))
  for k in range(5)
]


def update():
  screen.antialias = image.X4

  w = screen.width
  h = screen.height
  r = min(w, h) * 0.30
  cy = h * 0.44

  # same shape on each side, drawn with a different fill rule
  rules = [
    ("even-odd", image.EVEN_ODD, w * 0.27),
    ("nonzero", image.NON_ZERO, w * 0.73),
  ]

  for label, rule, cx in rules:
    t = mat3().translate(cx, cy).rotate(badge.ticks / 25).scale(r, r)

    # filled, using this side's fill rule
    fill = shape.custom(PENTAGRAM)
    fill.transform = t
    screen.fill_rule = rule
    screen.pen = color.rgb(120, 200, 255)
    screen.shape(fill)

    # white outline on top. stroke() works in the shape's *local* units, and the
    # pentagram is unit-sized, so the thickness is tiny (0.04, not e.g. 2 which
    # would be twice the whole shape and blow the miters off-screen). stroke
    # ribbons rely on even-odd to leave the band hollow, so draw with EVEN_ODD.
    outline = shape.custom(PENTAGRAM).stroke(0.1)
    outline.transform = t
    screen.fill_rule = image.EVEN_ODD
    screen.pen = color.rgb(255, 255, 255)
    screen.shape(outline)

    screen.pen = color.rgb(255, 255, 255)
    screen.text(label, cx - 24, cy + r + 12)

  # restore the default so the setting doesn't leak into other demos
  screen.fill_rule = image.EVEN_ODD
