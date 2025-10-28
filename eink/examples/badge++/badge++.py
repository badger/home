import badger2040
import badger_os
import jpegdec
import os
import re

# Global Constants
# Measurements are in pixels
WIDTH = badger2040.WIDTH
HEIGHT = badger2040.HEIGHT

# PNG images are not supported on the Universe 2023 badge.
# Enable this flag to allow this app to run on those badges.
BACK_COMPAT_MODE = False

LEFT_PADDING = 7
NAME_HEIGHT = 45
LASTNAME_HEIGHT = 30
DETAILS_HEIGHT = 18
LINE_SPACING = 2
DETAILS_TEXT_SIZE = 2

BADGE_PATH = "/badges/badge.txt"

FONTS = ["bitmap8", "serif", "sans", "gothic"]
THICKNESSES = [1, 4, 4, 2]
SIZE_ADJ = [1, 0.3, 0.3, 0.3]

# Will be replaced with badge.txt
# "Universe 2024", first_name, lastname_name, company, title, pronouns to the file on separate lines.
DEFAULT_TEXT = """Universe 2024
Mona Lisa
Octocat
GitHub
Company Mascot
she/her
@mona
"""

# ------------------------------
#      Utility functions
# ------------------------------


# Reduce the size of a string until it fits within a given width
def truncate_string(text, text_size, width):
    while True:
        length = display.measure_text(text, text_size)
        if length > 0 and length > width:
            text = text[:-1]
        else:
            text += ""
            return text


# Extract the width of the image based on the file name.
# It should be just before the extenstion and follow after an underscore.
def extract_image_width_from_filename(filename):
    match = re.search(r'_(\d+)\.', filename)
    if match:
        return int(match.group(1))
    return 0


# ------------------------------
#      Drawing functions
# ------------------------------

# Draw the badge, including user text
def draw_badge():
    display.set_pen(15)
    display.clear()
    
    # Draw the background
    try:
        target_image = BADGE_IMAGES[state["picture_idx"]]
        image_size = extract_image_width_from_filename(target_image)
        TEXT_WIDTH = WIDTH - LEFT_PADDING - image_size

        # If no image was pulled from the name, it must be the background.
        if(image_size == 0):
            image_size = WIDTH
        
        image_path = f"/badges/{target_image}"
        print(image_path)
        if image_path.endswith(".png"):
            png.open_file(image_path)
            png.decode(WIDTH - image_size, 0)
        else:
            jpeg.open_file(image_path)
            jpeg.decode(WIDTH - image_size, 0)
    except OSError:
        print("Badge background error")

    # Draw the firstname.
    display.set_pen(0)
    display.set_font(FONTS[state["font_idx"]])
    display.set_thickness(THICKNESSES[state["font_idx"]])
    
    size_adjustment = SIZE_ADJ[state["font_idx"]]
    vertical_adjustment = (int(1 / size_adjustment) - 1) * 5

    # Draw the firstname, scaling it based on the available width
    display.set_pen(0)
    name_size = 4 * size_adjustment  # A sensible starting scale
    while True:
        name_length = display.measure_text(first_name, name_size)
        if name_length >= TEXT_WIDTH and name_size >= 0.1:
            name_size -= 0.01
        else:
            display.text(first_name, LEFT_PADDING, 5 + vertical_adjustment, TEXT_WIDTH, name_size)
            break

    # Draw the lastname, scaling it based on the available width
    display.set_pen(0)
    lastname_size = 3 * size_adjustment  # A sensible starting scale
    while True:
        lastname_length = display.measure_text(last_name, lastname_size)
        if lastname_length >= TEXT_WIDTH and lastname_size >= 0.1:
            lastname_size -= 0.01
        else:
            display.text(last_name, LEFT_PADDING, NAME_HEIGHT + LINE_SPACING + vertical_adjustment, TEXT_WIDTH, lastname_size)
            break

    # Draw the title and pronouns, aligned to the bottom & truncated to fit on one line
    display.set_pen(0)
    display.set_thickness(int(THICKNESSES[state["font_idx"]] / 2))
    
    # Title
    display.text(title, LEFT_PADDING, HEIGHT - (DETAILS_HEIGHT * 2) - LINE_SPACING - 2, TEXT_WIDTH, DETAILS_TEXT_SIZE * size_adjustment)

    # Show pronouns if given, otherwise show any handle or blank if neither
    # if pronouns exists and is not empty, show it
    if pronouns and pronouns.strip() != "":
        display.text(pronouns, LEFT_PADDING, HEIGHT - DETAILS_HEIGHT, TEXT_WIDTH, DETAILS_TEXT_SIZE * size_adjustment)
    else:
        display.text(handle, LEFT_PADDING, HEIGHT - DETAILS_HEIGHT, TEXT_WIDTH, DETAILS_TEXT_SIZE * size_adjustment)
    
    display.update()


