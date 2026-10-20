from content import (
    BLACK, DULL_GOLD, FOOD_HEAL, GOLD, GRAY_1, GRAY_2, GRAY_3, GRAY_4, GRAY_5, GRAY_6, GREEN_1, GREEN_2,
    GREEN_3, GREEN_4, GREEN_5, GREEN_5_GRASS, GREEN_5_SHRUB, GREEN_6, HURT, LOW_HP, PACK_BLOCK,
    PACK_BLOCKS, PACK_MAX_SLOTS, POTION_HEAL_MIN, PURPLE,
)
from items import ITEMS, potion_heal_max
from monsters import ENEMY_KINDS
from rings import RINGS
from scrolls import SCROLLS
from world import (
    DIRT, HOLE, LADDER_UP, MAP_H, MAP_W, OPEN_GROUND, PATH, ROCK, ROOM_FLOOR, SEALED_GATE, STAIRS_DOWN,
    STAIRS_UP,
)

WIDTH = screen.width
HEIGHT = screen.height
CELL_W = 10
CELL_H = 10
MAP_Y = 25
VIEW_SCALE = 2
VIEW_W = 16
VIEW_H = 8
MAP_STRIP_W = VIEW_W * CELL_W * VIEW_SCALE
MAP_STRIP_H = VIEW_H * CELL_H * VIEW_SCALE
LOG_Y = MAP_Y + MAP_STRIP_H + 3
LOG_W = WIDTH - 8
GLYPH_LIFT = 2
HEADER_H = MAP_Y - 4
HEADER_MARGIN = 6
HEADER_PART_GAP = 4

PACK_COLS = PACK_BLOCK
PACK_ROWS = PACK_BLOCKS
PACK_SLOT = 30
PACK_BOX = 26
PACK_GRID_W = PACK_COLS * PACK_SLOT - (PACK_SLOT - PACK_BOX)
PACK_GRID_H = PACK_ROWS * PACK_SLOT - (PACK_SLOT - PACK_BOX)
PACK_PANEL_Y = MAP_Y - 4
PACK_PANEL_H = MAP_STRIP_H + 6
PACK_GRID_X = (WIDTH - PACK_GRID_W) // 2
PACK_GRID_Y = PACK_PANEL_Y + 24
PACK_TITLE_Y = PACK_PANEL_Y + 4
PACK_NAME_Y = PACK_GRID_Y + PACK_GRID_H + 8
PACK_EFFECT_Y = PACK_NAME_Y + 15
PACK_HINT_Y = PACK_EFFECT_Y + 15
PACK_BACKDROP = color.rgb(0, 0, 0, 205)
PACK_LOCKED = color.rgb(144, 150, 146).darken(50)
DEAD_TITLE_Y = PACK_PANEL_Y + 35
DEAD_HINT_Y = PACK_PANEL_Y + 101
ESCAPE_TITLE_Y = PACK_PANEL_Y + 8
ESCAPE_TALLY_Y = PACK_PANEL_Y + 46
ESCAPE_TALLY_PITCH = 15
ESCAPE_TALLY_X = 70
ESCAPE_TALLY_W = WIDTH - ESCAPE_TALLY_X * 2
ESCAPE_HINT_Y = PACK_PANEL_Y + PACK_PANEL_H - 22
MENU_TABS = (("pack", "PACK"), ("map", "MAP"))
MENU_TAB_GAP = 24
MENU_TAB_RULE = 14
MENU_MAP_SCALE = 6
MENU_MAP_W = MAP_W * MENU_MAP_SCALE
MENU_MAP_H = MAP_H * MENU_MAP_SCALE
MENU_MAP_X = 2
MENU_MAP_Y = HEIGHT - MENU_MAP_H - 2
MENU_STAT_X = MENU_MAP_X + MENU_MAP_W + 10
MENU_STAT_W = WIDTH - MENU_STAT_X - 4
MENU_STAT_PITCH = 16
MINIMAP_ROOM = color.rgb(144, 150, 146).darken(45)
MINIMAP_PATH = color.rgb(144, 150, 146).darken(65)

