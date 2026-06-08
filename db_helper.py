"""
db_helper.py — pure data layer for PSPC Viewer.

DbHelper wraps a sqlite3 connection and exposes clean methods that return
plain Python data (lists, dicts).  No tkinter imports here.
"""
import sqlite3
from collections import defaultdict
from typing import Optional

from constants import (
    EI_VIEW_COLS, PORT_DETAIL_COLS, HIDDEN_COLS, PORT_KW,
)


def safe_str(v) -> str:
    """Convert any SQLite value to a display-safe string."""
    if v is None:                         return ""
    if isinstance(v, (bytes, bytearray)): return v.hex().upper()
    return str(v)


def _is_blob_col(sample: list) -> bool:
    if not sample:
        return False
    return sum(1 for v in sample if isinstance(v, (bytes, bytearray))) > len(sample) * 0.5


# ─────────────────────────────────────────────────────────────────────────────

class DbHelper:
    """
    All database I/O for the PSPC Viewer lives here.

    Every public method returns plain Python data so the UI layer (viewer.py)
    stays free of SQL and sqlite3 concerns.
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._tables: list[str] = []
        self._refresh_table_list()

    # ── Table introspection ───────────────────────────────────────────────────

    def _refresh_table_list(self):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name COLLATE NOCASE")
        self._tables = [r[0] for r in cur.fetchall()]

    @property
    def all_tables(self) -> list[str]:
        return self._tables

    def col_exists(self, table: str, col: str) -> bool:
        try:
            cur = self.conn.cursor()
            cur.execute(f'PRAGMA table_info("{table}")')
            return any(c[1] == col for c in cur.fetchall())
        except Exception:
            return False

    def _table_cols(self, table: str) -> list[str]:
        cur = self.conn.cursor()
        cur.execute(f'PRAGMA table_info("{table}")')
        return [c[1] for c in cur.fetchall()]

    # ── Raw table data ────────────────────────────────────────────────────────

    def table_raw(self, name: str, show_hidden: bool = False
                  ) -> tuple[list[str], list[list]]:
        """
        Return (visible_cols, rows) for a raw SQL table.
        Hidden/blob columns are filtered out unless show_hidden is True.
        """
        cur = self.conn.cursor()
        cur.execute(f'SELECT * FROM "{name}"')
        all_cols = [d[0] for d in cur.description]
        all_rows = [list(r) for r in cur.fetchall()]

        if show_hidden:
            vis = list(range(len(all_cols)))
        else:
            vis = [i for i, c in enumerate(all_cols) if c not in HIDDEN_COLS]
            if all_rows:
                vis = [i for i in vis
                       if not _is_blob_col([r[i] for r in all_rows[:20]])]

        cols = [all_cols[i] for i in vis]
        rows = [[r[i] for i in vis] for r in all_rows]
        return cols, rows

    # ── EngineeringItems smart view ───────────────────────────────────────────

    def ei_view(self, show_hidden: bool = False
                ) -> tuple[list[str], list[list], list[Optional[int]]]:
        """
        Return (col_labels, rows, pnpids) for the EngineeringItems smart view.
        Shows all columns (same filtering as table_raw); PnPID is tracked
        separately for the port panel but not included as a visible column.
        """
        cur = self.conn.cursor()
        cur.execute('SELECT * FROM "EngineeringItems"')
        all_cols = [d[0] for d in cur.description]
        all_rows = [list(r) for r in cur.fetchall()]

        pnpid_idx = all_cols.index("PnPID") if "PnPID" in all_cols else None
        pnpids    = [
            (int(r[pnpid_idx]) if r[pnpid_idx] is not None else None)
            for r in all_rows
        ] if pnpid_idx is not None else [None] * len(all_rows)

        if show_hidden:
            vis = [i for i in range(len(all_cols)) if i != pnpid_idx]
        else:
            vis = [i for i, c in enumerate(all_cols)
                   if c not in HIDDEN_COLS and i != pnpid_idx]
            if all_rows:
                vis = [i for i in vis
                       if not _is_blob_col([r[i] for r in all_rows[:20]])]

        cols = [all_cols[i] for i in vis]
        rows = [[r[i] for i in vis] for r in all_rows]
        return cols, rows, pnpids

    # ── Component-specific join view ──────────────────────────────────────────

    def comp_join(self, table: str
                  ) -> tuple[list[str], list[list], list[Optional[int]]]:
        """
        Return (col_labels, rows, pnpids) for a component table joined with
        EngineeringItems.  Handles tables that have only a PnPID column
        (e.g. Fasteners, BlindDisk) without SQL errors.
        """
        cur       = self.conn.cursor()
        all_t     = self._table_cols(table)
        t_vis     = [c for c in all_t if c not in HIDDEN_COLS and c != "PnPID"]

        # Drop blob columns based on a data sample
        if t_vis:
            cur.execute(f'SELECT * FROM "{table}" LIMIT 20')
            sample = cur.fetchall()
            if sample:
                t_vis = [c for c in t_vis
                         if not _is_blob_col([r[all_t.index(c)] for r in sample])]

        has_ei     = "EngineeringItems" in self._tables
        sel_parts  = ["t.PnPID"]
        col_labels = []

        for c in t_vis:
            sel_parts.append(f't."{c}"')
            col_labels.append(c)

        if has_ei:
            used_labels = set(col_labels)

            # Always-pinned EI columns (added before the variable extras)
            pinned = [
                ("PartFamilyLongDesc", "Description"),
                ("ItemCode",           "Item Code"),
            ]
            for db_col, lbl in pinned:
                if db_col not in t_vis and lbl not in used_labels:
                    sel_parts.append(f'ei."{db_col}" AS "{lbl}"')
                    col_labels.append(lbl)
                    used_labels.add(lbl)

            # Additional EI columns (up to 7), skipping already-pinned ones
            pinned_db = {db_col for db_col, _ in pinned}
            ei_extra = [c for c, lbl, _ in EI_VIEW_COLS
                        if c not in t_vis and c not in pinned_db
                        and lbl not in used_labels][:7]
            for c in ei_extra:
                lbl = next((l for dc, l, _ in EI_VIEW_COLS if dc == c), c)
                sel_parts.append(f'ei."{c}" AS "{lbl}"')
                col_labels.append(lbl)
            join = (f'FROM "{table}" t '
                    f'LEFT JOIN "EngineeringItems" ei ON t.PnPID = ei.PnPID')
        else:
            join = f'FROM "{table}" t'

        cur.execute(f'SELECT {", ".join(sel_parts)} {join}')
        raw    = [list(r) for r in cur.fetchall()]
        pnpids = [int(r[0]) if r[0] is not None else None for r in raw]
        rows   = [r[1:] for r in raw]
        return col_labels, rows, pnpids

    # ── Port map ──────────────────────────────────────────────────────────────

    def port_map(self) -> dict[int, list[list]]:
        """
        Return {pnpid: [port_row, …]} for all components that have S2+ ports
        in the Port table (via PartPort).  Returns empty dict if tables are absent.
        """
        result: dict[int, list[list]] = defaultdict(list)
        if "PartPort" not in self._tables or "Port" not in self._tables:
            return result
        try:
            cols_sql = ", ".join(f'p."{c}"' for c, _, _ in PORT_DETAIL_COLS)
            rows     = self.conn.execute(
                f'SELECT pp.Part, {cols_sql} '
                f'FROM PartPort pp JOIN Port p ON p.PnPID = pp.Port '
                f'ORDER BY pp.Part, p.PortName'
            ).fetchall()
            for row in rows:
                result[int(row[0])].append(list(row[1:]))
        except Exception:
            pass
        return result

    def s1_port(self, pnpid: int) -> Optional[list]:
        """
        Return the S1 (primary) port data stored inline in EngineeringItems,
        or None if the component is not found.
        """
        if "EngineeringItems" not in self._tables:
            return None
        try:
            col_sql = ", ".join(f'"{c}"' for c, _, _ in PORT_DETAIL_COLS)
            row     = self.conn.execute(
                f'SELECT {col_sql} FROM "EngineeringItems" WHERE PnPID = ?',
                (pnpid,)
            ).fetchone()
            return list(row) if row else None
        except Exception:
            return None

    # ── All ports union (Port Connections tab) ────────────────────────────────

    def all_ports(self) -> tuple[list[str], list[list]]:
        """
        Return (col_labels, rows) combining S1 ports (from EngineeringItems)
        and S2+ ports (from Port table via PartPort) in one unified view.
        Falls back to a raw union of any port-keyword tables if the Plant 3D
        schema is not present.
        """
        tbl_lc = {t.lower(): t for t in self._tables}

        if all(k in tbl_lc for k in ("engineeringitems", "partport", "port")):
            return self._all_ports_plant3d(tbl_lc)
        return self._all_ports_fallback(tbl_lc)

    def _all_ports_plant3d(self, tbl_lc: dict) -> tuple[list[str], list[list]]:
        ei, pp, pt = (tbl_lc["engineeringitems"],
                      tbl_lc["partport"], tbl_lc["port"])
        q = f"""
        SELECT
            ei.PnPID             AS "Part ID",
            ei.PartFamilyLongDesc AS "Component",
            ei.PortName           AS "Port",
            ei.NominalDiameter    AS "Nom. Ø",
            ei.NominalUnit        AS "Unit",
            ei.EndType            AS "End Type",
            ei.PressureClass      AS "Press.Class",
            ei.Schedule           AS "Schedule",
            ei.WallThickness      AS "Wall Thk",
            ei.MatchingPipeOd     AS "Match. OD",
            ei.FlangeStd          AS "Flange Std",
            'EI (S1)'             AS "Source"
        FROM "{ei}" ei WHERE ei.PortName IS NOT NULL
        UNION ALL
        SELECT
            ei.PnPID,
            ei.PartFamilyLongDesc,
            p.PortName,
            p.NominalDiameter, p.NominalUnit, p.EndType,
            p.PressureClass,   p.Schedule,    p.WallThickness,
            p.MatchingPipeOd,  p.FlangeStd,
            'Port table (S2+)'
        FROM "{pt}" p
        JOIN "{pp}" pp2 ON pp2.Port  = p.PnPID
        JOIN "{ei}" ei  ON ei.PnPID  = pp2.Part
        ORDER BY 2, 1, 3
        """
        cur  = self.conn.cursor()
        cur.execute(q)
        cols = [d[0] for d in cur.description]
        rows = [list(r) for r in cur.fetchall()]
        return cols, rows

    def _all_ports_fallback(self, tbl_lc: dict) -> tuple[list[str], list[list]]:
        port_tables = [orig for lc, orig in tbl_lc.items()
                       if any(kw in lc for kw in PORT_KW)]
        if not port_tables:
            return [], []
        cols: list[str] | None = None
        rows: list[list] = []
        cur = self.conn.cursor()
        for t in port_tables:
            cur.execute(f'SELECT * FROM "{t}"')
            if cols is None:
                cols = ["⊞ Table"] + [d[0] for d in cur.description]
            for row in cur.fetchall():
                rows.append([t] + list(row))
        return (cols or []), rows

    # ── Write changes back to DB ──────────────────────────────────────────────

    def save_changes(self, pending: dict) -> None:
        """
        Write pending edits to the database and commit.

        pending format: {table_name: {row_index: {col_name: new_value}}}
        row_index is 0-based and corresponds to the rowid order at load time.
        """
        cur = self.conn.cursor()
        for tbl, rows in pending.items():
            cur.execute(f'SELECT rowid FROM "{tbl}"')
            rowid_map = [r[0] for r in cur.fetchall()]
            for row_idx, changes in rows.items():
                if row_idx >= len(rowid_map):
                    continue
                rowid = rowid_map[row_idx]
                for col, val in changes.items():
                    cur.execute(
                        f'UPDATE "{tbl}" SET "{col}" = ? WHERE rowid = ?',
                        (val, rowid))
        self.conn.commit()

    # ── Export to Excel ───────────────────────────────────────────────────────

    def export_excel(self, dest_path: str) -> None:
        """Export every table to a sheet in dest_path (.xlsx)."""
        import pandas as pd

        with pd.ExcelWriter(dest_path, engine="openpyxl") as wr:
            for tbl in self._tables:
                df = pd.read_sql_query(f'SELECT * FROM "{tbl}"', self.conn)
                for col in df.columns:
                    if df[col].dtype == object:
                        df[col] = df[col].apply(
                            lambda v: v.hex().upper()
                            if isinstance(v, (bytes, bytearray)) else v)
                df.to_excel(wr, sheet_name=tbl[:31], index=False)
