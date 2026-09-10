import math

skull = image.load("/system/assets/skull.png")
add_sprite("skull", skull)
mona_sans = font.load("/system/assets/fonts/DynaPuff-Medium.af")
size = 24

def update():
  global size
  screen.font = mona_sans
  screen.antialias = image.X2
  screen.alpha = 255

  i = round(badge.ticks / 200)
  i %= 10

  size = (math.sin(badge.ticks / 1000) * 5) + 15
  message = """[pen:180,150,120]Upon the mast I gleam and grin, A sentinel of bone and sin. Wind and thunder, night and hull— None fear the sea like a [pen:230,220,200]pirate skull[pen:180,150,120].

[sprite:skull]

Once I roared with breath and [pen:255,100,80]flame[pen:180,150,120], Now legend is my only name. But still I guard the [pen:255,200,80]plundered gold[pen:180,150,120], Grinning wide, forever bold.
"""

  screen.pen = color.rgb(100, 255, 100, 150)

  x = 10
  y = 10
  width = math.sin(badge.ticks / 500) * 40 + 110
  height = 200
  bounds = rect(x, y, width, height)
  screen.text(message, bounds, font_size=size, line_height=1, word_spacing=1.05)

  screen.pen = color.rgb(60, 80, 100, 100)
  screen.line(bounds.x, bounds.y, bounds.x + bounds.w, bounds.y)
  screen.line(bounds.x, bounds.y, bounds.x, bounds.y + bounds.h)
  screen.line(bounds.x, bounds.y + bounds.h, bounds.x + bounds.w, bounds.y + bounds.h)
  screen.line(bounds.x + bounds.w, bounds.y, bounds.x + bounds.w, bounds.y + bounds.h)




# [pen:r,g,b] and [sprite:skull] use the built-in renderers; register a custom
# [circle] renderer with add_glyph. A renderer is fn(image, params, measure): it
# returns its advance width when measuring, else draws at image.cursor.
def circle_glyph_renderer(image, _parameters, measure):
  if measure:
    return 12

  image.shape(shape.circle(image.cursor.x + 6, image.cursor.y + 7, 6))
  return None


add_glyph("circle", circle_glyph_renderer)
