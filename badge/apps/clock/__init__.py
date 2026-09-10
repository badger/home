# Your app's directory
APP_DIR = "/system/apps/clock"

import sys
import os
import wifi
import secrets

# Standalone bootstrap for finding app assets
os.chdir(APP_DIR)

# Standalone bootstrap for module imports
sys.path.insert(0, APP_DIR)


from badgeware import State
import time
import ntptime
from daylightsaving import DaylightSavingPolicy, DaylightSaving
from usermessage import user_message, center_text, stretch_text
from machine import RTC
import math


# Making classes for which clock is displayed etc, so we can refer to them by name.
class DisplayType:
    textclock = 1
    dotsclock = 2
    nixie = 3
    sevenseg = 4


class ClockState:
    Running = 0
    ConnectWiFi = 1
    UpdateTime = 2
    FirstRun = 3


secrets.require("REGION", "TIMEZONE")

REGION = secrets.REGION
TIMEZONE = secrets.TIMEZONE

# Setting up default values for the first run, and loading in the state with the
# user choices if the file's there.
state = {
    "dark_mode": True,
    "clock_style": 3,
    "colour_scheme": 5,
    "first_run": True
}

State.load("clock", state)

if state["first_run"]:
    clock_state = ClockState.FirstRun
    icons = image.load("assets/icons.png").spritesheet(5, 1)
else:
    clock_state = ClockState.Running

# Loading all the assets.
textclock_font = font.smart
dots_font = font.hungry
nixie_font = font.sins

palette = {
    1: (color.rgb(44, 44, 44), color.rgb(44, 44, 44, 100), color.rgb(255, 255, 255), color.rgb(255, 255, 255, 100)),
    2: (color.rgb(44, 4, 0), color.rgb(87, 8, 0, 100), color.rgb(255, 50, 31), color.rgb(255, 50, 31, 100)),
    3: (color.rgb(38, 23, 0), color.rgb(77, 47, 0, 100), color.rgb(255, 111, 0), color.rgb(255, 111, 0, 100)),
    4: (color.rgb(38, 23, 0), color.rgb(77, 47, 0, 100), color.rgb(255, 174, 46), color.rgb(255, 174, 46, 100)),
    5: (color.rgb(0, 35, 10), color.rgb(0, 71, 21, 100), color.rgb(11, 255, 81), color.rgb(11, 255, 81, 100)),
    6: (color.rgb(0, 14, 33), color.rgb(0, 28, 66, 100), color.rgb(82, 154, 255), color.rgb(82, 154, 255, 100)),
    7: (color.rgb(46, 0, 24), color.rgb(92, 0, 48, 100), color.rgb(255, 117, 189), color.rgb(255, 117, 189, 100)),
    8: (color.rgb(15, 0, 33), color.rgb(31, 0, 66, 100), color.rgb(190, 133, 255), color.rgb(190, 133, 255, 100))
}

if state["dark_mode"]:
    faded_brush = palette[state["colour_scheme"]][3]
    bg_brush = palette[state["colour_scheme"]][0]
    drawing_brush = palette[state["colour_scheme"]][2]
else:
    faded_brush = palette[state["colour_scheme"]][1]
    bg_brush = palette[state["colour_scheme"]][2]
    drawing_brush = palette[state["colour_scheme"]][0]

if state["clock_style"] == DisplayType.nixie:
    numerals = image.load("assets/nixie_num.png").spritesheet(10, 1)
    background = image.load("assets/nixie_bg.png")
    foreground = image.load("assets/nixie_fg.png")
    clock_dots = None
elif state["clock_style"] == DisplayType.sevenseg:
    if state["dark_mode"]:
        numerals = image.load("assets/digital_num.png").spritesheet(10, 1)
        clock_dots = image.load("assets/digital_dots.png").spritesheet(2, 1)
    else:
        numerals = image.load("assets/digital_num_invert.png").spritesheet(10, 1)
        clock_dots = image.load("assets/digital_dots_invert.png").spritesheet(2, 1)
    background = None
    foreground = None

