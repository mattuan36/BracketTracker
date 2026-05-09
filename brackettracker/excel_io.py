from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

RESULTS_SHEET_NAMES = frozenset({"results", "actuals", "answer", "answers", "truth"})


def _norm_header(s: Any) -> str:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    return str(s).strip().lower()


def _find_column(df: pd.DataFrame, *candidates: str) -> str | None:
    if df.empty or len(df.columns) == 0:
        return None
    lowered = {_norm_header(c): c for c in df.columns}
    for cand in candidates:
        if cand in lowered:
            return lowered[cand]
    return None


def _sheet_key(name: str) -> str:
    return re.sub(r"\s+", " ", str(name).strip())


@dataclass
class GameRow:
    game_id: str
    winner: str | None
    points: float


@dataclass
class ParticipantPicks:
    name: str
    picks: dict[str, str] = field(default_factory=dict)


@dataclass
class SheetNeedsReview:
    """A workbook sheet (or whole .xls bracket file) that could not be scored."""

    workbook: str
    sheet: str
    reasons: list[str] = field(default_factory=list)

    def format_issue_line(self) -> str:
        detail = " | ".join(self.reasons) if self.reasons else "No details."
        return f"[needs review] {self.workbook} / {self.sheet}: {detail}"


def _excel_engine(path: Path) -> str:
    return "xlrd" if path.suffix.lower() == ".xls" else "openpyxl"


def _read_sheet_table(path: Path, sheet: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=sheet, engine=_excel_engine(path))
    if df.empty:
        return df
    df = df.rename(columns={c: _norm_header(c) for c in df.columns})
    return df


def load_results_from_sheet(path: Path, sheet: str) -> tuple[dict[str, GameRow], list[str]]:
    """Parse a Results-style sheet: game id, winner (blank = not decided), optional points."""
    df = _read_sheet_table(path, sheet)
    issues: list[str] = []
    game_col = _find_column(df, "game", "game_id", "id", "match", "matchup")
    win_col = _find_column(df, "winner", "actual", "result", "champion")

    if not game_col or not win_col:
        issues.append(
            f"{path.name} [{sheet}]: need columns like 'Game' and 'Winner' "
            f"(found game={game_col!r}, winner={win_col!r})."
        )
        return {}, issues

    pts_col = _find_column(df, "points", "pts", "value", "weight")
    out: dict[str, GameRow] = {}
    for _, row in df.iterrows():
        gid_raw = row.get(game_col)
        if gid_raw is None or (isinstance(gid_raw, float) and pd.isna(gid_raw)):
            continue
        gid = str(gid_raw).strip()
        if not gid:
            continue
        w = row.get(win_col)
        winner: str | None
        if w is None or (isinstance(w, float) and pd.isna(w)) or str(w).strip() == "":
            winner = None
        else:
            winner = str(w).strip()

        pts = 1.0
        if pts_col:
            p = row.get(pts_col)
            if p is not None and not (isinstance(p, float) and pd.isna(p)):
                try:
                    pts = float(p)
                except (TypeError, ValueError):
                    issues.append(f"{path.name} [{sheet}] game {gid!r}: invalid Points, using 1.")
                    pts = 1.0

        if gid in out:
            issues.append(f"{path.name} [{sheet}]: duplicate game id {gid!r}, last row wins.")
        out[gid] = GameRow(game_id=gid, winner=winner, points=pts)

    return out, issues


def load_picks_from_sheet(path: Path, sheet: str) -> tuple[ParticipantPicks | None, list[str]]:
    """Parse a participant sheet: game id, pick."""
    df = _read_sheet_table(path, sheet)
    issues: list[str] = []
    if df.empty:
        issues.append(f"{path.name} [{sheet}]: empty sheet, skipped.")
        return None, issues

    game_col = _find_column(df, "game", "game_id", "id", "match", "matchup")
    pick_col = _find_column(df, "pick", "picks", "choice", "team", "selection")

    if not game_col or not pick_col:
        issues.append(
            f"{path.name} [{sheet}]: need 'Game' and 'Pick' columns "
            f"(found game={game_col!r}, pick={pick_col!r})."
        )
        return None, issues

    name = _sheet_key(sheet)
    picks: dict[str, str] = {}
    for _, row in df.iterrows():
        gid_raw = row.get(game_col)
        if gid_raw is None or (isinstance(gid_raw, float) and pd.isna(gid_raw)):
            continue
        gid = str(gid_raw).strip()
        if not gid:
            continue
        pk = row.get(pick_col)
        if pk is None or (isinstance(pk, float) and pd.isna(pk)):
            continue
        picks[gid] = str(pk).strip()

    if not picks:
        issues.append(f"{path.name} [{sheet}]: no picks found.")
        return None, issues

    return ParticipantPicks(name=name, picks=picks), issues


