
# Your apps directory
APP_DIR = "/system/apps/sense"

import os
import sys

# Standalone bootstrap for finding app assets
os.chdir(APP_DIR)

# Standalone bootstrap for module imports
sys.path.insert(0, APP_DIR)

import math

from badgeware import fatal_error
from breakout_bme280 import BreakoutBME280
from breakout_ltr559 import BreakoutLTR559
from lsm6ds3 import LSM6DS3, NORMAL_MODE_104HZ
from machine import I2C

BACKGROUND = brush.pattern(color.rgb(255, 255, 255), color.rgb(188, 211, 224), 26)

font_absolute = font.absolute
font_fear = font.fear
font_winds = font.winds

screen.antialias = image.X2

try:
    motion_sensor = LSM6DS3(I2C(), mode=NORMAL_MODE_104HZ)
    temperature_sensor = BreakoutBME280(I2C())
    light_sensor = BreakoutLTR559(I2C())
except OSError:
    while True:
        fatal_error("Error!", "\nNo Multi Sensor Stick detected.\n\nMake sure the Multi Sensor Stick is connected to the I2C port on the back of your badge and run this app again.")

motion_samples = []
graph = [25 for val in range(22)]
last_graph = badge.ticks

light_samples = []
LIGHT_MIN = 0
LIGHT_MAX = 255

# Window colours
TEMP_COLOUR = (190, 120, 120)
LIGHT_COLOUR = (200, 200, 120)
MOVE_COLOUR = (120, 170, 120)

# viewport for the full screen window
# we'll draw our sensor output to this image and blit it within a "window"
win = image(screen.width - 27, screen.height - 28)


def centre_text(text, w, y, image=win):
    size = image.measure_text(text)[0]
    tx = w - (size / 2) - 2
    image.text(text, tx, y)


def draw_light(_wx, _wy, _ww, _wh):
    global light_samples

    win.pen = color.rgb(*LIGHT_COLOUR)
    win.clear()

    reading = light_sensor.get_reading()
    avg_lux = 100

    # unpack the reading, we only want the lux value.
    if reading is not None:
        _, _, _, _, _, _, lux = reading
        # clamp the readings to our min/max
        lux = max(LIGHT_MIN, min(lux, LIGHT_MAX))

        # add the latest sample to our list
        light_samples.append(lux)
        light_samples = light_samples[-20:]

        # calculate the average
        avg_lux = sum(light_samples) / len(light_samples)

    diameter_modifier = avg_lux / 4
    diameter_base = 1
    diameter = diameter_base + diameter_modifier

    cpos = [(10, 10), (30, 50), (100, 60), (130, 10), (70, 0), (70, 100)]
    win.pen = color.rgb(255, 255, 255, avg_lux)
    for pos in cpos:
        x, y = pos
        win.shape(shape.circle(x, y, diameter + 2))
        win.shape(shape.circle(x, y, diameter).stroke(2))


def draw_temperature(_wx, wy, ww, wh):
    global graph, last_graph

    win.pen = color.rgb(*TEMP_COLOUR)
    win.clear()

    # add values to the dummy graph animation
    if badge.ticks - last_graph > 10:
        graph.append(25 + math.sin(badge.ticks) * 8)
        graph = graph[-22:]
        last_graph = badge.ticks

    # draw the bars for the graph
    for i, t in enumerate(graph):
        win.pen = color.rgb(5 * t, 5 * t, 5 * t, 50)
        win.shape(shape.rounded_rectangle(6 * i, (wy + wh - 10) - t, 5, t, 0))

    # calculate the centre of the window
    cx = ww / 2
    cy = wh / 2

    # get the raw values
    reading = temperature_sensor.read()

    # round the readings to 1 decimal place
    reading = [round(r, 1) for r in reading]

    # unpack the readings into sensible variables
    temp, pressure, humidity = reading

    # format the pressure reading
    pressure /= 100
    pressure = round(pressure)

    win.pen = color.rgb(255, 255, 255, 75)
    win.font = font_absolute

    # draw text for the readings
    temp_text = f"Temp: {temp}C"
    centre_text(temp_text, cx, cy - 35)

    humidity_text = f"RH: {humidity}%"
    centre_text(humidity_text, cx, cy - 20)

    pressure_text = f"{pressure} hPa"
    centre_text(pressure_text, cx, cy - 5)


