"""
Parses duct layout from JSON/YAML config files into DuctSystem objects.

JSON format example:
{
  "project_name": "Office Level 3",
  "project_number": "P-2025-001",
  "drawn_by": "Engineer A",
  "date": "2025-01-01",
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
          "length": 3000,
          "start": {"x": 0, "y": 0},
          "angle": 0
        },
        {
          "type": "round",
          "tag": "D-02",
          "diameter": 250,
          "length": 2000,
          "start": {"x": 3000, "y": 0},
          "angle": 0
        }
      ],
      "fittings": [
        {
          "type": "ELBOW_90",
          "shape": "rectangular",
          "tag": "F-01",
          "width": 600,
          "height": 300,
          "position": {"x": 3000, "y": 0},
          "angle": 0
        }
      ]
    }
  ]
}
"""

import json
from pathlib import Path
from typing import Union

from .models import (
    DuctSystem, DuctRun, RectangularDuct, RoundDuct, OvalDuct,
    Fitting, FittingType, DuctShape, Material, Point2D,
)


def _parse_point(d: dict) -> Point2D:
    return Point2D(x=float(d.get("x", 0)), y=float(d.get("y", 0)))


def _parse_material(s: str) -> Material:
    mapping = {
        "galvanized": Material.GALVANIZED_STEEL,
        "galvanized_steel": Material.GALVANIZED_STEEL,
        "stainless": Material.STAINLESS_STEEL,
        "stainless_steel": Material.STAINLESS_STEEL,
        "aluminum": Material.ALUMINUM,
        "flexible": Material.FLEXIBLE,
    }
    return mapping.get(s.lower().replace(" ", "_"), Material.GALVANIZED_STEEL)


def _parse_section(d: dict):
    section_type = d.get("type", "rectangular").lower()
    material = _parse_material(d.get("material", "galvanized"))
    start = _parse_point(d.get("start", {"x": 0, "y": 0}))

    if section_type == "rectangular":
        return RectangularDuct(
            width=float(d["width"]),
            height=float(d["height"]),
            length=float(d["length"]),
            start=start,
            angle=float(d.get("angle", 0)),
            material=material,
            gauge=float(d.get("gauge", 0.8)),
            tag=d.get("tag", ""),
        )
    elif section_type == "round":
        return RoundDuct(
            diameter=float(d["diameter"]),
            length=float(d["length"]),
            start=start,
            angle=float(d.get("angle", 0)),
            material=material,
            gauge=float(d.get("gauge", 0.6)),
            tag=d.get("tag", ""),
        )
    elif section_type == "oval":
        return OvalDuct(
            major=float(d["major"]),
            minor=float(d["minor"]),
            length=float(d["length"]),
            start=start,
            angle=float(d.get("angle", 0)),
            material=material,
            gauge=float(d.get("gauge", 0.6)),
            tag=d.get("tag", ""),
        )
    else:
        raise ValueError(f"Unknown duct section type: {section_type}")


def _parse_fitting(d: dict) -> Fitting:
    fitting_type_str = d.get("type", "ELBOW_90").upper()
    try:
        fitting_type = FittingType[fitting_type_str]
    except KeyError:
        raise ValueError(f"Unknown fitting type: {fitting_type_str}")

    shape_str = d.get("shape", "rectangular").lower()
    shape_map = {
        "rectangular": DuctShape.RECTANGULAR,
        "round": DuctShape.ROUND,
        "oval": DuctShape.OVAL,
    }
    shape = shape_map.get(shape_str, DuctShape.RECTANGULAR)
    material = _parse_material(d.get("material", "galvanized"))
    position = _parse_point(d.get("position", {"x": 0, "y": 0}))

    return Fitting(
        fitting_type=fitting_type,
        shape=shape,
        width=float(d.get("width", 0)),
        height=float(d.get("height", 0)),
        diameter=float(d.get("diameter", 0)),
        outlet_width=float(d.get("outlet_width", 0)),
        outlet_height=float(d.get("outlet_height", 0)),
        outlet_diameter=float(d.get("outlet_diameter", 0)),
        position=position,
        angle=float(d.get("angle", 0)),
        material=material,
        tag=d.get("tag", ""),
        quantity=int(d.get("quantity", 1)),
    )


def parse_json(data: dict) -> DuctSystem:
    system = DuctSystem(
        project_name=data.get("project_name", "HVAC Duct System"),
        project_number=data.get("project_number", ""),
        drawn_by=data.get("drawn_by", ""),
        date=data.get("date", ""),
        scale=data.get("scale", "1:100"),
    )
    for run_data in data.get("runs", []):
        run = DuctRun(name=run_data.get("name", "Run"))
        for sec in run_data.get("sections", []):
            run.sections.append(_parse_section(sec))
        for fit in run_data.get("fittings", []):
            run.fittings.append(_parse_fitting(fit))
        system.runs.append(run)
    return system


def load_file(path: Union[str, Path]) -> DuctSystem:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Layout file not found: {path}")

    if path.suffix in (".yaml", ".yml"):
        try:
            import yaml
            with open(path) as f:
                data = yaml.safe_load(f)
        except ImportError:
            raise ImportError("PyYAML is required for YAML files: pip install pyyaml")
    elif path.suffix == ".json":
        with open(path) as f:
            data = json.load(f)
    else:
        raise ValueError(f"Unsupported file format: {path.suffix} (use .json or .yaml)")

    return parse_json(data)
