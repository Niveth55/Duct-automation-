"""
Duct drawing engine – converts DuctSystem model objects into AutoCAD entities.

Coordinate system: all dimensions in mm (1 drawing unit = 1 mm).
The scale factor is applied to the insertion point / spacing only;
duct cross-sections are drawn true-to-size so dimensions read correctly.
"""

import math
import logging
from typing import Dict, List, Optional

from ..duct.models import (
    RectangularDuct, RoundDuct, OvalDuct,
    Fitting, FittingType, DuctShape, DuctRun, DuctSystem,
)
from ..autocad.helpers import (
    draw_rectangle, draw_line, draw_circle, draw_arc,
    draw_polyline, draw_text, draw_dim_horizontal, draw_centerline,
    offset_point,
)
from ..autocad.layers import set_entity_layer

logger = logging.getLogger(__name__)

# Drawing constants
LABEL_HEIGHT = 80        # mm – tag text height
DIM_OFFSET = 200         # mm – dimension line offset from duct edge
CL_EXTENSION = 100       # mm – centreline extension beyond duct end
INSULATION_OFFSET = 50   # mm – insulation outline offset (for insulated ducts)


# ---------------------------------------------------------------------------
# Section drawing
# ---------------------------------------------------------------------------

def draw_rectangular_duct(msp, duct: RectangularDuct, layer: str = "DUCT-SUPPLY"):
    """
    Draw a rectangular duct as a double-line plan view.

    The duct is drawn as two parallel lines representing the duct walls,
    with end caps, a centre-line, and a tag label.
    """
    x0, y0 = duct.start.x, duct.start.y
    w, h, L = duct.width, duct.height, duct.length
    angle = duct.angle

    # In plan view the duct width is drawn in the Y direction
    half_w = w / 2

    # Four corners of the duct in local coordinates (x along duct, y across)
    local = [
        (0,       -half_w),
        (L,       -half_w),
        (L,        half_w),
        (0,        half_w),
    ]

    # Rotate and translate
    rad = math.radians(angle)
    cos_a, sin_a = math.cos(rad), math.sin(rad)

    def to_world(lx, ly):
        wx = x0 + lx * cos_a - ly * sin_a
        wy = y0 + lx * sin_a + ly * cos_a
        return (wx, wy)

    corners = [to_world(lx, ly) for lx, ly in local]

    # Outer duct outline (closed polyline)
    ent = draw_polyline(msp, corners, closed=True, layer=layer)

    # Centre-line
    cl_start = to_world(-CL_EXTENSION, 0)
    cl_end   = to_world(L + CL_EXTENSION, 0)
    draw_centerline(msp, *cl_start, *cl_end)

    # Depth label inside duct (height dimension shown as "WxH")
    mid_x, mid_y = to_world(L / 2, 0)
    label = f"{int(w)}x{int(h)}"
    if duct.tag:
        label = f"{duct.tag}\\P{label}"   # MText newline
    try:
        txt = msp.AddText(label, _pt3_raw(mid_x, mid_y), LABEL_HEIGHT)
        txt.Layer = "DUCT-TEXT"
        txt.Alignment = 4   # Middle-Center
        txt.TextAlignmentPoint = _pt3_raw(mid_x, mid_y)
    except Exception:
        draw_text(msp, label, mid_x, mid_y - LABEL_HEIGHT / 2)

    # Dimension – length along duct
    dim_corner = to_world(0, -half_w - DIM_OFFSET)
    dim_end    = to_world(L, -half_w - DIM_OFFSET)
    try:
        msp.AddDimRotated(
            _pt3_raw(*to_world(0, -half_w)),
            _pt3_raw(*to_world(L, -half_w)),
            _pt3_raw(*dim_corner),
            math.radians(angle),
            "",
        ).Layer = "DUCT-DIMENSIONS"
    except Exception:
        pass

    return ent


