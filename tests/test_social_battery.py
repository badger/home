import os
import runpy
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


APP = Path(__file__).resolve().parents[1] / "badge" / "apps" / "social_battery" / "__init__.py"


class Screen:
    width = 160
    height = 120
    clip = (0, 0, 160, 120)

    def __init__(self):
        self.texts = []

    def rectangle(self, *args):
        pass

    def measure_text(self, text):
        return len(text) * 6, 9

    def text(self, text, *args):
        self.texts.append(text)


class Badge:
    actions = ()

    def pressed(self, button):
        return button in self.actions


class SocialBatteryTests(unittest.TestCase):
    def load_app(self, stored=None):
        screen = Screen()
        badge = Badge()
        saved = []

        class State:
            @staticmethod
            def load(key, state):
                self.assertEqual(key, "social_battery")
                if stored is not None:
                    state.update(stored)

            @staticmethod
            def save(key, state):
                self.assertEqual(key, "social_battery")
                saved.append(dict(state))

        badgeware = types.ModuleType("badgeware")
        badgeware.State = State
        globals_ = {
            "badge": badge,
            "screen": screen,
            "color": types.SimpleNamespace(rgb=lambda *rgb: rgb),
            "font": types.SimpleNamespace(nope="nope", ziplock="ziplock"),
            "BUTTON_UP": "up",
            "BUTTON_DOWN": "down",
            "run": lambda update: None,
        }
        original_path = sys.path[:]
        try:
            with patch.dict(sys.modules, {"badgeware": badgeware}), patch.object(os, "chdir"):
                app = runpy.run_path(str(APP), init_globals=globals_)
        finally:
            sys.path[:] = original_path
        return app, badge, screen, saved

    def test_controls_bounds_and_messages(self):
        app, badge, screen, saved = self.load_app()
        self.assertEqual(app["state"]["level"], 60)

        for _ in range(7):
            badge.actions = ("down",)
            app["update"]()
        self.assertEqual(app["state"]["level"], 0)
        self.assertEqual(len(saved), 6)
        self.assertIn("RECHARGING", screen.texts)
        self.assertIn("Not up for chatting now", screen.texts)

        for _ in range(11):
            badge.actions = ("up",)
            app["update"]()
        self.assertEqual(app["state"]["level"], 100)
        self.assertEqual(len(saved), 16)
        self.assertIn("READY TO CONNECT", screen.texts)
        self.assertIn("100%", screen.texts)

    def test_saved_level_restores_and_invalid_level_is_reported(self):
        app, badge, _, saved = self.load_app({"level": 20})
        self.assertEqual(app["state"]["level"], 20)
        badge.actions = ("down",)
        app["update"]()
        self.assertEqual(saved, [{"level": 10}])
        restored, _, _, _ = self.load_app(saved[-1])
        self.assertEqual(restored["state"]["level"], 10)

        with patch("builtins.print") as output:
            invalid, _, _, _ = self.load_app({"level": 999})
        self.assertEqual(invalid["state"]["level"], 60)
        output.assert_called_once()


if __name__ == "__main__":
    unittest.main()
