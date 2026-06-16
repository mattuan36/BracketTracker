"""
Simple desktop UI for BracketTracker (tkinter).

Run: python gui.py
Run with virtual environment: .\\.venv\\Scripts\\python gui.py
"""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from brackettracker.app_core import run_scoring
from brackettracker.example_bracket import (
    _EXAMPLE_BRACKET_SLOTS,
    example_bracket_game_id,
    load_example_bracket_participant,
)
from brackettracker.report import plot_leaderboard, save_standings_csv
from brackettracker.scoring import PersonScore

_CELL_W = 50
_CELL_H = 11
_BRACKET_PAD = 4
_ROUND_HEADER_H = 22
_REGION_HEADER_H = 8
_BRACKET_TITLE_H = _ROUND_HEADER_H + _REGION_HEADER_H
_TOP_ROW_BASE = 8
_BOTTOM_ROW_BASE = 42
_LEFT_DEPTH = {3: 0, 4: 1, 5: 2, 6: 3}
_WEST_EXCEL_COL = {13: 3, 12: 4, 11: 5, 10: 6}
_LEFT_BLOCK_END = 3
_RIGHT_BLOCK_START = 7
_RIGHT_BLOCK_END = 10
_FINALS_SEMI_ROW = 12
_FINALS_CHAMP_ROW = 15
_FINALS_SEMI_LEFT_COL = 4
_FINALS_CHAMP_COL = 5
_FINALS_SEMI_RIGHT_COL = 6
_BOTTOM_HALF_OFFSET = 16
_LINE_COLOR = "#9e9e9e"
_ROUND_LABELS_LEFT = ("First Round", "Second Round", "Sweet 16", "Elite 8")
_ROUND_LABELS_CENTER = ("Final 4", "National Champion", "Final 4")

# Each tuple: feeder row A, feeder row B, winner row, feeder column, winner column (left-side tree).
_REGIONAL_PAIR_EDGES: tuple[tuple[int, int, int, int, int], ...] = (
    (0, 2, 1, 0, 1),
    (4, 6, 5, 0, 1),
    (8, 10, 9, 0, 1),
    (12, 14, 13, 0, 1),
    (1, 5, 3, 1, 2),
    (9, 13, 11, 1, 2),
    (3, 11, 7, 2, 3),
)


def _left_col(excel_col: int) -> int:
    return _LEFT_DEPTH[excel_col]


def _right_col(excel_col: int) -> int:
    """Mirror of left columns: outer rounds on the right edge, inner rounds toward center."""
    return _RIGHT_BLOCK_END - _LEFT_DEPTH[_WEST_EXCEL_COL[excel_col]]


def _compact_slot_xy(region: str, excel_row: int, excel_col: int) -> tuple[int, int]:
    """Map sparse Excel coordinates to a tight visual grid."""
    if region == "east":
        return _left_col(excel_col), (excel_row - _TOP_ROW_BASE) // 2
    if region == "west":
        return _right_col(excel_col), (excel_row - _TOP_ROW_BASE) // 2
    if region == "south":
        return _left_col(excel_col), _BOTTOM_HALF_OFFSET + (excel_row - _BOTTOM_ROW_BASE) // 2
    if region == "midwest":
        return _right_col(excel_col), _BOTTOM_HALF_OFFSET + (excel_row - _BOTTOM_ROW_BASE) // 2
    if excel_row == 33:
        col = _FINALS_SEMI_LEFT_COL if excel_col == 7 else _FINALS_SEMI_RIGHT_COL
        return col, _FINALS_SEMI_ROW
    return _FINALS_CHAMP_COL, _FINALS_CHAMP_ROW


def _bracket_pixel_xy(col_idx: int | float, row_idx: int | float) -> tuple[int, int]:
    x = _BRACKET_PAD + int(col_idx * _CELL_W)
    y = _BRACKET_PAD + _BRACKET_TITLE_H + int(row_idx * _CELL_H)
    return x, y


def _cell_box(col_idx: int, row_idx: int) -> tuple[int, int, int, int]:
    x0, y0 = _bracket_pixel_xy(col_idx, row_idx)
    return x0, y0, x0 + _CELL_W - 1, y0 + _CELL_H - 1


