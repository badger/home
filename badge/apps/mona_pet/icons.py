WIDTH = 14
HEIGHT = 16
OUTLINE = color.rgb(18, 16, 28)

fonts = {}


def load(family):
  if family not in fonts:
    fonts[family] = (font.load(family), font.load(family + "_outline"))
  return fonts[family]


def draw(family, char, x, y, fill):
  filled, outline = load(family)
  previous = screen.font
  screen.font = filled
  screen.pen = fill
  screen.text(char, x, y)
  screen.font = outline
  screen.pen = OUTLINE
  screen.text(char, x, y)
  screen.font = previous
