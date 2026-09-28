"""The public screening API contract (Python level).

What these tests defend: a caller can never obtain a capacity number without
supplying the inputs the source data does not contain, can never confuse a
user input with a measurement, and always receives the interpretation block
that says what the number is not.

Phase 14 split the API into two explicitly separated paths:

* the **approved model** (``literature-screening-v1``, the default): inputs
  ``area_m2``, ``z_top``, ``z_base``; both named water-level scenarios with
  their statuses and diagnostics. Every ingested well has an UNKNOWN depth
  reference, so on the synthetic pilot data the approved result is UNAVAILABLE
  (C2); numbers are exercised on a copy whose reference is ground level.
* the **NOT_VALIDATED legacy paths** (owner decision O2): the placeholder
  scenarios and scenario JSON files, with the legacy inputs ``area_m2`` and
  ``thickness_m``. The legacy provenance tests below run the literature
  parameter set through the legacy resolver via its example JSON file, which
  is what they exercised before Phase 14; their expectations are unchanged
  apart from the NOT_VALIDATED labels.

Runs against the synthetic pilot dataset, so it needs no access to ``data/``.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from ccs_screen import api
from ccs_screen.approved_model import StorageInterval
from ccs_screen.config import REQUIRED_FIELDS
from ccs_screen.ingest.assumptions import EvidenceClass
from ccs_screen.ingest.units import DepthDatum

from test_ingest_pipeline import PO_WELLS, POZZI_STORICI, _write_xlsx

openpyxl = pytest.importorskip("openpyxl")

ROOT = Path(__file__).resolve().parents[1]

#: Approved-model inputs. SALUZZO|1 (synthetic) has TD 1527.5 m and a
#: Squarci-Taffi observation at 1522.6 m, inside this interval.
APPROVED = {"area_m2": 8.0e7, "z_top": 1400.0, "z_base": 1527.0}

#: Legacy inputs (O2: preserved for the NOT_VALIDATED paths).
LEGACY = {"area_m2": 8.0e7, "thickness_m": 35.0}

#: The literature parameter set through the legacy resolver: a scenario JSON
#: path, which the Python API accepts as a NOT_VALIDATED legacy scenario (O2).
LEGACY_LITERATURE = str(ROOT / "examples" / "literature-screening-v1.json")


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("api_data")
    _write_xlsx(d / "Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx")
    (d / "pozzi-storici.csv").write_bytes(POZZI_STORICI.encode("cp1252"))
    (d / "po_wells_clean.csv").write_bytes(PO_WELLS.encode("cp1252"))
    return d


@pytest.fixture(autouse=True)
def _clean_cache():
    api.clear_cache()
    yield
    api.clear_cache()


@pytest.fixture
def ground_level(data_dir, monkeypatch):
    """The synthetic records, with SALUZZO|1's references set to ground level.

    Test-only: no ingested well has an established reference. This is how the
    approved model's numeric path is exercised through the public API.
    """
    records = []
    for record in api.load_records(data_dir):
        if record.canonical_id == "SALUZZO|1":
            record = dataclasses.replace(
                record, depth_datum=DepthDatum.GROUND_LEVEL,
                temperatures=tuple(dataclasses.replace(o, depth_datum=DepthDatum.GROUND_LEVEL)
                                   for o in record.temperatures))
        records.append(record)
    frozen = tuple(records)
    monkeypatch.setattr(api, "load_records", lambda *_a, **_k: frozen)
    return data_dir


def screen(data_dir, **kw):
    """Approved-model screening of SALUZZO|1."""
    kw.setdefault("user_inputs", APPROVED)
    kw.setdefault("samples", 200)
    return api.screen_well("SALUZZO|1", data_dir=data_dir, **kw)


def legacy(data_dir, **kw):
    """Legacy (NOT_VALIDATED) screening of SALUZZO|1 with the literature parameters."""
    kw.setdefault("user_inputs", LEGACY)
    kw.setdefault("samples", 200)
    kw.setdefault("scenario", LEGACY_LITERATURE)
    return api.screen_well("SALUZZO|1", data_dir=data_dir, **kw)


def warnings_of(payload):
    return {w["code"]: w for w in payload["interpretation"]["warnings"]}


def scenarios_of(payload):
    return {s["name"]: s for s in payload["water_level_scenarios"]}


# -- discovery ---------------------------------------------------------------


def test_list_wells(data_dir):
    wells = api.list_wells(data_dir)
    entry = next(w for w in wells if w["well_id"] == "SALUZZO|1")
    assert entry["depth_m"] == pytest.approx(1527.5)
    assert entry["has_temperature"] is True
    assert entry["screenable_without_user_inputs"] is False
    assert entry["depth_datum"] == "unknown"
    reference = entry["approved_model_depth_reference"]
    assert (reference["status"], reference["diagnostic"]) == (
        "UNAVAILABLE", "DEPTH_REFERENCE_NOT_ESTABLISHED")
    json.dumps(wells)


def test_list_wells_reports_alternate_spellings(data_dir):
    entry = next(w for w in api.list_wells(data_dir) if w["well_id"] == "SALUZZO|1")
    assert {"SALUZZO 1", "SALUZZO 001"} <= set(entry["original_names"])


def test_get_well_carries_provenance_and_interpretation(data_dir):
    payload = api.get_well("SALUZZO|1", data_dir=data_dir)
    assert payload["canonical_id"] == "SALUZZO|1"
    assert payload["required_user_inputs"] == ["area_m2", "z_top", "z_base"]
    assert payload["required_user_inputs"] == list(api.REQUIRED_USER_INPUTS)
    assert payload["interpretation"]["site_specific"] is False
    assert payload["fields"]["temperature_k"]["provenance"] == "derived"
    assert payload["approved_model_depth_reference"]["status"] == "UNAVAILABLE"
    json.dumps(payload)


def test_unknown_well_is_rejected(data_dir):
    with pytest.raises(api.UnknownWellError):
        api.get_well("NO|SUCH|WELL", data_dir=data_dir)


def test_unknown_well_error_is_an_api_error():
    """The HTTP layer relies on this for its 404/400 split."""
    assert issubclass(api.UnknownWellError, api.ApiError)


def test_missing_data_dir_is_rejected():
    with pytest.raises(api.ApiError):
        api.list_wells("no-such-directory")


def test_required_user_inputs_tells_a_ui_what_to_ask(data_dir):
    """Approved model: area and the storage interval; blocked by the datum (C2)."""
    spec = api.required_user_inputs("SALUZZO|1", data_dir=data_dir)
    fields = {f["field"]: f for f in spec["required"]}
    assert set(fields) == {"area_m2", "z_top", "z_base"}
    assert fields["area_m2"]["unit"] == "m2"
    assert fields["z_top"]["unit"] == fields["z_base"]["unit"] == "m"
    assert spec["model_path"] == "APPROVED_MODEL"
    assert spec["can_be_screened_with_user_inputs"] is False
    (blocker,) = spec["blocked_by_missing_source_data"]
    assert blocker["field"] == "depth_datum"
    assert blocker["reason"].startswith("DEPTH_REFERENCE_NOT_ESTABLISHED")
    json.dumps(spec)


def test_required_user_inputs_for_a_legacy_scenario(data_dir):
    """O2: legacy scenarios keep their inputs and carry the NOT_VALIDATED label."""
    spec = api.required_user_inputs("SALUZZO|1", scenario=LEGACY_LITERATURE, data_dir=data_dir)
    assert {f["field"] for f in spec["required"]} == {"area_m2", "thickness_m"}
    assert spec["can_be_screened_with_user_inputs"] is True
    assert spec["validation_status"] == "NOT_VALIDATED"
    assert spec["model_path"] == "LEGACY_NOT_VALIDATED"


def test_approved_model_is_evaluable_once_the_reference_is_ground_level(ground_level):
    spec = api.required_user_inputs("SALUZZO|1", data_dir=ground_level)
    assert spec["can_be_screened_with_user_inputs"] is True
    assert spec["blocked_by_missing_source_data"] == []


def test_input_spec_states_what_it_is_never_inferred_from(data_dir):
    fields = {f["field"]: f for f in
              api.required_user_inputs("SALUZZO|1", data_dir=data_dir)["required"]}
    area = " ".join(fields["area_m2"]["not_inferred_from"])
    assert "licence" in area and "concession" in area and "spacing" in area and "radius" in area
    for name in ("z_top", "z_base"):
        assert "total well depth" in fields[name]["not_inferred_from"]
        assert "stratigraphic units" in fields[name]["not_inferred_from"]
    legacy_fields = {f["field"]: f for f in api.required_user_inputs(
        "SALUZZO|1", scenario=LEGACY_LITERATURE, data_dir=data_dir)["required"]}
    assert "gross stratigraphic thickness" in legacy_fields["thickness_m"]["not_inferred_from"]


def test_list_scenarios_exposes_evidence_posture():
    scenarios = {s["name"]: s for s in api.list_scenarios()}
    lit = scenarios["literature-screening-v1"]
    assert lit["literature_derived"] is True
    assert lit["supplies_user_inputs"] == []
    assert set(lit["evidence_classes"]) == {"generic", "regional"}
    json.dumps(api.list_scenarios())


def test_list_scenarios_states_each_validation_status():
    """O2: exactly one built-in runs the approved model; the rest are NOT_VALIDATED."""
    scenarios = {s["name"]: s for s in api.list_scenarios()}
    assert scenarios["literature-screening-v1"]["validation_status"] == "APPROVED_MODEL"
    assert scenarios["literature-screening-v1"]["required_user_inputs"] == [
        "area_m2", "z_top", "z_base"]
    for name in ("conservative-placeholder", "central-placeholder", "sensitivity-placeholder",
                 "source-data-only"):
        assert scenarios[name]["validation_status"] == "NOT_VALIDATED", name
        assert scenarios[name]["required_user_inputs"] == ["area_m2", "thickness_m"], name
        assert "NOT_VALIDATED" in scenarios[name]["description"] or name == "source-data-only"


# -- missing / invalid user inputs -------------------------------------------


def test_missing_both_inputs_blocks(data_dir):
    result = api.screen_well("SALUZZO|1", data_dir=data_dir)
    assert result["status"] == "blocked"
    assert result["model_path"] == "APPROVED_MODEL"
    assert result["reason"] == "missing_or_invalid_user_inputs"
    assert result["water_level_scenarios"] == []
    assert "scenario_based_capacity_mt" not in result


@pytest.mark.parametrize("omitted", ["area_m2", "z_top", "z_base"])
def test_missing_one_input_blocks_and_names_it(data_dir, omitted):
    body = {k: v for k, v in APPROVED.items() if k != omitted}
    result = api.screen_well("SALUZZO|1", body, data_dir=data_dir)
    assert result["status"] == "blocked"
    assert omitted in result["error"]


@pytest.mark.parametrize(
    "body",
    [
        {**APPROVED, "area_m2": 0},
        {**APPROVED, "area_m2": -1.0},
        {**APPROVED, "area_m2": float("nan")},
        {**APPROVED, "area_m2": float("inf")},
        {**APPROVED, "area_m2": "large"},
        {**APPROVED, "area_m2": None},
        {**APPROVED, "area_m2": True},
        {**APPROVED, "z_top": -1.0},
        {**APPROVED, "z_top": 1600.0},
        {**APPROVED, "z_base": 1400.0},
        {**APPROVED, "z_top": float("nan")},
        {**APPROVED, "z_base": float("inf")},
        {**APPROVED, "z_top": None},
        {**APPROVED, "z_base": "deep"},
    ],
)
def test_invalid_values_block_without_a_number(data_dir, body):
    result = api.screen_well("SALUZZO|1", body, data_dir=data_dir)
    assert result["status"] == "blocked"
    assert result["water_level_scenarios"] == []


def test_thickness_is_not_an_approved_input(data_dir):
    """A1/M1: the thickness term is the derived h_g; thickness_m is rejected."""
    result = api.screen_well("SALUZZO|1", {**APPROVED, "thickness_m": 35.0}, data_dir=data_dir)
    assert result["status"] == "blocked"
    assert "not an input of the approved model" in result["error"]
    legacy_only = api.screen_well("SALUZZO|1", LEGACY, data_dir=data_dir)
    assert legacy_only["status"] == "blocked"
    assert "z_top" in legacy_only["error"] or "thickness_m" in legacy_only["error"]


def test_legacy_inputs_object_is_refused_by_the_approved_model(data_dir):
    result = api.screen_well("SALUZZO|1", api.UserInputs(area_m2=8e7, thickness_m=35.0),
                             data_dir=data_dir)
    assert result["status"] == "blocked"
    assert "not an input of the approved model" in result["error"]


def test_approved_inputs_object_is_refused_by_a_legacy_scenario(data_dir):
    inputs = api.ApprovedUserInputs(area_m2=8e7, interval=StorageInterval(1400.0, 1527.0))
    result = api.screen_well("SALUZZO|1", inputs, scenario="sensitivity", data_dir=data_dir)
    assert result["status"] == "blocked"
    assert result["validation_status"] == "NOT_VALIDATED"


def test_unknown_user_input_is_rejected(data_dir):
    result = api.screen_well("SALUZZO|1", {**APPROVED, "porosity": 0.2}, data_dir=data_dir)
    assert result["status"] == "blocked"
    assert "unknown user input" in result["error"]


def test_user_inputs_have_no_defaults():
    """A default here would be a hidden geological assumption."""
    approved = inspect.signature(api.ApprovedUserInputs)
    for name in ("area_m2", "interval"):
        assert approved.parameters[name].default is inspect.Parameter.empty
    interval = inspect.signature(StorageInterval)
    for name in ("z_top_m", "z_base_m"):
        assert interval.parameters[name].default is inspect.Parameter.empty
    legacy_signature = inspect.signature(api.UserInputs)
    for name in api.LEGACY_REQUIRED_USER_INPUTS:
        assert legacy_signature.parameters[name].default is inspect.Parameter.empty


# -- approved model: both named scenarios ------------------------------------


def test_real_well_reference_makes_every_named_scenario_unavailable(data_dir):
    """C2 consequence: every ingested well's depth reference is UNKNOWN."""
    result = screen(data_dir)
    assert result["status"] == "evaluated"
    assert result["model_path"] == "APPROVED_MODEL"
    scenarios = scenarios_of(result)
    assert list(scenarios) == ["GROUND_REFERENCE", "SEA_LEVEL_SENSITIVITY"]
    for scenario in scenarios.values():
        assert scenario["validation_status"] == "UNAVAILABLE"
        assert scenario["capacity_mt"] is None and scenario["diagnostic_capacity_mt"] is None
        assert scenario["diagnostics"][0]["code"] == "DEPTH_REFERENCE_NOT_ESTABLISHED"
    assert result["storage_interval"]["h_g_m"] is None
    json.dumps(result)


