"""Swap Mona cards over the Bluetooth badge link (badgeware.link).

Hold two badges running ASCII Mona back to back, the proximity gesture
Contacts uses, and each badge sends the other its owner's card: GitHub
handle, Mona DNA and display name. There is no accept step; the swap starts
as soon as the link comes up, then the link lingers for a few seconds so a
SELECT press also shares the Mona on screen over the link as well as IR.

Messages reuse the Contacts chunking: kind, part index, part count, data.
"C" carries card chunks, "K" acknowledges a whole card, "S" carries a shared
Mona. The simulator's link is a stub that never links, so none of this runs
there and the rest of the app works without it.
"""

import json

import mona_dna

GAME = "ascii_mona"
SWAP_MS = 8000
LINGER_MS = 10000
CARD_VERSION = 2
MAX_NAME = 40

IDLE = 0
SWAP = 1
LINGER = 2


def clean_text(text, limit):
    return mona_dna.clean_text(text, limit)


def make_card(handle, dna, name=""):
    card = {"v": CARD_VERSION, "github": handle or "", "dna": mona_dna.dna_hex(dna)}
    name = clean_text(name, MAX_NAME)
    if name:
        card["name"] = name
    return card


def read_card(value):
    """(handle, dna, name) from a card dict, or None.

    Works for ASCII Mona cards and Contacts cards (which carry no DNA).
    """
    if not isinstance(value, dict):
        return None
    raw = value.get("github")
    handle = ""
    if isinstance(raw, str) and raw.strip():
        handle = mona_dna.clean_handle(raw)
        if handle and raw.strip().lower() == handle:
            handle = raw.strip()
    dna = mona_dna.parse_hex(value.get("dna"))
    if dna is None:
        if not handle:
            return None
        dna = mona_dna.dna_for(handle)
    return handle, dna, clean_text(value.get("name"), MAX_NAME)


def decode_card(data):
    try:
        return read_card(json.loads(data))
    except (ValueError, TypeError):
        return None


class Outbox:
    """One message split into link-sized chunks, resent until accepted."""

    def __init__(self, kind, payload):
        self.kind = kind
        self.payload = payload
        self.chunks = None
        self.sent = 0

    @property
    def done(self):
        return self.chunks is not None and self.sent >= len(self.chunks)

    def pump(self, link):
        if self.chunks is None:
            size = max(1, link.capacity() - 3)
            chunks = []
            for start in range(0, len(self.payload), size):
                chunks.append(self.payload[start:start + size])
            self.chunks = chunks[:255]
        while self.sent < len(self.chunks):
            message = self.kind + bytes((self.sent, len(self.chunks))) + self.chunks[self.sent]
            if not link.send(message):
                return False
            self.sent += 1
        return True


class Inbox:
    """Reassembles one chunked message."""

    def __init__(self):
        self.parts = {}
        self.total = 0

    def add(self, message):
        """Returns the whole payload once every part has arrived."""
        if len(message) < 3:
            return None
        index = message[1]
        total = message[2]
        if total == 0 or index >= total:
            return None
        if total != self.total:
            self.parts = {}
            self.total = total
        self.parts[index] = message[3:]
        if len(self.parts) < total:
            return None
        data = b"".join(self.parts[part] for part in range(total))
        self.parts = {}
        self.total = 0
        return data


