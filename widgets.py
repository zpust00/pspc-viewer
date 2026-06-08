"""
widgets.py — small reusable tkinter widgets.

Currently contains:
  CellEditor — places an Entry widget directly over a Treeview cell for inline editing.
"""
import tkinter as tk
from tkinter import ttk


class CellEditor:
    """
    Overlays a small Entry widget on top of a Treeview cell so the user can
    edit the value in-place.

    Usage
    -----
    editor = CellEditor(tree, on_save_callback)
    editor.open(item_iid, "#2", current_value)   # open on column 2
    editor.close()                               # close without saving
    """

    def __init__(self, tree: ttk.Treeview, on_save):
        """
        Parameters
        ----------
        tree     : the Treeview to attach to
        on_save  : callback(item_iid: str, col_index: int, new_value: str)
                   called when the user commits the edit
        """
        self.tree    = tree
        self.on_save = on_save
        self._w: tk.Entry | None = None

    # ── Public API ────────────────────────────────────────────────────────────

    def open(self, item: str, col_id: str, current: str):
        """Open the editor over (item, col_id) pre-filled with current."""
        self.close()
        bbox = self.tree.bbox(item, col_id)
        if not bbox:
            return
        x, y, w, h = bbox
        col_index   = int(col_id.replace("#", "")) - 1

        var = tk.StringVar(value=current)
        e   = tk.Entry(self.tree, textvariable=var,
                       relief="solid", bd=1,
                       font=("Consolas", 9), bg="#fffde7")
        e.place(x=x, y=y, width=max(w, 120), height=h)
        e.focus_set()
        e.select_range(0, tk.END)
        self._w = e

        commit = lambda _=None: (self.on_save(item, col_index, var.get()), self.close())
        e.bind("<Return>",    commit)
        e.bind("<Tab>",       commit)
        e.bind("<Escape>",    lambda _: self.close())
        e.bind("<FocusOut>",  lambda _: self.close())

    def close(self):
        """Destroy the editor widget without saving."""
        if self._w:
            self._w.destroy()
            self._w = None
