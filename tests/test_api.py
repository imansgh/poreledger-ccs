"""The public screening API contract.

What these tests defend: a caller can never obtain a capacity number without
supplying area and net thickness, can never confuse a user input with a
measurement, and always receives the interpretation block that says what the
number is not.

Runs against the synthetic pilot dataset, so it needs no access to ``data/``.
"""

from __future__ import annotations

import json

import pytest

from ccs_screen import api
from ccs_screen.config import REQUIRED_FIELDS
from ccs_screen.ingest.assumptions import EvidenceClass

from test_ingest_pipeline import PO_WELLS, POZZI_STORICI, _write_xlsx

openpyxl = pytest.importorskip("openpyxl")

VALID = {"area_m2": 8.0e7, "thickness_m": 35.0}


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


def screen(data_dir, **kw):
    kw.setdefault("user_inputs", VALID)
    kw.setdefault("samples", 200)
    return api.screen_well("SALUZZO|1", data_dir=data_dir, **kw)


# -- discovery ---------------------------------------------------------------


def test_list_wells(data_dir):
    wells = api.list_wells(data_dir)
    ids = {w["well_id"] for w in wells}
    assert "SALUZZO|1" in ids
    entry = next(w for w in wells if w["well_id"] == "SALUZZO|1")
    assert entry["depth_m"] == pytest.approx(1527.5)
    assert entry["has_temperature"] is True
    assert entry["screenable_without_user_inputs"] is False
    json.dumps(wells)


def test_list_wells_reports_alternate_spellings(data_dir):
    entry = next(w for w in api.list_wells(data_dir) if w["well_id"] == "SALUZZO|1")
    assert {"SALUZZO 1", "SALUZZO 001"} <= set(entry["original_names"])


def test_get_well_carries_provenance_and_interpretation(data_dir):
    payload = api.get_well("SALUZZO|1", data_dir=data_dir)
    assert payload["canonical_id"] == "SALUZZO|1"
    assert payload["required_user_inputs"] == list(api.REQUIRED_USER_INPUTS)
    assert payload["interpretation"]["site_specific"] is False
    assert payload["fields"]["temperature_k"]["provenance"] == "derived"
    json.dumps(payload)


def test_unknown_well_is_rejected(data_dir):
    with pytest.raises(api.UnknownWellError):
        api.get_well("NO|SUCH|WELL", data_dir=data_dir)


def test_missing_data_dir_is_rejected():
    with pytest.raises(api.ApiError):
        api.list_wells("no-such-directory")


def test_required_user_inputs_tells_a_ui_what_to_ask(data_dir):
    spec = api.required_user_inputs("SALUZZO|1", data_dir=data_dir)
    fields = {f["field"]: f for f in spec["required"]}
    assert set(fields) == {"area_m2", "thickness_m"}
    assert fields["area_m2"]["unit"] == "m2"
    assert fields["thickness_m"]["unit"] == "m"
    assert all(f["needed"] for f in fields.values())
    assert spec["can_be_screened_with_user_inputs"] is True
    json.dumps(spec)


def test_input_spec_states_what_it_is_never_inferred_from(data_dir):
    fields = {f["field"]: f for f in
              api.required_user_inputs("SALUZZO|1", data_dir=data_dir)["required"]}
    area = " ".join(fields["area_m2"]["not_inferred_from"])
    assert "licence" in area and "concession" in area and "spacing" in area and "radius" in area
    assert "gross stratigraphic thickness" in fields["thickness_m"]["not_inferred_from"]


def test_list_scenarios_exposes_evidence_posture():
    scenarios = {s["name"]: s for s in api.list_scenarios()}
    lit = scenarios["literature-screening-v1"]
    assert lit["literature_derived"] is True
    assert lit["supplies_user_inputs"] == [], "the literature scenario supplies neither"
    assert set(lit["evidence_classes"]) == {"generic", "regional"}
    assert "placeholder" in scenarios["central-placeholder"]["evidence_classes"]
    json.dumps(api.list_scenarios())


# -- missing / invalid user inputs -------------------------------------------


