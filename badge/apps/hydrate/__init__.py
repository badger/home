import sys
import os
import math

sys.path.insert(0, "/system/apps/hydrate")
os.chdir("/system/apps/hydrate")

from badgeware import State

CX = screen.width / 2
CY = screen.height / 2

state = {
    "current": 0,
    "goal": 2000
}


WHITE = color.rgb(255, 255, 255)
BLACK = color.rgb(0, 0, 0)
SHADOW = color.rgb(0, 0, 0, 125)
BLUE1 = color.rgb(116, 204, 244)
BLUE2 = color.rgb(28, 163, 236)
BLUE3 = color.rgb(15, 94, 156)
GREEN = color.rgb(0, 150, 0)

screen.antialias = image.X4

large_font = font.smart
screen.font = large_font

graph_max = math.degrees(math.pi * 2)


def goal_met():
    return state["current"] >= state["goal"]


def draw_graph(x, y, r, value):

    v = clamp(value, 0, state["goal"])

    # scale the current amount in ml to degrees for our graph
    v = (v * (graph_max / state["goal"]))

    # rotate and position it so 0 is at the top
    pie = shape.pie(0, 0, r, 0, v)
    pie.transform = mat3().translate(x, y)

    # Draw the  remaining non moving elements of the graph
    screen.pen = SHADOW
    screen.shape(shape.circle(x + 2, y + 4, r))

    screen.pen = BLUE3 if not goal_met() else GREEN
    screen.shape(shape.circle(x, y, r))

    screen.pen = BLUE2
    screen.shape(pie)
    screen.pen = WHITE
    screen.shape(shape.circle(x, y, r - 8))
    screen.pen = WHITE
    screen.shape(shape.circle(x, y, r).stroke(2))

    # if the graph is big enough, put the text in the centre.
    if r > 30:
        screen.pen = BLUE3
        text = f"{state["current"]}ml"
        tw = screen.measure_text(text)[0]
        tx = x - tw / 2
        ty = y - 6
        screen.text(text, tx, ty)


MENU_OPEN_Y = CY
MENU_CLOSED_Y = screen.height - 15
menu_pos = [0, MENU_CLOSED_Y, screen.width, screen.height - CY]
speed = 11.0
show_menu = False
menu_value = 0


def draw_menu():
    global menu_pos, show_menu, menu_value

    # unpack the menu position
    x, y, w, h = menu_pos

    # Slide the menu open/close
    if y >= MENU_OPEN_Y and show_menu:
        direction = -1
        y += speed * direction
    elif y <= MENU_CLOSED_Y and not show_menu:
        direction = 1
        y += speed * direction

    # clamp the position
    y = clamp(y, MENU_OPEN_Y, MENU_CLOSED_Y)

    # store the values in the list
    menu_pos = [x, y, w, h]

    # darken the background when the menu is showing
    if show_menu:
        screen.pen = SHADOW
        screen.clear()

    # draw the menu background
    screen.pen = WHITE
    screen.shape(shape.rounded_rectangle(x, y, w, h, 3, 3, 0, 0))

    # Show the menu elements if the menu is showing including during transition
    screen.pen = BLACK
    if y != MENU_CLOSED_Y:
        t = f"{menu_value}ml"
        tx = CX - screen.measure_text(str(t))[0] / 2
        screen.text(t, tx, y + 42)
        screen.text("-", 27, y + 42)
        screen.text("+", 127, y + 42)
        screen.text("OK", screen.width - 16, y + 18)

        # gold star for meeting your daily goal! :)
        sx, sy = CX, y + 23
        if goal_met():
            screen.pen = color.rgb(255, 255, 0)
            screen.shape(shape.star(sx, sy, 5, 9, 13))
        screen.pen = SHADOW
        screen.shape(shape.star(sx, sy, 5, 9, 13).stroke(2))

    else:
        screen.text("^", CX - 3, y + 2)


def draw_background():

    cy = CY - 8
    cx = CX

    y = 0
    for _row in range(12):
        x = 0
        for _col in range(16):
            dist = math.sqrt((x + 5 - cx) ** 2 + (y + 5 - cy) ** 2)
            pulse = (math.sin(-badge.ticks / 400 + (dist / 6)) / 2) + 0.5
            pulse = 0.8 + (pulse / 2)
            screen.pen = color.rgb(255, 255, 255, 50 * pulse)
            screen.rectangle(x, y, 10, 10)
            x += 10
        y += 10


def init():
    global state
    State.load("hydrate", state)


def update():
    global state, show_menu, menu_value

    if badge.pressed(BUTTON_SELECT):
        show_menu = not show_menu

    if show_menu:
        # increase/decrease the value to add
        # short press is +/- 5ml and long is +/- 25ml
        if badge.pressed(BUTTON_LEFT):
            menu_value -= 5
        elif badge.held(BUTTON_LEFT):
            menu_value -= 25
        if badge.pressed(BUTTON_RIGHT):
            menu_value += 5
        elif badge.held(BUTTON_RIGHT):
            menu_value += 25

        if badge.pressed(BUTTON_DOWN):
            state["current"] += menu_value
            menu_value = 0
            show_menu = not show_menu
            State.save("hydrate", state)

        if badge.held(BUTTON_UP):
            state["current"] = 0
            State.save("hydrate", state)

        menu_value = clamp(menu_value, 0, state["goal"])

    screen.pen = BLUE3
    screen.clear()

    draw_background()
    draw_graph(CX, CY - 8, 45, state["current"])
    if show_menu:
        screen.blur(0.5)
    draw_menu()


def on_exit():
    pass


init()
run(update)
