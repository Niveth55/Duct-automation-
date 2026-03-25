"""
Advanced BOM (Bill of Materials) calculator.

Calculates:
  - Sheet metal area (m²) per component
  - Weight (kg)
  - Flanges / joints
  - Gaskets
  - Fasteners (bolts, nuts, washers)
  - Insulation (optional)
  - Cost estimation (optional)

Output: structured BOM with line items ready for Excel/CSV export.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from collections import defaultdict

from geometry.base import DuctGeometry, DuctType, MATERIAL_DENSITY
from geometry.straight import StraightDuct
from geometry.elbow import Elbow
from geometry.transition import Transition
from geometry.tee import Tee
from geometry.reducer import Reducer
from standards.smacna import (
    JointType, joint_recommendation, JOINT_ALLOWANCE,
    seam_recommendation, recommended_gauge_rect, recommended_gauge_round,
)


# ── Material cost table (USD per kg) ─────────────────────────────────────────
MATERIAL_COST_PER_KG: Dict[str, float] = {
    "Galvanised Steel": 2.50,
    "Stainless Steel 304": 5.80,
    "Stainless Steel 316": 7.20,
    "Aluminium": 4.00,
    "Mild Steel": 1.80,
}

# ── Flange specifications ─────────────────────────────────────────────────────
FLANGE_WEIGHT_PER_M: Dict[str, float] = {   # kg per metre of duct perimeter
    JointType.SLIP_AND_DRIVE: 0.80,
    JointType.TDC:            1.20,
    JointType.ANGLE_IRON:     2.50,
    JointType.BEADED:         0.60,
}

# ── Gasket specifications ─────────────────────────────────────────────────────
GASKET_COST_PER_M = 0.80   # USD per metre of flange perimeter

# ── Fastener specifications ───────────────────────────────────────────────────
BOLT_SPACING_MM = 150       # mm between bolts on flanges
BOLT_COST       = 0.15      # USD per bolt assembly (bolt+nut+washer×2)
BOLT_WEIGHT     = 0.08      # kg per bolt assembly (M8)

# ── Insulation (optional) ─────────────────────────────────────────────────────
INSULATION_THICKNESS_MM  = 50
INSULATION_COST_PER_SQM  = 8.50   # USD per m²
INSULATION_WEIGHT_KG_SQM = 1.20   # kg per m²


@dataclass
class BOMLineItem:
    seq: int
    tag: str
    description: str
    specification: str
    quantity: float
    unit: str
    unit_weight_kg: float = 0.0
    total_weight_kg: float = 0.0
    unit_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    notes: str = ""

    def as_dict(self) -> dict:
        return {
            "Seq":           self.seq,
            "Tag":           self.tag,
            "Description":   self.description,
            "Specification": self.specification,
            "Qty":           round(self.quantity, 3),
            "Unit":          self.unit,
            "Unit Wt (kg)":  round(self.unit_weight_kg, 3),
            "Total Wt (kg)": round(self.total_weight_kg, 3),
            "Unit Cost ($)": round(self.unit_cost_usd, 2),
            "Total Cost ($)": round(self.total_cost_usd, 2),
            "Notes":         self.notes,
        }


@dataclass
class FullBOM:
    project_name: str = ""
    project_no:   str = ""
    drawn_by:     str = ""
    date:         str = ""
    items: List[BOMLineItem] = field(default_factory=list)

    @property
    def total_weight_kg(self) -> float:
        return sum(i.total_weight_kg for i in self.items)

    @property
    def total_cost_usd(self) -> float:
        return sum(i.total_cost_usd for i in self.items)

    def summary_by_category(self) -> Dict[str, float]:
        cats: Dict[str, float] = defaultdict(float)
        for item in self.items:
            cats[item.description] += item.total_cost_usd
        return dict(cats)


def calculate_bom(components: List[DuctGeometry],
                  project_name: str = "",
                  project_no: str = "",
                  drawn_by: str = "",
                  date: str = "",
                  include_insulation: bool = False,
                  include_cost: bool = True,
                  ) -> FullBOM:
    """
    Generate a complete BOM for a list of duct components.
    """
    bom = FullBOM(project_name=project_name, project_no=project_no,
                  drawn_by=drawn_by, date=date)
    seq = 1

    # ── Per-component items ───────────────────────────────────────────────────
    for comp in components:
        tag = comp.tag or f"C-{seq:03d}"

        # 1. Sheet metal body
        area   = comp.surface_area_sqm
        weight = comp.weight_kg
        mat    = comp.material
        cost_rate = MATERIAL_COST_PER_KG.get(mat, 2.50)
        # Cost per m² = (density × thickness_m × cost_per_kg)
        cost_per_sqm = (MATERIAL_DENSITY.get(mat, 7850) *
                        (comp.thickness / 1000) * cost_rate)
        sheet_cost = area * cost_per_sqm

        bom.items.append(BOMLineItem(
            seq=seq, tag=tag,
            description=f"Sheet Metal – {comp.duct_type}",
            specification=_spec_string(comp),
            quantity=round(area, 4),
            unit="m²",
            unit_weight_kg=round(weight / area if area else 0, 3),
            total_weight_kg=round(weight, 3),
            unit_cost_usd=round(cost_per_sqm, 2),
            total_cost_usd=round(sheet_cost, 2),
            notes=f"{mat}  {comp.thickness:.2f}mm",
        ))
        seq += 1

        # 2. Flanges / joints at each end of component
        n_flanges, flange_perim, jtype = _flange_info(comp)
        if n_flanges > 0:
            fw = FLANGE_WEIGHT_PER_M.get(jtype, 1.2) * flange_perim / 1000  # per flange
            fc = fw * cost_rate

            bom.items.append(BOMLineItem(
                seq=seq, tag=tag,
                description="Flange / Joint",
                specification=f"{jtype}",
                quantity=n_flanges,
                unit="EA",
                unit_weight_kg=round(fw, 3),
                total_weight_kg=round(fw * n_flanges, 3),
                unit_cost_usd=round(fc, 2),
                total_cost_usd=round(fc * n_flanges, 2),
                notes=f"Perim={flange_perim:.0f}mm",
            ))
            seq += 1

            # 3. Gaskets
            g_len  = flange_perim / 1000 * n_flanges   # m
            g_cost = g_len * GASKET_COST_PER_M
            bom.items.append(BOMLineItem(
                seq=seq, tag=tag,
                description="Gasket",
                specification="Foam/Rubber Sealing Strip",
                quantity=round(g_len, 3),
                unit="m",
                unit_weight_kg=0.05,
                total_weight_kg=round(g_len * 0.05, 3),
                unit_cost_usd=round(GASKET_COST_PER_M, 2),
                total_cost_usd=round(g_cost, 2),
            ))
            seq += 1

            # 4. Fasteners
            n_bolts = max(4, int(flange_perim / BOLT_SPACING_MM)) * n_flanges
            bom.items.append(BOMLineItem(
                seq=seq, tag=tag,
                description="Fastener Set",
                specification="M8 Bolt + Nut + 2× Washer",
                quantity=n_bolts,
                unit="SET",
                unit_weight_kg=BOLT_WEIGHT,
                total_weight_kg=round(n_bolts * BOLT_WEIGHT, 3),
                unit_cost_usd=BOLT_COST,
                total_cost_usd=round(n_bolts * BOLT_COST, 2),
            ))
            seq += 1

        # 5. Insulation (optional)
        if include_insulation:
            ins_cost = area * INSULATION_COST_PER_SQM
            ins_wt   = area * INSULATION_WEIGHT_KG_SQM
            bom.items.append(BOMLineItem(
                seq=seq, tag=tag,
                description="Insulation",
                specification=f"Rockwool/Glass-wool {INSULATION_THICKNESS_MM}mm",
                quantity=round(area, 4),
                unit="m²",
                unit_weight_kg=INSULATION_WEIGHT_KG_SQM,
                total_weight_kg=round(ins_wt, 3),
                unit_cost_usd=INSULATION_COST_PER_SQM,
                total_cost_usd=round(ins_cost, 2),
            ))
            seq += 1

    return bom


# ── Helpers ───────────────────────────────────────────────────────────────────

def _spec_string(comp: DuctGeometry) -> str:
    if isinstance(comp, StraightDuct):
        if comp.section == "Circular":
            return f"Ø{comp.diameter:.0f}×{comp.length:.0f}mm"
        return f"{comp.width:.0f}×{comp.height:.0f}×{comp.length:.0f}mm"
    if isinstance(comp, Elbow):
        return (f"{comp.section}  {comp.angle:.0f}°  "
                f"{'Ø' if comp.section=='Circular' else ''}"
                f"{comp.width:.0f}  R={comp.radius_cl:.0f}mm")
    if isinstance(comp, Transition):
        return (f"{comp.transition_type}  "
                f"{comp.inlet_w:.0f}×{comp.inlet_h:.0f}→"
                f"{comp.outlet_w:.0f}×{comp.outlet_h:.0f}  L={comp.length:.0f}")
    if isinstance(comp, Tee):
        return (f"Main {comp.main_w:.0f}×{comp.main_h:.0f}  "
                f"Branch {comp.branch_w:.0f}×{comp.branch_h:.0f}")
    if isinstance(comp, Reducer):
        return (f"{comp.reducer_type}  "
                f"{comp.inlet_w:.0f}×{comp.inlet_h:.0f}→"
                f"{comp.outlet_w:.0f}×{comp.outlet_h:.0f}  L={comp.length:.0f}")
    return str(comp)


def _flange_info(comp: DuctGeometry):
    """
    Return (n_flanges, perimeter_mm, joint_type) for a component.
    Most components have 2 end flanges.
    Tee has 3, Cross has 4.
    """
    if isinstance(comp, StraightDuct):
        if comp.section == "Circular":
            perim = math.pi * comp.diameter
        else:
            perim = 2 * (comp.width + comp.height)
        jtype = joint_recommendation(comp.width if comp.section != "Circular" else comp.diameter)
        return 2, perim, jtype

    if isinstance(comp, Elbow):
        if comp.section == "Circular":
            perim = math.pi * comp.width
        else:
            perim = 2 * (comp.width + comp.height)
        jtype = joint_recommendation(comp.width)
        return 2, perim, jtype

    if isinstance(comp, (Transition, Reducer)):
        iW = getattr(comp, "inlet_w", 0) or getattr(comp, "inlet_dia", 0)
        iH = getattr(comp, "inlet_h", 0)
        if iH:
            in_perim  = 2 * (iW + iH)
        else:
            in_perim  = math.pi * iW
        oW = getattr(comp, "outlet_w", 0) or getattr(comp, "outlet_dia", 0)
        oH = getattr(comp, "outlet_h", 0)
        if oH:
            out_perim = 2 * (oW + oH)
        else:
            out_perim = math.pi * oW
        avg_perim = (in_perim + out_perim) / 2
        jtype = joint_recommendation(iW)
        return 2, avg_perim, jtype

    if isinstance(comp, Tee):
        perim = 2 * (comp.main_w + comp.main_h)
        jtype = joint_recommendation(comp.main_w)
        return 3, perim, jtype

    return 2, 1000, JointType.TDC
