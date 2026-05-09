from __future__ import annotations

import re
from dataclasses import dataclass

from brackettracker.excel_io import GameRow, ParticipantPicks

# Optional abbreviation / short form → canonical normalized name (casefold, single-spaced).
# Used so picks like "UNC" can match results "North Carolina" when both normalize the same way.
_TEAM_ALIASES: dict[str, str] = {
    "unc": "north carolina",
    "uk": "kentucky",
    "kansas st": "kansas state",
    "kansas st.": "kansas state",
    "mich st": "michigan state",
    "mich st.": "michigan state",
    "michgian state": "michigan state",  # common bracket typo
    "fl st": "florida state",
    "ohio st": "ohio state",
    "ohio st.": "ohio state",
    "miss st": "mississippi state",
    "ok st": "oklahoma state",
    "wash st": "washington state",
    "utah st": "utah state",
    "utah st.": "utah state",
    "tamu": "texas a&m",
}

_SEED_PREFIX = re.compile(r"^\(?\d{1,2}\)?\s*[\.\-]?\s*")


def _norm_team(s: str) -> str:
    return " ".join(str(s).split()).casefold()


def normalize_team(s: str) -> str:
    """
    Normalize team strings for matching picks to results.

    - Collapses whitespace and case-folds.
    - Strips a leading seed like ``1 ``, ``(1)``, ``16.`` before the team name.
    - Maps known abbreviations to a canonical form (see internal alias table).
    """
    t = _norm_team(s)
    t = _SEED_PREFIX.sub("", t, count=1).strip()
    return _TEAM_ALIASES.get(t, t)


@dataclass
class PersonScore:
    name: str
    points_earned: float
    max_possible: float
    games_counted: int
    correct_known: int


def build_game_table(
    results: dict[str, GameRow],
    participants: list[ParticipantPicks],
    per_game_weights: dict[str, float] | None = None,
) -> dict[str, GameRow]:
    """Ensure every game id referenced in picks exists; default points from per_game_weights or 1."""
    merged = dict(results)
    for p in participants:
        for gid in p.picks:
            if gid not in merged:
                pts = 1.0
                if per_game_weights and gid in per_game_weights:
                    pts = float(per_game_weights[gid])
                merged[gid] = GameRow(game_id=gid, winner=None, points=pts)
    return merged


def score_all(
    games: dict[str, GameRow],
    participants: list[ParticipantPicks],
) -> list[PersonScore]:
    """
    For each game:
    - If winner is known: award points if pick matches (normalized string compare).
    - If winner unknown: count those points toward max_possible only (player could still win).
    """
    rows: list[PersonScore] = []
    for person in participants:
        earned = 0.0
        max_pos = 0.0
        correct = 0
        counted = 0
        for gid, gr in games.items():
            if gid not in person.picks:
                continue
            counted += 1
            pts = gr.points
            pick = person.picks[gid]
            if gr.winner is None:
                max_pos += pts
            else:
                if normalize_team(pick) == normalize_team(gr.winner):
                    earned += pts
                    correct += 1
                # decided wrong: contributes 0 to earned and 0 to remaining max

        # max_possible = what they have so far + what they could still get from undecided games they picked
        max_total = earned + max_pos
        rows.append(
            PersonScore(
                name=person.name,
                points_earned=earned,
                max_possible=max_total,
                games_counted=counted,
                correct_known=correct,
            )
        )

    rows.sort(key=lambda r: (r.points_earned, r.max_possible), reverse=True)
    return rows


def max_theoretical_total(games: dict[str, GameRow]) -> float:
    """Sum of points for games that are not yet decided (still in play)."""
    return sum(g.points for g in games.values() if g.winner is None)


def points_decided(games: dict[str, GameRow]) -> float:
    return sum(g.points for g in games.values() if g.winner is not None)
