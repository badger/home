"""Arcade character wheel for typing a GitHub handle with the badge buttons.

UP and DOWN spin the letter under the cursor (hold to spin fast), LEFT and
RIGHT move the cursor, and RIGHT past the last letter adds a slot. MENU
deletes the slot under the cursor, and blank slots are dropped when the
handle is entered. SELECT accepts a valid handle; BACK cancels.

The wheel only sees button names ("up", "down", "left", "right", "select",
"back", "menu"), so the app maps logical badge buttons onto it and the tests
can drive it without a badge.
"""

import mona_dna

CHARS = " abcdefghijklmnopqrstuvwxyz0123456789-"
BLANK = 0
REPEAT_DELAY_MS = 350
REPEAT_MS = 80
MOVES = ("up", "down", "left", "right")


class Wheel:
    def __init__(self, text=""):
        self.slots = [BLANK]
        self.cursor = 0
        self.repeat = None
        self.repeat_at = 0
        self.nudge = ""
        self.load(text)

    def load(self, text):
        slots = []
        if isinstance(text, str):
            for ch in text.lower():
                index = CHARS.find(ch)
                if index > BLANK:
                    slots.append(index)
        self.slots = slots[:mona_dna.MAX_HANDLE] or [BLANK]
        self.cursor = len(self.slots) - 1
        self.repeat = None
        self.nudge = ""

    @property
    def text(self):
        return "".join(CHARS[index] for index in self.slots if index != BLANK)

    @property
    def problem(self):
        return mona_dna.handle_problem(self.text)

    def letter(self, offset=0):
        """The character offset steps around the wheel from the cursor."""
        return CHARS[(self.slots[self.cursor] + offset) % len(CHARS)]

    def window(self, count):
        """(first slot index, slots) for a view count slots wide."""
        first = self.cursor - count // 2
        first = max(0, min(first, len(self.slots) - count))
        return first, self.slots[first:first + count]

    def spin(self, step):
        self.slots[self.cursor] = (self.slots[self.cursor] + step) % len(CHARS)
        self.nudge = ""

    def left(self):
        if self.cursor == 0:
            return
        if self.cursor == len(self.slots) - 1 and self.slots[self.cursor] == BLANK:
            self.slots.pop()
        self.cursor -= 1

    def right(self):
        if self.cursor < len(self.slots) - 1:
            self.cursor += 1
        elif self.slots[self.cursor] != BLANK and len(self.slots) < mona_dna.MAX_HANDLE:
            self.slots.append(BLANK)
            self.cursor += 1

    def delete(self):
        if len(self.slots) > 1:
            self.slots.pop(self.cursor)
            self.cursor = min(self.cursor, len(self.slots) - 1)
        else:
            self.slots[0] = BLANK
        self.nudge = ""

    def _move(self, name):
        if name == "up":
            self.spin(1)
        elif name == "down":
            self.spin(-1)
        elif name == "left":
            self.left()
        elif name == "right":
            self.right()

    def update(self, now, pressed, held):
        """One frame of input; returns "done", "cancel" or None."""
        for name in MOVES:
            if name in pressed:
                self._move(name)
                self.repeat = name
                self.repeat_at = now + REPEAT_DELAY_MS
        if self.repeat is not None:
            if self.repeat not in held:
                self.repeat = None
            elif now >= self.repeat_at:
                self._move(self.repeat)
                self.repeat_at = now + REPEAT_MS
        if "menu" in pressed:
            self.delete()
        if "back" in pressed:
            return "cancel"
        if "select" in pressed:
            problem = self.problem
            if problem:
                self.nudge = problem
                return None
            return "done"
        return None
