"""
Parse grid-style NCAA bracket .xls workbooks (63 pick cells in fixed coordinates).

Default layout matches a common printable pool template (2026 grid). Scoring: 1 / 2 / 4 / 6 / 8 / 12
by round; regional picks use column position (left cols 3–6, right 10–13); national games use
fixed center cells.

Game ids use the prefix ``example_bracket_`` (e.g. ``example_bracket_east_8_3``).
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from brackettracker.excel_io import ParticipantPicks

# Prefix for stable game keys (results sheets use the same ids in the Game column).
EXAMPLE_BRACKET_ID_PREFIX = "example_bracket"

# Exact (region, row, col) for each of the 63 pick cells — default grid layout.
_EXAMPLE_BRACKET_SLOTS: tuple[tuple[str, int, int], ...] = (
    ("east", 8, 3),
    ("east", 10, 4),
    ("east", 12, 3),
    ("east", 14, 5),
    ("east", 16, 3),
    ("east", 18, 4),
    ("east", 20, 3),
    ("east", 22, 6),
    ("east", 24, 3),
    ("east", 26, 4),
    ("east", 28, 3),
    ("east", 30, 5),
    ("east", 32, 3),
    ("east", 34, 4),
    ("east", 36, 3),
    ("west", 8, 13),
    ("west", 10, 12),
    ("west", 12, 13),
    ("west", 14, 11),
    ("west", 16, 13),
    ("west", 18, 12),
    ("west", 20, 13),
    ("west", 22, 10),
    ("west", 24, 13),
    ("west", 26, 12),
    ("west", 28, 13),
    ("west", 30, 11),
    ("west", 32, 13),
    ("west", 34, 12),
    ("west", 36, 13),
    ("south", 42, 3),
    ("south", 44, 4),
    ("south", 46, 3),
    ("south", 48, 5),
    ("south", 50, 3),
    ("south", 52, 4),
    ("south", 54, 3),
    ("south", 56, 6),
    ("south", 58, 3),
    ("south", 60, 4),
    ("south", 62, 3),
    ("south", 64, 5),
    ("south", 66, 3),
    ("south", 68, 4),
    ("south", 70, 3),
    ("midwest", 42, 13),
    ("midwest", 44, 12),
    ("midwest", 46, 13),
    ("midwest", 48, 11),
    ("midwest", 50, 13),
    ("midwest", 52, 12),
    ("midwest", 54, 13),
    ("midwest", 56, 10),
    ("midwest", 58, 13),
    ("midwest", 60, 12),
    ("midwest", 62, 13),
    ("midwest", 64, 11),
    ("midwest", 66, 13),
    ("midwest", 68, 12),
    ("midwest", 70, 13),
    ("nat", 33, 7),
    ("nat", 33, 9),
    ("nat", 42, 8),
)

# National cells (row, col, points) — used by example_bracket_points_for_cell
_NAT_CELLS: tuple[tuple[int, int, float], ...] = (
    (33, 7, 8.0),
    (33, 9, 8.0),
    (42, 8, 12.0),
)


def _points_regional(r: int, c: int) -> float:
    """Points for a regional pick from column index (default grid layout)."""
    if c in (3, 13):
        return 1.0
    if c in (4, 12):
        return 2.0
    if c in (5, 11):
        return 4.0
    if c in (6, 10):
        return 6.0
    return 0.0


def example_bracket_points_for_cell(r: int, c: int) -> float:
    for nr, nc, pts in _NAT_CELLS:
        if r == nr and c == nc:
            return pts
    return _points_regional(r, c)


def example_bracket_game_id(region_or_nat: str, r: int, c: int) -> str:
    return f"{EXAMPLE_BRACKET_ID_PREFIX}_{region_or_nat}_{r}_{c}"


def extract_participant_name(df: pd.DataFrame) -> str | None:
    """Parse 'NAME:______MATT_______' from row 1, column 0."""
    if len(df) < 2:
        return None
    cell = df.iloc[1, 0]
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return None
    s = str(cell).strip()
    m = re.search(r"NAME:\s*_*([A-Za-z0-9][A-Za-z0-9\s'.-]*?)\s*_*\s*$", s, re.I)
    if m:
        return re.sub(r"\s+", " ", m.group(1).strip())
    return None


def _skip_pick_text(s: str) -> bool:
    u = s.upper()
    if "CHAMPION" in u and "NCAA" in u:
        return True
    if "NCAA" in u and "CHAMPION" in u:
        return True
    return False


def parse_example_bracket_grid(df: pd.DataFrame) -> tuple[dict[str, str], dict[str, float]]:
    """
    Read all 63 tournament pick cells into picks and per-game point weights.
    Keys look like ``example_bracket_east_8_3``.
    """
    picks: dict[str, str] = {}
    weights: dict[str, float] = {}

    for region, r, c in _EXAMPLE_BRACKET_SLOTS:
        pts = example_bracket_points_for_cell(r, c)
        v = df.iloc[r, c] if r < len(df) and c < len(df.columns) else None
        if v is None or (isinstance(v, float) and pd.isna(v)):
            continue
        s = str(v).strip()
        if len(s) < 2 or _skip_pick_text(s):
            continue
        gid = example_bracket_game_id(region, r, c)
        picks[gid] = s
        weights[gid] = pts

    return picks, weights


def find_example_bracket_sheet_name(sheet_names: list[str]) -> str | None:
    """Prefer a sheet whose name contains ``example_bracket``, else common bracket sheet names."""
    for name in sheet_names:
        if "example_bracket" in name.lower():
            return name
    for name in sheet_names:
        low = name.lower()
        if "basketball_bracket" in low:
            return name
        if "basketball" in low and "bracket" in low:
            return name
    return None


def load_example_bracket_participant(path: Path, sheet_name: str | None = None) -> tuple[ParticipantPicks | None, list[str]]:
    """Load one .xls grid-style workbook as a single participant."""
    issues: list[str] = []
    path = Path(path)
    if path.suffix.lower() not in {".xls"}:
        issues.append(f"{path.name}: example bracket parser expects .xls")
        return None, issues

    try:
        xl = pd.ExcelFile(path, engine="xlrd")
    except Exception as e:
        issues.append(f"{path.name}: cannot open ({e})")
        return None, issues

    sheet = sheet_name or find_example_bracket_sheet_name(xl.sheet_names)
    if not sheet:
        issues.append(f"{path.name}: no sheet named like *example_bracket* or *basketball_bracket*")
        return None, issues

    try:
        df = pd.read_excel(path, sheet_name=sheet, header=None, engine="xlrd")
    except Exception as e:
        issues.append(f"{path.name} [{sheet}]: read failed ({e})")
        return None, issues

    name = extract_participant_name(df) or path.stem
    picks, _weights = parse_example_bracket_grid(df)
    if len(picks) < 60:
        issues.append(
            f"{path.name}: expected ~63 picks, got {len(picks)} — check layout matches the default grid template."
        )
    if not picks:
        issues.append(f"{path.name}: no bracket picks parsed.")
        return None, issues

    return ParticipantPicks(name=name, picks=picks), issues


def example_bracket_default_weights() -> dict[str, float]:
    """All 63 game ids with point values (for results templates)."""
    return {
        example_bracket_game_id(region, r, c): example_bracket_points_for_cell(r, c)
        for region, r, c in _EXAMPLE_BRACKET_SLOTS
    }
