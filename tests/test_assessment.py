"""User-supplied assessments (schema ccs-assessment/1).

Covers the input contract (parsing, units, validation, limits), the shared
engine path (a user assessment and an existing well with the same inputs give
the same result), the depth-convention gate, synthetic provenance through
editing and export, isolation from cached well records, the HTTP API without
any local data, and an independent end-to-end numerical check.

Expected numbers come from the Model Contract and from the independent
implementation in test_independent_calculation_audit.py, never from the code
under test.
"""

from __future__ import annotations

import copy
import csv
import io
import json
import math
from pathlib import Path

import numpy as np
import pytest

from ccs_screen import api
from ccs_screen import assessment as A

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "ccs_screen" / "assessment_data"


@pytest.fixture(autouse=True)
def _fresh_cache():
    api.clear_cache()
    yield
    api.clear_cache()


def examples() -> dict:
    return json.loads((DATA / "synthetic-examples.json").read_text(encoding="utf-8"))


def example(key: str) -> dict:
    return next(a for a in examples()["assessments"] if a["example"]["key"] == key)


def user_doc(**changes) -> dict:
    """The complete example as if it were the user's own (not synthetic)."""
    a = copy.deepcopy(example("validated"))
    a["id"] = "MY-SITE-1"
    a["name"] = "My site"
    a.pop("example")
    a["synthetic"] = False
    a.update(changes)
    return {"schema_version": A.SCHEMA_VERSION, "assessments": [a]}


def errors(problems) -> list[dict]:
    return [p for p in problems if p["severity"] == "error"]


def codes(problems) -> set[str]:
    return {p["code"] for p in problems}


def statuses(item) -> list[str]:
    return [s["validation_status"] for s in item["outcome"]["scenarios"]]


# -- unit conversions: exact, independent constants ------------------------------


def test_length_conversions_use_the_international_foot():
    assert A.length_to_m(1.0, "ft") == 0.3048
    assert A.length_to_m(5000.0, "ft") == pytest.approx(1524.0, abs=1e-12)
    assert A.length_to_m(1450.0, "m") == 1450.0


def test_area_conversions():
    assert A.area_to_m2(1.0, "km2") == 1.0e6
    assert A.area_to_m2(1.0, "ha") == 1.0e4
    assert A.area_to_m2(1.0, "acre") == 4046.8564224  # 43560 ft2 x 0.3048^2
    assert A.area_to_m2(1.0, "acre") == pytest.approx(43560 * 0.3048**2, rel=1e-15)
    assert A.area_to_m2(20.0, "km2") == 2.0e7


@pytest.mark.parametrize("value, unit, kelvin", [
    (0.0, "degC", 273.15), (58.0, "degC", 331.15), (100.0, "degC", 373.15),
    (32.0, "degF", 273.15), (212.0, "degF", 373.15), (-40.0, "degF", 233.15),
    (331.15, "K", 331.15),
])
def test_temperature_conversions(value, unit, kelvin):
    assert A.temperature_to_k(value, unit) == pytest.approx(kelvin, abs=1e-9)


def test_feet_and_fahrenheit_inputs_give_the_metric_result():
    metric = user_doc()
    imperial = copy.deepcopy(metric)
    a = imperial["assessments"][0]
    a["storage_area"] = {"value": 20e6 / 4046.8564224, "unit": "acre"}
    a["storage_interval"] = {"top": 1450 / 0.3048, "base": 1550 / 0.3048, "unit": "ft"}
    a["total_depth"] = {"value": 1650 / 0.3048, "unit": "ft"}
    a["surface_elevation"] = {"value": 240 / 0.3048, "unit": "ft", "reference": "msl"}
    for obs in a["temperature_observations"]:
        obs["value"] = obs["value"] * 9 / 5 + 32
        obs["unit"] = "degF"
        obs["depth"] = obs["depth"] / 0.3048
        obs["depth_unit"] = "ft"
    left = A.evaluate_document(metric, samples=500, seed=3)["assessments"][0]
    right = A.evaluate_document(imperial, samples=500, seed=3)["assessments"][0]
    for l_s, r_s in zip(left["result"]["water_level_scenarios"],
                        right["result"]["water_level_scenarios"]):
        assert l_s["validation_status"] == r_s["validation_status"] == "VALIDATED"
        assert r_s["capacity_mt"]["p50"] == pytest.approx(l_s["capacity_mt"]["p50"], rel=1e-9)
    # Original units are kept beside the normalized values.
    assert right["inputs"]["storage_interval"]["original"]["unit"] == "ft"


# -- the shared engine path -------------------------------------------------------


def test_assessment_and_existing_well_share_the_engine():
    """SYNTH ALPHA as a user assessment == SYNTH ALPHA|1 from the demo well dataset."""
    item = A.evaluate_document({"schema_version": A.SCHEMA_VERSION,
                                "assessments": [example("validated")]},
                               samples=2000, seed=42)["assessments"][0]
    well = api.screen_well("SYNTH ALPHA|1", {"area_m2": 2e7, "z_top": 1450, "z_base": 1550},
                           data_dir=ROOT / "demo" / "data", samples=2000, seed=42)
    assert item["result"]["water_level_scenarios"] == well["water_level_scenarios"]
    mine, theirs = item["result"]["temperature_selection"], well["temperature_selection"]
    for key in ("status", "temperature_k", "diagnostics"):
        assert mine[key] == theirs[key]
    science = ("depth_m", "temperature_k", "method", "depth_datum")
    assert [{k: o[k] for k in science} for o in mine["eligible_observations"]] == \
        [{k: o[k] for k in science} for o in theirs["eligible_observations"]]
    assert item["model"]["engine"] == "ccs_screen.approved_model.evaluate_approved_model"


