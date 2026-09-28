"""Phase 1 net-to-gross disclosure: recorded, reported, never used.

What these tests defend (docs/phase1-ntg-disclosure-draft.md,
docs/net-to-gross-semantics.md):

- ``net_to_gross`` is caller-declared provenance about ``thickness_m``. It is a
  dedicated dataclass, not an ``Assumption``, not in ``ASSUMABLE`` and never in
  ``screening_inputs``.
- A declared value must carry ``net_criterion`` and ``net_basis``; the range is
  ``0 < low <= high <= 1``. CSLF's 0.25-0.75 is not a validation bound.
- It changes no number. Capacity and the Monte Carlo output are compared with
  ``==``, not ``approx``: approx would hide exactly the drift being guarded.
- It is never inferred -- not from gross thickness, not from any record field.

Phase 14. ``thickness_m`` and its net-to-gross disclosure belong to the
NOT_VALIDATED legacy paths (owner decision O2), so the tests above the
"approved model" section run the literature parameter set through the legacy
resolver (its example JSON file) and are otherwise unchanged. On the approved
model the ratio refers to ``h_g = z_base - z_top`` and is a consistency check
only (A3, A7, S12); that is tested at the end.

Runs against the synthetic pilot dataset, so it needs no access to ``data/``.
"""

from __future__ import annotations

import dataclasses
import inspect
import math
from pathlib import Path

import pytest

from ccs_screen import api
from ccs_screen.ingest.assumptions import ASSUMABLE, Assumption, AssumptionError
from ccs_screen.ingest.records import ThicknessKind
from ccs_screen.ingest.scenario import SCENARIO_PARAMETERS, apply_scenario
from ccs_screen.monte_carlo import UniformPriors, run_capacity_mc

from test_ingest_pipeline import PO_WELLS, POZZI_STORICI, _write_xlsx

pytest.importorskip("openpyxl")

ROOT = Path(__file__).resolve().parents[1]
#: The literature parameter set through the legacy resolver (NOT_VALIDATED, O2).
LEGACY_LITERATURE = str(ROOT / "examples" / "literature-screening-v1.json")
VALID = {"area_m2": 8.0e7, "thickness_m": 35.0}
APPROVED = {"area_m2": 8.0e7, "z_top": 1400.0, "z_base": 1527.0}
NTG = {"low": 0.30, "high": 0.55, "net_criterion": "porosity_permeability",
       "net_basis": "log_derived"}
CAPACITY_NUMBERS = ("p10", "p50", "p90", "mean", "n_samples", "deterministic")


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("ntg_data")
    _write_xlsx(d / "Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx")
    (d / "pozzi-storici.csv").write_bytes(POZZI_STORICI.encode("cp1252"))
    (d / "po_wells_clean.csv").write_bytes(PO_WELLS.encode("cp1252"))
    return d


@pytest.fixture(autouse=True)
def _clean_cache():
    api.clear_cache()
    yield
    api.clear_cache()


def with_ntg(**overrides):
    return {**VALID, "net_to_gross": {**NTG, **overrides}}


def screen(data_dir, user_inputs=VALID, **kw):
    kw.setdefault("samples", 200)
    kw.setdefault("scenario", LEGACY_LITERATURE)
    return api.screen_well("SALUZZO|1", user_inputs, data_dir=data_dir, **kw)


def numbers(payload):
    cap = payload["scenario_based_capacity_mt"]
    return {k: cap[k] for k in CAPACITY_NUMBERS}


def codes(payload):
    return [w["code"] for w in payload["interpretation"]["warnings"]]


# -- validation --------------------------------------------------------------


def test_valid_range_is_accepted_and_exposed(data_dir):
    payload = screen(data_dir, with_ntg(cutoff_note="phi >= 8%, k >= 1 mD",
                                        thickness_convention="measured"))
    assert payload["status"] == "screened"
    prov = payload["thickness_provenance"]
    assert prov["declared"] is True
    assert prov["net_to_gross_status"] == "declared"
    ntg = prov["net_to_gross"]
    assert (ntg["low"], ntg["high"]) == (0.30, 0.55)
    assert ntg["net_criterion"] == "porosity_permeability"
    assert ntg["net_basis"] == "log_derived"
    assert ntg["evidence_class"] == "site_specific"
    assert ntg["confidence"] == "high"
    assert ntg["cutoff_note"] == "phi >= 8%, k >= 1 mD"
    assert ntg["thickness_convention"] == "measured"
    assert ntg["is_point"] is False
    assert ntg["unit"] == "-"


