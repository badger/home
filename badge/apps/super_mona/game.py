"""Platformer rules for Super Mona

This module is pure Python so it can run on the badge and in host tests. It
does not touch the screen or input hardware.
"""

TILE = 8
ROWS = 15
VIEW_W = 160
VIEW_H = 120

# Tile ids match the tile sheet built by tools/build_super_mona_assets.py.
EMPTY = 0
GROUND_TOP = 1
GROUND = 2
BRICK = 3
QUESTION = 4
USED = 5
HARD = 6
PIPE_TL = 7
PIPE_TR = 8
PIPE_L = 9
PIPE_R = 10
POLE = 11
POLE_TOP = 12
GIRDER = 13
CAVE_GROUND = 14
CAVE_BRICK = 15
HILL = 16
BUSH = 22
CLOUD = 25
CASTLE = 31

SOLID = bytearray(64)
for _tile in (GROUND_TOP, GROUND, BRICK, QUESTION, USED, HARD, PIPE_TL, PIPE_TR,
              PIPE_L, PIPE_R, GIRDER, CAVE_GROUND, CAVE_BRICK):
    SOLID[_tile] = 1
BREAKABLE = (BRICK, CAVE_BRICK)

CHARACTERS = {
    "mona": {
        "name": "MONA", "walk": 50, "run": 82, "accel": 190, "decel": 170,
        "skid": 420, "jump": 152, "run_jump": 168, "grav_hold": 300,
        "grav": 900, "about": "Balanced grip",
    },
    "luna": {
        "name": "LUNA", "walk": 50, "run": 78, "accel": 150, "decel": 100,
        "skid": 300, "jump": 166, "run_jump": 180, "grav_hold": 280,
        "grav": 820, "about": "High jumps, slippery",
    },
}
CHARACTER_ORDER = ("mona", "luna")
MAX_FALL = 210
SMALL_H = 11
BIG_H = 15
STOMP_BOUNCE = 120
SHELL_SPEED = 135
INVENTORY_SIZE = 3
ITEM_NAMES = {"chip": "POWER CHIP", "sparkle": "SPARKLE", "1up": "1-UP"}


