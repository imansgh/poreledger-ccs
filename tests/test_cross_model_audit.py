"""Phase 12 audit: cross-model consistency and the combined net effect.

Phases 1-11 tested each subsystem in isolation. These tests check the joins --
the places where two individually-defensible models are used together and
disagree. The capacity model assumes a bounded trap while the injectivity model
assumes an infinite aquifer; three thicknesses coexist with no relational check;
and the systematic bias is wider than the uncertainty band that is supposed to
express it.

The Finding 12.4 tests characterise the audit's *conditional scenario product*
of findings 3.1, 4.1 and 4.2 under a sea-level water level (11.1 excluded).
Under the approved Model Contract (F1, F2) that product is historical audit
material only: a scenario/sensitivity product, never an estimate of true or
reported capacity and never a correction factor. The approved model replaces it
with single joint scenario evaluation -- GROUND_REFERENCE as the baseline and
SEA_LEVEL_SENSITIVITY vs GROUND_REFERENCE as the individual effect -- which the
last section checks (F1; the wording here reconciles F3).

See ``docs/scientific-validation-audit.md``, Phase 12 and the final summary.
"""

from __future__ import annotations

import math

import pytest

from ccs_screen.monte_carlo import UniformPriors, run_capacity_mc
from ccs_screen.properties import co2_density_kg_m3

#: Shipped Theis defaults from cli.py.
AQUIFER = dict(
    permeability_m2=8e-14, thickness_m=40.0, viscosity_pa_s=4.5e-4,
    porosity=0.18, compressibility_1_pa=1.2e-9,
)
SECONDS_PER_YEAR = 365.25 * 24 * 3600
BRINE_DENSITY = 1060.0
GRAVITY = 9.80665
P_ATM_PA = 101_325.0

#: (well, depth_m, temperature_k, surface_elevation_m) from the real corpus.
WELLS = [
    ("SALUZZO|1", 1527.5, 318.15, 310.0),
    ("DESANA|1", 3224.9, 370.15, 142.0),
    ("MALOSSA|15", 5491.0, 416.15, 111.0),
    ("TRECATE|9|ST", 6087.0, 452.15, 139.0),
]

#: CSLF-T-2008-04: "fraction of the geological unit that has the porosity and
#: permeability required for CO2 injection: 0.25 to 0.75". Confirmed in Phase 9.
NET_TO_GROSS_RANGE = (0.25, 0.75)


def radius_of_investigation_m(time_s):
    transmissivity = AQUIFER["permeability_m2"] * AQUIFER["thickness_m"] / AQUIFER["viscosity_pa_s"]
    storativity = AQUIFER["porosity"] * AQUIFER["compressibility_1_pa"] * AQUIFER["thickness_m"]
    return math.sqrt(2.25 * transmissivity * time_s / storativity)


def closure_radius_m(area_km2):
    return math.sqrt(area_km2 * 1e6 / math.pi)


# -- Finding 12.1: closed trap vs infinite aquifer ---------------------------


@pytest.mark.parametrize(
    "area_km2,expected_days", [(20, 39.8), (80, 159.2), (200, 397.9)]
)
def test_pressure_front_reaches_the_closure_boundary_early(area_km2, expected_days):
    """CHARACTERISATION, Finding 12.1.

    Capacity is computed for a bounded trap; Theis assumes infinite extent. The
    front reaches the closure boundary in weeks to a little over a year, while
    the default injection duration is ten years.
    """
    transmissivity = AQUIFER["permeability_m2"] * AQUIFER["thickness_m"] / AQUIFER["viscosity_pa_s"]
    storativity = AQUIFER["porosity"] * AQUIFER["compressibility_1_pa"] * AQUIFER["thickness_m"]
    radius = closure_radius_m(area_km2)
    days = radius ** 2 * storativity / (2.25 * transmissivity) / 86400
    assert days == pytest.approx(expected_days, rel=0.02)
    assert days < 0.15 * 10 * 365.25, "the assumption should fail early in the 10-year run"


@pytest.mark.parametrize("area_km2,minimum_overshoot", [(20, 9.0), (80, 4.5), (200, 2.8)])
def test_ten_year_investigation_radius_far_exceeds_the_closure(area_km2, minimum_overshoot):
    """At the default 10-year duration the front is 3x to 10x beyond the trap."""
    overshoot = radius_of_investigation_m(10 * SECONDS_PER_YEAR) / closure_radius_m(area_km2)
    assert overshoot > minimum_overshoot


