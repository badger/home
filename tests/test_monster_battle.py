"""Battle rules can be checked without badge firmware."""

import importlib.util
from pathlib import Path
import random
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "badge" / "apps" / "monster_battle" / "monster_rules.py"
SPEC = importlib.util.spec_from_file_location("monster_rules", SOURCE)
rules = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rules)


class FixedRandom:
    def __init__(self, accuracy=1, variation=0):
        self.accuracy = accuracy
        self.variation = variation

    def randint(self, low, high):
        return self.accuracy if (low, high) == (1, 100) else self.variation


class BattleTests(unittest.TestCase):
    def test_dual_type_effectiveness(self):
        for attack_type, defender, expected in (
            ("ELECTRIC", 1, 2), ("ELECTRIC", 2, 2),
            ("ELECTRIC", 0, 0.25), ("DRAGON", 0, 2),
            ("WATER", 0, 0.5), ("GHOST", 1, 2),
            ("GHOST", 2, 2), ("PSYCHIC", 2, 0.5),
            ("FLYING", 0, 0.5), ("WATER", 2, 1),
        ):
            self.assertEqual(rules.effectiveness(attack_type, defender), expected)

    def test_typed_moves_apply_modifiers(self):
        for attacker, defender, move, expected in (
            (0, 1, 1, 38), (0, 2, 1, 38), (1, 2, 2, 56),
            (1, 0, 1, 9), (2, 0, 2, 14),
        ):
            battle = rules.Battle(attacker, defender, FixedRandom())
            before = battle.hp[1]
            event = battle.act(0, move)
            self.assertEqual(before - battle.hp[1], expected)
            self.assertIn("Strong hit" if expected > 28 else "Resisted", event[1])

    def test_neutral_damage_and_variation(self):
        for variation in (-2, 0, 2):
            for move, power in ((0, 15), (1, 19)):
                battle = rules.Battle(2, 1, FixedRandom(75, variation))
                battle.act(0, move)
                self.assertEqual(battle.hp[1], 110 - power - variation)

    def test_wild_rush_accuracy_boundary(self):
        for roll, hit in ((75, True), (76, False), (100, False)):
            battle = rules.Battle(0, 1, FixedRandom(roll))
            event = battle.act(0, 2)
            self.assertEqual(event[3], "hit" if hit else "miss")
            self.assertEqual(battle.hp[1], 82 if hit else 110)

    def test_healing_cap_and_exhaustion(self):
        battle = rules.Battle(0, 1)
        battle.hp[0] = 90
        self.assertIn("10 HP", battle.act(0, 3)[1])
        self.assertEqual(battle.hp[0], 100)
        battle.hp[0] = 20
        battle.act(0, 3)
        self.assertEqual(battle.hp[0], 48)
        self.assertFalse(battle.available(0, 3))
        with self.assertRaises(ValueError):
            battle.act(0, 3)
        self.assertEqual(battle.hp[0], 48)

    def test_knockout_stops_actions(self):
        for actor in (0, 1):
            battle = rules.Battle(0, 1, FixedRandom())
            battle.hp[1 - actor] = 1
            event = battle.act(actor, 0)
            self.assertEqual(battle.hp[1 - actor], 0)
            self.assertIn("-1 HP", event[1])
            self.assertEqual(battle.winner(), actor)
            with self.assertRaises(ValueError):
                battle.act(1 - actor, 0)

    def test_enemy_heals_only_while_available_and_hurt(self):
        battle = rules.Battle(0, 1, FixedRandom(variation=2))
        self.assertEqual(battle.enemy_move(), 2)
        battle.hp[1] = 30
        self.assertEqual(battle.enemy_move(), 3)
        battle.mends[1] = 0
        self.assertEqual(battle.enemy_move(), 2)

    def test_all_matchups_finish_and_restart_fresh(self):
        for player in range(3):
            for opponent in range(3):
                battle = rules.Battle(player, opponent, random.Random(42))
                for turn in range(100):
                    battle.act(0, turn % 3)
                    if battle.winner() is not None:
                        break
                    battle.act(1, battle.enemy_move())
                    if battle.winner() is not None:
                        break
                self.assertIsNotNone(battle.winner())
                self.assertTrue(all(0 <= hp <= rules.CREATURES[creature][2]
                                    for hp, creature in zip(battle.hp, battle.creatures)))
                fresh = rules.Battle(player, opponent)
                self.assertEqual(fresh.mends, [2, 2])
                self.assertIsNone(fresh.winner())


if __name__ == "__main__":
    unittest.main()
