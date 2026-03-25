"""
2D preview renderer using matplotlib embedded in Tkinter.
Renders plan view + flat pattern for any DuctGeometry component.
"""

from __future__ import annotations
import math
from typing import Optional, List

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.gridspec as gridspec
import numpy as np

from geometry.base import DuctGeometry, FlatPattern, CrossSection, DuctType
from geometry.straight    import StraightDuct
from geometry.elbow       import Elbow
from geometry.transition  import Transition
from geometry.tee         import Tee
from geometry.reducer     import Reducer


# ── Colour scheme ─────────────────────────────────────────────────────────────
CLR_OUTLINE  = "#1565C0"   # dark blue
CLR_HIDDEN   = "#9E9E9E"   # grey dashed
CLR_CENTRE   = "#E53935"   # red
CLR_DIM      = "#2E7D32"   # dark green
CLR_PATTERN  = "#F57C00"   # orange
CLR_FOLD     = "#B71C1C"   # dark red dashed
CLR_FILL     = "#E3F2FD"   # light blue fill
CLR_PATTERN_FILL = "#FFF3E0"


def build_preview_canvas(parent_frame, figsize=(10, 7)):
    """Create and return (canvas, toolbar, fig, axes_dict)."""
    fig = plt.figure(figsize=figsize, facecolor="#FAFAFA")
    gs  = gridspec.GridSpec(2, 2, figure=fig,
                             height_ratios=[1.4, 1],
                             hspace=0.45, wspace=0.35)
    axes = {
        "plan":     fig.add_subplot(gs[0, 0]),
        "elev":     fig.add_subplot(gs[0, 1]),
        "section":  fig.add_subplot(gs[1, 0]),
        "pattern":  fig.add_subplot(gs[1, 1]),
    }
    for ax in axes.values():
        ax.set_aspect("equal")
        ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
        ax.tick_params(labelsize=7)

    canvas  = FigureCanvasTkAgg(fig, master=parent_frame)
    toolbar = NavigationToolbar2Tk(canvas, parent_frame)
    toolbar.update()
    return canvas, toolbar, fig, axes


def render_component(axes: dict, component: DuctGeometry):
    """Clear axes and redraw all views for the given component."""
    for ax in axes.values():
        ax.cla()
        ax.set_aspect("equal")
        ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)

    if isinstance(component, StraightDuct):
        _render_straight(axes, component)
    elif isinstance(component, Elbow):
        _render_elbow(axes, component)
    elif isinstance(component, Transition):
        _render_transition(axes, component)
    elif isinstance(component, Tee):
        _render_tee(axes, component)
    elif isinstance(component, Reducer):
        _render_reducer(axes, component)

    # Always render flat patterns in bottom-right
    fps = component.flat_patterns()
    _render_flat_patterns(axes["pattern"], fps)


# ── Straight duct ─────────────────────────────────────────────────────────────

