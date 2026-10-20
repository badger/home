import icons

FOODS = (
  ("candy", "*", color.rgb(255, 125, 237), "SWEET: HAPPY UP", {"happy": 25, "hunger": 5}),
  ("fruit", "7", color.rgb(242, 77, 91), "FRUIT: FED + CLEAN UP", {"hunger": 15, "clean": 15}),
  ("burger", "9", color.rgb(233, 110, 18), "BURGER: FED UP", {"hunger": 30}),
)

TILE = 24
GAP = 6
PAD = 6
WIDTH = len(FOODS) * TILE + (len(FOODS) - 1) * GAP + PAD * 2
HEIGHT = TILE + PAD * 2
WINDOW = rect((160 - WIDTH) // 2, 16 + (90 - HEIGHT) // 2, WIDTH, HEIGHT)

WINDOW_EDGE = color.rgb(228, 220, 220, 200)
WINDOW_FILL = color.rgb(18, 16, 28, 215)
TILE_FILL = color.rgb(242, 245, 243)
CURSOR = color.rgb(95, 237, 131)


class Picker:
  def __init__(self):
    self.cursor = 0

  def move(self, step):
    self.cursor = (self.cursor + step) % len(FOODS)

  def choice(self):
    return FOODS[self.cursor]

  def caption(self):
    return self.choice()[3]

  def draw(self):
    screen.pen = WINDOW_EDGE
    screen.shape(shape.rounded_rectangle(WINDOW.x - 1, WINDOW.y - 1, WINDOW.w + 2, WINDOW.h + 2, 5))
    screen.pen = WINDOW_FILL
    screen.shape(shape.rounded_rectangle(WINDOW.x, WINDOW.y, WINDOW.w, WINDOW.h, 4))
    for index, (_name, char, fill, _caption, _effect) in enumerate(FOODS):
      x = WINDOW.x + PAD + index * (TILE + GAP)
      y = WINDOW.y + PAD
      if index == self.cursor:
        screen.pen = CURSOR
        screen.shape(shape.rounded_rectangle(x - 2, y - 2, TILE + 4, TILE + 4, 5))
      screen.pen = TILE_FILL
      screen.shape(shape.rounded_rectangle(x, y, TILE, TILE, 4))
      icons.draw("food", char, x + (TILE - icons.WIDTH) // 2, y + (TILE - icons.HEIGHT) // 2, fill)
