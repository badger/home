TITLE_H = 14
MENU_Y = 14
MENU_H = 12
TOOLBOX_W = 30
TOOL_SIZE = 13
TOOL_X = 2
TOOL_Y = 29
OPTIONS = (3, 98, 24, 46)
WORKSPACE = (30, 26, 290, 186)
CANVAS_X = 33
CANVAS_Y = 29
CANVAS_W = 280
CANVAS_H = 176
BOTTOM_Y = 212
SWATCH = (2, 214, 26, 24)
PALETTE_X = 32
PALETTE_Y = 214
PALETTE_PITCH = 13
PALETTE_CELL = 12
CLOSE = (305, 2, 13, 10)

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
    "#..........",
    "##.........",
    "#w#........",
    "#ww#.......",
    "#www#......",
    "#wwww#.....",
    "#wwwww#....",
    "#wwwwww#...",
    "#wwwwwww#..",
    "#wwwwwwww#.",
    "#wwwww#####",
    "#ww#ww#....",
    "#w#.#ww#...",
    "##..#ww#...",
    "#....#ww#..",
    ".....#ww#..",
    "......##...",
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


def palette_rect(index):
    column, row = index % PALETTE_COLS, index // PALETTE_COLS
    return PALETTE_X + column * PALETTE_PITCH, PALETTE_Y + row * PALETTE_PITCH, PALETTE_CELL, PALETTE_CELL


def menu_titles():
    screen.font = TEXT
    x = 4
    titles = []
    for title, items in MENUS:
        width = screen.measure_text(title)[0] + 8
        titles.append((title, items, x, width))
        x += width
    return titles


def menu_items(x, items):
    screen.font = TEXT
    width = max(screen.measure_text(item)[0] for item in items) + 24
    return [(item, x, MENU_Y + MENU_H + 3 + index * MENU_H, width) for index, item in enumerate(items)]


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
    screen.text("untitled - Mona Paint", 4, 1)
    for offset, glyph in ((32, "min"), (19, "max"), (0, "close")):
        x, y, w, h = CLOSE
        x -= offset
        raised(x, y, w, h)
        screen.pen = BLACK
        if glyph == "min":
            screen.rectangle(x + 3, y + 6, 6, 2)
        elif glyph == "max":
            screen.rectangle(x + 3, y + 2, 7, 2)
            screen.rectangle(x + 3, y + 2, 1, 6)
            screen.rectangle(x + 9, y + 2, 1, 6)
            screen.rectangle(x + 3, y + 7, 7, 1)
        else:
            for step in range(6):
                screen.rectangle(x + 3 + step, y + 2 + step, 2, 1)
                screen.rectangle(x + 8 - step, y + 2 + step, 2, 1)


def draw_menu_bar(open_menu):
    screen.pen = SILVER
    screen.rectangle(0, MENU_Y, screen.width, MENU_H)
    screen.font = TEXT
    for title, _items, x, width in menu_titles():
        if title == open_menu:
            sunken(x, MENU_Y, width, MENU_H)
        screen.pen = BLACK
        screen.text(title, x + 4, MENU_Y)


def draw_menu(open_menu, cursor_x, cursor_y):
    for title, items, x, _width in menu_titles():
        if title != open_menu:
            continue
        rows = menu_items(x, items)
        width = rows[0][3]
        raised(x, MENU_Y + MENU_H, width, len(rows) * MENU_H + 6)
        screen.font = TEXT
        for item, item_x, item_y, item_w in rows:
            if inside(cursor_x, cursor_y, (item_x, item_y, item_w, MENU_H)):
                screen.pen = NAVY
                screen.rectangle(item_x + 3, item_y, item_w - 6, MENU_H)
                screen.pen = WHITE
            else:
                screen.pen = BLACK
            screen.text(item, item_x + 12, item_y)


def draw_toolbox(tools, tool, options, option):
    screen.pen = SILVER
    screen.rectangle(0, MENU_Y + MENU_H, TOOLBOX_W, BOTTOM_Y - MENU_Y - MENU_H)
    for index, name in enumerate(tools):
        x, y, w, h = tool_rect(index)
        if name == tool:
            sunken(x, y, w, h, WHITE)
        else:
            raised(x, y, w, h)
        screen.blit(icons[name], vec2(x + 2, y + 2))
    x, y, w, h = OPTIONS
    sunken(x, y, w, h)
    for index, choice in enumerate(options):
        cx = x + w // 2
        cy = y + 8 + index * 15
        if index == option:
            screen.pen = NAVY
            screen.rectangle(x + 2, cy - 6, w - 4, 13)
        screen.pen = WHITE if index == option else BLACK
        if choice == "outline":
            screen.rectangle(cx - 7, cy - 4, 14, 1)
            screen.rectangle(cx - 7, cy + 4, 14, 1)
            screen.rectangle(cx - 7, cy - 4, 1, 9)
            screen.rectangle(cx + 6, cy - 4, 1, 9)
        elif choice == "filled":
            screen.rectangle(cx - 7, cy - 4, 14, 9)
        else:
            screen.circle(vec2(cx, cy), max(1, choice / 2))


def draw_workspace(canvas):
    screen.pen = GREY
    screen.rectangle(*WORKSPACE)
    screen.blit(canvas, vec2(CANVAS_X, CANVAS_Y))
    screen.pen = NAVY
    for x, y in ((CANVAS_X + CANVAS_W, CANVAS_Y + CANVAS_H // 2),
                 (CANVAS_X + CANVAS_W // 2, CANVAS_Y + CANVAS_H),
                 (CANVAS_X + CANVAS_W, CANVAS_Y + CANVAS_H)):
        screen.rectangle(x, y, 3, 3)


def draw_palette(pen):
    screen.pen = SILVER
    screen.rectangle(0, BOTTOM_Y, screen.width, screen.height - BOTTOM_Y)
    sunken(*SWATCH)
    x, y, _w, _h = SWATCH
    screen.pen = BLACK
    screen.rectangle(x + 10, y + 10, 12, 11)
    screen.pen = WHITE
    screen.rectangle(x + 11, y + 11, 10, 9)
    screen.pen = BLACK
    screen.rectangle(x + 4, y + 3, 12, 11)
    screen.pen = pen
    screen.rectangle(x + 5, y + 4, 10, 9)
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
