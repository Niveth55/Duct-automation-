"""
DXF drawing generator using ezdxf.

Produces a multi-view fabrication drawing:
  View 1 – Plan view (top view)
  View 2 – Front elevation
  View 3 – End section
  View 4 – Flat pattern layout (all sheets)
  View 5 – Title block

Each view is placed in model space at fixed offsets.
Layers follow SMACNA draughting conventions.
"""

from __future__ import annotations
import math
import logging
from pathlib import Path
from typing import List, Tuple, Optional

from geometry.base import DuctGeometry, FlatPattern, CrossSection, DuctType
from geometry.straight import StraightDuct
from geometry.elbow import Elbow
from geometry.transition import Transition
from geometry.tee import Tee
from geometry.reducer import Reducer

logger = logging.getLogger(__name__)

# ── View offsets (mm) ─────────────────────────────────────────────────────────
VIEW_GAP         = 200    # gap between views
PATTERN_ORIGIN_X = 0
PATTERN_ORIGIN_Y = -5000  # flat patterns below main views


# ── Layers ────────────────────────────────────────────────────────────────────
LAYER_OUTLINE    = "OUTLINE"
LAYER_HIDDEN     = "HIDDEN"
LAYER_CENTRELINE = "CENTRELINE"
LAYER_DIM        = "DIMENSIONS"
LAYER_TEXT       = "TEXT"
LAYER_HATCH      = "HATCH"
LAYER_PATTERN    = "FLAT_PATTERN"
LAYER_TITLEBLOCK = "TITLEBLOCK"

# ACI colours
C_WHITE  = 7
C_RED    = 1
C_YELLOW = 2
C_GREEN  = 3
C_CYAN   = 4
C_BLUE   = 5
C_GREY   = 8


def _ezdxf_available() -> bool:
    try:
        import ezdxf
        return True
    except ImportError:
        return False


def generate_dxf(component: DuctGeometry,
                 output_path: str,
                 title: str = "",
                 drawn_by: str = "",
                 project_no: str = "",
                 scale: str = "1:10") -> bool:
    """
    Generate a complete DXF file for a single duct component.

    Returns True on success, False if ezdxf unavailable.
    """
    if not _ezdxf_available():
        logger.warning("ezdxf not installed – DXF generation skipped.")
        return False

    import ezdxf
    from ezdxf import colors
    from ezdxf.enums import TextEntityAlignment

    doc = ezdxf.new(dxfversion="R2010")
    doc.header["$INSUNITS"] = 4   # mm
    doc.header["$MEASUREMENT"] = 1  # metric

    # ── Layers ──────────────────────────────────────────────────────────────
    def make_layer(name, color, ltype="Continuous", lw=25):
        if name not in doc.layers:
            layer = doc.layers.add(name)
        else:
            layer = doc.layers.get(name)
        layer.color = color
        layer.linetype = ltype
        layer.lineweight = lw

    make_layer(LAYER_OUTLINE,    C_WHITE, lw=50)
    make_layer(LAYER_HIDDEN,     C_BLUE,  ltype="DASHED", lw=25)
    make_layer(LAYER_CENTRELINE, C_RED,   ltype="CENTER",  lw=13)
    make_layer(LAYER_DIM,        C_GREEN, lw=18)
    make_layer(LAYER_TEXT,       C_WHITE, lw=18)
    make_layer(LAYER_HATCH,      C_GREY,  lw=13)
    make_layer(LAYER_PATTERN,    C_CYAN,  lw=35)
    make_layer(LAYER_TITLEBLOCK, C_WHITE, lw=50)

    # Load standard linetypes
    try:
        doc.linetypes.load_ltype_file("CENTER", "acad.lin")
        doc.linetypes.load_ltype_file("DASHED", "acad.lin")
    except Exception:
        pass   # linetype files may not be present

    msp = doc.modelspace()

    # ── Draw component views ─────────────────────────────────────────────────
    drawer = _ComponentDrawer(msp, component)
    drawer.draw_all_views()

    # ── Draw flat patterns ───────────────────────────────────────────────────
    _draw_flat_patterns(msp, component.flat_patterns(), PATTERN_ORIGIN_X, PATTERN_ORIGIN_Y)

    # ── Title block ──────────────────────────────────────────────────────────
    import datetime
    _draw_title_block(
        msp,
        origin=(-500, -8000),
        title=title or str(component),
        drawn_by=drawn_by,
        project_no=project_no,
        scale=scale,
        date=datetime.date.today().isoformat(),
        component=component,
    )

    # ── Save ─────────────────────────────────────────────────────────────────
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(out))
    logger.info("DXF saved: %s", out)
    return True


