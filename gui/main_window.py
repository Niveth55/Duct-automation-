"""
Main application window – Duct Automation GUI.

Layout (three-panel):
  LEFT   : Input panel  (duct type selector + parameter fields)
  CENTER : Preview panel (matplotlib multi-view canvas)
  RIGHT  : Output panel  (SMACNA validation, stats, generate buttons)
"""

from __future__ import annotations
import json
import logging
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Colour / style constants ──────────────────────────────────────────────────
BG_MAIN    = "#F5F5F5"
BG_PANEL   = "#FFFFFF"
BG_HEADER  = "#1565C0"
FG_HEADER  = "#FFFFFF"
BG_BTN_PRI = "#1976D2"
BG_BTN_SEC = "#43A047"
BG_BTN_WRN = "#E53935"
FG_BTN     = "#FFFFFF"
FONT_H1    = ("Segoe UI", 12, "bold")
FONT_H2    = ("Segoe UI", 10, "bold")
FONT_NORM  = ("Segoe UI", 9)
FONT_SMALL = ("Segoe UI", 8)
FONT_MONO  = ("Consolas", 9)

PAD = 6


class DuctAutomationApp(tk.Tk):
    """Root window for the Duct Automation application."""

    def __init__(self):
        super().__init__()
        self.title("Duct Automation System – AutoCAD & PP-BOM Generator")
        self.geometry("1400x860")
        self.minsize(1100, 700)
        self.configure(bg=BG_MAIN)

        # State
        self._component = None       # current DuctGeometry instance
        self._axes      = None
        self._canvas    = None
        self._toolbar   = None
        self._fig       = None
        self._project_path: Optional[Path] = None

        self._build_menu()
        self._build_ui()
        self._on_type_changed()      # populate fields for default type
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Menu bar ──────────────────────────────────────────────────────────────

    def _build_menu(self):
        mb = tk.Menu(self)
        self.config(menu=mb)

        fm = tk.Menu(mb, tearoff=0)
        fm.add_command(label="New Project",  command=self._new_project)
        fm.add_command(label="Open Project…", command=self._open_project)
        fm.add_command(label="Save Project",  command=self._save_project)
        fm.add_command(label="Save Project As…", command=self._save_project_as)
        fm.add_separator()
        fm.add_command(label="Exit", command=self._on_close)
        mb.add_cascade(label="File", menu=fm)

        em = tk.Menu(mb, tearoff=0)
        em.add_command(label="Generate DXF…", command=self._generate_dxf)
        em.add_command(label="Export BOM (Excel)…", command=self._export_bom_excel)
        em.add_command(label="Export BOM (CSV)…",   command=self._export_bom_csv)
        mb.add_cascade(label="Export", menu=em)

        hm = tk.Menu(mb, tearoff=0)
        hm.add_command(label="About", command=self._show_about)
        mb.add_cascade(label="Help", menu=hm)

    # ── Main UI layout ────────────────────────────────────────────────────────

    def _build_ui(self):
        # Header bar
        hdr = tk.Frame(self, bg=BG_HEADER, height=48)
        hdr.pack(side="top", fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="⚙  Duct Automation System",
                 font=("Segoe UI", 13, "bold"),
                 bg=BG_HEADER, fg=FG_HEADER).pack(side="left", padx=16, pady=8)
        tk.Label(hdr, text="SMACNA-Compliant HVAC Duct Designer",
                 font=("Segoe UI", 9), bg=BG_HEADER, fg="#90CAF9").pack(side="left")

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        sb = tk.Label(self, textvariable=self._status_var,
                      font=FONT_SMALL, bg="#ECEFF1", anchor="w",
                      bd=1, relief="sunken", padx=8)
        sb.pack(side="bottom", fill="x")

        # Three-panel body
        body = tk.PanedWindow(self, orient="horizontal",
                              sashwidth=5, sashrelief="raised",
                              bg=BG_MAIN)
        body.pack(fill="both", expand=True, padx=4, pady=4)

        left   = self._build_input_panel(body)
        center = self._build_preview_panel(body)
        right  = self._build_output_panel(body)

        body.add(left,   minsize=280, width=310)
        body.add(center, minsize=500)
        body.add(right,  minsize=280, width=320)

    # ── LEFT: Input panel ─────────────────────────────────────────────────────

    def _build_input_panel(self, parent) -> tk.Frame:
        frame = tk.Frame(parent, bg=BG_PANEL, bd=0)

        _section_label(frame, "COMPONENT TYPE")

        # Duct type dropdown
        types = ["Straight Duct", "Elbow", "Transition", "Tee / Branch", "Reducer"]
        self._type_var = tk.StringVar(value=types[0])
        cb = ttk.Combobox(frame, textvariable=self._type_var,
                          values=types, state="readonly", font=FONT_NORM)
        cb.pack(fill="x", padx=PAD, pady=(2, 6))
        cb.bind("<<ComboboxSelected>>", lambda _: self._on_type_changed())

        _section_label(frame, "PARAMETERS")

        # Scrollable parameter frame
        canvas_inner = tk.Canvas(frame, bg=BG_PANEL, highlightthickness=0)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=canvas_inner.yview)
        canvas_inner.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas_inner.pack(side="left", fill="both", expand=True)

        self._param_frame = tk.Frame(canvas_inner, bg=BG_PANEL)
        self._param_frame_id = canvas_inner.create_window(
            (0, 0), window=self._param_frame, anchor="nw")

        def _on_frame_configure(e):
            canvas_inner.configure(scrollregion=canvas_inner.bbox("all"))
        def _on_canvas_resize(e):
            canvas_inner.itemconfig(self._param_frame_id, width=e.width)

        self._param_frame.bind("<Configure>", _on_frame_configure)
        canvas_inner.bind("<Configure>", _on_canvas_resize)
        canvas_inner.bind_all("<MouseWheel>", lambda e: canvas_inner.yview_scroll(
            int(-1*(e.delta/120)), "units"))

        _section_label(frame, "MATERIAL")

        from geometry.base import Material
        mats = [Material.GALVANISED_STEEL, Material.STAINLESS_304,
                Material.STAINLESS_316, Material.ALUMINIUM, Material.MILD_STEEL]
        self._mat_var = tk.StringVar(value=mats[0])
        ttk.Combobox(frame, textvariable=self._mat_var,
                     values=mats, state="readonly",
                     font=FONT_NORM).pack(fill="x", padx=PAD, pady=2)

        _section_label(frame, "THICKNESS (mm)")
        self._thick_var = tk.StringVar(value="0.80")
        ttk.Entry(frame, textvariable=self._thick_var, font=FONT_NORM).pack(
            fill="x", padx=PAD, pady=2)

        _section_label(frame, "TAG")
        self._tag_var = tk.StringVar(value="")
        ttk.Entry(frame, textvariable=self._tag_var, font=FONT_NORM).pack(
            fill="x", padx=PAD, pady=2)

        # Buttons
        _btn(frame, "▶  Update Preview", BG_BTN_PRI, self._update_preview)
        _btn(frame, "⚡  Auto SMACNA Gauge", "#7B1FA2", self._auto_gauge)
        _btn(frame, "✦  Snap to Standard Size", "#0277BD", self._snap_standard)

        return frame

    # ── CENTER: Preview panel ─────────────────────────────────────────────────

    def _build_preview_panel(self, parent) -> tk.Frame:
        frame = tk.Frame(parent, bg=BG_MAIN)
        _section_label(frame, "2D MULTI-VIEW PREVIEW  (Plan / Elevation / Section / Flat Pattern)")

        try:
            from gui.preview import build_preview_canvas
            self._canvas, self._toolbar, self._fig, self._axes = \
                build_preview_canvas(frame, figsize=(10, 6.5))
            self._toolbar.pack(side="bottom", fill="x")
            self._canvas.get_tk_widget().pack(fill="both", expand=True)
        except Exception as exc:
            tk.Label(frame, text=f"Preview unavailable:\n{exc}",
                     font=FONT_NORM, bg=BG_MAIN, fg="red",
                     justify="center").pack(expand=True)
            logger.warning("Preview panel failed: %s", exc)

        return frame

    # ── RIGHT: Output panel ───────────────────────────────────────────────────

    def _build_output_panel(self, parent) -> tk.Frame:
        frame = tk.Frame(parent, bg=BG_PANEL, bd=0)

        _section_label(frame, "SMACNA VALIDATION")
        self._validation_box = tk.Text(
            frame, height=6, font=FONT_MONO, wrap="word",
            bg="#FAFAFA", relief="sunken", bd=1, state="disabled",
            fg="#333333",
        )
        self._validation_box.pack(fill="x", padx=PAD, pady=4)

        _section_label(frame, "COMPONENT STATISTICS")
        self._stats_box = tk.Text(
            frame, height=10, font=FONT_MONO, wrap="word",
            bg="#FAFAFA", relief="sunken", bd=1, state="disabled",
        )
        self._stats_box.pack(fill="x", padx=PAD, pady=4)

        _section_label(frame, "GENERATE OUTPUTS")
        _btn(frame, "📐  Generate DXF Drawing", BG_BTN_PRI, self._generate_dxf)
        _btn(frame, "📊  Export BOM to Excel",  BG_BTN_SEC, self._export_bom_excel)
        _btn(frame, "📄  Export BOM to CSV",    "#558B2F",  self._export_bom_csv)

        _section_label(frame, "LOG")
        self._log_box = tk.Text(
            frame, height=10, font=("Consolas", 8), wrap="word",
            bg="#263238", fg="#B2DFDB", bd=1, state="disabled",
        )
        vsb_log = ttk.Scrollbar(frame, orient="vertical",
                                 command=self._log_box.yview)
        self._log_box.configure(yscrollcommand=vsb_log.set)
        vsb_log.pack(side="right", fill="y", padx=(0, PAD))
        self._log_box.pack(fill="both", expand=True, padx=(PAD, 0), pady=4)

        _btn(frame, "🗑  Clear Log", "#546E7A", self._clear_log)

        # Attach GUI log handler
        handler = _GuiLogHandler(self._log_box)
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)

        return frame

    # ── Parameter field builder ───────────────────────────────────────────────

    _FIELD_DEFS = {
        "Straight Duct": [
            ("section",   "Section",       "combo",  ["Rectangular", "Circular"]),
            ("width",     "Width (mm)",    "float",  "400"),
            ("height",    "Height (mm)",   "float",  "200"),
            ("diameter",  "Diameter (mm)", "float",  "315"),
            ("length",    "Length (mm)",   "float",  "1000"),
        ],
        "Elbow": [
            ("section",    "Section",        "combo", ["Rectangular", "Circular"]),
            ("width",      "Width/Dia (mm)", "float", "400"),
            ("height",     "Height (mm)",    "float", "200"),
            ("angle",      "Angle (°)",      "float", "90"),
            ("elbow_type", "Elbow Type",     "combo", ["Radius", "Mitered"]),
            ("radius_cl",  "CL Radius (mm) [0=auto]", "float", "0"),
            ("n_pieces",   "Pieces (mitered)", "int", "3"),
        ],
        "Transition": [
            ("transition_type", "Type",        "combo", ["Rect-Rect", "Rect-Circle"]),
            ("inlet_w",   "Inlet W (mm)",      "float", "600"),
            ("inlet_h",   "Inlet H (mm)",      "float", "400"),
            ("outlet_w",  "Outlet W (mm)",     "float", "400"),
            ("outlet_h",  "Outlet H (mm)",     "float", "300"),
            ("outlet_dia","Outlet Dia (mm)",   "float", "315"),
            ("length",    "Length (mm)",       "float", "500"),
            ("offset_x",  "Offset X (mm)",    "float", "0"),
            ("offset_y",  "Offset Y (mm)",    "float", "0"),
        ],
        "Tee / Branch": [
            ("section",      "Section",          "combo", ["Rectangular", "Circular"]),
            ("main_w",       "Main W (mm)",      "float", "600"),
            ("main_h",       "Main H (mm)",      "float", "300"),
            ("branch_w",     "Branch W (mm)",    "float", "300"),
            ("branch_h",     "Branch H (mm)",    "float", "250"),
            ("main_dia",     "Main Dia (mm)",    "float", "400"),
            ("branch_dia",   "Branch Dia (mm)",  "float", "250"),
            ("branch_angle", "Branch Angle (°)", "float", "90"),
            ("neck_length",  "Neck Length (mm)", "float", "150"),
        ],
        "Reducer": [
            ("section",       "Section",          "combo", ["Rectangular", "Circular"]),
            ("reducer_type",  "Reducer Type",     "combo", ["Symmetric", "Eccentric"]),
            ("inlet_w",       "Inlet W (mm)",     "float", "600"),
            ("inlet_h",       "Inlet H (mm)",     "float", "400"),
            ("outlet_w",      "Outlet W (mm)",    "float", "400"),
            ("outlet_h",      "Outlet H (mm)",    "float", "300"),
            ("inlet_dia",     "Inlet Dia (mm)",   "float", "400"),
            ("outlet_dia",    "Outlet Dia (mm)",  "float", "250"),
            ("length",        "Length (mm)",      "float", "400"),
        ],
    }

    def _on_type_changed(self):
        for w in self._param_frame.winfo_children():
            w.destroy()
        self._field_vars = {}
        t = self._type_var.get()
        fields = self._FIELD_DEFS.get(t, [])
        for key, label, ftype, default in fields:
            tk.Label(self._param_frame, text=label, font=FONT_SMALL,
                     bg=BG_PANEL, anchor="w").pack(fill="x", padx=4, pady=(4, 0))
            if ftype == "combo":
                var = tk.StringVar(value=default[0])
                cb = ttk.Combobox(self._param_frame, textvariable=var,
                                  values=default, state="readonly", font=FONT_NORM)
                cb.pack(fill="x", padx=4, pady=(0, 2))
            else:
                var = tk.StringVar(value=str(default))
                ttk.Entry(self._param_frame, textvariable=var,
                          font=FONT_NORM).pack(fill="x", padx=4, pady=(0, 2))
            self._field_vars[key] = var
        self._update_preview()

    # ── Build component from current fields ───────────────────────────────────

    def _build_component(self):
        t    = self._type_var.get()
        mat  = self._mat_var.get()
        tag  = self._tag_var.get().strip()
        try:
            thick = float(self._thick_var.get())
        except ValueError:
            thick = 0.8

        def fv(key, cast=float, default=0):
            try:
                return cast(self._field_vars[key].get())
            except Exception:
                return default

        def sv(key, default=""):
            try:
                return self._field_vars[key].get()
            except Exception:
                return default

        from geometry.straight   import StraightDuct
        from geometry.elbow      import Elbow
        from geometry.transition import Transition
        from geometry.tee        import Tee
        from geometry.reducer    import Reducer
        from geometry.base       import CrossSection

        if t == "Straight Duct":
            return StraightDuct(
                section=sv("section", "Rectangular"),
                width=fv("width", default=400), height=fv("height", default=200),
                diameter=fv("diameter", default=315), length=fv("length", default=1000),
                material=mat, thickness=thick, tag=tag,
            )
        elif t == "Elbow":
            return Elbow(
                section=sv("section", "Rectangular"),
                width=fv("width", default=400), height=fv("height", default=200),
                angle=fv("angle", default=90),
                elbow_type=sv("elbow_type", "Radius"),
                radius_cl=fv("radius_cl", default=0),
                n_pieces=fv("n_pieces", cast=int, default=3),
                material=mat, thickness=thick, tag=tag,
            )
        elif t == "Transition":
            return Transition(
                transition_type=sv("transition_type", "Rect-Rect"),
                inlet_w=fv("inlet_w", default=600), inlet_h=fv("inlet_h", default=400),
                outlet_w=fv("outlet_w", default=400), outlet_h=fv("outlet_h", default=300),
                outlet_dia=fv("outlet_dia", default=315),
                length=fv("length", default=500),
                offset_x=fv("offset_x", default=0), offset_y=fv("offset_y", default=0),
                material=mat, thickness=thick, tag=tag,
            )
        elif t == "Tee / Branch":
            return Tee(
                section=sv("section", "Rectangular"),
                main_w=fv("main_w", default=600), main_h=fv("main_h", default=300),
                branch_w=fv("branch_w", default=300), branch_h=fv("branch_h", default=250),
                main_dia=fv("main_dia", default=400), branch_dia=fv("branch_dia", default=250),
                branch_angle=fv("branch_angle", default=90),
                neck_length=fv("neck_length", default=150),
                material=mat, thickness=thick, tag=tag,
            )
        elif t == "Reducer":
            return Reducer(
                section=sv("section", "Rectangular"),
                reducer_type=sv("reducer_type", "Symmetric"),
                inlet_w=fv("inlet_w", default=600), inlet_h=fv("inlet_h", default=400),
                outlet_w=fv("outlet_w", default=400), outlet_h=fv("outlet_h", default=300),
                inlet_dia=fv("inlet_dia", default=400), outlet_dia=fv("outlet_dia", default=250),
                length=fv("length", default=400),
                material=mat, thickness=thick, tag=tag,
            )

    # ── Preview update ────────────────────────────────────────────────────────

    def _update_preview(self):
        try:
            comp = self._build_component()
            if comp is None:
                return
            self._component = comp
        except Exception as exc:
            self._set_status(f"Build error: {exc}")
            logger.error("Build component error: %s", exc)
            return

        # Render preview
        if self._axes and self._canvas:
            try:
                from gui.preview import render_component
                render_component(self._axes, comp)
                self._canvas.draw()
            except Exception as exc:
                logger.warning("Render error: %s", exc)

        # Update stats
        self._update_stats(comp)
        self._run_validation(comp)
        self._set_status(f"Preview updated – {comp.duct_type}")

    def _update_stats(self, comp):
        from standards.smacna import (
            recommended_gauge_rect, recommended_gauge_round,
            seam_recommendation, joint_recommendation,
        )
        from geometry.straight import StraightDuct
        from geometry.base import CrossSection

        lines = []
        lines.append(f"Type:         {comp.duct_type}")
        lines.append(f"Material:     {comp.material}")
        lines.append(f"Thickness:    {comp.thickness:.2f} mm")
        lines.append(f"Surface Area: {comp.surface_area_sqm:.4f} m²")
        lines.append(f"Weight:       {comp.weight_kg:.3f} kg")

        if isinstance(comp, StraightDuct):
            if comp.section == CrossSection.CIRCULAR:
                g, t = recommended_gauge_round(comp.diameter)
            else:
                g, t = recommended_gauge_rect(comp.width)
            lines.append(f"Rec. Gauge:   {g}  ({t:.2f} mm)")
            lines.append(f"Seam:         {seam_recommendation(comp.width if comp.section!='Circular' else comp.diameter)}")
            lines.append(f"Joint:        {joint_recommendation(comp.width if comp.section!='Circular' else comp.diameter)}")

        fps = comp.flat_patterns()
        tot = sum(fp.area_sqm for fp in fps)
        lines.append(f"Flat Pattern: {len(fps)} sheet(s)  {tot:.4f} m²")

        _set_text(self._stats_box, "\n".join(lines))

    def _run_validation(self, comp):
        from standards.smacna import validate_duct
        from geometry.straight import StraightDuct
        from geometry.elbow import Elbow

        kwargs = dict(duct_type=comp.duct_type, thickness=comp.thickness)
        if isinstance(comp, StraightDuct):
            kwargs.update(width=comp.width, height=comp.height,
                          diameter=comp.diameter, length=comp.length)
        elif isinstance(comp, Elbow):
            kwargs.update(width=comp.width, height=comp.height,
                          angle=comp.angle, throat_radius=comp.throat_radius)

        errors = validate_duct(**kwargs)
        if errors:
            msg = "\n".join(errors)
            clr = "#B71C1C"
        else:
            msg = "✓ All SMACNA checks passed."
            clr = "#1B5E20"

        self._validation_box.config(state="normal", fg=clr)
        self._validation_box.delete("1.0", "end")
        self._validation_box.insert("1.0", msg)
        self._validation_box.config(state="disabled")

    # ── Auto gauge / snap to standard ────────────────────────────────────────

    def _auto_gauge(self):
        from standards.smacna import recommended_gauge_rect, recommended_gauge_round
        from geometry.straight import StraightDuct
        from geometry.base import CrossSection

        try:
            comp = self._build_component()
        except Exception:
            return

        if isinstance(comp, StraightDuct) and comp.section == CrossSection.CIRCULAR:
            _, t = recommended_gauge_round(comp.diameter)
        else:
            w = getattr(comp, "width", None) or getattr(comp, "inlet_w", 400)
            _, t = recommended_gauge_rect(w)

        self._thick_var.set(f"{t:.2f}")
        self._update_preview()
        self._set_status(f"Auto gauge set to {t:.2f} mm")

    def _snap_standard(self):
        from standards.smacna import nearest_standard_rect, nearest_standard_round
        from geometry.base import CrossSection

        t = self._type_var.get()
        try:
            section = self._field_vars.get("section", tk.StringVar(value="Rectangular")).get()
        except Exception:
            section = "Rectangular"

        if section == CrossSection.CIRCULAR:
            if "diameter" in self._field_vars:
                d = float(self._field_vars["diameter"].get() or 315)
                snapped = nearest_standard_round(d)
                self._field_vars["diameter"].set(str(snapped))
        else:
            keys = [(k, "width") for k in ("width", "inlet_w", "main_w") if k in self._field_vars]
            keys += [(k, "height") for k in ("height", "inlet_h", "main_h") if k in self._field_vars]
            w = float(self._field_vars.get("width", self._field_vars.get("inlet_w", tk.StringVar(value="400"))).get() or 400)
            h = float(self._field_vars.get("height", self._field_vars.get("inlet_h", tk.StringVar(value="200"))).get() or 200)
            sw, sh = nearest_standard_rect(w, h)
            for k, dim in [("width", sw), ("inlet_w", sw), ("main_w", sw),
                            ("height", sh), ("inlet_h", sh), ("main_h", sh)]:
                if k in self._field_vars:
                    self._field_vars[k].set(str(dim))

        self._update_preview()
        self._set_status("Snapped to nearest SMACNA standard size")

    # ── Generate DXF ──────────────────────────────────────────────────────────

    def _generate_dxf(self):
        comp = self._component
        if comp is None:
            try:
                comp = self._build_component()
                self._component = comp
            except Exception as exc:
                messagebox.showerror("Error", f"Build component first:\n{exc}")
                return

        path = filedialog.asksaveasfilename(
            title="Save DXF Drawing",
            defaultextension=".dxf",
            filetypes=[("DXF files", "*.dxf"), ("All", "*.*")],
            initialfile=f"{comp.tag or 'duct'}_drawing.dxf",
        )
        if not path:
            return

        self._set_status("Generating DXF…")
        def _worker():
            try:
                from drawing.dxf_writer import generate_dxf
                ok = generate_dxf(comp, path,
                                  title=str(comp.tag or comp.duct_type),
                                  drawn_by="Duct Automation",
                                  project_no="")
                if ok:
                    self.after(0, lambda: messagebox.showinfo("Done", f"DXF saved:\n{path}"))
                else:
                    self.after(0, lambda: messagebox.showwarning(
                        "Warning", "ezdxf not installed.\npip install ezdxf"))
            except Exception as exc:
                logger.exception("DXF error")
                self.after(0, lambda: messagebox.showerror("DXF Error", str(exc)))
            finally:
                self.after(0, lambda: self._set_status("Ready"))

        threading.Thread(target=_worker, daemon=True).start()

    # ── Export BOM ────────────────────────────────────────────────────────────

    def _export_bom_excel(self):
        self._export_bom(fmt="xlsx")

    def _export_bom_csv(self):
        self._export_bom(fmt="csv")

    def _export_bom(self, fmt: str):
        comp = self._component
        if comp is None:
            try:
                comp = self._build_component()
                self._component = comp
            except Exception as exc:
                messagebox.showerror("Error", str(exc))
                return

        ext  = f".{fmt}"
        ftyp = [("Excel", "*.xlsx")] if fmt == "xlsx" else [("CSV", "*.csv")]
        path = filedialog.asksaveasfilename(
            title=f"Export BOM ({fmt.upper()})",
            defaultextension=ext, filetypes=ftyp,
            initialfile=f"{comp.tag or 'duct'}_bom{ext}",
        )
        if not path:
            return

        def _worker():
            try:
                from bom.calculator import calculate_bom
                from bom.exporter import export_excel, export_csv
                bom = calculate_bom([comp])
                if fmt == "xlsx":
                    export_excel(bom, path)
                else:
                    export_csv(bom, path)
                self.after(0, lambda: messagebox.showinfo(
                    "Done", f"BOM exported:\n{path}\n\n"
                            f"Total Weight: {bom.total_weight_kg:.2f} kg\n"
                            f"Total Cost: ${bom.total_cost_usd:.2f}"))
            except Exception as exc:
                logger.exception("BOM export error")
                self.after(0, lambda: messagebox.showerror("BOM Error", str(exc)))
            finally:
                self.after(0, lambda: self._set_status("Ready"))

        self._set_status(f"Exporting BOM ({fmt.upper()})…")
        threading.Thread(target=_worker, daemon=True).start()

    # ── Project save / load ───────────────────────────────────────────────────

    def _new_project(self):
        self._project_path = None
        self._component = None
        self._type_var.set("Straight Duct")
        self._on_type_changed()
        self._set_status("New project")

    def _open_project(self):
        path = filedialog.askopenfilename(
            title="Open Project",
            filetypes=[("JSON", "*.json"), ("All", "*.*")],
        )
        if not path:
            return
        try:
            with open(path) as f:
                data = json.load(f)
            self._load_project_data(data)
            self._project_path = Path(path)
            self._set_status(f"Opened: {path}")
        except Exception as exc:
            messagebox.showerror("Open Error", str(exc))

    def _save_project(self):
        if self._project_path:
            self._do_save(self._project_path)
        else:
            self._save_project_as()

    def _save_project_as(self):
        path = filedialog.asksaveasfilename(
            title="Save Project As",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile="duct_project.json",
        )
        if path:
            self._project_path = Path(path)
            self._do_save(self._project_path)

    def _do_save(self, path: Path):
        try:
            data = self._collect_project_data()
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            self._set_status(f"Saved: {path}")
        except Exception as exc:
            messagebox.showerror("Save Error", str(exc))

    def _collect_project_data(self) -> dict:
        data = {
            "type": self._type_var.get(),
            "material": self._mat_var.get(),
            "thickness": self._thick_var.get(),
            "tag": self._tag_var.get(),
            "fields": {k: v.get() for k, v in self._field_vars.items()},
        }
        return data

    def _load_project_data(self, data: dict):
        self._type_var.set(data.get("type", "Straight Duct"))
        self._mat_var.set(data.get("material", "Galvanised Steel"))
        self._thick_var.set(data.get("thickness", "0.80"))
        self._tag_var.set(data.get("tag", ""))
        self._on_type_changed()
        for k, v in data.get("fields", {}).items():
            if k in self._field_vars:
                self._field_vars[k].set(v)
        self._update_preview()

    # ── Misc ──────────────────────────────────────────────────────────────────

    def _set_status(self, msg: str):
        self._status_var.set(msg)
        self.update_idletasks()

    def _clear_log(self):
        self._log_box.config(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.config(state="disabled")

    def _show_about(self):
        messagebox.showinfo(
            "About",
            "Duct Automation System\n"
            "Version 2.0\n\n"
            "Parametric HVAC duct designer with:\n"
            "• SMACNA-compliant geometry & gauges\n"
            "• Flat pattern development\n"
            "• DXF drawing generation (ezdxf)\n"
            "• Parts & Pieces BOM (Excel/CSV)\n\n"
            "Supports: Straight, Elbow, Transition, Tee, Reducer\n"
            "Materials: Galvanised Steel, Stainless, Aluminium\n"
        )

    def _on_close(self):
        try:
            if self._fig:
                import matplotlib.pyplot as plt
                plt.close(self._fig)
        except Exception:
            pass
        self.destroy()


# ── Widget helpers ────────────────────────────────────────────────────────────

def _section_label(parent, text: str):
    f = tk.Frame(parent, bg="#E3F2FD", bd=0)
    f.pack(fill="x", padx=0, pady=(8, 2))
    tk.Label(f, text=text, font=("Segoe UI", 8, "bold"),
             bg="#E3F2FD", fg="#1565C0",
             anchor="w", padx=6).pack(fill="x")


def _btn(parent, text: str, bg: str, command, pady=3):
    btn = tk.Button(
        parent, text=text, command=command,
        font=("Segoe UI", 9, "bold"),
        bg=bg, fg=FG_BTN, activebackground=bg,
        relief="flat", cursor="hand2",
        padx=10, pady=5,
    )
    btn.pack(fill="x", padx=PAD, pady=pady)
    btn.bind("<Enter>", lambda e: btn.config(bg=_lighten(bg)))
    btn.bind("<Leave>", lambda e: btn.config(bg=bg))
    return btn


def _lighten(hex_color: str) -> str:
    try:
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        r = min(255, r + 30); g = min(255, g + 30); b = min(255, b + 30)
        return f"#{r:02X}{g:02X}{b:02X}"
    except Exception:
        return hex_color


def _set_text(widget: tk.Text, text: str):
    widget.config(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", text)
    widget.config(state="disabled")


class _GuiLogHandler(logging.Handler):
    def __init__(self, widget: tk.Text):
        super().__init__()
        self._w = widget

    def emit(self, record):
        msg = self.format(record) + "\n"
        try:
            self._w.config(state="normal")
            self._w.insert("end", msg)
            self._w.see("end")
            self._w.config(state="disabled")
        except Exception:
            pass
