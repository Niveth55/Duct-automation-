"""
Tests for the duct automation pipeline (dry-run, no AutoCAD required).
"""

import json
import pytest
from pathlib import Path

from duct_automation.duct.models import (
    RectangularDuct, RoundDuct, OvalDuct, Fitting, FittingType,
    DuctShape, Material, DuctRun, DuctSystem, Point2D,
)
from duct_automation.duct.layout_parser import parse_json
from duct_automation.bom.generator import generate_bom, bom_to_text
from duct_automation.core import run


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

EXAMPLE_JSON = Path(__file__).parent.parent / "examples" / "office_hvac.json"


@pytest.fixture
def simple_system():
    sys = DuctSystem(project_name="Test", project_number="T-001",
                     drawn_by="Tester", date="2025-01-01")
    run_ = DuctRun(name="Supply Main")
    run_.sections.append(RectangularDuct(
        width=600, height=300, length=4000,
        start=Point2D(0, 0), tag="D-01",
    ))
    run_.sections.append(RoundDuct(
        diameter=250, length=2000,
        start=Point2D(4200, 0), tag="D-02",
    ))
    run_.fittings.append(Fitting(
        fitting_type=FittingType.TEE,
        shape=DuctShape.RECTANGULAR,
        width=600, height=300,
        position=Point2D(4100, 0), tag="F-01",
    ))
    run_.fittings.append(Fitting(
        fitting_type=FittingType.ELBOW_90,
        shape=DuctShape.ROUND,
        diameter=250,
        position=Point2D(6300, 0), tag="F-02",
    ))
    sys.runs.append(run_)
    return sys


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestModels:
    def test_rect_duct_perimeter(self):
        d = RectangularDuct(width=600, height=300, length=4000)
        assert d.perimeter == pytest.approx(1800)

    def test_rect_duct_area(self):
        d = RectangularDuct(width=600, height=300, length=4000)
        expected = (1800 * 4000) / 1_000_000
        assert d.area_sqm == pytest.approx(expected)

    def test_round_duct_perimeter(self):
        import math
        d = RoundDuct(diameter=250, length=2000)
        assert d.perimeter == pytest.approx(math.pi * 250)

    def test_oval_duct_area_positive(self):
        d = OvalDuct(major=500, minor=300, length=3000)
        assert d.area_sqm > 0

    def test_duct_run_total_length(self, simple_system):
        run_ = simple_system.runs[0]
        assert run_.total_length() == 6000


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

class TestParser:
    def test_parse_example_json(self):
        with open(EXAMPLE_JSON) as f:
            data = json.load(f)
        system = parse_json(data)
        assert system.project_name == "Office Level 3 HVAC"
        assert len(system.runs) == 3

    def test_parse_rect_section(self):
        data = {
            "project_name": "P", "runs": [{
                "name": "S", "sections": [{
                    "type": "rectangular", "width": 400, "height": 200,
                    "length": 3000, "tag": "D-99",
                }], "fittings": [],
            }]
        }
        system = parse_json(data)
        sec = system.runs[0].sections[0]
        assert isinstance(sec, RectangularDuct)
        assert sec.width == 400
        assert sec.tag == "D-99"

    def test_parse_round_section(self):
        data = {
            "project_name": "P", "runs": [{
                "name": "S", "sections": [{
                    "type": "round", "diameter": 315, "length": 2000,
                }], "fittings": [],
            }]
        }
        system = parse_json(data)
        sec = system.runs[0].sections[0]
        assert isinstance(sec, RoundDuct)
        assert sec.diameter == 315

    def test_parse_fitting(self):
        data = {
            "project_name": "P", "runs": [{
                "name": "S", "sections": [], "fittings": [{
                    "type": "ELBOW_90", "shape": "rectangular",
                    "width": 600, "height": 300, "tag": "F-X",
                }],
            }]
        }
        system = parse_json(data)
        fit = system.runs[0].fittings[0]
        assert fit.fitting_type == FittingType.ELBOW_90
        assert fit.tag == "F-X"

    def test_unknown_section_type_raises(self):
        data = {
            "project_name": "P", "runs": [{
                "name": "S", "sections": [{"type": "hexagonal"}],
                "fittings": [],
            }]
        }
        with pytest.raises(ValueError, match="hexagonal"):
            parse_json(data)


# ---------------------------------------------------------------------------
# BOM tests
# ---------------------------------------------------------------------------

class TestBOM:
    def test_bom_has_line_items(self, simple_system):
        bom = generate_bom(simple_system)
        assert len(bom.line_items) > 0

    def test_bom_duct_unit_mm(self, simple_system):
        bom = generate_bom(simple_system)
        duct_items = [i for i in bom.line_items if i.unit == "mm"]
        assert len(duct_items) >= 2  # rect + round

    def test_bom_fitting_unit_ea(self, simple_system):
        bom = generate_bom(simple_system)
        fit_items = [i for i in bom.line_items if i.unit == "EA"]
        assert len(fit_items) >= 2

    def test_bom_area_positive(self, simple_system):
        bom = generate_bom(simple_system)
        assert bom.total_area_sqm() > 0

    def test_bom_material_summary(self, simple_system):
        bom = generate_bom(simple_system)
        assert len(bom.material_summary) > 0

    def test_bom_text_output(self, simple_system):
        bom = generate_bom(simple_system)
        text = bom_to_text(bom)
        assert "PARTS & PIECES BILL OF MATERIALS" in text
        assert "MATERIAL SUMMARY" in text

    def test_bom_example_project(self):
        with open(EXAMPLE_JSON) as f:
            data = json.load(f)
        system = parse_json(data)
        bom = generate_bom(system)
        assert bom.project_name == "Office Level 3 HVAC"
        assert bom.total_area_sqm() > 0


# ---------------------------------------------------------------------------
# CSV / Excel export tests
# ---------------------------------------------------------------------------

class TestExport:
    def test_csv_export(self, simple_system, tmp_path):
        from duct_automation.bom.exporter import export_csv
        bom = generate_bom(simple_system)
        out = tmp_path / "bom.csv"
        export_csv(bom, out)
        assert out.exists()
        content = out.read_text()
        assert "Item No" in content

    def test_excel_export(self, simple_system, tmp_path):
        from duct_automation.bom.exporter import export_excel
        bom = generate_bom(simple_system)
        out = tmp_path / "bom.xlsx"
        export_excel(bom, out)
        # openpyxl may not be installed in all envs; fallback to csv
        assert out.exists() or (tmp_path / "bom.csv").exists()


# ---------------------------------------------------------------------------
# Full pipeline dry-run test
# ---------------------------------------------------------------------------

class TestPipeline:
    def test_dry_run_with_example(self, tmp_path):
        result = run(
            layout=str(EXAMPLE_JSON),
            output_dir=str(tmp_path),
            dry_run=True,
            export_bom=True,
            bom_formats=("csv",),
        )
        assert result["system"] is not None
        assert result["bom"] is not None
        assert "csv" in result["bom_paths"]
        assert Path(result["bom_paths"]["csv"]).exists()

    def test_dry_run_with_dict(self, tmp_path):
        layout = {
            "project_name": "Dict Test",
            "runs": [{
                "name": "Supply", "sections": [{
                    "type": "rectangular", "width": 300, "height": 200, "length": 1000,
                }], "fittings": [],
            }],
        }
        result = run(layout=layout, output_dir=str(tmp_path), dry_run=True,
                     export_bom=True, bom_formats=("csv",))
        assert result["bom"].project_name == "Dict Test"
