import math
import random

import icons

COLUMNS = 4
ROWS = 3
CARD_W = 19
CARD_H = 21
GAP = 3
WINDOW = rect(4, 20, COLUMNS * CARD_W + (COLUMNS - 1) * GAP + 8, ROWS * CARD_H + (ROWS - 1) * GAP + 13)
GRID_X = WINDOW.x + 4
GRID_Y = WINDOW.y + 9
FLIP_MS = 160
MISMATCH_MS = 900
HEART_MS = 1400
SAD_MS = 1200

FOOD_CARDS = (
  ("food", "*", color.rgb(255, 125, 237)),
  ("food", "7", color.rgb(242, 77, 91)),
  ("food", "9", color.rgb(233, 110, 18)),
  ("food", ">", color.rgb(249, 193, 62)),
  ("food", "2", color.rgb(255, 171, 168)),
  ("food", "I", color.rgb(95, 237, 131)),
)
HAT_CARDS = (
  ("hats", ",", color.rgb(249, 193, 62)),
  ("hats", "O", color.rgb(174, 133, 255)),
  ("hats", ">", color.rgb(22, 143, 251)),
  ("hats", "J", color.rgb(144, 150, 146)),
  ("hats", "M", color.rgb(233, 110, 18)),
  ("hats", "+", color.rgb(192, 120, 60)),
)

BACK = color.rgb(88, 58, 247)
BACK_EDGE = color.rgb(174, 133, 255)
FACE = color.rgb(242, 245, 243)
CURSOR = color.rgb(95, 237, 131)
DIM = color.rgb(18, 16, 28, 70)
HEART = color.rgb(247, 54, 120)
SAD = color.rgb(249, 193, 62)
WINDOW_EDGE = color.rgb(228, 220, 220, 200)
WINDOW_FILL = color.rgb(18, 16, 28, 215)


class Card:
  def __init__(self, face):
    self.face = face
    self.up = False
    self.matched = False
    self.flipped_at = -FLIP_MS

  def flip(self, up):
    self.up = up
    self.flipped_at = badge.ticks


class Match:
  def __init__(self):
    pairs = self.pick_pairs()
    faces = pairs + pairs
    self.cards = [Card(face) for face in self.shuffled(faces)]
    self.cursor = 0
    self.first = None
    self.second = None
    self.hide_at = None
    self.hearts = []
    self.sad_until = 0
    self.matches = 0
    self.cleared_at = None

  def pick_pairs(self):
    food = list(FOOD_CARDS)
    hats = list(HAT_CARDS)
    chosen = []
    for pool in (food, food, food, hats, hats, hats):
      chosen.append(pool.pop(random.randrange(len(pool))))
    return chosen

  def shuffled(self, items):
    items = list(items)
    for index in range(len(items) - 1, 0, -1):
      other = random.randrange(index + 1)
      items[index], items[other] = items[other], items[index]
    return items

  def cleared(self):
    return self.matches == len(self.cards) // 2

  def finished(self):
    return self.cleared_at is not None and badge.ticks - self.cleared_at >= HEART_MS

  def pairs_left(self):
    return len(self.cards) // 2 - self.matches

  def move(self, dx, dy):
    column = (self.cursor % COLUMNS + dx) % COLUMNS
    row = (self.cursor // COLUMNS + dy) % ROWS
    self.cursor = row * COLUMNS + column

  def select(self):
    if self.hide_at is not None:
      return None
    card = self.cards[self.cursor]
    if card.up or card.matched:
      return None
    card.flip(True)
    if self.first is None:
      self.first = card
      return None
    self.second = card
    if self.first.face == card.face:
      self.first.matched = card.matched = True
      self.first = self.second = None
      self.matches += 1
      self.cheer()
      if self.cleared():
        self.cleared_at = badge.ticks
        return "cleared"
      return "match"
    self.hide_at = badge.ticks + MISMATCH_MS
    self.sad_until = badge.ticks + SAD_MS
    return "miss"

  def cheer(self):
    x, y = self.card_origin(self.cursor)
    for index in range(5):
      self.hearts.append((x + CARD_W / 2 + random.randint(-8, 8), y + 4, badge.ticks + index * 90))

  def update(self):
    if self.hide_at is not None and badge.ticks >= self.hide_at:
      self.first.flip(False)
      self.second.flip(False)
      self.first = self.second = None
      self.hide_at = None
    self.hearts = [heart for heart in self.hearts if badge.ticks - heart[2] < HEART_MS]

  def card_origin(self, index):
    return GRID_X + (index % COLUMNS) * (CARD_W + GAP), GRID_Y + (index // COLUMNS) * (CARD_H + GAP)

  def draw(self):
    screen.pen = WINDOW_EDGE
    screen.shape(shape.rounded_rectangle(WINDOW.x - 1, WINDOW.y - 1, WINDOW.w + 2, WINDOW.h + 2, 5))
    screen.pen = WINDOW_FILL
    screen.shape(shape.rounded_rectangle(WINDOW.x, WINDOW.y, WINDOW.w, WINDOW.h, 4))
    for index, card in enumerate(self.cards):
      self.draw_card(index, card)
    for x, y, born in self.hearts:
      age = badge.ticks - born
      if age >= 0:
        draw_heart(x + math.sin(age / 120) * 2, y - age / 40, 2.5)

  def draw_card(self, index, card):
    x, y = self.card_origin(index)
    if index == self.cursor:
      screen.pen = CURSOR
      screen.shape(shape.rounded_rectangle(x - 2, y - 2, CARD_W + 4, CARD_H + 4, 4))
    progress = min(1.0, (badge.ticks - card.flipped_at) / FLIP_MS)
    showing_face = card.up if progress >= 0.5 else not card.up
    squash = abs(1 - progress * 2)
    width = max(1, CARD_W * squash)
    left = x + (CARD_W - width) / 2
    if showing_face:
      screen.pen = FACE
      screen.shape(shape.rounded_rectangle(left, y, width, CARD_H, 3))
      if progress >= 1:
        family, char, fill = card.face
        icons.draw(family, char, x + (CARD_W - icons.WIDTH) // 2, y + (CARD_H - icons.HEIGHT) // 2, fill)
        if card.matched:
          screen.pen = DIM
          screen.shape(shape.rounded_rectangle(x, y, CARD_W, CARD_H, 3))
    else:
      screen.pen = BACK_EDGE
      screen.shape(shape.rounded_rectangle(left, y, width, CARD_H, 3))
      screen.pen = BACK
      screen.shape(shape.rounded_rectangle(left + 1, y + 1, max(1, width - 2), CARD_H - 2, 2))
      if progress >= 1:
        screen.pen = BACK_EDGE
        screen.shape(shape.regular_polygon(vec2(x + CARD_W / 2, y + CARD_H / 2), 3, 4))

  def sad(self):
    return badge.ticks < self.sad_until


def draw_heart(x, y, size):
  screen.pen = HEART
  screen.shape(shape.circle(vec2(x - size * 0.5, y), size * 0.6))
  screen.shape(shape.circle(vec2(x + size * 0.5, y), size * 0.6))
  screen.shape(shape.custom([vec2(x - size * 1.05, y + size * 0.2), vec2(x + size * 1.05, y + size * 0.2), vec2(x, y + size * 1.4)]))
