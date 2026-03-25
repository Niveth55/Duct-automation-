"""
Transition (transformation) duct geometry.

Supported types:
  1. Rect → Rect   (offset or concentric pyramid frustum)
  2. Rect → Circle (eccentric / concentric)
  3. Circle → Circle (reducer – see reducer.py for symmetric case)

Flat pattern development:
  Rect→Rect:    each face is a trapezoid unrolled flat
  Rect→Circle:  triangulation method (approximate development)
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import List, Tuple

from .base import DuctGeometry, FlatPattern, DuctType, CrossSection, Polyline2D


@dataclass
class Transition(DuctGeometry):
    """
    Transition fitting.

    Parameters
    ----------
    inlet_w, inlet_h   : Inlet width & height mm
    outlet_w, outlet_h : Outlet width & height mm
    outlet_dia         : Outlet diameter mm (for rect→circle)
    length             : Overall length mm (perpendicular distance)
    offset_x           : Horizontal offset of outlet centreline mm
    offset_y           : Vertical offset of outlet centreline mm
    transition_type    : 'Rect-Rect' | 'Rect-Circle'
    """
    inlet_w:   float = 600.0
    inlet_h:   float = 400.0
    outlet_w:  float = 400.0
    outlet_h:  float = 300.0
    outlet_dia: float = 315.0
    length:    float = 500.0
    offset_x:  float = 0.0
    offset_y:  float = 0.0
    transition_type: str = "Rect-Rect"

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def duct_type(self) -> str:
        return DuctType.TRANSITION

    @property
    def surface_area_sqm(self) -> float:
        if self.transition_type == "Rect-Circle":
            return self._rect_circle_area()
        return self._rect_rect_area()

    def _rect_rect_area(self) -> float:
        """Sum of 4 trapezoidal panels."""
        iW, iH = self.inlet_w, self.inlet_h
        oW, oH = self.outlet_w, self.outlet_h
        L      = self.length
        ox, oy = self.offset_x, self.offset_y

        # Four slant lengths (actual 3D distances of each panel centre-line)
        # Simplified: use Pythagoras for each pair of parallel edges
        def panel_area(inlet_side, outlet_side, slant_H) -> float:
            return (inlet_side + outlet_side) / 2 * slant_H

        # Compute slant heights including offset
        slant_top_bot = math.sqrt(L**2 + oy**2)
        slant_left_right = math.sqrt(L**2 + ox**2)

        a_top    = panel_area(iW, oW, slant_top_bot)
        a_bottom = panel_area(iW, oW, slant_top_bot)
        a_left   = panel_area(iH, oH, slant_left_right)
        a_right  = panel_area(iH, oH, slant_left_right)

        return (a_top + a_bottom + a_left + a_right) / 1_000_000

    def _rect_circle_area(self) -> float:
        """
        Rect→Circle: 4 triangulated sectors (approximate).
        Each corner of the rectangle connects to an arc on the circle.
        """
        iW, iH = self.inlet_w, self.inlet_h
        r      = self.outlet_dia / 2
        L      = self.length

        # Corner-to-arc slant (average)
        corner_dist = math.sqrt((iW / 2)**2 + (iH / 2)**2)
        slant = math.sqrt(L**2 + ((corner_dist - r) / 2)**2)

        # Approximate: 4 triangular flaps + 4 curved panels
        tri_area = 4 * 0.5 * (iW / 2) * slant
        # Inlet perimeter rectangle half faces approximation
        circ_face = math.pi * r * slant
        return (tri_area + circ_face) / 1_000_000

    @property
    def weight_kg(self) -> float:
        return self._weight_from_area(self.surface_area_sqm)

    # ── Flat patterns ─────────────────────────────────────────────────────────

    def flat_patterns(self) -> List[FlatPattern]:
        if self.transition_type == "Rect-Circle":
            return self._rect_circle_flat()
        return self._rect_rect_flat()

    # ── Rect → Rect flat patterns ─────────────────────────────────────────────

    def _rect_rect_flat(self) -> List[FlatPattern]:
        """
        4 trapezoidal panels (Top, Bottom, Left, Right).
        Each panel is a trapezoid laid flat.
        The slant height is the true 3-D slant of that face.
        """
        iW, iH = self.inlet_w, self.inlet_h
        oW, oH = self.outlet_w, self.outlet_h
        L      = self.length
        ox, oy = self.offset_x, self.offset_y

        # Slant heights
        slant_TB = math.sqrt(L**2 + oy**2 + ((iH - oH) / 2)**2)
        slant_LR = math.sqrt(L**2 + ox**2 + ((iW - oW) / 2)**2)

        patterns = []

        def trapezoid(long_b: float, short_b: float, h: float, label: str) -> FlatPattern:
            offset = (long_b - short_b) / 2
            pts: Polyline2D = [
                (0, 0), (long_b, 0),
                (long_b - offset, h), (offset, h),
                (0, 0),
            ]
            area = (long_b + short_b) / 2 * h / 1_000_000
            return FlatPattern(outline=pts, fold_lines=[],
                               dimensions=(long_b, h), area_sqm=area, label=label)

        patterns.append(trapezoid(iW, oW, slant_TB, "Top Panel"))
        patterns.append(trapezoid(iW, oW, slant_TB, "Bottom Panel"))
        patterns.append(trapezoid(iH, oH, slant_LR, "Left Panel"))
        patterns.append(trapezoid(iH, oH, slant_LR, "Right Panel"))
        return patterns

    # ── Rect → Circle flat patterns ───────────────────────────────────────────

    def _rect_circle_flat(self) -> List[FlatPattern]:
        """
        Triangulation development of rect→circle transition.
        8 triangular / trapezoidal panels laid flat (4 rectangular faces
        and 4 corner triangles).
        """
        iW, iH = self.inlet_w, self.inlet_h
        r      = self.outlet_dia / 2
        L      = self.length
        N_arc  = 8   # arc subdivisions per quadrant

        patterns = []
        pattern_angle = 90.0   # degrees per quadrant

        def arc_strip_flat(base_width, arc_len, slant, label) -> FlatPattern:
            # Trapezoidal approximation
            pts: Polyline2D = [
                (0, 0), (base_width, 0),
                (base_width, slant), (0, slant),
                (0, 0),
            ]
            area = (base_width * slant) / 1_000_000
            return FlatPattern(outline=pts, fold_lines=[],
                               dimensions=(base_width, slant),
                               area_sqm=area, label=label)

        # Face strips (Top, Bottom, Left, Right)
        for face, base, offset in [
            ("Top",    iW, iH / 2),
            ("Bottom", iW, iH / 2),
            ("Left",   iH, iW / 2),
            ("Right",  iH, iW / 2),
        ]:
            arc_len = math.pi * r / 2   # 90° arc
            slant   = math.sqrt(L**2 + (offset - r)**2)
            patterns.append(arc_strip_flat(base, arc_len, slant, f"{face} Face"))

        # Corner triangles
        for corner in ("TL", "TR", "BL", "BR"):
            cx = iW / 2
            cy = iH / 2
            slant_c = math.sqrt(L**2 + cx**2 + cy**2)
            pts: Polyline2D = [(0, 0), (cx, 0), (0, slant_c), (0, 0)]
            area = (0.5 * cx * slant_c) / 1_000_000
            patterns.append(FlatPattern(
                outline=pts, fold_lines=[],
                dimensions=(cx, slant_c), area_sqm=area,
                label=f"Corner {corner}",
            ))

        return patterns

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "type": "Transition",
            "transition_type": self.transition_type,
            "inlet_w": self.inlet_w, "inlet_h": self.inlet_h,
            "outlet_w": self.outlet_w, "outlet_h": self.outlet_h,
            "outlet_dia": self.outlet_dia,
            "length": self.length,
            "offset_x": self.offset_x, "offset_y": self.offset_y,
            "material": self.material,
            "thickness": self.thickness,
            "tag": self.tag,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Transition":
        return cls(**{k: d[k] for k in (
            "inlet_w", "inlet_h", "outlet_w", "outlet_h",
            "outlet_dia", "length", "offset_x", "offset_y",
        ) if k in d},
            transition_type=d.get("transition_type", "Rect-Rect"),
            material=d.get("material", "Galvanised Steel"),
            thickness=float(d.get("thickness", 0.8)),
            tag=d.get("tag", ""),
        )
