"""Pig vs Goose: a tiny, splashy artillery duel."""

import math
import os
import sys

APP_DIR = "/system/apps/pig_vs_goose"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

from game import Game, WIDTH, HEIGHT, FLOOR, BLAST_RADIUS, DRYER_DURATION, soak_rgb

badge.mode(HIRES | VSYNC)
screen.font = font.nope
screen.antialias = image.OFF
screen.fill_rule = image.EVEN_ODD

SKY = color.rgb(176, 228, 230)
INK = color.rgb(36, 47, 61)
WHITE = color.rgb(255, 252, 235)
PINK = color.rgb(247, 146, 171)
BLUE = color.rgb(45, 154, 216)
GRASS = color.rgb(101, 153, 82)
DIRT = color.rgb(151, 100, 67)
ORANGE = color.rgb(249, 167, 65)
RED = color.rgb(221, 55, 59)
YELLOW = color.rgb(250, 225, 75)
terrain_image = image(WIDTH, HEIGHT)
terrain_revision = -1
game = None
mode = 0
MODES = ("VS COMPUTER", "PASS & PLAY", "BADGE VS BADGE")
multiplayer = None
link_error = ""
linked_round = 0
paused = False
clock = 0.0
names = ("PIG", "GOOSE")


def box(x, y, w, h, pen):
    screen.pen = pen
    screen.rectangle(int(x), int(y), int(w), int(h))


def circle(x, y, radius, pen):
    screen.pen = pen
    screen.shape(shape.circle(x, y, radius))


def text(label, x, y, pen=INK):
    screen.pen = pen
    screen.text(label, x, y)


def center(label, y, pen=INK):
    w, _ = screen.measure_text(label)
    text(label, (screen.width - w) / 2, y, pen)


def character(index, x, foot, scale=1, wet=0, tilt=0, wheel=0, cart=False, blow=0):
    # Pixel-art silhouettes drawn from primitives stay crisp at badge scale.
    cosine, sine = math.cos(tilt), math.sin(tilt)

    def point(dx, dy):
        return vec2(x + (dx * cosine - dy * sine) * scale,
                    foot + (dx * sine + dy * cosine) * scale)

    def panel(dx, dy, w, h, pen):
        screen.pen = pen
        screen.shape(shape.custom([point(dx, dy), point(dx + w, dy),
                                   point(dx + w, dy + h), point(dx, dy + h)]))

    if cart:
        panel(-5, -5, 10, 3.5, INK)
        panel(-4.5, -4.8, 9, 2.5, RED)
        for wx in (-3, 3):
            position = point(wx, -1.5)
            circle(position.x, position.y, 1.6 * scale, INK)
            circle(position.x, position.y, 0.9 * scale, WHITE)
            screen.pen = INK
            screen.line(position.x, position.y,
                        position.x + math.cos(wheel + tilt) * 1.3 * scale,
                        position.y + math.sin(wheel + tilt) * 1.3 * scale)

    def r(dx, dy, w, h, pen):
        if cart:
            dx = dx * 0.85 + blow * (-dy / 14)
            dy = dy * 0.85 - 4.5
            w, h = w * 0.85, h * 0.85
        panel(dx, dy, w, h, pen)

    if index == 0:
        r(-6, -9, 12, 7, INK)
        r(-5, -10, 10, 8, PINK)
        r(-5, -13, 3, 4, PINK)
        r(2, -13, 3, 4, PINK)
        r(3, -7, 5, 4, color.rgb(234, 107, 145))
        r(5, -6, 1, 1, INK)
        r(3, -9, 1, 2, INK)
        r(-4, -2, 2, 2, INK)
        r(2, -2, 2, 2, INK)
        r(-8, -7, 2, 3, PINK)
    else:
        r(-6, -7, 10, 5, INK)
        r(-6, -8, 10, 5, WHITE)
        r(-5, -12, 4, 8, WHITE)
        r(-6, -14, 6, 5, WHITE)
        r(-9, -11, 4, 2, ORANGE)
        r(-5, -12, 1, 1, INK)
        r(3, -10, 3, 4, WHITE)
        r(-4, -2, 2, 2, ORANGE)
        r(1, -2, 2, 2, ORANGE)
    if wet:
        r(-3, -5, 3, 2, BLUE)


