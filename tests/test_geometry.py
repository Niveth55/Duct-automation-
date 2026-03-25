"""Tests for all geometry modules."""
import math
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from geometry.base       import CrossSection, Material, MATERIAL_DENSITY
from geometry.straight   import StraightDuct
from geometry.elbow      import Elbow
from geometry.transition import Transition
from geometry.tee        import Tee
from geometry.reducer    import Reducer


# ── StraightDuct ─────────────────────────────────────────────────────────────

class TestStraightDuct:
    def test_rect_perimeter(self):
        d = StraightDuct(section="Rectangular", width=600, height=300, length=2000)
        assert d.perimeter_mm == pytest.approx(1800)

    def test_circ_perimeter(self):
        d = StraightDuct(section="Circular", diameter=400, length=1000)
        assert d.perimeter_mm == pytest.approx(math.pi * 400)

    def test_rect_area(self):
        d = StraightDuct(width=600, height=300, length=1000)
        assert d.surface_area_sqm == pytest.approx(1.8)

    def test_circ_area(self):
        d = StraightDuct(section="Circular", diameter=400, length=1000)
        expected = (math.pi * 400 * 1000) / 1e6
        assert d.surface_area_sqm == pytest.approx(expected)

    def test_weight_positive(self):
        d = StraightDuct(width=400, height=200, length=2000)
        assert d.weight_kg > 0

    def test_rect_flat_pattern_one_sheet(self):
        d = StraightDuct(width=400, height=200, length=1000)
        fps = d.flat_patterns()
        assert len(fps) == 1
        assert fps[0].area_sqm > 0

    def test_circ_flat_pattern_one_sheet(self):
        d = StraightDuct(section="Circular", diameter=315, length=1000)
        fps = d.flat_patterns()
        assert len(fps) == 1
        # Flat pattern W ≈ π × D
        assert fps[0].dimensions[0] == pytest.approx(math.pi * 315, rel=1e-3)

    def test_serialise_roundtrip(self):
        d = StraightDuct(width=500, height=250, length=3000,
                         material="Aluminium", thickness=1.2, tag="D-99")
        d2 = StraightDuct.from_dict(d.to_dict())
        assert d2.width == 500
        assert d2.material == "Aluminium"
        assert d2.tag == "D-99"


# ── Elbow ─────────────────────────────────────────────────────────────────────

class TestElbow:
    def test_auto_radius(self):
        e = Elbow(section="Rectangular", width=400, height=200, angle=90)
        assert e.radius_cl == pytest.approx(1.5 * 400)

    def test_throat_heel(self):
        e = Elbow(width=400, height=200, angle=90, radius_cl=600)
        assert e.throat_radius == pytest.approx(400)
        assert e.heel_radius   == pytest.approx(800)

    def test_area_positive(self):
        e = Elbow(width=400, height=200, angle=90)
        assert e.surface_area_sqm > 0

    def test_circular_flat_pattern(self):
        e = Elbow(section="Circular", width=315, angle=90)
        fps = e.flat_patterns()
        assert len(fps) == 1
        assert fps[0].area_sqm > 0

    def test_rect_radius_flat_patterns_4_pieces(self):
        e = Elbow(section="Rectangular", width=400, height=200,
                  angle=90, elbow_type="Radius")
        fps = e.flat_patterns()
        assert len(fps) == 4    # 2 cheeks + outer + inner

    def test_mitered_flat_patterns(self):
        e = Elbow(width=400, height=200, angle=90, elbow_type="Mitered", n_pieces=3)
        fps = e.flat_patterns()
        assert len(fps) == 3

    def test_45_deg_elbow(self):
        e = Elbow(width=300, height=150, angle=45)
        assert e.surface_area_sqm > 0
        assert e.cl_arc_length == pytest.approx(e.radius_cl * math.pi / 4, rel=1e-3)

    def test_serialise_roundtrip(self):
        e = Elbow(width=400, height=200, angle=90, elbow_type="Radius", n_pieces=3)
        e2 = Elbow.from_dict(e.to_dict())
        assert e2.angle == 90
        assert e2.elbow_type == "Radius"


# ── Transition ────────────────────────────────────────────────────────────────

