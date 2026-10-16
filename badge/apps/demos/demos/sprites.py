import random
import math

skull = image.load("/system/assets/skull.png")

def update():
  random.seed(0)
  for i in range(30):
    s = (math.sin(badge.ticks / 500) * 1) + 2

    skull.alpha = int((math.sin((badge.ticks + i * 30) / 500) + 1) * 127)

    x = math.sin(i + badge.ticks / 1000) * 40
    y = math.cos(i + badge.ticks / 1000) * 40

    pos = vec2(x + rnd(-20, 180), y + rnd(-20, 140))

    dr = rect(
      pos.x, pos.y, 32 * s, 24 * s
    )
    screen.blit(skull, dr)
