"""
Tkinter GUI for Duct Automation.

Provides a simple form to configure and run the duct drawing pipeline
without needing a terminal.
"""

import json
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


def launch_gui():
    """Launch the Tkinter GUI. Requires tkinter (part of stdlib)."""
    try:
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox, scrolledtext
    except ImportError:
        print("tkinter is not available in this Python environment.")
        return

    root = tk.Tk()
    root.title("Duct Automation – AutoCAD Generator & PP-BOM")
    root.geometry("800x620")
    root.resizable(True, True)

    # ---- Top frame: project info ----
    frm_top = ttk.LabelFrame(root, text="Project Settings", padding=8)
    frm_top.pack(fill="x", padx=10, pady=(10, 4))

    def lbl_entry(parent, row, label, default=""):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=2)
        var = tk.StringVar(value=default)
        ttk.Entry(parent, textvariable=var, width=40).grid(row=row, column=1, sticky="ew", padx=4, pady=2)
        return var

    var_layout   = lbl_entry(frm_top, 0, "Layout File (JSON/YAML):", "")
    var_output   = lbl_entry(frm_top, 1, "Output Directory:",       "./output")
    var_save_dwg = lbl_entry(frm_top, 2, "Save Drawing (.dwg):",    "")
    frm_top.columnconfigure(1, weight=1)

    def browse_layout():
        p = filedialog.askopenfilename(
            title="Select Layout File",
            filetypes=[("JSON files", "*.json"), ("YAML files", "*.yaml *.yml"), ("All", "*.*")],
        )
        if p:
            var_layout.set(p)

    def browse_output():
        p = filedialog.askdirectory(title="Select Output Directory")
        if p:
            var_output.set(p)

    def browse_dwg():
        p = filedialog.asksaveasfilename(
            title="Save AutoCAD Drawing",
            defaultextension=".dwg",
            filetypes=[("AutoCAD Drawing", "*.dwg")],
        )
        if p:
            var_save_dwg.set(p)

    ttk.Button(frm_top, text="Browse…", command=browse_layout).grid(row=0, column=2, padx=4)
    ttk.Button(frm_top, text="Browse…", command=browse_output).grid(row=1, column=2, padx=4)
    ttk.Button(frm_top, text="Browse…", command=browse_dwg).grid(row=2, column=2, padx=4)

    # ---- Options frame ----
    frm_opts = ttk.LabelFrame(root, text="Options", padding=8)
    frm_opts.pack(fill="x", padx=10, pady=4)

    var_dry_run     = tk.BooleanVar(value=True)
    var_export_bom  = tk.BooleanVar(value=True)
    var_xlsx        = tk.BooleanVar(value=True)
    var_csv         = tk.BooleanVar(value=True)
    var_hidden      = tk.BooleanVar(value=False)

    ttk.Checkbutton(frm_opts, text="Dry-run (simulation, no AutoCAD needed)",
                    variable=var_dry_run).grid(row=0, column=0, sticky="w", padx=4)
    ttk.Checkbutton(frm_opts, text="Hidden AutoCAD window",
                    variable=var_hidden).grid(row=0, column=1, sticky="w", padx=4)
    ttk.Checkbutton(frm_opts, text="Export BOM",
                    variable=var_export_bom).grid(row=1, column=0, sticky="w", padx=4)
    ttk.Checkbutton(frm_opts, text="Excel (.xlsx)", variable=var_xlsx).grid(row=1, column=1, sticky="w", padx=4)
    ttk.Checkbutton(frm_opts, text="CSV (.csv)",    variable=var_csv).grid( row=1, column=2, sticky="w", padx=4)

    # ---- JSON editor ----
    frm_editor = ttk.LabelFrame(root, text="Layout JSON (edit directly or load from file)", padding=8)
    frm_editor.pack(fill="both", expand=True, padx=10, pady=4)

    json_editor = scrolledtext.ScrolledText(frm_editor, height=12, font=("Consolas", 10))
    json_editor.pack(fill="both", expand=True)
    json_editor.insert("1.0", _EXAMPLE_JSON_STUB)

    def load_json_from_file(*_):
        path = var_layout.get().strip()
        if not path:
            return
        try:
            with open(path) as f:
                content = f.read()
            json_editor.delete("1.0", "end")
            json_editor.insert("1.0", content)
        except Exception as exc:
            messagebox.showerror("Load Error", str(exc))

    var_layout.trace_add("write", load_json_from_file)

    # ---- Log output ----
    frm_log = ttk.LabelFrame(root, text="Log", padding=4)
    frm_log.pack(fill="x", padx=10, pady=4)
    log_box = scrolledtext.ScrolledText(frm_log, height=8, state="disabled",
                                        font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4")
    log_box.pack(fill="x")

    class _GuiLogHandler(logging.Handler):
        def emit(self, record):
            msg = self.format(record) + "\n"
            log_box.config(state="normal")
            log_box.insert("end", msg)
            log_box.see("end")
            log_box.config(state="disabled")

    handler = _GuiLogHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)

    # ---- Action buttons ----
    frm_btns = ttk.Frame(root, padding=6)
    frm_btns.pack(fill="x", padx=10, pady=(0, 8))

    def _run():
        from .core import run, parse_json
        import json as _json

        try:
            layout_text = json_editor.get("1.0", "end").strip()
            layout_data = _json.loads(layout_text)
        except _json.JSONDecodeError as exc:
            messagebox.showerror("JSON Error", f"Invalid JSON in editor:\n{exc}")
            return

        formats = []
        if var_xlsx.get():
            formats.append("xlsx")
        if var_csv.get():
            formats.append("csv")

        def _worker():
            try:
                result = run(
                    layout=layout_data,
                    output_dir=var_output.get() or "./output",
                    acad_visible=not var_hidden.get(),
                    save_dwg=var_save_dwg.get() or None,
                    export_bom=var_export_bom.get(),
                    bom_formats=tuple(formats),
                    dry_run=var_dry_run.get(),
                )
                paths = result.get("bom_paths", {})
                if paths:
                    msg = "BOM files:\n" + "\n".join(f"  {p}" for p in paths.values())
                else:
                    msg = "Drawing complete (no BOM exported)."
                root.after(0, lambda: messagebox.showinfo("Done", msg))
            except Exception as exc:
                logger.exception("Run failed")
                root.after(0, lambda: messagebox.showerror("Error", str(exc)))

        threading.Thread(target=_worker, daemon=True).start()

    def _create_example():
        from .cli import _write_example
        p = filedialog.asksaveasfilename(
            title="Save Example Layout",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
        )
        if p:
            _write_example(p)
            var_layout.set(p)
            load_json_from_file()

    ttk.Button(frm_btns, text="▶  Run", command=_run,
               style="Accent.TButton").pack(side="left", padx=4)
    ttk.Button(frm_btns, text="Create Example Layout", command=_create_example).pack(side="left", padx=4)
    ttk.Button(frm_btns, text="Clear Log", command=lambda: (
        log_box.config(state="normal"), log_box.delete("1.0", "end"), log_box.config(state="disabled")
    )).pack(side="right", padx=4)

    root.mainloop()


_EXAMPLE_JSON_STUB = """{
  "project_name": "My HVAC Project",
  "project_number": "P-001",
  "drawn_by": "Your Name",
  "date": "2025-01-15",
  "scale": "1:100",
  "runs": [
    {
      "name": "Supply Main",
      "sections": [
        {
          "type": "rectangular",
          "tag": "D-01",
          "width": 600,
          "height": 300,
          "length": 4000,
          "start": {"x": 0, "y": 0},
          "angle": 0
        }
      ],
      "fittings": []
    }
  ]
}
"""
