"""
Elbow duct geometry – 90°, 45°, or custom angle.

Supports:
  1. Radius elbow (circular cross-section) – smooth curved elbow
  2. Rectangular radius elbow              – rectangular c/s with curved walls
  3. Mitered elbow                         – segmented (N-piece) miter cut

Flat pattern development:
  Circular radius elbow: sinusoidal development of cylindrical tube cut at angle
  Rectangular mitered:   individual flat trapezoids per segment
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import List, Tuple

from .base import DuctGeometry, FlatPattern, DuctType, CrossSection, Polyline2D


@dataclass
class Elbow(DuctGeometry):
    """
    Elbow fitting.

    Parameters
    ----------
    section      : 'Rectangular' or 'Circular'
    width        : mm  (rectangular W or circle diameter)
    height       : mm  (rectangular H – unused for circular)
    angle        : degrees (e.g. 90, 45, 30)
    elbow_type   : 'Radius' or 'Mitered'
    radius_cl    : Centre-line radius mm (Radius elbows).
                   If 0, auto-set to 1.5 × W (SMACNA default)
    n_pieces     : Number of cuts for mitered elbow (2–7)
    """
    section:   str   = CrossSection.RECTANGULAR
    width:     float = 400.0
    height:    float = 200.0
    angle:     float = 90.0
    elbow_type: str  = "Radius"
    radius_cl: float = 0.0    # 0 = auto
    n_pieces:  int   = 3

    def __post_init__(self):
        if self.radius_cl <= 0:
            # SMACNA: CL radius = 1.5 × larger dimension
            self.radius_cl = 1.5 * max(self.width, self.height)

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def duct_type(self) -> str:
        return DuctType.ELBOW

    @property
    def angle_rad(self) -> float:
        return math.radians(self.angle)

    @property
    def throat_radius(self) -> float:
        """Inner (throat) radius."""
        if self.section == CrossSection.CIRCULAR:
            return self.radius_cl - self.width / 2
        return self.radius_cl - self.width / 2

    @property
    def heel_radius(self) -> float:
        """Outer (heel) radius."""
        if self.section == CrossSection.CIRCULAR:
            return self.radius_cl + self.width / 2
        return self.radius_cl + self.width / 2

    @property
    def throat_arc_length(self) -> float:
        return self.throat_radius * self.angle_rad

    @property
    def heel_arc_length(self) -> float:
        return self.heel_radius * self.angle_rad

    @property
    def cl_arc_length(self) -> float:
        return self.radius_cl * self.angle_rad

    # ── Surface area ──────────────────────────────────────────────────────────

    @property
    def surface_area_sqm(self) -> float:
        if self.section == CrossSection.CIRCULAR:
            return self._circular_area()
        return self._rectangular_area()

    def _circular_area(self) -> float:
        # Torus section: 2π²·R·r · (angle/2π) = π·r·(angle_rad)·2·R... simplified:
        # A = 2π * r * arc_length_of_centreline / (2π) * 2π
        # Correct: A = circumference × cl_arc_length  (approximate for r << R)
        circ = math.pi * self.width   # diameter = self.width for circular
        return (circ * self.cl_arc_length) / 1_000_000

    def _rectangular_area(self) -> float:
        # Two flat cheeks (side walls) + curved top + curved bottom
        # Cheeks: sectors of annulus (throat to heel)
        annulus_area = 0.5 * (self.heel_radius ** 2 - self.throat_radius ** 2) * self.angle_rad
        two_cheeks = 2 * annulus_area / 1_000_000

        # Top (outer curved) + Bottom (inner curved) strips
        top_arc    = self.heel_arc_length * self.height / 1_000_000
        bottom_arc = self.throat_arc_length * self.height / 1_000_000

        # Two end-cap rectangles (W × H each)
        end_caps = 0.0   # end caps belong to the connected straight sections

        return two_cheeks + top_arc + bottom_arc

    @property
    def weight_kg(self) -> float:
        return self._weight_from_area(self.surface_area_sqm)

    # ── Flat patterns ─────────────────────────────────────────────────────────

    def flat_patterns(self) -> List[FlatPattern]:
        if self.section == CrossSection.CIRCULAR:
            return [self._circular_flat_pattern()]
        if self.elbow_type == "Mitered":
            return self._mitered_flat_patterns()
        return self._rect_radius_flat_patterns()

    # ── Circular elbow flat pattern ───────────────────────────────────────────

    def _circular_flat_pattern(self) -> FlatPattern:
        """
        Sinusoidal development of a cylindrical tube with one angled end cut.

        The tube is unwrapped: X axis = circumference (0..π·D),
        Y axis = pipe length at that angular position.

        For an elbow of angle α with centreline radius R:
          At angle θ around pipe c/s:
            L(θ) = throat_arc + (heel_arc - throat_arc) * (1 + cos θ) / 2

        This gives a sine curve on the flat pattern.
        """
        D    = self.width   # diameter
        circ = math.pi * D  # circumference
        N    = 64           # number of points around circumference

        L_min = self.throat_arc_length
        L_max = self.heel_arc_length

        points: Polyline2D = []
        for i in range(N + 1):
            theta = 2 * math.pi * i / N
            x = circ * i / N
            # sinusoidal profile
            y = L_min + (L_max - L_min) * (1 - math.cos(theta)) / 2
            points.append((x, y))

        # Close the pattern: go back along x=circ to x=0 at Y=0
        outline = [(0, 0)] + points + [(0, 0)]

        area = (circ * (L_min + L_max) / 2) / 1_000_000
        return FlatPattern(
            outline=outline,
            fold_lines=[],
            dimensions=(circ, L_max),
            area_sqm=area,
            label=f"Ø{D:.0f} {self.angle:.0f}° Elbow CL-R={self.radius_cl:.0f}",
        )

    # ── Rectangular mitered flat patterns ─────────────────────────────────────

    def _mitered_flat_patterns(self) -> List[FlatPattern]:
        """
        Each miter piece is a rectangular section with angled ends.
        N-piece miter: (N-1) internal cuts create N segments.
        Returns a list of FlatPattern, one per segment.
        """
        n     = max(2, self.n_pieces)
        W, H  = self.width, self.height
        alpha = self.angle_rad / (n - 1)   # miter cut angle per joint

        patterns = []
        for i in range(n):
            # The top width (Y at X=W) of each segment
            taper = W * math.tan(alpha / 2)
            L_min = max(50.0, self.radius_cl * alpha - taper)
            L_max = L_min + W * math.tan(alpha)

            outline: Polyline2D = [
                (0,   0),
                (W,   0),
                (W,   L_max),
                (0,   L_min),
                (0,   0),
            ]
            area = (W * (L_min + L_max) / 2) / 1_000_000
            label = f"Miter {i+1}/{n}  {self.angle:.0f}° ({n}pc)"
            patterns.append(FlatPattern(
                outline=outline,
                fold_lines=[],
                dimensions=(W, L_max),
                area_sqm=area,
                label=label,
            ))
        return patterns

    # ── Rectangular radius flat patterns ─────────────────────────────────────

    def _rect_radius_flat_patterns(self) -> List[FlatPattern]:
        """
        A radius elbow with rectangular c/s has:
          - 2 flat cheek (side) plates  → annular sectors
          - 1 outer (heel) curved strip
          - 1 inner (throat) curved strip
        Returns 4 FlatPattern objects.
        """
        angle_r = self.angle_rad
        W, H   = self.width, self.height
        R_cl   = self.radius_cl
        R_t    = self.throat_radius
        R_h    = self.heel_radius
        N      = 48

        # ── 1 & 2: Cheek plates (annular sectors) ─────────────────────────
        def annular_sector(R_in, R_out, a_rad, n=N) -> Polyline2D:
            pts = []
            for i in range(n + 1):
                a = a_rad * i / n
                pts.append((R_out * math.cos(a), R_out * math.sin(a)))
            for i in range(n, -1, -1):
                a = a_rad * i / n
                pts.append((R_in * math.cos(a), R_in * math.sin(a)))
            pts.append(pts[0])
            return pts

        cheek_pts  = annular_sector(R_t, R_h, angle_r)
        cheek_area = (0.5 * (R_h**2 - R_t**2) * angle_r) / 1_000_000
        cheek_w    = (R_h - R_t)
        cheek_h    = max(R_h * math.sin(angle_r), R_h * (1 - math.cos(angle_r)))

        patterns = []
        for side in ("Left Cheek", "Right Cheek"):
            patterns.append(FlatPattern(
                outline=cheek_pts,
                fold_lines=[],
                dimensions=(cheek_w, cheek_h),
                area_sqm=cheek_area,
                label=f"{side}  {self.angle:.0f}° R={R_cl:.0f}",
            ))

        # ── 3: Outer (heel) curved strip ──────────────────────────────────
        heel_len = R_h * angle_r
        outer: Polyline2D = [(0, 0), (heel_len, 0),
                              (heel_len, H), (0, H), (0, 0)]
        patterns.append(FlatPattern(
            outline=outer,
            fold_lines=[],
            dimensions=(heel_len, H),
            area_sqm=(heel_len * H) / 1_000_000,
            label=f"Outer (Heel) Strip  R={R_h:.0f}",
        ))

        # ── 4: Inner (throat) curved strip ────────────────────────────────
        throat_len = max(10.0, R_t * angle_r)
        inner: Polyline2D = [(0, 0), (throat_len, 0),
                              (throat_len, H), (0, H), (0, 0)]
        patterns.append(FlatPattern(
            outline=inner,
            fold_lines=[],
            dimensions=(throat_len, H),
            area_sqm=(throat_len * H) / 1_000_000,
            label=f"Inner (Throat) Strip  R={R_t:.0f}",
        ))

        return patterns

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "type": "Elbow",
            "section": self.section,
            "width": self.width,
            "height": self.height,
            "angle": self.angle,
            "elbow_type": self.elbow_type,
            "radius_cl": self.radius_cl,
            "n_pieces": self.n_pieces,
            "material": self.material,
            "thickness": self.thickness,
            "tag": self.tag,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Elbow":
        return cls(
            section=d.get("section", CrossSection.RECTANGULAR),
            width=float(d.get("width", 400)),
            height=float(d.get("height", 200)),
            angle=float(d.get("angle", 90)),
            elbow_type=d.get("elbow_type", "Radius"),
            radius_cl=float(d.get("radius_cl", 0)),
            n_pieces=int(d.get("n_pieces", 3)),
            material=d.get("material", "Galvanised Steel"),
            thickness=float(d.get("thickness", 0.8)),
            tag=d.get("tag", ""),
        )
