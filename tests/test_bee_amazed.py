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

    def test_tap_moves_one_step_and_holding_waits_before_repeating(self):
        self.grid(("#######", "#.....#", "#######"))
        player = self.app["Player"](1, 1)
        self.pressed = {"RIGHT"}
        self.held = {"RIGHT"}
        self.assertTrue(player.update(self.builder.maze))
        self.assertEqual((player.x, player.moves), (2, 1))
        self.pressed = set()
        self.held = {"RIGHT"}
        self.badge.ticks_delta = 179
        self.assertFalse(player.update(self.builder.maze))
        self.badge.ticks_delta = 1
        self.assertTrue(player.update(self.builder.maze))
        self.assertEqual((player.x, player.moves), (3, 2))

    def test_repeated_press_edge_during_hold_does_not_skip_repeat_delay(self):
        self.grid(("#######", "#.....#", "#######"))
        player = self.app["Player"](1, 1)
        self.held = self.pressed = {"RIGHT"}
        player.update(self.builder.maze)
        self.badge.ticks_delta = 16
        player.update(self.builder.maze)
        self.assertEqual((player.x, player.moves), (2, 1))

    def test_turn_and_release_allow_another_immediate_step(self):
        self.grid(("#######", "#.....#", "#######"))
        player = self.app["Player"](2, 1)
        self.held = {"RIGHT"}
        player.update(self.builder.maze)
        self.held = {"LEFT"}
        player.update(self.builder.maze)
        self.assertEqual(player.x, 2)
        self.held = set()
        player.update(self.builder.maze)
        self.held = {"LEFT"}
        player.update(self.builder.maze)
        self.assertEqual((player.x, player.moves), (1, 3))

    def test_held_movement_matches_across_frame_rates(self):
        for frame_ms in (10, 16, 40, 100):
            maze = [[0] * 60]
            player = self.app["Player"](0, 0)
            self.held = {"RIGHT"}
            player.update(maze)
            elapsed = 0
            while elapsed < 1800:
                self.badge.ticks_delta = min(frame_ms, 1800 - elapsed)
                elapsed += self.badge.ticks_delta
                player.update(maze)
            self.assertEqual((player.x, player.moves), (20, 20), frame_ms)

    def test_wall_and_open_edge_do_not_count_as_moves(self):
        for maze in ([[0, 16]], [[0]]):
            player = self.app["Player"](0, 0)
            self.held = {"RIGHT"}
            self.assertFalse(player.update(maze))
            self.badge.ticks_delta = 250
            self.assertFalse(player.update(maze))
            self.assertEqual((player.x, player.moves), (0, 0))

    def test_slow_frame_stops_at_flower_and_pause_does_not_rush(self):
        maze = [[0] * 60]
        player = self.app["Player"](0, 0)
        self.held = {"RIGHT"}
        player.update(maze)
        self.badge.ticks_delta = 10000
        player.update(maze)
        self.assertLessEqual(player.x, 3)
        player.move_wait = 0
        target = player.x + 1
        player.update(maze, target=(target, 0))
        self.assertEqual(player.x, target)

    def test_late_levels_keep_readable_tiles_and_fit_below_header(self):
        for width, height in ((320, 240), (160, 120)):
            self.app["screen"].width = width
            self.app["screen"].height = height
            self.app["level"] = 10000
            self.app["build_maze"]()
            pitch = self.app["wall_separation"]
            self.assertGreaterEqual(pitch, self.app["MIN_TILE_SIZE"])
            self.assertGreaterEqual(self.app["offset_y"], self.app["HEADER_HEIGHT"])
            self.assertLessEqual(self.app["offset_y"] + self.builder.grid_rows * pitch,
                                 height - self.app["FOOTER_HEIGHT"] + 1)
            self.assertLessEqual(self.app["offset_x"] + self.builder.grid_columns * pitch,
                                 width + 1)

    def test_hint_counter_and_move_counter_reset_for_next_level(self):
        self.start()
        self.tick(pressed=("SELECT",))
        self.tick()
        self.tick(pressed=("SELECT",))
        self.assertEqual(self.app["hints_used"], 2)
        self.app["player"].position(*self.app["goal"])
        self.tick()
        self.tick(pressed=("SELECT",))
        self.assertEqual(self.app["hints_used"], 0)
        self.assertEqual(self.app["player"].moves, 0)

    def test_select_on_finishing_frame_does_not_skip_completion_card(self):
        self.start()
        self.app["player"].position(*self.app["goal"])
        self.tick(pressed=("SELECT",))
        self.assertTrue(self.app["complete"])
        self.assertEqual(self.app["level"], 0)

    def test_full_level_through_direction_inputs_and_continue(self):
        self.app["level"] = 8
        self.app["build_maze"]()
        self.app["player"].position(*self.app["start"])
        self.start()
        player = self.app["player"]
        route = self.builder.pollen_trail((player.x, player.y), self.app["goal"], 9999)
        for cell in route:
            direction = {(-1, 0): "LEFT", (1, 0): "RIGHT",
                         (0, -1): "UP", (0, 1): "DOWN"}[
                             cell[0] - player.x, cell[1] - player.y]
            self.tick(held=(direction,))
            self.assertEqual((player.x, player.y), cell)
            self.tick()
        self.assertTrue(self.app["complete"])
        self.assertEqual(player.moves, len(route))
        self.tick(pressed=("SELECT",))
        self.assertEqual(self.app["level"], 9)
        self.assertFalse(self.app["complete"])
        self.assertEqual((player.x, player.y), self.app["start"])
        self.assertEqual(player.moves, 0)


if __name__ == "__main__":
    unittest.main()