class TestTransition:
    def test_rect_rect_area_positive(self):
        t = Transition(inlet_w=600, inlet_h=400, outlet_w=400, outlet_h=300, length=500)
        assert t.surface_area_sqm > 0

    def test_rect_circle_area_positive(self):
        t = Transition(inlet_w=600, inlet_h=400, outlet_dia=315,
                       length=500, transition_type="Rect-Circle")
        assert t.surface_area_sqm > 0

    def test_rect_rect_flat_4_panels(self):
        t = Transition(inlet_w=600, inlet_h=400, outlet_w=400, outlet_h=300, length=500)
        fps = t.flat_patterns()
        assert len(fps) == 4

    def test_rect_circle_flat_patterns(self):
        t = Transition(inlet_w=600, inlet_h=400, outlet_dia=315,
                       length=500, transition_type="Rect-Circle")
        fps = t.flat_patterns()
        assert len(fps) > 0

    def test_weight_positive(self):
        t = Transition(inlet_w=600, inlet_h=400, outlet_w=400, outlet_h=300, length=500)
        assert t.weight_kg > 0

    def test_serialise_roundtrip(self):
        t = Transition(inlet_w=600, inlet_h=400, outlet_w=400, outlet_h=300, length=500)
        t2 = Transition.from_dict(t.to_dict())
        assert t2.inlet_w == 600
        assert t2.length == 500


# ── Tee ───────────────────────────────────────────────────────────────────────

class TestTee:
    def test_rect_area_positive(self):
        t = Tee(main_w=600, main_h=300, branch_w=300, branch_h=250)
        assert t.surface_area_sqm > 0

    def test_circ_area_positive(self):
        t = Tee(section="Circular", main_dia=400, branch_dia=250)
        assert t.surface_area_sqm > 0

    def test_rect_flat_patterns_4(self):
        t = Tee(main_w=600, main_h=300, branch_w=300, branch_h=250)
        fps = t.flat_patterns()
        assert len(fps) == 4

    def test_circ_flat_patterns_2(self):
        t = Tee(section="Circular", main_dia=400, branch_dia=250)
        fps = t.flat_patterns()
        assert len(fps) == 2

    def test_weight_positive(self):
        t = Tee(main_w=600, main_h=300, branch_w=300, branch_h=250)
        assert t.weight_kg > 0

    def test_serialise_roundtrip(self):
        t = Tee(main_w=600, main_h=300, branch_w=300, branch_h=250, branch_angle=90)
        t2 = Tee.from_dict(t.to_dict())
        assert t2.main_w == 600
        assert t2.branch_angle == 90


# ── Reducer ───────────────────────────────────────────────────────────────────

class TestReducer:
    def test_circ_area(self):
        r = Reducer(section="Circular", inlet_dia=400, outlet_dia=250, length=400)
        r1, r2 = 200, 125
        slant = math.sqrt(400**2 + (r1 - r2)**2)
        expected = math.pi * (r1 + r2) * slant / 1e6
        assert r.surface_area_sqm == pytest.approx(expected, rel=1e-3)

    def test_rect_area_positive(self):
        r = Reducer(inlet_w=600, inlet_h=400, outlet_w=400, outlet_h=300, length=400)
        assert r.surface_area_sqm > 0

    def test_concentric_cone_flat(self):
        r = Reducer(section="Circular", inlet_dia=400, outlet_dia=250, length=400)
        fps = r.flat_patterns()
        assert len(fps) == 1
        assert fps[0].area_sqm > 0

    def test_eccentric_cone_flat_12_strips(self):
        r = Reducer(section="Circular", inlet_dia=400, outlet_dia=250,
                    length=400, reducer_type="Eccentric")
        fps = r.flat_patterns()
        assert len(fps) == 12

    def test_rect_flat_4_panels(self):
        r = Reducer(inlet_w=600, inlet_h=400, outlet_w=400, outlet_h=300, length=400)
        fps = r.flat_patterns()
        assert len(fps) == 4

    def test_weight_positive(self):
        r = Reducer(inlet_w=600, inlet_h=400, outlet_w=400, outlet_h=300, length=400)
        assert r.weight_kg > 0

    def test_serialise_roundtrip(self):
        r = Reducer(inlet_w=600, inlet_h=400, outlet_w=400, outlet_h=300,
                    length=400, reducer_type="Symmetric")
        r2 = Reducer.from_dict(r.to_dict())
        assert r2.inlet_w == 600
        assert r2.reducer_type == "Symmetric"


# ── geometry factory from_dict ────────────────────────────────────────────────

class TestGeometryFactory:
    def test_from_dict_straight(self):
        from geometry import from_dict
        d = StraightDuct(width=400, height=200, length=1000).to_dict()
        comp = from_dict(d)
        assert isinstance(comp, StraightDuct)

    def test_from_dict_elbow(self):
        from geometry import from_dict
        d = Elbow(width=400, height=200, angle=90).to_dict()
        assert isinstance(from_dict(d), Elbow)

    def test_from_dict_unknown_raises(self):
        from geometry import from_dict
        with pytest.raises(ValueError, match="Unknown"):
            from_dict({"type": "Hexagon"})
