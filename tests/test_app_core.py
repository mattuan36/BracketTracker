"""Integration tests for run_scoring + folder loading."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from brackettracker.app_core import run_scoring
from tests.conftest import write_simple_pool_xlsx


def test_run_scoring_simple_xlsx_pool(tmp_path: Path) -> None:
    pool = tmp_path / "pool.xlsx"
    write_simple_pool_xlsx(
        pool,
        results_rows=[
            {"Game": "G1", "Winner": "Alpha", "Points": 1},
            {"Game": "G2", "Winner": "", "Points": 2},
        ],
        alice_picks={"G1": "Alpha", "G2": "Beta"},
        bob_picks={"G1": "Gamma", "G2": "Beta"},
    )
    rows, issues, err, needs_review = run_scoring(tmp_path, results_file=pool)
    assert err is None
    assert needs_review == []
    alice_row = next(r for r in rows if r.name == "Alice")
    assert alice_row.points_earned == 1.0
    assert alice_row.max_possible >= 1.0


def test_run_scoring_empty_folder(tmp_path: Path) -> None:
    rows, issues, err, needs_review = run_scoring(tmp_path)
    assert err is not None
    assert not rows
    assert needs_review == []


def test_run_scoring_missing_results_file_logs_issue(tmp_path: Path) -> None:
    pool = tmp_path / "pool.xlsx"
    write_simple_pool_xlsx(
        pool,
        results_rows=[{"Game": "G1", "Winner": ""}],
        alice_picks={"G1": "A"},
    )
    missing = tmp_path / "nope.xlsx"
    rows, issues, err, needs_review = run_scoring(tmp_path, results_file=missing)
    assert err is None
    assert needs_review == []
    assert any("not found" in m.lower() for m in issues)


def test_invalid_participant_sheets_excluded_and_flagged_for_review(tmp_path: Path) -> None:
    """Sheets with wrong shape must not be scored; they appear in sheets_needing_review."""
    pool = tmp_path / "pool.xlsx"
    with pd.ExcelWriter(pool, engine="openpyxl") as w:
        pd.DataFrame([{"Game": "G1", "Winner": "Alpha", "Points": 1}]).to_excel(w, sheet_name="Results", index=False)
        pd.DataFrame([{"Game": "G1", "Pick": "Alpha"}]).to_excel(w, sheet_name="Alice", index=False)
        pd.DataFrame([{"Foo": 1, "Bar": 2}, {"Foo": 3, "Bar": 4}]).to_excel(w, sheet_name="BrokenLayout", index=False)
        pd.DataFrame(columns=["Game", "Pick"]).to_excel(w, sheet_name="NoPicks", index=False)

    rows, issues, err, needs_review = run_scoring(tmp_path, results_file=pool)
    assert err is None
    assert len(rows) == 1
    assert rows[0].name == "Alice"

    bad = {r.sheet for r in needs_review}
    assert "BrokenLayout" in bad
    assert "NoPicks" in bad
    assert not any(r.sheet == "Alice" for r in needs_review)
    assert not any(r.sheet == "Results" for r in needs_review)


def test_corrupt_workbook_recorded_for_review_while_others_score(tmp_path: Path) -> None:
    (tmp_path / "corrupt.xlsx").write_text("not a real xlsx", encoding="utf-8")
    pool = tmp_path / "pool.xlsx"
    write_simple_pool_xlsx(
        pool,
        results_rows=[{"Game": "G1", "Winner": ""}],
        alice_picks={"G1": "X"},
    )
    rows, issues, err, needs_review = run_scoring(tmp_path, results_file=pool)
    assert err is None
    assert len(rows) == 1
    corrupt = next(r for r in needs_review if r.workbook == "corrupt.xlsx")
    assert corrupt.sheet == "(entire workbook)"
    assert any("open" in reason.lower() or "excel" in reason.lower() for reason in corrupt.reasons)
