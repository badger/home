"""Vector renderer for Octo Drive in LORES (160x120)."""

import math

import game

WIDTH = 160
HEIGHT = 120
HORIZON = 34
ROAD_BOTTOM = 119

BLACK = color.rgb(0, 0, 0)
WHITE = color.rgb(255, 255, 255)
GOLD = color.rgb(255, 214, 74)
SKY = color.rgb(76, 156, 224)
SKY_LOW = color.rgb(246, 166, 108)
GRASS_A = color.rgb(42, 142, 82)
GRASS_B = color.rgb(34, 116, 72)
ROAD_A = color.rgb(64, 68, 78)
ROAD_B = color.rgb(72, 76, 88)
CURB_RED = color.rgb(235, 72, 78)
ORANGE = color.rgb(255, 142, 48)
PANEL = color.rgb(12, 16, 34, 220)
DIM = color.rgb(0, 0, 0, 165)
CAR_COLOURS = (
    color.rgb(76, 190, 255),
    color.rgb(255, 96, 126),
    color.rgb(255, 208, 76),
    color.rgb(166, 112, 255),
)
PLAYER = color.rgb(242, 242, 248)
PLAYER_ACCENT = color.rgb(36, 36, 48)

HUD_FONT = font.sins
TITLE_FONT = font.absolute
_players = image.load("assets/players.png").spritesheet(8, 8)
MONA = _players.sprite(0, 0)


def text(msg, x, y, pen=WHITE, shadow=True, fnt=None):
    screen.font = fnt or HUD_FONT
    if shadow:
        screen.pen = BLACK
        screen.text(msg, x + 1, y + 1)
    screen.pen = pen
    screen.text(msg, x, y)


def centre(msg, y, pen=WHITE, fnt=None):
    screen.font = fnt or HUD_FONT
    width, _ = screen.measure_text(msg)
    text(msg, (WIDTH - width) / 2, y, pen, fnt=fnt)


def road_point(distance, ahead, depth):
    _, curve, _ = game.track_at(distance + ahead)
    _, near_curve, _ = game.track_at(distance)
    centre_x = WIDTH // 2 + int((curve * 0.78 + near_curve * 0.22) * ahead * 0.075)
    road_width = 7 + int(73 * depth * depth)
    return centre_x, road_width


def road_geometry(distance):
    bands = []
    span = ROAD_BOTTOM - HORIZON
    y = HORIZON
    while y <= ROAD_BOTTOM:
        depth = (y - HORIZON) / span
        ahead = game.VIEW_DISTANCE * (1.0 - depth) * (1.0 - depth)
        centre_x, road_width = road_point(distance, ahead, depth)
        bands.append((y, centre_x, road_width, ahead, depth))
        y += 3
    return bands


