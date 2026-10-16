import sys
import os

sys.path.insert(0, "/system/apps/quest")
os.chdir("/system/apps/quest")

import math
import random
from badgeware import State, PixelFont, Image, brushes, screen, io, shapes, run
from beacon import GithubUniverseBeacon
from aye_arr.nec import NECReceiver
import ui



small_font = PixelFont.load("/system/assets/fonts/ark.ppf")
large_font = PixelFont.load("/system/assets/fonts/absolute.ppf")
splash = Image.load("assets/splash.png")

class Quest:
  def __init__(self, id, code, name):
    self.id = id
    self.name = name
    self.code = code

quests = [
  Quest(1, 0x11, "Hack Your Badge"),
  Quest(2, 0x22, "Whats up Docs"),
  Quest(3, 0x33, "Stars Lounge"),
  Quest(4, 0x44, "GitHub Next"),
  Quest(5, 0x55, "Open Source Zone"),
  Quest(6, 0x66, "Demos & Donuts"),
  Quest(7, 0x77, "GitHub Learn"),
  Quest(8, 0x88, "Octocat Generator"),
  Quest(9, 0x99, "Makerspace")
]

# setup handled ir button codes
for quest in quests:
  GithubUniverseBeacon.BUTTON_CODES[quest.id] = quest.code


state = {
  "completed": []
}

# load state here
State.load("quest", state)

_last_task_completed = None
_last_task_completed_at = None
def complete_quest(id):
  global _last_task_completed_at, _last_task_completed
  if id not in state["completed"] and id <= len(quests):
    _last_task_completed_at = io.ticks
    _last_task_completed = quests[id - 1]
    state["completed"].append(id)
    State.save("quest", state)

# setup the ir receiver to callback to our complete quest method when a code
# is received...
ir = GithubUniverseBeacon()
ir.on_known = complete_quest
receiver = NECReceiver(21, 0, 0)    # Pin, PIO, SM
receiver.bind(ir)
receiver.start()

def update():
  global _last_task_completed_at

  # decode any ir events that have occurred
  receiver.decode()

  # clear the screen
  screen.brush = brushes.color(35, 41, 37)
  screen.draw(shapes.rectangle(0, 0, 160, 120))

  # draw the quest tile grid
  ui.draw_status(state["completed"])
  ui.draw_tiles(state["completed"])

  # if button pressed and we're showing a quest completed screen then dismiss it
  if io.pressed and _last_task_completed_at:
    _last_task_completed_at = None

  if _last_task_completed_at:
    # if you find a new location then show well done screen
    width, height = 160, 120
    zoom_speed = 250
    if io.ticks - _last_task_completed_at < zoom_speed:
      # for first 250ms of well done screen animate it zooming in
      alpha = ((io.ticks - _last_task_completed_at) / zoom_speed)
      zoom = ((io.ticks - _last_task_completed_at) / zoom_speed) * 10
      width *= (zoom / 10)
      height *= (zoom / 10)
      splash.alpha = int(alpha * 255)
      screen.scale_blit(splash, 80 - width / 2, 60 - height / 2, width, height)
    else:
      splash.alpha = 255
      screen.blit(splash, 0, 0)

      label = _last_task_completed.name
      message = "Location Unlocked!"
      if len(state["completed"]) == len(quests):
        message = "Side Quest Complete!"

      screen.font = large_font
      lw, _ = screen.measure_text(label)
      screen.font = small_font
      mw, _ = screen.measure_text(message)

      # draw message bubble
      screen.brush = brushes.color(46, 160, 67, 200)
      lw_corners = (4, 4, 0, 0) if lw < mw else (4, 4, 4, 4)
      mw_corners = (4, 4, 4, 4) if lw < mw else (0, 0, 4, 4)
      screen.draw(shapes.rounded_rectangle(80 - (lw / 2) - 4, 2, lw + 8, 18, *lw_corners))
      screen.draw(shapes.rounded_rectangle(80 - (mw / 2) - 4, 20 , mw + 8, 12, *mw_corners))

      # draw task label and message
      screen.brush = brushes.color(255, 255, 255, 255)
      screen.font = large_font
      screen.text(label, 80 - (lw / 2), 2)
      screen.font = small_font
      screen.text(message, 80 - (mw / 2), 19)


if __name__ == "__main__":
    run(update)