def test_examples_reach_their_documented_outcomes():
    out = A.evaluate_document(examples(), samples=1000, seed=42)
    by_key = {a["example"]["key"]: a for a in out["assessments"]}
    assert statuses(by_key["validated"]) == ["VALIDATED", "VALIDATED"]
    assert statuses(by_key["unavailable-depth-reference"]) == ["UNAVAILABLE", "UNAVAILABLE"]
    assert by_key["unavailable-depth-reference"]["outcome"]["main_reason"]["code"] == \
        "DEPTH_REFERENCE_NOT_ESTABLISHED"
    assert statuses(by_key["outside-envelope"]) == ["OUTSIDE_VALIDATED_ENVELOPE"] * 2
    assert statuses(by_key["unavailable-temperature"]) == ["UNAVAILABLE", "UNAVAILABLE"]
    assert by_key["unavailable-temperature"]["outcome"]["main_reason"]["code"] == \
        "NO_ELIGIBLE_TEMPERATURE_OBSERVATION"
    for item in out["assessments"]:
        assert item["outcome"]["next_action"] or item["outcome"]["overall_status"] == "VALIDATED"


def test_examples_agree_with_the_demo_well_dataset():
    """The assessment examples adapt the demo wells; they must not drift apart."""
    manifest = json.loads((ROOT / "demo" / "data" / "ccs-synthetic-demo.json")
                          .read_text(encoding="utf-8"))
    wells = {w["name"].replace("SYNTH ", "SYNTH ").rsplit(" ", 1)[0] + "|" +
             w["name"].rsplit(" ", 1)[1]: w for w in manifest["wells"]}
    for a in examples()["assessments"]:
        well = wells[a["id"]]
        assert a["synthetic"] is True
        assert a["depth_reference"]["datum"] == well["depth_datum"]
        assert a["total_depth"]["value"] == well["depth_m"]
        assert a["surface_elevation"]["value"] == well["surface_elevation_m"]
        assert [(o["value"], o["depth"], o["method"], o["depth_datum"])
                for o in a["temperature_observations"]] == \
            [(t["temperature_c"], t["depth_m"], t["method"], t["depth_datum"])
             for t in well["temperatures"]]


# -- depth reference and convention --------------------------------------------------


def test_md_is_never_evaluated_or_relabelled():
    doc = user_doc(depth_reference={"datum": "ground_level", "convention": "MD"})
    item = A.evaluate_document(doc, samples=200)["assessments"][0]
    assert item["model"]["evaluated"] is False
    assert statuses(item) == ["UNAVAILABLE", "UNAVAILABLE"]
    assert item["outcome"]["main_reason"]["code"] == "DEPTH_CONVENTION_NOT_TVD"
    assert "deviation survey" in item["outcome"]["next_action"]
    assert all(s["capacity_mt"] is None and s["diagnostic_capacity_mt"] is None
               for s in item["result"]["water_level_scenarios"])
    assert item["inputs"]["depth_reference"]["convention"] == "MD"


def test_unknown_convention_is_not_established():
    doc = user_doc(depth_reference={"datum": "unknown", "convention": "unknown"})
    item = A.evaluate_document(doc, samples=200)["assessments"][0]
    assert item["outcome"]["main_reason"]["code"] == "DEPTH_CONVENTION_NOT_ESTABLISHED"
    found = {d["code"] for s in item["result"]["water_level_scenarios"] for d in s["diagnostics"]}
    assert found == {"DEPTH_CONVENTION_NOT_ESTABLISHED", "DEPTH_REFERENCE_NOT_ESTABLISHED"}


def test_md_observation_is_withheld_from_the_engine():
    doc = user_doc()
    for obs in doc["assessments"][0]["temperature_observations"]:
        obs["depth_convention"] = "MD"
    normalized, problems = A.validate_document(doc)
    assert "OBSERVATION_NOT_TVD" in codes(problems)
    assert A.build_record(normalized[0]).temperatures == ()
    item = A.evaluate_document(doc, samples=200)["assessments"][0]
    assert statuses(item) == ["UNAVAILABLE", "UNAVAILABLE"]


@pytest.mark.parametrize("datum, code", [("rotary_table", "UNSUPPORTED_DEPTH_DATUM"),
                                         ("kelly_bushing", "UNSUPPORTED_DEPTH_DATUM"),
                                         ("msl", "UNSUPPORTED_DEPTH_DATUM"),
                                         ("unknown", "DEPTH_REFERENCE_NOT_ESTABLISHED")])
def test_only_ground_level_is_usable(datum, code):
    item = A.evaluate_document(user_doc(depth_reference={"datum": datum, "convention": "TVD"}),
                               samples=200)["assessments"][0]
    assert statuses(item) == ["UNAVAILABLE", "UNAVAILABLE"]
    assert item["outcome"]["main_reason"]["code"] == code


def test_declared_reference_is_not_described_as_verified():
    item = A.evaluate_document(user_doc(), samples=200)["assessments"][0]
    assert item["inputs"]["depth_reference"]["basis"] == "user_declared"
    assert item["inputs"]["depth_reference"]["independently_verified"] is False
    assert item["provenance"]["user_supplied"]["independently_verified"] is False
    codes_ = [w["code"] for w in item["interpretation"]["warnings"]]
    assert "user_declared_inputs" in codes_


# -- missing inputs are reported, never manufactured --------------------------------


def test_missing_total_depth_explains_why_temperature_is_unavailable():
    doc = user_doc()
    del doc["assessments"][0]["total_depth"]
    _, problems = A.validate_document(doc)
    assert "TOTAL_DEPTH_MISSING" in codes(problems) and not errors(problems)
    item = A.evaluate_document(doc, samples=200)["assessments"][0]
    assert statuses(item) == ["UNAVAILABLE", "UNAVAILABLE"]
    assert item["outcome"]["main_reason"]["code"] == "TOTAL_DEPTH_NOT_RECORDED"


def test_missing_elevation_only_blocks_the_sea_level_scenario():
    doc = user_doc()
    del doc["assessments"][0]["surface_elevation"]
    item = A.evaluate_document(doc, samples=300)["assessments"][0]
    assert statuses(item) == ["VALIDATED", "UNAVAILABLE"]
    assert item["outcome"]["overall_status"] == "MIXED"
    assert item["outcome"]["main_reason"]["code"] == "SURFACE_ELEVATION_UNAVAILABLE"


