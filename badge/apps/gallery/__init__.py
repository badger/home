import math
import os
import sys

sys.path.insert(0, "/system/apps/gallery")
os.chdir("/system/apps/gallery")

badge.mode(HIRES | VSYNC)

screen.font = font.nope
screen.antialias = image.X2

ui_hidden = False

files = []

# list the png images, skipping macOS sidecar files and dotfiles like the demos app
image_files = [
    file for file in os.listdir("images")
    if not file.startswith(("__", ".")) and file.endswith(".png")
]
total_files = len(image_files)

if total_files == 0:
    fatal_error("No images found!", "Enter disk mode and copy your PNGs to /apps/gallery/images")

bar_width = screen.width - 20
bar_x = (screen.width // 2) - (bar_width // 2)
segment_width = (bar_width // total_files)


def center_text(text, y):
    w, _ = screen.measure_text(text)
    screen.text(text, (screen.width / 2) - (w / 2), y)


# create a dictionary of all the images in the images directory
for i, file in enumerate(image_files):
    screen.pen = color.black
    screen.clear()
    screen.pen = color.white

    center_text("Loading gallery images", 70)

    screen.shape(shape.rectangle(bar_x, (screen.height // 2) - 15, bar_width, 30).stroke(2))
    screen.shape(shape.rectangle((bar_x - segment_width) + segment_width, (screen.height // 2) - 15, segment_width * i, 30))

    name = file.rsplit(".", 1)[0]
    files.append({
        "name": file,
        "title": name.replace("-", " "),
        "image": image.load(f"images/{name}.png")
    })

    center_text(f"{name}", 155)
    display.update()


# given a gallery image index it clamps it into the range of available images

def clamp_index(index):
    return index % len(files)


# load the main image based on the gallery index provided
def load_image(index):
    global image
    index = clamp_index(index)
    image = files[index]["image"]


# render the thumbnail strip
def draw_thumbnails():
    if ui_hidden:
        return

    w, h = 60, 46
    spacing = w + 10
    # render the thumbnail strip
    for i in range(-3, 4):
        offset = thumbnail_scroll - int(thumbnail_scroll)

        pos = (((i + -offset) * spacing) + (w * 2.2), screen.height - (h + 10))

        # determine which gallery image we're drawing the thumbnail for
        thumbnail = clamp_index(int(thumbnail_scroll) + i)
        thumbnail_image = files[thumbnail]["image"]

        # draw the thumbnail shadow
        screen.pen = color.rgb(0, 0, 0, 50)
        screen.shape(shape.rectangle(
            pos[0] + 2, pos[1] + 2, w, h))

        # draw the active thumbnail outline
        if i == 0:
            brightness = (math.sin(badge.ticks / 200) * 127) + 127
            screen.pen = color.rgb(
                brightness, brightness, brightness, 150)
            screen.shape(shape.rectangle(
                pos[0] - 1, pos[1] - 1, w + 2, h + 2))

        x, y, = pos
        screen.blit(thumbnail_image, rect(0, 0, thumbnail_image.width, thumbnail_image.height), rect(x, y, w, h))


# start up with the first image in the gallery
index = 0
load_image(index)

thumbnail_scroll = index
image_changed_at = None


def update():
    global index, thumbnail_scroll, ui_hidden, image_changed_at

    # if the user presses left or right then switch image
    if badge.pressed(BUTTON_LEFT):
        index -= 1
        ui_hidden = False
        image_changed_at = badge.ticks
        load_image(index)

    if badge.pressed(BUTTON_RIGHT):
        index += 1
        ui_hidden = False
        image_changed_at = badge.ticks
        load_image(index)

    if badge.pressed(BUTTON_SELECT):
        ui_hidden = not ui_hidden
        image_changed_at = badge.ticks

    if image_changed_at and (badge.ticks - image_changed_at) > 2000:
        ui_hidden = True

    # draw the currently selected image
    screen.blit(image, rect(0, 0, image.width, image.height), rect(0, 0, screen.width, screen.height))

    # smooth scroll towards the newly selected image
    if thumbnail_scroll < index:
        thumbnail_scroll = min(thumbnail_scroll + 0.2, index)
    if thumbnail_scroll > index:
        thumbnail_scroll = max(thumbnail_scroll - 0.2, index)

    # draw the thumbnail ui
    draw_thumbnails()

    title = files[clamp_index(index)]["title"]
    width, _ = screen.measure_text(title)

    if not ui_hidden:
        screen.pen = color.rgb(0, 0, 0, 100)
        screen.shape(shape.rounded_rectangle(
            160 - (width / 2) - 8, -6, width + 16, 22, 6))
        screen.text(title, 160 - (width / 2) + 1, 1)
        screen.pen = color.rgb(255, 255, 255)
        screen.text(title, 160 - (width / 2), 0)


run(update)
