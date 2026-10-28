"""Badge-to-badge battles over the firmware's badgeware.link radio layer.

The central badge is the host. Both badges replay the same seeded Battle,
indexed host=0 and guest=1, so only the moves need to cross the link.

Messages (all far below the link's per-message capacity):
  H<creature>                 announce my creature after linking
  A / D                       accept / decline (or leave)
  S<seed:4><host><guest>      host starts a battle
  M<turn><move>               guest's move for a turn
  T<turn><first><host><guest> host's resolved turn
  R                           ask for a rematch
"""

import random
import struct

from monster_rules import Battle, CREATURES, Rng, first_actor


OFFER_MS = 20000


class Duel:
    def __init__(self, link, proximity, creature, rand=None):
        self.link = link
        self.proximity = proximity
        self.creature = creature
        self.rand = rand if rand is not None else random
        self.state = "lobby"
        self.state_at = 0
        self.message = ""
        self.outbox = []
        self.was_linked = False
        self.battle_id = 0
        self.reset_match()

    def reset_match(self):
        self.their_creature = None
        self.my_accept = False
        self.their_accept = False
        self.battle = None
        self.turn = 0
        self.moves = [None, None]
        self.events = []
        self.my_again = False
        self.their_again = False

    @property
    def me(self):
        return 0 if self.link.central else 1

    @property
    def partner_name(self):
        partner = self.link.partner
        return partner.name if partner else "Rival badge"

    def set_state(self, state, now):
        self.state = state
        self.state_at = now

    def queue(self, message):
        self.outbox.append(message)

    def flush(self):
        while self.outbox:
            if not self.link.send(self.outbox[0]):
                return
            self.outbox.pop(0)

    def leave(self, now, message=""):
        partner = self.link.partner
        self.proximity.rest(partner.id if partner else None, now)
        self.link.leave()
        self.was_linked = False
        self.outbox = []
        self.message = message
        self.reset_match()
        self.set_state("lobby", now)

    def close(self):
        self.link.close()

    def update(self, now):
        link = self.link
        link.pump()
        linked = link.linked
        if linked and not self.was_linked:
            if self.state == "lobby":
                self.reset_match()
                self.outbox = []
                self.message = ""
                self.queue(b"H" + bytes((self.creature,)))
                self.set_state("offer", now)
            else:
                link.leave()
                linked = False
        if self.was_linked and not linked and self.state != "lobby":
            self.proximity.clear()
            self.outbox = []
            self.message = "Your rival walked away."
            self.reset_match()
            self.set_state("lobby", now)
        self.was_linked = linked

        if linked:
            for message in link.receive():
                self.handle(bytes(message), now)
                if self.state == "lobby":
                    break

        if self.state == "lobby":
            self.proximity.update(now)
        elif self.state == "offer":
            if (self.my_accept and self.their_accept and link.central
                    and self.their_creature is not None):
                self.start_battle(now)
            elif now - self.state_at > OFFER_MS:
                self.queue(b"D")
                self.flush()
                self.leave(now, "Nobody accepted in time.")
        elif self.state == "over":
            if self.my_again and self.their_again and link.central:
                self.start_battle(now)

        if self.state != "lobby":
            self.flush()
        link.update()

    def handle(self, message, now):
        kind = message[:1]
        body = message[1:]
        central = self.link.central
        if kind == b"H" and len(body) == 1 and body[0] < len(CREATURES):
            self.their_creature = body[0]
        elif kind == b"A":
            self.their_accept = True
        elif kind == b"D":
            self.leave(now, "Your rival left.")
        elif kind == b"R":
            self.their_again = True
        elif kind == b"S" and len(body) == 6 and not central:
            seed = struct.unpack("<I", body[:4])[0]
            if body[4] < len(CREATURES) and body[5] < len(CREATURES):
                self.begin(seed, body[4], body[5], now)
        elif kind == b"M" and len(body) == 2 and central:
            if self.state == "battle" and body[0] == self.turn & 0xFF:
                self.moves[1] = body[1]
                self.resolve()
        elif kind == b"T" and len(body) == 4 and not central:
            if self.state == "battle" and body[0] == self.turn & 0xFF:
                self.apply(body[1], (body[2], body[3]))

    def accept(self):
        if self.state == "offer" and not self.my_accept:
            self.my_accept = True
            self.queue(b"A")

    def decline(self, now):
        if self.state != "lobby":
            self.queue(b"D")
            self.flush()
            self.leave(now)

    def rematch(self):
        if self.state == "over" and not self.my_again:
            self.my_again = True
            self.queue(b"R")

    def start_battle(self, now):
        seed = self.rand.getrandbits(32) or 1
        host, guest = self.creature, self.their_creature
        self.queue(b"S" + struct.pack("<I", seed) + bytes((host, guest)))
        self.begin(seed, host, guest, now)

    def begin(self, seed, host, guest, now):
        self.battle = Battle(host, guest, Rng(seed))
        self.battle_id += 1
        self.turn = 0
        self.moves = [None, None]
        self.events = []
        self.my_again = False
        self.their_again = False
        self.set_state("battle", now)

    def waiting(self):
        return self.state == "battle" and self.moves[self.me] is not None

    def choose(self, move):
        if self.state != "battle" or self.moves[self.me] is not None:
            return False
        if not self.battle.available(self.me, move):
            return False
        self.moves[self.me] = move
        if self.link.central:
            self.resolve()
        else:
            self.queue(b"M" + bytes((self.turn & 0xFF, move)))
        return True

    def resolve(self):
        host, guest = self.moves
        if host is None or guest is None:
            return
        if not self.battle.available(1, guest):
            guest = 0
        moves = (host, guest)
        first = first_actor(moves, self.rand.getrandbits(1))
        self.queue(b"T" + bytes((self.turn & 0xFF, first, host, guest)))
        self.apply(first, moves)

    def apply(self, first, moves):
        try:
            self.events.extend(self.battle.turn(first & 1, moves))
        except ValueError:
            self.battle.hp[1 - self.me] = 0
            self.events.append((self.me, ("Battle out of sync!", "Rematch to start fresh.", self.me, "miss"), tuple(self.battle.hp)))
        self.turn += 1
        self.moves = [None, None]
        if self.battle.winner() is not None:
            self.state = "over"

    def take_events(self):
        events = self.events
        self.events = []
        return events
