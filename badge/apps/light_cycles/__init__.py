"""Light Cycles: d-pad to steer, Select to play, Back for mode menu.

CPU: choose one or two bots. Nearby: open this app on both badges, hold them
back to back, then both press Select. First to five wins the match.
Scores are session-only. Home returns to the launcher.
"""

import struct
from badgeware import link as badgelink

COLS, ROWS = 50, 30
CELL, LEFT, TOP = 6, 10, 42
DX, DY = (1, 0, -1, 0), (0, 1, 0, -1)
STEP_MS = 140
COUNTDOWN_MS = 1800
RETRY_MS = 260
TIMEOUT_MS = 6000
TARGET = 5
CPU_NAMES = {
    2: ("USER", "ISO2"),
    3: ("USER", "ISO1", "ISO2"),
}


class Arena:
    def __init__(self, count):
        self.count = count
        self.scores = [0] * count
        self.reset()

    def reset(self):
        self.grid = bytearray(COLS * ROWS)
        starts = ((8, 7, 0), (41, 22, 2), (41, 7, 1))
        self.riders = [list(starts[i]) + [True] for i in range(self.count)]
        for i, rider in enumerate(self.riders):
            self.grid[rider[1] * COLS + rider[0]] = i + 1
        self.tick = 0
        self.over = False
        self.winner = -1

    def free(self, x, y):
        return 0 <= x < COLS and 0 <= y < ROWS and not self.grid[y * COLS + x]

    def direction(self, index, requested):
        current = self.riders[index][2]
        if 0 <= requested < 4 and requested != (current + 2) % 4:
            return requested
        return current

    def step(self, requested):
        if self.over:
            return
        destinations = []
        crashed = []
        for i, rider in enumerate(self.riders):
            x, y, direction, alive = rider
            direction = self.direction(i, requested[i])
            rider[2] = direction
            nx, ny = x + DX[direction], y + DY[direction]
            destinations.append((nx, ny))
            crashed.append(not alive or not self.free(nx, ny))
        # All riders choose against the old grid; a shared empty cell kills both.
        for i in range(self.count):
            for j in range(i):
                if self.riders[i][3] and self.riders[j][3] and destinations[i] == destinations[j]:
                    crashed[i] = crashed[j] = True
        for i, rider in enumerate(self.riders):
            if not rider[3]:
                continue
            rider[3] = not crashed[i]
            if rider[3]:
                rider[0], rider[1] = destinations[i]
                self.grid[rider[1] * COLS + rider[0]] = i + 1
        self.tick += 1
        survivors = [i for i in range(self.count) if self.riders[i][3]]
        if len(survivors) <= 1:
            self.over = True
            self.winner = survivors[0] if survivors else -1
            if self.winner >= 0:
                self.scores[self.winner] += 1

    def bot(self, index):
        x, y, heading, alive = self.riders[index]
        if not alive:
            return heading
        best, best_score = heading, -1
        for direction in (heading, (heading + 1) % 4, (heading - 1) % 4):
            nx, ny = x + DX[direction], y + DY[direction]
            if not self.free(nx, ny):
                continue
            seen = bytearray(COLS * ROWS)
            queue = [ny * COLS + nx]
            seen[queue[0]] = 1
            cursor = 0
            # Bounded flood fill avoids tiny pockets without large searches.
            while cursor < len(queue) and len(queue) < 96:
                cell = queue[cursor]
                cursor += 1
                cx, cy = cell % COLS, cell // COLS
                for d in range(4):
                    ax, ay = cx + DX[d], cy + DY[d]
                    if self.free(ax, ay):
                        at = ay * COLS + ax
                        if not seen[at]:
                            seen[at] = 1
                            queue.append(at)
                            if len(queue) >= 96:
                                break
            distance = 0
            while distance < 12 and self.free(nx, ny):
                distance += 1
                nx += DX[direction]
                ny += DY[direction]
            score = len(queue) * 4 + distance + (2 if direction == heading else 0)
            if score > best_score:
                best, best_score = direction, score
        return best