FILTERS = ("CRT", "PHOSPHOR", "CLEAN")
CRT_SPACING = 3
CRT_DARKNESS = 70
PHOSPHOR_DARKNESS = 60
PHOSPHOR_BRUSH = brush.duotone(color.rgb(2, 12, 6), color.rgb(150, 255, 170))

INTRO_TITLE_SCALE = 3
INTRO_TITLE_Y = 4
INTRO_SCENE_Y = 76
INTRO_FILTER_Y = 166
INTRO_FILTER_GAP = 18
INTRO_FILTER_PAD = 4
INTRO_HELP_Y = 188
INTRO_QUIT_Y = 202
INTRO_PROMPT_Y = 222
INTRO_OPTION_Y = 216
INTRO_OPTION_GAP = 12
INTRO_TILES = (
    "^  ^ ^----------",
    " ,,,,#|........|",
    "  o ,#......>..|",
    "^ ^  ^----------",
)
INTRO_GLYPHS = (
    "                ",
    "    b    $   r  ",
    "   @     !    s ",
    "                ",
)

small_font = font.sins
large_font = font.curse
header_font = font.smart
title_font = font.troll

PATTERN_SIZE = 8
PATTERN_MASK = PATTERN_SIZE - 1
SHADOW_BRUSH = color.rgb(0, 0, 0, 150)


def tile_patch(pen):
    scratch = image(CELL_W + PATTERN_SIZE, CELL_H + PATTERN_SIZE)
    scratch.antialias = image.OFF
    scratch.pen = pen
    scratch.rectangle(0, 0, scratch.width, scratch.height)

    made = {}
    patch = []
    for y in range(PATTERN_SIZE):
        phase_y = (y * CELL_H) & PATTERN_MASK
        for x in range(PATTERN_SIZE):
            phase_x = (x * CELL_W) & PATTERN_MASK
            phase = phase_y * PATTERN_SIZE + phase_x
            tile = made.get(phase)
            if tile is None:
                tile = image(CELL_W, CELL_H)
                tile.antialias = image.OFF
                tile.blit(scratch, vec2(-phase_x, -phase_y))
                made[phase] = tile
            patch.append(tile)
    return patch


ROOM_PATCH = tile_patch(brush.pattern(GRAY_6, BLACK, 10))
PATH_PATCH = tile_patch(brush.pattern(GREEN_6, GRAY_6, 8))
WALL_PATCH = tile_patch(brush.pattern(GRAY_5, GRAY_6, 11))
DIRT_PATCH = tile_patch(brush.pattern(GREEN_6, GRAY_6, 9))
GRASS_PATCH = tile_patch(brush.pattern(GREEN_6, GREEN_5_GRASS, 32))
SHRUB_PATCH = tile_patch(brush.pattern(GREEN_6, GREEN_5_SHRUB, 16))
HOLE_PATCH = tile_patch(brush.pattern(GRAY_6, GREEN_6, 19))
UP_STAIR_PATCH = tile_patch(brush.pattern(GRAY_5, GRAY_6, 7))
DOWN_STAIR_PATCH = tile_patch(brush.pattern(GRAY_5, GRAY_6, 26))
LADDER_PATCH = tile_patch(brush.pattern(GRAY_4, GRAY_6, 24))
GATE_PATCH = tile_patch(brush.pattern(GRAY_6, GOLD, 4))
SEALED_GATE_PATCH = tile_patch(brush.pattern(GRAY_6, DULL_GOLD, 4))
CAVE_WALL_PATCH = tile_patch(brush.pattern(GRAY_5, GRAY_6, 16))
CAVE_DIRT_SHARE = 62

