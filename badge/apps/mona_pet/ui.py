
background_day = image.load("assets/background/background_day.png")
background_dusk = image.load("assets/background/background_dusk.png")
background_night = image.load("assets/background/background_night.png")
surround = image.load("assets/ui/frame.png")
buttons = image.load("assets/ui/buttons.png").spritesheet(4, 2)

screen.font = font.ark

backgrounds = {
    "day": background_day,
    "dusk": background_dusk,
    "night": background_night,
}

# the play area, which everything but the frame and the buttons sits in
SCENE = rect(0, 16, 160, 90)


def background(look):
  first, second, part = look
  screen.blit(backgrounds[first], SCENE)
  if part > 0:
    screen.alpha = int(255 * part)
    screen.blit(backgrounds[second], SCENE)
    screen.alpha = 255


def draw_header():
  screen.blit(surround, vec2(0, 0))


TEXT = color.rgb(228, 220, 220, 220)


# the clock and the stats sit over the scene, so they take a shadow with them
def draw_shadowed(line, x, y):
  screen.pen = color.rgb(0, 0, 0, 190)
  screen.text(line, x + 1, y + 1)
  screen.pen = TEXT
  screen.text(line, x, y)


def draw_clock(hour, minute):
  draw_shadowed("%02d:%02d" % (hour, minute), 10, 18)


# under 30% on his lowest need the picture starts to tear, working up to a
# strength of 16 as that need reaches nothing
def draw_glitch(lowest):
  if lowest >= 30:
    return
  strength = round(16 * (30 - lowest) / 30)
  if strength < 1:
    return
  previous = screen.clip
  screen.clip = SCENE
  screen.glitch(strength)
  screen.clip = previous


def draw_scanlines(area=None):
  previous = screen.clip
  screen.clip = area or previous
  # every second row, knocked back 28 of 255
  screen.crt(2, 28)
  screen.clip = previous


def draw_button(x, y, label, active):
  column = ("play", "feed", "clean", "reset").index(label)
  screen.blit(buttons.sprite(column, 1 if active else 0), vec2(x, y))


def draw_strip_text(line):
  """A line in the button strip, where the buttons would be."""
  screen.pen = TEXT
  screen.text(line, rect(0, 108, 160, 11), align=image.CENTER)


def draw_intro(sprite):
  screen.pen = TEXT
  screen.text("KEEP MONA FED, CLEAN AND HAPPY, DAY TO DAY",
              rect(8, 21, 144, 22), align=image.CENTER)

  screen.cursor = vec2(66, 46)
  screen.text("< = PLAY")
  screen.text("> = FEED")
  screen.text("ENTER = CLEAN")
  screen.text("UP = WARP")
  screen.text("DOWN = STATS")

  # pixel-doubled, centred on x 34 with her feet at 98
  w, h = sprite.width * 2, sprite.height * 2
  screen.blit(sprite, rect(34 - w / 2, 98 - h, w, h))

  # blink the prompt, half a second on and half a second off
  if int(badge.ticks / 500) % 2:
    screen.text("PRESS ENTER TO START", rect(0, 108, 160, 11), align=image.CENTER)


STATS_PITCH = 9
STATS_PAD_X = 8
STATS_PAD_Y = 6


def draw_stats(stats):
  lines = ["%s %d%%" % (name, value) for name, value in stats]
  width = max(screen.measure_text(line)[0] for line in lines) + STATS_PAD_X * 2
  # the two extra pixels give the last line a little more under it
  height = len(lines) * STATS_PITCH + STATS_PAD_Y * 2 + 2
  x = SCENE.x + (SCENE.w - width) / 2
  y = SCENE.y + (SCENE.h - height) / 2
  screen.pen = color.rgb(228, 220, 220, 200)
  screen.shape(shape.rounded_rectangle(x - 1, y - 1, width + 2, height + 2, 5))
  screen.pen = color.rgb(18, 16, 28, 215)
  screen.shape(shape.rounded_rectangle(x, y, width, height, 4))

  for n, line in enumerate(lines):
    draw_shadowed(line, x + STATS_PAD_X, y + STATS_PAD_Y + n * STATS_PITCH)