def test_approved_model_with_a_ground_reference_reports_both_scenarios(ground_level):
    result = screen(ground_level)
    scenarios = scenarios_of(result)
    ground, sea = scenarios["GROUND_REFERENCE"], scenarios["SEA_LEVEL_SENSITIVITY"]
    assert ground["validation_status"] == sea["validation_status"] == "VALIDATED"
    assert (ground["z_wl_m"], sea["z_wl_m"]) == (0.0, 310.0)
    assert result["storage_interval"]["h_g_m"] == 127.0
    assert result["storage_interval"]["z_state_m"] == pytest.approx(1463.5)
    assert result["temperature_selection"]["temperature_k"] == pytest.approx(318.15)
    assert result["temperature_selection"]["selected_observation"]["method"] == (
        "extrapolated_squarci_taffi")
    for scenario in (ground, sea):
        capacity = scenario["capacity_mt"]
        assert capacity["p10"] < capacity["p50"] < capacity["p90"]
        assert capacity["n_samples"] == 200
        assert capacity["percentile_convention"]["convention"] == "statistical"
        assert capacity["uncertainty_band"]["includes_systematic_bias"] is False
        assert capacity["validation_status"] == "VALIDATED"
    effect = result["systematic_effect"]["individual_effects"][0]
    assert effect["p50_difference_mt"] == pytest.approx(
        sea["capacity_mt"]["p50"] - ground["capacity_mt"]["p50"])
    assert result["systematic_effect"]["multiplied_correction_factor"] is None
    json.dumps(result)


