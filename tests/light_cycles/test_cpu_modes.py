import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


def load_game():
    source = Path(__file__).resolve().parents[2] / "badge/apps/light_cycles/__init__.py"
    tree = ast.parse(source.read_text())
    logic_start = next(node.lineno for node in tree.body if isinstance(node, ast.ClassDef))
    colors = {"BACKGROUND", "GRID", "CYAN", "WHITE", "ISO1_WHITE", "DIM", "INKS", "CPU_INKS"}
    # Load game logic without the badge runtime's imports and startup calls.
    tree.body = [
        node for node in tree.body
        if isinstance(node, (ast.Assign, ast.ClassDef))
        and (not isinstance(node, ast.Assign) or node.lineno < logic_start
             or isinstance(node.targets[0], ast.Name) and node.targets[0].id in colors)
    ]
    namespace = {"color": SimpleNamespace(rgb=lambda r, g, b: (r, g, b))}
    exec(compile(tree, str(source), "exec"), namespace)
    return namespace


class CpuModesTest(unittest.TestCase):
    def setUp(self):
        self.runtime = load_game()
        for button in ("BACK", "UP", "DOWN", "SELECT", "RIGHT", "LEFT"):
            self.runtime["BUTTON_" + button] = button
        self.badge = Mock()
        self.badge.pressed.return_value = False
        self.runtime["badge"] = self.badge
        self.game = self.runtime["LightCycles"]()

    def press(self, button, now=0):
        self.badge.pressed.side_effect = lambda candidate: candidate == button
        self.game.update(now)

    def draw_log(self):
        screen = Mock()
        texts, rectangles = [], []
        screen.text.side_effect = lambda text, x, y: texts.append((text, screen.pen))
        screen.rectangle.side_effect = lambda x, y, w, h: rectangles.append((x, y, w, h, screen.pen))
        self.runtime.update(
            screen=screen,
            font=SimpleNamespace(bacteria=object(), futile=object()),
            centre=Mock(),
        )
        self.game.draw(0)
        return texts, rectangles

    def test_cpu_selection_defaults_to_two_bots_and_can_choose_one(self):
        self.press("SELECT")
        self.assertEqual(self.game.mode, "cpu_menu")
        self.assertEqual(self.game.cpu_choice, 1)
        self.press("UP")
        self.press("SELECT", 100)
        self.assertEqual(self.game.mode, "countdown")
        self.assertEqual(self.game.arena.count, 2)
        self.assertEqual(len(self.game.arena.riders), 2)
        self.assertEqual(self.game.arena.scores, [0, 0])

    def test_back_returns_from_cpu_selection_to_main_menu(self):
        self.press("SELECT")
        self.press("BACK")
        self.assertEqual(self.game.mode, "menu")
        self.assertIsNone(self.game.arena)

    def test_both_formats_step_only_the_selected_bots(self):
        for choice in (0, 1):
            with self.subTest(choice=choice):
                self.game.cpu_choice = choice
                self.game.cpu(0)
                arena = self.game.arena
                arena.bot = Mock(wraps=arena.bot)
                self.badge.pressed.return_value = False
                self.game.update(self.runtime["COUNTDOWN_MS"])
                self.assertEqual(arena.tick, 1)
                self.assertEqual(
                    [call.args[0] for call in arena.bot.call_args_list],
                    list(range(1, choice + 2)),
                )
                self.assertEqual(self.game.mode, "play")

    def test_round_and_match_reset_preserve_selected_format(self):
        for choice in (0, 1):
            with self.subTest(choice=choice):
                self.game.cpu_choice = choice
                self.game.cpu(0)
                self.game.arena.scores[1] = 2
                self.game.new_cpu_round(100)
                self.assertEqual(self.game.arena.scores[1], 2)
                self.game.arena.scores[1] = self.runtime["TARGET"]
                self.game.new_cpu_round(200)
                self.assertEqual(self.game.arena.scores, [0] * (choice + 2))
                self.assertEqual(len(self.game.arena.riders), choice + 2)

    def test_cpu_selection_draws_without_an_arena(self):
        self.runtime["BACKGROUND"] = 0
        self.runtime["screen"] = Mock()
        self.game.draw_menu = Mock()
        self.press("SELECT")
        self.game.draw(0)
        self.game.draw_menu.assert_called_once_with(0)

    def test_cpu_scoreboard_and_riders_use_requested_names_and_colors(self):
        expected = {
            0: [
                ("USER 3", (0, 235, 255)),
                ("ISO2 1", (255, 187, 42)),
            ],
            1: [
                ("USER 3", (0, 235, 255)),
                ("ISO1 1", (255, 255, 255)),
                ("ISO2 2", (255, 187, 42)),
            ],
        }
        for choice in (0, 1):
            with self.subTest(choice=choice):
                self.game.cpu_choice = choice
                self.game.cpu(0)
                self.game.arena.scores = [3, 1] if choice == 0 else [3, 1, 2]
                self.game.mode = "play"
                texts, rectangles = self.draw_log()
                self.assertEqual(texts, expected[choice])
                for i, (x, y, _, _) in enumerate(self.game.arena.riders):
                    left = self.runtime["LEFT"] + x * self.runtime["CELL"]
                    top = self.runtime["TOP"] + y * self.runtime["CELL"]
                    self.assertIn((left, top, 5, 5, expected[choice][i][1]), rectangles)
                    head_color = self.runtime["BACKGROUND"] if expected[choice][i][1] == (255, 255, 255) else self.runtime["WHITE"]
                    self.assertIn((left + 1, top + 1, 3, 3, head_color), rectangles)

    def test_cpu_round_and_match_results_name_the_winner(self):
        self.game.cpu(0)
        self.game.mode = "over"
        self.game.panel = Mock()
        for winner, match_over, title in (
            (-1, False, "DRAW"),
            (0, False, "USER WINS"),
            (1, False, "ISO1 WINS"),
            (2, False, "ISO2 WINS"),
            (2, True, "ISO2 WINS MATCH"),
        ):
            with self.subTest(winner=winner, match_over=match_over):
                self.game.arena.winner = winner
                self.game.arena.scores = [0, 0, 0]
                if match_over:
                    self.game.arena.scores[winner] = self.runtime["TARGET"]
                self.game.panel.reset_mock()
                self.draw_log()
                prompt = "SELECT: NEW MATCH" if match_over else "SELECT: NEXT ROUND"
                self.game.panel.assert_called_once_with(title, prompt)

    def test_one_v_one_winner_is_iso2(self):
        self.game.cpu_choice = 0
        self.game.cpu(0)
        self.game.mode = "over"
        self.game.arena.winner = 1
        self.game.panel = Mock()
        self.draw_log()
        self.game.panel.assert_called_once_with("ISO2 WINS", "SELECT: NEXT ROUND")

    def test_nearby_colors_and_names_are_unchanged(self):
        self.game.network = True
        self.game.arena = self.runtime["Arena"](2)
        self.game.local = 1
        self.game.mode = "play"
        texts, rectangles = self.draw_log()
        self.assertEqual(texts, [("RIVAL 0", (0, 235, 255)), ("YOU 0", (255, 65, 183))])
        x, y, _, _ = self.game.arena.riders[1]
        left = self.runtime["LEFT"] + x * self.runtime["CELL"]
        top = self.runtime["TOP"] + y * self.runtime["CELL"]
        self.assertIn((left, top, 5, 5, (255, 65, 183)), rectangles)
        self.assertIn((left + 1, top + 1, 3, 3, self.runtime["WHITE"]), rectangles)
        self.game.mode = "over"
        self.game.arena.winner = 1
        self.game.panel = Mock()
        self.draw_log()
        self.game.panel.assert_called_once_with("YOU WIN", "SELECT: NEXT ROUND")


if __name__ == "__main__":
    unittest.main()
