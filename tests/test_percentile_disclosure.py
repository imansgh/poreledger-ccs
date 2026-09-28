"""Findings 7.5 and 12.5: percentile semantics and uncertainty-band disclosure.

7.5 -- the payload states the convention where the percentiles are returned:
P10 = low case, P50 = median case, P90 = high case (statistical, not petroleum).

12.5 -- the payload states that P10-P90 is the model's sampled uncertainty band
and does not necessarily contain systematic/model bias.

Both are disclosure only. The final section pins the audited baseline cases to
the exact IEEE-754 values captured before the disclosure bundle was applied, so
any numerical drift -- one unit in the last place -- fails.

The synthetic-data section needs no ``data/``; the pinned section skips without it.

Phase 14. The audited baseline was captured on the pre-contract path, which is
now a NOT_VALIDATED legacy path (owner decision O2) with unchanged arithmetic.
The bit-exact pins therefore run the literature parameter set through the
legacy resolver (its example JSON file) and must still match to the last bit;
under the approved model the same real wells are UNAVAILABLE, because no
ingested depth reference is established (C2). Both are pinned below.
"""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

import pytest

from ccs_screen import api
from ccs_screen.ingest.scenario import apply_scenario
from ccs_screen.monte_carlo import UniformPriors, run_capacity_mc

from test_ingest_pipeline import PO_WELLS, POZZI_STORICI, _write_xlsx

pytest.importorskip("openpyxl")

VALID = {"area_m2": 8.0e7, "thickness_m": 35.0}
APPROVED = {"area_m2": 8.0e7, "z_top": 1400.0, "z_base": 1527.0}
BAND_CODE = "sampled_uncertainty_band_excludes_systematic_bias"
ROOT = Path(__file__).resolve().parents[1]
#: The literature parameter set through the legacy resolver (NOT_VALIDATED, O2).
LEGACY_LITERATURE = str(ROOT / "examples" / "literature-screening-v1.json")


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("pct_data")
    _write_xlsx(d / "Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx")
    (d / "pozzi-storici.csv").write_bytes(POZZI_STORICI.encode("cp1252"))
    (d / "po_wells_clean.csv").write_bytes(PO_WELLS.encode("cp1252"))
    return d


@pytest.fixture(autouse=True)
def _clean_cache():
    api.clear_cache()
    yield
    api.clear_cache()


@pytest.fixture(scope="module")
def payload(data_dir):
    api.clear_cache()
    return api.screen_well("SALUZZO|1", VALID, scenario=LEGACY_LITERATURE, data_dir=data_dir,
                           samples=500, seed=3)


@pytest.fixture
def approved_payload(data_dir, monkeypatch):
    """Approved model on SALUZZO|1 with a (test-only) ground-level reference."""
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
    return api.screen_well("SALUZZO|1", APPROVED, data_dir=data_dir, samples=500, seed=3)


# -- Finding 7.5 -------------------------------------------------------------


def test_percentile_convention_is_in_the_capacity_block(payload):
    conv = payload["scenario_based_capacity_mt"]["percentile_convention"]
    assert conv["convention"] == "statistical"
    assert conv["p10"].startswith("low case")
    assert conv["p50"].startswith("median case")
    assert conv["p90"].startswith("high case")
    assert "P10 = low case, P50 = median case, P90 = high case" in conv["note"]
    assert "NOT the petroleum" in conv["note"]


def test_percentile_order_matches_the_stated_convention(payload):
    cap = payload["scenario_based_capacity_mt"]
    assert cap["p10"] < cap["p50"] < cap["p90"]


def test_approved_validated_percentiles_carry_both_disclosures_and_s7(approved_payload):
    for scenario in approved_payload["water_level_scenarios"]:
        cap = scenario["capacity_mt"]
        assert cap["percentile_convention"]["convention"] == "statistical"
        assert cap["uncertainty_band"]["code"] == BAND_CODE
        assert cap["p10"] < cap["p50"] < cap["p90"]
        assert "not total accuracy" in cap["interpretation"]
    codes = [w["code"] for w in approved_payload["interpretation"]["warnings"]]
    assert BAND_CODE in codes


def test_temperature_comparison_states_the_convention(data_dir):
    out = api.compare_temperature_methods("SALUZZO|1", VALID, data_dir=data_dir, samples=50)
    assert out["percentile_convention"]["p50"].startswith("median case")


# -- Finding 12.5 ------------------------------------------------------------