month_days = {
    1: 31,
    2: 28,
    3: 31,
    4: 30,
    5: 31,
    6: 30,
    7: 31,
    8: 31,
    9: 30,
    10: 31,
    11: 30,
    12: 31
}

calendar_months = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December"
}

# These are the different Daylight Saving time zones, according to the Wikipedia article.
# Timezones are incredibly complex, we've covered the main ones here.
# "zonename": (hemisphere, week, month, weekday, hour, timezone, minutes clocks change by)
# Israel and Palestine each follow different daylight saving rules from standard, and are not included here.
regions = {
    "us": (0, 2, 3, 6, 2, 1, 11, 6, 2, 60),
    "cuba": (0, 2, 3, 6, 0, 1, 11, 6, 1, 60),
    "eu": (0, 0, 3, 6, 1, 0, 10, 6, 1, 60),
    "moldova": (0, 0, 3, 6, 2, 0, 10, 6, 3, 60),
    "lebanon": (0, 0, 3, 6, 0, 0, 10, 6, 0, 60),
    "egypt": (0, 0, 4, 4, 0, 0, 10, 3, 24, 60),
    "chile": (1, 1, 9, 5, 24, 1, 4, 5, 24, 60),
    "australia": (1, 1, 10, 6, 2, 1, 4, 6, 3, 60),
    "nz": (1, 0, 9, 6, 2, 1, 4, 6, 3, 60)
}


def update_time(region, timezone):
    # Set the time with ntptime and pass it to the daylight saving calculator.
    # Pass the result to the unit's RTC.

    # handle time out during ntp comms
    try:
        ntptime.settime()
        time.sleep(2)
    except OSError:
        return False

    timezone_minutes = timezone * 60

    hemisphere, week_in, month_in, weekday_in, hour_in, week_out, month_out, weekday_out, hour_out, mins_difference = regions[region]

    dstp = DaylightSavingPolicy(hemisphere, week_in, month_in, weekday_in, hour_in, timezone_minutes + mins_difference)
    stdp = DaylightSavingPolicy(hemisphere, week_out, month_out, weekday_out, hour_out, timezone_minutes)

    dst = DaylightSaving(dstp, stdp)
    t = time.mktime(time.gmtime())
    tm = time.gmtime(dst.localtime(t))
    RTC().datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], 0))
    year, month, day, dow, hour, minute, second, dow = RTC().datetime()
    rtc.datetime((year, month, day, hour, minute, second, dow))

    return True


def display_time():
    # Chooses which clock face to show based on the clock_style global.
    global clock_dots, numerals, background, foreground

    currenttime = rtc.datetime()

    if state["clock_style"] == DisplayType.textclock:
        draw_text_clock(currenttime)

    elif state["clock_style"] == DisplayType.dotsclock:
        draw_dots_clock(currenttime)

    # For the nixie and seven segment displays, we're reusing the same variables
    # for numerals, dots etc and just loading different files into them to save memory.
    elif state["clock_style"] == DisplayType.nixie:
        numerals = image.load("assets/nixie_num.png").spritesheet(10, 1)
        background = image.load("assets/nixie_bg.png")
        foreground = image.load("assets/nixie_fg.png")
        clock_dots = None
        screen.font = nixie_font
        draw_nixie_clock(currenttime)

    elif state["clock_style"] == DisplayType.sevenseg:
        if state["dark_mode"]:
            numerals = image.load("assets/digital_num.png").spritesheet(10, 1)
            clock_dots = image.load("assets/digital_dots.png").spritesheet(2, 1)
        else:
            numerals = image.load("assets/digital_num_invert.png").spritesheet(10, 1)
            clock_dots = image.load("assets/digital_dots_invert.png").spritesheet(2, 1)
        background = None
        foreground = None
        draw_sevenseg_clock(currenttime)