def rebuild_terrain():
    global terrain_revision
    terrain_image.pen = SKY
    terrain_image.clear()
    for x in range(WIDTH):
        y = 0
        while y < FLOOR:
            if not game.terrain[y][x]:
                y += 1
                continue
            start = y
            while y < FLOOR and game.terrain[y][x]:
                y += 1
            terrain_image.pen = DIRT
            terrain_image.rectangle(x, start, 1, y - start)
            terrain_image.pen = GRASS
            terrain_image.rectangle(x, start, 1, min(2, y - start))
    terrain_revision = game.revision


def landscape():
    if terrain_revision != game.revision:
        rebuild_terrain()
    screen.blit(terrain_image, rect(0, 0, screen.width, screen.height))
    sx, sy = screen.width / WIDTH, screen.height / HEIGHT
    for x, y in ((18, 30), (82, 22), (137, 34)):
        circle(x * sx, y * sy, 5 * sx, WHITE)
        circle((x + 5) * sx, (y - 2) * sy, 6 * sx, WHITE)
        circle((x + 10) * sx, y * sy, 4 * sx, WHITE)
    box(0, FLOOR * sy, screen.width, (HEIGHT - FLOOR) * sy, BLUE)
    for x in range(0, WIDTH, 16):
        box((x + int(clock * 5) % 8) * sx, (FLOOR + 2) * sy, 7 * sx, sy, WHITE)
    for i, player in enumerate(game.players):
        blowing = (game.phase == "dryer" and game.active == i
                   and 0.8 < game.dryer_time < 3.0)
        blow = math.sin(game.dryer_time * 39) * 3 if blowing else 0
        character(i, player["x"] * sx, player["y"] * sy, sx, player["soak"] > 30,
                  player["tilt"], player["wheel"], True, blow)
    if game.phase in ("move", "aim", "think"):
        player = game.players[game.active]
        x, y = player["x"] * sx, (player["y"] - 19) * sy
        circle(x, y + math.sin(clock * 5) * 2, 2.5 * sx, PINK if game.active == 0 else INK)
    for x, y in game.trail[::3]:
        circle(x * sx, y * sy, 0.6 * sx, WHITE)
    if game.projectile:
        x, y = game.projectile[:2]
        circle(x * sx, y * sy, 2.5 * sx, BLUE)
        circle((x - 0.7) * sx, (y - 0.8) * sy, 0.7 * sx, WHITE)
        if y < 15:
            text("^", max(4, min(screen.width - 12, x * sx)), 34)
    if game.phase == "splash":
        x, y = game.splash
        progress = 1 - max(0, game.timer) / 0.55
        radius = BLAST_RADIUS * min(1, progress * 3)
        screen.pen = BLUE
        screen.shape(shape.circle(x * sx, y * sy, radius * sx).stroke(2))
        for i in range(12):
            angle = i * math.pi / 6
            reach = radius + progress * 9
            circle((x + math.cos(angle) * reach) * sx,
                   (y + math.sin(angle) * reach + progress * progress * 9) * sy,
                   max(0.6, (1 - progress) * 2) * sx, BLUE)
        text("SPLASH!", max(3, min(screen.width - 66, x * sx - 25)),
             max(34, y * sy - 45), BLUE)
    if game.butterfly:
        butterfly()
    if game.phase == "dryer":
        hairdryer()


def butterfly():
    b = game.butterfly
    x = b["x"] * screen.width / WIDTH
    y = b["y"] * screen.height / HEIGHT
    spread = 1.5 + abs(math.sin(b["time"] * 15)) * 4
    for direction in (-1, 1):
        circle(x + direction * spread, y - 2, spread, ORANGE)
        circle(x + direction * spread, y + 3, spread * 0.75, PINK)
        circle(x + direction * spread, y - 2, spread * 0.45, YELLOW)
    box(x - 1, y - 4, 2, 10, INK)
    screen.pen = INK
    screen.line(x, y - 3, x - 3, y - 7)
    screen.line(x, y - 3, x + 3, y - 7)