@pytest.mark.parametrize("field", ["net_basis", "net_criterion"])
def test_basis_and_criterion_are_required(data_dir, field):
    raw = {k: v for k, v in NTG.items() if k != field}
    with pytest.raises(api.ApiError, match=field):
        api.NetToGross.from_mapping(raw)
    payload = screen(data_dir, {**VALID, "net_to_gross": raw})
    assert payload["status"] == "blocked"
    assert field in payload["error"]
    assert payload["scenario_based_capacity_mt"] is None


@pytest.mark.parametrize("field", ["net_basis", "net_criterion"])
def test_basis_and_criterion_cannot_be_null(field):
    with pytest.raises(api.ApiError, match=field):
        api.NetToGross.from_mapping({**NTG, field: None})


@pytest.mark.parametrize("field,value", [
    ("net_criterion", "net_sand"), ("net_criterion", ""),
    ("net_basis", "guess"), ("thickness_convention", "vertical"),
])
def test_unknown_enum_values_are_rejected(field, value):
    with pytest.raises(api.ApiError, match=field):
        api.NetToGross.from_mapping({**NTG, field: value})


def test_unknown_ntg_field_is_rejected():
    with pytest.raises(api.ApiError, match="unknown net_to_gross field"):
        api.NetToGross.from_mapping({**NTG, "gross_thickness_m": 900.0})


def test_low_above_high_is_rejected():
    with pytest.raises(api.ApiError, match="low must be <= high"):
        api.NetToGross.from_mapping({**NTG, "low": 0.6, "high": 0.4})


@pytest.mark.parametrize("value", [0.0, -0.1, 1.01, 2.0])
@pytest.mark.parametrize("side", ["low", "high"])
def test_outside_unit_interval_is_rejected(side, value):
    raw = {**NTG, "low": 0.1, "high": 1.0, side: value}
    with pytest.raises(api.ApiError, match=r"\(0, 1\]"):
        api.NetToGross.from_mapping(raw)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize("side", ["low", "high"])
def test_nan_and_infinity_are_rejected(side, value):
    raw = {**NTG, side: value}
    with pytest.raises(api.ApiError, match="finite"):
        api.NetToGross.from_mapping(raw)


@pytest.mark.parametrize("value", [True, "0.4", None])
def test_non_numeric_bounds_are_rejected(value):
    with pytest.raises(api.ApiError):
        api.NetToGross.from_mapping({**NTG, "low": value})


@pytest.mark.parametrize("low,high", [(0.05, 0.15), (0.85, 0.95), (0.01, 1.0), (1.0, 1.0)])
def test_outside_cslf_range_but_inside_unit_interval_is_accepted(data_dir, low, high):
    """0.25-0.75 is CSLF's E_h, not a validation bound for an Italian value."""
    payload = screen(data_dir, with_ntg(low=low, high=high))
    assert payload["status"] == "screened"
    ntg = payload["thickness_provenance"]["net_to_gross"]
    assert (ntg["low"], ntg["high"]) == (low, high)
    # The evidence class follows the caller's basis, not a generic citation.
    assert ntg["evidence_class"] == "site_specific"


@pytest.mark.parametrize("criterion", [c.value for c in api.NetCriterion])
def test_every_criterion_is_accepted(criterion):
    ntg = api.NetToGross.from_mapping({**NTG, "net_criterion": criterion})
    assert ntg.net_criterion.value == criterion


def test_carbonate_with_porosity_permeability_is_accepted():
    """The DOE/CSLF criterion is lithology-neutral: carbonate needs no other field."""
    ntg = api.NetToGross.from_mapping({
        **NTG, "net_criterion": "porosity_permeability", "net_basis": "core_derived",
        "cutoff_note": "vuggy dolomite; phi >= 5% and k >= 0.5 mD",
    })
    assert ntg.net_criterion is api.NetCriterion.POROSITY_PERMEABILITY
    # No lithology field exists to contradict it.
    assert "lithology" not in {f.name for f in dataclasses.fields(api.NetToGross)}


def test_point_value_is_accepted_with_a_warning(data_dir):
    payload = screen(data_dir, with_ntg(low=0.4, high=0.4))
    assert payload["status"] == "screened"
    assert payload["thickness_provenance"]["net_to_gross"]["is_point"] is True
    assert "net_to_gross_point_value" in codes(payload)
    assert "net_to_gross_not_declared" not in codes(payload)


@pytest.mark.parametrize("basis,evidence,confidence", [
    ("log_derived", "site_specific", "high"),
    ("core_derived", "site_specific", "high"),
    ("model_derived", "site_specific", "medium"),
    ("analogue", "regional", "low"),
    ("assumed", "user_input", "low"),
    ("unknown", "unsupported", "none"),
])
def test_basis_maps_onto_existing_evidence_vocabulary(basis, evidence, confidence):
    out = api.NetToGross.from_mapping({**NTG, "net_basis": basis}).to_dict()
    assert (out["evidence_class"], out["confidence"]) == (evidence, confidence)