def test_approved_user_inputs_drive_the_result(ground_level):
    small = screen(ground_level, user_inputs={**APPROVED, "area_m2": 5e7})
    large = screen(ground_level, user_inputs={**APPROVED, "area_m2": 1.5e8})
    p50 = lambda r: scenarios_of(r)["GROUND_REFERENCE"]["capacity_mt"]["p50"]  # noqa: E731
    assert p50(large) == pytest.approx(3 * p50(small), rel=1e-12)


def test_approved_payload_never_carries_a_legacy_capacity_key(ground_level):
    result = screen(ground_level)
    for forbidden in ("scenario_based_capacity_mt", "capacity_mt", "storage_capacity",
                      "resource", "certified", "validation_status"):
        assert forbidden not in result


def test_approved_payload_records_net_to_gross_as_a_check_only(ground_level):
    ntg = {"low": 0.3, "high": 0.5, "net_criterion": "porosity_permeability",
           "net_basis": "log_derived"}
    with_ntg = screen(ground_level, user_inputs={**APPROVED, "net_to_gross": ntg}, seed=5)
    without = screen(ground_level, seed=5)
    assert with_ntg["water_level_scenarios"] == without["water_level_scenarios"]
    check = with_ntg["net_to_gross_check"]
    assert check["declared"] is True and check["used_in_calculation"] is False
    assert check["relative_to"] == "h_g = z_base - z_top"
    assert "h_net / h_g" in check["net_to_gross"]["definition"]