def draw_round_duct(msp, duct: RoundDuct, layer: str = "DUCT-SUPPLY"):
    """
    Draw a round duct as parallel lines (plan) with diameter annotation.
    """
    x0, y0 = duct.start.x, duct.start.y
    r = duct.diameter / 2
    L = duct.length
    angle = duct.angle
    rad = math.radians(angle)
    cos_a, sin_a = math.cos(rad), math.sin(rad)

    def to_world(lx, ly):
        return (x0 + lx * cos_a - ly * sin_a,
                y0 + lx * sin_a + ly * cos_a)

    # Two parallel lines for the duct walls
    top_s = to_world(0,  r)
    top_e = to_world(L,  r)
    bot_s = to_world(0, -r)
    bot_e = to_world(L, -r)

    draw_line(msp, *top_s, *top_e, layer=layer)
    draw_line(msp, *bot_s, *bot_e, layer=layer)

    # End caps (short perpendicular lines)
    draw_line(msp, *top_s, *bot_s, layer=layer)
    draw_line(msp, *top_e, *bot_e, layer=layer)

    # Centre-line
    cl_s = to_world(-CL_EXTENSION, 0)
    cl_e = to_world(L + CL_EXTENSION, 0)
    draw_centerline(msp, *cl_s, *cl_e)

    # Label
    mid = to_world(L / 2, 0)
    label = f"Ø{int(duct.diameter)}"
    if duct.tag:
        label = f"{duct.tag}\\P{label}"
    draw_text(msp, label, mid[0], mid[1], layer="DUCT-TEXT")

    return None


def draw_oval_duct(msp, duct: OvalDuct, layer: str = "DUCT-SUPPLY"):
    """Draw an oval duct similar to round duct (plan view as parallel lines)."""
    x0, y0 = duct.start.x, duct.start.y
    half_h = duct.minor / 2
    L = duct.length
    angle = duct.angle
    rad = math.radians(angle)
    cos_a, sin_a = math.cos(rad), math.sin(rad)

    def to_world(lx, ly):
        return (x0 + lx * cos_a - ly * sin_a,
                y0 + lx * sin_a + ly * cos_a)

    top_s, top_e = to_world(0, half_h), to_world(L, half_h)
    bot_s, bot_e = to_world(0, -half_h), to_world(L, -half_h)

    draw_line(msp, *top_s, *top_e, layer=layer)
    draw_line(msp, *bot_s, *bot_e, layer=layer)
    draw_line(msp, *top_s, *bot_s, layer=layer)
    draw_line(msp, *top_e, *bot_e, layer=layer)

    mid = to_world(L / 2, 0)
    label = f"{int(duct.major)}x{int(duct.minor)}"
    if duct.tag:
        label = f"{duct.tag}\\P{label}"
    draw_text(msp, label, mid[0], mid[1], layer="DUCT-TEXT")

    return None


# ---------------------------------------------------------------------------
# Fitting drawing
# ---------------------------------------------------------------------------

def draw_fitting(msp, fitting: Fitting):
    """Dispatch fitting drawing based on type and shape."""
    drawers = {
        FittingType.ELBOW_90:  _draw_elbow_90,
        FittingType.ELBOW_45:  _draw_elbow_45,
        FittingType.TEE:       _draw_tee,
        FittingType.REDUCER:   _draw_reducer,
        FittingType.CAP:       _draw_cap,
        FittingType.DAMPER:    _draw_damper,
        FittingType.DIFFUSER:  _draw_diffuser,
    }
    fn = drawers.get(fitting.fitting_type)
    if fn:
        fn(msp, fitting)
    else:
        logger.warning("No drawing routine for fitting type: %s", fitting.fitting_type)


def _get_duct_half(fitting: Fitting) -> float:
    """Return half the duct width (plan view)."""
    if fitting.shape == DuctShape.ROUND:
        return fitting.diameter / 2
    return fitting.width / 2


def _draw_elbow_90(msp, fitting: Fitting):
    px, py = fitting.position.x, fitting.position.y
    half = _get_duct_half(fitting)
    angle = fitting.angle
    # Draw two arcs representing the elbow
    radius_inner = half
    radius_outer = half * 3

    rad = math.radians(angle)
    cos_a, sin_a = math.cos(rad), math.sin(rad)

    def to_world(lx, ly):
        return (px + lx * cos_a - ly * sin_a,
                py + lx * sin_a + ly * cos_a)

    # Centre of curvature
    cx, cy = to_world(0, 0)

    start_d = angle + 180
    end_d   = angle + 90

    try:
        draw_arc(msp, cx, cy, radius_inner, start_d, end_d, layer="DUCT-FITTINGS")
        draw_arc(msp, cx, cy, radius_outer, start_d, end_d, layer="DUCT-FITTINGS")
    except Exception as exc:
        logger.warning("Elbow 90 draw failed: %s", exc)

    if fitting.tag:
        draw_text(msp, fitting.tag, px, py, layer="DUCT-TEXT")


def _draw_elbow_45(msp, fitting: Fitting):
    px, py = fitting.position.x, fitting.position.y
    half = _get_duct_half(fitting)
    angle = fitting.angle

    radius_inner = half
    radius_outer = half * 3
    start_d = angle + 180
    end_d   = angle + 135  # 45° sweep

    try:
        draw_arc(msp, px, py, radius_inner, start_d, end_d, layer="DUCT-FITTINGS")
        draw_arc(msp, px, py, radius_outer, start_d, end_d, layer="DUCT-FITTINGS")
    except Exception as exc:
        logger.warning("Elbow 45 draw failed: %s", exc)

    if fitting.tag:
        draw_text(msp, fitting.tag, px, py, layer="DUCT-TEXT")


