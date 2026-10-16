import math

mona = image.load("assets/mona.png")
large_font = font.ignore
small_font = font.ark

TILE_COLORS = (
    None,
    color.rgb(3, 58, 22),
    color.rgb(25, 108, 46),
    color.rgb(46, 160, 67),
    color.rgb(46, 160, 67),
    color.rgb(86, 211, 100),
    color.rgb(3, 58, 22),
    color.rgb(25, 108, 46),
    color.rgb(46, 160, 67),
    color.rgb(25, 108, 46),
)


def draw_status(complete):
    screen.blit(mona, vec2(0, 72))
    screen.font = small_font
    screen.pen = color.white
    screen.text("mona's quest", 65, 0)

    screen.font = large_font
    screen.text("%d/9" % len(complete), 5, 8)
    screen.font = small_font
    screen.pen = color.rgb(140, 160, 180)
    screen.text("found", 7, 30)


def draw_tiles(complete):
    tile = shape.squircle(0, 0, 1, 6)
    origin_x = 70
    origin_y = 31
    screen.font = large_font

    for y in range(3):
        for x in range(3):
            pulse = 0.8 + (((math.sin(badge.ticks / 250 + x + y) / 2) + 0.5) / 2)
            index = x + y * 3 + 1
            tile_x = origin_x + x * 34
            tile_y = origin_y + y * 34
            label = str(index)
            label_x = tile_x - 6
            label_y = tile_y - 15

            if index in complete:
                screen.pen = TILE_COLORS[index]
                tile.transform = mat3().translate(tile_x, tile_y).scale(16)
                screen.shape(tile)
                screen.pen = color.rgb(255, 255, 255, int(150 * pulse))
            else:
                border = color.rgb(
                    int(50 * pulse),
                    int(60 * pulse),
                    int(70 * pulse),
                )
                tile.transform = mat3().translate(tile_x, tile_y).scale(16)
                screen.pen = border
                screen.shape(tile)
                tile.transform = mat3().translate(tile_x, tile_y).scale(14)
                screen.pen = color.rgb(21, 27, 35)
                screen.shape(tile)
                screen.pen = border

            screen.text(label, label_x, label_y)
