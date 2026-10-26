"""Mona DNA over infrared: NEC frames out of GPIO16, in through GPIO17.

Each NEC frame carries one byte, so a Mona travels as a short packet of
frames on address 0x4C:

    0xA5 0x5A LEN payload... CRC8

The payload is a version byte (2), the 19 DNA bytes (each below 0x80), then
the GitHub handle as ASCII (empty for a mystery Mona). CRC8 uses polynomial 0x07
over LEN and the payload. The receiver keeps a rolling window of bytes and
accepts a packet only when its sync, length, CRC, version and handle all
check out, so a dropped frame just means the second copy, or the next press,
gets through. An 8 character handle takes about six seconds to beam.

After two copies the beam sends command 0x88 on address 0x45, the Universe
quest beacon code. The quest app counts it as Quest 8 "Octocat Generator" and
the menu's Mona's Expedition as "Level Up Lounge". The beacon reset code 0xF0
is never sent.

Sending blocks for about 77 ms a frame, so the app sends at most one frame
per update. Without a working NEC sender (the simulator has none) the beam is
simulated with the same pacing so the rest of the app still works.
"""

import mona_dna

DNA_ADDRESS = 0x4C
QUEST_ADDRESS = 0x45
QUEST_CODE = 0x88
QUEST_NUMBER = 8
QUEST_KEY = "quest"

VERSION = 2
SYNC_A = 0xA5
SYNC_B = 0x5A
MIN_LEN = 1 + mona_dna.SIZE
MAX_LEN = MIN_LEN + mona_dna.MAX_HANDLE

TX_PIN = 16
RX_PIN = 17
# PIO0 SM0 is left for the receiver
TX_SLOTS = ((0, 1), (0, 2), (0, 3))

FRAME_MS = 80
COPIES = 2
COPY_GAP_MS = 250
QUEST_GAP_MS = 250
QUEST_REPEATS = 3
GAP_MS = 1200
DEDUPE_MS = 15000
ECHO_MS = 400
WINDOW = 64
INBOX_MAX = 160

try:
    from aye_arr.nec.remotes.descriptor import RemoteDescriptor as _Remote
except Exception:
    _Remote = object


class DnaRemote(_Remote):
    NAME = "AsciiMonaDNA"
    ADDRESS = DNA_ADDRESS
    BUTTON_CODES = {}

    def __init__(self):
        # the base sets up the button map the receiver looks codes up in
        super().__init__()
        self.on_any = None
        self.on_known = None


class QuestRemote(_Remote):
    NAME = "AsciiMonaQuest"
    ADDRESS = QUEST_ADDRESS
    BUTTON_CODES = {}

    def __init__(self):
        super().__init__()
        self.on_any = None
        self.on_known = None


def crc8(data):
    crc = 0
    for byte in data:
        crc ^= byte & 0xFF
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x07) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


def encode_packet(handle, dna):
    """The frame bytes for one copy of a Mona."""
    handle = handle or ""
    if handle and not mona_dna.valid_handle(handle):
        raise ValueError("not a GitHub handle")
    if not mona_dna.valid_dna(dna):
        raise ValueError("not Mona DNA")
    body = [0, VERSION] + list(dna)
    for ch in handle:
        body.append(ord(ch))
    body[0] = len(body) - 1
    return [SYNC_A, SYNC_B] + body + [crc8(body)]


def parse_payload(payload):
    """(handle, dna) from a payload, or None."""
    n = len(payload)
    if n < MIN_LEN or n > MAX_LEN or payload[0] != VERSION:
        return None
    dna = tuple(payload[1:MIN_LEN])
    if not mona_dna.valid_dna(dna):
        return None
    chars = []
    for index in range(MIN_LEN, n):
        byte = payload[index]
        if byte < 33 or byte > 126:
            return None
        chars.append(chr(byte))
    handle = "".join(chars)
    if handle and not mona_dna.valid_handle(handle):
        return None
    return handle, dna


def beam_frames(handle, dna):
    """(address, command, wait ms before it) for everything one press sends."""
    packet = encode_packet(handle, dna)
    frames = []
    for copy in range(COPIES):
        for index in range(len(packet)):
            wait = COPY_GAP_MS if copy and index == 0 else 0
            frames.append((DNA_ADDRESS, packet[index], wait))
    for index in range(QUEST_REPEATS):
        frames.append((QUEST_ADDRESS, QUEST_CODE, QUEST_GAP_MS if index == 0 else 0))
    return frames


class Decoder:
    """Finds packets in the byte stream from the DNA address."""

    def __init__(self):
        self.window = []
        self.last = None
        self.seen = None
        self.seen_at = 0

    def reset(self):
        self.window = []
        self.last = None

    def push(self, byte, now):
        """Add one received byte; returns (handle, dna) for a new Mona."""
        if self.last is not None and now - self.last > GAP_MS:
            self.window = []
        self.last = now
        window = self.window
        window.append(byte & 0xFF)
        if len(window) > WINDOW:
            del window[0]
        found = self._scan()
        if found is None:
            return None
        self.window = []
        key = (found[0].lower(), found[1])
        if self.seen == key and now - self.seen_at < DEDUPE_MS:
            return None
        self.seen = key
        self.seen_at = now
        return found

    def _scan(self):
        window = self.window
        n = len(window)
        for start in range(n - 3):
            if window[start] != SYNC_A or window[start + 1] != SYNC_B:
                continue
            length = window[start + 2]
            if length < MIN_LEN or length > MAX_LEN or start + 4 + length != n:
                continue
            if crc8(window[start + 2:n - 1]) != window[n - 1]:
                continue
            found = parse_payload(window[start + 3:n - 1])
            if found is not None:
                return found
        return None


