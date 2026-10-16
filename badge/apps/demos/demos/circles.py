import math
import random

def update():
  random.seed(0)

  for i in range(100):
    x = math.sin(i + badge.ticks / 100) * 40
    y = math.cos(i + badge.ticks / 100) * 40

    p = vec2(x + rnd(160), y + rnd(120))
    r = rnd(5, 20)
    screen.pen = color.rgb(rnd(255), rnd(255), rnd(255))
    screen.circle(p, r)
