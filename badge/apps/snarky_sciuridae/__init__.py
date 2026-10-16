APP_DIR = "/system/apps/snarky_sciuridae"

import sys
import os

# Standalone bootstrap for finding app assets
os.chdir(APP_DIR)

# Standalone bootstrap for module imports
sys.path.insert(0, APP_DIR)

import ui
from vpet import Pet
from badgeware import State

pet = Pet(95)  # create pet!

# speed at which each statistic goes from 100% to 0%
happiness_duration = 1800
hunger_duration = 1200
cleanliness_duration = 2400

screen.antialias = image.X2


def game_update():
    global pet

    if not pet.is_dead():
        # calculate pet's new stats based on the time since last update
        seconds = badge.ticks_delta / 1000

        # work out how much pet's stats have reduce since the last frame
        happy_delta = (seconds / happiness_duration) * 100
        pet.happy(-happy_delta)
        hunger_delta = (seconds / hunger_duration) * 100
        pet.hunger(-hunger_delta)
        clean_delta = (seconds / cleanliness_duration) * 100
        pet.clean(-clean_delta)

        # play with pet!
        if badge.pressed(BUTTON_LEFT):
            pet.happy(30)
            pet.unset_notify()
            pet.do_action("dance")

        # feed pet!
        if badge.pressed(BUTTON_SELECT):
            pet.hunger(30)
            pet.unset_notify()
            pet.do_action("eat")

        # clean pet!
        if badge.pressed(BUTTON_RIGHT):
            pet.clean(30)
            pet.unset_notify()
            pet.do_action("clean")

        # every 20 seconds pet will move to a new location
        if pet.time_since_last_position_change() > 20:
            pet.set_mood("run")
            pet.move_to_random()

        # every eight seconds pet will select a new idle animation
        if pet.time_since_last_mood_change() > 8:
            pet.random_idle()

        # yikes, pet is in a bad way!
        if min(pet.hunger(), pet.happy(), pet.clean()) < 30:
            pet.set_notify()

    else:
        pet.set_mood("dead")
        pet.set_speed(1)
        pet.unset_notify()
        pet.move_to_center()

        # if user pressed SELECT then reset pet's stats
        if badge.pressed(BUTTON_SELECT):
            pet = Pet(95)


def update():
    # update the game state based on user input and timed events
    game_update()

    # update pets state (position)
    pet.update()

    # draw the background scene
    ui.background()

    # draw our little friend
    pet.draw()

    # draw the user interface elements
    if not pet.is_dead():
        ui.draw_bar("happy",  8, 92, pet.happy())
        ui.draw_bar("hunger", 58, 92, pet.hunger())
        ui.draw_bar("clean",  108, 92, pet.clean())

        ui.draw_button(7, 107,  "play", pet.current_action() == "dance")
        ui.draw_button(57, 107,  "feed", pet.current_action() == "eat")
        ui.draw_button(107, 107, "clean", pet.current_action() == "clean")
    else:
        ui.draw_button(57, 107, "reset", False)

    ui.draw_scanlines()

    ui.draw_header()


def init():
    state = {
        "happy": 100,
        "hunger": 100,
        "clean": 100,
    }
    if State.load("badgepet", state):
        pet.load(state)

    del state


def on_exit():
    State.save("badgepet", pet.save())


init()
run(update)
