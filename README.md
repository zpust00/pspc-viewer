# PSPC Viewer — Autodesk Plant 3D

Python desktop aplikacija za odpiranje, pregledovanje in urejanje
**Autodesk Plant 3D `.pspc` datotek** (SQLite baze podatkov).

---

## Funkcionalnosti

| | |
|---|---|
| 📂 Odpri `.pspc` | File dialog — podpira vse SQLite formate |
| 📋 Tabele | Levi panel prikaže vse tabele v bazi |
| **All / Components** | Toggle med celotnim seznamom in poenostavljenim pogledom |
| ⚙ Nastavi Components | Izberi katere tabele so vidne v Components pogledu |
| 🔍 Iskanje | Real-time filter znotraj vsake tabele |
| ✏️ Uredi celice | Dvojni klik → inline urejanje, spremembe se označijo rumeno |
| 💾 Shrani | Zapiše spremembe nazaj v SQLite datoteko (Ctrl+S) |
| 📊 Export Excel | Vse tabele → en `.xlsx` delovni zvezek (Ctrl+E) |
| 🔌 Port Connections | Samodejno združi S1 (iz EngineeringItems) in S2/S3/S4 (iz Port tabele) |
| 👁️ Skrij stolpce | Desni klik na header → skrij; gumb **⊞ Columns** → upravljaj vse |
| ↔️ Premakni stolpce | Povleci header levo/desno za premik |
| ↕️ Sortiraj | Klik na header → razvrsti (▲/▼) |
| 💾 Nastavitve | Zadnja odprta datoteka in okno se zapomni ob ponovnem zagonu |

---

## Struktura projekta

```
SQLreader_job/
│
├── main.py          ← vstopna točka, samo zažene aplikacijo
│
├── constants.py     ← vse konstante (EI_VIEW_COLS, HIDDEN_COLS, …)
├── settings.py      ← Settings (JSON) + SettingsDialog (⚙ okno)
├── dialogs.py       ← ColumnDialog (pogovorno okno za stolpce)
├── widgets.py       ← CellEditor (inline urejanje celic)
│
├── db_helper.py     ← DbHelper — ves SQL tukaj, brez tkinter
│                      (table_raw, ei_view, comp_join, port_map, …)
│
└── viewer.py        ← PSPCViewer — ves tkinter tukaj, brez SQL
```

> **Ključna ločitev:** `db_helper.py` ne pozna tkinter, `viewer.py` ne piše SQL.

---

## Zahteve

- **Python 3.10+**
- `pandas >= 2.0`
- `openpyxl >= 3.1`
- `tkinter` — že vgrajen v Python (ni treba namestiti)

```bash
pip install -r requirements.txt
```

---

## Zagon

```bash
# Normalen zagon
python main.py

# Neposredno odpri datoteko
python main.py "C:\Projekti\PS315.pspc"
```

---

## Build → standalone `.exe` (Windows)

```bat
build_exe.bat
```

Ustvari `dist\PSPCViewer.exe` — ne potrebuje nameščenega Pythona.

> Zahteva PyInstaller:  `pip install pyinstaller`

---

## Bližnjice

| Tipke | Akcija |
|---|---|
| `Ctrl+O` | Odpri datoteko |
| `Ctrl+S` | Shrani spremembe v bazo |
| `Ctrl+E` | Izvozi v Excel |
| `F5` | Znova naloži trenutno tabelo |
| Dvojni klik na celico | Uredi celico |
| Klik na header | Razvrsti stolpec (▲/▼) |
| Vleci header L/R | Premakni stolpec |
| Desni klik na header | Skrij stolpec / upravljaj stolpce |

---

## Port Connections

Aplikacija **samodejno** zazna Plant 3D strukturo in združi:

- **S1** (zeleno) — primarni port, shranjen v `EngineeringItems` (inline stolpci)
- **S2, S3, S4 …** — dodatni porti iz tabele `Port` (prek `PartPort`)

Kliknite komponento v Components pogledu → vsi porti se prikažejo v spodnjem panelu.

### Tabele za Port Connections
```
EngineeringItems  →  PartPort  →  Port
       (S1)                       (S2+)
```

---

## Nastavitve

Shranjene v `~/.pspcviewer/config.json`:

```json
{
  "simplified_tables": ["EngineeringItems", "Valve", "Elbow", "…"],
  "last_file": "C:?????/???????/?????.pspc",
  "show_hidden_cols": false,
  "geometry": "1420x900",
  "panel_mode": "components"
}
```