# -- legacy path: labels only, behaviour unchanged (O2) -----------------------


def test_legacy_inputs_produce_a_not_validated_capacity(data_dir):
    result = legacy(data_dir)
    assert result["status"] == "screened"
    assert result["validation_status"] == "NOT_VALIDATED"
    assert result["model_path"] == "LEGACY_NOT_VALIDATED"
    capacity = result["scenario_based_capacity_mt"]
    assert capacity["p10"] < capacity["p50"] < capacity["p90"]
    assert capacity["n_samples"] == 200
    assert capacity["validation_status"] == "NOT_VALIDATED"
    assert warnings_of(result)["not_validated_legacy_path"]["invalidates_result"] is False


def test_legacy_user_inputs_actually_drive_the_result(data_dir):
    small = legacy(data_dir, user_inputs={"area_m2": 5e7, "thickness_m": 25.0})
    large = legacy(data_dir, user_inputs={"area_m2": 1.5e8, "thickness_m": 55.0})
    assert large["scenario_based_capacity_mt"]["p50"] > small["scenario_based_capacity_mt"]["p50"]


def test_capacity_key_is_named_scenario_based(data_dir):
    result = legacy(data_dir)
    assert "scenario_based_capacity_mt" in result
    for forbidden in ("capacity_mt", "storage_capacity", "resource", "certified"):
        assert forbidden not in result


