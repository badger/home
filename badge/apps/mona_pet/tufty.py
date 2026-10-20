import math
import random

# every animation: the Mona sheet it plays from and how many frames that
# holds. She has no sheet of her own for some of them, so those borrow one.
SHEETS = {
    "dance": ("dance", 6),
    "clean": ("love", 14),
    "eat": ("eating", 12),
    "run": ("default", 11),
    "sleep": ("sleep", 24),
    "idle": ("default", 11),
    "code": ("code", 4),
    "heart": ("heart", 14),
    "dead": ("dead", 7),
    "notify": ("notify", 11),
}
FRAMES = {name: count for name, (_, count) in SHEETS.items()}

# her art is drawn pixel-doubled, and fills its cell down to her feet
SCALE = 2

sheet_images = {sheet: image.load("assets/mona-sprites/mona-%s.png" % sheet)
                for sheet in {sheet for sheet, _ in SHEETS.values()}}
sheets = {name: sheet_images[sheet].spritesheet(count, 1)
          for name, (sheet, count) in SHEETS.items()}


def frame(mood):
  """One frame of a mood, for the screens that draw her outside the game."""
  return sheets[mood].sprite(round(badge.ticks / 100) % FRAMES[mood], 0)


# our little friend: where he is, how he feels, and which frame of which
# animation that adds up to
class Tufty:
  def __init__(self, y):
    self._happy = 100
    self._hunger = 100
    self._clean = 100
    self._animation = None
    self._mood = None
    self._mood_changed_at = (badge.ticks / 1000)
    self._action = None
    self._action_changed_at = None
    self._position_changed_at = (badge.ticks / 1000)
    self._position = (80, y + 2)
    self._direction = 1
    self._target = 80
    self._speed = 3
    self.set_mood("idle")

  def load(self, state):
    self._happy = state.get("happy", 0)
    self._hunger = state.get("hunger", 0)
    self._clean = state.get("clean", 0)

  def save(self):
    return {
      "happy": self._happy,
      "hunger": self._hunger,
      "clean": self._clean,
    }

  def draw(self):
    x, y = self._position

    if self._action:
      action_time = (badge.ticks / 1000) - self._action_changed_at
      sprite = sheets[self._action].sprite(round(action_time * 10) % FRAMES[self._action], 0)
    # when something needs doing she waves for attention, unless she is
    # busy, asleep or gone
    elif (self.alive() and self._mood != "sleep"
          and min(self._happy, self._hunger, self._clean) < 30):
      sprite = frame("notify")
    else:
      sprite = frame(self._mood)

    width, height = sprite.width * SCALE, sprite.height * SCALE

    # invert pet if they are walking left
    width *= -self._direction

    floating = math.sin(badge.ticks / 250) * 5 + 5 if self._mood == "dead" else 0

    # the patch of ground she stands on, drawing in tighter the further she
    # floats off it. Her feet are at y - 15, and the edge is hard like the
    # art it sits under.
    lift = max(0.0, 1.0 - floating / 20)
    antialias = screen.antialias
    screen.antialias = image.OFF
    screen.pen = color.rgb(0, 0, 0, 70)
    screen.shape(shape.ellipse(x, y - 15, 14 * lift, 4 * lift))
    screen.antialias = antialias

    x -= abs(width / 2)
    y -= height + 15 + floating

    screen.alpha = 150 if self._mood == "dead" else 255
    screen.blit(sprite, rect(x, y, width, height))
    screen.alpha = 255

  def move_to(self, target):
    self._target = target
    self._position_changed_at = (badge.ticks / 1000)

  def place(self, x):
    self._position = (x, self._position[1])
    self._target = x
    self._position_changed_at = (badge.ticks / 1000)

  def position(self):
    return self._position

  def move_to_center(self):
    self._target = 80
    self._position_changed_at = (badge.ticks / 1000)

  def move_to_random(self):
    self.move_to(random.randint(20, 140))

  def time_since_last_position_change(self):
    return (badge.ticks / 1000) - self._position_changed_at

  def set_mood(self, mood):
    self._mood = mood
    self._mood_changed_at = (badge.ticks / 1000)

  def do_action(self, action):
    self._action = action
    self._action_changed_at = (badge.ticks / 1000)

  def set_speed(self, speed):
    self._speed = speed

  def current_action(self):
    return self._action

  def asleep(self):
    return self._mood == "sleep" and self.alive()

  def alive(self):
    return self._happy > 0 and self._clean > 0 and self._hunger > 0

  def happy(self, amount=0):
    self._happy = clamp(self._happy + amount, 0, 100)
    return self._happy

  def clean(self, amount=0):
    self._clean = clamp(self._clean + amount, 0, 100)
    return self._clean

  def hunger(self, amount=0):
    self._hunger = clamp(self._hunger + amount, 0, 100)
    return self._hunger

  def update(self):
    x, y = self._position

    if abs(x - self._target) > self._speed and not self._action:
      self._direction = 1 if x > self._target else -1
      x -= (self._speed * self._direction)
      self._position = (x, y)
      if abs(x - self._target) <= self._speed and self._mood == "run":
        self.random_idle()

    # an action runs for four seconds, then he goes back to idling
    if self._action:
      if (badge.ticks / 1000) - self._action_changed_at > 4:
        self._action = None

  def random_idle(self):
    idles = ["idle", "idle", "code", "heart"]
    self.set_mood(random.choice(idles))

  def time_since_last_mood_change(self):
    return (badge.ticks / 1000) - self._mood_changed_at
