TITLE_H = 10
MENU_Y = 10
MENU_H = 10
TEXT_Y = -2
TOOLBOX_W = 27
TOOL_SIZE = 12
TOOL_X = 1
TOOL_Y = 21
OPTIONS = (2, 83, 23, 22)
OPTION_PITCH = 7
WORKSPACE = (27, 20, 133, 86)
CANVAS_X = 29
CANVAS_Y = 22
CANVAS_W = 126
CANVAS_H = 80
PIXEL = 1
PIXELS_W = CANVAS_W // PIXEL
PIXELS_H = CANVAS_H // PIXEL
BOTTOM_Y = 106
SWATCH = (1, 107, 14, 12)
PALETTE_X = 16
PALETTE_Y = 108
PALETTE_PITCH_X = 10
PALETTE_PITCH_Y = 10
PALETTE_CELL_W = 9
PALETTE_CELL_H = 10
CLOSE = (151, 1, 8, 8)

BLACK = color.rgb(0, 0, 0)
WHITE = color.rgb(255, 255, 255)
SILVER = color.rgb(192, 192, 192)
GREY = color.rgb(128, 128, 128)
NAVY = color.rgb(0, 0, 128)
TITLE_BANDS = 24
TITLE_PENS = tuple(
    color.rgb(int(16 * band / (TITLE_BANDS - 1)), int(132 * band / (TITLE_BANDS - 1)), int(128 + 80 * band / (TITLE_BANDS - 1)))
    for band in range(TITLE_BANDS)
)

TEXT = font.winds
TITLE_TEXT = font.match

PALETTE = (
    (0, 0, 0), (255, 0, 0), (255, 128, 64), (255, 255, 0), (0, 255, 0), (0, 255, 255), (0, 128, 255),
    (255, 255, 255), (255, 0, 128), (255, 255, 128), (0, 255, 128), (128, 255, 255), (128, 128, 255), (255, 0, 255),
)
INVERT_PAIRS = ((0, 7), (1, 5), (2, 11), (3, 6), (4, 13), (8, 10), (9, 12))
LEGACY_PALETTE = (
    (0, 0, 0), (128, 128, 128), (128, 0, 0), (128, 128, 0), (0, 128, 0), (0, 128, 128), (0, 0, 128),
    (128, 0, 128), (128, 128, 64), (0, 64, 64), (0, 128, 255), (0, 64, 128), (64, 0, 255), (128, 64, 0),
    (255, 255, 255), (192, 192, 192), (255, 0, 0), (255, 255, 0), (0, 255, 0), (0, 255, 255), (0, 0, 255),
    (255, 0, 255), (255, 255, 128), (0, 255, 128), (128, 255, 255), (128, 128, 255), (255, 0, 128), (255, 128, 64),
)
PALETTE_COLS = 14
PALETTE_PENS = tuple(color.rgb(*rgb) for rgb in PALETTE)

MENUS = (
    ("File", ("New", "Save", "Exit")),
    ("Edit", ("Undo",)),
    ("Image", ("Invert Colors", "Clear Image")),
)

INKS = {
    "#": (0, 0, 0),
    "w": (255, 255, 255),
    "g": (128, 128, 128),
    "s": (192, 192, 192),
    "y": (255, 255, 0),
    "r": (255, 0, 0),
    "b": (0, 0, 255),
    "p": (255, 128, 192),
    "o": (128, 64, 0),
}

ICONS = {
    "pencil": (
        ".......#.",
        "......#r#",
        ".....#y#.",
        "....#y#..",
        "...#y#...",
        "..#y#....",
        ".#w#.....",
        ".##......",
        "#........",
    ),
    "brush": (
        "........#",
        ".......#.",
        "......#..",
        ".....#...",
        "....g....",
        "..oog....",
        ".oooo....",
        "#ooo.....",
        "##.......",
    ),
    "eraser": (
        ".........",
        "....#####",
        "...#ppp##",
        "..#ppp#w#",
        ".#ppp#w#.",
        "#####w#..",
        "#www#w#..",
        "#####....",
        ".........",
    ),
    "fill": (
        "...#.....",
        "..#w#....",
        ".#www#...",
        "#wwwww#..",
        ".#wwwww#b",
        "..#www#.b",
        "...#w#..b",
        "....#...b",
        ".........",
    ),
    "picker": (
        ".......##",
        "......###",
        ".....###.",
        "....#w#..",
        "...#w#...",
        "..#w#....",
        ".#w#.....",
        "#b#......",
        "#........",
    ),
    "spray": (
        "#.#......",
        ".#.#.##..",
        "#.#..##..",
        "....####.",
        "....#ww#.",
        "....#ww#.",
        "....#ww#.",
        "....#ww#.",
        "....####.",
    ),
    "line": (
        "#........",
        ".#.......",
        "..#......",
        "...#.....",
        "....#....",
        ".....#...",
        "......#..",
        ".......#.",
        "........#",
    ),
    "rectangle": (
        ".........",
        "#########",
        "#.......#",
        "#.......#",
        "#.......#",
        "#.......#",
        "#.......#",
        "#########",
        ".........",
    ),
    "ellipse": (
        ".........",
        "..#####..",
        ".#.....#.",
        "#.......#",
        "#.......#",
        "#.......#",
        ".#.....#.",
        "..#####..",
        ".........",
    ),
    "rounded": (
        ".........",
        ".#######.",
        "#.......#",
        "#.......#",
        "#.......#",
        "#.......#",
        "#.......#",
        ".#######.",
        ".........",
    ),
}

