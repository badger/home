# Just a little quick method to wrap text into a given space. It will cut off if you run out of lines.
def word_wrap(text, font, w, h):
    screen.font = font
    words = text.split()
    lines = []
    currentline = ""
    _, y_height = screen.measure_text(text)
    total_h = y_height + 0

    for word in words:
        newline = f"{currentline}{word} "
        text_w, text_h = screen.measure_text(newline)
        if text_w <= w:
            currentline = newline
        else:
            lines.append(currentline)
            currentline = f"{word} "
            total_h += 0 + text_h
        if total_h > h:
            break
    lines.append(currentline)

    return lines, y_height


# And an accompanying one to draw the wrapped text.
def draw_wrapped_text(text, font, area):
    lines, y_height = word_wrap(text, font, area.w, area.h)
    y = area.y
    for line in lines:
        screen.text(line, area.x, y)
        y += y_height


class CutsceneLayout:
    img_top = 0
    img_btm = 1
    img_left = 2
    img_right = 3
    img_full = 4


# Depending on the selected layout, this just stores text and the name of
# an image, and draws both in the appropriate hlaves of the screen when asked.
class CutsceneScreen:
    def __init__(self, image, text, layout, font):
        self.image = image
        self.text = text
        self.font = font

        if layout == CutsceneLayout.img_full:
            self.text_box = rect(1, 1, 158, 118)
            self.img_box = rect(0, 0, 160, 120)
        elif layout == CutsceneLayout.img_btm:
            self.text_box = rect(1, 1, 158, 58)
            self.img_box = rect(0, 60, 160, 60)
        elif layout == CutsceneLayout.img_top:
            self.text_box = rect(1, 61, 158, 58)
            self.img_box = rect(0, 0, 160, 60)
        elif layout == CutsceneLayout.img_left:
            self.text_box = rect(81, 1, 78, 118)
            self.img_box = rect(0, 0, 80, 120)
        elif layout == CutsceneLayout.img_right:
            self.text_box = rect(1, 1, 78, 118)
            self.img_box = rect(80, 0, 80, 120)

    def draw(self, screen_image):
        screen.blit(screen_image, self.img_box)
        draw_wrapped_text(self.text, self.font, self.text_box)


# This stores a list of scenes as above, and cycles through them, loading in the right image
# and displaying the scene as it goes. Once you get to the last scene in the list, it returns false.
class Cutscene:
    def __init__(self, screens):
        self.screens = screens
        self.index = 0

    def advance(self):
        self.index += 1
        if self.index >= len(self.screens):
            return False
        return True

    def draw(self):
        screen_image = image.load(f"assets/{self.screens[self.index].image}.png")
        self.screens[self.index].draw(screen_image)
