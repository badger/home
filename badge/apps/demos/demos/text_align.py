# Demonstrates screen.text() alignment (align) and overflow inside bounds.
# The top box cycles through every horizontal x vertical combination; the bottom
# box feeds in far too much text with overflow=ELLIPSES so it is trimmed to a
# trailing "..." instead of spilling past the edge.

message = "Align the quick brown fox and watch it move."

paragraph = (
    "This paragraph is deliberately far too long to fit inside its little box. "
    "Rather than spilling past the edge, screen.text trims what doesn't fit and "
    "finishes the last visible line with an ellipsis so it stays tidy."
)

ALIGNS = (LEFT, CENTER, RIGHT)
VALIGNS = (TOP, MIDDLE, BOTTOM)
ANAMES = ("left", "center", "right")
VNAMES = ("top", "middle", "bottom")


def framed(b):
    screen.pen = color.rgb(70, 90, 110)
    screen.rectangle(b.x - 1, b.y - 1, b.w + 2, b.h + 2)
    screen.pen = color.rgb(18, 22, 30)
    screen.rectangle(b.x, b.y, b.w, b.h)


def update():
    screen.font = font.sins

    w, h = screen.width, screen.height
    pad = 4

    # advance through the 9 combos about once a second
    step = round(badge.ticks / 900)
    ai = step % 3
    vi = (step // 3) % 3

    align_box = rect(pad, pad + 12, w - pad * 2, h // 2 - pad - 12)
    clip_box = rect(pad, h // 2 + pad + 12, w - pad * 2, h // 2 - pad * 2 - 12)

    screen.pen = color.rgb(150, 170, 190)
    screen.text("align=({}, {})".format(ANAMES[ai], VNAMES[vi]), pad, pad)

    framed(align_box)
    screen.pen = color.rgb(235, 230, 215)
    screen.text(message, align_box, align=(ALIGNS[ai], VALIGNS[vi]))

    screen.pen = color.rgb(150, 170, 190)
    screen.text("overflow=ELLIPSES", pad, h // 2 + pad)

    framed(clip_box)
    screen.pen = color.rgb(235, 210, 160)
    screen.text(paragraph, clip_box, overflow=ELLIPSES)
