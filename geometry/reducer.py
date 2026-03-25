"""
Reducer / concentric or eccentric duct fitting.

Supported types:
  1. Rectangular symmetric reducer  – both sides taper equally
  2. Rectangular eccentric reducer  – one face stays flat
  3. Circular concentric reducer    – cone frustum
  4. Circular eccentric reducer     – offset cone

Flat pattern:
  Circular concentric: true radial cone development
  Circular eccentric : approximate triangulation
  Rectangular        : 4 trapezoidal panels
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import List

from .base import DuctGeometry, FlatPattern, DuctType, CrossSection, Polyline2D


@dataclass
class Reducer(DuctGeometry):
    """
    Reducer fitting.

    Parameters
    ----------
    section      : 'Rectangular' or 'Circular'
    inlet_w/h    : Inlet width & height mm
    outlet_w/h   : Outlet width & height mm
    inlet_dia    : Inlet diameter mm  (circular)
    outlet_dia   : Outlet diameter mm (circular)
    length       : Axial length mm
    reducer_type : 'Symmetric' | 'Eccentric'
    """
    section:      str   = CrossSection.RECTANGULAR
    inlet_w:      float = 600.0
    inlet_h:      float = 400.0
    outlet_w:     float = 400.0
    outlet_h:     float = 300.0
    inlet_dia:    float = 400.0
    outlet_dia:   float = 250.0
    length:       float = 400.0
    reducer_type: str   = "Symmetric"

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def duct_type(self) -> str:
        return DuctType.REDUCER

    @property
    def surface_area_sqm(self) -> float:
        if self.section == CrossSection.CIRCULAR:
            return self._circular_area()
        return self._rect_area()

    def _circular_area(self) -> float:
        """Lateral surface area of a frustum (cone)."""
        r1 = self.inlet_dia  / 2
        r2 = self.outlet_dia / 2
        slant = math.sqrt(self.length**2 + (r1 - r2)**2)
        return math.pi * (r1 + r2) * slant / 1_000_000

    def _rect_area(self) -> float:
        iW, iH = self.inlet_w, self.inlet_h
        oW, oH = self.outlet_w, self.outlet_h
        L      = self.length
        slant_TB = math.sqrt(L**2 + ((iH - oH) / 2)**2)
        slant_LR = math.sqrt(L**2 + ((iW - oW) / 2)**2)
        a_top    = (iW + oW) / 2 * slant_TB
        a_left   = (iH + oH) / 2 * slant_LR
        return (2 * a_top + 2 * a_left) / 1_000_000

    @property
    def weight_kg(self) -> float:
        return self._weight_from_area(self.surface_area_sqm)

    # ── Flat patterns ─────────────────────────────────────────────────────────

    def flat_patterns(self) -> List[FlatPattern]:
        if self.section == CrossSection.CIRCULAR:
            if self.reducer_type == "Symmetric":
                return [self._cone_flat()]
            return self._eccentric_cone_flat()
        return self._rect_reducer_flat()

    # ── Concentric circular cone development ──────────────────────────────────

    def _cone_flat(self) -> FlatPattern:
        """
        True radial development of a cone frustum.

        Apex of the full cone is at distance h_apex from the large end.
        Development: an annular sector with inner radius r_apex + slant_outlet
        and outer radius r_apex + slant_inlet.
        """
        r1    = self.inlet_dia  / 2
        r2    = self.outlet_dia / 2
        L     = self.length
        slant = math.sqrt(L**2 + (r1 - r2)**2)   # slant height of frustum

        # Full cone apex to large end
        if abs(r1 - r2) < 1e-6:
            # Parallel – cylinder
            circ = math.pi * r1
            pts: Polyline2D = [(0,0),(circ,0),(circ,L),(0,L),(0,0)]
            return FlatPattern(pts, [], (circ, L), (circ * L) / 1_000_000,
                               label=f"Ø{self.inlet_dia:.0f}→Ø{self.outlet_dia:.0f} Reducer")

        L_apex = r1 * slant / (r1 - r2)           # slant height, apex to big end
        L_apex_small = L_apex - slant              # slant height, apex to small end

        # Development: annular sector
        # Radius in flat: R_big = L_apex, R_small = L_apex_small
        # Arc angle: θ = 2π·r1 / L_apex
        theta = 2 * math.pi * r1 / L_apex          # radians
        N     = 120

        outer_pts: Polyline2D = []
        inner_pts: Polyline2D = []
        for i in range(N + 1):
            a = theta * i / N
            outer_pts.append((L_apex       * math.cos(a), L_apex       * math.sin(a)))
            inner_pts.append((L_apex_small * math.cos(a), L_apex_small * math.sin(a)))

        outline = outer_pts + list(reversed(inner_pts)) + [outer_pts[0]]
        area = math.pi * (r1 + r2) * slant / 1_000_000

        bx = L_apex
        return FlatPattern(
            outline=outline, fold_lines=[],
            dimensions=(bx * 2, bx * 2),
            area_sqm=area,
            label=f"Ø{self.inlet_dia:.0f}→Ø{self.outlet_dia:.0f} Concentric Reducer",
        )

    def _eccentric_cone_flat(self) -> List[FlatPattern]:
        """
        Eccentric cone triangulated into N strips, each laid flat.
        """
        r1, r2 = self.inlet_dia / 2, self.outlet_dia / 2
        L      = self.length
        N      = 12   # strips

        patterns = []
        for i in range(N):
            a1 = 2 * math.pi * i / N
            a2 = 2 * math.pi * (i + 1) / N
            # Points on big and small circles (eccentric: big centre at 0, small offset)
            offset = abs(r1 - r2)
            P1 = (r1 * math.cos(a1),           0,             r1 * math.sin(a1))
            P2 = (r1 * math.cos(a2),           0,             r1 * math.sin(a2))
            P3 = (offset + r2 * math.cos(a2),  L, r2 * math.sin(a2))
            P4 = (offset + r2 * math.cos(a1),  L, r2 * math.sin(a1))

            def dist3(a, b):
                return math.sqrt(sum((a[k]-b[k])**2 for k in range(3)))

            s14 = dist3(P1, P4)
            s23 = dist3(P2, P3)
            w   = dist3(P1, P2)
            h   = (s14 + s23) / 2
            pts: Polyline2D = [(0,0),(w,0),(w,h),(0,h),(0,0)]
            area = (w * h) / 1_000_000
            patterns.append(FlatPattern(pts, [], (w, h), area,
                                        label=f"Eccentric Strip {i+1}/{N}"))
        return patterns

    # ── Rectangular reducer flat patterns ─────────────────────────────────────

    def _rect_reducer_flat(self) -> List[FlatPattern]:
        iW, iH = self.inlet_w, self.inlet_h
        oW, oH = self.outlet_w, self.outlet_h
        L      = self.length

        if self.reducer_type == "Eccentric":
            # One flat face (bottom stays flat) – eccentric
            slant_top = math.sqrt(L**2 + (iH - oH)**2)
            slant_lr  = math.sqrt(L**2 + ((iW - oW) / 2)**2)
        else:
            slant_top = math.sqrt(L**2 + ((iH - oH) / 2)**2)
            slant_lr  = math.sqrt(L**2 + ((iW - oW) / 2)**2)

        def trap(long_b, short_b, h, label):
            off = (long_b - short_b) / 2
            pts: Polyline2D = [(0,0),(long_b,0),(long_b-off,h),(off,h),(0,0)]
            area = (long_b + short_b) / 2 * h / 1_000_000
            return FlatPattern(pts, [], (long_b, h), area, label)

        return [
            trap(iW, oW, slant_top, "Top Panel"),
            trap(iW, oW, slant_top, "Bottom Panel"),
            trap(iH, oH, slant_lr,  "Left Panel"),
            trap(iH, oH, slant_lr,  "Right Panel"),
        ]

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "type": "Reducer",
            "section": self.section,
            "inlet_w": self.inlet_w, "inlet_h": self.inlet_h,
            "outlet_w": self.outlet_w, "outlet_h": self.outlet_h,
            "inlet_dia": self.inlet_dia, "outlet_dia": self.outlet_dia,
            "length": self.length,
            "reducer_type": self.reducer_type,
            "material": self.material,
            "thickness": self.thickness,
            "tag": self.tag,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Reducer":
        return cls(
            section=d.get("section", CrossSection.RECTANGULAR),
            inlet_w=float(d.get("inlet_w", 600)),
            inlet_h=float(d.get("inlet_h", 400)),
            outlet_w=float(d.get("outlet_w", 400)),
            outlet_h=float(d.get("outlet_h", 300)),
            inlet_dia=float(d.get("inlet_dia", 400)),
            outlet_dia=float(d.get("outlet_dia", 250)),
            length=float(d.get("length", 400)),
            reducer_type=d.get("reducer_type", "Symmetric"),
            material=d.get("material", "Galvanised Steel"),
            thickness=float(d.get("thickness", 0.8)),
            tag=d.get("tag", ""),
        )
