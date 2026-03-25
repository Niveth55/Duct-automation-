"""
SMACNA (Sheet Metal and Air Conditioning Contractors' National Association)
standard tables and compliance logic.

References:
  SMACNA HVAC Duct Construction Standards – Metal and Flexible, 3rd Edition
  Table 1-1  : Rectangular duct reinforcement classes
  Table 5-1  : Round duct gauges and joints
  Appendix   : Recommended gauge selection by duct width and pressure class
"""

from __future__ import annotations
from typing import Tuple, Optional
import math


# ── Pressure classes (Pa) ─────────────────────────────────────────────────────
class PressureClass:
    LOW    = 500    # ±500 Pa   (~2 in. w.g.)
    MEDIUM = 1000   # ±1000 Pa  (~4 in. w.g.)
    HIGH   = 2000   # ±2000 Pa  (~8 in. w.g.)


# ── Rectangular duct gauge table ──────────────────────────────────────────────
# Key: (max_duct_width_mm, pressure_class)
# Value: (gauge_name, thickness_mm)
#
# SMACNA Table 1-1 (simplified – galvanised steel)
# Width bands: ≤750, ≤1500, ≤2100, >2100 mm

_RECT_GAUGE_TABLE = [
    # (max_width_mm, PressureClass,  gauge_str, thickness_mm)
    (750,   PressureClass.LOW,    "26 ga",  0.55),
    (750,   PressureClass.MEDIUM, "24 ga",  0.70),
    (750,   PressureClass.HIGH,   "22 ga",  0.85),
    (1500,  PressureClass.LOW,    "24 ga",  0.70),
    (1500,  PressureClass.MEDIUM, "22 ga",  0.85),
    (1500,  PressureClass.HIGH,   "20 ga",  1.00),
    (2100,  PressureClass.LOW,    "22 ga",  0.85),
    (2100,  PressureClass.MEDIUM, "20 ga",  1.00),
    (2100,  PressureClass.HIGH,   "18 ga",  1.30),
    (99999, PressureClass.LOW,    "20 ga",  1.00),
    (99999, PressureClass.MEDIUM, "18 ga",  1.30),
    (99999, PressureClass.HIGH,   "16 ga",  1.60),
]

# ── Round duct gauge table ────────────────────────────────────────────────────
# Key: max_diameter_mm
_ROUND_GAUGE_TABLE = [
    # (max_dia_mm, gauge_str, thickness_mm)
    (200,  "26 ga", 0.55),
    (350,  "26 ga", 0.55),
    (500,  "24 ga", 0.70),
    (750,  "22 ga", 0.85),
    (1000, "20 ga", 1.00),
    (1500, "18 ga", 1.30),
    (99999,"16 ga", 1.60),
]

# ── Seam types ────────────────────────────────────────────────────────────────
class SeamType:
    PITTSBURGH  = "Pittsburgh Lock"
    SNAP_LOCK   = "Snap Lock"
    STANDING    = "Standing Seam"
    BUTTON_PUNCH = "Button Punch Snap Lock"
    GROOVED     = "Grooved Seam"


# ── Flange / joint types ──────────────────────────────────────────────────────
class JointType:
    SLIP_AND_DRIVE = "Slip & Drive"
    TDC            = "TDC / TDF Flange"
    ANGLE_IRON     = "Angle Iron Flange"
    BEADED         = "Beaded Slip Coupling"


# ── Standard rectangular duct sizes (mm) ──────────────────────────────────────
STANDARD_RECT_WIDTHS  = [100, 150, 200, 250, 300, 350, 400, 450, 500,
                          600, 700, 750, 800, 900, 1000, 1200, 1400, 1600]
STANDARD_RECT_HEIGHTS = [100, 150, 200, 250, 300, 350, 400, 450, 500, 600, 700, 800]

# ── Standard round duct diameters (mm) ────────────────────────────────────────
STANDARD_ROUND_DIAS = [80, 100, 125, 160, 200, 250, 315, 355, 400,
                        450, 500, 560, 630, 710, 800, 900, 1000, 1250]

# ── Joint allowances (mm) ─────────────────────────────────────────────────────
JOINT_ALLOWANCE = {
    JointType.SLIP_AND_DRIVE: 25,
    JointType.TDC:            30,
    JointType.ANGLE_IRON:     40,
    JointType.BEADED:         20,
}

