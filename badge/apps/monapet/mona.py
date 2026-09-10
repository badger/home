import math
import random


ANIMATIONS = {
    "heart": 14,
    "eating": 12,
    "dance": 6,
    "code": 4,
    "default": 11,
    "notify": 11,
    "dead": 7,
}


class Mona:
    animations = {}

    def __init__(self, y):
        self._happy = 100
        self._hunger = 100
        self._clean = 100
        self._mood = "default"
        self._mood_changed_at = badge.ticks / 1000
        self._action = None
        self._action_changed_at = 0
        self._position_changed_at = badge.ticks / 1000
        self._position = (80, y + 2)
        self._direction = 1
        self._target = 80
        self._speed = 30
        self._notify = False

    def load(self, state):
        self._happy = state.get("happy", 100)
        self._hunger = state.get("hunger", 100)
        self._clean = state.get("clean", 100)

    def save(self):
        return {"happy": self._happy, "hunger": self._hunger, "clean": self._clean}

    def draw(self):
        name = self._action or self._mood
        frame_time = badge.ticks / (100 if self._action else 160)
        sprite = Mona.animations[name].sprite(int(frame_time) % ANIMATIONS[name], 0)
        x, y = self._position
        floating = math.sin(badge.ticks / 250) * 5 + 5 if self._mood == "dead" else 0
        width = sprite.width * 2 * self._direction
        height = sprite.height * 2
        sprite.alpha = 150 if self._mood == "dead" else 255
        screen.pen = color.rgb(0, 0, 0, 40)
        screen.shape(shape.rounded_rectangle(x - abs(width) / 2 + 5, y - 3, abs(width) - 10, 5, 2))
        screen.blit(sprite, rect(x - abs(width) / 2, y - height - floating, width, height))

        if self._notify:
            notify = Mona.animations["notify"].sprite(int(badge.ticks / 180) % ANIMATIONS["notify"], 0)
            screen.blit(notify, rect(x - abs(width) / 2, y - height, width, height))

    def move_to(self, target):
        self._target = target
        self._position_changed_at = badge.ticks / 1000

    def move_to_center(self):
        self.move_to(80)

    def move_to_random(self):
        self.move_to(random.randint(30, 130))

    def time_since_last_position_change(self):
        return badge.ticks / 1000 - self._position_changed_at

    def set_mood(self, mood):
        self._mood = mood
        self._mood_changed_at = badge.ticks / 1000

    def do_action(self, action):
        self._action = action
        self._action_changed_at = badge.ticks / 1000

    def set_notify(self):
        self._notify = True

    def unset_notify(self):
        self._notify = False

    def set_speed(self, speed):
        self._speed = speed

    def current_action(self):
        return self._action

    def is_dead(self):
        return self._happy <= 0 or self._clean <= 0 or self._hunger <= 0

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
        step = self._speed * (badge.ticks_delta / 1000)
        distance = self._target - x
        if abs(distance) > step and not self._action:
            self._direction = 1 if distance > 0 else -1
            self._position = (x + step * self._direction, y)
        elif not self._action:
            self._position = (self._target, y)

        if self._action and badge.ticks / 1000 - self._action_changed_at > 4:
            self._action = None

    def random_idle(self):
        self.set_mood(random.choice(("code", "default", "heart", "dance")))

    def time_since_last_mood_change(self):
        return badge.ticks / 1000 - self._mood_changed_at


for animation, frames in ANIMATIONS.items():
    Mona.animations[animation] = image.load("assets/mona-sprites/mona-%s.png" % animation).spritesheet(frames, 1)
