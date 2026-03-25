from .base import (
    DuctType, CrossSection, Material, MATERIAL_DENSITY,
    FlatPattern, DuctGeometry, Point2D, Point3D, Polyline2D,
)
from .straight    import StraightDuct
from .elbow       import Elbow
from .transition  import Transition
from .tee         import Tee
from .reducer     import Reducer

__all__ = [
    "DuctType", "CrossSection", "Material", "MATERIAL_DENSITY",
    "FlatPattern", "DuctGeometry",
    "StraightDuct", "Elbow", "Transition", "Tee", "Reducer",
]


def from_dict(d: dict) -> DuctGeometry:
    """Deserialise any geometry component from a dict."""
    t = d.get("type", "")
    mapping = {
        "StraightDuct": StraightDuct,
        "Elbow":        Elbow,
        "Transition":   Transition,
        "Tee":          Tee,
        "Reducer":      Reducer,
    }
    cls = mapping.get(t)
    if cls is None:
        raise ValueError(f"Unknown geometry type: {t!r}")
    return cls.from_dict(d)
