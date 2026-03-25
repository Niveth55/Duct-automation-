"""
Tee / Branch fitting geometry.

Supported types:
  - Straight Tee        : main duct continues, branch exits at 90°
  - Reducing Tee        : branch is smaller than main
  - Wye / Y-branch      : branch exits at an angle (default 45°)

Cross-sections: Rectangular or Circular
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import List

from .base import DuctGeometry, FlatPattern, DuctType, CrossSection, Polyline2D


@dataclass
class Tee(DuctGeometry):
    """
    Tee / branch fitting.

    Parameters
    ----------
    section      : 'Rectangular' or 'Circular'
    main_w/h     : Main (through) duct width & height mm
    branch_w/h   : Branch duct width & height mm (or diameter for circular)
    main_dia     : Main duct diameter mm (circular)
    branch_dia   : Branch duct diameter mm (circular)
    branch_angle : Branch exit angle from main axis degrees (90 = right-angle)
    neck_length  : Short straight neck on branch side mm
    """
    section:      str   = CrossSection.RECTANGULAR
    main_w:       float = 600.0
    main_h:       float = 300.0
    branch_w:     float = 300.0
    branch_h:     float = 250.0
    main_dia:     float = 400.0
    branch_dia:   float = 250.0
    branch_angle: float = 90.0     # degrees
    neck_length:  float = 150.0

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def duct_type(self) -> str:
        return DuctType.TEE

    @property
    def surface_area_sqm(self) -> float:
        if self.section == CrossSection.CIRCULAR:
            return self._circ_area()
        return self._rect_area()

    def _rect_area(self) -> float:
        # Main body (2 lengths of main: one each side of branch)
        body_len   = self.main_w * 2   # nominal body length either side
        main_perim = 2 * (self.main_w + self.main_h)
        branch_perim = 2 * (self.branch_w + self.branch_h)

        body_area   = main_perim * body_len / 1_000_000
        branch_area = branch_perim * self.neck_length / 1_000_000
        # Remove opening in main top plate
        opening     = (self.branch_w * self.branch_h) / 1_000_000
        return body_area + branch_area - opening

    def _circ_area(self) -> float:
        body_len     = self.main_dia * 2
        main_circ    = math.pi * self.main_dia
        branch_circ  = math.pi * self.branch_dia
        body_area    = (main_circ * body_len) / 1_000_000
        branch_area  = (branch_circ * self.neck_length) / 1_000_000
        opening      = math.pi * (self.branch_dia / 2)**2 / 1_000_000
        return body_area + branch_area - opening

    @property
    def weight_kg(self) -> float:
        return self._weight_from_area(self.surface_area_sqm)

    # ── Flat patterns ─────────────────────────────────────────────────────────

    def flat_patterns(self) -> List[FlatPattern]:
        if self.section == CrossSection.CIRCULAR:
            return self._circular_tee_flat()
        return self._rect_tee_flat()

    def _rect_tee_flat(self) -> List[FlatPattern]:
        """
        Rectangular tee flat patterns:
          - Top plate with branch opening (rectangular)
          - Bottom plate (solid rectangle)
          - 2 × side plates
          - Branch neck (4-panel unroll)
        """
        mW, mH = self.main_w, self.main_h
        bW, bH = self.branch_w, self.branch_h
        bL     = self.neck_length
        body_L = mW * 2   # body length (nominal)

        patterns: List[FlatPattern] = []

        # 1. Top plate (with rectangular cutout for branch)
        def top_plate() -> FlatPattern:
            ox = (body_L - bW) / 2
            outline: Polyline2D = [
                (0, 0), (body_L, 0),
                (body_L, mH), (ox + bW, mH),
                (ox + bW, mH + bH), (ox, mH + bH),
                (ox, mH), (0, mH), (0, 0),
            ]
            # Solid area minus cutout
            area = (body_L * mH - bW * bH) / 1_000_000
            return FlatPattern(outline, [], (body_L, mH + bH), area, "Top Plate (branch cutout)")

        # 2. Bottom plate
        def bottom_plate() -> FlatPattern:
            pts: Polyline2D = [(0,0),(body_L,0),(body_L,mH),(0,mH),(0,0)]
            return FlatPattern(pts, [], (body_L, mH),
                               (body_L * mH) / 1_000_000, "Bottom Plate")

        # 3. Side plates (×2)
        def side_plate() -> FlatPattern:
            pts: Polyline2D = [(0,0),(body_L,0),(body_L,mH),(0,mH),(0,0)]
            return FlatPattern(pts, [], (body_L, mH),
                               (body_L * mH) / 1_000_000, "Side Plate (×2)")

        # 4. Branch neck (unrolled – same as straight duct)
        def branch_neck() -> FlatPattern:
            girth  = 2 * (bW + bH)
            pts: Polyline2D = [(0,0),(girth,0),(girth,bL),(0,bL),(0,0)]
            fold_xs = [bW, bW + bH, bW + bH + bW]
            folds = [[(x, 0), (x, bL)] for x in fold_xs]
            return FlatPattern(pts, folds, (girth, bL),
                               (girth * bL) / 1_000_000, "Branch Neck")

        patterns = [top_plate(), bottom_plate(), side_plate(), branch_neck()]
        return patterns

    def _circular_tee_flat(self) -> List[FlatPattern]:
        """
        Circular tee: main cylinder with a saddle-cut opening,
        branch cylinder with a coped (scalloped) end.
        """
        mD = self.main_dia
        bD = self.branch_dia
        bL = self.neck_length
        mL = mD * 2
        N  = 64

        # Main cylinder flat (rectangle)
        mCirc = math.pi * mD
        main_pts: Polyline2D = [(0,0),(mCirc,0),(mCirc,mL),(0,mL),(0,0)]
        main_fp = FlatPattern(main_pts, [], (mCirc, mL),
                              (mCirc * mL) / 1_000_000, "Main Cylinder")

        # Branch cylinder with coped (saddle) end
        # At angle θ around branch c/s, the cope length is:
        #   L_cope(θ) = bL + r_branch * |cos θ| * r_branch/r_main (approx)
        bCirc = math.pi * bD
        r_m   = mD / 2
        r_b   = bD / 2
        pts: Polyline2D = []
        for i in range(N + 1):
            theta = 2 * math.pi * i / N
            x     = bCirc * i / N
            cope  = r_b * abs(math.cos(theta)) / math.sqrt(1 - (r_b / r_m * math.sin(theta))**2 + 1e-9)
            y     = bL + cope
            pts.append((x, y))
        branch_pts = [(0, 0)] + pts + [(0, 0)]
        branch_fp = FlatPattern(branch_pts, [], (bCirc, bL + r_b),
                                (bCirc * bL) / 1_000_000, "Branch Cylinder (coped end)")

        return [main_fp, branch_fp]

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "type": "Tee",
            "section": self.section,
            "main_w": self.main_w, "main_h": self.main_h,
            "branch_w": self.branch_w, "branch_h": self.branch_h,
            "main_dia": self.main_dia, "branch_dia": self.branch_dia,
            "branch_angle": self.branch_angle,
            "neck_length": self.neck_length,
            "material": self.material,
            "thickness": self.thickness,
            "tag": self.tag,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Tee":
        return cls(
            section=d.get("section", CrossSection.RECTANGULAR),
            main_w=float(d.get("main_w", 600)),
            main_h=float(d.get("main_h", 300)),
            branch_w=float(d.get("branch_w", 300)),
            branch_h=float(d.get("branch_h", 250)),
            main_dia=float(d.get("main_dia", 400)),
            branch_dia=float(d.get("branch_dia", 250)),
            branch_angle=float(d.get("branch_angle", 90)),
            neck_length=float(d.get("neck_length", 150)),
            material=d.get("material", "Galvanised Steel"),
            thickness=float(d.get("thickness", 0.8)),
            tag=d.get("tag", ""),
        )