# ── Component view drawer ─────────────────────────────────────────────────────

class _ComponentDrawer:
    """Dispatches to the correct view-drawing routine for each component type."""

    def __init__(self, msp, component: DuctGeometry):
        self.msp  = msp
        self.comp = component

    def draw_all_views(self):
        c = self.comp
        if isinstance(c, StraightDuct):
            self._draw_straight()
        elif isinstance(c, Elbow):
            self._draw_elbow()
        elif isinstance(c, Transition):
            self._draw_transition()
        elif isinstance(c, Tee):
            self._draw_tee()
        elif isinstance(c, Reducer):
            self._draw_reducer()

    # ── Straight duct ─────────────────────────────────────────────────────────
    def _draw_straight(self):
        c: StraightDuct = self.comp
        L, W, H = c.length, c.width, c.height
        D = c.diameter

        if c.section == CrossSection.CIRCULAR:
            # Plan view: 2 lines + centreline
            _rect(self.msp, 0, -D/2, L, D, LAYER_OUTLINE)
            _cline(self.msp, -50, 0, L+50, 0)
            # End section: circle
            _circle(self.msp, L+300+D/2, 0, D/2, LAYER_OUTLINE)
            _cline(self.msp, L+300, 0, L+300+D, 0)
            _cline(self.msp, L+300+D/2, -D/2-50, L+300+D/2, D/2+50)
            # Dims
            _dim_horizontal(self.msp, 0, -D/2-150, L, -D/2-150, f"L={L:.0f}")
            _dim_vertical(self.msp, L+50, -D/2, L+50, D/2, f"Ø{D:.0f}")
        else:
            # Plan view (top view)
            _rect(self.msp, 0, -W/2, L, W, LAYER_OUTLINE)
            _cline(self.msp, -50, 0, L+50, 0)
            # Front elevation
            ey = -H - VIEW_GAP
            _rect(self.msp, 0, ey-H/2, L, H, LAYER_OUTLINE)
            # End section
            ex = L + VIEW_GAP
            _rect(self.msp, ex, -H/2, W, H, LAYER_OUTLINE)
            # Dims
            _dim_horizontal(self.msp, 0, -W/2-150, L, -W/2-150, f"L={L:.0f}")
            _dim_vertical(self.msp, L+50, ey-H, L+50, ey, f"H={H:.0f}")
            _dim_horizontal(self.msp, ex, -H/2-150, ex+W, -H/2-150, f"W={W:.0f}")
            # Label
            _text(self.msp, f"{W:.0f}×{H:.0f}  L={L:.0f}mm", L/2, W/2+60)

    # ── Elbow ─────────────────────────────────────────────────────────────────
    def _draw_elbow(self):
        c: Elbow = self.comp
        W, H    = c.width, c.height
        R_cl    = c.radius_cl
        R_t     = c.throat_radius
        R_h     = c.heel_radius
        alpha   = c.angle_rad
        N       = 64

        if c.section == CrossSection.CIRCULAR:
            # Draw arc pair for throat and heel
            _arc(self.msp, 0, 0, R_t, 90, 90+c.angle, LAYER_OUTLINE)
            _arc(self.msp, 0, 0, R_h, 90, 90+c.angle, LAYER_OUTLINE)
            _arc(self.msp, 0, 0, R_cl, 90, 90+c.angle, LAYER_CENTRELINE)
            # Start cap
            _line(self.msp, R_t, 0, R_h, 0, LAYER_OUTLINE)
            # End cap (at angle)
            ex = R_cl * math.cos(math.radians(90 + c.angle))
            ey = R_cl * math.sin(math.radians(90 + c.angle))
            dx = (W/2) * math.sin(math.radians(c.angle))
            dy = (W/2) * math.cos(math.radians(c.angle))
            _line(self.msp, ex-dx, ey+dy, ex+dx, ey-dy, LAYER_OUTLINE)
        else:
            # Draw annular sector (cheeks visible in plan)
            _arc(self.msp, 0, 0, R_t, 0, c.angle, LAYER_OUTLINE)
            _arc(self.msp, 0, 0, R_h, 0, c.angle, LAYER_OUTLINE)
            _arc(self.msp, 0, 0, R_cl, 0, c.angle, LAYER_CENTRELINE)
            # End lines
            _line(self.msp, R_t, 0, R_h, 0, LAYER_OUTLINE)
            ex_t = R_t * math.cos(math.radians(c.angle))
            ey_t = R_t * math.sin(math.radians(c.angle))
            ex_h = R_h * math.cos(math.radians(c.angle))
            ey_h = R_h * math.sin(math.radians(c.angle))
            _line(self.msp, ex_t, ey_t, ex_h, ey_h, LAYER_OUTLINE)

        # Dimensions
        _text(self.msp, f"{c.angle:.0f}° {c.elbow_type} Elbow  R={R_cl:.0f}mm",
              R_cl, -200)

    # ── Transition ────────────────────────────────────────────────────────────
    def _draw_transition(self):
        c: Transition = self.comp
        iW, iH = c.inlet_w, c.inlet_h
        oW, oH = c.outlet_w, c.outlet_h
        L      = c.length
        ox, oy = c.offset_x, c.offset_y

        # Plan (top) view – trapezoid
        pts = [
            (0, -iW/2), (L, -oW/2 + ox), (L, oW/2 + ox), (0, iW/2), (0, -iW/2)
        ]
        _polyline(self.msp, pts, LAYER_OUTLINE)
        _cline(self.msp, -50, 0, L+50, 0)
        # Elevation
        ey = -max(iH, oH) - VIEW_GAP
        el_pts = [
            (0, ey - iH/2), (L, ey - oH/2 + oy),
            (L, ey + oH/2 + oy), (0, ey + iH/2), (0, ey - iH/2),
        ]
        _polyline(self.msp, el_pts, LAYER_OUTLINE)
        # Dims
        _dim_horizontal(self.msp, 0, -iW/2-150, iW, -iW/2-150, f"IN W={iW:.0f}")
        _dim_horizontal(self.msp, L, -oW/2+ox-150, L+oW, -oW/2+ox-150, f"OUT W={oW:.0f}")
        _dim_vertical(self.msp, L+100, ey-iH/2, L+100, ey+iH/2, f"H={iH:.0f}")
        _text(self.msp, f"Transition {iW:.0f}×{iH:.0f} → {oW:.0f}×{oH:.0f}  L={L:.0f}mm",
              L/2, iW/2+100)

    # ── Tee ──────────────────────────────────────────────────────────────────
    def _draw_tee(self):
        c: Tee = self.comp
        mW, mH = c.main_w, c.main_h
        bW, bH = c.branch_w, c.branch_h
        bL     = c.neck_length
        body   = mW * 2

        # Plan view – main duct body
        _rect(self.msp, -body/2, -mW/2, body, mW, LAYER_OUTLINE)
        # Branch opening
        _rect(self.msp, -bW/2, mW/2, bW, bL, LAYER_OUTLINE)
        # Centrelines
        _cline(self.msp, -body/2-50, 0, body/2+50, 0)
        _cline(self.msp, 0, -mW/2-50, 0, mW/2+bL+50)
        # Dims
        _dim_horizontal(self.msp, -body/2, -mW/2-150, body, -mW/2-150, f"Main W={mW:.0f}")
        _dim_vertical(self.msp, bW/2+100, mW/2, bW/2+100, mW/2+bL, f"Neck={bL:.0f}")
        _text(self.msp, f"Tee {mW:.0f}×{mH:.0f} + Branch {bW:.0f}×{bH:.0f}", 0, mW/2+bL+120)

    # ── Reducer ───────────────────────────────────────────────────────────────
    def _draw_reducer(self):
        c: Reducer = self.comp
        L = c.length
        if c.section == CrossSection.CIRCULAR:
            r1, r2 = c.inlet_dia/2, c.outlet_dia/2
            pts = [(0,-r1),(L,-r2),(L,r2),(0,r1),(0,-r1)]
            _polyline(self.msp, pts, LAYER_OUTLINE)
            _cline(self.msp, -50, 0, L+50, 0)
            _dim_horizontal(self.msp, 0, -r1-150, L, -r1-150, f"L={L:.0f}")
            _dim_vertical(self.msp, -100, -r1, -100, r1, f"IN Ø={c.inlet_dia:.0f}")
            _dim_vertical(self.msp, L+100, -r2, L+100, r2, f"OUT Ø={c.outlet_dia:.0f}")
        else:
            iW, iH = c.inlet_w, c.inlet_h
            oW, oH = c.outlet_w, c.outlet_h
            # Plan
            pts = [(0,-iW/2),(L,-oW/2),(L,oW/2),(0,iW/2),(0,-iW/2)]
            _polyline(self.msp, pts, LAYER_OUTLINE)
            _cline(self.msp, -50, 0, L+50, 0)
            # Elevation
            ey = -max(iH, oH) - VIEW_GAP
            el = [(0,ey-iH/2),(L,ey-oH/2),(L,ey+oH/2),(0,ey+iH/2),(0,ey-iH/2)]
            _polyline(self.msp, el, LAYER_OUTLINE)
            _dim_horizontal(self.msp, 0, -iW/2-150, L, -iW/2-150, f"L={L:.0f}")
            _dim_vertical(self.msp, -150, -iH/2, -150, iH/2, f"IN {iW:.0f}×{iH:.0f}")
            _dim_vertical(self.msp, L+150, -oH/2, L+150, oH/2, f"OUT {oW:.0f}×{oH:.0f}")


