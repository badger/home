"""Hardware-independent water-balloon physics, terrain, and turn rules."""

import math
import random


WIDTH = 200
HEIGHT = 150
FLOOR = 126
GRAVITY = 42
STEP = 1 / 120
BLAST_RADIUS = 17
WALK_DISTANCE = 12
WHEEL_BASE = 6
DRYER_DURATION = 3.8
RIDER_HEIGHT = 9


def soak_rgb(soak):
    stops = ((45, 154, 216), (250, 225, 75), (250, 174, 45), (235, 55, 55))
    position = max(0, min(100, soak)) / 100 * 3
    index = min(2, int(position))
    blend = position - index
    return tuple(int(a + (b - a) * blend)
                 for a, b in zip(stops[index], stops[index + 1]))


class Game:
    def __init__(self, computer=True):
        self.computer = computer
        self.terrain = [bytearray(WIDTH) for _ in range(HEIGHT)]
        phase = random.random() * 6
        self.cliff = random.randint(80, 120)
        cliff_direction = random.choice((-1, 1))
        cliff_height = int(86 + 16 * math.sin(self.cliff / 16 + phase)
                           + 8 * math.sin(self.cliff / 7 + phase))
        if not 45 <= cliff_height + 23 * cliff_direction <= FLOOR - 8:
            cliff_direction = -cliff_direction
        for x in range(WIDTH):
            top = int(86 + 16 * math.sin(x / 16 + phase)
                      + 8 * math.sin(x / 7 + phase)
                      + (23 * cliff_direction if x >= self.cliff else 0))
            top = max(45, min(FLOOR - 8, top))
            for y in range(top, FLOOR):
                self.terrain[y][x] = 1
        self.initial_surface = [self.surface(x) for x in range(WIDTH)]
        self.craters = []
        self.players = [
            {"x": 24.0, "y": 0.0, "vx": 0.0, "vy": 0.0, "fall": 0.0,
             "tilt": 0.0, "wheel": 0.0,
             "soak": 0, "cause": None, "angle": 47.0, "power": 66.0},
            {"x": float(WIDTH - 24), "y": 0.0, "vx": 0.0, "vy": 0.0, "fall": 0.0,
             "tilt": 0.0, "wheel": 0.0,
             "soak": 0, "cause": None, "angle": 47.0, "power": 66.0},
        ]
        for player in self.players:
            player["y"] = float(self.surface(int(player["x"])))
            player["y"], player["tilt"] = self.ground_pose(player["x"], player["y"])
            player["fall"] = player["y"]
        self.active = 0
        self.phase = "move"
        self.walk = float(WALK_DISTANCE)
        self.wind = random.randint(-5, 5)
        self.projectile = None
        self.trail = []
        self.splash = None
        self.timer = 0.0
        self.revision = 0
        self.winner = None
        self.turn = 1
        self.ai_index = 0
        self.ai_best = None
        self.ai_wait = 0.0
        self.accumulator = 0.0
        self.cart_accumulator = 0.0
        self.butterfly = None
        self.butterfly_delay = random.uniform(4, 9)
        self.dryer_time = 0.0
        self.dryer_before = 0
        self.dryer_after = 0
        self.dryer_applied = False

    def solid(self, x, y):
        x, y = int(x), int(y)
        return 0 <= x < WIDTH and 0 <= y < HEIGHT and self.terrain[y][x]

    def surface(self, x, start=0):
        x = max(0, min(WIDTH - 1, int(x)))
        for y in range(max(0, int(start)), FLOOR):
            if self.terrain[y][x]:
                return y
        return FLOOR

    def ground_pose(self, x, y):
        half = WHEEL_BASE / 2
        left = self.surface(x - half, y - 4)
        right = self.surface(x + half, y - 4)
        tilt = max(-0.95, min(0.95, math.atan2(right - left, WHEEL_BASE)))
        # Keep both wheel contacts above solid pixels, even at a cliff lip.
        left = self.surface(x - half * math.cos(tilt), y - 4)
        right = self.surface(x + half * math.cos(tilt), y - 4)
        ground = min(left + half * math.sin(tilt),
                     right - half * math.sin(tilt))
        if left == FLOOR and right == FLOOR:
            ground = FLOOR
        return ground, tilt

    def supported(self, player):
        ground, _ = self.ground_pose(player["x"], player["y"])
        return abs(ground - player["y"]) < 0.15 and ground < FLOOR

    def move(self, distance):
        if self.phase != "move" or self.walk <= 0:
            return
        player = self.players[self.active]
        if not self.supported(player):
            return
        distance = max(-self.walk, min(self.walk, distance))
        target = max(5, min(WIDTH - 6, player["x"] + distance))
        other = self.players[1 - self.active]
        if abs(target - other["x"]) < 11:
            return
        # Walk in subpixel steps so slopes cannot be skipped at low frame rates.
        steps = max(1, int(abs(target - player["x"]) / 0.4) + 1)
        step = (target - player["x"]) / steps
        for _ in range(steps):
            nx = player["x"] + step
            foot, tilt = self.ground_pose(nx, player["y"])
            if foot < player["y"] - 2:
                break
            player["x"] = nx
            player["wheel"] += step / 1.5
            if foot <= player["y"] + 2:
                player["y"] = foot
                player["tilt"] = tilt
            player["fall"] = player["y"]
            self.walk = max(0, self.walk - abs(step))
            if not self.supported(player):
                break

    def aim(self):
        if self.phase == "move" and self.carts_still():
            self.phase = "aim"

    def carts_still(self):
        return all(p["soak"] >= 100 or
                   (self.supported(p) and abs(p["vx"]) < 0.05 and p["vy"] == 0)
                   for p in self.players)

    def launch_values(self, angle, power, index=None):
        if index is None:
            index = self.active
        player = self.players[index]
        radians = angle * math.pi / 180
        direction = 1 if index == 0 else -1
        dx = math.cos(radians) * direction
        dy = -math.sin(radians)
        speed = 18 + power * 0.84
        return [player["x"] + dx * 6, player["y"] - RIDER_HEIGHT + dy * 6,
                dx * speed, dy * speed, 0.0]

    def fire(self):
        if self.phase != "aim" or not self.carts_still():
            return
        player = self.players[self.active]
        self.projectile = self.launch_values(player["angle"], player["power"])
        self.trail = []
        self.accumulator = 0.0
        self.phase = "flight"

    def advance_ball(self, ball, dt):
        ball[2] += self.wind * dt
        ball[3] += GRAVITY * dt
        ball[0] += ball[2] * dt
        ball[1] += ball[3] * dt
        ball[4] += dt

    def impact(self, ball, bonuses=True):
        x, y = ball[0], ball[1]
        if x < 0 or x >= WIDTH or y >= FLOOR or ball[4] >= 7:
            return "miss"
        if self.solid(x, y):
            return "hit"
        if bonuses and self.butterfly:
            if (x - self.butterfly["x"]) ** 2 + (y - self.butterfly["y"]) ** 2 <= 25:
                return "butterfly"
        for player in self.players:
            if (x - player["x"]) ** 2 + (y - (player["y"] - RIDER_HEIGHT)) ** 2 < 16:
                return "hit"
        return None

    def add_soak(self, player, amount, cause):
        if amount > 0 and player["soak"] < 100:
            player["soak"] = min(100, player["soak"] + amount)
            player["cause"] = cause

    def result_lines(self):
        names = ("PIG", "GOOSE")
        causes = {"splash": "balloon splash", "fall": "hard landing",
                  "water": "fell into water"}
        if self.winner == -1:
            return tuple("%s: %s" % (names[i], causes[p["cause"]])
                         for i, p in enumerate(self.players))
        loser = 1 - self.winner
        player = self.players[loser]
        return ("%s reached 100%% soaked" % names[loser],
                "Cause: %s" % causes[player["cause"]])

    def explode(self, x, y):
        self.splash = (x, y)
        self.carve_crater(x, y)
        self.craters.append((x, y))
        for player in self.players:
            distance = math.sqrt((x - player["x"]) ** 2
                                 + (y - (player["y"] - RIDER_HEIGHT)) ** 2)
            damage = max(0, int(56 * (1 - distance / (BLAST_RADIUS + 7))))
            self.add_soak(player, damage, "splash")
            player["fall"] = player["y"]
        self.revision += 1
        self.projectile = None
        self.phase = "splash"
        self.timer = 0.55

    def carve_crater(self, x, y):
        radius = BLAST_RADIUS
        for yy in range(max(0, int(y - radius)), min(FLOOR, int(y + radius) + 1)):
            for xx in range(max(0, int(x - radius)), min(WIDTH, int(x + radius) + 1)):
                if (xx - x) ** 2 + (yy - y) ** 2 <= radius * radius:
                    self.terrain[yy][xx] = 0

    def roll_step(self, player, dt):
        ground, tilt = self.ground_pose(player["x"], player["y"])
        if ground >= FLOOR and player["y"] >= FLOOR - 0.15:
            player["y"] = float(FLOOR)
            player["vx"] = player["vy"] = 0.0
            self.add_soak(player, 100, "water")
            return
        grounded = ground <= player["y"] + 0.15
        if grounded:
            player["y"] = ground
            player["tilt"] = tilt
            player["vy"] = 0
            player["fall"] = ground
            force = 42 * math.sin(tilt)
            friction = 7
            if abs(force) <= friction and abs(player["vx"]) < 1:
                player["vx"] = 0.0
            else:
                direction = 1 if player["vx"] > 0 else -1
                if abs(player["vx"]) < 0.1:
                    direction = 1 if force > 0 else -1
                velocity = player["vx"] + (force - direction * friction) * dt
                if player["vx"] * velocity < 0 and abs(force) <= friction:
                    velocity = 0.0
                player["vx"] = max(-26, min(26, velocity))
        else:
            player["vy"] += 75 * dt
        dx = player["vx"] * dt
        nx = max(4, min(WIDTH - 5, player["x"] + dx))
        other = self.players[1] if player is self.players[0] else self.players[0]
        if abs(nx - other["x"]) < 9 and abs(player["y"] - other["y"]) < 10:
            player["vx"] = 0.0
            nx = player["x"]
        next_ground, next_tilt = self.ground_pose(nx, player["y"])
        if next_ground < player["y"] - 2:
            player["vx"] = 0.0
        else:
            player["wheel"] += (nx - player["x"]) / 1.5
            player["x"] = nx
            if grounded and abs(next_ground - player["y"]) <= 2:
                player["y"] = next_ground
                player["tilt"] = next_tilt
                player["fall"] = next_ground
        if nx in (4, WIDTH - 5):
            player["vx"] = 0.0
        target = player["y"] + player["vy"] * dt
        while player["y"] < target:
            player["y"] = min(target, player["y"] + 0.5)
            ground, tilt = self.ground_pose(player["x"], player["y"])
            if player["y"] >= FLOOR or ground <= player["y"]:
                player["y"] = min(FLOOR, ground)
                drop = player["y"] - player["fall"]
                player["vy"] = 0.0
                player["tilt"] = tilt
                if player["y"] >= FLOOR:
                    self.add_soak(player, 100, "water")
                else:
                    self.add_soak(player, max(0, int(drop - 9)), "fall")
                player["fall"] = player["y"]
                break

    def settle(self, dt):
        self.cart_accumulator += dt
        while self.cart_accumulator >= STEP:
            self.cart_accumulator -= STEP
            for player in self.players:
                if player["soak"] < 100:
                    self.roll_step(player, STEP)
        return not self.carts_still()

    def spawn_butterfly(self):
        direction = random.choice((-1, 1))
        amplitude = random.uniform(4, 9)
        self.butterfly = {
            "x": -7.0 if direction == 1 else WIDTH + 7.0,
            "y": 0.0, "base": random.uniform(22 + amplitude, 43 - amplitude),
            "amplitude": amplitude, "direction": direction,
            "speed": random.uniform(12, 21), "phase": random.random() * math.pi * 2,
            "frequency": random.uniform(1.3, 2.7), "time": 0.0,
        }
        b = self.butterfly
        b["y"] = b["base"] + b["amplitude"] * math.sin(b["phase"])

    def update_butterfly(self, dt):
        if self.butterfly:
            b = self.butterfly
            b["time"] += dt
            b["x"] += b["direction"] * b["speed"] * dt
            b["y"] = b["base"] + b["amplitude"] * math.sin(
                b["phase"] + b["time"] * b["frequency"])
            if b["x"] < -10 or b["x"] > WIDTH + 10:
                self.butterfly = None
                self.butterfly_delay = random.uniform(9, 17)
        else:
            self.butterfly_delay -= dt
            if self.butterfly_delay <= 0:
                self.spawn_butterfly()

    def start_dryer(self):
        self.butterfly = None
        self.butterfly_delay = random.uniform(10, 18)
        self.projectile = None
        self.trail = []
        self.phase = "dryer"
        self.dryer_time = 0.0
        self.dryer_applied = False
        self.dryer_before = self.players[self.active]["soak"]
        self.dryer_after = max(0, self.dryer_before - 25)

    def update_dryer(self, dt):
        self.dryer_time += dt
        if not self.dryer_applied and self.dryer_time >= 1.6:
            self.players[self.active]["soak"] = self.dryer_after
            self.dryer_applied = True
        if self.dryer_time >= DRYER_DURATION:
            self.phase = "settle"
            self.timer = 0.4

    def check_winner(self):
        wet = [p["soak"] >= 100 for p in self.players]
        if any(wet):
            self.phase = "over"
            self.winner = -1 if all(wet) else (1 if wet[0] else 0)
            return True
        return False

    def finish_turn(self):
        if self.check_winner():
            return
        self.active = 1 - self.active
        self.turn += 1
        self.walk = float(WALK_DISTANCE)
        self.wind = random.randint(-5, 5)
        self.trail = []
        self.splash = None
        if self.computer and self.active == 1:
            self.phase = "think"
            self.ai_index = 0
            self.ai_best = None
            self.ai_wait = 0.0
        else:
            self.phase = "move"

    def evaluate_shot(self, angle, power):
        ball = self.launch_values(angle, power)
        # The same integrator/collision rules as real throws; doubled time step
        # keeps each incremental search batch short on MicroPython.
        while True:
            self.advance_ball(ball, STEP * 2)
            hit = self.impact(ball, bonuses=False)
            if hit:
                break
        target = self.players[1 - self.active]
        own = self.players[self.active]
        distance = math.sqrt((ball[0] - target["x"]) ** 2
                             + (ball[1] - (target["y"] - RIDER_HEIGHT)) ** 2)
        self_distance = math.sqrt((ball[0] - own["x"]) ** 2
                                  + (ball[1] - (own["y"] - RIDER_HEIGHT)) ** 2)
        return distance + max(0, 24 - self_distance) * 2

    def think(self, dt):
        self.ai_wait += dt
        if self.ai_index < 120:
            angle = 20 + (self.ai_index % 12) * 6
            power = 28 + (self.ai_index // 12) * 8
            score = self.evaluate_shot(angle, power)
            if self.ai_best is None or score < self.ai_best[0]:
                self.ai_best = (score, angle, power)
            self.ai_index += 1
        elif self.ai_wait >= 1.0:
            player = self.players[self.active]
            player["angle"] = max(10, min(170, self.ai_best[1] + random.randint(-3, 3)))
            player["power"] = max(20, min(100, self.ai_best[2] + random.randint(-3, 3)))
            self.phase = "aim"
            self.fire()

    def update(self, dt):
        dt = max(0, min(dt, 0.1))
        if self.phase == "over":
            return
        if self.phase == "dryer":
            self.update_dryer(dt)
            return
        self.update_butterfly(dt)
        if self.phase in ("move", "aim", "think", "flight"):
            self.settle(dt)
            if self.check_winner():
                return
        if self.phase == "think":
            if self.carts_still():
                self.think(dt)
        elif self.phase == "flight":
            self.accumulator += dt
            while self.accumulator >= STEP and self.phase == "flight":
                self.accumulator -= STEP
                self.advance_ball(self.projectile, STEP)
                hit = self.impact(self.projectile)
                if hit == "butterfly":
                    self.start_dryer()
                elif hit == "hit":
                    self.explode(self.projectile[0], self.projectile[1])
                elif hit == "miss":
                    self.projectile = None
                    self.phase = "settle"
                    self.timer = 0.3
            if self.projectile:
                self.trail.append((self.projectile[0], self.projectile[1]))
                if len(self.trail) > 24:
                    self.trail.pop(0)
        elif self.phase == "splash":
            self.timer -= dt
            if self.timer <= 0:
                self.phase = "settle"
                self.timer = 0.4
        elif self.phase == "settle":
            if not self.settle(dt):
                self.timer -= dt
                if self.timer <= 0:
                    self.finish_turn()