def test_legacy_numbers_equal_a_direct_engine_run(data_dir):
    """O2: the legacy arithmetic is unchanged -- a pass-through of the engine."""
    from ccs_screen.ingest.scenario import apply_scenario, load_scenario
    from ccs_screen.monte_carlo import UniformPriors, run_capacity_mc

    result = legacy(data_dir, seed=9)
    record = next(r for r in api.load_records(data_dir) if r.canonical_id == "SALUZZO|1")
    active = api._with_user_inputs(load_scenario(LEGACY_LITERATURE),
                                   api.UserInputs.from_mapping(LEGACY))
    mc = run_capacity_mc(UniformPriors(**apply_scenario(record, active).prior_ranges())
                         .sample(200, seed=9))
    capacity = result["scenario_based_capacity_mt"]
    assert (capacity["p10"], capacity["p50"], capacity["p90"]) == (mc.p10_mt, mc.p50_mt, mc.p90_mt)


# -- the provenance distinctions (legacy resolver) ---------------------------


def test_input_partition_is_disjoint_and_complete(data_dir):
    result = legacy(data_dir)
    buckets = {k: result[k] for k in api.INPUT_PARTITION_KEYS}
    flat = [name for names in buckets.values() for name in names]
    assert len(flat) == len(set(flat))
    assert set(flat) == set(REQUIRED_FIELDS)


def test_each_provenance_class_lands_in_the_right_bucket(data_dir):
    result = legacy(data_dir)
    assert result["user_supplied_inputs"] == ["area_m2", "thickness_m"]
    assert result["modelled_inputs"] == ["pressure_pa"]
    assert result["source_derived_inputs"] == ["temperature_k"]
    assert set(result["assumed_inputs"]) == {"porosity", "storage_efficiency"}


def test_labels_distinguish_user_from_literature(data_dir):
    inputs = legacy(data_dir)["screening_inputs"]
    assert inputs["area_m2"]["label"] == "USER"
    assert inputs["area_m2"]["evidence_class"] == EvidenceClass.USER_INPUT.value
    assert inputs["porosity"]["label"] == "ASSUMED"
    assert inputs["porosity"]["evidence_class"] == "regional"
    assert inputs["storage_efficiency"]["evidence_class"] == "generic"


