import math

screen.antialias = image.X4

canvas_area = (10, 15, screen.width - 20, screen.height - 35)

ui_font = font.vest


def draw_background():
    # fill the background in that classic red...
    screen.pen = color.rgb(170, 45, 40)
    screen.rectangle(0, 0, screen.width, screen.height)

    # draw the embossed gold logo
    screen.font = ui_font
    w, _ = screen.measure_text("Sketchy Sketch")
    screen.pen = color.rgb(240, 210, 160)
    screen.text("Sketchy Sketch", (screen.width / 2) - (w / 2) - 1, -1)
    screen.pen = color.rgb(190, 140, 80, 100)
    screen.text("Sketchy Sketch", (screen.width / 2) - (w / 2), 0)

    # draw the canvas area grey background and screen shadows
    screen.pen = color.rgb(210, 210, 210)
    screen.shape(shape.rounded_rectangle(*canvas_area, 6))
    screen.pen = color.rgb(180, 180, 180)
    screen.shape(
        shape.rounded_rectangle(
            canvas_area[0] + 3, canvas_area[1], canvas_area[2] - 5, 3, 2
        )
    )
    screen.shape(
        shape.rounded_rectangle(
            canvas_area[0], canvas_area[1] + 3, 3, canvas_area[3] - 5, 2
        )
    )

    # draw highlights on the plastic "curve"
    screen.pen = color.rgb(255, 255, 255, 100)
    screen.rectangle(
        canvas_area[0] - 3, canvas_area[1] + 5, 1, canvas_area[3] - 10
    )
    screen.rectangle(
        canvas_area[0] + canvas_area[2] + 2,
        canvas_area[1] + 5,
        1,
        canvas_area[3] - 10
    )


left_dial_angle = 0
right_dial_angle = 0


def draw_dial(angle, pos):
    radius = 16

    # calculate an offset to fake perspective on the dials
    offset = ((screen.width / 2) - pos[0]) / 35

    # draw the dial shadow
    screen.pen = color.rgb(0, 0, 0, 40)
    screen.shape(shape.circle(pos[0] + offset * 1.5, pos[1], radius + 2))

    # draw the dial shaft
    screen.pen = color.rgb(150, 160, 170)
    screen.shape(shape.circle(pos[0] + offset, pos[1], radius))

    # draw the dial surface
    screen.pen = color.rgb(220, 220, 230)
    screen.shape(shape.circle(*pos, radius))

    # draw the animated ticks around the dial edge
    screen.pen = color.rgb(190, 190, 220)
    ticks = 20
    for i in range(ticks):
        deg = angle + (i * 360 / ticks)
        r = deg * (math.pi / 180.0)

        # tick inner and outer points
        outer = (pos[0] + math.sin(r) * radius, pos[1] + math.cos(r) * radius)
        inner = (
            pos[0] + math.sin(r) * (radius - 3),
            pos[1] + math.cos(r) * (radius - 3),
        )

        screen.shape(shape.line(*inner, *outer, 1.5))


def draw_cursor(cursor):
    cx = int(cursor[0] + canvas_area[0]) - 1
    cy = int(cursor[1] + canvas_area[1]) - 1
    # draw the current cursor
    i = (math.sin(badge.ticks / 120) * 60) + 60
    screen.pen = color.rgb(i, i, i)
    screen.rectangle(cx + 2, cy, 2, 1)
    screen.rectangle(cx - 3, cy, 2, 1)
    screen.rectangle(cx, cy + 2, 1, 2)
    screen.rectangle(cx, cy - 3, 1, 2)