class MonaLink:
    def __init__(self, card):
        self.card = card
        self.link = None
        self.prox = None
        self.state = IDLE
        self.since = 0
        self.was_linked = False
        self.partner_id = None
        self.partner_name = ""
        self.outbox = None
        self.share = None
        self.cards = Inbox()
        self.shares = Inbox()
        self.got = None
        self.acked = False
        self.ack_pending = False
        self.status = ""
        self.error = ""

    def open(self, module=None):
        if module is None:
            try:
                from badgeware import link as module
            except Exception:
                self.error = "badge link unavailable"
                return False
        try:
            self.link = module.Link(GAME)
            self.prox = module.Proximity(self.link)
        except Exception:
            self.link = None
            self.prox = None
            self.error = "badge link unavailable"
            return False
        return True

    @property
    def available(self):
        return self.link is not None

    @property
    def swapping(self):
        return self.state == SWAP

    @property
    def lingering(self):
        return self.state == LINGER and self.was_linked

    def set_card(self, card):
        self.card = card

    def update(self, now, idle):
        """Run the link for one frame.

        Returns ("card" or "share", handle, dna, name) when a Mona arrives.
        """
        if self.link is None:
            return None
        try:
            return self._update(now, idle)
        except Exception as err:
            self.error = "link error: %s" % err
            self._part(now)
            return None

    def _update(self, now, idle):
        link = self.link
        got = None
        link.pump()
        linked = bool(link.linked)
        if linked and not self.was_linked:
            if idle and self.state == IDLE:
                self._begin(now)
            else:
                link.leave()
                linked = False
        if self.was_linked and not linked:
            if self.state == SWAP:
                if self.got is not None:
                    got = ("card",) + self.got
                    self._rest(now)
                else:
                    self.status = "they walked away"
                    self._clear()
                self._reset()
            elif self.state == LINGER:
                self._rest(now)
                self._reset()
        self.was_linked = linked

        if linked:
            for message in link.receive():
                if self.state == IDLE:
                    continue
                found = self._handle(bytes(message))
                if found is not None:
                    got = found
            if self.ack_pending and link.send(b"K"):
                self.ack_pending = False

        if self.state == SWAP:
            self.outbox.pump(link)
            if self.got is not None and self.acked:
                got = ("card",) + self.got
                self.state = LINGER
                self.since = now
                self.status = "swapped"
            elif now - self.since > SWAP_MS:
                self.status = "swap failed, try again"
                self._part(now)
        elif self.state == LINGER:
            if self.share is not None and self.share.pump(link):
                self.share = None
            if now - self.since > LINGER_MS and self.share is None and not self.ack_pending:
                self._part(now)
        elif idle and self.prox is not None:
            self.prox.update(now)
        link.update()
        return got

    def _handle(self, message):
        kind = message[:1]
        if kind == b"K":
            self.acked = True
        elif kind == b"C":
            data = self.cards.add(message)
            if data is not None and self.got is None:
                card = decode_card(data)
                if card is not None:
                    self.got = card
                    self.ack_pending = True
        elif kind == b"S":
            data = self.shares.add(message)
            if data is not None:
                card = decode_card(data)
                if card is not None:
                    return ("share",) + card
        return None

    def _begin(self, now):
        partner = self.link.partner
        self.partner_id = partner.id if partner is not None else None
        self.partner_name = clean_text(partner.name, MAX_NAME) if partner is not None else ""
        self.state = SWAP
        self.since = now
        self.outbox = Outbox(b"C", json.dumps(self.card).encode())
        self.cards = Inbox()
        self.shares = Inbox()
        self.got = None
        self.acked = False
        self.ack_pending = False
        self.share = None
        self.status = "swapping"
        self.error = ""

    def share_mona(self, handle, dna, name, now):
        """Also send the Mona on screen while the link lingers after a swap."""
        if self.link is None or not self.lingering:
            return False
        self.share = Outbox(b"S", json.dumps(make_card(handle, dna, name)).encode())
        self.since = now
        return True

    def _rest(self, now):
        if self.prox is not None:
            try:
                self.prox.rest(self.partner_id, now)
            except Exception:
                pass

    def _clear(self):
        if self.prox is not None:
            try:
                self.prox.clear()
            except Exception:
                pass

    def _part(self, now):
        self._rest(now)
        if self.link is not None:
            try:
                self.link.leave()
            except Exception:
                pass
        self._reset()

    def _reset(self):
        self.state = IDLE
        self.outbox = None
        self.share = None
        self.got = None
        self.acked = False
        self.ack_pending = False
        self.partner_id = None

    def lights(self, now, idle):
        """Case light levels for this frame, or None to leave them to the app."""
        if self.link is None:
            return None
        if self.state == SWAP:
            return (0.5,)
        if idle and self.state == IDLE and self.prox is not None:
            try:
                return self.prox.lights(now)
            except Exception:
                return None
        return None

    def hint(self, now):
        """(text, progress or None) describing the link, or None."""
        if self.link is None:
            return None
        if self.state == SWAP:
            return ("swapping with " + (self.partner_name or "a badge"), None)
        if self.lingering:
            return ("linked: SELECT shares by link too", None)
        try:
            if self.prox.syncing() is not None:
                return ("hold steady", self.prox.progress(now))
            if self.prox.cooling(now) is not None:
                return ("pull apart to swap again", None)
        except Exception:
            return None
        return None

    def close(self):
        if self.link is None:
            return
        try:
            self.link.close()
        except Exception:
            pass
        self.link = None
        self.prox = None