class Beam:
    """The frames for one press, paced one per update."""

    def __init__(self, handle, dna, live):
        self.handle = handle or ""
        self.dna = dna
        self.frames = beam_frames(handle, dna)
        self.live = live
        self.index = 0
        self.next_at = None
        self.error = ""

    @property
    def done(self):
        return self.index >= len(self.frames)

    def progress(self):
        """Percent sent, 0 to 100."""
        return self.index * 100 // len(self.frames)

    def in_quest(self):
        return not self.done and self.frames[self.index][0] == QUEST_ADDRESS

    def step(self, now, send):
        """Send the next frame when it is due; True when one went out."""
        if self.done or (self.next_at is not None and now - self.next_at < 0):
            return False
        address, command, _ = self.frames[self.index]
        if send is not None:
            try:
                send(address, command)
            except Exception as err:
                self.error = "IR send failed: %s" % err
                self.index = len(self.frames)
                return False
        self.index += 1
        wait = self.frames[self.index][2] if self.index < len(self.frames) else 0
        self.next_at = now + FRAME_MS + wait
        return True


def mark_quest(state_api, number=QUEST_NUMBER):
    """Record a quest the way the quest app does; True when newly completed."""
    data = {"completed": []}
    try:
        state_api.load(QUEST_KEY, data)
    except Exception:
        pass
    done = data.get("completed")
    if not isinstance(done, list):
        done = []
        data["completed"] = done
    if number in done:
        return False
    done.append(number)
    try:
        state_api.save(QUEST_KEY, data)
    except Exception:
        return False
    return True


class IrPort:
    """Owns the NEC sender and the badgeware.ir binds for the app's lifetime."""

    def __init__(self):
        self.tx = None
        self.tx_tried = False
        self.ir = None
        self.listening = False
        self.inbox = []
        self.quest_hits = 0
        self.decoder = Decoder()
        self.beam = None
        self.quiet_until = None
        self.note = ""

    # Receiver callbacks only record what arrived; update() does the work.
    def on_dna(self, command):
        if len(self.inbox) < INBOX_MAX:
            self.inbox.append(command)

    def on_quest(self, command):
        if command == QUEST_CODE:
            self.quest_hits += 1

    def listen(self):
        try:
            from badgeware.ir import ir
        except Exception:
            self.note = "IR receive unavailable"
            return False
        bound = 0
        for remote, handler in ((DnaRemote(), self.on_dna), (QuestRemote(), self.on_quest)):
            try:
                remote.on_any = handler
                bound_remote = ir.bind(remote)
                if bound_remote is not None and bound_remote is not remote:
                    bound_remote.on_any = handler
                bound += 1
            except Exception:
                pass
        self.ir = ir
        self.listening = bound > 0
        if not self.listening:
            self.note = "IR receive busy"
        return self.listening

    def open_sender(self):
        if self.tx_tried:
            return self.tx is not None
        self.tx_tried = True
        try:
            from aye_arr.nec import NECSender
        except Exception:
            self.note = "IR send unavailable: simulated beam"
            return False
        for pio, sm in TX_SLOTS:
            tx = None
            try:
                tx = NECSender(TX_PIN, pio, sm)
                tx.start()
                self.tx = tx
                return True
            except Exception:
                _stop(tx)
        self.note = "IR send busy: simulated beam"
        return False

    @property
    def beaming(self):
        return self.beam is not None and not self.beam.done

    def start_beam(self, handle, dna):
        if self.beaming:
            return False
        live = self.open_sender()
        self.beam = Beam(handle, dna, live)
        self.decoder.reset()
        return True

    def send(self, address, command):
        self.tx.send_addr_cmd(address, command)

    def quiet(self, now):
        if self.beaming:
            return True
        return self.quiet_until is not None and now - self.quiet_until < 0

    def update(self, now):
        """Advance the beam and decode what arrived; returns a list of events.

        Events are ("sent", ok, error), ("mona", handle, dna) and ("quest",).
        """
        events = []
        beam = self.beam
        if beam is not None and not beam.done:
            beam.step(now, self.send if beam.live and self.tx is not None else None)
            if beam.done:
                self.quiet_until = now + ECHO_MS
                events.append(("sent", not beam.error, beam.error))
        if self.inbox or self.quest_hits:
            inbox = self.inbox
            self.inbox = []
            hits = self.quest_hits
            self.quest_hits = 0
            if self.quiet(now):
                # our own frames bouncing back
                self.decoder.reset()
            else:
                for byte in inbox:
                    found = self.decoder.push(byte, now)
                    if found is not None:
                        events.append(("mona", found[0], found[1]))
                if hits:
                    events.append(("quest",))
        return events

    def close(self):
        self.beam = None
        _stop(self.tx)
        self.tx = None
        if self.ir is not None:
            try:
                self.ir.close()
            except Exception:
                pass
            self.ir = None
        self.listening = False


def _stop(tx):
    if tx is None:
        return
    try:
        tx.stop()
    except Exception:
        pass
