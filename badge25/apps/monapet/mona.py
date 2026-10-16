import sys
import os

sys.path.insert(0, "/system/apps/monapet")
os.chdir("/system/apps/monapet")

from badgeware import screen, brushes, SpriteSheet, shapes, clamp, io
import random
import math

# this class defines our little friend, modify it to change their behaviour!
#
# - move mona to a random location
# - change mona's mood
# - alter mona's stats (happiness, hunger, cleanliness)
# - change mona's appearance
#
# the ui will automatically update to reflect mona's state

class Mona:
  _moods = []
  _animations = {}

  def __init__(self, y):
    self._happy = 100
    self._hunger = 100
    self._clean = 100
    self._animation = None
    self._mood = None
    self._mood_changed_at = (io.ticks / 1000)
    self._action = None
    self._action_changed_at = None
    self._position_changed_at = (io.ticks / 1000)
    self._position = (80, y + 2)
    self._direction = 1
    self._target = 80
    self._speed = 0.5
    self.set_mood("default")

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
    # break out x and y into a shorter hand variables
    x, y = self._position

    # select sprite for current animation frame
    if self._action:
      action_time = (io.ticks / 1000) - self._action_changed_at
      image = Mona._animations[self._action].frame(round(action_time * 10))
    else:
      image = Mona._animations[self._mood].frame(round(io.ticks / 100))

    width, height = image.width * 2, image.height * 2

    # draw monas shadow
    screen.brush = brushes.color(0, 0, 0, 20)
    screen.draw(shapes.rectangle(x - (width / 2) + 5, y , width - 10, 2))
    screen.draw(shapes.rectangle(x - (width / 2) + 5 + 2, y - 2, width - 10 - 4, 4))

    # invert mona if they are walking left
    width *= self._direction

    # is mona floating?
    floating = math.sin(io.ticks / 250) * 5 + 5 if self._mood == "dead" else 0

    # offset sprite
    x -= abs(width / 2)
    y -= height + floating

    # draw mona
    alpha = 150 if self._mood == "dead" else 255
    image.alpha = alpha
    screen.scale_blit(image, x, y, width, height)

    # draw monas reflection
    image.alpha = int(alpha * 0.2)
    screen.scale_blit(image, x, self._position[1] + (floating / 2) + 1, width, -20)
    image.alpha = 255

  # set a new target position for mona to move to
  def move_to(self, target):
    self._target = target
    self._position_changed_at = (io.ticks / 1000)

  # move mona back into centre frame
  def move_to_center(self):
    self._target = 80
    self._position_changed_at = (io.ticks / 1000)

  # select a random position for mona to move to
  def move_to_random(self):
    self.move_to(random.randint(90, 130))

  # return the number of seconds since mona moved
  def time_since_last_position_change(self):
    return (io.ticks / 1000) - self._position_changed_at

  # return monas current position
  def position(self):
    return self._position

  # change monas mood
  def set_mood(self, mood):
    self._mood = mood
    self._mood_changed_at = (io.ticks / 1000)

  def do_action(self, action):
    self._action = action
    self._action_changed_at = (io.ticks / 1000)

  def current_action(self):
    return self._action

  def is_dead(self):
    return self._happy == 0 or self._clean == 0 or self._hunger == 0

  # increase or decrease monas statistics
  def happy(self, amount=0):
    self._happy = clamp(self._happy + amount, 0, 100)
    return self._happy

  def clean(self, amount=0):
    self._clean = clamp(self._clean + amount, 0, 100)
    return self._clean

  def hunger(self, amount=0):
    self._hunger = clamp(self._hunger + amount, 0, 100)
    return self._hunger

  # update monas position
  def update(self):
    # break out x and y into a shorter hand variables
    x, y = self._position

    # if mona isn't at their target position then move towards it
    if x != self._target and not self._action:
      self._direction = 1 if x > self._target else -1
      self._position = (x - (self._speed * self._direction), y)

    # if mona is performing an action then let it run for 2 seconds and end it
    if self._action:
      if (io.ticks / 1000) - self._action_changed_at > 2:
        self._action = None

  # select a random mood for mona
  def random_idle(self):
    idles = ["code", "default", "heart", "dance"]
    self.set_mood(random.choice(idles))

  # return the number of seconds since monas mood changed
  def time_since_last_mood_change(self):
    return (io.ticks / 1000) - self._mood_changed_at

# define monas animations and the number of frames
animations = {
  # actions
  "heart":   14, # play
  "eating":  12, # eat
  "dance":    6, # clean

  # idles
  "code":     4,
  "default": 11,
  "notify":  11,

  # sad.
  "dead":     7, # oh no, mona!
}

# load the spritesheets for monas animations
for name, frame_count in animations.items():
  sprites = SpriteSheet(f"/system/assets/mona-sprites/mona-{name}.png", frame_count, 1)
  Mona._animations[name] = sprites.animation()  # noqa: SLF001
print("done")

Mona._moods = list(Mona._animations.keys())  # noqa: SLF001