def _render_straight(axes, c: StraightDuct):
    ax_p, ax_e, ax_s = axes["plan"], axes["elev"], axes["section"]
    L = c.length

    if c.section == CrossSection.CIRCULAR:
        D, R = c.diameter, c.diameter / 2
        # Plan (top)
        _filled_rect(ax_p, 0, -R, L, D)
        _cline_h(ax_p, -R*.1, L*1.05, 0)
        _dim(ax_p, 0, -R-D*.15, L, -R-D*.15, f"L = {L:.0f} mm")
        _dim_v(ax_p, L+D*.1, -R, L+D*.1, R, f"Ø{D:.0f}")
        ax_p.set_title("Plan View", fontsize=9, fontweight="bold")

        # Front elevation (same as plan for cylinder)
        _filled_rect(ax_e, 0, -R, L, D)
        _cline_h(ax_e, -R*.1, L*1.05, 0)
        ax_e.set_title("Front Elevation", fontsize=9, fontweight="bold")

        # End section
        circ = plt.Circle((0, 0), R, fill=True, facecolor=CLR_FILL,
                           edgecolor=CLR_OUTLINE, linewidth=1.5)
        ax_s.add_patch(circ)
        _cline_h(ax_s, -R*1.15, R*1.15, 0)
        _cline_v(ax_s, 0, -R*1.15, R*1.15)
        _dim_v(ax_s, R*1.3, -R, R*1.3, R, f"Ø{D:.0f}")
        ax_s.set_xlim(-R*1.8, R*1.8); ax_s.set_ylim(-R*1.8, R*1.8)
        ax_s.set_title("End Section", fontsize=9, fontweight="bold")
    else:
        W, H = c.width, c.height
        # Plan
        _filled_rect(ax_p, 0, -W/2, L, W)
        _cline_h(ax_p, -L*.02, L*1.05, 0)
        _dim(ax_p, 0, -W/2-W*.2, L, -W/2-W*.2, f"L = {L:.0f}")
        _dim_v(ax_p, L+W*.15, -W/2, L+W*.15, W/2, f"W={W:.0f}")
        ax_p.set_title("Plan View (Top)", fontsize=9, fontweight="bold")

        # Elevation
        _filled_rect(ax_e, 0, -H/2, L, H)
        _cline_h(ax_e, -L*.02, L*1.05, 0)
        _dim(ax_e, 0, -H/2-H*.25, L, -H/2-H*.25, f"L = {L:.0f}")
        _dim_v(ax_e, L+H*.15, -H/2, L+H*.15, H/2, f"H={H:.0f}")
        ax_e.set_title("Front Elevation", fontsize=9, fontweight="bold")

        # End section
        _filled_rect(ax_s, -W/2, -H/2, W, H)
        _dim(ax_s, -W/2, -H/2-H*.25, W/2, -H/2-H*.25, f"W={W:.0f}")
        _dim_v(ax_s, W/2+W*.15, -H/2, W/2+W*.15, H/2, f"H={H:.0f}")
        ax_s.set_title("End Section", fontsize=9, fontweight="bold")

    _auto_scale(axes["plan"])
    _auto_scale(axes["elev"])
    _auto_scale(axes["section"])


# ── Elbow ─────────────────────────────────────────────────────────────────────

def _render_elbow(axes, c: Elbow):
    ax_p = axes["plan"]
    R_t, R_h, R_cl = c.throat_radius, c.heel_radius, c.radius_cl
    alpha = c.angle_rad
    N     = 120

    angles = np.linspace(0, alpha, N)

    # Outer arc (heel)
    xh = R_h * np.cos(angles)
    yh = R_h * np.sin(angles)
    # Inner arc (throat)
    xt = R_t * np.cos(angles)
    yt = R_t * np.sin(angles)
    # CL arc
    xc = R_cl * np.cos(angles)
    yc = R_cl * np.sin(angles)

    # Fill between arcs
    ax_p.fill_betweenx(yh, xt, xh, alpha=0.25, color=CLR_FILL)
    ax_p.plot(xh, yh, color=CLR_OUTLINE, linewidth=1.5)
    ax_p.plot(xt, yt, color=CLR_OUTLINE, linewidth=1.5)
    ax_p.plot(xc, yc, color=CLR_CENTRE, linewidth=0.8, linestyle="--")
    # End caps
    ax_p.plot([xt[0], xh[0]], [yt[0], yh[0]], color=CLR_OUTLINE, linewidth=1.5)
    ax_p.plot([xt[-1], xh[-1]], [yt[-1], yh[-1]], color=CLR_OUTLINE, linewidth=1.5)

    # Dimensions
    mid = N // 2
    ax_p.annotate(
        f"R={R_cl:.0f}", (xc[mid], yc[mid]),
        fontsize=7, color=CLR_DIM, ha="center",
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.7),
    )
    ax_p.set_title(f"Elbow Plan – {c.angle:.0f}°  {c.elbow_type}", fontsize=9, fontweight="bold")

    # Elevation (same as plan for symmetric elbow)
    ax_e = axes["elev"]
    W, H = c.width, c.height
    ax_e.fill_betweenx(yh, xt, xh, alpha=0.25, color=CLR_FILL)
    ax_e.plot(xh, yh, color=CLR_OUTLINE, linewidth=1.5)
    ax_e.plot(xt, yt, color=CLR_OUTLINE, linewidth=1.5)
    ax_e.set_title("Elevation", fontsize=9, fontweight="bold")

    # Section
    ax_s = axes["section"]
    if c.section == CrossSection.CIRCULAR:
        circ = plt.Circle((0, 0), c.width/2, fill=True, facecolor=CLR_FILL,
                           edgecolor=CLR_OUTLINE, linewidth=1.5)
        ax_s.add_patch(circ)
        ax_s.set_xlim(-c.width, c.width); ax_s.set_ylim(-c.width, c.width)
    else:
        _filled_rect(ax_s, -W/2, -H/2, W, H)
    ax_s.set_title("Cross-Section", fontsize=9, fontweight="bold")

    _auto_scale(ax_p); _auto_scale(axes["elev"]); _auto_scale(ax_s)


