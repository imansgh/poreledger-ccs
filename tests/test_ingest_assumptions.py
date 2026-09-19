"""The assumption layer -- the only door through which unsourced values enter.

The discipline these tests protect: a capacity number produced from an
undocumented area looks exactly like one produced from a measured area, so an
assumption without an owner and a rationale is rejected outright.
"""

from __future__ import annotations

import json

import pytest

from ccs_screen.ingest.assumptions import (
    ASSUMABLE,
    NO_ASSUMPTIONS,
    Assumption,
    AssumptionError,
    AssumptionSet,
)
from ccs_screen.ingest.provenance import Confidence, Provenance, Unit


def make(**kw) -> Assumption:
    base = dict(parameter="porosity", value=0.18, author="Test Engineer",
                rationale="pilot placeholder", date="2026-09-19")
    base.update(kw)
    return Assumption(**base)


def test_assumption_records_its_justification():
    a = make(citation="CSLF 2007")
    assert a.author == "Test Engineer"
    assert a.rationale
    assert a.date == "2026-09-19"
    assert a.citation == "CSLF 2007"


def test_assumption_infers_its_unit():
    assert make(parameter="area_m2", value=1e8).unit is Unit.SQUARE_METRE
    assert make(parameter="pressure_pa", value=15e6).unit is Unit.PASCAL
    assert make(parameter="porosity", value=0.18).unit is Unit.DIMENSIONLESS


def test_assumption_renders_as_an_assumed_field_value():
    fv = make().as_field_value()
    assert fv.provenance is Provenance.ASSUMED
    assert fv.value == pytest.approx(0.18)
    assert any("Test Engineer" in n for n in fv.notes)
    assert not fv.is_from_source, "an assumption is never source data"


def test_range_assumption_keeps_the_declared_range():
    fv = make(value=(0.12, 0.24)).as_field_value()
    assert fv.value == pytest.approx(0.18)  # midpoint stored
    assert any("(0.12, 0.24)" in n for n in fv.notes)


def test_range_reaches_config_as_a_range():
    assert make(value=(0.12, 0.24)).config_value() == [0.12, 0.24]
    assert make(value=0.18).config_value() == pytest.approx(0.18)


@pytest.mark.parametrize("missing", ["author", "rationale"])
def test_assumption_without_justification_is_rejected(missing):
    with pytest.raises(AssumptionError) as excinfo:
        make(**{missing: "   "})
    assert missing in str(excinfo.value)


def test_unassumable_parameter_is_rejected():
    """Depth and temperature come from sources or not at all."""
    for parameter in ("depth_m", "temperature_k", "gross_thickness_m", "well_id"):
        with pytest.raises(AssumptionError) as excinfo:
            make(parameter=parameter)
        assert "not an assumable parameter" in str(excinfo.value)


def test_assumable_set_is_exactly_the_unavailable_fields():
    assert set(ASSUMABLE) == {"area_m2", "porosity", "pressure_pa",
                              "storage_efficiency", "thickness_m"}


def test_inverted_range_is_rejected():
    with pytest.raises(AssumptionError):
        make(value=(0.30, 0.10))


def test_three_element_range_is_rejected():
    with pytest.raises(AssumptionError):
        make(value=(0.1, 0.2, 0.3))


def test_duplicate_parameter_in_a_set_is_rejected():
    with pytest.raises(AssumptionError) as excinfo:
        AssumptionSet(name="dupes", assumptions=(make(), make(value=0.2)))
    assert "porosity" in str(excinfo.value)


def test_empty_set_is_the_default():
    assert len(NO_ASSUMPTIONS) == 0
    assert NO_ASSUMPTIONS.get("porosity") is None


def test_set_lookup_and_iteration():
    s = AssumptionSet(name="s", assumptions=(make(), make(parameter="area_m2", value=1e8)))
    assert len(s) == 2
    assert s.get("area_m2") is not None
    assert s.get("pressure_pa") is None
    assert set(s.parameters) == {"porosity", "area_m2"}
    assert len(list(s)) == 2


def test_round_trip_through_json(tmp_path):
    original = AssumptionSet(name="pilot", assumptions=(
        make(value=(0.12, 0.24), citation="CSLF"),
        make(parameter="area_m2", value=1e8),
    ))
    path = tmp_path / "assumptions.json"
    path.write_text(json.dumps(original.to_dict()), encoding="utf-8")
    loaded = AssumptionSet.from_json_file(path)
    assert loaded.name == "pilot"
    assert set(loaded.parameters) == {"porosity", "area_m2"}
    assert loaded.get("porosity").value == (0.12, 0.24)


def test_missing_assumption_file_is_reported():
    with pytest.raises(AssumptionError) as excinfo:
        AssumptionSet.from_json_file("no-such-assumptions.json")
    assert "not found" in str(excinfo.value)


def test_malformed_assumption_json_is_reported(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text('{"name": "x", ', encoding="utf-8")
    with pytest.raises(AssumptionError) as excinfo:
        AssumptionSet.from_json_file(path)
    assert "not valid JSON" in str(excinfo.value)


def test_from_mapping_rejects_an_unjustified_entry():
    with pytest.raises(AssumptionError):
        AssumptionSet.from_mapping({
            "name": "bad",
            "assumptions": [{"parameter": "porosity", "value": 0.18}],
        })


def test_confidence_defaults_to_low():
    """An assumption is low-confidence until someone argues otherwise."""
    assert make().confidence is Confidence.LOW


def test_shipped_example_assumption_set_is_valid():
    """examples/pilot-assumptions.json must stay loadable and justified."""
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "examples" / "pilot-assumptions.json"
    if not path.exists():
        pytest.skip("example assumption set not present")
    s = AssumptionSet.from_json_file(path)
    assert set(s.parameters) == set(ASSUMABLE)
    for a in s:
        assert a.author and a.rationale
        assert "PLACEHOLDER" in a.rationale or "assumption by definition" in a.rationale
