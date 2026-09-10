import math
from badgeware import screen, PixelFont, SpriteSheet, shapes, brushes, io, Image

screen.antialias = Image.X2
canvas_area = (10, 15, 140, 85)

font = PixelFont.load("/system/assets/fonts/vest.ppf")
mona = SpriteSheet("/system/assets/mona-sprites/mona-dance.png", 6, 1).animation()


def draw_mona(pos, direction):
    frame = int(io.ticks / 150)
    screen.scale_blit(mona.frame(frame), pos[0], pos[1], 28 * direction, 24)


def draw_background():
    # fill the background in that classic red...
    screen.brush = brushes.color(170, 45, 40)
    screen.draw(shapes.rectangle(0, 0, 160, 120))

    # draw the embossed gold logo
    screen.font = font
    w, _ = screen.measure_text("MonaSketch")
    screen.brush = brushes.color(240, 210, 160)
    screen.text("MonaSketch", 80 - (w / 2) - 1, -1)
    screen.brush = brushes.color(190, 140, 80, 100)
    screen.text("MonaSketch", 80 - (w / 2), 0)

    # draw the canvas area grey background and screen shadows
    screen.brush = brushes.color(210, 210, 210)
    screen.draw(shapes.rounded_rectangle(*canvas_area, 6))
    screen.brush = brushes.color(180, 180, 180)
    screen.draw(
        shapes.rounded_rectangle(
            canvas_area[0] + 3, canvas_area[1], canvas_area[2] - 5, 3, 2
        )
    )
    screen.draw(
        shapes.rounded_rectangle(
            canvas_area[0], canvas_area[1] + 3, 3, canvas_area[3] - 5, 2
        )
    )

    # draw highlights on the plastic "curve"
    screen.brush = brushes.color(255, 255, 255, 100)
    screen.draw(
        shapes.rectangle(
            canvas_area[0] - 3, canvas_area[1] + 5, 1, canvas_area[3] - 10, 2
        )
    )
    screen.draw(
        shapes.rectangle(
            canvas_area[0] + canvas_area[2] + 2,
            canvas_area[1] + 5,
            1,
            canvas_area[3] - 10,
            2,
        )
    )


left_dial_angle = 0
right_dial_angle = 0


def draw_dial(angle, pos):
    radius = 16

    # calculate an offset to fake perspective on the dials
    offset = (80 - pos[0]) / 35

    # draw the dial shadow
    screen.brush = brushes.color(0, 0, 0, 40)
    screen.draw(shapes.circle(pos[0] + offset * 1.5, pos[1], radius + 2))

    # draw the dial shaft
    screen.brush = brushes.color(150, 160, 170)
    screen.draw(shapes.circle(pos[0] + offset, pos[1], radius))

    # draw the dial surface
    screen.brush = brushes.color(220, 220, 230)
    screen.draw(shapes.circle(*pos, radius))

    # draw the animated ticks around the dial edge
    screen.brush = brushes.color(190, 190, 220)
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

        screen.draw(shapes.line(*inner, *outer, 1.5))


def draw_cursor(cursor):
    cx = int(cursor[0] + canvas_area[0])
    cy = int(cursor[1] + canvas_area[1])
    # draw the current cursor
    i = (math.sin(io.ticks / 250) * 127) + 127
    screen.brush = brushes.xor(i, i, i)
    screen.draw(shapes.rectangle(cx + 2, cy, 2, 1))
    screen.draw(shapes.rectangle(cx - 3, cy, 2, 1))
    screen.draw(shapes.rectangle(cx, cy + 2, 1, 2))
    screen.draw(shapes.rectangle(cx, cy - 3, 1, 2))