def draw_motion(_wx, wy, ww, wh):
    global motion_samples

    win.pen = color.rgb(*MOVE_COLOUR)
    win.clear()

    # centre of viewport
    cx = 40
    cy = 45

    # Z axis rectangle position
    rx = ww - 40
    ry = wy

    # clamp radius to window bounds
    radius = (min(ww, wh) / 2) * 0.5

    ax, ay, az, _, _, _ = motion_sensor.get_readings()

    # convert 16bit motion into Gs
    ax /= 16384
    ay /= 16384
    az /= 16384

    # clamp to between -1G and 1G
    magnitude = math.sqrt(ax ** 2 + ay ** 2 + az ** 2)
    if magnitude > 1:
        ax /= magnitude
        ay /= magnitude
        az /= magnitude

    # add to motion sample buffer
    motion_samples.append((ax, ay, az))
    motion_samples = motion_samples[-20:]

    x, y, z = 0, 0, 0

    for sample in motion_samples:
        x += sample[0]
        y += sample[1]
        z += sample[2]

    # calculate new average x and y position
    x /= len(motion_samples)
    y /= len(motion_samples)
    z /= len(motion_samples)

    # draw raw sample buffer values
    win.pen = color.rgb(0, 0, 0, 50)
    for sample in motion_samples:
        sx, sy = sample[0], sample[1]
        win.shape(shape.circle((sx * radius) + cx, (sy * radius) + cy, 2))

    # draw averaged position
    win.pen = color.rgb(255, 255, 255, 200)
    win.shape(shape.circle(cx, cy, radius).stroke(2))
    win.shape(shape.circle((x * radius) + cx, (y * radius) + cy, 4))

    # clamp the value for the y axis
    y = max(ry + 60 * z, ry)

    # draw the elements for the Z axis display
    win.shape(shape.rounded_rectangle(rx, ry, 15, 70, 3).stroke(2))
    win.shape(shape.rounded_rectangle(rx, y, 15, 10, 3))


# UI STUFF
class Widget:

    widgets = []
    selected = 0

    def __init__(self, title=None, draw=None, x=23, y=28, w=40, h=40, window=None):
        self.draw = draw
        self.title = title
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        # position and size for the full screen window
        self.wx = 10
        self.wy = 10
        self.ww = screen.width - 20
        self.wh = screen.height - 20

        self.selected = False
        self.full_view = False
        self.colour_main = [255, 255, 255, 100]
        self.margin = (23, 5)
        self.window = window

        # Attempt to plave the widget.
        # Will check for free space left to right, top to bottom.
        while any(self.check_layout(w) for w in Widget.widgets):
            self.x += 2
            if self.x + self.w > screen.width - self.margin[0]:
                self.x = self.margin[0]
                self.y += 2
                if self.y + self.h > screen.height - self.margin[1]:
                    raise RuntimeError("One or more widgets unable to fit into bounds")

        Widget.widgets.append(self)

    def check_layout(self, w):
        return self.x + self.w >= w.x and self.x <= w.x + w.w and self.y + self.h >= w.y and self.y <= w.y + w.h

    def colour(self, colour):
        self.colour = colour

    @staticmethod
    def is_fullscreen():
        return any(view.full_view for view in Widget.widgets)

    def update_widget(self):

        if self == Widget.widgets[Widget.selected]:
            # We don't want to overwrite 'selected' if it already has ticks
            if not self.selected:
                self.selected = badge.ticks
        else:
            self.selected = False

        # A one pixel jump when the icon is initially selected
        if badge.ticks - self.selected < 50:
            yo = -2
        else:
            yo = 0

        # if full view is not active on any of the widgets, we can draw the icons.
        if not any(view.full_view for view in Widget.widgets):
            # Widget shadow
            screen.pen = color.rgb(0, 0, 0, 70)
            screen.shape(shape.rounded_rectangle(self.x + 1.5, self.y + 1.5, self.w, self.h, 5))

            # Widget main body w/ outline
            screen.pen = color.rgb(*self.colour_main)
            screen.shape(shape.rounded_rectangle(self.x, self.y + yo, self.w, self.h, 5))
            screen.pen = color.rgb(0, 0, 0, 70)
            screen.shape(shape.rounded_rectangle(self.x, self.y + yo, self.w, self.h, 5).stroke(2))
            screen.pen = color.rgb(255, 255, 255, 128)

            line_y = (self.y + 3) + yo
            screen.shape(shape.line(self.x + 2, line_y, self.x + self.w - 2, line_y, 1))
            if self.selected:
                screen.pen = color.rgb(0, 0, 0, 100)
                screen.shape(shape.rounded_rectangle(self.x, self.y + yo, self.w, self.h, 5).stroke(2))

            if self.title:
                screen.font = font_winds
                # Centre X and Y
                tx = (self.x + self.w / 2) - screen.measure_text(self.title)[0] / 2
                ty = (self.y + self.h / 2) - 7
                screen.text(self.title, tx, ty + yo)
            elif self.selected and self.data:
                pass
                # Show some data if the widget is selected and data exists

        # If full view is active on this widget, draw the full screen information
        if self.full_view:

            # window shadow
            screen.pen = color.rgb(0, 0, 0, 100)
            screen.shape(shape.rounded_rectangle(self.wx + 3, self.wy + 3, self.ww, self.wh, 5))

            # main window
            screen.pen = color.rgb(*self.colour_main)
            screen.shape(shape.rounded_rectangle(self.wx, self.wy, self.ww, self.wh, 5))
            screen.pen = color.rgb(0, 0, 0, 100)
            screen.shape(shape.rounded_rectangle(self.wx, self.wy, self.ww, self.wh, 5).stroke(3))
            screen.shape(shape.line(13, 14, 147, 14, 1))

            if self.draw:
                self.draw(self.wx, self.wy, self.ww, self.wh)
            screen.blit(win, vec2(self.wx + 4, self.wy + 5))

            # draw the close button
            screen.shape(shape.rounded_rectangle(71, screen.height - 28, 18, 15, 3, 3, 0, 0))
            screen.font = font_absolute
            screen.pen = color.rgb(255, 255, 255, 120)
            screen.text("X", 76, screen.height - 29)

    @staticmethod
    def update():
        for w in Widget.widgets:
            w.update_widget()