def draw_sevenseg_clock(currenttime):
    # For Tufty's seven segment clock, the numerals are PNGs with transparent holes or backgrounds.
    # This lets us change out the colour that's behind them to colour the digits or their background.

    screen.antialias = image.X4

    # This is how far out from the centre each set of digits gets moved to make room for the dots.
    digit_offset = 4

    # Start with a blank slate.
    if state["dark_mode"]:
        screen.pen = color.rgb(0, 0, 0)
    else:
        screen.pen = bg_brush

    screen.clear()

    digit_h = numerals.sprite(0, 0).height
    digit_y = math.floor((screen.height - digit_h) / 2)

    screen.pen = drawing_brush

    # The whole next section draws bars of increasing thickness diagonally
    # across the screen, as well as drawing the bar to display seconds.
    bar_width = 80

    y = 0
    leftx = (screen.width - screen.height - bar_width) / 2
    rightx = leftx + bar_width
    offset = 0

    seconds_spacing = 6  # Distance between the seconds bar and the stripes.
    seconds = currenttime[5]
    second_width = math.floor(seconds / 60 * (screen.width - rightx - seconds_spacing)) + 1

    # Draws the top right seconds bar, width calculated as a proportion of
    # the distance between the stripes and the screen's edge.
    seconds_x_start = rightx + seconds_spacing
    seconds_y_start = 2
    seconds_xy_offset = digit_y - 4
    screen.shape(shape.custom([
        vec2(seconds_x_start, seconds_y_start),
        vec2(seconds_x_start + second_width, seconds_y_start),
        vec2(seconds_x_start + second_width + seconds_xy_offset - seconds_y_start, seconds_xy_offset),
        vec2(seconds_x_start + seconds_xy_offset - seconds_y_start, seconds_xy_offset)
    ]))

    # Draws the stripes increasing in thiccness until it gets to half way down the screen.
    while y <= screen.height / 2:
        seg_path = [vec2(leftx, y),
                    vec2(rightx, y),
                    vec2(rightx + offset, y + offset),
                    vec2(leftx + offset, y + offset)]
        seg = shape.custom(seg_path)
        screen.shape(seg)
        offset += 1
        y += 2 * offset
        leftx += 2 * offset
        rightx += 2 * offset

    y = screen.height
    rightx = screen.width - ((screen.width - screen.height - bar_width) / 2)
    leftx = rightx - bar_width

    # Then the lower left bar for the seconds...
    seconds_x_start = leftx - seconds_spacing
    screen.shape(shape.custom([
        vec2(seconds_x_start, screen.height - seconds_y_start),
        vec2(seconds_x_start - second_width, screen.height - seconds_y_start),
        vec2(seconds_x_start - second_width - seconds_xy_offset + seconds_y_start, screen.height - seconds_xy_offset),
        vec2(seconds_x_start - seconds_xy_offset + seconds_y_start, screen.height - seconds_xy_offset)
    ]))

    # Just like above, draws stripes increasing in thiccness from the bottom of the screen.
    offset = 0
    while y >= 60:
        seg_path = [vec2(leftx, y),
                    vec2(rightx, y),
                    vec2(rightx - offset, y - offset),
                    vec2(leftx - offset, y - offset)]
        seg = shape.custom(seg_path)
        screen.shape(seg)
        offset += 1
        y -= 2 * offset
        leftx -= 2 * offset
        rightx -= 2 * offset

    # This draws a bright rectangle behind the digit cutouts to light them up.
    if state["dark_mode"]:
        screen.pen = drawing_brush
    else:
        screen.pen = bg_brush
    screen.shape(shape.rectangle(0, digit_y, screen.width, digit_h))

    # Quickly draw the dots in between the numerals, flashing every second
    if currenttime[5] % 2:
        screen.blit(clock_dots.sprite(0, 0), vec2(76, digit_y))
    else:
        screen.blit(clock_dots.sprite(1, 0), vec2(76, digit_y))

    # Then finally draw the digit sprites.
    hour = currenttime[3]
    minute = currenttime[4]

    draw_digits(hour, minute, numerals, digit_offset, digit_y)


