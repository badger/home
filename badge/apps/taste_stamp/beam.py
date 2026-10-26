# IR beaming for Taste Stamp: one NEC frame per verdict or prompt.
#
# Each message is a single command byte on address 0x53, sent as a short
# burst. The NEC protocol already carries a checksum for the address and
# the command. Beams only reach badges that are running Taste Stamp, since
# the receiver is bound by this app.
#
# The Badge Simulator has no IR hardware. Every IR call is guarded, so the
# app runs there and reports that the beam was only simulated.

ADDRESS = 0x53
TX_PIN = 16
# Leave PIO0 state machine 0 to the badge's IR receiver.
TX_PIO = 0
TX_SM = 1

VERDICT = 1
PROMPT = 2
VERDICT_BASE = 0x00
PROMPT_BASE = 0x40

BURST = 3
FRAME_MS = 77
GAP_MS = 90
ECHO_MS = 350
DEDUPE_MS = 1200
INBOX_LIMIT = 16


def encode(kind, index):
    if kind == VERDICT:
        return VERDICT_BASE + index
    return PROMPT_BASE + index


def decode(cmd, verdict_count, prompt_count):
    # Returns (kind, index), or None for anything this app didn't send.
    if VERDICT_BASE <= cmd < VERDICT_BASE + verdict_count:
        return (VERDICT, cmd - VERDICT_BASE)
    if PROMPT_BASE <= cmd < PROMPT_BASE + prompt_count:
        return (PROMPT, cmd - PROMPT_BASE)
    return None


LIGHT_MS = 600
LIGHT_STEP_MS = 75


def lights(t):
    # Case-light chase while a beam goes out or comes in, t ms after it
    # starts, or None once it has finished.
    if t < 0 or t >= LIGHT_MS:
        return None
    lit = int(t // LIGHT_STEP_MS) % 4
    levels = []
    for i in range(4):
        levels.append(1.0 if i == lit else 0.1)
    return tuple(levels)


def make_sender():
    try:
        from aye_arr.nec import NECSender
        tx = NECSender(TX_PIN, TX_PIO, TX_SM)
    except Exception:
        return None
    try:
        tx.start()
    except Exception:
        stop_sender(tx)
        return None
    return tx


def stop_sender(tx):
    # Releases the state machine and its PIO program memory, so a later
    # launch can claim them again.
    try:
        tx.stop()
    except Exception:
        pass


def listen(handler):
    # Binds the 0x53 receiver and routes every valid command byte to
    # handler. Returns True when IR receiving is available.
    try:
        from badgeware.ir import ir
    except Exception:
        return False
    try:
        from aye_arr.nec.remotes.descriptor import RemoteDescriptor
        base = RemoteDescriptor
    except Exception:
        base = object

    def ignore(key):
        pass

    class VerdictBeam(base):
        NAME = "TasteStamp"
        ADDRESS = 0x53
        BUTTON_CODES = {}

        def __init__(self):
            try:
                super().__init__()
            except Exception:
                pass
            self.on_any = handler
            self.on_known = ignore

    try:
        bound = ir.bind(VerdictBeam())
        if bound is not None:
            bound.on_any = handler
            bound.on_known = ignore
        return True
    except Exception:
        return False


def stop_listening():
    try:
        from badgeware.ir import ir
        ir.close()
    except Exception:
        pass


class Beam:
    # Queues outgoing bursts one frame per update and filters incoming
    # frames for echoes and repeats.

    def __init__(self, verdict_count, prompt_count, sender=None, receiving=False):
        self.verdict_count = verdict_count
        self.prompt_count = prompt_count
        self.tx = sender
        self.receiving = receiving
        self.queue = []
        self.next_due = 0
        self.last_send = None
        # A fixed buffer, so the IR callback never allocates memory.
        self.inbox = [0] * INBOX_LIMIT
        self.count = 0
        self.last_cmd = None
        self.last_seen = 0

    def can_send(self):
        return self.tx is not None

    def busy(self):
        return len(self.queue) > 0

    def send(self, kind, index, now):
        # Queues a burst. Returns False when there is no IR transmitter.
        if self.tx is None:
            return False
        cmd = encode(kind, index)
        self.queue = [cmd] * BURST
        # Keep the gap after a frame that has only just gone out.
        self.next_due = max(now, self.next_due)
        return True

    def pump(self, now):
        # Sends at most one queued frame. Returns False if the send failed.
        if not self.queue or now < self.next_due:
            return True
        cmd = self.queue.pop(0)
        try:
            self.tx.send_addr_cmd(ADDRESS, cmd)
        except Exception:
            self.queue = []
            stop_sender(self.tx)
            self.tx = None
            return False
        self.last_send = now
        self.last_cmd = cmd
        self.last_seen = now
        self.next_due = now + FRAME_MS + GAP_MS
        return True

    def heard(self, cmd):
        # IR callback: only record the byte; update() does the work.
        count = self.count
        if count < INBOX_LIMIT:
            self.inbox[count] = cmd
            self.count = count + 1

    def receive(self, now):
        # Returns the newest new (kind, index) message, or None.
        count = self.count
        if count == 0:
            return None
        frames = self.inbox[:count]
        self.count = 0
        if self.queue or (self.last_send is not None and now - self.last_send < ECHO_MS):
            return None
        found = None
        for cmd in frames:
            if cmd == self.last_cmd and now - self.last_seen < DEDUPE_MS:
                self.last_seen = now
                continue
            message = decode(cmd, self.verdict_count, self.prompt_count)
            if message is None:
                continue
            self.last_cmd = cmd
            self.last_seen = now
            found = message
        return found

    def close(self):
        if self.tx is not None:
            stop_sender(self.tx)
            self.tx = None
        if self.receiving:
            stop_listening()
            self.receiving = False