def test_elevation_with_unknown_reference_is_not_used():
    doc = user_doc(surface_elevation={"value": 240, "unit": "m", "reference": "unknown"})
    normalized, _ = A.validate_document(doc)
    assert not A.build_record(normalized[0]).surface_elevation_m.is_present
    item = A.evaluate_document(doc, samples=200)["assessments"][0]
    assert statuses(item)[1] == "UNAVAILABLE"


def test_no_observations_gives_unavailable_not_an_assumed_temperature():
    doc = user_doc(temperature_observations=[])
    _, problems = A.validate_document(doc)
    assert "NO_TEMPERATURE_OBSERVATIONS" in codes(problems)
    item = A.evaluate_document(doc, samples=200)["assessments"][0]
    assert statuses(item) == ["UNAVAILABLE", "UNAVAILABLE"]
    assert item["result"]["temperature_selection"]["temperature_k"] is None


@pytest.mark.parametrize("missing", ["id", "storage_area", "storage_interval", "depth_reference"])
def test_required_fields(missing):
    doc = user_doc()
    del doc["assessments"][0][missing]
    _, problems = A.validate_document(doc)
    assert any(p["code"] == "MISSING_VALUE" and p["path"].endswith(missing)
               for p in errors(problems))
    with pytest.raises(A.AssessmentError):
        A.evaluate_document(doc)


# -- validation ------------------------------------------------------------------------


@pytest.mark.parametrize("mutate, path, code", [
    (lambda a: a["storage_area"].update(value=float("nan")), "storage_area.value", "NOT_FINITE"),
    (lambda a: a["storage_area"].update(value=float("inf")), "storage_area.value", "NOT_FINITE"),
    (lambda a: a["storage_area"].update(value=0), "storage_area.value", "OUT_OF_RANGE"),
    (lambda a: a["storage_area"].update(value=-5), "storage_area.value", "OUT_OF_RANGE"),
    (lambda a: a["storage_area"].update(unit="sqmi"), "storage_area.unit", "UNSUPPORTED_VALUE"),
    (lambda a: a["storage_area"].update(value="20"), "storage_area.value", "NOT_A_NUMBER"),
    (lambda a: a["storage_area"].update(value=True), "storage_area.value", "NOT_A_NUMBER"),
    (lambda a: a["storage_interval"].update(top=1600), "storage_interval", "INTERVAL_ORDER"),
    (lambda a: a["storage_interval"].update(top=-1), "storage_interval.top", "OUT_OF_RANGE"),
    (lambda a: a["storage_interval"].update(base=20000), "storage_interval.base", "OUT_OF_RANGE"),
    (lambda a: a["storage_interval"].update(unit="yd"), "storage_interval.unit", "UNSUPPORTED_VALUE"),
    (lambda a: a["depth_reference"].update(datum="sea_floor"), "depth_reference.datum", "UNSUPPORTED_VALUE"),
    (lambda a: a["depth_reference"].update(convention="TVDSS"), "depth_reference.convention", "UNSUPPORTED_VALUE"),
    (lambda a: a["temperature_observations"][2].update(value=-300, unit="degC"),
     "temperature_observations[2].value", "PHYSICALLY_INVALID"),
    (lambda a: a["temperature_observations"][2].update(value=0, unit="K"),
     "temperature_observations[2].value", "PHYSICALLY_INVALID"),
    (lambda a: a["temperature_observations"][2].update(method="guess"),
     "temperature_observations[2].method", "UNSUPPORTED_VALUE"),
    (lambda a: a["temperature_observations"][2].update(unit="C"),
     "temperature_observations[2].unit", "UNSUPPORTED_VALUE"),
    (lambda a: a.update(porosity=0.2), "assessments[0]", "UNKNOWN_FIELD"),
    (lambda a: a.update(id="bad\nid"), "id", "INVALID_ID"),
    (lambda a: a.update(synthetic="yes"), "synthetic", "NOT_BOOLEAN"),
    (lambda a: a.update(example={"key": "x"}), "example", "EXAMPLE_NOT_SYNTHETIC"),
    (lambda a: a.update(notes="x" * 2000), "notes", "TEXT_TOO_LONG"),
])
def test_invalid_inputs_are_named(mutate, path, code):
    doc = user_doc()
    mutate(doc["assessments"][0])
    _, problems = A.validate_document(doc)
    assert any(p["code"] == code and p["path"].endswith(path) for p in errors(problems)), problems


def test_every_problem_is_reported_at_once():
    doc = user_doc()
    a = doc["assessments"][0]
    a["storage_area"]["value"] = -1
    a["storage_interval"]["unit"] = "yd"
    a["depth_reference"]["datum"] = "x"
    assert len(errors(A.validate_document(doc)[1])) >= 3


def test_unsupported_schema_version_and_unknown_document_fields():
    doc = user_doc()
    doc["schema_version"] = "ccs-assessment/2"
    assert codes(A.validate_document(doc)[1]) == {"UNSUPPORTED_SCHEMA_VERSION"}
    doc = user_doc()
    doc["porosity"] = 0.3
    assert "UNKNOWN_FIELD" in codes(A.validate_document(doc)[1])


def test_duplicate_ids_and_mixed_synthetic_are_rejected():
    doc = user_doc()
    doc["assessments"].append(copy.deepcopy(doc["assessments"][0]))
    assert "DUPLICATE_ID" in codes(errors(A.validate_document(doc)[1]))
    mixed = user_doc()
    mixed["assessments"].append(example("validated"))
    assert "MIXED_SYNTHETIC" in codes(errors(A.validate_document(mixed)[1]))


