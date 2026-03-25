"""
Duct data models - defines all duct types, fittings, and system layout.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple


class DuctShape(Enum):
    RECTANGULAR = "rectangular"
    ROUND = "round"
    OVAL = "oval"


class FittingType(Enum):
    ELBOW_90 = "90° Elbow"
    ELBOW_45 = "45° Elbow"
    TEE = "Tee"
    CROSS = "Cross"
    REDUCER = "Reducer/Transition"
    OFFSET = "Offset"
    CAP = "End Cap"
    DAMPER = "Volume Damper"
    DIFFUSER = "Diffuser/Grille"


class Material(Enum):
    GALVANIZED_STEEL = "Galvanized Steel"
    STAINLESS_STEEL = "Stainless Steel"
    ALUMINUM = "Aluminum"
    FLEXIBLE = "Flexible Duct"


@dataclass
class Point2D:
    x: float
    y: float

    def as_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)


@dataclass
class Point3D:
    x: float
    y: float
    z: float = 0.0

    def as_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass
class RectangularDuct:
    """Rectangular duct section."""
    width: float           # mm
    height: float          # mm
    length: float          # mm
    start: Point2D = field(default_factory=lambda: Point2D(0, 0))
    angle: float = 0.0     # degrees from horizontal
    material: Material = Material.GALVANIZED_STEEL
    gauge: float = 0.8     # sheet metal thickness in mm
    tag: str = ""          # e.g. "D-01"

    @property
    def shape(self) -> DuctShape:
        return DuctShape.RECTANGULAR

    @property
    def perimeter(self) -> float:
        return 2 * (self.width + self.height)

    @property
    def area_sqm(self) -> float:
        """Surface area in m²."""
        return (self.perimeter * self.length) / 1_000_000

    @property
    def cross_section_area(self) -> float:
        """Cross-sectional area in mm²."""
        return self.width * self.height

    def __str__(self) -> str:
        return f"{self.tag or 'Rect'} {self.width}x{self.height}mm L={self.length}mm"


@dataclass
class RoundDuct:
    """Circular/round duct section."""
    diameter: float        # mm
    length: float          # mm
    start: Point2D = field(default_factory=lambda: Point2D(0, 0))
    angle: float = 0.0
    material: Material = Material.GALVANIZED_STEEL
    gauge: float = 0.6
    tag: str = ""

    @property
    def shape(self) -> DuctShape:
        return DuctShape.ROUND

    @property
    def perimeter(self) -> float:
        import math
        return math.pi * self.diameter

    @property
    def area_sqm(self) -> float:
        return (self.perimeter * self.length) / 1_000_000

    @property
    def cross_section_area(self) -> float:
        import math
        return math.pi * (self.diameter / 2) ** 2

    def __str__(self) -> str:
        return f"{self.tag or 'Round'} Ø{self.diameter}mm L={self.length}mm"


@dataclass
class OvalDuct:
    """Oval/flat-oval duct section."""
    major: float           # major axis mm
    minor: float           # minor axis mm
    length: float          # mm
    start: Point2D = field(default_factory=lambda: Point2D(0, 0))
    angle: float = 0.0
    material: Material = Material.GALVANIZED_STEEL
    gauge: float = 0.6
    tag: str = ""

    @property
    def shape(self) -> DuctShape:
        return DuctShape.OVAL

    @property
    def perimeter(self) -> float:
        import math
        # Ramanujan approximation
        a, b = self.major / 2, self.minor / 2
        h = ((a - b) / (a + b)) ** 2
        return math.pi * (a + b) * (1 + (3 * h) / (10 + math.sqrt(4 - 3 * h)))

    @property
    def area_sqm(self) -> float:
        return (self.perimeter * self.length) / 1_000_000

    def __str__(self) -> str:
        return f"{self.tag or 'Oval'} {self.major}x{self.minor}mm L={self.length}mm"


@dataclass
class Fitting:
    """HVAC duct fitting."""
    fitting_type: FittingType
    shape: DuctShape
    # For rectangular
    width: float = 0.0
    height: float = 0.0
    # For round/oval
    diameter: float = 0.0
    # For reducers – outlet dimensions
    outlet_width: float = 0.0
    outlet_height: float = 0.0
    outlet_diameter: float = 0.0
    # Placement
    position: Point2D = field(default_factory=lambda: Point2D(0, 0))
    angle: float = 0.0
    material: Material = Material.GALVANIZED_STEEL
    tag: str = ""
    quantity: int = 1

    def __str__(self) -> str:
        return f"{self.tag or ''} {self.fitting_type.value} ({self.shape.value})"


@dataclass
class DuctRun:
    """A connected sequence of duct sections forming one branch."""
    name: str
    sections: List = field(default_factory=list)   # RectangularDuct | RoundDuct | OvalDuct
    fittings: List[Fitting] = field(default_factory=list)

    def total_length(self) -> float:
        return sum(s.length for s in self.sections)

    def total_area_sqm(self) -> float:
        return sum(s.area_sqm for s in self.sections)


@dataclass
class DuctSystem:
    """Complete HVAC duct system layout."""
    project_name: str = "HVAC Duct System"
    project_number: str = ""
    drawn_by: str = ""
    date: str = ""
    scale: str = "1:100"
    runs: List[DuctRun] = field(default_factory=list)

    def all_sections(self):
        for run in self.runs:
            yield from run.sections

    def all_fittings(self):
        for run in self.runs:
            yield from run.fittings
