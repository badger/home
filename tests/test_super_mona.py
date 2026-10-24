"""Host-side checks for the Super Mona platformer rules and assets."""

from pathlib import Path
import sys
import unittest
from unittest import mock

from PIL import Image


APP = Path(__file__).resolve().parents[1] / "badge/apps/super_mona"
sys.path.insert(0, str(APP))

import game  # noqa: E402
from game import TILE, ROWS, Controls, Session, World, tile_of  # noqa: E402
import levels  # noqa: E402

DT = 1 / 30


def make_world(level=None, **session):
    level = level or blank_level()
    s = Session()
    for key, value in session.items():
        setattr(s, key, value)
    return World(level, s)


def blank_level(width=60):
    level = game.Level("TEST", width)
    level.ground(0, width - 1)
    level.start = (4, 12)
    return level


def settle(world, frames=10, controls=None):
    controls = controls or Controls()
    for _ in range(frames):
        world.step(DT, controls)


def bot(world, c):
    p = world.player
    lv = world.level
    c.right = True
    c.run = True
    rows = range(tile_of(p.y), tile_of(p.y + p.h - 0.01) + 1)
    wall = any(lv.solid(tile_of(p.x + p.w + d), ty) for d in (1, 10) for ty in rows)
    front = tile_of(p.x + p.w + 10)
    feet = tile_of(p.y + p.h + 1)
    gap = not any(lv.solid(front + k, y) for k in (0, 1) for y in range(feet, ROWS))
    want = (wall or gap) and p.on_ground
    c.jump_pressed = want and not c.jump
    c.jump = want or (c.jump and p.vy < 0)


