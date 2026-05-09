from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from brackettracker.scoring import PersonScore


def standings_table(rows: list[PersonScore]) -> pd.DataFrame:
    data = [
        {
            "Rank": i + 1,
            "Name": r.name,
            "Points": round(r.points_earned, 4),
            "Max possible": round(r.max_possible, 4),
            "Correct (decided)": r.correct_known,
            "Games picked": r.games_counted,
        }
        for i, r in enumerate(rows)
    ]
    return pd.DataFrame(data)


def print_standings(rows: list[PersonScore]) -> None:
    df = standings_table(rows)
    with pd.option_context("display.max_rows", None, "display.max_columns", None, "display.width", 120):
        print(df.to_string(index=False))


def save_standings_csv(rows: list[PersonScore], path: Path) -> None:
    standings_table(rows).to_csv(path, index=False)


def plot_leaderboard(rows: list[PersonScore], path: Path | None, title: str = "Bracket standings") -> None:
    if not rows:
        return
    names = [r.name for r in rows]
    pts = [r.points_earned for r in rows]
    fig, ax = plt.subplots(figsize=(max(8, len(names) * 0.35), 5))
    ax.barh(names[::-1], pts[::-1], color="#2e7d32")
    ax.set_xlabel("Points")
    ax.set_title(title)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