def _is_results_sheet(name: str) -> bool:
    key = _norm_header(name).replace(" ", "_")
    return key in RESULTS_SHEET_NAMES


def discover_excel_files(folder: Path) -> list[Path]:
    return sorted(
        p for p in folder.iterdir() if p.suffix.lower() in {".xlsx", ".xlsm", ".xls"} and p.is_file()
    )


def load_folder(
    folder: Path,
    results_file: Path | None = None,
    results_sheet: str | None = None,
) -> tuple[dict[str, GameRow], list[ParticipantPicks], list[str], list[SheetNeedsReview]]:
    """
    Load all workbooks in folder. Sheets named like 'Results' hold actual outcomes;
    each other sheet with Game/Pick columns is a participant (xlsx), or each grid-style
    .xls file with an *example_bracket* or *basketball_bracket* sheet is one participant.

    Sheets that fail validation or raise while loading are **not** scored; they appear in
    ``sheets_needing_review`` (and a one-line summary is appended to ``issues``).
    """
    from brackettracker.example_bracket import load_example_bracket_participant

    issues: list[str] = []
    sheets_needing_review: list[SheetNeedsReview] = []
    files = discover_excel_files(folder)
    if not files:
        issues.append(f"No Excel files (.xlsx/.xlsm/.xls) in {folder}")
        return {}, [], issues, sheets_needing_review

    results: dict[str, GameRow] = {}

    # --- Load results ---
    candidates: list[tuple[Path, str]] = []
    if results_file is not None:
        rp = Path(results_file)
        if not rp.is_file():
            issues.append(f"--results file not found: {rp}")
        else:
            try:
                xl = pd.ExcelFile(rp, engine=_excel_engine(rp))
                if results_sheet:
                    candidates.append((rp, results_sheet))
                else:
                    for s in xl.sheet_names:
                        if _is_results_sheet(s):
                            candidates.append((rp, s))
                    if not candidates:
                        candidates.append((rp, xl.sheet_names[0]))
            except Exception as e:
                issues.append(f"Could not open results file {rp.name}: {e}")

    if not candidates:
        preferred = [p for p in files if p.stem.lower() in {"results", "_results", "actuals", "answer"}]
        scan_files = preferred if len(preferred) == 1 else files
        for p in scan_files:
            try:
                xl = pd.ExcelFile(p, engine=_excel_engine(p))
                for s in xl.sheet_names:
                    if _is_results_sheet(s):
                        candidates.append((p, s))
                        break
                if candidates:
                    break
            except Exception as e:
                issues.append(f"Could not open {p.name}: {e}")

    for rp, s in candidates[:1]:
        r, iss = load_results_from_sheet(rp, s)
        issues.extend(iss)
        results.update(r)
        if r:
            break

    # --- Load participants: example-bracket .xls (one bracket per file) or xlsx sheets ---
    participants: list[ParticipantPicks] = []
    seen_names: set[str] = set()

    def _record_review(workbook_name: str, sheet_label: str, reasons: list[str]) -> None:
        reasons = [r for r in reasons if r]
        if not reasons:
            reasons = ["Invalid or unreadable sheet."]
        sheets_needing_review.append(
            SheetNeedsReview(workbook=workbook_name, sheet=sheet_label, reasons=reasons)
        )

    for p in files:
        if p.suffix.lower() == ".xls":
            try:
                part, iss = load_example_bracket_participant(p)
            except Exception as e:
                _record_review(p.name, "(grid bracket)", [f"{type(e).__name__}: {e}"])
                continue
            if part is None:
                _record_review(p.name, "(grid bracket)", list(iss))
                continue
            issues.extend(iss)
            label = f"{p.stem} — {part.name}" if len(files) > 1 else part.name
            if label in seen_names:
                label = f"{p.stem} — {part.name} ({p.name})"
            seen_names.add(label)
            part.name = label
            participants.append(part)
            continue

        try:
            xl = pd.ExcelFile(p, engine="openpyxl")
        except Exception as e:
            _record_review(p.name, "(entire workbook)", [f"Could not open file: {type(e).__name__}: {e}"])
            continue

        for s in xl.sheet_names:
            if _is_results_sheet(s):
                continue
            try:
                part, iss = load_picks_from_sheet(p, s)
            except Exception as e:
                _record_review(p.name, s, [f"{type(e).__name__}: {e}"])
                continue
            if part is None:
                _record_review(p.name, s, list(iss))
                continue
            issues.extend(iss)
            label = f"{p.stem} — {part.name}" if len(files) > 1 else part.name
            if label in seen_names:
                label = f"{p.stem} — {part.name} ({p.name})"
            seen_names.add(label)
            part.name = label
            participants.append(part)

    if not participants:
        issues.append(
            "No participants found. Use grid-style .xls bracket files or xlsx sheets with 'Game' and 'Pick'."
        )

    return results, participants, issues, sheets_needing_review
