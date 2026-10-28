"""Host-side checks for pollen hints; graphics/input are stubbed, not emulated."""

from collections import deque
from pathlib import Path
import random
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


APP = Path(__file__).resolve().parents[1] / "badge/apps/bee_amazed/__init__.py"


class PollenTests(unittest.TestCase):
    def setUp(self):
        self.pressed = set()
        self.held = set()
        self.badge = SimpleNamespace(
            ticks=1000, ticks_delta=16, mode=Mock(),
            pressed=lambda button: button in self.pressed,
            held=lambda button: button in self.held,
        )
        screen = Mock(width=320, height=240)
        screen.measure_text.return_value = (100, 8)
        self.app = {
            "__name__": "bee_amazed_under_test", "badge": self.badge,
            "screen": screen, "image": Mock(), "font": Mock(),
            "color": Mock(), "shape": Mock(), "rect": Mock(),
            "vec2": Mock(), "run": Mock(), "HIRES": 1, "VSYNC": 2,
            **{"BUTTON_" + key: key for key in
               ("LEFT", "RIGHT", "UP", "DOWN", "SELECT")},
        }
        with patch("os.chdir"), patch.object(sys, "path", list(sys.path)):
            exec(compile(APP.read_text(), str(APP), "exec"), self.app)
        self.builder = self.app["builder"]

    def grid(self, rows):
        self.builder.maze = [[16 if value == "#" else 0 for value in row]
                             for row in rows]
        self.builder.grid_rows = len(rows)
        self.builder.grid_columns = len(rows[0])

    def tick(self, pressed=(), held=(), delta=16):
        self.pressed = set(pressed)
        self.held = set(held)
        self.badge.ticks += delta
        self.badge.ticks_delta = delta
        self.app["update"]()

    def start(self):
        self.tick(pressed=("SELECT",))
        self.tick()

    def test_start_does_not_also_request_hint(self):
        self.start()
        self.assertEqual(self.app["state"], self.app["GameState"].PLAYING)
        self.assertEqual(self.app["hint"], [])

    def test_hint_follows_shortest_route_in_cyclic_maze(self):
        self.grid(("#####", "#...#", "#.#.#", "#...#", "#####"))
        trail = self.builder.pollen_trail((1, 1), (3, 1))
        self.assertEqual(trail, [(2, 1), (3, 1)])

    def test_hint_leads_out_of_dead_end(self):
        self.grid(("#######", "#.....#", "###.###", "#...###", "#######"))
        self.assertEqual(self.builder.pollen_trail((1, 3), (5, 1)),
                         [(2, 3), (3, 3), (3, 2), (3, 1), (4, 1), (5, 1)])

    def test_visited_path_bits_remain_walkable_and_unchanged(self):
        self.grid(("#####", "#...#", "#####"))
        self.builder.maze[1][1:4] = [4, 12, 8]
        before = [row[:] for row in self.builder.maze]
        self.assertEqual(self.builder.pollen_trail((1, 1), (3, 1)),
                         [(2, 1), (3, 1)])
        self.assertEqual(self.builder.maze, before)

    def test_unreachable_flower_and_already_at_goal(self):
        self.grid(("#####", "#.#.#", "#####"))
        self.assertEqual(self.builder.pollen_trail((1, 1), (3, 1)), [])
        self.assertEqual(self.builder.pollen_trail((1, 1), (1, 1)), [])

    def test_open_edges_do_not_wrap_into_other_rows(self):
        self.grid(("..#", "#.."))
        self.assertEqual(self.builder.pollen_trail((0, 0), (2, 1)),
                         [(1, 0), (1, 1), (2, 1)])

    def test_generated_maze_hints_reduce_distance_at_every_step(self):
        # Compare to an independent flood-fill over real randomly built mazes.
        rng = random.Random(26)
        for width, height in ((2, 2), (4, 3), (9, 7), (14, 10)):
            for _ in range(5):
                with patch("random.choice", rng.choice):
                    self.builder.build(width, height)
                maze = self.builder.maze
                goal = (width * 2 - 1, 1)
                distance = {goal: 0}
                queue = deque([goal])
                while queue:
                    x, y = queue.popleft()
                    for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                        if (0 <= ny < len(maze) and 0 <= nx < len(maze[0])
                                and maze[ny][nx] < 16 and (nx, ny) not in distance):
                            distance[nx, ny] = distance[x, y] + 1
                            queue.append((nx, ny))
                cells = list(distance)
                for start in rng.sample(cells, min(10, len(cells))):
                    trail = self.builder.pollen_trail(start, goal)
                    self.assertEqual(len(trail), min(6, distance[start]))
                    previous = start
                    for cell in trail:
                        self.assertEqual(abs(cell[0] - previous[0]) +
                                         abs(cell[1] - previous[1]), 1)
                        self.assertEqual(distance[cell], distance[previous] - 1)
                        previous = cell

    def test_hint_expires_by_elapsed_time_and_can_be_requested_again(self):
        self.start()
        self.tick(pressed=("SELECT",))
        self.assertTrue(self.app["hint"])
        self.tick(delta=2499)
        self.assertTrue(self.app["hint"])
        self.tick(delta=1)
        self.assertEqual(self.app["hint"], [])
        self.tick(pressed=("SELECT",))
        self.assertTrue(self.app["hint"])

    def test_movement_clears_hint_and_request_uses_current_position(self):
        self.start()
        self.tick(pressed=("SELECT",))
        player = self.app["player"]
        first = self.app["hint"][0]
        dx, dy = first[0] - player.x, first[1] - player.y
        direction = {(-1, 0): "LEFT", (1, 0): "RIGHT",
                     (0, -1): "UP", (0, 1): "DOWN"}[dx, dy]
        self.tick(held=(direction,), delta=30)
        self.assertEqual((player.x, player.y), first)
        self.assertEqual(self.app["hint"], [])
        self.tick(pressed=("SELECT",))
        self.assertEqual(self.app["hint"],
                         self.builder.pollen_trail(first, self.app["goal"]))

    def test_finish_and_next_level_clear_hint(self):
        self.start()
        self.tick(pressed=("SELECT",))
        self.app["player"].position(*self.app["goal"])
        self.tick()
        self.assertTrue(self.app["complete"])
        self.assertEqual(self.app["hint"], [])
        self.tick(pressed=("SELECT",))
        self.assertEqual(self.app["level"], 1)
        self.assertFalse(self.app["complete"])
        self.assertEqual(self.app["hint"], [])
        self.assertEqual(self.app["hint_remaining"], 0)


if __name__ == "__main__":
    unittest.main()
