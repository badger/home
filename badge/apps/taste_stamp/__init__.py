# Taste Stamp: a Creative Director's rubber stamp.

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2
screen.fill_rule = image.EVEN_ODD
W = screen.width
H = screen.height

UI_FONT = font.nope
SMALL_FONT = font.sins
screen.font = UI_FONT


def rgb(c, alpha=255):
    return color.rgb(c[0], c[1], c[2], alpha)


DESK = (13, 17, 23)
PAPER = (241, 236, 224)
STRIP = (232, 226, 212)
LINE_GREY = (212, 205, 190)
HEADING_GREY = (186, 178, 162)
PAPER_TEXT = (150, 142, 128)
WHITE = (240, 246, 252)

DESK_C = rgb(DESK)
PAPER_C = rgb(PAPER)
STRIP_C = rgb(STRIP)
LINE_C = rgb(LINE_GREY)
HEADING_C = rgb(HEADING_GREY)
PAPER_TEXT_C = rgb(PAPER_TEXT)
SHADOW_C = color.rgb(0, 0, 0, 110)
WHITE_C = rgb(WHITE)

# Layout.
TITLE_Y = 4
PAPER_X = 14
PAPER_Y = 26
PAPER_W = W - 2 * PAPER_X
PAPER_H = 190
STRIP_H = 20
TEXT_X = PAPER_X + 16
TEXT_W = PAPER_W - 32

# The brief under the stamps: bar widths as fractions of the text column.
# Negative values are headings and 0 is a paragraph gap.
BRIEF = (-0.42, 0.94, 0.88, 0.97, 0.52, 0, -0.3, 0.9, 0.96, 0.84, 0.6, 0, 0.91, 0.7)


class App:
    def __init__(self):
        self.desk = image(W, H)
        self.desk.antialias = image.X2
        # The brief's header is vector text, which needs EVEN_ODD.
        self.desk.fill_rule = image.EVEN_ODD
        self.render_desk()

    # Frame loop.

    def update(self):
        now = badge.ticks
        if not self.handle_buttons(now):
            return False
        self.draw_stamp_mode(now)
        return None

    def handle_buttons(self, now):
        # Returns False when the app should exit.
        if badge.pressed(BUTTON_BACK):
            return False
        return True

    # The desk.

    def render_desk(self):
        d = self.desk
        d.pen = DESK_C
        d.clear()
        d.pen = SHADOW_C
        d.shape(shape.rounded_rectangle(PAPER_X + 3, PAPER_Y + 4, PAPER_W, PAPER_H, 4))
        d.pen = PAPER_C
        d.shape(shape.rounded_rectangle(PAPER_X, PAPER_Y, PAPER_W, PAPER_H, 4))
        d.pen = STRIP_C
        d.shape(shape.rounded_rectangle(PAPER_X, PAPER_Y, PAPER_W, STRIP_H, 4))
        d.rectangle(PAPER_X, PAPER_Y + STRIP_H - 6, PAPER_W, 6)
        d.pen = LINE_C
        d.rectangle(PAPER_X, PAPER_Y + STRIP_H, PAPER_W, 1)
        d.font = SMALL_FONT
        d.pen = PAPER_TEXT_C
        d.text("creative-brief.md", PAPER_X + 8, PAPER_Y + 4)
        y = PAPER_Y + 30
        for v in BRIEF:
            if v < 0:
                d.pen = HEADING_C
                d.shape(shape.rounded_rectangle(TEXT_X, y - 1, -v * TEXT_W, 6, 2))
            elif v > 0:
                d.pen = LINE_C
                d.shape(shape.rounded_rectangle(TEXT_X, y, v * TEXT_W, 4, 2))
            y += 11

    # Drawing.

    def draw_stamp_mode(self, now):
        screen.blit(self.desk, vec2(0, 0))
        self.draw_title("TASTE STAMP")

    def draw_title(self, title):
        screen.font = UI_FONT
        screen.pen = WHITE_C
        screen.text(title, 10, TITLE_Y)


app = App()


def update():
    return app.update()


run(update)