def hairdryer():
    t = game.dryer_time
    player = game.players[game.active]
    px = player["x"] * screen.width / WIDTH
    py = player["y"] * screen.height / HEIGHT
    x = max(49, min(screen.width - 63, px))
    target_y = max(45, py - 100)
    descent = min(1, t / 0.8)
    ascent = max(0, (t - 3) / (DRYER_DURATION - 3))
    y = -100 + (target_y + 100) * (descent - ascent)
    shake = math.sin(t * 45) * 2 if 0.8 < t < 3 else 0
    x += shake
    # An absurdly oversized salon dryer, nozzle down, with a dangling power cord.
    screen.pen = INK
    screen.line(x + 48, y + 46, x + 55, y + 65)
    screen.line(x + 55, y + 65, x + 42, y + 75)
    screen.line(x + 42, y + 75, x + 56, y + 87)
    box(x + 29, y - 3, 22, 56, INK)
    box(x + 33, y, 14, 48, PINK)
    box(x + 35, y + 17, 7, 9, INK)
    circle(x - 18, y, 28, INK)
    box(x - 18, y - 28, 53, 56, INK)
    circle(x - 18, y, 24, RED)
    box(x - 18, y - 24, 49, 48, RED)
    box(x - 13, y + 19, 32, 18, INK)
    box(x - 9, y + 22, 24, 12, ORANGE)
    for vent in range(4):
        box(x - 29 + vent * 8, y - 15, 3, 24, INK)
    text("TURBO", x - 11, y - 21, WHITE)
    if 0.8 < t < 3:
        for stream in range(7):
            start_x = x - 10 + stream * 4
            screen.pen = WHITE if stream % 2 else YELLOW
            for segment in range(5):
                u = segment / 5
                v = (segment + 1) / 5
                wiggle = math.sin(t * 22 + stream + segment) * 4
                ax = start_x * (1 - u) + (px + (stream - 3) * 4) * u
                bx = start_x * (1 - v) + (px + (stream - 3) * 4) * v
                ay = (y + 38) * (1 - u) + (py - 12) * u
                by = (y + 38) * (1 - v) + (py - 12) * v
                screen.line(ax + wiggle, ay, bx - wiggle, by)
        for i in range(6):
            progress = (t * 2 + i / 6) % 1
            circle(px + (i - 3) * 6 + math.sin(t * 17 + i) * 4,
                   py - 12 - progress * 24, 1.5 * (1 - progress), BLUE)
    box(46, 31, screen.width - 92, 15, INK)
    center("BUTTERFLY BONUS! -25 SOAK", 32, YELLOW)
    if t >= 1.6:
        box(86, screen.height - 47, screen.width - 172, 16, INK)
        center("%d%% -> %d%%" % (game.dryer_before, game.dryer_after),
               screen.height - 46, WHITE)


def hud():
    box(0, 0, screen.width, 30, INK)
    for i, x in enumerate((7, screen.width - 103)):
        player = game.players[i]
        name = names[i]
        if multiplayer and multiplayer.local_player == i:
            name = "*" + name
        text("%s %d%%" % (name, player["soak"]), x, 2, WHITE)
        box(x, 19, 94, 4, SKY)
        box(x, 19, max(0, int(94 * player["soak"] / 100)), 4,
            color.rgb(*soak_rgb(player["soak"])))
    label = "WIND %s%d" % (">" if game.wind >= 0 else "<", abs(game.wind))
    w, _ = screen.measure_text(label)
    text(label, (screen.width - w) / 2, 8, WHITE)
    box(0, screen.height - 27, screen.width, 27, INK)
    player = game.players[game.active]
    if multiplayer and game.phase in ("move", "aim") and game.active != multiplayer.local_player:
        center("YOU: %s   Waiting for %s" %
               (names[multiplayer.local_player], names[game.active]),
               screen.height - 26, WHITE)
        center("Opponent's turn   MENU pause", screen.height - 13, WHITE)
        return
    if game.phase == "move":
        center("%s DRIVE  %d left" % (names[game.active], math.ceil(game.walk)),
               screen.height - 26, WHITE)
        center("L/R drive  SELECT aim" if game.carts_still() else
               "Rolling downhill! Hold on...", screen.height - 13, WHITE)
    elif game.phase == "aim":
        center("%s  ANGLE %d  POWER %d" %
               (names[game.active], player["angle"], player["power"]),
               screen.height - 26, WHITE)
        center("L/R angle  U/D power  SELECT throw", screen.height - 13, WHITE)
    else:
        label = {"think": "GOOSE is plotting...",
                 "flight": "Water balloon away!",
                 "splash": "A proper soaking!",
                 "dryer": "FWOOSH! Emergency fluff cycle!",
                 "settle": "Mind the drop!",
                 "over": "SELECT rematch   BACK title"}[game.phase]
        center(label, screen.height - 21, WHITE)


