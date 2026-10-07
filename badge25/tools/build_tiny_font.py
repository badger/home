from pathlib import Path
import struct


GLYPHS = {
    "A": (2, 5, 7, 5, 5), "B": (6, 5, 6, 5, 6),
    "C": (3, 4, 4, 4, 3), "D": (6, 5, 5, 5, 6),
    "E": (7, 4, 6, 4, 7), "F": (7, 4, 6, 4, 4),
    "G": (3, 4, 5, 5, 3), "H": (5, 5, 7, 5, 5),
    "I": (7, 2, 2, 2, 7), "J": (1, 1, 1, 5, 2),
    "K": (5, 5, 6, 5, 5), "L": (4, 4, 4, 4, 7),
    "M": (5, 7, 7, 5, 5), "N": (5, 7, 7, 7, 5),
    "O": (2, 5, 5, 5, 2), "P": (6, 5, 6, 4, 4),
    "Q": (2, 5, 5, 3, 1), "R": (6, 5, 6, 5, 5),
    "S": (3, 4, 2, 1, 6), "T": (7, 2, 2, 2, 2),
    "U": (5, 5, 5, 5, 7), "V": (5, 5, 5, 5, 2),
    "W": (5, 5, 7, 7, 5), "X": (5, 5, 2, 5, 5),
    "Y": (5, 5, 2, 2, 2), "Z": (7, 1, 2, 4, 7),
    "0": (7, 5, 5, 5, 7), "1": (2, 6, 2, 2, 7),
    "2": (6, 1, 2, 4, 7), "3": (6, 1, 2, 1, 6),
    "4": (5, 5, 7, 1, 1), "5": (7, 4, 6, 1, 6),
    "6": (3, 4, 6, 5, 2), "7": (7, 1, 2, 2, 2),
    "8": (2, 5, 2, 5, 2), "9": (2, 5, 3, 1, 6),
    " ": (0, 0, 0, 0, 0), ".": (0, 0, 0, 0, 2),
    ",": (0, 0, 0, 2, 4), ":": (0, 2, 0, 2, 0),
    "-": (0, 0, 7, 0, 0), "=": (0, 7, 0, 7, 0),
    "/": (1, 1, 2, 4, 4), "?": (6, 1, 2, 0, 2),
    "!": (2, 2, 2, 0, 2), "%": (5, 1, 2, 4, 5),
    "(": (1, 2, 2, 2, 1), ")": (4, 2, 2, 2, 4),
}


def build():
    codepoints = range(32, 127)
    header = b"ppf!" + struct.pack(">HIHH", 0, 95, 4, 5)
    header += b"Compact 5".ljust(32, b"\0")
    table = bytearray()
    pixels = bytearray()
    for codepoint in codepoints:
        char = chr(codepoint)
        table.extend(struct.pack(">IH", codepoint, 0 if char == " " else 3))
        pixels.extend(row << 5 for row in GLYPHS.get(char.upper(), GLYPHS["?"]))
    return header + table + pixels


if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1] / "apps" / "sensor_dashboard" / "tiny.ppf"
    target.write_bytes(build())