class LightCycles:
    def __init__(self):
        self.mode = "menu"
        self.choice = 0
        self.cpu_choice = 1
        self.link = None
        self.proximity = None
        self.arena = None
        self.message = ""
        self.network = False
        self.local = 0
        self.want = 0
        self.remote_want = 2
        self.round_id = 0
        self.my_ready = False
        self.their_ready = False
        self.pending = None
        self.pending_tick = 0
        self.sent_at = 0
        self.ready_at = 0
        self.input_at = 0
        self.input_serial = 0
        self.remote_serial = 0
        self.ping_at = 0
        self.last_rx = 0
        self.linked_before = False
        self.mode_at = 0
        self.step_at = 0

    def set_mode(self, mode, now):
        self.mode, self.mode_at = mode, now

    def close(self):
        if self.link is not None:
            self.link.close()
            self.link = None
            self.proximity = None
        badge.caselights(0)

    def menu(self, message=""):
        self.close()
        self.network = False
        self.pending = None
        self.message = message
        self.mode = "menu"

    def cpu(self, now):
        self.network = False
        self.local = 0
        self.arena = Arena(self.cpu_choice + 2)
        self.new_cpu_round(now)

    def new_cpu_round(self, now):
        if max(self.arena.scores) >= TARGET:
            self.arena.scores = [0] * self.arena.count
        self.arena.reset()
        self.want = self.arena.riders[0][2]
        self.set_mode("countdown", now)
        self.step_at = now + COUNTDOWN_MS

    def nearby(self, now):
        self.link = badgelink.Link("light_cycles")
        self.proximity = badgelink.Proximity(self.link)
        self.network = True
        self.linked_before = False
        self.message = ""
        self.set_mode("lobby", now)

    def leave(self, now, message):
        partner = self.link.partner
        self.proximity.rest(partner.id if partner else None, now)
        self.link.leave()
        self.pending = None
        self.my_ready = self.their_ready = False
        self.message = message
        self.linked_before = False
        self.set_mode("lobby", now)

    def send(self, packet):
        self.link.send(packet)

    def reliable(self, packet, tick, now):
        self.pending, self.pending_tick = packet, tick
        self.sent_at = now
        self.send(packet)

    def prepare(self, now):
        self.arena.reset()
        self.want = self.arena.riders[self.local][2]
        self.remote_want = self.arena.riders[1][2]
        self.input_serial = self.remote_serial = 0
        self.my_ready = self.their_ready = False
        self.pending = None
        self.step_at = now + COUNTDOWN_MS
        self.set_mode("countdown", now)

    def host_start(self, now):
        if max(self.arena.scores) >= TARGET:
            self.arena.scores = [0, 0]
        self.round_id = (self.round_id + 1) & 65535
        self.prepare(now)
        packet = b"S" + struct.pack("<HBB", self.round_id, *self.arena.scores)
        self.reliable(packet, 0, now)

    def ack(self, tick):
        self.send(b"K" + struct.pack("<HH", self.round_id, tick))

    def handle(self, packet, now):
        kind, body = packet[:1], packet[1:]
        if kind in (b"P", b"Q") and not body:
            self.last_rx = now
            if kind == b"P":
                self.send(b"Q")
        elif kind == b"R" and len(body) == 2:
            round_id = struct.unpack("<H", body)[0]
            if round_id == self.round_id and self.mode in ("offer", "over"):
                self.last_rx = now
                self.their_ready = True
        elif kind == b"S" and len(body) == 4 and not self.link.central:
            round_id, score0, score1 = struct.unpack("<HBB", body)
            if round_id == self.round_id and self.mode in ("countdown", "play", "over"):
                self.last_rx = now
                self.ack(0)
            elif (round_id == (self.round_id + 1) & 65535
                  and self.mode in ("offer", "over") and self.my_ready
                  and score0 <= TARGET and score1 <= TARGET):
                self.last_rx = now
                self.round_id = round_id
                self.arena.scores = [score0, score1]
                self.prepare(now)
                self.ack(0)
        elif kind == b"K" and len(body) == 4 and self.link.central:
            round_id, tick = struct.unpack("<HH", body)
            if round_id == self.round_id and self.pending is not None and tick == self.pending_tick:
                self.last_rx = now
                self.pending = None
                if tick == 0:
                    self.mode_at = now
                    self.step_at = now + COUNTDOWN_MS
        elif kind == b"I" and len(body) == 7 and self.link.central:
            round_id, tick, serial, direction = struct.unpack("<HHHB", body)
            if (round_id == self.round_id and tick == self.arena.tick + 1
                    and direction < 4 and (serial - self.remote_serial) & 65535 < 32768
                    and self.mode in ("countdown", "play")):
                self.last_rx = now
                self.remote_serial = serial
                self.remote_want = self.arena.direction(1, direction)
        elif kind == b"T" and len(body) == 6 and not self.link.central:
            round_id, tick, d0, d1 = struct.unpack("<HHBB", body)
            if round_id != self.round_id or d0 > 3 or d1 > 3:
                return
            if tick == self.arena.tick and tick > 0:
                self.last_rx = now
                self.ack(tick)
            elif (tick == self.arena.tick + 1 and not self.arena.over
                  and self.mode in ("countdown", "play")):
                self.last_rx = now
                self.arena.step((d0, d1))
                self.want = self.arena.direction(self.local, self.want)
                self.set_mode("over" if self.arena.over else "play", now)
                self.ack(tick)
                if self.arena.over:
                    self.my_ready = self.their_ready = False
        elif kind == b"L" and not body:
            self.leave(now, "Opponent left")

    def steer(self):
        for button, direction in ((BUTTON_RIGHT, 0), (BUTTON_DOWN, 1),
                                  (BUTTON_LEFT, 2), (BUTTON_UP, 3)):
            if badge.pressed(button):
                heading = self.arena.riders[self.local][2]
                if direction != (heading + 2) % 4 and direction != self.want:
                    self.want = direction
                    self.input_serial = (self.input_serial + 1) & 65535
                break

    def network_frame(self, now):
        self.link.pump()
        linked = self.link.linked
        if linked and not self.linked_before:
            self.local = 0 if self.link.central else 1
            self.arena = Arena(2)
            self.round_id = 0
            self.my_ready = self.their_ready = False
            self.pending = None
            self.last_rx = now
            self.ping_at = now
            self.set_mode("offer", now)
        elif self.linked_before and not linked:
            self.proximity.clear()
            self.pending = None
            self.message = "Connection lost"
            self.set_mode("lobby", now)
        self.linked_before = linked
        if linked:
            for packet in self.link.receive():
                self.handle(packet, now)
                if self.mode == "lobby":
                    break
            if self.mode != "lobby":
                if now - self.last_rx > TIMEOUT_MS:
                    self.leave(now, "Link timed out")
                else:
                    if now - self.ping_at >= 700:
                        self.send(b"P")
                        self.ping_at = now
                    if self.pending is not None and now - self.sent_at >= RETRY_MS:
                        self.send(self.pending)
                        self.sent_at = now
                    if self.my_ready and self.mode in ("offer", "over") and now - self.ready_at >= RETRY_MS:
                        self.send(b"R" + struct.pack("<H", self.round_id))
                        self.ready_at = now
                    if (self.link.central and self.mode in ("offer", "over")
                            and self.my_ready and self.their_ready and self.pending is None):
                        self.host_start(now)
        if self.mode == "lobby":
            self.proximity.update(now)

    def update(self, now):
        if badge.pressed(BUTTON_BACK):
            if self.mode == "menu":
                reset()
                return
            if self.link is not None and self.link.linked:
                self.send(b"L")
                self.link.update()
            self.menu()
            return
        if self.mode == "menu":
            if badge.pressed(BUTTON_UP) or badge.pressed(BUTTON_DOWN):
                self.choice = 1 - self.choice
            if badge.pressed(BUTTON_SELECT):
                if self.choice == 0:
                    self.set_mode("cpu_menu", now)
                else:
                    self.nearby(now)
            return
        if self.mode == "cpu_menu":
            if badge.pressed(BUTTON_UP) or badge.pressed(BUTTON_DOWN):
                self.cpu_choice = 1 - self.cpu_choice
            if badge.pressed(BUTTON_SELECT):
                self.cpu(now)
            return
        if self.network:
            self.network_frame(now)
        if self.mode in ("offer", "over"):
            if badge.pressed(BUTTON_SELECT):
                if self.network:
                    self.my_ready = True
                    self.send(b"R" + struct.pack("<H", self.round_id))
                    self.ready_at = now
                else:
                    self.new_cpu_round(now)
        elif self.mode in ("countdown", "play"):
            self.steer()
            if self.network and not self.link.central and now - self.input_at >= 60:
                self.send(b"I" + struct.pack("<HHHB", self.round_id, self.arena.tick + 1,
                                            self.input_serial, self.want))
                self.input_at = now
            if now >= self.step_at:
                if self.network:
                    if self.link.central and self.pending is None:
                        directions = (self.arena.direction(0, self.want),
                                      self.arena.direction(1, self.remote_want))
                        self.arena.step(directions)
                        self.want, self.remote_want = directions
                        packet = b"T" + struct.pack("<HHBB", self.round_id, self.arena.tick, *directions)
                        self.reliable(packet, self.arena.tick, now)
                        self.set_mode("over" if self.arena.over else "play", now)
                        if self.arena.over:
                            self.my_ready = self.their_ready = False
                        self.step_at = now + STEP_MS
                else:
                    directions = [self.want] + [self.arena.bot(i) for i in range(1, self.arena.count)]
                    self.arena.step(directions)
                    self.want = self.arena.riders[0][2]
                    self.set_mode("over" if self.arena.over else "play", now)
                    self.step_at = now + STEP_MS
        if self.link is not None:
            self.link.update()

    def draw(self, now):
        screen.pen = BACKGROUND
        screen.clear()
        if self.mode in ("menu", "cpu_menu", "lobby", "offer"):
            self.draw_menu(now)
            return
        arena = self.arena
        inks = INKS if self.network else CPU_INKS[arena.count]
        cpu_names = () if self.network else CPU_NAMES[arena.count]
        screen.font = font.bacteria
        for i, score in enumerate(arena.scores):
            screen.pen = inks[i]
            name = ("YOU" if i == self.local else "RIVAL") if self.network else cpu_names[i]
            screen.text("%s %d" % (name, score), 10 + i * (150 if self.network else 102), 8)
        centre("FIRST TO 5   /   BACK: MENU", 25, DIM)
        screen.pen = GRID
        screen.rectangle(LEFT - 2, TOP - 2, COLS * CELL + 4, ROWS * CELL + 4)
        screen.pen = BACKGROUND
        screen.rectangle(LEFT, TOP, COLS * CELL, ROWS * CELL)
        screen.pen = GRID
        for x in range(0, COLS, 5):
            screen.rectangle(LEFT + x * CELL, TOP, 1, ROWS * CELL)
        for y in range(0, ROWS, 5):
            screen.rectangle(LEFT, TOP + y * CELL, COLS * CELL, 1)
        for at, owner in enumerate(arena.grid):
            if owner:
                screen.pen = inks[owner - 1]
                screen.rectangle(LEFT + at % COLS * CELL, TOP + at // COLS * CELL, CELL - 1, CELL - 1)
        for i, (x, y, direction, alive) in enumerate(arena.riders):
            if alive:
                # Contrast ISO1's head against its white trail.
                screen.pen = BACKGROUND if not self.network and inks[i] == ISO1_WHITE else WHITE
                screen.rectangle(LEFT + x * CELL + 1, TOP + y * CELL + 1, CELL - 3, CELL - 3)
        if self.mode == "countdown":
            number = str(max(1, 3 - (now - self.mode_at) // 600))
            self.panel(number, "D-PAD TO STEER")
        elif self.mode == "over":
            winner = arena.winner
            if winner < 0:
                title = "DRAW"
            elif self.network:
                title = "YOU WIN" if winner == self.local else "RIVAL WINS"
            else:
                title = cpu_names[winner] + " WINS"
            match_over = max(arena.scores) >= TARGET
            if match_over:
                title += " MATCH"
            prompt = "SELECT: NEW MATCH" if match_over else "SELECT: NEXT ROUND"
            if self.my_ready:
                prompt = "WAITING FOR RIVAL"
            elif self.their_ready:
                prompt = "RIVAL READY / SELECT"
            self.panel(title, prompt)
        else:
            centre("D-PAD: STEER  AVOID TRAILS", 224, DIM)

    def panel(self, title, subtitle):
        screen.pen = BACKGROUND
        screen.rectangle(14, 99, 292, 57)
        centre(title, 108, WHITE, font.futile)
        centre(subtitle, 139, CYAN)

    def draw_menu(self, now):
        centre("LIGHT CYCLES", 24, CYAN, font.futile)
        centre("CPU BATTLE" if self.mode == "cpu_menu" else "OUTLAST YOUR RIVALS", 52, DIM)
        if self.mode in ("menu", "cpu_menu"):
            cpu_menu = self.mode == "cpu_menu"
            labels = ("1V1 - ONE CPU", "1V2 - TWO CPUS") if cpu_menu else ("CPU BATTLE", "NEARBY BADGE")
            choice = self.cpu_choice if cpu_menu else self.choice
            for i, label in enumerate(labels):
                screen.pen = GRID if choice == i else BACKGROUND
                screen.rectangle(35, 83 + i * 36, 250, 29)
                centre(("> " if choice == i else "  ") + label, 92 + i * 36,
                       CYAN if choice == i else DIM, font.futile)
            centre("UP/DOWN: RIVALS  SELECT: GO" if cpu_menu else "UP/DOWN: MODE  SELECT: GO", 176, WHITE)
            centre("D-PAD: STEER  BACK: MENU", 195, DIM)
            centre("HOME: LAUNCHER", 213, DIM)
        elif self.mode == "lobby":
            peer = self.proximity.syncing()
            if peer is not None:
                centre("CONNECTING...", 104, WHITE, font.futile)
            elif self.proximity.cooling(now) is not None:
                centre("PULL BADGES APART", 104, WHITE, font.futile)
            else:
                centre("HOLD BADGES", 96, WHITE, font.futile)
                centre("BACK TO BACK", 122, WHITE, font.futile)
            centre("OPEN ON BOTH BADGES", 157, DIM)
            centre(self.message or "BACK: MODE MENU", 193, CYAN)
        else:
            partner = self.link.partner
            centre(partner.name if partner else "NEARBY RIDER", 92, WHITE, font.futile)
            centre("YOU ARE CYAN" if self.local == 0 else "YOU ARE MAGENTA", 123, INKS[self.local])
            centre("WAITING FOR RIVAL" if self.my_ready else "SELECT: READY", 160, CYAN)
            centre("RIVAL READY" if self.their_ready else "BOTH RIDERS MUST ACCEPT", 185, DIM)
            centre("BACK: MODE MENU", 213, DIM)


badge.mode(HIRES | VSYNC)
screen.antialias = image.OFF
BACKGROUND = color.rgb(2, 7, 16)
GRID = color.rgb(12, 38, 51)
CYAN = color.rgb(0, 235, 255)
WHITE = color.rgb(235, 255, 255)
ISO1_WHITE = color.rgb(255, 255, 255)
DIM = color.rgb(105, 161, 181)
INKS = (CYAN, color.rgb(255, 65, 183), color.rgb(255, 187, 42))
CPU_INKS = {
    2: (CYAN, INKS[2]),
    3: (CYAN, ISO1_WHITE, INKS[2]),
}


def centre(text, y, pen, typeface=None):
    screen.font = typeface or font.bacteria
    screen.pen = pen
    while text and screen.measure_text(text)[0] > screen.width - 16:
        text = text[:-1]
    screen.text(text, (screen.width - screen.measure_text(text)[0]) // 2, y)


game = LightCycles()


def update():
    game.update(badge.ticks)
    game.draw(badge.ticks)


def on_exit():
    game.close()


run(update)