# ── Flat pattern layout ───────────────────────────────────────────────────────

def _draw_flat_patterns(msp, patterns: List[FlatPattern], ox: float, oy: float):
    """Lay all flat patterns out horizontally with gap between them."""
    x = ox
    gap = 150

    for fp in patterns:
        # Translate outline to position
        translated = [(x + px, oy + py) for px, py in fp.outline]
        _polyline(msp, translated, LAYER_PATTERN, closed=False)

        # Fold lines
        for fold in fp.fold_lines:
            pts = [(x + p[0], oy + p[1]) for p in fold]
            _polyline(msp, pts, LAYER_CENTRELINE, closed=False)

        # Label
        bx0, by0, bx1, by1 = fp.bounding_box()
        _text(msp, fp.label, x + (bx0 + bx1)/2, oy + by1 + 80,
              height=60, layer=LAYER_PATTERN)
        _text(msp, f"Area={fp.area_sqm*1e6:.0f} cm² ({fp.area_sqm:.4f} m²)",
              x + (bx0 + bx1)/2, oy + by1 + 160, height=50, layer=LAYER_PATTERN)

        # Bounding box dims
        W_pat = bx1 - bx0
        H_pat = by1 - by0
        _dim_horizontal(msp, x+bx0, oy+by0-120, x+bx1, oy+by0-120, f"{W_pat:.0f}")
        _dim_vertical(msp, x+bx1+120, oy+by0, x+bx1+120, oy+by1, f"{H_pat:.0f}")

        x += W_pat + gap