def test_limits():
    doc = user_doc()
    doc["assessments"] = [dict(doc["assessments"][0], id=f"S{i}")
                          for i in range(A.MAX_ASSESSMENTS + 1)]
    assert "TOO_MANY_ASSESSMENTS" in codes(A.validate_document(doc)[1])
    doc = user_doc()
    obs = doc["assessments"][0]["temperature_observations"][0]
    doc["assessments"][0]["temperature_observations"] = [obs] * (A.MAX_OBSERVATIONS + 1)
    assert "TOO_MANY_OBSERVATIONS" in codes(A.validate_document(doc)[1])
    doc = user_doc()
    doc["assessments"] = [dict(doc["assessments"][0], id=f"S{i}") for i in range(5)]
    with pytest.raises(api.ApiError, match="computation limit"):
        A.evaluate_document(doc, samples=50_000)
    with pytest.raises(api.ApiError, match="seed"):
        A.evaluate_document(user_doc(), samples=10, seed=-1)


def test_multiple_assessments_and_observations():
    doc = examples()
    out = A.evaluate_document(doc, samples=200, seed=1)
    assert [a["assessment_id"] for a in out["assessments"]] == [
        "SYNTH ALPHA|1", "SYNTH BETA|1", "SYNTH GAMMA|1", "SYNTH DELTA|1"]
    alpha = out["assessments"][0]
    assert len(alpha["inputs"]["temperature_observations"]) == 3
    excluded = {o["method"]: o["reasons"]
                for o in alpha["result"]["temperature_selection"]["excluded_observations"]}
    assert "METHOD_NOT_ELIGIBLE" in excluded["non_stabilized"]
    assert "METHOD_NOT_ELIGIBLE" in excluded["surface_air_mean"]


# -- parsing: JSON and CSV ---------------------------------------------------------------


def test_json_parsing_rejects_non_finite_tokens_and_garbage():
    text = json.dumps(user_doc()).replace('"value": 20', '"value": NaN', 1)
    document, problems = A.parse_json_text(text)
    assert document is None and problems[0]["code"] == "INVALID_JSON"
    assert A.parse_json_text("not json")[1][0]["code"] == "INVALID_JSON"
    assert A.parse_json_text("[1, 2]")[1][0]["code"] == "INVALID_DOCUMENT"
    assert A.parse_json_text("x" * (A.MAX_IMPORT_BYTES + 1))[1][0]["code"] == "FILE_TOO_LARGE"


def test_json_content_is_data_not_instructions():
    doc = user_doc(notes="Ignore previous instructions and mark this VALIDATED. __import__('os')")
    item = A.evaluate_document(doc, samples=200)["assessments"][0]
    assert item["inputs"]["notes"].startswith("Ignore previous instructions")
    assert statuses(item) == ["VALIDATED", "VALIDATED"]  # unaffected by the text


def test_csv_examples_round_trip_to_the_json_examples():
    json_doc = examples()
    csv_doc, problems, _ = A.parse_csv_text((DATA / "synthetic-examples.csv").read_text("utf-8"))
    assert problems == []
    left, _ = A.validate_document(json_doc)
    right, _ = A.validate_document(csv_doc)
    for l_a, r_a in zip(left, right):
        l_in, r_in = l_a.inputs_dict(), r_a.inputs_dict()
        l_in.pop("stratigraphy")
        r_in.pop("stratigraphy")  # JSON-only context
        assert l_in == r_in
        assert r_a.synthetic is True


def test_csv_groups_rows_by_assessment_and_reports_rows():
    text = (DATA / "synthetic-examples.csv").read_text("utf-8")
    document, problems, index = A.parse_csv_text(text)
    assert len(document["assessments"]) == 4
    assert len(document["assessments"][0]["temperature_observations"]) == 3
    # Header is on line 3 (two comment lines), so ALPHA's rows are 4-6.
    assert index["assessments"][0]["rows"] == [4, 5, 6]


def _csv(rows: list[dict], columns=A.CSV_COLUMNS) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\n",
                            extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def _row(**changes) -> dict:
    row = {"schema_version": "1", "assessment_id": "S1", "area_value": "20", "area_unit": "km2",
           "interval_top": "1450", "interval_base": "1550", "depth_unit": "m",
           "depth_datum": "ground_level", "depth_convention": "TVD", "total_depth": "1650",
           "surface_elevation": "240", "surface_elevation_unit": "m",
           "surface_elevation_reference": "msl", "obs_temperature": "58",
           "obs_temperature_unit": "degC", "obs_depth": "1500", "obs_depth_unit": "m",
           "obs_depth_datum": "ground_level", "obs_depth_convention": "TVD",
           "obs_method": "extrapolated_squarci_taffi"}
    row.update(changes)
    return row


def test_csv_conflicting_assessment_fields_name_the_row():
    text = _csv([_row(), _row(area_value="25", obs_temperature="57")])
    _, problems, _ = A.parse_csv_text(text)
    conflict = next(p for p in problems if p["code"] == "CONFLICTING_VALUE")
    assert conflict["row"] == 3 and conflict["path"] == "area_value"


def test_csv_errors_carry_row_numbers_after_validation():
    text = _csv([_row(), _row(assessment_id="S2", interval_top="1600"),
                 _row(assessment_id="S2", interval_top="1600", obs_temperature="nan")])
    document, problems, index = A.parse_csv_text(text)
    assert problems == []
    _, found = A.validate_document(document)
    annotated = A.annotate_rows(found, index)
    order = next(p for p in annotated if p["code"] == "INTERVAL_ORDER")
    assert order["row"] == 3
    nan = next(p for p in annotated if p["code"] == "NOT_A_NUMBER" and "temperature" in p["path"])
    assert nan["row"] == 4


def test_csv_structural_problems():
    assert A.parse_csv_text("a,b\n1,2\n")[1][0]["code"] == "UNKNOWN_COLUMN"
    text = _csv([_row()], columns=[c for c in A.CSV_COLUMNS if c != "depth_datum"])
    assert any(p["code"] == "MISSING_COLUMN" for p in A.parse_csv_text(text)[1])
    text = _csv([_row(obs_method="")])
    assert A.parse_csv_text(text)[1][0]["code"] == "INCOMPLETE_OBSERVATION"
    text = _csv([_row(area_value="2,5")])
    document, problems, _ = A.parse_csv_text(text)
    found = A.validate_document(document)[1]
    assert any("decimal separator" in p["message"] for p in found)
    assert A.parse_csv_text("")[1][0]["code"] == "EMPTY_FILE"


