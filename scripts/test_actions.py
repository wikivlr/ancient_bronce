from __future__ import annotations

import unittest
from pathlib import Path

from ancient_bronce.actions import (
    ActionError,
    Position,
    begin_turn,
    create_human,
    drink,
    eat,
    load_game_rules,
    move_human,
    perform_action,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = PROJECT_ROOT / "rules" / "game_rules.json"


class HumanActionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rules = load_game_rules(RULES_PATH)
        self.human = create_human("human-1", "Aru", Position(5, 5), self.rules)

    def test_turn_reduces_hunger_and_thirst_and_sets_temperature(self) -> None:
        begin_turn(self.human, self.rules, effective_temperature=8)
        self.assertEqual(self.human.hunger, 2)
        self.assertEqual(self.human.thirst, 2)
        self.assertEqual(self.human.temperature, -2)

    def test_human_can_move_three_orthogonal_cells(self) -> None:
        move_human(
            self.human,
            [Position(6, 5), Position(6, 6), Position(7, 6)],
            self.rules,
            world_width=100,
            world_height=100,
        )
        self.assertEqual(self.human.position, Position(7, 6))
        self.assertEqual(self.human.movement_used, 3)
        self.assertEqual(self.human.fatigue, 2)

    def test_human_cannot_exceed_three_movement_cells_in_one_turn(self) -> None:
        with self.assertRaises(ActionError):
            move_human(
                self.human,
                [Position(6, 5), Position(7, 5), Position(8, 5), Position(9, 5)],
                self.rules,
                world_width=100,
                world_height=100,
            )

    def test_actions_consume_fatigue_until_exhausted(self) -> None:
        perform_action(self.human, "interact", self.rules)
        perform_action(self.human, "research", self.rules)
        perform_action(self.human, "craft_build", self.rules)
        self.assertEqual(self.human.fatigue, 0)
        with self.assertRaises(ActionError):
            perform_action(self.human, "copulate", self.rules)

    def test_rest_recovers_fatigue_and_ends_person_turn(self) -> None:
        self.human.fatigue = 0
        perform_action(self.human, "rest", self.rules)
        self.assertEqual(self.human.fatigue, 3)
        self.assertTrue(self.human.turn_ended)
        with self.assertRaises(ActionError):
            perform_action(self.human, "eat", self.rules)

    def test_eating_and_drinking_are_free_and_repeatable(self) -> None:
        self.human.hunger = 0
        self.human.thirst = 0
        for _ in range(4):
            eat(self.human, 1, self.rules)
            drink(self.human, 1, self.rules)
        self.assertEqual(self.human.hunger, 3)
        self.assertEqual(self.human.thirst, 3)
        self.assertEqual(self.human.fatigue, 3)
        self.assertEqual(self.human.action_counts["eat"], 4)
        self.assertEqual(self.human.action_counts["drink"], 4)

    def test_different_humans_have_independent_positions_and_needs(self) -> None:
        second = create_human("human-2", "Bel", Position(5, 5), self.rules)
        move_human(
            self.human,
            [Position(6, 5)],
            self.rules,
            world_width=100,
            world_height=100,
        )
        self.human.hunger = 0
        self.assertEqual(second.position, Position(5, 5))
        self.assertEqual(second.hunger, 3)


if __name__ == "__main__":
    unittest.main()
