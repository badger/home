# IR beaming for Taste Stamp: one NEC frame per verdict or prompt.
#
# Each message is a single command byte on address 0x53. The NEC protocol
# already carries a checksum for the address and the command.

ADDRESS = 0x53
TX_PIN = 16
# Leave PIO0 state machine 0 to the badge's IR receiver.
TX_PIO = 0
TX_SM = 1

VERDICT = 1
PROMPT = 2
VERDICT_BASE = 0x00
PROMPT_BASE = 0x40


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