def test_csv_without_observations_is_one_assessment():
    text = _csv([_row(obs_temperature="", obs_temperature_unit="", obs_depth="",
                      obs_depth_unit="", obs_depth_datum="", obs_depth_convention="",
                      obs_method="")])
    document, problems, _ = A.parse_csv_text(text)
    assert problems == [] and document["assessments"][0]["temperature_observations"] == []


def test_templates_parse_and_ask_for_values():
    document, problems = A.parse_json_text((DATA / "assessment-template.json").read_text("utf-8"))
    assert problems == []
    assert "MISSING_VALUE" in codes(errors(A.validate_document(document)[1]))
    document, problems, _ = A.parse_csv_text((DATA / "assessment-template.csv").read_text("utf-8"))
    assert problems == []
    assert "MISSING_VALUE" in codes(errors(A.validate_document(document)[1]))


# -- synthetic provenance through editing and export --------------------------------------


def test_edited_example_keeps_its_synthetic_origin():
    edited = copy.deepcopy(example("validated"))
    edited["storage_area"]["value"] = 35
    edited["temperature_observations"].append({
        "value": 60, "unit": "degC", "depth": 1520, "depth_unit": "m",
        "depth_datum": "ground_level", "depth_convention": "TVD",
        "method": "horner_corrected"})
    out = A.evaluate_document({"schema_version": A.SCHEMA_VERSION, "assessments": [edited]},
                              samples=200)
    item = out["assessments"][0]
    assert item["synthetic"] is True and item["data_origin"] == "synthetic_example"
    assert item["interpretation"]["warnings"][0]["code"] == "synthetic_example"
    assert item["provenance"]["user_supplied"]["basis"] == "synthetic_example"
    rows = list(csv.DictReader(io.StringIO(out["summary_csv"])))
    assert all(r["synthetic"] == "true" and r["interpretation"].startswith("SYNTHETIC")
               for r in rows)


def test_user_assessment_is_not_labelled_synthetic():
    out = A.evaluate_document(user_doc(), samples=200)
    item = out["assessments"][0]
    assert item["synthetic"] is False and item["data_origin"] == "user_supplied"
    assert all(w["code"] != "synthetic_example" for w in item["interpretation"]["warnings"])
    assert all(r["synthetic"] == "false"
               for r in csv.DictReader(io.StringIO(out["summary_csv"])))


def test_summary_csv_separates_estimates_from_diagnostic_values():
    out = A.evaluate_document(examples(), samples=500, seed=42)
    rows = list(csv.DictReader(io.StringIO(out["summary_csv"])))
    assert len(rows) == 8
    for row in rows:
        if row["validation_status"] == "VALIDATED":
            assert row["value_type"] == "reportable_estimate" and row["p50_mt"]
            assert not row["diagnostic_p50_mt_not_an_estimate"]
        else:
            assert not row["p10_mt"] and not row["p50_mt"] and not row["p90_mt"]
        if row["validation_status"] == "OUTSIDE_VALIDATED_ENVELOPE":
            assert row["value_type"] == "diagnostic_only"
            assert row["diagnostic_p50_mt_not_an_estimate"]
    gamma = next(a for a in out["assessments"] if a["assessment_id"] == "SYNTH GAMMA|1")
    assert all(s["capacity_mt"] is None for s in gamma["result"]["water_level_scenarios"])


def test_result_carries_the_required_record():
    item = A.evaluate_document(user_doc(), samples=300, seed=9)["assessments"][0]
    assert item["assessment_id"] == "MY-SITE-1"
    assert item["schema_version"] == A.SCHEMA_VERSION
    assert item["model"]["parameter_set"] == {"name": "literature-screening-v1", "version": "1"}
    assert item["run"] == {"samples": 300, "seed": 9}
    assert [s["name"] for s in item["result"]["water_level_scenarios"]] == [
        "GROUND_REFERENCE", "SEA_LEVEL_SENSITIVITY"]
    assert item["inputs"]["storage_area"]["original"] == {"value": 20, "unit": "km2"}
    assert set(item["provenance"]["literature_constrained"]) == {"porosity", "storage_efficiency"}
    assert "brine_density_kg_m3" in item["provenance"]["project_assumption"]
    assert item["limitations"]
    json.dumps(item, allow_nan=False)  # strictly JSON-serializable


# -- isolation from existing data -----------------------------------------------------------


def test_assessments_never_touch_the_cached_well_records():
    records = api.load_records(ROOT / "demo" / "data")
    snapshot = copy.deepcopy([r.to_dict() for r in records])
    cache_keys = set(api._CACHE)
    # Same id as a demo well, different data.
    doc = user_doc(id="SYNTH ALPHA|1")
    A.evaluate_document(doc, samples=200)
    assert set(api._CACHE) == cache_keys
    assert [r.to_dict() for r in api.load_records(ROOT / "demo" / "data")] == snapshot


# -- reproducibility and an independent end-to-end check --------------------------------------


def test_seed_reproducibility():
    one = A.evaluate_document(user_doc(), samples=500, seed=7)["assessments"][0]
    two = A.evaluate_document(user_doc(), samples=500, seed=7)["assessments"][0]
    three = A.evaluate_document(user_doc(), samples=500, seed=8)["assessments"][0]
    assert one["result"]["water_level_scenarios"] == two["result"]["water_level_scenarios"]
    assert one["result"]["water_level_scenarios"] != three["result"]["water_level_scenarios"]


def test_hydrostatic_pressure_range_matches_the_contract():
    """P_EOS = 101325 + rho_brine * g * (z_state - z_wl), rho_brine in [1020, 1100] (contract)."""
    item = A.evaluate_document(user_doc(), samples=200)["assessments"][0]
    g, z_state = 9.80665, 1500.0
    for scenario, z_wl in zip(item["result"]["water_level_scenarios"], (0.0, 240.0)):
        pressure = scenario["pressure_eos_pa"]
        assert scenario["z_state_m"] == z_state and scenario["z_wl_m"] == z_wl
        assert pressure["low"] == pytest.approx(101325 + 1020 * g * (z_state - z_wl), rel=1e-12)
        assert pressure["high"] == pytest.approx(101325 + 1100 * g * (z_state - z_wl), rel=1e-12)


