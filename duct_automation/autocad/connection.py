"""
AutoCAD COM connection manager.

Connects to a running AutoCAD instance (or launches one) via Windows COM.
Falls back to a simulation/mock mode on non-Windows platforms for testing.
"""

import platform
import logging

logger = logging.getLogger(__name__)

_IS_WINDOWS = platform.system() == "Windows"


class AutoCADConnection:
    """
    Wraps the AutoCAD COM application object.

    Usage:
        conn = AutoCADConnection()
        conn.connect()
        acad = conn.app
        doc  = conn.doc
        msp  = conn.mspace   # model space
    """

    def __init__(self, visible: bool = True, create_new: bool = False):
        self.visible = visible
        self.create_new = create_new
        self._app = None
        self._doc = None
        self._mspace = None
        self._simulated = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def connect(self):
        if _IS_WINDOWS:
            self._connect_windows()
        else:
            logger.warning("Non-Windows platform – using simulation mode.")
            self._connect_simulated()

    def disconnect(self):
        self._app = None
        self._doc = None
        self._mspace = None

    @property
    def app(self):
        self._require_connected()
        return self._app

    @property
    def doc(self):
        self._require_connected()
        return self._doc

    @property
    def mspace(self):
        self._require_connected()
        return self._mspace

    @property
    def is_simulated(self) -> bool:
        return self._simulated

    def zoom_extents(self):
        if not self._simulated:
            try:
                self._app.ZoomExtents()
            except Exception as exc:
                logger.warning("ZoomExtents failed: %s", exc)

    def save(self, path: str = ""):
        if not self._simulated:
            if path:
                self._doc.SaveAs(path)
            else:
                self._doc.Save()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect_windows(self):
        try:
            import win32com.client as win32
            import pythoncom
            pythoncom.CoInitialize()

            prog_id = "AutoCAD.Application"
            if self.create_new:
                self._app = win32.Dispatch(prog_id)
            else:
                try:
                    self._app = win32.GetActiveObject(prog_id)
                    logger.info("Connected to existing AutoCAD instance.")
                except Exception:
                    logger.info("No running AutoCAD found – launching new instance.")
                    self._app = win32.Dispatch(prog_id)

            self._app.Visible = self.visible
            self._doc = self._app.ActiveDocument
            self._mspace = self._doc.ModelSpace
            self._simulated = False
        except ImportError:
            logger.warning("pywin32 not installed – falling back to simulation.")
            self._connect_simulated()
        except Exception as exc:
            logger.error("AutoCAD connection error: %s", exc)
            raise

    def _connect_simulated(self):
        self._app = _SimApp()
        self._doc = _SimDoc()
        self._mspace = _SimModelSpace()
        self._simulated = True

    def _require_connected(self):
        if self._app is None:
            raise RuntimeError("Not connected. Call connect() first.")


# ---------------------------------------------------------------------------
# Simulation stubs – used when AutoCAD / pywin32 is unavailable
# ---------------------------------------------------------------------------

class _SimModelSpace:
    """Records all draw calls for offline testing."""

    def __init__(self):
        self.entities = []

    def AddLine(self, start, end):
        entity = _SimEntity("Line", {"start": start, "end": end})
        self.entities.append(entity)
        return entity

    def AddLightWeightPolyline(self, pts):
        entity = _SimEntity("LWPolyline", {"points": pts})
        self.entities.append(entity)
        return entity

    def AddCircle(self, center, radius):
        entity = _SimEntity("Circle", {"center": center, "radius": radius})
        self.entities.append(entity)
        return entity

    def AddArc(self, center, radius, start_angle, end_angle):
        entity = _SimEntity("Arc", {
            "center": center, "radius": radius,
            "start_angle": start_angle, "end_angle": end_angle,
        })
        self.entities.append(entity)
        return entity

    def AddText(self, text, insert, height):
        entity = _SimEntity("Text", {"text": text, "insert": insert, "height": height})
        self.entities.append(entity)
        return entity

    def AddMText(self, insert, width, text):
        entity = _SimEntity("MText", {"text": text, "insert": insert, "width": width})
        self.entities.append(entity)
        return entity

    def AddHatch(self, pattern_type, pattern_name, associativity):
        entity = _SimEntity("Hatch", {
            "pattern_type": pattern_type,
            "pattern_name": pattern_name,
        })
        self.entities.append(entity)
        return entity

    def AddDimAligned(self, ext1, ext2, dim_line, text):
        entity = _SimEntity("DimAligned", {
            "ext1": ext1, "ext2": ext2,
            "dim_line": dim_line, "text": text,
        })
        self.entities.append(entity)
        return entity

    def AddDimRotated(self, ext1, ext2, dim_line, rotation, text):
        entity = _SimEntity("DimRotated", {
            "ext1": ext1, "ext2": ext2, "rotation": rotation,
        })
        self.entities.append(entity)
        return entity


class _SimEntity:
    def __init__(self, kind: str, props: dict):
        self.kind = kind
        self.props = props
        self.Layer = "0"
        self.Color = 256  # BYLAYER
        self.Linetype = "BYLAYER"
        self.LineWeight = -1  # BYLAYER

    def Update(self):
        pass

    def AppendOuterLoop(self, loop):
        pass

    def Evaluate(self):
        pass

    def __repr__(self):
        return f"<SimEntity {self.kind} {self.props}>"


class _SimDoc:
    def __init__(self):
        self.Layers = _SimLayers()
        self.Linetypes = _SimLinetypes()

    def Save(self):
        logger.info("[SIM] Document saved.")

    def SaveAs(self, path):
        logger.info("[SIM] Document saved as: %s", path)


class _SimApp:
    def __init__(self):
        self.Visible = True

    def ZoomExtents(self):
        logger.info("[SIM] ZoomExtents called.")


class _SimLayers:
    def __init__(self):
        self._layers = {}

    def Add(self, name):
        layer = _SimLayer(name)
        self._layers[name] = layer
        return layer

    def Item(self, name):
        if name in self._layers:
            return self._layers[name]
        return self.Add(name)

    def __iter__(self):
        return iter(self._layers.values())


class _SimLayer:
    def __init__(self, name):
        self.Name = name
        self.Color = 7
        self.LineWeight = -1
        self.Linetype = "Continuous"
        self.LayerOn = True
        self.Freeze = False


class _SimLinetypes:
    def Load(self, name, file):
        pass
