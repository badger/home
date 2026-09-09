import random
import math

# this class defines our little friend, modify it to change their behaviour!
#
# - move pet to a random location
# - change pet's mood
# - alter pet's stats (happiness, hunger, cleanliness)
# - change pet's appearance
#
# the ui will automatically update to reflect pet's state

class Pet:
  _moods = []
  _animations = {}

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
    self._notify = False
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
    # break out x and y into a shorter hand variables
    x, y = self._position

    # select sprite for current animation frame
    if self._action:
      action_time = (badge.ticks / 1000) - self._action_changed_at
      image = Pet._animations[self._action].sprite(round(action_time * 10) % animations[self._action], 0)
    else:
      image = Pet._animations[self._mood].sprite(round(badge.ticks / 100) % animations[self._mood], 0)

    if self._notify:
      notify_image = Pet._animations["notify"].sprite(round(badge.ticks / 4) % animations["notify"], 0)
    else:
      notify_image = None

    width, height = image.width, image.height

    # invert pet if they are walking left
    width *= -self._direction

    # is pet floating?
    floating = math.sin(badge.ticks / 250) * 5 + 5 if self._mood == "dead" else 0

    # offset sprite
    x -= abs(width / 2)
    y -= height + floating

    # draw pet
    alpha = 150 if self._mood == "dead" else 255
    image.alpha = alpha
    screen.blit(image, rect(x, y, width, height))

    # draw black cloud
    if notify_image:
      screen.blit(notify_image, rect(x, y, width, height))

  # set a new target position for pet to move to
  def move_to(self, target):
    self._target = target
    self._position_changed_at = (badge.ticks / 1000)

  # move pet back into centre frame
  def move_to_center(self):
    self._target = 80
    self._position_changed_at = (badge.ticks / 1000)

  # select a random position for pet to move to
  def move_to_random(self):
    self.move_to(random.randint(20, 140))

  # return the number of seconds since pet moved
  def time_since_last_position_change(self):
    return (badge.ticks / 1000) - self._position_changed_at

  # return pets current position
  def position(self):
    return self._position

  # change pets mood
  def set_mood(self, mood):
    self._mood = mood
    self._mood_changed_at = (badge.ticks / 1000)

  def do_action(self, action):
    self._action = action
    self._action_changed_at = (badge.ticks / 1000)

  def set_notify(self):
    self._notify = True

  def unset_notify(self):
    self._notify = False

  def set_speed(self, speed):
    self._speed = speed

  def current_action(self):
    return self._action

  def is_dead(self):
    return self._happy == 0 or self._clean == 0 or self._hunger == 0

  # increase or decrease pets statistics
  def happy(self, amount=0):
    self._happy = clamp(self._happy + amount, 0, 100)
    return self._happy

  def clean(self, amount=0):
    self._clean = clamp(self._clean + amount, 0, 100)
    return self._clean

  def hunger(self, amount=0):
    self._hunger = clamp(self._hunger + amount, 0, 100)
    return self._hunger

  # update pets position
  def update(self):
    # break out x and y into a shorter hand variables
    x, y = self._position

    # if pet isn't at their target position then move towards it
    if abs(x - self._target) > self._speed and not self._action:
      self._direction = 1 if x > self._target else -1
      x -= (self._speed * self._direction)
      self._position = (x, y)
      # if we've reached our destination, cancel out of the run animation
      if abs(x - self._target) <= self._speed and self._mood == "run":
        self.random_idle()

    # if pet is performing an action then let it run for 4 seconds and end it
    if self._action:
      if (badge.ticks / 1000) - self._action_changed_at > 4:
        self._action = None

  # select a random mood for pet
  def random_idle(self):
    idles = ["dig", "sleep", "idle", "lick", "tail"]
    self.set_mood(random.choice(idles))

  # return the number of seconds since pets mood changed
  def time_since_last_mood_change(self):
    return (badge.ticks / 1000) - self._mood_changed_at

# define pets animations and the number of frames
animations = {
  # actions
  "dance":    6, # play
  "clean":    11, # clean
  "eat":      12, # eat
  "run":      5,
  "sleep":    12,
  "dig":      5,
  "idle":     14,
  "lick":     4,
  "tail":     4,
  "dead":     14,
  "notify":   4

}


# load the spritesheets for pets animations
for name, frame_count in animations.items():
  Pet._animations[name] = image.load(f"assets/squirrel-sprites/{name}.png").spritesheet(frame_count, 1)  # noqa: SLF001
print("done")

Pet._moods = list(Pet._animations.keys())  # noqa: SLF001