def _draw_round_headers(canvas: tk.Canvas) -> None:
    y = _BRACKET_PAD + _ROUND_HEADER_H // 2
    label_width = _CELL_W - 4
    for col_idx, label in enumerate(_ROUND_LABELS_LEFT):
        x0, _, x1, _ = _cell_box(col_idx, 0)
        canvas.create_text(
            (x0 + x1) // 2,
            y,
            text=label,
            fill="#555",
            font=("Segoe UI", 6, "bold"),
            width=label_width,
            justify=tk.CENTER,
        )
    for offset, label in enumerate(_ROUND_LABELS_LEFT):
        col_idx = _RIGHT_BLOCK_END - offset
        x0, _, x1, _ = _cell_box(col_idx, 0)
        canvas.create_text(
            (x0 + x1) // 2,
            y,
            text=label,
            fill="#555",
            font=("Segoe UI", 6, "bold"),
            width=label_width,
            justify=tk.CENTER,
        )
    for col_idx, label in zip(
        (_FINALS_SEMI_LEFT_COL, _FINALS_CHAMP_COL, _FINALS_SEMI_RIGHT_COL),
        _ROUND_LABELS_CENTER,
    ):
        x0, _, x1, _ = _cell_box(col_idx, 0)
        canvas.create_text(
            (x0 + x1) // 2,
            y,
            text=label,
            fill="#555",
            font=("Segoe UI", 6, "bold"),
            width=label_width,
            justify=tk.CENTER,
        )


