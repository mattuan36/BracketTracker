"""
Bracket tracker CLI: read Excel files from a folder, score picks, print standings.

Expected layout:
  - Grid-style .xls (example bracket template): one participant per file; sheet *example_bracket*
    or *basketball_bracket*; name from NAME: line; 63 picks use ids like example_bracket_east_8_3.
  - Or .xlsx: one sheet named Results (or Actuals / Answer) with Game, Winner, optional Points;
    other sheets: one person each with columns Game, Pick.

Example:
  python main.py ./my_bracket_folder
  python main.py ./data --results ./data/results.xlsx --csv-out standings.csv --chart-out chart.png
  python gui.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from brackettracker.app_core import run_scoring
from brackettracker.report import plot_leaderboard, print_standings, save_standings_csv


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Score bracket picks from Excel workbooks in a folder.")
    p.add_argument(
        "folder",
        type=Path,
        help="Directory containing .xlsx files (each non-Results sheet = one person).",
    )
    p.add_argument(
        "--results",
        type=Path,
        default=None,
        help="Optional path to the workbook with a Results sheet (defaults: auto-detect).",
    )
    p.add_argument(
        "--results-sheet",
        default=None,
        help="Sheet name for outcomes when --results is set (defaults: first Results/Actuals sheet).",
    )
    p.add_argument("--csv-out", type=Path, default=None, help="Write standings table to CSV.")
    p.add_argument("--chart-out", type=Path, default=None, help="Save leaderboard bar chart (PNG).")
    args = p.parse_args(argv)

    rows, issues, err, needs_review = run_scoring(
        args.folder,
        results_file=args.results,
        results_sheet=args.results_sheet,
    )
    for msg in issues:
        print(msg, file=sys.stderr)
    if needs_review:
        print("\nSheets needing manual review / correction:", file=sys.stderr)
        for rev in needs_review:
            print(f"  • {rev.workbook} — {rev.sheet}", file=sys.stderr)
            for reason in rev.reasons:
                print(f"      {reason}", file=sys.stderr)
    if err:
        print(err, file=sys.stderr)
        return 1

    print_standings(rows)

    if args.csv_out:
        save_standings_csv(rows, args.csv_out.resolve())
        print(f"Wrote {args.csv_out}")

    if args.chart_out:
        try:
            plot_leaderboard(rows, args.chart_out.resolve())
            print(f"Wrote chart {args.chart_out}")
        except Exception as e:
            print(f"Chart failed: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
