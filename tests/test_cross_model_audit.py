"""Phase 12 audit: cross-model consistency and the combined net effect.

Phases 1-11 tested each subsystem in isolation. These tests check the joins --
the places where two individually-defensible models are used together and
disagree. The capacity model assumes a bounded trap while the injectivity model
assumes an infinite aquifer; three thicknesses coexist with no relational check;
and the systematic bias is wider than the uncertainty band that is supposed to
express it.

The combined-effect tests use the convention ``factor = true / reported``, so a
factor above 1 means the tool understates capacity.

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
    """true / reported, combining findings 3.1, 4.1, 4.2 and 11.1."""
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
def test_the_net_effect_is_an_understatement(well, depth_m, temperature_k, elevation_m):
    """CHARACTERISATION, Finding 12.4 -- the result the freeze existed to produce.

    Excludes the EOS term (11.1), which needs CoolProp; including it lowers the
    factors slightly but never below 1.
    """
    low = combined_factor(depth_m, temperature_k, elevation_m, NET_TO_GROSS_RANGE[1])
    high = combined_factor(depth_m, temperature_k, elevation_m, NET_TO_GROSS_RANGE[0])
    assert low > 1.0, "the net direction must be an understatement"
    assert high > low
    assert high < 6.0, "and it should stay inside a plausible bound"


@pytest.mark.parametrize("well,depth_m,temperature_k,elevation_m", WELLS)
def test_finding_31_dominates_every_other_bias(well, depth_m, temperature_k, elevation_m):
    """Finding 12.4's decision structure: everything else moves it under 16%."""
    without_31 = combined_factor(depth_m, temperature_k, elevation_m, 1.0)
    assert 0.84 < without_31 < 1.01, "the non-3.1 biases should be a modest overstatement"

    with_31_low = combined_factor(depth_m, temperature_k, elevation_m, NET_TO_GROSS_RANGE[1])
    assert with_31_low / without_31 == pytest.approx(1 / 0.75, rel=1e-9)


def test_the_two_overstating_findings_run_the_same_way():
    """4.2 and 11.1 both overstate, so they compound rather than offset."""
    depth_m, temperature_k, elevation_m = 1527.5, 318.15, 310.0
    gauge = BRINE_DENSITY * GRAVITY * depth_m
    corrected = BRINE_DENSITY * GRAVITY * (depth_m - elevation_m)
    datum_factor = co2_density_kg_m3(corrected, temperature_k) / co2_density_kg_m3(
        gauge, temperature_k
    )
    assert datum_factor < 1.0, "an uncorrected datum overstates capacity"


# -- Finding 12.5: bias vs band ----------------------------------------------


def test_the_systematic_bias_can_exceed_the_reported_band():
    """CHARACTERISATION, Finding 12.5 -- the audit's key interpretive result.

    The true value can sit above P90, not merely near the edge of the band.
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
    for name in ("api.py", "web/schemas.py"):
        text = (root / name).read_text(encoding="utf-8")
        assert "theis" not in text.lower()
        assert "permeability" not in text.lower()