def _draw_connector_pair(
    canvas: tk.Canvas,
    col_feed: int,
    row_a: int,
    row_b: int,
    col_win: int,
    row_win: int,
    *,
    mirror: bool,
) -> None:
    x0a, y0a, x1a, y1a = _cell_box(col_feed, row_a)
    x0b, y0b, x1b, y1b = _cell_box(col_feed, row_b)
    x_wl, y0w, x_wr, y1w = _cell_box(col_win, row_win)
    y_a = (y0a + y1a) // 2
    y_b = (y0b + y1b) // 2
    y_w = (y0w + y1w) // 2
    y_win = (y_a + y_b) // 2
    stub = max(5, _CELL_W // 5)

    if not mirror:
        mid_x = x1a + stub
        canvas.create_line(x1a, y_a, mid_x, y_a, fill=_LINE_COLOR)
        canvas.create_line(x1a, y_b, mid_x, y_b, fill=_LINE_COLOR)
        canvas.create_line(mid_x, y_a, mid_x, y_b, fill=_LINE_COLOR)
        canvas.create_line(mid_x, y_win, x_wl, y_w, fill=_LINE_COLOR)
    else:
        mid_x = x0a - stub
        canvas.create_line(x0a, y_a, mid_x, y_a, fill=_LINE_COLOR)
        canvas.create_line(x0a, y_b, mid_x, y_b, fill=_LINE_COLOR)
        canvas.create_line(mid_x, y_a, mid_x, y_b, fill=_LINE_COLOR)
        canvas.create_line(mid_x, y_win, x_wr, y_w, fill=_LINE_COLOR)


_E8_COL_LEFT = 3
_E8_COL_RIGHT = 7
_E8_ROW_TOP = 7
_E8_ROW_BOTTOM = 7 + _BOTTOM_HALF_OFFSET


def _draw_e8_to_f4(
    canvas: tk.Canvas,
    col_e8: int,
    row_e8: int,
    col_f4: int,
    row_f4: int,
) -> None:
    """Direct bracket line from a regional E8 cell to a semifinal F4 cell."""
    x0e, y0e, x1e, y1e = _cell_box(col_e8, row_e8)
    x0f, y0f, x1f, y1f = _cell_box(col_f4, row_f4)
    y_e = (y0e + y1e) // 2
    y_f = (y0f + y1f) // 2
    stub = max(5, _CELL_W // 5)

    if col_e8 < col_f4:
        mid_x = x1e + stub
        canvas.create_line(x1e, y_e, mid_x, y_e, fill=_LINE_COLOR)
        canvas.create_line(mid_x, y_e, mid_x, y_f, fill=_LINE_COLOR)
        canvas.create_line(mid_x, y_f, x0f, y_f, fill=_LINE_COLOR)
    else:
        mid_x = x0e - stub
        canvas.create_line(x0e, y_e, mid_x, y_e, fill=_LINE_COLOR)
        canvas.create_line(mid_x, y_e, mid_x, y_f, fill=_LINE_COLOR)
        canvas.create_line(mid_x, y_f, x1f, y_f, fill=_LINE_COLOR)


def _draw_connector_semis_to_champ(canvas: tk.Canvas) -> None:
    _, _, x1l, y1l = _cell_box(_FINALS_SEMI_LEFT_COL, _FINALS_SEMI_ROW)
    x0l, y0l, _, _ = _cell_box(_FINALS_SEMI_LEFT_COL, _FINALS_SEMI_ROW)
    y_l = (y0l + y1l) // 2
    x0r, y0r, x1r, y1r = _cell_box(_FINALS_SEMI_RIGHT_COL, _FINALS_SEMI_ROW)
    y_r = (y0r + y1r) // 2
    x_wl, y0w, x_wr, y1w = _cell_box(_FINALS_CHAMP_COL, _FINALS_CHAMP_ROW)
    y_w = (y0w + y1w) // 2
    mid_x = (x1l + x0r) // 2
    mid_y = (y_l + y_r) // 2
    canvas.create_line(x1l, y_l, mid_x, y_l, fill=_LINE_COLOR)
    canvas.create_line(x0r, y_r, mid_x, y_r, fill=_LINE_COLOR)
    canvas.create_line(mid_x, y_l, mid_x, y_r, fill=_LINE_COLOR)
    canvas.create_line(mid_x, mid_y, mid_x, y0w, fill=_LINE_COLOR)
    canvas.create_line(mid_x, y_w, x_wl, y_w, fill=_LINE_COLOR)
    canvas.create_line(mid_x, y_w, x_wr, y_w, fill=_LINE_COLOR)


def _draw_bracket_linework(canvas: tk.Canvas) -> None:
    for row_a, row_b, row_win, col_feed, col_win in _REGIONAL_PAIR_EDGES:
        _draw_connector_pair(canvas, col_feed, row_a, row_b, col_win, row_win, mirror=False)
        right_feed = _RIGHT_BLOCK_END - col_feed
        right_win = _RIGHT_BLOCK_END - col_win
        _draw_connector_pair(canvas, right_feed, row_a, row_b, right_win, row_win, mirror=True)
        _draw_connector_pair(
            canvas,
            col_feed,
            row_a + _BOTTOM_HALF_OFFSET,
            row_b + _BOTTOM_HALF_OFFSET,
            col_win,
            row_win + _BOTTOM_HALF_OFFSET,
            mirror=False,
        )
        _draw_connector_pair(
            canvas,
            right_feed,
            row_a + _BOTTOM_HALF_OFFSET,
            row_b + _BOTTOM_HALF_OFFSET,
            right_win,
            row_win + _BOTTOM_HALF_OFFSET,
            mirror=True,
        )

    _draw_e8_to_f4(canvas, _E8_COL_LEFT, _E8_ROW_TOP, _FINALS_SEMI_LEFT_COL, _FINALS_SEMI_ROW)
    _draw_e8_to_f4(canvas, _E8_COL_RIGHT, _E8_ROW_TOP, _FINALS_SEMI_LEFT_COL, _FINALS_SEMI_ROW)
    _draw_e8_to_f4(canvas, _E8_COL_LEFT, _E8_ROW_BOTTOM, _FINALS_SEMI_RIGHT_COL, _FINALS_SEMI_ROW)
    _draw_e8_to_f4(canvas, _E8_COL_RIGHT, _E8_ROW_BOTTOM, _FINALS_SEMI_RIGHT_COL, _FINALS_SEMI_ROW)
    _draw_connector_semis_to_champ(canvas)


def _draw_pick_cell(
    canvas: tk.Canvas,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    pick: str,
    *,
    mirror: bool = False,
    center: bool = False,
    fill: str | None = None,
    outline: str = "#bbb",
) -> None:
    cell_fill = fill or ("#e8f5e9" if pick else "#f5f5f5")
    canvas.create_rectangle(x0, y0, x1, y1, outline=outline, fill=cell_fill)
    if pick:
        if center:
            canvas.create_text(
                x0 + (x1 - x0) // 2,
                y0 + _CELL_H // 2,
                text=_truncate(pick),
                anchor=tk.CENTER,
                font=("Segoe UI", 7),
            )
        elif mirror:
            canvas.create_text(
                x1 - 3,
                y0 + _CELL_H // 2,
                text=_truncate(pick),
                anchor=tk.E,
                font=("Segoe UI", 7),
            )
        else:
            canvas.create_text(
                x0 + 3,
                y0 + _CELL_H // 2,
                text=_truncate(pick),
                anchor=tk.W,
                font=("Segoe UI", 7),
            )


def _bracket_content_size() -> tuple[int, int]:
    """Fixed pixel size of the bracket grid (all 63 slots visible)."""
    last_row = _BOTTOM_HALF_OFFSET + 14
    width = _BRACKET_PAD * 2 + (_RIGHT_BLOCK_END + 1) * _CELL_W
    height = _BRACKET_PAD * 2 + _BRACKET_TITLE_H + (last_row + 1) * _CELL_H
    return width, height


def _sync_bracket_scrollbars(
    canvas: tk.Canvas,
    vscroll: ttk.Scrollbar,
    hscroll: ttk.Scrollbar,
    content_w: int,
    content_h: int,
) -> None:
    canvas.update_idletasks()
    view_w = max(canvas.winfo_width(), 1)
    view_h = max(canvas.winfo_height(), 1)
    if content_h <= view_h:
        vscroll.grid_remove()
        canvas.yview_moveto(0)
    else:
        vscroll.grid(row=1, column=1, sticky="ns")
    if content_w <= view_w:
        hscroll.grid_remove()
        canvas.xview_moveto(0)
    else:
        hscroll.grid(row=2, column=0, sticky="ew")
    canvas.configure(scrollregion=(0, 0, max(content_w, view_w), max(content_h, view_h)))


def _browse_dir(var: tk.StringVar, on_change: object | None = None) -> None:
    p = filedialog.askdirectory()
    if p:
        var.set(p)
        if on_change:
            on_change()


def _browse_file(var: tk.StringVar, title: str, filetypes: list[tuple[str, str]], on_change: object | None = None) -> None:
    p = filedialog.askopenfilename(title=title, filetypes=filetypes)
    if p:
        var.set(p)
        if on_change:
            on_change()


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


def _menu_not_yet(feature: str) -> None:
    messagebox.showinfo(feature, f"{feature} is not implemented yet.")


def _show_getting_started() -> None:
    messagebox.showinfo(
        "Getting Started Guide",
        "1. Use File → Open File… to load a template bracket (.xls).\n"
        "2. Use File → Open Folder to select the folder with participant brackets.\n"
        "3. Optionally set a results workbook via File → Open File… (.xlsx).\n"
        "4. Use Run → Run Scoring to compute standings shown at the bottom.",
    )


def _show_about() -> None:
    messagebox.showinfo(
        "About BracketTracker",
        "BracketTracker\n\n"
        "Score NCAA-style bracket picks from Excel workbooks in a folder.",
    )


def _add_menu_button(parent: ttk.Frame, label: str, items: list[tuple[str, object]]) -> None:
    mb = ttk.Menubutton(parent, text=label)
    menu = tk.Menu(mb, tearoff=0)
    mb["menu"] = menu
    for item_label, command in items:
        menu.add_command(label=item_label, command=command)
    mb.pack(side=tk.LEFT, padx=2)


def _truncate(text: str, max_len: int = 11) -> str:
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def refresh_bracket_canvas(
    canvas: tk.Canvas,
    vscroll: ttk.Scrollbar,
    hscroll: ttk.Scrollbar,
    template_var: tk.StringVar,
    bracket_name_var: tk.StringVar,
    bracket_issues_var: tk.StringVar,
    content_size: dict[str, int] | None = None,
) -> None:
    def _set_size(w: int, h: int) -> None:
        if content_size is not None:
            content_size["w"] = w
            content_size["h"] = h
        _sync_bracket_scrollbars(canvas, vscroll, hscroll, w, h)

    canvas.delete("all")
    bracket_issues_var.set("")
    path_str = template_var.get().strip()
    if not path_str:
        canvas.create_text(
            200,
            80,
            text="No template bracket loaded.\nUse File → Open File… to open a .xls template.",
            fill="#666",
            font=("Segoe UI", 10),
            justify=tk.CENTER,
        )
        bracket_name_var.set("")
        _set_size(400, 160)
        return

    p = Path(path_str)
    if not p.is_file():
        canvas.create_text(200, 80, text=f"File not found:\n{p.name}", fill="#a00", justify=tk.CENTER)
        bracket_name_var.set("")
        _set_size(400, 160)
        return

    part, issues = load_example_bracket_participant(p)
    if not part:
        msg = "\n".join(issues) if issues else "Could not load bracket."
        canvas.create_text(200, 80, text=msg, fill="#a00", justify=tk.CENTER, width=360)
        bracket_name_var.set("")
        _set_size(400, 160)
        return

    bracket_name_var.set(part.name)
    if issues:
        bracket_issues_var.set("; ".join(issues))

    picks = part.picks
    max_x = 0
    max_y = 0

    _draw_round_headers(canvas)
    _draw_bracket_linework(canvas)

    region_titles = (
        (0, -0.6, "East"),
        (10, -0.6, "West"),
        (0, _BOTTOM_HALF_OFFSET - 0.6, "South"),
        (10, _BOTTOM_HALF_OFFSET - 0.6, "Midwest"),
    )
    for col_idx, row_idx, title in region_titles:
        x, y = _bracket_pixel_xy(col_idx, row_idx)
        anchor = tk.W if col_idx <= _LEFT_BLOCK_END else tk.E
        tx = x if anchor == tk.W else x + _CELL_W
        canvas.create_text(tx, y, text=title, fill="#333", font=("Segoe UI", 8, "bold"), anchor=anchor)

    for region, row, col in _EXAMPLE_BRACKET_SLOTS:
        gid = example_bracket_game_id(region, row, col)
        pick = picks.get(gid, "")
        col_idx, row_idx = _compact_slot_xy(region, row, col)
        x0, y0 = _bracket_pixel_xy(col_idx, row_idx)
        x1 = x0 + _CELL_W - 1
        y1 = y0 + _CELL_H - 1
        if region == "nat":
            if row == 42:
                fill = "#fff3e0" if pick else "#fafafa"
                outline = "#ef6c00"
                _draw_pick_cell(canvas, x0, y0, x1, y1, pick, center=True, fill=fill, outline=outline)
            else:
                _draw_pick_cell(canvas, x0, y0, x1, y1, pick, center=True)
        else:
            _draw_pick_cell(canvas, x0, y0, x1, y1, pick, mirror=region in {"west", "midwest"})
        max_x = max(max_x, x1)
        max_y = max(max_y, y1)

    _set_size(max_x + _BRACKET_PAD, max_y + _BRACKET_PAD)


def _standings_columns() -> tuple[str, ...]:
    return ("rank", "name", "points", "max_possible", "correct", "games")


def refresh_standings_tree(tree: ttk.Treeview, rows: list[PersonScore]) -> None:
    tree.delete(*tree.get_children())
    for i, row in enumerate(rows):
        tree.insert(
            "",
            tk.END,
            values=(
                i + 1,
                row.name,
                f"{row.points_earned:.2f}",
                f"{row.max_possible:.2f}",
                row.correct_known,
                row.games_counted,
            ),
        )


def clear_standings_tree(tree: ttk.Treeview) -> None:
    tree.delete(*tree.get_children())


def run_scoring_action(
    folder_var: tk.StringVar,
    results_var: tk.StringVar,
    sheet_var: tk.StringVar,
    csv_var: tk.StringVar,
    chart_var: tk.StringVar,
    standings_tree: ttk.Treeview,
    issues_log: scrolledtext.ScrolledText,
    root: tk.Tk,
    status: tk.StringVar,
    set_busy: object,
) -> None:
    issues_log.delete("1.0", tk.END)
    clear_standings_tree(standings_tree)
    folder = folder_var.get().strip()
    if not folder:
        messagebox.showwarning("Folder", "Select the folder that contains bracket files (File → Open Folder).")
        return

    csv_out = csv_var.get().strip()
    if not csv_out:
        messagebox.showwarning("Output", "Choose where to save the standings CSV (File → Save As…).")
        return

    results_path = results_var.get().strip()
    rf = Path(results_path) if results_path else None
    sheet = sheet_var.get().strip() or None
    chart_path = chart_var.get().strip()

    def worker() -> None:
        try:
            rows, issues, err, needs_review = run_scoring(Path(folder), results_file=rf, results_sheet=sheet)

            def _log_issues() -> None:
                for msg in issues:
                    issues_log.insert(tk.END, f"{msg}\n")
                if needs_review:
                    issues_log.insert(tk.END, "\nSheets needing manual review / correction:\n")
                    for rev in needs_review:
                        issues_log.insert(tk.END, f"  • {rev.workbook} — {rev.sheet}\n")
                        for reason in rev.reasons:
                            issues_log.insert(tk.END, f"      {reason}\n")

            def finish_fail() -> None:
                set_busy(False)
                status.set("Ready")
                _log_issues()
                if err:
                    issues_log.insert(tk.END, f"\n{err}\n")
                messagebox.showerror("Scoring failed", err or "Scoring failed.")

            def finish_success() -> None:
                set_busy(False)
                status.set("Ready")
                _log_issues()
                refresh_standings_tree(standings_tree, rows)
                save_standings_csv(rows, Path(csv_out).resolve())
                issues_log.insert(tk.END, f"\nWrote CSV: {csv_out}\n")

                if chart_path:
                    try:
                        plot_leaderboard(rows, Path(chart_path).resolve())
                        issues_log.insert(tk.END, f"Wrote chart: {chart_path}\n")
                    except Exception as e:
                        issues_log.insert(tk.END, f"Chart failed: {e}\n")

                issues_log.see(tk.END)

            if err:
                root.after(0, finish_fail)
            else:
                root.after(0, finish_success)

        except Exception as e:
            def finish_exc() -> None:
                set_busy(False)
                status.set("Ready")
                issues_log.insert(tk.END, f"Error: {e}\n")
                messagebox.showerror("Error", str(e))

            root.after(0, finish_exc)

    set_busy(True)
    status.set("Running…")
    threading.Thread(target=worker, daemon=True).start()


def main() -> None:
    root = tk.Tk()
    root.title("BracketTracker")
    root.minsize(820, 520)
    root.geometry("1220x620")

    bracket_w, bracket_h = _bracket_content_size()

    menubar = ttk.Frame(root, padding=(4, 4))
    menubar.grid(row=0, column=0, sticky="ew")

    folder_var = tk.StringVar()
    template_var = tk.StringVar()
    results_var = tk.StringVar()
    sheet_var = tk.StringVar()
    csv_var = tk.StringVar(value=str(Path.cwd() / "standings.csv"))
    chart_var = tk.StringVar()
    status = tk.StringVar(value="Ready")
    bracket_name_var = tk.StringVar()
    bracket_issues_var = tk.StringVar()

    frm = ttk.Frame(root, padding=8)
    frm.grid(row=1, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(1, weight=1)
    frm.columnconfigure(0, weight=1)
    frm.rowconfigure(0, weight=1)

    paned = ttk.Panedwindow(frm, orient=tk.HORIZONTAL)
    paned.grid(row=0, column=0, sticky="nsew")

    bracket_frame = ttk.LabelFrame(paned, text="Bracket", padding=6)
    standings_frame = ttk.LabelFrame(paned, text="Standings", padding=6)
    paned.add(bracket_frame, weight=1)
    paned.add(standings_frame, weight=1)

    bracket_frame.columnconfigure(0, weight=1)
    bracket_frame.rowconfigure(1, weight=1)
    standings_frame.columnconfigure(0, weight=1)
    standings_frame.rowconfigure(0, weight=1)

    bracket_header = ttk.Frame(bracket_frame)
    bracket_header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 2))
    ttk.Label(bracket_header, text="Participant:").pack(side=tk.LEFT)
    ttk.Label(bracket_header, textvariable=bracket_name_var, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(4, 12))
    ttk.Label(bracket_header, textvariable=template_var, foreground="#555").pack(side=tk.LEFT)
    ttk.Label(bracket_header, textvariable=bracket_issues_var, foreground="#b36b00").pack(side=tk.LEFT, padx=(8, 0))

    bracket_canvas = tk.Canvas(
        bracket_frame,
        background="white",
        highlightthickness=1,
        highlightbackground="#ccc",
    )
    bracket_vscroll = ttk.Scrollbar(bracket_frame, orient=tk.VERTICAL, command=bracket_canvas.yview)
    bracket_hscroll = ttk.Scrollbar(bracket_frame, orient=tk.HORIZONTAL, command=bracket_canvas.xview)
    bracket_canvas.configure(yscrollcommand=bracket_vscroll.set, xscrollcommand=bracket_hscroll.set)
    bracket_canvas.grid(row=1, column=0, sticky="nsew")
    bracket_vscroll.grid(row=1, column=1, sticky="ns")
    bracket_hscroll.grid(row=2, column=0, sticky="ew")

    cols = _standings_columns()
    standings_tree = ttk.Treeview(standings_frame, columns=cols, show="headings", height=12)
    headings = {
        "rank": ("Rank", 50),
        "name": ("Name", 160),
        "points": ("Points", 80),
        "max_possible": ("Max possible", 100),
        "correct": ("Correct", 80),
        "games": ("Games picked", 100),
    }
    for col, (heading, width) in headings.items():
        standings_tree.heading(col, text=heading)
        standings_tree.column(col, width=width, anchor=tk.CENTER if col != "name" else tk.W)
    standings_tree.grid(row=0, column=0, sticky="nsew")

    tree_scroll = ttk.Scrollbar(standings_frame, orient=tk.VERTICAL, command=standings_tree.yview)
    standings_tree.configure(yscrollcommand=tree_scroll.set)
    tree_scroll.grid(row=0, column=1, sticky="ns")

    issues_log = scrolledtext.ScrolledText(standings_frame, height=5, font=("Consolas", 9), state=tk.NORMAL)
    issues_log.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
    standings_frame.rowconfigure(0, weight=1)

    ttk.Label(frm, textvariable=status, foreground="#555").grid(row=1, column=0, sticky="w", pady=(6, 0))

    run_menu_commands: list[tk.Menu] = []

    def set_busy(busy: bool) -> None:
        state = tk.DISABLED if busy else tk.NORMAL
        for menu in run_menu_commands:
            menu.entryconfig(0, state=state)

    bracket_content_size = {"w": bracket_w, "h": bracket_h}

    def refresh_bracket() -> None:
        refresh_bracket_canvas(
            bracket_canvas,
            bracket_vscroll,
            bracket_hscroll,
            template_var,
            bracket_name_var,
            bracket_issues_var,
            bracket_content_size,
        )

    def on_bracket_resize(_event: tk.Event) -> None:
        _sync_bracket_scrollbars(
            bracket_canvas,
            bracket_vscroll,
            bracket_hscroll,
            bracket_content_size["w"],
            bracket_content_size["h"],
        )

    bracket_canvas.bind("<Configure>", on_bracket_resize)

    def open_template_file() -> None:
        _browse_file(
            template_var,
            "Template bracket",
            [("Excel", "*.xls"), ("All", "*.*")],
            refresh_bracket,
        )

    def open_results_file() -> None:
        _browse_file(
            results_var,
            "Results workbook",
            [("Excel", "*.xlsx *.xls"), ("All", "*.*")],
        )

    def open_folder() -> None:
        _browse_dir(folder_var)

    def start_scoring() -> None:
        run_scoring_action(
            folder_var,
            results_var,
            sheet_var,
            csv_var,
            chart_var,
            standings_tree,
            issues_log,
            root,
            status,
            set_busy,
        )

    def add_menu_with_run(parent: ttk.Frame, label: str, items: list[tuple[str, object]]) -> None:
        mb = ttk.Menubutton(parent, text=label)
        menu = tk.Menu(mb, tearoff=0)
        mb["menu"] = menu
        for item_label, command in items:
            menu.add_command(label=item_label, command=command)
        mb.pack(side=tk.LEFT, padx=2)
        if label == "Run":
            run_menu_commands.append(menu)

    add_menu_with_run(
        menubar,
        "File",
        [
            ("New Template Bracket", lambda: _menu_not_yet("New Template Bracket")),
            ("New Bracket Entry", lambda: _menu_not_yet("New Bracket Entry")),
            ("Open File…", open_template_file),
            ("Open Folder", open_folder),
            ("Save", lambda: _menu_not_yet("Save")),
            ("Save As…", lambda: _browse_save_csv(csv_var)),
        ],
    )
    add_menu_with_run(
        menubar,
        "Edit",
        [
            ("Modify Template Bracket", lambda: _menu_not_yet("Modify Template Bracket")),
            ("Modify Bracket Entry", lambda: _menu_not_yet("Modify Bracket Entry")),
        ],
    )
    add_menu_with_run(
        menubar,
        "View",
        [
            ("View Template Bracket", refresh_bracket),
            ("View Bracket Entry", lambda: _menu_not_yet("View Bracket Entry")),
            ("View Results", open_results_file),
        ],
    )
    add_menu_with_run(menubar, "Run", [("Run Scoring", start_scoring)])
    add_menu_with_run(
        menubar,
        "Help",
        [
            ("Getting Started Guide", _show_getting_started),
            ("About", _show_about),
        ],
    )

    refresh_bracket()
    root.mainloop()


if __name__ == "__main__":
    main()