def test_pressure_stays_modelled(data_dir):
    pressure = legacy(data_dir)["screening_inputs"]["pressure_pa"]
    assert pressure["label"] == "MODELLED"
    assert pressure["assumed"] is False
    assert "rho*g*z" in pressure["derivation"]


def test_every_input_serialises_with_the_required_fields(data_dir):
    payload = json.loads(json.dumps(legacy(data_dir)))
    for name, entry in payload["screening_inputs"].items():
        for key in ("value", "unit", "evidence_class", "assumed", "provenance", "label"):
            assert key in entry, f"{name} missing {key}"


def test_assumed_and_user_inputs_carry_rationale_and_citation(data_dir):
    inputs = legacy(data_dir)["screening_inputs"]
    for name in ("area_m2", "thickness_m", "porosity", "storage_efficiency"):
        assert inputs[name]["rationale"], name
        assert inputs[name]["citation"] is not None, name
    assert inputs["storage_efficiency"]["citation"]["year"] == 2008
    assert inputs["porosity"]["citation"]["year"] == 2011
    assert inputs["area_m2"]["citation"]["evidence_class"] == "user_input"


# -- source precedence -------------------------------------------------------


def test_source_temperature_is_not_overridden(data_dir):
    result = legacy(data_dir)
    assert result["screening_inputs"]["temperature_k"]["assumed"] is False
    assert result["temperature"]["method"] == "extrapolated_squarci_taffi"


def test_temperature_cannot_be_supplied_as_a_user_input(data_dir):
    for body, scenario in ((APPROVED, api.DEFAULT_SCENARIO), (LEGACY, LEGACY_LITERATURE)):
        result = api.screen_well("SALUZZO|1", {**body, "temperature_k": 400.0},
                                 scenario=scenario, data_dir=data_dir)
        assert result["status"] == "blocked"
        assert "temperature_k" in result["error"]


def test_well_without_temperature_stays_blocked_even_with_inputs(data_dir):
    result = api.screen_well("ASIGLIANO|1", LEGACY, scenario=LEGACY_LITERATURE,
                             data_dir=data_dir, samples=50)
    assert result["status"] == "blocked"
    assert result["scenario_based_capacity_mt"] is None
    assert "temperature_k" in result["missing_fields"]


def test_scenario_value_for_a_user_input_does_not_shadow_the_caller(data_dir):
    result = api.screen_well(
        "SALUZZO|1", {"area_m2": 1.234e8, "thickness_m": 42.0},
        scenario="sensitivity", data_dir=data_dir, samples=100,
    )
    assert result["screening_inputs"]["area_m2"]["value"] == pytest.approx(1.234e8)
    assert result["screening_inputs"]["area_m2"]["label"] == "USER"


# -- interpretation ----------------------------------------------------------


def test_interpretation_block_is_explicit(data_dir):
    for payload in (screen(data_dir), legacy(data_dir)):
        interpretation = payload["interpretation"]
        assert interpretation["type"] == "scenario_based_capacity"
        assert interpretation["site_specific"] is False
        assert interpretation["certified"] is False
        assert interpretation["proven_resource"] is False


def test_approved_interpretation_states_the_interval_policy_and_s7(data_dir):
    interpretation = screen(data_dir)["interpretation"]
    assert "storage-assessment interval" in interpretation["storage_interval_policy"]
    assert "conditional on the declared model" in interpretation["percentile_interpretation"]
    assert "net_thickness_policy" not in interpretation


def test_interpretation_appears_on_every_response_shape(data_dir):
    responses = [
        api.get_well("SALUZZO|1", data_dir=data_dir),
        api.required_user_inputs("SALUZZO|1", data_dir=data_dir),
        api.screen_well("SALUZZO|1", data_dir=data_dir),
        screen(data_dir),
        legacy(data_dir),
        api.compare_temperature_methods("SALUZZO|1", LEGACY, data_dir=data_dir, samples=50),
        api.screening_funnel(data_dir=data_dir, samples=20),
        api.screening_funnel(scenario=LEGACY_LITERATURE, data_dir=data_dir, user_inputs=LEGACY,
                             samples=20),
    ]
    for response in responses:
        assert response["interpretation"]["type"] == "scenario_based_capacity"


