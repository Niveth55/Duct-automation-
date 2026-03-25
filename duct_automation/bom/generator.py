"""
Parts & Pieces Bill of Materials (PP-BOM) generator.

Produces a structured BOM from a DuctSystem, including:
  - Duct sections (by type, size, material)
  - Fittings (by type, size, quantity)
  - Material summary (total sheet metal area per gauge/material)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from collections import defaultdict

from ..duct.models import (
    DuctSystem, RectangularDuct, RoundDuct, OvalDuct,
    Fitting, FittingType, Material, DuctShape,
)


@dataclass
class BOMLineItem:
    item_no: int
    tag: str
    description: str
    size: str               # e.g. "600x300", "Ø250"
    material: str
    gauge_mm: float
    quantity: float         # lengths in mm, fittings as count
    unit: str               # "mm" or "EA"
    area_sqm: float = 0.0   # sheet metal surface area
    notes: str = ""

    def as_dict(self) -> dict:
        return {
            "Item No": self.item_no,
            "Tag":     self.tag,
            "Description": self.description,
            "Size":    self.size,
            "Material": self.material,
            "Gauge (mm)": self.gauge_mm,
            "Quantity": self.quantity,
            "Unit":    self.unit,
            "Area (m²)": round(self.area_sqm, 3),
            "Notes":   self.notes,
        }


@dataclass
class MaterialSummary:
    material: str
    gauge_mm: float
    total_area_sqm: float

    def as_dict(self) -> dict:
        return {
            "Material":   self.material,
            "Gauge (mm)": self.gauge_mm,
            "Total Area (m²)": round(self.total_area_sqm, 3),
        }


@dataclass
class BOM:
    project_name: str
    project_number: str
    drawn_by: str
    date: str
    line_items: List[BOMLineItem] = field(default_factory=list)
    material_summary: List[MaterialSummary] = field(default_factory=list)

    def total_area_sqm(self) -> float:
        return sum(item.area_sqm for item in self.line_items)


def _size_label_rect(w: float, h: float) -> str:
    return f"{int(w)}x{int(h)}mm"


def _size_label_round(d: float) -> str:
    return f"Ø{int(d)}mm"


def _size_label_oval(major: float, minor: float) -> str:
    return f"{int(major)}x{int(minor)}mm (oval)"


def _fitting_size(fitting: Fitting) -> str:
    if fitting.shape == DuctShape.RECTANGULAR:
        size = _size_label_rect(fitting.width, fitting.height)
        if fitting.outlet_width:
            size += f" → {_size_label_rect(fitting.outlet_width, fitting.outlet_height)}"
    elif fitting.shape == DuctShape.ROUND:
        size = _size_label_round(fitting.diameter)
        if fitting.outlet_diameter:
            size += f" → {_size_label_round(fitting.outlet_diameter)}"
    else:
        size = f"{int(fitting.major)}x{int(fitting.minor)}mm"
    return size


def generate_bom(system: DuctSystem) -> BOM:
    """Generate a complete PP-BOM from a DuctSystem."""
    bom = BOM(
        project_name=system.project_name,
        project_number=system.project_number,
        drawn_by=system.drawn_by,
        date=system.date,
    )

    item_no = 1

    # ----------------------------------------------------------------
    # Duct sections – consolidate identical size+material+gauge
    # ----------------------------------------------------------------
    # Key: (description_key, size, material_name, gauge)
    duct_aggregator: Dict[tuple, dict] = defaultdict(lambda: {
        "total_length": 0.0,
        "total_area": 0.0,
        "tags": [],
    })

    for section in system.all_sections():
        mat_name = section.material.value
        gauge = section.gauge

        if isinstance(section, RectangularDuct):
            key = ("Rectangular Duct", _size_label_rect(section.width, section.height), mat_name, gauge)
        elif isinstance(section, RoundDuct):
            key = ("Round Duct", _size_label_round(section.diameter), mat_name, gauge)
        elif isinstance(section, OvalDuct):
            key = ("Oval Duct", _size_label_oval(section.major, section.minor), mat_name, gauge)
        else:
            continue

        duct_aggregator[key]["total_length"] += section.length
        duct_aggregator[key]["total_area"] += section.area_sqm
        if section.tag:
            duct_aggregator[key]["tags"].append(section.tag)

    for (desc, size, mat, gauge), data in sorted(duct_aggregator.items()):
        tags = ", ".join(sorted(set(data["tags"])))
        bom.line_items.append(BOMLineItem(
            item_no=item_no,
            tag=tags,
            description=desc,
            size=size,
            material=mat,
            gauge_mm=gauge,
            quantity=round(data["total_length"], 0),
            unit="mm",
            area_sqm=round(data["total_area"], 3),
        ))
        item_no += 1

    # ----------------------------------------------------------------
    # Fittings – consolidate by type + shape + size
    # ----------------------------------------------------------------
    fitting_aggregator: Dict[tuple, dict] = defaultdict(lambda: {
        "count": 0,
        "tags": [],
    })

    for fitting in system.all_fittings():
        mat_name = fitting.material.value
        size = _fitting_size(fitting)
        key = (fitting.fitting_type.value, fitting.shape.value, size, mat_name)
        fitting_aggregator[key]["count"] += fitting.quantity
        if fitting.tag:
            fitting_aggregator[key]["tags"].append(fitting.tag)

    for (ftype, shape, size, mat), data in sorted(fitting_aggregator.items()):
        tags = ", ".join(sorted(set(data["tags"])))
        bom.line_items.append(BOMLineItem(
            item_no=item_no,
            tag=tags,
            description=f"{ftype} ({shape})",
            size=size,
            material=mat,
            gauge_mm=0.0,
            quantity=data["count"],
            unit="EA",
            area_sqm=0.0,
        ))
        item_no += 1

    # ----------------------------------------------------------------
    # Material summary – group by material + gauge
    # ----------------------------------------------------------------
    mat_totals: Dict[tuple, float] = defaultdict(float)
    for item in bom.line_items:
        if item.unit == "mm" and item.area_sqm > 0:
            mat_totals[(item.material, item.gauge_mm)] += item.area_sqm

    for (mat, gauge), total in sorted(mat_totals.items()):
        bom.material_summary.append(MaterialSummary(
            material=mat,
            gauge_mm=gauge,
            total_area_sqm=round(total, 3),
        ))

    return bom


def bom_to_text(bom: BOM) -> str:
    """Render BOM as a plain-text table for console output."""
    lines = []
    lines.append("=" * 100)
    lines.append(f"  PARTS & PIECES BILL OF MATERIALS")
    lines.append(f"  Project: {bom.project_name}   No: {bom.project_number}")
    lines.append(f"  Drawn by: {bom.drawn_by}   Date: {bom.date}")
    lines.append("=" * 100)

    header = (f"{'Item':>4}  {'Tag':<12} {'Description':<30} {'Size':<22} "
              f"{'Material':<22} {'Gauge':>6} {'Qty':>10} {'Unit':<5} {'Area(m²)':>9}")
    lines.append(header)
    lines.append("-" * 100)

    for item in bom.line_items:
        row = (f"{item.item_no:>4}  {item.tag:<12} {item.description:<30} {item.size:<22} "
               f"{item.material:<22} {item.gauge_mm:>6.1f} {item.quantity:>10.0f} "
               f"{item.unit:<5} {item.area_sqm:>9.3f}")
        lines.append(row)

    lines.append("=" * 100)
    lines.append(f"  MATERIAL SUMMARY")
    lines.append("-" * 60)
    lines.append(f"  {'Material':<25} {'Gauge(mm)':>10} {'Total Area(m²)':>16}")
    lines.append("-" * 60)
    for ms in bom.material_summary:
        lines.append(f"  {ms.material:<25} {ms.gauge_mm:>10.1f} {ms.total_area_sqm:>16.3f}")
    lines.append(f"  {'GRAND TOTAL':.<40} {bom.total_area_sqm():>16.3f} m²")
    lines.append("=" * 100)

    return "\n".join(lines)
