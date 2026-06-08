"""
settings.py — persistent user preferences + the Settings configuration dialog.
"""
import json
import os
import tkinter as tk
from tkinter import ttk

from constants import SETTINGS_DIR, SETTINGS_FILE, DEFAULT_SIMPLIFIED


# ─────────────────────────────────────────────────────────────────────────────
#  Settings  (thin JSON wrapper)
# ─────────────────────────────────────────────────────────────────────────────

class Settings:
    """Load / save user preferences from ~/.pspcviewer/config.json."""

    _DEFAULTS: dict = {
        "simplified_tables": DEFAULT_SIMPLIFIED,
        "last_file":         None,
        "show_hidden_cols":  False,
        "geometry":          "1420x900",
        "panel_mode":        "components",   # "all" | "components"
        "column_prefs":      {},             # {table: {hidden: [...], order: [...]}}
    }

    def __init__(self):
        self._d = dict(self._DEFAULTS)
        self._load()

    def _load(self):
        try:
            with open(SETTINGS_FILE) as f:
                self._d.update(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def save(self):
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w") as f:
            json.dump(self._d, f, indent=2)

    def __getitem__(self, k):
        return self._d.get(k, self._DEFAULTS.get(k))

    def __setitem__(self, k, v):
        self._d[k] = v


# ─────────────────────────────────────────────────────────────────────────────
#  SettingsDialog  (configure the Components simplified table list)
# ─────────────────────────────────────────────────────────────────────────────

class SettingsDialog(tk.Toplevel):
    """Lets the user choose which tables appear in the 'Components' view."""

    def __init__(self, parent: tk.Tk, settings: Settings, db_tables: list[str]):
        super().__init__(parent)
        self.title("⚙  Configure 'Components' view")
        self.geometry("440x580")
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        self.settings = settings
        self.result: list[str] | None = None   # set to new list on Save

        current = set(settings["simplified_tables"])
        known   = set(db_tables)
        # Tables saved from before that are no longer in this DB
        extra   = [t for t in current if t not in known]
        display = db_tables + extra

        # ── Header ───────────────────────────────────────────
        ttk.Label(self,
                  text="Tables visible in 'Components' view",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
        ttk.Label(self,
                  text="Grey = not in current database (remembered from before).",
                  foreground="#888").pack(anchor="w", padx=12, pady=(0, 6))

        # ── Scrollable checklist ──────────────────────────────
        outer  = ttk.Frame(self)
        outer.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)
        canvas = tk.Canvas(outer, bg="white", highlightthickness=0)
        vsb    = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        inner  = ttk.Frame(canvas)
        inner.bind("<Configure>",
                   lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(fill=tk.BOTH, expand=True)
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        self._vars: dict[str, tk.BooleanVar] = {}
        for t in display:
            var = tk.BooleanVar(value=(t in current))
            self._vars[t] = var
            fg = "#000" if t in known else "#aaa"
            tk.Checkbutton(inner, text=t, variable=var, foreground=fg,
                           bg="white", font=("Consolas", 9)).pack(anchor="w", padx=8, pady=1)

        # ── Buttons ───────────────────────────────────────────
        bf = ttk.Frame(self)
        bf.pack(fill=tk.X, padx=12, pady=8)
        ttk.Button(bf, text="All",
                   command=lambda: [v.set(True)  for v in self._vars.values()]).pack(side=tk.LEFT, padx=2)
        ttk.Button(bf, text="None",
                   command=lambda: [v.set(False) for v in self._vars.values()]).pack(side=tk.LEFT, padx=2)
        ttk.Button(bf, text="Default",
                   command=self._reset).pack(side=tk.LEFT, padx=2)
        ttk.Button(bf, text="Cancel",
                   command=self.destroy).pack(side=tk.RIGHT, padx=2)
        ttk.Button(bf, text="Save",
                   command=self._save).pack(side=tk.RIGHT, padx=2)

    def _reset(self):
        ds = set(DEFAULT_SIMPLIFIED)
        for t, v in self._vars.items():
            v.set(t in ds)

    def _save(self):
        self.result = [t for t, v in self._vars.items() if v.get()]
        self.destroy()
