"""
Shared scoring pipeline for CLI and GUI (no printing side effects).
"""

from __future__ import annotations

from pathlib import Path

from brackettracker.excel_io import GameRow, SheetNeedsReview, load_folder
from brackettracker.example_bracket import example_bracket_default_weights
from brackettracker.scoring import PersonScore, build_game_table, score_all


def run_scoring(
    folder: Path,
    results_file: Path | None = None,
    results_sheet: str | None = None,
) -> tuple[list[PersonScore], list[str], str | None, list[SheetNeedsReview]]:
    """
    Load folder, compute standings.

    Returns (rows sorted by score, issue messages, fatal_error, sheets_needing_review).
    If fatal_error is set, rows is empty (but ``sheets_needing_review`` may still list bad sheets).
    """
    folder = Path(folder).resolve()
    if not folder.is_dir():
        return [], [], f"Not a directory: {folder}", []

    issues_prefix: list[str] = []
    rf: Path | None = None
    if results_file is not None:
        p = Path(results_file)
        if str(p).strip():
            if p.is_file():
                rf = p.resolve()
            else:
                issues_prefix.append(f"Results file not found (ignored): {p}")

    rs = (results_sheet or "").strip() or None

    results, participants, issues, sheets_needing_review = load_folder(
        folder, results_file=rf, results_sheet=rs
    )
    issues = issues_prefix + issues

    if not participants:
        err = "No participants loaded."
        if not any("No Excel" in m for m in issues):
            err += " Add .xls/.xlsx files or check the folder path."
        return [], issues, err, sheets_needing_review

    example_weights = None
    for part in participants:
        if any(k.startswith("example_bracket_") for k in part.picks):
            example_weights = example_bracket_default_weights()
            break

    if example_weights:
        for gid in list(results.keys()):
            if gid in example_weights:
                gr = results[gid]
                results[gid] = GameRow(game_id=gid, winner=gr.winner, points=example_weights[gid])

    games = build_game_table(results, participants, per_game_weights=example_weights)
    rows = score_all(games, participants)
    return rows, issues, None, sheets_needing_review
