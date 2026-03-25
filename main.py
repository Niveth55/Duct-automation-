#!/usr/bin/env python3
"""
Duct Automation System – Entry Point
=====================================
Parametric HVAC duct designer with:
  • SMACNA-compliant geometry (Straight, Elbow, Transition, Tee, Reducer)
  • Flat pattern development for sheet metal fabrication
  • Multi-view DXF drawing generation (plan, elevation, section, flat pattern)
  • Parts & Pieces BOM with weight, fasteners, and cost estimation
  • Interactive Tkinter GUI with real-time 2D preview
  • CLI for batch/headless operation

Usage:
  python main.py                     # Launch GUI
  python main.py --cli --help        # CLI help
  python main.py --cli --type straight --width 600 --height 300 --length 3000
"""

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── CLI ───────────────────────────────────────────────────────────────────────

def _cli(args):
    """Headless CLI mode – generate DXF and BOM without GUI."""
    from geometry.straight   import StraightDuct
    from geometry.elbow      import Elbow
    from geometry.transition import Transition
    from geometry.tee        import Tee
    from geometry.reducer    import Reducer
    from geometry.base       import CrossSection, Material
    from standards.smacna    import recommended_gauge_rect, recommended_gauge_round
    from bom.calculator      import calculate_bom
    from bom.exporter        import export_excel, export_csv
    from drawing.dxf_writer  import generate_dxf

    t = args.type.lower()

    # Auto-select gauge if not specified
    thickness = args.thickness
    if thickness <= 0:
        if t == "straight" and args.section == "Circular":
            _, thickness = recommended_gauge_round(args.diameter)
        else:
            _, thickness = recommended_gauge_rect(args.width)
        logger.info("Auto gauge selected: %.2f mm", thickness)

    # Build component
    if t == "straight":
        comp = StraightDuct(
            section=args.section,
            width=args.width, height=args.height,
            diameter=args.diameter, length=args.length,
            material=args.material, thickness=thickness,
            tag=args.tag,
        )
    elif t == "elbow":
        comp = Elbow(
            section=args.section,
            width=args.width, height=args.height,
            angle=args.angle, elbow_type=args.elbow_type,
            radius_cl=args.radius_cl, n_pieces=args.n_pieces,
            material=args.material, thickness=thickness,
            tag=args.tag,
        )
    elif t == "transition":
        comp = Transition(
            transition_type=args.transition_type,
            inlet_w=args.inlet_w, inlet_h=args.inlet_h,
            outlet_w=args.outlet_w, outlet_h=args.outlet_h,
            outlet_dia=args.outlet_dia, length=args.length,
            material=args.material, thickness=thickness,
            tag=args.tag,
        )
    elif t == "tee":
        comp = Tee(
            section=args.section,
            main_w=args.main_w, main_h=args.main_h,
            branch_w=args.branch_w, branch_h=args.branch_h,
            main_dia=args.diameter, branch_dia=args.branch_dia,
            neck_length=args.neck_length,
            material=args.material, thickness=thickness,
            tag=args.tag,
        )
    elif t == "reducer":
        comp = Reducer(
            section=args.section,
            reducer_type=args.reducer_type,
            inlet_w=args.inlet_w, inlet_h=args.inlet_h,
            outlet_w=args.outlet_w, outlet_h=args.outlet_h,
            inlet_dia=args.diameter, outlet_dia=args.outlet_dia,
            length=args.length,
            material=args.material, thickness=thickness,
            tag=args.tag,
        )
    else:
        logger.error("Unknown type: %s", t)
        sys.exit(1)

    # Print summary
    print(f"\n{'='*60}")
    print(f"  {comp.duct_type}  |  {comp.material}  |  {comp.thickness:.2f} mm")
    print(f"  Surface Area : {comp.surface_area_sqm:.4f} m²")
    print(f"  Weight       : {comp.weight_kg:.3f} kg")
    fps = comp.flat_patterns()
    print(f"  Flat Patterns: {len(fps)} sheet(s)")
    for fp in fps:
        print(f"    • {fp.label}  [{fp.dimensions[0]:.0f}×{fp.dimensions[1]:.0f} mm]  {fp.area_sqm:.4f} m²")

    # SMACNA validation
    from standards.smacna import validate_duct
    errors = validate_duct(comp.duct_type, width=args.width,
                            thickness=thickness, diameter=args.diameter)
    if errors:
        print("\nSMACNA Warnings:")
        for e in errors:
            print(f"  {e}")
    else:
        print("\n✓ SMACNA checks: all passed")
    print(f"{'='*60}\n")

    # Output dir
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    tag = comp.tag or t

    # DXF
    if not args.no_dxf:
        dxf_path = out_dir / f"{tag}_drawing.dxf"
        ok = generate_dxf(comp, str(dxf_path),
                          title=f"{comp.duct_type} – {tag}",
                          drawn_by=args.engineer)
        if ok:
            print(f"DXF: {dxf_path}")
        else:
            print("DXF skipped (install ezdxf: pip install ezdxf)")

    # BOM
    if not args.no_bom:
        bom = calculate_bom(
            [comp],
            project_name=args.project_name,
            drawn_by=args.engineer,
            include_insulation=args.insulation,
        )

        if "xlsx" in args.bom_format:
            xl_path = out_dir / f"{tag}_bom.xlsx"
            export_excel(bom, xl_path)
            print(f"BOM Excel: {xl_path}")

        if "csv" in args.bom_format:
            csv_path = out_dir / f"{tag}_bom.csv"
            export_csv(bom, csv_path)
            print(f"BOM CSV: {csv_path}")

        print(f"Total Weight: {bom.total_weight_kg:.3f} kg")
        print(f"Total Cost:   ${bom.total_cost_usd:.2f}")