def draw_background():

    screen.pen = color.rgb(0, 0, 0)
    screen.clear()
    screen.pen = BACKGROUND
    screen.shape(shape.rounded_rectangle(0, 0, screen.width, screen.height, 5))

    screen.font = font_fear
    screen.pen = color.rgb(255, 255, 255)
    screen.shape(shape.rounded_rectangle(0, 0, screen.width, 20, 5, 5, 0, 0))
    screen.pen = color.rgb(75, 78, 83)
    screen.text("Sensor Suite", 25, 1)

    screen.pen = color.rgb(188, 211, 224)
    screen.shape(shape.line(0, 19, screen.width, 19, 1))

    # red margin line
    screen.pen = color.rgb(188, 30, 30, 100)
    screen.shape(shape.line(20, 0, 20, screen.height, 2))

    # margin holes
    screen.pen = color.rgb(100, 100, 100)
    screen.shape(shape.circle(9, 39, 3.8))
    screen.shape(shape.circle(9, 99, 3.8))
    screen.pen = color.rgb(150, 150, 150)
    screen.shape(shape.circle(10, 40, 3))
    screen.shape(shape.circle(10, 100, 3))


# Called once to initialise your app.
def init():
    global sensor

    # Widget setup
    temp_widget = Widget(w=114, title="Temperature", draw=draw_temperature)
    light_widget = Widget(w=56, title="Light", draw=draw_light)
    motion_widget = Widget(w=56, title="Move", draw=draw_motion)

    temp_widget.colour_main = TEMP_COLOUR
    light_widget.colour_main = LIGHT_COLOUR
    motion_widget.colour_main = MOVE_COLOUR


# Called every frame, update and render as you see fit!
def update():
    global sensor

    draw_background()

    if Widget.is_fullscreen():
        screen.blur(0.1)

    Widget.update()

    if not Widget.is_fullscreen():
        if badge.pressed(BUTTON_LEFT):
            if Widget.selected > 0:
                Widget.selected -= 1
            else:
                Widget.selected = len(Widget.widgets) - 1

        if badge.pressed(BUTTON_RIGHT):
            if Widget.selected < len(Widget.widgets) - 1:
                Widget.selected += 1
            else:
                Widget.selected = 0

    if badge.pressed(BUTTON_SELECT):
        Widget.widgets[Widget.selected].full_view = not Widget.widgets[Widget.selected].full_view


# Handle saving your app state here
def on_exit():
    pass


init()
run(update)