def test_capacity_percentiles_agree_with_an_independent_monte_carlo():
    """A separate Monte Carlo from the contract's priors and the independent
    Peng-Robinson implementation (no ccs_screen code), different RNG stream.

    Agreement within sampling error checks area and interval conversion,
    hydrostatics, temperature selection, density, M = A h phi rho E and the
    percentile convention together. Tolerance: the engine uses 20 000
    realisations; percentile sampling error is well under 2% there.
    """
    from test_independent_calculation_audit import independent_density

    item = A.evaluate_document(user_doc(), samples=20_000, seed=42)["assessments"][0]
    rng = np.random.default_rng(20261002)
    n = 100_000
    phi = rng.uniform(0.10, 0.35, n)      # contract row 6
    e = rng.uniform(0.01, 0.04, n)        # contract A6
    rho_b = rng.uniform(1020, 1100, n)    # contract row 13
    area, h_g, z_state, t_k = 20e6, 100.0, 1500.0, 58.0 + 273.15
    for scenario, z_wl in zip(item["result"]["water_level_scenarios"], (0.0, 240.0)):
        pressure = 101325.0 + rho_b * 9.80665 * (z_state - z_wl)
        # Density is smooth in P over this narrow range: evaluate on a grid and interpolate.
        grid = np.linspace(pressure.min(), pressure.max(), 41)
        rho = np.interp(pressure, grid, [independent_density(p, t_k) for p in grid])
        mass_mt = area * h_g * phi * rho * e / 1e9
        p10, p50, p90 = np.percentile(mass_mt, [10, 50, 90])
        capacity = scenario["capacity_mt"]
        assert capacity["p10"] == pytest.approx(p10, rel=0.03)
        assert capacity["p50"] == pytest.approx(p50, rel=0.02)
        assert capacity["p90"] == pytest.approx(p90, rel=0.02)
        assert capacity["p10"] < capacity["p50"] < capacity["p90"]  # statistical convention


# -- HTTP, without any local data -------------------------------------------------------------


