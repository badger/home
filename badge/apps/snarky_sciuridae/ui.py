
# load user interface sprites
icons = image.load("assets/ui/icons.png").spritesheet(4, 1)
background_day = image.load("assets/background/background_day.png")
background_dusk = image.load("assets/background/background_dusk.png")
background_night = image.load("assets/background/background_night.png")
surround = image.load("assets/ui/tufty_frame_beige.png")
buttons = image.load("assets/ui/buttons_48x14.png").spritesheet(4, 2)
scanlines = image.load("assets/ui/overlay_scanlines.png")

# load in the font - font sheet generated from
screen.font = font.ark

# brushes to match pets stats
stats_brushes = {
    "happy": color.rgb(141, 39, 135),
    "hunger": color.rgb(53, 141, 39),
    "clean": color.rgb(39, 106, 171),
    "warning": color.rgb(255, 0, 0, 200)
}

# icons to match pets stats
stats_icons = {
    "happy": icons.sprite(0, 0),
    "hunger": icons.sprite(1, 0),
    "clean": icons.sprite(2, 0)
}

# ui outline (contrast) colour
outline_brush = color.rgb(228, 220, 220, 150)
outline_brush_bold = color.rgb(228, 220, 220, 200)


# draw the background scenery
def background():
    _, _, _, current_hour, _, _, _ = rtc.datetime()

    if current_hour < 5 or current_hour > 21:
        background_image = background_night
    elif current_hour >= 7 and current_hour <= 19:
        background_image = background_day
    else:
        background_image = background_dusk

    screen.blit(background_image, rect(0, 16, 160, 90))


# draw the title banner
def draw_header():
    screen.blit(surround, vec2(0, 0))

# draw the scanline overlay
def draw_scanlines():
    screen.blit(scanlines, vec2(0, 13))

# draw a user action button with button name and label
def draw_button(x, y, label, active):

    if label == "play":
        u = 0
    elif label == "feed":
        u = 1
    elif label == "clean":
        u = 2
    else:
        u = 3

    if active:
        v = 1
    else:
        v = 0

    screen.blit(buttons.sprite(u, v), vec2(x, y))


# draw a statistics bar with icon and fill level
def draw_bar(name, x, y, amount):
    bar_width = 44

    screen.pen = outline_brush
    screen.shape(shape.rounded_rectangle(x, y, bar_width, 12, 3))

    # draw the bar background
    screen.pen = outline_brush
    screen.shape(shape.rounded_rectangle(x + 14, y + 3, bar_width - 17, 6, 2))

    # calculate how wide the bar "fill" is and clamp it to at least 3 pixels
    fill_width = round(max(((bar_width - 17) / 100) * amount, 3))

    # if bar level is low then alternate fill with red to show a warning
    screen.pen = stats_brushes[name]
    if amount <= 30:
        blink = round(badge.ticks / 250) % 2 == 0
        if blink:
            screen.pen = stats_brushes["warning"]
    screen.shape(shape.rounded_rectangle(x + 14, y + 3, fill_width, 6, 2))

    screen.pen = color.rgb(210, 230, 250, 50)
    screen.shape(shape.rounded_rectangle(x + 15, y + 3, fill_width - 2, 1, 1))

    screen.blit(stats_icons[name], vec2(x, y))


def center_text(text, y, sx=0, ex=160):
    w, _ = screen.measure_text(text)
    screen.text(text, sx + ((ex - sx) / 2) - (w / 2), y)


def shadow_text(text, y, sx=0, ex=160):
    temp = screen.pen
    screen.pen = color.rgb(0, 0, 0, 100)
    center_text(text, y + 1, sx + 1, ex + 1)
    screen.pen = temp
    center_text(text, y, sx, ex)
