from badgeware import screen, brushes, shapes

def update():
  # set the brush to a solid bright green
  screen.brush = brushes.color(0, 255, 0)

  # draw a circle in the middle of the screen
  screen.draw(shapes.circle(80, 60, 20))