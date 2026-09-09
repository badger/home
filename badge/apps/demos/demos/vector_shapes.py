import math


def update():
  screen.antialias = image.X4

  i = math.sin(badge.ticks / 2000) * 0.2 + 0.5
  f = math.sin(badge.ticks / 1000) * 150
  t = f + (math.sin(badge.ticks / 500) + 1.0) * 50 + 100

  stroke = ((math.sin(badge.ticks / 1000) + 1) * 0.05) + 0.1

  shapes = [
    shape.rectangle(-1, -1, 2, 2),
    shape.rectangle(-1, -1, 2, 2).stroke(stroke),
    shape.circle(0, 0, 1),
    shape.circle(0, 0, 1).stroke(stroke),
    shape.ellipse(0, 0, 1, 0.5),
    shape.ellipse(0, 0, 1, 0.5).stroke(stroke),
    shape.star(0, 0, 5, i, 1),
    shape.star(0, 0, 5, i, 1).stroke(stroke),
    shape.squircle(0, 0, 1),
    shape.squircle(0, 0, 1).stroke(stroke),
    shape.pie(0, 0, 1, f, t),
    shape.pie(0, 0, 1, f, t).stroke(stroke),
    shape.arc(0, 0, i, 1, f, t),
    shape.arc(0, 0, i, 1, f, t).stroke(stroke),
    shape.regular_polygon(0, 0, 1, 3),
    shape.regular_polygon(0, 0, 1, 3).stroke(stroke),
    shape.line(-0.75, -0.75, 0.75, 0.75, 0.5),
    shape.line(-0.75, -0.75, 0.75, 0.75, 0.5).stroke(stroke),
  ]



  for y in range(4):
    for x in range(4):
      i = y * 4 + x

      scale = ((math.sin((badge.ticks + i * 2000) / 1000) + 1) * 3) + 5

      if i < len(shapes):
        screen.pen = color.oklch(220, 128, i * 20, 150)

        shapes[i].transform = mat3().translate(x * 36 + 25, y * 26 + 20).rotate(badge.ticks / 100).scale(scale)
        screen.shape(shapes[i])
