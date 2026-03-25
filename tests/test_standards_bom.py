"""Tests for SMACNA standards and BOM calculator."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from standards.smacna import (
    recommended_gauge_rect, recommended_gauge_round,
    min_throat_radius, recommended_cl_radius,
    nearest_standard_rect, nearest_standard_round,
    validate_duct, seam_recommendation, joint_recommendation,
    PressureClass, SeamType, JointType,
)
from geometry.straight   import StraightDuct
from geometry.elbow      import Elbow
from geometry.tee        import Tee
from geometry.reducer    import Reducer
from geometry.transition import Transition
from bom.calculator      import calculate_bom, FullBOM
from bom.exporter        import export_csv, export_excel


# ── SMACNA gauge tables ───────────────────────────────────────────────────────

class TestSMACNAGauges:
    def test_small_rect_low_pressure(self):
        g, t = recommended_gauge_rect(400, PressureClass.LOW)
        assert t == pytest.approx(0.55, abs=0.01)   # 26 ga
        assert "26" in g

    def test_large_rect_high_pressure(self):
        g, t = recommended_gauge_rect(2200, PressureClass.HIGH)
        assert t >= 1.60   # 16 ga

    def test_small_round(self):
        g, t = recommended_gauge_round(200)
        assert t == pytest.approx(0.55, abs=0.01)

    def test_large_round(self):
        g, t = recommended_gauge_round(1200)
        assert t >= 1.30

    def test_throat_radius_min(self):
        assert min_throat_radius(400) == pytest.approx(200)

    def test_cl_radius_default(self):
        assert recommended_cl_radius(400) == pytest.approx(600)

    def test_snap_rect_standard(self):
        w, h = nearest_standard_rect(410, 210)
        assert w in [400, 450]
        assert h in [200, 250]

    def test_snap_round_standard(self):
        d = nearest_standard_round(290)
        assert d in [250, 315]

    def test_seam_small_duct(self):
        assert seam_recommendation(400) == SeamType.PITTSBURGH

    def test_seam_large_duct(self):
        result = seam_recommendation(1600)
        assert result in [SeamType.STANDING, SeamType.SNAP_LOCK]

    def test_joint_small(self):
        assert joint_recommendation(400) == JointType.SLIP_AND_DRIVE

    def test_joint_large(self):
        assert joint_recommendation(1500) == JointType.ANGLE_IRON


# ── SMACNA validation ─────────────────────────────────────────────────────────

class TestValidation:
    def test_valid_duct_no_errors(self):
        errors = validate_duct("Straight Duct", width=400, height=200,
                               length=2000, thickness=0.8)
        assert errors == []

    def test_long_duct_warning(self):
        errors = validate_duct("Straight Duct", width=400, height=200,
                               length=5000, thickness=0.8)
        assert any("3000" in e for e in errors)

    def test_thin_gauge_warning(self):
        errors = validate_duct("Straight Duct", width=1200, height=600,
                               length=2000, thickness=0.55)
        assert any("Gauge" in e for e in errors)

    def test_high_aspect_ratio_warning(self):
        errors = validate_duct("Straight Duct", width=2400, height=200,
                               length=1000, thickness=1.0)
        assert any("Aspect" in e for e in errors)

    def test_small_throat_radius_error(self):
        errors = validate_duct("Elbow", width=400, height=200,
                               angle=90, throat_radius=100, thickness=0.8)
        assert any("Throat" in e or "throat" in e for e in errors)


# ── BOM calculator ────────────────────────────────────────────────────────────

class TestBOMCalculator:
    def _make_components(self):
        return [
            StraightDuct(width=600, height=300, length=3000, thickness=0.8),
            Elbow(width=600, height=300, angle=90, thickness=0.8),
            Transition(inlet_w=600, inlet_h=300, outlet_w=400, outlet_h=250,
                       length=500, thickness=0.8),
            Tee(main_w=600, main_h=300, branch_w=300, branch_h=250, thickness=0.8),
            Reducer(inlet_w=600, inlet_h=300, outlet_w=400, outlet_h=250,
                    length=400, thickness=0.8),
        ]

    def test_bom_has_items(self):
        bom = calculate_bom(self._make_components())
        assert len(bom.items) > 0

    def test_bom_has_sheet_metal(self):
        bom = calculate_bom(self._make_components())
        sm = [i for i in bom.items if "Sheet Metal" in i.description]
        assert len(sm) == 5   # one per component

    def test_bom_has_flanges(self):
        bom = calculate_bom(self._make_components())
        flanges = [i for i in bom.items if "Flange" in i.description]
        assert len(flanges) > 0

    def test_bom_has_gaskets(self):
        bom = calculate_bom(self._make_components())
        gaskets = [i for i in bom.items if "Gasket" in i.description]
        assert len(gaskets) > 0

    def test_bom_has_fasteners(self):
        bom = calculate_bom(self._make_components())
        fasteners = [i for i in bom.items if "Fastener" in i.description]
        assert len(fasteners) > 0

    def test_total_weight_positive(self):
        bom = calculate_bom(self._make_components())
        assert bom.total_weight_kg > 0

    def test_total_cost_positive(self):
        bom = calculate_bom(self._make_components())
        assert bom.total_cost_usd > 0

    def test_insulation_items(self):
        bom = calculate_bom(self._make_components(), include_insulation=True)
        ins = [i for i in bom.items if "Insulation" in i.description]
        assert len(ins) == 5

    def test_bom_summary_by_category(self):
        bom = calculate_bom(self._make_components())
        summary = bom.summary_by_category()
        assert len(summary) > 0
        assert sum(summary.values()) == pytest.approx(bom.total_cost_usd, rel=1e-3)

    def test_bom_as_dict(self):
        bom = calculate_bom([StraightDuct(width=400, height=200, length=1000)])
        d = bom.items[0].as_dict()
        assert "Qty" in d
        assert "Total Wt (kg)" in d


# ── BOM exporter ──────────────────────────────────────────────────────────────

class TestBOMExport:
    def _simple_bom(self):
        return calculate_bom([StraightDuct(width=400, height=200, length=1000)])

    def test_csv_export(self, tmp_path):
        bom = self._simple_bom()
        p = tmp_path / "bom.csv"
        export_csv(bom, p)
        assert p.exists()
        content = p.read_text()
        assert "Sheet Metal" in content

    def test_excel_export(self, tmp_path):
        bom = self._simple_bom()
        p = tmp_path / "bom.xlsx"
        export_excel(bom, p)
        # Either xlsx or fallback csv should exist
        assert p.exists() or (tmp_path / "bom.csv").exists()

    def test_project_manager_roundtrip(self, tmp_path):
        from project.manager import new_project, save_project, load_project
        from geometry.straight import StraightDuct
        p = new_project("Test Project", "Engineer A")
        p.components.append(StraightDuct(width=400, height=200, length=1000, tag="D-1"))
        path = tmp_path / "test.dap.json"
        save_project(p, path)
        loaded = load_project(path)
        assert loaded.name == "Test Project"
        assert len(loaded.components) == 1
        assert loaded.components[0].tag == "D-1"