def draw_nixie_clock(currenttime):
    # Nixie is simpler than 7 segment as there's no vector drawing to figure out,
    # all the hard work is done by the images.

    # It doesn't do dark mode, so here we're setting a new drawing brush
    # based on whichever regular brush is the bright one.
    this_drawing_brush = bg_brush
    if state["dark_mode"]:
        this_drawing_brush = drawing_brush

    # First draw the background
    screen.blit(background, vec2(0, 0))

    # Then make up a string for the date and draw it.
    year = currenttime[0]
    month = calendar_months[currenttime[1]]
    mday = currenttime[2]

    suffix = "th" if 4 <= mday % 100 <= 20 else {1:"st",2:"nd",3:"rd"}.get(mday % 10, "th")

    date = str(mday) + suffix + " " + month + " " + str(year)

    screen.pen = this_drawing_brush
    center_text(date, 3)

    # Draw the digits just like in the 7 segment clock...
    hour = currenttime[3]
    minute = currenttime[4]

    draw_digits(hour, minute, numerals, 0, 20)

    # Draw a rectangle in the selected palette colour - its width
    # is proportional to the seconds value.
    seconds = currenttime[5]
    second_width = seconds / 60 * screen.width

    screen.shape(shape.rectangle(0, 102, second_width, 7))

    # Finally just draw the glass tube image over this bar.
    screen.blit(foreground, vec2(0, 102))


def draw_digits(hour, minute, spritesheet, center_offset, y_pos):
    # This is used for both the nixie and digital clocks. Both use PNGs with alpha transparency,
    # in the seven segment case so that the selected colour shows through the clear digits and
    # in the nixie case so the glass and stuff doesn't look weird.

    # Simply divide the hours and minutes into individual digits...
    hourtens = math.floor(hour / 10)
    hourunits = hour % 10
    minutetens = math.floor(minute / 10)
    minuteunits = minute % 10

    # ...and then use that to pick a sprite from the spritesheet of numerals.
    screen.blit(spritesheet.sprite(hourtens, 0), vec2(0 - center_offset, y_pos))
    screen.blit(spritesheet.sprite(hourunits, 0), vec2(40 - center_offset, y_pos))
    screen.blit(spritesheet.sprite(minutetens, 0), vec2(80 + center_offset, y_pos))
    screen.blit(spritesheet.sprite(minuteunits, 0), vec2(120 + center_offset, y_pos))


def draw_dot_row(y, width, total_dots, filled_dots, space_size, space_every):
    # This method draws a row of circles across a given width, sizing them so they fill the
    # width with a specified gap, and optional double space every X dots.

    # First work out how many spaces.
    num_spaces = total_dots - 1
    if space_every > 0:
        num_spaces += total_dots / space_every
    total_space_width = num_spaces * space_size

    # That gives us how much space we have to work with for the dots.
    # We work out their radius, then get an actual width based on that radius.
    total_dot_width = width - total_space_width
    dot_radius = (total_dot_width / total_dots) / 2
    actual_dots_width = dot_radius * 2 * total_dots

    # Then we can figure out where to draw the first dot.
    total_width = actual_dots_width + total_space_width
    dot_x = dot_radius

    w = int(total_width)
    h = int(dot_radius * 2)

    dot_row = image(w, h)
    dot_row.antialias = image.X4
    dot_row.pen = drawing_brush

    # Now we just iterate through, drawing a dot and increasing the x co-ordinate each time.
    for i in range(total_dots):
        if filled_dots > i:
            dot_row.pen = drawing_brush
        else:
            dot_row.pen = faded_brush
        dot_row.shape(shape.circle(dot_x, dot_radius, dot_radius))
        dot_x += (2 * dot_radius) + space_size
        if space_every > 0:
            if (i + 1) % space_every == 0:
                dot_x += space_size

    x_pos = ((screen.width - total_width) / 2)
    screen.blit(dot_row, rect(x_pos, y, total_width, dot_radius * 2))

    # We return the height of the row so we can add it to y for the next row.
    return dot_radius * 2


