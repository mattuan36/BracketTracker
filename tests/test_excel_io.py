"""Tests for Excel helpers (columnar picks + results)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from brackettracker.excel_io import load_picks_from_sheet, load_results_from_sheet


def test_load_results_from_sheet(tmp_path: Path) -> None:
    path = tmp_path / "r.xlsx"
    pd.DataFrame(
        [
            {"Game": "G1", "Winner": "Duke", "Points": 3},
            {"Game": "G2", "Winner": "", "Points": 1},
        ]
    ).to_excel(path, sheet_name="Results", index=False)
    out, issues = load_results_from_sheet(path, "Results")
    assert not issues or all("duplicate" not in m.lower() for m in issues)
    assert out["G1"].winner == "Duke"
    assert out["G1"].points == 3.0
    assert out["G2"].winner is None


def test_load_picks_from_sheet(tmp_path: Path) -> None:
    path = tmp_path / "p.xlsx"
    pd.DataFrame(
        [
            {"Game": "G1", "Pick": "UNC"},
            {"Game": "G2", "Pick": "(1) Duke"},
        ]
    ).to_excel(path, sheet_name="Pat", index=False)
    part, issues = load_picks_from_sheet(path, "Pat")
    assert part is not None
    assert part.name == "Pat"
    assert part.picks["G1"] == "UNC"
    assert part.picks["G2"] == "(1) Duke"