# ── Title block ───────────────────────────────────────────────────────────────

def _draw_title_block(msp, origin, title, drawn_by, project_no,
                      scale, date, component: DuctGeometry):
    ox, oy = origin
    W, H   = 10000, 800

    # Border
    _rect(msp, ox, oy, W, H, LAYER_TITLEBLOCK)

    # Dividers
    cols = [0.35, 0.55, 0.70, 0.85]
    for c in cols:
        _line(msp, ox + W*c, oy, ox + W*c, oy+H, LAYER_TITLEBLOCK)
    row_h = H / 3
    for r in [1, 2]:
        _line(msp, ox, oy + row_h*r, ox+W, oy + row_h*r, LAYER_TITLEBLOCK)

    def cell(txt, cx, cy, h=60):
        _text(msp, txt, ox + cx, oy + cy, height=h, layer=LAYER_TITLEBLOCK)

    cell("PROJECT:", W*0.02, H*0.72, 45)
    cell(title[:60], W*0.02, H*0.52, 70)
    cell("PROJECT NO:", W*0.37, H*0.72, 45)
    cell(project_no, W*0.37, H*0.52, 70)
    cell("DRAWN BY:", W*0.57, H*0.72, 45)
    cell(drawn_by, W*0.57, H*0.52, 70)
    cell("DATE:", W*0.72, H*0.72, 45)
    cell(date, W*0.72, H*0.52, 70)
    cell("SCALE:", W*0.87, H*0.72, 45)
    cell(scale, W*0.87, H*0.52, 70)

    # Stats
    stats = (f"Surface Area: {component.surface_area_sqm:.3f} m²  |  "
             f"Weight: {component.weight_kg:.2f} kg  |  "
             f"Material: {component.material}  |  "
             f"Gauge: {component.thickness:.2f} mm")
    cell(stats, W*0.02, H*0.18, 50)

    # Title
    cell("HVAC DUCT FABRICATION DRAWING", W*0.02, H*0.82, 55)
    cell("Generated by Duct Automation System", W*0.55, H*0.18, 40)


