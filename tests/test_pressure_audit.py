"""Phase 4 audit regression tests for the pressure model.

``P = rho g z`` is arithmetically exact, so most of these tests are about the
three things that are *not* pinned by the arithmetic: which pressure convention
the result is in, what surface ``z`` is measured from, and whether the fracture
comparison subtracts two compatible quantities.

Several tests below assert the *current, flawed* behaviour rather than the
correct behaviour. They are marked as characterisation tests and name the
finding they pin. That is deliberate: Phase 4 found defects it was not
authorised to fix, and a test that locks in today's behaviour is how the defect
stays visible until someone decides to change it. Each one says what it should
assert instead once the corresponding finding is resolved.

See ``docs/scientific-validation-audit.md``, Phase 4.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from ccs_screen.ingest.assumptions import AssumptionSet
from ccs_screen.ingest.records import DepthDatum
from ccs_screen.ingest.scenario import (
    LITERATURE_SCREENING_V1,
    STANDARD_GRAVITY_M_S2,
    ScreeningScenario,
)
from ccs_screen.ingest.units import DepthMeasurement, UnitError
from ccs_screen.pressure import (
    DEFAULT_FRACTURE_GRADIENT_PA_M,
    DEFAULT_SAFETY_FACTOR,
    allowable_delta_p_pa,
    fracture_pressure_pa,
    theis_injection_delta_p_pa,
)
from ccs_screen.properties import co2_density_kg_m3

#: Standard atmosphere, exact by definition. Used only to measure the size of
#: the offset in Finding 4.1 -- it is deliberately NOT added to the model.
P_ATM_PA = 101_325.0

CASES = [
    ("shallow pilot", 1020.0, 897.0),
    ("SALUZZO-like", 1050.0, 1527.5),
    ("mid", 1060.0, 3000.0),
    ("deep pilot", 1100.0, 6694.0),
]


def scenario_with_brine(density):
    return ScreeningScenario(
        name="audit-probe",
        description="Phase 4 audit probe scenario.",
        assumptions=AssumptionSet(name="audit-probe"),
        brine_density_kg_m3=density,
    )


def independent_hydrostatic_pa(rho, z):
    """Exact rational P = rho g z, gauge. No production import."""
    return Fraction(str(rho)) * Fraction(str(STANDARD_GRAVITY_M_S2)) * Fraction(str(z))


# -- arithmetic --------------------------------------------------------------


@pytest.mark.parametrize("name,rho,z", CASES)
def test_matches_independent_rational_implementation(name, rho, z):
    low, high = scenario_with_brine(rho).hydrostatic_pressure_pa(z)
    assert low == high, "a point density must give a point pressure"
    assert low == pytest.approx(float(independent_hydrostatic_pa(rho, z)), rel=1e-15)


@pytest.mark.parametrize("factor", [2.0, 3.0, 10.0])
def test_exactly_linear_in_depth(factor):
    s = scenario_with_brine(1050.0)
    base = s.hydrostatic_pressure_pa(1000.0)[0]
    assert s.hydrostatic_pressure_pa(1000.0 * factor)[0] / base == pytest.approx(factor, abs=1e-12)


@pytest.mark.parametrize("factor", [2.0, 3.0])
def test_exactly_linear_in_brine_density(factor):
    base = scenario_with_brine(1050.0).hydrostatic_pressure_pa(1000.0)[0]
    scaled = scenario_with_brine(1050.0 * factor).hydrostatic_pressure_pa(1000.0)[0]
    assert scaled / base == pytest.approx(factor, abs=1e-12)


def test_density_range_propagates_as_a_pressure_range():
    """A declared brine range must stay a range, not collapse to a point."""
    low, high = scenario_with_brine((1020.0, 1100.0)).hydrostatic_pressure_pa(1500.0)
    assert low < high
    assert low == pytest.approx(1020.0 * STANDARD_GRAVITY_M_S2 * 1500.0, rel=1e-15)
    assert high == pytest.approx(1100.0 * STANDARD_GRAVITY_M_S2 * 1500.0, rel=1e-15)


# -- Finding 4.1: gauge vs absolute ------------------------------------------


def test_model_is_gauge_not_absolute():
    """CHARACTERISATION, Finding 4.1.

    Zero depth returns 0 Pa, i.e. vacuum, so the model is gauge. Both consumers
    (the EOS and the fracture comparison) require absolute pressure.

    When Finding 4.1 is resolved this must assert P(0) == P_ATM_PA instead.
    """
    assert scenario_with_brine(1050.0).hydrostatic_pressure_pa(0.0)[0] == 0.0


def test_no_atmospheric_term_anywhere_in_the_pressure_path():
    """CHARACTERISATION, Finding 4.1. Pins the absence so a fix is deliberate."""
    s = scenario_with_brine(1050.0)
    for z in (100.0, 1500.0, 5000.0):
        assert s.hydrostatic_pressure_pa(z)[0] == pytest.approx(
            1050.0 * STANDARD_GRAVITY_M_S2 * z, rel=1e-15
        ), "an atmospheric offset appeared; update Finding 4.1 and this test together"


@pytest.mark.parametrize("name,rho,z", CASES)
def test_atmospheric_offset_is_small_but_not_negligible_shallow(name, rho, z):
    """Quantifies Finding 4.1 so the bound cannot drift unnoticed."""
    gauge = scenario_with_brine(rho).hydrostatic_pressure_pa(z)[0]
    fraction = P_ATM_PA / gauge
    assert fraction < 0.012, "offset should be at most ~1.1% at the shallowest pilot"
    if z < 1000:
        assert fraction > 0.010


def test_gauge_pressure_understates_co2_density_most_at_shallow_depth():
    """Finding 4.1: the density bias is 4.1% at 897 m, 0.09% at 6694 m.

    The shallow case is large because that state point sits on the steep part
    of the CO2 isotherm -- the same near-critical sensitivity as Phase 1.
    """
    shallow_rho, shallow_z = 1020.0, 897.0
    temperature_k = 288.15 + 0.030 * shallow_z
    gauge = shallow_rho * STANDARD_GRAVITY_M_S2 * shallow_z
    bias = (
        co2_density_kg_m3(gauge + P_ATM_PA, temperature_k)
        - co2_density_kg_m3(gauge, temperature_k)
    ) / co2_density_kg_m3(gauge + P_ATM_PA, temperature_k)
    assert 0.03 < bias < 0.05, f"shallow density bias moved from the audited 4.15%: {bias:.4f}"


# -- Finding 4.2: depth datum ------------------------------------------------


def test_unknown_datum_refuses_to_produce_a_sub_sea_depth():
    """The ingestion layer is correct: it raises rather than guessing."""
    with pytest.raises(UnitError):
        DepthMeasurement(value_m=1500.0, datum=DepthDatum.UNKNOWN).to_msl()


def test_known_datum_without_elevation_also_refuses():
    with pytest.raises(UnitError):
        DepthMeasurement(value_m=1500.0, datum=DepthDatum.ROTARY_TABLE).to_msl()


def test_datum_correction_subtracts_the_elevation():
    corrected = DepthMeasurement(
        value_m=1500.0, datum=DepthDatum.ROTARY_TABLE, datum_elevation_m=120.0
    ).to_msl()
    assert corrected.value_m == pytest.approx(1380.0)
    assert corrected.datum is DepthDatum.MEAN_SEA_LEVEL


def test_hydrostatic_model_accepts_an_uncorrected_depth():
    """CHARACTERISATION, Finding 4.2 -- the largest effect found in Phase 4.

    ``hydrostatic_pressure_pa`` takes a bare float. It cannot tell a sub-sea
    depth from an along-hole depth measured from a rotary table 238.7 m above
    sea level, and the scenario layer passes it the uncorrected one.
    """
    s = scenario_with_brine(1050.0)
    raw = s.hydrostatic_pressure_pa(1500.0)[0]
    corrected = s.hydrostatic_pressure_pa(1500.0 - 120.0)[0]
    assert raw > corrected
    assert (raw - corrected) / corrected == pytest.approx(0.0870, abs=0.001)


def test_documented_rotary_table_elevations_are_multi_megapascal():
    """Finding 4.2 magnitude, using the two elevations the sources state."""
    for elevation_m, expected_mpa in ((120.00, 1.20), (238.7, 2.39)):
        overstatement_pa = 1020.0 * STANDARD_GRAVITY_M_S2 * elevation_m
        assert overstatement_pa / 1e6 == pytest.approx(expected_mpa, abs=0.01)


# -- fracture pressure -------------------------------------------------------


def test_fracture_gradient_is_within_normal_clastic_practice():
    """0.6631 psi/ft and 1.530 SG equivalent mud weight, derived independently."""
    psi_per_ft = DEFAULT_FRACTURE_GRADIENT_PA_M * 0.3048 / 6894.757
    assert 0.60 < psi_per_ft < 0.80
    assert psi_per_ft == pytest.approx(0.6631, abs=0.001)
    equivalent_mud_weight_sg = DEFAULT_FRACTURE_GRADIENT_PA_M / STANDARD_GRAVITY_M_S2 / 1000
    assert equivalent_mud_weight_sg == pytest.approx(1.530, abs=0.001)


def test_fracture_pressure_does_not_depend_on_brine_density():
    """The two pressure models must stay independently defined."""
    import inspect

    parameters = inspect.signature(fracture_pressure_pa).parameters
    assert "depth_m" in parameters
    assert not any("brine" in p or "density" in p for p in parameters)


@pytest.mark.parametrize("name,rho,z", CASES)
def test_headroom_matches_independent_recomputation(name, rho, z):
    initial_pressure_pa = rho * STANDARD_GRAVITY_M_S2 * z
    independent = max(
        DEFAULT_SAFETY_FACTOR * z * DEFAULT_FRACTURE_GRADIENT_PA_M - initial_pressure_pa, 0.0
    )
    produced = allowable_delta_p_pa(initial_pressure_pa=initial_pressure_pa, depth_m=z)
    assert produced == pytest.approx(independent, rel=1e-15)


@pytest.mark.parametrize("name,rho,z", CASES)
def test_fracture_exceeds_hydrostatic_by_a_physical_margin(name, rho, z):
    ratio = fracture_pressure_pa(z) / (rho * STANDARD_GRAVITY_M_S2 * z)
    assert 1.3 < ratio < 1.6


def test_no_injection_window_returns_zero_not_a_negative_headroom():
    assert allowable_delta_p_pa(initial_pressure_pa=5e7, depth_m=1500.0) == 0.0


@pytest.mark.parametrize("safety_factor", [0.0, -0.1, 1.5])
def test_safety_factor_outside_its_interval_is_rejected(safety_factor):
    with pytest.raises(ValueError):
        allowable_delta_p_pa(initial_pressure_pa=1e7, depth_m=1500.0, safety_factor=safety_factor)


# -- convention compatibility ------------------------------------------------


def test_theis_delta_p_is_invariant_under_a_pressure_offset():
    """Why Phase 5 is unblocked: a difference does not carry a convention.

    Theis takes no absolute pressure at all, so Finding 4.1 cannot reach it.
    """
    import inspect

    parameters = inspect.signature(theis_injection_delta_p_pa).parameters
    assert not any("pressure" in p for p in parameters), (
        "Theis gained an absolute-pressure argument; it would now inherit Finding 4.1"
    )


def test_headroom_mixes_a_gauge_initial_against_an_absolute_limit():
    """CHARACTERISATION, Finding 4.1: headroom is overstated by exactly P_atm.

    Once the hydrostatic model returns absolute pressure this difference
    becomes zero and this test must be replaced.
    """
    z, rho = 1527.5, 1050.0
    gauge = rho * STANDARD_GRAVITY_M_S2 * z
    mixed = allowable_delta_p_pa(initial_pressure_pa=gauge, depth_m=z)
    consistent = allowable_delta_p_pa(initial_pressure_pa=gauge + P_ATM_PA, depth_m=z)
    assert mixed - consistent == pytest.approx(P_ATM_PA, rel=1e-9)
    assert (mixed - consistent) / consistent == pytest.approx(0.0212, abs=0.001)


# -- brine density -----------------------------------------------------------


def test_literature_scenario_gradient_is_normally_pressured():
    """10.00-10.79 kPa/m: between seawater and moderately saline formation water."""
    low, high = LITERATURE_SCREENING_V1.pressure_gradient_pa_per_m()
    assert low == pytest.approx(10_002.8, abs=1.0)
    assert high == pytest.approx(10_787.3, abs=1.0)
    assert low > 1000.0 * STANDARD_GRAVITY_M_S2, "must exceed pure water"
    assert high < 1200.0 * STANDARD_GRAVITY_M_S2, "must stay below saturated NaCl brine"


def test_brine_density_is_a_flat_assumption_not_a_correlation():
    """Finding 4.6: no temperature or salinity dependence, by design.

    Pinned so a correlation cannot be introduced without revisiting the audit.
    """
    import inspect

    source = inspect.getsource(ScreeningScenario.pressure_gradient_pa_per_m)
    for term in ("temperature", "salinity", "tds", "nacl"):
        assert term not in source.lower()


# -- edge cases --------------------------------------------------------------


def test_zero_depth_gives_zero_gauge_pressure():
    assert scenario_with_brine(1050.0).hydrostatic_pressure_pa(0.0) == (0.0, 0.0)


def test_negative_depth_is_accepted_and_returns_negative_pressure():
    """CHARACTERISATION, Finding 4.7.

    ``pressure.py`` guards every input with ``_require_positive``;
    ``hydrostatic_pressure_pa`` guards none. Not reachable through ingestion,
    which parses positive depths, but the two modules disagree.
    """
    assert scenario_with_brine(1050.0).hydrostatic_pressure_pa(-100.0)[0] < 0


@pytest.mark.parametrize("depth_m", [0.0, -1.0])
def test_fracture_pressure_rejects_non_positive_depth(depth_m):
    with pytest.raises(ValueError):
        fracture_pressure_pa(depth_m)


def test_scenario_without_brine_density_refuses_to_derive_pressure():
    from ccs_screen.ingest.assumptions import AssumptionError

    with pytest.raises(AssumptionError):
        scenario_with_brine(None).hydrostatic_pressure_pa(1500.0)
