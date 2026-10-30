"""Host-authoritative gameplay over the same badgeware link used by Pong."""

import json
import struct

from game import Game, WIDTH, HEIGHT, FLOOR


PROTOCOL = b"PVG1"
PHASES = ("move", "aim", "flight", "splash", "settle", "dryer", "over")
PLAYER_KEYS = ("x", "y", "vx", "vy", "fall", "tilt", "wheel",
               "soak", "cause", "angle", "power")
STATE_KEYS = ("active", "phase", "walk", "wind", "projectile", "trail",
              "splash", "timer", "revision", "winner", "turn", "butterfly",
              "dryer_time", "dryer_before", "dryer_after", "dryer_applied")
SELECT = 1
BACK = 2
MENU = 4
MAX_PAYLOAD = 24000
MAX_PARTS = 2048
RETRY = 0.7
TIMEOUT = 12.0


def controls(game, dt, horizontal, vertical, buttons):
    if game.phase == "move":
        game.move(horizontal * 12 * dt)
        if buttons & SELECT:
            game.aim()
    elif game.phase == "aim":
        player = game.players[game.active]
        player["angle"] = max(10, min(170, player["angle"] + horizontal * 38 * dt))
        player["power"] = max(20, min(100, player["power"] + vertical * 35 * dt))
        if buttons & BACK:
            game.phase = "move"
        elif buttons & SELECT:
            game.fire()


