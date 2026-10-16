import os
import sys

APP_DIR = "/system/apps/demos"

sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

badge.mode(LORES | VSYNC)


import gc
import sys

from demos import demos
names = sorted(demos.keys())

selected = None
menu_index = 0
demo = None

def load_demo(index):
  global selected, demo

  # unload previously running demo
  if demo:
    del sys.modules[f"{APP_DIR}/demos/{names[selected]}"]

  gc.collect()

  selected = index
  selected %= len(names)

  name = names[selected]
  demo = __import__(demos[name])

  print(f"loaded example {name} ({round(gc.mem_free() / 1000)}KB free)")

selected = 0
load_demo(0)

def update():
  global selected, menu_index

  if badge.pressed(BUTTON_DOWN):
    load_demo(selected + 1)

  if badge.pressed(BUTTON_UP):
    load_demo(selected - 1)

  # make sure a font is loaded by default in case the example wishes to use it
  screen.font = font.sins

  # call example update function
  demo.update()

  # restore font for our use in case demo overrode it
  screen.font = font.sins

  if menu_index < selected:
    menu_index += (selected - menu_index) / 20
  if menu_index > selected:
    menu_index -= (menu_index - selected) / 20

  # render 5 items above the current item, and 1 below, fade out from current
  for i in range(len(names)):
    name = names[i]

    y = 102 + (i * 10) - menu_index * 10
    alpha = abs(y) / 3
    if i == selected:
      screen.pen = color.rgb(20, 40, 60, 255)
      w, h = screen.measure_text(name)
      screen.rectangle(3, y + 2, w + 4, h - 2)

      screen.pen = color.rgb(255, 255, 255, 255)
      screen.text(name, 5, y)
    else:
      screen.pen = color.rgb(20, 40, 60, alpha)
      w, h = screen.measure_text(name)
      screen.rectangle(3, y + 2, w + 4, h - 2)

      screen.pen = color.rgb(255, 255, 255, alpha)
      screen.text(name, 5, y)


run(update)