def test_missing_both_inputs_blocks(data_dir):
    result = api.screen_well("SALUZZO|1", data_dir=data_dir)
    assert result["status"] == "blocked"
    assert result["reason"] == "missing_or_invalid_user_inputs"
    assert result["scenario_based_capacity_mt"] is None
    assert "area_m2" in result["error"] and "thickness_m" in result["error"]


@pytest.mark.parametrize("omitted", ["area_m2", "thickness_m"])
def test_missing_one_input_blocks_and_names_it(data_dir, omitted):
    body = {k: v for k, v in VALID.items() if k != omitted}
    result = api.screen_well("SALUZZO|1", body, data_dir=data_dir)
    assert result["status"] == "blocked"
    assert omitted in result["error"]
    assert result["scenario_based_capacity_mt"] is None


@pytest.mark.parametrize(
    "body",
    [
        {"area_m2": 0, "thickness_m": 35.0},
        {"area_m2": -1.0, "thickness_m": 35.0},
        {"area_m2": 8e7, "thickness_m": 0},
        {"area_m2": 8e7, "thickness_m": -5.0},
        {"area_m2": float("nan"), "thickness_m": 35.0},
        {"area_m2": float("inf"), "thickness_m": 35.0},
        {"area_m2": "large", "thickness_m": 35.0},
        {"area_m2": None, "thickness_m": 35.0},
        {"area_m2": True, "thickness_m": 35.0},
    ],
)
def test_invalid_values_block_without_a_number(data_dir, body):
    result = api.screen_well("SALUZZO|1", body, data_dir=data_dir)
    assert result["status"] == "blocked"
    assert result["scenario_based_capacity_mt"] is None
    assert result["error"]


def test_unknown_user_input_is_rejected(data_dir):
    result = api.screen_well("SALUZZO|1", {**VALID, "porosity": 0.2}, data_dir=data_dir)
    assert result["status"] == "blocked"
    assert "porosity" in result["error"]
    assert "unknown user input" in result["error"]


def test_blocked_result_still_tells_the_caller_what_is_needed(data_dir):
    result = api.screen_well("SALUZZO|1", data_dir=data_dir)
    fields = {f["field"] for f in result["required_user_inputs"]}
    assert fields == {"area_m2", "thickness_m"}
    assert result["interpretation"]["type"] == "scenario_based_capacity"
    json.dumps(result)


def test_user_inputs_object_rejects_bad_values():
    with pytest.raises(api.ApiError):
        api.UserInputs(area_m2=0.0, thickness_m=35.0)
    with pytest.raises(TypeError):
        api.UserInputs(area_m2=8e7)  # type: ignore[call-arg]


def test_user_inputs_have_no_defaults():
    """A default here would be a hidden geological assumption."""
    import inspect

    signature = inspect.signature(api.UserInputs)
    for name in api.REQUIRED_USER_INPUTS:
        assert signature.parameters[name].default is inspect.Parameter.empty


# -- successful screening ----------------------------------------------------


def test_explicit_inputs_produce_a_capacity(data_dir):
    result = screen(data_dir)
    assert result["status"] == "screened"
    capacity = result["scenario_based_capacity_mt"]
    assert capacity["p10"] < capacity["p50"] < capacity["p90"]
    assert capacity["n_samples"] == 200


def test_user_inputs_are_echoed_with_units(data_dir):
    echoed = screen(data_dir)["user_inputs"]
    assert echoed["area_m2"] == {"value": 8.0e7, "unit": "m2"}
    assert echoed["thickness_m"] == {"value": 35.0, "unit": "m"}


def test_user_inputs_actually_drive_the_result(data_dir):
    small = screen(data_dir, user_inputs={"area_m2": 5e7, "thickness_m": 25.0})
    large = screen(data_dir, user_inputs={"area_m2": 1.5e8, "thickness_m": 55.0})
    assert large["scenario_based_capacity_mt"]["p50"] > small["scenario_based_capacity_mt"]["p50"]


def test_capacity_key_is_named_scenario_based(data_dir):
    """The key itself carries the caveat, not only the prose."""
    result = screen(data_dir)
    assert "scenario_based_capacity_mt" in result
    for forbidden in ("capacity_mt", "storage_capacity", "resource", "certified"):
        assert forbidden not in result


