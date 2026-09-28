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

Phase 14 (approved Model Contract). The Finding 4.1 characterisations below now
describe the NOT_VALIDATED legacy resolver (``ScreeningScenario``), which owner
decision O2 keeps unchanged: it is still gauge. The approved model adds
``P_atm = 101 325 Pa`` at the EOS input (B1) and evaluates pressure at
``z_state`` relative to a named water level (M1, M2); that is tested in the
"approved pressure" section and in ``tests/test_approved_model.py``. The fracture
gradient and safety factor have no default any more (D1, rule B), so the
fracture tests pass arbitrary caller-supplied values.
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
from ccs_screen.approved_model import P_ATM_PA as APPROVED_P_ATM_PA
from ccs_screen.approved_model import eos_pressure_pa
from ccs_screen.pressure import (
    allowable_delta_p_pa,
    fracture_pressure_pa,
    theis_injection_delta_p_pa,
)
from ccs_screen.properties import co2_density_kg_m3

#: Standard atmosphere, exact by definition. Used here to measure the size of
#: the offset in Finding 4.1 on the legacy resolver, which does not add it. The
#: approved model adds it (B1); see the "approved pressure" section.
P_ATM_PA = 101_325.0

#: Arbitrary caller-supplied fracture criterion for the arithmetic tests. No
#: gradient or safety factor is approved and neither has a default (D1).
CALLER_GRADIENT_PA_M = 17_000.0
CALLER_SAFETY_FACTOR = 0.8

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
    """CHARACTERISATION, Finding 4.1 -- legacy resolver (NOT_VALIDATED, O2).

    Zero depth returns 0 Pa, i.e. vacuum, so the legacy model is gauge. Finding
    4.1 is resolved on the approved path only (B1):
    ``test_approved_pressure_is_absolute_at_the_water_level`` asserts
    P(z_state = z_wl) == P_ATM_PA there.
    """
    assert scenario_with_brine(1050.0).hydrostatic_pressure_pa(0.0)[0] == 0.0


def test_no_atmospheric_term_anywhere_in_the_pressure_path():
    """CHARACTERISATION, Finding 4.1 -- legacy resolver only. O2 keeps the legacy
    arithmetic unchanged, so the absence is still pinned there."""
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
    """CHARACTERISATION, Finding 4.2 / 10.2 revision. `hydrostatic_pressure_pa`
    takes a bare float and applies no depth-reference or water-level offset;
    the scenario passes the ingested depth unchanged. The 120 m shift below is
    a sensitivity, not a measured datum error, and its direction is not
    established.
    """
    s = scenario_with_brine(1050.0)
    raw = s.hydrostatic_pressure_pa(1500.0)[0]
    corrected = s.hydrostatic_pressure_pa(1500.0 - 120.0)[0]
    assert raw > corrected
    assert (raw - corrected) / corrected == pytest.approx(0.0870, abs=0.001)


def test_documented_rotary_table_elevations_are_multi_megapascal():
    """Finding 4.2 sensitivity to the two rotary-table elevations the sources
    state (not a measured error; see the 4.2 / 10.2 revision)."""
    for elevation_m, expected_mpa in ((120.00, 1.20), (238.7, 2.39)):
        overstatement_pa = 1020.0 * STANDARD_GRAVITY_M_S2 * elevation_m
        assert overstatement_pa / 1e6 == pytest.approx(expected_mpa, abs=0.01)


# -- fracture pressure -------------------------------------------------------


def test_no_fracture_gradient_or_safety_factor_default_exists():
    """D1, rule B. Replaces the characterisation of the removed 15 000 Pa/m
    default (0.6631 psi/ft), which is no longer part of any code path."""
    import inspect

    import ccs_screen.pressure as pressure

    assert not [name for name in dir(pressure) if name.startswith("DEFAULT_")]
    for function in (fracture_pressure_pa, allowable_delta_p_pa):
        for name in ("fracture_gradient_pa_m", "safety_factor"):
            parameter = inspect.signature(function).parameters.get(name)
            if parameter is not None:
                assert parameter.default is inspect.Parameter.empty, (function.__name__, name)


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
        CALLER_SAFETY_FACTOR * z * CALLER_GRADIENT_PA_M - initial_pressure_pa, 0.0
    )
    produced = allowable_delta_p_pa(initial_pressure_pa=initial_pressure_pa, depth_m=z,
                                    fracture_gradient_pa_m=CALLER_GRADIENT_PA_M,
                                    safety_factor=CALLER_SAFETY_FACTOR)
    assert produced == pytest.approx(independent, rel=1e-15)


