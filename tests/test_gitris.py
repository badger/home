import contextlib
import io
from pathlib import Path
import types
import unittest
from unittest.mock import patch


APP = Path(__file__).resolve().parents[1] / "badge/apps/gitris/__init__.py"
BUTTONS = ("LEFT", "RIGHT", "UP", "DOWN", "SELECT", "MENU", "BACK", "HOME")


class Badge:
    ticks_delta = 0

    def __init__(self):
        self.presses = set()
        self.holds = set()

    def mode(self, mode):
        self.display_mode = mode

    def pressed(self, button):
        return button in self.presses

    def held(self, button):
        return button in self.holds


class Screen:
    width, height = 320, 240

    def __init__(self):
        self.rectangles = []
        self.texts = []

    def rectangle(self, x, y, width, height):
        self.rectangles.append((x, y, width, height))

    def text(self, text, x, y):
        self.texts.append((text, x, y))

    def measure_text(self, text):
        return len(text) * 6, 8


class GitrisTests(unittest.TestCase):
    def setUp(self):
        self.badge = Badge()
        self.screen = Screen()
        self.saved = {}
        self.callbacks = []
        self.save_error = False

        def load(key, values):
            values.update(self.saved.get(key, {}))

        def save(key, values):
            if self.save_error:
                raise OSError("test storage failure")
            self.saved[key] = dict(values)

        state = types.SimpleNamespace(load=load, save=save)
        module = types.ModuleType("badgeware")
        module.State = state
        self.runtime = {
            "badge": self.badge,
            "screen": self.screen,
            "color": types.SimpleNamespace(rgb=lambda *values: values),
            "font": types.SimpleNamespace(nope="nope", ignore="ignore"),
            "HIRES": 1,
            "VSYNC": 2,
            "run": self.callbacks.append,
        }
        self.runtime.update({"BUTTON_" + name: name for name in BUTTONS})
        with patch.dict("sys.modules", {"badgeware": module}), patch("os.chdir"):
            exec(compile(APP.read_text(), str(APP), "exec"), self.runtime)
        self.state = self.runtime["state"]

    def call(self, name, *args):
        return self.runtime[name](*args)

    def frame(self, milliseconds=16, pressed=(), held=()):
        self.badge.ticks_delta = milliseconds
        self.badge.presses = set(pressed)
        self.badge.holds = set(held)
        self.call("update")

    def start(self):
        self.frame(pressed=("SELECT",))
        self.state["conflict_every"] = 0

    def test_title_and_runtime_registration(self):
        self.assertEqual(len(self.callbacks), 1)
        self.frame()
        self.assertEqual(self.state["screen"], "title")
        self.assertIn("GITRIS", [item[0] for item in self.screen.texts])

    def test_all_shapes_and_rotations_fit_the_board(self):
        self.start()
        for piece in range(7):
            self.state["curr"] = piece
            for rotation in range(4):
                self.assertFalse(self.call("_collides", 3, 0, rotation))
                self.assertEqual(len(set(self.call("_cells_at", 3, 0, rotation))), 4)

    def test_bag_contains_every_piece_once(self):
        for _ in range(20):
            self.assertEqual(sorted(self.call("_refill_bag")), list(range(7)))

    def test_left_and_right_pressed_and_held_repeat(self):
        self.start()
        self.state["curr"] = 1
        x = self.state["x"]
        self.frame(pressed=("LEFT",))
        self.assertEqual(self.state["x"], x - 1)
        self.frame(100, held=("LEFT",))
        self.assertEqual(self.state["x"], x - 1)
        self.frame(60, held=("LEFT",))
        self.assertEqual(self.state["x"], x - 2)
        self.frame(pressed=("RIGHT",))
        self.assertEqual(self.state["x"], x - 1)

    def test_sideways_movement_cannot_leave_the_board(self):
        self.start()
        for direction in (-1, 1):
            for _ in range(30):
                self.call("_move", direction, 0)
            self.assertFalse(self.call("_collides", self.state["x"], self.state["y"], self.state["rot"]))
            self.assertTrue(all(0 <= x < 10 for x, _ in self.call("_cells_at", self.state["x"], self.state["y"], self.state["rot"])))

    def test_rotation_is_bound_to_up(self):
        self.start()
        self.state["curr"] = 2
        self.frame(pressed=("UP",))
        self.assertEqual(self.state["rot"], 1)

    def test_gravity_waits_for_the_fall_interval(self):
        self.start()
        self.frame(799)
        self.assertEqual(self.state["y"], 0)
        self.frame(1)
        self.assertEqual(self.state["y"], 1)

    def test_soft_drop_scores_and_locks_at_the_floor(self):
        self.start()
        pieces = self.state["pieces"]
        self.frame(pressed=("DOWN",))
        self.assertEqual(self.state["y"], 1)
        self.assertEqual(self.state["score"], 1)
        for _ in range(22):
            self.frame(65, held=("DOWN",))
        self.assertGreater(self.state["pieces"], pieces)
        self.assertTrue(any(any(row) for row in self.state["board"]))

    def test_select_hard_drops_exactly_one_piece(self):
        self.start()
        pieces = self.state["pieces"]
        self.frame(pressed=("SELECT",))
        self.assertEqual(self.state["pieces"], pieces + 1)
        self.assertEqual(sum(bool(value) for row in self.state["board"] for value in row), 4)
        self.frame(held=("SELECT",))
        self.assertEqual(self.state["pieces"], pieces + 1)

    def test_menu_pauses_and_select_resumes_without_catching_up(self):
        self.start()
        self.frame(pressed=("MENU",))
        y = self.state["y"]
        self.frame(5000)
        self.assertEqual(self.state["screen"], "pause")
        self.assertEqual(self.state["y"], y)
        self.frame(pressed=("SELECT",))
        self.frame()
        self.assertEqual(self.state["screen"], "play")
        self.assertEqual(self.state["y"], y)

    def test_back_pauses_then_returns_to_title(self):
        self.start()
        self.frame(pressed=("BACK",))
        self.assertEqual(self.state["screen"], "pause")
        self.frame(pressed=("BACK",))
        self.assertEqual(self.state["screen"], "title")
        self.frame(pressed=("SELECT",))
        self.assertEqual(self.state["score"], 0)

    def test_line_clear_score_and_level(self):
        self.start()
        self.state["board"][-1] = [1] * 10
        self.state["lines"] = 9
        self.call("_clear_lines")
        self.assertEqual(self.state["score"], 40)
        self.assertEqual(self.state["lines"], 10)
        self.assertEqual(self.state["level"], 2)
        self.assertEqual(self.state["fall_ms"], 740)
        self.assertEqual(len(self.state["board"]), 20)
        self.assertFalse(any(self.state["board"][0]))

    def test_four_line_clear(self):
        self.start()
        self.state["board"][-4:] = [[1] * 10 for _ in range(4)]
        self.call("_clear_lines")
        self.assertEqual(self.state["score"], 1200)
        self.assertEqual(self.state["lines"], 4)

    def test_conflict_row_has_one_gap(self):
        self.start()
        self.assertTrue(self.call("_push_conflict_row"))
        row = self.state["board"][-1]
        self.assertEqual(row.count(0), 1)
        self.assertEqual(row.count(8), 9)

    def test_conflict_row_does_not_discard_occupied_top_row(self):
        self.start()
        self.state["board"][0][0] = 1
        self.assertFalse(self.call("_push_conflict_row"))
        self.assertEqual(self.state["screen"], "gameover")

    def test_high_score_is_saved(self):
        self.start()
        self.state["score"] = 321
        self.call("_to_gameover")
        self.assertEqual(self.saved["gitris"]["hiscore"], 321)
        self.assertEqual(self.state["screen"], "gameover")

    def test_storage_failure_is_reported_without_crashing(self):
        self.start()
        self.state["score"] = 100
        self.save_error = True
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.call("_to_gameover")
        self.assertIn("high score could not be saved", output.getvalue())
        self.frame()
        self.assertIn("High score could not be saved.", [item[0] for item in self.screen.texts])

    def test_every_screen_and_rectangle_stays_in_display(self):
        self.start()
        for mode in ("title", "play", "pause", "gameover"):
            self.state["screen"] = mode
            self.frame()
        for x, y, width, height in self.screen.rectangles:
            self.assertGreaterEqual(x, 0)
            self.assertGreaterEqual(y, 0)
            self.assertLessEqual(x + width, 320)
            self.assertLessEqual(y + height, 240)
        for text, x, y in self.screen.texts:
            self.assertGreaterEqual(x, 0, text)
            self.assertGreaterEqual(y, 0, text)
            self.assertLess(y, 240, text)


if __name__ == "__main__":
    unittest.main()