def draw_dots_clock(currenttime):
    # Drawing the dots clock just involves writing the text captions and
    # creating the rows of dots using the above method.

    screen.antialias = image.X4
    screen.font = dots_font

    screen.pen = bg_brush
    screen.clear()

    row_spacing = 1
    border = 2.5

    month = currenttime[1]
    mday = currenttime[2]
    hours = currenttime[3]
    minutes = currenttime[4]

    # The draw_dot_row and stretch_text functions both return the height of what they've
    # just rendered, so we just add that plus a small gap to the y coordinate each time
    # to move down the screen as we draw.
    y = 0

    y += stretch_text("MONTH", border, y, screen.width - (2 * border), drawing_brush) - 1
    y += draw_dot_row(y, screen.width - (2 * border), 12, month, 1, 0) + (2 * row_spacing)

    y += stretch_text("DAY", border, y, screen.width - (2 * border), drawing_brush) - 1
    y += draw_dot_row(y, screen.width - (2 * border), month_days[month], mday, 1, 0) + (2 * row_spacing)

    y += stretch_text("HOUR", border, y, screen.width - (2 * border), drawing_brush) - 1
    y += draw_dot_row(y, screen.width - (2 * border), 24, hours, 1, 4) + (2 * row_spacing)

    # Minutes and seconds get two rows each, so there's a little maths to do to split the total
    # between the two rows.
    y += stretch_text("MINUTE", border, y, screen.width - (2 * border), drawing_brush) - 1
    y += draw_dot_row(y, screen.width - (2 * border), 30, minutes, 1, 5) + (2 * row_spacing)
    if currenttime[4] > 30:
        minutes -= 30
    else:
        minutes = 0
    y += draw_dot_row(y, screen.width - (2 * border), 30, minutes, 1, 5) + (2 * row_spacing)

    y += stretch_text("SECOND", border, y, screen.width - (2 * border), drawing_brush) - 1
    seconds = currenttime[5]
    y += draw_dot_row(y, screen.width - (2 * border), 30, seconds, 1, 5) + (2 * row_spacing)
    if currenttime[5] > 30:
        seconds -= 30
    else:
        seconds = 0
    y += draw_dot_row(y, screen.width - (2 * border), 30, seconds, 1, 5) + (2 * row_spacing)