class SuperMonaTests(unittest.TestCase):
    def test_levels_build_with_flag_and_ground_start(self):
        for factory in levels.LEVELS:
            level = factory()
            self.assertIsNotNone(level.flag_x, level.name)
            self.assertLess(level.castle_door // TILE, level.width)
            sx, sy = level.start
            self.assertTrue(level.solid(sx, sy + 1), level.name)
            world = World(level, Session())
            settle(world)
            self.assertTrue(world.player.on_ground, level.name)

    def test_held_jump_goes_higher(self):
        heights = []
        for hold in (False, True):
            world = make_world()
            settle(world)
            ground = world.player.y
            c = Controls()
            c.jump_pressed = True
            c.jump = True
            world.step(DT, c)
            c.jump_pressed = False
            c.jump = hold
            peak = ground
            for _ in range(60):
                world.step(DT, c)
                peak = min(peak, world.player.y)
            heights.append(ground - peak)
        self.assertGreater(heights[1], heights[0] + 8)

    def test_stomp_squashes_bug(self):
        level = blank_level()
        level.enemy(8)
        world = make_world(level)
        enemy = world.enemies[0]
        world.player.x = enemy.x
        world.player.y = enemy.y - 20
        world.player.vy = 60
        settle(world, 8)
        self.assertIn(enemy.state, ("squashed",))
        self.assertGreater(world.session.score, 0)

    def test_side_hit_shrinks_big_player_then_kills(self):
        level = blank_level()
        level.enemy(9)
        world = make_world(level, big=True)
        settle(world, 2)
        for _ in range(40):
            world.step(DT, controls_right())
        self.assertFalse(world.player.big)
        self.assertGreater(world.player.invulnerable, 0)
        self.assertEqual(world.state, "play")
        world.player.invulnerable = 0
        world.enemies[0].x = world.player.x + 2
        world.enemies[0].y = world.player.y + world.player.h - world.enemies[0].h
        world.step(DT, Controls())
        self.assertEqual(world.state, "dying")

    def test_question_block_releases_chip_that_grows(self):
        level = blank_level()
        level.block(5, 9, "chip")
        world = make_world(level)
        settle(world)
        world.player.x = 5 * TILE + 1
        c = Controls()
        c.jump_pressed = c.jump = True
        world.step(DT, c)
        c.jump_pressed = False
        for _ in range(30):
            world.step(DT, c)
        self.assertEqual(level.get(5, 9), game.USED)
        self.assertEqual(len(world.items), 1)
        item = world.items[0]
        for _ in range(30):
            world.step(DT, Controls())
        world.player.x = item.x
        world.player.y = item.y + item.h - world.player.h
        world.step(DT, Controls())
        self.assertTrue(world.player.big)
        self.assertTrue(world.session.big)

    def test_brick_breaks_only_when_big(self):
        for big in (False, True):
            level = blank_level()
            level.row(5, 9, "B")
            world = make_world(level, big=big)
            settle(world)
            world.player.x = 5 * TILE + 1
            c = Controls()
            c.jump_pressed = c.jump = True
            world.step(DT, c)
            c.jump_pressed = False
            for _ in range(30):
                world.step(DT, c)
            self.assertEqual(level.get(5, 9), game.EMPTY if big else game.BRICK)

    def test_shell_pickup_and_throw(self):
        level = blank_level()
        level.enemy(10, "shellbot")
        world = make_world(level)
        settle(world, 2)
        shell = world.enemies[0]
        shell.state = "shell"
        shell.vx = 0
        world.player.x = shell.x - world.player.w - 2
        c = Controls()
        c.right = True
        c.run = True
        for _ in range(10):
            world.step(DT, c)
            if world.player.carrying:
                break
        self.assertIs(world.player.carrying, shell)
        self.assertEqual(shell.state, "carried")
        world.step(DT, Controls())
        self.assertIsNone(world.player.carrying)
        self.assertEqual(shell.state, "kicked")
        self.assertGreater(shell.vx, 0)

    def test_inventory_and_character_switch(self):
        level = blank_level()
        level.switch = True
        world = make_world(level, big=True)
        world.apply_item("chip")
        self.assertEqual(world.session.inventory, ["chip"])
        self.assertFalse(world.use_item(0))
        world.player.big = False
        self.assertTrue(world.use_item(0))
        self.assertTrue(world.player.big)
        self.assertTrue(world.switch_character())
        self.assertEqual(world.session.character, "luna")
        level.switch = False
        self.assertFalse(world.switch_character())

    def test_hundred_stars_gives_life(self):
        s = Session()
        for _ in range(100):
            s.add_star()
        self.assertEqual((s.stars, s.lives), (0, 4))

    def test_every_level_can_be_finished(self):
        for factory in levels.LEVELS:
            level = factory()
            world = World(level, Session())
            c = Controls()
            for _ in range(int(120 / DT)):
                world.player.sparkle = 1.0
                bot(world, c)
                world.step(DT, c)
                if world.state == "clear":
                    break
            self.assertEqual(world.state, "clear", level.name)
            self.assertGreater(world.session.score, 0)

    def test_asset_sizes(self):
        sizes = {
            "assets/tiles.png": (128, 32),
            "assets/players.png": (128, 64),
            "assets/mobs.png": (64, 16),
            "icon.png": (24, 24),
        }
        for name, size in sizes.items():
            with Image.open(APP / name) as img:
                self.assertEqual(img.size, size, name)


def controls_right():
    c = Controls()
    c.right = True
    return c


class Anything:
    """Stand-in for runtime objects: every attribute/call returns itself."""

    width = 160
    height = 120

    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        return Anything()

    def __call__(self, *args, **kwargs):
        return Anything()

    def __or__(self, other):
        return self

    def __iter__(self):
        return iter((40, 10))


class FakeBadge(Anything):
    def __init__(self):
        self.ticks = 0
        self.ticks_delta = 33
        self.down = set()
        self.fresh = set()

    def pressed(self, button):
        return button in self.fresh

    def held(self, button):
        return button in self.down

    def frame(self, buttons=(), hold=()):
        self.fresh = set(buttons)
        self.down = set(buttons) | set(hold)
        self.ticks += self.ticks_delta


class AppStateTests(unittest.TestCase):
    def test_app_runs_through_every_screen(self):
        import builtins
        import importlib
        import types

        names = ("UP", "DOWN", "LEFT", "RIGHT", "SELECT", "BACK", "MENU", "HOME")
        fake = FakeBadge()
        saved = {}
        state_mod = types.ModuleType("badgeware")
        state_mod.State = types.SimpleNamespace(
            load=lambda name, data: None,
            save=lambda name, data: saved.update(data),
        )
        runtime = {
            "badge": fake, "screen": Anything(), "image": Anything(), "font": Anything(),
            "color": Anything(), "vec2": Anything, "rect": Anything, "LORES": Anything(),
            "VSYNC": Anything(), "is_dir": lambda path: path == "/super_mona",
            "run": lambda update: None,
        }
        for name in names:
            runtime["BUTTON_" + name] = name
        old_modules = dict(sys.modules)
        added = [k for k in runtime if not hasattr(builtins, k)]
        sys.modules["badgeware"] = state_mod
        for key, value in runtime.items():
            setattr(builtins, key, value)
        chdir = mock.patch("os.chdir")
        chdir.start()
        try:
            for mod in ("render", "__init__", "super_mona_app"):
                sys.modules.pop(mod, None)
            spec = importlib.util.spec_from_file_location("super_mona_app", APP / "__init__.py")
            app = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(app)

            def frames(n, buttons=(), hold=()):
                for _ in range(n):
                    fake.frame(buttons, hold)
                    app.update()
                    fake.frame((), hold)

            frames(3)
            self.assertEqual(app.state, app.TITLE)
            frames(1, ("SELECT",))
            self.assertEqual(app.state, app.INTRO)
            frames(80)
            self.assertEqual(app.state, app.PLAY)
            frames(20, hold=("RIGHT", "BACK"))
            frames(1, ("MENU",))
            self.assertEqual(app.state, app.PAUSE)
            app.session.inventory.append("sparkle")
            for page in range(4):
                self.assertEqual(app.page, page)
                frames(1, ("UP",))
                frames(1, ("DOWN",))
                if page != 2:
                    frames(1, ("SELECT",))
                frames(1, ("RIGHT",))
            frames(1, ("BACK",))
            self.assertEqual(app.state, app.PLAY)
            app.world.kill_player()
            frames(120)
            self.assertEqual(app.session.lives, 2)
            self.assertEqual(app.state, app.INTRO)
            app.session.lives = 1
            frames(80)
            app.world.kill_player()
            frames(120)
            self.assertEqual(app.state, app.OVER)
            frames(40)
            frames(1, ("SELECT",))
            self.assertEqual(app.state, app.TITLE)
            app.new_game()
            app.session.level = len(app.LEVELS) - 1
            app.start_level()
            frames(80)
            app.world.state = "clear"
            frames(1)
            self.assertEqual(app.state, app.WIN)
            frames(40)
            app.on_exit()
        finally:
            chdir.stop()
            for key in added:
                delattr(builtins, key)
            sys.modules.clear()
            sys.modules.update(old_modules)


if __name__ == "__main__":
    unittest.main()