map_view = image(VIEW_W * CELL_W, VIEW_H * CELL_H)
map_view.antialias = image.OFF
map_view.font = small_font
minimap_view = image(MAP_W, MAP_H)
minimap_view.antialias = image.OFF
banner_view = image(WIDTH // 2, 26)
banner_view.antialias = image.OFF


def build_intro_scene():
    patches = {
        " ": GRASS_PATCH, "^": SHRUB_PATCH, ",": DIRT_PATCH, "o": HOLE_PATCH, "#": PATH_PATCH,
        ".": ROOM_PATCH, ">": DOWN_STAIR_PATCH, "-": WALL_PATCH, "|": WALL_PATCH,
    }
    pens = {"@": GREEN_1}
    for item in ITEMS.values():
        pens.setdefault(item["glyph"], item["pen"])
    for char, kind in ENEMY_KINDS.items():
        pens[char] = kind["pen"]

    scene = image(len(INTRO_TILES[0]) * CELL_W, len(INTRO_TILES) * CELL_H)
    scene.antialias = image.OFF
    scene.font = small_font
    for y, tiles in enumerate(INTRO_TILES):
        glyphs = INTRO_GLYPHS[y]
        for x, tile in enumerate(tiles):
            px = x * CELL_W
            py = y * CELL_H
            scene.blit(patches[tile][(y & PATTERN_MASK) * PATTERN_SIZE + (x & PATTERN_MASK)], vec2(px, py))
            if glyphs[x] != " ":
                scene.pen = pens.get(glyphs[x], GRAY_2)
                scene.text(glyphs[x], px + 2, py - GLYPH_LIFT)
    return scene


def build_intro_title():
    canvas = image(1, 1)
    canvas.font = title_font
    title_w, title_h = canvas.measure_text("ROGUE")
    canvas = image(int(title_w) + 2, int(title_h) + 2)
    canvas.antialias = image.OFF
    canvas.font = title_font
    canvas.pen = GREEN_5
    canvas.text("ROGUE", 1, 1)
    canvas.pen = GREEN_1
    canvas.text("ROGUE", 0, 0)
    return canvas


INTRO_SCENE = build_intro_scene()
INTRO_TITLE = build_intro_title()


def draw_text(text, x, y, pen):
    screen.pen = pen
    screen.text(text, x, y)


def draw_centered(text, y, pen):
    w, _ = screen.measure_text(text)
    draw_text(text, (WIDTH - w) / 2, y, pen)


def draw_doubled(text, chosen_font, y, pen):
    banner_view.font = chosen_font
    banner_view.pen = BLACK
    banner_view.clear()
    width, _height = banner_view.measure_text(text)
    banner_view.pen = pen
    banner_view.text(text, (banner_view.width - width) / 2, 0)
    screen.blit(banner_view, rect(0, y, banner_view.width * 2, banner_view.height * 2))


def cell_patch(area, x, y):
    tile = area.tiles[y][x]
    if area.gate is not None and (x, y) == area.gate:
        return GATE_PATCH
    if tile == LADDER_UP:
        return LADDER_PATCH
    if tile == STAIRS_UP:
        return UP_STAIR_PATCH
    if tile == STAIRS_DOWN:
        return DOWN_STAIR_PATCH
    if tile == ROOM_FLOOR:
        return ROOM_PATCH
    if tile == PATH:
        return PATH_PATCH
    if tile == DIRT:
        if area.outdoors or ((x * 73856093) ^ (y * 19349663)) % 100 < CAVE_DIRT_SHARE:
            return DIRT_PATCH
        return PATH_PATCH
    if tile == ROCK:
        return SHRUB_PATCH if area.outdoors else CAVE_WALL_PATCH
    if tile == HOLE:
        return HOLE_PATCH
    if tile == SEALED_GATE:
        return SEALED_GATE_PATCH
    if tile == OPEN_GROUND:
        return GRASS_PATCH if area.outdoors else None
    return WALL_PATCH


def cell_glyph(area, player, x, y):
    if x == player.x and y == player.y:
        return "@", GREEN_1
    if not area.visible[y][x]:
        return None
    enemy = area.enemy_at(x, y)
    if enemy is not None:
        return enemy.char, enemy.kind["pen"]
    item = area.item_at(x, y)
    if item is not None:
        definition = ITEMS[item.kind]
        return definition["glyph"], definition["pen"]
    return None


def minimap_pen(area, player, x, y):
    if x == player.x and y == player.y:
        return GREEN_1
    if not area.explored[y][x]:
        return None
    if area.visible[y][x] and area.enemy_at(x, y) is not None:
        return HURT
    if area.gate is not None and (x, y) == area.gate:
        return GOLD

    tile = area.tiles[y][x]
    if tile == SEALED_GATE:
        return DULL_GOLD
    if tile == LADDER_UP:
        return GOLD
    if tile == STAIRS_UP or tile == STAIRS_DOWN:
        return GREEN_2
    if tile == HOLE:
        return GREEN_4
    if tile == ROOM_FLOOR:
        return MINIMAP_ROOM
    if tile == PATH:
        return MINIMAP_PATH
    if tile == DIRT:
        return GREEN_5_GRASS if area.outdoors else MINIMAP_PATH
    if tile == ROCK:
        return GREEN_5_SHRUB if area.outdoors else GRAY_6
    if tile == OPEN_GROUND:
        return GREEN_6 if area.outdoors else None
    return GRAY_6


def item_effect(pack, item, level):
    kind = item.kind
    if kind == "potion":
        return "heals " + str(POTION_HEAL_MIN) + "-" + str(potion_heal_max(level))
    if kind == "food":
        return "+1 max HP, heals " + str(FOOD_HEAL)
    if kind == "scroll":
        return SCROLLS[item.effect]["hint"] if item.effect in pack.identified else "effect unknown"
    if kind == "arrows":
        return "ammunition, " + str(pack.arrows()) + " held"
    if kind == "bow":
        return "ENTER shoots the nearest foe" if item.equipped else "equip it to shoot arrows"
    if kind == "ring":
        return RINGS[item.effect]["hint"] if item.effect in pack.identified else "effect unknown"
    return ITEMS[kind]["hint"]


def draw_map(area, player):
    vx = clamp(player.x - VIEW_W // 2, 0, MAP_W - VIEW_W)
    vy = clamp(player.y - VIEW_H // 2, 0, MAP_H - VIEW_H)
    map_view.pen = BLACK
    map_view.clear()

    for row in range(VIEW_H):
        y = vy + row
        py = row * CELL_H
        for col in range(VIEW_W):
            x = vx + col
            if not area.explored[y][x]:
                continue
            px = col * CELL_W
            patch = cell_patch(area, x, y)
            if patch is not None:
                map_view.blit(patch[(y & PATTERN_MASK) * PATTERN_SIZE + (x & PATTERN_MASK)], vec2(px, py))
                if not area.visible[y][x]:
                    map_view.pen = SHADOW_BRUSH
                    map_view.rectangle(px, py, CELL_W, CELL_H)
            glyph = cell_glyph(area, player, x, y)
            if glyph is not None:
                map_view.pen = glyph[1]
                map_view.text(glyph[0], px + 2, py - GLYPH_LIFT)

    screen.blit(map_view, rect(0, MAP_Y, MAP_STRIP_W, MAP_STRIP_H))


def draw_header(game, menu):
    player = game.player
    pack = player.pack
    hp = [("HP " + str(player.hp) + "/" + str(player.max_hp), HURT if player.hp <= LOW_HP else GREEN_1)]
    item = pack.selected() if menu.open and menu.tab == "pack" else None
    heal = 0
    if item is not None and item.kind == "potion":
        heal = min(potion_heal_max(game.level), player.max_hp - player.hp)
    elif item is not None and item.kind == "food":
        heal = min(FOOD_HEAL, player.max_hp + 1 - player.hp)
    if heal > 0:
        hp.append(("+" + str(heal), GREEN_3))
    groups = [
        hp,
        [("D" + str(game.level), GRAY_2)],
        [("ATK " + str(player.attack), GRAY_3)],
        [("ARM " + str(player.defence), GRAY_3)],
        [("!" + str(pack.count("potion")), GREEN_2), ("?" + str(pack.count("scroll")), PURPLE), ("/" + str(pack.arrows()), GRAY_2)],
    ]

    screen.pen = GRAY_6
    screen.rectangle(0, 0, WIDTH, HEADER_H)
    screen.font = header_font
    widths = [sum(screen.measure_text(text)[0] for text, _ in group) + HEADER_PART_GAP * (len(group) - 1) for group in groups]
    gap = (WIDTH - HEADER_MARGIN * 2 - sum(widths)) / (len(groups) - 1)
    _w, text_h = screen.measure_text("H")
    y = (HEADER_H - text_h) / 2
    x = HEADER_MARGIN
    for index, group in enumerate(groups):
        part_x = x
        for text, pen in group:
            draw_text(text, part_x, y, pen)
            part_x += screen.measure_text(text)[0] + HEADER_PART_GAP
        x += widths[index] + gap
    screen.font = small_font


def draw_map_tab(game, menu):
    area = game.area
    player = game.player
    minimap_view.pen = BLACK
    minimap_view.clear()
    for y in range(MAP_H):
        for x in range(MAP_W):
            pen = minimap_pen(area, player, x, y)
            if pen is not None:
                minimap_view.pen = pen
                minimap_view.put(x, y)

    screen.pen = GREEN_6
    screen.shape(shape.rectangle(MENU_MAP_X - 1, MENU_MAP_Y - 1, MENU_MAP_W + 2, MENU_MAP_H + 2).stroke(1))
    screen.blit(minimap_view, rect(MENU_MAP_X, MENU_MAP_Y, MENU_MAP_W, MENU_MAP_H))

    seen, total = area.exploration()
    stats = (
        ("explored", str(seen * 100 // total) + "%"),
        ("kills", str(game.kills)),
        ("items", str(game.items_found)),
        ("gold", str(player.gold)),
        ("turns", str(game.turns)),
        ("layer", "surface" if area.outdoors else str(area.layer)),
        ("seed", "%08x" % area.seed),
    )
    y = PACK_GRID_Y
    for label, value in stats:
        draw_text(label, MENU_STAT_X, y, GRAY_4)
        value_width, _ = screen.measure_text(value)
        draw_text(value, MENU_STAT_X + MENU_STAT_W - value_width, y, GREEN_2)
        y += MENU_STAT_PITCH

    if menu.saving:
        draw_text("You chronicle", MENU_STAT_X, MENU_MAP_Y + MENU_MAP_H - 26, GOLD)
        draw_text("your adventures...", MENU_STAT_X, MENU_MAP_Y + MENU_MAP_H - 13, GOLD)
    else:
        draw_text("ENTER save", MENU_STAT_X, MENU_MAP_Y + MENU_MAP_H - 26, GREEN_1)
        draw_text("and quit", MENU_STAT_X, MENU_MAP_Y + MENU_MAP_H - 13, GREEN_1)


def draw_pack_tab(game):
    pack = game.player.pack
    for slot in range(PACK_MAX_SLOTS):
        x = PACK_GRID_X + (slot % PACK_COLS) * PACK_SLOT
        y = PACK_GRID_Y + (slot // PACK_COLS) * PACK_SLOT
        if slot >= pack.slots:
            screen.pen = PACK_LOCKED
            screen.shape(shape.rectangle(x, y, PACK_BOX, PACK_BOX).stroke(1))
            continue

        selected = slot == pack.cursor
        screen.pen = GREEN_6 if selected else GRAY_6
        screen.rectangle(x, y, PACK_BOX, PACK_BOX)
        screen.pen = GREEN_2 if selected else GRAY_4
        screen.shape(shape.rectangle(x, y, PACK_BOX, PACK_BOX).stroke(2 if selected else 1))
        if slot >= len(pack.items):
            continue

        item = pack.items[slot]
        if item.kind == "scroll":
            glyph = SCROLLS[item.effect]["char"] if item.effect in pack.identified else "s"
        else:
            glyph = ITEMS[item.kind]["char"]
        glyph_w, glyph_h = screen.measure_text(glyph)
        if item.equipped:
            screen.pen = GOLD
        else:
            screen.pen = GREEN_1 if selected else GRAY_1
        screen.text(glyph, x + (PACK_BOX - glyph_w) / 2, y + (PACK_BOX - glyph_h) / 2)

    item = pack.selected()
    if item is None:
        draw_centered("Pack is empty" if len(pack.items) == 0 else "Empty slot", PACK_NAME_Y, GRAY_3)
        return

    draw_centered(pack.name(item), PACK_NAME_Y, GRAY_1)
    effect = item_effect(pack, item, game.level)
    if effect:
        draw_centered(effect, PACK_EFFECT_Y, GREEN_2)
    if item.kind == "bow":
        action = "ENTER stow" if item.equipped else "ENTER equip"
    elif item.kind == "ring":
        action = "ENTER remove" if item.equipped else "ENTER wear"
    else:
        action = ITEMS[item.kind]["action"]
    draw_centered(action + "   BACK drop", PACK_HINT_Y, GREEN_3)


def draw_menu(game, menu):
    on_map = menu.tab == "map"
    top = 0 if on_map else PACK_PANEL_Y
    height = HEIGHT if on_map else PACK_PANEL_H
    screen.pen = PACK_BACKDROP
    screen.rectangle(0, top, WIDTH, height)
    screen.pen = GREEN_6
    screen.shape(shape.rectangle(1, top + 1, WIDTH - 2, height - 2).stroke(1))

    widths = [screen.measure_text(label)[0] for _key, label in MENU_TABS]
    x = (WIDTH - sum(widths) - MENU_TAB_GAP * (len(MENU_TABS) - 1)) / 2
    for index, (key, label) in enumerate(MENU_TABS):
        selected = key == menu.tab
        draw_text(label, x, PACK_TITLE_Y, GREEN_1 if selected else GRAY_4)
        if selected:
            screen.pen = GREEN_2
            screen.rectangle(x, PACK_TITLE_Y + MENU_TAB_RULE, widths[index], 1)
        x += widths[index] + MENU_TAB_GAP

    close_width, _ = screen.measure_text("HOME close")
    draw_text("HOME close", WIDTH - close_width - 6, PACK_TITLE_Y, GRAY_4)
    draw_text("DOWN pack" if on_map else "UP map & save", 6, PACK_TITLE_Y, GRAY_4)

    if on_map:
        draw_map_tab(game, menu)
    else:
        draw_pack_tab(game)


def draw_game(game, menu):
    screen.pen = BLACK
    screen.clear()
    screen.font = small_font

    draw_header(game, menu)

    screen.pen = BLACK
    screen.rectangle(0, MAP_Y - 4, WIDTH, MAP_STRIP_H + 6)
    draw_map(game.area, game.player)

    lines = game.log.lines
    for index, message in enumerate(lines):
        screen.pen = GRAY_2 if index == len(lines) - 1 else GRAY_4
        screen.text(message, rect(4, LOG_Y + index * 12, LOG_W, 14), overflow=ELLIPSES)

    if menu.open:
        draw_menu(game, menu)


def draw_dead(game, menu):
    draw_game(game, menu)
    screen.pen = BLACK
    screen.rectangle(0, PACK_PANEL_Y, WIDTH, PACK_PANEL_H)

    draw_doubled("YOU DIED", large_font, DEAD_TITLE_Y, HURT)
    draw_doubled("ENTER to explore again", small_font, DEAD_HINT_Y, GREEN_1)

    screen.pen = HURT
    screen.shape(shape.rectangle(1, PACK_PANEL_Y + 1, WIDTH - 2, PACK_PANEL_H - 2).stroke(1))
    screen.font = small_font


def draw_escaped(game, menu):
    draw_game(game, menu)
    screen.pen = BLACK
    screen.rectangle(0, PACK_PANEL_Y, WIDTH, PACK_PANEL_H)

    draw_doubled("You escape the ruins", header_font, ESCAPE_TITLE_Y, GREEN_1)

    tally = (
        ("enemies killed", str(game.kills), GRAY_4, GREEN_2),
        ("items found", str(game.items_found), GRAY_4, GREEN_2),
        ("items used", str(game.items_used), GRAY_4, GREEN_2),
        ("gold found", str(game.gold_found), GRAY_4, GOLD),
        ("explored", str(game.explored_percent()) + "%", GRAY_4, GREEN_2),
        ("score", str(game.score()), GREEN_1, GREEN_1),
    )
    y = ESCAPE_TALLY_Y
    for label, value, label_pen, value_pen in tally:
        draw_text(label, ESCAPE_TALLY_X, y, label_pen)
        value_width, _ = screen.measure_text(value)
        draw_text(value, ESCAPE_TALLY_X + ESCAPE_TALLY_W - value_width, y, value_pen)
        y += ESCAPE_TALLY_PITCH

    draw_centered("ENTER to play again", ESCAPE_HINT_Y, GREEN_3)

    screen.pen = GREEN_4
    screen.shape(shape.rectangle(1, PACK_PANEL_Y + 1, WIDTH - 2, PACK_PANEL_H - 2).stroke(1))


def draw_intro(filter_index, blink, resume):
    screen.pen = BLACK
    screen.clear()
    title_w = INTRO_TITLE.width * INTRO_TITLE_SCALE
    title_h = INTRO_TITLE.height * INTRO_TITLE_SCALE
    screen.blit(INTRO_TITLE, rect((WIDTH - title_w) // 2, INTRO_TITLE_Y, title_w, title_h))
    screen.blit(INTRO_SCENE, rect(0, INTRO_SCENE_Y, INTRO_SCENE.width * VIEW_SCALE, INTRO_SCENE.height * VIEW_SCALE))

    screen.font = header_font
    widths = [screen.measure_text(name)[0] for name in FILTERS]
    x = (WIDTH - sum(widths) - INTRO_FILTER_GAP * (len(FILTERS) - 1)) / 2
    _w, text_h = screen.measure_text("H")
    draw_text("<", x - INTRO_FILTER_GAP, INTRO_FILTER_Y, GRAY_4)
    for index, name in enumerate(FILTERS):
        width = widths[index]
        selected = index == filter_index
        if selected:
            box = (x - INTRO_FILTER_PAD, INTRO_FILTER_Y - 2, width + INTRO_FILTER_PAD * 2, text_h + 2)
            screen.pen = GREEN_6
            screen.rectangle(*box)
            screen.pen = GREEN_4
            screen.shape(shape.rectangle(*box).stroke(1))
        draw_text(name, x, INTRO_FILTER_Y, GREEN_1 if selected else GRAY_4)
        x += width + INTRO_FILTER_GAP
    draw_text(">", x - INTRO_FILTER_GAP + 10, INTRO_FILTER_Y, GRAY_4)

    screen.font = small_font
    draw_centered("ARROWS move   ENTER wait or descend   HOME pack", INTRO_HELP_Y, GRAY_3)
    draw_centered("hold HOME to quit", INTRO_QUIT_Y, GRAY_4)
    if resume is None:
        if blink:
            draw_centered("ENTER to begin", INTRO_PROMPT_Y, GREEN_1)
        return
    for index, (label, chosen) in enumerate((("RESUME", resume), ("NEW GAME", not resume))):
        draw_centered("> " + label + " <" if chosen else label, INTRO_OPTION_Y + index * INTRO_OPTION_GAP, GREEN_1 if chosen else GRAY_4)


def apply_filter(filter_index):
    choice = FILTERS[filter_index]
    if choice == "CRT":
        screen.crt(CRT_SPACING, CRT_DARKNESS)
    elif choice == "PHOSPHOR":
        screen.pen = PHOSPHOR_BRUSH
        screen.rectangle(0, 0, WIDTH, HEIGHT)
        screen.crt(CRT_SPACING, PHOSPHOR_DARKNESS)