def test_a_no_flow_boundary_would_raise_pressure_so_the_rate_ceiling_is_overstated():
    """Direction of Finding 12.1: Theis understates dP, so Qmax is too high.

    Proxy: halving transmissivity stands in for the extra resistance a boundary
    imposes. dP rises, so the permitted rate falls.
    """
    from ccs_screen.pressure import theis_injection_delta_p_pa

    base = theis_injection_delta_p_pa(
        rate_m3_s=0.08, time_s=10 * SECONDS_PER_YEAR, radius_m=500.0, **AQUIFER
    )
    confined = theis_injection_delta_p_pa(
        rate_m3_s=0.08, time_s=10 * SECONDS_PER_YEAR, radius_m=500.0,
        **{**AQUIFER, "permeability_m2": AQUIFER["permeability_m2"] / 2},
    )
    assert confined > base


# -- Finding 12.2: three thicknesses -----------------------------------------


def test_capacity_and_theis_thicknesses_are_independent_parameters():
    """CHARACTERISATION, Finding 12.2.

    Nothing relates thickness_m to aquifer_thickness_m, so nothing objects if
    the hydraulic thickness is set below the storage thickness -- which is
    physically impossible.
    """
    from ccs_screen.cli import SCALAR_DEFAULTS
    from ccs_screen.monte_carlo import DEPLETED_GAS_ANALOG

    storage_low, storage_high = DEPLETED_GAS_ANALOG.thickness_m
    hydraulic = SCALAR_DEFAULTS["aquifer_thickness_m"]
    assert storage_low < hydraulic < storage_high, (
        "the shipped hydraulic thickness sits inside the storage prior, unchecked"
    )


def test_porosity_is_specified_twice_with_no_reconciliation():
    """The same rock carries a literature range and a separate CLI default."""
    from ccs_screen.cli import SCALAR_DEFAULTS
    from ccs_screen.ingest.scenario import LITERATURE_SCREENING_V1

    literature = next(
        a.value for a in LITERATURE_SCREENING_V1.assumptions.assumptions
        if a.parameter == "porosity"
    )
    aquifer = SCALAR_DEFAULTS["aquifer_porosity"]
    assert literature[0] <= aquifer <= literature[1]
    assert isinstance(aquifer, float), "a point value against a literature range"


# -- Finding 12.3: T and P depths --------------------------------------------


@pytest.mark.parametrize(
    "well,depth_m,temperature_k,depth_gap_m,expected_error",
    [
        ("SALUZZO|1", 1527.5, 318.15, -4.9, -0.0018),
        ("DESANA|1", 3224.9, 370.15, -24.5, -0.0045),
        ("MALOSSA|15", 5491.0, 416.15, -104.0, -0.0112),
        ("TRECATE|9|ST", 6087.0, 452.15, 160.9, 0.0153),
    ],
)
def test_temperature_pressure_depth_gap_costs_under_two_percent(
    well, depth_m, temperature_k, depth_gap_m, expected_error
):
    """Finding 12.3 retires a Phase 6 concern: the worst case is 1.53%.

    Each well is evaluated at its own state point -- the effect is strongly
    state-dependent, so a generic one gives a different answer. Capacity is
    linear in density, so the density error is the capacity error.
    """
    pressure = BRINE_DENSITY * GRAVITY * depth_m
    temperature_error = depth_gap_m / 1000 * 30.0

    base = co2_density_kg_m3(pressure, temperature_k)
    shifted = co2_density_kg_m3(pressure, temperature_k - temperature_error)
    relative = (shifted - base) / base
    assert relative == pytest.approx(expected_error, abs=0.002)
    assert abs(relative) < 0.02, "the smallest effect in the audit"


# -- Finding 12.4: the combined net effect -----------------------------------


