"""Badge-to-badge Pocket Rivals battles, checked with fake paired links."""

from pathlib import Path
import random
import sys
import unittest


APP = Path(__file__).resolve().parents[1] / "badge" / "apps" / "monster_battle"
sys.path.insert(0, str(APP))

import duel as duel_module  # noqa: E402
from duel import Duel  # noqa: E402
from monster_rules import Battle, Rng, first_actor  # noqa: E402


class Partner:
    def __init__(self, ident, name):
        self.id = ident
        self.name = name


class FakeLink:
    def __init__(self, central, ident, name):
        self.central = central
        self.id = ident
        self.name = name
        self.peer = None
        self.linked = False
        self.inbox = []
        self.fail_sends = 0
        self.closed = False

    @property
    def partner(self):
        if not self.linked or self.peer is None:
            return None
        return Partner(self.peer.id, self.peer.name)

    def send(self, message):
        if not self.linked or self.fail_sends:
            self.fail_sends = max(0, self.fail_sends - 1)
            return False
        self.peer.inbox.append(bytes(message))
        return True

    def receive(self):
        messages, self.inbox = self.inbox, []
        return messages

    def pump(self):
        pass

    def update(self):
        pass

    def leave(self):
        for link in (self, self.peer):
            link.linked = False
            link.inbox = []

    def close(self):
        self.closed = True
        self.leave()


class FakeProximity:
    def __init__(self):
        self.rested = []

    def update(self, now):
        pass

    def rest(self, ident, now):
        self.rested.append(ident)

    def clear(self):
        pass


def pair(host_creature=0, guest_creature=1, seed=7):
    host_link = FakeLink(True, b"host", "Host")
    guest_link = FakeLink(False, b"guest", "Guest")
    host_link.peer, guest_link.peer = guest_link, host_link
    host = Duel(host_link, FakeProximity(), host_creature, random.Random(seed))
    guest = Duel(guest_link, FakeProximity(), guest_creature, random.Random(seed + 1))
    return host, guest


class Clock:
    now = 0


def step(clock, *duels, frames=3):
    for _ in range(frames):
        clock.now += 16
        for duel in duels:
            duel.update(clock.now)


def connect(host, guest, clock):
    host.link.linked = guest.link.linked = True
    step(clock, host, guest)


def start(host, guest, clock):
    connect(host, guest, clock)
    host.accept()
    guest.accept()
    step(clock, host, guest)


class RulesHelperTests(unittest.TestCase):
    def test_rng_is_deterministic_and_in_range(self):
        first, second = Rng(1234), Rng(1234)
        rolls = [first.randint(-2, 2) for _ in range(200)]
        self.assertEqual(rolls, [second.randint(-2, 2) for _ in range(200)])
        self.assertEqual(set(rolls), {-2, -1, 0, 1, 2})
        self.assertEqual(Rng(0).state, 1)

    def test_mend_has_priority_otherwise_coin_decides(self):
        self.assertEqual(first_actor((3, 0), 1), 0)
        self.assertEqual(first_actor((1, 3), 0), 1)
        self.assertEqual(first_actor((3, 3), 1), 1)
        self.assertEqual(first_actor((0, 2), 0), 0)

    def test_turn_stops_after_knockout(self):
        battle = Battle(0, 1, Rng(5))
        battle.hp[1] = 1
        events = battle.turn(0, (0, 0))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][2][1], 0)
        self.assertEqual(battle.winner(), 0)


class DuelTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()

    def test_handshake_shares_creatures_and_starts_matching_battles(self):
        host, guest = pair(2, 0)
        connect(host, guest, self.clock)
        self.assertEqual((host.state, guest.state), ("offer", "offer"))
        self.assertEqual((host.their_creature, guest.their_creature), (0, 2))
        self.assertEqual(guest.partner_name, "Host")
        host.accept()
        step(self.clock, host, guest)
        self.assertEqual(guest.state, "offer")
        self.assertTrue(guest.their_accept)
        guest.accept()
        step(self.clock, host, guest)
        self.assertEqual((host.state, guest.state), ("battle", "battle"))
        self.assertEqual(host.battle.creatures, (2, 0))
        self.assertEqual(guest.battle.creatures, (2, 0))
        self.assertEqual((host.me, guest.me), (0, 1))
        self.assertEqual(host.battle.rng.state, guest.battle.rng.state)

    def test_full_battle_stays_in_sync(self):
        host, guest = pair(0, 1, seed=11)
        start(host, guest, self.clock)
        picker = random.Random(3)
        host_events, guest_events = [], []
        for _ in range(60):
            if host.state == "over":
                break
            host.choose(picker.randint(0, 3) if host.battle.mends[0] else picker.randint(0, 2))
            self.assertTrue(host.waiting())
            guest.choose(picker.randint(0, 3) if guest.battle.mends[1] else picker.randint(0, 2))
            step(self.clock, host, guest)
            host_events += host.take_events()
            guest_events += guest.take_events()
        self.assertEqual(host.state, "over")
        self.assertEqual(guest.state, "over")
        self.assertEqual(host_events, guest_events)
        self.assertEqual(host.battle.hp, guest.battle.hp)
        self.assertEqual(host.battle.mends, guest.battle.mends)
        self.assertIsNotNone(host.battle.winner())

    def test_mend_goes_first(self):
        host, guest = pair(0, 1)
        start(host, guest, self.clock)
        host.battle.hp[0] = guest.battle.hp[0] = 40
        host.choose(0)
        guest.choose(3)
        step(self.clock, host, guest)
        events = guest.take_events()
        self.assertEqual(events[0][0], 1)
        self.assertEqual(events[0][1][3], "heal")
        self.assertEqual(events, host.take_events())

    def test_host_sanitizes_impossible_guest_move(self):
        host, guest = pair(0, 1)
        start(host, guest, self.clock)
        host.battle.mends[1] = 0
        host.choose(1)
        host.handle(b"M\x00\x03", self.clock.now)
        events = host.take_events()
        self.assertIn("Quick Hit", [event for actor, event, _ in events if actor == 1][0][0])

    def test_stale_turn_messages_are_ignored(self):
        host, guest = pair(0, 1)
        start(host, guest, self.clock)
        guest.handle(b"T\x05\x00\x00\x00", self.clock.now)
        self.assertEqual(guest.turn, 0)
        self.assertEqual(guest.take_events(), [])
        host.handle(b"M\x09\x00", self.clock.now)
        self.assertIsNone(host.moves[1])

    def test_decline_returns_both_to_lobby(self):
        host, guest = pair()
        connect(host, guest, self.clock)
        guest.decline(self.clock.now)
        step(self.clock, host, guest)
        self.assertEqual((host.state, guest.state), ("lobby", "lobby"))
        self.assertFalse(host.link.linked)
        self.assertEqual(guest.proximity.rested, [b"host"])

    def test_offer_times_out(self):
        host, guest = pair()
        connect(host, guest, self.clock)
        self.clock.now += duel_module.OFFER_MS + 1
        host.update(self.clock.now)
        self.assertEqual(host.state, "lobby")
        self.assertEqual(host.message, "Nobody accepted in time.")

    def test_disconnect_mid_battle(self):
        host, guest = pair()
        start(host, guest, self.clock)
        host.link.linked = guest.link.linked = False
        step(self.clock, host, guest)
        self.assertEqual((host.state, guest.state), ("lobby", "lobby"))
        self.assertEqual(guest.message, "Your rival walked away.")
        self.assertIsNone(guest.battle)

    def test_rematch_starts_new_battle(self):
        host, guest = pair()
        start(host, guest, self.clock)
        first = host.battle
        host.battle.hp[1] = guest.battle.hp[1] = 1
        host.choose(0)
        guest.choose(0)
        step(self.clock, host, guest)
        self.assertEqual((host.state, guest.state), ("over", "over"))
        host.rematch()
        step(self.clock, host, guest)
        self.assertEqual(host.state, "over")
        self.assertTrue(guest.their_again)
        guest.rematch()
        step(self.clock, host, guest)
        self.assertEqual((host.state, guest.state), ("battle", "battle"))
        self.assertIsNot(host.battle, first)
        self.assertEqual((host.battle_id, guest.battle_id), (2, 2))
        self.assertEqual(host.battle.hp, guest.battle.hp)

    def test_failed_sends_are_retried_in_order(self):
        host, guest = pair(1, 2)
        host.link.fail_sends = 2
        guest.link.fail_sends = 2
        connect(host, guest, self.clock)
        host.accept()
        guest.accept()
        step(self.clock, host, guest, frames=8)
        self.assertEqual((host.state, guest.state), ("battle", "battle"))
        self.assertEqual(guest.battle.creatures, (1, 2))
        self.assertEqual(host.outbox, [])


if __name__ == "__main__":
    unittest.main()
