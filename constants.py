"""
constants.py — shared constants for PSPC Viewer
No imports beyond the stdlib; safe to import from anywhere.
"""
import os

APP_VERSION = "1.3"

# ── Settings file location ─────────────────────────────────────────────────
SETTINGS_DIR  = os.path.join(os.path.expanduser("~"), ".pspcviewer")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "config.json")

# ── Plant Vault Projects root (toolbar quick-open) ─────────────────────────
PLANT_VAULT_ROOT = os.path.join(os.path.expanduser("~"), "Documents", "Plant Vault Projects", "Projects")

# ── Default 'Components' simplified table list ─────────────────────────────
DEFAULT_SIMPLIFIED: list[str] = [
    "EngineeringItems", "BlindDisk", "BlindFlange", "BoltSet", "Clamp",
    "Coupling", "Cross", "Elbow", "Fasteners", "Flange", "Gasket",
    "Instrument", "Olet", "Pipe", "PipeRunComponent", "Reducer",
    "SingleBranchFitting", "StubEnd", "Swage", "Tee", "Valve",
    "ValveActuator", "ValveActuatorMap",
]

# ── EngineeringItems smart-view columns ────────────────────────────────────
# Format: (db_column_name, display_label, pixel_width)
EI_VIEW_COLS: list[tuple] = [
    ("PartFamilyLongDesc",  "Description",    280),
    ("PartCategory",         "Category",       100),
    ("NominalDiameter",      "Nom. Ø",          70),
    ("NominalUnit",          "Unit",             50),
    ("EndType",              "End Type",         80),
    ("PressureClass",        "Press.Class",      85),
    ("Schedule",             "Schedule",         70),
    ("WallThickness",        "Wall Thk",         70),
    ("ConnectionPortCount",  "Ports",            55),
    ("Manufacturer",         "Manufacturer",    140),
    ("ItemCode",             "Item Code",       100),
    ("Material",             "Material",        100),
    ("DesignStd",            "Design Std",      110),
    ("Weight",               "Weight",           70),
    ("WeightUnit",           "Wt. Unit",         65),
]

# ── Port detail bottom-panel columns ───────────────────────────────────────
PORT_DETAIL_COLS: list[tuple] = [
    ("PortName",        "Port",          65),
    ("NominalDiameter", "Nom. Ø",        75),
    ("NominalUnit",     "Unit",           50),
    ("EndType",         "End Type",       80),
    ("PressureClass",   "Press.Class",    85),
    ("Schedule",        "Schedule",       70),
    ("WallThickness",   "Wall Thk",       70),
    ("MatchingPipeOd",  "Match. OD",      90),
    ("FlangeStd",       "Flange Std",     90),
    ("GasketStd",       "Gasket Std",     80),
    ("Facing",          "Facing",         70),
    ("FlangeThickness", "Flange Thk",     80),
    ("EngagementLength","Engage Len",     85),
    ("LengthUnit",      "Len Unit",       65),
]

# ── Columns always hidden in raw view (binary GUIDs / internals) ───────────
HIDDEN_COLS: set[str] = {
    "PnPGuid", "PnPTimestamp", "SizeRecordId", "PartFamilyId",
    "CatalogPartFamilyId", "CatalogPartId", "ValveBodyFamilyId",
    "ValveBodyPartSizeId", "ActuatorFamilyId", "ActuatorPartSizeId",
    "CatalogId", "ContentGeometryParamDefinition",
    "ContentIsoSymbolDefinition", "ContentGeometryTemplate",
}

# ── Keywords used to auto-detect port-related tables ──────────────────────
PORT_KW: tuple = (
    "port", "connect", "nozzle", "endpoint", "endtype",
    "end_type", "branch", "open_end",
)