# ── Minimum bend radius multipliers (× duct width) ───────────────────────────
MIN_CL_RADIUS_FACTOR = 1.5   # SMACNA recommended CL radius = 1.5 × W


# ── Functions ─────────────────────────────────────────────────────────────────

def recommended_gauge_rect(width_mm: float,
                            pressure_class: int = PressureClass.LOW
                            ) -> Tuple[str, float]:
    """Return (gauge_label, thickness_mm) for a rectangular duct."""
    for max_w, pc, gauge, thick in _RECT_GAUGE_TABLE:
        if width_mm <= max_w and pressure_class <= pc:
            return gauge, thick
    return "16 ga", 1.60


def recommended_gauge_round(diameter_mm: float) -> Tuple[str, float]:
    """Return (gauge_label, thickness_mm) for a round duct."""
    for max_d, gauge, thick in _ROUND_GAUGE_TABLE:
        if diameter_mm <= max_d:
            return gauge, thick
    return "16 ga", 1.60


def min_throat_radius(duct_width_mm: float) -> float:
    """Minimum throat radius for elbows (SMACNA Table 4-2)."""
    # Minimum = 0.5 × W, recommended = 1.5 × W (CL)
    return 0.5 * duct_width_mm


def recommended_cl_radius(duct_width_mm: float) -> float:
    return MIN_CL_RADIUS_FACTOR * duct_width_mm


def nearest_standard_rect(width: float, height: float) -> Tuple[float, float]:
    """Snap width and height to nearest SMACNA standard sizes."""
    def nearest(val, choices):
        return min(choices, key=lambda x: abs(x - val))
    return nearest(width, STANDARD_RECT_WIDTHS), nearest(height, STANDARD_RECT_HEIGHTS)


def nearest_standard_round(diameter: float) -> float:
    return min(STANDARD_ROUND_DIAS, key=lambda x: abs(x - diameter))


def validate_duct(duct_type: str,
                  width: float = 0, height: float = 0,
                  diameter: float = 0,
                  length: float = 0,
                  thickness: float = 0,
                  angle: float = 0,
                  throat_radius: float = 0) -> list[str]:
    """
    Validate duct parameters against SMACNA rules.
    Returns a list of warning/error strings (empty = all OK).
    """
    errors = []

    # Length checks
    if length > 0 and length > 3000:
        errors.append("⚠ Section length > 3000 mm – consider adding intermediate joint.")

    # Gauge checks
    if width > 0 and thickness > 0:
        _, rec_thick = recommended_gauge_rect(width)
        if thickness < rec_thick:
            errors.append(
                f"⚠ Gauge {thickness:.2f} mm may be too thin for W={width:.0f} mm. "
                f"SMACNA recommends ≥ {rec_thick:.2f} mm."
            )

    if diameter > 0 and thickness > 0:
        _, rec_thick = recommended_gauge_round(diameter)
        if thickness < rec_thick:
            errors.append(
                f"⚠ Gauge {thickness:.2f} mm may be too thin for Ø{diameter:.0f} mm. "
                f"SMACNA recommends ≥ {rec_thick:.2f} mm."
            )

    # Elbow checks
    if "elbow" in duct_type.lower() or angle > 0:
        if throat_radius > 0 and width > 0:
            min_r = min_throat_radius(width)
            if throat_radius < min_r:
                errors.append(
                    f"✗ Throat radius {throat_radius:.0f} mm < SMACNA minimum "
                    f"{min_r:.0f} mm for W={width:.0f} mm."
                )

    # Dimension sanity
    if width > 0 and height > 0 and width / height > 8:
        errors.append(
            f"⚠ Aspect ratio {width/height:.1f}:1 exceeds SMACNA recommended 4:1 max."
        )

    return errors


def seam_recommendation(width: float, pressure_class: int = PressureClass.LOW) -> str:
    """Recommend seam type based on duct size and pressure class."""
    if width <= 750 and pressure_class == PressureClass.LOW:
        return SeamType.PITTSBURGH
    if width <= 1500:
        return SeamType.SNAP_LOCK
    return SeamType.STANDING


def joint_recommendation(width: float) -> str:
    """Recommend joint/flange type."""
    if width <= 600:
        return JointType.SLIP_AND_DRIVE
    if width <= 1200:
        return JointType.TDC
    return JointType.ANGLE_IRON
