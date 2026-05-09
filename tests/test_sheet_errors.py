"""Tests for sheets that raise during load (manual review list)."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pandas as pd

from brackettracker.app_core import run_scoring
from brackettracker.excel_io import load_picks_from_sheet


def test_unexpected_error_in_load_picks_flags_sheet_for_review(tmp_path: Path) -> None:
    pool = tmp_path / "pool.xlsx"
    with pd.ExcelWriter(pool, engine="openpyxl") as w:
        pd.DataFrame([{"Game": "G1", "Winner": ""}]).to_excel(w, sheet_name="Results", index=False)
        pd.DataFrame([{"Game": "G1", "Pick": "A"}]).to_excel(w, sheet_name="Alice", index=False)
        pd.DataFrame([{"Game": "G1", "Pick": "B"}]).to_excel(w, sheet_name="Zed", index=False)

    real_load = load_picks_from_sheet

    def flaky(path: Path, sheet: str):
        if sheet == "Zed":
            raise RuntimeError("simulated parse failure")
        return real_load(path, sheet)

    with mock.patch("brackettracker.excel_io.load_picks_from_sheet", side_effect=flaky):
        rows, issues, err, needs_review = run_scoring(tmp_path, results_file=pool)

    assert err is None
    assert len(rows) == 1
    assert rows[0].name == "Alice"
    zed = next(r for r in needs_review if r.sheet == "Zed")
    assert any("RuntimeError" in reason for reason in zed.reasons)
    assert any("simulated" in reason.lower() for reason in zed.reasons)