def test_uncertainty_band_disclosure_is_in_the_capacity_block(payload):
    band = payload["scenario_based_capacity_mt"]["uncertainty_band"]
    assert band["code"] == BAND_CODE
    assert band["interval"] == "p10-p90"
    assert band["lower_bound"].startswith("p10") and "lower sampled case" in band["lower_bound"]
    assert band["upper_bound"].startswith("p90") and "upper sampled case" in band["upper_bound"]
    assert band["includes_systematic_bias"] is False
    assert band["values_adjusted"] is False
    text = band["statement"]
    assert "sampled uncertainty band" in text
    assert "P10 is the lower sampled case and P90 is the upper sampled case" in text
    assert "correctly computed" in text
    assert "outside the Monte Carlo sampling uncertainty" in text
    assert "may place the true value outside the reported P10-P90 interval" in text


def test_band_disclosure_does_not_say_the_percentiles_are_wrong(payload):
    text = payload["scenario_based_capacity_mt"]["uncertainty_band"]["statement"].lower()
    for word in ("wrong", "incorrect", "invalid", "unreliable", "error"):
        assert word not in text


def test_band_disclosure_is_an_interpretation_warning(payload):
    warning = {w["code"]: w for w in payload["interpretation"]["warnings"]}[BAND_CODE]
    assert warning["invalidates_result"] is False
    assert warning["correction_applied"] is False
    assert warning["detail"] == api.UNCERTAINTY_BAND_DISCLOSURE["statement"]


def test_no_band_disclosure_without_a_band(data_dir):
    blocked = api.screen_well("SALUZZO|1", {"area_m2": 8.0e7}, scenario=LEGACY_LITERATURE,
                              data_dir=data_dir)
    assert blocked["scenario_based_capacity_mt"] is None
    assert BAND_CODE not in [w["code"] for w in blocked["interpretation"]["warnings"]]
    funnel = api.screening_funnel(scenario=LEGACY_LITERATURE, user_inputs=VALID,
                                  data_dir=data_dir, samples=20)
    assert BAND_CODE not in [w["code"] for w in funnel["interpretation"]["warnings"]]
    # Approved model on real-reference data: every scenario UNAVAILABLE, so no band.
    unavailable = api.screen_well("SALUZZO|1", APPROVED, data_dir=data_dir, samples=20)
    assert BAND_CODE not in [w["code"] for w in unavailable["interpretation"]["warnings"]]


def test_module_constants_are_not_mutated_by_requests(data_dir):
    before = (dict(api.PERCENTILE_CONVENTION), dict(api.UNCERTAINTY_BAND_DISCLOSURE))
    first = api.screen_well("SALUZZO|1", VALID, scenario=LEGACY_LITERATURE, data_dir=data_dir,
                            samples=20)
    first["scenario_based_capacity_mt"]["percentile_convention"]["p10"] = "tampered"
    first["scenario_based_capacity_mt"]["uncertainty_band"]["statement"] = "tampered"
    assert (api.PERCENTILE_CONVENTION, api.UNCERTAINTY_BAND_DISCLOSURE) == before


# -- values unchanged --------------------------------------------------------


def test_percentiles_equal_the_engine_values_exactly(data_dir, payload):
    """The API block is a pass-through of np.percentile: bitwise, not approx."""
    record = next(r for r in api.load_records(data_dir) if r.canonical_id == "SALUZZO|1")
    active = api._with_user_inputs(api._scenario(LEGACY_LITERATURE),
                                   api.UserInputs.from_mapping(VALID))
    mc = run_capacity_mc(UniformPriors(**apply_scenario(record, active).prior_ranges())
                         .sample(500, seed=3))
    cap = payload["scenario_based_capacity_mt"]
    assert (cap["p10"], cap["p50"], cap["p90"], cap["mean"]) == (
        mc.p10_mt, mc.p50_mt, mc.p90_mt, mc.mean_mt)


def test_text_reports_state_the_convention(data_dir):
    from ccs_screen.ingest.report import screen_well as screen_record

    record = next(r for r in api.load_records(data_dir) if r.canonical_id == "SALUZZO|1")
    active = api._with_user_inputs(api._scenario(LEGACY_LITERATURE),
                                   api.UserInputs.from_mapping(VALID))
    text = screen_record(record, active, samples=50).render()
    assert "(low / median / high case)" in text
    assert "excludes systematic/model bias" in text


# -- pinned audited baseline (real data) -------------------------------------

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
REAL_SOURCES = ("Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx", "pozzi-storici.csv",
                "po_wells_clean.csv")
real_data = pytest.mark.skipif(
    not all((DATA_DIR / n).is_file() for n in REAL_SOURCES),
    reason="real source data not present; this check needs the local data/ directory",
)