# ------------------------------
#        Program setup
# ------------------------------

# Global variables
state = {
    "font_idx": 0,
    "picture_idx": 0
}
badger_os.state_load("badge++", state)

# Create a new Badger and set it to update NORMAL
display = badger2040.Badger2040()
display.led(128)
display.set_update_speed(badger2040.UPDATE_NORMAL)

jpeg = jpegdec.JPEG(display.display)

# Only load the PNG library if we're not in compatibility mode.
if(not(BACK_COMPAT_MODE)):
    import pngdec
    png = pngdec.PNG(display.display)
else:
    print("PNG library is not available on the Universe 2023 badge.")

# Open the badge file
try:
    badge = open(BADGE_PATH, "r")
except OSError:
    with open(BADGE_PATH, "w") as f:
        f.write(DEFAULT_TEXT)
        f.flush()
    badge = open(BADGE_PATH, "r")

# Read in the next 6 lines           # Default values
try:
    event = badge.readline()         # "Universe 2024"
    first_name = badge.readline()    # "Mona Lisa"
    last_name = badge.readline()     # "Octocat"
    company = badge.readline()       # "GitHub"
    title = badge.readline()         # "Company Mascot"
    pronouns = badge.readline()      # "she/her"
    handle = badge.readline()        # "@mona"
    
    # If the first name is empty, use the last name as the first name
    if first_name.strip() == "":
        first_name = last_name
        last_name = ""
    
    # Truncate Title and pronouns to fit
    title = truncate_string(title, DETAILS_TEXT_SIZE, 310)
    pronouns = truncate_string(pronouns, DETAILS_TEXT_SIZE, 110)
    handle = truncate_string(handle, DETAILS_TEXT_SIZE, 220)
    
finally:
    badge.close()
    
# Inventory profile images. Ignore PNGs if compatibility mode is enabled.
try:
    BADGE_IMAGES = [
        f for f in os.listdir("/badges")
        if f.endswith(".jpg") or (not(BACK_COMPAT_MODE) and f.endswith(".png"))
    ]
    TOTAL_IMAGES = len(BADGE_IMAGES)
except OSError:
    pass

# Avoid trying to be an invalid state if images are removed.
state["picture_idx"] = max(state["picture_idx"], TOTAL_IMAGES - 1)

# ------------------------------
#       Main program loop
# ------------------------------

changed = False
draw_badge()

while True:
    # Sometimes a button press or hold will keep the system
    # powered *through* HALT, so latch the power back on.
    display.keepalive()

    # Was the image requested to be changed?
    if display.pressed(badger2040.BUTTON_DOWN):
        state["picture_idx"] -= 1
        if (state["picture_idx"] < 0):
            state["picture_idx"] = TOTAL_IMAGES - 1
    
        changed = True

    # Was the image requested to be changed?
    if display.pressed(badger2040.BUTTON_UP):
        state["picture_idx"] += 1
        if (state["picture_idx"] >= TOTAL_IMAGES):
            state["picture_idx"] = 0
    
        changed = True

    # Was the font requested to be changed?
    if display.pressed(badger2040.BUTTON_A):
        state["font_idx"] += 1
        if (state["font_idx"] >= len(FONTS)):
            state["font_idx"] = 0
            
        changed = True

    # Was the font requested to be changed?
    if display.pressed(badger2040.BUTTON_B):
        state["font_idx"] -= 1
        if (state["font_idx"] <= 0):
            state["font_idx"] = len(FONTS) - 1

        changed = True

    if changed:
        draw_badge()
        badger_os.state_save("badge++", state)
        changed = False

    display.halt()