POINTER = (
    "#.......",
    "##......",
    "#w#.....",
    "#ww#....",
    "#www#...",
    "#wwww#..",
    "#wwwww#.",
    "#wwwwww#",
    "#ww#####",
    "#w#ww#..",
    "##.#ww#.",
    "#..#ww#.",
    "....##..",
)


def bitmap(rows):
    sprite = image(len(rows[0]), len(rows))
    sprite.pen = color.rgb(0, 0, 0, 0)
    sprite.clear()
    for y, row in enumerate(rows):
        for x, ink in enumerate(row):
            if ink != ".":
                sprite.pen = color.rgb(*INKS[ink])
                sprite.put(x, y)
    return sprite


icons = {name: bitmap(rows) for name, rows in ICONS.items()}
pointer = bitmap(POINTER)


def raised(x, y, w, h):
    screen.pen = SILVER
    screen.rectangle(x, y, w, h)
    screen.pen = WHITE
    screen.rectangle(x, y, w - 1, 1)
    screen.rectangle(x, y, 1, h - 1)
    screen.pen = BLACK
    screen.rectangle(x, y + h - 1, w, 1)
    screen.rectangle(x + w - 1, y, 1, h)
    screen.pen = GREY
    screen.rectangle(x + 1, y + h - 2, w - 2, 1)
    screen.rectangle(x + w - 2, y + 1, 1, h - 2)


def sunken(x, y, w, h, face=SILVER):
    screen.pen = face
    screen.rectangle(x, y, w, h)
    screen.pen = GREY
    screen.rectangle(x, y, w - 1, 1)
    screen.rectangle(x, y, 1, h - 1)
    screen.pen = WHITE
    screen.rectangle(x, y + h - 1, w, 1)
    screen.rectangle(x + w - 1, y, 1, h)


