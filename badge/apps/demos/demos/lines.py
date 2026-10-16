import random
import math

def update():
  random.seed(0)

  for i in range(100):
    x = math.sin(i + badge.ticks / 500) * 40
    y = math.cos(i + badge.ticks / 500) * 40
    p1 = vec2(x + rnd(-50, 210), y + rnd(-50, 170))
    p2 = vec2(x + rnd(-50, 210), y + rnd(-50, 170))
    screen.pen = color.rgb(rnd(255), rnd(255), rnd(255))
    screen.line(p1, p2)

