# Duct Automation – AutoCAD Generator & PP-BOM

A Python tool that automatically generates **HVAC duct layouts in AutoCAD** and produces a **Parts & Pieces Bill of Materials (PP-BOM)** in Excel and CSV formats.

---

## Features

| Feature | Details |
|---|---|
| **AutoCAD Drawing** | Connects to a running AutoCAD instance via COM and draws duct plans automatically |
| **Duct types** | Rectangular, Round (circular), Oval |
| **Fittings** | 90°/45° Elbows, Tees, Reducers, Volume Dampers, Diffusers/Grilles, End Caps |
| **Layer management** | Separate layers for Supply, Return, Exhaust, Fittings, Dimensions, Text |
| **Annotations** | Duct size labels, tag numbers, centrelines, length dimensions, title block |
| **PP-BOM** | Consolidated bill of materials with quantities, areas (m²), material summary |
| **BOM export** | Excel (.xlsx) with formatting + CSV (.csv) |
| **Simulation mode** | Works without AutoCAD on any platform (Linux/Mac/Windows) |
| **GUI** | Tkinter graphical interface |
| **CLI** | Full command-line interface |

---

## Project Structure

```
Duct-automation-/
├── duct_automation/
│   ├── __init__.py
│   ├── __main__.py          # python -m duct_automation
│   ├── cli.py               # Command-line interface
│   ├── gui.py               # Tkinter GUI
│   ├── core.py              # Pipeline orchestrator
│   ├── autocad/
│   │   ├── connection.py    # AutoCAD COM connection + simulation stubs
│   │   ├── layers.py        # Layer definitions and setup
│   │   └── helpers.py       # Low-level drawing primitives
│   └── duct/
│       ├── models.py        # Data models (ducts, fittings, system)
│       ├── layout_parser.py # JSON/YAML layout file parser
│       └── drawing.py       # Duct + fitting drawing engine
├── bom/
│   ├── generator.py         # PP-BOM generator
│   └── exporter.py          # Excel + CSV exporters
├── examples/
│   └── office_hvac.json     # Full example layout
├── tests/
│   └── test_duct_automation.py
├── requirements.txt
└── setup.py
```

---

## Installation

```bash
pip install -r requirements.txt

# Windows only – AutoCAD COM interface:
pip install pywin32
```

---

## Quick Start

### 1. Generate an example layout file

```bash
python -m duct_automation --create-example my_project.json
```

### 2. Draw ducts and generate BOM (simulation – no AutoCAD needed)

```bash
python -m duct_automation --layout my_project.json --dry-run
```

### 3. Draw in AutoCAD (Windows, AutoCAD must be running)

```bash
python -m duct_automation --layout my_project.json --output ./output
```

### 4. Save the drawing file

```bash
python -m duct_automation --layout my_project.json --save-dwg ./drawings/duct_layout.dwg
```

### 5. Launch the GUI

```bash
python -m duct_automation --gui
```

---

## Layout File Format

Layout files are JSON (or YAML) describing the duct system:

```json
{
  "project_name": "Office Level 3",
  "project_number": "P-2025-001",
  "drawn_by": "Engineer A",
  "date": "2025-01-15",
  "scale": "1:100",
  "runs": [
    {
      "name": "Supply Main",
      "sections": [
        {
          "type": "rectangular",
          "tag": "D-01",
          "width": 600,
          "height": 300,
          "length": 4000,
          "start": {"x": 0, "y": 0},
          "angle": 0,
          "material": "galvanized",
          "gauge": 0.8
        },
        {
          "type": "round",
          "tag": "D-02",
          "diameter": 250,
          "length": 2000,
          "start": {"x": 4200, "y": 0}
        }
      ],
      "fittings": [
        {
          "type": "TEE",
          "shape": "rectangular",
          "tag": "F-01",
          "width": 600,
          "height": 300,
          "position": {"x": 4100, "y": 0}
        },
        {
          "type": "REDUCER",
          "shape": "rectangular",
          "tag": "F-02",
          "width": 600,
          "height": 300,
          "outlet_width": 400,
          "outlet_height": 300,
          "position": {"x": 4000, "y": 0}
        }
      ]
    }
  ]
}
```

### Duct Section Fields

| Field | Type | Description |
|---|---|---|
| `type` | string | `rectangular`, `round`, or `oval` |
| `tag` | string | Label shown in drawing and BOM |
| `width` / `height` | float (mm) | Rectangular duct cross-section |
| `diameter` | float (mm) | Round duct diameter |
| `major` / `minor` | float (mm) | Oval duct axes |
| `length` | float (mm) | Duct section length |
| `start` | `{x, y}` | Insertion point in drawing units (mm) |
| `angle` | float (°) | Rotation angle (0 = horizontal) |
| `material` | string | `galvanized`, `stainless_steel`, `aluminum`, `flexible` |
| `gauge` | float (mm) | Sheet metal thickness |

### Fitting Types

| `type` key | Description |
|---|---|
| `ELBOW_90` | 90° elbow |
| `ELBOW_45` | 45° elbow |
| `TEE` | Tee branch |
| `CROSS` | Cross junction |
| `REDUCER` | Reducer / transition |
| `DAMPER` | Volume damper |
| `DIFFUSER` | Supply/return diffuser or grille |
| `CAP` | End cap |

### Run Name → AutoCAD Layer

| Run name contains | Layer |
|---|---|
| `supply` | `DUCT-SUPPLY` (red) |
| `return` | `DUCT-RETURN` (green) |
| `exhaust` | `DUCT-EXHAUST` (magenta) |
| `fresh` | `DUCT-FRESH` (cyan) |
| *(other)* | `DUCT-SUPPLY` |

---

## Python API

```python
from duct_automation.core import run

result = run(
    layout="my_project.json",   # or a dict
    output_dir="./output",
    dry_run=True,               # True = no AutoCAD connection
    export_bom=True,
    bom_formats=("xlsx", "csv"),
)

bom = result["bom"]
print(f"Total sheet metal area: {bom.total_area_sqm():.2f} m²")
```

---

## Running Tests

```bash
pip install pytest openpyxl
pytest tests/ -v
```

---

## AutoCAD Requirements

- AutoCAD 2018 or later (Windows)
- `pywin32` package (`pip install pywin32`)
- AutoCAD must be **open and running** before executing the tool
- On non-Windows platforms, the tool runs in **simulation mode** automatically

---

## BOM Output Example

```
====================================================================================================
  PARTS & PIECES BILL OF MATERIALS
  Project: Office Level 3 HVAC   No: P-2025-003
====================================================================================================
Item  Tag          Description                    Size                   Material         Gauge        Qty  Unit   Area(m²)
----------------------------------------------------------------------------------------------------
   1  D-01,D-02    Rectangular Duct               600x300mm              Galvanized Steel    0.8      10000  mm       1.800
   2  D-03         Rectangular Duct               400x300mm              Galvanized Steel    0.6       3000  mm       0.420
   3  E-01         Round Duct                     Ø400mm                 Galvanized Steel    0.7       4000  mm       5.027
   4  F-01         Tee (rectangular)              600x300mm              Galvanized Steel    0.0          1  EA       0.000
   ...
====================================================================================================
  MATERIAL SUMMARY
  Galvanized Steel      0.8        12.600 m²
  Galvanized Steel      0.6         7.340 m²
  GRAND TOTAL..............................  19.940 m²
====================================================================================================
```