def test_scale_mismatch_warning_is_present_for_literature_scenario(data_dir):
    for payload in (screen(data_dir), legacy(data_dir)):
        warning = warnings_of(payload)["scale_mismatch_basin_vs_closure"]
        assert warning["message"] == (
            "Literature-constrained porosity and storage-efficiency ranges are not "
            "site-specific closure-scale calibrations."
        )
        assert set(warning["affects"]) == {"porosity", "storage_efficiency"}
        assert warning["invalidates_result"] is False
        assert warning["correction_applied"] is False
    assert "storage-assessment interval" in warnings_of(screen(data_dir))[
        "scale_mismatch_basin_vs_closure"]["detail"]


def test_no_scale_warning_for_a_placeholder_scenario(data_dir):
    result = api.screen_well("SALUZZO|1", LEGACY, scenario="sensitivity",
                             data_dir=data_dir, samples=100)
    assert "scale_mismatch_basin_vs_closure" not in warnings_of(result)


def test_interpretation_warnings_do_not_leak_between_calls(data_dir, ground_level):
    first = legacy(data_dir)
    second = api.screen_well("SALUZZO|1", LEGACY, scenario="sensitivity",
                             data_dir=data_dir, samples=50)
    approved = screen(ground_level)
    # Per-request disclosures (net-to-gross, uncertainty band) attach to both
    # legacy calls; the scenario-specific scale warning to the first only; the
    # O2 label leads every legacy result.
    per_request = ["net_to_gross_not_declared",
                   "sampled_uncertainty_band_excludes_systematic_bias"]
    assert list(warnings_of(first)) == ["not_validated_legacy_path",
                                        "scale_mismatch_basin_vs_closure", *per_request]
    assert list(warnings_of(second)) == ["not_validated_legacy_path", *per_request]
    assert list(warnings_of(approved)) == ["scale_mismatch_basin_vs_closure",
                                           "sampled_uncertainty_band_excludes_systematic_bias"]
    assert api.INTERPRETATION["warnings"] == []
    assert api.APPROVED_INTERPRETATION["warnings"] == []


# -- samples bounds ----------------------------------------------------------


def test_published_limits():
    limits = api.REQUEST_LIMITS["samples"]
    assert limits["min"] == api.MIN_SAMPLES == 1
    assert limits["max"] == api.MAX_SAMPLES == 50_000
    assert limits["clamped"] is False


@pytest.mark.parametrize("samples", [1, 2_000, 50_000])
def test_valid_sample_counts(samples):
    assert api.validate_samples(samples) == samples


@pytest.mark.parametrize(
    "samples,fragment",
    [
        (0, "must be >= 1"),
        (-1, "must be >= 1"),
        (50_001, "must be <= 50000"),
        (10_000_000, "must be <= 50000"),
        (2.5, "expected an integer"),
        ("2000", "expected an integer"),
        (None, "expected an integer"),
    ],
)
def test_invalid_sample_counts_are_rejected(samples, fragment):
    with pytest.raises(api.ApiError) as excinfo:
        api.validate_samples(samples)
    assert fragment in str(excinfo.value)


@pytest.mark.parametrize("samples", [True, False])
def test_booleans_are_rejected_as_sample_counts(samples):
    """bool is an int subclass; True would otherwise mean one realisation."""
    with pytest.raises(api.ApiError) as excinfo:
        api.validate_samples(samples)
    assert "bool" in str(excinfo.value)


def test_excessive_sample_count_is_rejected_not_clamped(data_dir):
    with pytest.raises(api.ApiError) as excinfo:
        api.screen_well("SALUZZO|1", APPROVED, data_dir=data_dir, samples=10_000_000)
    assert "not clamped" in str(excinfo.value)


def test_sample_count_is_honoured_exactly(data_dir, ground_level):
    for samples in (50, 777):
        assert legacy(data_dir, samples=samples)["scenario_based_capacity_mt"]["n_samples"] == samples
        approved = screen(ground_level, samples=samples)
        assert approved["n_samples"] == samples
        for scenario in approved["water_level_scenarios"]:
            assert scenario["capacity_mt"]["n_samples"] == samples
            assert scenario["envelope"]["n_realisations"] == samples


# -- cache safety ------------------------------------------------------------