# ── Transition ────────────────────────────────────────────────────────────────

def _render_transition(axes, c: Transition):
    ax_p, ax_e = axes["plan"], axes["elev"]
    iW, iH = c.inlet_w, c.inlet_h
    oW, oH = c.outlet_w, c.outlet_h
    L = c.length
    ox, oy = c.offset_x, c.offset_y

    # Plan
    pts_plan = [(0, -iW/2), (L, -oW/2+ox), (L, oW/2+ox), (0, iW/2)]
    _filled_poly(ax_p, pts_plan)
    _cline_h(ax_p, -L*.05, L*1.05, 0)
    _dim(ax_p, 0, -iW/2-iW*.2, iW/2, -iW/2-iW*.2, f"IN W={iW:.0f}")
    ax_p.set_title("Plan View", fontsize=9, fontweight="bold")

    # Elevation
    pts_el = [(0, -iH/2), (L, -oH/2+oy), (L, oH/2+oy), (0, iH/2)]
    _filled_poly(ax_e, pts_el)
    _cline_h(ax_e, -L*.05, L*1.05, 0)
    _dim_v(ax_e, L+iH*.15, -oH/2+oy, L+iH*.15, oH/2+oy, f"OUT H={oH:.0f}")
    ax_e.set_title("Elevation", fontsize=9, fontweight="bold")

    # Section – inlet
    ax_s = axes["section"]
    _filled_rect(ax_s, -iW/2, -iH/2, iW, iH)
    _filled_rect(ax_s, -oW/2+ox, -oH/2+oy, oW, oH, alpha=0.35, color="#FF8A65")
    ax_s.set_title("Inlet (blue) / Outlet (orange) Section", fontsize=8, fontweight="bold")
    _auto_scale(ax_p); _auto_scale(ax_e); _auto_scale(ax_s)


# ── Tee ──────────────────────────────────────────────────────────────────────

def _render_tee(axes, c: Tee):
    ax_p = axes["plan"]
    mW, mH = c.main_w, c.main_h
    bW, bH = c.branch_w, c.branch_h
    bL     = c.neck_length
    body   = mW * 2

    # Plan: main body
    _filled_rect(ax_p, -body/2, -mW/2, body, mW)
    # Branch
    _filled_rect(ax_p, -bW/2, mW/2, bW, bL, color="#FFE082")
    _cline_h(ax_p, -body/2-mW*.1, body/2+mW*.1, 0)
    _cline_v(ax_p, 0, -mW/2-mW*.1, mW/2+bL+mW*.1)
    _dim(ax_p, -body/2, -mW/2-mW*.25, body/2, -mW/2-mW*.25, f"Main W={mW:.0f}")
    _dim_v(ax_p, bW/2+bW*.2, mW/2, bW/2+bW*.2, mW/2+bL, f"Neck={bL:.0f}")
    ax_p.set_title("Tee – Plan View", fontsize=9, fontweight="bold")

    ax_e = axes["elev"]
    _filled_rect(ax_e, -body/2, -mH/2, body, mH)
    _filled_rect(ax_e, -bH/2, mH/2, bH, bL, color="#FFE082")
    ax_e.set_title("Elevation", fontsize=9, fontweight="bold")

    ax_s = axes["section"]
    _filled_rect(ax_s, -mW/2, -mH/2, mW, mH)
    ax_s.set_title("Main Cross-Section", fontsize=9, fontweight="bold")
    _auto_scale(ax_p); _auto_scale(ax_e); _auto_scale(ax_s)