def test_no_injection_window_returns_zero_not_a_negative_headroom():
    assert allowable_delta_p_pa(initial_pressure_pa=5e7, depth_m=1500.0,
                                fracture_gradient_pa_m=CALLER_GRADIENT_PA_M,
                                safety_factor=CALLER_SAFETY_FACTOR) == 0.0


@pytest.mark.parametrize("safety_factor", [0.0, -0.1, 1.5])
def test_safety_factor_outside_its_interval_is_rejected(safety_factor):
    with pytest.raises(ValueError):
        allowable_delta_p_pa(initial_pressure_pa=1e7, depth_m=1500.0,
                             fracture_gradient_pa_m=CALLER_GRADIENT_PA_M,
                             safety_factor=safety_factor)


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
    """CHARACTERISATION, Finding 4.1 revision: if the fracture gradient is
    absolute, headroom is overstated by exactly P_atm; its convention is
    undocumented, so this is conditional, not a confirmed defect. B2 is DEFERRED
    and no fracture criterion is approved (D1), so the criterion is caller-supplied.
    Replace this test once the convention is declared.
    """
    z, rho = 1527.5, 1050.0
    gauge = rho * STANDARD_GRAVITY_M_S2 * z
    criterion = dict(fracture_gradient_pa_m=CALLER_GRADIENT_PA_M,
                     safety_factor=CALLER_SAFETY_FACTOR)
    mixed = allowable_delta_p_pa(initial_pressure_pa=gauge, depth_m=z, **criterion)
    consistent = allowable_delta_p_pa(initial_pressure_pa=gauge + P_ATM_PA, depth_m=z, **criterion)
    assert mixed - consistent == pytest.approx(P_ATM_PA, rel=1e-9)
    independent = CALLER_SAFETY_FACTOR * CALLER_GRADIENT_PA_M * z - gauge - P_ATM_PA
    assert (mixed - consistent) / consistent == pytest.approx(P_ATM_PA / independent, rel=1e-9)


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
        fracture_pressure_pa(depth_m, CALLER_GRADIENT_PA_M)


# -- approved pressure (B1, M1, M2) -------------------------------------------


def test_approved_pressure_is_absolute_at_the_water_level():
    """Finding 4.1 resolved on the approved path: P_EOS(z_state = z_wl) = P_atm."""
    assert APPROVED_P_ATM_PA == P_ATM_PA
    assert eos_pressure_pa(1050.0, 0.0, 0.0) == P_ATM_PA
    assert eos_pressure_pa(1050.0, 250.0, 250.0) == P_ATM_PA


@pytest.mark.parametrize("name,rho,z", CASES)
def test_approved_pressure_matches_independent_rational_implementation(name, rho, z):
    expected = Fraction(str(P_ATM_PA)) + independent_hydrostatic_pa(rho, z)
    assert eos_pressure_pa(rho, z, 0.0) == pytest.approx(float(expected), rel=1e-15)


def test_approved_pressure_depends_on_the_state_point_not_total_depth():
    """M1/S1: the state point is z_state; total depth is not an argument."""
    import inspect

    assert list(inspect.signature(eos_pressure_pa).parameters) == [
        "brine_density_kg_m3", "z_state_m", "z_wl_m"]


def test_scenario_without_brine_density_refuses_to_derive_pressure():
    from ccs_screen.ingest.assumptions import AssumptionError

    with pytest.raises(AssumptionError):
        scenario_with_brine(None).hydrostatic_pressure_pa(1500.0)
