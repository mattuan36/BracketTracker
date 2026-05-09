"""
Simple desktop UI for BracketTracker (tkinter).

Run: python gui.py
Run with virtual environment: .\.venv\Scripts\python gui.py
"""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from brackettracker.app_core import run_scoring
from brackettracker.example_bracket import load_example_bracket_participant
from brackettracker.report import plot_leaderboard, save_standings_csv, standings_table


def _browse_dir(var: tk.StringVar) -> None:
    p = filedialog.askdirectory()
    if p:
        var.set(p)


def _browse_file(var: tk.StringVar, title: str, filetypes: list[tuple[str, str]]) -> None:
    p = filedialog.askopenfilename(title=title, filetypes=filetypes)
    if p:
        var.set(p)


def _browse_save_csv(var: tk.StringVar) -> None:
    p = filedialog.asksaveasfilename(
        title="Save standings as CSV",
        defaultextension=".csv",
        filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
    )
    if p:
        var.set(p)


def _browse_save_png(var: tk.StringVar) -> None:
    p = filedialog.asksaveasfilename(
        title="Save chart as PNG",
        defaultextension=".png",
        filetypes=[("PNG", "*.png"), ("All files", "*.*")],
    )
    if p:
        var.set(p)


def verify_example_bracket(path_str: str, log: scrolledtext.ScrolledText) -> None:
    log.delete("1.0", tk.END)
    p = Path(path_str.strip())
    if not p.is_file():
        log.insert(tk.END, "Choose a valid .xls example bracket file.\n")
        return
    if p.suffix.lower() != ".xls":
        log.insert(tk.END, "Example bracket should be a .xls file.\n")
        return
    part, issues = load_example_bracket_participant(p)
    lines: list[str] = []
    for msg in issues:
        lines.append(f"[info] {msg}\n")
    if not part:
        log.insert(tk.END, "".join(lines) or "Could not load bracket.\n")
        return
    sample = list(part.picks.items())[:5]
    lines.append(f"Participant name: {part.name}\n")
    lines.append(f"Picks loaded: {len(part.picks)} (expect 63 for full template)\n\n")
    lines.append("Sample game ids → picks:\n")
    for gid, team in sample:
        lines.append(f"  {gid} → {team}\n")
    log.insert(tk.END, "".join(lines))


def run_scoring_action(
    folder_var: tk.StringVar,
    results_var: tk.StringVar,
    sheet_var: tk.StringVar,
    csv_var: tk.StringVar,
    chart_var: tk.StringVar,
    log: scrolledtext.ScrolledText,
    run_btn: ttk.Button,
    status: tk.StringVar,
) -> None:
    log.delete("1.0", tk.END)
    folder = folder_var.get().strip()
    if not folder:
        messagebox.showwarning("Folder", "Select the folder that contains bracket files.")
        return

    csv_out = csv_var.get().strip()
    if not csv_out:
        messagebox.showwarning("Output", "Choose where to save the standings CSV.")
        return

    results_path = results_var.get().strip()
    rf = Path(results_path) if results_path else None
    sheet = sheet_var.get().strip() or None
    chart_path = chart_var.get().strip()

    root = run_btn.winfo_toplevel()

    def worker() -> None:
        try:
            rows, issues, err, needs_review = run_scoring(Path(folder), results_file=rf, results_sheet=sheet)

            def _log_needs_review() -> None:
                if not needs_review:
                    return
                log.insert(tk.END, "\nSheets needing manual review / correction:\n")
                for rev in needs_review:
                    log.insert(tk.END, f"  • {rev.workbook} — {rev.sheet}\n")
                    for reason in rev.reasons:
                        log.insert(tk.END, f"      {reason}\n")
                log.insert(tk.END, "\n")

            def finish_fail() -> None:
                run_btn.state(["!disabled"])
                status.set("Ready")
                for msg in issues:
                    log.insert(tk.END, f"{msg}\n")
                if issues:
                    log.insert(tk.END, "\n")
                _log_needs_review()
                log.insert(tk.END, f"{err}\n")
                messagebox.showerror("Scoring failed", err)

            def finish_success() -> None:
                run_btn.state(["!disabled"])
                status.set("Ready")
                for msg in issues:
                    log.insert(tk.END, f"{msg}\n")
                if issues:
                    log.insert(tk.END, "\n")
                _log_needs_review()

                import pandas as pd

                df = standings_table(rows)
                with pd.option_context("display.max_rows", None, "display.max_columns", None, "display.width", 120):
                    table_txt = df.to_string(index=False)
                log.insert(tk.END, table_txt + "\n")

                save_standings_csv(rows, Path(csv_out).resolve())
                log.insert(tk.END, f"\nWrote CSV: {csv_out}\n")

                if chart_path:
                    try:
                        plot_leaderboard(rows, Path(chart_path).resolve())
                        log.insert(tk.END, f"Wrote chart: {chart_path}\n")
                    except Exception as e:
                        log.insert(tk.END, f"Chart failed: {e}\n")

                log.see(tk.END)
                messagebox.showinfo("Done", "Standings saved.")

            if err:
                root.after(0, finish_fail)
            else:
                root.after(0, finish_success)

        except Exception as e:
            def finish_exc() -> None:
                run_btn.state(["!disabled"])
                status.set("Ready")
                log.insert(tk.END, f"Error: {e}\n")
                messagebox.showerror("Error", str(e))

            root.after(0, finish_exc)

    run_btn.state(["disabled"])
    status.set("Running…")
    threading.Thread(target=worker, daemon=True).start()


