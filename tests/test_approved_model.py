"""The approved Model Contract (Phase 13, frozen), implemented in Phase 14.

Every test here is NEW COVERAGE for ``ccs_screen.approved_model``. The contract
is ``docs/phase13-owner-decision-record.md``; the decision each test defends is
named in its docstring. Synthetic records are used wherever the approved path
must produce numbers: every ingested well has an UNKNOWN depth reference, so on
real data the approved result is UNAVAILABLE by construction (C2), and that
consequence is tested as well.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import math
from pathlib import Path

import numpy as np
import pytest

from ccs_screen import approved_model as am
from ccs_screen.approved_model import (
    APPROVED_PRIORS,
    P_ATM_PA,
    Diagnostic,
    StorageInterval,
    ValidationStatus,
    WaterLevelScenario,
    draw_realisations,
    eos_pressure_pa,
    evaluate_approved_model,
    select_temperature,
)
from ccs_screen.ingest.identity import canonical_well_id
from ccs_screen.ingest.provenance import (
    Confidence,
    FieldValue,
    Provenance,
    TemperatureMethod,
    Unit,
)
from ccs_screen.ingest.records import NormalizedWellRecord, TemperatureObservation
from ccs_screen.ingest.scenario import (
    LITERATURE_SCREENING_V1,
    STANDARD_GRAVITY_M_S2,
    STORAGE_EFFICIENCY_PRIOR_STATEMENT,
)
from ccs_screen.ingest.units import DepthDatum
from ccs_screen.monte_carlo import CapacitySample, run_capacity_mc
from ccs_screen.properties import (
    VALIDATED_ENVELOPE_PRESSURE_PA,
    VALIDATED_ENVELOPE_TEMPERATURE_K,
    co2_density_kg_m3,
)

ROOT = Path(__file__).resolve().parents[1]
ST = TemperatureMethod.SQUARCI_TAFFI
FW = TemperatureMethod.FERTL_WICHMANN
HORNER = TemperatureMethod.HORNER
GROUND = DepthDatum.GROUND_LEVEL
G = STANDARD_GRAVITY_M_S2


def obs(depth: float, temperature_k: float, method: TemperatureMethod = ST,
        datum: DepthDatum = GROUND) -> TemperatureObservation:
    return TemperatureObservation(depth_m=depth, temperature_k=temperature_k,
                                  method=method.value, depth_datum=datum)


def record(*temperatures: TemperatureObservation, depth_m: float | None = 3000.0,
           datum: DepthDatum = GROUND, quota: float | None = 200.0,
           well: str = "SYNTHETIC 1") -> NormalizedWellRecord:
    rec = NormalizedWellRecord(identity=canonical_well_id(well))
    if depth_m is not None:
        rec.depth_m = FieldValue(value=depth_m, unit=Unit.METRE,
                                 provenance=Provenance.EXTRACTED, confidence=Confidence.HIGH)
    rec.depth_datum = datum
    if quota is not None:
        rec.surface_elevation_m = FieldValue(value=quota, unit=Unit.METRE,
                                             provenance=Provenance.EXTRACTED,
                                             confidence=Confidence.MEDIUM)
    rec.temperatures = tuple(temperatures)
    return rec


def evaluate(rec: NormalizedWellRecord, z_top: float = 1400.0, z_base: float = 1600.0,
             n: int = 300, seed: int = 7, area: float = 5.0e7):
    return evaluate_approved_model(rec, area_m2=area, interval=StorageInterval(z_top, z_base),
                                   n=n, seed=seed)


def codes(entries) -> list[str]:
    return [d["code"] for d in entries]


# -- storage interval: derived h_g and z_state (A1, M1, S1) -------------------


def test_h_g_and_z_state_are_derived_from_the_interval():
    interval = StorageInterval(1234.5, 1789.25)
    assert interval.h_g_m == 1789.25 - 1234.5
    assert interval.z_state_m == (1234.5 + 1789.25) / 2


def test_derived_values_are_reported_and_drive_the_calculation():
    result = evaluate(record(obs(1500.0, 330.0)), z_top=1450.0, z_base=1550.0).to_dict()
    interval = result["storage_interval"]
    assert (interval["h_g_m"], interval["z_state_m"]) == (100.0, 1500.0)
    assert "PROJECT MODEL CONVENTION" in interval["state_point_convention"]
    assert result["water_level_scenarios"][0]["z_state_m"] == 1500.0


def test_capacity_is_linear_in_the_derived_h_g():
    """Doubling the interval doubles h_g and capacity; z_state is held."""
    rec = record(obs(1500.0, 330.0))
    thin = evaluate(rec, z_top=1450.0, z_base=1550.0).scenario(WaterLevelScenario.GROUND_REFERENCE)
    thick = evaluate(rec, z_top=1400.0, z_base=1600.0).scenario(WaterLevelScenario.GROUND_REFERENCE)
    assert thick.capacity.p50_mt == pytest.approx(2 * thin.capacity.p50_mt, rel=1e-12)


@pytest.mark.parametrize("z_top,z_base", [
    (1600.0, 1400.0), (1500.0, 1500.0), (-1.0, 100.0), (0.0, -5.0),
    (float("nan"), 100.0), (0.0, float("inf")), (True, 100.0), ("10", 100.0), (None, 100.0),
])
def test_invalid_interval_is_rejected(z_top, z_base):
    with pytest.raises(am.IntervalError):
        StorageInterval(z_top, z_base)


def test_interval_is_closed():
    interval = StorageInterval(1000.0, 2000.0)
    assert interval.contains(1000.0) and interval.contains(2000.0) and interval.contains(1500.0)
    assert not interval.contains(999.9) and not interval.contains(2000.1)


def test_there_is_no_thickness_input():
    """Final Gap Closure A: no independent thickness_m in the approved formulation."""
    params = inspect.signature(evaluate_approved_model).parameters
    assert "thickness_m" not in params and "interval" in params
    assert {f.name for f in dataclasses.fields(StorageInterval)} == {"z_top_m", "z_base_m"}


# -- depth reference: C2 and the O4 datum guard -------------------------------


@pytest.mark.parametrize("datum,expected", [
    (DepthDatum.GROUND_LEVEL, None),
    (DepthDatum.UNKNOWN, Diagnostic.DEPTH_REFERENCE_NOT_ESTABLISHED),
    (None, Diagnostic.DEPTH_REFERENCE_NOT_ESTABLISHED),
    (DepthDatum.MEAN_SEA_LEVEL, Diagnostic.UNSUPPORTED_DEPTH_DATUM),
    (DepthDatum.ROTARY_TABLE, Diagnostic.UNSUPPORTED_DEPTH_DATUM),
    (DepthDatum.KELLY_BUSHING, Diagnostic.UNSUPPORTED_DEPTH_DATUM),
])
def test_depth_reference_guard(datum, expected):
    assert am.depth_reference_diagnostic(datum) is expected


@pytest.mark.parametrize("datum,expected", [
    (DepthDatum.UNKNOWN, "DEPTH_REFERENCE_NOT_ESTABLISHED"),
    (DepthDatum.MEAN_SEA_LEVEL, "UNSUPPORTED_DEPTH_DATUM"),
    (DepthDatum.ROTARY_TABLE, "UNSUPPORTED_DEPTH_DATUM"),
    (DepthDatum.KELLY_BUSHING, "UNSUPPORTED_DEPTH_DATUM"),
])
def test_well_without_a_ground_reference_is_unavailable_everywhere(datum, expected):
    """C2/O4: interval, h_g, z_state, temperature and pressure unavailable; no capacity."""
    result = evaluate(record(obs(1500.0, 330.0, datum=datum), datum=datum))
    payload = result.to_dict()
    assert payload["depth_reference"]["status"] == "UNAVAILABLE"
    assert codes(payload["depth_reference"]["diagnostics"]) == [expected]
    assert payload["storage_interval"]["status"] == "UNAVAILABLE"
    assert payload["storage_interval"]["h_g_m"] is None
    assert payload["storage_interval"]["z_state_m"] is None
    assert payload["temperature_selection"]["status"] == "UNAVAILABLE"
    assert payload["temperature_selection"]["evaluated"] is False
    for scenario in payload["water_level_scenarios"]:
        assert scenario["validation_status"] == "UNAVAILABLE"
        assert scenario["capacity_mt"] is None and scenario["diagnostic_capacity_mt"] is None
        assert scenario["pressure_eos_pa"] is None
        assert codes(scenario["diagnostics"]) == [expected]


def test_mixed_references_between_depth_and_observations():
    """O4 applies to each temperature-observation depth as well as to depth_m."""
    rec = record(
        obs(1500.0, 390.0, datum=DepthDatum.ROTARY_TABLE),   # nearest, unsupported datum
        obs(1510.0, 380.0, datum=DepthDatum.UNKNOWN),        # next, not established
        obs(1450.0, 330.0, datum=GROUND),                    # eligible
    )
    selection = select_temperature(rec, StorageInterval(1400.0, 1600.0))
    assert selection.temperature_k == 330.0
    excluded = {o.depth_m: set(r) for o, r in selection.excluded}
    assert excluded[1500.0] == {Diagnostic.UNSUPPORTED_DEPTH_DATUM}
    assert excluded[1510.0] == {Diagnostic.DEPTH_REFERENCE_NOT_ESTABLISHED}


def test_observation_defaults_to_an_unknown_reference():
    assert TemperatureObservation(1.0, 300.0, ST.value).depth_datum is DepthDatum.UNKNOWN


def test_no_datum_conversion_is_ever_applied(monkeypatch):
    """O4: DepthMeasurement.to_msl is never called by the approved path."""
    from ccs_screen.ingest import units

    def forbidden(self):  # pragma: no cover - failing is the point
        raise AssertionError("the approved path must not convert datums")

    monkeypatch.setattr(units.DepthMeasurement, "to_msl", forbidden)
    for datum in DepthDatum:
        evaluate(record(obs(1500.0, 330.0), datum=datum), n=20)


# -- pressure and the two named water-level scenarios (B1, M2) ----------------


def test_p_atm_is_the_declared_project_constant():
    assert P_ATM_PA == 101_325.0
    constants = am.model_constants()
    assert constants["p_atm_pa"]["value"] == 101_325.0
    assert "PROJECT MODEL CONSTANT" in constants["p_atm_pa"]["label"]
    assert constants["gravity_m_s2"]["value"] == 9.80665
    assert constants["not_ranked_as_sensitivities"] is True


def test_eos_pressure_is_absolute_and_uses_the_state_point():
    assert eos_pressure_pa(1050.0, 1500.0, 0.0) == P_ATM_PA + 1050.0 * G * 1500.0
    assert eos_pressure_pa(1050.0, 1500.0, 200.0) == P_ATM_PA + 1050.0 * G * 1300.0


def test_both_named_scenarios_are_always_evaluated_in_order():
    result = evaluate(record(obs(1500.0, 330.0), quota=250.0))
    names = [s.scenario for s in result.scenarios]
    assert names == [WaterLevelScenario.GROUND_REFERENCE, WaterLevelScenario.SEA_LEVEL_SENSITIVITY]
    payload = result.to_dict()["water_level_scenarios"]
    assert [p["role"] for p in payload] == ["baseline", "sensitivity"]
    assert "PROJECT REFERENCE SCENARIO" in payload[0]["label"]
    assert all("not a measured formation head" in p["label"] for p in payload)


def test_water_level_depths_are_zero_and_quota():
    result = evaluate(record(obs(1500.0, 330.0), quota=250.0))
    ground = result.scenario(WaterLevelScenario.GROUND_REFERENCE)
    sea = result.scenario(WaterLevelScenario.SEA_LEVEL_SENSITIVITY)
    assert (ground.z_wl_m, sea.z_wl_m) == (0.0, 250.0)
    low, high = APPROVED_PRIORS.brine_density_kg_m3
    assert ground.pressure_eos_range_pa == (P_ATM_PA + low * G * 1500.0, P_ATM_PA + high * G * 1500.0)
    assert sea.pressure_eos_range_pa == (P_ATM_PA + low * G * 1250.0, P_ATM_PA + high * G * 1250.0)


def test_sea_level_scenario_needs_the_quota():
    result = evaluate(record(obs(1500.0, 330.0), quota=None))
    ground = result.scenario(WaterLevelScenario.GROUND_REFERENCE)
    sea = result.scenario(WaterLevelScenario.SEA_LEVEL_SENSITIVITY)
    assert ground.status is ValidationStatus.VALIDATED
    assert sea.status is ValidationStatus.UNAVAILABLE
    assert codes(sea.diagnostics) == ["SURFACE_ELEVATION_UNAVAILABLE"]
    assert sea.capacity is None and sea.diagnostic_capacity is None


def test_water_level_is_never_sampled_and_draws_are_shared():
    """M2: deterministic scenarios; both runs use the same draws (same seed)."""
    draws = draw_realisations(area_m2=5e7, h_g_m=200.0, temperature_k=330.0,
                              priors=APPROVED_PRIORS, n=500, seed=3)
    assert set(draws) == {"area_m2", "thickness_m", "porosity", "brine_density_kg_m3",
                          "temperature_k", "storage_efficiency"}
    rho = draws["brine_density_kg_m3"]
    ground = eos_pressure_pa(rho, 1500.0, 0.0)
    sea = eos_pressure_pa(rho, 1500.0, 250.0)
    assert np.allclose(ground - sea, rho * G * 250.0, rtol=1e-12)


# -- temperature selection: M3 + R1 + C3 and the deferred guard ---------------


def select(*observations, z_top=1400.0, z_base=1600.0, **kw):
    return select_temperature(record(*observations, **kw), StorageInterval(z_top, z_base))


@pytest.mark.parametrize("method", [
    TemperatureMethod.RAW, TemperatureMethod.NON_STABILIZED,
    TemperatureMethod.UNKNOWN, TemperatureMethod.SURFACE_AIR,
])
def test_only_corrected_methods_qualify(method):
    """M3 (1), S5: uncorrected BHT is never substituted."""
    selection = select(obs(1500.0, 330.0, method=method))
    assert selection.status is am.Availability.UNAVAILABLE
    assert codes(selection.diagnostics) == ["NO_ELIGIBLE_TEMPERATURE_OBSERVATION"]
    assert selection.excluded[0][1] == (Diagnostic.METHOD_NOT_ELIGIBLE,)


def test_observation_outside_the_interval_does_not_qualify():
    selection = select(obs(1399.9, 330.0), obs(1600.1, 331.0))
    assert not selection.available
    assert all(r == (Diagnostic.OUTSIDE_STORAGE_INTERVAL,) for _, r in selection.excluded)


def test_interval_bounds_themselves_qualify():
    assert select(obs(1400.0, 330.0)).temperature_k == 330.0
    assert select(obs(1600.0, 331.0)).temperature_k == 331.0


def test_nearest_observation_is_selected_without_interpolation():
    selection = select(obs(1450.0, 330.0), obs(1580.0, 340.0))
    assert selection.temperature_k == 330.0
    assert selection.selected.depth_m == 1450.0


def test_nearest_wins_over_method_no_accuracy_ranking():
    """S2/M3 (6): FW nearer than ST is selected; no method ranking."""
    selection = select(obs(1510.0, 331.0, method=FW), obs(1450.0, 330.0, method=ST))
    assert selection.selected.method == FW.value


def test_equal_distance_at_different_depths_keeps_the_shallower():
    """R1-1: a PROJECT SELECTION CONVENTION, not an accuracy claim."""
    selection = select(obs(1600.0, 340.0), obs(1400.0, 330.0))
    assert selection.temperature_k == 330.0
    assert codes(selection.diagnostics) == ["EQUAL_DISTANCE_SHALLOWER_SELECTED"]
    assert selection.diagnostics[0]["depths_m"] == [1400.0, 1600.0]


def test_equal_distance_tie_is_not_split_by_floating_point_rounding():
    """(900.3 + 2099.7) / 2 is 1500 in real arithmetic; the tie must survive."""
    z_top, z_base = 900.3, 2099.7
    z_state = (z_top + z_base) / 2
    selection = select(obs(1000.0, 330.0), obs(2000.0, 360.0), z_top=z_top, z_base=z_base)
    assert abs(abs(1000.0 - z_state) - abs(2000.0 - z_state)) < 1e-9
    assert selection.temperature_k == 330.0
    assert "EQUAL_DISTANCE_SHALLOWER_SELECTED" in codes(selection.diagnostics)


def test_same_method_same_depth_different_values_is_unavailable():
    """R1-2, C3: no value chosen; a conflict diagnostic is emitted."""
    selection = select(obs(1500.0, 330.0), obs(1500.0, 331.0))
    assert selection.status is am.Availability.UNAVAILABLE
    assert selection.temperature_k is None
    (conflict,) = selection.diagnostics
    assert conflict["code"] == "TEMPERATURE_SAME_METHOD_CONFLICT"
    assert conflict["methods"] == [ST.value]
    assert conflict["values_k"] == {ST.value: [330.0, 331.0]}


def test_same_method_same_depth_identical_values_is_not_a_conflict():
    assert select(obs(1500.0, 330.0), obs(1500.0, 330.0)).temperature_k == 330.0


def test_same_method_conflict_is_checked_before_the_squarci_taffi_tie_break():
    """Evaluation order: step 4 (conflict) precedes step 5 (ST)."""
    selection = select(obs(1500.0, 330.0, method=FW), obs(1500.0, 331.0, method=FW),
                       obs(1500.0, 335.0, method=ST))
    assert not selection.available
    assert codes(selection.diagnostics) == ["TEMPERATURE_SAME_METHOD_CONFLICT"]


def test_different_methods_at_the_same_depth_use_squarci_taffi():
    """R1-3: a deterministic project tie-break, not an accuracy ranking."""
    selection = select(obs(1500.0, 335.0, method=FW), obs(1500.0, 330.0, method=ST))
    assert selection.temperature_k == 330.0
    assert codes(selection.diagnostics) == ["SAME_DEPTH_SQUARCI_TAFFI_CONVENTION"]


def test_horner_and_fertl_wichmann_without_squarci_taffi_are_guarded():
    """Deferred Horner-vs-FW tie: the guard selects no value and reports it."""
    selection = select(obs(1500.0, 334.0, method=HORNER), obs(1500.0, 335.0, method=FW))
    assert selection.status is am.Availability.UNAVAILABLE
    (guard,) = selection.diagnostics
    assert guard["code"] == "TEMPERATURE_METHOD_TIE_UNRESOLVED"
    assert guard["methods"] == sorted([HORNER.value, FW.value])


def test_horner_fertl_wichmann_and_squarci_taffi_together_use_squarci_taffi():
    selection = select(obs(1500.0, 334.0, method=HORNER), obs(1500.0, 335.0, method=FW),
                       obs(1500.0, 330.0, method=ST))
    assert selection.temperature_k == 330.0


def test_a_single_horner_observation_qualifies():
    assert select(obs(1500.0, 336.0, method=HORNER)).temperature_k == 336.0


def test_shallower_rule_applies_before_the_method_rules():
    """R1-1 keeps the shallower depth; the ST rule then applies only there."""
    selection = select(obs(1400.0, 330.0, method=FW), obs(1600.0, 340.0, method=ST))
    assert selection.selected.method == FW.value
    assert selection.temperature_k == 330.0


def test_corrected_observations_below_the_recorded_total_depth_are_excluded():
    """S11/M3: observations deeper than the recorded TD never qualify."""
    selection = select(obs(6000.0, 440.15), obs(6099.0, 441.15, method=FW),
                       obs(6247.9, 452.15, method=FW), z_top=5950.0, z_base=6300.0,
                       depth_m=6087.0)
    assert selection.temperature_k == 440.15
    reasons = {o.depth_m: r for o, r in selection.excluded}
    assert reasons[6099.0] == (Diagnostic.BELOW_RECORDED_TOTAL_DEPTH,)
    assert reasons[6247.9] == (Diagnostic.BELOW_RECORDED_TOTAL_DEPTH,)


def test_unrecorded_total_depth_makes_observations_ineligible():
    selection = select(obs(1500.0, 330.0), depth_m=None)
    assert not selection.available
    assert selection.excluded[0][1] == (Diagnostic.TOTAL_DEPTH_NOT_RECORDED,)


def test_ingestion_time_temperature_is_never_used():
    """The approved path does not fall back to the legacy record.temperature_k."""
    rec = record(obs(1500.0, 330.0, method=TemperatureMethod.NON_STABILIZED))
    rec.temperature_k = FieldValue(value=345.0, unit=Unit.KELVIN, provenance=Provenance.DERIVED,
                                   confidence=Confidence.MEDIUM, derivation="legacy selection")
    result = evaluate(rec)
    assert result.temperature.temperature_k is None
    assert all(s.status is ValidationStatus.UNAVAILABLE for s in result.scenarios)
    assert all("TEMPERATURE_UNAVAILABLE" in codes(s.diagnostics) for s in result.scenarios)


def test_temperature_selection_does_not_use_the_0_85_filter():
    """S3: a shallow in-interval observation qualifies; nothing is filtered by TD fraction."""
    selection = select(obs(500.0, 300.0), z_top=400.0, z_base=600.0, depth_m=6000.0)
    assert selection.temperature_k == 300.0


def _real_record(well: str) -> NormalizedWellRecord:
    from ccs_screen.ingest.normalize import WellNormalizer

    data = ROOT / "data"
    if not (data / "Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx").is_file():
        pytest.skip("real source data not present; this check needs the local data/ directory")
    return {r.canonical_id: r for r in WellNormalizer(data).run()}[well]


def test_trecate_below_td_observations_are_excluded_on_real_data():
    """S11 on the real record: 6099 m and 6247.9 m (recorded TD 6087 m).

    The real depth reference is UNKNOWN, so the approved result is UNAVAILABLE
    regardless; the exclusion is checked on a copy whose references are
    hypothetically ground level, to show S11 applies independently of C2.
    """
    real = _real_record("TRECATE|9|ST")
    assert real.depth_m.value == 6087.0
    ground = dataclasses.replace(
        real, depth_datum=GROUND,
        temperatures=tuple(dataclasses.replace(o, depth_datum=GROUND) for o in real.temperatures))
    selection = select_temperature(ground, StorageInterval(5900.0, 6300.0))
    below = {o.depth_m for o, r in selection.excluded if Diagnostic.BELOW_RECORDED_TOTAL_DEPTH in r}
    assert {6099.0, 6247.9} <= below
    assert selection.selected.depth_m == 6000.0

    unavailable = evaluate_approved_model(real, area_m2=5e7,
                                          interval=StorageInterval(5900.0, 6300.0), n=10, seed=1)
    assert all(s.status is ValidationStatus.UNAVAILABLE for s in unavailable.scenarios)
    assert unavailable.depth_reference_diagnostic is Diagnostic.DEPTH_REFERENCE_NOT_ESTABLISHED


# -- EOS envelope: flag and block, no draw discarded (E1, M4, C1) -------------


def test_envelope_constants_are_the_contract_values():
    assert VALIDATED_ENVELOPE_PRESSURE_PA == (1.0e6, 35.0e6)
    assert VALIDATED_ENVELOPE_TEMPERATURE_K == (280.0, 400.0)


def test_every_realisation_inside_is_validated():
    result = evaluate(record(obs(1500.0, 330.0)), n=400)
    ground = result.scenario(WaterLevelScenario.GROUND_REFERENCE)
    assert ground.status is ValidationStatus.VALIDATED
    assert ground.validated_percentiles == "REPORTED"
    assert ground.envelope.n_outside == 0 and ground.envelope.n_realisations == 400
    assert ground.capacity.n == 400 and ground.diagnostic_capacity is None
    block = ground.to_dict()["capacity_mt"]
    assert block["validation_status"] == "VALIDATED"
    assert "conditional on the declared model" in block["interpretation"]


def test_a_straddling_scenario_is_flagged_and_blocked_without_dropping_draws():
    """M4: some realisations above 35 MPa -> OUTSIDE; percentiles over ALL draws."""
    n, seed = 600, 11
    rec = record(obs(3300.0, 370.0), depth_m=4000.0)
    result = evaluate(rec, z_top=3250.0, z_base=3350.0, n=n, seed=seed)
    ground = result.scenario(WaterLevelScenario.GROUND_REFERENCE)
    assert ground.status is ValidationStatus.OUTSIDE_VALIDATED_ENVELOPE
    assert ground.validated_percentiles == "BLOCKED"
    assert ground.capacity is None
    assert 0 < ground.envelope.n_outside < n
    assert ground.envelope.n_pressure_above == ground.envelope.n_outside
    assert ground.to_dict()["envelope"]["realisations_discarded"] == 0

    diagnostic = ground.diagnostic_capacity
    assert diagnostic.n == n, "a draw was discarded"
    draws = draw_realisations(area_m2=5e7, h_g_m=100.0, temperature_k=370.0,
                              priors=APPROVED_PRIORS, n=n, seed=seed)
    pressure = eos_pressure_pa(draws["brine_density_kg_m3"], 3300.0, 0.0)
    everything = run_capacity_mc([
        CapacitySample(5e7, 100.0, float(draws["porosity"][i]), float(pressure[i]), 370.0,
                       float(draws["storage_efficiency"][i])) for i in range(n)])
    assert (diagnostic.p10_mt, diagnostic.p50_mt, diagnostic.p90_mt) == (
        everything.p10_mt, everything.p50_mt, everything.p90_mt)
    inside = everything.masses_mt[pressure <= VALIDATED_ENVELOPE_PRESSURE_PA[1]]
    assert float(np.percentile(inside, 50)) != diagnostic.p50_mt

    payload = ground.to_dict()
    assert payload["capacity_mt"] is None
    assert payload["diagnostic_capacity_mt"]["validation_status"] == "NOT_VALIDATED"
    assert "NOT VALIDATED" in payload["diagnostic_capacity_mt"]["label"]
    assert "OUTSIDE_VALIDATED_ENVELOPE" in codes(payload["diagnostics"])


def test_temperature_outside_the_envelope_blocks_every_realisation():
    result = evaluate(record(obs(1500.0, 410.0)), n=100)
    for scenario in result.scenarios:
        assert scenario.status is ValidationStatus.OUTSIDE_VALIDATED_ENVELOPE
        assert scenario.envelope.n_outside == 100 and not scenario.envelope.temperature_inside
        assert scenario.diagnostic_capacity.n == 100


def test_pressure_below_the_envelope_is_flagged():
    result = evaluate(record(obs(60.0, 290.0)), z_top=50.0, z_base=70.0, n=50)
    ground = result.scenario(WaterLevelScenario.GROUND_REFERENCE)
    assert ground.status is ValidationStatus.OUTSIDE_VALIDATED_ENVELOPE
    assert ground.envelope.n_pressure_below == 50


def test_envelope_is_checked_on_absolute_not_gauge_pressure():
    """C1: at z_state = 91 m the gauge pressure is below 1 MPa but P_EOS is not."""
    rho_low, rho_high = APPROVED_PRIORS.brine_density_kg_m3
    assert rho_high * G * 91.0 < 1.0e6 <= P_ATM_PA + rho_low * G * 91.0
    result = evaluate(record(obs(91.0, 290.0)), z_top=80.0, z_base=102.0, n=200)
    assert result.scenario(WaterLevelScenario.GROUND_REFERENCE).status is ValidationStatus.VALIDATED


def test_state_point_above_the_water_level_is_reported_and_not_evaluable():
    result = evaluate(record(obs(150.0, 290.0), quota=400.0), z_top=100.0, z_base=200.0, n=30)
    sea = result.scenario(WaterLevelScenario.SEA_LEVEL_SENSITIVITY)
    assert sea.status is ValidationStatus.OUTSIDE_VALIDATED_ENVELOPE
    assert {"STATE_POINT_ABOVE_WATER_LEVEL", "EOS_NOT_EVALUABLE"} <= set(codes(sea.diagnostics))
    assert sea.diagnostic_capacity is None and sea.capacity is None
    assert sea.envelope.n_realisations == 30


def test_outside_is_not_called_impossible():
    assert "not the same as physically impossible" in am.OUTSIDE_ENVELOPE_STATEMENT


# -- Monte Carlo priors and the capacity equation (A4-A6, S6, S7) -------------


def test_approved_priors_are_the_contract_values():
    assert APPROVED_PRIORS.porosity == (0.10, 0.35)
    assert APPROVED_PRIORS.brine_density_kg_m3 == (1020.0, 1100.0)
    assert APPROVED_PRIORS.storage_efficiency == (0.01, 0.04)
    assert am.APPROVED_PARAMETER_SET is LITERATURE_SCREENING_V1


def test_a6_statement_is_exact_and_documented():
    assert STORAGE_EFFICIENCY_PRIOR_STATEMENT == (
        "The Uniform distribution is a project-defined prior over the DOE-derived "
        "P15–P85 bounds. It is not claimed to reproduce the DOE probability distribution."
    )
    rationale = LITERATURE_SCREENING_V1.get("storage_efficiency").rationale
    assert STORAGE_EFFICIENCY_PRIOR_STATEMENT in rationale
    assert APPROVED_PRIORS.to_dict()["storage_efficiency"]["statement"] == STORAGE_EFFICIENCY_PRIOR_STATEMENT


def test_only_declared_priors_vary():
    """S6: area, h_g and temperature are deterministic; water level is not drawn."""
    draws = draw_realisations(area_m2=5e7, h_g_m=150.0, temperature_k=330.0,
                              priors=APPROVED_PRIORS, n=1000, seed=5)
    for constant, value in (("area_m2", 5e7), ("thickness_m", 150.0), ("temperature_k", 330.0)):
        assert np.all(draws[constant] == value)
    for varied, (low, high) in (("porosity", (0.10, 0.35)),
                                ("brine_density_kg_m3", (1020.0, 1100.0)),
                                ("storage_efficiency", (0.01, 0.04))):
        assert draws[varied].min() >= low and draws[varied].max() <= high
        assert draws[varied].std() > 0


def test_capacity_matches_an_independent_recomputation():
    """M = A * h_g * phi * rho_CO2(P_EOS, T) * E, per realisation, then percentiles."""
    n, seed = 250, 21
    result = evaluate(record(obs(1500.0, 330.0)), n=n, seed=seed)
    ground = result.scenario(WaterLevelScenario.GROUND_REFERENCE)
    draws = draw_realisations(area_m2=5e7, h_g_m=200.0, temperature_k=330.0,
                              priors=APPROVED_PRIORS, n=n, seed=seed)
    masses = []
    for i in range(n):
        p_eos = P_ATM_PA + draws["brine_density_kg_m3"][i] * G * (1500.0 - 0.0)
        rho = co2_density_kg_m3(p_eos, 330.0)
        masses.append(5e7 * 200.0 * draws["porosity"][i] * rho * draws["storage_efficiency"][i] / 1e9)
    p10, p50, p90 = np.percentile(masses, [10, 50, 90])
    assert (ground.capacity.p10_mt, ground.capacity.p50_mt, ground.capacity.p90_mt) == pytest.approx(
        (p10, p50, p90), rel=1e-12)


def test_b1_is_the_only_difference_from_the_legacy_resolver_at_the_same_state():
    """With z_state = TD, h_g = legacy thickness and the same temperature, the
    approved GROUND_REFERENCE masses equal the legacy masses recomputed with
    P + 101325 Pa: the atmospheric term (B1) is the only arithmetic change."""
    from ccs_screen.ingest.assumptions import Assumption, AssumptionSet
    from ccs_screen.ingest.scenario import ScreeningScenario, apply_scenario
    from ccs_screen.monte_carlo import UniformPriors

    td, temperature, n, seed = 2000.0, 340.0, 200, 13
    rec = record(obs(td, temperature), depth_m=td)
    rec.temperature_k = FieldValue(value=temperature, unit=Unit.KELVIN, provenance=Provenance.DERIVED,
                                   confidence=Confidence.MEDIUM, derivation="synthetic")
    user = (Assumption(parameter="area_m2", value=5e7, author="t", rationale="t"),
            Assumption(parameter="thickness_m", value=100.0, author="t", rationale="t"))
    legacy = ScreeningScenario(
        name="legacy-copy", description="legacy resolver over the approved parameter set",
        brine_density_kg_m3=LITERATURE_SCREENING_V1.brine_density_kg_m3,
        assumptions=AssumptionSet(name="legacy-copy",
                                  assumptions=LITERATURE_SCREENING_V1.assumptions.assumptions + user))
    config = apply_scenario(rec, legacy)
    legacy_samples = UniformPriors(**config.prior_ranges()).sample(n, seed=seed)
    shifted = run_capacity_mc([dataclasses.replace(s, pressure_pa=s.pressure_pa + P_ATM_PA)
                               for s in legacy_samples])

    approved = evaluate(rec, z_top=td - 50.0, z_base=td + 50.0, n=n, seed=seed)
    ground = approved.scenario(WaterLevelScenario.GROUND_REFERENCE)
    assert ground.status is ValidationStatus.VALIDATED
    assert np.allclose(ground.capacity.masses_mt, shifted.masses_mt, rtol=1e-9, atol=0)
    unshifted = run_capacity_mc(legacy_samples)
    assert not np.allclose(ground.capacity.masses_mt, unshifted.masses_mt, rtol=1e-9, atol=0)


def test_net_to_gross_never_enters_the_approved_calculation():
    source = inspect.getsource(am)
    tree = ast.parse(source)
    names = {node.id.lower() for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not any("ntg" in n or "net_to_gross" in n for n in names)


# -- F1: joint scenarios, baseline, individual effect ------------------------


def test_systematic_effect_is_a_scenario_contrast_not_a_factor():
    result = evaluate(record(obs(1500.0, 330.0), quota=250.0), n=300)
    effect = result.systematic_effect()
    assert effect["baseline"] == "GROUND_REFERENCE"
    assert effect["joint_scenarios"] == ["GROUND_REFERENCE", "SEA_LEVEL_SENSITIVITY"]
    assert effect["multiplied_correction_factor"] is None
    (individual,) = effect["individual_effects"]
    assert individual["contrast"] == "SEA_LEVEL_SENSITIVITY vs GROUND_REFERENCE"
    assert individual["is_correction"] is False
    ground = result.scenario(WaterLevelScenario.GROUND_REFERENCE).capacity
    sea = result.scenario(WaterLevelScenario.SEA_LEVEL_SENSITIVITY).capacity
    assert individual["status"] == "AVAILABLE"
    assert individual["p50_difference_mt"] == sea.p50_mt - ground.p50_mt
    assert individual["p50_difference_mt"] < 0
    assert "No multiplied correction factor" in effect["methodology"]


def test_systematic_effect_is_withheld_unless_both_scenarios_are_validated():
    result = evaluate(record(obs(1500.0, 330.0), quota=None), n=50)
    (individual,) = result.systematic_effect()["individual_effects"]
    assert individual["status"] == "UNAVAILABLE"
    assert individual["p50_difference_mt"] is None


def test_results_are_reproducible_for_a_seed():
    first = evaluate(record(obs(1500.0, 330.0)), n=100, seed=99).to_dict()
    second = evaluate(record(obs(1500.0, 330.0)), n=100, seed=99).to_dict()
    assert first == second


def test_payload_is_json_serialisable_and_carries_the_contract():
    import json

    payload = evaluate(record(obs(1500.0, 330.0)), n=50).to_dict()
    json.dumps(payload)
    assert payload["model_path"] == "APPROVED_MODEL"
    assert payload["contract"] == "docs/phase13-owner-decision-record.md"
    assert payload["capacity_equation"] == "M = A * h_g * phi * rho_CO2(P_EOS, T) * E"
    assert "never sampled" in payload["water_level_scenario_statement"]


def test_the_approved_path_never_labels_itself_not_validated():
    payload = evaluate(record(obs(1500.0, 330.0)), n=50).to_dict()
    statuses = {s["validation_status"] for s in payload["water_level_scenarios"]}
    assert statuses <= {"VALIDATED", "OUTSIDE_VALIDATED_ENVELOPE", "UNAVAILABLE"}


def test_only_the_approved_parameter_set_object_selects_the_approved_model():
    assert am.is_approved_parameter_set(LITERATURE_SCREENING_V1)
    assert not am.is_approved_parameter_set(dataclasses.replace(LITERATURE_SCREENING_V1))


# -- E2 ------------------------------------------------------------------------


def test_the_unsupported_peneloux_justification_is_corrected():
    import ccs_screen.properties as properties

    doc = properties.__doc__
    assert "is not supported" in doc and "14 of 45" in doc
    assert "It is kept because most Italian pilot reservoirs sit below 20 MPa" not in doc


def test_all_contract_math_constants_have_finite_values():
    assert all(math.isfinite(v) for v in (*VALIDATED_ENVELOPE_PRESSURE_PA,
                                          *VALIDATED_ENVELOPE_TEMPERATURE_K, P_ATM_PA))