# ── Low-level drawing helpers ─────────────────────────────────────────────────

def _line(msp, x1, y1, x2, y2, layer=LAYER_OUTLINE):
    msp.add_line((x1, y1), (x2, y2), dxfattribs={"layer": layer})


def _rect(msp, x, y, w, h, layer=LAYER_OUTLINE):
    """Axis-aligned rectangle from lower-left corner."""
    pts = [(x, y), (x+w, y), (x+w, y+h), (x, y+h)]
    msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": layer})


def _polyline(msp, pts, layer=LAYER_OUTLINE, closed=True):
    if len(pts) >= 2:
        msp.add_lwpolyline(pts, close=closed, dxfattribs={"layer": layer})


def _circle(msp, cx, cy, r, layer=LAYER_OUTLINE):
    msp.add_circle((cx, cy), r, dxfattribs={"layer": layer})


def _arc(msp, cx, cy, r, start_deg, end_deg, layer=LAYER_OUTLINE):
    msp.add_arc((cx, cy), r, start_deg, end_deg, dxfattribs={"layer": layer})


def _cline(msp, x1, y1, x2, y2):
    """Centreline (dashed layer)."""
    _line(msp, x1, y1, x2, y2, LAYER_CENTRELINE)


def _text(msp, text: str, x: float, y: float, height: float = 80,
          layer: str = LAYER_TEXT):
    msp.add_text(
        text,
        dxfattribs={
            "insert": (x, y),
            "height": height,
            "layer":  layer,
        },
    )


def _dim_horizontal(msp, x1, y, x2, y2, label: str = ""):
    try:
        msp.add_linear_dim(
            base=(x1, y), p1=(x1, y+10), p2=(x2, y+10),
            angle=0,
            override={"dimtad": 1, "dimasz": 50},
            dxfattribs={"layer": LAYER_DIM},
        ).render()
    except Exception:
        # Fallback: text annotation
        mx = (x1 + x2) / 2
        _line(msp, x1, y, x2, y2, LAYER_DIM)
        _text(msp, label or f"{abs(x2-x1):.0f}", mx, y-120, height=60, layer=LAYER_DIM)


def _dim_vertical(msp, x, y1, x2, y2, label: str = ""):
    try:
        msp.add_linear_dim(
            base=(x, y1), p1=(x-10, y1), p2=(x-10, y2),
            angle=90,
            override={"dimtad": 1, "dimasz": 50},
            dxfattribs={"layer": LAYER_DIM},
        ).render()
    except Exception:
        my = (y1 + y2) / 2
        _line(msp, x, y1, x2, y2, LAYER_DIM)
        _text(msp, label or f"{abs(y2-y1):.0f}", x+60, my, height=60, layer=LAYER_DIM)
