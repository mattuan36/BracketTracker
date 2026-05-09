"""Unit tests for scoring and team name normalization."""

from __future__ import annotations

import pytest

from brackettracker.excel_io import GameRow, ParticipantPicks
from brackettracker.scoring import build_game_table, normalize_team, score_all


class TestNormalizeTeam:
    """How picks and results are compared after normalization."""

    def test_full_name_case_and_whitespace(self) -> None:
        assert normalize_team("  Duke ") == normalize_team("DUKE")
        assert normalize_team("North Carolina") == normalize_team("north  carolina")

    def test_seed_prefix_before_name(self) -> None:
        """Bracket-style ``1 Duke``, ``(16) Siena``, ``8. Ohio State`` → same as plain name."""
        assert normalize_team("1 Duke") == normalize_team("Duke")
        assert normalize_team("(1) Duke") == normalize_team("duke")
        assert normalize_team("16 Siena") == normalize_team("Siena")
        assert normalize_team("8 Ohio State") == normalize_team("Ohio State")

    def test_abbreviation_alias_matches_full_name(self) -> None:
        assert normalize_team("UNC") == normalize_team("North Carolina")
        assert normalize_team("UK") == normalize_team("Kentucky")

    def test_plain_seed_only_does_not_match_team_name(self) -> None:
        """A pick that is only a seed number must not equal a school name."""
        assert normalize_team("1") != normalize_team("Duke")
        assert normalize_team("16") != normalize_team("Siena")

    def test_typo_alias_michigan_state(self) -> None:
        assert normalize_team("Michgian State") == normalize_team("Michigan State")


class TestScoreAll:
    def test_basic_two_games_one_participant(self) -> None:
        games = {
            "G1": GameRow("G1", "Alpha", 1.0),
            "G2": GameRow("G2", None, 2.0),
        }
        alice = ParticipantPicks(name="Alice", picks={"G1": "Alpha", "G2": "Beta"})
        rows = score_all(games, [alice])
        assert len(rows) == 1
        r = rows[0]
        assert r.name == "Alice"
        assert r.points_earned == 1.0
        assert r.max_possible == 3.0  # 1 earned + 2 still open
        assert r.correct_known == 1
        assert r.games_counted == 2

    def test_pick_with_seed_matches_result_without(self) -> None:
        games = {
            "G1": GameRow("G1", "Duke", 1.0),
        }
        p = ParticipantPicks(name="P", picks={"G1": "(1) Duke"})
        rows = score_all(games, [p])
        assert rows[0].points_earned == 1.0
        assert rows[0].correct_known == 1

    def test_abbreviation_pick_matches_full_winner(self) -> None:
        games = {
            "G1": GameRow("G1", "North Carolina", 1.0),
        }
        p = ParticipantPicks(name="P", picks={"G1": "UNC"})
        rows = score_all(games, [p])
        assert rows[0].points_earned == 1.0

    def test_wrong_pick_zero_points(self) -> None:
        games = {"G1": GameRow("G1", "Alpha", 5.0)}
        p = ParticipantPicks(name="P", picks={"G1": "Beta"})
        rows = score_all(games, [p])
        assert rows[0].points_earned == 0.0
        assert rows[0].correct_known == 0

    def test_multiple_participants_sorted_by_points(self) -> None:
        games = {
            "G1": GameRow("G1", "A", 1.0),
            "G2": GameRow("G2", "B", 1.0),
        }
        a = ParticipantPicks(name="Low", picks={"G1": "X", "G2": "X"})
        b = ParticipantPicks(name="High", picks={"G1": "A", "G2": "B"})
        rows = score_all(games, [a, b])
        assert [x.name for x in rows] == ["High", "Low"]
        assert rows[0].points_earned == 2.0
        assert rows[1].points_earned == 0.0


class TestBuildGameTable:
    def test_fills_missing_games_with_default_points(self) -> None:
        results: dict[str, GameRow] = {}
        p = ParticipantPicks(name="A", picks={"X": "y"})
        g = build_game_table(results, [p])
        assert g["X"].points == 1.0
        assert g["X"].winner is None