def _draw_tee(msp, fitting: Fitting):
    px, py = fitting.position.x, fitting.position.y
    half = _get_duct_half(fitting)
    a = fitting.angle
    L = half * 4   # nominal tee body length

    rad = math.radians(a)
    cos_a, sin_a = math.cos(rad), math.sin(rad)

    def to_world(lx, ly):
        return (px + lx * cos_a - ly * sin_a,
                py + lx * sin_a + ly * cos_a)

    # Main duct outline
    corners = [
        to_world(-L,  half), to_world(L,  half),
        to_world(L, -half),  to_world(-L, -half),
    ]
    draw_polyline(msp, corners, closed=True, layer="DUCT-FITTINGS")

    # Branch outlet (perpendicular)
    br = [
        to_world(-half, half), to_world(half, half),
        to_world(half, half + L), to_world(-half, half + L),
    ]
    draw_polyline(msp, br, closed=True, layer="DUCT-FITTINGS")

    if fitting.tag:
        draw_text(msp, fitting.tag, px, py, layer="DUCT-TEXT")


def _draw_reducer(msp, fitting: Fitting):
    px, py = fitting.position.x, fitting.position.y
    angle = fitting.angle
    L = max(fitting.width, fitting.diameter, 300) * 1.5   # reducer length

    if fitting.shape == DuctShape.RECTANGULAR:
        in_half  = fitting.width / 2
        out_half = fitting.outlet_width / 2 if fitting.outlet_width else in_half * 0.6
    else:
        in_half  = fitting.diameter / 2
        out_half = fitting.outlet_diameter / 2 if fitting.outlet_diameter else in_half * 0.6

    rad = math.radians(angle)
    cos_a, sin_a = math.cos(rad), math.sin(rad)

    def to_world(lx, ly):
        return (px + lx * cos_a - ly * sin_a,
                py + lx * sin_a + ly * cos_a)

    pts = [
        to_world(0,  in_half),
        to_world(L,  out_half),
        to_world(L, -out_half),
        to_world(0, -in_half),
    ]
    draw_polyline(msp, pts, closed=True, layer="DUCT-FITTINGS")

    if fitting.tag:
        mid = to_world(L / 2, 0)
        draw_text(msp, fitting.tag, *mid, layer="DUCT-TEXT")


def _draw_cap(msp, fitting: Fitting):
    px, py = fitting.position.x, fitting.position.y
    if fitting.shape == DuctShape.ROUND:
        draw_circle(msp, px, py, fitting.diameter / 2, layer="DUCT-FITTINGS")
    else:
        draw_rectangle(
            msp, px - fitting.width / 2, py - fitting.height / 2,
            fitting.width, fitting.height,
            angle=fitting.angle, layer="DUCT-FITTINGS",
        )
    if fitting.tag:
        draw_text(msp, fitting.tag, px, py, layer="DUCT-TEXT")


def _draw_damper(msp, fitting: Fitting):
    """Draw a volume damper (rectangle with diagonal blade lines)."""
    px, py = fitting.position.x, fitting.position.y
    half = _get_duct_half(fitting)
    L = half * 2
    angle = fitting.angle

    rad = math.radians(angle)
    cos_a, sin_a = math.cos(rad), math.sin(rad)

    def to_world(lx, ly):
        return (px + lx * cos_a - ly * sin_a,
                py + lx * sin_a + ly * cos_a)

    # Outline
    corners = [
        to_world(-L,  half), to_world(L,  half),
        to_world(L,  -half), to_world(-L, -half),
    ]
    draw_polyline(msp, corners, closed=True, layer="DUCT-FITTINGS")

    # Blade line
    draw_line(msp, *to_world(-L, half), *to_world(L, -half), layer="DUCT-FITTINGS")

    if fitting.tag:
        draw_text(msp, fitting.tag, px, py, layer="DUCT-TEXT")


def _draw_diffuser(msp, fitting: Fitting):
    """Draw a supply/return diffuser (rectangle with X cross)."""
    px, py = fitting.position.x, fitting.position.y
    w = fitting.width if fitting.width else 600
    h = fitting.height if fitting.height else 600

    draw_rectangle(msp, px - w / 2, py - h / 2, w, h,
                   angle=fitting.angle, layer="DUCT-FITTINGS")
    # Cross lines
    draw_line(msp, px - w / 2, py - h / 2, px + w / 2, py + h / 2, layer="DUCT-FITTINGS")
    draw_line(msp, px - w / 2, py + h / 2, px + w / 2, py - h / 2, layer="DUCT-FITTINGS")

    if fitting.tag:
        draw_text(msp, fitting.tag, px, py, layer="DUCT-TEXT")


