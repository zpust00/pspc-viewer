"""
viewer.py — PSPCViewer: the main application window.

All tkinter UI lives here.  Database work is delegated to DbHelper.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sqlite3
import os
import sys

from constants import (
    EI_VIEW_COLS, PORT_DETAIL_COLS, DEFAULT_SIMPLIFIED, APP_VERSION,
    PLANT_VAULT_ROOT,
)
from settings  import Settings, SettingsDialog
from dialogs   import ColumnDialog
from widgets   import CellEditor
from db_helper import DbHelper, safe_str


def resource_path(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    return os.path.join(base, rel)


# ─────────────────────────────────────────────────────────────────────────────

class PSPCViewer:
    APP_TITLE = "PSPC Viewer — Autodesk Plant 3D"

    def __init__(self, root: tk.Tk):
        self.root = root
        self.cfg  = Settings()
        self.db:  DbHelper | None = None
        self.conn: sqlite3.Connection | None = None

        # State
        self.cur_file:  str | None   = None
        self.cur_table: str | None   = None
        self.cur_cols:  list[str]    = []
        self.cur_rows:  list[list]   = []
        self.pending:   dict         = {}  # {tbl: {row_idx: {col: val}}}

        # Port detail
        self._port_map:    dict[int, list[list]] = {}
        self._comp_pnpids: list[int | None]      = []
        self._port_panel_visible = False

        # Port connections tab
        self.all_port_rows: list[list] = []
        self.port_tab_cols: list[str]  = []

        # Plant Vault quick-open state
        self._proj_paths: dict[str, str] = {}
        self._spec_paths: dict[str, str] = {}

        # Header drag state
        self._drag_from:    str | None = None
        self._drag_start_x: int        = 0
        self._drag_moved:   bool       = False

        # Sort state  {col_name: currently_reversed}
        self._sort_rev: dict[str, bool] = {}

        # UI mode
        self._mode        = tk.StringVar(value=self.cfg["panel_mode"])
        self._show_hidden = tk.BooleanVar(value=self.cfg["show_hidden_cols"])

        root.title(self.APP_TITLE)
        root.geometry(self.cfg["geometry"])
        root.minsize(960, 640)
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.bind("<Configure>", self._on_resize)

        self._build_ui()
        self._bind_keys()
        self._apply_mode_style()

        last = self.cfg["last_file"]
        if last and os.path.isfile(last):
            root.after(200, lambda: self._open(last))

    # ══════════════════════════════════════════════════════════════════════════
    #  UI construction
    # ══════════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        self._build_menu()
        self._build_toolbar()
        self._build_body()
        self._build_status()

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _build_menu(self):
        mb = tk.Menu(self.root)

        fm = tk.Menu(mb, tearoff=0)
        fm.add_command(label="Open…",            command=self.cmd_open,   accelerator="Ctrl+O")
        fm.add_separator()
        fm.add_command(label="Export to Excel…", command=self.cmd_excel,  accelerator="Ctrl+E")
        fm.add_separator()
        fm.add_command(label="Exit",             command=self._on_close)
        mb.add_cascade(label="File", menu=fm)

        vm = tk.Menu(mb, tearoff=0)
        vm.add_command(label="Port Connections tab", command=self.cmd_ports_tab)
        vm.add_command(label="Reload table",         command=self.cmd_reload, accelerator="F5")
        vm.add_separator()
        vm.add_checkbutton(label="Show hidden columns (GUIDs / blobs)",
                           variable=self._show_hidden, command=self.cmd_reload)
        mb.add_cascade(label="View", menu=vm)

        hm = tk.Menu(mb, tearoff=0)
        hm.add_command(label="About", command=self._about)
        mb.add_cascade(label="Help", menu=hm)
        self.root.config(menu=mb)

    # ── Toolbar ───────────────────────────────────────────────────────────────

    def _build_toolbar(self):
        bar = ttk.Frame(self.root, relief="raised")
        bar.pack(side=tk.TOP, fill=tk.X)

        # Left: standard action buttons
        for lbl, cmd in [
            ("📂 Open",             self.cmd_open),
            ("📊 Export Excel",     self.cmd_excel),
            ("|", None),
            ("🔌 Port Connections", self.cmd_ports_tab),
            ("🔄 Reload",           self.cmd_reload),
            ("|", None),
            ("❓ How To",           self.cmd_howto),
            ("|", None),
        ]:
            if lbl == "|":
                ttk.Separator(bar, orient=tk.VERTICAL).pack(
                    side=tk.LEFT, fill=tk.Y, padx=5, pady=3)
            else:
                ttk.Button(bar, text=lbl, command=cmd).pack(
                    side=tk.LEFT, padx=2, pady=2)

        # Middle: Plant Vault project selector
        ttk.Label(bar, text="Project:").pack(side=tk.LEFT, padx=(0, 2), pady=2)
        self._proj_var   = tk.StringVar()
        self._proj_combo = ttk.Combobox(bar, textvariable=self._proj_var,
                                        width=30, state="readonly")
        self._proj_combo.pack(side=tk.LEFT, padx=2, pady=2)
        self._proj_combo.bind("<<ComboboxSelected>>", self._on_proj_select)
        ttk.Button(bar, text="⟳", width=2,
                   command=self._refresh_projects).pack(side=tk.LEFT, padx=(0, 4), pady=2)

        ttk.Separator(bar, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=5, pady=3)

        # Right: spec sheet selector
        ttk.Label(bar, text="Spec Sheet:").pack(side=tk.LEFT, padx=(0, 2), pady=2)
        self._spec_var   = tk.StringVar()
        self._spec_combo = ttk.Combobox(bar, textvariable=self._spec_var,
                                        width=30, state="readonly")
        self._spec_combo.pack(side=tk.LEFT, padx=2, pady=2)
        self._spec_combo.bind("<<ComboboxSelected>>", self._on_spec_select)

        self._refresh_projects()

    # ── Body (left panel + notebook) ──────────────────────────────────────────

    def _build_body(self):
        pw = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        pw.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        lf = ttk.Frame(pw, width=180)
        pw.add(lf, weight=1)
        self._build_left_panel(lf)

        rf = ttk.Frame(pw)
        pw.add(rf, weight=7)
        self.nb = ttk.Notebook(rf)
        self.nb.pack(fill=tk.BOTH, expand=True)
        self._build_data_tab()
        self._build_ports_tab()

    # ── Left panel ────────────────────────────────────────────────────────────

    def _build_left_panel(self, parent):
        hdr = ttk.Frame(parent)
        hdr.pack(fill=tk.X, padx=4, pady=(4, 0))
        ttk.Label(hdr, text="Tables",
                  font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        self._btn_gear = ttk.Button(hdr, text="⚙", width=2,
                                     command=self._open_settings)
        self._btn_gear.pack(side=tk.RIGHT)

        tog = ttk.Frame(parent)
        tog.pack(fill=tk.X, padx=4, pady=(2, 0))
        self._btn_all  = tk.Button(tog, text="All",
                                    relief="flat", padx=8, pady=2,
                                    font=("Segoe UI", 9),
                                    command=lambda: self._set_mode("all"))
        self._btn_comp = tk.Button(tog, text="Components",
                                    relief="flat", padx=8, pady=2,
                                    font=("Segoe UI", 9),
                                    command=lambda: self._set_mode("components"))
        self._btn_all .pack(side=tk.LEFT,  fill=tk.X, expand=True)
        self._btn_comp.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        self._tbl_q = tk.StringVar()
        self._tbl_q.trace_add("write", self._refresh_tbl_list)
        ttk.Entry(parent, textvariable=self._tbl_q).pack(
            fill=tk.X, padx=4, pady=(3, 1))

        frm = ttk.Frame(parent)
        frm.pack(fill=tk.BOTH, expand=True, padx=2, pady=(0, 2))
        vsb = ttk.Scrollbar(frm)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tbl_lb = tk.Listbox(frm, yscrollcommand=vsb.set,
                                  activestyle="dotbox",
                                  font=("Consolas", 9))
        self.tbl_lb.pack(fill=tk.BOTH, expand=True)
        vsb.config(command=self.tbl_lb.yview)
        self.tbl_lb.bind("<<ListboxSelect>>", self._on_tbl_sel)

    # ── Data tab ─────────────────────────────────────────────────────────────

    def _build_data_tab(self):
        self._data_tab = ttk.Frame(self.nb)
        self.nb.add(self._data_tab, text="  📋 Data  ")

        # Top bar
        top = ttk.Frame(self._data_tab)
        top.pack(fill=tk.X, padx=4, pady=(4, 2))
        ttk.Label(top, text="Table:").pack(side=tk.LEFT)
        self._lbl_tbl = ttk.Label(top, text="—",
                                   font=("Segoe UI", 9, "bold"),
                                   foreground="#005a9e")
        self._lbl_tbl.pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(top, text="🔍").pack(side=tk.LEFT)
        self._srch = tk.StringVar()
        self._srch.trace_add("write", self._apply_search)
        ttk.Entry(top, textvariable=self._srch, width=26).pack(
            side=tk.LEFT, padx=2)
        ttk.Button(top, text="✕", width=2,
                   command=lambda: self._srch.set("")).pack(
            side=tk.LEFT, padx=(0, 8))
        ttk.Button(top, text="⊞ Columns",
                   command=self._open_col_dialog).pack(side=tk.LEFT, padx=2)

        # Main treeview
        tf = ttk.Frame(self._data_tab)
        tf.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 2))
        vsb = ttk.Scrollbar(tf, orient=tk.VERTICAL)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb = ttk.Scrollbar(tf, orient=tk.HORIZONTAL)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        sty = ttk.Style()
        sty.configure("Treeview",         rowheight=22, font=("Consolas", 9))
        sty.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        sty.map("Treeview", background=[("selected", "#cce5ff")])

        self.dtree = ttk.Treeview(tf, yscrollcommand=vsb.set,
                                   xscrollcommand=hsb.set,
                                   selectmode="extended")
        self.dtree.pack(fill=tk.BOTH, expand=True)
        vsb.config(command=self.dtree.yview)
        hsb.config(command=self.dtree.xview)
        self.dtree.tag_configure("mod",  background="#fff3cd")
        self.dtree.tag_configure("odd",  background="#f8f9fa")
        self.dtree.tag_configure("even", background="#ffffff")

        self.dtree.bind("<Double-1>",         self._dbl_click)
        self.dtree.bind("<Return>",           self._enter_key)
        self.dtree.bind("<<TreeviewSelect>>", self._on_row_select)
        self.dtree.bind("<Button-3>",         self._on_header_rclick)
        self.dtree.bind("<ButtonPress-1>",    self._hdr_press)
        self.dtree.bind("<B1-Motion>",        self._hdr_motion)
        self.dtree.bind("<ButtonRelease-1>",  self._hdr_release)

        self.editor = CellEditor(self.dtree, self._on_cell_save)

        self._lbl_rows = ttk.Label(self._data_tab, text="", foreground="#666")
        self._lbl_rows.pack(anchor="e", padx=8, pady=1)

        # Port detail panel (hidden until Components mode + component table)
        self._port_sep = ttk.Separator(self._data_tab, orient=tk.HORIZONTAL)
        self._port_frm = ttk.LabelFrame(self._data_tab,
                                         text="Ports of selected component",
                                         height=200)
        self._port_frm.pack_propagate(False)
        pf   = ttk.Frame(self._port_frm)
        pf.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        pvsb = ttk.Scrollbar(pf, orient=tk.VERTICAL)
        pvsb.pack(side=tk.RIGHT, fill=tk.Y)
        phsb = ttk.Scrollbar(pf, orient=tk.HORIZONTAL)
        phsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.ptree_detail = ttk.Treeview(pf, yscrollcommand=pvsb.set,
                                          xscrollcommand=phsb.set)
        self.ptree_detail.pack(fill=tk.BOTH, expand=True)
        pvsb.config(command=self.ptree_detail.yview)
        phsb.config(command=self.ptree_detail.xview)
        self.ptree_detail.tag_configure("s1",   background="#d4edda")
        self.ptree_detail.tag_configure("odd",  background="#e8f4f8")
        self.ptree_detail.tag_configure("even", background="#ffffff")

    def _show_port_panel(self):
        if not self._port_panel_visible:
            self._port_sep.pack(fill=tk.X, padx=4, pady=(2, 0))
            self._port_frm.pack(fill=tk.BOTH, padx=4, pady=(2, 4))
            self._port_panel_visible = True

    def _hide_port_panel(self):
        if self._port_panel_visible:
            self._port_sep.pack_forget()
            self._port_frm.pack_forget()
            self._port_panel_visible = False

    # ── Port connections tab ──────────────────────────────────────────────────

    def _build_ports_tab(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="  🔌 Port Connections  ")

        top = ttk.Frame(tab)
        top.pack(fill=tk.X, padx=4, pady=(4, 2))
        ttk.Label(top, text="🔍").pack(side=tk.LEFT)
        self._port_q = tk.StringVar()
        self._port_q.trace_add("write", self._filter_port_tab)
        ttk.Entry(top, textvariable=self._port_q, width=32).pack(
            side=tk.LEFT, padx=2)
        ttk.Button(top, text="✕", width=2,
                   command=lambda: self._port_q.set("")).pack(side=tk.LEFT)
        ttk.Separator(top, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=8, pady=2)
        ttk.Button(top, text="🔄 Reload",
                   command=self._load_all_ports).pack(side=tk.LEFT)

        pf  = ttk.Frame(tab)
        pf.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 2))
        vsb = ttk.Scrollbar(pf, orient=tk.VERTICAL)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb = ttk.Scrollbar(pf, orient=tk.HORIZONTAL)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.ptree = ttk.Treeview(pf, yscrollcommand=vsb.set,
                                   xscrollcommand=hsb.set)
        self.ptree.pack(fill=tk.BOTH, expand=True)
        vsb.config(command=self.ptree.yview)
        hsb.config(command=self.ptree.xview)
        self.ptree.tag_configure("odd",  background="#f8f9fa")
        self.ptree.tag_configure("even", background="#ffffff")
        self._lbl_ports = ttk.Label(
            tab, text="Open a .pspc file to see port connections.",
            foreground="#666")
        self._lbl_ports.pack(anchor="e", padx=8, pady=1)

    def _build_status(self):
        self._status = tk.StringVar(value="Ready — open a .pspc file to begin.")
        ttk.Label(self.root, textvariable=self._status,
                  relief=tk.SUNKEN, anchor=tk.W, padding=(4, 1)).pack(
            side=tk.BOTTOM, fill=tk.X)

    def _bind_keys(self):
        self.root.bind("<Control-o>", lambda _: self.cmd_open())
        self.root.bind("<Control-e>", lambda _: self.cmd_excel())
        self.root.bind("<F5>",        lambda _: self.cmd_reload())

    # ══════════════════════════════════════════════════════════════════════════
    #  Commands
    # ══════════════════════════════════════════════════════════════════════════

    # ── Plant Vault quick-open ─────────────────────────────────────────────────

    def _refresh_projects(self):
        """Scan PLANT_VAULT_ROOT and populate the Project combobox."""
        self._proj_paths = {}
        dirs = []
        if os.path.isdir(PLANT_VAULT_ROOT):
            try:
                for entry in sorted(os.scandir(PLANT_VAULT_ROOT),
                                    key=lambda e: e.name.lower()):
                    if entry.is_dir():
                        dirs.append(entry.name)
                        self._proj_paths[entry.name] = entry.path
            except PermissionError:
                pass
        self._proj_combo["values"] = dirs
        self._spec_combo["values"] = []
        self._spec_var.set("")
        if not dirs:
            self._proj_var.set("")

    def _on_proj_select(self, _=None):
        """Project chosen — scan its Spec Sheets folder for .pspc files."""
        proj = self._proj_var.get()
        if not proj or proj not in self._proj_paths:
            return
        self._spec_paths = {}
        spec_dir = os.path.join(self._proj_paths[proj], "Spec Sheets")
        files = []
        if os.path.isdir(spec_dir):
            try:
                for entry in sorted(os.scandir(spec_dir),
                                    key=lambda e: e.name.lower()):
                    if entry.is_file() and entry.name.lower().endswith(".pspc"):
                        files.append(entry.name)
                        self._spec_paths[entry.name] = entry.path
            except PermissionError:
                pass
        self._spec_combo["values"] = files
        self._spec_var.set("")
        if not files:
            self._status.set(
                f"No .pspc files in '{proj}\\Spec Sheets'  —  check folder path")

    def _on_spec_select(self, _=None):
        """Spec sheet chosen — open it."""
        name = self._spec_var.get()
        if name and name in self._spec_paths:
            self._open(self._spec_paths[name])

    def cmd_open(self):
        path = filedialog.askopenfilename(
            title="Open PSPC / SQLite file",
            filetypes=[
                ("Plant 3D Spec", "*.pspc"),
                ("SQLite DB",     "*.db *.sqlite *.sqlite3"),
                ("All files",     "*.*"),
            ])
        if path:
            self._open(path)

    def cmd_save(self):
        if not self.db:
            messagebox.showwarning("No file", "No file is open.")
            return
        if not self.pending:
            messagebox.showinfo("Nothing to save", "No unsaved changes.")
            return
        total = sum(len(r) for rows in self.pending.values() for r in rows.values())
        if not messagebox.askyesno("Save changes",
                f"Write {total} cell change(s) to:\n{self.cur_file}"):
            return
        try:
            self.db.save_changes(self.pending)
            self.pending = {}
            self._status.set("✓ Changes saved.")
            messagebox.showinfo("Saved", "All changes written to the database.")
            self.cmd_reload()
        except Exception as e:
            messagebox.showerror("Save failed", str(e))

    def cmd_excel(self):
        if not self.db:
            messagebox.showwarning("No file", "No file is open.")
            return
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="📋  Export Screen  (vidni stolpci / filtrirane vrstice)",
                         command=self._excel_screen)
        menu.add_command(label="📦  Export All  (vse tabele v ločene sheete)",
                         command=self._excel_all)
        try:
            menu.post(self.root.winfo_pointerx(), self.root.winfo_pointery())
        finally:
            menu.grab_release()

    def _excel_screen(self):
        if not self.cur_table:
            messagebox.showwarning("No table", "Najprej izberi tabelo.")
            return
        try:
            import pandas as pd
            import openpyxl  # noqa
        except ImportError as e:
            messagebox.showerror("Missing library",
                f"Install:  pip install pandas openpyxl\n\n({e})")
            return
        dest = filedialog.asksaveasfilename(
            title="Export Screen to Excel", defaultextension=".xlsx",
            filetypes=[("Excel workbook", "*.xlsx"), ("All files", "*.*")])
        if not dest:
            return
        try:
            disp_cols = self._get_displaycols()
            all_cols  = list(self.dtree["columns"])
            indices   = [all_cols.index(c) for c in disp_cols if c in all_cols]
            rows = [
                [self.dtree.item(iid, "values")[i] for i in indices]
                for iid in self.dtree.get_children()
            ]
            df = pd.DataFrame(rows, columns=disp_cols)
            with pd.ExcelWriter(dest, engine="openpyxl") as wr:
                df.to_excel(wr, sheet_name=self.cur_table[:31], index=False)
            self._status.set(f"✓ Exported (screen) → {dest}")
            messagebox.showinfo("Done", f"Saved:\n{dest}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    def _excel_all(self):
        try:
            import pandas   # noqa
            import openpyxl  # noqa
        except ImportError as e:
            messagebox.showerror("Missing library",
                f"Install:  pip install pandas openpyxl\n\n({e})")
            return
        dest = filedialog.asksaveasfilename(
            title="Export All to Excel", defaultextension=".xlsx",
            filetypes=[("Excel workbook", "*.xlsx"), ("All files", "*.*")])
        if not dest:
            return
        try:
            self.db.export_excel(dest)
            self._status.set(f"✓ Exported (all) → {dest}")
            messagebox.showinfo("Done", f"Saved:\n{dest}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    def cmd_ports_tab(self):
        self.nb.select(1)
        if self.db:
            self._load_all_ports()

    def cmd_reload(self):
        if self.cur_table:
            self._load_table(self.cur_table)

    # ══════════════════════════════════════════════════════════════════════════
    #  File open
    # ══════════════════════════════════════════════════════════════════════════

    def _open(self, path: str):
        try:
            if self.conn:
                self.conn.close()
            self.conn      = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            self.db        = DbHelper(self.conn)
            self.cur_file  = path
            self.pending   = {}
            self.root.title(f"{self.APP_TITLE}  —  {os.path.basename(path)}  [read-only]")
            self._status.set(f"Opened: {path}")
            self.cfg["last_file"] = path
            self.cfg.save()
            self._populate_tables()
            self._load_all_ports()
        except Exception as e:
            messagebox.showerror("Open failed", str(e))

    # ══════════════════════════════════════════════════════════════════════════
    #  Left-panel table list
    # ══════════════════════════════════════════════════════════════════════════

    def _populate_tables(self):
        self._refresh_tbl_list()
        start = ("EngineeringItems"
                 if "EngineeringItems" in self.db.all_tables
                 else (self.db.all_tables[0] if self.db.all_tables else None))
        if start:
            self._select_lb(start)
            self._load_table(start)

    def _refresh_tbl_list(self, *_):
        if not self.db:
            return
        q     = self._tbl_q.get().lower()
        mode  = self._mode.get()
        simp  = set(self.cfg["simplified_tables"])
        names = self.db.all_tables
        if mode == "components":
            names = [t for t in names if t in simp]
        if q:
            names = [t for t in names if q in t.lower()]
        self.tbl_lb.delete(0, tk.END)
        for t in names:
            self.tbl_lb.insert(tk.END, t)

    def _select_lb(self, name: str):
        items = list(self.tbl_lb.get(0, tk.END))
        if name in items:
            idx = items.index(name)
            self.tbl_lb.selection_clear(0, tk.END)
            self.tbl_lb.selection_set(idx)
            self.tbl_lb.see(idx)

    def _on_tbl_sel(self, _):
        sel = self.tbl_lb.curselection()
        if sel:
            self._load_table(self.tbl_lb.get(sel[0]))

    def _set_mode(self, mode: str):
        self._mode.set(mode)
        self.cfg["panel_mode"] = mode
        self._apply_mode_style()
        self._refresh_tbl_list()
        if self.cur_table:
            self._load_table(self.cur_table)

    def _apply_mode_style(self):
        mode = self._mode.get()
        if mode == "all":
            self._btn_all .config(bg="#005a9e", fg="white")
            self._btn_comp.config(bg="#e0e0e0", fg="#333")
            self._btn_gear.pack_forget()
            self._hide_port_panel()
        else:
            self._btn_all .config(bg="#e0e0e0", fg="#333")
            self._btn_comp.config(bg="#005a9e", fg="white")
            self._btn_gear.pack(side=tk.RIGHT)

    # ══════════════════════════════════════════════════════════════════════════
    #  Table loading  (delegates data work to DbHelper)
    # ══════════════════════════════════════════════════════════════════════════

    def _load_table(self, name: str):
        if not self.db:
            return
        self.cur_table = name
        self._lbl_tbl.config(text=name)
        self._srch.set("")
        self.editor.close()
        self._sort_rev.clear()

        mode      = self._mode.get()
        has_pnpid = self.db.col_exists(name, "PnPID")

        if mode == "components" and has_pnpid:
            self._show_port_panel()
            if name == "EngineeringItems":
                self._load_ei()
            else:
                self._load_comp(name)
        else:
            self._hide_port_panel()
            self._load_raw(name)

    def _load_raw(self, name: str):
        try:
            cols, rows = self.db.table_raw(name, self._show_hidden.get())
            self.cur_cols     = cols
            self.cur_rows     = rows
            self._comp_pnpids = []
            self._render(cols, rows)
            self._lbl_rows.config(text=f"{len(rows)} rows · {len(cols)} columns")
            self._status.set(f"Table: {name}  —  {len(rows)} rows")
        except Exception as e:
            messagebox.showerror("Load error", str(e))

    def _load_ei(self):
        try:
            labels, rows, pnpids = self.db.ei_view(self._show_hidden.get())
            self.cur_cols     = labels
            self.cur_rows     = rows
            self._comp_pnpids = pnpids
            self._port_map    = self.db.port_map()
            self._render(labels, rows)
            self._lbl_rows.config(
                text=f"{len(rows)} components · {len(labels)} columns  "
                     f"— click a row to see its ports below")
            self._status.set(f"Table: EngineeringItems  —  {len(rows)} components")
        except Exception as e:
            messagebox.showerror("Load error (EI view)", str(e))

    def _load_comp(self, name: str):
        try:
            labels, rows, pnpids = self.db.comp_join(name)
            self.cur_cols     = labels
            self.cur_rows     = rows
            self._comp_pnpids = pnpids
            self._port_map    = self.db.port_map()
            self._render(labels, rows)
            self._lbl_rows.config(
                text=f"{len(rows)} rows · {len(labels)} columns  "
                     f"— click a row to see its ports below")
            self._status.set(f"Table: {name}  —  {len(rows)} rows")
        except Exception as e:
            messagebox.showerror("Load error (join view)", str(e))

    # ══════════════════════════════════════════════════════════════════════════
    #  Render  (tkinter only, no SQL)
    # ══════════════════════════════════════════════════════════════════════════

    def _render(self, cols: list[str], rows: list[list]):
        tree = self.dtree
        tree.delete(*tree.get_children())
        tree["displaycolumns"] = "#all"
        tree["columns"] = cols
        tree["show"]    = "headings"
        for col in cols:
            w = min(max(len(col) * 9, 70), 300)
            tree.heading(col, text=col)          # sort handled by _hdr_release
            tree.column(col, width=w, minwidth=40, stretch=False)
        # Auto-hide columns where every row is blank
        if rows:
            empty = {i for i, _ in enumerate(cols)
                     if all(not safe_str(r[i]).strip() for r in rows)}
            vis = [c for i, c in enumerate(cols) if i not in empty]
        else:
            vis = list(cols)
        tree["displaycolumns"] = vis or cols

        for i, row in enumerate(rows):
            tag = "odd" if i % 2 else "even"
            tree.insert("", tk.END, iid=str(i),
                        values=[safe_str(v) for v in row], tags=(tag,))
        self._apply_col_prefs()

    # ══════════════════════════════════════════════════════════════════════════
    #  Port detail panel
    # ══════════════════════════════════════════════════════════════════════════

    def _on_row_select(self, _):
        if not self._port_panel_visible:
            return
        sel = self.dtree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx < len(self._comp_pnpids) and self._comp_pnpids[idx] is not None:
            self._refresh_port_detail(self._comp_pnpids[idx])

    def _refresh_port_detail(self, pnpid: int):
        tree = self.ptree_detail
        tree.delete(*tree.get_children())
        labels = [lbl for _, lbl, _ in PORT_DETAIL_COLS]
        widths = [w   for _, _,   w in PORT_DETAIL_COLS]
        tree["columns"] = labels
        tree["show"]    = "headings"
        for lbl, w in zip(labels, widths):
            tree.heading(lbl, text=lbl)
            tree.column(lbl, width=w, minwidth=40, stretch=False)

        s1 = self.db.s1_port(pnpid)
        if s1:
            s1[0] = s1[0] or "S1"
            tree.insert("", tk.END, values=[safe_str(v) for v in s1], tags=("s1",))

        extra = self._port_map.get(pnpid, [])
        for i, p in enumerate(extra):
            tree.insert("", tk.END,
                        values=[safe_str(v) for v in p],
                        tags=("odd" if i % 2 else "even",))

        total = (1 if s1 else 0) + len(extra)
        self._port_frm.config(
            text=f"Ports of selected component  "
                 f"({total} port{'s' if total != 1 else ''})  "
                 f"— S1 (green) from EngineeringItems  ·  S2+ from Port table")

    # ══════════════════════════════════════════════════════════════════════════
    #  Port connections tab
    # ══════════════════════════════════════════════════════════════════════════

    def _load_all_ports(self):
        if not self.db:
            return
        try:
            cols, rows = self.db.all_ports()
            if not cols:
                self._lbl_ports.config(text="No port tables detected.")
                return
            self.all_port_rows = rows
            self.port_tab_cols = cols
            self._render_port_tab(cols, rows)
            self._lbl_ports.config(
                text=f"{len(rows)} port entries  "
                     f"(S1 from EngineeringItems · S2+ from Port table)")
        except Exception as e:
            self._lbl_ports.config(text=f"Error: {e}")

    def _render_port_tab(self, cols: list[str], rows: list[list]):
        tree = self.ptree
        tree.delete(*tree.get_children())
        tree["columns"] = cols
        tree["show"]    = "headings"
        for col in cols:
            w = min(max(len(col) * 9, 60), 280)
            tree.heading(col, text=col,
                         command=lambda c=col: self._sort_col(tree, c, False))
            tree.column(col, width=w, minwidth=40, stretch=False)
        for i, row in enumerate(rows):
            tree.insert("", tk.END, iid=str(i),
                        values=[safe_str(v) for v in row],
                        tags=("odd" if i % 2 else "even",))

    def _filter_port_tab(self, *_):
        q    = self._port_q.get().lower()
        tree = self.ptree
        tree.delete(*tree.get_children())
        for i, row in enumerate(self.all_port_rows):
            if not q or any(q in safe_str(v).lower() for v in row):
                tree.insert("", tk.END, iid=str(i),
                            values=[safe_str(v) for v in row],
                            tags=("odd" if i % 2 else "even",))

    # ══════════════════════════════════════════════════════════════════════════
    #  Cell editing
    # ══════════════════════════════════════════════════════════════════════════

    def _dbl_click(self, event):
        return  # read-only mode
        if self.dtree.identify_region(event.x, event.y) == "heading":
            return
        item = self.dtree.identify_row(event.y)
        col  = self.dtree.identify_column(event.x)
        if not item or not col:
            return
        disp     = self._get_displaycols()
        disp_idx = int(col.replace("#", "")) - 1
        if disp_idx < 0 or disp_idx >= len(disp):
            return
        col_name = disp[disp_idx]
        all_idx  = list(self.dtree["columns"]).index(col_name)
        val      = self.dtree.item(item, "values")[all_idx]
        self.editor.open(item, f"#{all_idx + 1}", val)

    def _enter_key(self, _):
        return  # read-only mode

    def _on_cell_save(self, item: str, col_index: int, new_value: str):
        vals = list(self.dtree.item(item, "values"))
        if col_index >= len(vals) or vals[col_index] == new_value:
            return
        vals[col_index] = new_value
        self.dtree.item(item, values=vals, tags=("mod",))
        row_idx  = int(item)
        col_name = (self.cur_cols[col_index]
                    if col_index < len(self.cur_cols) else f"col_{col_index}")
        self.pending.setdefault(self.cur_table, {})\
                    .setdefault(row_idx, {})[col_name] = new_value
        self._status.set(
            f"⚠ Unsaved — {self.cur_table}.{col_name}  row {row_idx + 1}")

    # ══════════════════════════════════════════════════════════════════════════
    #  Search & sort
    # ══════════════════════════════════════════════════════════════════════════

    def _apply_search(self, *_):
        q    = self._srch.get().lower()
        tree = self.dtree
        tree.delete(*tree.get_children())
        for i, row in enumerate(self.cur_rows):
            if not q or any(q in safe_str(v).lower() for v in row):
                tree.insert("", tk.END, iid=str(i),
                            values=[safe_str(v) for v in row],
                            tags=("odd" if i % 2 else "even",))

    def _sort_col(self, tree: ttk.Treeview, col: str, reverse: bool):
        data = [(tree.set(c, col), c) for c in tree.get_children("")]
        try:
            data.sort(key=lambda x: (x[0] == "", float(x[0])), reverse=reverse)
        except (ValueError, TypeError):
            data.sort(key=lambda x: (x[0] == "", x[0].lower()), reverse=reverse)
        for idx, (_, child) in enumerate(data):
            tree.move(child, "", idx)

    # ══════════════════════════════════════════════════════════════════════════
    #  Header drag-to-reorder
    # ══════════════════════════════════════════════════════════════════════════

    def _hdr_press(self, event):
        if self.dtree.identify_region(event.x, event.y) == "heading":
            self._drag_from    = self._col_id_at_x(event.x)
            self._drag_start_x = event.x
            self._drag_moved   = False
        else:
            self._drag_from = None

    def _hdr_motion(self, event):
        if self._drag_from and abs(event.x - self._drag_start_x) > 8:
            self._drag_moved = True
            self.dtree.config(cursor="sb_h_double_arrow")

    def _hdr_release(self, event):
        self.dtree.config(cursor="")
        if not self._drag_from:
            return
        if self._drag_moved:
            if self.dtree.identify_region(event.x, event.y) == "heading":
                to = self._col_id_at_x(event.x)
                if to and to != self._drag_from:
                    self._move_col(self._drag_from, to)
        else:
            if self.dtree.identify_region(event.x, event.y) == "heading":
                col = self._drag_from
                if col:
                    rev = self._sort_rev.get(col, False)
                    self._sort_col(self.dtree, col, rev)
                    self._sort_rev[col] = not rev
                    arrow = " ▲" if not rev else " ▼"
                    for c in self._get_displaycols():
                        self.dtree.heading(c, text=c.rstrip(" ▲▼"))
                    self.dtree.heading(col, text=col.rstrip(" ▲▼") + arrow)
        self._drag_from  = None
        self._drag_moved = False

    def _col_id_at_x(self, x: int) -> str | None:
        col_n = self.dtree.identify_column(x)
        if not col_n or col_n == "#0":
            return None
        idx  = int(col_n.replace("#", "")) - 1
        cols = self._get_displaycols()
        return cols[idx] if 0 <= idx < len(cols) else None

    def _move_col(self, from_id: str, to_id: str):
        disp = self._get_displaycols()
        if from_id not in disp or to_id not in disp:
            return
        fi, ti = disp.index(from_id), disp.index(to_id)
        disp.insert(ti, disp.pop(fi))
        self.dtree["displaycolumns"] = disp
        self._save_col_prefs()

    def _get_displaycols(self) -> list[str]:
        d = self.dtree["displaycolumns"]
        if not d or d in ("#all", ("#all",)):
            return list(self.dtree["columns"])
        if isinstance(d, str):
            return list(self.dtree["columns"])
        return list(d)

    # ══════════════════════════════════════════════════════════════════════════
    #  Column visibility
    # ══════════════════════════════════════════════════════════════════════════

    def _save_col_prefs(self):
        if not self.cur_table:
            return
        all_cols = list(self.dtree["columns"])
        disp     = self._get_displaycols()
        hidden   = [c for c in all_cols if c not in set(disp)]
        prefs    = self.cfg["column_prefs"]
        prefs[self.cur_table] = {"hidden": hidden, "order": disp}
        self.cfg["column_prefs"] = prefs
        self.cfg.save()

    def _apply_col_prefs(self):
        if not self.cur_table:
            return
        saved = self.cfg["column_prefs"].get(self.cur_table)
        if not saved:
            return
        all_cols = list(self.dtree["columns"])
        col_set  = set(all_cols)
        hidden   = set(saved.get("hidden", []))
        order    = [c for c in saved.get("order", []) if c in col_set]
        order   += [c for c in all_cols if c not in set(order)]
        disp     = [c for c in order if c not in hidden]
        if disp:
            self.dtree["displaycolumns"] = disp

    def _on_header_rclick(self, event):
        if self.dtree.identify_region(event.x, event.y) != "heading":
            return
        col = self._col_id_at_x(event.x)
        if not col:
            return
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=f'Hide  "{col}"',
                         command=lambda: self._hide_col(col))
        menu.add_separator()
        menu.add_command(label="⊞  Show / Hide Columns…",
                         command=self._open_col_dialog)
        try:
            menu.post(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _hide_col(self, col: str):
        disp = [c for c in self._get_displaycols() if c != col]
        if not disp:
            messagebox.showwarning("Column visibility",
                                   "Can't hide the last visible column.")
            return
        self.dtree["displaycolumns"] = disp
        self._status.set(f"Column hidden: {col}  — use '⊞ Columns' to restore")
        self._save_col_prefs()

    def _open_col_dialog(self):
        if not self.dtree["columns"]:
            messagebox.showinfo("No table", "Load a table first.")
            return
        dlg = ColumnDialog(self.root, self.dtree)
        self.root.wait_window(dlg)
        if dlg.result is not None:
            self.dtree["displaycolumns"] = dlg.result
            hidden_n = len(self.dtree["columns"]) - len(dlg.result)
            self._status.set(
                f"Columns updated — {len(dlg.result)} visible"
                + (f", {hidden_n} hidden" if hidden_n else ""))
            self._save_col_prefs()

    # ══════════════════════════════════════════════════════════════════════════
    #  Settings dialog
    # ══════════════════════════════════════════════════════════════════════════

    def _open_settings(self):
        tables = self.db.all_tables if self.db else []
        dlg    = SettingsDialog(self.root, self.cfg, tables)
        self.root.wait_window(dlg)
        if dlg.result is not None:
            self.cfg["simplified_tables"] = dlg.result
            self.cfg.save()
            self._refresh_tbl_list()
            self._status.set(
                f"✓ Settings saved  ({len(dlg.result)} tables in Components view)")

    # ══════════════════════════════════════════════════════════════════════════
    #  Misc / lifecycle
    # ══════════════════════════════════════════════════════════════════════════

    def _about(self):
        messagebox.showinfo("About PSPC Viewer",
            f"PSPC Viewer v{APP_VERSION}\n\n"
            "Pregledovalnik Autodesk Plant 3D .pspc datotek.\n"
            ".pspc je SQLite baza z informacijami o inštrumentaciji (cevovodi,\n"
            "komponente, priključki). Datoteka se odpre samo za branje (read-only)\n"
            "— originalni podatki se nikoli ne spremenijo.\n\n"
            "Kaj lahko naredite:\n"
            "  • Pregledate vse tabele in vsebino baze\n"
            "  • Iščete in sortirate po stolpcih\n"
            "  • V Components načinu vidite komponente z vsemi priključki (S1–S4)\n"
            "  • Izvozite katerokoli tabelo v Excel (.xlsx)\n\n"
            "Stolpci:\n"
            "  Right-click header  → skrij ta stolpec\n"
            "  ⊞ Columns button   → pokaži / skrij stolpce\n"
            "  Drag header L/R    → preuredi stolpce\n"
            "  Click header       → razvrsti (▲ ▼)\n\n"
            "Bližnjice:  Ctrl+O  Odpri  ·  Ctrl+E  Izvozi v Excel  ·  F5  Osveži\n\n"
            "Config:  ~/.pspcviewer/config.json")

    def cmd_howto(self):
        win = tk.Toplevel(self.root)
        win.title("How To Use — PSPC Viewer")
        win.resizable(False, False)
        win.grab_set()

        text = (
            "═══════════════════════════════════════\n"
            "  WHAT IS THIS PROGRAM?\n"
            "═══════════════════════════════════════\n"
            "PSPC Viewer lets you inspect .pspc files from\n"
            "Autodesk Plant 3D projects. A .pspc file is a\n"
            "SQLite database containing piping and\n"
            "instrumentation data: components, ports,\n"
            "engineering items, and their connections.\n"
            "\n"
            "The file is always opened READ-ONLY —\n"
            "your original data is never modified.\n"
            "\n"
            "═══════════════════════════════════════\n"
            "  GETTING STARTED\n"
            "═══════════════════════════════════════\n"
            "1. Click  📂 Open  (or Ctrl+O) and select\n"
            "   a .pspc file from your Plant 3D project.\n"
            "2. The left panel lists all tables in the file.\n"
            "3. Click a table name to view its contents.\n"
            "\n"
            "═══════════════════════════════════════\n"
            "  BROWSING DATA\n"
            "═══════════════════════════════════════\n"
            "• Click a column header   → sort ascending / descending\n"
            "• Right-click a header    → hide that column\n"
            "• ⊞ Columns button        → show or hide any column\n"
            "• Drag a column header    → reorder columns\n"
            "• Search box (top-left)   → filter table list by name\n"
            "\n"
            "═══════════════════════════════════════\n"
            "  COMPONENTS VIEW\n"
            "═══════════════════════════════════════\n"
            "Switch to  Components  mode in the top-left\n"
            "dropdown to see only the main instrument/\n"
            "equipment tables.\n"
            "\n"
            "Click any component row to see all its ports\n"
            "listed below (S1–S4 connections):\n"
            "  S1 (green)  = defined directly in EngineeringItems\n"
            "  S2 / S3 / S4 = looked up via the PartPort table\n"
            "\n"
            "═══════════════════════════════════════\n"
            "  PORT CONNECTIONS TAB\n"
            "═══════════════════════════════════════\n"
            "Click  🔌 Port Connections  to open a full\n"
            "view of all port-to-port connections in the file.\n"
            "Useful for tracing how components are linked.\n"
            "\n"
            "═══════════════════════════════════════\n"
            "  EXPORTING TO EXCEL\n"
            "═══════════════════════════════════════\n"
            "Click  📊 Export Excel  (or Ctrl+E) to save\n"
            "every table as a separate sheet in an .xlsx file.\n"
            "\n"
            "═══════════════════════════════════════\n"
            "  KEYBOARD SHORTCUTS\n"
            "═══════════════════════════════════════\n"
            "  Ctrl+O   Open file\n"
            "  Ctrl+E   Export to Excel\n"
            "  F5       Reload current table\n"
        )

        frm = ttk.Frame(win, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        sb = ttk.Scrollbar(frm, orient=tk.VERTICAL)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        box = tk.Text(frm, width=56, height=28, wrap=tk.NONE,
                      font=("Courier", 10), relief=tk.FLAT,
                      yscrollcommand=sb.set, state=tk.NORMAL)
        box.insert(tk.END, text)
        box.config(state=tk.DISABLED)
        box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=box.yview)

        ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 8))

    def _on_resize(self, _):
        if hasattr(self, "_resize_job"):
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(
            500, lambda: self.cfg.__setitem__("geometry", self.root.geometry()))

    def _on_close(self):
        if self.pending:
            if messagebox.askyesno("Unsaved changes",
                    "You have unsaved changes. Save before closing?"):
                self.cmd_save()
        self.cfg.save()
        if self.conn:
            self.conn.close()
        self.root.destroy()
