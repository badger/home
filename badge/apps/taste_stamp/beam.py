# IR beaming for Taste Stamp: one NEC frame per verdict or prompt.
#
# Each message is a single command byte on address 0x53. The NEC protocol
# already carries a checksum for the address and the command.

ADDRESS = 0x53

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