# -- the five provenance distinctions ----------------------------------------


def test_input_partition_is_disjoint_and_complete(data_dir):
    result = screen(data_dir)
    buckets = {k: result[k] for k in api.INPUT_PARTITION_KEYS}
    flat = [name for names in buckets.values() for name in names]
    assert len(flat) == len(set(flat)), "a parameter must appear in exactly one bucket"
    assert set(flat) == set(REQUIRED_FIELDS)


def test_each_provenance_class_lands_in_the_right_bucket(data_dir):
    result = screen(data_dir)
    assert result["user_supplied_inputs"] == ["area_m2", "thickness_m"]
    assert result["modelled_inputs"] == ["pressure_pa"]
    assert result["source_derived_inputs"] == ["temperature_k"]
    assert set(result["assumed_inputs"]) == {"porosity", "storage_efficiency"}


def test_labels_distinguish_user_from_literature(data_dir):
    inputs = screen(data_dir)["screening_inputs"]
    assert inputs["area_m2"]["label"] == "USER"
    assert inputs["area_m2"]["evidence_class"] == EvidenceClass.USER_INPUT.value
    assert inputs["porosity"]["label"] == "ASSUMED"
    assert inputs["porosity"]["evidence_class"] == "regional"
    assert inputs["storage_efficiency"]["evidence_class"] == "generic"


def test_pressure_stays_modelled(data_dir):
    pressure = screen(data_dir)["screening_inputs"]["pressure_pa"]
    assert pressure["label"] == "MODELLED"
    assert pressure["assumed"] is False
    assert "rho*g*z" in pressure["derivation"]


def test_label_legend_covers_every_label_used(data_dir):
    result = screen(data_dir)
    used = {i["label"] for i in result["screening_inputs"].values()}
    assert used <= set(result["label_legend"])


def test_every_input_serialises_with_the_required_fields(data_dir):
    payload = json.loads(json.dumps(screen(data_dir)))
    for name, entry in payload["screening_inputs"].items():
        assert "value" in entry, name
        assert "unit" in entry, name
        assert "evidence_class" in entry, name
        assert "assumed" in entry, name
        assert "provenance" in entry, name
        assert "label" in entry, name


def test_assumed_and_user_inputs_carry_rationale_and_citation(data_dir):
    inputs = screen(data_dir)["screening_inputs"]
    for name in ("area_m2", "thickness_m", "porosity", "storage_efficiency"):
        assert inputs[name]["rationale"], name
        assert inputs[name]["citation"] is not None, name
    assert inputs["storage_efficiency"]["citation"]["year"] == 2008
    assert inputs["porosity"]["citation"]["year"] == 2011
    assert inputs["area_m2"]["citation"]["evidence_class"] == "user_input"


def test_user_citation_does_not_claim_literature_support(data_dir):
    citation = screen(data_dir)["screening_inputs"]["area_m2"]["citation"]
    assert "no literature range" in citation["text"]
    assert citation["evidence_class"] == "user_input"


# -- source precedence -------------------------------------------------------


def test_source_temperature_is_not_overridden(data_dir):
    result = screen(data_dir)
    assert result["screening_inputs"]["temperature_k"]["assumed"] is False
    assert result["temperature"]["method"] == "extrapolated_squarci_taffi"
    assert result["temperature"]["provenance"] == "derived"


def test_temperature_cannot_be_supplied_as_a_user_input(data_dir):
    result = api.screen_well("SALUZZO|1", {**VALID, "temperature_k": 400.0}, data_dir=data_dir)
    assert result["status"] == "blocked"
    assert "temperature_k" in result["error"]


def test_well_without_temperature_stays_blocked_even_with_inputs(data_dir):
    result = api.screen_well("ASIGLIANO|1", VALID, data_dir=data_dir, samples=50)
    assert result["status"] == "blocked"
    assert result["scenario_based_capacity_mt"] is None
    assert "temperature_k" in result["missing_fields"]