def tile_of(value):
    return int(value // TILE)


def overlap(ax, ay, aw, ah, bx, by, bw, bh):
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


class Controls:
    def __init__(self):
        self.left = False
        self.right = False
        self.up = False
        self.down = False
        self.jump = False
        self.jump_pressed = False
        self.run = False


class Level:
    def __init__(self, name, width, theme="day", time=300, switch=False):
        self.name = name
        self.width = width
        self.theme = theme
        self.time = time
        self.switch = switch
        self.tiles = bytearray(width * ROWS)
        self.decor = {}
        self.contents = {}
        self.stars = set()
        self.spawns = []
        self.start = (2, 12)
        self.flag_x = None
        self.castle_door = None
        self.dirty = []

    # Building helpers used by levels.py ---------------------------------
    def index(self, tx, ty):
        return ty * self.width + tx

    def get(self, tx, ty):
        if tx < 0 or tx >= self.width:
            return HARD
        if ty < 0 or ty >= ROWS:
            return EMPTY
        return self.tiles[ty * self.width + tx]

    def set(self, tx, ty, tile):
        if 0 <= tx < self.width and 0 <= ty < ROWS:
            index = ty * self.width + tx
            if self.tiles[index] != tile:
                self.tiles[index] = tile
                self.dirty.append(index)

    def solid(self, tx, ty):
        return SOLID[self.get(tx, ty)]

    def ground(self, x0, x1, top=13):
        cave = self.theme == "cave"
        for x in range(x0, x1 + 1):
            for y in range(top, ROWS):
                if cave:
                    self.set(x, y, CAVE_GROUND)
                else:
                    self.set(x, y, GROUND_TOP if y == top else GROUND)

    def ceiling(self, x0, x1, rows=(2,)):
        for x in range(x0, x1 + 1):
            for y in rows:
                self.set(x, y, CAVE_BRICK)

    def row(self, x, y, text, content=None):
        """Place blocks from a string: B brick, Q question, H hard, = girder,
        o floating star, - nothing."""
        for i, ch in enumerate(text):
            tx = x + i
            if ch == "B":
                self.set(tx, y, CAVE_BRICK if self.theme == "cave" else BRICK)
            elif ch == "Q":
                self.set(tx, y, QUESTION)
                self.contents[self.index(tx, y)] = content or "star"
            elif ch == "H":
                self.set(tx, y, HARD)
            elif ch == "=":
                self.set(tx, y, GIRDER)
            elif ch == "o":
                self.stars.add((tx, y))
        return self

    def block(self, x, y, content, brick=False):
        if brick:
            self.set(x, y, CAVE_BRICK if self.theme == "cave" else BRICK)
        else:
            self.set(x, y, QUESTION)
        self.contents[self.index(x, y)] = content

    def star_line(self, x, y, count):
        for i in range(count):
            self.stars.add((x + i, y))

    def pipe(self, x, height, base=13):
        top = base - height
        self.set(x, top, PIPE_TL)
        self.set(x + 1, top, PIPE_TR)
        for y in range(top + 1, base):
            self.set(x, y, PIPE_L)
            self.set(x + 1, y, PIPE_R)

    def stairs(self, x, height, up=True, base=13):
        for i in range(height):
            column = i + 1 if up else height - i
            for j in range(column):
                self.set(x + i, base - 1 - j, HARD)

    def enemy(self, x, kind="bug", y=12):
        self.spawns.append((x, y, kind))

    def hill(self, x, base=13):
        for i in range(6):
            self.decor[self.index(x + i % 3, base - 2 + i // 3)] = HILL + i

    def bush(self, x, base=13):
        for i in range(3):
            self.decor[self.index(x + i, base - 1)] = BUSH + i

    def cloud(self, x, y):
        for i in range(6):
            self.decor[self.index(x + i % 3, y + i // 3)] = CLOUD + i

    def flag(self, x, base=13):
        self.set(x, base - 1, HARD)
        self.set(x, base - 10, POLE_TOP)
        for y in range(base - 9, base - 1):
            self.set(x, y, POLE)
        self.flag_x = x
        castle_x = x + 5
        for i in range(25):
            tx = castle_x + i % 5
            ty = base - 5 + i // 5
            if 0 <= tx < self.width:
                self.decor[self.index(tx, ty)] = CASTLE + i
        self.castle_door = castle_x * TILE + 18


class Body:
    w = 6
    h = 7

    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False

    def move_x(self, level, dt):
        self.x += self.vx * dt
        top = tile_of(self.y)
        bottom = tile_of(self.y + self.h - 0.01)
        if self.vx > 0:
            tx = tile_of(self.x + self.w - 0.01)
            for ty in range(top, bottom + 1):
                if level.solid(tx, ty):
                    self.x = tx * TILE - self.w
                    return True
        elif self.vx < 0:
            tx = tile_of(self.x)
            for ty in range(top, bottom + 1):
                if level.solid(tx, ty):
                    self.x = (tx + 1) * TILE
                    return True
        return False

    def move_y(self, level, dt):
        """Returns the list of tile x positions hit by the head, if any."""
        self.y += self.vy * dt
        self.on_ground = False
        left = tile_of(self.x)
        right = tile_of(self.x + self.w - 0.01)
        if self.vy >= 0:
            ty = tile_of(self.y + self.h - 0.01)
            for tx in range(left, right + 1):
                if level.solid(tx, ty) and self.y + self.h - self.vy * dt <= ty * TILE + 0.5 + abs(self.vy * dt):
                    self.y = ty * TILE - self.h
                    self.vy = 0.0
                    self.on_ground = True
                    return None
        else:
            ty = tile_of(self.y)
            hits = [tx for tx in range(left, right + 1) if level.solid(tx, ty)]
            if hits:
                self.y = (ty + 1) * TILE
                self.vy = 0.0
                return (hits, ty)
        return None


class Player(Body):
    def __init__(self, x, y, character, big=False):
        Body.__init__(self, x, y)
        self.character = character
        self.big = big
        self.facing = 1
        self.crouch = False
        self.jump_buffer = 0.0
        self.coyote = 0.0
        self.invulnerable = 0.0
        self.sparkle = 0.0
        self.carrying = None
        self.stomp_chain = 0
        self.walk_phase = 0.0
        self.skidding = False
        self.dead = False

    @property
    def h(self):
        return BIG_H if self.big else SMALL_H

    def stats(self):
        return CHARACTERS[self.character]


class Enemy(Body):
    def __init__(self, x, y, kind):
        Body.__init__(self, x, y)
        self.kind = kind
        self.state = "walk"
        self.vx = -18.0
        self.timer = 0.0
        self.active = False
        self.grace = 0.0
        self.alive = True

    def harmful(self):
        return self.state in ("walk", "kicked")


class Item(Body):
    w = 8
    h = 8

    def __init__(self, x, y, kind):
        Body.__init__(self, x, y)
        self.kind = kind
        self.emerge = 0.5
        self.target_y = y - TILE
        self.alive = True


class Session:
    def __init__(self, high=0):
        self.score = 0
        self.stars = 0
        self.lives = 3
        self.level = 0
        self.character = "mona"
        self.big = False
        self.inventory = []
        self.high = high
        self.events = []

    def add_score(self, points):
        self.score += points
        if self.score > self.high:
            self.high = self.score

    def add_star(self):
        self.stars += 1
        self.add_score(200)
        self.events.append("star")
        if self.stars >= 100:
            self.stars -= 100
            self.lives += 1
            self.events.append("1up")

    def store(self, kind):
        if len(self.inventory) < INVENTORY_SIZE:
            self.inventory.append(kind)
            return True
        return False


class World:
    def __init__(self, level, session):
        self.level = level
        self.session = session
        sx, sy = level.start
        self.player = Player(sx * TILE + 1, 0, session.character, session.big)
        self.player.y = (sy + 1) * TILE - self.player.h
        self.enemies = [Enemy(x * TILE + 1, (y + 1) * TILE - 7, kind) for x, y, kind in level.spawns]
        self.items = []
        self.particles = []
        self.bumps = []
        self.cam_x = 0.0
        self.time_left = float(level.time)
        self.elapsed = 0.0
        self.state = "play"
        self.state_time = 0.0
        self.flag_y = None if level.flag_x is None else (ROWS - 12) * TILE
        self.flag_bonus = 0
        self.max_cam = max(0, level.width * TILE - VIEW_W)

    # Public API ------------------------------------------------------------
    def update(self, dt, controls):
        if dt > 0.05:
            dt = 0.05
        if dt <= 0:
            return
        self.elapsed += dt
        self.state_time += dt
        self.update_particles(dt)
        if self.state == "play":
            self.time_left -= dt * 2.5
            if self.time_left <= 0:
                self.time_left = 0
                self.kill_player()
            self.update_player(dt, controls)
            self.update_items(dt)
            self.update_enemies(dt)
            if self.state == "play":
                self.check_flag()
                if self.player.y > VIEW_H + 8:
                    self.kill_player(fell=True)
            self.update_camera()
        elif self.state == "dying":
            p = self.player
            if self.state_time > 0.5:
                p.vy = min(p.vy + 600 * dt, MAX_FALL * 1.5)
                p.y += p.vy * dt
            if self.state_time > 2.6:
                self.state = "dead"
        elif self.state == "flag":
            self.update_flag(dt)
        elif self.state == "castle":
            self.update_castle(dt)
        elif self.state == "tally":
            self.update_tally(dt)

    def switch_character(self):
        if not self.level.switch:
            return False
        order = CHARACTER_ORDER
        nxt = order[(order.index(self.player.character) + 1) % len(order)]
        self.player.character = nxt
        self.session.character = nxt
        self.session.events.append("switch")
        return True

    def use_item(self, slot):
        inv = self.session.inventory
        if slot >= len(inv) or self.state != "play":
            return False
        kind = inv[slot]
        if kind == "chip" and self.player.big:
            return False
        inv.pop(slot)
        self.apply_item(kind, from_inventory=True)
        return True

    # Player ------------------------------------------------------------------
    def update_player(self, dt, c):
        p = self.player
        s = p.stats()
        if p.invulnerable > 0:
            p.invulnerable -= dt
        if p.sparkle > 0:
            p.sparkle -= dt

        direction = (1 if c.right else 0) - (1 if c.left else 0)
        p.crouch = p.big and c.down and p.on_ground
        if p.crouch:
            direction = 0
        top_speed = s["run"] if c.run else s["walk"]
        p.skidding = False
        if direction:
            if p.vx * direction < 0:
                p.vx += direction * s["skid"] * dt
                p.skidding = p.on_ground
            else:
                if abs(p.vx) < top_speed:
                    p.vx += direction * s["accel"] * dt
                    if abs(p.vx) > top_speed:
                        p.vx = direction * top_speed
                else:
                    p.vx -= direction * s["decel"] * dt
                    if abs(p.vx) < top_speed:
                        p.vx = direction * top_speed
            if p.on_ground or p.carrying is None:
                p.facing = direction
        else:
            slow = s["decel"] * dt * (1 if p.on_ground else 0.4)
            if abs(p.vx) <= slow:
                p.vx = 0.0
            else:
                p.vx -= slow if p.vx > 0 else -slow

        if c.jump_pressed:
            p.jump_buffer = 0.12
        elif p.jump_buffer > 0:
            p.jump_buffer -= dt
        if p.on_ground:
            p.coyote = 0.08
            p.stomp_chain = 0
        elif p.coyote > 0:
            p.coyote -= dt
        if p.jump_buffer > 0 and p.coyote > 0:
            p.vy = -(s["run_jump"] if abs(p.vx) > s["walk"] + 6 else s["jump"])
            p.jump_buffer = 0.0
            p.coyote = 0.0
            p.on_ground = False
            self.session.events.append("jump")

        gravity = s["grav_hold"] if (c.jump and p.vy < 0) else s["grav"]
        p.vy = min(p.vy + gravity * dt, MAX_FALL)

        if p.move_x(self.level, dt):
            p.vx = 0.0
        if p.x < self.cam_x:
            p.x = self.cam_x
            if p.vx < 0:
                p.vx = 0.0
        head = p.move_y(self.level, dt)
        if head:
            hits, ty = head
            centre = tile_of(p.x + p.w / 2)
            tx = centre if centre in hits else hits[0]
            self.bump(tx, ty)

        if p.on_ground and abs(p.vx) > 1:
            p.walk_phase += abs(p.vx) * dt
        self.collect_stars()
        self.update_carry(c)

    def collect_stars(self):
        p = self.player
        stars = self.level.stars
        if not stars:
            return
        for tx in range(tile_of(p.x), tile_of(p.x + p.w - 0.01) + 1):
            for ty in range(tile_of(p.y), tile_of(p.y + p.h - 0.01) + 1):
                if (tx, ty) in stars:
                    stars.discard((tx, ty))
                    self.session.add_star()
                    self.spawn_particle("sparkle", tx * TILE, ty * TILE, 0, 0)

    def update_carry(self, c):
        p = self.player
        shell = p.carrying
        if shell is None:
            return
        if not shell.alive or shell.state != "carried":
            p.carrying = None
            return
        shell.x = p.x + p.facing * 5
        shell.y = p.y + p.h - shell.h - (4 if p.big else 1)
        if not c.run:
            self.throw_shell()

    def throw_shell(self):
        p = self.player
        shell = p.carrying
        p.carrying = None
        if shell is None:
            return
        shell.state = "kicked"
        shell.vx = p.facing * SHELL_SPEED
        shell.vy = 0.0
        shell.grace = 0.25
        shell.y = p.y + p.h - shell.h
        shell.x = p.x + (p.w if p.facing > 0 else -shell.w)
        if self.body_in_wall(shell):
            shell.x = p.x
            if self.body_in_wall(shell):
                self.defeat_enemy(shell, 200)
        self.session.events.append("kick")

    def body_in_wall(self, body):
        for tx in range(tile_of(body.x), tile_of(body.x + body.w - 0.01) + 1):
            for ty in range(tile_of(body.y), tile_of(body.y + body.h - 0.01) + 1):
                if self.level.solid(tx, ty):
                    return True
        return False

    def hurt_player(self):
        p = self.player
        if p.invulnerable > 0 or p.sparkle > 0 or self.state != "play":
            return
        if p.carrying is not None:
            p.carrying.state = "shell"
            p.carrying.timer = 0.0
            p.carrying = None
        if p.big:
            p.big = False
            p.y += BIG_H - SMALL_H
            p.invulnerable = 2.0
            self.session.big = False
            self.session.events.append("shrink")
        else:
            self.kill_player()

    def kill_player(self, fell=False):
        if self.state != "play":
            return
        p = self.player
        p.dead = True
        p.big = False
        p.vx = 0.0
        p.vy = -170.0 if not fell else 0.0
        p.carrying = None
        self.session.big = False
        self.state = "dying"
        self.state_time = 0.0
        self.session.events.append("die")

    def grow(self):
        p = self.player
        if p.big:
            return
        p.big = True
        p.y -= BIG_H - SMALL_H
        self.session.big = True
        self.session.events.append("grow")

    def apply_item(self, kind, from_inventory=False):
        if kind == "chip":
            if self.player.big:
                if from_inventory or not self.session.store("chip"):
                    self.session.add_score(1000)
                else:
                    self.session.events.append("stored")
            else:
                self.grow()
                self.session.add_score(1000)
        elif kind == "sparkle":
            self.player.sparkle = 8.0
            self.session.add_score(1000)
            self.session.events.append("sparkle")
        elif kind == "1up":
            self.session.lives += 1
            self.session.events.append("1up")

    # Blocks ------------------------------------------------------------------
    def bump(self, tx, ty):
        level = self.level
        tile = level.get(tx, ty)
        index = level.index(tx, ty)
        content = level.contents.get(index)
        if content is not None:
            if content.startswith("multi"):
                remaining = int(content[5:] or "5") - 1
                self.pop_star(tx, ty)
                if remaining > 0:
                    level.contents[index] = "multi%d" % remaining
                    self.add_bump(tx, ty, tile)
                else:
                    del level.contents[index]
                    level.set(tx, ty, USED)
                    self.add_bump(tx, ty, USED)
            else:
                del level.contents[index]
                level.set(tx, ty, USED)
                self.add_bump(tx, ty, USED)
                if content == "star":
                    self.pop_star(tx, ty)
                else:
                    self.items.append(Item(tx * TILE, ty * TILE, content))
                    self.session.events.append("item")
        elif tile in BREAKABLE:
            if self.player.big:
                level.set(tx, ty, EMPTY)
                for vx, vy in ((-40, -150), (40, -150), (-30, -90), (30, -90)):
                    self.spawn_particle("debris", tx * TILE + 2, ty * TILE + 2, vx, vy)
                self.session.add_score(50)
                self.session.events.append("break")
            else:
                self.add_bump(tx, ty, tile)
                self.session.events.append("bump")
        else:
            self.session.events.append("bump")
            return
        self.hit_from_below(tx, ty)

    def add_bump(self, tx, ty, tile):
        self.bumps.append([tx, ty, tile, 0.0])

    def pop_star(self, tx, ty):
        self.session.add_star()
        self.spawn_particle("star", tx * TILE, ty * TILE - TILE, 0, -160)

    def hit_from_below(self, tx, ty):
        x0 = tx * TILE
        top = ty * TILE
        for e in self.enemies:
            if e.alive and e.state in ("walk", "shell") and abs(e.y + e.h - top) < 2 and overlap(e.x, 0, e.w, 1, x0, 0, TILE, 1):
                self.defeat_enemy(e, 100)
        for item in self.items:
            if item.emerge <= 0 and abs(item.y + item.h - top) < 2 and overlap(item.x, 0, item.w, 1, x0, 0, TILE, 1):
                item.vy = -110
                item.vx = abs(item.vx or 40) * (1 if item.x + 4 > x0 + 4 else -1)

    # Items -------------------------------------------------------------------
    def update_items(self, dt):
        p = self.player
        for item in self.items:
            if item.emerge > 0:
                item.emerge -= dt
                item.y = item.target_y + TILE * max(0.0, item.emerge) / 0.5
                if item.emerge <= 0:
                    item.y = item.target_y
                    item.vx = 40.0 if item.kind != "sparkle" else 55.0
                    if item.kind == "sparkle":
                        item.vy = -120.0
                continue
            item.vy = min(item.vy + 600 * dt, MAX_FALL)
            if item.move_x(self.level, dt):
                item.vx = -item.vx
            item.move_y(self.level, dt)
            if item.on_ground and item.kind == "sparkle":
                item.vy = -130.0
            if item.y > VIEW_H + 16 or item.x < self.cam_x - 32:
                item.alive = False
            if overlap(p.x, p.y, p.w, p.h, item.x, item.y, item.w, item.h):
                item.alive = False
                self.apply_item(item.kind)
        self.items = [i for i in self.items if i.alive]

    # Enemies -----------------------------------------------------------------
    def update_enemies(self, dt):
        level = self.level
        p = self.player
        activate = self.cam_x + VIEW_W + 16
        for e in self.enemies:
            if not e.alive:
                continue
            if not e.active:
                if e.x < activate:
                    e.active = True
                else:
                    continue
            if e.grace > 0:
                e.grace -= dt
            if e.state == "squashed":
                e.timer += dt
                if e.timer > 0.5:
                    e.alive = False
                continue
            if e.state == "dead":
                e.vy = min(e.vy + 600 * dt, MAX_FALL)
                e.x += e.vx * dt
                e.y += e.vy * dt
                if e.y > VIEW_H + 16:
                    e.alive = False
                continue
            if e.state == "carried":
                self.shell_hits(e)
                continue
            if e.state == "shell":
                e.timer += dt
                e.vx = 0.0
                if e.timer > 6.0:
                    e.state = "walk"
                    e.vx = -18.0 if p.x < e.x else 18.0
            e.vy = min(e.vy + 600 * dt, MAX_FALL)
            if e.move_x(level, dt):
                e.vx = -e.vx
            e.move_y(level, dt)
            if e.y > VIEW_H + 16 or e.x < self.cam_x - 64:
                e.alive = False
                continue
            if e.state == "kicked":
                self.shell_hits(e)
            self.touch_player(e)
        if len(self.enemies) > 1:
            self.walkers_bounce()
        self.enemies = [e for e in self.enemies if e.alive]

    def walkers_bounce(self):
        walkers = [e for e in self.enemies if e.alive and e.active and e.state == "walk"]
        for i in range(len(walkers)):
            a = walkers[i]
            for b in walkers[i + 1:]:
                if overlap(a.x, a.y, a.w, a.h, b.x, b.y, b.w, b.h):
                    if a.x < b.x:
                        a.vx, b.vx = -abs(a.vx), abs(b.vx)
                    else:
                        a.vx, b.vx = abs(a.vx), -abs(b.vx)

    def shell_hits(self, shell):
        for other in self.enemies:
            if other is shell or not other.alive or not other.active:
                continue
            if other.state in ("dead", "squashed"):
                continue
            if overlap(shell.x, shell.y, shell.w, shell.h, other.x, other.y, other.w, other.h):
                self.defeat_enemy(other, 200)
                if shell.state == "carried":
                    self.defeat_enemy(shell, 200)
                    self.player.carrying = None
                    return

    def touch_player(self, e):
        p = self.player
        if self.state != "play" or e.state in ("dead", "squashed", "carried"):
            return
        if not overlap(p.x, p.y, p.w, p.h, e.x, e.y, e.w, e.h):
            return
        if p.sparkle > 0:
            self.defeat_enemy(e, 200)
            return
        falling_onto = p.vy > 0 and (p.y + p.h) - e.y <= 5
        if e.state == "shell":
            if not falling_onto and p.carrying is None and self.controls_run:
                e.state = "carried"
                e.timer = 0.0
                p.carrying = e
                self.session.events.append("pickup")
                return
            e.state = "kicked"
            e.vx = SHELL_SPEED if (e.x + e.w / 2) >= (p.x + p.w / 2) else -SHELL_SPEED
            e.grace = 0.25
            self.session.add_score(400)
            self.session.events.append("kick")
            if falling_onto:
                p.vy = -STOMP_BOUNCE
            return
        if falling_onto:
            p.stomp_chain += 1
            points = min(100 * (1 << (p.stomp_chain - 1)), 8000)
            self.session.add_score(points)
            self.spawn_particle("score", e.x, e.y - 4, 0, -30, points)
            p.vy = -(p.stats()["jump"] if self.controls_jump else STOMP_BOUNCE)
            p.y = e.y - p.h
            if e.kind == "bug":
                e.state = "squashed"
                e.timer = 0.0
            elif e.state == "walk":
                e.state = "shell"
                e.timer = 0.0
                e.vx = 0.0
            else:
                e.state = "shell"
                e.timer = 0.0
                e.vx = 0.0
            self.session.events.append("stomp")
            return
        if e.state == "kicked" and e.grace > 0:
            return
        self.hurt_player()

    def defeat_enemy(self, e, points):
        e.state = "dead"
        e.vy = -120.0
        e.vx = 30.0 if e.vx >= 0 else -30.0
        self.session.add_score(points)
        self.spawn_particle("score", e.x, e.y - 4, 0, -30, points)
        self.session.events.append("defeat")

    # Particles -----------------------------------------------------------------
    def spawn_particle(self, kind, x, y, vx, vy, data=None):
        self.particles.append([kind, float(x), float(y), float(vx), float(vy), 0.0, data])

    def update_particles(self, dt):
        alive = []
        for part in self.particles:
            kind = part[0]
            part[5] += dt
            if kind == "debris":
                part[4] += 500 * dt
            elif kind == "star":
                part[4] += 520 * dt
            part[1] += part[3] * dt
            part[2] += part[4] * dt
            life = 0.6 if kind == "star" else (0.8 if kind == "score" else (0.35 if kind == "sparkle" else 1.2))
            if part[5] < life:
                alive.append(part)
        self.particles = alive
        bumps = []
        for bump in self.bumps:
            bump[3] += dt
            if bump[3] < 0.16:
                bumps.append(bump)
        self.bumps = bumps

    # Camera / flag ---------------------------------------------------------------
    def update_camera(self):
        target = self.player.x - 64
        if target > self.cam_x:
            self.cam_x = min(target, self.max_cam)

    def check_flag(self):
        fx = self.level.flag_x
        if fx is None:
            return
        p = self.player
        if p.x + p.w >= fx * TILE + 3 and p.y < (ROWS - 2) * TILE:
            if p.carrying is not None:
                p.carrying.state = "shell"
                p.carrying = None
            self.state = "flag"
            self.state_time = 0.0
            p.x = fx * TILE + 3 - p.w
            p.vx = 0.0
            p.vy = 0.0
            height = (ROWS - 3) * TILE - (p.y + p.h)
            bonus = 100
            for limit, points in ((64, 5000), (48, 2000), (32, 800), (16, 400)):
                if height >= limit:
                    bonus = points
                    break
            self.flag_bonus = bonus
            self.session.add_score(bonus)
            self.spawn_particle("score", p.x + 8, p.y, 0, -20, bonus)
            self.session.events.append("flag")

    def update_flag(self, dt):
        p = self.player
        base = (ROWS - 3) * TILE
        p.y = min(p.y + 70 * dt, base - p.h)
        if self.flag_y is not None:
            self.flag_y = min(self.flag_y + 70 * dt, base - TILE)
        if p.y >= base - p.h and (self.flag_y is None or self.flag_y >= base - TILE) and self.state_time > 0.4:
            self.state = "castle"
            self.state_time = 0.0
            p.x += p.w + 2
            p.facing = 1

    def update_castle(self, dt):
        p = self.player
        p.vx = 40.0
        p.vy = min(p.vy + 900 * dt, MAX_FALL)
        p.move_x(self.level, dt)
        p.move_y(self.level, dt)
        p.walk_phase += 40 * dt
        self.update_camera()
        door = self.level.castle_door or (p.x + 1)
        if p.x >= door - 3 or self.state_time > 4:
            self.state = "tally"
            self.state_time = 0.0
            p.vx = 0.0

    def update_tally(self, dt):
        if self.time_left > 0:
            step = min(self.time_left, max(1, int(dt * 120)))
            self.time_left -= step
            self.session.add_score(int(step) * 50)
        elif self.state_time > 1.0:
            self.state = "clear"

    # Convenience for touch_player ----------------------------------------------
    controls_run = False
    controls_jump = False

    def step(self, dt, controls):
        self.controls_run = controls.run
        self.controls_jump = controls.jump
        self.update(dt, controls)
