import math
import random

def update():
  random.seed(1)

  for _ in range(20):
    x = random.uniform(-5, 5)
    y = random.uniform(-5, 5)
    s = random.uniform(0.5, 2)
    star = shape.star(x, y, 5, s / 2, s)
    star.transform = mat3().translate(80, 60).scale(15).rotate(badge.ticks / 10)
    screen.shape(star)


  b = math.sin(badge.ticks / 500) * 2 + 2
  screen.blur(b)

  screen.text(f"blur radius: {b:.2f}", 50, 100)
