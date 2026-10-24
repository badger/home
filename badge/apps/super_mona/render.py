"""Drawing for Super Mona (LORES, 160x120).

The whole stage is pre-rendered once into an offscreen image. Each frame blits
a 160x120 window of it, then overlays the moving sprites and the HUD.
"""

import math

from game import (
    TILE, ROWS, VIEW_W, VIEW_H, CHARACTERS, ITEM_NAMES, EMPTY, POLE,
)

SKY = {
    "day": color.rgb(92, 148, 252),
    "cave": color.rgb(0, 0, 0),
    "dusk": color.rgb(52, 44, 110),
}
BLACK = color.rgb(0, 0, 0)
WHITE = color.rgb(255, 255, 255)
GOLD = color.rgb(255, 214, 74)
DIM = color.rgb(0, 0, 0, 170)
PANEL = color.rgb(16, 12, 40, 225)
MAP_SOLID = color.rgb(200, 120, 60)
MAP_PLAYER = color.rgb(255, 80, 200)
MAP_FLAG = color.rgb(80, 255, 120)

HUD_FONT = font.sins
TITLE_FONT = font.absolute

_tiles = image.load("assets/tiles.png").spritesheet(16, 4)
_players = image.load("assets/players.png").spritesheet(8, 4)
_mobs = image.load("assets/mobs.png").spritesheet(8, 2)
TILES = [_tiles.sprite(i % 16, i // 16) for i in range(64)]
PLAYERS = [[_players.sprite(c, r) for c in range(8)] for r in range(4)]
MOBS = [_mobs.sprite(i % 8, i // 8) for i in range(16)]

STAND, WALK1, WALK2, JUMP, SKID, CROUCH, DEAD, CLIMB = range(8)
ITEM_SPRITES = {"chip": 7, "sparkle": 12, "1up": 11}


def text(msg, x, y, pen=WHITE, shadow=True):
    if shadow:
        screen.pen = BLACK
        screen.text(msg, x + 1, y + 1)
    screen.pen = pen
    screen.text(msg, x, y)


def centre(msg, y, pen=WHITE, fnt=None):
    screen.font = fnt or HUD_FONT
    w, _ = screen.measure_text(msg)
    text(msg, (VIEW_W - w) / 2, y, pen)


def hero_sprite(character, big, col=STAND):
    row = (2 if character == "luna" else 0) + (1 if big else 0)
    return PLAYERS[row][col]


class Renderer:
    def __init__(self, level):
        self.level = level
        self.sky = SKY.get(level.theme, SKY["day"])
        self.canvas = image(level.width * TILE, VIEW_H)
        self.canvas.antialias = image.OFF
        self.canvas.pen = self.sky
        self.canvas.rectangle(0, 0, self.canvas.width, VIEW_H)
        for index in range(level.width * ROWS):
            self.draw_cell(index, clear=False)
        del level.dirty[:]
        self.minimap = None

    def draw_cell(self, index, clear=True):
        level = self.level
        x = (index % level.width) * TILE
        y = (index // level.width) * TILE
        c = self.canvas
        if clear:
            c.pen = self.sky
            c.rectangle(x, y, TILE, TILE)
        decor = level.decor.get(index)
        if decor is not None:
            c.blit(TILES[decor], vec2(x, y))
        tile = level.tiles[index]
        if tile != EMPTY:
            c.blit(TILES[tile], vec2(x, y))

    def refresh(self):
        dirty = self.level.dirty
        if dirty:
            for index in dirty:
                self.draw_cell(index)
            del dirty[:]
            self.minimap = None

    # World ---------------------------------------------------------------
    def draw(self, world, t):
        self.refresh()
        cam = int(world.cam_x)
        screen.blit(self.canvas.window(cam, 0, VIEW_W, VIEW_H), vec2(0, 0))
        self.draw_bumps(world, cam)
        self.draw_stars(world, cam, t)
        self.draw_items(world, cam)
        self.draw_flag(world, cam)
        self.draw_enemies(world, cam, t)
        self.draw_player(world, cam, t)
        self.draw_particles(world, cam, t)

    def draw_bumps(self, world, cam):
        for tx, ty, tile, age in world.bumps:
            x = tx * TILE - cam
            if x < -TILE or x > VIEW_W:
                continue
            y = ty * TILE
            lift = int(4 * math.sin(math.pi * min(age / 0.16, 1.0)))
            screen.pen = self.sky
            screen.rectangle(x, y, TILE, TILE)
            screen.blit(TILES[tile], vec2(x, y - lift))

    def draw_stars(self, world, cam, t):
        frame = MOBS[8 + int(t * 6) % 3]
        left = cam // TILE - 1
        right = left + VIEW_W // TILE + 2
        for tx, ty in world.level.stars:
            if left <= tx <= right:
                screen.blit(frame, vec2(tx * TILE - cam, ty * TILE))

    def draw_items(self, world, cam):
        for item in world.items:
            x = int(item.x) - cam
            if x < -TILE or x > VIEW_W:
                continue
            screen.blit(MOBS[ITEM_SPRITES.get(item.kind, 7)], vec2(x, int(item.y)))
            if item.emerge > 0:
                # Keep the item behind its block while it rises out.
                bx = int(item.x) - cam
                by = int(item.target_y) + TILE
                screen.blit(TILES[world.level.get(int(item.x) // TILE, by // TILE)], vec2(bx, by))

    def draw_flag(self, world, cam):
        fx = world.level.flag_x
        if fx is None or world.flag_y is None:
            return
        x = fx * TILE - 4 - cam
        if -TILE < x < VIEW_W:
            screen.blit(MOBS[14], vec2(x, int(world.flag_y)))

    def draw_enemies(self, world, cam, t):
        step = int(t * 6) % 2
        for e in world.enemies:
            if not e.active:
                continue
            x = int(e.x) - 1 - cam
            if x < -TILE or x > VIEW_W:
                continue
            y = int(e.y + e.h) - TILE
            flip = False
            if e.kind == "bug":
                index = 2 if e.state == "squashed" else step
            else:
                if e.state == "walk":
                    index = 3 + step
                    flip = e.vx > 0
                elif e.state == "shell" and e.timer > 4.0:
                    index = 5 + step
                else:
                    index = 5
            sprite = MOBS[index]
            if e.state == "dead":
                screen.blit(sprite, rect(x, y + TILE, TILE, -TILE))
            elif flip:
                screen.blit(sprite, rect(x + TILE, y, -TILE, TILE))
            else:
                screen.blit(sprite, vec2(x, y))

    def draw_player(self, world, cam, t):
        p = world.player
        state = world.state
        if state in ("tally", "clear") and world.level.castle_door and p.x >= world.level.castle_door - 4:
            return
        if p.invulnerable > 0 and int(t * 20) % 2:
            return
        if p.dead:
            col = DEAD
        elif state == "flag":
            col = CLIMB
        elif p.crouch:
            col = CROUCH
        elif not p.on_ground and state == "play":
            col = JUMP
        elif p.skidding:
            col = SKID
        elif abs(p.vx) > 1 or state == "castle":
            col = WALK1 if int(p.walk_phase / 6) % 2 else WALK2
        else:
            col = STAND
        character = p.character
        if p.sparkle > 0 and int(t * 12) % 2:
            character = "luna" if character == "mona" else "mona"
        sprite = hero_sprite(character, p.big, col)
        x = int(p.x) - 5 - cam
        y = int(p.y + p.h) - 16
        if p.facing < 0:
            screen.blit(sprite, rect(x + 16, y, -16, 16))
        else:
            screen.blit(sprite, vec2(x, y))

    def draw_particles(self, world, cam, t):
        screen.font = HUD_FONT
        for kind, x, y, vx, vy, age, data in world.particles:
            sx = int(x) - cam
            if kind == "score":
                text(str(data), sx, int(y), WHITE)
            elif kind == "debris":
                screen.blit(MOBS[13], vec2(sx, int(y)))
            elif kind == "star":
                screen.blit(MOBS[8 + int(t * 12) % 3], vec2(sx, int(y)))
            elif kind == "sparkle":
                screen.blit(MOBS[12], vec2(sx, int(y)))

    # HUD -----------------------------------------------------------------
    def draw_hud(self, world):
        s = world.session
        screen.font = HUD_FONT
        name = CHARACTERS[world.player.character]["name"]
        text("%s x%d" % (name, s.lives), 2, 0)
        screen.blit(MOBS[8], vec2(52, 2))
        text("x%02d" % s.stars, 61, 0, GOLD)
        text("%06d" % s.score, 84, 0)
        text("%3d" % int(world.time_left + 0.99), 138, 0)

    # Map page -------------------------------------------------------------
    def build_minimap(self):
        level = self.level
        mm = image(level.width, ROWS)
        mm.antialias = image.OFF
        mm.pen = self.sky
        mm.rectangle(0, 0, level.width, ROWS)
        mm.pen = MAP_SOLID
        for index in range(level.width * ROWS):
            tile = level.tiles[index]
            if tile != EMPTY and tile != POLE:
                mm.rectangle(index % level.width, index // level.width, 1, 1)
        self.minimap = mm

    def draw_map(self, world, x, y, w, h):
        if self.minimap is None:
            self.build_minimap()
        level = self.level
        screen.blit(self.minimap, rect(x, y, w, h))
        sx = w / level.width
        sy = h / ROWS
        screen.pen = WHITE
        screen.rectangle(x + int(world.cam_x / TILE * sx), y, 1, h)
        screen.rectangle(x + int((world.cam_x + VIEW_W) / TILE * sx), y, 1, h)
        if level.flag_x is not None:
            screen.pen = MAP_FLAG
            screen.rectangle(x + int(level.flag_x * sx), y + int(3 * sy), 2, int(9 * sy))
        p = world.player
        screen.pen = MAP_PLAYER
        screen.rectangle(x + int(p.x / TILE * sx) - 1, y + int(p.y / TILE * sy) - 1, 3, 3)


def item_sprite(kind):
    return MOBS[ITEM_SPRITES.get(kind, 7)]


def item_name(kind):
    return ITEM_NAMES.get(kind, kind.upper())