def test_concurrent_cold_cache_normalizes_once(data_dir, monkeypatch):
    """A cold-cache burst must not multiply the most expensive operation."""
    api.clear_cache()
    calls = []
    original = api.WellNormalizer

    class CountingNormalizer(original):  # type: ignore[misc,valid-type]
        def run(self):
            calls.append(1)
            return super().run()

    monkeypatch.setattr(api, "WellNormalizer", CountingNormalizer)
    barrier = threading.Barrier(8)

    def load():
        barrier.wait()
        return api.load_records(data_dir)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = [f.result() for f in [pool.submit(load) for _ in range(8)]]

    assert len(calls) == 1, f"normalized {len(calls)} times under a concurrent burst"
    assert all(r is results[0] for r in results)


def test_concurrent_screening_is_stable(data_dir):
    def run():
        result = legacy(data_dir, samples=100)
        return round(result["scenario_based_capacity_mt"]["p50"], 6)

    with ThreadPoolExecutor(max_workers=8) as pool:
        values = {f.result() for f in [pool.submit(run) for _ in range(24)]}
    assert len(values) == 1, f"screening was not deterministic under threads: {values}"


def test_concurrent_approved_screening_is_stable(ground_level):
    def run():
        result = screen(ground_level, samples=100)
        return round(scenarios_of(result)["GROUND_REFERENCE"]["capacity_mt"]["p50"], 9)

    with ThreadPoolExecutor(max_workers=8) as pool:
        values = {f.result() for f in [pool.submit(run) for _ in range(16)]}
    assert len(values) == 1, f"approved screening was not deterministic under threads: {values}"


def test_refresh_rebuilds_rather_than_mutating(data_dir):
    first = api.load_records(data_dir)
    assert api.load_records(data_dir) is first
    assert api.load_records(data_dir, refresh=True) is not first


def test_failed_load_does_not_poison_the_cache():
    for _ in range(2):
        with pytest.raises(api.ApiError):
            api.load_records("no-such-directory")


# -- temperature comparison / funnel -----------------------------------------


def test_compare_temperature_methods(data_dir):
    """O2 consequence 2: a NOT_VALIDATED legacy diagnostic, with legacy inputs."""
    result = api.compare_temperature_methods("SALUZZO|1", LEGACY, data_dir=data_dir, samples=100)
    assert result["status"] == "compared"
    assert result["selected_method"] == "extrapolated_squarci_taffi"
    assert result["p50_spread_percent"] > 0
    assert result["validation_status"] == "NOT_VALIDATED"
    assert result["model_path"] == "LEGACY_NOT_VALIDATED"
    assert "M3/R1" in result["validation_note"]
    json.dumps(result)


def test_compare_requires_user_inputs_too(data_dir):
    assert api.compare_temperature_methods("SALUZZO|1", data_dir=data_dir)["status"] == "blocked"


def test_compare_refuses_the_approved_interval(data_dir):
    result = api.compare_temperature_methods("SALUZZO|1", APPROVED, data_dir=data_dir)
    assert result["status"] == "blocked"
    assert "legacy diagnostic" in result["error"]


def test_approved_funnel_reports_depth_reference_readiness(data_dir):
    funnel = api.screening_funnel(data_dir=data_dir, samples=20)
    assert funnel["model_path"] == "APPROVED_MODEL"
    assert funnel["approved_results_computed"] == 0
    assert funnel["depth_reference"] == {"ESTABLISHED_GROUND_LEVEL": 0,
                                         "DEPTH_REFERENCE_NOT_ESTABLISHED": funnel["total_wells"]}
    assert funnel["required_user_inputs"] == ["area_m2", "z_top", "z_base"]


def test_approved_funnel_refuses_a_fleet_level_interval(data_dir):
    with pytest.raises(api.ApiError, match="for each well"):
        api.screening_funnel(data_dir=data_dir, user_inputs=APPROVED, samples=20)


def test_funnel_without_user_inputs_screens_nothing(data_dir):
    funnel = api.screening_funnel(scenario=LEGACY_LITERATURE, data_dir=data_dir, samples=20)
    assert funnel["screenable"] == 0
    assert funnel["source_complete"] == 0
    assert funnel["validation_status"] == "NOT_VALIDATED"


def test_funnel_with_user_inputs_screens_wells(data_dir):
    funnel = api.screening_funnel(scenario=LEGACY_LITERATURE, data_dir=data_dir,
                                  user_inputs=LEGACY, samples=20)
    assert funnel["screenable"] >= 1
    assert funnel["source_complete"] == 0
    assert funnel["validation_status"] == "NOT_VALIDATED"