#: Captured before the disclosure bundle, samples=2000, seed=42, VALID inputs.
#: (p10, p50, p90, mean) as float.hex, and sha256 of the raw Monte Carlo array.
BASELINE = {
    "SALUZZO|1": (("0x1.4f8344b3e062ep+2", "0x1.5498666943797p+3",
                   "0x1.441bd864f9cbdp+4", "0x1.7abbefcb8757dp+3"),
                  "c1dda27de87c6e3dfe628b9c48860b305528bf4ec78e989e604050c2e501576d"),
    "DESANA|1": (("0x1.4490ac72ea9c0p+2", "0x1.49f1360f98686p+3",
                  "0x1.39d9a184b9acep+4", "0x1.6ee4b98fc8cfep+3"),
                 "da78080e9e3802e245be022ecef7bfeb6a1fbb0cf9370e3cb07e6d89cddbf640"),
    "MALOSSA|15": (("0x1.60e355a41f2dep+2", "0x1.66633191bde90p+3",
                    "0x1.54f6cac328bdbp+4", "0x1.8e8f883a14892p+3"),
                   "1043b8eefc7eb134a48c489d711e82de322f77cff679b1db52abf2c579ba318f"),
    "TRECATE|9|ST": (("0x1.4af68da0dd80ap+2", "0x1.50764b4ec880dp+3",
                      "0x1.400f6b62fac79p+4", "0x1.761e23e63e36ap+3"),
                     "b9a5aa5b240bfd50f01f3d78c45ee1dc625e29b27c528d72533ab34638a12c92"),
    "ASTI|1": (("0x1.270e7af547e30p+2", "0x1.2c3ea4fd8bc48p+3",
                "0x1.1d947e420437cp+4", "0x1.4de2153c0e454p+3"),
               "6f3ffb11e10a08ee099dd71c639d0b5cfa836259a809d2229699d240102c52a4"),
}

CARBONATE_NTG = {"low": 0.2, "high": 0.6, "net_criterion": "porosity_permeability",
                 "net_basis": "analogue"}


@real_data
@pytest.mark.parametrize("well", sorted(BASELINE))
@pytest.mark.parametrize("user_inputs", [VALID, {**VALID, "net_to_gross": CARBONATE_NTG}],
                         ids=["ntg-absent", "ntg-declared"])
def test_audited_baseline_is_bit_for_bit_unchanged(well, user_inputs):
    """The legacy path's numbers are unchanged to the last bit (O2); only labelled."""
    expected, masses_sha = BASELINE[well]
    out = api.screen_well(well, user_inputs, scenario=LEGACY_LITERATURE,
                          data_dir=str(DATA_DIR), samples=2000, seed=42)
    cap = out["scenario_based_capacity_mt"]
    assert tuple(float(cap[k]).hex() for k in ("p10", "p50", "p90", "mean")) == expected
    assert (cap["n_samples"], cap["deterministic"]) == (2000, False)
    assert out["validation_status"] == cap["validation_status"] == "NOT_VALIDATED"

    record = next(r for r in api.load_records(str(DATA_DIR)) if r.canonical_id == well)
    active = api._with_user_inputs(api._scenario(LEGACY_LITERATURE),
                                   api.UserInputs.from_mapping(user_inputs))
    mc = run_capacity_mc(UniformPriors(**apply_scenario(record, active).prior_ranges())
                         .sample(2000, seed=42))
    assert hashlib.sha256(mc.masses_mt.tobytes()).hexdigest() == masses_sha


@real_data
@pytest.mark.parametrize("well", ["MALOSSA|15", "TRECATE|9|ST"])
def test_carbonate_wells_screen_with_porosity_permeability_ntg(well):
    out = api.screen_well(well, {**VALID, "net_to_gross": CARBONATE_NTG},
                          scenario=LEGACY_LITERATURE, data_dir=str(DATA_DIR), samples=200)
    assert out["status"] == "screened"
    assert out["thickness_provenance"]["net_to_gross"]["net_criterion"] == "porosity_permeability"


@real_data
@pytest.mark.parametrize("well", sorted(BASELINE))
def test_audited_wells_are_unavailable_under_the_approved_model(well):
    """C2 consequence on the same wells: no approved number is produced."""
    record = next(r for r in api.load_records(str(DATA_DIR)) if r.canonical_id == well)
    td = float(record.depth_m.value)
    out = api.screen_well(well, {"area_m2": 8.0e7, "z_top": td - 100.0, "z_base": td},
                          data_dir=str(DATA_DIR), samples=50, seed=42)
    assert out["status"] == "evaluated"
    for scenario in out["water_level_scenarios"]:
        assert scenario["validation_status"] == "UNAVAILABLE"
        assert scenario["capacity_mt"] is None and scenario["diagnostic_capacity_mt"] is None
        assert scenario["diagnostics"][0]["code"] == "DEPTH_REFERENCE_NOT_ESTABLISHED"