def combined_factor(depth_m, temperature_k, elevation_m, net_to_gross):
    """Conditional scenario product of findings 3.1, 4.1 and 4.2 (sea-level water
    level; 11.1 not included). Historical audit material (F2): not an estimate of
    true or reported capacity and not a correction factor (F1)."""
    gauge = BRINE_DENSITY * GRAVITY * depth_m
    corrected = BRINE_DENSITY * GRAVITY * (depth_m - elevation_m)

    double_count = 1.0 / net_to_gross                                   # 3.1
    absolute = co2_density_kg_m3(gauge + P_ATM_PA, temperature_k) / co2_density_kg_m3(
        gauge, temperature_k
    )                                                                   # 4.1
    datum = co2_density_kg_m3(corrected, temperature_k) / co2_density_kg_m3(
        gauge, temperature_k
    )                                                                   # 4.2
    return double_count * absolute * datum


@pytest.mark.parametrize("well,depth_m,temperature_k,elevation_m", WELLS)
def test_the_conditional_scenario_product_exceeds_one(well, depth_m, temperature_k, elevation_m):
    """CHARACTERISATION (historical, F2), Finding 12.4.

    Under the sea-level scenario and the generic NTG range, the product of the
    3.1, 4.1 and 4.2 terms exceeds 1. It is a conditional scenario product --
    not a statement about true or reported capacity and not a correction (F1).
    Excludes the EOS term (11.1), which needs CoolProp.
    """
    low = combined_factor(depth_m, temperature_k, elevation_m, NET_TO_GROSS_RANGE[1])
    high = combined_factor(depth_m, temperature_k, elevation_m, NET_TO_GROSS_RANGE[0])
    assert low > 1.0, "the conditional product exceeds 1 under this scenario"
    assert high > low
    assert high < 6.0, "and it stays inside the audited bound"


@pytest.mark.parametrize("well,depth_m,temperature_k,elevation_m", WELLS)
def test_the_31_term_dominates_the_conditional_product(well, depth_m, temperature_k, elevation_m):
    """Finding 12.4's structure (historical, F2): without the 3.1 term the product
    stays within 0.84-1.01. On the approved path 3.1 is resolved by the gross
    formulation (A1, A4), so the term does not arise there."""
    without_31 = combined_factor(depth_m, temperature_k, elevation_m, 1.0)
    assert 0.84 < without_31 < 1.01, "without 3.1 the conditional product stays near 1"

    with_31_low = combined_factor(depth_m, temperature_k, elevation_m, NET_TO_GROSS_RANGE[1])
    assert with_31_low / without_31 == pytest.approx(1 / 0.75, rel=1e-9)


def test_the_sea_level_scenario_state_has_the_lower_density():
    """Finding 4.2 as a scenario contrast: evaluating the brine column from sea
    level instead of ground level lowers CO2 density at the same temperature.
    This is the direction of SEA_LEVEL_SENSITIVITY vs GROUND_REFERENCE, not a
    measured error in either (M2)."""
    depth_m, temperature_k, elevation_m = 1527.5, 318.15, 310.0
    gauge = BRINE_DENSITY * GRAVITY * depth_m
    corrected = BRINE_DENSITY * GRAVITY * (depth_m - elevation_m)
    datum_factor = co2_density_kg_m3(corrected, temperature_k) / co2_density_kg_m3(
        gauge, temperature_k
    )
    assert datum_factor < 1.0


# -- Finding 12.5: bias vs band ----------------------------------------------


def test_the_systematic_bias_can_exceed_the_reported_band():
    """CHARACTERISATION, Finding 12.5 -- the audit's key interpretive result.

    A systematic scenario effect can be larger than the sampled band, so the band
    does not bracket it (S7: P10/P50/P90 are conditional on the declared model).
    The comparison uses the historical conditional product (F2) as the size of
    that effect; it is not an estimate of true capacity (F1).
    """
    depth_m, temperature_k, elevation_m = 1527.5, 318.15, 310.0
    pressure = BRINE_DENSITY * GRAVITY * depth_m
    priors = UniformPriors(
        area_m2=(8e7, 8e7), thickness_m=(35.0, 35.0), porosity=(0.10, 0.35),
        pressure_pa=(pressure * 0.98, pressure * 1.02),
        temperature_k=(temperature_k, temperature_k),
        storage_efficiency=(0.01, 0.04),
    )
    result = run_capacity_mc(priors.sample(20_000, seed=42))
    band_upper = result.p90_mt / result.p50_mt

    bias_upper = combined_factor(depth_m, temperature_k, elevation_m, NET_TO_GROSS_RANGE[0])
    assert bias_upper > band_upper, (
        "the bias upper bound must exceed P90/P50 for this finding to hold"
    )


