import math

def update():
  for i in range(100):

    screen.pen = color.oklch(128, 128, (badge.ticks / 100) + i + 150, 100)

    # line clipping to rect
    p1 = vec2(
      int(math.sin(i + badge.ticks / 500) * 100 + 0),
      int(math.sin(i + badge.ticks / 400) * 100 + 0)
    )

    p2 = vec2(
      int(math.sin(i + badge.ticks / 300) * 100 + 320),
      int(math.sin(i + badge.ticks / 200) * 100 + 240)
    )
    clip = rect(10, 10, 140, 100)

    # clip_line returns true if a line is inside the clipping bounds or has been clipped
    # lines outside of the bounds should be rejected, since they cannot be clipped
    if algorithm.clip_line(p1, p2, clip):
      screen.line(p1, p2)

  screen.pen = color.rgb(60, 80, 100, 100)
  screen.line(clip.x, clip.y, clip.x + clip.w, clip.y)
  screen.line(clip.x, clip.y, clip.x, clip.y + clip.h)
  screen.line(clip.x, clip.y + clip.h, clip.x + clip.w, clip.y + clip.h)
  screen.line(clip.x + clip.w, clip.y, clip.x + clip.w, clip.y + clip.h)