def aiming():
    player = game.players[game.active]
    sx, sy = screen.width / WIDTH, screen.height / HEIGHT
    ball = game.launch_values(player["angle"], player["power"])
    for _ in range(9):
        for _ in range(4):
            game.advance_ball(ball, 1 / 120)
        if game.impact(ball):
            break
        circle(ball[0] * sx, ball[1] * sy, 0.7 * sx, INK)


def start():
    global game, terrain_revision, paused
    game = Game(mode == 0)
    terrain_revision = -1
    paused = False


def start_link():
    global multiplayer, link_error, game, linked_round
    try:
        from badgeware import link as badgelink
    except ImportError as error:
        link_error = "Badge link requires physical firmware"
        print("Pig vs Goose:", link_error, error)
        return
    from multiplayer import Multiplayer
    try:
        connection = badgelink.Link("pig_vs_goose")
    except (OSError, RuntimeError) as error:
        link_error = "Cannot start badge link"
        print("Pig vs Goose:", link_error, error)
        return
    multiplayer = Multiplayer(connection, badgelink.Proximity(connection))
    game = None
    linked_round = 0
    link_error = ""


def stop_link():
    global multiplayer, game, paused
    if multiplayer:
        multiplayer.send(b"X")
        multiplayer.close()
    multiplayer = None
    game = None
    paused = False


def link_lobby():
    box(0, 0, screen.width, screen.height, SKY)
    center("BADGE vs BADGE", 22)
    if multiplayer.status == "error":
        center("LINK INTERRUPTED", 67)
        center(multiplayer.message, 93)
        center("BACK: return and pair again", 180)
    elif multiplayer.status == "search":
        center("Bring two badges close together", 64)
        center("Open this mode on both badges", 86)
        center("Finding another Pig vs Goose...", 119)
        center("BACK cancel", 190)
    elif multiplayer.status == "offer":
        partner = multiplayer.link.partner
        center("Opponent found!", 57)
        if partner:
            center(str(partner.name)[:28], 79)
        center("You will be %s" % names[multiplayer.local_player], 108)
        center("Waiting for their SELECT..." if multiplayer.accepted
               else "SELECT: ready to play", 142)
        center("Both players must accept", 165)
        center("BACK cancel", 198)
    else:
        center("Syncing landscape...", 100)
        center("BACK cancel", 190)


def linked_frame(dt):
    global game, paused, terrain_revision, linked_round
    if badge.pressed(BUTTON_BACK) and (
            multiplayer.status != "play" or multiplayer.paused
            or (game and game.phase == "over")):
        stop_link()
        title()
        return
    horizontal = int(bool(badge.held(BUTTON_RIGHT))) - int(bool(badge.held(BUTTON_LEFT)))
    vertical = int(bool(badge.held(BUTTON_UP))) - int(bool(badge.held(BUTTON_DOWN)))
    buttons = (int(bool(badge.pressed(BUTTON_SELECT))) |
               (int(bool(badge.pressed(BUTTON_BACK))) << 1) |
               (int(bool(badge.pressed(BUTTON_MENU))) << 2))
    multiplayer.update(badge.ticks, dt, horizontal, vertical, buttons)
    game = multiplayer.game
    paused = multiplayer.paused
    if multiplayer.status != "play" or game is None:
        link_lobby()
        return
    if linked_round != multiplayer.round:
        terrain_revision = -1
        linked_round = multiplayer.round
    landscape()
    if game.phase == "aim":
        aiming()
    hud()
    if multiplayer.message:
        box(0, screen.height - 14, screen.width, 14, INK)
        center(multiplayer.message, screen.height - 13, WHITE)
    if paused:
        help_panel()
        center("Both badges paused; BACK leaves", 201, INK)
    elif game.phase == "over":
        result_panel()
        box(0, screen.height - 27, screen.width, 27, INK)
        voted = multiplayer.rematch[multiplayer.local_player]
        center("Waiting for opponent's rematch" if voted else
               "SELECT rematch   BACK leave", screen.height - 21, WHITE)