# ---------------------------------------------------------------------------
# Title block
# ---------------------------------------------------------------------------

def draw_title_block(msp, system: DuctSystem, origin_x: float = 0, origin_y: float = -3000):
    """Draw a simple title block below the drawing."""
    x, y = origin_x, origin_y
    W, H = 8000, 600  # title block width and height

    # Border
    draw_rectangle(msp, x, y, W, H, layer="TITLEBLOCK")
    # Dividers
    for col_x in [x + W * 0.4, x + W * 0.6, x + W * 0.8]:
        draw_line(msp, col_x, y, col_x, y + H, layer="TITLEBLOCK")

    # Row 1 – labels
    row_h = H / 3
    draw_line(msp, x, y + row_h, x + W, y + row_h, layer="TITLEBLOCK")
    draw_line(msp, x, y + 2 * row_h, x + W, y + 2 * row_h, layer="TITLEBLOCK")

    lh = 60  # label text height
    vh = 80  # value text height

    def txt(text, tx, ty, height=lh):
        draw_text(msp, text, tx, ty, height=height, layer="TITLEBLOCK")

    txt("PROJECT:", x + 20, y + 2 * row_h + 20, lh)
    txt(system.project_name, x + 20, y + 2 * row_h + 20 + lh + 10, vh)

    txt("PROJECT NO:", x + W * 0.4 + 20, y + 2 * row_h + 20, lh)
    txt(system.project_number, x + W * 0.4 + 20, y + 2 * row_h + 20 + lh + 10, vh)

    txt("DRAWN BY:", x + W * 0.6 + 20, y + 2 * row_h + 20, lh)
    txt(system.drawn_by, x + W * 0.6 + 20, y + 2 * row_h + 20 + lh + 10, vh)

    txt("DATE:", x + W * 0.8 + 20, y + 2 * row_h + 20, lh)
    txt(system.date, x + W * 0.8 + 20, y + 2 * row_h + 20 + lh + 10, vh)

    txt("SCALE:", x + 20, y + row_h + 20, lh)
    txt(system.scale, x + 20, y + row_h + 20 + lh + 10, vh)

    txt("DUCT LAYOUT - PLAN VIEW", x + W * 0.4 + 20, y + row_h + 20, vh)

    txt("DUCT AUTOMATION SYSTEM", x + 20, y + 20, lh)
    txt("Generated by Duct Automation", x + W * 0.4 + 20, y + 20, lh)


# ---------------------------------------------------------------------------
# Main drawing orchestrator
# ---------------------------------------------------------------------------

SECTION_LAYER_MAP = {
    "supply": "DUCT-SUPPLY",
    "return": "DUCT-RETURN",
    "exhaust": "DUCT-EXHAUST",
    "fresh": "DUCT-FRESH",
}


def draw_duct_system(msp, system: DuctSystem):
    """
    Draw the complete duct system into the given model space.

    Each DuctRun is drawn in sequence. The run name is used to pick
    the appropriate layer (supply/return/exhaust).
    """
    for run in system.runs:
        # Determine layer from run name
        layer = "DUCT-SUPPLY"
        name_lower = run.name.lower()
        for key, lyr in SECTION_LAYER_MAP.items():
            if key in name_lower:
                layer = lyr
                break

        for section in run.sections:
            try:
                if isinstance(section, RectangularDuct):
                    draw_rectangular_duct(msp, section, layer=layer)
                elif isinstance(section, RoundDuct):
                    draw_round_duct(msp, section, layer=layer)
                elif isinstance(section, OvalDuct):
                    draw_oval_duct(msp, section, layer=layer)
            except Exception as exc:
                logger.error("Failed to draw section %s: %s", section, exc)

        for fitting in run.fittings:
            try:
                draw_fitting(msp, fitting)
            except Exception as exc:
                logger.error("Failed to draw fitting %s: %s", fitting, exc)

    draw_title_block(msp, system)
    logger.info("Drawing complete: %d runs drawn.", len(system.runs))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _pt3_raw(x, y, z=0.0):
    try:
        import win32com.client
        import pythoncom
        return win32com.client.VARIANT(
            pythoncom.VT_ARRAY | pythoncom.VT_R8,
            [float(x), float(y), float(z)],
        )
    except ImportError:
        return (float(x), float(y), float(z))
