"""Shared fixtures for BracketTracker tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_simple_pool_xlsx(
    path: Path,
    *,
    results_rows: list[dict],
    alice_picks: dict[str, str],
    bob_picks: dict[str, str] | None = None,
) -> None:
    """Minimal xlsx: Results sheet + Alice + optional Bob participant sheets."""
    results_df = pd.DataFrame(results_rows)
    alice_df = pd.DataFrame([{"Game": k, "Pick": v} for k, v in alice_picks.items()])
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        results_df.to_excel(w, sheet_name="Results", index=False)
        alice_df.to_excel(w, sheet_name="Alice", index=False)
        if bob_picks is not None:
            bob_df = pd.DataFrame([{"Game": k, "Pick": v} for k, v in bob_picks.items()])
            bob_df.to_excel(w, sheet_name="Bob", index=False)
