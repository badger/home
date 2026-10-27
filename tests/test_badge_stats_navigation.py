"""Host-side checks for the 2026 Badge app's stats and logical controls."""

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


APP = Path(__file__).resolve().parents[1] / "badge/apps/badge/__init__.py"


class BadgeStatsNavigationTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(APP.read_text())
        definitions = [node for node in tree.body
                       if isinstance(node, (ast.ClassDef, ast.FunctionDef))
                       and node.name in ("User", "update")]
        self.pressed = set()
        self.held = set()
        self.badge = SimpleNamespace(
            pressed=lambda button: button in self.pressed,
            held=lambda button: button in self.held,
        )
        self.ns = dict(
            badge=self.badge, color=Mock(), shape=Mock(), screen=Mock(width=320, height=240),
            tilt=Mock(), black=0, phosphor=1, white=2,
            STATS_VIEW=0, NAME_VIEW=1, PROFILE_VIEW=2, VIEW_COUNT=3,
            TILE_SIZE=33, mona_sans=Mock(), HANDLE_SIZE=28,
            NAME_SIZE=16, LABEL_SIZE=14, AVATAR_SIZE=150,
            center_text=Mock(), placeholder_if_none=lambda text: text,
            handle="example", contact_name="", linkedin="", view=0,
        )
        for name in ("LEFT", "RIGHT", "UP", "DOWN", "SELECT"):
            self.ns["BUTTON_" + name] = name
        exec(compile(ast.Module(body=definitions, type_ignores=[]), str(APP), "exec"), self.ns)
        self.user = self.ns["User"]("example")
        self.user.name = "Example"
        for value, (_, field) in enumerate(self.user.STATS):
            setattr(self.user, field, value)
        self.user.draw_stat = Mock()
        self.user.draw_avatar = Mock()
        self.user.fetch_step = Mock(return_value=None)
        self.ns["user"] = self.user

    def rows(self):
        self.user.draw_stat.reset_mock()
        self.user.draw_stats_view(None)
        return [(call.args[0], call.args[1])
                for call in self.user.draw_stat.call_args_list]

    def tick(self, *buttons):
        self.pressed = set(buttons)
        self.user.draw = Mock()
        self.ns["update"]()

    def test_original_stats_then_additional_stats(self):
        self.assertEqual(self.rows(), [("Followers", 0), ("Contribs", 1), ("Repos", 2)])
        self.user.scroll_stats(1)
        self.assertEqual(self.rows(), [("Contribs", 1), ("Repos", 2), ("Best Day", 3)])
        self.user.scroll_stats(1)
        self.assertEqual(self.rows(), [("Repos", 2), ("Best Day", 3), ("Yrs on GH", 4)])

    def test_scrolling_stops_at_both_ends(self):
        self.user.scroll_stats(-1)
        self.assertEqual(self.user.stats_offset, 0)
        for _ in range(10):
            self.user.scroll_stats(1)
        self.assertEqual(self.user.stats_offset, 2)
        for _ in range(10):
            self.user.scroll_stats(-1)
        self.assertEqual(self.user.stats_offset, 0)

    def test_scroll_indicators_match_available_directions(self):
        for offset, arrows in ((0, ["v"]), (1, ["^", "v"]), (2, ["^"])):
            self.user.stats_offset = offset
            self.ns["screen"].text.reset_mock()
            self.rows()
            self.assertEqual([call.args[0] for call in self.ns["screen"].text.call_args_list],
                             arrows)

    def test_vertical_buttons_scroll_without_changing_view(self):
        self.tick("DOWN")
        self.assertEqual((self.ns["view"], self.user.stats_offset), (0, 1))
        self.tick("UP")
        self.assertEqual((self.ns["view"], self.user.stats_offset), (0, 0))

    def test_horizontal_buttons_wrap_views_and_preserve_scroll(self):
        self.tick("DOWN")
        self.tick("LEFT")
        self.assertEqual(self.ns["view"], 2)
        self.tick("DOWN")
        self.assertEqual(self.user.stats_offset, 1)
        self.tick("RIGHT")
        self.assertEqual((self.ns["view"], self.user.stats_offset), (0, 1))

    def test_refresh_chord_does_not_change_view_or_scroll(self):
        self.ns["view"] = 2
        self.user.stats_offset = 1
        self.user.update = Mock()
        self.held = {"LEFT", "RIGHT"}
        self.tick("LEFT", "RIGHT")
        self.user.update.assert_called_once_with(True)
        self.assertEqual((self.ns["view"], self.user.stats_offset), (2, 1))

    def test_select_still_animates_avatar(self):
        self.user.animate_avatar = Mock()
        self.tick("SELECT")
        self.user.animate_avatar.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