class Multiplayer:
    def __init__(self, link, proximity):
        self.link = link
        self.proximity = proximity
        self.game = None
        self.status = "search"
        self.message = ""
        self.linked_before = False
        self.accepted = False
        self.peer_accepted = False
        self.host = False
        self.local_player = 0
        self.paused = False
        self.round = 0
        self.round_seen = 0
        self.rematch = [False, False]
        self.time = 0.0
        self.heard_at = 0.0
        self.hello_at = -1.0
        self.ping_at = -1.0
        self.snapshot_at = -1.0
        self.sequence = 0
        self.received_sequence = 0
        self.outgoing = None
        self.outgoing_part = 0
        self.outgoing_at = 0.0
        self.outgoing_started = 0.0
        self.incoming_sequence = 0
        self.incoming_parts = {}
        self.incoming_total = 0
        self.input_sequence = 0
        self.input_received = 0
        self.input_pending = None
        self.input_at = -1.0
        self.input_started = 0.0
        self.remote_axes = (0, 0)
        self.remote_until = 0.0
        self.terrain_acked = None
        self.terrain_sending = None
        self.snapshot_tag = None

    def send(self, payload):
        return self.link.send(payload)

    def fail(self, reason):
        print("Pig vs Goose link:", reason)
        self.message = reason
        self.status = "error"
        self.remote_axes = (0, 0)
        self.link.leave()

    def close(self):
        self.link.close()

    def new_round(self):
        self.round += 1
        self.game = Game(False)
        self.paused = False
        self.rematch = [False, False]
        self.remote_axes = (0, 0)
        self.remote_until = 0.0
        self.terrain_acked = None
        self.status = "play"

    def snapshot(self):
        game = self.game
        packet = {
            "r": self.round,
            "p": [[p[key] for key in PLAYER_KEYS] for p in game.players],
            "s": [getattr(game, key) for key in STATE_KEYS],
            "z": self.paused,
            "v": self.rematch,
        }
        tag = (self.round, game.revision)
        if self.terrain_acked != tag:
            packet["t"] = [game.initial_surface, game.craters]
        self.terrain_sending = tag
        return json.dumps(packet).encode()

    def apply_snapshot(self, payload):
        data = json.loads(payload)
        if (not isinstance(data, dict) or not isinstance(data.get("r"), int)
                or not isinstance(data.get("p"), list) or len(data["p"]) != 2
                or any(not isinstance(p, list) or len(p) != len(PLAYER_KEYS)
                       for p in data["p"])
                or not isinstance(data.get("s"), list)
                or len(data["s"]) != len(STATE_KEYS)
                or data["s"][1] not in PHASES or data["s"][0] not in (0, 1)
                or data.get("z") not in (True, False)
                or not isinstance(data.get("v"), list) or len(data["v"]) != 2):
            raise ValueError("Invalid game snapshot")
        round_id = data["r"]
        if round_id < self.round_seen:
            return
        terrain = data.get("t")
        if self.game is None or round_id != self.round_seen:
            if terrain is None:
                raise ValueError("Missing new-round landscape")
            self.game = Game(False)
            self.game.revision = -1
        game = self.game
        revision = data["s"][8]
        if terrain is not None and (game.revision != revision or round_id != self.round_seen):
            tops, craters = terrain
            if (len(tops) != WIDTH or any(type(y) is not int or not 0 <= y <= FLOOR for y in tops)
                    or not isinstance(craters, list)
                    or any(not isinstance(c, list) or len(c) != 2 for c in craters)):
                raise ValueError("Invalid landscape")
            game.terrain = [bytearray(WIDTH) for _ in range(HEIGHT)]
            for x, top in enumerate(tops):
                for y in range(top, FLOOR):
                    game.terrain[y][x] = 1
            for x, y in craters:
                game.carve_crater(x, y)
            game.initial_surface = tops
            game.craters = craters
        elif game.revision != revision:
            raise ValueError("Missing changed landscape")
        game.players = [dict(zip(PLAYER_KEYS, p)) for p in data["p"]]
        for key, value in zip(STATE_KEYS, data["s"]):
            setattr(game, key, value)
        self.round_seen = round_id
        self.round = round_id
        self.paused = data["z"]
        self.rematch = data["v"]
        self.status = "play"

    def queue_snapshot(self):
        payload = self.snapshot()
        size = min(180, self.link.capacity() - 9)
        if size < 1:
            self.fail("Badge link packet capacity too small")
            return
        if len(payload) > MAX_PAYLOAD:
            self.fail("Match exceeds link snapshot limit")
            return
        if (len(payload) + size - 1) // size > MAX_PARTS:
            self.fail("Landscape exceeds link fragment limit")
            return
        self.sequence += 1
        self.outgoing = [b"S" + struct.pack("<IHH", self.sequence, index // size,
                         (len(payload) + size - 1) // size) + payload[index:index + size]
                         for index in range(0, len(payload), size)]
        self.outgoing_part = 0
        self.outgoing_at = self.time
        self.outgoing_started = self.time
        self.snapshot_at = self.time
        self.snapshot_tag = (self.round, self.game.turn, self.game.phase, self.paused)

    def stream(self):
        if self.outgoing:
            if self.time - self.outgoing_started > TIMEOUT:
                self.fail("Game sync timed out; pair again")
                return
            if self.time - self.outgoing_at >= RETRY:
                self.outgoing_part = 0
                self.outgoing_at = self.time
            for _ in range(4):
                if self.outgoing_part >= len(self.outgoing):
                    break
                if not self.send(self.outgoing[self.outgoing_part]):
                    break
                self.outgoing_part += 1
                self.outgoing_at = self.time

    def receive_snapshot(self, message):
        if len(message) <= 9:
            self.fail("Invalid snapshot packet")
            return
        sequence, index, total = struct.unpack("<IHH", message[1:9])
        if not 0 < total <= MAX_PARTS or index >= total:
            self.fail("Invalid snapshot fragment")
            return
        if sequence <= self.received_sequence:
            self.send(b"K" + struct.pack("<I", sequence))
            return
        if sequence < self.incoming_sequence:
            return
        if sequence != self.incoming_sequence:
            self.incoming_sequence = sequence
            self.incoming_parts = {}
            self.incoming_total = total
        if total != self.incoming_total:
            self.fail("Inconsistent snapshot fragments")
            return
        self.incoming_parts[index] = message[9:]
        if sum(len(part) for part in self.incoming_parts.values()) > MAX_PAYLOAD:
            self.fail("Snapshot too large")
            return
        if len(self.incoming_parts) == total:
            payload = b"".join(self.incoming_parts[i] for i in range(total))
            try:
                self.apply_snapshot(payload)
            except (ValueError, KeyError, TypeError, IndexError) as error:
                self.fail("Invalid peer state: %s" % error)
                return
            self.received_sequence = sequence
            self.incoming_parts = {}
            self.send(b"K" + struct.pack("<I", sequence))

    def button_action(self, player, buttons):
        if buttons & MENU:
            self.paused = not self.paused
            self.remote_axes = (0, 0)
            return
        if self.paused:
            if buttons & SELECT:
                self.paused = False
            return
        if self.game.phase == "over":
            if buttons & SELECT:
                self.rematch[player] = True
                if all(self.rematch):
                    self.new_round()
            return
        if self.game.active == player:
            controls(self.game, 0, 0, 0, buttons)

    def receive_input(self, message):
        if len(message) != 17:
            self.fail("Invalid controller packet")
            return
        sequence, round_id, turn, phase, horizontal, vertical, buttons = struct.unpack(
            "<IIIBbbB", message[1:])
        if horizontal not in (-1, 0, 1) or vertical not in (-1, 0, 1) or buttons > 7:
            self.fail("Invalid controller values")
            return
        self.send(b"J" + struct.pack("<I", sequence))
        if sequence <= self.input_received:
            return
        self.input_received = sequence
        if round_id != self.round or turn != self.game.turn:
            return
        if phase != PHASES.index(self.game.phase):
            return
        self.remote_axes = (horizontal, vertical)
        self.remote_until = self.time + 0.35
        self.button_action(1, buttons)

    def handle(self, message):
        if not message:
            return
        kind = message[:1]
        if kind == b"A":
            if message[1:] != PROTOCOL:
                self.fail("Different game versions; update both badges")
                return
            self.peer_accepted = True
        elif kind == b"P":
            self.send(b"Q")
        elif kind == b"Q":
            pass
        elif kind == b"X":
            self.fail("Other player left")
        elif self.host and self.game is not None:
            if kind == b"K" and len(message) == 5:
                sequence = struct.unpack("<I", message[1:])[0]
                if self.outgoing and sequence == self.sequence:
                    self.outgoing = None
                    self.terrain_acked = self.terrain_sending
            elif kind == b"I":
                self.receive_input(message)
        elif not self.host:
            if kind == b"S":
                self.receive_snapshot(message)
            elif kind == b"J" and len(message) == 5 and self.input_pending:
                if struct.unpack("<I", message[1:])[0] == self.input_sequence:
                    self.input_pending = None
                    self.message = ""

    def update(self, now, dt, horizontal=0, vertical=0, buttons=0):
        dt = max(0, min(dt, 0.1))
        self.time += dt
        self.link.pump()
        linked = self.link.linked
        if self.status == "error":
            return
        if linked and not self.linked_before:
            self.status = "offer"
            self.host = bool(self.link.central)
            self.local_player = 0 if self.host else 1
            self.heard_at = self.time
        elif not linked and self.linked_before:
            self.fail("Connection lost; return and pair again")
            return
        self.linked_before = linked
        if not linked:
            self.proximity.update(now)
        else:
            for message in self.link.receive():
                self.heard_at = self.time
                self.handle(message)
                if self.status == "error":
                    return
            if self.time - self.heard_at > TIMEOUT:
                self.fail("Other badge stopped responding")
                return
            if self.time - self.ping_at >= 0.7:
                self.send(b"P")
                self.ping_at = self.time
            if self.status == "offer" and buttons & SELECT:
                self.accepted = True
                buttons = 0
            if self.accepted and self.time - self.hello_at >= 0.4:
                self.send(b"A" + PROTOCOL)
                self.hello_at = self.time
            if self.accepted and self.peer_accepted and self.status == "offer":
                self.status = "sync"
                if self.host:
                    self.new_round()
            if self.host and self.game:
                self.button_action(0, buttons if self.status == "play" else 0)
                if not self.paused:
                    if self.game.active == 0:
                        controls(self.game, dt, horizontal, vertical, 0)
                    elif self.time < self.remote_until:
                        controls(self.game, dt, *self.remote_axes, 0)
                    self.game.update(dt)
                tag = (self.round, self.game.turn, self.game.phase, self.paused)
                if not self.outgoing and (self.time - self.snapshot_at >= 0.12
                                          or tag != self.snapshot_tag):
                    self.queue_snapshot()
                self.stream()
            elif not self.host and self.status == "play":
                # Retry edge-triggered actions until acknowledged. Axis-only
                # updates are disposable; their lease expires if the link stalls.
                if buttons and self.input_pending:
                    self.message = "Waiting for previous control"
                elif not self.input_pending and (buttons or self.time - self.input_at >= 0.1):
                    self.input_sequence += 1
                    packet = b"I" + struct.pack("<IIIBbbB", self.input_sequence,
                        self.round, self.game.turn, PHASES.index(self.game.phase),
                        horizontal, vertical, buttons)
                    if buttons:
                        self.input_pending = packet
                        self.input_started = self.time
                    self.send(packet)
                    self.input_at = self.time
                if self.input_pending and self.time - self.input_at >= 0.2:
                    if self.time - self.input_started > TIMEOUT:
                        self.fail("Control sync timed out; pair again")
                        return
                    self.send(self.input_pending)
                    self.input_at = self.time
        self.link.update()