def tool_rect(index):
    return TOOL_X + (index % 2) * TOOL_SIZE, TOOL_Y + (index // 2) * TOOL_SIZE, TOOL_SIZE, TOOL_SIZE


def option_rect(index):
    x, y, w, _h = OPTIONS
    return x + 1, y + 1 + index * OPTION_PITCH, w - 2, OPTION_PITCH


def palette_rect(index):
    column, row = index % PALETTE_COLS, index // PALETTE_COLS
    return PALETTE_X + column * PALETTE_PITCH_X, PALETTE_Y + row * PALETTE_PITCH_Y, PALETTE_CELL_W, PALETTE_CELL_H


def menu_titles():
    screen.font = TEXT
    x = 2
    titles = []
    for title, items in MENUS:
        width = screen.measure_text(title)[0] + 6
        titles.append((title, items, x, width))
        x += width
    return titles


def menu_items(x, items):
    screen.font = TEXT
    width = max(screen.measure_text(item)[0] for item in items) + 12
    return [(item, x, MENU_Y + MENU_H + 2 + index * MENU_H, width) for index, item in enumerate(items)]


def inside(x, y, area):
    ax, ay, aw, ah = area
    return ax <= x < ax + aw and ay <= y < ay + ah


def draw_title():
    band = screen.width / TITLE_BANDS
    for index in range(TITLE_BANDS):
        screen.pen = TITLE_PENS[index]
        screen.rectangle(int(index * band), 0, int(band) + 1, TITLE_H)
    screen.font = TITLE_TEXT
    screen.pen = WHITE
    screen.text("Mona Paint", 2, TEXT_Y)
    for offset, glyph in ((18, "min"), (9, "max"), (0, "close")):
        x, y, w, h = CLOSE
        x -= offset
        raised(x, y, w, h)
        screen.pen = BLACK
        if glyph == "min":
            screen.rectangle(x + 2, y + 4, 3, 1)
        elif glyph == "max":
            screen.rectangle(x + 2, y + 1, 4, 1)
            screen.rectangle(x + 2, y + 1, 1, 4)
            screen.rectangle(x + 5, y + 1, 1, 4)
            screen.rectangle(x + 2, y + 4, 4, 1)
        else:
            for step in range(4):
                screen.put(x + 2 + step, y + 1 + step)
                screen.put(x + 5 - step, y + 1 + step)


def draw_menu_bar(open_menu):
    screen.pen = SILVER
    screen.rectangle(0, MENU_Y, screen.width, MENU_H)
    screen.font = TEXT
    for title, _items, x, width in menu_titles():
        if title == open_menu:
            sunken(x, MENU_Y, width, MENU_H)
        screen.pen = BLACK
        screen.text(title, x + 3, MENU_Y + TEXT_Y)


def draw_menu(open_menu, cursor_x, cursor_y):
    for title, items, x, _width in menu_titles():
        if title != open_menu:
            continue
        rows = menu_items(x, items)
        width = rows[0][3]
        raised(x, MENU_Y + MENU_H, width, len(rows) * MENU_H + 4)
        screen.font = TEXT
        for item, item_x, item_y, item_w in rows:
            if inside(cursor_x, cursor_y, (item_x, item_y, item_w, MENU_H)):
                screen.pen = NAVY
                screen.rectangle(item_x + 2, item_y, item_w - 4, MENU_H)
                screen.pen = WHITE
            else:
                screen.pen = BLACK
            screen.text(item, item_x + 6, item_y + TEXT_Y)


def draw_toolbox(tools, tool, options, option):
    screen.pen = SILVER
    screen.rectangle(0, MENU_Y + MENU_H, TOOLBOX_W, BOTTOM_Y - MENU_Y - MENU_H)
    for index, name in enumerate(tools):
        x, y, w, h = tool_rect(index)
        if name == tool:
            sunken(x, y, w, h, WHITE)
        else:
            raised(x, y, w, h)
        screen.blit(icons[name], vec2(x + 1, y + 1))
    sunken(*OPTIONS)
    for index, choice in enumerate(options):
        ox, oy, ow, oh = option_rect(index)
        cx = ox + ow // 2
        cy = oy + oh // 2
        if index == option:
            screen.pen = NAVY
            screen.rectangle(ox, oy, ow, oh)
        screen.pen = WHITE if index == option else BLACK
        if choice == "outline":
            screen.rectangle(cx - 5, cy - 2, 10, 1)
            screen.rectangle(cx - 5, cy + 2, 10, 1)
            screen.rectangle(cx - 5, cy - 2, 1, 5)
            screen.rectangle(cx + 4, cy - 2, 1, 5)
        elif choice == "filled":
            screen.rectangle(cx - 5, cy - 2, 10, 5)
        else:
            screen.circle(vec2(cx, cy), index + 1)


def draw_workspace(canvas):
    screen.pen = GREY
    screen.rectangle(*WORKSPACE)
    screen.blit(canvas, rect(CANVAS_X, CANVAS_Y, CANVAS_W, CANVAS_H))
    screen.pen = NAVY
    for x, y in ((CANVAS_X + CANVAS_W, CANVAS_Y + CANVAS_H // 2),
                 (CANVAS_X + CANVAS_W // 2, CANVAS_Y + CANVAS_H),
                 (CANVAS_X + CANVAS_W, CANVAS_Y + CANVAS_H)):
        screen.rectangle(x, y, 2, 2)


def draw_palette(pen):
    screen.pen = SILVER
    screen.rectangle(0, BOTTOM_Y, screen.width, screen.height - BOTTOM_Y)
    sunken(*SWATCH)
    x, y, _w, _h = SWATCH
    screen.pen = BLACK
    screen.rectangle(x + 6, y + 5, 6, 5)
    screen.pen = WHITE
    screen.rectangle(x + 7, y + 6, 4, 3)
    screen.pen = BLACK
    screen.rectangle(x + 2, y + 2, 6, 5)
    screen.pen = pen
    screen.rectangle(x + 3, y + 3, 4, 3)
    for index, swatch in enumerate(PALETTE_PENS):
        cx, cy, w, h = palette_rect(index)
        sunken(cx, cy, w, h, swatch)
        screen.pen = BLACK
        screen.rectangle(cx + 1, cy + 1, w - 2, 1)
        screen.rectangle(cx + 1, cy + 1, 1, h - 2)
        screen.pen = swatch
        screen.rectangle(cx + 2, cy + 2, w - 3, h - 3)


def draw_pointer(x, y):
    screen.blit(pointer, vec2(int(x), int(y)))