# -- disclosure --------------------------------------------------------------


def test_absent_ntg_is_explicitly_reported_as_unknown(data_dir):
    payload = screen(data_dir)
    prov = payload["thickness_provenance"]
    assert prov["declared"] is False
    assert prov["net_to_gross"] is None
    assert prov["net_to_gross_status"] == "unknown -- not supplied by the caller"
    assert prov["used_in_calculation"] is False
    assert prov["thickness_kind"] == ThicknessKind.NET_STORAGE.value
    warning = {w["code"]: w for w in payload["interpretation"]["warnings"]}[
        "net_to_gross_not_declared"]
    assert warning["invalidates_result"] is False
    assert warning["correction_applied"] is False


def test_used_in_calculation_is_false_when_declared(data_dir):
    payload = screen(data_dir, with_ntg())
    assert payload["thickness_provenance"]["used_in_calculation"] is False
    assert payload["thickness_provenance"]["net_to_gross"]["used_in_calculation"] is False
    assert "net_to_gross_not_declared" not in codes(payload)


def test_compare_temperature_methods_discloses_the_same_way(data_dir):
    absent = api.compare_temperature_methods("SALUZZO|1", VALID, data_dir=data_dir, samples=50)
    declared = api.compare_temperature_methods("SALUZZO|1", with_ntg(), data_dir=data_dir,
                                               samples=50)
    assert absent["thickness_provenance"]["declared"] is False
    assert "net_to_gross_not_declared" in codes(absent)
    assert declared["thickness_provenance"]["net_to_gross"]["low"] == 0.30
    assert "net_to_gross_not_declared" not in codes(declared)
    assert ([v["p50_mt"] for v in absent["variants"]]
            == [v["p50_mt"] for v in declared["variants"]])


@pytest.mark.parametrize("user_inputs", [None, VALID])
def test_screening_funnel_emits_no_ntg_warning_for_absence(data_dir, user_inputs):
    payload = api.screening_funnel(scenario=LEGACY_LITERATURE, user_inputs=user_inputs,
                                   data_dir=data_dir, samples=20)
    assert not any(c.startswith("net_to_gross") for c in codes(payload))
    assert "thickness_provenance" not in payload
    approved = api.screening_funnel(data_dir=data_dir, samples=20)
    assert not any(c.startswith("net_to_gross") for c in codes(approved))


def test_input_free_endpoints_emit_no_ntg_warning(data_dir):
    for payload in (api.get_well("SALUZZO|1", data_dir),
                    api.required_user_inputs("SALUZZO|1", data_dir=data_dir)):
        assert not any(c.startswith("net_to_gross") for c in codes(payload))


# -- backward compatibility --------------------------------------------------


def test_absent_ntg_does_not_break_existing_callers(data_dir):
    by_mapping = screen(data_dir, VALID)
    by_object = screen(data_dir, api.UserInputs(area_m2=8.0e7, thickness_m=35.0))
    assert by_mapping["status"] == by_object["status"] == "screened"
    assert numbers(by_mapping) == numbers(by_object)
    # user_inputs keeps its exact pre-Phase-1 shape: NTG is reported elsewhere.
    assert set(by_mapping["user_inputs"]) == {"area_m2", "thickness_m"}
    assert set(screen(data_dir, with_ntg())["user_inputs"]) == {"area_m2", "thickness_m"}


def test_explicit_null_ntg_is_the_same_as_absent(data_dir):
    assert numbers(screen(data_dir, {**VALID, "net_to_gross": None})) == numbers(screen(data_dir))


def test_malformed_ntg_blocks_rather_than_screening(data_dir):
    payload = screen(data_dir, {**VALID, "net_to_gross": 0.4})
    assert payload["status"] == "blocked"
    assert "net_to_gross must be an object" in payload["error"]


# -- inertness ---------------------------------------------------------------


def test_ntg_is_not_an_assumption_and_not_assumable():
    assert "net_to_gross" not in ASSUMABLE
    assert "net_to_gross" not in SCENARIO_PARAMETERS
    assert ASSUMABLE == ("area_m2", "porosity", "pressure_pa", "storage_efficiency",
                         "thickness_m")
    with pytest.raises(AssumptionError):
        Assumption(parameter="net_to_gross", value=0.4, author="x", rationale="y")
    assert not issubclass(api.NetToGross, Assumption)
    assert "net_to_gross" not in api.REQUIRED_USER_INPUTS
    assert "net_to_gross" not in api.LEGACY_REQUIRED_USER_INPUTS


