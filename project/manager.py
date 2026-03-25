"""
Project save / load manager.

A project file (*.dap.json) stores:
  - metadata (name, engineer, date)
  - a list of serialised DuctGeometry components
"""

from __future__ import annotations
import json
import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union

from geometry import DuctGeometry, from_dict as geometry_from_dict


@dataclass
class Project:
    name:        str = "Untitled Project"
    number:      str = ""
    engineer:    str = ""
    description: str = ""
    created:     str = ""
    modified:    str = ""
    components: List[DuctGeometry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name":        self.name,
            "number":      self.number,
            "engineer":    self.engineer,
            "description": self.description,
            "created":     self.created,
            "modified":    datetime.datetime.now().isoformat(timespec="seconds"),
            "components":  [c.to_dict() for c in self.components],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Project":
        components = []
        for cd in d.get("components", []):
            try:
                components.append(geometry_from_dict(cd))
            except Exception as exc:
                import warnings
                warnings.warn(f"Could not load component: {exc}")
        return cls(
            name=d.get("name", "Untitled"),
            number=d.get("number", ""),
            engineer=d.get("engineer", ""),
            description=d.get("description", ""),
            created=d.get("created", ""),
            modified=d.get("modified", ""),
            components=components,
        )


def save_project(project: Project, path: Union[str, Path]):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(project.to_dict(), f, indent=2)


def load_project(path: Union[str, Path]) -> Project:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Project file not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return Project.from_dict(data)


def new_project(name: str = "New Project", engineer: str = "") -> Project:
    now = datetime.datetime.now().isoformat(timespec="seconds")
    return Project(name=name, engineer=engineer, created=now, modified=now)