def _build_cli_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="duct_automation",
        description="Duct Automation CLI – generate DXF drawings and BOM",
    )
    p.add_argument("--cli", action="store_true", help="Run in CLI (no GUI)")

    # Component type
    p.add_argument("--type", default="straight",
                   choices=["straight", "elbow", "transition", "tee", "reducer"])
    p.add_argument("--section", default="Rectangular",
                   choices=["Rectangular", "Circular"])
    p.add_argument("--tag", default="", help="Component tag/ID")

    # Dimensions
    p.add_argument("--width",      type=float, default=400)
    p.add_argument("--height",     type=float, default=200)
    p.add_argument("--diameter",   type=float, default=315)
    p.add_argument("--length",     type=float, default=1000)
    p.add_argument("--angle",      type=float, default=90,  help="Elbow angle degrees")
    p.add_argument("--radius-cl",  type=float, default=0,   dest="radius_cl")
    p.add_argument("--n-pieces",   type=int,   default=3,   dest="n_pieces")
    p.add_argument("--elbow-type", default="Radius",
                   choices=["Radius", "Mitered"], dest="elbow_type")
    p.add_argument("--transition-type", default="Rect-Rect",
                   choices=["Rect-Rect", "Rect-Circle"], dest="transition_type")
    p.add_argument("--reducer-type", default="Symmetric",
                   choices=["Symmetric", "Eccentric"], dest="reducer_type")
    p.add_argument("--inlet-w",   type=float, default=600, dest="inlet_w")
    p.add_argument("--inlet-h",   type=float, default=400, dest="inlet_h")
    p.add_argument("--outlet-w",  type=float, default=400, dest="outlet_w")
    p.add_argument("--outlet-h",  type=float, default=300, dest="outlet_h")
    p.add_argument("--outlet-dia",type=float, default=315, dest="outlet_dia")
    p.add_argument("--main-w",    type=float, default=600, dest="main_w")
    p.add_argument("--main-h",    type=float, default=300, dest="main_h")
    p.add_argument("--branch-w",  type=float, default=300, dest="branch_w")
    p.add_argument("--branch-h",  type=float, default=250, dest="branch_h")
    p.add_argument("--branch-dia",type=float, default=250, dest="branch_dia")
    p.add_argument("--neck-length",type=float, default=150, dest="neck_length")

    # Material
    p.add_argument("--material", default="Galvanised Steel",
                   choices=["Galvanised Steel", "Stainless Steel 304",
                            "Stainless Steel 316", "Aluminium", "Mild Steel"])
    p.add_argument("--thickness", type=float, default=0,
                   help="Sheet thickness mm (0 = auto SMACNA)")

    # Output
    p.add_argument("--output", "-o", default="./output", help="Output directory")
    p.add_argument("--project-name", default="HVAC Project", dest="project_name")
    p.add_argument("--engineer", default="")
    p.add_argument("--bom-format", default="xlsx,csv", dest="bom_format")
    p.add_argument("--no-dxf",  action="store_true", dest="no_dxf")
    p.add_argument("--no-bom",  action="store_true", dest="no_bom")
    p.add_argument("--insulation", action="store_true")
    p.add_argument("--verbose", "-v", action="store_true")

    return p


# ── GUI ───────────────────────────────────────────────────────────────────────

def _launch_gui():
    try:
        from gui.main_window import DuctAutomationApp
        app = DuctAutomationApp()
        app.mainloop()
    except ImportError as exc:
        logger.error("GUI dependencies missing: %s", exc)
        print("\nRequired: pip install matplotlib\n")
        sys.exit(1)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = _build_cli_parser()
    args   = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.cli:
        _cli(args)
    else:
        _launch_gui()


if __name__ == "__main__":
    main()