def test_ntg_never_becomes_an_assumption_via_user_inputs():
    inputs = api.UserInputs.from_mapping(with_ntg())
    assert [a.parameter for a in inputs.as_assumptions()] == list(api.LEGACY_REQUIRED_USER_INPUTS)


def test_ntg_does_not_enter_screening_inputs(data_dir):
    payload = screen(data_dir, with_ntg())
    assert "net_to_gross" not in payload["screening_inputs"]
    partition = [n for k in api.INPUT_PARTITION_KEYS for n in payload[k]]
    assert "net_to_gross" not in partition
    assert sorted(partition) == sorted(payload["screening_inputs"])
    assert len(partition) == len(set(partition)) == 6


@pytest.mark.parametrize("ntg", [
    NTG,
    {**NTG, "low": 0.05, "high": 0.05},
    {**NTG, "low": 0.9, "high": 1.0, "net_basis": "unknown", "net_criterion": "unspecified"},
])
def test_ntg_does_not_alter_capacity(data_dir, ntg):
    without = screen(data_dir, VALID, samples=2000, seed=42)
    declared = screen(data_dir, {**VALID, "net_to_gross": ntg}, samples=2000, seed=42)
    assert numbers(declared) == numbers(without)
    assert declared["screening_inputs"] == without["screening_inputs"]


def test_ntg_does_not_alter_monte_carlo_output(data_dir):
    """NTG never reaches the config, so the sampled array is bitwise identical."""
    base = api._scenario(api.DEFAULT_SCENARIO)
    record = next(r for r in api.load_records(data_dir) if r.canonical_id == "SALUZZO|1")
    configs = [
        apply_scenario(record, api._with_user_inputs(base, api.UserInputs.from_mapping(ui)))
        for ui in (VALID, with_ntg(), with_ntg(low=0.1, high=0.1))
    ]
    priors = [c.prior_ranges() for c in configs]
    assert priors[0] == priors[1] == priors[2]
    runs = [run_capacity_mc(UniformPriors(**p).sample(500, seed=7)) for p in priors]
    assert runs[0].masses_mt.tobytes() == runs[1].masses_mt.tobytes() == runs[2].masses_mt.tobytes()
    assert (runs[0].p10_mt, runs[0].p50_mt, runs[0].p90_mt) == (
        runs[1].p10_mt, runs[1].p50_mt, runs[1].p90_mt)


# -- no inference ------------------------------------------------------------


def test_no_automatic_derivation_from_thickness_fields(data_dir):
    record = next(r for r in api.load_records(data_dir) if r.canonical_id == "SALUZZO|1")
    assert record.gross_thickness_m.is_present, "fixture must carry a gross thickness"
    # Only area and net thickness supplied: nothing fills net_to_gross in.
    assert api.UserInputs.from_mapping(VALID).net_to_gross is None
    assert screen(data_dir)["thickness_provenance"]["net_to_gross"] is None
    # The only constructor path is from a caller mapping; none takes a record.
    factories = {name for name, member in inspect.getmembers(api.NetToGross)
                 if isinstance(inspect.getattr_static(api.NetToGross, name), classmethod)}
    assert factories == {"from_mapping"}
    # No defaults: a value cannot appear unless the caller states one.
    fields = {f.name: f for f in dataclasses.fields(api.NetToGross)}
    for name in ("low", "high", "net_criterion", "net_basis"):
        assert fields[name].default is dataclasses.MISSING
    # No code path reads gross thickness as a number to divide by.
    source = inspect.getsource(api)
    assert "gross_thickness_m.value" not in source
    assert "net_thickness / gross" not in source


def test_no_numeric_cutoff_or_default_value_is_carried():
    """cutoff_note is free text; there is no GR/porosity/permeability threshold field."""
    assert {f.name for f in dataclasses.fields(api.NetToGross)} == set(api.NET_TO_GROSS_FIELDS)
    assert set(api.NET_TO_GROSS_FIELDS) == {
        "low", "high", "net_criterion", "net_basis", "cutoff_note", "thickness_convention"}
    ntg = api.NetToGross.from_mapping({**NTG, "cutoff_note": "GR < 60 API"})
    assert ntg.cutoff_note == "GR < 60 API"


def test_thickness_kind_is_unchanged():
    assert [(k.name, k.value) for k in ThicknessKind] == [
        ("GROSS_STRATIGRAPHIC", "gross_stratigraphic"),
        ("NET_STORAGE", "net_storage"),
        ("AQUIFER_HYDRAULIC", "aquifer_hydraulic"),
    ]


