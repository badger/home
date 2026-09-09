import math

# Off-screen panel we punch holes in, then composite over the backdrop. Built
# lazily on the first frame so `screen` is known; re-cleared every frame.
overlay = None


def backdrop():
  # colourful spinning blobs for the holes to reveal
  for i in range(8):
    a = i / 8 * 2 * math.pi + badge.ticks / 1400
    screen.pen = color.hsv(i * 32, 200, 230)
    x = screen.width * 0.5 + math.cos(a) * screen.width * 0.26
    y = screen.height * 0.5 + math.sin(a) * screen.height * 0.26
    screen.shape(shape.circle(x, y, screen.width * 0.14))


def update():
  global overlay
  if overlay is None:
    overlay = image(screen.width, screen.height)

  screen.antialias = image.X4
  backdrop()

  # opaque frosted panel that hides the backdrop until we cut through it
  overlay.antialias = image.X4
  overlay.pen = color.rgb(22, 24, 34, 240)
  overlay.clear()

  # brush.erase(): a clean porthole — dst-out, AA edges feather into transparency
  cx = screen.width * 0.32 + math.sin(badge.ticks / 1100) * screen.width * 0.06
  cy = screen.height * 0.5
  r = screen.width * 0.18
  overlay.pen = brush.erase()
  overlay.shape(shape.circle(cx, cy, r))

  # brush.erase(color): a translucent stained-glass window in a single pass
  wx = screen.width * 0.68
  tint = color.rgb(255, 120, 0, 150)
  overlay.pen = brush.erase(tint)
  overlay.shape(shape.circle(wx, cy, r))

  # composite the punched panel over the backdrop
  screen.blit(overlay, vec2(0, 0))

  screen.pen = color.rgb(255, 255, 255)
  screen.text("erase()", cx - 24, cy + r + 10)
  screen.text("erase(color)", wx - 40, cy + r + 10)