# ── Reducer ───────────────────────────────────────────────────────────────────

def _render_reducer(axes, c: Reducer):
    ax_p, ax_e = axes["plan"], axes["elev"]
    L = c.length

    if c.section == CrossSection.CIRCULAR:
        r1, r2 = c.inlet_dia/2, c.outlet_dia/2
        pts = [(0,-r1),(L,-r2),(L,r2),(0,r1)]
        _filled_poly(ax_p, pts)
        _cline_h(ax_p, -L*.05, L*1.05, 0)
        _dim(ax_p, 0, -r1-r1*.25, L, -r1-r1*.25, f"L={L:.0f}")
        _dim_v(ax_p, -r1*.3, -r1, -r1*.3, r1, f"Ø{c.inlet_dia:.0f}")
        _dim_v(ax_p, L+r2*.3, -r2, L+r2*.3, r2, f"Ø{c.outlet_dia:.0f}")
        ax_p.set_title("Reducer – Plan", fontsize=9, fontweight="bold")
        ax_e.set_title("(same as plan for circular)", fontsize=8)
        _filled_poly(ax_e, pts)

        ax_s = axes["section"]
        for r, col, lbl in [(r1, CLR_FILL, "Inlet"), (r2, "#FFE082", "Outlet")]:
            circ = plt.Circle((0, 0), r, fill=True, facecolor=col,
                               edgecolor=CLR_OUTLINE, linewidth=1.5, alpha=0.7)
            ax_s.add_patch(circ)
        ax_s.set_xlim(-r1*1.5, r1*1.5); ax_s.set_ylim(-r1*1.5, r1*1.5)
        ax_s.set_title("Inlet (blue) / Outlet (yellow)", fontsize=8, fontweight="bold")
    else:
        iW, iH = c.inlet_w, c.inlet_h
        oW, oH = c.outlet_w, c.outlet_h
        pts_p = [(0,-iW/2),(L,-oW/2),(L,oW/2),(0,iW/2)]
        pts_e = [(0,-iH/2),(L,-oH/2),(L,oH/2),(0,iH/2)]
        _filled_poly(ax_p, pts_p)
        _filled_poly(ax_e, pts_e)
        _cline_h(ax_p, -L*.05, L*1.05, 0)
        _dim(ax_p, 0, -iW/2-iW*.2, L, -iW/2-iW*.2, f"L={L:.0f}")
        ax_p.set_title("Plan View", fontsize=9, fontweight="bold")
        ax_e.set_title("Elevation", fontsize=9, fontweight="bold")

        ax_s = axes["section"]
        _filled_rect(ax_s, -iW/2, -iH/2, iW, iH)
        _filled_rect(ax_s, -oW/2, -oH/2, oW, oH, alpha=0.5, color="#FFE082")
        ax_s.set_title("Inlet / Outlet Section", fontsize=8, fontweight="bold")

    _auto_scale(ax_p); _auto_scale(ax_e); _auto_scale(axes["section"])


# ── Flat patterns ─────────────────────────────────────────────────────────────

