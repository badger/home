"""Validate and clean the GitHub handles that seed ASCII Mona's DNA."""

MAX_HANDLE = 39
HANDLE_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
PREFIXES = ("https://", "http://", "www.", "github.com/", "@")


def handle_problem(text):
    """Why text is not a GitHub handle, or "" when it is one.

    No regex: MicroPython's re reads {1,39} as literal braces.
    """
    if not isinstance(text, str) or not text:
        return "type a handle"
    if len(text) > MAX_HANDLE:
        return "39 characters max"
    for ch in text:
        if ch not in HANDLE_CHARS:
            return "letters, digits and - only"
    if text[0] == "-" or text[-1] == "-":
        return "no - at either end"
    if "--" in text:
        return "no double hyphens"
    return ""


def valid_handle(text):
    return handle_problem(text) == ""


def clean_handle(text):
    """"@Mona", "github.com/mona" or a profile URL become "mona"; junk becomes ""."""
    if isinstance(text, (bytes, bytearray)):
        try:
            text = bytes(text).decode()
        except UnicodeError:
            return ""
    if not isinstance(text, str):
        return ""
    text = text.strip()
    for prefix in PREFIXES:
        if text.lower().startswith(prefix):
            text = text[len(prefix):]
    for stop in "/?#":
        cut = text.find(stop)
        if cut >= 0:
            text = text[:cut]
    text = text.strip()
    if handle_problem(text):
        return ""
    return text.lower()


def clean_text(text, limit):
    """Printable ASCII the badge fonts can draw, trimmed to limit.

    Square brackets become parentheses because the vector font has no glyphs
    for them.
    """
    if isinstance(text, (bytes, bytearray)):
        try:
            text = bytes(text).decode()
        except UnicodeError:
            return ""
    if not isinstance(text, str):
        return ""
    out = []
    for ch in text:
        if ch == "[":
            out.append("(")
        elif ch == "]":
            out.append(")")
        elif ch == "\n" or ch == "\t":
            out.append(" ")
        elif " " <= ch <= "~":
            out.append(ch)
    return "".join(out).strip()[:limit]