def main() -> None:
    root = tk.Tk()
    root.title("BracketTracker")
    root.minsize(720, 560)

    pad = {"padx": 8, "pady": 4}
    folder_var = tk.StringVar()
    example_var = tk.StringVar()
    results_var = tk.StringVar()
    sheet_var = tk.StringVar()
    csv_var = tk.StringVar(value=str(Path.cwd() / "standings.csv"))
    chart_var = tk.StringVar()
    status = tk.StringVar(value="Ready")

    frm = ttk.Frame(root, padding=12)
    frm.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    frm.columnconfigure(1, weight=1)

    r = 0
    ttk.Label(frm, text="Bracket folder *").grid(row=r, column=0, sticky="w", **pad)
    ttk.Entry(frm, textvariable=folder_var, width=56).grid(row=r, column=1, sticky="ew", **pad)
    ttk.Button(frm, text="Browse…", command=lambda: _browse_dir(folder_var)).grid(row=r, column=2, **pad)
    r += 1

    ttk.Label(frm, text="Example bracket (.xls)").grid(row=r, column=0, sticky="nw", **pad)
    ex_frame = ttk.Frame(frm)
    ex_frame.grid(row=r, column=1, columnspan=2, sticky="ew", **pad)
    ex_frame.columnconfigure(0, weight=1)
    ttk.Entry(ex_frame, textvariable=example_var, width=56).grid(row=0, column=0, sticky="ew", padx=(0, 8))
    ttk.Button(ex_frame, text="Browse…", command=lambda: _browse_file(example_var, "Example bracket", [("Excel", "*.xls"), ("All", "*.*")])).grid(row=0, column=1)
    r += 1

    ttk.Label(frm, text="Results file (optional)").grid(row=r, column=0, sticky="w", **pad)
    res_frame = ttk.Frame(frm)
    res_frame.grid(row=r, column=1, columnspan=2, sticky="ew", **pad)
    res_frame.columnconfigure(0, weight=1)
    ttk.Entry(res_frame, textvariable=results_var, width=56).grid(row=0, column=0, sticky="ew", padx=(0, 8))
    ttk.Button(
        res_frame,
        text="Browse…",
        command=lambda: _browse_file(results_var, "Results workbook", [("Excel", "*.xlsx *.xls"), ("All", "*.*")]),
    ).grid(row=0, column=1)
    r += 1

    ttk.Label(frm, text="Results sheet (optional)").grid(row=r, column=0, sticky="w", **pad)
    ttk.Entry(frm, textvariable=sheet_var, width=56).grid(row=r, column=1, columnspan=2, sticky="ew", **pad)
    r += 1

    ttk.Label(frm, text="Output CSV *").grid(row=r, column=0, sticky="w", **pad)
    out_frame = ttk.Frame(frm)
    out_frame.grid(row=r, column=1, columnspan=2, sticky="ew", **pad)
    out_frame.columnconfigure(0, weight=1)
    ttk.Entry(out_frame, textvariable=csv_var, width=56).grid(row=0, column=0, sticky="ew", padx=(0, 8))
    ttk.Button(out_frame, text="Save as…", command=lambda: _browse_save_csv(csv_var)).grid(row=0, column=1)
    r += 1

    ttk.Label(frm, text="Output chart PNG (optional)").grid(row=r, column=0, sticky="w", **pad)
    chart_frame = ttk.Frame(frm)
    chart_frame.grid(row=r, column=1, columnspan=2, sticky="ew", **pad)
    chart_frame.columnconfigure(0, weight=1)
    ttk.Entry(chart_frame, textvariable=chart_var, width=56).grid(row=0, column=0, sticky="ew", padx=(0, 8))
    ttk.Button(chart_frame, text="Save as…", command=lambda: _browse_save_png(chart_var)).grid(row=0, column=1)
    r += 1

    btn_row = ttk.Frame(frm)
    btn_row.grid(row=r, column=0, columnspan=3, pady=12)
    verify_btn = ttk.Button(
        btn_row,
        text="Verify example bracket",
        command=lambda: verify_example_bracket(example_var.get(), log),
    )
    verify_btn.pack(side=tk.LEFT, padx=4)
    run_btn = ttk.Button(btn_row, text="Run scoring")
    run_btn.pack(side=tk.LEFT, padx=4)
    r += 1

    ttk.Label(frm, textvariable=status, foreground="#555").grid(row=r, column=0, columnspan=3, sticky="w", padx=8)
    r += 1

    ttk.Label(frm, text="Log & standings").grid(row=r, column=0, sticky="nw", **pad)
    log = scrolledtext.ScrolledText(frm, height=18, width=88, font=("Consolas", 10))
    log.grid(row=r, column=1, columnspan=2, sticky="nsew", **pad)
    frm.rowconfigure(r, weight=1)

    run_btn.configure(
        command=lambda: run_scoring_action(
            folder_var,
            results_var,
            sheet_var,
            csv_var,
            chart_var,
            log,
            run_btn,
            status,
        )
    )

    root.mainloop()


if __name__ == "__main__":
    main()
