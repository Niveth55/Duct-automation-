"""
Command-line interface for Duct Automation.

Usage examples:
    python -m duct_automation --layout my_project.json
    python -m duct_automation --layout my_project.yaml --output ./output --dry-run
    python -m duct_automation --layout my_project.json --save-dwg ./drawings/duct.dwg
    python -m duct_automation --gui
"""

import argparse
import logging
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="duct_automation",
        description="Duct Automation – AutoCAD drawing generator and PP-BOM exporter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Draw from JSON layout and generate BOM in ./output
  python -m duct_automation --layout project.json --output ./output

  # Dry-run (simulation, no AutoCAD required)
  python -m duct_automation --layout project.json --dry-run

  # Save the AutoCAD drawing file
  python -m duct_automation --layout project.json --save-dwg ./drawings/duct_layout.dwg

  # Launch the graphical interface
  python -m duct_automation --gui

  # Generate example layout file
  python -m duct_automation --create-example example_project.json
        """,
    )

    p.add_argument(
        "--layout", "-l",
        metavar="FILE",
        help="Path to JSON or YAML duct layout file.",
    )
    p.add_argument(
        "--output", "-o",
        metavar="DIR",
        default="./output",
        help="Output directory for BOM files (default: ./output).",
    )
    p.add_argument(
        "--save-dwg",
        metavar="FILE",
        help="Save the AutoCAD drawing to this .dwg path.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate drawing without connecting to AutoCAD.",
    )
    p.add_argument(
        "--no-bom",
        action="store_true",
        help="Skip BOM generation.",
    )
    p.add_argument(
        "--bom-formats",
        default="xlsx,csv",
        help="Comma-separated BOM export formats (default: xlsx,csv).",
    )
    p.add_argument(
        "--hidden",
        action="store_true",
        help="Run AutoCAD hidden (no window).",
    )
    p.add_argument(
        "--gui",
        action="store_true",
        help="Launch the graphical interface.",
    )
    p.add_argument(
        "--create-example",
        metavar="FILE",
        help="Write an example JSON layout file and exit.",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging.",
    )

    return p


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.create_example:
        _write_example(args.create_example)
        return 0

    if args.gui:
        from .gui import launch_gui
        launch_gui()
        return 0

    if not args.layout:
        parser.print_help()
        print("\nError: --layout is required (or use --gui / --create-example).")
        return 1

    from .core import run
    result = run(
        layout=args.layout,
        output_dir=args.output,
        acad_visible=not args.hidden,
        save_dwg=args.save_dwg,
        export_bom=not args.no_bom,
        bom_formats=tuple(args.bom_formats.split(",")),
        dry_run=args.dry_run,
    )

    if result["bom_paths"]:
        print("\nBOM files generated:")
        for fmt, path in result["bom_paths"].items():
            print(f"  [{fmt.upper()}] {path}")

    return 0


def _write_example(path: str):
    """Write an example JSON layout file."""
    import json

    example = {
        "project_name": "Example Office HVAC",
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
                        "type": "rectangular",
                        "tag": "D-02",
                        "width": 400,
                        "height": 300,
                        "length": 3000,
                        "start": {"x": 4200, "y": 0},
                        "angle": 0,
                        "material": "galvanized",
                        "gauge": 0.8
                    },
                    {
                        "type": "rectangular",
                        "tag": "D-03",
                        "width": 300,
                        "height": 250,
                        "length": 2500,
                        "start": {"x": 4200, "y": 1000},
                        "angle": 90,
                        "material": "galvanized",
                        "gauge": 0.6
                    }
                ],
                "fittings": [
                    {
                        "type": "TEE",
                        "shape": "rectangular",
                        "tag": "F-01",
                        "width": 600,
                        "height": 300,
                        "position": {"x": 4100, "y": 0},
                        "angle": 0
                    },
                    {
                        "type": "REDUCER",
                        "shape": "rectangular",
                        "tag": "F-02",
                        "width": 600,
                        "height": 300,
                        "outlet_width": 400,
                        "outlet_height": 300,
                        "position": {"x": 4000, "y": 0},
                        "angle": 0
                    }
                ]
            },
            {
                "name": "Return Main",
                "sections": [
                    {
                        "type": "rectangular",
                        "tag": "R-01",
                        "width": 500,
                        "height": 250,
                        "length": 5000,
                        "start": {"x": 0, "y": -2000},
                        "angle": 0,
                        "material": "galvanized",
                        "gauge": 0.8
                    }
                ],
                "fittings": [
                    {
                        "type": "ELBOW_90",
                        "shape": "rectangular",
                        "tag": "F-03",
                        "width": 500,
                        "height": 250,
                        "position": {"x": 5100, "y": -2000},
                        "angle": 0
                    },
                    {
                        "type": "DIFFUSER",
                        "shape": "rectangular",
                        "tag": "GR-01",
                        "width": 600,
                        "height": 600,
                        "position": {"x": 1000, "y": 0},
                        "quantity": 4
                    },
                    {
                        "type": "DAMPER",
                        "shape": "rectangular",
                        "tag": "VD-01",
                        "width": 500,
                        "height": 250,
                        "position": {"x": 500, "y": -2000},
                        "angle": 0
                    }
                ]
            },
            {
                "name": "Round Exhaust",
                "sections": [
                    {
                        "type": "round",
                        "tag": "E-01",
                        "diameter": 315,
                        "length": 3000,
                        "start": {"x": 0, "y": -4000},
                        "angle": 0,
                        "material": "galvanized",
                        "gauge": 0.6
                    },
                    {
                        "type": "round",
                        "tag": "E-02",
                        "diameter": 250,
                        "length": 2000,
                        "start": {"x": 3200, "y": -4000},
                        "angle": 0,
                        "material": "galvanized",
                        "gauge": 0.6
                    }
                ],
                "fittings": [
                    {
                        "type": "REDUCER",
                        "shape": "round",
                        "tag": "F-04",
                        "diameter": 315,
                        "outlet_diameter": 250,
                        "position": {"x": 3100, "y": -4000},
                        "angle": 0
                    },
                    {
                        "type": "ELBOW_90",
                        "shape": "round",
                        "tag": "F-05",
                        "diameter": 250,
                        "position": {"x": 5200, "y": -4000},
                        "angle": 0
                    }
                ]
            }
        ]
    }

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(example, f, indent=2)
    print(f"Example layout written to: {out}")
    print("Run with:  python -m duct_automation --layout", out, "--dry-run")