def draw_text_clock(currenttime):
    # The text clock involves solely drawing text.

    screen.pen = bg_brush
    screen.clear()

    screen.font = textclock_font

    # First of all we're making a list of lists containing all of the words that are
    # going on the screen.
    words = [["it", "is", "about", "half", "twenty"],
             ["quarter", "ten_", "five_", "past", "to"],
             ["one", "two", "three", "four", "five"],
             ["six", "seven", "eight", "nine", "ten"],
             ["eleven", "twelve", "o'clock", "on"],
             ["sunday", "monday", "tuesday"],
             ["wednesday", "thursday"],
             ["friday", "saturday", "morning"],
             ["afternoon", "evening", "night"]]

    # displayed_time contains all the words we want lit up. These ones are always lit.
    displayed_time = ["it", "is", "about", "on"]

    # We need to work out which number on a clock face we're
    # currently closest to.
    hours = currenttime[3]
    minutes_in_seconds = (currenttime[4] * 60) + currenttime[5]
    hour_portion = (minutes_in_seconds + 150) / 300
    minutes = math.floor(hour_portion)

    # Depending on that, we just do a bunch of checks to decide which words
    # to put into which variables.
    # The '_' on the "five_" and "ten_" are there to differentiate the minutes
    # from the hour number. The underscore is stripped before being displayed.
    # If something needs to be lit we just add it to displayed_time.
    if minutes == 0 or minutes == 12:
        displayed_time.append("o'clock")
    if minutes == 1 or minutes == 11 or minutes == 5 or minutes == 7:
        displayed_time.append("five_")
    if minutes == 2 or minutes == 10:
        displayed_time.append("ten_")
    if minutes == 3 or minutes == 9:
        displayed_time.append("quarter")
    if minutes == 4 or minutes == 8 or minutes == 5 or minutes == 7:
        displayed_time.append("twenty")
    if minutes == 6:
        displayed_time.append("half")

    if minutes <= 6 and minutes > 0:
        displayed_time.append("past")
    elif minutes == 12:
        hours += 1
    elif minutes > 6 and minutes < 12:
        displayed_time.append("to")
        hours += 1
    if hours > 23:
        hours -= 24

    if hours == 0 or hours == 12:
        displayed_time.append("twelve")
    if hours == 1 or hours == 13:
        displayed_time.append("one")
    if hours == 2 or hours == 14:
        displayed_time.append("two")
    if hours == 3 or hours == 15:
        displayed_time.append("three")
    if hours == 4 or hours == 16:
        displayed_time.append("four")
    if hours == 5 or hours == 17:
        displayed_time.append("five")
    if hours == 6 or hours == 18:
        displayed_time.append("six")
    if hours == 7 or hours == 19:
        displayed_time.append("seven")
    if hours == 8 or hours == 20:
        displayed_time.append("eight")
    if hours == 9 or hours == 21:
        displayed_time.append("nine")
    if hours == 10 or hours == 22:
        displayed_time.append("ten")
    if hours == 11 or hours == 23:
        displayed_time.append("eleven")

    weekdaytime = (currenttime[0], currenttime[1], currenttime[2], currenttime[3], currenttime[4], currenttime[5], currenttime[6], 0)
    weekday = int((time.mktime(weekdaytime) // 86400) - 10957) % 7

    if weekday == 0:
        displayed_time.append("saturday")
    if weekday == 1:
        displayed_time.append("sunday")
    if weekday == 2:
        displayed_time.append("monday")
    if weekday == 3:
        displayed_time.append("tuesday")
    if weekday == 4:
        displayed_time.append("wednesday")
    if weekday == 5:
        displayed_time.append("thursday")
    if weekday == 6:
        displayed_time.append("friday")

    if hours > 4 and hours < 12:
        displayed_time.append("morning")
    elif hours >= 12 and hours < 18:
        displayed_time.append("afternoon")
    elif hours >= 18 and hours < 22:
        displayed_time.append("evening")
    else:
        displayed_time.append("night")

    # Finally we draw it all.
    border = 2
    y = border

    # Measuring some random text to get a line height.
    line_height = screen.measure_text("Anything here")
    y_spacing = (screen.height - (2 * border) - (line_height[1] * len(words))) / (len(words) - 1)

    # Then for each line we go through each word and see if it's in displayed_time. If it is we
    # draw it with the bright brush, if not we draw it with the faded brush.
    # After each word we move the x drawing position along by the word's width, plus a spacing
    # calculated by measuring all the words together, subtracting that from the screen width
    # and dividing the result by the number of words so that they're evenly spaced.
    # We NEED to remoive any "_" of the string before calculating and displaying.
    for line in words:
        spaces = len(line) - 1
        textwidth = screen.measure_text("".join(line).replace("_", ""))
        x_spacing = (screen.width - (2 * border) - textwidth[0]) / spaces

        x = border
        for word in line:
            if word in displayed_time:
                screen.pen = drawing_brush
            else:
                screen.pen = faded_brush
            displayed_word = word.replace("_", "")
            screen.text(displayed_word, x, y)
            x += screen.measure_text(displayed_word)[0]
            x += round(x_spacing)

        y += line_height[1] + y_spacing


def intro_screen():
    # The intro screen only shows on the first run of Clock.
    # It just shows some icons to demonstrate what each button does.

    screen.pen = brush.pattern(color.rgb(0, 0, 0), color.rgb(20, 20, 20), 20)
    screen.clear()

    screen.pen = color.rgb(255, 255, 255)
    screen.font = textclock_font
    center_text("Welcome to Clock!", 3)

    screen.blit(icons.sprite(0, 0), vec2(23, 104))
    screen.blit(icons.sprite(1, 0), vec2(73, 104))
    screen.blit(icons.sprite(2, 0), vec2(123, 104))
    screen.blit(icons.sprite(3, 0), vec2(144, 27))
    screen.blit(icons.sprite(4, 0), vec2(144, 77))

    screen.font = nixie_font
    center_text("Press any button", 40)
    center_text("to continue,", 50)
    center_text("this screen will", 60)
    center_text("not be shown again.", 70)


def switch_palette():
    # This switches between light and dark mode by making the background,
    # faded and drawing brush the appropriate light or dark values from
    # the selected colour palette.

    global bg_brush, drawing_brush, faded_brush

    if state["dark_mode"]:
        faded_brush = palette[state["colour_scheme"]][3]
        bg_brush = palette[state["colour_scheme"]][0]
        drawing_brush = palette[state["colour_scheme"]][2]
    else:
        faded_brush = palette[state["colour_scheme"]][1]
        bg_brush = palette[state["colour_scheme"]][2]
        drawing_brush = palette[state["colour_scheme"]][0]


def write_settings():
    # Simply saves the user-selected options as a state.
    State.save("clock", state)


def init():
    pass


def update():
    # Main update loop.

    global state, clock_state

    # First we check if it's the first time of running, and if so show the intro screen.
    # Any face button press will move it into the regular running mode.
    if clock_state == ClockState.FirstRun:
        intro_screen()
        if any(x in badge.pressed() for x in [BUTTON_LEFT, BUTTON_SELECT, BUTTON_RIGHT, BUTTON_UP, BUTTON_DOWN]):
            clock_state = ClockState.Running
            state["first_run"] = False
            write_settings()

    # Next we check if anything's been pressed before choosing what to display.
    if badge.pressed(BUTTON_UP):
        state["dark_mode"] = not state["dark_mode"]
        write_settings()
        switch_palette()

    if badge.pressed(BUTTON_DOWN):
        state["colour_scheme"] += 1
        if state["colour_scheme"] > 8:
            state["colour_scheme"] = 1
        write_settings()
        switch_palette()

    if badge.pressed(BUTTON_RIGHT):
        state["clock_style"] += 1
        if state["clock_style"] > 4:
            state["clock_style"] = 1
        write_settings()

    if badge.pressed(BUTTON_LEFT):
        state["clock_style"] -= 1
        if state["clock_style"] < 1:
            state["clock_style"] = 4
        write_settings()

    # If the year in the RTC is 2021 or earlier, we need to sync so it has the same effect as pressing SELECT.
    if badge.pressed(BUTTON_SELECT) or time.gmtime()[0] <= 2021 and clock_state == ClockState.Running:
        user_message("Updating...", ["Updating time", "from NTP server...", "Getting WiFi details..."])
        clock_state = ClockState.ConnectWiFi

    # So here we just decide what to do based on the clock_state global.
    # Running is normal operation, but if SELECT was detected as pressed above,
    # then we go through states to get the WiFi details, connect and finally
    # pull the time from the NTP server.

    # We use states here because the screen doesn't update until the end of Update(),
    # so anything we put on the display will be overwritten by anything we put further down.
    # By using states each step of the process happens on a different loop through Update(),
    # so we can display a message for each step.
    if clock_state == ClockState.Running:
        display_time()

    elif clock_state == ClockState.UpdateTime:
        if update_time(REGION, TIMEZONE):
            clock_state = ClockState.Running
        else:
            user_message("Error!", ["Unable to get time", "from NTP server."])

    elif clock_state == ClockState.ConnectWiFi:
        user_message("Please Wait", ["Connecting to WiFi..."])
        if wifi.connect():
            clock_state = ClockState.UpdateTime

def on_exit():
    pass


init()
run(update)
