"""
dialogs.py — application-level dialogs (not settings-related).

Currently contains:
  ColumnDialog  — show / hide / reorder columns for the active table view
"""
import tkinter as tk
from tkinter import ttk, messagebox


class ColumnDialog(tk.Toplevel):
    """
    Two-panel dialog: Visible (left) ↔ Hidden (right).
    Move items with the arrow buttons; reorder Visible with ▲ / ▼.
    """

    def __init__(self, parent: tk.Tk, tree: ttk.Treeview):
        super().__init__(parent)
        self.title("⊞  Show / Hide Columns")
        self.geometry("540x400")
        self.minsize(420, 300)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        self.tree   = tree
        self.result: list[str] | None = None

        all_cols = list(tree["columns"])
        cur_disp = self._get_disp(tree)
        cur_set  = set(cur_disp)

        shown  = list(cur_disp)
        hidden = [c for c in all_cols if c not in cur_set]

        ttk.Label(self,
                  text="Visible columns (left) will be shown in that order.",
                  foreground="#555").pack(anchor="w", padx=12, pady=(8, 4))

        # ── Main three-column layout ──────────────────────────────────────────
        mid = ttk.Frame(self)
        mid.pack(fill=tk.BOTH, expand=True, padx=12, pady=2)
        mid.columnconfigure(0, weight=1)
        mid.columnconfigure(2, weight=1)
        mid.rowconfigure(1, weight=1)

        # Left panel — Visible
        ttk.Label(mid, text="Visible", font=("Segoe UI", 9, "bold")).grid(
            row=0, column=0, pady=(0, 2))
        lf   = ttk.Frame(mid)
        lf.grid(row=1, column=0, sticky="nsew")
        lvsb = ttk.Scrollbar(lf)
        lvsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.shown_lb = tk.Listbox(
            lf, yscrollcommand=lvsb.set, selectmode=tk.EXTENDED,
            font=("Consolas", 9), activestyle="dotbox")
        self.shown_lb.pack(fill=tk.BOTH, expand=True)
        lvsb.config(command=self.shown_lb.yview)
        self.shown_lb.bind("<MouseWheel>",
            lambda e: self.shown_lb.yview_scroll(int(-e.delta / 120), "units"))
        for c in shown:
            self.shown_lb.insert(tk.END, c)

        # Centre — arrow buttons
        cf = ttk.Frame(mid, width=60)
        cf.grid(row=1, column=1, padx=6)
        ttk.Button(cf, text="◀ Show",  width=7, command=self._show_sel).pack(pady=3)
        ttk.Button(cf, text="Hide ▶",  width=7, command=self._hide_sel).pack(pady=3)
        ttk.Separator(cf, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
        ttk.Button(cf, text="▲ Up",    width=7, command=self._move_up).pack(pady=3)
        ttk.Button(cf, text="▼ Down",  width=7, command=self._move_down).pack(pady=3)

        # Right panel — Hidden
        ttk.Label(mid, text="Hidden", font=("Segoe UI", 9, "bold")).grid(
            row=0, column=2, pady=(0, 2))
        rf   = ttk.Frame(mid)
        rf.grid(row=1, column=2, sticky="nsew")
        rvsb = ttk.Scrollbar(rf)
        rvsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.hidden_lb = tk.Listbox(
            rf, yscrollcommand=rvsb.set, selectmode=tk.EXTENDED,
            font=("Consolas", 9), activestyle="dotbox")
        self.hidden_lb.pack(fill=tk.BOTH, expand=True)
        rvsb.config(command=self.hidden_lb.yview)
        self.hidden_lb.bind("<MouseWheel>",
            lambda e: self.hidden_lb.yview_scroll(int(-e.delta / 120), "units"))
        for c in hidden:
            self.hidden_lb.insert(tk.END, c)

        # ── Bottom buttons ────────────────────────────────────────────────────
        bf = ttk.Frame(self)
        bf.pack(fill=tk.X, padx=12, pady=8)
        ttk.Button(bf, text="Show All",
                   command=self._show_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(bf, text="Hide All",
                   command=self._hide_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(bf, text="Cancel",
                   command=self.destroy).pack(side=tk.RIGHT, padx=2)
        ttk.Button(bf, text="Apply",
                   command=self._apply).pack(side=tk.RIGHT, padx=2)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _show_sel(self):
        sel = self.hidden_lb.curselection()
        items = [self.hidden_lb.get(i) for i in sel]
        for i in reversed(sel):
            self.hidden_lb.delete(i)
        for item in items:
            self.shown_lb.insert(tk.END, item)

    def _hide_sel(self):
        sel = self.shown_lb.curselection()
        items = [self.shown_lb.get(i) for i in sel]
        for i in reversed(sel):
            self.shown_lb.delete(i)
        for item in items:
            self.hidden_lb.insert(tk.END, item)

    def _move_up(self):
        sel = self.shown_lb.curselection()
        if not sel or sel[0] == 0:
            return
        for i in sel:
            val = self.shown_lb.get(i)
            self.shown_lb.delete(i)
            self.shown_lb.insert(i - 1, val)
            self.shown_lb.selection_set(i - 1)

    def _move_down(self):
        sel = self.shown_lb.curselection()
        if not sel or sel[-1] == self.shown_lb.size() - 1:
            return
        for i in reversed(sel):
            val = self.shown_lb.get(i)
            self.shown_lb.delete(i)
            self.shown_lb.insert(i + 1, val)
            self.shown_lb.selection_set(i + 1)

    def _show_all(self):
        items = list(self.hidden_lb.get(0, tk.END))
        self.hidden_lb.delete(0, tk.END)
        for item in items:
            self.shown_lb.insert(tk.END, item)

    def _hide_all(self):
        items = list(self.shown_lb.get(0, tk.END))
        self.shown_lb.delete(0, tk.END)
        for item in items:
            self.hidden_lb.insert(tk.END, item)

    def _apply(self):
        new_disp = list(self.shown_lb.get(0, tk.END))
        if not new_disp:
            messagebox.showwarning("Column visibility",
                                   "At least one column must remain visible.",
                                   parent=self)
            return
        self.result = new_disp
        self.destroy()

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _get_disp(tree: ttk.Treeview) -> list[str]:
        d = tree["displaycolumns"]
        if not d or d in ("#all", ("#all",)):
            return list(tree["columns"])
        if isinstance(d, str):
            return list(tree["columns"])
        return list(d)