def test_scenario_value_for_a_user_input_does_not_shadow_the_caller(data_dir):
    """A scenario that also supplies area must not win over the request."""
    result = api.screen_well(
        "SALUZZO|1", {"area_m2": 1.234e8, "thickness_m": 42.0},
        scenario="sensitivity", data_dir=data_dir, samples=100,
    )
    assert result["status"] == "screened"
    assert result["screening_inputs"]["area_m2"]["value"] == pytest.approx(1.234e8)
    assert result["screening_inputs"]["area_m2"]["label"] == "USER"


# -- interpretation metadata -------------------------------------------------


def test_interpretation_block_is_present_and_explicit(data_dir):
    interpretation = screen(data_dir)["interpretation"]
    assert interpretation["type"] == "scenario_based_capacity"
    assert interpretation["site_specific"] is False
    assert interpretation["certified"] is False
    assert interpretation["proven_resource"] is False


def test_interpretation_appears_on_every_response_shape(data_dir):
    responses = [
        api.get_well("SALUZZO|1", data_dir=data_dir),
        api.required_user_inputs("SALUZZO|1", data_dir=data_dir),
        api.screen_well("SALUZZO|1", data_dir=data_dir),                 # blocked
        screen(data_dir),                                                # screened
        api.compare_temperature_methods("SALUZZO|1", VALID, data_dir=data_dir, samples=50),
        api.screening_funnel(data_dir=data_dir, user_inputs=VALID, samples=20),
    ]
    for response in responses:
        assert response["interpretation"]["type"] == "scenario_based_capacity"
        assert response["interpretation"]["site_specific"] is False


def test_interpretation_carries_both_policies(data_dir):
    interpretation = screen(data_dir)["interpretation"]
    assert "licence boundaries" in interpretation["area_policy"]
    assert "not derived from gross" in interpretation["net_thickness_policy"]


def test_no_response_claims_certified_or_proven(data_dir):
    """Loaded phrases may appear only inside a denial, never as a claim.

    The structured booleans are the contract; this guards the prose that sits
    beside them, since a substring alone cannot tell "certified capacity" from
    "not a certified capacity".
    """
    result = screen(data_dir)
    assert result["interpretation"]["certified"] is False
    assert result["interpretation"]["proven_resource"] is False
    assert result["interpretation"]["site_specific"] is False

    blob = json.dumps(result).lower()
    for phrase in ("certified storage capacity", "proven storage resource",
                   "site-specific estimate"):
        index = 0
        while (index := blob.find(phrase, index)) != -1:
            preceding = blob[max(0, index - 12):index]
            assert "not " in preceding, (
                f"{phrase!r} appears without a negation: ...{blob[max(0, index-40):index+40]}..."
            )
            index += len(phrase)


# -- temperature comparison --------------------------------------------------


def test_compare_temperature_methods(data_dir):
    result = api.compare_temperature_methods("SALUZZO|1", VALID, data_dir=data_dir, samples=100)
    assert result["status"] == "compared"
    assert result["selected_method"] == "extrapolated_squarci_taffi"
    assert len(result["variants"]) >= 2
    assert result["p50_spread_percent"] > 0
    assert "No temperature method is authoritative" in result["note"]
    json.dumps(result)


def test_compare_requires_user_inputs_too(data_dir):
    result = api.compare_temperature_methods("SALUZZO|1", data_dir=data_dir)
    assert result["status"] == "blocked"


# -- funnel ------------------------------------------------------------------


def test_funnel_without_user_inputs_screens_nothing(data_dir):
    funnel = api.screening_funnel(data_dir=data_dir, samples=20)
    assert funnel["screenable"] == 0
    assert funnel["source_complete"] == 0


def test_funnel_with_user_inputs_screens_wells(data_dir):
    funnel = api.screening_funnel(data_dir=data_dir, user_inputs=VALID, samples=20)
    assert funnel["screenable"] >= 1
    assert funnel["source_complete"] == 0, "nothing is screenable from source data alone"
    json.dumps(funnel)


# -- caching -----------------------------------------------------------------


def test_records_are_cached_between_calls(data_dir):
    first = api.load_records(data_dir)
    assert api.load_records(data_dir) is first
    assert api.load_records(data_dir, refresh=True) is not first