def test_the_band_omits_every_systematic_finding():
    """Only three priors vary, and none of them represents a bias."""
    priors = UniformPriors(
        area_m2=(8e7, 8e7), thickness_m=(35.0, 35.0), porosity=(0.10, 0.35),
        pressure_pa=(1.5e7, 1.6e7), temperature_k=(318.15, 318.15),
        storage_efficiency=(0.01, 0.04),
    )
    varying = [
        name for name in ("area_m2", "thickness_m", "porosity",
                          "pressure_pa", "temperature_k", "storage_efficiency")
        if getattr(priors, name)[0] < getattr(priors, name)[1]
    ]
    assert sorted(varying) == ["porosity", "pressure_pa", "storage_efficiency"]


# -- consistency of the axes that do agree -----------------------------------


def test_temperature_reaches_capacity_through_exactly_one_path():
    """The density call is the only consumer, so no divergent conversion exists."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src" / "ccs_screen"
    call_sites = [
        path for path in root.rglob("*.py")
        if "co2_density_kg_m3(" in path.read_text(encoding="utf-8")
        and path.name not in ("properties.py", "__init__.py")
    ]
    assert [p.name for p in call_sites] == ["monte_carlo.py"]


def test_injectivity_is_absent_from_the_public_surface():
    """Three of the five HIGH findings are contained by this fact."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src" / "ccs_screen"
    # The net-to-gross criterion vocabulary names permeability as a *label* for
    # what defined "net" (docs/net-to-gross-semantics.md section 3). It is not an
    # injectivity input and carries no value, so only those tokens are exempt.
    ntg_vocabulary = ("porosity_permeability", "permeability_only",
                      "porosity and permeability")
    for name in ("api.py", "web/schemas.py"):
        text = (root / name).read_text(encoding="utf-8").lower()
        for token in ntg_vocabulary:
            text = text.replace(token, "")
        assert "theis" not in text
        assert "permeability" not in text


# -- F1: single joint scenario evaluation (approved model) --------------------


def test_the_approved_model_reports_joint_scenarios_not_a_product():
    """F1: baseline, individual effect and joint scenarios; never a multiplied factor."""
    from ccs_screen.approved_model import (
        StorageInterval,
        WaterLevelScenario,
        evaluate_approved_model,
    )
    from ccs_screen.ingest.identity import canonical_well_id
    from ccs_screen.ingest.provenance import Confidence, FieldValue, Provenance, Unit
    from ccs_screen.ingest.records import NormalizedWellRecord, TemperatureObservation
    from ccs_screen.ingest.units import DepthDatum

    depth_m, temperature_k, elevation_m = 1527.5, 318.15, 310.0
    record = NormalizedWellRecord(identity=canonical_well_id("F1 PROBE 1"))
    record.depth_m = FieldValue(value=depth_m, unit=Unit.METRE, provenance=Provenance.EXTRACTED,
                                confidence=Confidence.HIGH)
    record.surface_elevation_m = FieldValue(value=elevation_m, unit=Unit.METRE,
                                            provenance=Provenance.EXTRACTED,
                                            confidence=Confidence.MEDIUM)
    record.depth_datum = DepthDatum.GROUND_LEVEL
    record.temperatures = (TemperatureObservation(
        depth_m=1500.0, temperature_k=temperature_k, method="extrapolated_squarci_taffi",
        depth_datum=DepthDatum.GROUND_LEVEL),)
    result = evaluate_approved_model(record, area_m2=8e7, interval=StorageInterval(1450.0, 1527.5),
                                     n=400, seed=42)
    effect = result.systematic_effect()
    assert effect["baseline"] == WaterLevelScenario.GROUND_REFERENCE.value
    assert effect["multiplied_correction_factor"] is None
    (individual,) = effect["individual_effects"]
    ground = result.scenario(WaterLevelScenario.GROUND_REFERENCE).capacity
    sea = result.scenario(WaterLevelScenario.SEA_LEVEL_SENSITIVITY).capacity
    assert individual["p50_difference_mt"] == sea.p50_mt - ground.p50_mt
    assert individual["is_correction"] is False
    # The contrast has the direction of the historical 4.2 term, as a scenario.
    assert sea.p50_mt < ground.p50_mt
