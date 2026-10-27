"""Small JSON contract shared by the badge and local editor service."""

THEMES = {
    "lime": (211, 250, 55),
    "blue": (93, 182, 255),
    "pink": (255, 143, 193),
}
DEFAULT = {
    "title": "Hello, Universe",
    "message": "Your next conversation starts here.",
    "theme": "lime",
}


def validate(value):
    if not isinstance(value, dict):
        raise ValueError("Card must be an object")
    result = {}
    for key, limit in (("title", 32), ("message", 160)):
        text = value.get(key)
        if not isinstance(text, str) or not text.strip() or len(text) > limit:
            raise ValueError("%s must contain 1-%d characters" % (key, limit))
        if any(ord(char) < 32 or ord(char) > 126 for char in text):
            raise ValueError("%s must use printable ASCII characters" % key)
        result[key] = text.strip()
    if value.get("theme") not in THEMES:
        raise ValueError("Choose lime, blue, or pink")
    result["theme"] = value["theme"]
    return result


def validate_page(value):
    if not isinstance(value, dict) or not isinstance(value.get("messages"), list):
        raise ValueError("History must contain a messages list")
    if len(value["messages"]) > 10:
        raise ValueError("History page exceeds 10 messages")
    cursor = value.get("next_cursor")
    if cursor is not None and (not isinstance(cursor, str) or not cursor or len(cursor) > 512):
        raise ValueError("Invalid history cursor")
    messages = []
    ids = set()
    for entry in value["messages"]:
        card = validate(entry)
        for key, limit in (("id", 128), ("name", 32), ("created_at", 32)):
            text = entry.get(key)
            if not isinstance(text, str) or not text.strip() or len(text) > limit:
                raise ValueError("Invalid history " + key)
            if any(ord(char) < 32 or ord(char) > 126 for char in text):
                raise ValueError("Invalid history " + key)
            card[key] = text
        if card["id"] in ids:
            raise ValueError("Duplicate message ID")
        ids.add(card["id"])
        messages.append(card)
    if not messages and cursor is not None:
        raise ValueError("Empty history page cannot have a next cursor")
    return {"messages": messages, "next_cursor": cursor}


def encode_cursor(value):
    return "".join(chr(byte) if (65 <= byte <= 90 or 97 <= byte <= 122
                                or 48 <= byte <= 57 or byte in (45, 46, 95, 126))
                   else "%%%02X" % byte for byte in value.encode())


def wrap(text, width, measure):
    lines = []
    line = ""
    for word in text.split():
        candidate = line + (" " if line else "") + word
        if measure(candidate) <= width:
            line = candidate
            continue
        if line:
            lines.append(line)
            line = ""
        for character in word:
            if line and measure(line + character) > width:
                lines.append(line)
                line = ""
            line += character
    if line:
        lines.append(line)
    return lines
