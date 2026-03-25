"""
Low-level AutoCAD drawing helpers – wraps COM calls with type conversions.
"""

import math
import array
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Type alias
Pt2 = Tuple[float, float]
Pt3 = Tuple[float, float, float]


def _pt3(x: float, y: float, z: float = 0.0):
    """Return a VARIANT-compatible point array."""
    try:
        import win32com.client
        pt = win32com.client.VARIANT(
            win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8,
            [x, y, z],
        )
        return pt
    except ImportError:
        return (x, y, z)


def _pts_flat(coords: List[Pt2]) -> object:
    """
    Flatten list of (x,y) pairs into a flat float array for AddLightWeightPolyline.
    """
    flat = []
    for x, y in coords:
        flat.extend([float(x), float(y)])
    try:
        return array.array("d", flat)
    except Exception:
        return flat


def draw_rectangle(msp, x: float, y: float, w: float, h: float,
                   angle: float = 0.0, layer: str = "0") -> object:
    """
    Draw an axis-aligned or rotated rectangle as a closed LWPolyline.

    Args:
        msp   : ModelSpace object
        x, y  : lower-left corner (in mm / drawing units)
        w, h  : width and height (mm)
        angle : rotation angle in degrees
        layer : target layer name

    Returns the polyline entity.
    """
    corners = [(0, 0), (w, 0), (w, h), (0, h)]

    if angle != 0.0:
        rad = math.radians(angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        rotated = []
        for cx, cy in corners:
            rx = cx * cos_a - cy * sin_a + x
            ry = cx * sin_a + cy * cos_a + y
            rotated.append((rx, ry))
        corners = rotated
    else:
        corners = [(x + cx, y + cy) for cx, cy in corners]

    pts = _pts_flat(corners)
    try:
        ent = msp.AddLightWeightPolyline(pts)
        ent.Closed = True
        ent.Layer = layer
        return ent
    except Exception as exc:
        logger.error("draw_rectangle failed: %s", exc)
        raise


def draw_line(msp, x1: float, y1: float, x2: float, y2: float,
              layer: str = "0") -> object:
    """Draw a single line segment."""
    try:
        ent = msp.AddLine(_pt3(x1, y1), _pt3(x2, y2))
        ent.Layer = layer
        return ent
    except Exception as exc:
        logger.error("draw_line failed: %s", exc)
        raise


def draw_circle(msp, cx: float, cy: float, radius: float,
                layer: str = "0") -> object:
    """Draw a circle."""
    try:
        ent = msp.AddCircle(_pt3(cx, cy), radius)
        ent.Layer = layer
        return ent
    except Exception as exc:
        logger.error("draw_circle failed: %s", exc)
        raise


def draw_arc(msp, cx: float, cy: float, radius: float,
             start_deg: float, end_deg: float,
             layer: str = "0") -> object:
    """Draw an arc (angles in degrees, CCW from east)."""
    try:
        ent = msp.AddArc(
            _pt3(cx, cy),
            radius,
            math.radians(start_deg),
            math.radians(end_deg),
        )
        ent.Layer = layer
        return ent
    except Exception as exc:
        logger.error("draw_arc failed: %s", exc)
        raise


def draw_polyline(msp, points: List[Pt2], closed: bool = False,
                  layer: str = "0") -> object:
    """Draw a polyline from a list of (x,y) points."""
    pts = _pts_flat(points)
    try:
        ent = msp.AddLightWeightPolyline(pts)
        ent.Closed = closed
        ent.Layer = layer
        return ent
    except Exception as exc:
        logger.error("draw_polyline failed: %s", exc)
        raise


def draw_text(msp, text: str, x: float, y: float, height: float = 100.0,
              layer: str = "DUCT-TEXT") -> object:
    """Add a single-line text entity."""
    try:
        ent = msp.AddText(text, _pt3(x, y), height)
        ent.Layer = layer
        return ent
    except Exception as exc:
        logger.error("draw_text failed: %s", exc)
        raise


def draw_mtext(msp, text: str, x: float, y: float,
               width: float = 1000.0, height: float = 100.0,
               layer: str = "DUCT-TEXT") -> object:
    """Add a multi-line text (MText) entity."""
    try:
        ent = msp.AddMText(_pt3(x, y), width, text)
        ent.Layer = layer
        return ent
    except Exception as exc:
        logger.error("draw_mtext failed: %s", exc)
        raise


def draw_dim_horizontal(msp, x1: float, y1: float, x2: float, y2: float,
                        dim_y: float, layer: str = "DUCT-DIMENSIONS") -> object:
    """Add a horizontal rotated dimension."""
    try:
        ent = msp.AddDimRotated(
            _pt3(x1, y1), _pt3(x2, y2),
            _pt3((x1 + x2) / 2, dim_y),
            0.0, "",
        )
        ent.Layer = layer
        return ent
    except Exception as exc:
        logger.warning("draw_dim_horizontal: %s", exc)


def draw_centerline(msp, x1: float, y1: float, x2: float, y2: float) -> object:
    """Draw a centre-line between two points."""
    return draw_line(msp, x1, y1, x2, y2, layer="DUCT-CENTERLINE")


def offset_point(x: float, y: float, distance: float, angle_deg: float) -> Pt2:
    """Return a new point offset from (x,y) along angle_deg by distance."""
    rad = math.radians(angle_deg)
    return (x + distance * math.cos(rad), y + distance * math.sin(rad))
