"""
AutoCAD layer management for duct drawings.
"""

import logging
logger = logging.getLogger(__name__)

# Layer definitions: name -> (color_index, lineweight_mm*100, description)
LAYER_DEFS = {
    "DUCT-SUPPLY":        (1,  25,  "Supply air ducts"),
    "DUCT-RETURN":        (3,  25,  "Return air ducts"),
    "DUCT-EXHAUST":       (6,  25,  "Exhaust air ducts"),
    "DUCT-FRESH":         (4,  25,  "Fresh air ducts"),
    "DUCT-FITTINGS":      (2,  18,  "Duct fittings"),
    "DUCT-INSULATION":    (8,  13,  "Duct insulation outline"),
    "DUCT-DIMENSIONS":    (7,   9,  "Dimension annotations"),
    "DUCT-TEXT":          (7,   9,  "Text labels and tags"),
    "DUCT-CENTERLINE":    (8,   9,  "Centrelines"),
    "DUCT-HATCH":         (9,   9,  "Section hatching"),
    "TITLEBLOCK":         (7,  18,  "Drawing title block"),
}

# AutoCAD color indices
ACI_RED    = 1
ACI_YELLOW = 2
ACI_GREEN  = 3
ACI_CYAN   = 4
ACI_BLUE   = 5
ACI_MAGENTA = 6
ACI_WHITE  = 7
ACI_GREY   = 8
ACI_LTGREY = 9


def setup_layers(doc):
    """Create all required layers in the AutoCAD document."""
    layers = doc.Layers
    for name, (color, lw, _desc) in LAYER_DEFS.items():
        try:
            try:
                layer = layers.Item(name)
            except Exception:
                layer = layers.Add(name)
            layer.Color = color
            layer.LineWeight = lw
        except Exception as exc:
            logger.warning("Could not set up layer '%s': %s", name, exc)


def set_entity_layer(entity, layer_name: str):
    """Assign an entity to a layer."""
    try:
        entity.Layer = layer_name
    except Exception as exc:
        logger.warning("Could not set layer on entity: %s", exc)
