import math

def update():
  screen.antialias = image.OFF

  r1s = 80
  r1x = (math.sin(badge.ticks / 250) * 20) + 80 - r1s / 2
  r1y = (math.cos(badge.ticks / 250) * 20) + 60 - r1s / 2
  r1 = rect(r1x, r1y, r1s, r1s)

  screen.pen = color.rgb(255, 0, 0, 100)
  screen.rectangle(r1)

  r2s = 80
  r2x = (math.sin(badge.ticks / 500) * 40) + 80 - r1s / 2
  r2y = (math.cos(badge.ticks / 500) * 40) + 60 - r1s / 2
  r2 = rect(r2x, r2y, r2s, r2s)

  screen.pen = color.rgb(0, 0, 255, 100)
  screen.rectangle(r2)

  r3 = r1.intersection(r2)
  # pen(100, 255, 100)
  # screen.rectangle(r3)

  screen.pen = color.rgb(255, 0, 255)
  screen.shape(shape.rectangle(r3.x, r3.y, r3.w, r3.h).stroke(2))
