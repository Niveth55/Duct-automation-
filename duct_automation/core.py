"""
Core orchestrator – connects all components and runs the full pipeline.

Pipeline:
  1. Load duct layout (JSON/YAML)
  2. Connect to AutoCAD (or simulation)
  3. Set up layers
  4. Draw duct system
  5. Zoom extents
  6. Generate BOM
  7. Export BOM (Excel + CSV)
"""

import logging
from pathlib import Path
from typing import Optional, Union

from .duct.layout_parser import load_file, parse_json
from .duct.models import DuctSystem
from .duct.drawing import draw_duct_system
from .autocad.connection import AutoCADConnection
from .autocad.layers import setup_layers
from .bom.generator import generate_bom, bom_to_text
from .bom.exporter import export_excel, export_csv

logger = logging.getLogger(__name__)


def run(
    layout: Union[str, Path, dict],
    output_dir: Union[str, Path] = ".",
    acad_visible: bool = True,
    save_dwg: Optional[str] = None,
    export_bom: bool = True,
    bom_formats: tuple = ("xlsx", "csv"),
    dry_run: bool = False,
) -> dict:
    """
    Full pipeline entry point.

    Args:
        layout       : Path to a JSON/YAML layout file, or a pre-parsed dict.
        output_dir   : Directory for BOM output files.
        acad_visible : Whether to show the AutoCAD window.
        save_dwg     : If given, save the drawing to this path.
        export_bom   : Generate and export BOM files.
        bom_formats  : Tuple of formats to export ("xlsx", "csv").
        dry_run      : If True, use simulation mode regardless of platform.

    Returns:
        dict with keys: "system", "bom", "bom_paths"
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load layout
    if isinstance(layout, dict):
        system: DuctSystem = parse_json(layout)
    else:
        logger.info("Loading layout: %s", layout)
        system = load_file(layout)

    logger.info("Loaded system: '%s' with %d runs.", system.project_name, len(system.runs))

    # 2. Connect to AutoCAD
    conn = AutoCADConnection(visible=acad_visible)
    if dry_run:
        from .autocad.connection import (
            _SimApp, _SimDoc, _SimModelSpace,
        )
        conn._app = _SimApp()
        conn._doc = _SimDoc()
        conn._mspace = _SimModelSpace()
        conn._simulated = True
    else:
        conn.connect()

    # 3. Set up layers
    setup_layers(conn.doc)

    # 4. Draw
    logger.info("Drawing duct system into AutoCAD …")
    draw_duct_system(conn.mspace, system)
    conn.zoom_extents()

    # 5. Save DWG
    if save_dwg and not conn.is_simulated:
        conn.save(save_dwg)
        logger.info("Drawing saved: %s", save_dwg)

    # 6 & 7. BOM
    bom = None
    bom_paths = {}

    if export_bom:
        logger.info("Generating BOM …")
        bom = generate_bom(system)

        print("\n" + bom_to_text(bom))

        project_slug = (system.project_name or "duct_project").replace(" ", "_")

        if "xlsx" in bom_formats:
            xlsx_path = output_dir / f"{project_slug}_BOM.xlsx"
            export_excel(bom, xlsx_path)
            bom_paths["xlsx"] = str(xlsx_path)

        if "csv" in bom_formats:
            csv_path = output_dir / f"{project_slug}_BOM.csv"
            export_csv(bom, csv_path)
            bom_paths["csv"] = str(csv_path)

    logger.info("Pipeline complete.")
    return {"system": system, "bom": bom, "bom_paths": bom_paths}