# -- HTTP --------------------------------------------------------------------


@pytest.fixture(scope="module")
def client(data_dir):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from ccs_screen.web.app import create_app
    from ccs_screen.web.settings import Settings

    with TestClient(create_app(Settings(data_dir=str(data_dir)))) as c:
        yield c


def test_http_accepts_ntg_and_matches_python(client, data_dir):
    """Over HTTP only built-in scenarios are accepted: legacy = a placeholder."""
    body = {"user_inputs": with_ntg(), "samples": 200, "scenario": "sensitivity"}
    over_http = client.post("/wells/SALUZZO|1/screen", json=body).json()
    direct = screen(data_dir, with_ntg(), scenario="sensitivity")
    assert over_http["thickness_provenance"] == direct["thickness_provenance"]
    assert numbers(over_http) == numbers(direct)


def test_http_without_ntg_matches_python(client, data_dir):
    over_http = client.post("/wells/SALUZZO|1/screen",
                            json={"user_inputs": VALID, "samples": 200,
                                  "scenario": "sensitivity"}).json()
    assert over_http["thickness_provenance"]["declared"] is False
    assert numbers(over_http) == numbers(screen(data_dir, scenario="sensitivity"))


@pytest.mark.parametrize("bad", [
    {k: v for k, v in NTG.items() if k != "net_basis"},
    {k: v for k, v in NTG.items() if k != "net_criterion"},
    {**NTG, "low": 0.7, "high": 0.2},
    {**NTG, "low": 0.0},
    {**NTG, "high": 1.5},
    {**NTG, "net_criterion": "net_sand"},
    {**NTG, "extra": 1},
])
def test_http_rejects_malformed_ntg(client, bad):
    for inputs in (VALID, APPROVED):
        resp = client.post("/wells/SALUZZO|1/screen",
                           json={"user_inputs": {**inputs, "net_to_gross": bad}, "samples": 50})
        assert resp.status_code in (400, 422)


# -- approved model (A3, A7, S12) --------------------------------------------


@pytest.fixture
def ground_level(data_dir, monkeypatch):
    from ccs_screen.ingest.units import DepthDatum

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


def approved(data_dir, user_inputs=APPROVED, **kw):
    kw.setdefault("samples", 300)
    kw.setdefault("seed", 42)
    return api.screen_well("SALUZZO|1", user_inputs, data_dir=data_dir, **kw)


@pytest.mark.parametrize("ntg", [
    NTG,
    {**NTG, "low": 0.05, "high": 0.05},
    {**NTG, "low": 0.9, "high": 1.0, "net_basis": "unknown", "net_criterion": "unspecified"},
])
def test_approved_ntg_is_a_check_only_and_changes_nothing(ground_level, ntg):
    """A4, S12: the gross-to-net reduction lives inside E; NTG never enters."""
    without = approved(ground_level)
    declared = approved(ground_level, {**APPROVED, "net_to_gross": ntg})
    assert declared["water_level_scenarios"] == without["water_level_scenarios"]
    assert declared["storage_interval"] == without["storage_interval"]
    check = declared["net_to_gross_check"]
    assert check["used_in_calculation"] is False
    assert check["net_to_gross"]["used_in_calculation"] is False
    assert check["relative_to"] == "h_g = z_base - z_top"
    assert check["consistency"] == "0 < h_net <= h_g holds by construction"


def test_approved_ntg_definition_refers_to_the_interval(ground_level):
    check = approved(ground_level, {**APPROVED, "net_to_gross": NTG})["net_to_gross_check"]
    definition = check["net_to_gross"]["definition"]
    assert "h_net / h_g" in definition and "Not identified with DOE hn/hg" in definition
    assert "divided" in check["usage"]


def test_approved_path_emits_no_ntg_warning(ground_level):
    """The Finding 9.1 double count cannot arise on the approved path (A4)."""
    for body in (APPROVED, {**APPROVED, "net_to_gross": {**NTG, "low": 0.4, "high": 0.4}}):
        assert not any(c.startswith("net_to_gross") for c in codes(approved(ground_level, body)))


def test_approved_absent_ntg_is_reported_as_not_declared(ground_level):
    check = approved(ground_level)["net_to_gross_check"]
    assert check["declared"] is False and check["net_to_gross"] is None


def test_approved_malformed_ntg_blocks(data_dir):
    payload = approved(data_dir, {**APPROVED, "net_to_gross": 0.4})
    assert payload["status"] == "blocked"
    assert "net_to_gross must be an object" in payload["error"]
