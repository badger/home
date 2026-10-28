import builtins
import importlib.util
from pathlib import Path
import types
import unittest


MODULE = Path(__file__).resolve().parents[1] / "badge/flip_buttons.py"
ACTIONS = ("UP", "DOWN", "LEFT", "RIGHT", "SELECT", "BACK", "MENU", "HOME")


class Group:
    def __init__(self):
        self.down = set()
        self.just = set()

    def held(self, button=None):
        return set(self.down) if button is None else button in self.down

    def pressed(self, button=None):
        return set(self.just) if button is None else button in self.just

    def released(self, button=None):
        return set() if button is None else False


class Badge:
    def __init__(self):
        self.buttons = Group()
        self.pad = Group()
        self.rotated = False

    def rotate_180(self):
        return self.rotated

    def held(self, button=None):
        both = self.buttons.held() | self.pad.held()
        return both if button is None else button in both

    def pressed(self, button=None):
        both = self.buttons.pressed() | self.pad.pressed()
        return both if button is None else button in both

    def released(self, button=None):
        return set() if button is None else False

    def direction(self):
        return types.SimpleNamespace(x="firmware", y="firmware")


class FlipButtonsTests(unittest.TestCase):
    def setUp(self):
        self.saved = {}
        globals_ = {"BUTTON_" + name: name for name in ACTIONS}
        globals_["vec2"] = lambda x, y: types.SimpleNamespace(x=x, y=y)
        self.badge = globals_["badge"] = Badge()
        for name, value in globals_.items():
            self.saved[name] = getattr(builtins, name, None)
            setattr(builtins, name, value)
        spec = importlib.util.spec_from_file_location("flip_buttons", MODULE)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.physical = self.badge.buttons
        self.module.install()

    def tearDown(self):
        for name, value in self.saved.items():
            if value is None:
                delattr(builtins, name)
            else:
                setattr(builtins, name, value)

    def test_upright_input_is_unchanged(self):
        self.physical.down = {"UP"}
        self.assertTrue(self.badge.held("UP"))
        self.assertFalse(self.badge.held("DOWN"))
        self.assertEqual(self.badge.buttons.held(), {"UP"})

    def test_rotated_physical_arrows_are_swapped(self):
        self.badge.rotated = True
        self.physical.down = {"UP", "LEFT", "SELECT"}
        self.physical.just = {"LEFT"}
        self.assertEqual(self.badge.held(), {"DOWN", "RIGHT", "SELECT"})
        self.assertTrue(self.badge.pressed("RIGHT"))
        self.assertFalse(self.badge.pressed("LEFT"))
        self.assertEqual(self.badge.buttons.held(), {"DOWN", "RIGHT", "SELECT"})
        direction = self.badge.direction()
        self.assertEqual((direction.x, direction.y), (1, 1))

    def test_rotated_touch_pad_is_left_to_firmware(self):
        self.badge.rotated = True
        self.badge.pad.down = {"UP", "BACK"}
        self.assertEqual(self.badge.held(), {"UP", "BACK"})
        self.assertTrue(self.badge.held("UP"))
        self.assertFalse(self.badge.held("DOWN"))
        self.assertEqual(self.badge.direction().x, "firmware")

    def test_install_is_idempotent(self):
        wrapped = self.badge.buttons
        self.module.install()
        self.assertIs(self.badge.buttons, wrapped)

    def test_other_attributes_reach_the_physical_group(self):
        self.physical.extra = 42
        self.assertEqual(self.badge.buttons.extra, 42)


if __name__ == "__main__":
    unittest.main()
