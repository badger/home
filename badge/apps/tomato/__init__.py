
# Your apps directory
APP_DIR = "/system/apps/tomato"

import os
import sys

# Standalone bootstrap for finding app assets
os.chdir(APP_DIR)

# Standalone bootstrap for module imports
sys.path.insert(0, APP_DIR)

from badgeware import display
import time

# Centre points for the display
CX = screen.width // 2
CY = screen.height // 2

BLACK = color.rgb(0, 0, 0)
WHITE = color.rgb(255, 255, 255)
SHADOW = color.rgb(0, 0, 0, 100)

screen.antialias = screen.X4

small_font = font.winds
large_font = font.ignore
screen.font = small_font


def shadow_text(text, x, y):
    screen.pen = color.rgb(20, 40, 60, 100)
    screen.text(text, x + 1, y + 1)
    screen.pen = color.rgb(255, 255, 255)
    screen.text(text, x, y)


def center_text(text, y):
    w, _ = screen.measure_text(text)
    shadow_text(text, screen.width / 2 - (w / 2), y)


class Tomato(object):
    def __init__(self):

        self.background = brush.pattern(color.rgb(200, 50, 50, 170), color.rgb(200, 50, 50), 4)
        self.foreground = color.rgb(255, 255, 255, 100)  # Slightly lighter for foreground elements.

        # Time constants.
        # Feel free to change these to ones that work better for you.
        self.TASK = 25 * 60
        self.SHORT = 10 * 60
        self.LONG = 30 * 60

        # How long the completion alert should be played (seconds)
        self.alert_duration = 5
        self.alert_start_time = 0
        self.last_toggle = 0

        self.is_break_time = False
        self.start_time = 0
        self.tasks_complete = 0
        self.running = False
        self.paused = False
        self.time_elapsed = 0
        self.current_timer = self.TASK

        self.btn_pos = ((CX - 30), screen.height - 30)

    def draw(self):

        # Clear the screen
        screen.pen = BLACK
        screen.clear()

        # Draw the background rect with rounded corners
        screen.pen = self.background
        screen.shape(shape.rounded_rectangle(0, 0, screen.width, screen.height, 5))

        # Draw the foreground rect, this is where we will show the time remaining.
        screen.pen = SHADOW
        screen.shape(shape.rounded_rectangle(12, 12, screen.width - 20, 55, 5))
        screen.pen = self.foreground
        screen.shape(shape.rounded_rectangle(10, 10, screen.width - 20, 55, 5))

        # unpack the button position
        x, y = self.btn_pos

        # Draw the button with drop shadow
        screen.pen = SHADOW
        screen.shape(shape.rounded_rectangle(x + 2, y + 2, 60, 20, 4))
        screen.pen = self.foreground
        screen.shape(shape.rounded_rectangle(x, y, 60, 20, 4))

        # Draw the button text, the text shown here depends on the current timer state
        screen.pen = self.foreground
        screen.font = small_font
        if not self.running:
            if self.is_break_time:
                center_text("Start Break", y + 3)
            else:
                center_text("Start Task", y + 3)
        elif self.running and self.paused:
            center_text("Resume", y + 3)
        else:
            center_text("Pause", y + 3)

        text = self.return_string()
        screen.font = large_font
        center_text(text, 22)

    def run(self):

        self.alert_start_time = 0

        if self.is_break_time:
            self.background = brush.pattern(color.rgb(60, 60, 150, 170), color.rgb(60, 60, 150), 4)
            if self.tasks_complete < 4:
                self.current_timer = self.SHORT
            else:
                self.current_timer = self.LONG
        else:
            self.current_timer = self.TASK
            self.background = brush.pattern(color.rgb(200, 50, 50, 170), color.rgb(200, 50, 50), 4)

        if not self.running:
            self.reset()
            self.running = True
            self.start_time = time.time()
        elif self.running and not self.paused:
            self.paused = True
        elif self.running and self.paused:
            self.paused = False
            self.start_time = time.time() - self.time_elapsed

    def reset(self):
        self.start_time = 0
        self.time_elapsed = 0

    def case_lights_off(self):
        badge.caselights(0)

    def toggle_case_lights(self):
        if badge.ticks - self.last_toggle > 250:
            lights = [1.0 - light for light in badge.caselights()]
            badge.caselights(*lights)
            self.last_toggle = badge.ticks

    def update(self):

        if time.time() - self.alert_start_time < self.alert_duration:
            self.toggle_case_lights()
        else:
            self.case_lights_off()

        if self.running and not self.paused:

            # Dim the backlight when the timer is running
            display.backlight(0.5)

            self.time_elapsed = time.time() - self.start_time

            if self.time_elapsed >= self.current_timer:
                self.running = False
                self.alert_start_time = time.time()
                if not self.is_break_time:
                    if self.tasks_complete < 4:
                        self.tasks_complete += 1
                    else:
                        self.tasks_complete = 0
                self.is_break_time = not self.is_break_time
        else:
            # restore the backlight to full brightness
            display.backlight(1.0)

    # Return the remaining time formatted in a string for displaying with vector text.
    def return_string(self):
        minutes, seconds = divmod(self.current_timer - self.time_elapsed, 60)
        return f"{minutes:02d}:{seconds:02d}"


# Create an instance of our timer object
def init():
    global timer
    timer = Tomato()


def on_exit():
    pass


def update():
    global timer

    if badge.pressed(BUTTON_SELECT):
        timer.run()
    timer.draw()
    timer.update()


init()
run(update)