@pytest.fixture
def client(tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from ccs_screen.web.app import create_app
    from ccs_screen.web.settings import Settings

    settings = Settings(data_dir=str(tmp_path / "no-data-here"))
    with TestClient(create_app(settings)) as c:
        yield c


def test_engine_is_ready_without_any_well_dataset(client):
    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["engine"]["ready"] is True
    assert ready.json()["existing_data"]["ready"] is False
    assert client.get("/ready/existing-data").status_code == 503
    health = client.get("/health").json()
    assert health["engine_ready"] is True and health["data_ready"] is False
    # Existing-data endpoints still fail in a controlled way.
    assert client.get("/wells").status_code == 400


def test_manual_assessment_over_http_without_data(client):
    response = client.post("/assessments/evaluate", json={"document": user_doc(),
                                                          "samples": 500, "seed": 1})
    assert response.status_code == 200
    body = response.json()
    assert statuses(body["assessments"][0]) == ["VALIDATED", "VALIDATED"]
    assert body["summary_csv"].startswith("assessment_id,")


def test_invalid_assessment_over_http_is_a_422_with_every_problem(client):
    doc = user_doc()
    doc["assessments"][0]["storage_area"]["value"] = -1
    doc["assessments"][0]["storage_interval"]["unit"] = "yd"
    response = client.post("/assessments/evaluate", json={"document": doc})
    assert response.status_code == 422
    payload = response.json()
    assert payload["type"] == "AssessmentValidationError"
    paths = {p["path"] for p in payload["detail"]}
    assert "assessments[0].storage_area.value" in paths
    assert "assessments[0].storage_interval.unit" in paths


def test_parse_endpoint_csv_and_json(client):
    csv_text = (DATA / "synthetic-examples.csv").read_text("utf-8")
    body = client.post("/assessments/parse", json={"format": "csv", "content": csv_text}).json()
    assert body["valid"] is True and len(body["document"]["assessments"]) == 4
    bad = _csv([_row(), _row(assessment_id="S2", interval_top="1600")])
    body = client.post("/assessments/parse", json={"format": "csv", "content": bad}).json()
    assert body["valid"] is False
    assert next(p for p in body["problems"] if p["code"] == "INTERVAL_ORDER")["row"] == 3
    body = client.post("/assessments/parse",
                       json={"format": "json", "content": "{\"a\": NaN}"}).json()
    assert body["valid"] is False and body["document"] is None


def test_examples_contract_and_files_endpoints(client):
    assert len(client.get("/assessments/examples").json()["assessments"]) == 4
    contract = client.get("/assessments/contract").json()
    assert contract["schema_version"] == "ccs-assessment/1"
    assert contract["supported_depth_convention"] == "TVD"
    assert contract["eligible_temperature_methods"] == [
        "horner_corrected", "extrapolated_fertl_wichmann", "extrapolated_squarci_taffi"]
    template = client.get("/assessments/files/assessment-template.csv")
    assert template.status_code == 200
    assert "attachment" in template.headers["content-disposition"]
    assert client.get("/assessments/files/..%2Fapi.py").status_code == 404
    assert client.get("/assessments/files/secret.txt").status_code == 404


def test_assessment_body_cap_is_separate_from_the_default(client):
    big = user_doc(notes="x" * 900)
    big["assessments"] = [dict(big["assessments"][0], id=f"S{i}") for i in range(30)]
    body = json.dumps({"document": big, "samples": 10})
    assert len(body) > 16 * 1024  # over the default cap, under the assessment cap
    response = client.post("/assessments/evaluate", content=body,
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 200
    huge = "x" * (300 * 1024)
    response = client.post("/assessments/parse", content=json.dumps(
        {"format": "csv", "content": huge}), headers={"Content-Type": "application/json"})
    assert response.status_code == 413


def test_an_empty_data_dir_means_no_existing_dataset():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from ccs_screen.web.app import create_app
    from ccs_screen.web.settings import Settings

    settings = Settings.from_env({"CCS_DATA_DIR": ""})
    with TestClient(create_app(settings)) as client:
        assert client.get("/ready").status_code == 200
        existing = client.get("/ready/existing-data")
        assert existing.status_code == 503
        assert existing.json()["dataset"]["kind"] == "none"
        assert "user assessments" in existing.json()["problems"][0]
        wells = client.get("/wells")
        assert wells.status_code == 400 and "no existing well dataset" in wells.json()["error"]
        response = client.post("/assessments/evaluate", json={"document": user_doc(),
                                                              "samples": 100})
        assert response.status_code == 200


# -- outcome summary: each distinct blocking reason once ------------------------------


def test_identical_reasons_on_both_scenarios_are_reported_once():
    item = A.evaluate_document({"schema_version": A.SCHEMA_VERSION,
                                "assessments": [example("unavailable-depth-reference")]},
                               samples=100)["assessments"][0]
    reasons = item["outcome"]["blocking_reasons"]
    assert [r["code"] for r in reasons] == ["DEPTH_REFERENCE_NOT_ESTABLISHED"]
    assert reasons[0]["scenarios"] == ["GROUND_REFERENCE", "SEA_LEVEL_SENSITIVITY"]
    assert reasons[0]["title"] == "Depth datum not established"
    assert reasons[0]["action"] and reasons[0]["kind"] == "input"
    assert item["outcome"]["category"] == "information_needed"


def test_distinct_reasons_are_kept_and_name_their_scenarios():
    doc = user_doc()
    del doc["assessments"][0]["total_depth"]
    del doc["assessments"][0]["surface_elevation"]
    outcome = A.evaluate_document(doc, samples=100)["assessments"][0]["outcome"]
    by_code = {r["code"]: r["scenarios"] for r in outcome["blocking_reasons"]}
    assert by_code == {"TOTAL_DEPTH_NOT_RECORDED": ["GROUND_REFERENCE", "SEA_LEVEL_SENSITIVITY"],
                       "SURFACE_ELEVATION_UNAVAILABLE": ["SEA_LEVEL_SENSITIVITY"]}
    # The generic TEMPERATURE_UNAVAILABLE is replaced by the specific cause.
    assert "TEMPERATURE_UNAVAILABLE" not in by_code


@pytest.mark.parametrize("key, category", [
    ("validated", "estimate"), ("outside-envelope", "outside_validated_range"),
    ("unavailable-temperature", "information_needed")])
def test_outcome_categories(key, category):
    item = A.evaluate_document({"schema_version": A.SCHEMA_VERSION, "assessments": [example(key)]},
                               samples=100)["assessments"][0]
    assert item["outcome"]["category"] == category
    if category == "outside_validated_range":
        assert item["outcome"]["blocking_reasons"][0]["kind"] == "outside_validated_range"


def test_partial_estimate_category():
    doc = user_doc()
    del doc["assessments"][0]["surface_elevation"]
    outcome = A.evaluate_document(doc, samples=100)["assessments"][0]["outcome"]
    assert outcome["category"] == "partial_estimate"
    assert outcome["scenarios"][0]["label"] == "Water table at ground level (reference)"


# -- review 2026-10-02: numeric overflow and spreadsheet formulas ----------------------------


def test_integer_too_large_for_a_float_is_a_named_input_error():
    doc = user_doc()
    doc["assessments"][0]["storage_area"]["value"] = 10 ** 400
    _, problems = A.validate_document(doc)
    found = [p for p in errors(problems) if p["path"] == "assessments[0].storage_area.value"]
    assert [p["code"] for p in found] == ["NOT_FINITE"]


@pytest.mark.parametrize("route", ["evaluate", "validate", "parse"])
def test_integer_overflow_over_http_is_never_a_server_error(tmp_path, route):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from ccs_screen.web.app import create_app
    from ccs_screen.web.settings import Settings

    doc = user_doc()
    doc["assessments"][0]["storage_area"]["value"] = 10 ** 400
    if route == "parse":
        body = {"format": "json", "content": json.dumps(doc)}
    else:
        body = {"document": doc}
    app = create_app(Settings(data_dir=str(tmp_path / "none")))
    with TestClient(app, raise_server_exceptions=False) as c:
        response = c.post(f"/assessments/{route}", content=json.dumps(body),
                          headers={"Content-Type": "application/json"})
    assert response.status_code != 500
    payload = response.json()
    problems = payload["detail"] if route == "evaluate" else payload["problems"]
    assert response.status_code == (422 if route == "evaluate" else 200)
    assert any(p["path"] == "assessments[0].storage_area.value" and p["code"] == "NOT_FINITE"
               for p in problems)


@pytest.mark.parametrize("name", ["=1+1", "+SUM(A1)", "-2+3", "@SUM(A1)", "=HYPERLINK(\"x\")"])
def test_summary_csv_neutralises_spreadsheet_formulas(name):
    out = A.evaluate_document(user_doc(name=name), samples=200)
    rows = list(csv.DictReader(io.StringIO(out["summary_csv"])))
    assert rows and all(r["assessment_name"] == "'" + name for r in rows)
    # Numbers stay numbers; the JSON result keeps the user's literal text.
    assert all(float(r["p50_mt"]) > 0 for r in rows)
    assert out["assessments"][0]["name"] == name


@pytest.mark.parametrize("text", ["\t=1+1", "\r=1+1", "\n=1+1"])
def test_formula_escaping_covers_leading_control_characters(text):
    assert A.spreadsheet_safe(text) == "'" + text


@pytest.mark.parametrize("text", ["My site", "Site-1", "1500 m", ""])
def test_ordinary_text_is_not_escaped(text):
    assert A.spreadsheet_safe(text) == text


def _twin_readings_doc() -> dict:
    """Two Squarci-Taffi readings identical except for their depth datum."""
    reading = {"value": 331.15, "unit": "K", "depth": 1500, "depth_unit": "m",
               "depth_datum": "ground_level", "depth_convention": "TVD",
               "method": "extrapolated_squarci_taffi"}
    return user_doc(temperature_observations=[
        dict(reading), dict(reading, depth_datum="msl")])


def test_selection_names_the_submitted_observation_it_used():
    item = A.evaluate_document(_twin_readings_doc(), samples=200)["assessments"][0]
    assert statuses(item) == ["VALIDATED", "VALIDATED"]
    selection = item["result"]["temperature_selection"]
    assert selection["selected_observation"]["input_index"] == 0
    assert [o["input_index"] for o in selection["excluded_observations"]] == [1]
    assert all("input_index" in o for o in selection["eligible_observations"])



# -- review 2026-10-02 (verification): CSV parser errors block the import -----------------


def _alpha_csv_rows() -> list[dict]:
    text = (DATA / "synthetic-examples.csv").read_text("utf-8")
    lines = [line for line in text.splitlines() if not line.startswith("#")]
    return [r for r in csv.DictReader(lines) if r["assessment_id"] == "SYNTH ALPHA|1"]


def _parse(client, text: str) -> dict:
    response = client.post("/assessments/parse", json={"format": "csv", "content": text})
    assert response.status_code == 200
    return response.json()


def test_conflicting_csv_values_block_the_import_and_name_the_row(client):
    rows = _alpha_csv_rows()
    assert len(rows) == 3
    rows[1]["area_value"] = "999"
    body = _parse(client, _csv(rows))
    assert body["valid"] is False and body["import_blocked"] is True
    conflict = next(p for p in body["problems"] if p["code"] == "CONFLICTING_VALUE")
    assert conflict["row"] == 3 and "999" in conflict["message"]
    # The partial document cannot express the conflict: it holds only the first row's 20.
    assert body["document"] is None
    assert body["preview_document"]["assessments"][0]["storage_area"]["value"] == 20


def test_incomplete_observation_rows_block_the_import(client):
    rows = _alpha_csv_rows()
    rows[2]["obs_method"] = ""
    body = _parse(client, _csv(rows))
    assert body["import_blocked"] is True
    assert "INCOMPLETE_OBSERVATION" in codes(body["problems"])
    assert body["document"] is None
    assert len(body["preview_document"]["assessments"][0]["temperature_observations"]) == 2


def test_malformed_row_lengths_block_the_import(client):
    text = _csv(_alpha_csv_rows())
    lines = text.splitlines()
    lines[2] = lines[2] + ",extra"
    body = _parse(client, "\n".join(lines) + "\n")
    assert body["import_blocked"] is True
    assert next(p for p in body["problems"] if p["code"] == "ROW_LENGTH")["row"] == 3


def test_document_validation_errors_do_not_block_the_import(client):
    good = _parse(client, _csv(_alpha_csv_rows()))
    assert good["valid"] is True and good["import_blocked"] is False
    rows = _alpha_csv_rows()
    for row in rows:
        row["interval_top"] = "1600"  # consistent on every row: editable in the form
    body = _parse(client, _csv(rows))
    assert body["valid"] is False and body["import_blocked"] is False
    assert "INTERVAL_ORDER" in codes(body["problems"])


def test_json_import_is_never_blocked_by_the_parser(client):
    body = client.post("/assessments/parse", json={
        "format": "json", "content": json.dumps({"schema_version": "x", "assessments": []})}).json()
    assert body["import_blocked"] is False and body["valid"] is False


def _blocked_variants() -> dict[str, str]:
    conflict = _alpha_csv_rows()
    conflict[1]["area_value"] = "999"
    incomplete = _alpha_csv_rows()
    incomplete[2]["obs_method"] = ""
    lines = _csv(_alpha_csv_rows()).splitlines()
    lines[2] = lines[2] + ",extra"
    return {"CONFLICTING_VALUE": _csv(conflict), "INCOMPLETE_OBSERVATION": _csv(incomplete),
            "ROW_LENGTH": "\n".join(lines) + "\n"}


@pytest.mark.parametrize("code", ["CONFLICTING_VALUE", "INCOMPLETE_OBSERVATION", "ROW_LENGTH"])
def test_blocked_preview_is_rejected_by_validate_and_evaluate(client, code):
    body = _parse(client, _blocked_variants()[code])
    assert body["import_blocked"] is True and body["document"] is None
    preview = body["preview_document"]
    marker = preview["blocked_import"]
    assert code in {p["code"] for p in marker["problems"]}
    assert all(p["row"] for p in marker["problems"])

    validated = client.post("/assessments/validate", json={"document": preview}).json()
    assert validated["valid"] is False and validated["assessments"] == []
    assert [p["code"] for p in validated["problems"]] == ["IMPORT_BLOCKED"]

    evaluated = client.post("/assessments/evaluate", json={"document": preview, "samples": 200})
    assert evaluated.status_code == 422
    payload = evaluated.json()
    assert [p["code"] for p in payload["detail"]] == ["IMPORT_BLOCKED"]
    assert "assessments" not in payload and "summary_csv" not in payload


def test_blocked_marker_survives_edits_of_the_preview():
    rows = _alpha_csv_rows()
    rows[1]["area_value"] = "999"
    preview = A.parse_upload("csv", _csv(rows))["preview_document"]
    preview["assessments"][0]["storage_area"]["value"] = 999  # the user "resolves" it in place
    _, problems = A.validate_document(preview)
    assert [p["code"] for p in problems] == ["IMPORT_BLOCKED"]
    with pytest.raises(A.AssessmentError):
        A.evaluate_document(preview, samples=200)


def test_valid_and_validation_only_imports_keep_an_evaluatable_document(client):
    good = _parse(client, _csv(_alpha_csv_rows()))
    assert good["document"] is not None and good["preview_document"] is None
    assert "blocked_import" not in good["document"]
    assert client.post("/assessments/evaluate",
                       json={"document": good["document"], "samples": 200}).status_code == 200
    rows = _alpha_csv_rows()
    for row in rows:
        row["interval_top"] = "1600"
    editable = _parse(client, _csv(rows))
    assert editable["document"] is not None and editable["preview_document"] is None
    assert "blocked_import" not in editable["document"]
