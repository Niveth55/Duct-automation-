"""
Straight duct geometry – rectangular and circular cross-sections.

Flat pattern:
  Rectangular: 4 panels unrolled flat (single-piece longitudinal seam)
  Circular:    single rolled sheet (seam along length)
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import List

from .base import DuctGeometry, FlatPattern, DuctType, CrossSection, Polyline2D


@dataclass
class StraightDuct(DuctGeometry):
    """
    Straight duct section.

    Rectangular: width × height × length (all mm)
    Circular:    diameter × length (mm)
    """
    section: str   = CrossSection.RECTANGULAR
    width: float   = 400.0    # mm  (rectangular W, or diameter for circular)
    height: float  = 200.0    # mm  (rectangular H)
    diameter: float = 315.0   # mm  (circular only)
    length: float  = 1000.0   # mm

    # ── DuctGeometry interface ────────────────────────────────────────────────

    @property
    def duct_type(self) -> str:
        return DuctType.STRAIGHT

    @property
    def perimeter_mm(self) -> float:
        if self.section == CrossSection.CIRCULAR:
            return math.pi * self.diameter
        return 2 * (self.width + self.height)

    @property
    def surface_area_sqm(self) -> float:
        return (self.perimeter_mm * self.length) / 1_000_000

    @property
    def cross_section_area_sqmm(self) -> float:
        if self.section == CrossSection.CIRCULAR:
            return math.pi * (self.diameter / 2) ** 2
        return self.width * self.height

    @property
    def weight_kg(self) -> float:
        return self._weight_from_area(self.surface_area_sqm)

    # ── Flat patterns ─────────────────────────────────────────────────────────

    def flat_patterns(self) -> List[FlatPattern]:
        if self.section == CrossSection.CIRCULAR:
            return [self._circular_flat()]
        return [self._rectangular_flat()]

    def _circular_flat(self) -> FlatPattern:
        """Single rectangular sheet that wraps into a cylinder."""
        W = math.pi * self.diameter   # developed circumference
        H = self.length
        outline: Polyline2D = [(0, 0), (W, 0), (W, H), (0, H), (0, 0)]
        area = (W * H) / 1_000_000
        return FlatPattern(
            outline=outline,
            fold_lines=[],
            dimensions=(W, H),
            area_sqm=area,
            label=f"Ø{self.diameter:.0f}×{self.length:.0f}mm Cylinder",
        )

    def _rectangular_flat(self) -> FlatPattern:
        """
        Four panels laid out in a cross / strip for a rectangular duct.
        Panels (bottom, front, top, back) joined along the 4 seam lines.
        Layout: all panels in a horizontal strip left to right.
        """
        panels = [
            ("Bottom", self.width,  self.length),
            ("Front",  self.height, self.length),
            ("Top",    self.width,  self.length),
            ("Back",   self.height, self.length),
        ]
        total_girth = sum(p[1] for p in panels)

        outline: Polyline2D = [(0, 0), (total_girth, 0),
                                (total_girth, self.length), (0, self.length), (0, 0)]

        fold_lines: List[Polyline2D] = []
        x = 0.0
        for _, pw, _ in panels[:-1]:
            x += pw
            fold_lines.append([(x, 0), (x, self.length)])

        area = (total_girth * self.length) / 1_000_000
        return FlatPattern(
            outline=outline,
            fold_lines=fold_lines,
            dimensions=(total_girth, self.length),
            area_sqm=area,
            label=f"{self.width:.0f}×{self.height:.0f}×{self.length:.0f}mm Rect Duct",
        )

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "type": "StraightDuct",
            "section": self.section,
            "width": self.width,
            "height": self.height,
            "diameter": self.diameter,
            "length": self.length,
            "material": self.material,
            "thickness": self.thickness,
            "tag": self.tag,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "StraightDuct":
        return cls(
            section=d.get("section", CrossSection.RECTANGULAR),
            width=float(d.get("width", 400)),
            height=float(d.get("height", 200)),
            diameter=float(d.get("diameter", 315)),
            length=float(d.get("length", 1000)),
            material=d.get("material", "Galvanised Steel"),
            thickness=float(d.get("thickness", 0.8)),
            tag=d.get("tag", ""),
        )