def _render_flat_patterns(ax, patterns: List[FlatPattern]):
    ax.set_title("Flat Pattern Development", fontsize=9, fontweight="bold")
    if not patterns:
        return

    x_cursor = 0
    gap = max(50, patterns[0].dimensions[0] * 0.05)
    colors_cycle = [CLR_PATTERN_FILL, "#E8F5E9", "#FCE4EC", "#EDE7F6"]

    for idx, fp in enumerate(patterns):
        xs = [p[0] + x_cursor for p in fp.outline]
        ys = [p[1]             for p in fp.outline]
        fill_c = colors_cycle[idx % len(colors_cycle)]
        ax.fill(xs, ys, color=fill_c, alpha=0.6)
        ax.plot(xs, ys, color=CLR_PATTERN, linewidth=1.5)

        for fold in fp.fold_lines:
            fx = [p[0] + x_cursor for p in fold]
            fy = [p[1]             for p in fold]
            ax.plot(fx, fy, color=CLR_FOLD, linewidth=0.8,
                    linestyle="--", dashes=(4, 2))

        # Label
        bx0 = min(xs); bx1 = max(xs)
        by1 = max(ys)
        ax.text((bx0+bx1)/2, by1 + (by1-min(ys))*0.05,
                fp.label, fontsize=6, ha="center", va="bottom",
                color=CLR_PATTERN)
        ax.text((bx0+bx1)/2, min(ys) - (by1-min(ys))*0.08,
                f"{fp.area_sqm:.4f} m²", fontsize=6, ha="center", va="top",
                color="#555555")

        x_cursor += fp.dimensions[0] + gap

    _auto_scale(ax)


# ── Drawing helpers ───────────────────────────────────────────────────────────

def _filled_rect(ax, x, y, w, h, alpha=0.3, color=CLR_FILL):
    rect = mpatches.FancyBboxPatch(
        (x, y), w, h,
        boxstyle="square,pad=0",
        facecolor=color, edgecolor=CLR_OUTLINE,
        linewidth=1.5, alpha=alpha + 0.1,
    )
    ax.add_patch(rect)
    # Also draw outline at full opacity
    xs = [x, x+w, x+w, x,   x]
    ys = [y, y,   y+h, y+h, y]
    ax.plot(xs, ys, color=CLR_OUTLINE, linewidth=1.5)


def _filled_poly(ax, pts, alpha=0.3, color=CLR_FILL):
    from matplotlib.patches import Polygon
    poly = Polygon(pts, closed=True, facecolor=color,
                   edgecolor=CLR_OUTLINE, linewidth=1.5, alpha=alpha+0.1)
    ax.add_patch(poly)
    xs = [p[0] for p in pts] + [pts[0][0]]
    ys = [p[1] for p in pts] + [pts[0][1]]
    ax.plot(xs, ys, color=CLR_OUTLINE, linewidth=1.5)


def _cline_h(ax, x1, x2, y):
    ax.axhline(y=y, xmin=0, xmax=1, color=CLR_CENTRE,
               linewidth=0.7, linestyle=(0, (8, 4, 2, 4)))


def _cline_v(ax, x, y1, y2):
    ax.plot([x, x], [y1, y2], color=CLR_CENTRE,
            linewidth=0.7, linestyle=(0, (8, 4, 2, 4)))


def _dim(ax, x1, y, x2, y2, label):
    mx = (x1 + x2) / 2
    ax.annotate("", xy=(x2, y), xytext=(x1, y),
                arrowprops=dict(arrowstyle="<->", color=CLR_DIM, lw=0.9))
    ax.text(mx, y - abs(y)*0.03 - 1, label, fontsize=6.5,
            ha="center", va="top", color=CLR_DIM)


def _dim_v(ax, x, y1, x2, y2, label):
    my = (y1 + y2) / 2
    ax.annotate("", xy=(x, y2), xytext=(x, y1),
                arrowprops=dict(arrowstyle="<->", color=CLR_DIM, lw=0.9))
    ax.text(x + abs(x)*0.03 + 1, my, label, fontsize=6.5,
            ha="left", va="center", color=CLR_DIM, rotation=90)


def _auto_scale(ax):
    ax.relim()
    ax.autoscale_view(scalex=True, scaley=True)
    # Add 15% margin
    xl = ax.get_xlim(); yl = ax.get_ylim()
    xm = (xl[1]-xl[0])*0.15; ym = (yl[1]-yl[0])*0.15
    ax.set_xlim(xl[0]-xm, xl[1]+xm)
    ax.set_ylim(yl[0]-ym, yl[1]+ym)
