icons = image.load("assets/icons.png").spritesheet(4, 1)
arrows = image.load("assets/arrows.png").spritesheet(3, 1)

screen.font = font.ark

COLORS = {
    "happy": color.rgb(141, 39, 135),
    "hunger": color.rgb(53, 141, 39),
    "clean": color.rgb(39, 106, 171),
}


def background():
    screen.pen = color.rgb(219, 231, 239)
    screen.clear()
    screen.pen = color.rgb(146, 190, 122)
    screen.shape(shape.rectangle(0, 72, screen.width, 48))
    screen.pen = color.rgb(105, 151, 92)
    screen.shape(shape.rectangle(0, 88, screen.width, 32))


def draw_bar(name, x, amount):
    screen.pen = color.rgb(250, 250, 250, 190)
    screen.shape(shape.rounded_rectangle(x, 5, 45, 12, 3))
    screen.blit(icons.sprite(("happy", "hunger", "clean").index(name), 0), vec2(x + 2, 7))
    screen.pen = color.rgb(50, 50, 50, 90)
    screen.shape(shape.rounded_rectangle(x + 14, 8, 27, 6, 2))
    screen.pen = color.red if amount <= 30 and int(badge.ticks / 250) % 2 else COLORS[name]
    screen.shape(shape.rounded_rectangle(x + 14, 8, max(2, 27 * amount / 100), 6, 2))


def draw(mona):
    draw_bar("happy", 6, mona.happy())
    draw_bar("hunger", 57, mona.hunger())
    draw_bar("clean", 108, mona.clean())

    if mona.is_dead():
        screen.pen = color.white
        screen.text("SELECT TO RESET", 41, 106)
        return

    for index, (label, x) in enumerate((("PLAY", 8), ("FEED", 59), ("CLEAN", 108))):
        screen.pen = color.rgb(255, 255, 255, 210)
        screen.shape(shape.rounded_rectangle(x, 103, 44, 14, 3))
        screen.blit(arrows.sprite(index, 0), vec2(x + 3, 106))
        screen.pen = color.rgb(40, 40, 40)
        screen.text(label, x + 13, 106)