def title():
    box(0, 0, screen.width, screen.height, SKY)
    circle(screen.width - 30, 44, 24, WHITE)
    box(0, screen.height - 32, screen.width, 32, GRASS)
    center("PIG vs GOOSE", 22)
    center("THE GREAT WATER-BALLOON DUEL", 42)
    character(0, screen.width * 0.25, 117, 3)
    character(1, screen.width * 0.75, 117, 3)
    circle(screen.width / 2, 80 + math.sin(clock * 3) * 6, 7, BLUE)
    center("< %s >" % MODES[mode], 139)
    center("Left / Right choose   SELECT start", 158)
    center("Roll. Aim. Splash. Catch a butterfly!", 187)
    center("MENU: controls / pause    HOME: exit", 218, WHITE)
    if link_error:
        box(0, 175, screen.width, 32, INK)
        center(link_error, 178, WHITE)
        center("Simulator: solo / pass & play only", 192, WHITE)


def help_panel():
    box(13, 37, screen.width - 26, 160, INK)
    center("SPLASH SCHOOL", 46, WHITE)
    center("Drive: Left / Right, then Select", 65, WHITE)
    center("Aim: L/R angle, Up/Down power", 84, WHITE)
    center("Select throws. Back returns to drive.", 103, WHITE)
    center("Hit butterfly: dryer removes 25 soak", 122, WHITE)
    center("Carts roll! Wait for them to stop.", 141, WHITE)
    center("100% soaked loses. Falls soak too!", 160, WHITE)
    center("SELECT resume   BACK title", 176, WHITE)


def update():
    global game, mode, paused, clock, link_error
    dt = max(0, min(badge.ticks_delta / 1000, 0.1))
    if multiplayer:
        linked_frame(dt)
        if not paused:
            clock += dt
        return
    if badge.pressed(BUTTON_MENU):
        paused = not paused
    if paused:
        if game:
            landscape()
            hud()
        else:
            title()
        help_panel()
        if badge.pressed(BUTTON_SELECT):
            paused = False
        elif badge.pressed(BUTTON_BACK):
            game = None
            paused = False
        return
    clock += dt
    if game is None:
        if badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_RIGHT):
            mode = (mode + (1 if badge.pressed(BUTTON_RIGHT) else -1)) % len(MODES)
            link_error = ""
        title()
        if badge.pressed(BUTTON_SELECT):
            if mode == 2:
                start_link()
            else:
                start()
        return
    if game.phase == "over":
        if badge.pressed(BUTTON_SELECT):
            start()
        elif badge.pressed(BUTTON_BACK):
            game = None
            return
    elif not (game.computer and game.active == 1):
        if game.phase == "move":
            direction = int(bool(badge.held(BUTTON_RIGHT))) - int(bool(badge.held(BUTTON_LEFT)))
            game.move(direction * 12 * dt)
            if badge.pressed(BUTTON_SELECT):
                game.aim()
        elif game.phase == "aim":
            player = game.players[game.active]
            direction = int(bool(badge.held(BUTTON_RIGHT))) - int(bool(badge.held(BUTTON_LEFT)))
            power = int(bool(badge.held(BUTTON_UP))) - int(bool(badge.held(BUTTON_DOWN)))
            player["angle"] = max(10, min(170, player["angle"] + direction * 38 * dt))
            player["power"] = max(20, min(100, player["power"] + power * 35 * dt))
            if badge.pressed(BUTTON_BACK):
                game.phase = "move"
            elif badge.pressed(BUTTON_SELECT):
                game.fire()
    game.update(dt)
    landscape()
    if game.phase == "aim":
        aiming()
    hud()
    if game.phase == "over":
        result_panel()


def result_panel():
    box(20, 66, screen.width - 40, 86, INK)
    center("BOTH SOAKED!" if game.winner == -1 else
           "%s WINS!" % names[game.winner], 76, WHITE)
    for i, line in enumerate(game.result_lines()):
        center(line, 102 + i * 19, WHITE)


def on_exit():
    if multiplayer:
        multiplayer.close()


run(update)
