import math

# colour stops are constant, so define them once. each stop is (position, color)
# with position 0..1, up to 16 stops.
SUNSET = [
  (0.0, color.rgb(255, 94, 91)),
  (0.5, color.rgb(255, 209, 102)),
  (1.0, color.rgb(67, 138, 255)),
]

ORB = [
  (0.0, color.rgb(255, 255, 255)),
  (0.35, color.rgb(120, 210, 255)),
  (1.0, color.rgb(18, 28, 84)),
]

W, H = screen.width, screen.height

# --- linear gradient filling a rounded rectangle ---------------------------
RX, RY = W * 0.06, H * 0.08
RW, RH = W * 0.88, H * 0.40
# map the 0..1 unit square onto the rectangle
RECT_M = mat3().translate(RX, RY).scale(RW, RH)

# --- radial gradient filling a circle --------------------------------------
CX, CY = W * 0.5, H * 0.74
RAD = min(W, H) * 0.22
# map the 0..1 square onto the circle's bounding box. centre the bright stop
# toward the top-left (0.35, 0.35) and reach the last stop at the far corner
# (1, 1) so it reads like a lit sphere.
ORB_M = mat3().translate(CX - RAD, CY - RAD).scale(RAD * 2, RAD * 2)

# Both brushes are built once. What construction costs is the 256-entry lookup
# table, and that depends only on the stops, so the animated one is repositioned
# with geometry() each frame instead of being rebuilt.
sunset_brush = brush.gradient(brush.LINEAR, 0.0, 0.5, 1.0, 0.5, SUNSET, RECT_M)
orb_brush = brush.gradient(brush.RADIAL, 0.35, 0.35, 1.0, 1.0, ORB, ORB_M)


def update():
  screen.antialias = image.X4

  # the gradient axis lives in 0..1 space; rotate it about the centre over time
  ang = badge.ticks / 1200
  dx, dy = math.cos(ang) * 0.5, math.sin(ang) * 0.5

  sunset_brush.geometry(0.5 - dx, 0.5 - dy, 0.5 + dx, 0.5 + dy, RECT_M)
  screen.pen = sunset_brush
  screen.shape(shape.rounded_rectangle(RX, RY, RW, RH, H * 0.05))

  screen.pen = orb_brush
  screen.shape(shape.circle(CX, CY, RAD))

  screen.pen = color.rgb(255, 255, 255)
  screen.text("linear", RX, RY + RH + 3)
  screen.text("radial", CX - 18, CY + RAD + 4)