class Renderer:
    def draw_attract(self, t):
        self.draw_scene(t * 92.0, 0.0, 92.0, (), (), t)

    def draw(self, world, t):
        self.draw_scene(world.distance, world.lane, world.speed, world.traffic, world.hazards, t)

    def draw_scene(self, distance, lane, speed, traffic, hazards, t):
        screen.pen = SKY
        screen.clear()
        screen.pen = SKY_LOW
        screen.rectangle(0, HORIZON - 7, WIDTH, 12)
        self.draw_scenery(distance)
        bands = road_geometry(distance)
        for index, (y, centre_x, road_width, ahead, depth) in enumerate(bands):
            stripe = int((distance + ahead) / 45) & 1
            screen.pen = GRASS_A if stripe else GRASS_B
            screen.rectangle(0, y, WIDTH, 3)
            screen.pen = CURB_RED if (stripe + index) & 1 else WHITE
            curb = max(1, int(road_width * 0.08))
            screen.rectangle(centre_x - road_width - curb, y, curb, 3)
            screen.rectangle(centre_x + road_width, y, curb, 3)
            screen.pen = ROAD_A if stripe else ROAD_B
            screen.rectangle(centre_x - road_width, y, road_width * 2, 3)
            if road_width > 14 and int((distance + ahead) / 28) & 1:
                mark = max(1, int(depth * 2))
                screen.pen = WHITE
                screen.rectangle(centre_x - mark // 2, y, mark, 3)
        self.draw_hazards(distance, hazards)
        self.draw_traffic(distance, traffic)
        self.draw_player(lane, speed, t)

    def draw_scenery(self, distance):
        screen.pen = color.rgb(255, 224, 112)
        screen.rectangle(124, 14, 13, 13)
        shift = int(distance / 24) % 38
        screen.pen = color.rgb(54, 94, 126)
        for x in range(-40, 200, 38):
            peak = x - shift
            screen.rectangle(peak, 27, 30, 8)
            screen.rectangle(peak + 7, 23, 17, 5)
        screen.pen = color.rgb(26, 82, 68)
        for x in range(-20, 190, 24):
            tree = x - int(distance / 10) % 24
            screen.rectangle(tree, 29, 3, 8)
            screen.rectangle(tree - 3, 26, 9, 5)

    def draw_traffic(self, distance, traffic):
        visible = []
        for car in traffic:
            ahead = car.distance - distance
            if 8 < ahead < game.VIEW_DISTANCE:
                visible.append((ahead, car))
        visible.sort(reverse=True, key=lambda item: item[0])
        span = ROAD_BOTTOM - HORIZON
        for ahead, car in visible:
            depth = 1.0 - math.sqrt(ahead / game.VIEW_DISTANCE)
            y = HORIZON + int(depth * span)
            centre_x, road_width = road_point(distance, ahead, depth)
            size = max(2, 2 + int(depth * 8))
            x = centre_x + int(car.lane * road_width * 0.66) - size // 2
            screen.pen = BLACK
            screen.rectangle(x - 1, y, size + 2, max(2, size // 2 + 2))
            screen.pen = CAR_COLOURS[car.colour % len(CAR_COLOURS)]
            screen.rectangle(x, y - 1, size, max(2, size // 2 + 1))
            if size > 5:
                screen.pen = SKY
                screen.rectangle(x + 2, y, size - 4, 2)

    def draw_hazards(self, distance, hazards):
        visible = []
        for hazard in hazards:
            ahead = hazard.distance - distance
            if -4 < ahead < game.VIEW_DISTANCE:
                visible.append((ahead, hazard))
        visible.sort(reverse=True, key=lambda item: item[0])
        span = ROAD_BOTTOM - HORIZON
        for ahead, hazard in visible:
            depth = 1.0 - math.sqrt(max(0.0, ahead) / game.VIEW_DISTANCE)
            y = HORIZON + int(depth * span)
            centre_x, road_width = road_point(distance, max(0.0, ahead), depth)
            size = max(2, 2 + int(depth * 7))
            x = centre_x + int(hazard.lane * road_width * 0.66)
            if hazard.kind == "cone":
                screen.pen = ORANGE
                screen.rectangle(x - size // 2, y, size, max(1, size // 3))
                screen.rectangle(x - max(1, size // 4), y - max(1, size // 2), max(2, size // 2), max(1, size // 2))
                screen.pen = WHITE
                screen.rectangle(x - max(1, size // 3), y - 1, max(2, size * 2 // 3), 1)
            elif hazard.kind == "oil":
                screen.pen = BLACK
                screen.rectangle(x - size, y, size * 2, max(2, size // 2))
                screen.rectangle(x - size // 2, y - 1, size, max(1, size // 3))
            else:
                screen.pen = BLACK
                screen.rectangle(x - size, y, size * 2, max(2, size // 2 + 2))
                screen.pen = CURB_RED
                screen.rectangle(x - size + 1, y - 1, max(1, size - 1), max(2, size // 2))
                screen.pen = WHITE
                screen.rectangle(x, y - 1, max(1, size - 1), max(2, size // 2))

    def draw_player(self, lane, speed, t):
        x = WIDTH // 2 + int(lane * 35)
        bounce = 1 if speed > 120 and int(t * 18) & 1 else 0
        y = 98 + bounce
        screen.pen = BLACK
        screen.rectangle(x - 13, y + 11, 26, 5)
        screen.blit(MONA, vec2(x - 8, y - 10))
        screen.pen = PLAYER
        screen.rectangle(x - 11, y + 3, 22, 11)
        screen.rectangle(x - 7, y, 14, 6)
        screen.pen = PLAYER_ACCENT
        screen.rectangle(x - 10, y + 10, 5, 5)
        screen.rectangle(x + 5, y + 10, 5, 5)
        screen.pen = CURB_RED
        screen.rectangle(x - 8, y + 6, 16, 3)
        screen.pen = GOLD
        screen.rectangle(x - 7, y + 7, 3, 2)
        screen.rectangle(x + 4, y + 7, 3, 2)

    def draw_hud(self, world):
        text("%03d" % int(world.speed), 2, 0)
        text("KM/H", 28, 0, GOLD)
        text("%06d" % world.session.score, 67, 0)
        text("%02d" % int(world.time_left + 0.99), 142, 0, GOLD)
        text(world.section, 2, 11)
        checkpoint = min(world.next_checkpoint + 1, len(game.CHECKPOINTS))
        text("CP %d/%d" % (checkpoint, len(game.CHECKPOINTS)), 124, 11)

    def draw_progress(self, world, x=18, y=88, width=124):
        screen.pen = BLACK
        screen.rectangle(x - 1, y - 1, width + 2, 5)
        screen.pen = WHITE
        screen.rectangle(x, y, width, 3)
        screen.pen = GOLD
        screen.rectangle(x, y, int(width * world.progress), 3)
        for checkpoint in game.CHECKPOINTS[:-1]:
            cx = x + int(width * checkpoint / game.TRACK_LENGTH)
            screen.pen = BLACK
            screen.rectangle(cx, y - 2, 1, 7)
