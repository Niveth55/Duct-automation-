"""
Base classes for all duct geometry components.
All linear units in millimetres (mm).
All angles in degrees.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import math


# ── Type aliases ─────────────────────────────────────────────────────────────
Point2D = Tuple[float, float]
Point3D = Tuple[float, float, float]
Polyline2D = List[Point2D]


# ── Enumerations ─────────────────────────────────────────────────────────────
class DuctType:
    STRAIGHT    = "Straight Duct"
    ELBOW       = "Elbow"
    TRANSITION  = "Transition"
    TEE         = "Tee / Branch"
    REDUCER     = "Reducer"


class CrossSection:
    RECTANGULAR = "Rectangular"
    CIRCULAR    = "Circular"
    OVAL        = "Oval"


class Material:
    GALVANISED_STEEL = "Galvanised Steel"
    STAINLESS_304    = "Stainless Steel 304"
    STAINLESS_316    = "Stainless Steel 316"
    ALUMINIUM        = "Aluminium"
    MILD_STEEL       = "Mild Steel"


# Material densities kg/m³
MATERIAL_DENSITY: Dict[str, float] = {
    Material.GALVANISED_STEEL: 7850.0,
    Material.STAINLESS_304:    7900.0,
    Material.STAINLESS_316:    7980.0,
    Material.ALUMINIUM:        2700.0,
    Material.MILD_STEEL:       7850.0,
}


@dataclass
class FlatPattern:
    """Developed (unrolled) flat-pattern sheet with outline and fold lines."""
    outline: Polyline2D                  # outer closed polygon
    fold_lines: List[Polyline2D]         # internal fold lines
    dimensions: Tuple[float, float]      # bounding box (W × H) mm
    area_sqm: float
    label: str = ""

    def bounding_box(self) -> Tuple[float, float, float, float]:
        xs = [p[0] for p in self.outline]
        ys = [p[1] for p in self.outline]
        return min(xs), min(ys), max(xs), max(ys)


@dataclass
class DuctGeometry(ABC):
    """Abstract base for all duct component geometries."""
    material: str = Material.GALVANISED_STEEL
    thickness: float = 0.8          # sheet metal gauge mm
    tag: str = ""

    # ── Abstract interface ────────────────────────────────────────────────────

    @property
    @abstractmethod
    def duct_type(self) -> str: ...

    @property
    @abstractmethod
    def surface_area_sqm(self) -> float:
        """External surface area in m²."""
        ...

    @property
    @abstractmethod
    def weight_kg(self) -> float:
        """Component weight in kg."""
        ...

    @abstractmethod
    def flat_patterns(self) -> List[FlatPattern]:
        """Return flat-pattern sheet(s) for fabrication."""
        ...

    @abstractmethod
    def to_dict(self) -> dict:
        """Serialise to JSON-compatible dict."""
        ...

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _weight_from_area(self, area_sqm: float) -> float:
        density = MATERIAL_DENSITY.get(self.material, 7850.0)
        return area_sqm * (self.thickness / 1000.0) * density
